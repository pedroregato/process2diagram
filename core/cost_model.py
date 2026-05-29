# core/cost_model.py
# ─────────────────────────────────────────────────────────────────────────────
# Modelo de dados e lógica de projeção para Cenários de Custo-Benefício.
# Sem dependências de Streamlit — pode ser testado standalone.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ModelPricing:
    provider: str               # chave de AVAILABLE_PROVIDERS
    model_id: str               # ex: "deepseek-v4-flash", "gpt-4o-mini"
    label: str                  # nome amigável para exibição
    input_price_per_1m: float   # USD por 1M tokens de input
    output_price_per_1m: float  # USD por 1M tokens de output
    quality_index: float        # 0.0–10.0 — índice qualitativo estimado (editável)
    context_window_k: int       # tamanho de contexto em K tokens
    notes: str = ""             # ex: "free tier available", "deprecated"


@dataclass
class AgentTokenProfile:
    agent_name: str         # ex: "bpmn", "minutes" — deve coincidir com BaseAgent.name
    display_name: str       # ex: "Agente BPMN"
    avg_input_tokens: int   # estimativa heurística base
    avg_output_tokens: int
    source: str = "heuristic"       # "historical" | "heuristic"
    context_multiplier: float = 1.0  # fator de escala com tamanho da transcrição


@dataclass
class ScenarioConfig:
    name: str
    assignments: dict = field(default_factory=dict)   # agent_name → model_id
    n_bpmn_runs: int = 1
    active_agents: list = field(default_factory=list)  # agent_names habilitados


@dataclass
class ScenarioResult:
    scenario_name: str
    total_cost_usd: float
    per_agent: dict = field(default_factory=dict)   # agent_name → USD
    avg_quality_index: float = 0.0
    cost_per_quality: float = 0.0
    warnings: list = field(default_factory=list)


# ── Catálogo de preços ────────────────────────────────────────────────────────
# Providers mapeados para as chaves exatas de AVAILABLE_PROVIDERS em config.py.
# NF-2: ao adicionar novo provider em config.py, adicionar entradas aqui.

PRICING_CATALOG: list[ModelPricing] = [
    # ── DeepSeek ──────────────────────────────────────────────────────────────
    ModelPricing("DeepSeek", "deepseek-chat",     "DeepSeek Chat",      0.27, 1.10, 7.5,   64,
                 notes="deprecated 24/07/2026"),
    ModelPricing("DeepSeek", "deepseek-reasoner", "DeepSeek Reasoner",  0.55, 2.19, 8.5,   64),
    ModelPricing("DeepSeek", "deepseek-v4-flash", "DeepSeek V4 Flash",  0.10, 0.28, 7.0,  128),
    ModelPricing("DeepSeek", "deepseek-v4-pro",   "DeepSeek V4 Pro",    0.27, 1.10, 8.0,  128),
    # ── Claude (Anthropic) ────────────────────────────────────────────────────
    ModelPricing("Claude (Anthropic)", "claude-haiku-4-5-20251001", "Claude Haiku 4.5",   0.80,  4.00, 7.8, 200),
    ModelPricing("Claude (Anthropic)", "claude-sonnet-4-20250514",  "Claude Sonnet 4.6",  3.00, 15.00, 9.2, 200),
    ModelPricing("Claude (Anthropic)", "claude-opus-4-5",           "Claude Opus 4.5",   15.00, 75.00, 9.8, 200),
    # ── OpenAI ────────────────────────────────────────────────────────────────
    ModelPricing("OpenAI", "gpt-4o-mini", "GPT-4o Mini", 0.15,  0.60, 7.5, 128),
    ModelPricing("OpenAI", "gpt-4o",      "GPT-4o",      2.50, 10.00, 9.0, 128),
    ModelPricing("OpenAI", "o3-mini",     "o3-mini",     1.10,  4.40, 8.8, 200),
    # ── Groq (Llama) ──────────────────────────────────────────────────────────
    ModelPricing("Groq (Llama)", "llama-3.3-70b-versatile", "Llama 3.3 70B",  0.06, 0.06, 7.0, 128),
    ModelPricing("Groq (Llama)", "llama-3.1-8b-instant",    "Llama 3.1 8B",   0.05, 0.08, 6.0, 128),
    # ── Google Gemini ─────────────────────────────────────────────────────────
    ModelPricing("Google Gemini", "gemini-2.0-flash", "Gemini 2.0 Flash", 0.10,  0.40, 7.8, 1000,
                 notes="free tier available"),
    ModelPricing("Google Gemini", "gemini-2.5-pro",   "Gemini 2.5 Pro",   1.25, 10.00, 9.0, 1000),
    # ── Grok (xAI) ────────────────────────────────────────────────────────────
    ModelPricing("Grok (xAI)", "grok-4-1-fast-reasoning", "Grok 4.1 Fast",  0.20,  0.50, 8.0, 2000),
    ModelPricing("Grok (xAI)", "grok-3",                  "Grok 3",         3.00, 15.00, 8.5,  131),
    ModelPricing("Grok (xAI)", "grok-3-mini",             "Grok 3 Mini",    0.30,  0.50, 7.5,  131),
]


# ── Perfis heurísticos de tokens por agente ───────────────────────────────────
# Usados quando não há histórico Supabase disponível.
# avg_input_tokens / avg_output_tokens calibrados para transcrição de ~1500 palavras.

