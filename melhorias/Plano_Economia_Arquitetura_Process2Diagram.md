
# 📋 PLANO DE ECONOMIA — Otimização da Arquitetura Process2Diagram
## Submissão ao Claude Code (Implementador Sênior)
## Data: 30 de junho de 2026 | Versão: v4.58
## Orçamento: Limitado | Objetivo: Reduzir custo de LLM sem perder qualidade

---

## 🎯 OBJETIVO

Reduzir o custo mensal de chamadas LLM do pipeline Process2Diagram em **30-50%** 
através de otimizações arquiteturais — sem degradar a qualidade dos artefatos gerados 
(BPMN, Ata, Requisitos, SBVR, BMM, Synthesizer).

---

## 📊 BASELINE ATUAL

| Métrica | Valor Atual | Fonte |
|---------|-------------|-------|
| Custo DeepSeek API | ~$3/mês | Dashboard DeepSeek |
| Custo OpenAI API | ~$0-5/mês | Dashboard OpenAI (embeddings) |
| Provider default | DeepSeek V4 Flash | `modules/config.py` |
| Embedding provider | OpenAI text-embedding-3-small | `modules/embeddings.py` |
| Semantic Cache | Implementado | `services/semantic_cache.py` |
| Batch embeddings | Implementado | `embed_batch()` em `modules/embeddings.py` |
| n_bpmn_runs default | 3 | `core/session_state.py` |
| use_langgraph | True | `core/session_state.py` |

---

## 🔧 OTIMIZAÇÕES ARQUITETURAIS A IMPLEMENTAR

### 1. ATIVAR E AUDITAR O SEMANTIC CACHE (Impacto: Alto)

**Problema:** O Semantic Cache (`services/semantic_cache.py`) pode não estar integrado 
em todos os agentes do pipeline. Chamadas idênticas ou semelhantes são reprocessadas 
sem necessidade.

**Ação:**
- [ ] Verificar se `_call_llm()` em `agents/base_agent.py` consulta o Semantic Cache 
      ANTES de toda chamada de API
- [ ] Garantir que a chave de cache use o texto PÓS-sanitização PII (para evitar 
      misses por nomes diferentes)
- [ ] Adicionar métrica `cache_hit_rate` ao `LLMTelemetry` para monitoramento
- [ ] Definir TTL apropriado por tipo de agente:
  - AgentBPMN: 7 dias (estruturas de processo são estáveis)
  - AgentMinutes: 1 dia (atas são específicas por reunião)
  - AgentRequirements: 3 dias
  - AgentSBVR/BMM: 7 dias

**Economia estimada:** 30-50% em chamadas repetidas durante desenvolvimento e testes.

---

### 2. OTIMIZAR EMBEDDING PIPELINE (Impacto: Médio-Alto)

**Problema:** Embeddings podem estar sendo gerados um a um (`embed_text`) em vez 
de em batch (`embed_batch`), ou chunks podem estar sobrepostos demais.

**Ação:**
- [ ] Auditar `modules/embeddings.py`:
  - Verificar se `chunk_text(transcript, 500, 80)` está otimizado
  - Testar se overlap de 80 tokens é necessário ou se 40-50 é suficiente
  - Reduzir overlap = menos chunks = menos embeddings
- [ ] Garantir que `embed_batch()` seja usado em TODOS os pontos de ingestão:
  - `modules/document_store.py` → `embed_document()`
  - `agents/agent_document_extractor.py` → extração de documentos
  - `pages/TranscriptBackfill.py` → backfill de transcrições
- [ ] Implementar deduplicação de chunks antes de embedding:
  - Hash SHA-256 do chunk como chave
  - Não re-embedar chunks idênticos em reprocessamentos

**Economia estimada:** 20-40% em custo de embeddings OpenAI.

---

### 3. REDUZIR N_BPMN_RUNS ADAPTATIVAMENTE (Impacto: Médio)

**Problema:** `n_bpmn_runs=3` é fixo, mas nem toda transcrição precisa de 3 runs 
+ tournament do AgentValidator.

**Ação:**
- [ ] Implementar lógica adaptativa em `core/pipeline.py`:
  - Transcrição nota A ou B (AgentTranscriptQuality): `n_bpmn_runs=1` ou `2`
  - Transcrição nota C: `n_bpmn_runs=2`
  - Transcrição nota D ou E: `n_bpmn_runs=3` (fallback)
- [ ] Adicionar flag `adaptive_bpmn_runs` em `core/session_state.py` (default: True)
- [ ] O tournament do AgentValidator só executa quando `n_bpmn_runs > 1`

**Economia estimada:** 20-30% em chamadas do AgentBPMN para transcrições de boa qualidade.

---

### 4. CONDICIONAR AGENTES OPCIONAIS (Impacto: Médio)

**Problema:** Agentes opcionais (SBVR, BMM, Synthesizer, DMN, Argumentation, CKF) 
podem estar rodando mesmo quando não há valor agregado para o tipo de reunião.

**Ação:**
- [ ] Usar o `classify_meeting_type()` do `MeetingROI.py` para decidir quais 
      agentes executar:
  - Reunião "Técnica/Operacional": BPMN + Minutes + Requirements (pular SBVR/BMM)
  - Reunião "Estratégica": BPMN + Minutes + Requirements + SBVR + BMM + Synthesizer
  - Reunião "Descoberta": BPMN + Minutes + Requirements + DMN
  - Reunião "Curta/Rápida": Minutes apenas
