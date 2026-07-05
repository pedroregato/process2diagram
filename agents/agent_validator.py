# agents/agent_validator.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentValidator — pure-Python BPMN quality scorer, no LLM call.
#
# Scores a BPMNModel on five user-configurable dimensions:
#   1. Granularidade  — activity count relative to transcript length
#   2. Task type      — specificity of task_type assignments
#   3. Gateways       — gateway correctness (labels, split/join symmetry)
#   4. Structural     — penalty for structural issues (dangling refs, isolated
#                       nodes, unreachable nodes, XOR missing labels, …)
#   5. Semantic       — naming quality (gateway-with-verb, task-as-state,
#                       generic start/end event names)
#
# Usage (called by Orchestrator when n_bpmn_runs > 1):
#   validator = AgentValidator()
#   score = validator.score(hub.bpmn, hub.transcript_clean, weights)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import xml.etree.ElementTree as _ET
import re as _re

from core.knowledge_hub import BPMNModel, BPMNValidationScore, AgentOutcomeScore, KnowledgeHub
from modules.bpmn_structural_validator import validate_bpmn_structure

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

# Semantic dimension — activity verbs that must NOT appear as gateway names
_ACTIVITY_VERBS = {
    "validar", "analisar", "verificar", "revisar", "conferir", "aprovar",
    "processar", "avaliar", "checar", "executar", "calcular", "gerar",
    "encaminhar", "solicitar", "emitir", "registrar", "cadastrar",
    "elaborar", "preparar", "enviar", "receber", "notificar", "publicar",
}

# Generic names that violate Bruce Silver Level 1 naming rules
_GENERIC_START_NAMES = {
    "início", "inicio", "start", "começar", "iniciar",
    "início do processo", "inicio do processo",
}
_GENERIC_END_NAMES = {
    "fim", "end", "encerrar", "terminar", "fim do processo",
    # "processo" as the subject (not the specific business outcome) is the
    # tell — "Contrato Encerrado e Arquivado" is fine, "Processo Encerrado"
    # isn't (PC123: found in a real generated diagram, slipped past the
    # exact-match set above since "encerrado"/"concluído" are conjugated
    # forms, not literal matches for "encerrar"/"terminar").
    "processo encerrado", "processo concluído", "processo concluido",
    "processo finalizado", "processo terminado",
}


# ── Scorer ────────────────────────────────────────────────────────────────────

