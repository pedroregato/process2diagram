# Requisitos — Funcionalidade: Cenários de Custo-Benefício por Combinação de LLMs
**Projeto:** Process2Diagram  
**Versão alvo:** v4.21  
**Página nova:** `pages/CostBenefitScenarios.py`  
**Grupo de navegação:** Análise  
**Data:** 2025-05-29  

---

## 1. Contexto e Motivação

O Process2Diagram executa um pipeline multi-agente onde cada agente faz chamadas LLM independentes. Atualmente todos os agentes usam o mesmo provedor/modelo selecionado globalmente no sidebar. Isso impede que o usuário saiba, *antes de executar*, qual combinação de provedores minimiza custo, maximiza qualidade estimada, ou encontra o melhor equilíbrio.

A funcionalidade **Cenários de Custo-Benefício** resolve isso: o usuário configura um conjunto de atribuições agente→provedor/modelo, o sistema projeta o custo esperado por agente e por cenário completo, compara visualmente os cenários e permite salvar a combinação preferida como preset de configuração.

---

## 2. Escopo da Funcionalidade

### 2.1 O que está incluído

- Nova página Streamlit `pages/CostBenefitScenarios.py` registrada no grupo **Análise** em `app.py`
- Módulo de dados `core/cost_model.py` com tabela de preços por provedor/modelo e lógica de projeção
- Widget de construção de cenários: linha por agente LLM, seletor de provedor + modelo por linha
- Projeção de tokens por agente baseada em média histórica (do `hub.meta` / Supabase) ou em estimativa heurística por tamanho de transcrição
- Painel comparativo de até **5 cenários simultâneos** em Plotly: custo total, custo por agente, índice qualidade estimada
- Exportação do cenário selecionado como preset aplicável ao pipeline (escrito em `st.session_state`)
- Suporte a todos os provedores já registrados em `modules/config.py`: DeepSeek, Claude (Anthropic), OpenAI, Groq (Llama), Google Gemini — e os adicionados posteriormente via `AVAILABLE_PROVIDERS`

### 2.2 O que está excluído

- Execução real do pipeline a partir desta página (apenas projeção)
- Coleta de métricas de qualidade em tempo real (usa índice estimado estático, não benchmark ao vivo)
- Integração com billing APIs dos provedores

---

## 3. Modelo de Dados — `core/cost_model.py`

### 3.1 Estrutura `ModelPricing`

```python
@dataclass
class ModelPricing:
    provider: str          # chave de AVAILABLE_PROVIDERS
    model_id: str          # ex: "deepseek-chat", "gpt-4o-mini"
    label: str             # nome amigável para exibição
    input_price_per_1m: float   # USD por 1M tokens de input
    output_price_per_1m: float  # USD por 1M tokens de output
    quality_index: float   # 0.0–10.0 — índice qualitativo estimado (editável)
    context_window_k: int  # tamanho de contexto em K tokens
    notes: str = ""        # ex: "free tier available", "deprecated"
```

### 3.2 Catálogo inicial `PRICING_CATALOG: list[ModelPricing]`

| Provider | Model ID | Input $/1M | Output $/1M | Quality Index | Context K |
|---|---|---|---|---|---|
| DeepSeek | deepseek-chat | 0.27 | 1.10 | 7.5 | 64 |
| DeepSeek | deepseek-reasoner | 0.55 | 2.19 | 8.5 | 64 |
| DeepSeek | deepseek-v4-flash | 0.10 | 0.28 | 7.0 | 128 |
| DeepSeek | deepseek-v4-pro | 0.27 | 1.10 | 8.0 | 128 |
| Claude (Anthropic) | claude-haiku-4-5 | 0.80 | 4.00 | 7.8 | 200 |
| Claude (Anthropic) | claude-sonnet-4-6 | 3.00 | 15.00 | 9.2 | 200 |
| Claude (Anthropic) | claude-opus-4-6 | 15.00 | 75.00 | 9.8 | 200 |
| OpenAI | gpt-4o-mini | 0.15 | 0.60 | 7.5 | 128 |
| OpenAI | gpt-4o | 2.50 | 10.00 | 9.0 | 128 |
| OpenAI | o3-mini | 1.10 | 4.40 | 8.8 | 200 |
| Groq (Llama) | llama-3.3-70b-versatile | 0.06 | 0.06 | 7.0 | 128 |
| Groq (Llama) | llama-3.1-8b-instant | 0.05 | 0.08 | 6.0 | 128 |
| Google Gemini | gemini-2.0-flash | 0.10 | 0.40 | 7.8 | 1000 |
| Google Gemini | gemini-2.5-pro | 1.25 | 10.00 | 9.0 | 1000 |
| Grok (xAI) | grok-3 | 3.00 | 15.00 | 8.5 | 131 |
| Grok (xAI) | grok-3-mini | 0.30 | 0.50 | 7.5 | 131 |

