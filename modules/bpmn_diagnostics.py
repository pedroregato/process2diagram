# modules/bpmn_diagnostics.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Diagnostic Module
#
# Responsabilidade única: receber um BPMNModel (hub.bpmn) e renderizar
# o painel de diagnóstico completo no Streamlit, sem lógica de UI dispersa
# no app.py.
#
# API pública:
#   render_bpmn_diagnostics(bpmn_model: BPMNModel) -> None
#
# Internamente:
#   _build_bpmn_process(bpmn_model) -> BpmnProcess
#       Bridge BPMNModel → BpmnProcess (replica a lógica de agent_bpmn)
#
#   _render_summary(report)        → bloco principal do expander
#   _render_lane_issues(report)    → alertas de lane suspeita
#   _render_skill_viewer()         → sub-expander com o skill ativo
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from core.knowledge_hub import BPMNModel

# Skill path — deve coincidir com AgentBPMN.skill_path
_SKILL_PATH = Path("skills/skill_bpmn.md")


# ── Public API ────────────────────────────────────────────────────────────────

def render_bpmn_diagnostics(bpmn_model: "BPMNModel") -> None:
    """
    Renderiza o painel de diagnóstico BPMN no Streamlit.

    Deve ser chamado dentro do Tab BPMN 2.0, após o viewer bpmn-js.
    Captura qualquer exceção internamente — nunca quebra a UI principal.

    Args:
        bpmn_model: hub.bpmn (BPMNModel populado pelo AgentBPMN)
    """
    try:
        report = _analyse(bpmn_model)
        _render_expander(report)
    except Exception as err:
        with st.expander("🔍 Diagnóstico BPMN", expanded=False):
            st.warning(f"Diagnóstico indisponível: {err}")


# ── Internal: analysis ────────────────────────────────────────────────────────

def _analyse(bpmn_model: "BPMNModel") -> dict:
    """Build BpmnProcess from BPMNModel and run analyse_bpmn_crossings."""
    from modules.bpmn_generator import analyse_bpmn_crossings
    bpmn_process = _build_bpmn_process(bpmn_model)
    return analyse_bpmn_crossings(bpmn_process)


def _build_bpmn_process(bpmn_model: "BPMNModel"):
    """
    Bridge BPMNModel → BpmnProcess.

    Handles both single-pool (bpmn_model.steps/edges/lanes) and
    collaboration models (bpmn_model.is_collaboration / pool_models).
    """
    from modules.schema import BpmnProcess, BpmnElement, BpmnPool, BpmnLane, SequenceFlow

    if getattr(bpmn_model, "is_collaboration", False) and getattr(bpmn_model, "pool_models", None):
        return _build_collaboration_process(bpmn_model)
    return _build_single_process(bpmn_model)


def _build_single_process(bpmn_model: "BPMNModel"):
    """Bridge for single-pool models."""
    from modules.schema import BpmnProcess, BpmnElement, BpmnPool, BpmnLane, SequenceFlow

    _TASK_TYPE_MAP = {
        "userTask":         "userTask",
        "serviceTask":      "serviceTask",
        "scriptTask":       "scriptTask",
        "manualTask":       "manualTask",
        "businessRuleTask": "businessRuleTask",
        "parallelGateway":  "parallelGateway",
        "exclusiveGateway": "exclusiveGateway",
    }

    # ── Elements ──────────────────────────────────────────────────────────────
    _start_name = getattr(bpmn_model, "process_trigger", "") or "Início"
    _outcomes   = getattr(bpmn_model, "process_outcomes", []) or []
    _end_name   = (_outcomes[0] if _outcomes else None) or "Fim"

    elements = []
    for i, step in enumerate(bpmn_model.steps):
        el_type = "exclusiveGateway" if step.is_decision \
            else _TASK_TYPE_MAP.get(step.task_type, "userTask")

        if i == 0:
            elements.append(BpmnElement(
                id="ev_start", name=_start_name, type="startEvent",
                actor=None, lane=step.lane,
            ))

        elements.append(BpmnElement(
            id=step.id, name=step.title, type=el_type,
            actor=step.actor, lane=step.lane,
        ))

        if i == len(bpmn_model.steps) - 1:
            source_ids = {e.source for e in bpmn_model.edges}
            terminal   = [s for s in bpmn_model.steps if s.id not in source_ids]
            end_lane   = terminal[-1].lane if terminal else step.lane
            elements.append(BpmnElement(
                id="ev_end", name=_end_name, type="endEvent",
                actor=None, lane=end_lane,
            ))

    # ── Flows ─────────────────────────────────────────────────────────────────
    flows = []
    if bpmn_model.steps:
        flows.append(SequenceFlow(id="sf_start", source="ev_start",
                                  target=bpmn_model.steps[0].id))
    for i, edge in enumerate(bpmn_model.edges):
        flows.append(SequenceFlow(
            id=f"sf_{i+1:03d}",
            source=edge.source, target=edge.target,
            name=edge.label or "", condition=edge.condition or "",
        ))
    if bpmn_model.steps:
        flows.append(SequenceFlow(id="sf_end",
                                  source=bpmn_model.steps[-1].id, target="ev_end"))

    # ── Pools / Lanes ─────────────────────────────────────────────────────────
    pools = []
    if bpmn_model.lanes:
        lane_objects = []
        for lane_name in bpmn_model.lanes:
            lane_id    = "lane_" + lane_name.lower().replace(" ", "_")
            member_ids = [
                s.id for s in bpmn_model.steps
                if s.lane and s.lane.lower() == lane_name.lower()
            ]
            lane_objects.append(BpmnLane(id=lane_id, name=lane_name,
                                         element_ids=member_ids))
        pools.append(BpmnPool(id="pool_1", name=bpmn_model.name, lanes=lane_objects))

    return BpmnProcess(name=bpmn_model.name, elements=elements,
                       flows=flows, pools=pools)