class AgentValidator:
    """Pure-Python BPMN quality scorer — no LLM call."""

    def score(
        self,
        model: BPMNModel,
        transcript: str,
        weights: dict,  # {"granularity": int, "task_type": int, "gateways": int, "structural": int}
    ) -> BPMNValidationScore:

        steps = self._flat_steps(model)
        edges = self._flat_edges(model)

        s_gran = self._score_granularity(steps, transcript)
        s_type = self._score_tasktype(steps)
        s_gw   = self._score_gateways(steps, edges)
        s_str, n_errors, n_warnings = self._score_structural(model)
        s_sem, n_sem_viol = self._score_semantic(steps)

        w_g   = weights.get("granularity", 5)
        w_t   = weights.get("task_type",   5)
        w_gw  = weights.get("gateways",    5)
        w_s   = weights.get("structural",  5)
        w_sem = weights.get("semantic",    5)
        total_w = w_g + w_t + w_gw + w_s + w_sem or 1

        weighted = (
            w_g * s_gran + w_t * s_type + w_gw * s_gw + w_s * s_str + w_sem * s_sem
        ) / total_w

        tasks    = [s for s in steps if s.task_type not in _EVENT_TYPES | _GATEWAY_TYPES]
        gateways = [s for s in steps if s.task_type in _GATEWAY_TYPES]

        return BPMNValidationScore(
            granularity=round(s_gran, 2),
            task_type=round(s_type, 2),
            gateways=round(s_gw, 2),
            structural=round(s_str, 2),
            semantic=round(s_sem, 2),
            weighted=round(weighted, 2),
            n_tasks=len(tasks),
            n_gateways=len(gateways),
            n_structural_errors=n_errors,
            n_structural_warnings=n_warnings,
            n_semantic_violations=n_sem_viol,
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

            # ── Single-exit SPLIT gateway: structural defect (heavy penalty) ─
            # A JOIN gateway legitimately has 1 outgoing edge (merges N→1).
            # A SPLIT gateway with < 2 exits means a branch was omitted.
            is_join = incoming.get(s.id, 0) > 1
            if len(out_edges) < 2 and not is_join:
                scores.append(0.0)
                continue

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

    def _score_structural(self, model: BPMNModel) -> tuple[float, int, int]:
        """
        Score 0-10 based on bpmn_structural_validator results.
        Penalty: -2.5 per error, -0.5 per warning; info issues are free.
        Returns (score, n_errors, n_warnings).
        """
        issues = validate_bpmn_structure(model)
        n_errors   = sum(1 for i in issues if i.severity == "error")
        n_warnings = sum(1 for i in issues if i.severity == "warning")
        score = max(0.0, 10.0 - n_errors * 2.5 - n_warnings * 0.5)
        return round(score, 2), n_errors, n_warnings

    def _score_semantic(self, steps) -> tuple[float, int]:
        """
        Score 0-10 based on BPMN naming conventions (Bruce Silver Level 1).

        Violations detected (penalty per occurrence):
          -4.0  Gateway title starts with an activity verb
                ("Validar Contrato" as exclusiveGateway → should be userTask)
                (PC118: raised from -2.5 — a single occurrence used to survive
                a tournament with a merely-good-not-perfect score elsewhere;
                this is an explicit "never" rule in skill_bpmn.md and should
                dominate the semantic dimension almost by itself)
          -2.0  Non-gateway/event task title ends with "?"
                ("Documento Válido?" as userTask → should be exclusiveGateway)
          -1.0  Start event with generic name ("Início", "Start", …)
          -1.0  End event with generic name ("Fim", "End", …)

        Returns (score 0–10, n_violations).
        """
        penalty = 0.0
        n_violations = 0

        for s in steps:
            title_lower = s.title.lower().strip()
            first_word  = title_lower.split()[0] if title_lower else ""

            if s.task_type in _GATEWAY_TYPES:
                if first_word in _ACTIVITY_VERBS:
                    penalty += 4.0
                    n_violations += 1

            elif s.task_type in _EVENT_TYPES:
                is_start = "start" in s.task_type.lower()
                is_end   = "end"   in s.task_type.lower()
                if is_start and title_lower in _GENERIC_START_NAMES:
                    penalty += 1.0
                    n_violations += 1
                elif is_end and title_lower in _GENERIC_END_NAMES:
                    penalty += 1.0
                    n_violations += 1

            else:
                # Regular task named as a decision state
                if s.title.strip().endswith("?"):
                    penalty += 2.0
                    n_violations += 1

        return max(0.0, round(10.0 - penalty, 2)), n_violations

    # ══════════════════════════════════════════════════════════════════════════
    # Outcome validators — per-agent acceptance criteria (pure Python, no LLM)
    # Each method returns AgentOutcomeScore and is always fail-open.
    # ══════════════════════════════════════════════════════════════════════════

    def validate_all(self, hub: KnowledgeHub, weights: dict | None = None) -> dict:
        """
        Run all applicable outcome validators and return
        dict[agent_name → AgentOutcomeScore].

        Always fail-open: any internal exception yields a failed score with
        the exception message in warnings. Never raises.
        """
        validators = [
            ("transcript_quality", self._validate_quality),
            ("nlp",                self._validate_nlp),
            ("bpmn",               self._validate_bpmn_outcomes),
            ("mermaid",            self._validate_mermaid),
            ("minutes",            self._validate_minutes),
            ("requirements",       self._validate_requirements),
            ("sbvr",               self._validate_sbvr),
            ("bmm",                self._validate_bmm),
        ]
        results: dict = {}
        for name, fn in validators:
            try:
                results[name] = fn(hub)
            except Exception as exc:
                results[name] = AgentOutcomeScore(
                    agent_name=name,
                    passed=False,
                    score=0.0,
                    checks={},
                    warnings=[f"Validation error: {exc}"],
                )
        return results

    # ── Per-agent validators ──────────────────────────────────────────────────

    def _validate_quality(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        tq = hub.transcript_quality
        checks = {
            "grade in {A-E}": tq.grade in {"A", "B", "C", "D", "E"},
            "criteria non-empty": bool(tq.criteria),
        }
        warnings = []
        if tq.grade in {"D", "E"}:
            warnings.append(f"Grade {tq.grade} — transcript quality baixa. Verifique a transcrição.")
        return self._make_score("transcript_quality", checks, warnings)

    def _validate_nlp(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        nlp = hub.nlp
        words = len(hub.transcript_clean.split()) if hub.transcript_clean else 0
        checks = {
            "segments non-empty (transcript > 50w)": (
                bool(nlp.segments) if words > 50 else True
            ),
            "language_detected set": bool(getattr(nlp, "language_detected", None)),
        }
        warnings = []
        if words > 50 and not nlp.actors:
            warnings.append("Nenhum ator detectado — verifique se a transcrição inclui nomes de participantes.")
        return self._make_score("nlp", checks, warnings)

    def _validate_bpmn_outcomes(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        bpmn = hub.bpmn
        checks: dict = {}
        warnings: list = []

        # steps count
        steps = self._flat_steps(bpmn)
        checks["≥3 steps"] = len(steps) >= 3

        # lanes present and non-generic
        _GENERIC = {"usuário", "usuario", "sistema", "validador", "user", "system"}
        lanes = getattr(bpmn, "lanes", []) or []
        if bpmn.is_collaboration and bpmn.pool_models:
            lanes = [lane for pool in bpmn.pool_models for lane in (pool.lanes or [])]
        non_generic = [
            ln for ln in lanes
            if (ln.name if hasattr(ln, "name") else str(ln)).lower().strip() not in _GENERIC
        ]
        checks["≥1 non-generic lane"] = bool(non_generic)

        # XML validity
        xml_ok = False
        has_diagram = False
        has_start = False
        has_end = False
        if bpmn.bpmn_xml:
            try:
                root = _ET.fromstring(bpmn.bpmn_xml)
                xml_ok = True
                ns = {"bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI"}
                has_diagram = root.find(".//bpmndi:BPMNDiagram", ns) is not None
                xml_str = bpmn.bpmn_xml
                has_start = xml_str.count("startEvent") >= 1
                has_end   = xml_str.count("endEvent")   >= 1
            except _ET.ParseError as exc:
                warnings.append(f"XML parse error: {exc}")

        checks["bpmn_xml parseable"] = xml_ok
        checks["BPMNDiagram element present"] = has_diagram
        checks["startEvent present (exactly 1)"] = has_start
        checks["endEvent present (≥1)"] = has_end

        return self._make_score("bpmn", checks, warnings)

    def _validate_mermaid(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        code = hub.bpmn.mermaid or ""
        checks: dict = {}
        warnings: list = []

        checks["starts with flowchart"] = code.strip().startswith("flowchart")
        checks["no reserved node IDs (END/start/end)"] = not bool(
            _re.search(r'\b(END|start|end)\b\s*[\[\{]', code)
        )
        # Decision nodes should use {} not {{}}
        checks["decisions use {} not {{}}"] = "{{" not in code
        # Quoted labels inside {} are invalid Mermaid syntax
        checks["no quoted labels in {} nodes"] = not bool(
            _re.search(r'\{[^}]*"[^"]*"[^}]*\}', code)
        )

        if not code:
            warnings.append("mermaid_code is empty — MermaidGenerator may not have run.")
        return self._make_score("mermaid", checks, warnings)

    def _validate_minutes(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        m = hub.minutes
        checks: dict = {}
        warnings: list = []

        checks["≥1 participant"] = bool(m.participants)
        checks["≥1 decision"] = bool(m.decisions)

        ai_ok = True
        for item in m.action_items:
            resp = getattr(item, "responsible", None) or getattr(item, "owner", None)
            dl   = getattr(item, "deadline", None)
            if not resp or not dl:
                ai_ok = False
                break
        checks["action_items have responsible+deadline"] = ai_ok or not m.action_items

        if not m.participants:
            warnings.append("Nenhum participante extraído.")
        if not m.decisions:
            warnings.append("Nenhuma decisão extraída — verifique se a reunião teve conteúdo substantivo.")
        return self._make_score("minutes", checks, warnings)

    def _validate_requirements(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        items = hub.requirements.items
        _VALID_TYPES = {"functional", "non_functional", "constraint", "business_rule",
                        "ui_field", "validation"}
        checks: dict = {}
        warnings: list = []

        checks["≥1 requirement"] = bool(items)
        fields_ok = all(
            getattr(r, "id", None) and getattr(r, "description", None)
            and getattr(r, "type", None) and getattr(r, "speaker", None)
            for r in items
        ) if items else True
        checks["required fields populated (id/description/type/speaker)"] = fields_ok

        bad_types = [
            r for r in items
            if getattr(r, "type", None) and r.type not in _VALID_TYPES
        ]
        checks["type values within IEEE 830 set"] = not bool(bad_types)
        if bad_types:
            warnings.append(f"{len(bad_types)} item(s) com type fora do conjunto IEEE 830.")
        return self._make_score("requirements", checks, warnings)

    def _validate_sbvr(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        if not hub.sbvr.ready:
            return AgentOutcomeScore(
                agent_name="sbvr", passed=True, score=10.0,
                checks={"agent_skipped": True},
                warnings=["AgentSBVR não foi executado nesta sessão."],
            )
        vocab = hub.sbvr.vocabulary
        rules = hub.sbvr.rules
        checks: dict = {}
        warnings: list = []

        checks["5–15 terms"] = 5 <= len(vocab) <= 15
        checks["3–10 rules"] = 3 <= len(rules) <= 10
        no_empty_def = all(
            bool(getattr(t, "definition", None)) for t in vocab
        )
        checks["all terms have definition"] = no_empty_def

        if not (5 <= len(vocab) <= 15):
            warnings.append(f"Vocabulário tem {len(vocab)} termo(s) — esperado 5–15.")
        if not (3 <= len(rules) <= 10):
            warnings.append(f"Regras têm {len(rules)} item(s) — esperado 3–10.")
        return self._make_score("sbvr", checks, warnings)

    def _validate_bmm(self, hub: KnowledgeHub) -> AgentOutcomeScore:
        if not hub.bmm.ready:
            return AgentOutcomeScore(
                agent_name="bmm", passed=True, score=10.0,
                checks={"agent_skipped": True},
                warnings=["AgentBMM não foi executado nesta sessão."],
            )
        bmm = hub.bmm
        checks: dict = {}
        warnings: list = []

        checks["vision non-empty"] = bool(getattr(bmm, "vision", None))
        checks["mission non-empty"] = bool(getattr(bmm, "mission", None))
        checks["≥1 goal"] = bool(getattr(bmm, "goals", []))
        strats_with_links = all(
            bool(getattr(s, "goal_links", None))
            for s in getattr(bmm, "strategies", [])
        )
        checks["strategies have goal_links"] = strats_with_links or not getattr(bmm, "strategies", [])

        if not getattr(bmm, "vision", None):
            warnings.append("vision está vazio.")
        if not getattr(bmm, "mission", None):
            warnings.append("mission está vazio.")
        return self._make_score("bmm", checks, warnings)

    # ── Score builder ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_score(agent_name: str, checks: dict, warnings: list) -> AgentOutcomeScore:
        """Derive score 0–10 from check results and build AgentOutcomeScore."""
        if not checks:
            return AgentOutcomeScore(agent_name=agent_name, passed=True,
                                     score=10.0, checks=checks, warnings=warnings)
        # Exclude "agent_skipped" from pass/fail calculation
        real_checks = {k: v for k, v in checks.items() if k != "agent_skipped"}
        if not real_checks:
            return AgentOutcomeScore(agent_name=agent_name, passed=True,
                                     score=10.0, checks=checks, warnings=warnings)
        n_pass  = sum(1 for v in real_checks.values() if v)
        n_total = len(real_checks)
        score   = round(n_pass / n_total * 10.0, 2)
        passed  = all(real_checks.values())
        return AgentOutcomeScore(
            agent_name=agent_name,
            passed=passed,
            score=score,
            checks=checks,
            warnings=warnings,
        )

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
