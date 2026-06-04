# pages/BpmnEditor.py
# ─────────────────────────────────────────────────────────────────────────────
# Editor visual de diagramas BPMN com registro de versões no banco de dados.
#
# Fluxo de edição:
#   1. Seleciona projeto → processo → versão a editar
#   2. O diagrama abre no editor bpmn-js (Modeler completo)
#   3. Usuário edita e clica "📋 Exportar XML" na barra do editor
#   4. Copia o XML da área de texto que aparece no editor
#   5. Cola no campo "XML editado" abaixo → modeler re-renderiza com o novo XML
#      (st.session_state é lido ANTES de renderizar o modeler — mesmo rerun)
#   6. Adicione notas e clique "💾 Salvar nova versão"
#
# Chave da solução sem cross-frame hacks:
#   st.session_state["bpme_paste_xml"] já contém o valor colado no início do
#   rerun seguinte à colagem — Python lê antes de renderizar o modeler, portanto
#   _display_xml usa o XML editado na mesma passagem.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import streamlit.components.v1 as components

from ui.auth_gate import apply_auth_gate
from core.project_store import (
    list_bpmn_processes,
    list_bpmn_versions,
    save_bpmn_new_version,
    bpmn_tables_exist,
    load_meeting_as_hub,
)
from ui.project_selector import require_active_project
from modules.bpmn_editor import editor_from_xml
from modules.bpmn_viewer import preview_from_xml

apply_auth_gate()

# ── Feedback persistido entre reruns ──────────────────────────────────────────
if "_bpme_ok" in st.session_state:
    st.success(st.session_state.pop("_bpme_ok"))
if "_bpme_err" in st.session_state:
    st.error(st.session_state.pop("_bpme_err"))

# ── Reset de widgets após salvar (deve ocorrer ANTES de renderizá-los) ────────
if st.session_state.pop("_bpme_reset_fields", False):
    st.session_state["bpme_paste_xml"] = ""
    st.session_state["bpme_notes"]     = ""

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.title("✏️ Editor BPMN")
st.caption("Edite diagramas BPMN visualmente e registre novas versões no banco de dados.")

# ── Guarda de pré-requisitos ──────────────────────────────────────────────────
if not bpmn_tables_exist():
    st.error(
        "As tabelas `bpmn_processes` e `bpmn_versions` não foram encontradas. "
        "Execute o script de setup do Supabase antes de usar esta funcionalidade."
    )
    st.stop()

