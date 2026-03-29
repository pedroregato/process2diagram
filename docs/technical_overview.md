# Resumo Técnico Executivo — Process2Diagram

**Data:** 2026-03-29
**Versão:** v3.6
**Repositório:** `github.com/pedroregato/process2diagram`
**Deploy:** Streamlit Cloud (auto-deploy em push para `main`)

---

## 1. Visão Geral

**Process2Diagram** converte transcrições de reuniões em diagramas de processo profissionais e documentação estruturada, usando um pipeline sequencial de agentes LLM especializados com um Hub de Conhecimento centralizado.

### Entradas

| Tipo | Descrição |
|------|-----------|
| Texto livre | Cole diretamente na interface |
| Arquivo `.txt` | Upload via file uploader |
| Transcrição Teams | Formato nativo com speaker labels e timestamps |

### Saídas

| Formato | Padrão | Ferramentas compatíveis |
|---------|--------|------------------------|
| BPMN 2.0 XML | OMG ISO/IEC 19510 | Camunda, Bizagi, draw.io, bpmn.io |
| Mermaid flowchart | — | mermaid.live, GitHub, Notion |
| Ata de Reunião | Markdown estruturado | Qualquer editor Markdown |
| Análise de Requisitos | JSON + Markdown (IEEE 830) | Export direto |
| Relatório de Qualidade ASR | JSON interno | Visualizado na interface |

### Provedores LLM

| Provedor | Modelo padrão | client_type |
|----------|--------------|-------------|
| **DeepSeek** (padrão) | `deepseek-chat` | `openai_compatible` |
| Claude (Anthropic) | `claude-sonnet-4-20250514` | `anthropic` |
| OpenAI | `gpt-4o-mini` | `openai_compatible` |
| Groq (Llama) | `llama-3.3-70b-versatile` | `openai_compatible` |
| Google Gemini | `gemini-2.0-flash` | `openai_compatible` |

---

## 2. Arquitetura do Pipeline (PC1 — v3.6)

```
Transcrição bruta (usuário)
         │
         ▼
┌─────────────────────────────┐
│  Step 0                     │
│  AgentTranscriptQuality     │  LLM — avalia qualidade do ASR
│  • artifact_ratio census    │  Lê: transcript_raw
│  • 6 critérios ponderados   │  Escreve: hub.transcript_quality
│  • detecção de inconsistên- │  (CriterionScore[], grade A-E,
│    cias por LLM (ruído de   │   InconsistencyItem[])
│    fundo, artefatos fonét.) │
└────────────┬────────────────┘
             │ Não-fatal: pipeline continua mesmo em falha
             ▼
┌─────────────────────────────┐
│  Step 0.5                   │
│  TranscriptPreprocessor     │  Sem LLM — rule-based
│  • parse formato Teams      │  Lê: transcript_raw
│  • remoção de fillers PT/EN │  Escreve: hub.transcript_clean
│  • colapso de repetições    │          hub.preprocessing
│  • marcação [?] de artefatos│
│  • fix de metadados inválid.│
└────────────┬────────────────┘
             │ Pulo automático se transcript_clean já curado pelo usuário
             ▼
┌─────────────────────────────┐
│  Step 1                     │
│  NLPChunker                 │  Sem LLM — spaCy
│  • normalização whitespace  │  Lê: transcript_clean
│  • NER (PER, ORG)           │  Escreve: hub.nlp
│  • segmentação por tipo     │  (segments, actors, entities)
│  • detecção de idioma       │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│  Step 2                     │
│  AgentBPMN                  │  LLM + SKILL_BPMN.md
│  • extração steps/edges/    │  Lê: transcript_clean, hub.nlp
│    lanes em JSON            │  Escreve: hub.bpmn
│  • _enforce_rules() post-   │  (BPMNStep[], BPMNEdge[],
│    processamento             │   bpmn_xml, mermaid)
│  • geradores BPMN XML e     │
│    Mermaid                  │
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│  Step 3                     │
│  AgentMinutes               │  LLM + SKILL_MINUTES.md
│  • transcrição completa     │  Lê: transcript_clean, hub.nlp
│  • convenção de iniciais    │  Escreve: hub.minutes
│    (MF, PG…)                │  (participants, decisions,
│  • attribution raised_by    │   action_items com raised_by)
└────────────┬────────────────┘
             ▼
┌─────────────────────────────┐
│  Step 4                     │
│  AgentRequirements          │  LLM + SKILL_REQUIREMENTS.md
│  • IEEE 830 adaptado        │  Lê: transcript_clean, hub.nlp
│  • 5 tipos: ui_field,       │  Escreve: hub.requirements
│    validation, business_    │  (RequirementItem[] com speaker
│    rule, functional,        │   attribution + source_quote)
│    non_functional           │
└────────────┬────────────────┘
             ▼
      KnowledgeHub completo
      (hub.version++)
```