> **Nota de implementação:** os preços acima são pontos de partida. O catálogo deve ser editável pelo usuário via UI (campo numérico inline), com valores persistidos em `st.session_state["cost_catalog_overrides"]`. Não gravar em Supabase nesta versão.

### 3.3 Estrutura `AgentTokenProfile`

```python
@dataclass
class AgentTokenProfile:
    agent_name: str        # ex: "AgentBPMN", "AgentMinutes"
    avg_input_tokens: int  # média histórica ou estimativa heurística
    avg_output_tokens: int
    source: str            # "historical" | "heuristic"
```

Perfis heurísticos padrão (quando não há histórico Supabase):

| Agente | Input tokens (est.) | Output tokens (est.) |
|---|---|---|
| AgentTranscriptQuality | 800 | 300 |
| AgentBPMN | 3500 | 1200 |
| AgentMinutes | 3500 | 800 |
| AgentRequirements | 3500 | 1500 |
| AgentSBVR | 2000 | 600 |
| AgentBMM | 2000 | 500 |
| AgentSynthesizer | 5000 | 2000 |

> Os valores de `avg_input_tokens` devem escalar linearmente com `transcript_word_count` quando o usuário informar o tamanho da transcrição. Fórmula: `estimated_input = base_input + (words / 750) * context_multiplier`.

### 3.4 Estrutura `ScenarioConfig`

```python
@dataclass
class ScenarioConfig:
    name: str                              # ex: "Custo Mínimo", "Qualidade Máxima"
    assignments: dict[str, str]            # agent_name → model_id
    n_bpmn_runs: int = 1                   # multiplicador para AgentBPMN
    active_agents: list[str] = field(default_factory=list)  # agentes habilitados
```

### 3.5 Função `project_cost(scenario, token_profiles, catalog) → ScenarioResult`

```python
@dataclass
class ScenarioResult:
    scenario_name: str
    total_cost_usd: float
    per_agent: dict[str, float]     # agent_name → custo USD
    avg_quality_index: float        # média ponderada por output tokens
    cost_per_quality: float         # total_cost / avg_quality_index
    warnings: list[str]             # ex: "AgentBPMN usa modelo sem json_mode"
```

---

## 4. Interface — `pages/CostBenefitScenarios.py`

### 4.1 Layout geral

```
┌─────────────────────────────────────────────────────────────┐
│  💰 Cenários de Custo-Benefício                              │
│  Projete o custo estimado de diferentes combinações de LLMs  │
├───────────────────┬─────────────────────────────────────────┤
│  PAINEL ESQUERDO  │  PAINEL DIREITO                          │
│  (40%)            │  (60%)                                   │
│                   │                                          │
│  ▸ Parâmetros     │  ▸ Gráfico comparativo (Plotly)          │
│    de transcrição │  ▸ Tabela de resultados                  │
│                   │  ▸ Botão: Aplicar Cenário                │
│  ▸ Editor de      │                                          │
│    cenários       │                                          │
│    (tabs 1..5)    │                                          │
│                   │                                          │
│  ▸ Catálogo de    │                                          │
│    preços (expand)│                                          │
└───────────────────┴─────────────────────────────────────────┘
```

### 4.2 Seção "Parâmetros de transcrição"

