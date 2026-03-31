# agents/agent_validator.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentValidator — pure-Python BPMN quality scorer, no LLM call.
#
# Scores a BPMNModel on three user-configurable dimensions:
#   1. Granularidade  — activity count relative to transcript length
#   2. Task type      — specificity of task_type assignments
#   3. Gateways       — structural correctness (labels, split/join symmetry)
#
# Usage (called by Orchestrator when n_bpmn_runs > 1):
#   validator = AgentValidator()
#   score = validator.score(hub.bpmn, hub.transcript_clean, weights)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from core.knowledge_hub import BPMNModel, BPMNValidationScore

# ── Task type sets ────────────────────────────────────────────────────────────

_EVENT_TYPES = {
    "noneStartEvent", "startMessageEvent", "startTimerEvent",
    "noneEndEvent", "endMessageEvent", "errorEndEvent",
    "intermediateTimerCatchEvent", "intermediateMessageCatchEvent",
    "intermediateMessageThrowEvent",
}
_GATEWAY_TYPES = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway", "gateway",
}
_SPECIFIC_TASK_TYPES = {
    "serviceTask", "businessRuleTask", "scriptTask",
    "manualTask", "sendTask", "receiveTask",
}

# Keyword heuristics for task-type validation
_SERVICE_KW  = {"sistema", "automático", "automaticamente", "processa", "gera",
                "api", "integra", "sincroniza", "envia e-mail", "notifica"}
_MANUAL_KW   = {"assinar", "imprimir", "ligar", "coletar", "presencial",
                "físico", "papel", "preencher planilha", "assina"}
_RULE_KW     = {"classificar", "categorizar", "regra", "política",
                "critério", "avaliar conformidade"}


# ── Scorer ────────────────────────────────────────────────────────────────────

class AgentValidator:
    """Pure-Python BPMN quality scorer — no LLM call."""

    def score(
        self,
        model: BPMNModel,
        transcript: str,
        weights: dict,       # {"granularity": int, "task_type": int, "gateways": int}
    ) -> BPMNValidationScore:

        steps = self._flat_steps(model)
        edges = self._flat_edges(model)

        s_gran = self._score_granularity(steps, transcript)
        s_type = self._score_tasktype(steps)
        s_gw   = self._score_gateways(steps, edges)

        w_g = weights.get("granularity", 5)
        w_t = weights.get("task_type",   5)
        w_gw = weights.get("gateways",   5)
        total_w = w_g + w_t + w_gw or 1

        weighted = (w_g * s_gran + w_t * s_type + w_gw * s_gw) / total_w

        tasks = [s for s in steps
                 if s.task_type not in _EVENT_TYPES | _GATEWAY_TYPES]
        gateways = [s for s in steps if s.task_type in _GATEWAY_TYPES]

        return BPMNValidationScore(
            granularity=round(s_gran, 2),
            task_type=round(s_type, 2),
            gateways=round(s_gw, 2),
            weighted=round(weighted, 2),
            n_tasks=len(tasks),
            n_gateways=len(gateways),
            transcript_words=len(transcript.split()),
        )

    # ── Dimension scorers ─────────────────────────────────────────────────────

    def _score_granularity(self, steps, transcript: str) -> float:
        """
        Score 0-10 based on activity count vs. transcript length.
        Target: 1 task per 50-100 words (process descriptions typically dense).
        """
        tasks = [s for s in steps
                 if s.task_type not in _EVENT_TYPES | _GATEWAY_TYPES]
        n = len(tasks)
        if n == 0:
            return 0.0
        words = max(len(transcript.split()), 1)
        lo = words / 100   # 1 task per 100 words → minimum expected
        hi = words / 40    # 1 task per 40 words  → maximum expected
        if lo <= n <= hi:
            return 10.0
        if n < lo:
            return max(0.0, 10.0 - (lo - n) * 3)
        return max(0.0, 10.0 - (n - hi) * 1.5)

    def _score_tasktype(self, steps) -> float:
        """
        Score 0-10 based on task_type specificity.
        - Specific type that matches title keywords → 10
        - Specific type even without keyword match  →  7 (valid but not verified)
        - userTask when keyword suggests specific   →  3 (missed opportunity)
        - userTask when appropriate                 →  6 (neutral)
        """
        tasks = [s for s in steps
                 if s.task_type not in _EVENT_TYPES | _GATEWAY_TYPES]
        if not tasks:
            return 5.0

        total = 0.0
        for t in tasks:
            text = (t.title + " " + t.description).lower()
            tt = t.task_type

            if tt in _SPECIFIC_TASK_TYPES:
                if tt == "serviceTask"       and any(k in text for k in _SERVICE_KW):
                    total += 10.0
                elif tt == "manualTask"      and any(k in text for k in _MANUAL_KW):
                    total += 10.0
                elif tt == "businessRuleTask" and any(k in text for k in _RULE_KW):
                    total += 10.0
                else:
                    total += 7.0   # specific type assigned — not confirmed by keyword
            else:
                if any(k in text for k in _SERVICE_KW):
                    total += 3.0   # should have been serviceTask
                elif any(k in text for k in _MANUAL_KW):
                    total += 4.0   # should have been manualTask
                else:
                    total += 6.0   # userTask is appropriate here

        return total / len(tasks)

    def _score_gateways(self, steps, edges) -> float:
        """
        Score 0-10 based on gateway structural correctness:
          - XOR/Exclusive: all outgoing edges of a split have labels
          - AND/OR: split gateways have a matching join of the same type
        Returns neutral 5.0 if there are no gateways (not penalized).
        """
        scores: list[float] = []
        step_map = {s.id: s for s in steps}

        # Incoming edge count per node
        incoming: dict[str, int] = {}
        for e in edges:
            incoming[e.target] = incoming.get(e.target, 0) + 1

        for s in steps:
            if s.task_type not in _GATEWAY_TYPES:
                continue

            out_edges = [e for e in edges if e.source == s.id]

            # ── XOR: all outgoing edges should be labeled ─────────────────
            if s.task_type == "exclusiveGateway" and len(out_edges) > 1:
                labeled = sum(1 for e in out_edges if (e.label or "").strip())
                scores.append(labeled / len(out_edges) * 10.0)

            # ── AND / OR: must have a corresponding join ──────────────────
            if s.task_type in ("parallelGateway", "inclusiveGateway") and len(out_edges) > 1:
                join_exists = any(
                    s2.task_type == s.task_type
                    and s2.id != s.id
                    and incoming.get(s2.id, 0) > 1
                    for s2 in steps
                )
                scores.append(10.0 if join_exists else 0.0)

        return round(sum(scores) / len(scores), 2) if scores else 5.0

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _flat_steps(model: BPMNModel):
        if model.is_collaboration and model.pool_models:
            result = []
            for pool in model.pool_models:
                result.extend(pool.steps)
            return result
        return model.steps

    @staticmethod
    def _flat_edges(model: BPMNModel):
        if model.is_collaboration and model.pool_models:
            result = []
            for pool in model.pool_models:
                result.extend(pool.edges)
            return result
        return model.edges
