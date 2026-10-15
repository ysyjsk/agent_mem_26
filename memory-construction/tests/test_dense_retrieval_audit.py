"""CPU contracts for the narrow dense retrieval audit entry point."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from workflow_memory.ir import Evidence, stable_hash

from tools.run_dense_retrieval_audit import (
    PROTOCOL,
    query_payload,
    retrieval_metrics,
    summarize,
    verify_question_manifest,
)


def _reference(*fields):
    source_fields = [{"event_id": event_id, "field": field,
                      "field_value_hash": stable_hash(value)}
                     for event_id, field, value in fields]
    return {"reference_status": "available", "source_fields": source_fields}


def test_query_payload_is_plain_question_without_evaluator_fields():
    question = {"question": "At source step 4, what URL was observed?",
                "reference": _reference(("event-4", "post_state_ref.url", "https://example.test"))}
    payload = query_payload(question, "Qwen3-Embedding-8B", max_length=1024, batch_size=2)
    assert payload == {"model": "Qwen3-Embedding-8B", "input": question["question"],
                       "max_length": 1024, "batch_size": 2}
    assert "reference" not in payload
    assert "source_ids" not in payload


def test_retrieval_metrics_are_evaluator_side_and_distinguish_literal_coverage():
    literal = Evidence(evidence_id="literal-1", source_refs=("event-4",),
                       predicate="observed_url", value="https://example.test", modality="source_literal")
    semantic = Evidence(evidence_id="semantic-5", source_refs=("event-5",),
                        predicate="action", value="a paraphrase", modality="model")
    snapshot = SimpleNamespace(evidence=(literal, semantic))
    reference = _reference(("event-4", "post_state_ref.url", "https://example.test"),
                           ("event-5", "action", "click('x')"))
    metrics = retrieval_metrics(snapshot, [
        {"evidence_id": "literal-1", "score": 0.9},
        {"evidence_id": "semantic-5", "score": 0.8},
    ], reference)
    assert metrics["source_recall"] == 1.0
    assert metrics["literal_field_coverage"] == 0.5
    assert metrics["retrieved_source_ids"] == ["event-4", "event-5"]


def test_question_manifest_verification_does_not_require_reader_or_gold_changes():
    reference = _reference(("event-4", "action", "click('x')"))
    reference["reference_hash"] = stable_hash(reference)
    manifest = {"schema_version": "test", "questions": [{
        "question_id": "q1", "question": "What happened?", "reference": reference,
    }]}
    manifest["manifest_hash"] = stable_hash(manifest)
    verify_question_manifest(manifest)


def test_summary_is_retrieval_only_and_marks_official_qa_unavailable():
    rows = [{"construction_run_id": "old", "method": "Ours-dev", "status": "completed",
             "source_recall": 1.0, "literal_field_coverage": 0.5, "embedding_calls": 1,
             "input_tokens": 12, "embedding_elapsed_s": 0.1, "retrieval_elapsed_s": 0.01,
             "elapsed_s": 0.11, "dense_valid": True, "render_version": "full-v1", "top_k": 8}]
    summary = summarize(rows, Path("raw.jsonl"))[0]
    assert summary["source_recall_mean"] == 1.0
    assert summary["literal_field_coverage_mean"] == 0.5
    assert summary["reader_calls"] == 0
    assert summary["quality_scope"] == PROTOCOL
    assert summary["official_qa_status"] == "not_evaluated"
