# Guia de Implementação — Knowledge Hub Persistente + Agente de Análise Autônomo
**Process2Diagram v4.16 → v4.17 (PC9)**  
**Para execução via Claude Code CLI no PyCharm**

---

## Leia antes de começar

Este guia cobre duas features estruturalmente distintas que se complementam:

| Feature | O que é | Onde vive |
|---|---|---|
| **A. Knowledge Hub Persistente** | Memória semântica cross-session acumulada sobre processos, entidades, nomenclaturas e contradições detectadas entre versões | Supabase + novo módulo `core/knowledge_store.py` |
| **B. Agente de Análise Autônomo** | Agente que, dado um objetivo analítico em linguagem natural, planeja e executa múltiplas ferramentas em sequência sem o usuário guiar cada passo | `agents/agent_analyst.py` + LangChain ReAct |

**Dependência entre elas:** o Knowledge Hub é a base de conhecimento que o Agente Autônomo consulta e enriquece. Implemente A antes de B.

**O que NÃO muda:**
- O `KnowledgeHub` em `core/knowledge_hub.py` (hub de sessão — não confundir com o novo hub persistente)
- O `AgentAssistant` e o fluxo de tool-use existente
- O Supabase schema existente (apenas novas tabelas são adicionadas)

---

## Feature A — Knowledge Hub Persistente

### Conceito

Hoje, cada pipeline run é isolado. O LLM não sabe que o "processo de onboarding" apareceu em 10 reuniões anteriores, que a entidade "Equipe de Compliance" é recorrente, ou que a versão 3 do processo contradiz a versão 1 em um ponto específico.

O Knowledge Hub Persistente acumula esse conhecimento em Supabase e o injeta automaticamente no contexto do `AgentAssistant` e do novo `AgentAnalyst`, tornando as respostas progressivamente mais ricas.

### Estrutura de dados

Quatro novas tabelas Supabase. Criar em `setup/supabase_schema_knowledge_hub.sql`:

```sql
-- Entidades organizacionais recorrentes (pessoas, times, sistemas, departamentos)
CREATE TABLE IF NOT EXISTS kh_entities (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    entity_type   TEXT NOT NULL,  -- 'person' | 'team' | 'system' | 'department'
    canonical_name TEXT NOT NULL,
    aliases       TEXT[],         -- variações de nome encontradas nas transcrições
    first_seen_meeting_id UUID REFERENCES meetings(id),
    last_seen_meeting_id  UUID REFERENCES meetings(id),
    occurrence_count INT DEFAULT 1,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, canonical_name, entity_type)
);

-- Processos identificados e suas versões semânticas
CREATE TABLE IF NOT EXISTS kh_processes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    process_name  TEXT NOT NULL,
    description   TEXT,
    version_count INT DEFAULT 1,
    first_meeting_id UUID REFERENCES meetings(id),
    last_meeting_id  UUID REFERENCES meetings(id),
    embedding     vector(1536),   -- embedding do nome+descrição para busca semântica
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Fatos e regras de negócio consolidados cross-meeting
CREATE TABLE IF NOT EXISTS kh_facts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID REFERENCES projects(id) ON DELETE CASCADE,
    fact_type     TEXT NOT NULL,  -- 'rule' | 'decision' | 'constraint' | 'nomenclature'
    content       TEXT NOT NULL,  -- o fato em linguagem natural
    source_meeting_ids UUID[],    -- reuniões que fundamentam este fato
    confidence    FLOAT DEFAULT 1.0,
    superseded_by UUID REFERENCES kh_facts(id),  -- se foi substituído por versão mais recente
    embedding     vector(1536),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Contradições detectadas entre versões de processos
CREATE TABLE IF NOT EXISTS kh_contradictions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID REFERENCES projects(id) ON DELETE CASCADE,
    process_name   TEXT,
    description    TEXT NOT NULL,  -- descrição da contradição em linguagem natural
    meeting_a_id   UUID REFERENCES meetings(id),
    meeting_b_id   UUID REFERENCES meetings(id),
    fact_a_id      UUID REFERENCES kh_facts(id),
    fact_b_id      UUID REFERENCES kh_facts(id),
    severity       TEXT DEFAULT 'medium',  -- 'low' | 'medium' | 'high'
    resolved       BOOLEAN DEFAULT FALSE,
    resolution_note TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Índices semânticos
CREATE INDEX IF NOT EXISTS idx_kh_processes_embedding
    ON kh_processes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_kh_facts_embedding
    ON kh_facts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Funções de busca semântica
CREATE OR REPLACE FUNCTION match_kh_processes(
    query_embedding vector(1536),
    match_project_id UUID,
    match_count INT DEFAULT 5
)
RETURNS TABLE (id UUID, process_name TEXT, description TEXT, similarity FLOAT)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT p.id, p.process_name, p.description,
           1 - (p.embedding <=> query_embedding) AS similarity
    FROM kh_processes p
    WHERE p.project_id = match_project_id
      AND p.embedding IS NOT NULL
    ORDER BY p.embedding <=> query_embedding
    LIMIT match_count;
END; $$;

CREATE OR REPLACE FUNCTION match_kh_facts(
    query_embedding vector(1536),
    match_project_id UUID,
    match_count INT DEFAULT 8
)
RETURNS TABLE (id UUID, fact_type TEXT, content TEXT, confidence FLOAT, similarity FLOAT)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT f.id, f.fact_type, f.content, f.confidence,
           1 - (f.embedding <=> query_embedding) AS similarity
    FROM kh_facts f
    WHERE f.project_id = match_project_id
      AND f.embedding IS NOT NULL
      AND f.superseded_by IS NULL   -- apenas fatos ativos
    ORDER BY f.embedding <=> query_embedding
    LIMIT match_count;
END; $$;
```

