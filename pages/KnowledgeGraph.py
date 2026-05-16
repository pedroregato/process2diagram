# pages/KnowledgeGraph.py
# ─────────────────────────────────────────────────────────────────────────────
# Grafo de Conhecimento — visualização interativa das entidades, processos e
# fatos extraídos do Knowledge Hub via Plotly (sem dependências externas).
#
# Fase D do BMIF — Business Meeting Intelligence Framework
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import streamlit as st
import plotly.graph_objects as go
import math
import random

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from modules.supabase_client import get_supabase_client

apply_auth_gate()

# ── Palette ───────────────────────────────────────────────────────────────────

_COLORS = {
    "ACTOR":     "#3b82f6",
    "SYSTEM":    "#8b5cf6",
    "PROCESS":   "#f59e0b",
    "CONCEPT":   "#22c55e",
    "DOCUMENT":  "#06b6d4",
    "LOCATION":  "#f97316",
    "fact":      "#94a3b8",
    "process":   "#f59e0b",
    "edge":      "#334155",
    "bg":        "rgba(0,0,0,0)",
    "text":      "#e0e7f0",
}

_NODE_SYMBOLS = {
    "ACTOR":    "circle",
    "SYSTEM":   "diamond",
    "PROCESS":  "square",
    "CONCEPT":  "triangle-up",
    "DOCUMENT": "hexagon",
    "LOCATION": "star",
}

# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _load_graph_data(project_id: str) -> dict:
    db = get_supabase_client()
    if not db:
        return {"entities": [], "processes": [], "facts": [], "contradictions": []}

    try:
        entities = (
            db.table("kh_entities")
            .select("id, entity_type, canonical_name, aliases, occurrence_count, metadata")
            .eq("project_id", project_id)
            .order("occurrence_count", desc=True)
            .limit(150)
            .execute().data or []
        )
    except Exception:
        entities = []

    try:
        processes = (
            db.table("kh_processes")
            .select("id, process_name, description, version_count, status, involved_entities")
            .eq("project_id", project_id)
            .order("version_count", desc=True)
            .limit(50)
            .execute().data or []
        )
    except Exception:
        processes = []

    try:
        facts = (
            db.table("kh_facts")
            .select("id, subject_entity_id, predicate, object_entity_id, object_value, process_id, confidence, dialogue_act")
            .eq("project_id", project_id)
            .limit(300)
            .execute().data or []
        )
    except Exception:
        facts = []

    try:
        contradictions = (
            db.table("kh_contradictions")
            .select("id, fact_a_id, fact_b_id, severity, relation_type")
            .eq("project_id", project_id)
            .limit(50)
            .execute().data or []
        )
    except Exception:
        contradictions = []

    return {
        "entities": entities,
        "processes": processes,
        "facts": facts,
        "contradictions": contradictions,
    }


# ── Layout helpers ─────────────────────────────────────────────────────────────

def _circular_layout(n: int, radius: float = 1.0, offset: tuple = (0, 0)) -> list[tuple[float, float]]:
    """Positions for n nodes evenly on a circle."""
    positions = []
    for i in range(n):
        angle = 2 * math.pi * i / max(n, 1)
        x = offset[0] + radius * math.cos(angle)
        y = offset[1] + radius * math.sin(angle)
        positions.append((x, y))
    return positions


def _spring_layout(nodes: list[str], edges: list[tuple[str, str]], iterations: int = 50) -> dict[str, tuple[float, float]]:
    """Simple force-directed layout (no external library)."""
    rng = random.Random(42)
    pos = {n: (rng.uniform(-1, 1), rng.uniform(-1, 1)) for n in nodes}
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)

    k = 1.0 / math.sqrt(max(len(nodes), 1))
    for _ in range(iterations):
        disp: dict[str, list[float]] = {n: [0.0, 0.0] for n in nodes}
        node_list = list(nodes)
        for i, u in enumerate(node_list):
            for v in node_list[i + 1:]:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                d = max(math.sqrt(dx * dx + dy * dy), 0.01)
                rep = k * k / d
                disp[u][0] += dx / d * rep
                disp[u][1] += dy / d * rep
                disp[v][0] -= dx / d * rep
                disp[v][1] -= dy / d * rep
            for v in adj[u]:
                if v > u:
                    continue
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                d = max(math.sqrt(dx * dx + dy * dy), 0.01)
                attr = d * d / k
                disp[u][0] -= dx / d * attr
                disp[u][1] -= dy / d * attr
                disp[v][0] += dx / d * attr
                disp[v][1] += dy / d * attr

        t = 0.1
        for n in nodes:
            dx, dy = disp[n]
            d = max(math.sqrt(dx * dx + dy * dy), 0.01)
            move = min(d, t)
            pos[n] = (pos[n][0] + dx / d * move, pos[n][1] + dy / d * move)

    return pos


