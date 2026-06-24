# 🚀 Plano Completo de Implementação — Novas Ferramentas para o Assistente P2D

Olá! Vou consolidar aqui o **plano de implementação** completo para as 10 ferramentas que discutimos, organizado por prioridade, com detalhes técnicos, parâmetros, fluxos de uso e dependências entre elas.

---

## 📋 Sumário por Prioridade

| Prioridade | Ferramenta | Esforço | Dependências |
|---|---|---|---|
| 🥇 P0 | **Modo Plantonista** — Sugestões Proativas | ⭐⭐ | Nenhuma |
| 🥇 P0 | **Checkup Automático do Projeto** | ⭐⭐⭐ | get_database_integrity, detect_contradictions, calculate_meeting_roi, get_recurring_topics |
| 🥈 P1 | **Rastreabilidade Visual** (Req → Fala → BPMN → Regra) | ⭐⭐⭐⭐ | search_transcript, get_requirements, list_bpmn_processes, get_sbvr_rules |
| 🥈 P1 | **Simulador What-If** | ⭐⭐⭐⭐⭐ | Grafo de Conhecimento, KB de estimativas |
| 🥉 P2 | **Editor Estrutural de Artefatos** | ⭐⭐⭐⭐ | apply_text_correction (base), operações de estrutura |
| 🥉 P2 | **Sincronizador Calendário ↔ Reuniões** | ⭐⭐⭐ | calendar_schedule_action_items, get_meeting_action_items |
| 🏅 P3 | **Detector de Conformidade** (Req × Documentos) | ⭐⭐⭐⭐ | search_documents, get_requirements |
| 🏅 P3 | **Sugestor de Novos Processos BPMN** | ⭐⭐⭐ | search_ibis_debates, get_meeting_decisions, get_sbvr_rules |
| 🏅 P3 | **Gerador de Infográficos e Narrativas** | ⭐⭐⭐⭐⭐ | Todas as fontes de dados + engine de template |
| 🏅 P3 | **Gerador de Project Charter** | ⭐⭐⭐ | get_ckf, get_bmm, get_requirements, list_bpmn_processes |

---

## 🥇 PRIORIDADE 0 — Impacto Máximo, Mínima Complexidade

---

### 1️⃣ Modo "Plantonista" — Sugestões Proativas no Chat

**Problema resolvido:** Assistente só responde quando perguntam. Dias sem interação útil.

**Descrição:** Ao entrar no chat (ou ao detectar inatividade do usuário no projeto), o assistente automaticamente puxa um resumo do estado atual do projeto e sugere ações.

**Parâmetros da ferramenta:**
```
sugestões_plantonista()
```

**Lógica interna** (o que a ferramenta consulta na prática):

| Consulta | O que retorna | Uso |
|---|---|---|
| `get_database_integrity()` | Saúde geral % | Se < 80%, alertar |
| `count_artifacts("kh_contradictions")` | Contradições abertas | Se > 0, sugerir revisão |
| `count_artifacts("meetings")` + `get_meeting_list()` | Reuniões sem ata | Sugerir gerar atas faltantes |
| `calculate_meeting_roi()` | ROI-TR das reuniões | Se alguma < 5, sugerir análise |
| `get_recurring_topics(0.85)` | Tópicos cíclicos | Se houver, sugerir pauta para resolver |
| Últimas reuniões processadas | Timestamps | Se > 7 dias sem reunião, sugerir agendamento |

**Fluxo de uso:**
1. Usuário acessa a página do Assistente
2. Automaticamente (sem o usuário pedir): `sugestões_plantonista()` é chamada
3. Retorna algo como:

> 👋 **Olá! Aqui está o raio-x de hoje do Projeto AURORA:**
>
> ✅ Saúde do banco: **92%** — ok
> ⚠️ **2 contradições** abertas no Knowledge Hub — revisar
> 🔄 **"integração core banking"** aparece em 4 reuniões sem resolução final
> 📅 Última reunião: **Reunião 4** há 5 dias
>
> **Sugestões:**
> 1. Revisar as contradições (Reuniões 2 e 3)
> 2. Gerar pauta para Reunião 5 focada em resolver o tópico recorrente