### Novo módulo `core/knowledge_store.py`

Criar do zero. Responsabilidades: CRUD das 4 tabelas + lógica de detecção de contradições + extração de entidades/fatos via LLM.

```python
# core/knowledge_store.py
# ─────────────────────────────────────────────────────────────────────────────
# Persistent Knowledge Hub — cross-session organizational memory.
#
# Public API:
#   KnowledgeStore(project_id)
#     .ingest_from_hub(hub, meeting_id, llm_config, embed_fn) → IngestReport
#     .search_relevant_context(query, embed_fn, k=5) → KHContext
#     .get_project_summary() → str
#     .list_contradictions(resolved=False) → list[dict]
#     .resolve_contradiction(contradiction_id, note) → None
# ─────────────────────────────────────────────────────────────────────────────
```

#### Método central: `ingest_from_hub()`

Este método é chamado automaticamente ao final de cada pipeline run bem-sucedido. Ele lê o `KnowledgeHub` da sessão e extrai, via LLM, os elementos a persistir:

```
ingest_from_hub(hub, meeting_id, llm_config, embed_fn)
        │
        ├── ExtractEntities(hub.transcript_clean, hub.minutes)
        │     LLM → list[{type, name, aliases}]
        │     → upsert em kh_entities (merge aliases, incrementa occurrence_count)
        │
        ├── ExtractFacts(hub.minutes, hub.requirements, hub.sbvr)
        │     LLM → list[{type, content, confidence}]
        │     → embed cada fato → upsert em kh_facts
        │
        ├── ExtractProcesses(hub.bpmn, hub.minutes)
        │     LLM → list[{name, description}]
        │     → semantic search em kh_processes (similarity > 0.85 = mesmo processo)
        │     → se novo: INSERT; se existente: UPDATE version_count, last_meeting_id
        │
        └── DetectContradictions(new_facts, existing_facts_in_project)
              LLM → list[{fact_a_id, fact_b_id, description, severity}]
              → INSERT em kh_contradictions
              → notificar via st.session_state["_kh_new_contradictions"]
```

#### Método `search_relevant_context()`

Chamado pelo `AgentAssistant` e pelo novo `AgentAnalyst` para enriquecer o contexto:

```python
def search_relevant_context(
    self,
    query: str,
    embed_fn: Callable[[str], list[float]],
    k: int = 5,
) -> KHContext:
    """
    Semantic search across kh_processes + kh_facts.
    Returns KHContext with ranked results ready for prompt injection.
    """
```

#### Dataclass de retorno `KHContext`

```python
@dataclass
class KHContext:
    processes: list[dict]      # {name, description, similarity}
    facts: list[dict]          # {type, content, confidence, similarity}
    entities: list[dict]       # {type, name, occurrences} — keyword match
    contradictions: list[dict] # contradições não resolvidas relevantes à query
    
    def to_prompt_block(self) -> str:
        """Formata como bloco de contexto para injeção no system prompt."""
```

