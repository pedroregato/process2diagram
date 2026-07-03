# Process2Diagram

> Converta transcrições de reuniões em diagramas de processo, documentação estruturada e inteligência de negócio — automaticamente, com uma plataforma multi-agente LLM.

**Versão atual:** v5.14 · **Deploy:** Streamlit Cloud · **Python:** 3.13

---

## O que é

**Process2Diagram** é uma plataforma Streamlit completa que recebe uma transcrição de reunião (texto colado, `.txt`, `.docx` ou `.pdf`) e produz automaticamente um conjunto integrado de artefatos de negócio:

| Artefato | Formato | Descrição |
|---|---|---|
| **BPMN 2.0** | XML + viewer interativo | Diagrama de processo com pools, lanes, gateways e eventos (OMG ISO/IEC 19510) |
| **Fluxograma Mermaid** | SVG pan/zoom | Visão alternativa do mesmo processo |
| **Ata de Reunião** | `.md` · `.docx` · `.pdf` | Participantes, decisões, action items com responsável e prazo |
| **Análise de Requisitos** | JSON · Markdown · Mind Map | Classificados por tipo IEEE 830 e prioridade, com rastreabilidade ao falante |
| **Vocabulário SBVR** | JSON | Termos de negócio e regras formais (OMG SBVR) |
| **Modelo BMM** | JSON | Visão, missão, objetivos, estratégias e políticas (OMG BMM) |
| **Relatório Executivo** | HTML interativo | Síntese integrada com sidebar nav, filtros, action items e comentários persistentes |

Os artefatos são persistidos no **Supabase** (PostgreSQL + pgvector) e ficam acessíveis nas páginas de análise, assistente RAG e rastreamento de requisitos.

---

## Navegação — 5 grupos

| Grupo | Páginas |
|---|---|
| **Inicio** | Home — tela de boas-vindas com KPIs globais, guia de uso e reuniões recentes |
| **Pipeline** | Pipeline (execucao principal) · Diagramas (viewer full-screen) · Editor BPMN |
| **Analise** | Assistente RAG · Rastreador de Requisitos · Dashboard ROI-TR |
| **Sistema** | Configuracoes · Banco de Dados · Estimador de Custo LLM · Guias |
| **Manutencao** | Batch Runner · Backfill BPMN · Backfill Atas · Backfill Embeddings |

---

## Pipeline Multi-Agente

```
Transcricao (texto / .txt / .docx / .pdf)
        |
        v
 AgentTranscriptQuality   <- LLM; grade A-E, 6 criterios ponderados
        |
 Transcript Preprocessor  <- sem LLM; remove ASR fillers, ruido, repeticoes
        |
 NLP Chunker              <- sem LLM; spaCy NER, segmentacao, deteccao de atores
        |
 AgentBPMN                <- LLM; extracao, _enforce_rules(), bpmn_auto_repair()
        |                    > LangGraph Adaptive Retry (opcional, ate 5 tentativas)
        |                    > Modo torneio 1/3/5 passes + AgentValidator (scorer puro Python)
        |
        +-- AgentMinutes --------+  execucao paralela (ThreadPoolExecutor)
        +-- AgentRequirements ---+
        |
 AgentSBVR               <- LLM (opcional); vocabulario de negocio + regras
        |
 AgentBMM                <- LLM (opcional); visao, missao, metas, estrategias
        |
 AgentSynthesizer        <- LLM (opcional); relatorio HTML interativo
        |
 KnowledgeHub            <- estado central em st.session_state; salvo no Supabase
```

Todos os agentes leem e escrevem exclusivamente em sua secao do **KnowledgeHub** (dataclass central). Nenhum agente chama outro diretamente.

---

## Providers de LLM Suportados

| Provider | Modelo padrao | Observacao |
|---|---|---|
| **DeepSeek** _(padrao)_ | `deepseek-chat` | Menor custo |
| Claude (Anthropic) | `claude-sonnet-4-20250514` | Alta qualidade de extracao |
| OpenAI | `gpt-4o-mini` | Versatil |
| Groq (Llama) | `llama-3.3-70b-versatile` | Mais rapido |
| Google Gemini | `gemini-2.0-flash` | Tier gratuito disponivel |

Cada usuario insere sua propria chave de API no sidebar — nunca armazenada em disco.

---