- [ ] Mapear `meeting_type` → conjunto de agentes em `core/orchestrator.py`
- [ ] Permitir override manual via sidebar (manter flexibilidade)

**Economia estimada:** 15-25% em reuniões que não precisam de todos os artefatos.

---

### 5. OTIMIZAR PROMPTS DOS SKILLS (Impacto: Baixo-Médio)

**Problema:** Os arquivos `skills/*.md` podem ter instruções redundantes ou 
mais longas do que necessário, aumentando tokens de entrada.

**Ação:**
- [ ] Revisar cada skill file para:
  - Eliminar redundâncias entre system prompt e user prompt
  - Usar exemplos few-shot em vez de descrições longas (onde aplicável)
  - Remover instruções genéricas que já estão em `BaseAgent._load_skill()`
- [ ] Prioridade de revisão (maior uso → maior impacto):
  1. `skills/skill_bpmn.md` (agente mais chamado)
  2. `skills/skill_minutes.md`
  3. `skills/skill_transcript_quality.md`
  4. `skills/skill_requirements.md`
  5. Demais skills

**Economia estimada:** 5-15% em tokens de entrada por chamada.

---

### 6. IMPLEMENTAR EARLY EXIT NO PIPELINE (Impacto: Baixo-Médio)

**Problema:** Se a transcrição for de qualidade muito baixa (nota E), o pipeline 
continua processando e gera artefatos inúteis.

**Ação:**
- [ ] Em `core/pipeline.py`, após `AgentTranscriptQuality`:
  - Nota E → parar pipeline, retornar aviso ao usuário com sugestões de melhoria
  - Nota D → executar apenas Minutes (resumo básico), pular BPMN/Requirements
- [ ] Adicionar flag `early_exit_on_poor_quality` em `core/session_state.py`

**Economia estimada:** 10-20% em transcrições de baixa qualidade (evita processamento inútil).

---

### 7. CONSOLIDAR CHAMADAS DE EMBEDDING NO DOCUMENT MANAGER (Impacto: Baixo)

**Problema:** Upload de documentos no `DocumentManager.py` pode gerar múltiplas 
chamadas de embedding separadas.

**Ação:**
- [ ] Em `modules/document_store.py`, garantir que `upload_document()` + `embed_document()` 
      usem `embed_batch()` com TODOS os chunks do documento de uma vez
- [ ] Implementar queue de embeddings para processamento em background (se não existir)

**Economia estimada:** 10-15% em ingestão de documentos.

---

## 📈 MÉTRICAS DE ACOMPANHAMENTO

Implementar ou verificar em `pages/LLMBenchmark.py` e `pages/CostEstimator.py`:

| Métrica | Como Medir | Meta |
|---------|-----------|------|
| Cache hit rate | `hub.meta.cache_hits / total_calls` | > 40% |
| Custo por reunião | `CostEstimator.project_cost()` / n_reuniões | < $0.05 |
| Tokens por reunião | Soma de `tokens_in` no `LLMTelemetry` | Redução de 20% |
| n_bpmn_runs médio | Média de `n_bpmn_runs` usado | < 2.0 |
| Agentes executados por reunião | Contagem no `Orchestrator._PLAN` | Redução de 15% |

---

## 🗓️ CRONOGRAMA DE IMPLEMENTAÇÃO

| Semana | Foco | Arquivos Principais | Entregável |
|--------|------|---------------------|------------|
| 1 | Semantic Cache audit | `services/semantic_cache.py`, `agents/base_agent.py` | Cache ativo em 100% dos agentes |
| 2 | Embedding pipeline | `modules/embeddings.py`, `modules/document_store.py` | Batch + deduplicação |
| 3 | Adaptive n_bpmn_runs | `core/pipeline.py`, `core/session_state.py` | Lógica adaptativa implementada |
| 4 | Agentes condicionais | `core/orchestrator.py`, `pages/MeetingROI.py` | Mapeamento tipo→agentes |
| 5 | Prompt optimization | `skills/*.md` | Skills revisados e enxutos |
| 6 | Early exit + testes | `core/pipeline.py`, `tests/` | Pipeline com early exit |

---

## ✅ CRITÉRIOS DE ACEITE

- [ ] Custo mensal de API DeepSeek reduzido em pelo menos 30%
- [ ] Custo mensal de API OpenAI (embeddings) reduzido em pelo menos 20%
- [ ] Qualidade dos artefatos mantida (score do AgentValidator não cai)
- [ ] Nenhuma funcionalidade removida (apenas otimizada)
- [ ] Métricas de telemetria atualizadas e visíveis no LLMBenchmark
- [ ] Documentação no `claude_guideline/roadmap.md` atualizada

---

## 📝 NOTAS PARA O CLAUDE CODE

> Este plano deve ser implementado incrementalmente, uma otimização por vez.
> Cada otimização deve ser testada isoladamente antes de prosseguir para a próxima.
> Priorizar itens 1-3 (maior impacto) antes de 4-7.
> Manter backward compatibility: todas as flags devem ser opt-in via session_state.

---

*Plano gerado em 30/06/2026 para submissão ao Claude Code.*
*Revisar após implementação de cada fase.*
