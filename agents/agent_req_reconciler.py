# agents/agent_req_reconciler.py
# ─────────────────────────────────────────────────────────────────────────────
# Reconciliador de requisitos entre reuniões.
#
# Para cada requisito novo extraído pela reunião atual:
#   1. Pré-filtro por sobreposição de palavras (Jaccard, sem API)
#   2. LLM classifica o par (requisito existente × novo):
#        confirmed  — mesma definição, sem alteração
#        revised    — mesmo assunto, definição diferente
#        contradicted — conflito direto com definição anterior
#        unrelated  — assunto diferente → trata como novo REQ-XXX
#   3. Persiste resultado no Supabase (nova versão ou novo requisito)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
from typing import Any

from agents.base_agent import BaseAgent
from core.project_store import (
    list_requirements,
    save_new_requirement,
    add_requirement_version,
    update_requirement,
    next_req_number,
)

# Threshold de sobreposição Jaccard para enviar ao LLM
_JACCARD_THRESHOLD = 0.12
# Máximo de candidatos por requisito enviados ao LLM
_MAX_CANDIDATES = 3

_SYSTEM_PROMPT = """Você é um analista de requisitos de software experiente.
Sua tarefa é comparar um REQUISITO EXISTENTE (de uma reunião anterior) com um
REQUISITO NOVO (da reunião atual) e classificar a relação entre eles.

Responda APENAS com JSON válido, sem explicações adicionais:
{
  "change_type": "confirmed" | "revised" | "contradicted" | "unrelated",
  "change_summary": "<resumo curto do que mudou, ou vazio se confirmed/unrelated>",
  "contradiction_detail": "<descrição do conflito, citando ambos os valores, ou vazio>"
}

Definições:
- confirmed: mesma definição, requisito reafirmado sem alteração
- revised: mesmo assunto/funcionalidade, mas com detalhes alterados
- contradicted: define algo que CONFLITA diretamente com a definição anterior
  (ex: "campo tem 20 chars" vs "campo tem 120 chars")
- unrelated: assuntos completamente diferentes
"""


def _jaccard(a: str, b: str) -> float:
    """Similaridade Jaccard entre dois textos (sobreposição de palavras)."""
    s1 = set(re.findall(r"\w+", a.lower()))
    s2 = set(re.findall(r"\w+", b.lower()))
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def _req_text(req: Any) -> str:
    """Texto combinado título + descrição para comparação."""
    if hasattr(req, "title"):
        return f"{req.title} {req.description or ''}"
    return f"{req.get('title', '')} {req.get('description', '')}"


def _format_existing(req: dict) -> str:
    num = str(req.get("req_number", "?")).zfill(3)
    return (
        f"REQ-{num} — {req.get('title', '')}\n"
        f"Descrição: {req.get('description', '')}\n"
        f"Tipo: {req.get('req_type', '')} | Prioridade: {req.get('priority', '')}"
    )


