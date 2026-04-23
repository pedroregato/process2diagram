# pages/BpmnEditor.py
# ─────────────────────────────────────────────────────────────────────────────
# Editor visual de diagramas BPMN com registro de versões no banco de dados.
#
# Fluxo de edição:
#   1. Seleciona projeto → processo → versão a editar
#   2. O diagrama abre no editor bpmn-js (Modeler completo)
#   3. Usuário edita visualmente os elementos
#   4. Clica "📋 Exportar XML" dentro do editor → XML aparece na área de texto
#   5. Copia o XML e cola no campo "XML editado" abaixo do editor
#   6. Adiciona notas da versão e clica "💾 Salvar nova versão"
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import streamlit.components.v1 as components

from ui.auth_gate import apply_auth_gate
from core.project_store import (
    list_projects,
    list_bpmn_processes,
    list_bpmn_versions,
    save_bpmn_new_version,
    bpmn_tables_exist,
)
from modules.bpmn_editor import editor_from_xml
from modules.bpmn_viewer import preview_from_xml

apply_auth_gate()

# ── Feedback persistido entre reruns ──────────────────────────────────────────
if "_bpme_ok" in st.session_state:
    st.success(st.session_state.pop("_bpme_ok"))
if "_bpme_err" in st.session_state:
    st.error(st.session_state.pop("_bpme_err"))

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.title("✏️ Editor BPMN")
st.caption("Edite diagramas BPMN visualmente e registre novas versões no banco de dados.")

# ── Guarda de pré-requisitos ──────────────────────────────────────────────────
if not bpmn_tables_exist():
    st.error(
        "As tabelas `bpmn_processes` e `bpmn_versions` não foram encontradas no banco de dados. "
        "Execute o script de setup do Supabase antes de usar esta funcionalidade."
    )
    st.stop()

# ── Seletores de processo ─────────────────────────────────────────────────────
projects = list_projects()
if not projects:
    st.info("Nenhum projeto encontrado. Processe pelo menos uma transcrição antes de usar o editor.")
    st.stop()

col_proj, col_proc = st.columns(2)

with col_proj:
    proj_opts = {p["name"]: p["id"] for p in projects}
    proj_name = st.selectbox("Projeto", list(proj_opts.keys()), key="bpme_project")
    project_id = proj_opts[proj_name]

processes = list_bpmn_processes(project_id)

with col_proc:
    if not processes:
        st.info("Nenhum processo BPMN registrado para este projeto.")
        st.stop()
    proc_opts = {f"{p['name']} ({p.get('version_count', 0)} versão(ões))": p["id"] for p in processes}
    proc_label = st.selectbox("Processo BPMN", list(proc_opts.keys()), key="bpme_process")
    process_id = proc_opts[proc_label]

# ── Versões do processo ───────────────────────────────────────────────────────
versions = list_bpmn_versions(process_id)
if not versions:
    st.warning("Nenhuma versão BPMN registrada para este processo.")
    st.stop()

st.markdown("---")
st.subheader("📋 Versões registradas")

# Monta tabela resumida
ver_rows = []
for v in versions:
    mtg = v.get("meetings") or {}
    ver_rows.append({
        "Versão":  v.get("version", "—"),
        "Atual":   "✅" if v.get("is_current") else "",
        "Reunião": f"#{mtg.get('meeting_number', '?')} — {mtg.get('title', '')}" if mtg else "—",
        "Notas":   v.get("change_notes") or "",
        "ID":      v["id"],
    })

st.dataframe(ver_rows, use_container_width=True, hide_index=True,
             column_config={"ID": st.column_config.TextColumn(disabled=True)})

# ── Seletor de versão para editar ─────────────────────────────────────────────
st.markdown("#### Selecionar versão para editar")
ver_opts_labels = [
    f"v{v.get('version', '?')}{' (atual)' if v.get('is_current') else ''} — {(v.get('meetings') or {}).get('title', 'sem reunião')}"
    for v in versions
]
ver_sel_idx = st.selectbox(
    "Versão base",
    range(len(versions)),
    format_func=lambda i: ver_opts_labels[i],
    key="bpme_version_sel",
)
selected_version = versions[ver_sel_idx]
base_xml = selected_version.get("bpmn_xml") or ""

meeting_id_for_version = selected_version.get("meeting_id") or ""

if not base_xml.strip():
    st.error("Esta versão não possui XML BPMN armazenado.")
    st.stop()

# ── Editor ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🎨 Editor visual")
st.info(
    "**Como usar:**  \n"
    "1. Edite os elementos do diagrama usando a paleta à esquerda  \n"
    "2. Clique **📋 Exportar XML** na barra do editor  \n"
    "3. Selecione todo o texto (Ctrl+A) e copie (Ctrl+C)  \n"
    "4. Cole no campo **XML editado** abaixo  \n"
    "5. Preencha as notas e salve"
)

editor_html = editor_from_xml(base_xml, height=620)
components.html(editor_html, height=620 + 260, scrolling=False)

# ── Salvar nova versão ────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("💾 Salvar nova versão")

user_login = st.session_state.get("_usuario_login", "")

# ── Passo 1: Capturar XML do clipboard ───────────────────────────────────────
st.markdown(
    "**Passo 1:** No editor acima, clique **📋 Exportar XML** para copiar o diagrama. "
    "Depois clique o botão abaixo para capturá-lo diretamente."
)

col_cap, col_status = st.columns([2, 3])
with col_cap:
    if st.button("📥 Capturar XML do Editor", use_container_width=True, key="bpme_capture_btn"):
        st.session_state["_bpme_capture"] = True

