"""Manual single-case generation and optional reference-based judging."""

import asyncio
import json

from agents import Agent, OpenAIResponsesModel, RunConfig, Runner

from .config import BENCHMARK_DIR
from .models import Judgment
from .runtime import model_settings, usage_dict


def case_context(case):
    """Case IDs are bookkeeping only; history must be explicit in the data."""
    return case.get("context", [])


async def evaluate_one(agent, case):
    session_id = f"benchmark-{case['id']}"
    agent.reset(session_id)
    context = case_context(case)
    outcome = await agent.ask(session_id, case["question"], context=context)
    return {"id": case["id"], "question": case["question"], "context": context, **outcome.model_dump()}


async def judge_answer(agent, question, context, facts, answer):
    """One explicitly requested judge call; no automatic retries or saving."""
    config = agent.config
    judge = Agent(
        name="Niural correctness judge",
        instructions=(BENCHMARK_DIR / "judge_prompt.txt").read_text(encoding="utf-8"),
        model=OpenAIResponsesModel(config.judge_model, agent.client),
        model_settings=model_settings(config.judge_model, "low"),
        output_type=Judgment,
    )
    payload = json.dumps({
        "QUESTION": question,
        "CONTEXT": context,
        "REFERENCE_FACTS": facts,
        "CANDIDATE_ANSWER": answer,
    })
    async with asyncio.timeout(config.turn_timeout):
        result = await Runner.run(
            judge, payload, max_turns=1,
            run_config=RunConfig(tracing_disabled=agent.langsmith_client is None,
                                 workflow_name="Niural correctness judge"),
        )
    return result.final_output.model_dump(), usage_dict(result)
