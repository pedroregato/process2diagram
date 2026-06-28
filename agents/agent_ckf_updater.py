# agents/agent_ckf_updater.py
# ─────────────────────────────────────────────────────────────────────────────
# CKF Updater — mantém o Context Knowledge File do contexto atualizado
# com os insights gerados a cada reunião.
#
# Reads:  hub.minutes, hub.requirements, hub.sbvr, hub.bmm, hub.bpmn,
#         hub.context_skill (CKF atual), hub.context_id
# Writes: hub.context_skill (CKF atualizado)
#         → persiste em contexts.skill_md via save_context_skill()
#
# Output: Markdown puro (não JSON) — usa _call_llm() diretamente.
# Execução: não-fatal; falha silenciosa preserva o CKF anterior.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub


class AgentCKFUpdater(BaseAgent):

    name                 = "ckf_updater"
    skill_path           = "skills/skill_ckf_updater.md"
    required_hub_fields  = []   # digest gracefully handles absent artefacts; early-exit when empty

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        system = self._skill

        # ── Digest: o que aprendemos nesta reunião ─────────────────────────
        digest_parts: list[str] = []

        # Participantes e decisões (Minutes)
        if hub.minutes.ready:
            m = hub.minutes
            if m.participants:
                names = [f"{p.name} ({p.initials})" if p.initials else p.name
                         for p in m.participants if p.name]
                if names:
                    digest_parts.append("### Participantes desta reunião\n" + "\n".join(f"- {n}" for n in names))

            if m.agenda:
                digest_parts.append("### Tópicos discutidos\n" + "\n".join(f"- {t}" for t in m.agenda[:8]))

            if m.decisions:
                digest_parts.append("### Decisões tomadas\n" + "\n".join(f"- {d}" for d in m.decisions[:6]))

        # Termos e regras de negócio (SBVR)
        if hub.sbvr.ready:
            s = hub.sbvr
            if s.vocabulary:
                entries = [f"- **{t.term}**: {t.definition}" for t in s.vocabulary[:10] if t.term]
                if entries:
                    digest_parts.append("### Termos de negócio identificados\n" + "\n".join(entries))

            if s.rules:
                rules = [f"- {r.statement}" for r in s.rules[:6] if r.statement]
                if rules:
                    digest_parts.append("### Regras de negócio identificadas\n" + "\n".join(rules))

        # Objetivos estratégicos (BMM)
        if hub.bmm.ready:
            b = hub.bmm
            if b.vision:
                digest_parts.append(f"### Visão estratégica\n{b.vision}")
            if b.goals:
                goals = [f"- {g.name}: {g.description}" for g in b.goals[:5] if g.name]
                if goals:
                    digest_parts.append("### Objetivos identificados\n" + "\n".join(goals))

        # Processos e unidades organizacionais (BPMN)
        if hub.bpmn.ready:
            b = hub.bpmn
            if b.name:
                digest_parts.append(f"### Processo mapeado\n{b.name}")
            lanes = list({s.lane for s in b.steps if s.lane})
            if lanes:
                digest_parts.append("### Unidades organizacionais\n" + "\n".join(f"- {l}" for l in lanes))

        # Requisitos — termos de domínio (Requirements)
        if hub.requirements.ready:
            req_titles = [r.title for r in hub.requirements.requirements[:8] if r.title]
            if req_titles:
                digest_parts.append("### Requisitos levantados\n" + "\n".join(f"- {t}" for t in req_titles))

        if not digest_parts:
            return "", ""  # Nada útil para aprender — skip

        digest = "\n\n".join(digest_parts)
        current_ckf = (hub.context_skill or "").strip()

        user = (
            f"## CKF Atual\n\n{current_ckf}\n\n"
            if current_ckf else
            "## CKF Atual\n\n(vazio — criar a partir do digest)\n\n"
        )
        user += f"## Digest da Reunião\n\n{digest}\n\n"
        user += "Produza o CKF atualizado:"

        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
        context_id: str = "",
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)

        if not system or not user:
            return hub  # Nada para aprender nesta execução

        # Disable json_mode — output is plain Markdown, not JSON
        saved_cfg = self.provider_cfg
        self.provider_cfg = {**saved_cfg, "supports_json_mode": False}
        try:
            updated_ckf = self._call_llm(system, user, hub).strip()
        finally:
            self.provider_cfg = saved_cfg

        if not updated_ckf:
            return hub

        # Update hub in-memory
        hub.context_skill = updated_ckf
        hub.mark_agent_run(self.name)
        hub.bump()

        # Persist to Supabase (non-fatal)
        _ctx_id = context_id or getattr(hub, "context_id", "")
        if _ctx_id:
            try:
                from core.project_store import save_context_skill
                save_context_skill(_ctx_id, updated_ckf)
            except Exception:
                pass  # persistence failure is non-fatal

        return hub
