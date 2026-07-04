# pages/BpmnStudio.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Studio (PC116) — gera BPMN 2.0 + Mermaid a partir de uma descrição de
# processo em texto livre, independente de uma reunião. Inclui o caminho
# inverso: dado um XML BPMN, gera a descrição textual do processo.
#
# Ver melhorias/bpmn-studio.md para o plano completo.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from datetime import datetime as _dt
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import streamlit.components.v1 as components

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from ui.components.page_header import render_page_header
from modules.session_security import get_session_llm_client
from modules.bpmn_editor import editor_from_xml
from modules.mermaid_renderer import render_mermaid_block
from modules.bpmn_describer import describe_bpmn_from_xml
from agents.agent_bpmn_studio import generate_bpmn_from_description
from core.project_store import (
    bpmn_tables_exist,
    list_bpmn_processes,
    list_meetings,
    save_bpmn_from_hub,
)

apply_auth_gate()

render_page_header(
    "🏗️", "BPMN Studio",
    "Gere BPMN 2.0 + Mermaid a partir de uma descrição de processo em texto livre "
    "— sem depender de uma reunião — ou descreva um processo a partir do XML.",
)

if not bpmn_tables_exist():
    st.error(
        "As tabelas `bpmn_processes` e `bpmn_versions` não foram encontradas. "
        "Execute o script de setup do Supabase antes de usar esta funcionalidade."
    )
    st.stop()

project_id, project_name = require_active_project()
_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

# Clear the paste-back widget BEFORE it's instantiated below — Streamlit
# forbids writing to a widget's session_state key once that widget has
# already rendered in the current script run (mirrors pages/BpmnEditor.py
# lines 54-55, which exists for the exact same reason).
if st.session_state.pop("_bpmns_reset_paste", False):
    st.session_state["bpmns_paste_xml"] = ""

tab_gerar, tab_descrever = st.tabs(["🧩 Gerar", "📖 Descrever"])

