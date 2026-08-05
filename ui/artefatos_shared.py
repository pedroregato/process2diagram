# ui/artefatos_shared.py
# ─────────────────────────────────────────────────────────────────────────────
# Código compartilhado pelas 6 páginas da seção "Artefatos" (PC208):
# pages/Artefatos.py (Visão Geral) + ArtefatosRequisitos/Modelagem/Reunioes/
# Debates/Qualidade.py. Não é uma página — não é registrado em app.py.
#
# Os loaders @st.cache_data mantêm os nomes com "_" originais de quando viviam
# em pages/Artefatos.py (PC208 apenas os moveu, não renomeou) — importados
# explicitamente por nome em cada página nova, sem risco de precisar reescrever
# call sites já existentes (`_load_x.clear()`, `_load_x(pid)`, etc.).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st

from core.project_store import (
    list_meetings, list_requirements_light,
    list_requirement_versions, list_requirement_versions_by_project,
    list_contradictions,
    list_sbvr_terms, list_sbvr_rules,
    list_bpmn_processes, list_bpmn_versions, bpmn_tables_exist,
    list_dmn_by_project, list_argumentation_by_project,
    list_communication_noise_by_project,
    get_asset_metadata_map,
    list_provocations_by_project,
)
from ui.components.promote_asset import render_promote_button

try:
    from modules.document_store import list_documents
except ImportError:
    def list_documents(project_id, **_):  # type: ignore
        return []

# ── Loaders cacheados (TTLs calibrados pelo ritmo de mudança dos dados) ───────
# meetings/contradictions: 120s (podem mudar após pipeline)
# requirements/SBVR/BPMN/docs: 300s (mudam raramente)
# bpmn_tables_exist: 3600s (estrutura permanente)
# DMN/IBIS/Ruídos: carregados sob demanda via session_state (JSONs pesados)

