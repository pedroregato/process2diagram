# pages/KnowledgeGraph.py
# ─────────────────────────────────────────────────────────────────────────────
# Grafo de Conhecimento — visualização interativa das entidades, processos e
# fatos extraídos do Knowledge Hub via pyvis (física Barnes-Hut, arrastar nós).
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
import streamlit.components.v1 as components

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from modules.supabase_client import get_supabase_client

apply_auth_gate()

# ── Palette ───────────────────────────────────────────────────────────────────

# 12 cores maximamente distintas — atribuídas por ordem alfabética de tipo.
_PALETTE = [
    "#f87171",  # vermelho
    "#38bdf8",  # azul-ciano
    "#4ade80",  # verde
    "#c084fc",  # roxo
    "#f472b6",  # rosa
    "#34d399",  # esmeralda
    "#fb923c",  # laranja
    "#22d3ee",  # ciano claro
    "#a78bfa",  # violeta
    "#86efac",  # verde-claro
    "#fbbf24",  # âmbar (reservado para processos KH)
    "#e2e8f0",  # cinza claro
]

# Cor fixa para nós de Processo do Knowledge Hub
_PROC_COLOR = "#fde047"

# Mapeamento tipo → forma pyvis
_TYPE_SHAPE: dict[str, str] = {
    "PERSON":     "dot",
    "ACTOR":      "dot",
    "SYSTEM":     "diamond",
    "PROCESS":    "square",
    "DOCUMENT":   "triangle",
    "CONCEPT":    "hexagon",
    "RULE":       "star",
    "ROLE":       "triangleDown",
    "DEPARTMENT": "ellipse",
    "LOCATION":   "ellipse",
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
            .select("id, entity_type, canonical_name, aliases, occurrence_count, "
                    "meeting_ids, first_seen_meeting_id, last_seen_meeting_id, metadata")
            .eq("project_id", project_id)
            .order("occurrence_count", desc=True)
            .limit(150)
            .execute().data or []
        )
    except Exception:
        try:
            # Fallback: schema without meeting_ids (pre-migration)
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


# ── Graph builder (pyvis) ──────────────────────────────────────────────────────

def _build_pyvis_graph(
    data: dict, max_nodes: int, show_ep_edges: bool,
    show_processes: bool, entity_types: list[str],
    min_occurrence: int = 1, graph_height: int = 720,
    show_entity_edges: bool = False, min_shared_meetings: int = 2,
    physics_enabled: bool = True,
) -> str:
    """Build a pyvis network and return the full HTML string."""
    from pyvis.network import Network

    entities = data["entities"]
    processes = data["processes"] if show_processes else []

    if entity_types:
        entities = [e for e in entities if e.get("entity_type", "ACTOR") in entity_types]
    if min_occurrence > 1:
        entities = [e for e in entities if (e.get("occurrence_count") or 1) >= min_occurrence]
    entities = entities[:max_nodes]

    entity_ids = {e["id"] for e in entities}

    # Cor por tipo (atribuição dinâmica, ordem alfabética)
    unique_types = sorted({e.get("entity_type", "ACTOR") for e in entities})
    type_color = {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(unique_types)}

    # Entity meeting map — prefere meeting_ids[], fallback a first/last seen
    entity_meeting_map: dict[str, set[str]] = {}
    for e in entities:
        mtgs: set[str] = set(e.get("meeting_ids") or [])
        for col in ("first_seen_meeting_id", "last_seen_meeting_id"):
            v = e.get(col)
            if v:
                mtgs.add(v)
        entity_meeting_map[e["id"]] = mtgs

    net = Network(
        height=f"{graph_height}px",
        width="100%",
        bgcolor="#0d1b2a",
        font_color="#f1f5f9",
    )

    # ── Nós de entidade ────────────────────────────────────────────────────────
    for e in entities:
        eid   = e["id"]
        etype = e.get("entity_type", "ACTOR")
        count = e.get("occurrence_count") or 1
        name  = e.get("canonical_name", "?")
        aliases = ", ".join((e.get("aliases") or [])[:3])
        size  = max(12, min(40, 12 + count * 2.5))
        color = type_color.get(etype, _PALETTE[0])
        shape = _TYPE_SHAPE.get(etype, "dot")
        tooltip = (
            f"<b>{name}</b><br>"
            f"Tipo: {etype.replace('_', ' ').title()}<br>"
            f"Ocorrências: {count}"
            + (f"<br>Aliases: {aliases}" if aliases else "")
        )
        net.add_node(
            eid, label=name, title=tooltip,
            color={
                "background": color,
                "border": "#0a0f1a",
                "highlight": {"background": color, "border": "#ffffff"},
                "hover":     {"background": color, "border": "#ffffff"},
            },
            size=size, shape=shape,
            font={"color": "#ffffff", "size": 12, "face": "Segoe UI, system-ui"},
        )

    # ── Nós de processo KH ────────────────────────────────────────────────────
    for proc in processes:
        pid   = f"proc_{proc['id']}"
        pname = proc.get("process_name", "?")
        desc  = (proc.get("description") or "")[:80]
        tooltip = (
            f"<b>{pname}</b><br>"
            f"Tipo: Processo (KH)<br>"
            f"Status: {proc.get('status', '—')}<br>"
            f"Versões: {proc.get('version_count', 1)}"
            + (f"<br>{desc}" if desc else "")
        )
        net.add_node(
            pid, label=pname[:24], title=tooltip,
            color={
                "background": _PROC_COLOR,
                "border": "#78350f",
                "highlight": {"background": _PROC_COLOR, "border": "#ffffff"},
                "hover":     {"background": _PROC_COLOR, "border": "#ffffff"},
            },
            size=22, shape="square",
            font={"color": "#0a0f1a", "size": 11, "bold": True, "face": "Segoe UI, system-ui"},
        )

    # ── Arestas entidade → processo (co-ocorrência de reunião) ────────────────
    if show_ep_edges:
        for proc in processes:
            pid = f"proc_{proc['id']}"
            proc_meetings = set(proc.get("meeting_ids") or [])
            if not proc_meetings:
                continue
            for e in entities:
                eid = e["id"]
                shared = entity_meeting_map.get(eid, set()) & proc_meetings
                if shared:
                    n = len(shared)
                    reuniao = "reunião" if n == 1 else "reuniões"
                    net.add_edge(
                        eid, pid,
                        title=f"Participou em {n} {reuniao} onde este processo foi discutido",
                        color={"color": "#475569", "highlight": "#94a3b8", "hover": "#94a3b8"},
                        width=max(1.0, 1.0 + n * 0.4),
                    )

    # ── Arestas entidade → entidade (co-ocorrência opcional) ──────────────────
    entity_list = list(entities)
    if show_entity_edges and len(entity_list) > 1:
        for i, ea in enumerate(entity_list):
            for eb in entity_list[i + 1:]:
                shared = entity_meeting_map.get(ea["id"], set()) & entity_meeting_map.get(eb["id"], set())
                if len(shared) >= min_shared_meetings:
                    n = len(shared)
                    reuniao = "reunião" if n == 1 else "reuniões"
                    net.add_edge(
                        ea["id"], eb["id"],
                        title=f"Co-ocorreram em {n} {reuniao}",
                        color={"color": "#334155", "highlight": "#64748b", "hover": "#64748b"},
                        width=1.0,
                        dashes=True,
                    )

    # ── Opções de física (Barnes-Hut) e interação ─────────────────────────────
    options = {
        "physics": {
            "enabled": physics_enabled,
            "solver": "barnesHut",
            "barnesHut": {
                "gravitationalConstant": -8000,
                "centralGravity": 0.3,
                "springLength": 130,
                "springConstant": 0.04,
                "damping": 0.09,
                "avoidOverlap": 0.4,
            },
            "maxVelocity": 50,
            "minVelocity": 0.75,
            "stabilization": {
                "enabled": True,
                "iterations": 200,
                "updateInterval": 25,
                "onlyDynamicEdges": False,
                "fit": True,
            },
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 80,
            "navigationButtons": False,
            "keyboard": False,
            "zoomView": True,
            "dragView": True,
            "dragNodes": True,
            "multiselect": False,
        },
        "edges": {
            "smooth": {"type": "continuous"},
            "arrows": {"to": {"enabled": False}},
            "hoverWidth": 2,
            "selectionWidth": 2,
        },
        "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 3,
        },
    }
    net.set_options(json.dumps(options))

    return net.generate_html(local=False)




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

