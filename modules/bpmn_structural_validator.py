# modules/bpmn_structural_validator.py
# ─────────────────────────────────────────────────────────────────────────────
# Structural validator for BPMNModel.
#
# Checks correctness at the model level (before XML generation):
#   - Dangling edge references
#   - Isolated nodes (no in or out)
#   - Unreachable nodes
#   - XOR gateway outgoing edges missing labels
#   - AND/OR split without a corresponding join
#   - Gateway with a single outgoing edge (redundant decision)
#
# Public API:
#   validate_bpmn_structure(model: BPMNModel) -> list[BPMNIssue]
#
# Never raises — wraps all logic in a try/except.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_hub import BPMNModel


@dataclass
class BPMNIssue:
    severity: str          # "error" | "warning" | "info"
    element_id: str | None
    message: str


_GATEWAY_TYPES = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway", "gateway",
}

_EVENT_TYPES = {
    "noneStartEvent", "startMessageEvent", "startTimerEvent",
    "noneEndEvent", "endMessageEvent", "errorEndEvent",
    "intermediateTimerCatchEvent", "intermediateMessageCatchEvent",
    "intermediateMessageThrowEvent", "startEvent", "endEvent",
    "start", "end",
}


def validate_bpmn_structure(model: "BPMNModel") -> list[BPMNIssue]:
    """
    Run structural checks on a BPMNModel.
    Returns a (possibly empty) list of BPMNIssue objects.
    Safe to call at any time — never raises.
    """
    try:
        return _run_checks(model)
    except Exception:
        return []


def _run_checks(model: "BPMNModel") -> list[BPMNIssue]:
    if model.is_collaboration:
        issues: list[BPMNIssue] = []
        for pm in model.pool_models:
            from core.knowledge_hub import BPMNModel as _BM
            flat = _BM(
                name=pm.name,
                steps=pm.steps,
                edges=pm.edges,
                lanes=pm.lanes,
            )
            for iss in _run_checks(flat):
                eid = f"[{pm.name}] {iss.element_id}" if iss.element_id else None
                issues.append(BPMNIssue(iss.severity, eid,
                                        f"[{pm.name}] {iss.message}"))
        return issues

    issues: list[BPMNIssue] = []
    step_ids = {s.id for s in model.steps}

    # ── Check 1: Dangling edge references ────────────────────────────────────
    for e in model.edges:
        if e.source not in step_ids:
            issues.append(BPMNIssue("error", e.source,
                f"Edge source '{e.source}' references a non-existent step"))
        if e.target not in step_ids:
            issues.append(BPMNIssue("error", e.target,
                f"Edge target '{e.target}' references a non-existent step"))

    # Build adjacency (only for valid references)
    outgoing: dict[str, list] = {s.id: [] for s in model.steps}
    incoming: dict[str, list[str]] = {s.id: [] for s in model.steps}
    for e in model.edges:
        if e.source in outgoing and e.target in incoming:
            outgoing[e.source].append(e)
            incoming[e.target].append(e.source)

    # ── Check 2: Isolated nodes ───────────────────────────────────────────────
    if len(model.steps) > 1:
        for s in model.steps:
            if not outgoing[s.id] and not incoming[s.id]:
                issues.append(BPMNIssue("error", s.id,
                    f"'{s.title}' ({s.id}) is isolated — no incoming or outgoing edges"))

    # ── Check 3: Unreachable nodes (BFS from roots) ───────────────────────────
    roots = [s.id for s in model.steps if not incoming[s.id]]
    if roots and len(model.steps) > 1:
        visited: set[str] = set()
        queue = list(roots)
        while queue:
            n = queue.pop(0)
            if n in visited:
                continue
            visited.add(n)
            for e in outgoing.get(n, []):
                if e.target not in visited:
                    queue.append(e.target)
        for s in model.steps:
            if s.id not in visited:
                issues.append(BPMNIssue("error", s.id,
                    f"'{s.title}' ({s.id}) is unreachable from the process start"))

    # ── Check 4: XOR gateway missing edge labels ──────────────────────────────
    for s in model.steps:
        if s.task_type in _EVENT_TYPES:
            continue
        is_xor = s.is_decision or s.task_type == "exclusiveGateway"
        out_edges = outgoing[s.id]
        if is_xor and len(out_edges) > 1:
            unlabeled = [e for e in out_edges if not (e.label or "").strip()]
            if unlabeled:
                issues.append(BPMNIssue("warning", s.id,
                    f"XOR gateway '{s.title}' ({s.id}) has {len(unlabeled)} outgoing "
                    f"edge(s) without condition labels"))

    # ── Check 5: AND / OR split missing join ──────────────────────────────────
    for s in model.steps:
        if s.task_type not in ("parallelGateway", "inclusiveGateway"):
            continue
        if len(outgoing[s.id]) <= 1:
            continue   # not a split — skip
        join_exists = any(
            s2.task_type == s.task_type
            and s2.id != s.id
            and len(incoming[s2.id]) > 1
            for s2 in model.steps
        )
        if not join_exists:
            gw_label = "AND" if s.task_type == "parallelGateway" else "OR"
            issues.append(BPMNIssue("warning", s.id,
                f"{gw_label} gateway '{s.title}' ({s.id}) opens parallel branches "
                f"but has no corresponding {gw_label} join — branches may never converge"))

    # ── Check 6: Decision with a single outgoing edge ─────────────────────────
    for s in model.steps:
        if s.task_type in _EVENT_TYPES:
            continue
        is_gw = s.is_decision or s.task_type in _GATEWAY_TYPES
        if is_gw and len(outgoing[s.id]) == 1:
            issues.append(BPMNIssue("info", s.id,
                f"Gateway '{s.title}' ({s.id}) has only one outgoing edge — "
                f"may be a redundant decision point"))

    return issues