### Novo agente `agents/agent_knowledge_extractor.py`

Agente LLM responsável pela extração estruturada de entidades, fatos e processos a partir do `KnowledgeHub`. Herda de `BaseAgent`. Seu `skill_path` aponta para `skills/skill_knowledge_extractor.md` (a criar).

O agente recebe um prompt com excertos do hub e retorna JSON com três listas:
```json
{
  "entities": [{"type": "team", "name": "Equipe de Compliance", "aliases": ["Compliance", "time de compliance"]}],
  "facts": [{"type": "rule", "content": "Todo pedido acima de R$10.000 requer aprovação do CFO", "confidence": 0.95}],
  "processes": [{"name": "Processo de Aprovação Financeira", "description": "Fluxo de aprovação de gastos corporativos"}],
  "contradictions": [{"description": "Reunião 3 define aprovação em 2 dias; reunião 7 define 5 dias úteis", "severity": "high"}]
}
```

### Integração com o pipeline existente

Adicionar ao final de `core/pipeline.py → run_pipeline()`, após o hub estar totalmente populado:

```python
# ── Knowledge Hub ingestion (async, non-blocking) ─────────────────────────
if _should_ingest_knowledge(hub, config):
    try:
        from core.knowledge_store import KnowledgeStore
        ks = KnowledgeStore(project_id=config.project_id)
        report = ks.ingest_from_hub(
            hub=hub,
            meeting_id=config.meeting_id,
            llm_config=config.llm_config,
            embed_fn=_get_embed_fn(config),
        )
        hub.meta.kh_ingest_report = report
        if report.new_contradictions:
            st.session_state["_kh_new_contradictions"] = report.new_contradictions
    except Exception as e:
        # Non-fatal — pipeline success is not dependent on KH ingestion
        hub.meta.kh_ingest_error = str(e)
```

`_should_ingest_knowledge()` verifica: Supabase configurado + `config.project_id` não None + `config.run_kh_ingest` True (novo toggle na sidebar).

### Integração com o `AgentAssistant`

Em `agents/agent_assistant.py → _build_system_prompt_tools()`, adicionar bloco de contexto do Knowledge Hub:

```python
# Enriquecer system prompt com Knowledge Hub context
if project_id:
    try:
        from core.knowledge_store import KnowledgeStore
        ks = KnowledgeStore(project_id)
        kh_ctx = ks.search_relevant_context(
            query=last_question,
            embed_fn=self._get_embed_fn(),
        )
        if kh_ctx.has_content():
            prompt += f"\n\n## Conhecimento Acumulado do Projeto\n{kh_ctx.to_prompt_block()}"
    except Exception:
        pass  # KH indisponível não bloqueia o assistente
```

### Nova página `pages/KnowledgeHub.py`

Página de visualização e gestão do Knowledge Hub persistente. Registrar no grupo "Análise" em `app.py`.

**Conteúdo:**
- **Aba 🧠 Entidades** — tabela de entidades por tipo, ocorrências, primeira/última vez vista; busca por nome
- **Aba 📋 Fatos** — tabela de fatos por tipo (rule/decision/constraint/nomenclature); filtro por confiança; botão "Marcar como supersedido"
- **Aba 🔄 Processos** — lista de processos identificados, versão count, linha do tempo cross-meeting
- **Aba ⚠️ Contradições** — lista de contradições com severidade; botão "Marcar como resolvida" + campo de nota; badge no nav quando há contradições abertas
- **Aba 📊 Evolução** — gráfico de linha: fatos acumulados por reunião; histograma de entidades por tipo

### Arquivos a criar/modificar (Feature A)