# ── Graph builder ──────────────────────────────────────────────────────────────

def _build_graph(data: dict, max_nodes: int, show_facts: bool, show_processes: bool, entity_types: list[str]) -> go.Figure:
    entities = data["entities"]
    processes = data["processes"] if show_processes else []
    facts = data["facts"] if show_facts else []
    contradictions = data["contradictions"]

    # Filter entities by selected types
    if entity_types:
        entities = [e for e in entities if e.get("entity_type", "ACTOR") in entity_types]
    entities = entities[:max_nodes]

    entity_ids = {e["id"] for e in entities}
    process_ids = {p["id"] for p in processes}
    contra_pairs = {(c.get("fact_a_id"), c.get("fact_b_id")) for c in contradictions}

    # Build id→index maps
    id_to_idx: dict[str, int] = {}
    node_x: list[float] = []
    node_y: list[float] = []
    node_text: list[str] = []
    node_color: list[str] = []
    node_size: list[float] = []
    node_symbol: list[str] = []
    node_hover: list[str] = []

    # --- Entity nodes ---
    all_node_ids = list(entity_ids) + [f"proc_{p['id']}" for p in processes]
    edge_pairs: list[tuple[str, str]] = []

    for fact in facts:
        s = fact.get("subject_entity_id")
        o = fact.get("object_entity_id")
        if s in entity_ids and o and o in entity_ids:
            edge_pairs.append((s, o))

    for proc in processes:
        involved = proc.get("involved_entities") or []
        for eid in involved:
            if eid in entity_ids:
                edge_pairs.append((eid, f"proc_{proc['id']}"))

    pos = _spring_layout(all_node_ids, edge_pairs, iterations=80)

    for e in entities:
        eid = e["id"]
        etype = e.get("entity_type", "ACTOR")
        count = e.get("occurrence_count", 1)
        idx = len(id_to_idx)
        id_to_idx[eid] = idx
        px, py = pos.get(eid, (0, 0))
        node_x.append(px)
        node_y.append(py)
        node_text.append(e.get("canonical_name", "?"))
        node_color.append(_COLORS.get(etype, "#94a3b8"))
        node_size.append(max(12, min(40, 12 + count * 3)))
        node_symbol.append(_NODE_SYMBOLS.get(etype, "circle"))
        aliases = ", ".join((e.get("aliases") or [])[:3])
        node_hover.append(
            f"<b>{e.get('canonical_name')}</b><br>"
            f"Tipo: {etype}<br>"
            f"Ocorrencias: {count}<br>"
            + (f"Aliases: {aliases}" if aliases else "")
        )

    for proc in processes:
        pid = f"proc_{proc['id']}"
        idx = len(id_to_idx)
        id_to_idx[pid] = idx
        px, py = pos.get(pid, (0, 0))
        node_x.append(px)
        node_y.append(py)
        node_text.append(proc.get("process_name", "?")[:22])
        node_color.append(_COLORS["PROCESS"])
        node_size.append(20)
        node_symbol.append("square")
        node_hover.append(
            f"<b>{proc.get('process_name')}</b><br>"
            f"Status: {proc.get('status', '—')}<br>"
            f"Versoes: {proc.get('version_count', 1)}<br>"
            f"{(proc.get('description') or '')[:80]}"
        )

    # --- Edges ---
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    edge_labels_x: list[float] = []
    edge_labels_y: list[float] = []
    edge_labels_text: list[str] = []

    fact_id_set = {f["id"] for f in facts}

    for fact in facts:
        s = fact.get("subject_entity_id")
        o = fact.get("object_entity_id")
        if not (s in id_to_idx and o and o in id_to_idx):
            continue
        si, oi = id_to_idx[s], id_to_idx[o]
        x0, y0 = node_x[si], node_y[si]
        x1, y1 = node_x[oi], node_y[oi]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        edge_labels_x.append(mx)
        edge_labels_y.append(my)
        edge_labels_text.append(fact.get("predicate", "")[:30])

    for proc in processes:
        pid = f"proc_{proc['id']}"
        if pid not in id_to_idx:
            continue
        oi = id_to_idx[pid]
        for eid in (proc.get("involved_entities") or []):
            if eid not in id_to_idx:
                continue
            si = id_to_idx[eid]
            x0, y0 = node_x[si], node_y[si]
            x1, y1 = node_x[oi], node_y[oi]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    # --- Contradiction edges ---
    contra_x: list[float | None] = []
    contra_y: list[float | None] = []
    for c in contradictions:
        # Use fact subject ids to find entity positions
        fa_id = c.get("fact_a_id")
        fb_id = c.get("fact_b_id")
        # Try to find entities that own these facts
        fa_ent = next((f.get("subject_entity_id") for f in facts if f["id"] == fa_id), None)
        fb_ent = next((f.get("subject_entity_id") for f in facts if f["id"] == fb_id), None)
        if fa_ent in id_to_idx and fb_ent and fb_ent in id_to_idx:
            si, oi = id_to_idx[fa_ent], id_to_idx[fb_ent]
            contra_x += [node_x[si], node_x[oi], None]
            contra_y += [node_y[si], node_y[oi], None]

    # --- Assemble figure ---
    fig = go.Figure()

    if edge_x:
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(color="#334155", width=1),
            hoverinfo="skip", showlegend=False,
        ))

    if contra_x:
        fig.add_trace(go.Scatter(
            x=contra_x, y=contra_y, mode="lines",
            line=dict(color="#ef4444", width=1.5, dash="dot"),
            hoverinfo="skip", showlegend=False, name="Contradicao",
        ))

    if node_x:
        fig.add_trace(go.Scatter(
            x=node_x, y=node_y, mode="markers+text",
            marker=dict(
                color=node_color, size=node_size,
                symbol=node_symbol,
                line=dict(color="#0f172a", width=1.5),
            ),
            text=node_text,
            textposition="top center",
            textfont=dict(size=9, color=_COLORS["text"]),
            hovertext=node_hover,
            hoverinfo="text",
            showlegend=False,
        ))

    if edge_labels_text and any(t for t in edge_labels_text):
        fig.add_trace(go.Scatter(
            x=edge_labels_x, y=edge_labels_y, mode="text",
            text=edge_labels_text,
            textfont=dict(size=7, color="#64748b"),
            hoverinfo="skip", showlegend=False,
        ))

    fig.update_layout(
        paper_bgcolor=_COLORS["bg"],
        plot_bgcolor=_COLORS["bg"],
        font=dict(color=_COLORS["text"], family="Segoe UI, system-ui"),
        margin=dict(l=0, r=0, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=600,
        dragmode="pan",
    )
    return fig


# ── Legend helper ──────────────────────────────────────────────────────────────

def _legend_html() -> str:
    items = [
        ("ACTOR",    _COLORS["ACTOR"],    "●", "Pessoa / Ator"),
        ("SYSTEM",   _COLORS["SYSTEM"],   "◆", "Sistema"),
        ("PROCESS",  _COLORS["PROCESS"],  "■", "Processo"),
        ("CONCEPT",  _COLORS["CONCEPT"],  "▲", "Conceito"),
        ("DOCUMENT", _COLORS["DOCUMENT"], "⬡", "Documento"),
        ("LOCATION", _COLORS["LOCATION"], "★", "Local"),
    ]
    parts = [
        f'<span style="margin-right:14px;white-space:nowrap;">'
        f'<span style="color:{color};font-size:1.1em;">{sym}</span>'
        f' <span style="font-size:0.82em;color:#94a3b8;">{label}</span></span>'
        for _, color, sym, label in items
    ]
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:8px 0;">'
        + "".join(parts)
        + '<span style="margin-left:16px;white-space:nowrap;">'
          '<span style="color:#ef4444;font-size:0.9em;">- - -</span>'
          ' <span style="font-size:0.82em;color:#94a3b8;">Contradicao</span></span>'
        + "</div>"
    )


