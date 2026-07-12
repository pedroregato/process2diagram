# services/llm_telemetry.py
# ─────────────────────────────────────────────────────────────────────────────
# LLM call telemetry — records latency, token counts and metadata for every
# LLM call (passive) and on-demand benchmark runs.
#
# Design principles:
#   - Fail-open: any Supabase error is silently swallowed
#   - Async write: daemon thread — never blocks the pipeline
#   - Single module-level singleton `_telemetry` used by base_agent
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class TelemetryRecord:
    agent_name:    str
    provider:      str
    model:         str
    latency_ms:    int
    input_tokens:  int
    output_tokens: int
    total_tokens:  int
    from_cache:    bool = False
    long_context:  bool = False
    is_error:      bool = False
    benchmark_run: bool = False
    skill_version: Optional[str] = None
    error_message: Optional[str] = None
    # PC183 — schema-validation outcome (output_schema.model_validate). These
    # records share the same table but are a distinct event type: they carry
    # no latency/token data, so query()'s default latency/throughput views
    # must keep filtering is_validation_event=False (see query()).
    is_validation_event: bool = False
    schema_valid:        Optional[bool] = None


# ── Synthetic transcripts for on-demand benchmarks ────────────────────────────

TRANSCRIPT_SHORT = """\
Reunião de planejamento de produto — 15/05/2026.
Participantes: Ana Costa (PM), Roberto Silva (Tech Lead), Marina Souza (Design).

Ana: Precisamos definir as prioridades do Q3. O que temos no backlog?
Roberto: Temos três features críticas — autenticação SSO, relatórios avançados e API pública.
Marina: Do ponto de vista de UX, os relatórios avançados são mais urgentes.
Ana: Concordo. Vamos priorizar: 1) Relatórios avançados, 2) SSO, 3) API pública.
Roberto: Vou alocar dois devs para relatórios. Prazo estimado: seis semanas.
Ana: Perfeito. Marina, pode preparar os wireframes até quinta-feira?
Marina: Sim, entrego na quinta.
Ana: Decisão final — relatórios avançados como prioridade Q3, início na próxima semana.
"""

TRANSCRIPT_MEDIUM = """\
Reunião de planejamento estratégico — Q3 2026. Data: 15/05/2026.
Participantes: Ana Costa (Diretora de Produto), Roberto Silva (Tech Lead),
Marina Souza (UX Design), Carlos Mendes (Arquitetura), Fernanda Lima (QA).

Ana: Vamos revisar o roadmap do Q3. Roberto, qual é a situação do backlog técnico?
Roberto: Temos cinco iniciativas críticas. A primeira é a autenticação SSO — demanda de compliance
que afeta três clientes enterprise. A segunda é relatórios avançados com filtros e exportação.
A terceira é a API pública v2, que desbloquearia parceiros estratégicos. Também temos
performance de banco — estamos com queries acima de 500ms em produção — e refatoração
do módulo de notificações que está causando falhas esporádicas.

Ana: E do ponto de vista de design, Marina?
Marina: Relatórios avançados e a API têm dependência de UI. Para SSO, o fluxo é padrão.
Minha recomendação é priorizar relatórios avançados — é o que mais impacta retenção.

Carlos: Do ponto de vista de arquitetura, SSO exige mudanças na camada de autenticação
que afetam os outros módulos. Sugiro começar por SSO para evitar retrabalho.

Fernanda: Concordo com Carlos. SSO tem menos superfície de testes que relatórios.
O risco de regressão nos relatórios é maior dado o estado atual do módulo.

Ana: Considerando os inputs: priorizamos SSO primeiro para compliance e arquitetura,
depois relatórios avançados para retenção, e API v2 como terceira prioridade.
Performance e notificações entram como bugs prioritários, não features.

Roberto: SSO leva quatro semanas com dois devs. Relatórios levam seis semanas.
Podemos rodar em paralelo se a Marina liberar os wireframes dos relatórios em duas semanas.
Marina: Dois wireframes de tela principal até 25/05 — factível.

Ana: Decisões finais — SSO: início 20/05, prazo 17/06, responsável Roberto.
Relatórios avançados: início 20/05 (design paralelo), desenvolvimento a partir de 17/06.
API v2: início 01/08. Performance e notificações: bugs com prioridade máxima, sem sprint dedicada.

Próximos passos: Roberto monta equipe SSO amanhã. Marina entrega wireframes até 25/05.
Carlos revisa arquitetura de autenticação até 22/05. Fernanda prepara plano de testes SSO.
"""

TRANSCRIPTS = {
    "Curta (~150 palavras)":  TRANSCRIPT_SHORT,
    "Media (~350 palavras)": TRANSCRIPT_MEDIUM,
}

# ── Benchmark task definitions ────────────────────────────────────────────────
# Representative but concise prompts — same JSON structure as production agents.