| Arquivo | Ação |
|---|---|
| `setup/supabase_schema_knowledge_hub.sql` | CRIAR — DDL das 4 tabelas + índices + funções SQL |
| `core/knowledge_store.py` | CRIAR — KnowledgeStore, KHContext, IngestReport |
| `agents/agent_knowledge_extractor.py` | CRIAR — extração estruturada de entidades/fatos/processos |
| `skills/skill_knowledge_extractor.md` | CRIAR — system prompt para extração (lowercase) |
| `core/pipeline.py` | MODIFICAR — chamar `ks.ingest_from_hub()` ao final do run |
| `agents/agent_assistant.py` | MODIFICAR — injetar `kh_ctx.to_prompt_block()` no system prompt |
| `pages/KnowledgeHub.py` | CRIAR — página de visualização e gestão |
| `app.py` | MODIFICAR — registrar KnowledgeHub.py no grupo "Análise" |
| `core/knowledge_hub.py` | MODIFICAR — adicionar `kh_ingest_report` e `kh_ingest_error` ao `SessionMetadata`; guard em `migrate()` |
| `CLAUDE.md` | MODIFICAR — documentar PC9-A |

---

## Feature B — Agente de Análise Autônomo

### Conceito

O `AgentAssistant` atual é **reativo** — responde a perguntas pontuais com até 5 rounds de tool-use. O `AgentAnalyst` é **proativo** — dado um objetivo analítico em linguagem natural ("Identifique gargalos no processo de aprovação financeira e compare com a versão anterior"), ele:

1. **Planeja** uma sequência de passos analíticos
2. **Executa** autonomamente, chamando múltiplas ferramentas
3. **Raciocina** sobre os resultados intermediários
4. **Produz** um relatório estruturado

Isso é exatamente o padrão **ReAct** (Reasoning + Acting) do LangChain — o único cenário onde o framework agrega valor real aqui.

### Por que LangChain ReAct aqui e não no AssistantAgent?

O `AgentAssistant` tem um loop controlado (≤ 5 rounds, histórico gerenciado manualmente, múltiplos providers). Substituí-lo por LangChain seria regressão. O `AgentAnalyst` é novo e tem um perfil diferente:

- **Objetivo único de longa duração** (não conversa multi-turn)
- **Cadeia de raciocínio longa** (pode precisar de 10–20 passos)
- **Transparência do raciocínio** como feature (o usuário quer ver o pensamento)
- **Retry automático de passos falhos** como requisito

O LangChain `create_react_agent` + `AgentExecutor` resolve isso sem reescrever infraestrutura.

### Dependências novas

```
langchain>=0.3.0
langchain-openai>=0.2.0
langchain-anthropic>=0.3.0
```

> **Nota:** `langgraph` já está no projeto. LangChain é a camada acima — `langgraph` é uma
> dependência do próprio LangChain. Versões compatíveis: confirmar com
> `pip install langchain langchain-openai langchain-anthropic --dry-run` antes de fixar.

### Arquitetura do `AgentAnalyst`

```
pages/Assistente.py (novo modo "🔬 Análise Autônoma")
        │
        ▼
AgentAnalyst.run(objective, project_id, llm_config)
        │
        ├── _build_langchain_llm(llm_config)
        │     → ChatOpenAI (DeepSeek/OpenAI/Groq/Gemini) ou ChatAnthropic
        │
        ├── _build_tools(project_id)
        │     → LangChain Tool wrappers sobre AssistantToolExecutor
        │     → Tool adicional: search_knowledge_hub(query)
        │     → Tool adicional: render_table(...)  ← integração com Feature v4.16
        │
        ├── create_react_agent(llm, tools, prompt)
        │     → ReAct prompt com instruções em PT-BR
        │     → KHContext injetado como contexto inicial
        │
        └── AgentExecutor(agent, tools, verbose=True, max_iterations=20)
                │
                ▼  streaming via callbacks
            AnalysisReport
              ├── steps: list[ReActStep]   # raciocínio + ação de cada passo
              ├── tables: list[dict]       # tabelas geradas via render_table
              ├── conclusion: str          # resposta final do agente
              └── metadata: dict          # tokens, tempo, ferramentas usadas
```

### Novo módulo `agents/agent_analyst.py`

```python
# agents/agent_analyst.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentAnalyst — autonomous analysis agent using LangChain ReAct pattern.
#
# Unlike AgentAssistant (reactive, conversational), AgentAnalyst executes
# multi-step analytical objectives autonomously, with full chain-of-thought
# transparency and access to both Supabase tools and the Knowledge Hub.
#
# Public API:
#   AgentAnalyst(llm_config, project_id)
#     .run(objective: str, kh_context: KHContext | None) -> AnalysisReport
#     .run_streaming(objective, kh_context, callback) -> Iterator[ReActStep]
# ─────────────────────────────────────────────────────────────────────────────
```