### Fluxo de curadoria (opcional, antes do pipeline)

```
Cole transcrição
      │
      ▼
[🧹 Pré-processar]  ←  instantâneo, sem LLM
      │
      ▼
Painel de curadoria:
  • Stats: fillers removidos, artefatos [?], repetições
  • Coluna esquerda: original (somente leitura + cópia)
  • Coluna direita: pré-processada (EDITÁVEL + cópia)
      │
  Usuário revisa e edita
      │
      ▼
[⚡ Iniciar Agentes Selecionados]
      │
      ▼
hub.transcript_clean = texto curado
Orchestrator pula Step 0.5 (já curado)
```

---

## 3. KnowledgeHub — Estado Central

```python
@dataclass
class KnowledgeHub:
    version: int                        # incrementado em cada .bump()
    transcript_raw: str                 # transcrição original intocada
    transcript_clean: str               # texto pré-processado / curado
    transcript_quality: TranscriptQualityModel   # Step 0
    preprocessing: PreprocessingModel            # Step 0.5
    nlp: NLPEnvelope                             # Step 1
    bpmn: BPMNModel                              # Step 2
    minutes: MinutesModel                        # Step 3
    requirements: RequirementsModel              # Step 4
    validation: ValidationReport                 # reservado PC2
    meta: SessionMetadata                        # tokens, timing, provider
```

### Modelos de dados principais

**TranscriptQualityModel**
```python
criteria: list[CriterionScore]   # 6 critérios com score 0-100 e justificativa
overall_score: float             # média ponderada
grade: str                       # A / B / C / D / E
overall_summary: str
recommendation: str
inconsistencies: list[InconsistencyItem]  # trechos suspeitos detectados pela IA
```

**Critérios de avaliação ASR (pesos)**

| Critério | Peso | O que mede |
|----------|------|-----------|
| Inteligibilidade Léxica | 20% | WER — palavras reconhecíveis |
| Atribuição de Falantes | 20% | Diarization — quem disse o quê |
| Coerência Semântica | 20% | Lógica contextual |
| Completude do Conteúdo | 15% | Ausência de truncamentos |
| Vocabulário de Domínio | 15% | Termos técnicos/negócio corretos |
| Qualidade da Pontuação | 10% | Demarcação de sentenças |

**Escala de nota:** A (90–100) · B (75–89) · C (60–74) · D (45–59) · E (0–44)

**PreprocessingModel**
```python
fillers_removed: int
artifact_turns: int        # turnos marcados com [?]
repetitions_collapsed: int
metadata_issues: list[str]
```

**BPMNModel**
```python
steps: list[BPMNStep]   # id, title, actor, task_type, lane
edges: list[BPMNEdge]   # source, target, label, condition
lanes: list[str]
bpmn_xml: str           # OMG BPMN 2.0 XML com coordenadas absolutas
mermaid: str            # fluxograma Mermaid (TD e LR)
```

**RequirementsModel** — IEEE 830 adaptado
```python
requirements: list[RequirementItem]
# RequirementItem: id, title, type (ui_field|validation|business_rule|
#                  functional|non_functional), priority, actor,
#                  source_quote, speaker (iniciais)
```

### Evolução de schema (`migrate()`)

`KnowledgeHub.migrate(hub)` é o ponto único de compatibilidade retroativa. Toda vez que um campo é adicionado a qualquer dataclass, uma guarda `if not hasattr(obj, 'field'):` é acrescentada aqui. Versões de schema:

| Versão | Alteração |
|--------|-----------|
| v3.2 | `RequirementsModel` adicionado |
| v3.3 | `ActionItem.raised_by`, `RequirementItem.speaker` |
| v3.4 | `TranscriptQualityModel` adicionado |
| v3.5 | `PreprocessingModel` adicionado |
| v3.6 | `InconsistencyItem[]` em `TranscriptQualityModel` |

---

## 4. Estrutura de Diretórios

