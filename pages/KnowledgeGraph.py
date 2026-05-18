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

# 12 cores maximamente distintas no círculo cromático — atribuídas
# dinamicamente aos tipos presentes nos dados (ordem alfabética dos tipos).
# Desta forma funciona independentemente dos nomes que o LLM usa para os tipos.
_PALETTE = [
    "#f87171",  # vermelho
    "#38bdf8",  # azul-ciano
    "#4ade80",  # verde
    "#fbbf24",  # âmbar
    "#c084fc",  # roxo
    "#f472b6",  # rosa
    "#34d399",  # esmeralda
    "#fb923c",  # laranja
    "#fde047",  # amarelo
    "#22d3ee",  # ciano claro
    "#a78bfa",  # violeta
    "#86efac",  # verde-claro
]

_SYMBOL_LIST = [
    "circle", "diamond", "square", "triangle-up", "star",
    "hexagon2", "circle-open", "triangle-down", "cross",
    "pentagon", "diamond-open", "square-open",
]

# Cor fixa para nós de Processo do Knowledge Hub
_PROC_COLOR  = "#fde047"
_PROC_SYMBOL = "square-dot"
_PROC_LABEL  = "Processo (Knowledge Hub)"

_COLORS = {
    "edge":  "#475569",
    "bg":    "#0d1b2a",
    "text":  "#f1f5f9",
    "label": "#ffffff",
}


def _type_styles(unique_types: list[str]) -> dict[str, dict]:
    """Atribui cor e símbolo distintos a cada tipo presente nos dados."""
    styles: dict[str, dict] = {}
    for i, t in enumerate(sorted(unique_types)):
        styles[t] = {
            "color":  _PALETTE[i % len(_PALETTE)],
            "symbol": _SYMBOL_LIST[i % len(_SYMBOL_LIST)],
            "label":  t.replace("_", " ").title(),
        }
    return styles

# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _load_graph_data(project_id: str) -> dict:
    db = get_supabase_client()
    if not db:
        return {"entities": [], "processes": [], "facts": [], "contradictions": []}

    try:
        entities = (
            db.table("kh_entities")
            .select("id, entity_type, canonical_name, aliases, occurrence_count, "
                    "first_seen_meeting_id, last_seen_meeting_id, metadata")
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
            .select("id, process_name, description, version_count, status, meeting_ids")
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
            .select("id, fact_type, content, source_meeting_ids, confidence, is_active, dialogue_act")
            .eq("project_id", project_id)
            .eq("is_active", True)
            .limit(300)
            .execute().data or []
        )
    except Exception:
        try:
            facts = (
                db.table("kh_facts")
                .select("id, fact_type, content, source_meeting_ids, confidence, is_active")
                .eq("project_id", project_id)
                .eq("is_active", True)
                .limit(300)
                .execute().data or []
            )
        except Exception:
            facts = []

    try:
        contradictions = (
            db.table("kh_contradictions")
            .select("id, description, meeting_a_id, meeting_b_id, severity, relation_type, status")
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

def _build_graph(
    data: dict, max_nodes: int, show_facts: bool,
    show_processes: bool, entity_types: list[str],
    min_occurrence: int = 1, show_labels: bool = True,
    graph_height: int = 640,
) -> go.Figure:
    from collections import defaultdict

    entities = data["entities"]
    processes = data["processes"] if show_processes else []
    facts     = data["facts"] if show_facts else []
    contradictions = data["contradictions"]

    if entity_types:
        entities = [e for e in entities if e.get("entity_type", "ACTOR") in entity_types]
    if min_occurrence > 1:
        entities = [e for e in entities if (e.get("occurrence_count") or 1) >= min_occurrence]
    entities = entities[:max_nodes]

    entity_ids = {e["id"] for e in entities}

    # ── 0. Estilos dinâmicos — cor/símbolo atribuídos aos tipos reais nos dados ─
    unique_types = sorted({e.get("entity_type", "unknown") for e in entities})
    styles = _type_styles(unique_types)

    # ── 1. Spring layout (coordenadas) ─────────────────────────────────────────
    all_node_ids = list(entity_ids) + [f"proc_{p['id']}" for p in processes]

    # Build entity→process edges via meeting co-occurrence:
    # entity seen in a meeting where the process was discussed → draw edge.
    # kh_entities has first_seen_meeting_id / last_seen_meeting_id;
    # kh_processes has meeting_ids (full list).
    edge_pairs: list[tuple[str, str]] = []
    entity_meeting_map: dict[str, set[str]] = {}
    for e in entities:
        mtgs: set[str] = set()
        for col in ("first_seen_meeting_id", "last_seen_meeting_id"):
            v = e.get(col)
            if v:
                mtgs.add(v)
        entity_meeting_map[e["id"]] = mtgs

    for proc in processes:
        proc_meetings = set(proc.get("meeting_ids") or [])
        if not proc_meetings:
            continue
        pid = f"proc_{proc['id']}"
        for e in entities:
            eid = e["id"]
            if eid not in entity_ids:
                continue
            if entity_meeting_map.get(eid, set()) & proc_meetings:
                edge_pairs.append((eid, pid))

    pos = _spring_layout(all_node_ids, edge_pairs, iterations=80)

    # ── 2. Construir arrays paralelos de nós ───────────────────────────────────
    id_to_idx: dict[str, int] = {}
    node_x: list[float]  = []
    node_y: list[float]  = []
    node_text: list[str] = []
    node_size: list[float] = []
    node_hover: list[str] = []
    node_etype: list[str] = []   # tipo de cada nó (para agrupar por trace)

    for e in entities:
        eid   = e["id"]
        etype = e.get("entity_type", "ACTOR")
        count = e.get("occurrence_count", 1)
        id_to_idx[eid] = len(id_to_idx)
        px, py = pos.get(eid, (0.0, 0.0))
        node_x.append(px);  node_y.append(py)
        node_text.append(e.get("canonical_name", "?"))
        node_size.append(max(14, min(42, 14 + count * 3)))
        node_etype.append(etype)
        aliases = ", ".join((e.get("aliases") or [])[:3])
        type_label = styles.get(etype, {}).get("label", etype)
        node_hover.append(
            f"<b>{e.get('canonical_name')}</b><br>"
            f"Tipo: {type_label}<br>"
            f"Ocorrencias: {count}"
            + (f"<br>Aliases: {aliases}" if aliases else "")
        )

    # Nós de processo KH
    proc_x: list[float] = []; proc_y: list[float] = []
    proc_text: list[str] = []; proc_size: list[float] = []; proc_hover: list[str] = []
    for proc in processes:
        pid = f"proc_{proc['id']}"
        id_to_idx[pid] = len(id_to_idx)
        px, py = pos.get(pid, (0.0, 0.0))
        proc_x.append(px);  proc_y.append(py)
        proc_text.append(proc.get("process_name", "?")[:22])
        proc_size.append(20)
        proc_hover.append(
            f"<b>{proc.get('process_name')}</b><br>"
            f"Status: {proc.get('status', '—')}<br>"
            f"Versoes: {proc.get('version_count', 1)}<br>"
            + (proc.get("description") or "")[:80]
        )

    # ── 3. Arestas entidade → processo (co-ocorrência de reunião) ──────────────
    edge_x: list[float | None] = []; edge_y: list[float | None] = []
    elbl_x: list[float] = []; elbl_y: list[float] = []; elbl_t: list[str] = []

    all_x = node_x + proc_x
    all_y = node_y + proc_y

    for eid, pid in edge_pairs:
        if eid not in id_to_idx or pid not in id_to_idx:
            continue
        si, oi = id_to_idx[eid], id_to_idx[pid]
        x0, y0 = all_x[si], all_y[si]
        x1, y1 = all_x[oi], all_y[oi]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    # ── 4. Arestas de contradição (não há entity refs diretas) ────────────────
    contra_x: list[float | None] = []; contra_y: list[float | None] = []
    # kh_contradictions use meeting_a_id/meeting_b_id — shown as KPI count only

    # ── 5. Montar figura ───────────────────────────────────────────────────────
    fig = go.Figure()

    # Arestas (abaixo dos nós)
    if edge_x:
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(color="#475569", width=1.2),
            hoverinfo="skip", showlegend=False,
        ))
    if contra_x:
        fig.add_trace(go.Scatter(
            x=contra_x, y=contra_y, mode="lines",
            line=dict(color="#ef4444", width=2, dash="dot"),
            hoverinfo="skip", name="Contradicao detectada", showlegend=True,
        ))

    # ── Um trace de marcadores por tipo — gera legenda nativa do Plotly ──
    type_indices: dict[str, list[int]] = defaultdict(list)
    for i, et in enumerate(node_etype):
        type_indices[et].append(i)

    for etype in sorted(type_indices.keys()):
        idxs   = type_indices[etype]
        st_    = styles.get(etype, {})
        color  = st_.get("color",  _PALETTE[0])
        symbol = st_.get("symbol", "circle")
        label  = st_.get("label",  etype)
        xs   = [node_x[i] for i in idxs]
        ys   = [node_y[i] for i in idxs]
        sizes = [node_size[i] for i in idxs]
        texts = [node_text[i] for i in idxs]
        hovers = [node_hover[i] for i in idxs]

        # Marcadores — com legenda
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers",
            name=label,
            marker=dict(
                color=color, size=sizes, symbol=symbol,
                line=dict(color="#0a0f1a", width=2),
                opacity=0.95,
            ),
            hovertext=hovers, hoverinfo="text",
            showlegend=True,
            legendgroup=etype,
        ))
        # Labels (sem entrar na legenda)
        if show_labels:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="text",
                text=[f"<b>{t}</b>" for t in texts],
                textposition="top center",
                textfont=dict(size=11, color="#ffffff", family="Segoe UI, system-ui"),
                hoverinfo="skip", showlegend=False,
                legendgroup=etype,
            ))

    # Nós de processo KH
    if proc_x:
        fig.add_trace(go.Scatter(
            x=proc_x, y=proc_y, mode="markers",
            name=_PROC_LABEL,
            marker=dict(
                color=_PROC_COLOR, size=proc_size,
                symbol=_PROC_SYMBOL,
                line=dict(color="#0a0f1a", width=2), opacity=0.95,
            ),
            hovertext=proc_hover, hoverinfo="text",
            showlegend=True, legendgroup="_PROC",
        ))
        if show_labels:
            fig.add_trace(go.Scatter(
                x=proc_x, y=proc_y, mode="text",
                text=[f"<b>{t}</b>" for t in proc_text],
                textposition="top center",
                textfont=dict(size=10, color="#ffffff", family="Segoe UI, system-ui"),
                hoverinfo="skip", showlegend=False, legendgroup="_PROC",
            ))

    # Labels das arestas
    if elbl_t and any(t for t in elbl_t):
        fig.add_trace(go.Scatter(
            x=elbl_x, y=elbl_y, mode="text",
            text=elbl_t,
            textfont=dict(size=8, color="#94a3b8", family="Segoe UI, system-ui"),
            hoverinfo="skip", showlegend=False,
        ))

    fig.update_layout(
        paper_bgcolor=_COLORS["bg"],
        plot_bgcolor=_COLORS["bg"],
        font=dict(color=_COLORS["text"], family="Segoe UI, system-ui"),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, showspikes=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, showspikes=False),
        height=graph_height,
        dragmode="pan",
        hoverlabel=dict(bgcolor="#1e293b", font_size=12,
                        font_color="#f1f5f9", bordercolor="#475569"),
        legend=dict(
            bgcolor="#111f30", bordercolor="#334155", borderwidth=1,
            font=dict(color="#f1f5f9", size=12),
            title=dict(text="<b>Tipo de entidade</b>",
                       font=dict(color="#fbbf24", size=12)),
            itemsizing="constant",
            x=1.01, y=1, xanchor="left", yanchor="top",
        ),
    )
    return fig




