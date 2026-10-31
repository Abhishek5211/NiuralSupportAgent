"""Account support agent with local conversation history and optional streaming."""

import asyncio
import logging
import time
from collections.abc import Callable

from agents import Agent, OpenAIResponsesModel, RunConfig, Runner
from agents.stream_events import StreamEvent
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent

from mock_api import MockAPI
from mock_api.auth import EMPLOYER_ID
from .config import Config, PACKAGE_DIR
from .evaluate import judge_answer
from .models import ChatRequest, Outcome
from .observability import configure_langsmith
from .runtime import error_details, model_settings, usage_dict
from .tools import build_tools


class SupportAgent:
    def __init__(self, config: Config):
        self.config = config
        self.langsmith_client = configure_langsmith(config)
        logging.getLogger("openai.agents").setLevel(logging.CRITICAL)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=0,
            timeout=45,
        )
        self.agent = Agent(
            name="Niural support",
            instructions=(PACKAGE_DIR / "prompt.txt").read_text(encoding="utf-8"),
            model=OpenAIResponsesModel(config.model, self.client),
            model_settings=model_settings(config.model, "medium",
                                          parallel_tool_calls=config.parallel_tool_calls),
            tools=build_tools(MockAPI(config.mock_token)),
        )
        self.histories = {}
        self.locks = {}

    async def ask(self, session_id: str, question: str, *, context=None,
                  on_text: Callable[[str], None] | None = None,
                  on_event: Callable[[StreamEvent], None] | None = None) -> Outcome:
        request = ChatRequest(session_id=session_id, message=question)
        key = (EMPLOYER_ID, request.session_id)
        lock = self.locks.setdefault(key, asyncio.Lock())

        async with lock:
            if context and key in self.histories:
                raise ValueError("Initial context can only seed a fresh conversation")
            history = self.histories.get(key, list(context or []))
            messages = history + [{"role": "user", "content": request.message}]
            started = time.perf_counter()
            try:
                async with asyncio.timeout(self.config.turn_timeout):
                    result = await self._run(messages, on_text, on_event)
                self.histories[key] = result.to_input_list()
                return Outcome(
                    answer=str(result.final_output),
                    usage=usage_dict(result),
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            except Exception as error:
                return Outcome(
                    error=error_details(error),
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                )

    async def _run(self, messages, on_text, on_event):
        options = {
            "max_turns": self.config.max_turns,
            "run_config": RunConfig(tracing_disabled=self.langsmith_client is None,
                                    workflow_name="Niural support"),
        }
        if on_text is None and on_event is None:
            return await Runner.run(self.agent, messages, **options)

        stream = Runner.run_streamed(self.agent, messages, **options)
        try:
            async for event in stream.stream_events():
                if on_event is not None:
                    on_event(event)
                if (on_text is not None and event.type == "raw_response_event"
                        and isinstance(event.data, ResponseTextDeltaEvent)):
                    on_text(event.data.delta)
            return stream
        finally:
            if not stream.is_complete:
                stream.cancel()

    def reset(self, session_id: str):
        self.histories.pop((EMPLOYER_ID, session_id), None)

    async def close(self):
        await self.client.close()
        if self.langsmith_client is not None:
            await asyncio.to_thread(self.langsmith_client.close, timeout=10)

    async def judge(self, question, context, facts, answer):
        """Compatibility helper for the notebook; evaluation lives in evaluate.py."""
        return await judge_answer(self, question, context, facts, answer)
