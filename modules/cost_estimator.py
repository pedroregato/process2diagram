# modules/cost_estimator.py
# ─────────────────────────────────────────────────────────────────────────────
# Estimativa de custos LLM para o Process2Diagram.
#
# Dados de preço são aproximados e atualizados até abril/2026.
# Fonte: páginas de preço oficiais de cada provedor.
#
# Não faz chamadas LLM — cálculo puramente Python.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass, field

# ── Preços por provedor (USD por 1 000 000 tokens) ───────────────────────────
# input_usd: custo por 1M tokens de entrada (prompt + contexto)
# output_usd: custo por 1M tokens de saída (resposta gerada)

PROVIDER_PRICING: dict[str, dict] = {
    "DeepSeek": {
        "model":      "deepseek-v4-flash",
        "input_usd":  0.14,    # cache miss; cache hit = $0.0028
        "output_usd": 0.28,
        "note":       "1M context · Cache reduz input em ~98% · deepseek-chat deprecated 24/07/2026",
        "free_tier":  False,
        "source":     "api-docs.deepseek.com/quick_start/pricing",
    },
    "DeepSeek V4 Pro": {
        "model":      "deepseek-v4-pro",
        "input_usd":  0.435,   # cache miss; cache hit = $0.003625
        "output_usd": 0.87,
        "note":       "1M context · Modelo premium · 75% discount até 31/05/2026",
        "free_tier":  False,
        "source":     "api-docs.deepseek.com/quick_start/pricing",
    },
    "DeepSeek V4 Flash (Thinking)": {
        "model":      "deepseek-v4-flash (thinking mode)",
        "input_usd":  0.14,    # mesmo preço do flash + thinking tokens de saída
        "output_usd": 0.28,
        "note":       "Modo raciocínio ativado (reasoning_effort=high) — output inclui tokens de thinking",
        "free_tier":  False,
        "source":     "api-docs.deepseek.com/quick_start/pricing",
    },
    "Claude (Anthropic)": {
        "model":      "claude-sonnet-4-20250514",
        "input_usd":  3.00,
        "output_usd": 15.00,
        "note":       "Alta qualidade; custo mais elevado",
        "free_tier":  False,
        "source":     "anthropic.com/pricing",
    },
    "OpenAI": {
        "model":      "gpt-4o-mini",
        "input_usd":  0.15,
        "output_usd": 0.60,
        "note":       "Bom equilíbrio custo/qualidade",
        "free_tier":  False,
        "source":     "openai.com/pricing",
    },
    "Groq (Llama)": {
        "model":      "llama-3.3-70b-versatile",
        "input_usd":  0.59,
        "output_usd": 0.79,
        "note":       "Velocidade de inferência muito alta",
        "free_tier":  True,
        "source":     "groq.com/pricing",
    },
    "Google Gemini": {
        "model":      "gemini-2.0-flash",
        "input_usd":  0.075,
        "output_usd": 0.30,
        "note":       "Tier gratuito: 1 500 req/dia, 1M tokens/min",
        "free_tier":  True,
        "source":     "ai.google.dev/pricing",
    },

    # ── Grok (xAI) ─────────────────────────────────────────────────────
    "Grok (xAI)": {
        "model":      "grok-4-1-fast-reasoning (2M context)",
        "input_usd":  0.20,
        "output_usd": 0.50,
        "note":       "Contexto gigante de 2M tokens - excelente para transcrições longas",
        "free_tier":  False,
        "source":     "docs.x.ai/developers/models",
    },

    "Grok 4.20 Multi-Agent (xAI)": {
        "model":      "grok-4.20-multi-agent",
        "input_usd":  2.00,
        "output_usd": 6.00,
        "note":       "Suporte nativo a multi-agente - ideal para análise complexa de reuniões",
        "free_tier":  False,
        "source":     "docs.x.ai/developers/models",
    },
}

