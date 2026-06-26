# agents/agent_bpmn.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Agent — expert em BPMN 2.0 (OMG / ISO-IEC 19510).
#
# Reads:  hub.transcript_clean, hub.nlp (actors, segments)
# Writes: hub.bpmn  (BPMNModel — steps, edges, lanes, mermaid,
#                                bpmn_xml via bpmn_generator)
#
# Supports two LLM output formats:
#   Flat  (single-pool): { "name", "steps", "edges", "lanes" }
#   Multi-pool:          { "name", "pools": [...], "message_flows": [...] }
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re as _re
import unicodedata as _ud

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub, BPMNModel, BPMNStep, BPMNEdge,
    BPMNPoolData, BPMNMessageFlow,
)


def _ascii_id(s: str) -> str:
    """Normalize a string to a safe ASCII XML id segment."""
    nfkd = _ud.normalize("NFKD", s)
    return "".join(c for c in nfkd if _ud.category(c) != "Mn").lower().replace(" ", "_")


def _infer_lane_name(generic_name: str, model: BPMNModel,
                     nlp_actors: list | None = None) -> str:
    """
    Infer a real organizational lane name from three sources, in priority order:

    Priority 1 — step.actor fields for steps in the generic lane.
        If a step already has a non-generic actor assigned by the LLM, that
        actor is the most direct answer.  Prefer NLP-normalized form when
        there is a close match.

    Priority 2 — NLP actors that appear verbatim in step texts for this lane.
        Uses hub.nlp.actors (named entities detected before the LLM call).

    Priority 3 — regex over step titles/descriptions (original heuristic).
    """
    from collections import Counter

    _GENERIC_SET = {
        "usuário", "usuario", "user", "utilizador",
        "validador", "validator", "revisor", "reviewer",
        "sistema", "system", "automático", "automatic",
        "ator", "actor", "papel", "role", "pessoa", "person",
        "participante", "participant",
    }

    # ── Priority 1: step actor fields ────────────────────────────────────────
    actor_candidates = [
        s.actor for s in model.steps
        if s.lane == generic_name
        and s.actor
        and s.actor.lower().strip() not in _GENERIC_SET
    ]
    if actor_candidates:
        best = Counter(actor_candidates).most_common(1)[0][0]
        if nlp_actors:
            for nlp_actor in nlp_actors:
                if (nlp_actor.lower() in best.lower()
                        or best.lower() in nlp_actor.lower()):
                    return nlp_actor   # prefer NLP-normalized form
        return best

    # ── Priority 2: NLP actors appearing in step texts ───────────────────────
    if nlp_actors:
        lane_text = " ".join(
            (s.title or "") + " " + (s.description or "")
            for s in model.steps if s.lane == generic_name
        )
        nlp_hits = Counter(a for a in nlp_actors if a in lane_text)
        if nlp_hits:
            return nlp_hits.most_common(1)[0][0]

    # ── Priority 3: regex heuristic (original) ───────────────────────────────
    texts = []
    for step in model.steps:
        if step.lane == generic_name:
            texts.append(step.title)
            texts.append(step.description)
    combined = " ".join(texts)

    org_patterns = [
        r'\b(Equipe\s+de\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+(?:\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+)*)\b',
        r'\b(Gestores?\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+(?:\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+)*)\b',
        r'\b([A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+(?:\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+){1,3})\b',
    ]
    _STOP_WORDS = {
        "cadastrar", "cadastro", "enviar", "validar", "processar",
        "organograma", "escola", "unidade", "após", "para", "com",
        "início", "iniciar", "ajustar", "devolvido",
    }
    candidates: list[str] = []
    for pattern in org_patterns:
        for match in _re.finditer(pattern, combined):
            phrase = match.group(1).strip()
            words = phrase.lower().split()
            if any(w in _STOP_WORDS for w in words):
                continue
            if 2 <= len(phrase.split()) <= 4:
                candidates.append(phrase)
    if candidates:
        return Counter(candidates).most_common(1)[0][0]

    return generic_name


# ── Event task_type constants ─────────────────────────────────────────────────

# New event task_types introduced in skill v3.0 that map to BPMN element types.
_EVENT_TASK_TYPE_MAP: dict[str, tuple[str, str]] = {
    "noneStartEvent":               ("startEvent",             "none"),
    "startMessageEvent":            ("startEvent",             "message"),
    "startTimerEvent":              ("startEvent",             "timer"),
    "noneEndEvent":                 ("endEvent",               "none"),
    "endMessageEvent":              ("endEvent",               "message"),
    "errorEndEvent":                ("endEvent",               "error"),
    "intermediateTimerCatchEvent":  ("intermediateCatchEvent", "timer"),
    "intermediateMessageCatchEvent":("intermediateCatchEvent", "message"),
    "intermediateMessageThrowEvent":("intermediateThrowEvent", "message"),
    # Legacy / generic event types that the LLM still sometimes emits
    "startEvent":                   ("startEvent",             "none"),
    "endEvent":                     ("endEvent",               "none"),
    "start":                        ("startEvent",             "none"),
    "end":                          ("endEvent",               "none"),
}

# task_types that represent start events (generator adds its own for single-pool)
_START_TYPES = {"noneStartEvent", "startMessageEvent", "startTimerEvent", "startEvent", "start"}
# task_types that represent end events
_END_TYPES   = {"noneEndEvent", "endMessageEvent", "errorEndEvent", "endEvent", "end"}