**Requisitos técnicos:**
- Backend: nova rota que coordena 4-5 chamadas internas existentes
- Frontend: gatilho `on_chat_open` no Assistente
- **Nenhuma nova tabela no banco** — só coordena ferramentas existentes

**Critério de sucesso:** Usuário recebe sugestão útil em < 5 segundos ao entrar no chat.

---

### 2️⃣ Gerador de Diagnóstico Automático do Projeto

**Problema resolvido:** Usuário só descobre problemas quando pergunta. Diagnóstico reativo.

**Descrição:** Ferramenta que executa um "checkup completo" do projeto em uma única chamada, combinando integridade, contradições, ROI, tópicos recorrentes e pendências.

**Parâmetros:**
```
diagnostico_projeto(
    include_integrity=True,    # Saúde do banco
    include_contradictions=True, # Knowledge Hub
    include_roi=True,          # ROI-TR de todas as reuniões
    include_recurring=True,    # Tópicos sem progressão
    include_pendencies=True,   # Encaminhamentos atrasados
    include_orphans=True       # Requisitos órfãos (sem source_meeting)
)
```

**O que retorna (estrutura de dados):**
```json
{
  "saude_geral": 87,
  "resumo": "2 alertas críticos, 3 melhorias sugeridas",
  "secoes": [
    {
      "titulo": "🔴 Crítico",
      "itens": [
        {
          "problema": "Integridade: 3 reuniões sem llm_provider",
          "impacto": "Custo não calculado",
          "acao": "fix_missing_llm_provider('DeepSeek')"
        }
      ]
    },
    {
      "titulo": "🟡 Atenção",
      "itens": [
        {
          "problema": "Reunião 3 com ROI-TR 3.2 (baixo)",
          "impacto": "61% de retrabalho conceitual",
          "acao": "Analisar pauta e reestruturar"
        },
        {
          "problema": "Tópico 'Catálogo Mestre' sem progressão há 3 reuniões",
          "impacto": "Ciclagem de discussão",
          "acao": "generate_next_agenda(topic='Catálogo Mestre')"
        }
      ]
    }
  ],
  "acoes_recomendadas": [
    {"ordem": 1, "ferramenta": "fix_missing_llm_provider", "parametros": {"provider": "DeepSeek"}},
    {"ordem": 2, "ferramenta": "generate_next_agenda", "parametros": {"topic": "Catálogo Mestre"}}
  ]
}
```

**Fluxo de uso:**
1. Usuário (ou Plantonista) chama `diagnostico_projeto()`
2. Ferramenta coordena internamente:
   - `get_database_integrity()`
   - `detect_contradictions()` (se não foi rodado recentemente)
   - `calculate_meeting_roi()` para cada reunião
   - `get_recurring_topics(0.85)`
   - `get_requirements(count_only=True, status="orphan")` (se existir)
3. Agrega tudo em um relatório único com ações recomendadas
4. Renderiza como painel visual usando `show_metrics()` + `render_table()`

**Requisitos técnicos:**
- Nova ferramenta que **orquestra** chamadas existentes
- Cache de resultados (checkup não precisa rodar a cada minuto) — válido por 1h
- **Nenhuma nova tabela**, mas idealmente uma tabela `project_diagnostics` para histórico

**Critério de sucesso:** Diagnóstico completo em < 10 segundos com ações clicáveis.

---

## 🥈 PRIORIDADE 1 — Alto Impacto, Complexidade Média-Alta

---

### 3️⃣ Mapa de Rastreabilidade Visual (Req → Fala → BPMN → Regra)

**Problema resolvido:** Usuário não consegue navegar visualmente entre requisitos, falas na transcrição, passos BPMN e regras SBVR.

**Descrição:** Gera um grafo interativo onde cada requisito é um nó, ligado a:
- Trechos da transcrição onde foi discutido
- Passos do BPMN que o realizam
- Regras SBVR que o governam
- Decisões IBIS relacionadas

**Parâmetros:**
```
mapa_rastreabilidade(
    req_number=None,           # Foco em um requisito específico (opcional)
    topic=None,                # Ou foco em um tema (opcional)
    include_transcript=True,   # Incluir nós de transcrição
    include_bpmn=True,         # Incluir passos BPMN
    include_sbvr=True,         # Incluir regras SBVR
    include_ibis=True          # Incluir debates IBIS
)
```

