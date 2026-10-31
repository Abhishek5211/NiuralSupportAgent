"""Manually evaluate full-agent FAQ answers; LLM judging is opt-in."""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from uuid import uuid4

from langsmith import tracing_context

from ..agent import SupportAgent
from ..config import BENCHMARK_DIR, Config
from .retriever import FAQCase
from .judges import RAGEvaluator
from .experiments import answer_feedback, ensure_faq_dataset
from ..runtime import error_details, git_metadata


async def answer_case(agent, case, evaluator, *, judge):
    evidence, tool_names = [], {}

    def capture(event):
        if event.type != "run_item_stream_event":
            return
        item = event.item
        if event.name == "tool_called":
            tool_names[item.call_id] = item.tool_name
        elif event.name == "tool_output":
            output = item.output
            if isinstance(output, str):
                try:
                    output = json.loads(output)
                except ValueError:
                    output = {"raw_output": output}
            evidence.append({"tool": tool_names.get(item.call_id, "tool"), "result": output})

    session_id = f"faq-answer-{case.id}-{uuid4().hex}"
    try:
        # Only the question reaches the agent. Capture actual tool evidence for judging.
        outcome = await agent.ask(session_id, case.question, on_event=capture)
    finally:
        agent.reset(session_id)
    row = {"id": case.id, "question": case.question, **outcome.model_dump(), "evidence": evidence}
    if not row["error"] and not row["answer"]:
        row["error"] = {"type": "empty_answer", "message": "No answer was generated."}
    if judge:
        if row["error"]:
            row["answer_judgment"] = {"correct": False, "grounded": False, "helpful": False,
                                      "citations_valid": False, "reason": "No successful answer was generated."}
        else:
            try:
                verdict, usage = await evaluator.judge_answer(
                    case.question, case.expected_behavior, case.required_facts, evidence, row["answer"])
                row["answer_judgment"], row["answer_judgment_usage"] = verdict, usage
            except Exception as error:
                row["answer_judgment_error"] = error_details(error)
    return row


async def evaluate(args):
    if args.output.exists():
        raise FileExistsError(f"Choose a new --output path; {args.output} already exists")
    cases = [FAQCase.model_validate(row) for row in json.loads(
        (BENCHMARK_DIR / "faq_cases.json").read_text(encoding="utf-8"))]
    agent = SupportAgent(Config.load())
    try:
        await asyncio.to_thread(agent.guide.open_index)
        config, client = agent.config, agent.langsmith_client
        evaluator = RAGEvaluator(config, agent.client, tracing=client is not None)
        metadata = {**git_metadata(), **agent.guide.metadata, **agent.guide.search_metadata,
                    "mode": "full-agent-faq", "retrieval_k": 3, "answer_rubric": "customer-answers-v1",
                    "agent_model": config.model, "judge_model": config.judge_model if args.judge else None,
                    "judge": args.judge, "max_turns": config.max_turns,
                    "turn_timeout": config.turn_timeout, "parallel_tool_calls": config.parallel_tool_calls}
        cases_by_id, rows = {case.id: case for case in cases}, []

        async def target(inputs):
            row = await answer_case(agent, cases_by_id[inputs["id"]], evaluator, judge=args.judge)
            rows.append(row)
            print(f"Case {row['id']}: {'error' if row['error'] else 'answered'}")
            return row

        experiment_info = None
        with tracing_context(client=client, project_name=config.langsmith_project, enabled=client is not None):
            if client is not None:
                dataset = await asyncio.to_thread(ensure_faq_dataset, client, cases)
                experiment = await client.aevaluate(
                    target, data=dataset, evaluators=[answer_feedback] if args.judge else [],
                    experiment_prefix=args.name, metadata=metadata, max_concurrency=1,
                    description="Full support-agent FAQ answers with actual tool evidence", num_repetitions=1)
                experiment_info = {"dataset": dataset, "name": experiment.experiment_name, "url": experiment.url}
                print(f"LangSmith experiment: {experiment.url or experiment.experiment_name}")
            else:
                for case in cases:
                    await target({"id": case.id, "question": case.question})
        rows.sort(key=lambda row: row["id"])
        grades = [row["answer_judgment"] for row in rows if "answer_judgment" in row]
        summary = {"cases": len(rows), "answer_errors": sum(bool(row["error"]) for row in rows),
                   "mean_answer_latency_ms": mean(row["latency_ms"] for row in rows),
                   "agent_total_tokens": sum(row["usage"].get("total_tokens", 0) for row in rows)}
        if args.judge:
            summary["answer_judged_cases"] = len(grades)
            for field in ("correct", "grounded", "helpful", "citations_valid"):
                summary["answer_" + field] = mean(grade[field] for grade in grades) if grades else None
        report = {"metadata": metadata, "experiment": experiment_info, "summary": summary, "cases": rows}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
        print(json.dumps(summary, indent=2))
        print(f"Saved {args.output}")
    finally:
        await agent.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", action="store_true", help="Grade the four answer-quality dimensions.")
    parser.add_argument("--name", default="v7-faq-answers", help="LangSmith experiment name prefix.")
    parser.add_argument("--output", type=Path, default=BENCHMARK_DIR / "results/faq-answers-v7.json")
    asyncio.run(evaluate(parser.parse_args()))


if __name__ == "__main__":
    main()
