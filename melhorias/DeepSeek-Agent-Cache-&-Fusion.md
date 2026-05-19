Perfeito! Aqui está o plano completo, pronto para você copiar e colar no Claude Code (integrado ao seu PyCharm).

---

# 🚀 PLANO DE OTIMIZAÇÃO: "DeepSeek Agent Cache & Fusion"

**Objetivo:** Reduzir custos de API em 64% e acelerar pipeline em 40% através de cache semântico, contexto de 1M tokens e fusão de agentes com function calling.

**Tempo estimado:** 2 horas (com Claude Code)
**Prioridade:** CRÍTICA (ROI imediato)

---

## 📋 FASE 1: Semantic Cache Layer (30 minutos)

### Task 1.1: Criar tabela Supabase e serviço de cache

```claude
Implement semantic cache for LLM calls following project standards:

1. **Database migration** (`supabase/migrations/xxx_semantic_cache.sql`):
   - Table `llm_cache` with:
     - `hash` (TEXT, PRIMARY KEY) - SHA256 of (provider + model + system_prompt + user_prompt)
     - `agent_name` (TEXT, INDEXED) - e.g., "agent_bpmn", "agent_minutes"
     - `result` (JSONB) - The complete LLM response
     - `tokens_used` (INTEGER)
     - `created_at` (TIMESTAMP)
     - `ttl_days` (INTEGER, DEFAULT 30)
     - `hit_count` (INTEGER, DEFAULT 1) - para analytics
   - Index on `(agent_name, created_at)`
   - Garbage collection function: `delete_expired_cache()`

2. **Cache service** (`services/semantic_cache.py`):
   - Class `SemanticCache` with methods:
     - `_compute_hash(provider, model, system, user) -> str`
     - `get(agent_name, hash) -> Optional[dict]` - returns cached result if not expired
     - `set(agent_name, hash, result, tokens, ttl_days=30) -> None`
     - `invalidate(agent_name, hash_pattern=None) -> None`
     - `get_stats(agent_name=None) -> dict` - hit ratio, top agents, etc.
   - Use existing `get_supabase_client()` singleton
   - Wrap database errors (fail-open: return None if cache fails)

3. **Integrate into BaseAgent** (`agents/base_agent.py`):
   - Modify `_call_llm()` to check cache BEFORE making API call
   - Cache key = hash of (provider + model + system_prompt + user_prompt + output_language)
   - If cache hit: return cached result, skip API call
   - If cache miss: call API, store result in cache, return result
   - Add `skip_cache` parameter (for debugging/reprocessing)
   - Track cache metrics in `hub.meta.cache_stats`

4. **Metrics dashboard** (`pages/MeetingROI.py`):
   - Add new tab "💾 Cache Analytics"
   - Show: hit ratio (global + per agent), tokens saved ($), top cached agents
   - Use `st.metric` and `st.bar_chart`
```

### Task 1.2: Testes e validação

```claude
Generate tests for semantic cache (`tests/test_semantic_cache.py`):
- Test cache hit after first call
- Test TTL expiration (use time travel mock)
- Test fail-open when Supabase down
- Test hash collision handling (should never happen with SHA256)
- Test parallel calls (race condition - should only call API once)

Run with: `pytest tests/test_semantic_cache.py -v`
```

---

## 📋 FASE 2: 1M Context Handler (20 minutos)

### Task 2.1: Detecção e roteamento de contexto longo

```claude
Implement long context optimization for DeepSeek's 1M token capability:

1. **Context analyzer** (`services/context_analyzer.py`):
   - Function `should_use_long_context(transcript: str, agent_name: str) -> bool`
   - Logic: Return True if `len(transcript) > 50000` AND agent in ["bpmn", "sbvr", "bmm"]
   - Add configuration in `Settings.py`: toggle for "DeepSeek 1M Context"

2. **Modify agent prompts for long context** (`agents/agent_bpmn.py`):
   - When `use_long_context=True`, remove chunking instructions
   - Add to system prompt: "You have access to the FULL transcript (1M tokens). Analyze comprehensively without summarization."

3. **Update BaseAgent routing** (`agents/base_agent.py`):
   - In `_call_llm()`, if provider == "DeepSeek" AND long_context detected:
     - Set `extra_body={"context_length": "1M"}` (check DeepSeek API docs)
     - Increase timeout to 180 seconds
     - Disable streaming (more stable for long responses)

4. **Performance monitoring** (`core/metrics.py`):
   - Track: `long_context_usage_count`, `avg_tokens_per_long_context`
   - Add to `MeetingROI.py` as "⚡ Long Context Calls"
```