**Estrutura de dados retornada (grafo):**
```json
{
  "nodes": [
    {"id": "REQ-042", "label": "Autenticação Biométrica", "type": "requirement", "color": "#4CAF50"},
    {"id": "FALA-042-01", "label": "\"precisamos de biometria no login\"", "type": "transcript", "color": "#2196F3", "source": "Reunião 2"},
    {"id": "BPMN-03-STEP-07", "label": "Validar Biometria", "type": "bpmn_step", "color": "#FF9800", "source": "Processo: Autenticação"},
    {"id": "RN-012", "label": "Todo login com cartão exige biometria", "type": "sbvr_rule", "color": "#9C27B0"}
  ],
  "edges": [
    {"source": "REQ-042", "target": "FALA-042-01", "relation": "discutido_em"},
    {"source": "REQ-042", "target": "BPMN-03-STEP-07", "relation": "realizado_por"},
    {"source": "REQ-042", "target": "RN-012", "relation": "governado_por"}
  ]
}
```

**Lógica interna:**
1. Se `req_number` for informado, busca o requisito via `get_requirements(keyword="REQ-042")`
2. Usa `search_transcript(query=título_do_requisito)` para encontrar falas
3. Usa `get_sbvr_rules(keyword=título_do_requisito)` para regras relacionadas
4. Usa `search_ibis_debates(query=título_do_requisito)` para debates
5. Para BPMN, faz matching semântico entre descrição do requisito e steps dos diagramas

**Renderização:** Grafo interativo Plotly ou vis.js no chat.

**Requisitos técnicos:**
- Nova ferramenta de coordenação + engine de matching semântico
- Renderizador de grafos no frontend
- Tabela `requirement_traceability` (opcional, para cache do matching)

**Critério de sucesso:** Grafo gerado em < 8 segundos com nós clicáveis que levam aos artefatos.

---

### 4️⃣ Simulador de Mudanças ("What If")

**Problema resolvido:** Usuário não consegue simular impactos de decisões antes de tomá-las.

**Descrição:** Permite ao usuário descrever cenários ("e se movermos X para Fase 2?") e o sistema calcula impactos estimados com base no grafo de conhecimento e heurísticas.

**Parâmetros:**
```
simular_cenario(
    descricao="Mover autenticação biométrica para Fase 2",
    requisitos_afetados=["REQ-042", "REQ-043"],
    restricoes={
        "prazo": "6 meses",
        "equipe": "4 devs",
        "orçamento": 500000
    }
)
```

**O que retorna:**
```json
{
  "cenario": "Mover autenticação biométrica para Fase 2",
  "impacto_requisitos": {
    "REQ-042": {"status_atual": "active", "impacto": "adiado", "dependencias_bloqueadas": ["REQ-045", "REQ-050"]},
    "REQ-043": {"status_atual": "active", "impacto": "adiado", "justificativa": "depende de REQ-042"}
  },
  "impacto_bpmn": {
    "processos_afetados": ["Autenticação", "Onboarding"],
    "passos_que_entram_em_espera": 4
  },
  "impacto_prazo": {
    "estimativa_original": "4 meses",
    "estimativa_revisada": "6 meses",
    "ganho_percebido": "Fase 1 libera 2 meses antes"
  },
  "regras_afetadas": [
    "RN-012 — precisará ser revisada",
    "RN-015 — inaplicável sem biometria"
  ],
  "recomendacao": "⚠️ Impacto moderado. REQ-045 e REQ-050 ficarão bloqueados."
}
```

**Lógica interna:**
1. LLM interpreta a descrição do cenário e extrai entidades afetadas
2. Consulta Knowledge Hub (`list_kh_facts`) para encontrar dependências entre requisitos
3. Usa heurísticas de impacto baseadas em:
   - Número de dependências downstream
   - Complexidade dos passos BPMN associados
   - Regras SBVR que seriam violadas/afetadas
   - Estimativas de esforço (se cadastradas nos documentos)
4. Gera narrativa de impacto