#### Adaptador LangChain → ferramentas existentes

Em vez de duplicar a lógica de ferramentas, criar `adapters/langchain_tools.py` que envolve o `AssistantToolExecutor` existente em `LangChain Tool` objects:

```python
# adapters/langchain_tools.py
from langchain.tools import Tool
from core.assistant_tools import AssistantToolExecutor

def build_langchain_tools(project_id: str, is_admin: bool = False) -> list[Tool]:
    executor = AssistantToolExecutor(project_id=project_id)
    
    tools = [
        Tool(
            name="get_meeting_list",
            description="Lista todas as reuniões do projeto com número, título e data.",
            func=lambda _: executor.execute("get_meeting_list", {}),
        ),
        Tool(
            name="get_meeting_action_items",
            description="Retorna action items de uma reunião específica. Input: número da reunião (int).",
            func=lambda meeting_number: executor.execute(
                "get_meeting_action_items", {"meeting_number": int(meeting_number)}
            ),
        ),
        Tool(
            name="get_requirements",
            description="Busca requisitos do projeto. Input JSON: {keyword?, req_type?, priority?}.",
            func=lambda args_json: executor.execute("get_requirements", _parse_json_arg(args_json)),
        ),
        Tool(
            name="search_transcript",
            description="Busca semântica nas transcrições. Input: texto da query.",
            func=lambda query: executor.execute("search_transcript", {"query": query}),
        ),
        Tool(
            name="list_bpmn_processes",
            description="Lista processos BPMN documentados no projeto.",
            func=lambda _: executor.execute("list_bpmn_processes", {}),
        ),
        Tool(
            name="get_sbvr_terms",
            description="Retorna termos do vocabulário SBVR do projeto. Input: keyword opcional.",
            func=lambda kw: executor.execute("get_sbvr_terms", {"keyword": kw} if kw else {}),
        ),
        # ── Knowledge Hub tools ─────────────────────────────────────────────
        Tool(
            name="search_knowledge_hub",
            description=(
                "Busca conhecimento acumulado cross-sessão: processos recorrentes, "
                "fatos/regras consolidados, entidades organizacionais. "
                "Input: texto descrevendo o que buscar."
            ),
            func=lambda query: _search_kh(query, project_id),
        ),
        # ── render_table (integração com Feature v4.16) ─────────────────────
        Tool(
            name="render_table",
            description=(
                "Registra dados tabulares para exibição e exportação Excel. "
                "Input JSON: {title, columns, rows, chart_type, chart_x_col?, chart_y_cols?}."
            ),
            func=lambda args_json: executor.execute("render_table", _parse_json_arg(args_json)),
        ),
    ]
    
    # Admin tools — apenas se is_admin
    if is_admin:
        tools += [
            Tool(
                name="get_database_integrity",
                description="Relatório de integridade do banco de dados.",
                func=lambda _: executor.execute("get_database_integrity", {}),
            ),
        ]
    
    return tools
```

#### System prompt ReAct (`skills/skill_analyst.md`)

```markdown
---
agent: analyst
version: 1.0
---

## Identidade

Você é um analista sênior de processos e negócios. Seu papel é executar
objetivos analíticos complexos de forma autônoma, utilizando as ferramentas
disponíveis para coletar dados, raciocinar sobre eles e produzir análises
estruturadas e acionáveis.

## Instruções de Raciocínio

1. Antes de agir, escreva explicitamente seu plano de ação.
2. Após cada ferramenta, reflita sobre o resultado antes de decidir o próximo passo.
3. Quando tiver dados suficientes para uma tabela, use `render_table` — não escreva tabelas em Markdown.
4. Se uma ferramenta falhar, tente uma abordagem alternativa antes de desistir.
5. Ao concluir, produza uma análise clara com:
   - Achados principais (bullet points)
   - Dados de suporte (via render_table quando aplicável)
   - Recomendações concretas e priorizadas

## Contexto do Projeto

{kh_context_block}

## Ferramentas disponíveis

{tools}

## Formato de resposta

{format_instructions}
```

### Interface em `pages/Assistente.py`

Adicionar um novo modo de operação "🔬 Análise Autônoma" via toggle na sidebar, ao lado do existente "🔧 Modo Ferramentas":

