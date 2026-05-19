## 📋 FASE 2: 1M Context Handler – Plano de Implementação

**Pré‑requisito:** Fase 1 (cache semântico) concluída.  
**Duração estimada:** 20-25 minutos com Claude Code.  
**Objetivo:** Usar os 1M tokens de contexto do DeepSeek para eliminar chunking em transcrições longas (>50k tokens), reduzindo chamadas API e melhorando qualidade.

---

## 🔧 Task 2.1 – Analisador de Contexto (5 min)

Criar módulo para decidir quando usar 1M.

```claude
Create `services/context_analyzer.py`:

1. Function `should_use_long_context(transcript: str, agent_name: str) -> bool`:
   - Input: transcript string, agent name (e.g., "agent_bpmn", "agent_sbvr")
   - Token estimation: `len(transcript) / 4` (rough approximation)
   - Return True if estimated_tokens > 50000 AND agent in LONG_CONTEXT_AGENTS
   - Add configuration: `LONG_CONTEXT_ENABLED = True` (toggle in Settings.py)
   - Log decision reason for debugging

2. Add `LONG_CONTEXT_AGENTS = {"agent_bpmn", "agent_sbvr", "agent_bmm"}` (minutes/requirements already optimized in Phase 3)

3. Function `estimate_tokens(text: str) -> int`:
   - Simple: `len(text) // 4` (Portuguese ~4 chars/token)
   - Optional: use tiktoken for accuracy if available

4. Unit test: `tests/test_context_analyzer.py` with edge cases (empty, 10k, 100k, 500k)
```

---

## 🔧 Task 2.2 – Roteamento no BaseAgent (5 min)

Modificar `_call_llm()` para usar contexto longo quando aplicável.

```claude
Modify `agents/base_agent.py`:

1. In `_call_llm()`, before building API request:
   - Call `should_use_long_context(user_prompt, self.name)`
   - If True and provider == "DeepSeek":
     - Set `use_long_context = True`
     - Increase timeout to 180 seconds (from default 60)
     - Add `extra_body = {"context_length": "1M"}` (check DeepSeek API docs for exact parameter)

2. Add logging to `hub.meta`:
   - `long_context_used: bool`
   - `original_tokens_estimate: int`
   - `context_window: str` ("1M" or "128k")

3. Ensure cache key includes long context flag (so cached responses for 1M are separate from chunked)