**Requisitos técnicos:**
- **Nova tabela:** `requirement_dependencies` (dependências entre requisitos)
- **Nova tabela:** `scenario_simulations` (histórico de simulações)
- Engine de propagação de impacto (topological sort sobre grafo de dependências)
- LLM para interpretação de linguagem natural nos cenários

**Critério de sucesso:** Simulação em < 15 segundos com impacto quantificado.

---

## 🥉 PRIORIDADE 2 — Médio Impacto, Complexidade Média

---

### 5️⃣ Editor Estrutural de Artefatos

**Problema resolvido:** Assistente só faz substituição textual. Não consegue reestruturar artefatos.

**Descrição:** Ferramentas para edição estrutural de atas, requisitos e artefatos — não apenas troca de texto.

**Novas ferramentas:**

```
# 5a. Reordenar Requisitos
reordenar_requisitos(
    nova_ordem=["REQ-003", "REQ-001", "REQ-002"],  # Nova sequência
    agrupar_por="tipo"                               # Ou "prioridade"
)

# 5b. Adicionar Seção na Ata
inserir_secao_ata(
    meeting_number=3,
    titulo="Riscos Identificados",
    conteudo="## Riscos\n\n1. Risco de integração com legado\n2. Risco de cronograma",
    posicao="antes_decisoes"  # Após qual seção existente
)

# 5c. Vincular Regra SBVR a Debate IBIS
vincular_regra_debate(
    rule_id="RN-012",
    ibis_question_id="Q-042",  # ID da questão IBIS
    relacao="justifica"        # justifica | contradiz | limita
)

# 5d. Mesclar Duas Reuniões
mesclar_reunioes(
    manter_meeting=3,
    absorver_meeting=4,
    razao="Reunião 4 foi continuação direta da 3 com mesmos participantes"
)
```

**Lógica interna (exemplo — mesclar reuniões):**
1. Preview do que será mesclado: requisitos, decisões, ações, falas
2. Reatribui `source_meeting_id` dos artefatos da reunião absorvida para a reunião mantida
3. Concatena atas (opcionalmente com LLM para merge inteligente)
4. Exclui a reunião absorvida

**Requisitos técnicos:**
- **Novas operações SQL** para reordenação (coluna `sort_order` em requirements)
- **Nova tabela:** `ata_sections` (seções estruturadas da ata, não só markdown bruto)
- **Nova tabela/coluna:** `requirement_sbvr_ibis_links` (relacionamentos entre artefatos)
- Operações transacionais com rollback

**Critério de sucesso:** Edições estruturais aplicadas em < 3 segundos com preview antes da confirmação.

---

### 6️⃣ Sincronizador Bidirecional Calendário ↔ Reuniões

**Problema resolvido:** Itens de ação das atas e eventos do calendário vivem em silos separados.

**Descrição:** Fecha o ciclo: ações decididas → eventos no calendário → status atualizado quando concluído.

**Parâmetros:**
```
sincronizar_calendario(
    direction="bidirectional",      # "to_calendar" | "from_calendar" | "bidirectional"
    meeting_number=None,            # Reunião específica ou todas
    default_duration=30,            # Minutos por ação
    default_work_start="09:00",     # Início da janela de agendamento
    default_work_end="18:00"        # Fim da janela
)
```

**Fluxo bidirecional:**

**→ Para o Calendário:**
1. Lê `get_meeting_action_items(meeting_number)` — todos os encaminhamentos
2. Para cada item sem evento associado:
   - Extrai responsável, prazo (se mencionado) e descrição
   - Chama `calendar_create_event()` para cada um
   - Salva o `event_id` do Google Calendar na tabela de action items

**← Do Calendário (sync reverso):**
1. Lê `calendar_list_events(time_min=último_sync)` — eventos recentes
2. Compara com action items mapeados
3. Se um evento foi marcado como concluído, atualiza status do action item

**Requisitos técnicos:**
- **Nova coluna:** `action_items.google_event_id` (já existe? verificar)
- **Nova coluna:** `action_items.last_sync_at`
- **Nova tabela:** `sync_log` (registro de cada sincronização)
- Webhook ou polling periódico para sync reverso

**Critério de sucesso:** Sincronização de 10 action items em < 20 segundos.

