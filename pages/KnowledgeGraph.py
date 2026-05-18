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

# Verbo semântico por tipo — aresta entidade → processo.
# PERSON/ACTOR não entram aqui: determinados dinamicamente via roster.
_EP_VERB: dict[str, str] = {
    "ROLE":       "Esteve presente em",
    "SYSTEM":     "Foi mencionado em",
    "DOCUMENT":   "Foi referenciado em",
    "CONCEPT":    "Foi discutido em",
    "RULE":       "Foi aplicada em",
    "DEPARTMENT": "Esteve envolvido em",
    "LOCATION":   "Foi citado em",
    "PROCESS":    "Relacionou-se com este processo em",
}
_EP_VERB_DEFAULT = "Apareceu em"


def _is_participant(entity: dict, participant_names: set[str]) -> bool:
    """Retorna True se a entidade consta no roster de participantes do projeto."""
    if not participant_names:
        return False
    name = (entity.get("canonical_name") or "").lower().strip()
    if name and name in participant_names:
        return True
    for alias in (entity.get("aliases") or []):
        if alias and alias.lower().strip() in participant_names:
            return True
    return False

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

    # Roster de participantes confirmados do projeto — usado para distinguir
    # "participou" vs "foi mencionado" nas arestas de pessoas.
    participant_names: set[str] = set()
    try:
        roster = (
            db.table("project_roster")
            .select("full_name, name_aliases")
            .eq("project_id", project_id)
            .eq("is_active", True)
            .execute().data or []
        )
        for r in roster:
            if r.get("full_name"):
                participant_names.add(r["full_name"].lower().strip())
            for alias in (r.get("name_aliases") or []):
                if alias:
                    participant_names.add(alias.lower().strip())
    except Exception:
        pass

    return {
        "entities": entities,
        "processes": processes,
        "facts": facts,
        "contradictions": contradictions,
        "participant_names": participant_names,
    }


# ── Graph builder (pyvis) ──────────────────────────────────────────────────────

def _render_legend(type_color: dict[str, str]) -> None:
    """Renders a color legend as styled badges above the graph."""
    # Dark colors get white text; light colors get dark text
    _light = {"#fde047", "#fbbf24", "#4ade80", "#86efac", "#22d3ee", "#e2e8f0"}
    badges = []
    for etype in sorted(type_color):
        color = type_color[etype]
        label = etype.replace("_", " ").title()
        shape = _TYPE_SHAPE.get(etype, "●")
        shape_icon = {"dot": "●", "diamond": "◆", "square": "■", "triangle": "▲",
                      "hexagon": "⬡", "star": "★", "triangleDown": "▼",
                      "ellipse": "⬭"}.get(shape, "●")
        txt = "#0a0f1a" if color in _light else "#ffffff"
        badges.append(
            f'<span style="background:{color};color:{txt};padding:3px 10px;'
            f'border-radius:12px;margin:2px 3px;font-size:12px;display:inline-block;'
            f'font-family:Segoe UI,system-ui,sans-serif">'
            f'{shape_icon} {label}</span>'
        )
    # Processo KH badge
    badges.append(
        f'<span style="background:{_PROC_COLOR};color:#0a0f1a;padding:3px 10px;'
        f'border-radius:12px;margin:2px 3px;font-size:12px;display:inline-block;'
        f'font-family:Segoe UI,system-ui,sans-serif">'
        f'■ Processo (KH)</span>'
    )
    st.markdown(
        '<div style="margin-bottom:6px">' + "".join(badges) + "</div>",
        unsafe_allow_html=True,
    )