# ── Main render ────────────────────────────────────────────────────────────────

project_id, project_name = require_active_project()

st.markdown(f"## 🕸️ Grafo de Conhecimento")
st.caption(f"Projeto: **{project_name}**")

with st.expander("O que e um Grafo de Conhecimento e por que ele importa?", expanded=False):
    st.markdown("""
Um **Grafo de Conhecimento** (Knowledge Graph) representa o conhecimento organizacional
como uma rede de **entidades** (pessoas, sistemas, conceitos, documentos) ligadas por
**relacoes semanticas** (fatos extraidos das transcricoes das reunioes).

#### Por que usar?

| Perspectiva | Valor gerado |
|---|---|
| **Rastreabilidade** | Quem mencionou o que, em qual reuniao, com qual frequencia |
| **Descoberta de padroes** | Entidades que aparecem juntas frequentemente sinalizam dependencias nao documentadas |
| **Deteccao de conflitos** | Contradicoes entre fatos de reunioes diferentes ficam visiveis como arestas vermelhas |
| **Auditoria de decisoes** | Quais atores estiveram envolvidos em cada processo ou decisao |
| **Inteligencia organizacional** | A base para o Assistente responder perguntas com contexto historico |

#### Como ler o grafo

- **No (bolinha/forma):** cada entidade ou processo extraido das reunioes
- **Tamanho do no:** proporcional ao numero de ocorrencias — entidades mais citadas ficam maiores
- **Aresta cinza:** relacao (fato) entre duas entidades — o predicado aparece no meio da aresta
- **Aresta vermelha tracejada:** contradicao detectada entre dois fatos
- **Forma do no:** indica o tipo — circulo=Ator, losango=Sistema, quadrado=Processo, triangulo=Conceito

#### Interacao

Use o mouse para **arrastar** o grafo, **rolar** para zoom e **clicar com hover** para ver
detalhes de cada entidade. Os filtros na barra lateral permitem isolar tipos especificos
de entidades ou desativar as relacoes para uma visao mais limpa.
    """)

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
    max_occ = max((e.get("occurrence_count") or 1) for e in entities) if entities else 1
    min_occurrence = st.slider(
        "Ocorrencias minimas", 1, max(max_occ, 2), 1, key="kg_min_occ",
        help="Oculta entidades com menos ocorrencias — reduz o cluster central.",
    )
    show_processes = st.toggle("Mostrar processos", value=True, key="kg_procs")
    show_facts = st.toggle("Mostrar arestas entidade→processo", value=True, key="kg_facts")
    show_labels = st.toggle("Mostrar rotulos", value=True, key="kg_labels")
    max_nodes = st.slider(
        "Max entidades no grafo", 10, min(150, len(entities)), min(60, len(entities)), key="kg_maxn"
    )
    graph_height = st.select_slider(
        "Altura do grafo", [480, 600, 720, 860, 1000], value=640, key="kg_height"
    )
    st.markdown("---")
    st.caption("A legenda de cores aparece dentro do grafico (canto superior direito).")