_TASK_TYPE_MAP = {
    # Standard tasks
    "userTask":          "userTask",
    "serviceTask":       "serviceTask",
    "scriptTask":        "scriptTask",
    "manualTask":        "manualTask",
    "businessRuleTask":  "businessRuleTask",
    "sendTask":          "sendTask",
    "receiveTask":       "receiveTask",
    # Hierarchical (Silver Level 1) — generator renders as callActivity with double border
    "callActivity":      "callActivity",
    # Iteration markers — PC27b will add loop/MI XML markers; render as userTask for now
    "loopTask":          "userTask",
    "multiInstanceTask": "userTask",
    # Boundary events — PC27b will anchor to task boundary; render as userTask for now
    "boundaryTimerEvent": "userTask",
    "boundaryErrorEvent": "userTask",
    # Gateways
    "parallelGateway":   "parallelGateway",
    "exclusiveGateway":  "exclusiveGateway",
    "inclusiveGateway":  "inclusiveGateway",
    "eventBasedGateway": "eventBasedGateway",
    "complexGateway":    "complexGateway",
}


class AgentBPMN(BaseAgent):

    name = "bpmn"
    skill_path = "skills/skill_bpmn.md"
    # Collaboration BPMN JSON with multiple pools can exceed 4096 output tokens.
    # Guarantee at least 8192 regardless of long-context mode.
    _min_output_tokens: int = 8192

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        if getattr(hub, "context_skill", "").strip():
            system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill.strip()}"

        if getattr(hub, "context_files_text", "").strip():
            system += f"\n\n## Documentos de Referência do Contexto\n\n{hub.context_files_text.strip()}"

        actor_hint = ""
        if hub.nlp.actors:
            actor_hint = f"\nActors identified by NLP pre-processing: {', '.join(hub.nlp.actors)}"

        user = (
            f"Extract the BPMN 2.0 process from this transcript:{actor_hint}\n\n"
            f"{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)

        # ── Proactive collaboration detection ─────────────────────────────────
        # Uses two independent signals: NLP actors (structured) + keyword scan.
        # When either fires, we inject a mandatory format directive into the
        # system prompt AND adjust retry hints to never offer flat format.
        _COLLAB_KEYWORDS = {
            "cliente", "fornecedor", "banco", "bureau", "serasa", "quod",
            "receita federal", "parceiro", "portal do cliente", "externo",
            "contratante", "contratado", "prestador", "tomador",
        }
        _transcript_lower = (hub.transcript_clean or "").lower()
        _kw_hits = sum(1 for kw in _COLLAB_KEYWORDS if kw in _transcript_lower)
        _nlp_orgs = len(hub.nlp.actors) if (hub.nlp and hub.nlp.actors) else 0
        _collaboration_expected = _nlp_orgs >= 2 or _kw_hits >= 2

        if _collaboration_expected:
            system += (
                "\n\n## MANDATORY FORMAT — COLLABORATION\n\n"
                "This transcript involves legally distinct organisations exchanging messages. "
                "You MUST use the multi-pool collaboration format:\n"
                "{\"name\": \"...\", \"pools\": ["
                "{\"id\": \"pool_1\", \"name\": \"Organisation A\", "
                "\"steps\": [...], \"edges\": [...], \"lanes\": [...]}, "
                "{\"id\": \"pool_2\", \"name\": \"Organisation B\", "
                "\"steps\": [...], \"edges\": [...], \"lanes\": [...]}], "
                "\"message_flows\": [{\"id\": \"mf_1\", \"name\": \"...\", "
                "\"source\": {\"pool\": \"pool_1\", \"step\": \"S01\"}, "
                "\"target\": {\"pool\": \"pool_2\", \"step\": \"S01\"}}]}\n"
                "NEVER use flat format (steps/edges/lanes at root level) "
                "when the process involves multiple organisations."
            )

        # ── Retry hints — separated by error type ────────────────────────────
        # _flat_hint  : JSON parse errors (KeyError / malformed structure).
        #               Offers flat format only when collaboration is NOT expected.
        # _semantic_hint: semantic validation errors (ValueError — edges missing).
        #               Preserves multi-pool structure; names the failing pool.
        _flat_hint = (
            "\n\nIMPORTANT CORRECTION: Your previous response was truncated or malformed. "
            "Return ONLY valid JSON. "
            + (
                "This transcript involves multiple organisations — you MUST use the "
                "multi-pool collaboration format: "
                "{\"name\": ..., \"pools\": [...], \"message_flows\": [...]}. "
                "NEVER switch to flat format."
                if _collaboration_expected else
                "If all participants belong to the same organisation → flat format: "
                "{\"name\": ..., \"steps\": [...], \"edges\": [...], \"lanes\": [...]}. "
                "If there are legally distinct organisations → pools format: "
                "{\"name\": ..., \"pools\": [...], \"message_flows\": [...]}. "
                "Choose the correct format based on the transcript — do NOT default to flat."
            )
        )

        _original_ensure_utf8 = self._ensure_utf8

        def _bpmn_call_with_retry(system, user, hub):
            parse = self._parse_json
            last_error = None
            _h0 = None  # hash of attempt-0 prompt; backfilled on successful retry
            for attempt in range(1 + self.max_retries):
                try:
                    raw = self._call_llm(system, user, hub)
                    result = parse(raw)
                    # Semantic validation: steps without edges is an incomplete extraction.
                    # Pools format: check each pool; flat format: check top-level.
                    # Only enforce when there are > 2 steps (trivial processes may have no edges).
                    _pools = result.get("pools") if isinstance(result, dict) else None
                    if _pools:
                        # Helper: steps/edges may be nested under pool["process"]
                        # (code expects that sub-key per docstring) OR at the top level
                        # of the pool dict (as taught in skill examples).
                        # Validation must check both to avoid a silent blind spot.
                        def _pf(p, key):
                            top = p.get(key) or []
                            if not top:
                                _sub = p.get("process")
                                if isinstance(_sub, dict):
                                    top = _sub.get(key) or []
                            return top
                        _total_steps = sum(len(_pf(p, "steps")) for p in _pools)
                        _total_edges = sum(len(_pf(p, "edges")) for p in _pools)
                        # Per-pool check: a pool with steps but no edges is incomplete
                        # even if other pools have edges (aggregate check misses this).
                        for _p in _pools:
                            _p_steps = len(_pf(_p, "steps"))
                            _p_edges = len(_pf(_p, "edges"))
                            if _p_steps > 2 and _p_edges == 0:
                                raise ValueError(
                                    f"Incomplete BPMN: pool '{_p.get('name', '?')}' has "
                                    f"{_p_steps} steps but 0 edges — sequence flows missing."
                                )
                    else:
                        _total_steps = len(result.get("steps") or []) if isinstance(result, dict) else 0
                        _total_edges = len(result.get("edges") or []) if isinstance(result, dict) else 0
                    if _total_steps > 2 and _total_edges == 0:
                        raise ValueError(
                            f"Incomplete BPMN: {_total_steps} steps but 0 edges — "
                            "all sequence flows are missing."
                        )
                    # Message flow coverage: every endMessageEvent and sendTask must
                    # have a corresponding outgoing message_flow entry.
                    # An endMessageEvent without a message_flow is a "silent" event —
                    # it sends nothing and breaks choreography between pools.
                    if _pools:
                        _mf_list = result.get("message_flows") or []
                        _mf_sources = {
                            (mf.get("source", {}).get("pool"),
                             mf.get("source", {}).get("step"))
                            for mf in _mf_list
                            if isinstance(mf, dict)
                            and isinstance(mf.get("source"), dict)
                        }
                        _orphaned = []
                        for _p in _pools:
                            _p_id = _p.get("id", "")
                            for _s in (_p.get("steps") or []):
                                _tt = _s.get("task_type", "")
                                if _tt in ("endMessageEvent", "sendTask"):
                                    if (_p_id, _s.get("id")) not in _mf_sources:
                                        _orphaned.append(
                                            f"'{_s.get('title', _s.get('id', '?'))}'"
                                            f" ({_tt}) in pool"
                                            f" '{_p.get('name', _p_id)}'"
                                        )
                        if _orphaned:
                            raise ValueError(
                                "Incomplete BPMN: the following message-sending elements "
                                "have no outgoing message_flow — add them to "
                                "`message_flows`: " + "; ".join(_orphaned)
                            )
                    # Linha B: retry succeeded — backfill H0 so future reruns hit cache
                    if attempt > 0 and _h0 and not getattr(self, "_lg_skip_cache", False):
                        self._backfill_cache(_h0, raw)
                    return result
                except (ValueError, KeyError) as exc:
                    last_error = exc
                    if attempt == 0:
                        _h0 = getattr(self, "_last_computed_cache_hash", None)
                    if attempt < self.max_retries:
                        hint = repr(str(exc))[:300]
                        # ── Hint selection by error type ──────────────────────
                        # ValueError = semantic validation (incomplete content).
                        #   → preserve format, pinpoint the specific problem.
                        # KeyError   = JSON parse / structure mismatch.
                        #   → may need format guidance → use _flat_hint.
                        if isinstance(exc, ValueError):
                            _retry_suffix = (
                                "\n\nCRITICAL CORRECTION REQUIRED: The JSON was parsed "
                                "successfully but the content is INCOMPLETE. "
                                + (
                                    "DO NOT change to flat format — keep the multi-pool "
                                    "collaboration structure. "
                                    if _collaboration_expected else ""
                                )
                                + "Fix the specific problem described above: "
                                + str(exc)
                                + " Ensure EVERY pool has sequence flows (edges) "
                                "connecting ALL its steps in order."
                            )
                        else:
                            _retry_suffix = _flat_hint
                        user = _original_ensure_utf8(
                            f"{user}\n\n"
                            f"IMPORTANT: Your previous response caused a parse error:\n{hint}\n"
                            f"Return ONLY valid JSON. No markdown. No explanation."
                            f"{_retry_suffix}"
                        )
            raise RuntimeError(
                f"[{self.name}] Failed after {1 + self.max_retries} attempts. "
                f"Last error: {repr(last_error)}"
            )

        import time as _time
        import logging as _logging
        _t0 = _time.monotonic()

        data = _bpmn_call_with_retry(system, user, hub)

        hub.bpmn = self._build_model(data)
        hub.bpmn.raw_llm_dict = data  # preserved for rerun-without-LLM

        # ── Format escape detection ───────────────────────────────────────────
        # If collaboration was expected but the LLM returned flat format, log it.
        _format_escape = _collaboration_expected and not hub.bpmn.is_collaboration
        if _format_escape:
            _logging.warning(
                "[AgentBPMN] Format escape detected: collaboration expected "
                "(nlp_actors=%d, kw_hits=%d) but LLM returned flat format.",
                _nlp_orgs, _kw_hits,
            )

        # Capture enforce_rules changes via before/after step count as proxy
        _steps_before = len(hub.bpmn.steps)
        self._enforce_rules(hub.bpmn, getattr(hub.nlp, "actors", None))
        _steps_after = len(hub.bpmn.steps)

        try:
            from modules.bpmn_auto_repair import repair_bpmn
            report = repair_bpmn(hub.bpmn)
            hub.bpmn.repair_log = report.repairs
        except Exception:
            hub.bpmn.repair_log = []
        try:
            hub.bpmn.mermaid = self._generate_mermaid(hub.bpmn)
        except Exception:
            hub.bpmn.mermaid = ""
        hub.bpmn.bpmn_xml = self._generate_bpmn_xml(hub.bpmn)
        from modules.bpmn_auto_repair import reformat_bpmn_labels
        _xml_fmt, _fmt_changes = reformat_bpmn_labels(hub.bpmn.bpmn_xml)
        if not any(c.startswith("[ERRO]") for c in _fmt_changes):
            hub.bpmn.bpmn_xml = _xml_fmt

        # ── Build execution log ───────────────────────────────────────────────
        from datetime import datetime as _dt, timezone as _tz
        _long_titles = [
            s.title for s in hub.bpmn.steps if len(s.title) > 35
        ]
        _type_counts: dict = {}
        for _s in hub.bpmn.steps:
            _type_counts[_s.task_type] = _type_counts.get(_s.task_type, 0) + 1
        hub.bpmn.execution_log = {
            "generated_at": _dt.now(_tz.utc).isoformat(),
            "source": "llm_call",
            "llm": {
                "provider": hub.meta.llm_provider or "",
                "model":    hub.meta.llm_model or "",
                "tokens_in":  hub.meta.total_tokens_used,
                "from_cache": hub.meta.cache_hits > 0,
                "cache_hits": hub.meta.cache_hits,
                "latency_s":  round(_time.monotonic() - _t0, 1),
            },
            "enforce_rules": {
                "steps_before": _steps_before,
                "steps_after":  _steps_after,
                "removed": _steps_before - _steps_after,
            },
            "repair_passes": hub.bpmn.repair_log,
            "reformat_passes": _fmt_changes,
            "collaboration": {
                "expected": _collaboration_expected,
                "nlp_actors": _nlp_orgs,
                "keyword_hits": _kw_hits,
                "format_escape": _format_escape,
            },
            "metrics": {
                "steps":       len(hub.bpmn.steps),
                "edges":       len(hub.bpmn.edges),
                "lanes":       len(hub.bpmn.lanes),
                "gateways":    sum(1 for s in hub.bpmn.steps if s.is_decision),
                "task_types":  _type_counts,
                "long_titles": _long_titles,
            },
        }
        hub.bpmn.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> BPMNModel:
        """Dispatch to flat or multi-pool builder based on JSON structure."""
        if not isinstance(data, dict):
            return BPMNModel(name="Process")
        pools_val = data.get("pools")
        # Use multi-pool only when "pools" is a non-empty list of dicts
        if isinstance(pools_val, list) and pools_val and isinstance(pools_val[0], dict):
            return AgentBPMN._build_model_multi(data)
        return AgentBPMN._build_model_flat(data)

    @staticmethod
    def _build_model_flat(data: dict) -> BPMNModel:
        """Parse flat single-pool format: { steps, edges, lanes }."""
        steps = [
            BPMNStep(
                id=s["id"],
                title=s.get("title", "Step"),
                description=s.get("description", ""),
                actor=s.get("actor") or None,
                is_decision=s.get("is_decision", False),
                task_type=s.get("task_type", "userTask"),
                lane=s.get("lane") or None,
            )
            for s in data.get("steps", [])
        ]
        edges = [
            BPMNEdge(
                source=e["source"],
                target=e["target"],
                label=e.get("label", ""),
                condition=e.get("condition", ""),
            )
            for e in data.get("edges", [])
        ]
        lanes = data.get("lanes") or []
        if not lanes:
            # Derive from per-step lane assignments when the LLM omits the top-level list
            lanes = sorted({s.lane for s in steps if s.lane})
        return BPMNModel(
            name=data.get("name", "Process"),
            description=data.get("description", ""),
            steps=steps,
            edges=edges,
            lanes=lanes,
            process_trigger=(data.get("process_trigger") or "").strip(),
            process_outcomes=[
                o.strip() for o in (data.get("process_outcomes") or [])
                if isinstance(o, str) and o.strip()
            ],
        )

    @staticmethod
    def _build_model_multi(data: dict) -> BPMNModel:
        """
        Parse multi-pool format:
          { "name", "pools": [{ "id", "name", "process": { steps, edges, lanes } }],
            "message_flows": [{ "id", "name", "source": {pool,step}, "target": {pool,step} }] }

        Step IDs are namespaced with a pool prefix (p1_, p2_...) in the
        flattened model.steps/edges so that enforce_rules works across pools
        without ID collisions.
        """
        pool_models: list[BPMNPoolData] = []
        all_steps:  list[BPMNStep] = []
        all_edges:  list[BPMNEdge] = []
        all_lanes:  list[str] = []

        for i, pool_data in enumerate(data.get("pools", [])):
            if not isinstance(pool_data, dict):
                continue   # skip malformed pool entries
            prefix   = f"p{i + 1}_"
            pool_id  = pool_data.get("id", f"pool_{i + 1}")
            pool_name = pool_data.get("name", f"Pool {i + 1}")
            # Steps/edges may be nested under pool["process"] (expected by code)
            # OR at the top level of the pool dict (as taught in skill examples).
            # Read from "process" first; fall back to top-level pool fields so that
            # both LLM output styles are handled without losing data.
            _proc_sub = pool_data.get("process")
            proc = _proc_sub if isinstance(_proc_sub, dict) else {}

            raw_steps = proc.get("steps") or pool_data.get("steps") or []
            raw_edges = proc.get("edges") or pool_data.get("edges") or []
            raw_lanes = proc.get("lanes") or pool_data.get("lanes") or []

            orig_steps = [
                BPMNStep(
                    id=s["id"],
                    title=s.get("title", "Step"),
                    description=s.get("description", ""),
                    actor=s.get("actor") or None,
                    is_decision=s.get("is_decision", False),
                    task_type=s.get("task_type", "userTask"),
                    lane=s.get("lane") or None,
                )
                for s in raw_steps
            ]
            orig_edges = [
                BPMNEdge(
                    source=e["source"],
                    target=e["target"],
                    label=e.get("label", ""),
                    condition=e.get("condition", ""),
                )
                for e in raw_edges
            ]

            pool_models.append(BPMNPoolData(
                pool_id=pool_id,
                name=pool_name,
                steps=orig_steps,
                edges=orig_edges,
                lanes=list(raw_lanes),
            ))

            # Flatten into model with prefixed IDs
            for s in orig_steps:
                all_steps.append(BPMNStep(
                    id=prefix + s.id,
                    title=s.title,
                    description=s.description,
                    actor=s.actor,
                    is_decision=s.is_decision,
                    task_type=s.task_type,
                    lane=s.lane,
                ))
            for e in orig_edges:
                all_edges.append(BPMNEdge(
                    source=prefix + e.source,
                    target=prefix + e.target,
                    label=e.label,
                    condition=e.condition,
                ))
            for lane_name in raw_lanes:
                if lane_name not in all_lanes:
                    all_lanes.append(lane_name)

        # Message flows
        mf_list: list[BPMNMessageFlow] = []
        for mf in data.get("message_flows", []):
            src = mf.get("source", {})
            tgt = mf.get("target", {})
            mf_list.append(BPMNMessageFlow(
                id=mf.get("id", f"mf_{len(mf_list) + 1}"),
                source_pool=src.get("pool", ""),
                source_step=src.get("step", ""),
                target_pool=tgt.get("pool", ""),
                target_step=tgt.get("step", ""),
                name=mf.get("name", ""),
            ))

        return BPMNModel(
            name=data.get("name", "Process"),
            description=data.get("description", ""),
            steps=all_steps,
            edges=all_edges,
            lanes=all_lanes,
            is_collaboration=True,
            pool_models=pool_models,
            message_flows_data=mf_list,
        )

    # ── Post-extraction rule enforcement ─────────────────────────────────────

    @staticmethod
    def _enforce_rules(model: BPMNModel, nlp_actors: list | None = None) -> None:
        """
        Deterministic post-processing. Mutates the model in-place.

        Rule 0  — remove steps the LLM declared as start/end events
                  (single-pool only; multi-pool handles events explicitly)
        Rule 1  — serviceTask with unnamed system actor → lane = None
        Rule 1b — generic lane names → infer from step descriptions
        Rule 2  — correction loop pointing back to gateway → redirect to
                  the upstream work step that feeds the gateway
        Rule 3  — remove empty lanes (lanes with 0 steps assigned); runs
                  after Rules 1/1b so vacated lanes are also pruned
        """
        # ── Rule 0: strip redundant start/end event steps (single-pool) ──────
        if not model.is_collaboration:
            _start_steps = [s for s in model.steps if s.task_type in _START_TYPES]
            _end_steps   = [s for s in model.steps if s.task_type in _END_TYPES]

            # Capture meaningful names before stripping (only if not already set by JSON parse)
            _generic_start = {"início", "inicio", "start", "begin", "iniciar"}
            _generic_end   = {"fim", "end", "finish", "término", "termino", "encerrar"}
            if _start_steps and not model.process_trigger:
                _t = (_start_steps[0].title or "").strip()
                if _t and _t.lower() not in _generic_start:
                    model.process_trigger = _t
            if _end_steps and not model.process_outcomes:
                _outcomes = [
                    s.title.strip() for s in _end_steps
                    if s.title and s.title.strip().lower() not in _generic_end
                ]
                if _outcomes:
                    model.process_outcomes = _outcomes

            event_step_ids = {s.id for s in _start_steps + _end_steps}
            if event_step_ids:
                model.steps = [s for s in model.steps if s.id not in event_step_ids]
                model.edges = [
                    e for e in model.edges
                    if e.source not in event_step_ids and e.target not in event_step_ids
                ]

        # ── Rule 1b: generic lane names → infer from step descriptions ───────
        _GENERIC_LANE_NAMES = {
            "usuário", "usuario", "user", "utilizador",
            "validador", "validator", "revisor", "reviewer",
            "sistema", "system", "automático", "automatic",
            "ator", "actor", "papel", "role", "pessoa", "person",
            "participante", "participant",
        }
        lane_replacement: dict[str, str] = {}
        for lane_name in list(model.lanes):
            if lane_name.lower().strip() in _GENERIC_LANE_NAMES:
                candidate = _infer_lane_name(lane_name, model, nlp_actors)
                if candidate and candidate != lane_name:
                    lane_replacement[lane_name] = candidate

        if lane_replacement:
            model.lanes = [lane_replacement.get(ln, ln) for ln in model.lanes]
            for step in model.steps:
                if step.lane in lane_replacement:
                    step.lane = lane_replacement[step.lane]
            for pm in model.pool_models:
                pm.lanes = [lane_replacement.get(ln, ln) for ln in pm.lanes]
                for step in pm.steps:
                    if step.lane in lane_replacement:
                        step.lane = lane_replacement[step.lane]

        _GENERIC_ACTORS = {
            "sistema", "system", "automático", "automatic",
            "automaticamente", "auto", None,
        }

        step_map = {s.id: s for s in model.steps}

        # ── Rule 1: serviceTask with unnamed system → lane = None ─────────────
        # (runs before Rule 3 so that lanes vacated by Rule 1 are also removed)
        for step in model.steps:
            if step.task_type == "serviceTask":
                actor_lower = (step.actor or "").lower().strip()
                if actor_lower in _GENERIC_ACTORS or not actor_lower:
                    step.lane = None

        # ── Rule 2: correction loop pointing back to a gateway ────────────────
        # (no change in order — runs after Rule 1)
        outgoing: dict[str, list] = {s.id: [] for s in model.steps}
        for edge in model.edges:
            if edge.source in outgoing:
                outgoing[edge.source].append(edge)

        incoming: dict[str, list[str]] = {s.id: [] for s in model.steps}
        for edge in model.edges:
            if edge.target in incoming:
                incoming[edge.target].append(edge.source)

        _ALL_GW_TYPES = {
            "exclusiveGateway", "parallelGateway", "inclusiveGateway",
            "eventBasedGateway", "complexGateway", "gateway",
        }
        gateway_ids = {
            s.id for s in model.steps
            if s.is_decision or s.task_type in _ALL_GW_TYPES
        }

        for edge in model.edges:
            if edge.target not in gateway_ids:
                continue

            gw_id         = edge.target
            correction_id = edge.source
            gw_step        = step_map.get(gw_id)
            correction_step = step_map.get(correction_id)
            if not gw_step or not correction_step:
                continue

            gw_out_targets = {e.target for e in outgoing.get(gw_id, [])}
            if correction_id not in gw_out_targets:
                continue

            upstream_candidates = [
                src for src in incoming.get(gw_id, [])
                if src != correction_id and src in step_map
            ]
            if not upstream_candidates:
                continue

            same_lane = [
                c for c in upstream_candidates
                if step_map[c].lane == correction_step.lane
            ]
            best = same_lane[0] if same_lane else upstream_candidates[0]
            edge.target = best

        # ── Rule 3: remove empty lanes (lanes with no step assigned) ──────────
        # Can happen after Rule 1 sets lane=None for serviceTask, or when the
        # LLM declares a lane in `lanes` but assigns no steps to it.
        # Empty lanes create blank rows in the viewer and inflate lane spans,
        # causing the crossing detector to miscount lane boundaries.
        populated = {s.lane for s in model.steps if s.lane}
        model.lanes = [ln for ln in model.lanes if ln in populated]
        for pm in model.pool_models:
            pm_pop = {s.lane for s in pm.steps if s.lane}
            pm.lanes = [ln for ln in pm.lanes if ln in pm_pop]

    # ── BPMN XML generation ───────────────────────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml(model: BPMNModel) -> str:
        try:
            from modules.schema import (
                BpmnProcess, BpmnElement, BpmnPool, BpmnLane,
                SequenceFlow, MessageFlow,
            )
            from modules.bpmn_generator import generate_bpmn_xml

            if model.is_collaboration:
                return AgentBPMN._generate_bpmn_xml_multi(
                    model, BpmnProcess, BpmnElement, BpmnPool,
                    BpmnLane, SequenceFlow, MessageFlow, generate_bpmn_xml,
                )
            return AgentBPMN._generate_bpmn_xml_single(
                model, BpmnProcess, BpmnElement, BpmnPool,
                BpmnLane, SequenceFlow, generate_bpmn_xml,
            )
        except Exception:
            return ""

    # ── Single-pool BPMN XML bridge ───────────────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml_single(model, BpmnProcess, BpmnElement, BpmnPool,
                                  BpmnLane, SequenceFlow, generate_bpmn_xml) -> str:
        _start_name = model.process_trigger or "Início"
        _end_name   = (model.process_outcomes[0] if model.process_outcomes else None) or "Fim"
        elements = []
        for i, step in enumerate(model.steps):
            if step.is_decision:
                el_type = "exclusiveGateway"
            elif step.task_type in _EVENT_TASK_TYPE_MAP:
                # Intermediate events are kept; start/end already stripped by Rule 0
                el_type_str, ev_type = _EVENT_TASK_TYPE_MAP[step.task_type]
                if "intermediate" in el_type_str.lower():
                    elements.append(BpmnElement(
                        id=step.id, name=step.title,
                        type=el_type_str, event_type=ev_type,
                        lane=step.lane, actor=step.actor,
                        documentation=step.description or "",
                    ))
                    if i == 0:
                        elements.insert(0, BpmnElement(
                            id="ev_start", name=_start_name, type="startEvent",
                            lane=step.lane, actor=None,
                        ))
                    if i == len(model.steps) - 1:
                        source_ids = {e.source for e in model.edges}
                        terminal = [s for s in model.steps if s.id not in source_ids]
                        end_lane = terminal[-1].lane if terminal else step.lane
                        elements.append(BpmnElement(
                            id="ev_end", name=_end_name, type="endEvent",
                            lane=end_lane, actor=None,
                        ))
                    continue
                else:
                    el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")
            else:
                el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")

            if i == 0:
                elements.append(BpmnElement(
                    id="ev_start", name=_start_name, type="startEvent",
                    actor=None, lane=step.lane,
                ))

            elements.append(BpmnElement(
                id=step.id, name=step.title, type=el_type,
                actor=step.actor, lane=step.lane,
                documentation=step.description or "",
            ))

            if i == len(model.steps) - 1:
                source_ids = {e.source for e in model.edges}
                terminal = [s for s in model.steps if s.id not in source_ids]
                end_lane = terminal[-1].lane if terminal else step.lane
                elements.append(BpmnElement(
                    id="ev_end", name=_end_name, type="endEvent",
                    actor=None, lane=end_lane,
                ))

        flows = []
        if model.steps:
            flows.append(SequenceFlow(id="sf_start", source="ev_start",
                                      target=model.steps[0].id))
        for i, edge in enumerate(model.edges):
            flows.append(SequenceFlow(
                id=f"sf_{i + 1:03d}",
                source=edge.source, target=edge.target,
                name=edge.label or "", condition=edge.condition or "",
            ))
        if model.steps:
            source_ids = {e.source for e in model.edges}
            terminal = [s for s in model.steps if s.id not in source_ids]
            if not terminal:
                terminal = [model.steps[-1]]
            for _j, _term in enumerate(terminal):
                _fid = "sf_end" if _j == 0 else f"sf_end_{_j}"
                flows.append(SequenceFlow(id=_fid, source=_term.id,
                                          target="ev_end"))

        pools = []
        if model.lanes:
            lane_objects = []
            for lane_name in model.lanes:
                lane_id = "lane_" + _ascii_id(lane_name)
                member_ids = [
                    s.id for s in model.steps
                    if s.lane and s.lane.lower() == lane_name.lower()
                ]
                lane_objects.append(BpmnLane(
                    id=lane_id, name=lane_name, element_ids=member_ids,
                ))
            pools.append(BpmnPool(id="pool_1", name=model.name,
                                  lanes=lane_objects))

        bpmn_process = BpmnProcess(
            name=model.name,
            documentation=model.description or "",
            elements=elements,
            flows=flows,
            pools=pools,
        )
        return generate_bpmn_xml(bpmn_process)

    # ── Multi-pool BPMN XML bridge ────────────────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml_multi(model, BpmnProcess, BpmnElement, BpmnPool,
                                 BpmnLane, SequenceFlow, MessageFlow,
                                 generate_bpmn_xml) -> str:
        """
        Build a BpmnProcess with one BpmnPool per pool_model, each pool
        carrying its own elements and flows.  Message flows are added as
        MessageFlow objects referencing prefixed element IDs.
        """
        pools = []

        # Map pool_id → (xml_pool_id, prefix) for message flow resolution
        pool_id_to_xml:    dict[str, str] = {}
        pool_id_to_prefix: dict[str, str] = {}

        for i, pm in enumerate(model.pool_models):
            prefix       = f"p{i + 1}_"
            xml_pool_id  = f"pool_{i + 1}"
            pool_id_to_xml[pm.pool_id]    = xml_pool_id
            pool_id_to_prefix[pm.pool_id] = prefix

            elements = _build_pool_elements(pm, prefix, BpmnElement)
            flows    = _build_pool_flows(pm, prefix, elements, SequenceFlow)
            lanes    = _build_pool_lanes(pm, prefix, xml_pool_id, elements, BpmnLane)

            pools.append(BpmnPool(
                id=xml_pool_id,
                name=pm.name,
                lanes=lanes,
                elements=elements,
                flows=flows,
            ))

        # Build MessageFlow objects (resolve pool aliases and "start"/"end")
        schema_mf = []
        for mf in model.message_flows_data:
            src_prefix = pool_id_to_prefix.get(mf.source_pool, "p1_")
            tgt_prefix = pool_id_to_prefix.get(mf.target_pool, "p2_")

            src_id = _resolve_mf_step(mf.source_step, src_prefix, "throw")
            tgt_id = _resolve_mf_step(mf.target_step, tgt_prefix, "catch")

            schema_mf.append(MessageFlow(
                id=mf.id,
                source=src_id,
                target=tgt_id,
                name=mf.name,
            ))

        bpmn_process = BpmnProcess(
            name=model.name,
            documentation=model.description or "",
            elements=[],    # elements are owned by each pool
            flows=[],       # flows are owned by each pool
            pools=pools,
            message_flows=schema_mf,
        )
        return generate_bpmn_xml(bpmn_process)

    # ── Mermaid generator ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_mermaid(model: BPMNModel) -> str:
        from agents.agent_mermaid import MermaidGenerator
        return MermaidGenerator.generate(model)