def _build_collaboration_process(bpmn_model: "BPMNModel"):
    """Bridge for collaboration models (multiple pools)."""
    from modules.schema import BpmnProcess, BpmnElement, BpmnPool, BpmnLane, SequenceFlow

    _TASK_TYPE_MAP = {
        "userTask": "userTask", "serviceTask": "serviceTask",
        "scriptTask": "scriptTask", "manualTask": "manualTask",
        "businessRuleTask": "businessRuleTask",
        "parallelGateway": "parallelGateway",
        "exclusiveGateway": "exclusiveGateway",
    }

    all_elements: list = []
    all_flows:    list = []
    pool_objects: list = []

    for pi, pool_model in enumerate(bpmn_model.pool_models):
        steps = getattr(pool_model, "steps", [])
        edges = getattr(pool_model, "edges", [])
        lanes = getattr(pool_model, "lanes", [])
        pool_id = getattr(pool_model, "id", None) or f"pool_{pi+1}"
        pool_name = getattr(pool_model, "name", pool_id)

        # Elements for this pool
        for i, step in enumerate(steps):
            el_type = "exclusiveGateway" if step.is_decision \
                else _TASK_TYPE_MAP.get(step.task_type, "userTask")
            if i == 0:
                all_elements.append(BpmnElement(
                    id=f"ev_start_{pool_id}", name="Início", type="startEvent",
                    actor=None, lane=step.lane,
                ))
            all_elements.append(BpmnElement(
                id=step.id, name=step.title, type=el_type,
                actor=step.actor, lane=step.lane,
            ))
            if i == len(steps) - 1:
                src_ids  = {e.source for e in edges}
                terminal = [s for s in steps if s.id not in src_ids]
                end_lane = terminal[-1].lane if terminal else step.lane
                all_elements.append(BpmnElement(
                    id=f"ev_end_{pool_id}", name="Fim", type="endEvent",
                    actor=None, lane=end_lane,
                ))

        # Flows for this pool
        if steps:
            all_flows.append(SequenceFlow(
                id=f"sf_start_{pool_id}",
                source=f"ev_start_{pool_id}", target=steps[0].id,
            ))
        for i, edge in enumerate(edges):
            all_flows.append(SequenceFlow(
                id=f"sf_{pool_id}_{i+1:03d}",
                source=edge.source, target=edge.target,
                name=edge.label or "", condition=edge.condition or "",
            ))
        if steps:
            all_flows.append(SequenceFlow(
                id=f"sf_end_{pool_id}",
                source=steps[-1].id, target=f"ev_end_{pool_id}",
            ))

        # Lanes for this pool
        lane_objects: list = []
        for lane_name in lanes:
            lane_id    = f"lane_{pool_id}_" + lane_name.lower().replace(" ", "_")
            member_ids = [s.id for s in steps
                          if s.lane and s.lane.lower() == lane_name.lower()]
            lane_objects.append(BpmnLane(id=lane_id, name=lane_name,
                                         element_ids=member_ids))
        pool_objects.append(BpmnPool(id=pool_id, name=pool_name,
                                     lanes=lane_objects))

    return BpmnProcess(name=bpmn_model.name, elements=all_elements,
                       flows=all_flows, pools=pool_objects)


# ── Internal: rendering ───────────────────────────────────────────────────────

def _render_expander(report: dict) -> None:
    """Render the full diagnostic expander in Streamlit."""
    has_issues = (
        report["will_use_link_events"]
        or report["element_lane_issues"]
        or report["geometric_crossings"]
    )

    with st.expander("🔍 Diagnóstico do diagrama BPMN", expanded=has_issues):
        _render_summary(report)
        _render_lane_issues(report)
        _render_link_events_info(report)

    # Skill viewer é um expander separado — Streamlit não permite
    # expanders aninhados dentro de outros expanders.
    _render_skill_viewer()


def _render_summary(report: dict) -> None:
    """Render the main summary block."""
    st.markdown(report["summary"])


def _render_lane_issues(report: dict) -> None:
    """Render lane issue warnings if present."""
    issues = report.get("element_lane_issues", [])
    if not issues:
        return

    st.warning(
        "⚠️ Elementos com lane suspeita — verifique se o modelo LLM "
        "atribuiu as lanes corretamente antes de usar o diagrama."
    )
    for iss in issues:
        st.caption(
            f"**[{iss['type']}]** `{iss['name']}` — {iss['issue']}"
        )


def _render_link_events_info(report: dict) -> None:
    """Render link events injection info."""
    n = report.get("link_pairs_needed", 0)
    if n == 0:
        return

    st.info(
        f"🔧 **{n} par(es) de Link Events** foram injetados automaticamente "
        f"pelo gerador para eliminar os cruzamentos acima. "
        f"No diagrama aparecem como ⇒ (throw) e ➡ (catch) — "
        f"eventos intermediários que funcionam como conectores de página."
    )


def _render_skill_viewer() -> None:
    """Render sub-expander showing the active BPMN skill content."""
    with st.expander("📄 Skill BPMN ativo", expanded=False):
        if _SKILL_PATH.exists():
            content = _SKILL_PATH.read_text(encoding="utf-8")
            # Show version from frontmatter if present
            version = "?"
            for line in content.splitlines():
                if line.startswith("version:"):
                    version = line.split(":", 1)[1].strip()
                    break
            st.caption(f"Arquivo: `{_SKILL_PATH}` · Versão: **{version}**")
            st.code(content, language="markdown")
        else:
            st.warning(
                f"Arquivo `{_SKILL_PATH}` não encontrado. "
                f"Verifique se o path está correto e se o arquivo "
                f"foi commitado no repositório."
            )
