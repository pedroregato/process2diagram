# Avaliação — Proposta do Assistente (`proposta-assistente-20260708.md`)

> Este documento avalia viabilidade das 18 ferramentas propostas pelo próprio Assistente (auto-sugestão) e traça um plano de implementação para as que valem a pena. Pesquisa de base: leitura de `core/assistant_tools.py` + `core/tools/*.py` (catálogo real de ~90 tools), `requirements.txt`, e `melhorias/integracao-Jira.md` (já existente).

## Achado geral mais importante

**6 das 18 propostas já existem, no todo ou em grande parte**, sob outro nome. O assistente não tinha visão completa do próprio catálogo ao propor. Antes de construir qualquer coisa nova, vale considerar só **renomear/documentar melhor** essas 6 (ganho rápido, custo ~zero):

| # | Proposta | Já existe como |
|---|---|---|
| 10 | Assistente de Edição Visual de BPMN | `apply_bpmn_corrections` + `suggest_bpmn_corrections` (`core/tools/tools_bpmn_sbvr.py`) — já traduz linguagem natural em correções estruturadas e salva nova versão |
| 16 | Trilha de Auditoria Visual | `get_requirement_history` + `diff_requirement` (`core/tools/tools_knowledge_requirements2.py`) — já dá histórico de versão + diff HTML vermelho/verde estilo git |
| 4 (parte de dados) | Workflow de Aprovação | `update_requirement_status` já aceita `approved`/`rejected`/`revised`/`in_progress`/etc + `status_note` + versiona — falta só a camada de notificação/UX conversacional |
| 8 (parte de conteúdo) | Exportador de Termo de Abertura | `gerar_project_charter` já gera o Charter completo via LLM — falta só o `.docx` |
| 18 | Simulador de Impacto Regulatório | `simular_cenario` + `verificar_conformidade` combinados já cobrem "documento normativo mudou → o que é afetado" |
| 7 | Integrador Jira/ADO | Já tem plano próprio em `melhorias/integracao-Jira.md` — não é gap novo, é iniciativa já registrada (ver ressalva abaixo) |

**Ressalva sobre `melhorias/integracao-Jira.md`:** o documento existente mistura visão de produto real com conteúdo claramente aspiracional/gerado por outra IA para um rebrand futuro ("RawToInsights AI", Firestore, Google Cloud Run, Gemini — nada disso é a stack atual, que é Supabase + Streamlit + DeepSeek). Antes de tratar Jira como prioridade de engenharia, esse documento precisa ser reescrito contra a arquitetura REAL (Supabase, `core/tools/`, `AssistantToolExecutor`) — hoje ele não é executável como está.

## Restrição arquitetural que elimina 3 propostas de cara

`AssistantToolExecutor.__init__(self, project_id, ...)` recebe **um único** `project_id`; toda query em todo mixin filtra por `.eq("project_id", self.project_id)`. Não existe hoje nenhuma tool que agregue artefatos (requisitos, BPMN, IBIS, decisões) de **múltiplos projetos ao mesmo tempo** — só existe isso para metadados de usuário (`list_users_by_project`, `get_users_by_domain`). Isso torna as propostas **#13 Benchmarking de Projetos**, **#14 Catálogo de Processos Reutilizáveis** e **#15 Biblioteca de Decisões** uma mudança de arquitetura, não um novo tool isolado — precisariam de uma camada nova de "cross-project query" (instanciar N executors e agregar, ou reescrever queries pra aceitar lista de `project_id`). Não é proibitivo, mas é um projeto à parte, não uma "melhoria pontual". Recomendo tratar como **Fase separada**, só se houver demanda real de negócio por comparação entre clientes/projetos (normalmente um recurso de tier Enterprise).

## Veredito completo (18 itens)