# ── Pool builder helpers (module-level for readability) ───────────────────────

def _resolve_mf_step(step_ref: str, prefix: str, direction: str) -> str:
    """
    Resolve a message-flow step reference to a prefixed element ID.
    - "start" → ev_start of that pool
    - "end"   → ev_end of that pool
    - anything else → prefixed step id
    direction = "throw" | "catch" (used only to pick ev_end vs ev_start
    when the reference is ambiguous)
    """
    if step_ref in ("start", "ev_start"):
        return prefix + "ev_start"
    if step_ref in ("end", "ev_end"):
        return prefix + "ev_end"
    return prefix + step_ref


def _build_pool_elements(pm: BPMNPoolData, prefix: str, BpmnElement) -> list:
    """
    Build the BpmnElement list for one pool.
    Handles the new event task_types from skill v3.0.
    If no explicit start/end event step is present, synthetic ones are injected.
    """
    from modules.schema import BpmnElement as _BE  # noqa: F401 (type alias)

    steps = pm.steps
    if not steps:
        return []

    has_start = any(s.task_type in _START_TYPES for s in steps)
    has_end   = any(s.task_type in _END_TYPES   for s in steps)

    elements = []

    # Inject synthetic startEvent before first step if needed
    if not has_start:
        elements.append(BpmnElement(
            id=prefix + "ev_start",
            name="Início",
            type="startEvent",
            event_type="none",
            lane=steps[0].lane,
            actor=None,
        ))

    for step in steps:
        if step.task_type in _EVENT_TASK_TYPE_MAP:
            el_type_str, ev_type = _EVENT_TASK_TYPE_MAP[step.task_type]
            elements.append(BpmnElement(
                id=prefix + step.id,
                name=step.title,
                type=el_type_str,
                event_type=ev_type,
                lane=step.lane,
                actor=step.actor,
                documentation=step.description or "",
            ))
        elif step.is_decision:
            elements.append(BpmnElement(
                id=prefix + step.id,
                name=step.title,
                type="exclusiveGateway",
                lane=step.lane,
                actor=step.actor,
            ))
        else:
            el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")
            elements.append(BpmnElement(
                id=prefix + step.id,
                name=step.title,
                type=el_type,
                lane=step.lane,
                actor=step.actor,
                documentation=step.description or "",
            ))

    # Inject synthetic endEvent after last step if needed
    if not has_end:
        source_ids  = {e.source for e in pm.edges}
        terminal    = [s for s in steps if s.id not in source_ids]
        end_lane    = terminal[-1].lane if terminal else (steps[-1].lane if steps else None)
        elements.append(BpmnElement(
            id=prefix + "ev_end",
            name="Fim",
            type="endEvent",
            event_type="none",
            lane=end_lane,
            actor=None,
        ))

    return elements