# ── Leitura do clipboard via st_javascript ────────────────────────────────────
if st.session_state.get("_bpme_capture"):
    from streamlit_javascript import st_javascript
    result = st_javascript(
        "await (async () => { try { return await navigator.clipboard.readText(); }"
        " catch(e) { return '__CLIPBOARD_ERROR__: ' + e.message; } })()"
    )
    # result == 0 → JS ainda resolvendo (st_javascript retorna 0 enquanto aguarda)
    if result != 0:
        st.session_state.pop("_bpme_capture", None)
        if isinstance(result, str) and result.startswith("__CLIPBOARD_ERROR__"):
            st.session_state["_bpme_err"] = (
                "❌ Não foi possível ler a área de transferência. "
                "Verifique as permissões do browser ou use o campo manual abaixo."
            )
            st.rerun()
        elif isinstance(result, str) and ("<bpmn" in result or "<?xml" in result):
            st.session_state["_bpme_captured_xml"] = result.strip()
            st.rerun()
        else:
            st.session_state["_bpme_err"] = (
                "⚠️ Clipboard não contém XML BPMN válido. "
                "Certifique-se de clicar '📋 Exportar XML' no editor antes de capturar."
            )
            st.rerun()
    else:
        with col_status:
            st.info("⏳ Lendo área de transferência…")

# ── Passo 2: XML capturado — mostrar e confirmar ──────────────────────────────
captured_xml = st.session_state.get("_bpme_captured_xml", "")

if captured_xml:
    orig_lines = len(base_xml.splitlines())
    new_lines  = len(captured_xml.splitlines())
    delta      = new_lines - orig_lines
    sign       = "+" if delta >= 0 else ""

    if captured_xml.strip() == base_xml.strip():
        st.warning("⚠️ O XML capturado é idêntico à versão base — nenhuma alteração detectada.")
    else:
        st.success(
            f"✅ XML capturado — {new_lines} linhas "
            f"(base: {orig_lines}, diferença: {sign}{delta})"
        )

    # Validação estrutural rápida
    import xml.etree.ElementTree as ET
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
    except ET.ParseError as parse_err:
        st.error(f"❌ XML inválido — não será possível salvar: {parse_err}")
        captured_xml = ""   # bloqueia o save

# ── Passo 3: Notas e salvar ───────────────────────────────────────────────────
if captured_xml:
    st.markdown("**Passo 2:** Adicione notas e salve como nova versão.")
    col_notes, col_actions = st.columns([3, 2])

    with col_notes:
        change_notes = st.text_area(
            "Notas da versão",
            height=90,
            key="bpme_notes",
            placeholder="Ex.: Ajuste nas lanes, correção de gateway XOR...",
        )
        st.caption(f"Registrado por: **{user_login}**")

    with col_actions:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button(
            "💾 Salvar nova versão",
            type="primary",
            use_container_width=True,
            key="bpme_save_btn",
            disabled=(captured_xml.strip() == base_xml.strip()),
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
                    "✅ Nova versão salva com sucesso! "
                    "A versão anterior foi marcada como não-atual."
                )
                st.session_state.pop("_bpme_captured_xml", None)
                st.session_state.pop("bpme_show_preview", None)
                st.session_state["bpme_notes"] = ""
                st.rerun()
            else:
                st.session_state["_bpme_err"] = (
                    "❌ Falha ao salvar. Verifique a conexão com o banco de dados."
                )
                st.rerun()

        if st.button("👁️ Prévia", use_container_width=True, key="bpme_preview_btn"):
            st.session_state["bpme_show_preview"] = not st.session_state.get("bpme_show_preview", False)

        if st.button("🗑️ Descartar XML capturado", use_container_width=True, key="bpme_discard_btn"):
            st.session_state.pop("_bpme_captured_xml", None)
            st.rerun()

# ── Prévia do XML capturado ───────────────────────────────────────────────────
if st.session_state.get("bpme_show_preview") and captured_xml:
    st.markdown("##### Prévia do XML capturado")
    try:
        preview_html = preview_from_xml(captured_xml)
        components.html(preview_html, height=500, scrolling=False)
    except Exception as e:
        st.error(f"Erro ao gerar prévia: {e}")

# ── Fallback: entrada manual por cole/colar ───────────────────────────────────
with st.expander("⌨️ Alternativa: colar XML manualmente", expanded=False):
    st.caption(
        "Use esta opção se o botão de captura não funcionar no seu browser "
        "(alguns ambientes bloqueiam a leitura do clipboard)."
    )
    manual_xml = st.text_area(
        "Cole o XML aqui",
        height=160,
        key="bpme_manual_xml",
        placeholder="<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<bpmn:definitions ...>",
    )
    manual_notes = st.text_area(
        "Notas (manual)",
        height=60,
        key="bpme_manual_notes",
        placeholder="Ajuste manual...",
    )
    if st.button("💾 Salvar (manual)", key="bpme_save_manual", disabled=not manual_xml.strip()):
        ok = save_bpmn_new_version(
            process_id=process_id,
            meeting_id=meeting_id_for_version,
            project_id=project_id,
            bpmn_xml=manual_xml.strip(),
            mermaid_code="",
            version_notes=manual_notes.strip(),
            created_by=user_login,
        )
        if ok:
            st.session_state["_bpme_ok"] = "✅ Nova versão salva com sucesso (entrada manual)."
            st.session_state["bpme_manual_xml"]   = ""
            st.session_state["bpme_manual_notes"] = ""
            st.rerun()
        else:
            st.session_state["_bpme_err"] = "❌ Falha ao salvar. Verifique a conexão com o banco de dados."
            st.rerun()

# ── Histórico — XML bruto da versão base ─────────────────────────────────────
with st.expander("📄 XML da versão selecionada (referência)", expanded=False):
    st.code(base_xml, language="xml")
