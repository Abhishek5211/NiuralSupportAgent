"""Manually evaluate FAQ retrieval; generation and LLM judging are opt-in."""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean

from langsmith import traceable, tracing_context
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .config import BENCHMARK_DIR, Config
from .observability import configure_langsmith
from .rag_evaluate import RAGEvaluator
from .retrieval import GuideRetriever
from .runtime import error_details, git_metadata


class FAQCase(BaseModel):
    id: int
    question: str
    facts: str
    expected_sections: list[str] = Field(min_length=1)


def score_sections(expected: list[str], retrieved: list[str]) -> dict:
    retrieved = retrieved[:3]
    expected_set = set(expected)
    ranks = [rank for rank, section in enumerate(retrieved, 1) if section in expected_set]
    return {
        "hit_at_1": bool(ranks and ranks[0] == 1),
        "hit_at_3": bool(ranks),
        "first_relevant_rank": ranks[0] if ranks else None,
        "section_coverage_at_3": len(expected_set.intersection(retrieved)) / len(expected_set),
    }


async def evaluate(args):
    if args.output.exists():
        raise FileExistsError(f"Choose a new --output path; {args.output} already exists")
    config = Config.load()
    cases = [FAQCase.model_validate(row) for row in json.loads(
        (BENCHMARK_DIR / "faq_cases.json").read_text(encoding="utf-8"))]
    langsmith = configure_langsmith(config)
    try:
        async with AsyncOpenAI(api_key=config.api_key, max_retries=0, timeout=45) as client:
            retriever = GuideRetriever(config, client)
            # Missing/stale index or labels fail before any embedding or model call.
            await asyncio.to_thread(retriever.open_index)
            sections = {chunk.section for chunk in retriever.chunks}
            if any(not set(case.expected_sections) <= sections for case in cases):
                raise ValueError("FAQ source labels do not match the indexed guide")
            evaluator = RAGEvaluator(config, client, tracing=langsmith is not None)

            @traceable(name="Product guide FAQ case")
            async def evaluate_case(case):
                row = {"id": case.id, "question": case.question,
                       "expected_sections": case.expected_sections}
                try:
                    result = await retriever.search(case.question)
                    row["retrieval"] = result.model_dump()
                    row["metrics"] = score_sections(
                        case.expected_sections, [m.section for m in result.matches])
                except Exception as error:
                    row["error"] = error_details(error)
                    return row
                passages = [match.model_dump() for match in result.matches]
                tasks = []
                if args.judge:
                    tasks.append(("retrieval_judgment", evaluator.judge_retrieval,
                                  [case.question, case.facts, passages]))
                if args.generate:
                    tasks.append(("generation", evaluator.generate, [case.question, passages]))
                for name, function, arguments in tasks:
                    try:
                        value, usage = await function(*arguments)
                        row[name] = value
                        row[name + "_usage"] = usage
                    except Exception as error:
                        row[name + "_error"] = error_details(error)
                if args.judge and "generation" in row:
                    try:
                        verdict, usage = await evaluator.judge_answer(
                            case.question, case.facts, passages, row["generation"])
                        row["answer_judgment"], row["answer_judgment_usage"] = verdict, usage
                    except Exception as error:
                        row["answer_judgment_error"] = error_details(error)
                return row

            rows = []
            with tracing_context(client=langsmith, project_name=config.langsmith_project,
                                 enabled=langsmith is not None):
                for case in cases:
                    row = await evaluate_case(case)
                    rows.append(row)
                    print(f"Case {case.id}: hit@3={row.get('metrics', {}).get('hit_at_3', 'error')}")
            successful = [row for row in rows if "retrieval" in row]
            summary = {
                "cases": len(rows), "retrieval_errors": len(rows) - len(successful),
                "hit_at_1": sum(row["metrics"]["hit_at_1"] for row in successful) / len(rows),
                "hit_at_3": sum(row["metrics"]["hit_at_3"] for row in successful) / len(rows),
                "mean_latency_ms": mean(row["retrieval"]["latency_ms"] for row in successful) if successful else None,
                "embedding_tokens": sum(row["retrieval"]["embedding_tokens"] for row in successful),
            }
            if args.judge:
                retrieval_grades = [row["retrieval_judgment"] for row in rows if "retrieval_judgment" in row]
                passage_grades = [passage for grade in retrieval_grades for passage in grade["passages"]]
                summary["retrieval_judged_cases"] = len(retrieval_grades)
                summary["passage_relevance"] = mean(p["relevant"] for p in passage_grades) if passage_grades else None
                summary["context_sufficiency"] = mean(g["sufficient"] for g in retrieval_grades) if retrieval_grades else None
                if args.generate:
                    answer_grades = [row["answer_judgment"] for row in rows if "answer_judgment" in row]
                    summary["answer_judged_cases"] = len(answer_grades)
                    for field in ("correct", "grounded", "helpful", "citations_valid"):
                        summary["answer_" + field] = mean(g[field] for g in answer_grades) if answer_grades else None
            report = {"metadata": {**git_metadata(), **retriever.metadata,
                                   "generate": args.generate, "judge": args.judge,
                                   "agent_model": config.model, "judge_model": config.judge_model},
                      "summary": summary, "cases": rows}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, ensure_ascii=False)
            print(json.dumps(summary, indent=2))
            print(f"Saved {args.output}")
    finally:
        if langsmith is not None:
            await asyncio.to_thread(langsmith.close, timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BENCHMARK_DIR / "results/retriever-v5.json")
    parser.add_argument("--generate", action="store_true", help="Also generate answers from retrieved passages.")
    parser.add_argument("--judge", action="store_true", help="Judge passage relevance/sufficiency, and generated answers if enabled.")
    asyncio.run(evaluate(parser.parse_args()))


if __name__ == "__main__":
    main()
