"""Manually run a selected benchmark suite as a LangSmith experiment."""

import argparse
import asyncio
import json

from langsmith import tracing_context

from .agent import SupportAgent
from .config import BENCHMARK_DIR, Config
from .evaluate import case_context, evaluate_one
from .runtime import error_details, git_metadata

SUITES = {
    "standard": ("cases.json", "niural-account-v1"),
    "hard": ("hard_cases.json", "niural-account-hard-v1"),
    "arithmetic": ("arithmetic_cases.json", "niural-account-arithmetic-v1"),
}


def ensure_dataset(client, suite="standard"):
    filename, dataset_name = SUITES[suite]
    cases = json.loads((BENCHMARK_DIR / filename).read_text(encoding="utf-8"))
    examples = [{
        "inputs": {"id": case["id"], "question": case["question"], "context": case_context(case)},
        "outputs": {"facts": case["facts"]},
    } for case in cases]
    if not client.has_dataset(dataset_name=dataset_name):
        client.create_dataset(dataset_name=dataset_name,
                              description=f"{len(cases)} synthetic Niural {suite} cases; snapshot 2026-09-28.")
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
                        max_concurrency=1, judge=True, suite="standard"):
    config = agent.config
    if not config.langsmith_tracing or not config.langsmith_api_key:
        raise ValueError("Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env.")
    if max_concurrency < 1:
        raise ValueError("Concurrency must be at least 1.")

    client = agent.langsmith_client
    dataset_name = await asyncio.to_thread(ensure_dataset, client, suite)

    async def target(inputs):
        # The target receives questions/context only, never reference facts.
        return await evaluate_one(agent, inputs)

    async def correctness(inputs, outputs, reference_outputs):
        if outputs.get("error") or not outputs.get("answer"):
            return {"key": "correctness", "score": 0, "comment": "No successful answer was generated."}
        try:
            verdict, _ = await agent.judge(
                inputs["question"], inputs["context"], reference_outputs["facts"], outputs["answer"],
            )
            return {"key": "correctness", "score": int(verdict["correct"]), "comment": verdict["reason"]}
        except Exception as error:
            # An unavailable judge is ungraded, not an incorrect agent answer.
            return {"key": "correctness", "score": None,
                    "comment": "Judge failed: " + error_details(error)["message"]}

    with tracing_context(client=client, enabled=True):
        results = await client.aevaluate(
            target,
            data=dataset_name,
            evaluators=[correctness] if judge else [],
            experiment_prefix=name,
            description=description,
            metadata={**git_metadata(), "suite": suite, "agent_model": config.model,
                      "max_turns": config.max_turns, "turn_timeout": config.turn_timeout,
                      "parallel_tool_calls": config.parallel_tool_calls,
                      "judge_model": config.judge_model if judge else None,
                      "snapshot_date": "2026-09-28"},
            max_concurrency=max_concurrency,
            num_repetitions=1,
        )
    print(f"Finished experiment: {results.experiment_name}")
    if results.url:
        print(f"LangSmith: {results.url}")
    print(f"View {dataset_name} under LangSmith Datasets & Experiments.")
    return results


async def run_from_cli(args):
    agent = SupportAgent(Config.load())
    try:
        return await run_benchmark(agent, name=args.name, description=args.description,
                                   max_concurrency=args.concurrency, judge=not args.no_judge,
                                   suite=args.suite)
    finally:
        await agent.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="account-tools", help="Experiment name prefix.")
    parser.add_argument("--description", default="Typed account queries")
    parser.add_argument("--concurrency", type=int, default=1, help="Cases running simultaneously; default 1.")
    parser.add_argument("--no-judge", action="store_true", help="Save answers/traces without paid judge calls.")
    parser.add_argument("--suite", choices=SUITES, default="standard", help="Choose standard, compound hard or hypothetical arithmetic cases.")
    args = parser.parse_args()
    asyncio.run(run_from_cli(args))


if __name__ == "__main__":
    main()