# ── Main render ────────────────────────────────────────────────────────────────

project_id, project_name = require_active_project()

st.markdown(f"## 🕸️ Grafo de Conhecimento")
st.caption(
    f"Projeto: **{project_name}** — "
    "Visualizacao das entidades, processos e relacoes extraidos automaticamente das reunioes. "
    "Baseado no Knowledge Hub (BMIF Fase D)."
)

data = _load_graph_data(project_id)
entities = data["entities"]
processes = data["processes"]
facts = data["facts"]
contradictions = data["contradictions"]

if not entities and not processes:
    st.info(
        "Nenhum dado de Knowledge Hub encontrado para este projeto. "
        "Execute o pipeline em pelo menos uma reuniao para popular o grafo."
    )
    st.stop()

# ── KPI strip ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Entidades", len(entities))
k2.metric("Processos", len(processes))
k3.metric("Fatos / Relacoes", len(facts))
k4.metric("Contradicoes", len(contradictions))

st.markdown("---")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filtros do Grafo")
    all_types = sorted({e.get("entity_type", "ACTOR") for e in entities})
    selected_types = st.multiselect(
        "Tipos de entidade", all_types, default=all_types, key="kg_types"
    )
    show_facts = st.toggle("Mostrar relacoes (fatos)", value=True, key="kg_facts")
    show_processes = st.toggle("Mostrar processos", value=True, key="kg_procs")
    max_nodes = st.slider("Max entidades no grafo", 10, min(150, len(entities)), min(60, len(entities)), key="kg_maxn")
    st.markdown("---")
    st.markdown(_legend_html(), unsafe_allow_html=True)