# ═════════════════════════════════════════════════════════════════════════════
# ABA GERAR — descrição → BPMN + Mermaid
# ═════════════════════════════════════════════════════════════════════════════
with tab_gerar:
    st.markdown(
        "Descreva o processo em texto livre — não precisa ser uma transcrição de "
        "reunião. Quanto mais detalhado (quem faz o quê, decisões, exceções), "
        "melhor o resultado."
    )
    description = st.text_area(
        "Descrição do processo",
        key="bpmns_description",
        height=180,
        placeholder=(
            "Ex: O cliente preenche o formulário de solicitação no portal. "
            "O analista financeiro valida os documentos anexados. Se a documentação "
            "estiver incompleta, o processo retorna ao cliente para complementação. "
            "Se estiver completa, o gerente aprova ou rejeita o pedido. Em caso de "
            "aprovação, o sistema gera o contrato automaticamente..."
        ),
        label_visibility="collapsed",
    )
    run_nlp = st.checkbox(
        "Detectar atores automaticamente (NLP, sem custo de LLM)",
        value=True,
        key="bpmns_run_nlp",
        help="Roda uma análise leve (spaCy, sem chamada a LLM) antes da geração para "
             "melhorar a nomeação de lanes/organizações.",
    )

    if st.button("🧩 Gerar BPMN", type="primary", key="bpmns_generate_btn"):
        if not description or len(description.strip()) < 20:
            st.error("Descreva o processo com mais detalhes (mínimo ~20 caracteres).")
        else:
            client_info = get_session_llm_client(st.session_state.selected_provider)
            if not client_info:
                st.error("Chave de API não encontrada para o provedor selecionado.")
            else:
                n_runs = st.session_state.get("n_bpmn_runs", 3)
                with st.spinner(f"Gerando BPMN e Mermaid — torneio de {n_runs} execuções…"):
                    try:
                        hub = generate_bpmn_from_description(
                            description.strip(),
                            client_info,
                            st.session_state.provider_cfg,
                            run_nlp=run_nlp,
                            output_language=st.session_state.output_language,
                            n_runs=n_runs,
                            bpmn_weights=st.session_state.get("bpmn_weights"),
                        )
                        if not hub.bpmn.ready:
                            st.error("Não foi possível gerar um diagrama a partir desta descrição.")
                        else:
                            st.session_state["_bpmns_hub"] = hub
                            st.session_state["_bpmns_proc_name"] = hub.bpmn.name or "Processo"
                            # New generation — discard any manual edit left over
                            # from a previous diagram (mirrors pages/BpmnEditor.py).
                            st.session_state.pop("_bpmns_edited_xml", None)
                            st.session_state["bpmns_paste_xml"] = ""
                    except Exception as exc:
                        st.error(f"❌ Erro ao gerar BPMN: {exc}")

    hub = st.session_state.get("_bpmns_hub")
    if hub is not None and hub.bpmn.ready:
        st.markdown("---")
        _score = getattr(hub.validation, "bpmn_score", None)
        if _score:
            st.caption(
                f"🏆 Melhor de {hub.validation.n_bpmn_runs} execuções (torneio) — "
                f"score {_score.weighted:.1f}/10 "
                f"(granularidade {_score.granularity:.1f} · tipo de tarefa {_score.task_type:.1f} · "
                f"gateways {_score.gateways:.1f} · estrutural {_score.structural:.1f} · "
                f"semântica {_score.semantic:.1f})"
            )
        tab_bpmn, tab_mermaid = st.tabs(["📐 Diagrama BPMN", "📊 Mermaid"])
        with tab_bpmn:
            # Lê o XML colado ANTES de renderizar o editor, para refletir a
            # edição na mesma passagem (mesmo padrão de pages/BpmnEditor.py).
            _pasted = st.session_state.get("bpmns_paste_xml", "").strip()
            if _pasted and ("<bpmn" in _pasted or "<?xml" in _pasted or "<definitions" in _pasted):
                st.session_state["_bpmns_edited_xml"] = _pasted

            _edited_xml = st.session_state.get("_bpmns_edited_xml")
            _active_xml = _edited_xml or hub.bpmn.bpmn_xml

            st.info(
                "**Como editar:** ajuste o diagrama na paleta à esquerda, clique "
                "**📋 Exportar XML** na barra do editor, copie o conteúdo da caixa "
                "que aparece (Ctrl+A → Ctrl+C) e cole no campo abaixo — o editor e "
                "o Salvar passam a usar a versão editada."
            )
            components.html(editor_from_xml(_active_xml, height=500), height=500 + 260, scrolling=False)

            col_paste, col_discard = st.columns([4, 1])
            with col_paste:
                st.text_area(
                    "📋 XML editado — cole aqui o conteúdo exportado pelo editor acima",
                    height=140,
                    key="bpmns_paste_xml",
                    placeholder='<?xml version="1.0" encoding="UTF-8"?>\n<definitions ...',
                )
            with col_discard:
                st.write("")
                st.write("")
                if st.button(
                    "↩️ Descartar edição",
                    key="bpmns_discard_edit_btn",
                    disabled=not _edited_xml,
                    use_container_width=True,
                    help="Volta a exibir e salvar a versão gerada originalmente pelo agente.",
                ):
                    st.session_state.pop("_bpmns_edited_xml", None)
                    st.session_state["_bpmns_reset_paste"] = True
                    st.rerun()

            if _edited_xml:
                st.caption(
                    "✏️ Exibindo a versão editada manualmente — o **Salvar** abaixo "
                    "grava esta versão, não a gerada originalmente pelo agente. O "
                    "Mermaid na aba ao lado continua refletindo a extração original "
                    "(não é recalculado a partir de edições manuais no BPMN)."
                )

            with st.expander("📝 Código BPMN (XML)", expanded=False):
                st.code(_active_xml, language="xml")
        with tab_mermaid:
            render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="bpmns", height=500)

        st.markdown("#### 💾 Salvar")
        col_name, col_meeting = st.columns(2)
        with col_name:
            proc_name = st.text_input(
                "Nome do processo",
                value=st.session_state.get("_bpmns_proc_name", hub.bpmn.name or "Processo"),
                key="bpmns_proc_name_input",
            )
        with col_meeting:
            meetings = list_meetings(project_id)
            _NONE = "— Nenhuma (processo autônomo) —"

            def _fmt_meeting(m: dict) -> str:
                date = (m.get("meeting_date") or "")[:10]
                title = m.get("title") or m.get("id", "")[:8]
                return f"{date}  {title}" if date else title

            meet_labels = [_NONE] + [_fmt_meeting(m) for m in meetings]
            meet_sel = st.selectbox(
                "Vincular a reunião (opcional)",
                meet_labels,
                key="bpmns_meeting_sel",
            )
            selected_meeting_id = None
            if meet_sel != _NONE:
                idx = meet_labels.index(meet_sel) - 1
                selected_meeting_id = meetings[idx]["id"]

        processes = list_bpmn_processes(project_id)
        _NEW_PROC = "➕ Novo processo"
        proc_labels = [_NEW_PROC] + [
            f"{p['name']} ({p.get('version_count', 0)} versão(ões))" for p in processes
        ]
        proc_sel = st.selectbox(
            "Salvar como",
            proc_labels,
            key="bpmns_save_target_sel",
            help="Escolha um processo existente para adicionar uma nova versão, "
                 "ou crie um processo novo.",
        )

        if st.button("💾 Salvar", type="primary", key="bpmns_save_btn"):
            hub.bpmn.name = proc_name.strip() or hub.bpmn.name
            _edited_xml_to_save = st.session_state.get("_bpmns_edited_xml")
            if _edited_xml_to_save:
                hub.bpmn.bpmn_xml = _edited_xml_to_save
            if proc_sel == _NEW_PROC:
                target_process_id = None
                override_name = proc_name.strip()
            else:
                idx = proc_labels.index(proc_sel) - 1
                target_process_id = processes[idx]["id"]
                override_name = ""

            pid = save_bpmn_from_hub(
                meeting_id=selected_meeting_id,
                project_id=project_id,
                hub=hub,
                bpmn_process_id=target_process_id,
                bpmn_process_override_name=override_name,
            )
            if pid:
                st.success(
                    f"✅ Processo salvo com sucesso"
                    + (f" — vinculado à reunião selecionada." if selected_meeting_id else " — sem reunião vinculada.")
                )
                st.page_link("pages/BpmnEditor.py", label="→ Abrir no Editor BPMN")
            else:
                st.error("❌ Erro ao salvar. Verifique a conexão com o banco de dados.")