# Preços de embedding (USD por 1 000 000 tokens/chars)
EMBEDDING_PRICING: dict[str, dict] = {
    "Google Gemini": {
        "model":     "text-embedding-004",
        "usd_per_1m": 0.0,     # gratuito no tier free (1 500 req/dia)
        "note":      "Gratuito no tier free (aistudio.google.com)",
    },
    "OpenAI": {
        "model":     "text-embedding-3-small",
        "usd_per_1m": 0.02,
        "note":      "$0.02 por 1M tokens",
    },
    # Grok embeddings ainda não tem preço público claro em 2026 (pode ser pay-per-use)
    # Por enquanto deixamos sem inclusão aqui. Podemos adicionar depois quando tiver preço oficial.
}

# ── Perfil de consumo de tokens por agente ────────────────────────────────────
# Estimativas baseadas em transcrições típicas de 2 000–5 000 palavras.
# input_tokens: tokens de entrada (prompt de sistema + transcrição + histórico)
# output_tokens: tokens de saída (artefato gerado)

AGENT_TOKEN_PROFILE: dict[str, dict] = {
    "quality":      {"input": 3_000,  "output": 500,   "label": "🔬 Quality Inspector"},
    "bpmn":         {"input": 6_000,  "output": 2_500, "label": "📐 AgentBPMN (1 pass)"},
    "minutes":      {"input": 6_000,  "output": 3_000, "label": "📋 AgentMinutes"},
    "requirements": {"input": 6_000,  "output": 2_000, "label": "📝 AgentRequirements"},
    "sbvr":         {"input": 5_000,  "output": 1_500, "label": "📖 AgentSBVR"},
    "bmm":          {"input": 5_000,  "output": 1_500, "label": "🎯 AgentBMM"},
    "synthesizer":  {"input": 10_000, "output": 4_000, "label": "📄 AgentSynthesizer"},
    "meeting_namer":{"input": 1_500,  "output": 200,   "label": "🏷️ AgentMeetingNamer"},
}

# Tokens adicionais por pass extra de BPMN
BPMN_EXTRA_PASS_TOKENS = {"input": 6_000, "output": 2_500}


# ── Dataclasses de resultado ──────────────────────────────────────────────────

@dataclass
class AgentCostBreakdown:
    agent:         str
    label:         str
    input_tokens:  int
    output_tokens: int
    cost_usd:      float

@dataclass
class ScenarioEstimate:
    provider:          str
    model:             str
    n_meetings:        int
    agents_enabled:    list[str]
    n_bpmn_passes:     int
    total_input:       int
    total_output:      int
    total_tokens:      int
    total_cost_usd:    float
    cost_per_meeting:  float
    breakdown:         list[AgentCostBreakdown] = field(default_factory=list)


# ── Funções de cálculo ────────────────────────────────────────────────────────

def cost_for_tokens(
    input_tokens: int,
    output_tokens: int,
    provider: str,
) -> float:
    """Calcula custo em USD para uma quantidade de tokens com o provedor dado."""
    pricing = PROVIDER_PRICING.get(provider)
    if not pricing:
        return 0.0
    cost = (
        input_tokens  / 1_000_000 * pricing["input_usd"]
        + output_tokens / 1_000_000 * pricing["output_usd"]
    )
    return round(cost, 6)