def _build_pyvis_graph(
    data: dict, max_nodes: int, show_ep_edges: bool,
    show_processes: bool, entity_types: list[str],
    min_occurrence: int = 1, graph_height: int = 720,
    show_entity_edges: bool = False, min_shared_meetings: int = 2,
    physics_enabled: bool = True, show_contradictions: bool = True,
) -> tuple[str, dict[str, str]]:
    """Build a pyvis network. Returns (html_string, type_color_map)."""
    from pyvis.network import Network

    entities = data["entities"]
    processes = data["processes"] if show_processes else []

    if entity_types:
        entities = [e for e in entities if e.get("entity_type", "ACTOR") in entity_types]
    if min_occurrence > 1:
        entities = [e for e in entities if (e.get("occurrence_count") or 1) >= min_occurrence]
    entities = entities[:max_nodes]

    entity_ids = {e["id"] for e in entities}
    participant_names: set[str] = data.get("participant_names") or set()
    contradictions = data.get("contradictions") or []

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
        all_aliases = e.get("aliases") or []
        size  = max(12, min(40, 12 + count * 2.5))
        color = type_color.get(etype, _PALETTE[0])
        shape = _TYPE_SHAPE.get(etype, "dot")
        # Plain text tooltip — vis-network sanitizes HTML in newer versions
        is_part = etype in {"PERSON", "ACTOR"} and _is_participant(e, participant_names)
        role_label = "Participante confirmado" if is_part else etype.replace("_", " ").title()
        meta = e.get("metadata") or {}
        meta_desc = (meta.get("description") or "").strip()
        tooltip = (
            f"{name}\n"
            f"Tipo: {role_label}\n"
            f"Ocorrências: {count}"
            + (f"\nAliases: {', '.join(all_aliases)}" if all_aliases else "")
            + (f"\n{meta_desc}" if meta_desc else "")
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
        desc  = (proc.get("description") or "").strip()
        tooltip = (
            f"{pname}\n"
            f"Tipo: Processo (KH)\n"
            f"Status: {proc.get('status', '—')}\n"
            f"Versões: {proc.get('version_count', 1)}"
            + (f"\n\n{desc}" if desc else "")
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
                    etype = e.get("entity_type", "")
                    if etype in {"PERSON", "ACTOR"}:
                        verb = "Participou de" if _is_participant(e, participant_names) else "Foi mencionado em"
                    else:
                        verb = _EP_VERB.get(etype, _EP_VERB_DEFAULT)
                    net.add_edge(
                        eid, pid,
                        title=f"{verb} {n} {reuniao} onde este processo foi discutido",
                        color={"color": "#475569", "highlight": "#94a3b8", "hover": "#94a3b8"},
                        width=max(1.0, 1.0 + n * 0.4),
                    )

    # ── Arestas entidade → entidade (co-ocorrência opcional) ──────────────────
    _people_types = {"PERSON", "ACTOR", "ROLE"}
    entity_list = list(entities)
    if show_entity_edges and len(entity_list) > 1:
        for i, ea in enumerate(entity_list):
            for eb in entity_list[i + 1:]:
                shared = entity_meeting_map.get(ea["id"], set()) & entity_meeting_map.get(eb["id"], set())
                if len(shared) >= min_shared_meetings:
                    n = len(shared)
                    reuniao = "reunião" if n == 1 else "reuniões"
                    ta = ea.get("entity_type", "")
                    tb = eb.get("entity_type", "")
                    ea_part = ta in _people_types and _is_participant(ea, participant_names)
                    eb_part = tb in _people_types and _is_participant(eb, participant_names)
                    if ea_part and eb_part:
                        ee_title = f"Participaram juntos em {n} {reuniao}"
                    elif ea_part or eb_part:
                        ee_title = f"Co-ocorreram em {n} {reuniao}"
                    elif ta in _people_types and tb in _people_types:
                        ee_title = f"Foram mencionados juntos em {n} {reuniao}"
                    else:
                        ee_title = f"Foram mencionados juntos em {n} {reuniao}"
                    net.add_edge(
                        ea["id"], eb["id"],
                        title=ee_title,
                        color={"color": "#334155", "highlight": "#64748b", "hover": "#64748b"},
                        width=1.0,
                        dashes=True,
                    )

    # ── Arestas de contradição (vermelhas tracejadas) ─────────────────────────
    # kh_contradictions liga reuniões (não entidades). Para representar no grafo,
    # invertemos o entity_meeting_map e escolhemos a entidade mais representativa
    # (maior occurrence_count) de cada lado da contradição.
    if show_contradictions and contradictions:
        # ── Mapa meeting → entidades (usa TODA a lista pré-filtro) ────────────
        _all_ents = data["entities"]
        _full_memap: dict[str, list[dict]] = {}
        for _e in _all_ents:
            _mtgs: set[str] = set(_e.get("meeting_ids") or [])
            for _col in ("first_seen_meeting_id", "last_seen_meeting_id"):
                _v = _e.get(_col)
                if _v:
                    _mtgs.add(_v)
            for _mid in _mtgs:
                _full_memap.setdefault(_mid, []).append(_e)
        for _mid in _full_memap:
            _full_memap[_mid].sort(
                key=lambda x: x.get("occurrence_count") or 1, reverse=True
            )

        # ── Cores por severidade ──────────────────────────────────────────────
        _sev_color = {
            "critical": "#7f1d1d",
            "high":     "#dc2626",
            "medium":   "#ef4444",
            "low":      "#f87171",
        }

        for _ci, c in enumerate(contradictions):
            mid_a    = c.get("meeting_a_id")
            mid_b    = c.get("meeting_b_id")
            severity = (c.get("severity") or "medium").lower()
            desc     = (c.get("description") or "Contradição detectada")[:200]
            rel      = c.get("relation_type") or ""
            cnode_id = f"_contra_{c['id']}"
            node_color = _sev_color.get(severity, "#ef4444")

            tooltip = (
                f"Contradição ({severity})"
                + (f"\nRelação: {rel}" if rel else "")
                + f"\n\n{desc}"
            )

            # ── Nó de contradição — sempre adicionado ─────────────────────────
            net.add_node(
                cnode_id,
                label="⚠",
                title=tooltip,
                color={
                    "background": node_color,
                    "border": "#450a0a",
                    "highlight": {"background": node_color, "border": "#ffffff"},
                    "hover":     {"background": node_color, "border": "#ffffff"},
                },
                size=20,
                shape="star",
                font={"color": "#ffffff", "size": 14, "bold": True,
                      "face": "Segoe UI, system-ui"},
            )
            entity_ids.add(cnode_id)

            # ── Arestas para até 2 entidades de cada reunião ──────────────────
            for _mid in (mid_a, mid_b):
                if not _mid:
                    continue
                _ents_side = _full_memap.get(_mid, [])
                _connected = 0
                for _e in _ents_side:
                    if _connected >= 2:
                        break
                    _eid = _e["id"]
                    # Adiciona o nó de entidade se ainda não estiver no grafo
                    if _eid not in entity_ids:
                        _etype = _e.get("entity_type", "ACTOR")
                        _count = _e.get("occurrence_count") or 1
                        _name  = _e.get("canonical_name", "?")
                        _color = type_color.get(_etype, _PALETTE[0])
                        _is_p  = (_etype in {"PERSON", "ACTOR"}
                                  and _is_participant(_e, participant_names))
                        _rlbl  = ("Participante confirmado" if _is_p
                                  else _etype.replace("_", " ").title())
                        net.add_node(
                            _eid, label=_name,
                            title=(f"{_name}\nTipo: {_rlbl}\n"
                                   f"Ocorrências: {_count}\n(incluído por contradição)"),
                            color={
                                "background": _color, "border": "#0a0f1a",
                                "highlight": {"background": _color, "border": "#ffffff"},
                                "hover":     {"background": _color, "border": "#ffffff"},
                            },
                            size=max(10, min(28, 10 + _count * 2)),
                            shape=_TYPE_SHAPE.get(_etype, "dot"),
                            font={"color": "#ffffff", "size": 11,
                                  "face": "Segoe UI, system-ui"},
                        )
                        entity_ids.add(_eid)
                    net.add_edge(
                        _eid, cnode_id,
                        title=f"Envolvido na contradição\nSeveridade: {severity}",
                        color={"color": node_color,
                               "highlight": "#fca5a5", "hover": "#fca5a5"},
                        width=1.5,
                        dashes=True,
                    )
                    _connected += 1

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

    html = net.generate_html(local=False)

    # ── CSS: tooltip whitespace + toolbar styles ───────────────────────────────
    html = html.replace(
        "</style>",
        ".vis-tooltip{white-space:pre-line!important;"
        "font-family:'Segoe UI',system-ui,sans-serif!important;"
        "font-size:13px!important;line-height:1.6!important;"
        "max-width:440px!important;max-height:none!important;"
        "overflow:visible!important;word-break:break-word!important;"
        "box-shadow:0 4px 16px rgba(0,0,0,.6)!important;"
        "border-radius:8px!important;padding:10px 14px!important;}"
        "#graph-toolbar{display:flex;gap:5px;padding:8px 10px;"
        "background:#1e293b;border-bottom:1px solid #334155;"
        "flex-wrap:wrap;align-items:center;font-family:'Segoe UI',system-ui,sans-serif;}"
        ".tb-btn{background:#334155;color:#f1f5f9;border:1px solid #475569;"
        "border-radius:6px;padding:5px 11px;font-size:12px;cursor:pointer;"
        "white-space:nowrap;transition:background .15s;}"
        ".tb-btn:hover{background:#475569;}"
        "#btnClearFocus{display:none;background:#1d4ed8;border-color:#1e40af;}"
        "#btnClearFocus:hover{background:#2563eb;}"
        ".tb-sep{width:1px;background:#475569;height:22px;margin:0 3px;flex-shrink:0;}"
        "#tb-status{font-size:11px;color:#94a3b8;margin-left:6px;flex:1;}"
        "#tb-hint{font-size:10px;color:#64748b;margin-left:auto;}"
        "</style>",
        1,
    )

    # ── Toolbar HTML — injetado antes do container do grafo ───────────────────
    _phys_init = "true" if physics_enabled else "false"
    toolbar_div = (
        '<div id="graph-toolbar">'
        '<button id="btnPhysics" class="tb-btn" onclick="togglePhysics()">⏸ Pausar</button>'
        '<div class="tb-sep"></div>'
        '<button class="tb-btn" onclick="zoomIn()" title="Zoom in">＋</button>'
        '<button class="tb-btn" onclick="zoomOut()" title="Zoom out">－</button>'
        '<button class="tb-btn" onclick="fitGraph()" title="Ajustar ao ecrã">⊡ Fit</button>'
        '<div class="tb-sep"></div>'
        '<button class="tb-btn" onclick="saveImg()" title="Salvar como PNG">💾 Imagem</button>'
        '<button class="tb-btn" onclick="openNewTab()" title="Abrir em nova aba">⛶ Nova aba</button>'
        '<div class="tb-sep"></div>'
        '<button id="btnClearFocus" class="tb-btn" onclick="clearFocus()" title="Limpar foco e restaurar todas as cores">✕ Limpar foco</button>'
        '<span id="tb-status"></span>'
        '<span id="tb-hint">Clique em um nó para focar</span>'
        '</div>'
    )
    html = html.replace('<div id="mynetwork"', toolbar_div + '<div id="mynetwork"', 1)

    # ── JS — injetado antes de </body> para que `network` já esteja definido ──
    toolbar_js = f"""
<script>
var _physicsOn = {_phys_init};

// ── Focus mode state ──────────────────────────────────────────────────────────
var _focusMode   = false;
var _focusedNode = null;
var _savedNodes  = {{}};   // nodeId -> {{color, font}}
var _savedEdges  = {{}};   // edgeId -> {{color}}

// Cores usadas para elementos fora do foco
var _DIM_NODE = {{
    background: '#0d1520',
    border:     '#1a2535',
    highlight:  {{background: '#0d1520', border: '#1e2d42'}},
    hover:      {{background: '#0d1520', border: '#1e2d42'}}
}};
var _DIM_FONT  = {{color: '#1e293b'}};
var _DIM_EDGE  = {{color: 'rgba(15,23,42,0.12)', highlight: 'rgba(15,23,42,0.12)', hover: 'rgba(15,23,42,0.12)'}};

function _saveOriginals() {{
    if (Object.keys(_savedNodes).length > 0) return;
    network.body.data.nodes.get().forEach(function(n) {{
        _savedNodes[n.id] = {{
            color: JSON.parse(JSON.stringify(n.color || {{}})),
            font:  JSON.parse(JSON.stringify(n.font  || {{}}))
        }};
    }});
    network.body.data.edges.get().forEach(function(e) {{
        _savedEdges[e.id] = {{
            color: JSON.parse(JSON.stringify(e.color || {{}}))
        }};
    }});
}}

function focusNode(nodeId) {{
    _saveOriginals();
    _focusMode   = true;
    _focusedNode = nodeId;

    var connNodes = new Set(network.getConnectedNodes(nodeId));
    connNodes.add(nodeId);
    var connEdges = new Set(network.getConnectedEdges(nodeId));

    // 1. Dim todos os nós fora do foco (zIndex baixo) e destaca os conectados
    var dimUpdates = [];
    var focusIds   = [];
    network.body.data.nodes.get().forEach(function(n) {{
        if (connNodes.has(n.id)) {{
            focusIds.push(n.id);
        }} else {{
            dimUpdates.push({{id: n.id, color: _DIM_NODE, font: _DIM_FONT, zIndex: -1}});
        }}
    }});
    if (dimUpdates.length) network.body.data.nodes.update(dimUpdates);

    // 2. Traz nós em foco para frente: salva posições → remove → reinicia com zIndex alto
    //    (no canvas do vis.js, nós inseridos por último são desenhados por cima)
    var focusPositions = network.getPositions(focusIds);
    var focusData = focusIds.map(function(nid) {{
        var s = _savedNodes[nid] || {{}};
        var n = network.body.data.nodes.get(nid);
        return Object.assign({{}}, n, {{color: s.color, font: s.font, zIndex: 10}});
    }});
    network.body.data.nodes.remove(focusIds);
    network.body.data.nodes.add(focusData);
    // Restaura posições (remove+add reseta x/y para 0)
    focusIds.forEach(function(nid) {{
        var pos = focusPositions[nid];
        if (pos) network.moveNode(nid, pos.x, pos.y);
    }});

    // 3. Arestas: destaca as conectadas, esmaesce as demais
    var edgeUpdates = network.body.data.edges.get().map(function(e) {{
        if (connEdges.has(e.id)) {{
            var s = _savedEdges[e.id] || {{}};
            return {{id: e.id, color: s.color}};
        }}
        return {{id: e.id, color: _DIM_EDGE}};
    }});
    network.body.data.edges.update(edgeUpdates);

    // UI feedback
    var label = (network.body.data.nodes.get(nodeId) || {{}}).label || nodeId;
    var nConn  = connNodes.size - 1;
    document.getElementById('tb-status').textContent =
        '🔍 ' + label + ' — ' + nConn + ' conex' + (nConn === 1 ? 'ão' : 'ões');
    document.getElementById('tb-hint').style.display = 'none';
    document.getElementById('btnClearFocus').style.display = '';
}}

function clearFocus() {{
    if (!_focusMode) return;
    _focusMode   = false;
    _focusedNode = null;

    // Restaura todos os nós (cores + zIndex original = 0)
    var nodeUpdates = network.body.data.nodes.get().map(function(n) {{
        var s = _savedNodes[n.id] || {{}};
        return {{id: n.id, color: s.color, font: s.font, zIndex: 0}};
    }});
    network.body.data.nodes.update(nodeUpdates);

    // Restaura todas as arestas
    var edgeUpdates = network.body.data.edges.get().map(function(e) {{
        var s = _savedEdges[e.id] || {{}};
        return {{id: e.id, color: s.color}};
    }});
    network.body.data.edges.update(edgeUpdates);

    document.getElementById('tb-status').textContent = '';
    document.getElementById('tb-hint').style.display = '';
    document.getElementById('btnClearFocus').style.display = 'none';
}}

// ── Click handler ─────────────────────────────────────────────────────────────
network.on('click', function(params) {{
    if (params.nodes.length > 0) {{
        var nid = params.nodes[0];
        if (_focusMode && _focusedNode === nid) {{
            clearFocus();        // segundo clique no mesmo nó → limpa foco
        }} else {{
            focusNode(nid);      // primeiro clique → ativa foco
        }}
    }} else if (params.edges.length === 0) {{
        clearFocus();            // clique em área vazia → limpa foco
    }}
}});

// ── Physics controls ──────────────────────────────────────────────────────────
function _setPhysicsBtn() {{
    var btn = document.getElementById('btnPhysics');
    if (_physicsOn) {{
        btn.innerHTML = '⏸ Pausar';
        btn.style.background = '';
        btn.style.borderColor = '';
    }} else {{
        btn.innerHTML = '▶ Retomar';
        btn.style.background = '#16a34a';
        btn.style.borderColor = '#15803d';
    }}
}}

function togglePhysics() {{
    _physicsOn = !_physicsOn;
    network.setOptions({{physics: {{enabled: _physicsOn}}}});
    if (!_physicsOn) network.stopSimulation();
    _setPhysicsBtn();
}}

function zoomIn() {{
    network.moveTo({{
        scale: network.getScale() * 1.3,
        animation: {{duration: 200, easingFunction: 'easeInOutQuad'}}
    }});
}}

function zoomOut() {{
    network.moveTo({{
        scale: network.getScale() / 1.3,
        animation: {{duration: 200, easingFunction: 'easeInOutQuad'}}
    }});
}}

function fitGraph() {{
    network.fit({{animation: {{duration: 500, easingFunction: 'easeInOutQuad'}}}});
}}

function saveImg() {{
    try {{
        var src = network.getCanvas();
        var dst = document.createElement('canvas');
        dst.width  = src.width;
        dst.height = src.height;
        var ctx = dst.getContext('2d');
        ctx.fillStyle = '#0d1b2a';
        ctx.fillRect(0, 0, dst.width, dst.height);
        ctx.drawImage(src, 0, 0);
        var link = document.createElement('a');
        link.href = dst.toDataURL('image/png');
        link.download = 'grafo_conhecimento.png';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }} catch(e) {{
        alert('Nao foi possivel salvar: ' + e.message);
    }}
}}

function openNewTab() {{
    try {{
        var blob = new Blob(
            ['<!DOCTYPE html>' + document.documentElement.outerHTML],
            {{type: 'text/html;charset=utf-8'}}
        );
        var url = URL.createObjectURL(blob);
        window.open(url, '_blank');
    }} catch(e) {{
        alert('Permita pop-ups para esta pagina e tente novamente.');
    }}
}}

// Auto-estacionar após estabilização + pré-salvar cores originais
network.on('stabilizationIterationsDone', function() {{
    _saveOriginals();
    if (_physicsOn) {{
        _physicsOn = false;
        network.stopSimulation();
        _setPhysicsBtn();
        var s = document.getElementById('tb-status');
        s.textContent = '✓ Estabilizado';
        setTimeout(function() {{
            if (!_focusMode) s.textContent = '';
        }}, 2500);
    }}
}});
</script>
"""
    html = html.replace("</body>", toolbar_js + "</body>", 1)

    return html, type_color




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

**Modo foco:** clique em qualquer no para destacar apenas ele e suas conexoes diretas —
os demais elementos ficam esmaecidos. Clique novamente no mesmo no, em area vazia, ou em
**✕ Limpar foco** na barra de ferramentas para restaurar o grafo completo.
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
    show_contradictions = st.toggle(
        "Arestas de contradicao", value=True, key="kg_contras",
        help="Exibe arestas vermelhas tracejadas entre entidades de reunioes com contradicoes detectadas.",
    )
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
    if st.button("🔄 Recarregar dados", key="kg_refresh", use_container_width=True,
                 help="Limpa o cache e recarrega do Supabase. Use após apagar ou fundir entidades."):
        _load_graph_data.clear()
        st.rerun()

# ── Main graph ────────────────────────────────────────────────────────────────
tab_graph, tab_table, tab_facts, tab_export = st.tabs(
    ["🕸️ Grafo", "📋 Entidades", "🔗 Fatos", "⬇️ Exportar"]
)

with tab_graph:
    if not selected_types:
        st.warning("Selecione pelo menos um tipo de entidade no painel lateral.")
    else:
        try:
            html_graph, type_color = _build_pyvis_graph(
                data, max_nodes, show_ep_edges, show_processes, selected_types,
                min_occurrence=min_occurrence, graph_height=graph_height,
                show_entity_edges=show_entity_edges, min_shared_meetings=min_shared,
                physics_enabled=physics_enabled, show_contradictions=show_contradictions,
            )
            _render_legend(type_color)
            if show_contradictions and contradictions:
                st.markdown(
                    '<span style="background:#ef4444;color:#fff;padding:3px 10px;'
                    'border-radius:12px;margin:2px 3px;font-size:12px;'
                    'font-family:Segoe UI,system-ui,sans-serif">'
                    '— Contradição detectada</span>',
                    unsafe_allow_html=True,
                )
            components.html(html_graph, height=graph_height + 80, scrolling=False)
        except ImportError:
            st.error(
                "A biblioteca **pyvis** nao esta instalada. "
                "Execute `pip install pyvis==0.3.2` e reinicie o servidor."
            )

        if contradictions and not show_contradictions:
            st.info(
                f"**{len(contradictions)} contradicao(oes)** detectada(s) — "
                "ative 'Arestas de contradicao' no painel lateral para visualizar no grafo."
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