| # | Proposta | Veredito | Esforço | Vale construir agora? |
|---|---|---|---|---|
| 1 | Analista de Tendências | Parcial (`get_requirement_history`, `get_recurring_topics` dão a matéria-prima) | Médio | Sim — ver plano |
| 2 | Classificador de Maturidade | Não existe, mas baixa acionabilidade | Baixo-médio | Não — fundir em `diagnostico_projeto` em vez de tool nova |
| 3 | Estimador de Risco por Requisito | Não existe | Médio | Sim — ver plano |
| 4 | Workflow de Aprovação | Dados já existem; falta notificação | Alto (notificação = integração nova) | Parcial — ver plano (sem notificação) |
| 5 | ADR (Registro de Decisão Arquitetural) | Não existe | Médio-alto (schema novo) | Não agora — artefato de engenharia de software, público-alvo diferente do projeto (BA/PM) |
| 6 | Gerador de Release Notes | Não existe, mas reaproveita `get_requirement_history`/`diff_requirement` | Médio | Sim — ver plano |
| 7 | Integrador Jira/ADO | Já planejado à parte (doc precisa reescrita) | Alto | Não nesta rodada — auth externa, escopo próprio |
| 8 | Termo de Abertura em .docx | `gerar_project_charter` já existe; falta exportar | **Baixo** | **Sim — quick win** |
| 9 | Importador de Planilha (.xlsx) | Não existe; `openpyxl` já é dependência | Médio | Sim — ver plano |
| 10 | Edição Visual de BPMN | Já existe (`apply_bpmn_corrections`) | — | Não construir; documentar/divulgar melhor |
| 11 | Comparador de Atas | Parcial (`compare_meeting_transcripts` é outra coisa — duplicata, não diff) | **Baixo-médio** | **Sim — quick win** |
| 12 | Tour Guiado do Projeto | Não existe, mas é UX/onboarding, não "inteligência" | Baixo | Não como tool do Assistente — melhor como página estática (padrão `Orientacoes_*`) |
| 13 | Benchmarking entre Projetos | Não existe — exige mudança de arquitetura | Alto | Não agora — Fase separada |
| 14 | Catálogo de Processos Reutilizáveis (cross-projeto) | Existe só single-project (`sugerir_processos`) | Alto | Não agora — Fase separada |
| 15 | Biblioteca de Decisões (cross-projeto) | Existe só single-project (`cluster_topic_decisions`) | Alto | Não agora — Fase separada |
| 16 | Trilha de Auditoria Visual | Já existe (`get_requirement_history`+`diff_requirement`) | — | Não construir; documentar melhor |
| 17 | Verificador de Rastreabilidade Obrigatória | Parcial (`get_database_integrity` é outro escopo — pipeline, não completude de conteúdo) | **Baixo-médio** | **Sim — quick win** |
| 18 | Simulador de Impacto Regulatório | Já coberto combinando 2 tools existentes | — | Não construir; documentar o combo no guia de ferramentas |

## Priorização recomendada por 1ª pergunta de ROI

Priorizei por **"quanto reaproveita infraestrutura já validada"** — não por frente temática como o assistente fez. As 3 primeiras entradas mal têm código novo de verdade, é composição do que já existe.

---

### 🥇 Onda 1 — Quick wins (reaproveitam ≥80% de infraestrutura existente)

#### 1. Termo de Abertura em .docx (proposta #8)
- **O quê:** `gerar_project_charter()` já produz Markdown formal via LLM. Adicionar export `.docx` reaproveitando o renderizador markdown→docx que **já existe e é genérico**: `modules/minutes_exporter.py::_render_markdown_docx()` (usado hoje como fallback de ata) ou, melhor ainda, o padrão recém-criado em `modules/ata_template_engine.py` (PC160) — reaproveitando inclusive templates por contexto se o cliente quiser o Charter com a identidade visual da empresa.
- **Como:** nova tool `export_project_charter_docx()` (ou parâmetro `formato: "markdown"|"docx"` na tool existente) → chama `gerar_project_charter()` → passa o Markdown resultante para uma função `markdown_to_docx()` extraída/generalizada de `_render_markdown_docx()` → retorna widget de download (`type="file_download"`, mesmo padrão já usado por outras tools de export).
- **Esforço:** 1 dia. Zero schema novo, zero LLM novo, zero UI nova (reaproveita o widget de download já existente no chat).