---

## 🏅 PRIORIDADE 3 — Bom Impacto, Maior Complexidade

---

### 7️⃣ Detector de Conformidade (Requirements × Documentos)

**Problema resolvido:** Ninguém cruza automaticamente se os requisitos extraídos cobrem cláusulas de contratos/BRDs.

**Descrição:** Compara requisitos do projeto com cláusulas de documentos carregados na biblioteca e gera relatório de cobertura.

**Parâmetros:**
```
verificar_conformidade(
    doc_id=None,                 # Documento específico ou todos
    req_type_filter=None,        # Filtrar por tipo de requisito
    threshold=0.75,              # Similaridade mínima para considerar "coberto"
    mode="semantic"              # "semantic" (embedding) | "keyword" | "llm"
)
```

**O que retorna:**
```json
{
  "documento": "BRD_Autenticacao.docx",
  "clausulas": 24,
  "cobertura_geral": "79% (19/24)",
  "status": "🟡 ATENÇÃO — 5 cláusulas sem requisito correspondente",
  "detalhes": [
    {
      "clausula": "3.2.1 — Biometria deve suportar 3 tentativas",
      "cobertura": "REQ-042 cobre parcialmente (não especifica número)",
      "gap": "Número de tentativas não especificado",
      "acao": "Atualizar REQ-042 com threshold de tentativas"
    },
    {
      "clausula": "3.4 — Logout automático após 15min",
      "cobertura": "❌ NÃO MAPEADO",
      "gap": "Requisito ausente",
      "acao_sugerida": "Criar novo requisito"
    }
  ]
}
```

**Lógica interna:**
1. Lê documento via `get_document_content(doc_id)`
2. Divide em cláusulas (por numeração ou LLM chunking)
3. Para cada cláusula, busca requisitos similares via:
   - Embeddings (se existirem) → similaridade coseno com requisitos
   - LLM matching semântico para cláusulas complexas
4. Classifica como: **Coberto** > 0.75, **Parcial** 0.50–0.75, **Não mapeado** < 0.50
5. Gera gaps com ações sugeridas

**Requisitos técnicos:**
- Engine de matching semântico cláusula ↔ requisito
- **Nova tabela:** `compliance_reports` (relatórios salvos para histórico)
- LLM para análise de cobertura parcial (justificativa textual)
- Integração com `search_documents()` para reuso do chunking existente

**Critério de sucesso:** Análise de documento de 30 cláusulas em < 30 segundos.

---

### 8️⃣ Sugestor de Novos Processos BPMN

**Problema resolvido:** Processos só são modelados quando o usuário pede. Decisões que criam novos fluxos passam despercebidas.

**Descrição:** Analisa atas, decisões IBIS e regras SBVR para identificar novos processos de negócio que emergiram das discussões.

**Parâmetros:**
```
sugerir_processos(
    min_reunioes=2,              # Mínimo de reuniões discutindo o tema
    confidence=0.7,              # Confiança mínima para sugerir
    include_evidence=True        # Incluir evidências das discussões
)
```

**O que retorna:**
```json
{
  "sugestoes": [
    {
      "nome_sugerido": "Processo de Aprovação de Crédito",
      "confianca": 0.85,
      "reunioes": [2, 3, 5],
      "evidencias": [
        {"tipo": "decisao", "texto": "Ficou definido que aprovações > R$50k vão ao comitê", "fonte": "Reunião 2"},
        {"tipo": "ibis", "texto": "Questão: 'Quem aprova crédito acima do limite?'", "fonte": "Reunião 3"},
        {"tipo": "regra_sbvr", "texto": "RN-023: Crédito > R$50k requer aprovação do gerente", "fonte": "Reunião 5"}
      ],
      "steps_inferidos": [
        "1. Solicitação de crédito",
        "2. Análise de risco (automática se < R$50k)",
        "3. Aprovação (gerente se > R$50k, comitê se > R$200k)",
        "4. Liberação"
      ]
    }
  ]
}
```