- `st.number_input("Palavras estimadas na transcrição", min=100, max=50000, value=1500, step=100)`
- `st.selectbox("Agentes a executar", options=lista_multiselect)` — checkboxes por agente
- `st.slider("Número de runs BPMN (torneio)", 1, 5, 1)`
- `st.toggle("Usar histórico Supabase para estimativa de tokens", default=False)` — quando True, busca média de `hub.meta.total_tokens_used` por agente nos últimos 30 runs

### 4.3 Editor de cenários

- Tabs nomeadas: **Cenário 1** … **Cenário 5** (+ botão "Adicionar Cenário")
- Cada tab contém:
  - Campo texto: nome do cenário
  - Tabela editável: uma linha por agente ativo
    - Coluna 1: nome do agente (read-only)
    - Coluna 2: `st.selectbox` — provedor
    - Coluna 3: `st.selectbox` — modelo (filtrado pelo provedor selecionado)
    - Coluna 4 (calculado, read-only): custo estimado USD para este agente
  - Rodapé da tab: **custo total estimado** em destaque + **quality index médio**
- Botão **"Preset: Custo Mínimo"** — preenche automaticamente todos os agentes com o modelo de menor custo disponível
- Botão **"Preset: Qualidade Máxima"** — preenche com o modelo de maior quality_index por provedor disponível
- Botão **"Preset: Balanceado"** — heurística: Groq para Quality/NLP, DeepSeek para BPMN/Minutes/Requirements, Claude Haiku para Synthesizer

### 4.4 Catálogo de preços (expandable)

- `st.expander("📋 Catálogo de preços — editar valores")`
- `st.data_editor` com colunas: Provider, Model, Input $/1M, Output $/1M, Quality Index
- Alterações persistidas em `st.session_state["cost_catalog_overrides"]`
- Botão "Restaurar padrões"

### 4.5 Painel de comparação (direita)

#### Gráfico 1 — Custo total por cenário (bar chart Plotly)
- Barras empilhadas: cada segmento = um agente
- Eixo Y: USD
- Tooltip: agente, provedor, modelo, custo parcial

#### Gráfico 2 — Custo × Qualidade (scatter Plotly)
- Eixo X: custo total USD
- Eixo Y: quality index médio
- Cada ponto = um cenário
- Tamanho do ponto proporcional ao número de agentes ativos
- Quadrante "ideal": baixo custo + alta qualidade destacado

#### Tabela resumo
| Cenário | Custo Total | Quality Index | Custo/Qualidade | Warnings |
|---|---|---|---|---|
| … | … | … | … | … |

#### Botão "▶ Aplicar Cenário X ao Pipeline"
- Escreve em `st.session_state`:
  - `["selected_provider"]` = provedor majoritário do cenário
  - `["scenario_assignments"]` = dict agent→model_id (novo campo)
  - `["n_bpmn_runs"]` = valor configurado
- Exibe `st.success("Cenário X aplicado. Vá para Pipeline para executar.")`
- Inclui `st.page_link("pages/Pipeline.py", label="→ Ir para Pipeline")`

---

## 5. Integração com o Pipeline

### 5.1 Leitura de `scenario_assignments` no `BaseAgent`

Em `agents/base_agent.py`, método `_call_llm()`:

```python
# Após obter provider_cfg existente:
assignments = st.session_state.get("scenario_assignments", {})
if self.name in assignments:
    model_override = assignments[self.name]
    # substituir provider_cfg["default_model"] pelo model_override
    # manter client_type do provider_cfg original (não muda)
```

> **Regra:** o `scenario_assignments` sobrescreve apenas o `model_id`, nunca o `client_type` nem o `api_key`. O provedor (e portanto a chave de API) é determinado pela seleção global do sidebar como hoje.

> **Implicação:** na v4.21, o cenário define qual *modelo* cada agente usa dentro do mesmo provedor já configurado. Atribuição de *provedores distintos por agente* (multi-provider routing) fica para versão futura (v4.x+).

### 5.2 Exibição no Pipeline

Em `pages/Pipeline.py`, abaixo do header do pipeline, adicionar badge informativo quando `scenario_assignments` estiver ativo:

