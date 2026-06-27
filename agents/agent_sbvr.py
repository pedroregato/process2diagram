# agents/agent_sbvr.py
# ─────────────────────────────────────────────────────────────────────────────
# SBVR Agent — extrai vocabulário de negócio e regras de negócio (OMG SBVR).
#
# Reads:  hub.transcript_clean
# Writes: hub.sbvr  (SBVRModel — domain, vocabulary, rules)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, SBVRModel, BusinessTerm, BusinessRule, _VALID_SPHERES


class AgentSBVR(BaseAgent):

    name = "sbvr"
    skill_path = "skills/skill_sbvr.md"
    required_hub_fields = ["transcript_clean"]

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        if getattr(hub, "context_skill", "").strip():
            system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill.strip()}"

        if getattr(hub, "context_files_text", "").strip():
            system += f"\n\n## Documentos de Referência do Contexto\n\n{hub.context_files_text.strip()}"

        # Inject BMM policies if available — helps SBVR link rules to stated policies
        if getattr(hub, "bmm", None) and hub.bmm.ready and hub.bmm.policies:
            pol_lines = "\n".join(
                f"- {p.id}: {p.statement[:120]}" for p in hub.bmm.policies[:8]
            )
            system += (
                f"\n\n## Políticas Corporativas (BMM) para Contexto\n\n"
                f"Para cada regra extraída, verifique se ela implementa uma das políticas "
                f"abaixo e preencha `bmm_policy_ref` com o ID correspondente:\n\n{pol_lines}"
            )

        user = (
            "Extract the business vocabulary and rules from this transcript:\n\n"
            f"{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.sbvr = self._build_model(data)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model builder ─────────────────────────────────────────────────────────

    def _build_model(self, data: dict) -> SBVRModel:
        vocabulary = [
            BusinessTerm(
                term=t.get("term", "").strip(),
                definition=t.get("definition", "").strip(),
                category=t.get("category", "concept"),
            )
            for t in data.get("vocabulary", [])
            if t.get("term", "").strip()
        ]

        rules = []
        for i, r in enumerate(data.get("rules", [])):
            if not r.get("statement", "").strip():
                continue
            raw_sphere = str(r.get("sphere", "geral")).lower().strip()
            sphere = raw_sphere if raw_sphere in _VALID_SPHERES else "geral"
            rules.append(BusinessRule(
                id=r.get("id", f"BR{i + 1:03d}"),
                statement=r.get("statement", "").strip(),
                short_title=r.get("short_title", "").strip(),
                rule_type=r.get("rule_type", "constraint"),
                source=r.get("source") or "",
                sphere=sphere,
                sphere_owner=str(r.get("sphere_owner", "") or "").strip(),
                bmm_policy_ref=r.get("bmm_policy_ref") or None,
                speaker_quote=str(r.get("speaker_quote", "") or "")[:200].strip(),
            ))

        return SBVRModel(
            domain=data.get("domain", "").strip(),
            vocabulary=vocabulary,
            rules=rules,
            ready=True,
        )