#### 2. Comparador de Atas (proposta #11)
- **O quê:** diff estruturado entre 2 reuniões específicas — participantes que entraram/saíram, decisões novas, encaminhamentos que mudaram de status — não é duplicata do `compare_meeting_transcripts` (que mede similaridade textual pra achar reuniões repetidas).
- **Como:** nova tool `compare_meetings(meeting_id_a, meeting_id_b)`. Reaproveita 2 padrões já provados no código: (a) o diff HTML vermelho/verde já usado em `diff_requirement` (`core/tools/tools_knowledge_requirements2.py:1008`) — mesma lógica de renderização, aplicada a `participants`/`decisions`/`action_items` em vez de campos de requisito; (b) `set` diff simples em Python (participantes só em A, só em B, em ambos) — não precisa de LLM, é comparação estrutural.
- **Esforço:** 1-2 dias. Sem schema novo (usa `meetings.minutes_md`/campos já persistidos).

#### 3. Verificador de Rastreabilidade Obrigatória (proposta #17)
- **O quê:** scan agregado do projeto inteiro: requisitos sem `source_quote`, questões IBIS sem alternativa registrada, processos BPMN sem descrição textual — gap analysis de completude, diferente do `get_database_integrity` (que é saúde de *pipeline*, não de *conteúdo*).
- **Como:** nova tool `verificar_rastreabilidade_obrigatoria()`, sem LLM (heurística pura, mesmo espírito de `diagnostico_projeto`/`sugestoes_plantonista`): 3 queries diretas (`requirements` sem `source_quote`, `argumentation_questions` sem `resolution`/alternativa, `bpmn_processes` sem `description`), consolidadas num relatório com contagem + lista de IDs afetados.
- **Esforço:** 1 dia. Zero schema novo, zero LLM.

**Onda 1 total: ~4 dias de trabalho, 3 ferramentas novas, reaproveitamento máximo.**

---

### 🥈 Onda 2 — Valor real, esforço moderado (schema existente, lógica nova)

#### 4. Gerador de Release Notes (proposta #6)
- **O quê:** consolida `diff_requirement` de MÚLTIPLOS requisitos entre 2 marcos (ex: reunião N e reunião N+5) numa nota de release única, em linguagem natural — técnica e executiva.
- **Como:** nova tool `gerar_release_notes(meeting_id_inicio, meeting_id_fim)`: busca todas as `requirement_versions` no intervalo de datas das 2 reuniões (já existe a tabela), agrupa por `change_type`, e usa 1 chamada LLM pra sintetizar em prosa (reaproveita o padrão de `gerar_deck_executivo`/`gerar_project_charter` — 1 chamada LLM sobre dados já agregados em Python).
- **Esforço:** 2-3 dias.

#### 5. Analista de Tendências (proposta #1)
- **O quê:** rankings agregados — "quais REQs mais mudam de versão", "quais tópicos geram mais debate IBIS", "quais participantes têm mais contribuições contestadas" (cruzando `contradictions` com `source_quote`/autor).
- **Como:** nova tool `analisar_tendencias()`, sem LLM — 3 `GROUP BY`/`COUNT` sobre tabelas já existentes (`requirement_versions`, `argumentation_questions`, `contradictions`), resultado como tabela + insight textual opcional.
- **Esforço:** 2-3 dias.

#### 6. Estimador de Risco por Requisito (proposta #3)
- **O quê:** score de risco por REQ cruzando: nº de contradições abertas envolvendo o REQ, nº de revisões (`requirement_versions`), presença de gateway BPMN relacionado (via `mapa_rastreabilidade`), e opcionalmente ambiguidade textual (reaproveitar heurística já usada em `analyze_requirement_quality`, se existir — confirmar antes de reinventar).
- **Como:** nova tool `estimar_risco_requisito(req_number)` ou em lote `estimar_risco_projeto()` — fórmula heurística ponderada (sem LLM, ou com LLM só pra explicar o score em texto).
- **Esforço:** 3-4 dias (a parte de calibrar os pesos da fórmula é a parte incerta, não o código em si).