def estimate_scenario(
    provider:       str,
    n_meetings:     int,
    agents_enabled: list[str],
    n_bpmn_passes:  int = 1,
) -> ScenarioEstimate:
    """
    Estima custo total para processar `n_meetings` reuniões com os agentes
    e configurações especificadas.
    """
    pricing = PROVIDER_PRICING.get(provider, {})
    breakdown: list[AgentCostBreakdown] = []
    total_input = total_output = 0

    for agent_key in agents_enabled:
        profile = AGENT_TOKEN_PROFILE.get(agent_key)
        if not profile:
            continue

        inp = profile["input"]
        out = profile["output"]

        # Passes extras de BPMN
        if agent_key == "bpmn" and n_bpmn_passes > 1:
            inp += BPMN_EXTRA_PASS_TOKENS["input"]  * (n_bpmn_passes - 1)
            out += BPMN_EXTRA_PASS_TOKENS["output"] * (n_bpmn_passes - 1)

        agent_cost = cost_for_tokens(inp, out, provider)
        breakdown.append(AgentCostBreakdown(
            agent=agent_key,
            label=profile["label"],
            input_tokens=inp,
            output_tokens=out,
            cost_usd=agent_cost,
        ))
        total_input  += inp
        total_output += out

    cost_per_meeting = cost_for_tokens(total_input, total_output, provider)
    total_cost = round(cost_per_meeting * n_meetings, 6)

    return ScenarioEstimate(
        provider=provider,
        model=pricing.get("model", ""),
        n_meetings=n_meetings,
        agents_enabled=agents_enabled,
        n_bpmn_passes=n_bpmn_passes,
        total_input=total_input * n_meetings,
        total_output=total_output * n_meetings,
        total_tokens=(total_input + total_output) * n_meetings,
        total_cost_usd=total_cost,
        cost_per_meeting=cost_per_meeting,
        breakdown=breakdown,
    )


def estimate_embedding_cost(
    n_meetings:      int,
    avg_chars:       int,
    embed_provider:  str,
) -> float:
    """
    Estima custo de geração de embeddings para um projeto.
    """
    pricing = EMBEDDING_PRICING.get(embed_provider)
    if not pricing:
        return 0.0
    # ~4 chars ≈ 1 token (heurística padrão)
    total_tokens = (n_meetings * avg_chars) / 4
    return round(total_tokens / 1_000_000 * pricing["usd_per_1m"], 6)


def compare_providers(
    n_meetings:     int,
    agents_enabled: list[str],
    n_bpmn_passes:  int = 1,
) -> list[dict]:
    """
    Retorna estimativas para todos os provedores, ordenadas por custo.
    """
    results = []
    for provider in PROVIDER_PRICING:
        est = estimate_scenario(provider, n_meetings, agents_enabled, n_bpmn_passes)
        pricing = PROVIDER_PRICING[provider]
        results.append({
            "Provedor":          provider,
            "Modelo":            pricing["model"],
            "Custo total (USD)": est.total_cost_usd,
            "Por reunião (USD)": est.cost_per_meeting,
            "Tier gratuito":     "✅" if pricing.get("free_tier", False) else "—",
            "Observação":        pricing["note"],
        })
    results.sort(key=lambda x: x["Custo total (USD)"])
    return results

# ── Cotação USD/BRL (AwesomeAPI) ──────────────────────────────────────────────

import urllib.request as _urllib_request
import json as _json
from time import time as _time

_USD_BRL_CACHE: tuple[float, float] = (0.0, 0.0)  # (rate, timestamp)
_USD_BRL_TTL   = 3600  # segundos — recarrega a cada 1 hora


def get_usd_brl_rate(fallback: float = 5.20) -> tuple[float, bool]:
    """Fetch USD/BRL bid rate from AwesomeAPI with 1-hour in-memory cache.

    Returns:
        (rate, from_cache)
        rate       — float com a cotação (fallback se API falhar)
        from_cache — True se o valor veio do cache, False se foi buscado agora
    """
    global _USD_BRL_CACHE
    rate, ts = _USD_BRL_CACHE
    if rate > 0 and (_time() - ts) < _USD_BRL_TTL:
        return rate, True
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL"
        with _urllib_request.urlopen(url, timeout=3) as resp:
            data = _json.loads(resp.read())
        rate = float(data["USDBRL"]["bid"])
        _USD_BRL_CACHE = (rate, _time())
        return rate, False
    except Exception:
        if rate > 0:                        # cache expirado mas válido
            return rate, True
        return fallback, False              # sem cache, sem API → fallback