# ── Contexto de trabalho ativo + seletor de processo ─────────────────────────
project_id, proj_name = require_active_project()
_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {proj_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

processes = list_bpmn_processes(project_id)
col_proc = st.columns(1)[0]
with col_proc:
    if not processes:
        st.info("Nenhum processo BPMN registrado para este projeto.")
        st.stop()
    def _proc_label(p: dict) -> str:
        mtg = p.get("meetings") or {}
        label = f"{p['name']} ({p.get('version_count', 0)} versão(ões))"
        mtg_num = mtg.get("meeting_number")
        if mtg_num:
            label += f" — Reunião #{mtg_num}"
        return label

    proc_opts = {_proc_label(p): p["id"] for p in processes}
    proc_label = st.selectbox("Processo BPMN", list(proc_opts.keys()), key="bpme_process")
    process_id = proc_opts[proc_label]

# ── Versões ───────────────────────────────────────────────────────────────────
versions = list_bpmn_versions(process_id)
if not versions:
    st.warning("Nenhuma versão BPMN registrada para este processo.")
    st.stop()

st.markdown("---")
st.subheader("📋 Versões registradas")
ver_rows = []
for v in versions:
    mtg = v.get("meetings") or {}
    ver_rows.append({
        "Versão":  v.get("version", "—"),
        "Atual":   "✅" if v.get("is_current") else "",
        "Reunião": f"#{mtg.get('meeting_number','?')} — {mtg.get('title','')}" if mtg else "—",
        "Data":    (mtg.get("meeting_date") or "")[:10] if mtg else "—",
        "Notas":   v.get("change_notes") or "",
        "ID":      v["id"],
    })
st.dataframe(ver_rows, use_container_width=True, hide_index=True,
             column_config={"ID": st.column_config.TextColumn(disabled=True)})

ver_opts_labels = [
    f"v{v.get('version','?')}{' (atual)' if v.get('is_current') else ''} — "
    f"#{(v.get('meetings') or {}).get('meeting_number', '?')} · "
    f"{((v.get('meetings') or {}).get('meeting_date') or '')[:10]} · "
    f"{(v.get('meetings') or {}).get('title', 'sem reunião')}"
    for v in versions
]
ver_sel_idx = st.selectbox(
    "Versão base para editar",
    range(len(versions)),
    format_func=lambda i: ver_opts_labels[i],
    key="bpme_version_sel",
)
selected_version = versions[ver_sel_idx]
base_xml         = selected_version.get("bpmn_xml") or ""
meeting_id_for_version = selected_version.get("meeting_id") or ""

if not base_xml.strip():
    st.error("Esta versão não possui XML BPMN armazenado.")
    st.stop()

# ── Reset ao trocar processo/versão ───────────────────────────────────────────
_version_key = f"{process_id}:{selected_version.get('id')}"
if st.session_state.get("_bpme_version_key") != _version_key:
    st.session_state.pop("_bpme_captured_xml", None)
    st.session_state["bpme_paste_xml"]   = ""
    st.session_state["_bpme_version_key"] = _version_key

# ── Reconversão Method & Style v7.0 ──────────────────────────────────────────
with st.expander("🔄 Reconverter com Method & Style v7.0", expanded=False):
    st.markdown(
        "Re-executa o **AgentBPMN** sobre a transcrição desta reunião aplicando as "
        "regras de notação Method & Style v7.0. O XML gerado é carregado no editor "
        "abaixo para revisão — salve apenas quando estiver satisfeito."
    )
    if not meeting_id_for_version:
        st.warning("Esta versão não está vinculada a uma reunião — reconversão indisponível.")
    else:
        if st.button("🔄 Iniciar Reconversão", key="bpme_reconvert_btn"):
            from modules.session_security import get_session_llm_client
            from agents.agent_bpmn import AgentBPMN

            _client_info  = get_session_llm_client(st.session_state.get("selected_provider", ""))
            _provider_cfg = st.session_state.get("provider_cfg") or {}

            if not _client_info:
                st.error("Configure um provedor LLM em **Sistema → Configurações** antes de reconverter.")
            else:
                with st.spinner("Carregando transcrição da reunião..."):
                    _reconv_hub = load_meeting_as_hub(meeting_id_for_version, project_id)

                if not _reconv_hub:
                    st.error("Reunião não encontrada no banco de dados.")
                else:
                    _transcript = (
                        (_reconv_hub.transcript_clean or "") or (_reconv_hub.transcript_raw or "")
                    ).strip()
                    if len(_transcript) < 50:
                        st.error(
                            "Transcrição não disponível ou muito curta. "
                            "Reprocesse pelo Pipeline antes de reconverter."
                        )
                    else:
                        with st.spinner("Reconvertendo com AgentBPMN (Method & Style v7.0)…"):
                            try:
                                _reconv_hub = AgentBPMN(_client_info, _provider_cfg).run(_reconv_hub)
                            except Exception as _exc:
                                st.error(f"Erro na reconversão: {_exc}")
                                _reconv_hub = None

                        if _reconv_hub and getattr(_reconv_hub.bpmn, "ready", False) and _reconv_hub.bpmn.bpmn_xml:
                            st.session_state["_bpme_captured_xml"] = _reconv_hub.bpmn.bpmn_xml
                            _n_steps    = len(_reconv_hub.bpmn.steps)
                            _n_call_act = sum(1 for s in _reconv_hub.bpmn.steps if s.task_type == "callActivity")
                            _n_loops    = sum(1 for s in _reconv_hub.bpmn.steps if s.task_type in ("loopTask", "multiInstanceTask"))
                            _c1, _c2, _c3 = st.columns(3)
                            _c1.metric("Nós nível 1", _n_steps)
                            _c2.metric("callActivities", _n_call_act)
                            _c3.metric("Loop / Multi-instance", _n_loops)
                            if _reconv_hub.bpmn.repair_log:
                                st.caption(f"Reparos automáticos aplicados: {len(_reconv_hub.bpmn.repair_log)}")
                            st.success("✅ XML carregado no editor — revise e salve quando pronto.")
                            st.rerun()
                        else:
                            st.error("O agente não produziu um modelo BPMN válido.")

# ── Lê o XML colado ANTES de renderizar o modeler ────────────────────────────
# st.session_state["bpme_paste_xml"] já tem o valor do widget do rerun anterior.
# Assim _display_xml usa o XML editado na mesma passagem — sem reruns extras.
_pasted = st.session_state.get("bpme_paste_xml", "").strip()
if _pasted and ("<bpmn" in _pasted or "<?xml" in _pasted or "<definitions" in _pasted):
    st.session_state["_bpme_captured_xml"] = _pasted

_display_xml = st.session_state.get("_bpme_captured_xml") or base_xml

# ── Editor visual ─────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🎨 Editor visual")
st.info(
    "**Como usar:**  \n"
    "1. Edite os elementos usando a paleta à esquerda  \n"
    "2. Clique **📋 Exportar XML** na barra do editor — o XML aparece na caixa abaixo do editor  \n"
    "3. Copie todo o texto da caixa (Ctrl+A → Ctrl+C)  \n"
    "4. Cole no campo **XML editado** abaixo — o diagrama é atualizado automaticamente  \n"
    "5. Adicione notas e clique **💾 Salvar nova versão**"
)

editor_html = editor_from_xml(_display_xml, height=620)
components.html(editor_html, height=620 + 260, scrolling=False)

# ── Campo de paste — lido no PRÓXIMO rerun antes do modeler ──────────────────
st.markdown("---")
st.subheader("💾 Salvar nova versão")
user_login = st.session_state.get("_usuario_login", "")

col_paste, col_meta = st.columns([3, 2])

with col_paste:
    st.text_area(
        "📋 XML editado — cole aqui o conteúdo exportado pelo editor acima",
        height=180,
        key="bpme_paste_xml",
        placeholder='<?xml version="1.0" encoding="UTF-8"?>\n<definitions ...',
        help=(
            "Após clicar 'Exportar XML' no editor, selecione tudo na caixa interna "
            "(Ctrl+A) e copie (Ctrl+C). Cole aqui. O modeler acima será atualizado "
            "na próxima interação."
        ),
    )

with col_meta:
    change_notes = st.text_area(
        "Notas da versão",
        height=100,
        key="bpme_notes",
        placeholder="Ex.: Ajuste nas lanes, correção de gateway XOR...",
    )
    st.caption(f"Registrado por: **{user_login}**")

# ── Status do XML colado ───────────────────────────────────────────────────────
captured_xml = st.session_state.get("_bpme_captured_xml", "")

if not captured_xml:
    st.info("⏳ Cole o XML exportado no campo acima para habilitar o salvamento.")
else:
    orig_lines = len(base_xml.splitlines())
    new_lines  = len(captured_xml.splitlines())
    delta      = new_lines - orig_lines
    sign       = "+" if delta >= 0 else ""

    if captured_xml.strip() == base_xml.strip():
        st.warning("⚠️ O XML colado é idêntico à versão base — nenhuma alteração detectada.")
    else:
        st.success(f"✅ XML pronto — {new_lines} linhas (base: {orig_lines}, diff: {sign}{delta})")

    # Validação estrutural rápida
    try:
        ET.fromstring(captured_xml)
        issues = []
        if "<bpmn:process" not in captured_xml and "<process " not in captured_xml:
            issues.append("⚠️ Nenhum `<bpmn:process>` encontrado.")
        if "startEvent" not in captured_xml:
            issues.append("⚠️ Nenhum `startEvent` encontrado.")
        if "endEvent" not in captured_xml:
            issues.append("⚠️ Nenhum `endEvent` encontrado.")
        for iss in issues:
            st.warning(iss)
    except ET.ParseError as e:
        st.error(f"❌ XML inválido: {e}")
        captured_xml = ""

# ── Botões de ação ────────────────────────────────────────────────────────────
col_save, col_preview, col_discard = st.columns([2, 1, 1])

with col_save:
    if st.button(
        "💾 Salvar nova versão",
        type="primary",
        use_container_width=True,
        key="bpme_save_btn",
        disabled=not captured_xml or captured_xml.strip() == base_xml.strip(),
    ):
        ok = save_bpmn_new_version(
            process_id=process_id,
            meeting_id=meeting_id_for_version,
            project_id=project_id,
            bpmn_xml=captured_xml,
            mermaid_code="",
            version_notes=change_notes.strip(),
            created_by=user_login,
        )
        if ok:
            st.session_state["_bpme_ok"] = (
                "✅ Nova versão salva! A versão anterior foi marcada como não-atual."
            )
            st.session_state.pop("_bpme_captured_xml", None)
            st.session_state.pop("bpme_show_preview", None)
            st.session_state["_bpme_reset_fields"] = True
            st.rerun()
        else:
            st.session_state["_bpme_err"] = "❌ Falha ao salvar. Verifique a conexão com o banco."
            st.rerun()

with col_preview:
    if captured_xml and st.button("👁️ Prévia", use_container_width=True, key="bpme_preview_btn"):
        st.session_state["bpme_show_preview"] = not st.session_state.get("bpme_show_preview", False)

with col_discard:
    if captured_xml and st.button("🗑️ Descartar", use_container_width=True, key="bpme_discard_btn"):
        st.session_state.pop("_bpme_captured_xml", None)
        st.session_state["bpme_paste_xml"] = ""
        st.rerun()

# ── Prévia ────────────────────────────────────────────────────────────────────
if st.session_state.get("bpme_show_preview") and captured_xml:
    st.markdown("##### Prévia do XML colado")
    try:
        components.html(preview_from_xml(captured_xml), height=500, scrolling=False)
    except Exception as e:
        st.error(f"Erro ao gerar prévia: {e}")

# ── XML da versão base (referência) ──────────────────────────────────────────
with st.expander("📄 XML da versão selecionada (referência)", expanded=False):
    st.code(base_xml, language="xml")