## Funcionalidades de Destaque

### Pipeline e BPMN
- **LangGraph Adaptive Retry** — AgentBPMN re-executado ate atingir score configuravel (threshold 0–10, ate 5 tentativas), com melhor candidato selecionado automaticamente.
- **Torneio multi-run** — 1, 3 ou 5 passes de BPMN com selecao pelo AgentValidator (scorer puro Python, sem LLM): granularidade, tipo de tarefa, gateways, integridade estrutural.
- **Auto-repair deterministico** — 4 passes de correcao estrutural sem LLM: dangling edges, isolated nodes, XOR labels, gateway bypass.
- **Execucao paralela** — Meeting Minutes e Requirements executam simultaneamente via `ThreadPoolExecutor`; fallback automatico para sequencial em excecao.
- **_enforce_rules()** — pos-processamento programatico: lanes genericas inferidas dos atores NLP, loops de correcao redirecionados para antes do gateway, service tasks sem ator para lane `None`.

### Editor BPMN
- Editor visual completo com **bpmn-js Modeler** embutido (sem CDN externo).
- Selecao de projeto / processo / versao com historico em dataframe.
- Exportacao XML via `navigator.clipboard` com fallback manual (Ctrl+A, Ctrl+C).
- Salva nova versao no Supabase (`save_bpmn_new_version()`); versao anterior marcada como nao-atual.
- Validacao estrutural com `xml.etree.ElementTree` antes de persistir.

### Assistente RAG com Tool-Use
- **Modo A (padrao):** `AgentAssistant.chat_with_tools()` — loop de ate 5 rounds de tool-use, 10 ferramentas de consulta disponíveis a todos os usuarios + ferramentas admin protegidas por RBAC (`is_admin()`).
- **Modo B (fallback):** RAG classico — busca por keyword (ILIKE) + busca semantica via `pgvector` (cosine similarity, `match_transcript_chunks()`).
- Re-edicao de perguntas anteriores via botao `Editar` com truncamento de historico.
- Embeddings: Google Gemini `gemini-embedding-001` (1536 dims) com retry automatico em 429 e delay de 1.2s para tier gratuito.

### Dashboard ROI-TR
- Classifica cada reuniao em **11 tipos** via LLM (Kick-off, Levantamento de Requisitos, Tomada de Decisao, Revisao de Processos, etc.) e persiste em `meetings.meeting_type`.
- **Matriz de pesos por tipo** — DC ponderado: decisoes valem mais numa Tomada de Decisao; requisitos valem mais num Levantamento; termos SBVR valem mais numa Definicao Conceitual.
- **Indice de Fulfillment** (0–100 %) — entrega real vs. minimo esperado para o tipo de reuniao.
- **ROI-TR** (0–10) = DC ponderado / custo humano estimado.
- **TRC** (%) — Taxa de Retrabalho Conceitual baseada em sinais linguisticos de revisao.

### Rastreador de Requisitos
- Board Supabase-backed para gestao de status de requisitos por projeto.
- Export para Excel e CSV via `modules/reqtracker_exporter.py`.

### Manutencao e Operacao
- **Batch Runner** — executa o pipeline completo sobre multiplas transcricoes em sequencia.
- **Backfill pages** — retroage BPMN, atas e embeddings para reunioes ja armazenadas sem esses artefatos.
- **Database Overview** — health score, KPIs de cobertura por campo, correcoes inline, gestao completa de embeddings com progresso por reuniao.
- **Estimador de Custo** — calculadora interativa de custo LLM por provedor/agente (sem chamadas reais).

---

## Executando Localmente

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Baixar modelo spaCy em portugues (necessario uma vez)
python -m spacy download pt_core_news_lg