4. Fallback: if long context request fails (e.g., model doesn't support), automatically retry with standard context
```

---

## 🔧 Task 2.3 – Atualização dos Prompts dos Agentes (5 min)

Modificar os system prompts para funcionarem bem com contexto completo.

```claude
Update skill files for agents that will use 1M context:

1. `skills/skill_bpmn.md` – add at the beginning:
   ```
   ## INSTRUÇÃO DE CONTEXTO LONGO
   Você receberá a transcrição COMPLETA da reunião (até 1 milhão de tokens).
   NÃO resuma, NÃO chunke. Analise o texto integralmente.
   Mantenha todos os detalhes de processos, atores, decisões e fluxos.
   ```

2. `skills/skill_sbvr.md` – add similar instruction:
   ```
   ## LARGE CONTEXT MODE
   Full transcript provided. Extract ALL business vocabulary and rules without summarization.
   ```

3. `skills/skill_bmm.md` – analogamente.

4. Create helper in `services/context_analyzer.py`:
   - `inject_long_context_instruction(skill_content: str, use_long: bool) -> str`
   - If use_long: prepend instruction, else return original

5. Modify `BaseAgent._load_skill()` to call this helper based on context decision
```

---

## 🔧 Task 2.4 – Otimização do Truncamento (3 min)

Evitar que o agente corte a resposta.

```claude
Modify `agents/base_agent.py` – `_call_with_retry()`:

1. For long context calls, set `max_tokens = 16384` (DeepSeek's max output)
2. Add warning if response hits token limit (truncation)
3. Log `response_truncated` flag in hub.meta

Add to `services/context_analyzer.py`:
- `estimate_output_tokens(agent_name) -> int` – based on typical output length per agent
```

---

## 🔧 Task 2.5 – Dashboard e Métricas (5 min)

Integrar ao `MeetingROI.py` para monitorar uso.

```claude
Enhance `pages/MeetingROI.py`:

1. Add new KPI row:
   - "📏 Long Context Calls" (total count)
   - "📈 Avg Tokens Saved" (compared to chunking baseline)
   - "⚡ Speedup Factor" (latency improvement)

2. New tab "🔬 Long Context" (next to "💾 Cache LLM"):
   - Line chart: long context usage over time (by project)
   - Bar chart: tokens saved per agent (BPMN, SBVR, BMM)
   - Table: each long context call with estimated savings
   - Toggle: enable/disable long context globally (admin)

3. Add to `core/metrics.py` – function `compute_long_context_savings(hub)`:
   - Compare actual tokens vs estimated if chunked (estimate = chunks * overhead)
   - Store in `session_state.long_context_stats`

4. Export report option: "Download Long Context Savings (JSON)"
```

---

## 🔧 Task 2.6 – Testes e Validação (2 min)

```claude
Generate tests in `tests/test_long_context.py`:

1. `test_should_use_long_context()` – thresholds (49k → False, 51k → True)
2. `test_estimate_tokens()` – accuracy within 20%
3. `test_prompt_injection()` – instruction added when long context True
4. `test_fallback_on_failure()` – if 1M fails, retry with standard
5. `test_cache_separation()` – same prompt with/without long context have different cache keys

Run: `pytest tests/test_long_context.py -v`
```

---

## ✅ Critérios de Sucesso para Fase 2

| Métrica | Baseline | Alvo | Onde medir |
|:---|:---:|:---:|:---|
| Chamadas por transcrição longa (>50k tokens) | 10-15 | 1-2 | `hub.meta.total_tokens_used` |
| Tokens por chamada (agente BPMN) | 15k | 25k (mas 1 chamada só) | Dashboard Long Context |
| Tempo de pipeline (transcrição 100k tokens) | ~180s | ~90s | `orchestrator` logs |
| Qualidade BPMN (score) | 7.5 | >= 7.5 | `hub.validation` |
| Uso de long context | 0% | > 30% das chamadas BPMN | Dashboard |

---

## 🚀 Comandos para Claude Code (executar na ordem)

```bash
# 1. Criar analisador de contexto
Claude: "Create services/context_analyzer.py with should_use_long_context(), estimate_tokens(), and LONG_CONTEXT_AGENTS set"

# 2. Modificar BaseAgent
Claude: "Modify agents/base_agent.py _call_llm() to route long context to DeepSeek with timeout=180 and extra_body context_length 1M"

# 3. Atualizar skills dos agentes
Claude: "Prepend long context instruction to skills/skill_bpmn.md, skill_sbvr.md, skill_bmm.md when use_long_context True"

# 4. Dashboard
Claude: "Add Long Context tab to pages/MeetingROI.py with metrics: calls count, tokens saved, speedup factor"

# 5. Testes
Claude: "Create tests/test_long_context.py with 5 unit tests covering thresholds, fallback, cache separation"

# 6. Migração (opcional)
Claude: "Add settings toggle 'enable_long_context' in Settings.py with default True"
```

---

## 📊 Custo-Benefício (Projetado)

Para uma reunião de **100k tokens** (ex: offsite de 4h):

| Abordagem | Chamadas API | Tokens processados | Custo | Tempo |
|:---|:---:|:---:|:---:|:---|
| Chunking (atual, 500 token chunks) | ~200 | 200x500 = 100k | $0.025 | ~45s |
| 1M contexto (Fase 2) | 1 | 100k | $0.025 | ~15s |

**Ganho:** Mesmo custo, **3x mais rápido**, zero perda de contexto entre chunks.

---

## ⚠️ Pontos de Atenção

1. **DeepSeek API pode ter limitação**: Verifique se o parâmetro `context_length` é suportado. Caso contrário, use `max_tokens` de entrada.
2. **Timeout**: Aumente para 180s, mas monitore timeouts reais – algumas respostas longas podem levar >2min.
3. **Cache**: As chaves de cache para 1M contexto devem incluir a flag – você já tem `skip_cache` e o hash base, basta incluir `long_context` no cálculo.
4. **Fallback**: Se o DeepSeek retornar erro (ex: contexto excede máximo), automaticamente refaça com chunking (seu código atual).

---

## 🎯 Próximo Passo Após Fase 2

Com o cache (Fase 1) e 1M contexto (Fase 2) rodando, colete métricas por **3-5 dias**. Depois avalie se ainda vale a pena a Fase 3 (agente unificado com function calling) – o ganho adicional será menor, mas ainda significativo.

**Deseja que eu gere o código completo de cada arquivo (ex: `context_analyzer.py` completo) para você colar diretamente?**