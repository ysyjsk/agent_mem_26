"""Public step-ordinal retrieval over derived memory, never evaluator gold.

The only temporal hint is explicit step numbering in the user's question.
SourceEvent IDs map ordinals to existing Evidence provenance; source actions,
states, expected answers and question reference IDs are never inspected here.
"""
from __future__ import annotations

import re
from typing import Any

from .construction import EvidenceBundle, Snapshot, query
from .ir import canonical_json, stable_hash

MODE = "public-step-lexical-v2"
_STEP_LIST = re.compile(r"\b(?:source\s+)?steps?\s*(\d+)((?:\s*(?:,\s*(?:and\s*)?|and\s*|&)\s*\d+)*)", re.IGNORECASE)


def public_step_numbers(question: str) -> tuple[int, ...]:
    """Parse literal 1-based lists, not 'containing N source steps' or labels."""
    result = []
    for match in _STEP_LIST.finditer(str(question)):
        for number in re.findall(r"\d+", match.group(0)):
            value = int(number)
            if value > 0 and value not in result:
                result.append(value)
    return tuple(result)


def query_public_steps(snapshot: Snapshot, question: str, retrieval_budget: int = 8) -> tuple[EvidenceBundle, dict[str, Any]]:
    budget = int(retrieval_budget)
    if budget < 1:
        raise ValueError("public step retrieval budget must be positive")
    requested = public_step_numbers(question)
    positions = {event.event_id: index + 1 for index, event in enumerate(snapshot.events)}
    in_prefix = [step for step in requested if step <= len(snapshot.events)]
    question_lower = str(question).lower()
    intent = "url" if re.search(r"\burl\b", question_lower) else "action" if re.search(r"\bactions?|commands?|workflow\b", question_lower) else "generic"
    tokens = set(re.findall(r"[\w-]+", question_lower))
    candidates = {step: [] for step in in_prefix}
    scores = {}
    for evidence in snapshot.evidence:
        relevant = [step for step in in_prefix if any(positions.get(ref) == step for ref in evidence.source_refs)]
        if not relevant:
            continue
        predicate = str(evidence.predicate).lower()
        body = canonical_json({"predicate": predicate, "value": evidence.value, "kind": evidence.event_kind}).lower()
        literal = evidence.modality == "source_literal" or ":literal:" in evidence.evidence_id
        if intent == "url":
            exact_type = predicate in {"observed_url", "url", "post_state_url"}
            kind_match = evidence.event_kind in {"observation", "confirmation"}
            type_match = exact_type or "url" in predicate or "http://" in body or "https://" in body
        elif intent == "action":
            exact_type = predicate in {"action_command", "attempted_action_command"}
            kind_match = evidence.event_kind == "attempt"
            type_match = exact_type or "action" in predicate or "command" in predicate
        else:
            exact_type, kind_match, type_match = False, evidence.event_kind in {"observation", "confirmation"}, False
        overlap = len(tokens & set(re.findall(r"[\w-]+", body)))
        # Public fact type and provenance outrank paraphrase, never a hidden
        # reference ID or value match. Stable ties preserve reproducibility.
        priority = (int(exact_type and literal), int(exact_type), int(kind_match), int(type_match), overlap)
        scores[evidence.evidence_id] = float(sum(priority[:-1]) * 10 + overlap)
        for step in relevant:
            candidates[step].append((priority, evidence))
    selected = []
    seen = set()
    if any(candidates.values()):
        for values in candidates.values():
            values.sort(key=lambda pair: tuple(-part for part in pair[0]) + (pair[1].evidence_id,))
        # A fixed-budget round robin prevents one requested step's many facts
        # from consuming every slot needed by a multi-step workflow question.
        rank = 0
        while len(selected) < budget and any(rank < len(values) for values in candidates.values()):
            for step in in_prefix:
                values = candidates[step]
                if rank < len(values) and values[rank][1].evidence_id not in seen:
                    evidence = values[rank][1]
                    selected.append(evidence)
                    seen.add(evidence.evidence_id)
                    if len(selected) == budget:
                        break
            rank += 1
        bundle = EvidenceBundle(snapshot_id=snapshot.snapshot_id, epoch=snapshot.epoch, question=question,
                   evidence=tuple(selected), state=snapshot.state_view, aliases=snapshot.aliases,
                   relations=snapshot.relations, workflow=snapshot.workflow_view, budget=budget,
                   scores={evidence.evidence_id: scores[evidence.evidence_id] for evidence in selected})
        strategy, fallback = "public_step_filter_then_fact_priority_lexical", None
    else:
        if requested:
            # An explicit public ordinal is a hard scope boundary.  If the
            # requested step is outside the arrived prefix, or no derived
            # evidence was published for an in-prefix step, broad lexical
            # fallback could expose a different step and make an ``unknown``
            # question answerable by accident.  Keep the bundle empty and let
            # the Reader report that the requested fact is not evidenced.
            bundle = EvidenceBundle(snapshot_id=snapshot.snapshot_id, epoch=snapshot.epoch, question=question,
                                    evidence=tuple(), state=snapshot.state_view, aliases=snapshot.aliases,
                                    relations=snapshot.relations, workflow=snapshot.workflow_view, budget=budget,
                                    scores={})
            selected = []
            strategy = "public_step_filter_no_match"
            fallback = "no_derived_evidence_for_public_steps"
        else:
            bundle = query(snapshot, question, budget)
            selected = list(bundle.evidence)
            strategy = "core_lexical_fallback"
            fallback = "no_explicit_step_numbers"
    selected_ids = [evidence.evidence_id for evidence in selected]
    plan = {"mode": MODE, "strategy": strategy, "fallback_reason": fallback, "intent": intent,
            "requested_source_positions": list(requested), "in_prefix_source_positions": in_prefix,
            "out_of_prefix_positions": [step for step in requested if step > len(snapshot.events)],
            "budget": budget, "selected_count": len(selected), "selected_evidence_ids": selected_ids,
            "selected_source_positions": sorted({positions[ref] for evidence in selected for ref in evidence.source_refs if ref in positions}),
            "snapshot_id": snapshot.snapshot_id, "epoch": snapshot.epoch,
            "information_scope": "public_question+derived_evidence_provenance+snapshot_ordinals_only",
            "checks": {"budget_respected": len(selected) <= budget, "unique_evidence": len(selected_ids) == len(set(selected_ids)),
                       "selected_from_snapshot_evidence": set(selected_ids) <= {evidence.evidence_id for evidence in snapshot.evidence},
                       "step_filter_respected": fallback is not None or all(any(positions.get(ref) in in_prefix for ref in evidence.source_refs) for evidence in selected)}}
    plan["request_hash"] = stable_hash({"question": question, "mode": MODE, "budget": budget,
                                       "snapshot_id": snapshot.snapshot_id, "epoch": snapshot.epoch})
    return bundle, plan


__all__ = ["MODE", "public_step_numbers", "query_public_steps"]