@st.cache_data(ttl=120, show_spinner=False)
def _load_meetings(pid):           return list_meetings(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_requirements(pid):       return list_requirements_light(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_req_versions(req_id):    return list_requirement_versions(req_id)

@st.cache_data(ttl=120, show_spinner=False)
def _load_req_versions_all(pid):   return list_requirement_versions_by_project(pid)

@st.cache_data(ttl=120, show_spinner=False)
def _load_contradictions(pid):     return list_contradictions(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_sbvr_terms(pid):         return list_sbvr_terms(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_sbvr_rules(pid):         return list_sbvr_rules(pid)

@st.cache_data(ttl=3600, show_spinner=False)
def _bpmn_tables_exist_cached() -> bool:
    return bpmn_tables_exist()

@st.cache_data(ttl=300, show_spinner=False)
def _load_bpmn_procs(pid):
    return list_bpmn_processes(pid) if _bpmn_tables_exist_cached() else []

@st.cache_data(ttl=300, show_spinner=False)
def _load_bpmn_versions(pid):      return list_bpmn_versions(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_dmn(pid):                return list_dmn_by_project(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_argumentation(pid):      return list_argumentation_by_project(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_documents(pid):          return list_documents(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_noise(pid):              return list_communication_noise_by_project(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_asset_meta_map(pid):     return get_asset_metadata_map(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_provocations(pid):       return list_provocations_by_project(pid)


# ── Chaves de session_state para carregamento sob demanda ────────────────────
# Mesmo formato usado desde antes do PC208 — DMN/IBIS/Ruídos são carregados na
# 1ª visita à página correspondente e ficam em cache de sessão entre reruns.
def dmn_session_key(project_id: str) -> str:   return f"_art_dmn_{project_id}"
def ibis_session_key(project_id: str) -> str:  return f"_art_ibis_{project_id}"
def noise_session_key(project_id: str) -> str: return f"_art_noise_{project_id}"


# ── Helpers com closure sobre dados carregados pela própria página ───────────
# Mantidos como factories (em vez de aceitar os dados como parâmetro extra em
# toda chamada) para que o corpo de cada aba, movido praticamente byte-a-byte
# de pages/Artefatos.py, continue chamando meet_label(mid) / doc_label(id) /
# _promote_widget(tipo, id, titulo) exatamente como antes — sem precisar tocar
# em cada call site espalhado pelas abas.

def make_meet_label(meet_map: dict):
    def meet_label(mid: str | None) -> str:
        if not mid or mid not in meet_map:
            return "—"
        m = meet_map[mid]
        dt = m.get("meeting_date") or ""
        return f"Reunião {m.get('meeting_number', '?')} — {m.get('title', '')} ({dt})"
    return meet_label


def make_doc_label(doc_map: dict):
    def doc_label(doc_id: str | None) -> str:
        if not doc_id or doc_id not in doc_map:
            return "—"
        return doc_map[doc_id].get("title", "Documento")
    return doc_label


def _origin_badge(origin: str | None) -> str:
    """Retorna HTML de badge para a origem do artefato."""
    if origin == "documento":
        return '<span class="badge badge-documento">📄 Documento</span>'
    return '<span class="badge badge-transcricao">🎙️ Transcrição</span>'


def make_promote_widget(project_id: str, asset_meta_map: dict):
    def _promote_widget(artifact_type: str, artifact_id: str, title: str) -> None:
        """Wrapper fino de render_promote_button() já resolvendo já-promovido/
        created_by e o rerun com invalidação de cache pós-promoção
        (melhorias/promocao-ativos-negocio.md)."""
        already = (artifact_type, artifact_id) in asset_meta_map
        if render_promote_button(
            project_id, artifact_type, artifact_id,
            title=title, key_suffix=artifact_id, already_promoted=already,
            created_by=st.session_state.get("_usuario_login", ""),
        ):
            _load_asset_meta_map.clear()
            st.rerun()
    return _promote_widget


# ── CSS compartilhado (badges, cards de contradição, dots de versão) ─────────
def inject_artefatos_css() -> None:
    st.markdown("""
    <style>
    .req-card {
        border: 1px solid #1e3a55; border-radius: 8px;
        padding: 1rem 1.2rem; margin-bottom: .6rem;
        background: #0F2040;
    }
    .req-number { font-family: monospace; font-weight: 700; font-size: 1rem; }
    .badge {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: .72rem; font-weight: 600; letter-spacing: .04em;
    }
    .badge-backlog      { background:#1e293b; color:#94a3b8; }
    .badge-active       { background:#0d4f2e; color:#4ade80; }
    .badge-approved     { background:#064e3b; color:#6ee7b7; }
    .badge-in-progress  { background:#1e3a6e; color:#93c5fd; }
    .badge-implemented  { background:#134e4a; color:#5eead4; }
    .badge-revised      { background:#4a3000; color:#fbbf24; }
    .badge-contradicted { background:#4a0d0d; color:#f87171; }
    .badge-deprecated   { background:#2a2a2a; color:#9ca3af; }
    .badge-rejected     { background:#3b0f1f; color:#fda4af; }
    .badge-new          { background:#0d2f4f; color:#60a5fa; }
    .badge-confirmed    { background:#0d3f1f; color:#34d399; }
    .contradiction-box {
        border-left: 4px solid #f87171; padding: .8rem 1rem;
        background: rgba(248,113,113,.06); border-radius: 0 8px 8px 0;
        margin-bottom: .5rem;
    }
    .version-dot {
        display: inline-block; width: 10px; height: 10px;
        border-radius: 50%; margin-right: 6px;
    }
    .ibis-badge-decided    { background:#0d4f2e; color:#4ade80; }
    .ibis-badge-deferred   { background:#4a3000; color:#fbbf24; }
    .ibis-badge-unresolved { background:#4a0d0d; color:#f87171; }
    .badge-transcricao { background:#1e3a6e; color:#93c5fd; }
    .badge-documento   { background:#0d3f2e; color:#6ee7b7; }
    </style>
    """, unsafe_allow_html=True)


# ── Faixa de navegação lateral dentro da seção Artefatos ─────────────────────
ARTEFATOS_NAV_PAGES: list[tuple[str, str]] = [
    ("pages/Artefatos.py",           "🗂️ Visão Geral"),
    ("pages/ArtefatosRequisitos.py", "📝 Requisitos"),
    ("pages/ArtefatosModelagem.py",  "📐 Modelagem Formal"),
    ("pages/ArtefatosReunioes.py",   "🗓️ Reuniões"),
    ("pages/ArtefatosDebates.py",    "🗺️ Debates (IBIS)"),
    ("pages/ArtefatosQualidade.py",  "🔎 Qualidade & Sinais"),
]


def render_artefatos_nav(active: str) -> None:
    """Faixa de st.page_link() no topo de cada página da seção Artefatos,
    linkando para as outras 5 — navegação lateral dentro do assunto sem
    depender só da sidebar (PC208)."""
    cols = st.columns(len(ARTEFATOS_NAV_PAGES))
    for col, (path, label) in zip(cols, ARTEFATOS_NAV_PAGES):
        with col:
            st.page_link(path, label=label, use_container_width=True, disabled=(path == active))
    st.markdown("")