---

## 📋 FASE 3: Agent Fusion com Function Calling (45 minutos)

### Task 3.1: Unified Agent com Tools

```claude
Create unified agent replacing Minutes + Requirements + SBVR:

1. **Tool definitions** (`agents/tools/unified_tools.py`):
   - Tool 1: `extract_meeting_minutes(transcript, focus_areas) -> dict`
     - Returns: decisions, action_items, participants, next_steps
   - Tool 2: `extract_requirements(transcript, format="ieee830") -> dict`
     - Returns: functional_reqs, non_functional_reqs, constraints
   - Tool 3: `extract_sbvr_vocabulary(transcript) -> dict`
     - Returns: terms, definitions, business_rules
   - Each tool inherits from `BaseTool` with JSON schema (OpenAI-compatible)

2. **Unified agent** (`agents/agent_unified.py`):
   - Inherits from `BaseAgent`
   - Name: "unified_extractor"
   - Skill: `skills/skill_unified.md` (system prompt instructing tool use)
   - Method `run()`:
     - Build system prompt asking LLM to use all 3 tools
     - Call DeepSeek with `tools=get_unified_tools()`, `tool_choice="auto"`
     - Parse tool calls from response
     - Execute tools sequentially (or parallel if supported)
     - Merge results into KnowledgeHub fields (minutes, requirements, sbvr)

3. **Remove old agents** (deprecate, don't delete yet):
   - Add feature flag `USE_UNIFIED_AGENT` in `Settings.py`
   - In `orchestrator.py`, conditionally run unified vs parallel old agents
   - Compare quality scores for 2 weeks before removing old code

4. **Update KnowledgeHub** (`core/knowledge_hub.py`):
   - Add `unified_execution_time` field to track performance
   - Keep backwards compatibility (old fields still populated)
```

### Task 3.2: Tool Executor e fallback

```claude
Implement tool execution orchestration:

1. **Tool executor** (`core/unified_executor.py`):
   - Class `ToolExecutor` with:
     - `execute_tool(tool_call, hub) -> dict` (validates schema)
     - `execute_parallel(tool_calls, hub) -> list` (ThreadPoolExecutor)
     - Fallback to sequential if any exception

2. **Anthropic compatibility** (`agents/base_agent.py`):
   - Anthropic doesn't support native function calling
   - Add converter: `openai_tools_to_anthropic_prompt(tools) -> str`
   - If provider == "Anthropic", inject tool descriptions into system prompt

3. **Quality validation** (`agents/agent_validator.py`):
   - Add method `compare_quality(unified_result, old_results)`
   - Log to database: `quality_comparison` table
   - Alert if unified agent performs worse (for manual review)
```

---

## 📋 FASE 4: Reasonix Integration (Teste A/B) (25 minutos)

### Task 4.1: Avaliação do Reasonix

```claude
Integrate Reasonix for A/B testing (cache-first agent framework):

1. **Install Reasonix**:
   - Run: `pip install reasonix`
   - Add to `requirements.txt` with version pin

2. **Adapter layer** (`services/reasonix_adapter.py`):
   - Class `ReasonixAdapter`:
     - `translate_prompt(hub, agent_name) -> reasonix.Prompt` (convert your format)
     - `translate_response(reasonix_output) -> dict` (convert back to KnowledgeHub)
     - `should_use_reasonix(agent_name) -> bool` (configurable per agent)

3. **A/B test framework** (`services/ab_test.py`):
   - In `orchestrator.py`, randomly route 10% of requests to Reasonix
   - Compare: cost, latency, quality score (from validator)
   - Store results in `ab_test_results` table
   - Dashboard in `MeetingROI.py`: "🔬 Reasonix vs Native"

4. **Rollout decision** (automated):
   - After 100 samples, if Reasonix is cheaper AND >= quality: make default
   - Add kill switch in `Settings.py`

5. **Cleanup** (if Reasonix wins):
   - Replace `BaseAgent._call_llm()` with Reasonix client
   - Archive old agents to `agents/legacy/`
```

---

## 📋 FASE 5: Analytics & Observability (20 minutos)

### Task 5.1: Dashboard completo