# 3. Iniciar
streamlit run app.py
# -> http://localhost:8501
```

> Python 3.13 · Sem build step · Supabase e chaves LLM sao opcionais para uso local basico.

### Supabase (opcional — necessario para persistencia, RAG e analise cross-meeting)

1. Crie um projeto em [supabase.com](https://supabase.com)
2. Execute o DDL em `setup/supabase_schema_transcript_chunks.sql` (tabela `transcript_chunks` com `vector(1536)`, indice `ivfflat` coseno)
3. Adicione as credenciais em `.streamlit/secrets.toml`:

```toml
[supabase]
url = "https://<projeto>.supabase.co"
key = "<anon-key>"
```

Sem esse arquivo o app funciona normalmente em modo local — todas as funcoes Supabase retornam `[]`/`None` sem erro.

---

## Deploy no Streamlit Cloud

1. Faca push para o GitHub (branch `main`)
2. Acesse [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Selecione o repositorio e defina `Main file: app.py`
4. Adicione os secrets do Supabase em **App settings → Secrets** (se aplicavel)
5. **Deploy** — rebuild automatico a cada push para `main`

> Atencao: o filesystem do Streamlit Cloud e Linux com case-sensitivity. Nomes de skill files em `skills/` devem corresponder exatamente ao rastreado no git (`git ls-files skills/`).

---

## Estrutura do Repositorio

```
process2diagram/
|
+-- app.py                          # Entrada Streamlit — st.navigation() com 5 grupos
|
+-- pages/
|   +-- Home.py                     # Tela inicial — KPIs, guia, reunioes recentes
|   +-- Pipeline.py                 # Pipeline principal — entrada, execucao, tabs de resultado
|   +-- Diagramas.py                # Viewer full-screen — BPMN, Mermaid, Mind Map
|   +-- BpmnEditor.py               # Editor visual BPMN com historico de versoes
|   +-- Assistente.py               # Assistente RAG — tool-use + busca semantica
|   +-- ReqTracker.py               # Rastreador de requisitos por projeto
|   +-- MeetingROI.py               # Dashboard ROI-TR — qualidade e ROI de reunioes
|   +-- Settings.py                 # Configuracoes — providers, embeddings, SQL migrations
|   +-- DatabaseOverview.py         # Saude do banco, cobertura, embeddings, correcoes
|   +-- CostEstimator.py            # Calculadora de custo LLM por provedor
|   +-- BatchRunner.py              # Execucao em lote de multiplas transcricoes
|   +-- BpmnBackfill.py             # Backfill BPMN para reunioes existentes
|   +-- MinutesBackfill.py          # Backfill de atas para reunioes existentes
|   +-- TranscriptBackfill.py       # Backfill de embeddings para reunioes existentes
|
+-- core/
|   +-- knowledge_hub.py            # KnowledgeHub — dataclass central + migrate()
|   +-- pipeline.py                 # run_pipeline() — 3 paths: single / torneio / LangGraph
|   +-- lg_pipeline.py              # LGBPMNRunner — loop adaptativo LangGraph
|   +-- session_state.py            # init_session_state() — inicializacao idempotente
|   +-- rerun_handlers.py           # handle_rerun() — re-execucao individual de agentes
|   +-- assistant_tools.py          # Schemas de ferramentas + AssistantToolExecutor
|   +-- project_store.py            # CRUD Supabase — projetos, reunioes, versoes BPMN
|
+-- agents/
|   +-- base_agent.py               # BaseAgent — roteamento LLM, retry JSON, tokens
|   +-- orchestrator.py             # Sequencia + paralelo Minutes || Requirements
|   +-- agent_transcript_quality.py # Grade A-E, 6 criterios ponderados
|   +-- nlp_chunker.py              # spaCy NER, segmentacao, atores (sem LLM)
|   +-- agent_bpmn.py               # Extracao BPMN + _enforce_rules() + geradores
|   +-- agent_mermaid.py            # MermaidGenerator — conversor puro Python
|   +-- agent_minutes.py            # Ata de reuniao completa com iniciais
|   +-- agent_requirements.py       # Requisitos IEEE 830, speaker attribution
|   +-- agent_sbvr.py               # SBVR — vocabulario + regras de negocio
|   +-- agent_bmm.py                # BMM — visao, missao, metas, estrategias, politicas
|   +-- agent_synthesizer.py        # Relatorio HTML executivo interativo
|   +-- agent_validator.py          # Scorer BPMN puro Python (sem LLM)
|
+-- modules/
|   +-- bpmn_generator.py           # Gerador XML BPMN 2.0 (coordenadas absolutas)
|   +-- bpmn_auto_repair.py         # 4-pass repair deterministico
|   +-- bpmn_structural_validator.py # 6 verificacoes estruturais com severidade
|   +-- bpmn_viewer.py              # Viewer bpmn-js 17 (sem CDN externo)
|   +-- bpmn_editor.py              # editor_from_xml() — Modeler HTML embutido
|   +-- mermaid_renderer.py         # render_mermaid_block() — pan/zoom/fit, TD/LR toggle
|   +-- executive_html.py           # Gerador de relatorio HTML interativo
|   +-- minutes_exporter.py         # Export Ata -> .docx (python-docx) e .pdf (fpdf2)
|   +-- embeddings.py               # chunk_text(), embed_text(), embed_batch()
|   +-- meeting_roi_calculator.py   # ROI-TR v2 — TYPE_WEIGHTS (11 tipos), LLM classifier
|   +-- cross_meeting_analyzer.py   # Topicos recorrentes cross-meeting (semantico + keyword)
|   +-- requirements_mindmap.py     # Mind map de requisitos (Mermaid)
|   +-- mindmap_interactive.py      # Mind map SVG interativo (pan/zoom, colapsar/expandir)
|   +-- supabase_client.py          # Singleton Supabase client (fail-open sem secrets)
|   +-- auth.py                     # SHA-256 session login, is_authenticated(), is_admin()
|   +-- config.py                   # Registro de providers LLM
|   +-- cost_estimator.py           # PROVIDER_PRICING + estimate_cost() — sem LLM
|
+-- ui/
|   +-- sidebar.py                  # render_sidebar() — provider, config, re-run buttons
|   +-- input_area.py               # render_input_area() — textarea, upload, pre-processamento
|   +-- auth_gate.py                # apply_auth_gate() — login wall + st.stop()
|   +-- tabs/                       # Um modulo por aba de resultado
|
+-- skills/                         # System prompts dos agentes LLM (Markdown)
+-- tests/                          # 106 testes, 0 chamadas LLM
+-- setup/                          # DDL Supabase, helpers de setup
+-- requirements.txt                # Versoes pinadas para reproducibilidade no Cloud
+-- CLAUDE.md                       # Documentacao tecnica completa do projeto
```

---

## Autenticacao e Seguranca

- **Login gate** em todas as paginas via `ui/auth_gate.py` — SHA-256, sem dependencia de `secrets.toml`.
- **RBAC:** roles `user`, `admin` e `master`. Ferramentas destrutivas/admin no Assistente exigem `is_admin()`.
- **Chaves de API** armazenadas exclusivamente em `st.session_state` (RAM por sessao) — nunca gravadas em disco, logs ou variaveis de ambiente. Destruidas ao fechar a aba.
- Para implantacoes corporativas, utilize proxy backend com `st.secrets`.

---

## Suite de Testes

```bash
pytest tests/          # 106 testes, ~0.5s, 0 chamadas LLM
```

Cobertura:
- `test_bpmn_auto_repair.py` — 36 testes: dangling edges, isolated nodes, XOR labels, gateway bypass
- `test_bpmn_structural_validator.py` — 22 testes: 6 verificacoes estruturais + collaboration
- `test_agent_validator.py` — 22 testes: granularidade, task type, gateways, ponderado
- `test_mermaid_generator.py` — 26 testes: sanitize, format_node, format_edge, single/multi-pool

---

## Stack Tecnica

| Camada | Tecnologia |
|---|---|
| Interface | Streamlit 1.45.1 |
| LLM — Anthropic | anthropic 0.49.0 |
| LLM — OpenAI / compativel | openai 1.65.0 |
| Orquestramento adaptativo | langgraph >= 1.0 |
| NLP (sem LLM) | spaCy pt_core_news_lg |
| BPMN viewer / editor | bpmn-js 17 (inline, sem CDN) |
| Diagramas Mermaid | mermaid.ink (SVG server-side) |
| Banco de dados | Supabase (PostgreSQL + pgvector) |
| Busca semantica | pgvector ivfflat coseno, vector(1536) |
| Embeddings | Google Gemini `gemini-embedding-001` |
| Export Word | python-docx 1.1.2 |
| Export PDF | fpdf2 2.8.2 (puro Python, sem GTK) |

---

## Compatibilidade dos Artefatos BPMN

O XML gerado e compativel com ferramentas que suportam BPMN 2.0 (OMG ISO/IEC 19510):

- [Camunda Platform](https://camunda.com)
- [Bizagi Modeler](https://www.bizagi.com)
- [draw.io / diagrams.net](https://app.diagrams.net)
- [bpmn.io](https://bpmn.io)
