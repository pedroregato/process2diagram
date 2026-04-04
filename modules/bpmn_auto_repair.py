# modules/bpmn_auto_repair.py
# ─────────────────────────────────────────────────────────────────────────────
# Deterministic structural repairs for BPMNModel.
#
# Applied after _enforce_rules() in AgentBPMN.run(), before XML/Mermaid gen.
# Mutates model in-place; returns a RepairReport describing every fix.
#
# Repairs performed:
#   Pass 1 — Remove dangling edges  (source/target references a missing step)
#   Pass 2 — Remove isolated nodes  (no incoming AND no outgoing edges) — loop
#   Pass 3 — Label XOR edges        (infer Sim/Não or generic Opção N)
#   Pass 4 — Bypass redundant GW    (single-in, single-out gateway) — loop
#
# Safety rules:
#   - Never runs if model has ≤ 2 steps (too sparse to repair safely)
#   - Never raises — outer try/except returns empty RepairReport on failure
#   - Collaboration models are repaired pool-by-pool
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_hub import BPMNModel, BPMNStep, BPMNEdge

_GATEWAY_TYPES = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway", "gateway",
}

# Keywords used to infer the complementary XOR label
_YES_WORDS = ("sim", "yes", "aprovad", "ok", "true", "valid", "aceito", "sucesso")
_NO_WORDS  = ("não", "nao", "no", "negad", "false", "rejeit", "recusad", "falha")


@dataclass
class RepairReport:
    """Summary of all structural repairs applied to a BPMNModel."""
    repairs: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.repairs)

    def __bool__(self) -> bool:
        return bool(self.repairs)


# ── Public API ────────────────────────────────────────────────────────────────

def repair_bpmn(model: "BPMNModel") -> RepairReport:
    """
    Apply all structural repairs to *model* in-place.
    Returns a RepairReport. Never raises.
    """
    try:
        report = RepairReport()
        if model.is_collaboration:
            for pool in model.pool_models:
                _repair_pool(pool.steps, pool.edges, report,
                             prefix=f"[{pool.name}] ")
        else:
            _repair_pool(model.steps, model.edges, report)
        return report
    except Exception:
        return RepairReport()


# ── Internal repair engine ────────────────────────────────────────────────────

def _repair_pool(
    steps: list,
    edges: list,
    report: RepairReport,
    prefix: str = "",
) -> None:
    """
    Repair one pool (or a single-pool model) in-place.
    *steps* and *edges* are the live list objects from the model/pool —
    modifications via slice assignment propagate back to the caller.
    """
    # ── Pass 1: Remove dangling edges ─────────────────────────────────────────
    step_ids = {s.id for s in steps}
    valid = [e for e in edges if e.source in step_ids and e.target in step_ids]
    removed = len(edges) - len(valid)
    if removed:
        report.repairs.append(
            f"{prefix}Removed {removed} dangling edge(s) "
            f"referencing non-existent step(s)"
        )
        edges[:] = valid

    # ── Pass 2: Remove isolated nodes (loop until stable) ─────────────────────
    while len(steps) > 2:
        out_cnt = {s.id: 0 for s in steps}
        in_cnt  = {s.id: 0 for s in steps}
        for e in edges:
            if e.source in out_cnt:
                out_cnt[e.source] += 1
            if e.target in in_cnt:
                in_cnt[e.target]  += 1

        isolated = [s for s in steps if out_cnt[s.id] == 0 and in_cnt[s.id] == 0]
        if not isolated:
            break
        isolated_ids = {s.id for s in isolated}
        for s in isolated:
            report.repairs.append(
                f"{prefix}Removed isolated node '{s.title}' ({s.id})"
            )
        steps[:] = [s for s in steps if s.id not in isolated_ids]

    # ── Pass 3: Label unlabeled XOR outgoing edges ─────────────────────────────
    out_edges: dict[str, list] = {s.id: [] for s in steps}
    for e in edges:
        if e.source in out_edges:
            out_edges[e.source].append(e)

    for s in steps:
        is_xor = s.is_decision or s.task_type == "exclusiveGateway"
        outs = out_edges.get(s.id, [])
        if not is_xor or len(outs) < 2:
            continue
        unlabeled = [e for e in outs if not (e.label or "").strip()]
        if not unlabeled:
            continue

        labeled = [e for e in outs if (e.label or "").strip()]
        if len(outs) == 2:
            if labeled:
                existing = labeled[0].label.strip().lower()
                if any(w in existing for w in _YES_WORDS):
                    unlabeled[0].label = "Não"
                elif any(w in existing for w in _NO_WORDS):
                    unlabeled[0].label = "Sim"
                else:
                    unlabeled[0].label = "Outro"
            else:
                unlabeled[0].label = "Sim"
                unlabeled[1].label = "Não"
        else:
            # 3+ branches: add generic labels to the unlabeled ones
            start = len(labeled) + 1
            for i, e in enumerate(unlabeled):
                e.label = f"Opção {start + i}"

        report.repairs.append(
            f"{prefix}Added missing XOR label(s) on '{s.title}' ({s.id})"
        )

    # ── Pass 4: Bypass single-in / single-out redundant gateways (loop) ───────
    changed = True
    while changed:
        changed = False

        # Rebuild adjacency from current edges/steps
        out_map: dict[str, list] = {s.id: [] for s in steps}
        in_map:  dict[str, list] = {s.id: [] for s in steps}
        for e in edges:
            if e.source in out_map and e.target in in_map:
                out_map[e.source].append(e)
                in_map[e.target].append(e.source)

        for s in steps:
            is_gw = s.is_decision or s.task_type in _GATEWAY_TYPES
            if not is_gw:
                continue
            ins  = in_map.get(s.id, [])
            outs = out_map.get(s.id, [])
            # Only bypass when exactly 1 predecessor AND 1 successor
            if len(ins) != 1 or len(outs) != 1:
                continue

            gw_id        = s.id
            successor_id = outs[0].target

            # Redirect the predecessor's edge to the successor; drop gateway edges
            new_edges: list = []
            for e in edges:
                if e.target == gw_id:
                    ne = copy.copy(e)
                    ne.target = successor_id
                    new_edges.append(ne)
                elif e.source == gw_id:
                    pass   # drop — replaced by redirected edge above
                else:
                    new_edges.append(e)

            edges[:] = new_edges
            steps[:] = [s2 for s2 in steps if s2.id != gw_id]
            report.repairs.append(
                f"{prefix}Bypassed redundant gateway '{s.title}' ({gw_id})"
            )
            changed = True
            break   # restart loop with fresh adjacency
