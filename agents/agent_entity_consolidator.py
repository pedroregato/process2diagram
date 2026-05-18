# agents/agent_entity_consolidator.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentEntityConsolidator — identifica e funde entidades duplicadas no
# Knowledge Hub usando LLM + regras determinísticas.
#
# Duplicatas surgem porque o mesmo objeto real pode ser extraído com nomes
# ligeiramente diferentes em reuniões distintas (variações de ASR, abreviações,
# nomes completos vs. parciais, classificações de tipo conflitantes).
#
# Dois passos:
#   1. LLM analisa todas as entidades e retorna grupos de merge
#   2. Python executa os merges via knowledge_store.merge_entities()
#
# Sempre não-fatal: exceções são logadas mas não propagam para o chamador.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent

_log = logging.getLogger(__name__)

# Max entities sent to LLM per call to stay inside context window
_BATCH_SIZE = 80


class AgentEntityConsolidator(BaseAgent):
    """
    Detects and merges duplicate entities in kh_entities for a given project.

    Usage:
        agent = AgentEntityConsolidator(client_info, provider_cfg)
        stats = agent.consolidate(project_id)
        # stats = {"groups_found": N, "merges_done": N, "entities_removed": N}
    """

    name       = "entity_consolidator"
    skill_path = "skills/skill_entity_consolidator.md"

    def consolidate(self, project_id: str) -> dict:
        """
        Run full consolidation for the project.
        Returns stats dict. Never raises.
        """
        try:
            return self._run(project_id)
        except Exception as exc:
            _log.error("AgentEntityConsolidator.consolidate failed: %s", exc)
            return {"groups_found": 0, "merges_done": 0, "entities_removed": 0, "error": str(exc)}

    def _run(self, project_id: str) -> dict:
        from core.knowledge_store import get_entities, merge_entities

        entities = get_entities(project_id, limit=500)
        if len(entities) < 2:
            return {"groups_found": 0, "merges_done": 0, "entities_removed": 0}

        system = self._skill

        # Send in batches if too many entities
        all_groups: list[dict] = []
        for i in range(0, len(entities), _BATCH_SIZE):
            batch = entities[i: i + _BATCH_SIZE]
            groups = self._call_llm_for_groups(system, batch)
            all_groups.extend(groups)

        # Deduplicate: an entity id should appear in at most one merge group
        seen_ids: set[str] = set()
        clean_groups: list[dict] = []
        for g in all_groups:
            keep  = g.get("keep_id", "")
            disc  = [d for d in (g.get("discard_ids") or []) if d not in seen_ids and d != keep]
            if not disc or keep in seen_ids:
                continue
            clean_groups.append({**g, "discard_ids": disc})
            seen_ids.add(keep)
            seen_ids.update(disc)

        merges_done      = 0
        entities_removed = 0

        for g in clean_groups:
            keep_id     = g["keep_id"]
            discard_ids = g["discard_ids"]
            ok = merge_entities(project_id, keep_id, discard_ids)
            if ok:
                merges_done      += 1
                entities_removed += len(discard_ids)
                _log.info(
                    "Consolidated '%s' ← %d duplicate(s): %s",
                    g.get("keep_name", keep_id), len(discard_ids),
                    g.get("reason", ""),
                )

        _log.info(
            "AgentEntityConsolidator: %d group(s), %d merge(s), %d removed",
            len(clean_groups), merges_done, entities_removed,
        )
        return {
            "groups_found":    len(clean_groups),
            "merges_done":     merges_done,
            "entities_removed": entities_removed,
        }

    def _call_llm_for_groups(self, system: str, entities: list[dict]) -> list[dict]:
        """Call LLM with a batch of entities, return merge groups."""
        entity_list = [
            {
                "id":               e["id"],
                "canonical_name":   e.get("canonical_name"),
                "entity_type":      e.get("entity_type"),
                "occurrence_count": e.get("occurrence_count", 1),
                "aliases":          (e.get("aliases") or [])[:8],
            }
            for e in entities
        ]
        user = (
            "Analise as entidades abaixo e identifique duplicatas a consolidar.\n\n"
            f"```json\n{json.dumps(entity_list, ensure_ascii=False, indent=2)}\n```"
        )

        from core.knowledge_hub import KnowledgeHub
        stub = KnowledgeHub()
        try:
            data = self._call_with_retry(system, user, stub)
            return data.get("merge_groups") or []
        except Exception as exc:
            _log.error("AgentEntityConsolidator LLM call failed: %s", exc)
            return []

    # ── BaseAgent ABC stubs ───────────────────────────────────────────────────

    def build_prompt(self, hub: Any, output_language: str = "Auto-detect"):
        return self._skill, ""

    def run(self, hub: Any, output_language: str = "Auto-detect") -> Any:
        return hub