class AgentReqReconciler(BaseAgent):
    """Reconcilia requisitos de uma reunião com o histórico do projeto."""

    name = "req_reconciler"
    skill_path = None  # prompt definido inline, sem arquivo

    def _load_skill(self) -> str:  # type: ignore[override]
        return _SYSTEM_PROMPT

    def build_prompt(self, hub, output_language="Auto-detect"):  # type: ignore[override]
        # Not used directly — reconciler builds prompts inline in _classify_pair
        return _SYSTEM_PROMPT, ""

    # ── Ponto de entrada público ──────────────────────────────────────────────

    def run(  # type: ignore[override]
        self,
        hub,
        project_id: str,
        meeting_id: str,
        output_language: str = "Auto-detect",
    ) -> dict[str, int]:
        """Reconcilia e persiste os requisitos do hub.

        Retorna contagem por change_type: {"new": N, "confirmed": N,
        "revised": N, "contradicted": N}.
        """
        if not hub.requirements.ready:
            return {}

        new_reqs = hub.requirements.requirements
        if not new_reqs:
            return {}

        # Requisitos já existentes no projeto (excluindo a reunião atual)
        existing = [
            r for r in list_requirements(project_id)
            if r.get("last_meeting_id") != meeting_id
        ]

        counts: dict[str, int] = {
            "new": 0, "confirmed": 0, "revised": 0, "contradicted": 0
        }
        next_num = next_req_number(project_id)

        for item in new_reqs:
            result = self._reconcile_one(
                item, existing, project_id, meeting_id, next_num, hub
            )
            counts[result] = counts.get(result, 0) + 1
            if result == "new":
                next_num += 1

        return counts

    # ── Lógica interna ────────────────────────────────────────────────────────

    def _reconcile_one(
        self, item, existing: list[dict],
        project_id: str, meeting_id: str,
        next_num: int, hub,
    ) -> str:
        """Processa um único requisito. Retorna o change_type aplicado."""

        # Traceability fields extracted by AgentRequirements
        _source_quote = getattr(item, "source_quote", "") or ""
        _cited_by     = getattr(item, "speaker", "") or ""

        # Sem histórico → sempre novo
        if not existing:
            save_new_requirement(
                project_id, meeting_id, next_num,
                item.title, item.description,
                getattr(item, "type", ""), getattr(item, "priority", ""),
                source_quote=_source_quote, cited_by=_cited_by,
            )
            return "new"

        # Pré-filtro Jaccard
        text_new = _req_text(item)
        scored = sorted(
            existing,
            key=lambda r: _jaccard(_req_text(r), text_new),
            reverse=True,
        )
        top = [r for r in scored[:_MAX_CANDIDATES]
               if _jaccard(_req_text(r), text_new) >= _JACCARD_THRESHOLD]

        if not top:
            save_new_requirement(
                project_id, meeting_id, next_num,
                item.title, item.description,
                getattr(item, "type", ""), getattr(item, "priority", ""),
                source_quote=_source_quote, cited_by=_cited_by,
            )
            return "new"

        # LLM classifica contra o candidato mais similar
        best = top[0]
        classification = self._classify_pair(best, item, hub)
        change_type = classification.get("change_type", "unrelated")

        if change_type == "unrelated":
            save_new_requirement(
                project_id, meeting_id, next_num,
                item.title, item.description,
                getattr(item, "type", ""), getattr(item, "priority", ""),
                source_quote=_source_quote, cited_by=_cited_by,
            )
            return "new"

        # Versão do requisito existente
        versions = best.get("requirement_versions") or []
        version_num = (max((v.get("version", 0) for v in versions), default=0) + 1
                       if isinstance(versions, list) else 2)

        add_requirement_version(
            requirement_id=best["id"],
            meeting_id=meeting_id,
            version=version_num,
            title=item.title,
            description=item.description,
            req_type=getattr(item, "type", ""),
            priority=getattr(item, "priority", ""),
            change_type=change_type,
            change_summary=classification.get("change_summary", ""),
            contradiction_flag=(change_type == "contradicted"),
            contradiction_detail=classification.get("contradiction_detail", ""),
            source_quote=_source_quote,
            cited_by=_cited_by,
        )
        update_requirement(
            requirement_id=best["id"],
            status="contradicted" if change_type == "contradicted" else "revised"
                   if change_type == "revised" else best.get("status", "active"),
            last_meeting_id=meeting_id,
            title=item.title if change_type in ("revised", "contradicted") else best["title"],
            description=item.description if change_type in ("revised", "contradicted")
                        else best["description"],
        )
        return change_type

    def _classify_pair(self, existing: dict, new_item, hub) -> dict[str, str]:
        """Chama o LLM para classificar a relação entre dois requisitos."""
        user_prompt = (
            "REQUISITO EXISTENTE:\n"
            f"{_format_existing(existing)}\n\n"
            "REQUISITO NOVO (reunião atual):\n"
            f"Título: {new_item.title}\n"
            f"Descrição: {new_item.description}\n"
            f"Tipo: {getattr(new_item, 'type', '')} | "
            f"Prioridade: {getattr(new_item, 'priority', '')}"
        )
        try:
            raw = self._call_llm(_SYSTEM_PROMPT, user_prompt, hub)
            # extrai JSON mesmo que venha com markdown
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        return {"change_type": "unrelated", "change_summary": "", "contradiction_detail": ""}