DEFAULT_TOKEN_PROFILES: list[AgentTokenProfile] = [
    AgentTokenProfile("transcript_quality", "Agente Qualidade",     800,  300, context_multiplier=0.5),
    AgentTokenProfile("bpmn",               "Agente BPMN",         3500, 1200, context_multiplier=1.5),
    AgentTokenProfile("minutes",            "Agente Ata",          3500,  800, context_multiplier=1.2),
    AgentTokenProfile("requirements",       "Agente Requisitos",   3500, 1500, context_multiplier=1.2),
    AgentTokenProfile("sbvr",               "Agente SBVR",         2000,  600, context_multiplier=0.8),
    AgentTokenProfile("bmm",                "Agente BMM",          2000,  500, context_multiplier=0.8),
    AgentTokenProfile("synthesizer",        "Agente Síntese",      5000, 2000, context_multiplier=2.0),
    AgentTokenProfile("dmn",                "Agente DMN",          2000,  600, context_multiplier=0.8),
    AgentTokenProfile("argumentation",      "Agente IBIS",         2000,  600, context_multiplier=0.8),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_effective_catalog(overrides: Optional[dict] = None) -> list[ModelPricing]:
    """Retorna o catálogo com overrides do usuário aplicados."""
    if not overrides:
        return list(PRICING_CATALOG)
    result = []
    for m in PRICING_CATALOG:
        ov = overrides.get(m.model_id)
        if ov:
            m = ModelPricing(
                provider=m.provider,
                model_id=m.model_id,
                label=m.label,
                input_price_per_1m=float(ov.get("input_price_per_1m", m.input_price_per_1m)),
                output_price_per_1m=float(ov.get("output_price_per_1m", m.output_price_per_1m)),
                quality_index=float(ov.get("quality_index", m.quality_index)),
                context_window_k=m.context_window_k,
                notes=m.notes,
            )
        result.append(m)
    return result


def get_catalog_by_model(catalog: list[ModelPricing]) -> dict[str, ModelPricing]:
    return {m.model_id: m for m in catalog}


def get_providers_in_catalog(catalog: list[ModelPricing]) -> list[str]:
    seen: list[str] = []
    for m in catalog:
        if m.provider not in seen:
            seen.append(m.provider)
    return seen


def get_models_for_provider(provider: str, catalog: list[ModelPricing]) -> list[ModelPricing]:
    return [m for m in catalog if m.provider == provider]


def cheapest_model(catalog: list[ModelPricing]) -> ModelPricing:
    return min(catalog, key=lambda m: m.input_price_per_1m + m.output_price_per_1m)


def best_quality_model(catalog: list[ModelPricing]) -> ModelPricing:
    return max(catalog, key=lambda m: m.quality_index)


def estimate_tokens(profile: AgentTokenProfile, word_count: int) -> tuple[int, int]:
    """
    Escala estimativas de tokens linearmente com word_count.
    Fórmula: estimated_input = base_input + (words / 750) * context_multiplier * 100
    Output escala de forma mais conservadora.
    """
    base_words = 1500
    scale = word_count / base_words if word_count > 0 else 1.0
    inp = int(profile.avg_input_tokens + (word_count / 750) * profile.context_multiplier * 100)
    out = int(profile.avg_output_tokens * (1 + (scale - 1) * 0.3))
    out = max(out, int(profile.avg_output_tokens * 0.5))  # floor: 50% do base
    return inp, out


def project_cost(
    scenario: ScenarioConfig,
    word_count: int,
    catalog: list[ModelPricing],
) -> ScenarioResult:
    """
    Projeta o custo estimado de um cenário dado o tamanho da transcrição.
    Cálculo 100% local — sem LLM, sem Supabase, < 200 ms (NF-1, NF-3).
    """
    catalog_by_model = get_catalog_by_model(catalog)
    profiles_by_name = {p.agent_name: p for p in DEFAULT_TOKEN_PROFILES}

    per_agent: dict[str, float] = {}
    quality_weighted_sum = 0.0
    total_output_tokens = 0
    warnings: list[str] = []

    active = scenario.active_agents if scenario.active_agents else [p.agent_name for p in DEFAULT_TOKEN_PROFILES]

    for agent_name in active:
        model_id = scenario.assignments.get(agent_name)
        if not model_id:
            continue

        profile = profiles_by_name.get(agent_name)
        if not profile:
            continue

        pricing = catalog_by_model.get(model_id)
        if not pricing:
            warnings.append(f"{agent_name}: modelo '{model_id}' não encontrado no catálogo.")
            continue

        n_runs = scenario.n_bpmn_runs if agent_name == "bpmn" else 1
        inp, out = estimate_tokens(profile, word_count)
        inp *= n_runs
        out *= n_runs

        cost = (inp * pricing.input_price_per_1m + out * pricing.output_price_per_1m) / 1_000_000
        per_agent[agent_name] = cost
        quality_weighted_sum += pricing.quality_index * out
        total_output_tokens += out

    total_cost = sum(per_agent.values())
    avg_quality = quality_weighted_sum / total_output_tokens if total_output_tokens > 0 else 0.0
    cost_per_quality = total_cost / avg_quality if avg_quality > 0 else 0.0

    return ScenarioResult(
        scenario_name=scenario.name,
        total_cost_usd=total_cost,
        per_agent=per_agent,
        avg_quality_index=avg_quality,
        cost_per_quality=cost_per_quality,
        warnings=warnings,
    )
