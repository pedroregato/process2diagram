# agents/agent_bpmn_analyst.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentBPMNAnalyst — interpreta um diagrama BPMN 2.0 já existente e responde
# perguntas livres sobre ele (ex: "Descreva o subprocesso 'Contratar
# Consultoria'", "quem aprova o contrato?", "o que acontece se a proposta for
# reprovada?").
#
# Este agente NÃO faz parte do pipeline automático.
# É chamado sob demanda pela ferramenta ask_bpmn_diagram em
# core/tools/tools_bpmn_sbvr.py.
#
# Um único método público:
#   answer(process_name, bpmn_xml, question, detail_context="", output_language)
#       Responde em texto livre (Markdown leve) — não é JSON, portanto
#       _call_llm é chamado diretamente (mesmo padrão de
#       AgentBPMNReviewer.review() / DocumentAnalyzerAgent.analyze()).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import xml.etree.ElementTree as ET

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub

_BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"


class AgentBPMNAnalyst(BaseAgent):
    name = "bpmn_analyst"
    skill_path = "skills/skill_bpmn_analyst.md"

    # Satisfaz a interface abstrata do BaseAgent — não é usado diretamente.
    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:  # type: ignore[override]
        return self._skill, ""

    def run(self, hub: KnowledgeHub) -> KnowledgeHub:  # type: ignore[override]
        """Não usado no pipeline — chame answer()."""
        return hub

    # ── Pergunta livre sobre o diagrama ───────────────────────────────────────

    def answer(
        self,
        process_name: str,
        bpmn_xml: str,
        question: str,
        detail_context: str = "",
        output_language: str = "Auto-detect",
    ) -> str:
        """Responde a uma pergunta em linguagem natural sobre um diagrama BPMN.

        Args:
            process_name: nome de exibição do processo (para o cabeçalho do prompt).
            bpmn_xml: XML BPMN 2.0 completo. A seção <bpmndi:BPMNDiagram>
                (coordenadas visuais, sem valor semântico) é removida antes de
                enviar ao LLM — reduz tokens sem perder nenhuma informação
                relevante para responder perguntas.
            question: pergunta do usuário em linguagem natural.
            detail_context: XML de detalhamento(s) de fase (callActivity) já
                salvos que sejam relevantes à pergunta — concatenado ao prompt
                para permitir respostas sobre os passos internos reais de uma
                fase, em vez de apenas a documentation resumida.
            output_language: idioma de saída, mesmo parâmetro do pipeline normal.

        Returns:
            Resposta em texto livre (Markdown leve). Nunca lança exceção —
            retorna uma mensagem de erro clara em caso de falha do LLM.
        """
        system, user = self._build_prompt(
            process_name, bpmn_xml, question, detail_context, output_language
        )
        hub = KnowledgeHub.new()
        try:
            raw = self._call_llm(system, user, hub)
            return raw.strip()
        except Exception as exc:
            return f"Erro ao consultar o diagrama via LLM: {exc}"

    # ── Prompt builder ─────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        process_name: str,
        bpmn_xml: str,
        question: str,
        detail_context: str,
        output_language: str,
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill + f"\n\nResponda em: {lang}."

        clean_xml = self._strip_diagram_interchange(bpmn_xml)

        parts = [
            f"# Processo: {process_name or '(sem nome)'}",
            "",
            "## XML BPMN (semântico — coordenadas visuais removidas)",
            "```xml",
            clean_xml,
            "```",
        ]
        if detail_context.strip():
            parts += [
                "",
                "## Detalhamentos de fase já disponíveis",
                "Use este conteúdo para descrever os passos internos reais das "
                "fases abaixo, em vez de apenas a documentation resumida da fase "
                "no diagrama principal.",
                "",
                detail_context.strip(),
            ]
        parts += ["", "## Pergunta", question.strip()]

        return system, "\n".join(parts)

    # ── XML cleanup ────────────────────────────────────────────────────────────

    @staticmethod
    def _strip_diagram_interchange(xml_str: str) -> str:
        """Removes <bpmndi:BPMNDiagram> (pure layout/coordinates) from a BPMN
        XML string before sending it to the LLM — cuts token usage without
        losing any information relevant to answering questions about the
        process's structure or content. Fail-open: returns the original
        string unchanged if parsing fails."""
        if not xml_str or not xml_str.strip():
            return xml_str
        try:
            for pfx, uri in (
                ("",       "http://www.omg.org/spec/BPMN/20100524/MODEL"),
                ("bpmndi", _BPMNDI_NS),
                ("dc",     "http://www.omg.org/spec/DD/20100524/DC"),
                ("di",     "http://www.omg.org/spec/DD/20100524/DI"),
            ):
                ET.register_namespace(pfx, uri)
            root = ET.fromstring(xml_str)
            for parent in root.iter():
                diagrams = [
                    child for child in list(parent)
                    if child.tag == f"{{{_BPMNDI_NS}}}BPMNDiagram"
                ]
                for d in diagrams:
                    parent.remove(d)
            return ET.tostring(root, encoding="unicode")
        except Exception:
            return xml_str