```
ℹ️ Cenário ativo: "Balanceado" — AgentBPMN: deepseek-chat | AgentMinutes: llama-3.3-70b | …
```

---

## 6. Requisitos não-funcionais

| # | Requisito | Critério de aceite |
|---|---|---|
| NF-1 | Performance | Todos os cálculos de projeção devem ser síncronos, sem chamadas LLM ou rede. Resposta < 200 ms. |
| NF-2 | Consistência com config.py | `PRICING_CATALOG` deve ser derivado de `AVAILABLE_PROVIDERS` — não duplicar lista de provedores. Adicionar novo provider em `config.py` deve aparecer automaticamente no catálogo. |
| NF-3 | Zero acoplamento com Supabase | A estimativa heurística deve funcionar sem nenhuma conexão de banco. Supabase é opcional (toggle). |
| NF-4 | Preservação de estado | Cenários construídos devem sobreviver a reruns do Streamlit. Usar `st.session_state["cost_scenarios"]` (lista de `ScenarioConfig`). |
| NF-5 | Compatibilidade | Não quebrar o pipeline existente quando `scenario_assignments` não estiver definido em session_state. `BaseAgent` deve fazer `get()` com default seguro. |
| NF-6 | CSP Streamlit Cloud | Todos os gráficos via Plotly (já aprovado). Não usar CDN externo com eval(). |

---

## 7. Arquivos a criar/modificar

### Criar
- `pages/CostBenefitScenarios.py` — página principal
- `core/cost_model.py` — dataclasses + catálogo + função `project_cost()`

### Modificar
- `app.py` — registrar `CostBenefitScenarios.py` no grupo **Análise** do `st.navigation()`
- `agents/base_agent.py` — leitura de `scenario_assignments` em `_call_llm()`
- `pages/Pipeline.py` — badge de cenário ativo
- `CLAUDE.md` — atualizar versão para v4.21, documentar `core/cost_model.py` e `scenario_assignments`

---

## 8. Ordem de implementação sugerida

1. **`core/cost_model.py`** — dataclasses + catálogo + `project_cost()` + testes inline (sem Streamlit)
2. **`agents/base_agent.py`** — patch em `_call_llm()` para ler `scenario_assignments` (sem quebrar nada)
3. **`pages/CostBenefitScenarios.py`** — UI completa em ordem: parâmetros → editor de cenários → gráficos → botão aplicar
4. **`app.py`** — registrar página
5. **`pages/Pipeline.py`** — badge de cenário ativo
6. **`CLAUDE.md`** — atualizar documentação

---

## 9. Critérios de aceite (smoke test manual)

- [ ] Abrir a página sem erro com `streamlit run app.py`
- [ ] Criar dois cenários distintos, calcular e ver gráfico de barras empilhadas com diferença de custo
- [ ] Preset "Custo Mínimo" preenche todos os agentes com Groq llama-3.1-8b-instant
- [ ] Preset "Qualidade Máxima" preenche AgentBPMN e AgentSynthesizer com Claude Opus ou gpt-4o
- [ ] Editar preço de um modelo no catálogo → custo recalculado imediatamente
- [ ] Clicar "Aplicar Cenário" → `st.session_state["scenario_assignments"]` populado corretamente
- [ ] Abrir Pipeline → badge de cenário ativo visível
- [ ] Executar pipeline com cenário ativo → `BaseAgent` usa o model_id do cenário para os agentes configurados
- [ ] Remover `scenario_assignments` do session_state manualmente → pipeline continua funcionando normalmente

---

## 10. Notas adicionais para o Claude Code

- Respeitar a convenção de path do `_load_skill()`: usar `Path(__file__).parent.parent` para resolver caminhos relativos
- `st.data_editor` é o widget correto para a tabela editável do catálogo — não usar `st.table` (read-only)
- Para os `st.selectbox` de modelo filtrado por provedor, derivar as opções de `PRICING_CATALOG` filtrado pelo provider selecionado na mesma linha
- O campo `quality_index` no catálogo é intencionalmente subjetivo e editável — não tentar calculá-lo automaticamente
- Plotly já está em `requirements.txt` (usado em outras páginas)
- Não instalar dependências novas