# ═════════════════════════════════════════════════════════════════════════════
# ABA DESCREVER — BPMN → descrição textual
# ═════════════════════════════════════════════════════════════════════════════
with tab_descrever:
    st.markdown(
        "Cole o XML de um diagrama BPMN 2.0 (salvo neste projeto ou de qualquer "
        "outra origem) para gerar a descrição textual estruturada do processo."
    )
    uploaded = st.file_uploader(
        "Ou envie um arquivo .bpmn / .xml",
        type=["bpmn", "xml"],
        key="bpmns_describe_upload",
    )
    default_xml = ""
    if uploaded is not None:
        try:
            default_xml = uploaded.read().decode("utf-8", errors="replace")
        except Exception:
            default_xml = ""

    xml_input = st.text_area(
        "XML BPMN",
        value=default_xml,
        key="bpmns_describe_xml",
        height=220,
        placeholder="<?xml version=\"1.0\" ...?>\n<bpmn:definitions ...>...</bpmn:definitions>",
        label_visibility="collapsed",
    )

    if st.button("📖 Gerar descrição", type="primary", key="bpmns_describe_btn"):
        if not xml_input or not xml_input.strip():
            st.error("Cole ou envie um XML BPMN.")
        else:
            description_md = describe_bpmn_from_xml(xml_input.strip())
            st.session_state["_bpmns_description_md"] = description_md

    description_md = st.session_state.get("_bpmns_description_md")
    if description_md:
        st.markdown("---")
        st.markdown(description_md)
        st.download_button(
            "⬇️ Baixar .md",
            data=description_md.encode("utf-8"),
            file_name=f"descricao_processo_{_dt.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            key="bpmns_describe_download",
        )
