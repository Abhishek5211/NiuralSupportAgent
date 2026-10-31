"""Manually evaluate FAQ retrieval; generation and LLM judging are opt-in."""

import argparse
import asyncio
import json
from math import log2
from pathlib import Path
from statistics import mean
from typing import Literal

from langsmith import traceable, tracing_context
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, model_validator

from .config import BENCHMARK_DIR, Config
from .observability import configure_langsmith
from .rag_evaluate import RAGEvaluator
from .rag_experiment import ensure_faq_dataset, faq_feedback
from .retrieval import GuideRetriever
from .runtime import error_details, git_metadata


class FAQCase(BaseModel):
    id: int
    question: str
    facts: str
    expected_behavior: Literal["answer", "clarify", "unavailable", "answer_or_clarify"]
    required_facts: list[str] = Field(min_length=1)
    required_sections: list[str] = Field(default_factory=list)
    alternative_sections: list[list[str]] = Field(default_factory=list)

    @property
    def section_groups(self):
        # Every required section, and one section from each alternative group.
        return [[section] for section in self.required_sections] + self.alternative_sections

    @model_validator(mode="after")
    def validate_sections(self):
        if any(not group for group in self.section_groups):
            raise ValueError("Alternative groups cannot be empty")
        if not self.section_groups and self.expected_behavior != "clarify":
            raise ValueError("Only clarification-only cases may omit source labels")
        return self


def score_sections(groups: list[list[str]], retrieved: list[str], k: int = 3) -> dict:
    if not groups:
        return {f"recall_at_{k}": None, "reciprocal_rank": None, f"ndcg_at_{k}": None}
    group_by_section = {section: index for index, group in enumerate(groups) for section in group}
    found, ranks = set(), []
    for rank, section in enumerate(retrieved[:k], 1):
        group = group_by_section.get(section)
        if group is not None and group not in found:
            found.add(group)
            ranks.append(rank)
    dcg = sum(1 / log2(rank + 1) for rank in ranks)
    ideal_dcg = sum(1 / log2(rank + 1) for rank in range(1, min(k, len(groups)) + 1))
    return {
        f"recall_at_{k}": len(found) / len(groups),
        "reciprocal_rank": 1 / ranks[0] if ranks else 0.0,
        f"ndcg_at_{k}": dcg / ideal_dcg,
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
            if any(section not in sections for case in cases
                   for group in case.section_groups for section in group):
                raise ValueError("FAQ source labels do not match the indexed guide")
            evaluator = RAGEvaluator(config, client, tracing=langsmith is not None)

            @traceable(name="Product guide FAQ case")
            async def evaluate_case(case):
                row = {"id": case.id, "question": case.question,
                       "expected_behavior": case.expected_behavior, "required_facts": case.required_facts,
                       "required_sections": case.required_sections,
                       "alternative_sections": case.alternative_sections}
                try:
                    result = await retriever.search(case.question)
                    row["retrieval"] = result.model_dump()
                    retrieved_sections = [match.section for match in result.matches]
                    row["metrics"] = score_sections(case.section_groups, retrieved_sections)
                    row["missing_sections"] = [section for section in case.required_sections
                                               if section not in retrieved_sections]
                    row["missing_alternative_groups"] = [group for group in case.alternative_sections
                                                         if not set(group).intersection(retrieved_sections)]
                except Exception as error:
                    row["error"] = error_details(error)
                    return row
                passages = [match.model_dump() for match in result.matches]
                tasks = []
                if args.judge:
                    tasks.append(("retrieval_judgment", evaluator.judge_retrieval,
                                  [case.question, case.expected_behavior, case.required_facts, passages]))
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
                            case.question, case.expected_behavior, case.required_facts,
                            passages, row["generation"])
                        row["answer_judgment"], row["answer_judgment_usage"] = verdict, usage
                    except Exception as error:
                        row["answer_judgment_error"] = error_details(error)
                return row

            metadata = {**git_metadata(), **retriever.metadata, "retrieval_k": 3,
                        "generate": args.generate, "judge": args.judge,
                        "evaluation_rubric": "faq-behavior-v3",
                        "agent_model": config.model, "judge_model": config.judge_model}
            rows = []
            cases_by_id = {case.id: case for case in cases}

            async def target(inputs):
                case = cases_by_id[inputs["id"]]
                row = await evaluate_case(case)
                rows.append(row)
                print(f"Case {case.id}: recall@3={row.get('metrics', {}).get('recall_at_3', 'error')}")
                return row

            experiment_info = None
            with tracing_context(client=langsmith, project_name=config.langsmith_project,
                                 enabled=langsmith is not None):
                if langsmith is not None:
                    dataset = await asyncio.to_thread(ensure_faq_dataset, langsmith, cases)
                    experiment = await langsmith.aevaluate(
                        target, data=dataset, evaluators=[faq_feedback],
                        experiment_prefix=args.name, metadata=metadata,
                        description="Single-search product-guide retrieval and optional answer judging",
                        max_concurrency=1, num_repetitions=1)
                    experiment_info = {"dataset": dataset, "name": experiment.experiment_name,
                                       "url": experiment.url}
                    print(f"LangSmith experiment: {experiment.url or experiment.experiment_name}")
                else:
                    for case in cases:
                        await target({"id": case.id, "question": case.question})
            rows.sort(key=lambda row: row["id"])
            successful = [row for row in rows if "retrieval" in row]
            scored = [row for row in rows if row["required_sections"] or row["alternative_sections"]]
            summary = {
                "cases": len(rows), "retrieval_errors": len(rows) - len(successful),
                "retrieval_scored_cases": len(scored),
                **{key: mean(row.get("metrics", {}).get(field, 0.0) for row in scored) if scored else None
                   for key, field in (("recall_at_3", "recall_at_3"), ("mrr_at_3", "reciprocal_rank"),
                                      ("ndcg_at_3", "ndcg_at_3"))},
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
            report = {"metadata": metadata, "experiment": experiment_info,
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
    parser.add_argument("--name", default="v5-faq", help="LangSmith experiment name prefix.")
    parser.add_argument("--generate", action="store_true", help="Also generate answers from retrieved passages.")
    parser.add_argument("--judge", action="store_true", help="Judge passage relevance/sufficiency, and generated answers if enabled.")
    asyncio.run(evaluate(parser.parse_args()))


if __name__ == "__main__":
    main()