Use o mouse para **arrastar nos individualmente** (reorganize o layout), **scroll** para zoom e
**hover** para ver detalhes de cada entidade ou aresta. A simulacao fisica organiza os nos
automaticamente — desative em "Simulacao fisica" para fixar o layout apos arrastar.
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
    show_processes = st.toggle("Mostrar processos (KH)", value=True, key="kg_procs")
    show_ep_edges = st.toggle("Arestas entidade→processo", value=True, key="kg_facts",
        help="Conecta entidades aos processos do Knowledge Hub com os quais co-ocorreram.")
    show_entity_edges = st.toggle("Arestas entidade→entidade", value=False, key="kg_ent_edges",
        help="Conecta entidades que co-ocorrem em N+ reunioes. Pode gerar muitas arestas.")
    if show_entity_edges:
        min_shared = st.slider("Reunioes em comum (minimo)", 1, 5, 2, key="kg_shared_mtgs",
            help="Quantas reunioes as duas entidades precisam compartilhar para serem conectadas.")
    else:
        min_shared = 2
    physics_enabled = st.toggle("Simulacao fisica (mover nos)", value=True, key="kg_physics",
        help="Ativa a simulacao Barnes-Hut — os nos se atraem/repelem organicamente. Desative para fixar o layout.")
    max_nodes = st.slider(
        "Max entidades no grafo", 10, min(150, len(entities)), min(60, len(entities)), key="kg_maxn"
    )
    graph_height = st.select_slider(
        "Altura do grafo", [480, 600, 720, 860, 1000], value=720, key="kg_height"
    )
    st.markdown("---")
    st.caption("Passe o mouse sobre os nos e arestas para ver detalhes. Arraste nos para reorganizar.")

# ── Main graph ────────────────────────────────────────────────────────────────
tab_graph, tab_table, tab_facts, tab_export = st.tabs(
    ["🕸️ Grafo", "📋 Entidades", "🔗 Fatos", "⬇️ Exportar"]
)

with tab_graph:
    if not selected_types:
        st.warning("Selecione pelo menos um tipo de entidade no painel lateral.")
    else:
        try:
            html_graph = _build_pyvis_graph(
                data, max_nodes, show_ep_edges, show_processes, selected_types,
                min_occurrence=min_occurrence, graph_height=graph_height,
                show_entity_edges=show_entity_edges, min_shared_meetings=min_shared,
                physics_enabled=physics_enabled,
            )
            components.html(html_graph, height=graph_height + 30, scrolling=False)
        except ImportError:
            st.error(
                "A biblioteca **pyvis** nao esta instalada. "
                "Execute `pip install pyvis==0.3.2` e reinicie o servidor."
            )

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
        _mtgs: set[str] = set(_e.get("meeting_ids") or [])
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