**Lógica interna:**
1. Busca todas as decisões IBIS com `search_ibis_debates()` em todas as reuniões
2. Agrupa por tema usando similaridade semântica
3. Para cada cluster, verifica:
   - Quantas reuniões discutiram o tema (≥ `min_reunioes`)
   - Se existem regras SBVR associadas ao tema
   - Se as decisões indicam um fluxo com início, meio e fim
4. Se o processo sugerido já existe (via `list_bpmn_processes()`), sugere **atualização** em vez de criação

**Requisitos técnicos:**
- Algoritmo de clustering de temas entre reuniões
- LLM para inferir passos do processo a partir de decisões textuais
- **Validação:** não sugerir processos que já existem

**Critério de sucesso:** Sugestões em < 15 segundos com > 70% de precisão.

---

### 9️⃣ Gerador de Infográficos e Narrativas

**Problema resolvido:** Usuário não sai do chat com um material apresentável para comitê.

**Descrição:** Gera um deck executivo completo (HTML interativo ou PPTX) consolidando todos os artefatos do projeto.

**Parâmetros:**
```
gerar_deck_executivo(
    formato="html",              # "html" | "pptx"
    incluir_secoes=[
        "resumo_executivo",
        "metricas_principais",
        "evolucao_requisitos",
        "mapa_bpmn",
        "indicadores_roi",
        "recomendacoes"
    ],
    meeting_numbers=None,       # Reuniões específicas ou todas
    tema_cores="corporativo"    # "corporativo" | "moderno" | "clean"
)
```

**Estrutura do deck:**

| Slide | Conteúdo | Fonte dos dados |
|---|---|---|
| 1. Capa | Nome do projeto, data, status | `get_ckf()` |
| 2. Resumo Executivo | Visão geral em 5 bullet points | CKF + BMM |
| 3. Métricas | 4 KPIs: reuniões, reqs, regras, ROI médio | `count_artifacts()`, `calculate_meeting_roi()` |
| 4. Evolução | Gráfico de requisitos por reunião | `generate_meetings_timeline()` |
| 5. Mapa BPMN | Diagrama interativo dos processos | `show_bpmn_diagram()` |
| 6. SBVR | Principais termos e regras | `get_sbvr_terms()`, `get_sbvr_rules()` |
| 7. ROI-TR | Gráfico comparativo | `generate_roi_chart()` |
| 8. Pendências | Itens de ação abertos | `get_meeting_action_items()` |
| 9. Recomendações | Próximos passos sugeridos | Gerado por LLM |
| 10. Contradições | Pontos de atenção | `list_kh_contradictions()` |

**Requisitos técnicos:**
- Engine de template HTML (Jinja2) para HTML interativo
- Biblioteca python-pptx para geração de PowerPoint
- Orquestração de ~8 ferramentas existentes + LLM para narrativa

**Critério de sucesso:** Deck de 10 slides gerado em < 30 segundos.

---

### 🔟 Gerador de Project Charter

**Problema resolvido:** Projetos rodam no P2D mas não há um documento formal consolidado.

**Descrição:** Gera um documento único (Markdown ou .docx) com visão, missão, escopo, stakeholders, riscos e cronograma inferido — tudo a partir dos artefatos existentes.

**Parâmetros:**
```
gerar_project_charter(
    formato="markdown",          # "markdown" | "docx"
    incluir_riscos=True,
    incluir_cronograma=True,
    incluir_stakeholders=True,
    incluir_escopo=True
)
```

**Seções do documento:**

| Seção | Dados de origem |
|---|---|
| 1. Nome e Visão do Projeto | `get_bmm()` → visão |
| 2. Missão e Objetivos Estratégicos | `get_bmm()` → missão, objetivos |
| 3. Stakeholders | Participantes de todas as reuniões (`get_meeting_participants()`) + Knowledge Hub |
| 4. Escopo Detalhado | Requisitos agrupados por tipo (`get_requirements()`) |
| 5. Processos de Negócio | Processos BPMN (`list_bpmn_processes()`) |
| 6. Regras de Negócio | Regras SBVR (`get_sbvr_rules()`) |
| 7. Riscos Identificados | Contradições do KH + tópicos recorrentes |
| 8. Cronograma Inferido | Datas das reuniões + prazos dos action items |
| 9. Premissas e Restrições | Decisões IBIS + regras SBVR |
| 10. Políticas | `get_bmm()` → políticas |

