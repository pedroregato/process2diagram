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

# ── Área de recebimento do XML editado ───────────────────────────────────────
st.markdown("---")
st.subheader("💾 Salvar nova versão")

col_xml, col_meta = st.columns([3, 1])

with col_xml:
    edited_xml = st.text_area(
        "XML editado (cole aqui o conteúdo exportado do editor acima)",
        value="",
        height=200,
        key="bpme_edited_xml",
        placeholder="<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<bpmn:definitions ...>",
        help="Cole aqui o XML exportado pelo botão '📋 Exportar XML' dentro do editor.",
    )

with col_meta:
    change_notes = st.text_area(
        "Notas da versão",
        height=100,
        key="bpme_notes",
        placeholder="Ex.: Ajuste nas lanes, correção de gateway...",
    )
    user_login = st.session_state.get("_usuario_login", "")
    st.caption(f"Registrado por: **{user_login}**")

# Indicador de diferenças
if edited_xml.strip() and edited_xml.strip() != base_xml.strip():
    orig_lines = len(base_xml.splitlines())
    new_lines  = len(edited_xml.splitlines())
    delta = new_lines - orig_lines
    sign  = "+" if delta >= 0 else ""
    st.caption(
        f"📝 XML modificado detectado — original: {orig_lines} linhas, novo: {new_lines} linhas ({sign}{delta})"
    )
elif edited_xml.strip() == base_xml.strip() and edited_xml.strip():
    st.caption("⚠️ O XML colado é idêntico à versão base — nenhuma alteração detectada.")

# ── Validação prévia opcional ─────────────────────────────────────────────────
if edited_xml.strip() and edited_xml.strip() != base_xml.strip():
    with st.expander("🔍 Validar XML antes de salvar", expanded=False):
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(edited_xml.strip())
            # Basic BPMN checks
            has_process = "<bpmn:process" in edited_xml or "<process " in edited_xml
            has_start   = "startEvent" in edited_xml
            has_end     = "endEvent" in edited_xml
            issues = []
            if not has_process:
                issues.append("⚠️ Nenhum elemento `<bpmn:process>` encontrado.")
            if not has_start:
                issues.append("⚠️ Nenhum `startEvent` encontrado.")
            if not has_end:
                issues.append("⚠️ Nenhum `endEvent` encontrado.")
            if not issues:
                st.success("✅ XML válido e elementos BPMN essenciais presentes.")
            else:
                st.success("✅ XML bem formado.")
                for iss in issues:
                    st.warning(iss)
        except ET.ParseError as e:
            st.error(f"❌ XML inválido: {e}")
        except Exception as e:
            st.warning(f"Não foi possível validar: {e}")

# ── Botão de salvar ───────────────────────────────────────────────────────────
col_btn, col_prev = st.columns([1, 2])

with col_btn:
    save_disabled = not edited_xml.strip()
    if st.button(
        "💾 Salvar nova versão",
        type="primary",
        use_container_width=True,
        disabled=save_disabled,
        key="bpme_save_btn",
    ):
        if not edited_xml.strip():
            st.session_state["_bpme_err"] = "Cole o XML exportado antes de salvar."
            st.rerun()
        else:
            ok = save_bpmn_new_version(
                process_id=process_id,
                meeting_id=meeting_id_for_version,
                project_id=project_id,
                bpmn_xml=edited_xml.strip(),
                mermaid_code="",
                version_notes=change_notes.strip(),
                created_by=user_login,
            )
            if ok:
                st.session_state["_bpme_ok"] = (
                    "✅ Nova versão salva com sucesso! "
                    "A versão anterior foi marcada como não-atual."
                )
                # Limpa os campos de entrada
                st.session_state["bpme_edited_xml"] = ""
                st.session_state["bpme_notes"]       = ""
                st.session_state.pop("bpme_show_preview", None)
                st.rerun()
            else:
                st.session_state["_bpme_err"] = (
                    "❌ Falha ao salvar a versão. Verifique a conexão com o banco de dados."
                )
                st.rerun()

with col_prev:
    if edited_xml.strip():
        if st.button("👁️ Prévia do XML colado", use_container_width=True, key="bpme_preview_btn"):
            st.session_state["bpme_show_preview"] = not st.session_state.get("bpme_show_preview", False)

# ── Prévia do XML editado ─────────────────────────────────────────────────────
if st.session_state.get("bpme_show_preview") and edited_xml.strip():
    st.markdown("##### Prévia do XML editado")
    try:
        preview_html = preview_from_xml(edited_xml.strip())
        components.html(preview_html, height=500, scrolling=False)
    except Exception as e:
        st.error(f"Erro ao gerar prévia: {e}")

# ── Histórico — XML bruto da versão base ─────────────────────────────────────
with st.expander("📄 XML da versão selecionada (referência)", expanded=False):
    st.code(base_xml, language="xml")
