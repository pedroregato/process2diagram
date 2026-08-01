# Proposta de Melhoria: Observabilidade do Pipeline Extractor/Synthesizer

**Projeto:** Vichara (ex-process2diagram)
**Módulo alvo:** Live Transcription (Extractor + Synthesizer)
**Tipo:** Feature de instrumentação/observabilidade, não muda comportamento funcional existente
**Prioridade sugerida:** Média (não bloqueia entregas, mas cresce em valor conforme mais sessões ao vivo rodam em produção)

---

## 1. Problema

Hoje o Extractor e o Synthesizer rodam sem nenhum registro estruturado de desempenho ou qualidade. Não há como responder, sem abrir logs manualmente:

- O Extractor está demorando mais a cada segmento conforme a sessão cresce?
- Qual a proporção de eventos extraídos com baixa confiança numa sessão problemática?
- O Synthesizer está reconstruindo artefatos cada vez maiores sem ganho proporcional de clareza?
- Alguma sessão específica teve erro silencioso de um dos dois agentes?

Sem esses dados, qualquer degradação de qualidade (ex.: Extractor "alucinando" fatos, Synthesizer perdendo contexto em sessões longas) só é percebida quando o usuário reclama.

## 2. Solução proposta

Criar uma tabela `pipeline_metrics` no Supabase e instrumentar `extractor_agent.py` e `synthesizer_agent.py` para gravar uma linha por execução, seguindo os padrões já estabelecidos no projeto (`project_id` isolation, RLS, `migrate()` idempotente).

### 2.1 Schema

```sql
create table if not exists pipeline_metrics (
    id                    uuid primary key default gen_random_uuid(),
    project_id            uuid not null references projects(id) on delete cascade,
    session_id            uuid references live_sessions(id) on delete cascade,
    agent                 text not null check (agent in ('extractor','synthesizer')),
    run_started_at        timestamptz not null,
    duration_ms           integer not null,
    input_events_count    integer,      -- nº de session_events lidos (Synthesizer)
    output_events_count   integer,      -- nº de eventos novos gerados (Extractor)
    low_confidence_ratio  numeric,      -- % de eventos com confianca baixa
    artifact_size_chars   integer,      -- tamanho do artefato gerado
    clarity_index         numeric,      -- índice de clareza (Synthesizer)
    llm_provider          text,
    model                 text,
    tokens_in             integer,
    tokens_out            integer,
    error                 text,         -- null se sucesso
    metadata              jsonb not null default '{}'::jsonb
);

create index if not exists idx_pipeline_metrics_project on pipeline_metrics(project_id);
create index if not exists idx_pipeline_metrics_session on pipeline_metrics(session_id);
```

Adicionar essa criação à função `migrate()` existente, seguindo o padrão idempotente já usado (checar `information_schema` antes de criar).

### 2.2 Módulo de logging

Criar `pipeline_metrics_logger.py` com uma função única de gravação, para evitar duplicar lógica de insert nos dois agentes:

```python
def log_pipeline_run(
    project_id: str,
    session_id: str | None,
    agent: str,  # 'extractor' | 'synthesizer'
    run_started_at: datetime,
    duration_ms: int,
    input_events_count: int | None = None,
    output_events_count: int | None = None,
    low_confidence_ratio: float | None = None,
    artifact_size_chars: int | None = None,
    clarity_index: float | None = None,
    llm_provider: str | None = None,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    error: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Grava uma linha de métrica em pipeline_metrics. Falha silenciosamente
    (log local apenas) para nunca quebrar o fluxo principal do agente."""
    ...
```

Requisito importante: **essa função nunca deve lançar exceção que interrompa o Extractor/Synthesizer**. Se a gravação da métrica falhar, deve logar localmente (stderr ou logging padrão) e seguir em frente. Observabilidade não pode virar ponto de falha do pipeline principal.

### 2.3 Instrumentação

Em `extractor_agent.py`: envolver a chamada ao LLM com `time.time()` antes/depois, calcular `low_confidence_ratio` a partir dos eventos retornados (proporção com `confianca` abaixo de um limiar, ex. 0.5), e chamar `log_pipeline_run(agent='extractor', ...)` ao final de cada execução — tanto no caminho de sucesso quanto no de erro (`try/except` com `error=str(e)`).

Em `synthesizer_agent.py`: mesma lógica, registrando `input_events_count` (quantos `session_events` foram lidos), `artifact_size_chars` (tamanho do artefato reconstruído) e `clarity_index` (já calculado hoje, apenas persistir).

### 2.4 Dashboard mínimo (opcional nesta entrega)

Se o tempo permitir, adicionar uma aba/expander em `live_app.py` ou um `dashboard.py` separado mostrando, por `session_id`:
- Duração média de execução do Extractor vs Synthesizer (dois gráficos de linha lado a lado)
- `low_confidence_ratio` do Extractor ao longo da sessão
- `clarity_index` do Synthesizer ao longo da sessão

Isso é secundário — pode ficar para uma segunda entrega se o escopo já estiver grande.

## 3. Fora de escopo

- Não alterar a lógica de extração/síntese em si (nenhuma mudança de prompt ou de regras dos agentes).
- Não implementar LLM-as-judge ou avaliação semântica de qualidade nesta etapa — isso fica para uma iteração futura, depois que houver volume de dados real em `pipeline_metrics`.
- Não migrar nomenclatura `project_id` → `context_id` neste trabalho (está deferida até o guard de isolamento de contexto ser implementado).

## 4. Critérios de aceite

- [ ] Tabela `pipeline_metrics` criada via `migrate()` idempotente
- [ ] `pipeline_metrics_logger.py` criado, com falha silenciosa garantida (testar forçando erro de conexão e confirmar que o agente principal não quebra)
- [ ] `extractor_agent.py` grava métrica em toda execução (sucesso e erro)
- [ ] `synthesizer_agent.py` grava métrica em toda execução (sucesso e erro)
- [ ] RLS aplicado na nova tabela seguindo o padrão de `project_id` das demais tabelas
- [ ] Testado manualmente rodando uma sessão live mock e confirmando linhas em `pipeline_metrics` para ambos os agentes
- [ ] Nenhuma mudança de comportamento observável no fluxo funcional existente

## 5. Observação sobre execução

Este trabalho não requer decisões de produto — é puramente instrumentação seguindo padrões já estabelecidos no CLAUDE.md do projeto (Default Decisions: `project_id` isolation, RLS, `migrate()` idempotente, agentes só via Orchestrator). Caso o CLAUDE.md deste projeto instrua consulta antes de agir, e a linha de comando de execução autorizar prosseguir sem pausas, prossiga sem interromper para perguntas — as únicas exceções válidas para pausa seriam ambiguidade real sobre nome de FK (`projects.id`) ou sobre o limiar de `confianca` usado no `low_confidence_ratio`, caso esses não estejam already definidos no código existente.