```
process2diagram/
├── app.py                        # UI Streamlit — entrada, curadoria, tabs de resultado
│
├── core/
│   ├── knowledge_hub.py          # KnowledgeHub e todos os dataclasses
│   └── schema.py                 # Esquemas legados v2 (mantidos para compatibilidade)
│
├── agents/
│   ├── base_agent.py             # BaseAgent: LLM routing, JSON retry, token tracking
│   ├── orchestrator.py           # Sequencia os 5 steps; aceita progress_callback
│   ├── agent_transcript_quality.py  # Step 0 — avaliação ASR
│   ├── nlp_chunker.py            # Step 1 — spaCy, sem LLM
│   ├── agent_bpmn.py             # Step 2 — extração BPMN + _enforce_rules()
│   ├── agent_minutes.py          # Step 3 — ata de reunião
│   └── agent_requirements.py    # Step 4 — análise de requisitos
│
├── modules/
│   ├── config.py                 # Registro de provedores LLM
│   ├── session_security.py       # Chaves API apenas em st.session_state
│   ├── transcript_preprocessor.py  # Preprocessador rule-based (Teams format)
│   ├── bpmn_generator.py         # BPMN 2.0 XML — layout absoluto, link events
│   ├── bpmn_viewer.py            # Viewer bpmn-js 17 injetado inline
│   ├── bpmn_diagnostics.py       # Painel de validação de cruzamentos
│   ├── diagram_mermaid.py        # Gerador Mermaid
│   └── ingest.py                 # Loader de .txt
│
├── skills/
│   ├── SKILL_BPMN.md             # System prompt AgentBPMN
│   ├── SKILL_MINUTES.md          # System prompt AgentMinutes
│   ├── SKILL_REQUIREMENTS.md     # System prompt AgentRequirements
│   └── skill_transcript_quality.md  # System prompt AgentTranscriptQuality
│
└── docs/
    └── technical_overview.md    # Este documento
```

---

## 5. TranscriptPreprocessor — Limpeza Rule-Based

O módulo `modules/transcript_preprocessor.py` compreende o formato nativo de transcrição do Microsoft Teams e aplica limpeza sem nenhuma chamada LLM.

### Pipeline interno

```
_parse_teams_transcript()
  • Extrai header (título, data) e lista de _Turn(speaker, timestamp, lines)
  • Fallback gracioso para formatos não-Teams

Para cada turno:
  _remove_fillers()          → Hhh, Mhm, hum, né, assim, tipo, uh, um, é...
  _collapse_repetitions()    → "Ivo Ivo Ivo..." → "[rep: Ivo]"
  _is_artifact_turn()        → marca [? texto] se provável ruído de fundo
  _normalize_punctuation()   → remove pontuação dupla/órfã pós-remoção

_clean_metadata_line()
  • "Invalid Date, InvalidDate" → "[Data não registrada]"
```

### Detecção de artefatos

Um turno é marcado como `[? ...]` (não deletado — preservado para curadoria humana) quando, após limpeza:
- O conteúdo tem ≤ 3 palavras
- Nenhuma palavra pertence ao vocabulário de negócio
- Alguma palavra é substring do nome de um participante conhecido (captura de mic aberto)
- Ou é uma palavra capitalizada isolada não reconhecida como termo de domínio

### Saída

```python
PreprocessingResult(
    clean_text: str,
    fillers_removed: int,
    artifact_turns: int,
    repetitions_collapsed: int,
    metadata_issues: list[str],
)
```

---

## 6. AgentTranscriptQuality — Avaliação ASR

Único agente que lê `transcript_raw` (todos os outros usam `transcript_clean`).

### Protocolo de avaliação (skill_transcript_quality.md)

1. **Census obrigatório de artifact_ratio** — conta turnos de artefato / total de turnos
2. **Aplicação de teto por faixa:**

| artifact_ratio | Teto máximo de qualquer critério |
|---|---|
| < 5% | Sem penalidade |
| 5–15% | Máximo 80 |
| 15–25% | Máximo 65 |
| > 25% | Máximo 45 |

3. **Detecção de inconsistências** — antes de pontuar, identifica trechos suspeitos (ruído de fundo, fonética incorreta, repetição de codec) e retorna como `InconsistencyItem[]`

4. **Avaliação dos 6 critérios** com pontuação 0–100 e exemplos citados do texto

5. **Output JSON** com `criteria`, `overall_summary`, `recommendation`, `inconsistencies`

### Inconsistências na UI

Os trechos detectados são **destacados em amarelo** no painel "Pré-processada" da aba de qualidade. Passar o mouse exibe o motivo explicado pela IA (tooltip).

---

## 7. BPMN Generator — Layout e Roteamento

`modules/bpmn_generator.py` produz XML BPMN 2.0 compliant com coordenadas absolutas.

### Algoritmo de layout

1. Atribuição de colunas por ordem topológica de edges
2. Cálculo de `(x, y, w, h)` para cada elemento
3. Lanes com altura dinâmica baseada no número de elementos