```python
# Sidebar — novo toggle
asst_mode = st.sidebar.radio(
    "Modo de operação",
    options=["💬 Assistente", "🔬 Análise Autônoma"],
    key="asst_mode",
)
```

**No modo "🔬 Análise Autônoma":**
- Campo de texto maior com placeholder: *"Descreva o objetivo da análise. Ex: Identifique os gargalos no processo de aprovação e compare com a versão anterior."*
- Botão **"▶️ Iniciar Análise"** (não é `st.chat_input` — é uma execução única)
- Área de progresso mostrando cada step do ReAct em tempo real (streaming via callback)
- Ao concluir: `st.expander("🧠 Cadeia de raciocínio")` com todos os passos + conclusão final + tabelas geradas

#### Componente de progresso streaming

```python
def _render_analyst_progress(report_placeholder, step: ReActStep) -> None:
    """Atualiza o placeholder com o passo atual do ReAct."""
    with report_placeholder.container():
        for s in st.session_state.get("_analyst_steps", []):
            icon = "🔍" if s.type == "thought" else "🛠️" if s.type == "action" else "📊"
            with st.expander(f"{icon} {s.label}", expanded=(s == step)):
                st.markdown(s.content)
```

### `core/analyst_store.py` — Persistência de análises

Análises autônomas são caras (tokens) e valiosas. Persistir em Supabase para reuso:

```sql
-- Adicionar ao supabase_schema_knowledge_hub.sql
CREATE TABLE IF NOT EXISTS kh_analyses (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID REFERENCES projects(id) ON DELETE CASCADE,
    objective    TEXT NOT NULL,
    conclusion   TEXT,
    steps_json   JSONB,          -- list[ReActStep] serializado
    tables_json  JSONB,          -- list[table_data] para re-renderizar Excel
    tokens_used  INT,
    duration_s   FLOAT,
    created_by   TEXT,           -- username da sessão
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

Nova aba **"📜 Análises Anteriores"** na página `KnowledgeHub.py` lista análises salvas com botão "↩️ Reabrir" que restaura o resultado sem re-executar o LLM.

### Arquivos a criar/modificar (Feature B)

| Arquivo | Ação |
|---|---|
| `agents/agent_analyst.py` | CRIAR — AgentAnalyst, AnalysisReport, ReActStep |
| `adapters/langchain_tools.py` | CRIAR — wrappers LangChain sobre AssistantToolExecutor |
| `adapters/__init__.py` | CRIAR — vazio |
| `skills/skill_analyst.md` | CRIAR — system prompt ReAct (lowercase) |
| `pages/Assistente.py` | MODIFICAR — novo modo "🔬 Análise Autônoma", UI de progresso streaming |
| `pages/KnowledgeHub.py` | MODIFICAR — adicionar aba "📜 Análises Anteriores" |
| `setup/supabase_schema_knowledge_hub.sql` | MODIFICAR — adicionar tabela `kh_analyses` |
| `requirements.txt` | MODIFICAR — adicionar `langchain`, `langchain-openai`, `langchain-anthropic` pinados |
| `CLAUDE.md` | MODIFICAR — documentar PC9-B |

---

## Ordem de implementação recomendada

```
FASE 1 — Fundação de dados (sem LLM, sem UI)
  1.1  setup/supabase_schema_knowledge_hub.sql  ← DDL completo
  1.2  core/knowledge_store.py                  ← KnowledgeStore esqueleto + CRUD básico
  1.3  Testar CRUD manualmente no Supabase Dashboard

FASE 2 — Extração de conhecimento
  2.1  skills/skill_knowledge_extractor.md      ← system prompt
  2.2  agents/agent_knowledge_extractor.py      ← agente de extração
  2.3  Integrar em core/pipeline.py             ← ingest_from_hub() ao final do run
  2.4  Testar: rodar pipeline em reunião existente → verificar tabelas no Supabase

FASE 3 — Enriquecimento do AssistantAgent
  3.1  core/knowledge_store.py → search_relevant_context()
  3.2  agents/agent_assistant.py → injetar KHContext no system prompt
  3.3  Testar: perguntar ao assistente sobre entidade recorrente → verificar contexto

FASE 4 — Página KnowledgeHub
  4.1  pages/KnowledgeHub.py                    ← todas as abas exceto "Análises"
  4.2  Registrar em app.py no grupo "Análise"
  4.3  Testar UI de entidades, fatos, contradições

