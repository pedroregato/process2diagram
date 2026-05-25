# agents/agent_cross_doc_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────
# CrossDocAnalyzerAgent — compares two library documents and their extracted
# artifacts, returning a structured relationship map + contradiction report.
#
# Not part of the pipeline. Called on-demand from DocumentManager.py.
# Returns a plain dict (not a modified KnowledgeHub).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
from typing import Optional

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub


# ── Artifact serializers ───────────────────────────────────────────────────────

def _fmt_requirements(reqs: list[dict]) -> str:
    if not reqs:
        return "(none)"
    lines = []
    for r in reqs[:40]:
        rid   = r.get("req_id") or r.get("id", "?")
        title = r.get("title", "")
        desc  = r.get("description", "")[:120]
        rtype = r.get("req_type", "")
        pri   = r.get("priority", "")
        lines.append(f"- {rid} [{rtype}/{pri}] {title}: {desc}")
    return "\n".join(lines)


def _fmt_sbvr_terms(terms: list[dict]) -> str:
    if not terms:
        return "(none)"
    return "\n".join(
        f"- {t.get('term', '?')}: {t.get('definition', '')[:100]}"
        for t in terms[:30]
    )


def _fmt_sbvr_rules(rules: list[dict]) -> str:
    if not rules:
        return "(none)"
    return "\n".join(
        f"- {r.get('rule_id') or r.get('id', '?')} [{r.get('rule_type', '')}]: {r.get('statement', '')[:120]}"
        for r in rules[:30]
    )


def _fmt_bmm(bmm: dict) -> str:
    if not bmm:
        return "(none)"
    parts = []
    for goals in bmm.get("goals", [])[:10]:
        parts.append(f"[Goal] {goals.get('id', '?')}: {goals.get('description', '')[:100]}")
    for s in bmm.get("strategies", [])[:10]:
        parts.append(f"[Strategy] {s.get('id', '?')}: {s.get('description', '')[:100]}")
    for p in bmm.get("policies", [])[:10]:
        parts.append(f"[Policy] {p.get('id', '?')}: {p.get('description', '')[:100]}")
    return "\n".join(parts) if parts else "(none)"


def _fmt_dmn(dmn_list: list[dict]) -> str:
    if not dmn_list:
        return "(none)"
    return "\n".join(
        f"- {d.get('decision_id') or d.get('id', '?')}: {d.get('name', '')} — {d.get('question', '')[:100]}"
        for d in dmn_list[:20]
    )


# ── Agent ──────────────────────────────────────────────────────────────────────

class CrossDocAnalyzerAgent(BaseAgent):
    """
    Compares two documents from the library.

    Usage:
        agent = CrossDocAnalyzerAgent(client_info, provider_cfg)
        result = agent.analyze(doc_a_info, doc_b_info, output_language)

    doc_a_info / doc_b_info structure:
        {
            "id":           str,
            "title":        str,
            "content":      str,   # full content_text
            "requirements": list[dict],
            "sbvr_terms":   list[dict],
            "sbvr_rules":   list[dict],
            "bmm":          dict,  # {"goals": [...], "strategies": [...], "policies": [...]}
            "dmn":          list[dict],
        }
    """

    name       = "cross_doc_analyzer"
    skill_path = "skills/skill_cross_doc_analyzer.md"

    # stubs — this agent does not use the hub pipeline
    def run(self, hub: KnowledgeHub) -> KnowledgeHub:            # type: ignore[override]
        raise NotImplementedError("Use analyze() instead.")

    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:  # type: ignore[override]
        raise NotImplementedError("Use analyze() instead.")

    # ── Main entry point ───────────────────────────────────────────────────────

    def analyze(
        self,
        doc_a: dict,
        doc_b: dict,
        output_language: str = "Auto-detect",
    ) -> dict:
        """
        Run cross-document analysis.

        Returns the parsed JSON dict from the LLM or an error dict.
        """
        system = self._load_skill()
        user   = self._build_user_prompt(doc_a, doc_b, output_language)

        try:
            raw = self._call_llm_raw(system, user)
            return self._parse_json(raw)
        except Exception as exc:
            return {
                "error": str(exc),
                "alignment_score": 0,
                "summary": "Análise não disponível devido a erro.",
                "relationships": [],
                "contradictions": [],
                "gaps": {"only_in_a": [], "only_in_b": []},
            }

    # ── Prompt builder ─────────────────────────────────────────────────────────

    def _build_user_prompt(self, doc_a: dict, doc_b: dict, output_language: str) -> str:
        lang_instruction = (
            "Respond in Brazilian Portuguese."
            if output_language in ("Auto-detect", "Português (Brasil)")
            else f"Respond in {output_language}."
        )

        def _block(doc: dict, label: str) -> str:
            content_preview = (doc.get("content") or "")[:4000]
            return (
                f"## {label}: {doc['title']}\n\n"
                f"### Content preview (first 4000 chars)\n{content_preview}\n\n"
                f"### Requirements\n{_fmt_requirements(doc.get('requirements', []))}\n\n"
                f"### SBVR Terms\n{_fmt_sbvr_terms(doc.get('sbvr_terms', []))}\n\n"
                f"### SBVR Rules\n{_fmt_sbvr_rules(doc.get('sbvr_rules', []))}\n\n"
                f"### BMM\n{_fmt_bmm(doc.get('bmm', {}))}\n\n"
                f"### DMN Decisions\n{_fmt_dmn(doc.get('dmn', []))}\n"
            )

        return (
            f"{lang_instruction}\n\n"
            + _block(doc_a, "DOCUMENT A")
            + "\n---\n\n"
            + _block(doc_b, "DOCUMENT B")
            + "\n\nPerform the cross-document analysis as specified. Return only the JSON object."
        )

    # ── Low-level LLM call (bypasses hub pipeline) ─────────────────────────────

    def _call_llm_raw(self, system: str, user: str) -> str:
        """Direct LLM call returning raw string."""
        client_type = self.provider_cfg.get("client_type", "openai_compatible")
        api_key     = self.client_info.get("api_key", "")
        model       = self.provider_cfg.get("default_model", "")
        max_tokens  = self.provider_cfg.get("max_tokens", 4096)

        if client_type == "anthropic":
            import anthropic
            ac  = anthropic.Anthropic(api_key=api_key)
            msg = ac.messages.create(
                model=model, max_tokens=max_tokens,
                system=system + "\n\nRespond with valid JSON only.",
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))
        kwargs: dict = dict(
            model=model,
            messages=[
                {"role": "system", "content": system + "\n\nRespond with valid JSON only."},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_tokens,
        )
        if self.provider_cfg.get("supports_json_mode"):
            kwargs["response_format"] = {"type": "json_object"}
        if not self.provider_cfg.get("reasoning_effort") and "deepseek-v4" not in model.lower():
            kwargs["temperature"] = 0.2
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
