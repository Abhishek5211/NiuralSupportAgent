import asyncio
from collections.abc import Callable
import logging
import re
import time

from agents import Agent, MaxTurnsExceeded, ModelSettings, OpenAIChatCompletionsModel, OpenAIResponsesModel, RunConfig, RunHooks, Runner
from agents.retry import ModelRetrySettings
from openai import APIConnectionError, APIStatusError, AsyncOpenAI
from openai.types.shared import Reasoning
from openai.types.responses import ResponseTextDeltaEvent

from .config import BENCHMARK_DIR, Config, EMPLOYER_ID, MOCK_DIR, PACKAGE_DIR
from mock_api import MockAPI
from .models import ChatRequest, Judgment, Outcome
from .tools import build_tools


def usage_dict(result):
    usage = result.context_wrapper.usage
    return {key: getattr(usage, key, 0) for key in
            ("requests", "input_tokens", "output_tokens", "total_tokens")}


def safe_error(exc):
    if isinstance(exc, APIStatusError):
        body = exc.body if isinstance(exc.body, dict) else {}
        body = body.get("error", body)
        detail = str(body.get("message", "")) if isinstance(body, dict) else ""
        detail = re.sub(r"(?:gsk_|sk-)[A-Za-z0-9_*.-]+", "[REDACTED]", detail)[:800]
        return {"type": "model_service_error", "http_status": exc.status_code,
                "message": f"Model provider returned HTTP {exc.status_code}. Check the key, model access and quota.",
                "detail": detail}
    if isinstance(exc, APIConnectionError):
        return {"type": "connection_error", "message": "The model service could not be reached."}
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return {"type": "timeout", "message": "The agent exceeded its time limit."}
    if isinstance(exc, MaxTurnsExceeded):
        return {"type": "step_limit", "message": "The agent exceeded its model-turn limit."}
    # Never serialize raw exception messages, which can include request credentials.
    return {"type": type(exc).__name__, "message": "The run failed. Check the model and configuration."}


class AccountContext(RunHooks):
    async def on_tool_end(self, context, agent, tool, result):
        context.context["account_data_loaded"] = True


class SupportAgent:
    def __init__(self, config: Config, *, client=None, model=None):
        self.config = config
        # SDK exceptions may echo a masked API key; expose only safe errors.
        logging.getLogger("openai.agents").setLevel(logging.CRITICAL)
        self.client = client or AsyncOpenAI(api_key=config.api_key or "missing-key", base_url=config.base_url,
                                            max_retries=0, timeout=45)
        settings = ModelSettings(temperature=0, max_tokens=1400, parallel_tool_calls=False,
                                 retry=None if config.provider == "groq" else ModelRetrySettings(max_retries=0))
        if config.provider == "groq":
            settings.reasoning = Reasoning(effort="low")
        else:
            settings.store = False
        base = (PACKAGE_DIR / "prompt.txt").read_text(encoding="utf-8")
        api_reference = (MOCK_DIR / "API_DOCUMENTATION.md").read_text(encoding="utf-8")
        guide = (MOCK_DIR / "PRODUCT_GUIDE.md").read_text(encoding="utf-8")
        self.account_instructions = base + "\n\nSOURCE: mock_api/API_DOCUMENTATION.md\n" + api_reference
        instructions = self.account_instructions + "\n\nSOURCE: mock_api/PRODUCT_GUIDE.md\n" + guide
        self.agent = Agent(name="Niural support v1", instructions=instructions,
                           model=model or self._model(config.model),
                           tools=build_tools(MockAPI(config.mock_token)), model_settings=settings)
        # Application-managed history is the SDK's local replay strategy. No
        # server-managed conversation IDs or shared history are mixed into it.
        self.histories = {}
        self.locks = {}

    def _model(self, name):
        model_class = OpenAIChatCompletionsModel if self.config.provider == "groq" else OpenAIResponsesModel
        return model_class(name, self.client)

    def reset(self, session_id: str):
        self.histories.pop((EMPLOYER_ID, session_id), None)

    async def close(self):
        await self.client.close()

    async def ask(self, session_id: str, question: str, *, context=None,
                  on_text: Callable[[str], None] | None = None):
        """Answer a message; optionally send streamed text to on_text."""
        request = ChatRequest(session_id=session_id, message=question)
        session_id, question = request.session_id, request.message
        key = (EMPLOYER_ID, session_id)
        if key not in self.locks and len(self.locks) >= 100:
            raise ValueError("Session capacity reached; create a new agent instance.")
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            started = time.perf_counter()
            if context and key in self.histories:
                raise ValueError("Initial context can only seed a fresh conversation")
            initial = self.histories.get(key, list(context or []))
            messages = initial + [{"role": "user", "content": question}]
            account_loaded = any(item.get("type") == "function_call_output" for item in initial)
            def instructions(run_context, agent):
                # Groq free tier permits 8K TPM. Keep the API contract and fetched
                # records; avoid repeating the full product guide after a lookup.
                return self.account_instructions if run_context.context["account_data_loaded"] else self.agent.instructions
            turn_agent = self.agent.clone(instructions=instructions) if self.config.provider == "groq" else self.agent
            stream = None
            try:
                if not self.config.api_key and isinstance(self.agent.model, (OpenAIResponsesModel, OpenAIChatCompletionsModel)):
                    raise ValueError("Model provider key is not configured")
                options = dict(max_turns=self.config.max_turns,
                               context={"account_data_loaded": account_loaded},
                               hooks=AccountContext(), run_config=RunConfig(tracing_disabled=True))
                async with asyncio.timeout(self.config.turn_timeout):
                    if on_text is None:
                        result = await Runner.run(turn_agent, messages, **options)
                    else:
                        stream = Runner.run_streamed(turn_agent, messages, **options)
                        async for event in stream.stream_events():
                            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                                on_text(event.data.delta)
                        result = stream
                self.histories[key] = result.to_input_list()
                outcome = Outcome(answer=str(result.final_output), usage=usage_dict(result),
                                  latency_ms=round((time.perf_counter() - started) * 1000, 2))
            except Exception as exc:
                outcome = Outcome(error=safe_error(exc),
                                  latency_ms=round((time.perf_counter() - started) * 1000, 2))
            finally:
                if stream is not None and not stream.is_complete:
                    stream.cancel()
            return outcome

    async def judge(self, question, context, facts, answer):
        import json
        rubric = (BENCHMARK_DIR / "judge_prompt.txt").read_text(encoding="utf-8")
        judge = Agent(name="Niural correctness judge", instructions=rubric,
                      model=self._model(self.config.judge_model),
                      model_settings=ModelSettings(temperature=0, max_tokens=1000,
                                                   reasoning=Reasoning(effort="low") if self.config.provider == "groq" else None,
                                                   extra_body={"include_reasoning": False} if self.config.provider == "groq" else None,
                                                   retry=None if self.config.provider == "groq" else ModelRetrySettings(max_retries=0)),
                      )
        payload = json.dumps({"QUESTION": question, "CONTEXT": context,
                              "REFERENCE_FACTS": facts, "CANDIDATE_ANSWER": answer})
        result = await asyncio.wait_for(
            Runner.run(judge, payload, max_turns=1, run_config=RunConfig(tracing_disabled=True)),
            timeout=self.config.turn_timeout)
        text = str(result.final_output).strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1])
        return Judgment.model_validate_json(text).model_dump(), usage_dict(result)
