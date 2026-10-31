"""Manually run account benchmarks locally, with optional LangSmith experiments."""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from ..agent import SupportAgent
from ..config import BENCHMARK_DIR, Config
from .account import case_inputs, case_references, evaluate_correctness, evaluate_one
from ..runtime import git_metadata

SUITES = {
    "standard": ("cases.json", "niural-account-standard-v3"),
    "hard": ("hard_cases.json", "niural-account-hard-v2"),
    "arithmetic": ("arithmetic_cases.json", "niural-account-arithmetic-v2"),
    "failures": ("fail_scenarios.json", "niural-account-failures-v1"),
}


def load_examples(suite):
    filename, _ = SUITES[suite]
    cases = json.loads((BENCHMARK_DIR / filename).read_text(encoding="utf-8"))
    return [{
        "inputs": case_inputs(case),
        "outputs": case_references(case),
    } for case in cases]


def ensure_dataset(client, suite="standard", examples=None):
    filename, dataset_name = SUITES[suite]
    examples = load_examples(suite) if examples is None else examples
    if not client.has_dataset(dataset_name=dataset_name):
        client.create_dataset(dataset_name=dataset_name,
                              description=f"{len(examples)} synthetic Niural {suite} cases; snapshot 2026-09-28.")
    existing = list(client.list_examples(dataset_name=dataset_name))
    if not existing:
        client.create_examples(dataset_name=dataset_name, examples=examples)
    else:
        actual = [{"inputs": e.inputs, "outputs": e.outputs} for e in existing]
        expected_rows = sorted(json.dumps(row, sort_keys=True) for row in examples)
        actual_rows = sorted(json.dumps(row, sort_keys=True) for row in actual)
        if actual_rows != expected_rows:
            raise ValueError(f"The LangSmith dataset differs from {filename}. Use a new dataset version before comparing experiments.")
    return dataset_name


async def run_benchmark(agent, *, name="account-tools", description="Typed account queries",
                        max_concurrency=1, judge=True, suite="standard", output=None):
    config = agent.config
    if max_concurrency < 1:
        raise ValueError("Concurrency must be at least 1.")
    output = Path(output) if output is not None else BENCHMARK_DIR / "results" / f"{name}-{suite}.json"
    if output.exists():
        raise FileExistsError(f"Choose a new --output path; {output} already exists")
    examples = load_examples(suite)
    references = {example["inputs"]["id"]: example["outputs"] for example in examples}
    rows, judgments = [], {}
    metadata = {**git_metadata(), "name": name, "description": description,
                "suite": suite, "agent_model": config.model,
                "max_turns": config.max_turns, "turn_timeout": config.turn_timeout,
                "parallel_tool_calls": config.parallel_tool_calls,
                "judge_model": config.judge_model if judge else None,
                "snapshot_date": "2026-09-28", "judge": judge, "concurrency": max_concurrency}

    client = agent.langsmith_client
    async def target(inputs):
        events = []

        def capture(event):
            if event.type != "run_item_stream_event" or event.name not in {"tool_called", "tool_output"}:
                return
            item = event.item
            record = {"event": event.name, "call_id": item.call_id}
            if event.name == "tool_called":
                raw = item.raw_item
                record.update(tool=item.tool_name,
                              arguments=raw.get("arguments", "") if isinstance(raw, dict) else getattr(raw, "arguments", ""))
            else:
                record["output"] = item.output
            events.append(record)

        # Fault metadata configures the harness; references never enter prompts.
        result = await evaluate_one(agent, inputs, on_event=capture)
        result["tool_events"] = events
        rows.append({"id": inputs["id"], "inputs": inputs, "outputs": result,
                     "reference_outputs": references[inputs["id"]]})
        print(f"Case {inputs['id']}: {'error' if result.get('error') else 'answered'}")
        return result

    async def correctness(inputs, outputs, reference_outputs):
        verdict = await evaluate_correctness(agent, inputs, outputs, reference_outputs)
        judgments[inputs["id"]] = verdict
        return verdict

    results, experiment = None, None
    if client is not None:
        from langsmith import tracing_context

        dataset_name = await asyncio.to_thread(ensure_dataset, client, suite, examples)
        with tracing_context(client=client, enabled=True):
            results = await client.aevaluate(
                target, data=dataset_name, evaluators=[correctness] if judge else [],
                experiment_prefix=name, description=description, metadata=metadata,
                max_concurrency=max_concurrency, num_repetitions=1)
        experiment = {"dataset": dataset_name, "name": results.experiment_name, "url": results.url}
        print(f"LangSmith: {results.url or results.experiment_name}")
    else:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_local(example):
            async with semaphore:
                result = await target(example["inputs"])
                if judge:
                    await correctness(example["inputs"], result, example["outputs"])

        await asyncio.gather(*(run_local(example) for example in examples))

    rows.sort(key=lambda row: row["id"])
    usage = Counter()
    for row in rows:
        usage.update(row["outputs"].get("usage", {}))
        if row["id"] in judgments:
            row["judgment"] = judgments[row["id"]]
    graded = [verdict["score"] for verdict in judgments.values() if verdict["score"] is not None]
    summary = {"cases": len(rows), "error_cases": sum(bool(row["outputs"].get("error")) for row in rows),
               "mean_latency_ms": mean(row["outputs"]["latency_ms"] for row in rows) if rows else None,
               "agent_usage": dict(usage)}
    if judge:
        summary.update(graded_cases=len(graded), correct_cases=sum(score == 1 for score in graded),
                       ungraded_cases=len(rows) - len(graded), accuracy=mean(graded) if graded else None)
    report = {"metadata": metadata, "experiment": experiment, "summary": summary, "cases": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2))
    print(f"Saved {output}")
    # Preserve the existing notebook API for LangSmith-enabled callers.
    return results if results is not None else report


async def run_from_cli(args):
    config = Config.load()
    if args.local:
        config = config.model_copy(update={"langsmith_tracing": False})
    agent = SupportAgent(config)
    try:
        return await run_benchmark(agent, name=args.name, description=args.description,
                                   max_concurrency=args.concurrency, judge=not args.no_judge,
                                   suite=args.suite, output=args.output)
    finally:
        await agent.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="account-tools", help="Experiment name prefix.")
    parser.add_argument("--description", default="Typed account queries")
    parser.add_argument("--concurrency", type=int, default=1, help="Cases running simultaneously; default 1.")
    parser.add_argument("--no-judge", action="store_true", help="Save answers/traces without paid judge calls.")
    parser.add_argument("--local", action="store_true", help="Write JSON only; disable LangSmith for this run.")
    parser.add_argument("--output", type=Path, help="JSON report path; default benchmark/results/<name>-<suite>.json.")
    parser.add_argument("--suite", choices=SUITES, default="standard", help="Choose standard, hard, arithmetic or injected failure scenarios.")
    args = parser.parse_args()
    asyncio.run(run_from_cli(args))


if __name__ == "__main__":
    main()