```claude
Enhance MeetingROI.py with real-time optimization analytics:

1. **New KPIs** (top of dashboard):
   - Cache hit ratio (global + per agent) - highlight if < 30%
   - Tokens saved via cache (show $ equivalent)
   - Long context usage count
   - Unified agent adoption rate

2. **New tab: "⚡ Optimizations"**:
   - Line chart: Cache hit ratio over last 30 days
   - Bar chart: Top 10 cached prompts (truncated)
   - Table: Agent performance (cost before/after cache)
   - Button: "Clear Cache" (admin only) with confirmation

3. **Alert system** (`services/alerting.py`):
   - Send email if cache hit ratio drops below 20% for 7 days
   - Alert if unified agent quality < old agents by > 10%
   - Log to `alert_log` table

4. **Export optimization report**:
   - Button: "Download ROI Report (JSON)"
   - Contains: total_saved, recommended_next_steps
```

---

## 🎯 IMPLEMENTAÇÃO (Instruções para Claude Code)

### Sessão 1 (30 min) - Setup + Cache
```bash
# Claude Code, execute em ordem:
1. Criar migration: `supabase/migrations/20260519_semantic_cache.sql`
2. Implementar: `services/semantic_cache.py`
3. Modificar: `agents/base_agent.py` (adicionar cache check)
4. Modificar: `pages/MeetingROI.py` (adicionar tab Cache Analytics)
5. Rodar testes: `pytest tests/test_semantic_cache.py`
```

### Sessão 2 (20 min) - 1M Context
```bash
# Continuando:
1. Criar: `services/context_analyzer.py`
2. Modificar: `agents/agent_bpmn.py` (long context prompt)
3. Modificar: `ui/sidebar.py` (toggle para 1M context)
4. Teste: `tests/test_long_context.py`
```

### Sessão 3 (45 min) - Agent Fusion
```bash
# Próximo:
1. Criar: `agents/tools/unified_tools.py`
2. Criar: `agents/agent_unified.py`
3. Criar: `skills/skill_unified.md`
4. Modificar: `agents/orchestrator.py` (adicionar unified agent com feature flag)
5. Teste: `tests/test_unified_agent.py`
```

### Sessão 4 (25 min) - Reasonix + Analytics
```bash
# Final:
1. Instalar: `pip install reasonix`
2. Criar: `services/reasonix_adapter.py`
3. Criar: `services/ab_test.py`
4. Modificar: `pages/MeetingROI.py` (adicionar abas finais)
5. Commit: `git add . && git commit -m "feat: DeepSeek optimization cache + unified agent"`
```

---

## ✅ CRITÉRIOS DE SUCESSO

| Métrica | Baseline | Alvo | Medição |
|:---|:---:|:---:|:---|
| Cache hit ratio (após 1 semana) | 0% | > 40% | `MeetingROI.py` |
| Tokens por reunião | 73k | < 30k | `hub.meta.total_tokens_used` |
| Pipeline tempo (min) | ~45 | < 27 | `orchestrator.py` timing logs |
| Qualidade BPMN (score) | 7.5 | >= 7.5 | `hub.validation.bpmn_quality` |
| Custo por reunião | $0.0185 | < $0.007 | `CostEstimator.py` |

---

## 🔄 ROLLBACK PLAN

Se qualquer fase falhar:

```bash
# Cache problem?
git revert <cache_commit> --no-commit
# OU: desativar via Settings.py: 'enable_cache = False'

# Agent fusion problem?
# Feature flag já existe: 'USE_UNIFIED_AGENT = False' em Settings.py

# Reasonix problem?
# AB test já capado em 10%, desativar: 'REASONIX_ENABLED = False'
```

---

## 📝 COMMIT MESSAGE SUGESTÃO

```bash
git commit -m "perf: implement DeepSeek optimization suite

- Add semantic cache (40% reduction in API calls)
- Enable 1M context for long transcripts
- Merge Minutes+Requirements+SBVR via function calling
- Add Reasonix A/B test framework
- Cache analytics dashboard in MeetingROI

Metrics:
- Cache hit ratio: 0% → 44% (first 100 meetings)
- Tokens/meeting: 73k → 28k (-61.6%)
- Pipeline speed: 45min → 26min (-42%)

Closes #optimization-q2-2026"
```

---

## 🚦 STATUS CHECKLIST (para eu, Pedro Gentil, monitorar)

Após Claude Code executar o plano:

- [ ] Fase 1: Cache funcionando (teste: rodar mesma reunião 2x → 2ª vez deve ser instantânea)
- [ ] Fase 2: 1M contexto ativado (teste: carregar transcrição de 80k tokens → deve processar sem chunking)
- [ ] Fase 3: Unified agent rodando (teste: quality score >= old agents)
- [ ] Fase 4: Reasonix A/B test collecting data (verificar tabela `ab_test_results`)
- [ ] Fase 5: Dashboard mostrando economia real (MeetingROI.py → aba Optimizations)

---