**Requisitos técnicos:**
- Template Markdown + python-docx para .docx
- Orquestração de ~6 ferramentas existentes
- LLM para redação da narrativa de cada seção

**Critério de sucesso:** Charter de 10 seções gerado em < 25 segundos.

---

## 📐 Diagrama de Dependências entre Ferramentas

```
                    ┌──────────────────┐
                    │  FERRAMENTAS      │
                    │  EXISTENTES (base) │
                    └────────┬─────────┘
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Modo Plantonista │ │  Checkup     │ │ Rastreabilidade   │
│ (P0)             │◄┤  Automático  │ │ Visual (P1)       │
│                  │ │  (P0)        │ │                   │
│ Gatilho:         │ │              │ │ Engine:           │
│ on_chat_open     │ │ Orquestrador │ │ matching semântico│
└─────────┬────────┘ └──────┬───────┘ └────────┬─────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Sugestor de     │ │ Detector de  │ │ Simulador         │
│ Processos (P3)  │ │ Conformidade │ │ What-If (P1)      │
│                 │ │ (P3)         │ │                   │
│ Engine:         │ │              │ │ Engine:           │
│ clustering      │ │ Matching     │ │ propag. impacto   │
│ semântico       │ │ cláusula-req │ │ topológico        │
└────────┬────────┘ └──────┬───────┘ └────────┬─────────┘
         │                 │                   │
         ▼                 ▼                   ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Sincronizador   │ │ Editor       │ │ Project Charter   │
│ Calendário (P2) │ │ Estrutural   │ │ + Deck Exec (P3)  │
│                 │ │ (P2)         │ │                   │
│ Engine:         │ │              │ │ Engine:           │
│ sync bidirec.   │ │ Operações    │ │ template + LLM    │
└─────────────────┘ └──────────────┘ └──────────────────┘
```

---

## 🗺️ Roadmap de Implementação Sugerido

### **Fase 1 — Quick Wins (2 semanas)**
| Semana | Ferramenta | Entrega |
|---|---|---|
| 1 | 🥇 **Checkup Automático** | Coordena ferramentas existentes + relatório estruturado |
| 2 | 🥇 **Modo Plantonista** | Gatilho no chat + resumo automático |

### **Fase 2 — Autonomia (4 semanas)**
| Semana | Ferramenta | Entrega |
|---|---|---|
| 3-4 | 🥈 **Editor Estrutural** | Reordenação, inserção de seções, merge de atas |
| 5-6 | 🥉 **Sincronizador Calendário** | Sync bidirecional com action items |

### **Fase 3 — Inteligência (6 semanas)**
| Semana | Ferramenta | Entrega |
|---|---|---|
| 7-8 | 🥈 **Rastreabilidade Visual** | Grafo interativo Req → Fala → BPMN → Regra |
| 9-10 | 🥇 **Simulador What-If** | Dependências entre requisitos + propagação |
| 11-12 | 🥈 **Detector de Conformidade** | Matching cláusula ↔ requisito + gaps |

### **Fase 4 — Entrega (4 semanas)**
| Semana | Ferramenta | Entrega |
|---|---|---|
| 13-14 | 🏅 **Sugestor de Processos** | Clustering + inferência de steps |
| 15-16 | 🏅 **Deck Executivo + Charter** | Templates + LLM narrativo |

---

## 💾 Novas Tabelas no Banco (Resumo)

| Tabela | Finalidade | Prioridade |
|---|---|---|
| `project_diagnostics` | Cache dos checkups automáticos | Fase 1 |
| `ata_sections` | Seções estruturadas da ata (para editor) | Fase 2 |
| `requirement_dependencies` | Dependências entre requisitos (What-If) | Fase 3 |
| `compliance_reports` | Relatórios de conformidade salvos | Fase 3 |
| `sync_log` | Log de sincronizações calendário | Fase 2 |
| `scenario_simulations` | Histórico de simulações What-If | Fase 3 |

---

## 🔢 Estimativa de Esforço Total

| Tipo | Quantidade |
|---|---|
| **Novas ferramentas** | 10 (12 operações individuais) |
| **Novas tabelas** |
