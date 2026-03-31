## --- Process2Diagram v3.5 — Multi-Agent Architecture
## --- Pedro Gentil

import sys
from pathlib import Path
import json

import streamlit as st
import streamlit.components.v1 as components

# ── Fix import path ───────────────────────────────────────────────────────────
root_dir = Path(__file__).parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# ── Core imports ──────────────────────────────────────────────────────────────
from modules.session_security import render_api_key_gate, get_session_llm_client
from modules.config import AVAILABLE_PROVIDERS
from modules.ingest import load_transcript

# ── v3 Multi-agent imports ────────────────────────────────────────────────────
from core.knowledge_hub import KnowledgeHub, BPMNModel
from agents.orchestrator import Orchestrator
from agents.agent_bpmn import AgentBPMN
from agents.agent_validator import AgentValidator
from agents.agent_minutes import AgentMinutes
from agents.agent_mermaid import generate_mermaid

# ── BPMN viewer (presentation layer — separated from generator) ──────────────
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block

#  ── Outras funcionalidades ──────────────
from modules.bpmn_diagnostics import render_bpmn_diagnostics


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Process2Diagram",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
  h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; letter-spacing: -0.03em; }
  .main-title { font-family: 'IBM Plex Mono', monospace; font-size: 2.4rem; font-weight: 600;
    letter-spacing: -0.04em; color: #0f172a; margin-bottom: 0; }
  .sub-title { font-family: 'IBM Plex Sans', sans-serif; font-weight: 300; color: #64748b;
    margin-top: 0.2rem; font-size: 1rem; }
  .stTextArea textarea { font-family: 'IBM Plex Mono', monospace !important; font-size: 0.85rem; }
  .block-container { padding-top: 2rem; }
  div[data-testid="stSidebar"] { background: #0f172a; color: #e2e8f0; }
  div[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  div[data-testid="stSidebar"] .stSelectbox label,
  div[data-testid="stSidebar"] .stTextInput label { color: #94a3b8 !important; }
  .agent-badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600; margin: 2px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _grade_from_score(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "E"


def _render_highlighted_transcript(clean_text: str, inconsistencies: list, key: str) -> None:
    """
    Render preprocessed transcript as HTML with inconsistencies highlighted in yellow.
    Hovering over a highlight shows the LLM's reason as a tooltip.
    Falls back to plain text if no inconsistencies.
    """
    import html as _html

    if not inconsistencies:
        components.html(
            f"<div style='height:400px;overflow-y:scroll;font-family:monospace;"
            f"font-size:0.8rem;line-height:1.7;padding:10px 12px;"
            f"border:1px solid #e2e8f0;border-radius:6px;background:#fafafa'>"
            f"{_html.escape(clean_text).replace(chr(10), '<br>')}</div>",
            height=420,
        )
        return

    # Collect (start, end, reason) for every inconsistency found in clean_text
    spans: list[tuple[int, int, str]] = []
    for inc in inconsistencies:
        # The preprocessor may have wrapped the text as "[? ...]" — try both
        candidates = [
            f"[? {inc.text.rstrip('.')}]",
            f"[? {inc.text}]",
            inc.text,
        ]
        for candidate in candidates:
            idx = clean_text.find(candidate)
            if idx >= 0:
                spans.append((idx, idx + len(candidate), inc.reason))
                break

    # Sort; drop overlapping spans (keep first)
    spans.sort(key=lambda s: s[0])
    merged: list[tuple[int, int, str]] = []
    for s in spans:
        if merged and s[0] < merged[-1][1]:
            continue  # skip overlap
        merged.append(s)

    # Build HTML segment by segment
    parts: list[str] = []
    prev = 0
    for start, end, reason in merged:
        parts.append(_html.escape(clean_text[prev:start]))
        tooltip = _html.escape(reason[:120])
        highlighted = _html.escape(clean_text[start:end])
        parts.append(
            f'<mark title="{tooltip}" style="background:#fef08a;border-radius:3px;'
            f'cursor:help;padding:1px 0">{highlighted}</mark>'
        )
        prev = end
    parts.append(_html.escape(clean_text[prev:]))

    body = "".join(parts).replace("\n", "<br>")
    components.html(
        f"<div style='height:400px;overflow-y:scroll;font-family:monospace;"
        f"font-size:0.8rem;line-height:1.7;padding:10px 12px;"
        f"border:1px solid #e2e8f0;border-radius:6px;background:#fafafa'>"
        f"{body}</div>",
        height=420,
    )


def _copy_button(text: str, key: str, label: str = "📋 Copiar") -> None:
    """Render a clipboard copy button via JavaScript (works in Streamlit Cloud iframes)."""
    import json as _json
    safe = _json.dumps(text)   # properly escapes quotes, backslashes, newlines
    components.html(
        f"""
        <button id="cbtn_{key}"
          onclick="(function(){{
            var el = document.createElement('textarea');
            el.value = {safe};
            el.style.position='fixed'; el.style.opacity='0';
            document.body.appendChild(el);
            el.focus(); el.select();
            try {{ document.execCommand('copy'); }} catch(e) {{}}
            document.body.removeChild(el);
            var b = document.getElementById('cbtn_{key}');
            b.textContent = '✅ Copiado!';
            setTimeout(function(){{ b.textContent = '{label}'; }}, 2000);
          }})()"
          style="padding:5px 14px;border:1px solid #cbd5e1;border-radius:6px;
                 background:#f8fafc;cursor:pointer;font-size:0.82rem;
                 font-family:sans-serif;margin-top:4px">
          {label}
        </button>
        """,
        height=42,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    import subprocess as _sp
    _commit = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True).stdout.strip() or "unknown"
    st.markdown("## ⚙️ Process2Diagram")
    st.markdown(f"*v3.5 — Multi-Agent* `{_commit}`")
    st.markdown("---")

    st.markdown("### 🤖 LLM Provider")
    provider_names = list(AVAILABLE_PROVIDERS.keys())
    selected_provider = st.selectbox(
        "Choose provider",
        provider_names,
        index=provider_names.index("DeepSeek") if "DeepSeek" in provider_names else 0,
        key="selected_provider",
    )

    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    st.markdown(f"**Model:** `{provider_cfg['default_model']}`")
    st.markdown(f"**Cost:** {provider_cfg['cost_hint']}")
    st.markdown("---")

    render_api_key_gate(selected_provider, provider_cfg)

    st.markdown("---")
    st.markdown("### ⚙️ Options")
    output_language = st.selectbox("Output language", ["Auto-detect", "Portuguese (BR)", "English"])

    st.markdown("### 🤖 Active Agents")
    run_quality = st.checkbox("Agente Qualidade da Transcrição", value=True)
    run_bpmn = st.checkbox("Agente BPMN", value=True)

    # ── Multi-run BPMN validator ───────────────────────────────────────────
    n_bpmn_runs = 1
    bpmn_weights = {"granularity": 5, "task_type": 5, "gateways": 5}
    if run_bpmn:
        n_bpmn_runs = st.select_slider(
            "Rodadas BPMN", options=[1, 3, 5], value=1,
            help="Executa o Agente BPMN N vezes e seleciona o melhor resultado.",
        )
        if n_bpmn_runs > 1:
            st.caption("Pesos para seleção do melhor resultado (0 = ignorar):")
            bpmn_weights = {
                "granularity": st.slider("Granularidade", 0, 10, 5, key="w_gran"),
                "task_type":   st.slider("Task type",     0, 10, 5, key="w_type"),
                "gateways":    st.slider("Gateways",      0, 10, 8, key="w_gw"),
            }

    run_minutes = st.checkbox("Agente Ata de Reunião", value=True)
    run_requirements = st.checkbox("Agente Requisitos", value=True)

    show_raw_json = st.checkbox("Show raw JSON", value=False)
    st.markdown("---")
    st.caption("Keys live **only in your session**.\nNever stored or logged.")

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">Process2Diagram</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-title">Turn meeting transcripts into process diagrams — automatically.</p>',
    unsafe_allow_html=True,
)

if not get_session_llm_client(selected_provider):
    st.info(f"👈 Enter your **{selected_provider}** API key in the sidebar to start.")
    st.stop()

# ── Input ─────────────────────────────────────────────────────────────────────
st.markdown("### 📋 Transcript")
col_input, col_help = st.columns([3, 1])

with col_input:
    transcript_text = st.text_area(
        "Paste your meeting transcript here",
        height=220,
        placeholder=(
            "Exemplo:\n"
            "1) A equipe faz upload da foto.\n"
            "2) O sistema detecta rostos.\n"
            "3) O especialista identifica as pessoas.\n"
            "4) O sistema gera a legenda SVG.\n"
            "5) Os arquivos são enviados ao ECM."
        ),
        key="transcript_input",
    )

with col_help:
    st.markdown("**Dicas:**")
    st.markdown("""
- Passos numerados funcionam melhor
- Mencione atores: *"a equipe"*, *"o sistema"*
- Palavras de decisão: *"se"*, *"quando"*, *"caso contrário"*
- Regras: *"deve"*, *"não pode"*, *"obrigatório"*
    """)

uploaded_file = st.file_uploader("Ou envie um arquivo .txt", type=["txt"])
if uploaded_file:
    transcript_text = load_transcript(uploaded_file)
    st.success(f"Carregado: {uploaded_file.name}")

# ── Diagnóstico — sempre visível, fora do bloco generate_btn ─────────────────
with st.expander("🛠️ Diagnóstico — Arquivos de Skill em Runtime", expanded=False):
    st.caption(
        "Mostra o conteúdo **real** dos arquivos lidos pelo servidor. "
        "Use para confirmar que os skills estão corretos no repositório após cada commit."
    )

    import re as _re

    _SKILL_FILES = {
        "skill_bpmn.md": "skills/skill_bpmn.md",
        "skill_minutes.md": "skills/skill_minutes.md",
    }
    _SUSPICIOUS = [
        "cache_resource", "reruns", "KnowledgeHub", "st.cache",
        "Bearer", "base_agent", "ensure_utf8", "NLPChunker",
    ]

    for fname, rel_path in _SKILL_FILES.items():
        p = Path(rel_path)
        st.markdown(f"#### 📄 `{rel_path}`")

        if not p.exists():
            st.error(
                f"❌ **Arquivo não encontrado:** `{rel_path}`  \n"
                "O agente está rodando **sem system prompt**. "
                "Verifique o nome e o caminho no repositório."
            )
            continue

        raw = p.read_text(encoding="utf-8", errors="replace")
        found_suspicious = [t for t in _SUSPICIOUS if t in raw]
        has_placeholder = "{output_language}" in raw
        non_ascii = sum(1 for c in raw if ord(c) > 127)
        json_hits = len(_re.findall(r"json", raw, _re.IGNORECASE))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tamanho", f"{len(raw):,} chars")
        c2.metric("Não-ASCII", non_ascii)
        c3.metric("Ocorr. 'json'", json_hits)
        c4.metric("{output_language}", "✅" if has_placeholder else "❌")

        if found_suspicious:
            st.error(
                "⚠️ **Conteúdo suspeito** — tokens encontrados: "
                + ", ".join(f"`{t}`" for t in found_suspicious)
                + "  \nEste arquivo pode estar corrompido com texto de chat. "
                  "Substitua pelo arquivo correto no repositório."
            )
        else:
            st.success("✅ Arquivo íntegro — nenhum conteúdo suspeito detectado.")

        if not has_placeholder:
            st.warning("⚠️ Placeholder `{output_language}` ausente — instrução de idioma não será injetada.")

        st.code(raw, language="markdown")
        st.download_button(
            label=f"⬇️ Baixar {fname}",
            data=raw.encode("utf-8"),
            file_name=fname,
            mime="text/markdown",
            key=f"diag_dl_{fname}",
        )
        st.divider()

# ── Pré-processamento independente ────────────────────────────────────────────
preprocess_btn = st.button("🧹 Pré-processar Transcrição", use_container_width=True)

if preprocess_btn:
    if not transcript_text or len(transcript_text.strip()) < 20:
        st.warning("Cole ou carregue uma transcrição antes de pré-processar.")
    else:
        from modules.transcript_preprocessor import preprocess as _preprocess
        pp_result = _preprocess(transcript_text)
        st.session_state["pp_result"] = pp_result
        st.session_state["curated_clean"] = pp_result.clean_text
        # Invalidate any previous pipeline result when transcript changes
        st.session_state.pop("hub", None)

# Mostra painel de curadoria se preprocessamento já foi feito
if "pp_result" in st.session_state:
    pp = st.session_state["pp_result"]
    st.markdown("#### 🧹 Curadoria da Transcrição")
    stats_html = (
        f"<div style='display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.6rem'>"
        f"<span style='background:#f1f5f9;padding:3px 10px;border-radius:20px;font-size:0.82rem'>"
        f"<b>{pp.fillers_removed}</b> fillers removidos</span>"
        f"<span style='background:#fef9c3;padding:3px 10px;border-radius:20px;font-size:0.82rem'>"
        f"<b>{pp.artifact_turns}</b> artefatos <code>[?]</code></span>"
        f"<span style='background:#f1f5f9;padding:3px 10px;border-radius:20px;font-size:0.82rem'>"
        f"<b>{pp.repetitions_collapsed}</b> repetições colapsadas</span>"
        f"</div>"
    )
    st.markdown(stats_html, unsafe_allow_html=True)
    for issue in pp.metadata_issues:
        st.warning(f"⚠️ {issue}")
    st.caption(
        "Revise o texto pré-processado abaixo. Itens marcados com `[?]` são candidatos a artefatos — "
        "delete ou corrija conforme necessário. O botão **Processar Transcrição** usará este texto."
    )
    col_orig, col_clean = st.columns(2)
    with col_orig:
        st.markdown("**Original (somente leitura)**")
        st.text_area("orig", value=transcript_text, height=300,
                     disabled=True, label_visibility="collapsed", key="ta_orig_pre")
        _copy_button(transcript_text, key="pre_orig")
    with col_clean:
        st.markdown("**Pré-processada — edite aqui**")
        curated = st.text_area("clean", value=st.session_state.get("curated_clean", pp.clean_text),
                               height=300, label_visibility="collapsed", key="ta_curated")
        st.session_state["curated_clean"] = curated
        _copy_button(curated, key="pre_clean")

st.divider()

# ── Generate ──────────────────────────────────────────────────────────────────
generate_btn = st.button("⚡ Iniciar Agentes Selecionados", type="primary", use_container_width=True)

if generate_btn:
    st.session_state.pop("hub", None)   # limpa resultado anterior
    if not transcript_text or len(transcript_text.strip()) < 20:
        st.warning("Por favor, forneça uma transcrição com pelo menos algumas linhas.")
        st.stop()

    if not run_quality and not run_bpmn and not run_minutes and not run_requirements:
        st.warning("Selecione ao menos um agente na barra lateral.")
        st.stop()

    client_info = get_session_llm_client(selected_provider)

    # ── Initialize Knowledge Hub ──────────────────────────────────────────────
    hub = KnowledgeHub.new()
    # If user pre-processed and curated the text, inject it so the orchestrator
    # skips the preprocessing step and uses the curated version directly.
    curated_clean = st.session_state.get("curated_clean", "").strip()
    if curated_clean and curated_clean != transcript_text.strip():
        hub.set_transcript(transcript_text, clean=curated_clean)
    else:
        hub.set_transcript(transcript_text)
    hub.meta.llm_provider = selected_provider

    # ── Progress display ──────────────────────────────────────────────────────
    progress_placeholder = st.empty()
    agent_status: dict[str, str] = {}

    def update_progress(step_name: str, status: str):
        agent_status[step_name] = status
        icons = {"running": "⏳", "done": "✅", "error": "❌"}
        lines = []
        for name, st_val in agent_status.items():
            icon = next((v for k, v in icons.items() if k in st_val), "🔵")
            lines.append(f"{icon} **{name}** — {st_val}")
        progress_placeholder.markdown("  \n".join(lines))

    # ── Run Orchestrator ──────────────────────────────────────────────────────
    try:
        orchestrator = Orchestrator(
            client_info=client_info,
            provider_cfg=provider_cfg,
            progress_callback=update_progress,
        )

        # ── Multi-run BPMN: run N times, score, pick best ─────────────────
        if run_bpmn and n_bpmn_runs > 1:
            import copy as _copy
            _validator = AgentValidator()
            _agent_bpmn = AgentBPMN(client_info, provider_cfg)

            # Step 0-1 via orchestrator (Quality + NLP), skip BPMN for now
            hub = orchestrator.run(
                hub,
                output_language=output_language,
                run_quality=run_quality,
                run_bpmn=False,          # BPMN handled below
                run_minutes=False,
                run_requirements=False,
            )

            candidates = []
            for i in range(n_bpmn_runs):
                update_progress("Agente BPMN", f"rodada {i + 1}/{n_bpmn_runs}…")
                hub_c = _copy.copy(hub)
                hub_c.bpmn = BPMNModel()
                hub_c = _agent_bpmn.run(hub_c, output_language)
                score = _validator.score(hub_c.bpmn, hub_c.transcript_clean, bpmn_weights)
                score.run_index = i + 1
                candidates.append((score, hub_c.bpmn))

            best_score, best_bpmn = max(candidates, key=lambda x: x[0].weighted)
            hub.bpmn = best_bpmn
            hub.validation.bpmn_score = best_score
            hub.validation.bpmn_candidates = [c[0] for c in candidates]
            hub.validation.n_bpmn_runs = n_bpmn_runs
            hub.validation.ready = True
            hub.bump()
            update_progress(
                "Agente BPMN",
                f"done — rodada {best_score.run_index}/{n_bpmn_runs} selecionada "
                f"(score {best_score.weighted:.1f}/10)",
            )

            # Finish pipeline (Minutes + Requirements) with the winning hub
            hub = orchestrator.run(
                hub,
                output_language=output_language,
                run_quality=False,
                run_bpmn=False,
                run_minutes=run_minutes,
                run_requirements=run_requirements,
            )

        else:
            # Single-run (default) — original flow unchanged
            hub = orchestrator.run(
                hub,
                output_language=output_language,
                run_quality=run_quality,
                run_bpmn=run_bpmn,
                run_minutes=run_minutes,
                run_requirements=run_requirements,
            )

    except Exception as e:
        st.error(f"Erro no pipeline: {e}")
        st.stop()

    progress_placeholder.empty()

    # ── Salva no session_state ANTES de qualquer UI ───────────────────────────
    # Garante que o hub sobrevive ao rerun causado por st.download_button
    st.session_state["hub"] = hub

# ── Renderização — FORA do if generate_btn, recupera do session_state ─────────
# Desta forma, download buttons, tab switches e outros widgets não apagam a UI
hub = st.session_state.get("hub")
if hub is not None:
    hub = KnowledgeHub.migrate(hub)
    # Belt-and-suspenders: ensure transcript_quality always exists regardless of cache
    if not hasattr(hub, 'transcript_quality'):
        from core.knowledge_hub import TranscriptQualityModel
        hub.transcript_quality = TranscriptQualityModel()

    # ── Metrics banner ────────────────────────────────────────────────────────
    col_a, col_b, col_c, col_d = st.columns(4)
    if hub.bpmn.ready:
        col_a.metric("Etapas BPMN", len(hub.bpmn.steps))
        col_b.metric("Conexões", len(hub.bpmn.edges))
        actors = list(set(s.actor for s in hub.bpmn.steps if s.actor))
        col_c.metric("Atores", len(actors))
    if hub.minutes.ready:
        col_d.metric("Action Items", len(hub.minutes.action_items))

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs_to_show = []
    if hub.transcript_quality.ready:
        tabs_to_show += ["🔬 Qualidade da Transcrição"]
    if hub.bpmn.ready:
        tabs_to_show += ["📐 BPMN 2.0", "📊 Mermaid"]
        if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
            tabs_to_show += ["🏆 Validação BPMN"]

    if hub.bpmn.lanes:
        st.markdown(f"**Swimlanes:** {', '.join(f'`{l}`' for l in hub.bpmn.lanes)}")

    render_bpmn_diagnostics(hub.bpmn)  # ← adicionar esta linha

    if hub.minutes.ready:
        tabs_to_show += ["📋 Ata de Reunião"]
    if hub.requirements.ready:
        tabs_to_show += ["📝 Requisitos"]
    tabs_to_show += ["🔧 Exportar", "🔍 Knowledge Hub"]

    tabs = st.tabs(tabs_to_show)
    tab_idx = 0

    # ── Tab: Qualidade da Transcrição ─────────────────────────────────────────
    if hub.transcript_quality.ready:
        with tabs[tab_idx]:
            tq = hub.transcript_quality
            pp = getattr(hub, 'preprocessing', None)

            grade_colors = {"A": "#16a34a", "B": "#65a30d", "C": "#ca8a04",
                            "D": "#ea580c", "E": "#dc2626"}
            grade_color = grade_colors.get(tq.grade, "#64748b")

            # ── Top-line score + grade ─────────────────────────────────────
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:1.5rem;margin-bottom:1rem'>"
                f"<div style='font-size:3.5rem;font-weight:700;color:{grade_color};font-family:monospace'>"
                f"{tq.grade}</div>"
                f"<div><div style='font-size:1.8rem;font-weight:600;color:{grade_color}'>"
                f"{tq.overall_score:.1f} / 100</div>"
                f"<div style='color:#64748b;font-size:0.9rem'>Nota ponderada da transcrição (ASR bruta)</div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )

            # ── Criteria breakdown ─────────────────────────────────────────
            st.markdown("### Critérios de Avaliação")
            for c in tq.criteria:
                weight_pct = int(c.weight * 100)
                with st.expander(
                    f"**{c.criterion}** — {c.score}/100  (peso {weight_pct}%)",
                    expanded=False,
                ):
                    st.progress(c.score / 100)
                    st.markdown(c.justification)

            st.divider()

            if tq.overall_summary:
                st.markdown("### Análise Geral")
                st.markdown(tq.overall_summary)

            if tq.recommendation:
                grade_levels = {"A": "success", "B": "success", "C": "warning",
                                "D": "warning", "E": "error"}
                level = grade_levels.get(tq.grade, "info")
                if level == "success":
                    st.success(f"**Recomendação:** {tq.recommendation}")
                elif level == "warning":
                    st.warning(f"**Recomendação:** {tq.recommendation}")
                else:
                    st.error(f"**Recomendação:** {tq.recommendation}")

            # ── Inconsistências detectadas pela IA ────────────────────────
            if tq.inconsistencies:
                st.divider()
                st.markdown(f"### 🔍 Inconsistências Detectadas pela IA  `{len(tq.inconsistencies)}`")
                st.caption(
                    "Trechos identificados como prováveis ruídos de fundo, "
                    "captura de microfone aberto ou artefatos de ASR. "
                    "Use como guia para a curadoria manual."
                )
                for inc in tq.inconsistencies:
                    label = f"**{inc.speaker}** `{inc.timestamp}` — *{inc.text}*"
                    with st.expander(label, expanded=False):
                        st.markdown(f"**Motivo:** {inc.reason}")

            # ── Pré-processamento ──────────────────────────────────────────
            if pp and pp.ready:
                st.divider()
                st.markdown("### 🧹 Pré-processamento Automático")

                # Stats pills
                stats_html = (
                    f"<div style='display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.8rem'>"
                    f"<span style='background:#f1f5f9;padding:4px 12px;border-radius:20px;"
                    f"font-size:0.82rem'><b>{pp.fillers_removed}</b> fillers removidos</span>"
                    f"<span style='background:#fef9c3;padding:4px 12px;border-radius:20px;"
                    f"font-size:0.82rem'><b>{pp.artifact_turns}</b> turnos de artefato sinalizados "
                    f"<code>[?]</code></span>"
                    f"<span style='background:#f1f5f9;padding:4px 12px;border-radius:20px;"
                    f"font-size:0.82rem'><b>{pp.repetitions_collapsed}</b> repetições colapsadas</span>"
                    f"</div>"
                )
                st.markdown(stats_html, unsafe_allow_html=True)

                if pp.metadata_issues:
                    for issue in pp.metadata_issues:
                        st.warning(f"⚠️ {issue}")

                st.caption(
                    "Turnos marcados com `[?]` são candidatos a artefatos de ASR. "
                    "Revise antes de usar o texto pré-processado como fonte definitiva."
                )

                # Before / After
                col_raw, col_clean = st.columns(2)
                with col_raw:
                    st.markdown("**Transcrição original (ASR bruta)**")
                    st.text_area(
                        label="raw",
                        value=hub.transcript_raw,
                        height=400,
                        disabled=True,
                        label_visibility="collapsed",
                        key="ta_raw",
                    )
                    _copy_button(hub.transcript_raw, key="tab_orig")
                    st.download_button(
                        "⬇ Baixar original (.txt)",
                        data=hub.transcript_raw,
                        file_name="transcricao_original.txt",
                        mime="text/plain",
                        key="dl_raw",
                    )
                with col_clean:
                    st.markdown("**Transcrição pré-processada** *(inconsistências em* 🟡 *— passe o mouse)*")
                    _render_highlighted_transcript(
                        hub.transcript_clean,
                        tq.inconsistencies,
                        key=f"hl_{tab_idx}",
                    )
                    _copy_button(hub.transcript_clean, key="tab_clean")
                    st.download_button(
                        "⬇ Baixar pré-processada (.txt)",
                        data=hub.transcript_clean,
                        file_name="transcricao_preprocessada.txt",
                        mime="text/plain",
                        key="dl_clean",
                    )

        tab_idx += 1

    # ── Tab: BPMN 2.0 (bpmn-js viewer) ───────────────────────────────────────
    if hub.bpmn.ready:
        with tabs[tab_idx]:
            st.caption(
                "Renderizado com [bpmn-js](https://bpmn.io) · Arraste para mover · Scroll para zoom · Tecla 0 para ajustar tela"
            )

            if hub.bpmn.bpmn_xml:
                bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
                components.html(bpmn_html, height=1000, scrolling=False)

                if hub.bpmn.lanes:
                    st.markdown(f"**Swimlanes:** {', '.join(f'`{l}`' for l in hub.bpmn.lanes)}")
            else:
                st.info("ℹ️ Viewer bpmn-js indisponível — exibindo Mermaid como fallback.")
                render_mermaid_block(hub.bpmn.mermaid, show_code=False, key_suffix="bpmn_fallback")

        tab_idx += 1

        # ── Tab: Mermaid ──────────────────────────────────────────────────────
        with tabs[tab_idx]:
            st.caption("Fluxograma Mermaid · ↓/→ alterna direção · Cole em [mermaid.live](https://mermaid.live) para editar.")
            render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="mermaid_tab")

        tab_idx += 1

        # ── Tab: Validação BPMN (multi-run) ──────────────────────────────────
        if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
            with tabs[tab_idx]:
                val = hub.validation
                st.markdown(f"### Seleção entre {val.n_bpmn_runs} rodadas")
                best = val.bpmn_score

                # Ranking table
                rows = []
                for c in sorted(val.bpmn_candidates, key=lambda x: x.weighted, reverse=True):
                    rows.append({
                        "Rodada":        f"{'⭐ ' if c.run_index == best.run_index else ''}{c.run_index}",
                        "Granularidade": f"{c.granularity:.1f}",
                        "Task type":     f"{c.task_type:.1f}",
                        "Gateways":      f"{c.gateways:.1f}",
                        "Score final":   f"{c.weighted:.2f}",
                        "Atividades":    c.n_tasks,
                        "Gateways #":    c.n_gateways,
                    })
                st.dataframe(rows, use_container_width=True)

                st.caption(
                    f"Rodada **{best.run_index}** selecionada · "
                    f"Score {best.weighted:.2f}/10 · "
                    f"{best.n_tasks} atividades · {best.transcript_words} palavras na transcrição"
                )

            tab_idx += 1

    # ── Tab: Ata de Reunião ───────────────────────────────────────────────────
    if hub.minutes.ready:
        with tabs[tab_idx]:
            m = hub.minutes
            st.markdown(f"## {m.title}")
            col1, col2 = st.columns(2)
            col1.markdown(f"**Data:** {m.date or '—'}")
            col2.markdown(f"**Local:** {m.location or '—'}")

            if m.participants:
                st.markdown("**Participantes:**")
                cols = st.columns(min(len(m.participants), 4))
                for i, p in enumerate(m.participants):
                    cols[i % 4].markdown(f"`{p}`")

            if m.agenda:
                st.markdown("### 📌 Pauta")
                for i, item in enumerate(m.agenda, 1):
                    st.markdown(f"{i}. {item}")

            if m.summary:
                st.markdown("### 📝 Resumo")
                for block in m.summary:
                    st.markdown(f"**{block.get('topic', '')}**")
                    st.markdown(block.get("content", ""))

            if m.decisions:
                st.markdown("### ✅ Decisões")
                for d in m.decisions:
                    st.markdown(f"- {d}")

            if m.action_items:
                st.markdown("### 🎯 Action Items")
                prio_colors = {"high": "🔴", "normal": "🟡", "low": "🟢"}
                rows = []
                for ai in m.action_items:
                    prio = prio_colors.get(ai.priority, "⚪")
                    rows.append({
                        "Prioridade": prio,
                        "Por": ai.raised_by or "—",
                        "Tarefa": ai.task,
                        "Responsável": ai.responsible,
                        "Prazo": ai.deadline or "—",
                    })
                st.dataframe(rows, use_container_width=True)

            if m.next_meeting:
                st.info(f"📅 Próxima reunião: **{m.next_meeting}**")

        tab_idx += 1

    # ── Tab: Requisitos ───────────────────────────────────────────────────────
    if hub.requirements.ready:
        with tabs[tab_idx]:
            req = hub.requirements
            type_labels = {
                "ui_field":       "🖥️ Campo de tela",
                "validation":     "✅ Validação",
                "business_rule":  "📋 Regra de negócio",
                "functional":     "⚙️ Funcional",
                "non_functional": "📊 Não-funcional",
            }
            priority_colors = {"high": "🔴", "medium": "🟡", "low": "🟢", "unspecified": "⚪"}

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("Total de Requisitos", len(req.requirements))
            high_count = sum(1 for r in req.requirements if r.priority == "high")
            col_r2.metric("Alta Prioridade 🔴", high_count)
            types_count = len(set(r.type for r in req.requirements))
            col_r3.metric("Tipos distintos", types_count)

            # Filter by type
            selected_type = st.selectbox(
                "Filtrar por tipo",
                ["Todos"] + list(type_labels.values()),
                key="req_type_filter",
            )
            type_reverse = {v: k for k, v in type_labels.items()}

            rows = []
            for r in req.requirements:
                if selected_type != "Todos" and r.type != type_reverse.get(selected_type):
                    continue
                rows.append({
                    "ID": r.id,
                    "Tipo": type_labels.get(r.type, r.type),
                    "Prioridade": priority_colors.get(r.priority, "⚪"),
                    "Título": r.title,
                    "Etapa": r.process_step or "—",
                    "Ator": r.actor or "—",
                })

            if rows:
                st.dataframe(rows, use_container_width=True)

            # Detail expander per requirement
            st.markdown("---")
            st.markdown("### Detalhamento")
            for r in req.requirements:
                if selected_type != "Todos" and r.type != type_reverse.get(selected_type):
                    continue
                with st.expander(f"{r.id} — {r.title}  {priority_colors.get(r.priority, '')}"):
                    st.markdown(f"**Tipo:** {type_labels.get(r.type, r.type)}")
                    st.markdown(f"**Prioridade:** {priority_colors.get(r.priority, '⚪')} {r.priority}")
                    if r.actor:
                        st.markdown(f"**Ator:** {r.actor}")
                    if r.process_step:
                        st.markdown(f"**Etapa do processo:** {r.process_step}")
                    st.markdown(f"**Descrição:** {r.description}")
                    if r.source_quote:
                        speaker_tag = f"**[{r.speaker}]** " if r.speaker else ""
                        st.markdown(f"> {speaker_tag}*\"{r.source_quote}\"*")

            # ── Mind Map ──────────────────────────────────────────────────
            if getattr(req, 'mindmap', ''):
                st.markdown("---")
                st.markdown("### 🗺️ Mind Map dos Requisitos")
                render_mermaid_block(req.mindmap, show_code=True, key_suffix="req_mindmap", height=520)

        tab_idx += 1

    # ── Tab: Exportar ─────────────────────────────────────────────────────────
    with tabs[tab_idx]:
        st.markdown("### ⬇️ Downloads")

        if hub.bpmn.ready:
            st.markdown("**Diagrama BPMN**")
            col1, col2 = st.columns(2)

            with col1:
                if hub.bpmn.bpmn_xml:
                    st.download_button(
                        "⬇️ Diagrama .bpmn",
                        data=hub.bpmn.bpmn_xml,
                        file_name=f"{hub.bpmn.name.replace(' ', '_')}.bpmn",
                        mime="application/xml",
                        use_container_width=True,
                    )

            with col2:
                mermaid_content = generate_mermaid(hub.bpmn)
                st.download_button(
                    "⬇️ Fluxo .mermaid",
                    data=mermaid_content,
                    file_name=f"{hub.bpmn.name.replace(' ', '_')}.mmd",
                    mime="text/plain",
                    use_container_width=True,
                )

            st.markdown("---")

            bpmn_json = json.dumps({
                "name": hub.bpmn.name,
                "steps": [vars(s) for s in hub.bpmn.steps],
                "edges": [vars(e) for e in hub.bpmn.edges],
                "lanes": hub.bpmn.lanes,
            }, ensure_ascii=False, indent=2)

            st.download_button(
                "⬇️ BPMN estruturado .json",
                data=bpmn_json,
                file_name=f"{hub.bpmn.name.replace(' ', '_')}_bpmn.json",
                mime="application/json",
            )

            with st.expander("Como importar o diagrama"):
                st.markdown("""
| Ferramenta | Como importar |
|---|---|
| **Camunda Modeler** | File → Open → selecione o `.bpmn` |
| **Bizagi Modeler** | File → Open → selecione o `.bpmn` |
| **bpmn.io** | Arraste o `.bpmn` para o canvas |
| **Mermaid Live** | Cole o conteúdo do `.mmd` em [mermaid.live](https://mermaid.live) |
""")

        if hub.minutes.ready:
            st.markdown("**Ata de Reunião**")
            md_content = AgentMinutes.to_markdown(hub.minutes)
            st.download_button(
                "⬇️ Ata .md",
                data=md_content,
                file_name="ata_reuniao.md",
                mime="text/markdown",
            )

        if hub.requirements.ready:
            st.markdown("**Requisitos**")
            col_req1, col_req2 = st.columns(2)
            with col_req1:
                st.download_button(
                    "⬇️ Requisitos .md",
                    data=hub.requirements.markdown,
                    file_name=f"{hub.requirements.name.replace(' ', '_')}_requisitos.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col_req2:
                import json as _json
                req_json = _json.dumps(
                    {"name": hub.requirements.name,
                     "requirements": [r.__dict__ for r in hub.requirements.requirements]},
                    ensure_ascii=False, indent=2
                )
                st.download_button(
                    "⬇️ Requisitos .json",
                    data=req_json,
                    file_name=f"{hub.requirements.name.replace(' ', '_')}_requisitos.json",
                    mime="application/json",
                    use_container_width=True,
                )

    tab_idx += 1

    # ── Tab: Knowledge Hub ────────────────────────────────────────────────────
    with tabs[tab_idx]:
        st.markdown("### 🔍 Knowledge Hub — Estado da Sessão")
        col_meta1, col_meta2, col_meta3 = st.columns(3)
        col_meta1.metric("Versão do Hub", hub.version)
        col_meta2.metric("Tokens usados", hub.meta.total_tokens_used)
        col_meta3.metric("Agentes executados", len(hub.meta.agents_run))
        st.markdown(f"**Provider:** `{hub.meta.llm_provider}` — **Model:** `{hub.meta.llm_model}`")
        st.markdown(
            f"**Segmentos NLP:** {len(hub.nlp.segments)} — "
            f"**Atores:** {', '.join(hub.nlp.actors) or '—'} — "
            f"**Idioma:** `{hub.nlp.language_detected}`"
        )

        if show_raw_json:
            st.json(hub.to_dict())

        st.download_button(
            "⬇️ Knowledge Hub .json",
            data=hub.to_json(),
            file_name="knowledge_hub.json",
            mime="application/json",
        )
