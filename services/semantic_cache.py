# services/semantic_cache.py
# ─────────────────────────────────────────────────────────────────────────────
# SHA256-keyed LLM response cache stored in Supabase llm_cache table.
#
# Design:
#   - Cache stores the RAW LLM output (BEFORE PII desanitization).
#   - On cache hit, callers must apply desanitize(cached_raw, current_token_map)
#     to restore PII tokens correctly for the current session.
#   - This prevents PII leakage between sessions: two meetings with different
#     CPF/email values but identical structure share a cache entry, but each
#     session's token_map restores the correct PII for that session.
#   - Fail-open everywhere: any Supabase error returns None / is logged silently.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_TABLE = "llm_cache"

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_for_hash(text: str) -> str:
    """Collapse whitespace runs (spaces/tabs/newlines) to a single space and strip.

    Makes the exact-match cache tolerant to whitespace-only differences between
    otherwise identical prompts (re-pasted transcript with different line endings,
    extra blank lines, trailing spaces) without touching punctuation/wording —
    a real content change must still change the hash.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


class SemanticCache:

    @staticmethod
    def compute_hash(provider: str, model: str, system: str, safe_user: str) -> str:
        """SHA256 of (provider | model | system_prompt | sanitized_user_prompt).

        system/safe_user are whitespace-normalized before hashing (see
        _normalize_for_hash) so whitespace-only reprocessing still hits the cache.
        """
        key = (
            f"{provider}|{model}|"
            f"{_normalize_for_hash(system)}|{_normalize_for_hash(safe_user)}"
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def get(self, cache_hash: str) -> Optional[tuple[str, int]]:
        """
        Return (raw_llm_output, tokens_used) on cache hit, or None on miss/error.
        Handles TTL check client-side (also enforced by delete_expired_llm_cache()).
        Increments hit_count on a successful hit (fire-and-forget).
        """
        try:
            client = self._client()
            if client is None:
                return None
            resp = (
                client.table(_TABLE)
                .select("result, tokens_used, created_at, ttl_days, hit_count")
                .eq("hash", cache_hash)
                .limit(1)
                .execute()
            )
            if not resp.data:
                return None
            row = resp.data[0]

            # Client-side TTL check
            created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            ttl = timedelta(days=int(row.get("ttl_days") or 30))
            if datetime.now(timezone.utc) - created > ttl:
                try:
                    client.table(_TABLE).delete().eq("hash", cache_hash).execute()
                except Exception:
                    pass
                return None

            # Increment hit_count (non-critical, ignore failure)
            try:
                client.table(_TABLE).update(
                    {"hit_count": int(row.get("hit_count") or 1) + 1}
                ).eq("hash", cache_hash).execute()
            except Exception:
                pass

            result = row["result"]
            if not result:
                # Stale empty entry (from a previous failed API call) — purge and miss
                try:
                    client.table(_TABLE).delete().eq("hash", cache_hash).execute()
                except Exception:
                    pass
                return None
            return result, int(row.get("tokens_used") or 0)

        except Exception as exc:
            logger.debug("SemanticCache.get error (fail-open): %s", exc)
            return None

    def set(
        self,
        cache_hash: str,
        agent_name: str,
        raw_result: str,
        tokens: int,
        ttl_days: int = 30,
    ) -> None:
        """Store raw LLM output. Fail-open: logs and returns silently on any error."""
        try:
            client = self._client()
            if client is None:
                return
            client.table(_TABLE).upsert(
                {
                    "hash":        cache_hash,
                    "agent_name":  agent_name,
                    "result":      raw_result,
                    "tokens_used": tokens,
                    "ttl_days":    ttl_days,
                    "hit_count":   1,
                },
                on_conflict="hash",
            ).execute()
        except Exception as exc:
            logger.debug("SemanticCache.set error (fail-open): %s", exc)

    def invalidate(self, agent_name: Optional[str] = None) -> None:
        """Delete all cache entries, or entries for a specific agent. Fail-open."""
        try:
            client = self._client()
            if client is None:
                return
            q = client.table(_TABLE).delete()
            if agent_name:
                q = q.eq("agent_name", agent_name)
            else:
                # Delete all — use a condition that matches every row
                q = q.neq("hash", "")
            q.execute()
        except Exception as exc:
            logger.debug("SemanticCache.invalidate error (fail-open): %s", exc)

    def get_stats(self, agent_name: Optional[str] = None) -> dict:
        """
        Return aggregated cache statistics.

        Keys:
          total_entries      int  — distinct cache entries
          total_hits         int  — total cache hits across all entries
          total_tokens_saved int  — tokens avoided (tokens_used * hits per entry)
          by_agent           list[dict]  — per-agent breakdown, sorted by tokens_saved desc
            each dict: {agent, entries, hits, tokens_saved}
        """
        empty: dict = {
            "total_entries": 0,
            "total_hits": 0,
            "total_tokens_saved": 0,
            "by_agent": [],
        }
        try:
            client = self._client()
            if client is None:
                return empty
            q = client.table(_TABLE).select("agent_name, tokens_used, hit_count")
            if agent_name:
                q = q.eq("agent_name", agent_name)
            resp = q.execute()
            if not resp.data:
                return empty

            by_agent: dict[str, dict] = {}
            for row in resp.data:
                ag = row.get("agent_name") or "unknown"
                hits = max(0, int(row.get("hit_count") or 1) - 1)
                saved = int(row.get("tokens_used") or 0) * hits
                if ag not in by_agent:
                    by_agent[ag] = {"agent": ag, "entries": 0, "hits": 0, "tokens_saved": 0}
                by_agent[ag]["entries"] += 1
                by_agent[ag]["hits"] += hits
                by_agent[ag]["tokens_saved"] += saved

            rows = resp.data
            total_hits = sum(max(0, int(r.get("hit_count") or 1) - 1) for r in rows)
            total_saved = sum(
                int(r.get("tokens_used") or 0) * max(0, int(r.get("hit_count") or 1) - 1)
                for r in rows
            )
            return {
                "total_entries":      len(rows),
                "total_hits":         total_hits,
                "total_tokens_saved": total_saved,
                "by_agent": sorted(
                    by_agent.values(), key=lambda x: x["tokens_saved"], reverse=True
                ),
            }
        except Exception as exc:
            logger.debug("SemanticCache.get_stats error (fail-open): %s", exc)
            return empty

    @staticmethod
    def _client():
        try:
            from modules.supabase_client import get_supabase_client
            return get_supabase_client()
        except Exception:
            return None


# Module-level singleton — shared across all agent instances in a process.
_cache = SemanticCache()
