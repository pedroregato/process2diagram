# agents/agent_bpmn_reviewer.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentBPMNReviewer — auditor semântico de diagramas BPMN existentes.
#
# Este agente NÃO faz parte do pipeline automático.
# É chamado sob demanda pela ferramenta apply_bpmn_corrections em assistant_tools.py.
#
# Dois métodos públicos:
#   review(bpmn_xml, process_name) → str
#       Executa revisão completa em 4 fases e retorna relatório Markdown.
#       Usa skill_bpmn_reviewer.md como sistema prompt.
#
#   apply_corrections(bpmn_xml, process_name, corrections) → dict | None
#       Aplica lista de correções cirúrgicas e retorna JSON no formato AgentBPMN.
#       Usa prompt focado (sem o skill completo) para retornar JSON puro.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
from typing import Optional

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub


class AgentBPMNReviewer(BaseAgent):
    name = "bpmn_reviewer"
    skill_path = "skills/skill_bpmn_reviewer.md"

    # Satisfaz a interface abstrata do BaseAgent — não é usado diretamente.
    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:  # type: ignore[override]
        return self._load_skill(), ""

    def run(self, hub: KnowledgeHub) -> KnowledgeHub:  # type: ignore[override]
        """Não usado no pipeline — chame review() ou apply_corrections()."""
        return hub

    # ── Revisão completa (4 fases) ────────────────────────────────────────────

    def review(self, bpmn_xml: str, process_name: str = "") -> str:
        """Executa revisão em 4 fases e retorna relatório Markdown.

        O modelo recebe o skill completo (skill_bpmn_reviewer.md) como prompt de
        sistema e o XML como prompt de usuário. A resposta é texto estruturado
        (Markdown) — não JSON — portanto _call_llm é chamado diretamente.

        Returns: Markdown do relatório (Fases 1→4).
        """
        system = self._load_skill()
        user = self._build_review_user(bpmn_xml, process_name)
        hub = _MinimalHub()
        try:
            raw = self._call_llm(system, user, hub)
            return raw.strip()
        except Exception as exc:
            return f"Erro na revisão LLM: {exc}"

    # ── Aplicação de correções → JSON ─────────────────────────────────────────

    def apply_corrections(
        self,
        bpmn_xml: str,
        process_name: str,
        corrections: list[dict],
    ) -> Optional[dict]:
        """Aplica correções e retorna JSON corrigido no formato AgentBPMN flat.

        O prompt de sistema é focado em retornar JSON puro (sem o skill completo
        de 4 fases), para garantir output parseável. A validação de formato é
        tratada por _call_with_retry (até 3 tentativas).

        Returns: dict com chaves do formato AgentBPMN (name, steps, edges, lanes…)
                 ou None em caso de falha.
        """
        system = self._build_correction_system()
        user = self._build_correction_user(bpmn_xml, process_name, corrections)
        hub = _MinimalHub()
        try:
            return self._call_with_retry(system, user, hub)
        except Exception:
            return None

    # ── Prompt builders ───────────────────────────────────────────────────────

    def _build_review_user(self, bpmn_xml: str, process_name: str) -> str:
        MAX_XML = 12_000
        xml_excerpt = (
            bpmn_xml[:MAX_XML] + "\n[... XML truncado por tamanho ...]"
            if len(bpmn_xml) > MAX_XML else bpmn_xml
        )
        name_line = f"**Processo:** {process_name}\n\n" if process_name else ""
        return f"{name_line}# XML BPMN para Revisão\n\n```xml\n{xml_excerpt}\n```"

    @staticmethod
    def _build_correction_system() -> str:
        return (
            "Você é um especialista em BPMN 2.0 (OMG) e Bruce Silver Method and Style.\n"
            "Sua tarefa: aplicar as correções indicadas em um diagrama BPMN e retornar "
            "o modelo corrigido em JSON no formato plano do AgentBPMN.\n\n"
            "FORMATO DE SAÍDA OBRIGATÓRIO — JSON puro (sem markdown, sem explicação):\n"
            "{\n"
            '  "name": "Nome do Processo",\n'
            '  "description": "Descrição resumida do processo corrigido.",\n'
            '  "process_trigger": "Gatilho do processo",\n'
            '  "process_outcomes": ["Resultado 1", "Resultado 2"],\n'
            '  "process_type": "flat",\n'
            '  "steps": [\n'
            '    { "id": "S01", "title": "Verbo + Objeto", "description": "", '
            '"actor": null, "is_decision": false, "task_type": "noneStartEvent", "lane": "Lane A" },\n'
            '    { "id": "S02", "title": "Verbo + Objeto", "description": "", '
            '"actor": "Cargo", "is_decision": false, "task_type": "userTask", "lane": "Lane A" },\n'
            '    { "id": "S03", "title": "Pergunta ou Estado?", "description": "", '
            '"actor": null, "is_decision": true, "task_type": "exclusiveGateway", "lane": "Lane A" },\n'
            '    { "id": "S04", "title": "Resultado Alcancado", "description": "", '
            '"actor": null, "is_decision": false, "task_type": "noneEndEvent", "lane": "Lane A" }\n'
            "  ],\n"
            '  "edges": [\n'
            '    { "source": "S01", "target": "S02", "label": "", "condition": "" },\n'
            '    { "source": "S03", "target": "S04", "label": "Sim", "condition": "" }\n'
            "  ],\n"
            '  "lanes": ["Lane A"]\n'
            "}\n\n"
            "REGRAS CRÍTICAS (Bruce Silver Method and Style Level 1):\n"
            "1. Gateways: nome é pergunta ou estado — NUNCA verbo de atividade\n"
            "   (Validar, Analisar, Verificar, Conferir, Revisar, Aprovar → são tasks)\n"
            "2. Tasks: nome é verbo + objeto — NUNCA estado/pergunta ('Documento Válido?')\n"
            "3. Lanes: nomes organizacionais concretos — NUNCA 'Usuário', 'Sistema', 'Ator'\n"
            "4. Todo gateway exclusivo tem ≥ 2 saídas com rótulos distintos nas edges\n"
            "5. noneStartEvent: task_type='noneStartEvent'; noneEndEvent: task_type='noneEndEvent'\n"
            "6. Inclua TODOS os steps do processo original + novos gerados pelas correções\n"
            "7. Ao converter gateway→task, insira NOVO exclusiveGateway imediatamente após\n"
            "   com a pergunta correspondente e reaponte as saídas para o novo gateway\n"
            "8. Retorne APENAS JSON válido. Sem markdown, sem bloco de código, sem explicação."
        )

    @staticmethod
    def _build_correction_user(
        bpmn_xml: str,
        process_name: str,
        corrections: list[dict],
    ) -> str:
        MAX_XML = 10_000
        xml_excerpt = (
            bpmn_xml[:MAX_XML] + "\n[... XML truncado ...]"
            if len(bpmn_xml) > MAX_XML else bpmn_xml
        )
        corrections_str = json.dumps(corrections, ensure_ascii=False, indent=2)
        return (
            f"# Processo: {process_name}\n\n"
            f"## XML BPMN atual\n\n```xml\n{xml_excerpt}\n```\n\n"
            f"## Correções a aplicar ({len(corrections)} item(s))\n\n"
            f"```json\n{corrections_str}\n```\n\n"
            f"Aplique TODAS as correções acima ao modelo BPMN e retorne o JSON corrigido completo."
        )


# ── Minimal hub stub ──────────────────────────────────────────────────────────

class _MinimalHub:
    """Stub mínimo que satisfaz a interface de hub exigida por BaseAgent._call_with_retry()."""

    class _Meta:
        total_tokens_used  = 0
        processing_time_ms = 0
        cache_hits         = 0
        tokens_saved       = 0
        long_context_calls = 0
        llm_provider       = "unknown"
        llm_model          = "unknown"

    meta             = _Meta()
    transcript_clean = ""

    def bump(self):
        pass

    def mark_agent_run(self, name: str):
        pass