def _build_pool_flows(pm: BPMNPoolData, prefix: str, elements: list,
                      SequenceFlow) -> list:
    """Build SequenceFlow list for one pool, including start/end connectors."""
    steps    = pm.steps
    if not steps:
        return []

    has_start = any(s.task_type in _START_TYPES for s in steps)
    has_end   = any(s.task_type in _END_TYPES   for s in steps)

    el_ids = {el.id for el in elements}

    flows = []

    # Connect synthetic ev_start → first non-start-event step
    if not has_start:
        first_real = next(
            (s for s in steps if s.task_type not in _START_TYPES), steps[0]
        )
        flows.append(SequenceFlow(
            id=prefix + "sf_start",
            source=prefix + "ev_start",
            target=prefix + first_real.id,
        ))

    for k, edge in enumerate(pm.edges):
        src = prefix + edge.source
        tgt = prefix + edge.target
        if src in el_ids and tgt in el_ids:
            flows.append(SequenceFlow(
                id=prefix + f"sf_{k + 1:03d}",
                source=src,
                target=tgt,
                name=edge.label or "",
                condition=edge.condition or "",
            ))

    # Connect ALL terminal (leaf) steps → synthetic ev_end
    if not has_end:
        source_ids = {e.source for e in pm.edges}
        terminal   = [s for s in steps if s.id not in source_ids
                      and s.task_type not in _END_TYPES]
        for _j, _term in enumerate(terminal):
            _fid = prefix + ("sf_end" if _j == 0 else f"sf_end_{_j}")
            flows.append(SequenceFlow(
                id=_fid,
                source=prefix + _term.id,
                target=prefix + "ev_end",
            ))

    return flows


def _build_pool_lanes(pm: BPMNPoolData, prefix: str, xml_pool_id: str,
                      elements: list, BpmnLane) -> list:
    """Build BpmnLane list for one pool, assigning elements to lanes."""
    if not pm.lanes:
        return []

    el_map: dict[str, object] = {el.id: el for el in elements}
    lanes  = []

    for lane_name in pm.lanes:
        lane_id    = f"lane_{xml_pool_id}_" + _ascii_id(lane_name)
        member_ids = [
            el.id for el in elements
            if (getattr(el, "lane", None) or "").lower() == lane_name.lower()
        ]
        lanes.append(BpmnLane(id=lane_id, name=lane_name,
                               element_ids=member_ids))

    return lanes
