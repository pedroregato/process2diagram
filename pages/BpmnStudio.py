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
import xml.etree.ElementTree as ET
from dataclasses import asdict
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
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block
from modules.bpmn_describer import describe_bpmn_from_xml
from agents.agent_bpmn_studio import generate_bpmn_from_description
from core.project_store import (
    bpmn_tables_exist,
    list_bpmn_processes,
    list_meetings,
    save_bpmn_from_hub,
    get_current_bpmn_version_id,
    save_bpmn_callactivity_diagram,
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
    _n_runs_selected = st.select_slider(
        "Passes de Otimização (torneio de execuções)",
        options=[1, 3, 5],
        value=st.session_state.get("n_bpmn_runs", 3),
        key="bpmns_n_runs_slider",
        help="Cada passe é uma geração independente da LLM; o melhor dos N é escolhido "
             "por score de qualidade (AgentValidator). Mais passes = melhor comparação, "
             "mais tempo de espera (~1-2 min por passe). Reduza para 1 quando velocidade "
             "importa mais que o torneio de qualidade — a mesma configuração vale para o "
             "Pipeline principal e para o detalhamento de fases abaixo.",
    )
    st.session_state["n_bpmn_runs"] = _n_runs_selected

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
                hub.bpmn.db_process_id = pid  # habilita salvar detalhamentos de callActivity
                st.success(
                    f"✅ Processo salvo com sucesso"
                    + (f" — vinculado à reunião selecionada." if selected_meeting_id else " — sem reunião vinculada.")
                )
                st.page_link("pages/BpmnEditor.py", label="→ Abrir no Editor BPMN")
            else:
                st.error("❌ Erro ao salvar. Verifique a conexão com o banco de dados.")

        # ═════════════════════════════════════════════════════════════════════
        # DETALHAR UMA FASE (callActivity) — PC120
        # ═════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("#### 🔍 Detalhar uma fase (callActivity)")
        st.caption(
            "Gera um diagrama BPMN separado e detalhado para uma fase específica, "
            "usando a descrição já registrada nela como entrada — mesmo mecanismo "
            "de geração da aba principal (torneio de execuções)."
        )

        def _extract_call_activities(xml_str: str) -> list[dict]:
            _NS = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
            try:
                root = ET.fromstring(xml_str)
            except ET.ParseError:
                return []
            pool_by_process: dict[str, str] = {}
            for collab in root.findall(f"{_NS}collaboration"):
                for part in collab.findall(f"{_NS}participant"):
                    ref = part.get("processRef")
                    if ref:
                        pool_by_process[ref] = part.get("name", "")
            items: list[dict] = []
            for proc in root.findall(f"{_NS}process"):
                proc_id = proc.get("id")
                pool_name = pool_by_process.get(proc_id, "")
                for el in proc.findall(f"{_NS}callActivity"):
                    doc_el = el.find(f"{_NS}documentation")
                    items.append({
                        "id": el.get("id"),
                        "name": el.get("name") or el.get("id"),
                        "documentation": (doc_el.text or "").strip() if doc_el is not None else "",
                        "pool_name": pool_name,
                    })
            return items

        _call_activities = _extract_call_activities(_active_xml)
        if not _call_activities:
            st.caption("Nenhuma fase (callActivity) neste diagrama para detalhar.")
        else:
            _ca_labels = [
                f"{ca['name']} — {ca['pool_name']}" if ca["pool_name"] else ca["name"]
                for ca in _call_activities
            ]
            _ca_idx = st.selectbox(
                "Fase para detalhar",
                range(len(_call_activities)),
                format_func=lambda i: _ca_labels[i],
                key="bpmns_detail_ca_sel",
            )
            _selected_ca = _call_activities[_ca_idx]

            if st.button(f"🔍 Detalhar '{_selected_ca['name']}'", key="bpmns_detail_generate_btn"):
                if not _selected_ca["documentation"]:
                    st.error("Esta fase não tem descrição suficiente para detalhar.")
                else:
                    detail_client_info = get_session_llm_client(st.session_state.selected_provider)
                    if not detail_client_info:
                        st.error("Chave de API não encontrada para o provedor selecionado.")
                    else:
                        with st.spinner(f"Detalhando '{_selected_ca['name']}'…"):
                            try:
                                detail_hub = generate_bpmn_from_description(
                                    _selected_ca["documentation"],
                                    detail_client_info,
                                    st.session_state.provider_cfg,
                                    run_nlp=run_nlp,
                                    output_language=st.session_state.output_language,
                                    n_runs=st.session_state.get("n_bpmn_runs", 3),
                                    bpmn_weights=st.session_state.get("bpmn_weights"),
                                )
                                if not detail_hub.bpmn.ready:
                                    st.error("Não foi possível detalhar esta fase.")
                                else:
                                    hub.bpmn.detail_diagrams[_selected_ca["id"]] = detail_hub.bpmn
                                    _dmeta = st.session_state.setdefault("_bpmns_detail_meta", {})
                                    _score = detail_hub.validation.bpmn_score
                                    _dmeta[_selected_ca["id"]] = {
                                        "name": _selected_ca["name"],
                                        "pool_name": _selected_ca["pool_name"],
                                        "documentation": _selected_ca["documentation"],
                                        "score": asdict(_score) if _score else None,
                                    }
                                    st.success(f"✅ Detalhamento de '{_selected_ca['name']}' gerado.")
                            except Exception as exc:
                                st.error(f"❌ Erro ao detalhar: {exc}")

        if hub.bpmn.detail_diagrams:
            st.markdown("##### Fases já detalhadas nesta sessão")
            _detail_meta = st.session_state.get("_bpmns_detail_meta", {})
            for _element_id, _detail_model in hub.bpmn.detail_diagrams.items():
                _meta = _detail_meta.get(_element_id, {})
                _label = _meta.get("name", _element_id)
                with st.expander(f"📎 {_label}", expanded=False):
                    _dscore = _meta.get("score")
                    if _dscore:
                        st.caption(f"Score do torneio: {_dscore['weighted']:.1f}/10")
                    components.html(preview_from_xml(_detail_model.bpmn_xml), height=350, scrolling=False)
                    # st.expander não pode ser aninhado (CLAUDE.md — Known Pitfalls);
                    # este expander de detalhamento já está dentro do de cima.
                    st.caption("📝 Código BPMN (XML)")
                    st.code(_detail_model.bpmn_xml, language="xml")

                    if not hub.bpmn.db_process_id:
                        st.caption("⏳ Salve o diagrama principal (acima) antes de salvar este detalhamento.")
                    elif st.button(f"💾 Salvar detalhamento de '{_label}'", key=f"bpmns_save_detail_{_element_id}"):
                        _version_id = get_current_bpmn_version_id(hub.bpmn.db_process_id)
                        if not _version_id:
                            st.error("Não foi possível localizar a versão atual do processo salvo.")
                        else:
                            ok = save_bpmn_callactivity_diagram(
                                bpmn_version_id=_version_id,
                                element_id=_element_id,
                                element_name=_label,
                                bpmn_xml=_detail_model.bpmn_xml,
                                pool_name=_meta.get("pool_name", ""),
                                source_description=_meta.get("documentation", ""),
                                mermaid_code=_detail_model.mermaid,
                                bpmn_score=_dscore,
                                created_by=st.session_state.get("_usuario_login", ""),
                            )
                            if ok:
                                st.success("✅ Detalhamento salvo.")
                            else:
                                st.error("❌ Erro ao salvar o detalhamento.")

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