**Onda 2 total: ~8-10 dias, 3 ferramentas novas.**

---

### 🥉 Onda 3 — Maior esforço, avaliar demanda antes de comprometer

#### 7. Importador de Planilha de Requisitos (proposta #9)
- **O quê:** upload `.xlsx` de requisitos legados → mapeia colunas → cria `REQ-XXX` com `source_quote` apontando pro arquivo → reconcilia com requisitos já existentes (evitar duplicata).
- **Por que Onda 3, não Onda 1:** `openpyxl` já é dependência (bom sinal), mas a parte difícil não é ler o Excel — é a UI de mapeamento de coluna (usuário precisa dizer "essa coluna é título, essa é prioridade") e a reconciliação com duplicatas (reaproveitar `cluster_similar_requirements`/`merge_requirements`, que já existem, mas ainda é lógica de produto não trivial).
- **Esforço:** 4-6 dias.

#### 8. Workflow de Aprovação — só a parte de UX conversacional, sem notificação (proposta #4, escopo reduzido)
- **O quê:** fluxo dedicado "solicitar revisão de um REQ" no chat (hoje `update_requirement_status` já muda pra `revised`/`rejected`, mas sem um prompt estruturado pedindo motivo/quem deve revisar). Recomendo **não** construir a parte de notificação por e-mail/Slack agora — não existe NENHUMA infra de notificação no projeto hoje (sem SMTP, sem webhook), seria uma integração nova inteira só pra essa feature.
- **Como:** tool `solicitar_revisao_requisito(req_number, motivo, revisor_sugerido)` — grava em `status_note` (campo já existe) + status `revised`; visibilidade via `sugestoes_plantonista`/`diagnostico_projeto` (que já resumem pendências) em vez de notificação ativa.
- **Esforço:** 1-2 dias (a versão sem notificação). Notificação real fica como iniciativa separada, condicionada a decidir canal (e-mail? Slack? só o Calendar que já existe?).

---

## Não recomendo construir agora

- **#2 Classificador de Maturidade** — baixa acionabilidade prática; se quiser, é mais barato adicionar 1 campo a `diagnostico_projeto` do que criar tool nova.
- **#5 ADR** — artefato de engenharia de software (decisão arquitetural técnica), público-alvo diferente do resto do produto (BA/PM/gestão, não devs); exigiria schema novo. Só justifica se houver pedido explícito de um cliente técnico.
- **#7 Jira/ADO** — escopo próprio, doc existente precisa reescrita contra a stack real antes de virar plano executável.
- **#10, #16, #18** — já existem sob outro nome; ação recomendada é **documentar melhor** (ex: `pages/Orientacoes_Assistente.py`), não codificar de novo.
- **#12 Tour Guiado** — não é um "tool" de assistente, é conteúdo de onboarding; mais barato como página estática nova em `Orientacoes_*` do que como ferramenta LLM.
- **#13, #14, #15** — mudança de arquitetura (cross-project), não melhoria pontual. Só entra em pauta se houver demanda de negócio por comparação entre projetos/clientes.

## Resumo executivo

- **18 propostas → 6 já existem (documentar, não codificar) → 3 fora de escopo por arquitetura → 9 valem construir**, das quais **3 são quick wins de ~1 semana total** (Onda 1) e mais 3 de esforço moderado (Onda 2, ~2 semanas).
- Recomendo começar pela Onda 1 inteira (Termo de Abertura .docx, Comparador de Atas, Verificador de Rastreabilidade) — menor risco, reaproveitamento máximo de código já testado em produção, entrega valor visível rápido.