BENCHMARK_TASKS: dict[str, dict] = {
    "bpmn": {
        "label": "📐 BPMN",
        "system": (
            "You are a BPMN 2.0 expert. Extract a structured process model from "
            "the meeting transcript. Return JSON with keys: "
            "'steps' (list of {id, name, type, lane}), "
            "'edges' (list of {from, to, label}), "
            "'lanes' (list of strings). "
            "Use types: task, gateway, startEvent, endEvent."
        ),
        "user": "Extract the BPMN process from this meeting:\n\n{transcript}\n\nReturn valid JSON only.",
    },
    "minutes": {
        "label": "📋 Ata",
        "system": (
            "You are a meeting analyst. Extract structured meeting minutes. "
            "Return JSON with keys: 'summary' (string), "
            "'decisions' (list of strings), "
            "'action_items' (list of {owner, action, deadline}), "
            "'participants' (list of strings)."
        ),
        "user": "Extract meeting minutes from:\n\n{transcript}\n\nReturn valid JSON only.",
    },
    "requirements": {
        "label": "📝 Requisitos",
        "system": (
            "You are a requirements analyst (IEEE 830). Extract software requirements "
            "from the transcript. Return JSON with key 'requirements': list of "
            "{id, type, title, description, priority}. "
            "Types: functional, non_functional, constraint, business_rule."
        ),
        "user": "Extract requirements from:\n\n{transcript}\n\nReturn valid JSON only.",
    },
    "sbvr": {
        "label": "📖 SBVR",
        "system": (
            "You are an OMG SBVR expert. Extract business vocabulary and rules. "
            "Return JSON with keys: "
            "'concepts' (list of {term, definition, category}), "
            "'rules' (list of {id, statement, type, sphere}). "
            "Rule types: operative, structural."
        ),
        "user": "Extract SBVR elements from:\n\n{transcript}\n\nReturn valid JSON only.",
    },
    "bmm": {
        "label": "🎯 BMM",
        "system": (
            "You are an OMG BMM expert. Extract business motivation elements. "
            "Return JSON with keys: 'vision' (string), 'mission' (string), "
            "'goals' (list of strings), 'strategies' (list of strings), "
            "'policies' (list of strings)."
        ),
        "user": "Extract BMM elements from:\n\n{transcript}\n\nReturn valid JSON only.",
    },
}


# ── Benchmark runner ───────────────────────────────────────────────────────────

def run_benchmark_call(
    provider_name: str,
    provider_cfg: dict,
    api_key: str,
    system: str,
    user: str,
) -> tuple[int, int, int, Optional[str]]:
    """
    Run a single timed LLM call and return (latency_ms, input_tokens, output_tokens, error).
    error is None on success, error message string on failure.
    Uses the same routing as BaseAgent._call_llm but without hub/cache/PII.
    """
    client_type = provider_cfg.get("client_type", "openai_compatible")
    model       = provider_cfg.get("default_model", "")
    max_tokens  = provider_cfg.get("max_tokens", 4096)

    t0 = time.time()
    try:
        if client_type == "openai_compatible":
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            if provider_cfg.get("supports_json_mode"):
                kwargs["response_format"] = {"type": "json_object"}
                if "json" not in user.lower():
                    kwargs["messages"][-1]["content"] += "\n\nReturn valid JSON only."
            reasoning_effort = provider_cfg.get("reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
                kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
                kwargs.pop("temperature", None)
            resp = client.chat.completions.create(**kwargs, timeout=60)
            inp  = resp.usage.prompt_tokens     if resp.usage else 0
            out  = resp.usage.completion_tokens if resp.usage else 0

        elif client_type == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=model, max_tokens=max_tokens, temperature=0.1,
                system=system,
                messages=[{"role": "user", "content": user}],
                timeout=60,
            )
            inp = msg.usage.input_tokens  if msg.usage else 0
            out = msg.usage.output_tokens if msg.usage else 0
        else:
            return 0, 0, 0, f"Unknown client_type: {client_type}"

        latency_ms = int((time.time() - t0) * 1000)
        return latency_ms, inp, out, None

    except Exception as exc:
        latency_ms = int((time.time() - t0) * 1000)
        return latency_ms, 0, 0, str(exc)[:200]


# ── Telemetry service ─────────────────────────────────────────────────────────