# ── Main graph ────────────────────────────────────────────────────────────────
tab_graph, tab_table, tab_facts = st.tabs(["🕸️ Grafo", "📋 Entidades", "🔗 Relacoes"])

with tab_graph:
    if not selected_types:
        st.warning("Selecione pelo menos um tipo de entidade no painel lateral.")
    else:
        fig = _build_graph(data, max_nodes, show_facts, show_processes, selected_types)
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        if contradictions:
            st.info(
                f"**{len(contradictions)} contradicao(oes)** detectada(s) — "
                "representadas como tracejado vermelho. "
                "Acesse **Saude do Contexto** para detalhes."
            )

with tab_table:
    st.markdown("#### Entidades extraidas")
    if entities:
        rows = []
        for e in entities:
            aliases = ", ".join((e.get("aliases") or [])[:5])
            meta = e.get("metadata") or {}
            rows.append({
                "Tipo": e.get("entity_type", "—"),
                "Nome": e.get("canonical_name", "—"),
                "Ocorrencias": e.get("occurrence_count", 1),
                "Aliases": aliases,
                "Descricao": (meta.get("description") or "")[:60],
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma entidade disponivel.")

    if processes:
        st.markdown("#### Processos")
        proc_rows = []
        for p in processes:
            proc_rows.append({
                "Processo": p.get("process_name", "—"),
                "Status": p.get("status", "—"),
                "Versoes": p.get("version_count", 1),
                "Descricao": (p.get("description") or "")[:80],
            })
        st.dataframe(proc_rows, use_container_width=True, hide_index=True)

with tab_facts:
    st.markdown("#### Relacoes / Fatos")
    if facts:
        entity_name_map = {e["id"]: e.get("canonical_name", e["id"][:8]) for e in entities}
        proc_name_map = {p["id"]: p.get("process_name", p["id"][:8]) for p in processes}
        fact_rows = []
        for f in facts:
            subj = entity_name_map.get(f.get("subject_entity_id", ""), f.get("subject_entity_id", "")[:8] or "—")
            obj_e = entity_name_map.get(f.get("object_entity_id", ""), "")
            obj_v = f.get("object_value", "")
            obj = obj_e or obj_v or "—"
            proc = proc_name_map.get(f.get("process_id", ""), "")
            fact_rows.append({
                "Sujeito": subj,
                "Predicado": f.get("predicate", "—"),
                "Objeto": obj[:60],
                "Processo": proc[:30],
                "Confianca": f"{int((f.get('confidence') or 1.0) * 100)}%",
                "Ato Dialogo": f.get("dialogue_act") or "—",
            })
        st.dataframe(fact_rows, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum fato/relacao disponivel.")