### Waypoint routing (`_build_di`)

| Tipo de fluxo | Roteamento |
|---|---|
| Normal (forward) | centro-direita → centro-esquerda (2 pontos) |
| Elementos empilhados (mesma coluna) | centro-baixo → centro-topo (2 pontos) |
| Backward (loop) | U-path com 4 waypoints, 25 px abaixo dos elementos |

### Eliminação de cruzamentos

Fluxos com origem e destino separados por ≥ 2 bordas de lane são substituídos por pares de **Intermediate Link Events** (throw/catch), eliminando setas que cruzam visualmente outras lanes.

### Post-processamento de regras (`_enforce_rules`)

| Regra | Ação |
|---|---|
| 0 | Remove steps declarados como startEvent/endEvent pelo LLM (gerador os cria) |
| 1 | serviceTask com ator sistema anônimo → `lane = None` (OMG §7.4) |
| 1b | Nome de lane genérico → substitui por substantivo organizacional extraído do contexto |
| 2 | Loop de correção apontando para gateway → redirecionado ao step de trabalho upstream |

---

## 8. Interface do Usuário

### Fluxo completo

```
Sidebar                          Main
────────                         ──────────────────────────────────
Selecionar provedor LLM    →     Cole ou carregue a transcrição
Inserir chave de API
                                 [🧹 Pré-processar]  (sem LLM, instantâneo)
Opções:                               ↓
  Output language                Painel de curadoria:
                                   • Stats: fillers, artefatos [?], repetições
Active Agents:                     • Original (leitura) | Pré-processada (editável)
  ☑ Qualidade da Transcrição       • Botões 📋 Copiar em ambas as colunas
  ☑ BPMN
  ☑ Ata de Reunião              [⚡ Iniciar Agentes Selecionados]
  ☑ Requisitos                       ↓
                                 Barra de progresso por agente
  ☑ Show raw JSON
```

### Abas de resultado

| Aba | Conteúdo principal |
|-----|--------------------|
| 🔬 Qualidade da Transcrição | Nota A–E, critérios, 🔍 inconsistências detectadas, before/after com highlights amarelos |
| 📐 BPMN 2.0 | Viewer interativo bpmn-js (pan/zoom/fit) |
| 📊 Mermaid | Fluxograma com toggle TD/LR client-side |
| 📝 Ata de Reunião | Participantes, agenda, decisões, action items |
| 📋 Requisitos | Tabela filtrada por tipo/prioridade |
| 🔧 Exportar | Downloads: `.bpmn`, `.mmd`, `.md`, `.json` |
| 🔍 Knowledge Hub | Metadados: tokens, agentes, versão do hub |

---

## 9. Segurança

- Chaves de API armazenadas **exclusivamente em `st.session_state`** (memória de servidor por sessão)
- Nunca escritas em arquivo, log, variável de ambiente ou banco de dados
- `session_security.py` é o único ponto de leitura/escrita de credenciais
- Descartadas automaticamente ao fechar o browser ou reiniciar o servidor

---

## 10. Dependências

```
streamlit==1.42.0
anthropic==0.49.0
openai==1.65.0
spacy>=3.7,<4.0        # modelo: pt_core_news_lg
```

```bash
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
streamlit run app.py
```

---

## 11. Extensibilidade

### Novo provedor LLM → `modules/config.py`
Adicionar entrada em `AVAILABLE_PROVIDERS`. Se `client_type` for novo, adicionar branch em `BaseAgent._call_llm()`.

### Novo agente → 4 arquivos
1. `agents/agent_novo.py` (herda `BaseAgent`)
2. `skills/SKILL_NOVO.md` (system prompt)
3. `core/knowledge_hub.py` (novo dataclass + campo em KnowledgeHub + migrate guard)
4. `agents/orchestrator.py` (registrar no `_PLAN`)

### Novo formato de diagrama → 3 pontos
1. `modules/diagram_novoformato.py` → `generate(bpmn: BPMNModel) -> str`
2. Campo em `BPMNModel`
3. Tab / download em `app.py`

---

## 12. Roadmap PC2

- [ ] Execução paralela de agentes com `asyncio.gather()`
- [ ] `AgentValidator` — scoring pós-geração com roteamento condicional (LangGraph)
- [ ] `AgentSBVR` — regras de negócio em linguagem estruturada
- [ ] `AgentBMM` — modelagem de motivação de negócio
- [ ] Suite de testes automatizados por cenário
- [ ] Export PDF da ata de reunião

---

*Atualizado em 2026-03-29 · v3.6 · pedro.gentil@process2diagram*
