"""Run standalone or scripted conversation cases; judge only when requested."""

import asyncio
from collections import Counter
from copy import deepcopy
import json
from uuid import uuid4

from agents import Agent, OpenAIResponsesModel, RunConfig, Runner

from ..prompts import CORRECTNESS_PROMPT
from .faults import failure_scope, validate_faults
from ..models import Judgment
from ..runtime import error_details, model_settings, usage_dict


def case_context(case):
    """Optional initial history is explicit data, never inferred from a case ID."""
    return deepcopy(case.get("context", []))


def case_turns(case):
    """Normalize legacy single questions and explicit ordered user turns."""
    turns = case.get("turns", [{"question": case["question"]}])
    if not isinstance(turns, list) or not turns:
        raise ValueError("turns must be a nonempty list")
    if any(not isinstance(turn, dict) or not isinstance(turn.get("question"), str)
           or not turn["question"].strip() for turn in turns):
        raise ValueError("Every turn requires a nonempty question")
    if turns[-1]["question"] != case["question"]:
        raise ValueError("The last turn must match the top-level question")
    return deepcopy(turns)


def case_inputs(case):
    """Keep reference facts hidden; fault schedules control the harness, not prompts."""
    inputs = {"id": case["id"], "question": case["question"], "context": case_context(case)}
    turns = case_turns(case)
    if "turns" in case:
        inputs["turns"] = [{"question": turn["question"]} for turn in turns]
    if "faults" in case:
        validate_faults(case["faults"])
        if any(rule["turn"] > len(turns) for rule in case["faults"]):
            raise ValueError("A fault cannot reference a nonexistent turn")
        inputs["faults"] = deepcopy(case["faults"])
    if "continue_on_error" in case:
        if type(case["continue_on_error"]) is not bool:
            raise ValueError("continue_on_error must be boolean")
        inputs["continue_on_error"] = case["continue_on_error"]
    return inputs


def case_references(case):
    references = {"facts": case["facts"]}
    if "turns" in case:
        facts = [turn.get("facts") for turn in case_turns(case)]
        if any(not isinstance(value, str) or not value.strip() for value in facts):
            raise ValueError("Every scripted turn requires hidden reference facts")
        if facts[-1] != case["facts"]:
            raise ValueError("The last turn's facts must match the top-level facts")
        references["turn_facts"] = facts
        errors = [turn.get("expected_error") for turn in case_turns(case)]
        if any(errors):
            if any(value not in {None, "timeout"} for value in errors):
                raise ValueError("Only an explicit runtime timeout can be expected")
            references["turn_errors"] = errors
    return references


async def evaluate_one(agent, case, *, on_event=None):
    turns = case_turns(case)
    session_id = f"benchmark-{case['id']}-{uuid4().hex}"
    initial_context = case_context(case)
    transcript = deepcopy(initial_context)
    results = []
    usage = Counter()
    agent.reset(session_id)
    with failure_scope(case.get("faults", [])) as faults:
        try:
            for index, turn in enumerate(turns):
                faults.turn = index + 1
                # SupportAgent owns the full SDK history, including tool/reasoning items.
                # Supply seed context only on the first call; never replace its history.
                context = deepcopy(transcript)
                if index == 0:
                    outcome = await agent.ask(session_id, turn["question"], context=initial_context,
                                              on_event=on_event)
                else:
                    outcome = await agent.ask(session_id, turn["question"], on_event=on_event)
                record = {"question": turn["question"], "context": context, **outcome.model_dump()}
                if not record["error"] and not record["answer"]:
                    record["error"] = {"type": "empty_answer", "message": "The turn produced no answer."}
                results.append(record)
                usage.update(record.get("usage", {}))
                if record["error"] and not case.get("continue_on_error", False):
                    break
                transcript.extend([
                    {"role": "user", "content": turn["question"]},
                    {"role": "assistant", "content": record["error"]["message"] if record["error"] else record["answer"]},
                ])
        finally:
            agent.reset(session_id)

    complete = len(results) == len(turns) and not results[-1]["error"]
    output = {
        "id": case["id"], "question": case["question"], "session_id": session_id,
        "context": results[-1]["context"], "initial_context": initial_context,
        "answer": results[-1]["answer"] if complete else None,
        "error": results[-1]["error"], "usage": dict(usage),
        "latency_ms": round(sum(turn["latency_ms"] for turn in results), 2),
        "completed": complete, "turn_results": results,
    }
    if "faults" in case:
        output.update(fault_events=faults.events, unexercised_faults=faults.unexercised())
    return output


async def evaluate_correctness(agent, inputs, outputs, reference_outputs):
    """A conversation passes only if every executed user turn passes."""
    turns = case_turns(inputs)
    results = outputs.get("turn_results", [])
    if (outputs.get("error") or not outputs.get("answer")
            or len(results) != len(turns) or not outputs.get("completed")):
        return {"key": "correctness", "score": 0,
                "comment": "The conversation did not complete successfully."}
    facts = reference_outputs.get("turn_facts", [reference_outputs["facts"]])
    if len(facts) != len(turns):
        raise ValueError("Each conversation turn requires its own reference facts")
    errors = reference_outputs.get("turn_errors", [None] * len(turns))
    if len(errors) != len(turns):
        raise ValueError("Each conversation turn requires its own error expectation")
    if "faults" in inputs and ("unexercised_faults" not in outputs or outputs["unexercised_faults"]):
        return {"key": "correctness", "score": None,
                "comment": "Fault scenario was not fully exercised; inspect fault_events before scoring."}

    decisions = []
    judge_errors = []
    for index, (turn, result, expected, expected_error) in enumerate(zip(turns, results, facts, errors), 1):
        if expected_error:
            matches = (result.get("error") or {}).get("type") == expected_error and not result.get("answer")
            decisions.append((matches, f"Turn {index}: expected {expected_error}; received {(result.get('error') or {}).get('type', 'answer')}."))
            continue
        if result.get("error") or not result.get("answer"):
            decisions.append((False, f"Turn {index}: no successful answer."))
            continue
        try:
            verdict, _ = await agent.judge(
                turn["question"], result["context"], expected, result["answer"],
            )
            decisions.append((verdict["correct"], f"Turn {index}: {verdict['reason']}"))
        except Exception as error:
            judge_errors.append(f"Turn {index} judge unavailable: {error_details(error)['message']}")

    # A known incorrect turn fails even if another judge call is unavailable.
    failed = any(not correct for correct, _ in decisions)
    score = 0 if failed else None if judge_errors else 1
    return {"key": "correctness", "score": score,
            "comment": " ".join([reason for _, reason in decisions] + judge_errors)}


async def judge_answer(agent, question, context, facts, answer):
    """One explicitly requested judge call; no automatic retries or saving."""
    config = agent.config
    judge = Agent(
        name="Niural correctness judge",
        instructions=CORRECTNESS_PROMPT,
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