# ── Main graph ────────────────────────────────────────────────────────────────
tab_graph, tab_table, tab_facts, tab_export = st.tabs(
    ["🕸️ Grafo", "📋 Entidades", "🔗 Fatos", "⬇️ Exportar"]
)

with tab_graph:
    if not selected_types:
        st.warning("Selecione pelo menos um tipo de entidade no painel lateral.")
    else:
        fig = _build_graph(
            data, max_nodes, show_facts, show_processes, selected_types,
            min_occurrence=min_occurrence, show_labels=show_labels,
            graph_height=graph_height,
        )
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        if contradictions:
            st.info(
                f"**{len(contradictions)} contradicao(oes)** detectada(s). "
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
    st.markdown("#### Fatos / Decisoes / Regras extraidos")
    if facts:
        fact_rows = []
        for f in facts:
            conf = f.get("confidence")
            fact_rows.append({
                "Tipo":         f.get("fact_type") or "—",
                "Conteudo":     (f.get("content") or "")[:120],
                "Confianca":    f"{int((conf or 1.0) * 100)}%" if conf is not None else "—",
                "Ato Dialogo":  f.get("dialogue_act") or "—",
            })
        st.caption(f"{len(fact_rows)} fato(s) extraido(s) das transcricoes.")
        st.dataframe(fact_rows, use_container_width=True, hide_index=True)
    else:
        st.info(
            "Nenhum fato disponivel para este projeto ainda. "
            "Os fatos sao extraidos pelo **Knowledge Extractor** durante o pipeline "
            "(ative o checkbox 'Grafo de Conhecimento (KH)' na barra lateral)."
        )

with tab_export:
    st.markdown("#### Exportar dados do Grafo de Conhecimento")
    st.caption(
        "Exporte todos os dados brutos para analise externa ou para compartilhar com o assistente."
    )

    # Build entity→process edge list for export
    _entity_meeting_map: dict[str, set[str]] = {}
    for _e in entities:
        _mtgs: set[str] = set()
        for _col in ("first_seen_meeting_id", "last_seen_meeting_id"):
            _v = _e.get(_col)
            if _v:
                _mtgs.add(_v)
        _entity_meeting_map[_e["id"]] = _mtgs

    _edges_export = []
    for _p in processes:
        _pmtgs = set(_p.get("meeting_ids") or [])
        for _e in entities:
            if _entity_meeting_map.get(_e["id"], set()) & _pmtgs:
                _edges_export.append({
                    "entity_id":    _e["id"],
                    "entity_name":  _e.get("canonical_name", ""),
                    "entity_type":  _e.get("entity_type", ""),
                    "process_id":   _p["id"],
                    "process_name": _p.get("process_name", ""),
                })

    export_payload = {
        "project_id":   project_id,
        "project_name": project_name,
        "summary": {
            "entities":       len(entities),
            "processes":      len(processes),
            "facts":          len(facts),
            "contradictions": len(contradictions),
            "edges":          len(_edges_export),
        },
        "entities": [
            {
                "id":               e["id"],
                "canonical_name":   e.get("canonical_name"),
                "entity_type":      e.get("entity_type"),
                "occurrence_count": e.get("occurrence_count"),
                "aliases":          e.get("aliases") or [],
                "first_seen_meeting_id": e.get("first_seen_meeting_id"),
                "last_seen_meeting_id":  e.get("last_seen_meeting_id"),
            }
            for e in entities
        ],
        "processes": [
            {
                "id":            p["id"],
                "process_name":  p.get("process_name"),
                "description":   p.get("description"),
                "version_count": p.get("version_count"),
                "status":        p.get("status"),
                "meeting_ids":   p.get("meeting_ids") or [],
            }
            for p in processes
        ],
        "facts": [
            {
                "id":                f["id"],
                "fact_type":         f.get("fact_type"),
                "content":           f.get("content"),
                "confidence":        f.get("confidence"),
                "dialogue_act":      f.get("dialogue_act"),
                "source_meeting_ids": f.get("source_meeting_ids") or [],
            }
            for f in facts
        ],
        "contradictions": [
            {
                "id":            c["id"],
                "description":   c.get("description"),
                "severity":      c.get("severity"),
                "relation_type": c.get("relation_type"),
                "status":        c.get("status"),
                "meeting_a_id":  c.get("meeting_a_id"),
                "meeting_b_id":  c.get("meeting_b_id"),
            }
            for c in contradictions
        ],
        "edges_entity_process": _edges_export,
    }

    export_json = json.dumps(export_payload, ensure_ascii=False, indent=2)

    col_dl, col_info = st.columns([1, 3])
    with col_dl:
        st.download_button(
            label="⬇️ Baixar JSON",
            data=export_json,
            file_name=f"knowledge_graph_{project_name.replace(' ', '_')}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_info:
        st.info(
            f"**{len(entities)}** entidades · **{len(processes)}** processos · "
            f"**{len(facts)}** fatos · **{len(contradictions)}** contradições · "
            f"**{len(_edges_export)}** arestas computadas"
        )

    with st.expander("Previsualizar JSON (primeiros 3 elementos de cada lista)"):
        preview = {
            "summary":    export_payload["summary"],
            "entities":   export_payload["entities"][:3],
            "processes":  export_payload["processes"][:3],
            "facts":      export_payload["facts"][:3],
            "contradictions": export_payload["contradictions"][:3],
            "edges_entity_process": export_payload["edges_entity_process"][:5],
        }
        st.json(preview)
