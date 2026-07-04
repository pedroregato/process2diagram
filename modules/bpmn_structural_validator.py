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
#   - Dead-end node when an explicit end event already exists elsewhere (PC118)
#   - Level-1 node count over the Bruce Silver density limit (PC118)
#   - Single-participant "collaboration" that still uses sendTask/receiveTask
#     to fake a second organization (PC118)
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
        issues = _run_checks(model)
        issues += _check_message_flow_balance(model)
        issues += _check_single_pool_choreography(model)
        return issues
    except Exception:
        return []


# Event types that legitimately close a path — a sink typed as one of these
# is a normal process ending, never a dead end.
_END_EVENT_TYPES = {"noneEndEvent", "endMessageEvent", "errorEndEvent", "endEvent", "end"}


def _check_single_pool_choreography(model: "BPMNModel") -> list[BPMNIssue]:
    """
    Check 11 — Single-participant collaboration faking a second organization.

    A `<collaboration>` with exactly one declared participant that still uses
    sendTask/receiveTask is modeling an external actor's interaction (send/
    receive a message) without ever declaring that actor as its own pool.
    Method & Style (skill_bpmn.md, Passo 1): "sendTask e receiveTask são
    exclusivos do formato pools — nunca use em processo flat de pool único."
    A one-participant collaboration is, for this purpose, a single pool.
    """
    if not getattr(model, "is_collaboration", False):
        return []
    pools = getattr(model, "pool_models", []) or []
    if len(pools) != 1:
        return []

    issues: list[BPMNIssue] = []
    for s in pools[0].steps:
        if s.task_type in ("sendTask", "receiveTask"):
            issues.append(BPMNIssue(
                "error", s.id,
                f"'{s.title}' ({s.id}) is a {s.task_type} inside a single-"
                f"participant collaboration — this simulates a second "
                f"organization without declaring its pool. Add the "
                f"counterpart as an explicit second participant with "
                f"message_flows (Method & Style: sendTask/receiveTask are "
                f"exclusive to true multi-pool collaboration)",
            ))
    return issues


# Task types that are valid message senders in a collaboration
_VALID_SEND_TYPES = {
    "sendTask",
    "intermediateMessageThrowEvent",
}

# Task types that are valid message receivers in a collaboration
_VALID_RECEIVE_TYPES = {
    "receiveTask",
    "startEvent", "startMessageEvent", "noneStartEvent",
    "intermediateMessageCatchEvent",
}

# Task types that are NOT valid for either role (should trigger a warning)
_IMPROPER_TASK_TYPES = {
    "userTask", "serviceTask", "businessRuleTask",
    "scriptTask", "manualTask",
}