class LLMTelemetry:

    def record(self, rec: TelemetryRecord) -> None:
        """Fire-and-forget async write. Never raises."""
        threading.Thread(target=self._write, args=(rec,), daemon=True).start()

    def record_validation(self, agent_name: str, skill_version: Optional[str], valid: bool) -> None:
        """Fire-and-forget async write of a schema-validation outcome (PC183).

        Separate from record() because a validation event has no latency/token
        data of its own — it piggybacks on the same table as a distinct row
        (is_validation_event=True) so it can be queried independently without
        polluting the latency/throughput aggregates in query().
        """
        self.record(TelemetryRecord(
            agent_name=agent_name,
            provider="",
            model="",
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            skill_version=skill_version,
            is_validation_event=True,
            schema_valid=valid,
        ))

    def _write(self, rec: TelemetryRecord) -> None:
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                return
            db.table("llm_telemetry").insert({
                "agent_name":    rec.agent_name,
                "provider":      rec.provider,
                "model":         rec.model,
                "latency_ms":    rec.latency_ms,
                "input_tokens":  rec.input_tokens,
                "output_tokens": rec.output_tokens,
                "total_tokens":  rec.total_tokens,
                "from_cache":    rec.from_cache,
                "long_context":  rec.long_context,
                "is_error":      rec.is_error,
                "benchmark_run": rec.benchmark_run,
                "skill_version": rec.skill_version,
                "error_message": rec.error_message,
                "is_validation_event": rec.is_validation_event,
                "schema_valid":  rec.schema_valid,
            }).execute()
        except Exception:
            pass

    def query(
        self,
        provider:          Optional[str] = None,
        agent_name:        Optional[str] = None,
        days:              int  = 30,
        include_cache:     bool = False,
        include_benchmark: bool = True,
        only_benchmark:    bool = False,
        limit:             int  = 2000,
    ) -> list[dict]:
        """Query telemetry records from Supabase. Returns [] on any error."""
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                return []
            q = (
                db.table("llm_telemetry")
                .select("agent_name,provider,model,latency_ms,input_tokens,"
                        "output_tokens,total_tokens,from_cache,long_context,"
                        "is_error,benchmark_run,skill_version,created_at")
                .eq("is_error", False)
                .eq("is_validation_event", False)
                .gte("created_at", f"now() - interval '{days} days'")
                .order("created_at", desc=True)
                .limit(limit)
            )
            if provider:
                q = q.eq("provider", provider)
            if agent_name:
                q = q.eq("agent_name", agent_name)
            if not include_cache:
                q = q.eq("from_cache", False)
            if only_benchmark:
                q = q.eq("benchmark_run", True)
            elif not include_benchmark:
                q = q.eq("benchmark_run", False)
            return q.execute().data or []
        except Exception:
            return []

    def query_error_rate_by_provider(self, hours: int = 24) -> dict[str, dict]:
        """Error rate per provider over the last `hours` (PC183).

        Excludes cached/benchmark calls — those don't reflect live provider
        health. Returns {} on any error (fail-open).
        """
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                return {}
            rows = (
                db.table("llm_telemetry")
                .select("provider,is_error")
                .eq("is_validation_event", False)
                .eq("from_cache", False)
                .eq("benchmark_run", False)
                .gte("created_at", f"now() - interval '{hours} hours'")
                .limit(5000)
                .execute().data or []
            )
            stats: dict[str, dict] = {}
            for r in rows:
                p = r.get("provider") or "?"
                s = stats.setdefault(p, {"total": 0, "errors": 0})
                s["total"] += 1
                if r.get("is_error"):
                    s["errors"] += 1
            for s in stats.values():
                s["error_rate"] = s["errors"] / s["total"] if s["total"] else 0.0
            return stats
        except Exception:
            return {}

    def detect_error_anomalies(
        self,
        hours: int = 24,
        min_calls: int = 5,
        error_rate_threshold: float = 0.15,
    ) -> list[dict]:
        """Flags providers whose recent error rate crosses `error_rate_threshold`
        (PC183) — e.g. surfaces the known intermittent DeepSeek "conteúdo vazio"
        failure pattern as an actionable signal instead of silent retries.

        `min_calls` guards against false positives from low-volume noise
        (e.g. 1 error out of 1 call = 100% but meaningless).
        """
        stats = self.query_error_rate_by_provider(hours=hours)
        anomalies = [
            {"provider": provider, **s}
            for provider, s in stats.items()
            if s["total"] >= min_calls and s["error_rate"] >= error_rate_threshold
        ]
        return sorted(anomalies, key=lambda a: a["error_rate"], reverse=True)

    def query_recent_errors(self, hours: int = 24, limit: int = 20) -> list[dict]:
        """Most recent failed calls (PC183) — lets the Alertas panel show *why*
        a provider is flagged, not just the error rate. Returns [] on error.
        """
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                return []
            rows = (
                db.table("llm_telemetry")
                .select("agent_name,provider,model,error_message,created_at")
                .eq("is_error", True)
                .gte("created_at", f"now() - interval '{hours} hours'")
                .order("created_at", desc=True)
                .limit(limit)
                .execute().data or []
            )
            return rows
        except Exception:
            return []

    def query_schema_validation_rate(
        self,
        days: int = 30,
        agent_name: Optional[str] = None,
    ) -> list[dict]:
        """Per agent/skill_version well-formed-output rate (PC183) — surfaces
        PC84's schema validation outcome (previously only a transient
        warnings.warn(), never persisted) as a quality-over-time metric.
        Returns raw rows [{agent_name, skill_version, schema_valid, created_at}];
        aggregation is done by the caller (UI groups by agent/version/day).
        """
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                return []
            q = (
                db.table("llm_telemetry")
                .select("agent_name,skill_version,schema_valid,created_at")
                .eq("is_validation_event", True)
                .gte("created_at", f"now() - interval '{days} days'")
                .order("created_at", desc=True)
                .limit(5000)
            )
            if agent_name:
                q = q.eq("agent_name", agent_name)
            return q.execute().data or []
        except Exception:
            return []


# Module-level singleton used by base_agent
_telemetry = LLMTelemetry()
