"""LangSmith dataset snapshots and feedback for the FAQ evaluator."""

import json
from hashlib import sha256
from statistics import mean


def ensure_faq_dataset(client, cases):
    examples = [{"inputs": {"id": case.id, "question": case.question},
                 "outputs": {"facts": case.facts, "required_sections": case.required_sections,
                             "expected_behavior": case.expected_behavior, "required_facts": case.required_facts,
                             "alternative_sections": case.alternative_sections}}
                for case in cases]
    fingerprint = sha256(json.dumps(examples, sort_keys=True).encode()).hexdigest()[:12]
    name = f"niural-product-guide-faq-{fingerprint}"
    if not client.has_dataset(dataset_name=name):
        client.create_dataset(dataset_name=name,
                              description=f"{len(cases)} source-labeled product-guide FAQ cases.")
    existing = list(client.list_examples(dataset_name=name))
    if not existing:
        client.create_examples(dataset_name=name, examples=examples)
    else:
        actual = [{"inputs": example.inputs, "outputs": example.outputs} for example in existing]
        if sorted(json.dumps(row, sort_keys=True) for row in actual) != sorted(
                json.dumps(row, sort_keys=True) for row in examples):
            raise ValueError(f"LangSmith dataset {name} differs from the local FAQ snapshot")
    return name


def faq_feedback(outputs):
    """Publish existing scores; never repeat generation or paid judging."""
    metrics = outputs.get("metrics", {})
    labeled = bool(outputs.get("required_sections") or outputs.get("alternative_sections"))
    scores = [{"key": key, "score": metrics.get(field, 0.0 if labeled else None)} for key, field in (
        ("recall_at_3", "recall_at_3"), ("mrr_at_3", "reciprocal_rank"),
        ("ndcg_at_3", "ndcg_at_3"))]
    if "retrieval_judgment" in outputs:
        grade = outputs["retrieval_judgment"]
        scores.extend([
            {"key": "passage_relevance", "score": mean(p["relevant"] for p in grade["passages"]),
             "comment": grade["reason"]},
            {"key": "context_sufficiency", "score": int(grade["sufficient"]),
             "comment": grade["reason"]},
        ])
    elif "retrieval_judgment_error" in outputs:
        scores.extend({"key": key, "score": None,
                       "comment": outputs["retrieval_judgment_error"]["message"]}
                      for key in ("passage_relevance", "context_sufficiency"))
    answer_fields = ("correct", "grounded", "helpful", "citations_valid")
    if "answer_judgment" in outputs:
        grade = outputs["answer_judgment"]
        scores.extend({"key": "answer_" + field, "score": int(grade[field]),
                       "comment": grade["reason"]} for field in answer_fields)
    elif "answer_judgment_error" in outputs:
        scores.extend({"key": "answer_" + field, "score": None,
                       "comment": outputs["answer_judgment_error"]["message"]}
                      for field in answer_fields)
    return {"results": scores}