FASE 5 — Agente Autônomo
  5.1  requirements.txt → adicionar LangChain pinado
  5.2  adapters/langchain_tools.py              ← wrappers sobre AssistantToolExecutor
  5.3  skills/skill_analyst.md                  ← system prompt ReAct
  5.4  agents/agent_analyst.py                  ← AgentAnalyst
  5.5  Testar isolado: objetivo simples sem Streamlit
  5.6  pages/Assistente.py → modo "🔬 Análise Autônoma"
  5.7  core/analyst_store.py + persistência em Supabase
  5.8  pages/KnowledgeHub.py → aba "📜 Análises Anteriores"

FASE 6 — Documentação
  6.1  CLAUDE.md → PC9-A + PC9-B
```

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| `ingest_from_hub()` falha e bloqueia o pipeline | Encapsulado em `try/except`; falha é non-fatal; erro registrado em `hub.meta.kh_ingest_error` |
| LangChain versão incompatível com `langgraph` já instalado | Testar com `pip install --dry-run` antes de fixar; usar `langchain>=0.3.0` que é compatível com `langgraph>=0.2` |
| Agente autônomo em loop infinito (max_iterations ultrapassado) | `AgentExecutor(max_iterations=20, early_stopping_method="generate")` — ao limite, o LLM produz uma resposta parcial em vez de travar |
| Custos altos com DeepSeek em análises longas | Mostrar estimativa de custo antes de iniciar (usando `modules/cost_estimator.py`) com botão de confirmação |
| Contradições geradas com falso positivo | `confidence` threshold configurável (default 0.7) + botão "Marcar como falso positivo" na página KnowledgeHub |
| pgvector sem suporte a 1536 dims no plano gratuito | Usar `dimensions=768` com modelo de embedding menor como fallback; parametrizar em `KNOWLEDGE_HUB_EMBED_DIMS` em `config.py` |
| Streamlit Cloud cold start lento com LangChain | Import lazy dentro de `agents/agent_analyst.py` — `from langchain...` só executado quando modo Análise é ativado |
| Múltiplos usuários simultâneos escrevendo em `kh_entities` | Upsert com `ON CONFLICT (project_id, canonical_name, entity_type) DO UPDATE` — PostgreSQL resolve atomicamente |

---

## Integração com features anteriores

| Feature já implementada | Como se integra com PC9 |
|---|---|
| `render_table` (v4.16) | `AgentAnalyst` usa `render_table` via `adapters/langchain_tools.py` — tabelas geradas em análises autônomas também exportam para Excel |
| `transcript_chunks` / embeddings semânticos | `kh_processes` e `kh_facts` usam o mesmo pipeline de embedding (Gemini `gemini-embedding-001`, 1536 dims) via `modules/embeddings.py` |
| `AssistantToolExecutor` | Reutilizado integralmente via wrappers LangChain — zero duplicação de lógica de negócio |
| `modules/cost_estimator.py` | Estimativa exibida antes de iniciar análise autônoma |
| `core/project_store.py` | `KnowledgeStore` usa o mesmo `get_supabase_client()` singleton |
| `modules/auth.py → is_admin()` | Ferramentas admin do `AgentAnalyst` protegidas pelo mesmo gate |

---

## Atualização do CLAUDE.md

Ao concluir a implementação, atualizar as seguintes seções:

**Repository Structure** — adicionar:
```
│   ├── knowledge_store.py        # KnowledgeStore — persistent cross-session knowledge (entities, facts, processes, contradictions)
│   └── analyst_store.py          # AnalystStore — persist/retrieve autonomous analysis reports

├── adapters/
│   ├── __init__.py
│   └── langchain_tools.py        # LangChain Tool wrappers over AssistantToolExecutor

├── pages/
│   └── KnowledgeHub.py           # Knowledge Hub viewer — entities, facts, processes, contradictions, past analyses
```

**Dependencies** — adicionar:
```
langchain==X.X.X
langchain-openai==X.X.X
langchain-anthropic==X.X.X
openpyxl==X.X.X
```

**PC9 — Em andamento** — adicionar checklist completo ao final do histórico de versões.

---

*Guia gerado em 2026-05-13 — Process2Diagram v4.16 → v4.17 (PC9)*