def _check_message_flow_balance(model: "BPMNModel") -> list[BPMNIssue]:
    """
    Check 8 — Collaboration message flow choreography balance.
    Verifies that every message flow has:
      - A proper sender  (sendTask or message throw event)
      - A proper receiver (receiveTask or message catch/start event)
    Only runs on collaboration models with message_flows_data.
    """
    if not getattr(model, "is_collaboration", False):
        return []
    mf_list = getattr(model, "message_flows_data", []) or []
    if not mf_list:
        return []

    # Build a flat lookup: step_id → BPMNStep across all pools
    step_by_id: dict[str, object] = {}
    for pool in (getattr(model, "pool_models", None) or []):
        for s in (pool.steps or []):
            step_by_id[s.id] = s

    issues: list[BPMNIssue] = []

    for mf in mf_list:
        mf_label = f"'{getattr(mf, 'name', '') or mf.id}'"

        # ── Check sender ──────────────────────────────────────────────────────
        src_id = getattr(mf, "source_step", None)
        if src_id and src_id in step_by_id:
            src = step_by_id[src_id]
            src_type = getattr(src, "task_type", "")
            if src_type in _IMPROPER_TASK_TYPES:
                issues.append(BPMNIssue(
                    "warning", src_id,
                    f"Message flow {mf_label}: sender '{src.title}' ({src_id}) "
                    f"is typed as '{src_type}' — should be 'sendTask' "
                    f"to make choreography explicit",
                ))

        # ── Check receiver ────────────────────────────────────────────────────
        tgt_id = getattr(mf, "target_step", None)
        if tgt_id and tgt_id in step_by_id:
            tgt = step_by_id[tgt_id]
            tgt_type = getattr(tgt, "task_type", "")
            if tgt_type in _IMPROPER_TASK_TYPES:
                issues.append(BPMNIssue(
                    "warning", tgt_id,
                    f"Message flow {mf_label}: receiver '{tgt.title}' ({tgt_id}) "
                    f"is typed as '{tgt_type}' — should be 'receiveTask' or "
                    f"'intermediateMessageCatchEvent' to balance the choreography",
                ))

    return issues


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

    # ── Check 7: Task/event fan-in without explicit join gateway ──────────────
    # Detects when a task receives flows from multiple predecessors that are
    # themselves non-gateway nodes — indicating a XOR split converging directly
    # on a task instead of on an explicit join gateway.
    for s in model.steps:
        if s.task_type in _EVENT_TYPES:
            continue
        is_gw = s.is_decision or s.task_type in _GATEWAY_TYPES
        if is_gw:
            continue
        preds = incoming.get(s.id, [])
        if len(preds) < 2:
            continue
        # Only flag if ALL predecessors are non-gateway nodes (task-level fan-in)
        step_by_id = {st.id: st for st in model.steps}
        non_gw_preds = [
            p for p in preds
            if not (
                (step_by_id[p].is_decision if p in step_by_id else False)
                or (step_by_id[p].task_type in _GATEWAY_TYPES if p in step_by_id else False)
            )
        ]
        if len(non_gw_preds) == len(preds):
            issues.append(BPMNIssue("warning", s.id,
                f"'{s.title}' ({s.id}) receives {len(preds)} flows directly from tasks "
                f"— add an explicit XOR join gateway before this step "
                f"(Method & Style: never merge branches directly into a task)"))

    # ── Check 8: eventBasedGateway outgoing edges must be catch events ────────
    # OMG BPMN 2.0 §13.2.1: all outgoing sequence flows from an eventBasedGateway
    # must target intermediateTimerCatchEvent, intermediateMessageCatchEvent, or
    # receiveTask.  Any other target type is a spec violation.
    _EBG_VALID_TARGETS = {
        "intermediateTimerCatchEvent",
        "intermediateMessageCatchEvent",
        "receiveTask",
    }
    step_by_id_ebg = {st.id: st for st in model.steps}
    for s in model.steps:
        if s.task_type != "eventBasedGateway":
            continue
        for e in outgoing.get(s.id, []):
            tgt = step_by_id_ebg.get(e.target)
            if tgt is None:
                continue
            if tgt.task_type not in _EBG_VALID_TARGETS:
                issues.append(BPMNIssue("warning", s.id,
                    f"eventBasedGateway '{s.title}' ({s.id}) → '{tgt.title}' ({tgt.task_type}): "
                    f"target must be intermediateTimerCatchEvent, "
                    f"intermediateMessageCatchEvent, or receiveTask "
                    f"(OMG BPMN 2.0 §13.2.1)"))

    # ── Check 9: Dead-end node (explicit end event exists elsewhere) ─────────
    # A sink (no outgoing edge) is normal by itself — this model's terminal
    # step is commonly left untyped and the generator appends a synthetic end
    # event after it. But once the model DOES declare an explicit end event
    # (proving it distinguishes end states deliberately), any OTHER sink that
    # isn't itself an end event is a silently dropped path — the generator's
    # synthetic-end injection only fires when NO end event is present at all,
    # so this node never gets a closing event and the process appears to just
    # stop (Method & Style, Passo 5 — a devolution must loop back, not vanish).
    has_explicit_end = any(s.task_type in _END_EVENT_TYPES for s in model.steps)
    if has_explicit_end:
        for s in model.steps:
            if s.task_type in _END_EVENT_TYPES:
                continue
            if incoming[s.id] and not outgoing[s.id]:
                issues.append(BPMNIssue("error", s.id,
                    f"'{s.title}' ({s.id}) is a dead end — receives flow but has "
                    f"no outgoing sequence flow, and this process already has an "
                    f"explicit end event elsewhere. Route it back to the task "
                    f"that originated the correction, or give it its own end "
                    f"event naming the outcome reached"))

    # ── Check 10: Level-1 density (Bruce Silver Method — max 10 nodes) ───────
    _DENSITY_LIMIT = 10
    n_nodes = len(model.steps)
    if n_nodes > _DENSITY_LIMIT:
        excess = n_nodes - _DENSITY_LIMIT
        severity = "error" if excess > 5 else "warning"
        issues.append(BPMNIssue(severity, None,
            f"Level-1 node count ({n_nodes}) exceeds the Bruce Silver density "
            f"limit ({_DENSITY_LIMIT}) by {excess} — group cohesive phases into "
            f"callActivity so the flow fits one 'mental screen' (Method & Style, "
            f"Passo 0.1)"))

    return issues
