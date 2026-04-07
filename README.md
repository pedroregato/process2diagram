# Process2Diagram

> Converta transcrições de reuniões em diagramas de processo, atas, requisitos e relatórios executivos — automaticamente, com agentes LLM.

---

## O que é

**Process2Diagram** é uma aplicação Streamlit multi-agente que recebe uma transcrição de reunião (texto colado, `.txt`, `.docx` ou `.pdf`) e gera automaticamente:

| Artefato | Formato | Descrição |
|---|---|---|
| **BPMN 2.0** | XML + viewer interativo | Diagrama de processo com pools, lanes, gateways e eventos |
| **Fluxograma Mermaid** | SVG (pan/zoom) | Visão alternativa do mesmo processo |
| **Ata de Reunião** | `.md` · `.docx` · `.pdf` | Participantes, decisões, action items com responsável e prazo |
| **Requisitos** | JSON · Markdown · Mind Map | Classificados por tipo (IEEE 830) e prioridade, com rastreabilidade ao falante |
| **Vocabulário SBVR** | JSON | Termos de negócio e regras formais (OMG SBVR) |
| **Modelo BMM** | JSON | Visão, missão, objetivos, estratégias e políticas (OMG BMM) |
| **Relatório Executivo** | HTML interativo | Síntese integrada com sidebar, filtros, action items e comentários persistentes |

---

## Pipeline Multi-Agente

```
📄 Transcrição
      │
      ▼
🔬 Quality Inspector   ← Grade A–E, critérios ponderados
      │
🧹 Preprocessor        ← Remove ASR, fillers e ruído (sem LLM)
      │
🔤 NLP Chunker         ← spaCy NER, segmentação, detecção de atores (sem LLM)
      │
📐 BPMN Architect      ← Extração LLM → auto-repair → BPMN XML + Mermaid
      │                    ⟳ LangGraph Adaptive Retry (opcional)
      │                    🏆 Modo torneio multi-run (1/3/5 passes)
      │
      ├─── 📋 Meeting Minutes  ─┐  execução paralela
      └─── 📝 Requirements     ─┘  (ThreadPoolExecutor)
      │
📖 SBVR Agent          ← Vocabulário de negócio + regras (opcional)
      │
🎯 BMM Agent           ← Visão, metas, estratégias, políticas (opcional)
      │
📄 Executive Synthesizer ← Relatório HTML interativo (opcional)
```

Todos os agentes compartilham um **KnowledgeHub** — dataclass central armazenada em `st.session_state` — sem acoplamento direto entre agentes.

---

## Providers de LLM Suportados

| Provider | Modelo padrão | Observação |
|---|---|---|
| **DeepSeek** _(padrão)_ | `deepseek-chat` | Menor custo |
| Claude (Anthropic) | `claude-sonnet-4-20250514` | Alta qualidade |
| OpenAI | `gpt-4o-mini` | Versátil |
| Groq (Llama) | `llama-3.3-70b-versatile` | Mais rápido |
| Google Gemini | `gemini-2.0-flash` | Tier gratuito disponível |

Cada usuário insere sua própria chave de API no sidebar — nunca armazenada em disco.

---

## Funcionalidades de Destaque

- **LangGraph Adaptive Retry** — o agente BPMN é re-executado automaticamente até atingir um score de qualidade configurável (threshold 0–10, até 5 tentativas).
- **Torneio multi-run** — executa N passes de BPMN e seleciona o melhor candidato por pontuação ponderada (granularidade, tipo de tarefa, gateways, integridade estrutural).
- **Auto-repair determinístico** — 4 passes de correção estrutural do BPMN sem LLM: dangling edges, isolated nodes, XOR labels, gateway bypass.
- **Execução paralela** — Meeting Minutes e Requirements rodam simultaneamente via `ThreadPoolExecutor`.
- **Diagrama de arquitetura interativo** — exibido como splash screen ao abrir o app (pan/zoom/fit).
- **Relatório executivo auto-contido** — HTML standalone com sidebar, colapsável, filtros de requisitos, status de action items e comentários em localStorage.

---

## Executando Localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Baixar modelo spaCy em português (necessário uma vez)
python -m spacy download pt_core_news_lg

# 3. Iniciar
streamlit run app.py
# → http://localhost:8501
```

> **Python 3.13** · Sem build step · Sem banco de dados

---

## Deploy no Streamlit Cloud

1. Faça push para o GitHub (`main` branch)
2. Acesse [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Selecione o repositório e defina `Main file: app.py`
4. **Deploy** — nenhum secret é necessário (cada usuário insere sua chave no sidebar)

O deploy é automático a cada push para `main`.

---

## Estrutura do Repositório

```
process2diagram/
├── app.py                     # Entrada Streamlit — orquestrador slim
├── core/
│   ├── knowledge_hub.py       # KnowledgeHub — estado central compartilhado
│   ├── pipeline.py            # run_pipeline() — 3 paths: single / torneio / LangGraph
│   ├── lg_pipeline.py         # LGBPMNRunner — loop adaptativo com LangGraph
│   ├── session_state.py       # init_session_state() — inicialização idempotente
│   └── rerun_handlers.py      # handle_rerun() — re-execução individual de agentes
├── agents/
│   ├── base_agent.py          # BaseAgent — roteamento LLM, retry JSON, tokens
│   ├── orchestrator.py        # Sequência + execução paralela Minutes‖Requirements
│   ├── agent_bpmn.py          # BPMN Architect + _enforce_rules() + auto-repair
│   ├── agent_minutes.py       # Meeting Minutes
│   ├── agent_requirements.py  # Requirements (IEEE 830)
│   ├── agent_sbvr.py          # SBVR — vocabulário e regras de negócio
│   ├── agent_bmm.py           # BMM — motivação do negócio
│   ├── agent_synthesizer.py   # Executive Synthesizer → HTML
│   ├── agent_transcript_quality.py
│   ├── agent_validator.py     # Scorer puro Python (sem LLM)
│   ├── agent_mermaid.py       # MermaidGenerator — puro Python (sem LLM)
│   └── nlp_chunker.py         # spaCy NER (sem LLM)
├── modules/
│   ├── bpmn_generator.py      # Gerador XML BPMN 2.0 (coordenadas absolutas)
│   ├── bpmn_auto_repair.py    # 4-pass repair engine determinístico
│   ├── bpmn_structural_validator.py  # 6 verificações estruturais
│   ├── executive_html.py      # Gerador de relatório HTML interativo
│   ├── mermaid_renderer.py    # render_mermaid_block() — pan/zoom/fit
│   └── minutes_exporter.py    # Export Ata → .docx e .pdf
├── ui/
│   ├── sidebar.py             # Sidebar completa
│   ├── input_area.py          # Área de entrada + pré-processamento
│   ├── architecture_diagram.py # Splash diagram (flowchart TD, SVG cacheado)
│   └── tabs/                  # Uma tab por artefato
├── skills/                    # System prompts dos agentes LLM
├── tests/                     # 106 testes, 0 chamadas LLM
└── requirements.txt
```

---

## Segurança das Chaves de API

As chaves são armazenadas **exclusivamente** em `st.session_state` — memória RAM isolada por sessão de navegador. Nunca gravadas em disco, logs ou variáveis de ambiente. Destruídas ao fechar a aba.

Para implantações corporativas, utilize o padrão proxy backend com `st.secrets`.

---

## Suíte de Testes

```bash
pytest tests/          # 106 testes, ~0.5s, 0 chamadas LLM
```

Cobertura: auto-repair BPMN, validador estrutural, AgentValidator (4 dimensões), MermaidGenerator (single + multi-pool).
