# Reconciliação — PRODUCT_MANIFESTO.md × Manifestos Vigentes

> Auditoria de contradições solicitada por `melhorias/contexto-de-produto.md` (TAREFA 2).
> Escopo original: **detectar e reportar, não corrigir.**
> Autor: Claude Code (Agente 1). Data: 2026-07-19.
>
> **Atualização (PC195, mesma data):** o Agente 0 revisou este relatório e autorizou 2 dos
> itens de baixo risco listados abaixo — **aplicados**: (1) `COLLABORATIVE_MANIFESTO.md §5.3`
> corrigido de 1:1 para 1:N (v5.11→v5.12); (2) `manifestos/README.md` ganhou
> `PRODUCT_MANIFESTO.md` no mapa e na ordem de leitura (status v0.1/rascunho preservado,
> **não** tratado como ratificado). A ratificação do `PRODUCT_MANIFESTO` em si, a rodada de
> renomeação global e o item de isolamento multi-tenant no `ENGINEERING_MANIFESTO` (achados #7
> e §4 da recomendação) seguem pendentes, fora de escopo desta rodada.

---

## 0. Nota de leitura prévia

`manifestos/PRODUCT_MANIFESTO.md` foi lido na íntegra antes desta auditoria. Postura adotada:
decisão de *produto* (o que gerar, persistir, priorizar, nomear, integrar) consulta este
documento primeiro; decisão de *implementação* continua no `ENGINEERING_MANIFESTO`. A tese —
reunião como ativo, artefatos como espelhos não-gateados, duas memórias (contexto automático /
domínio por promoção), regra do lastro em código, Vichāra como única superfície com nome
próprio, cautela contra convergência prematura — está absorvida.

Achado geral, antes de entrar nos atritos: **este manifesto descreve, em boa parte, arquitetura
que já existe em produção** (PC164-168 Ativos de Negócio, PC190 AgentProvocations, PC01/07
identidade Vichāra). Não é uma tese aspiracional isolada do código — é, em grande medida, uma
nomeação retroativa e uma formalização ética do que a engenharia já vinha construindo. Isso
reduz a superfície real de atrito a poucos pontos concretos, listados abaixo.

---

## 1. Tabela de Atritos

| # | Tipo | Arquivo:linha | Trecho conflitante | Trecho do PRODUCT_MANIFESTO | Recomendação |
|---|---|---|---|---|---|
| 1 | **PREMISSA** | `manifestos/COLLABORATIVE_MANIFESTO.md:151` (§5.3 "Segregação de Dados") | "Cada cliente = projeto isolado no P2D" — afirma uma relação **1:1** entre cliente e projeto/contexto | §4: "domínio" (`tenant_id`) e "contexto" (`contexts`/`project_id`) são conceitos distintos; um domínio contém **N** contextos (ex. FGV → SDEA, Projeto Aurora). Confirmado em código: `list_all_business_assets_for_domain(tenant_id)` chama `list_contexts(tenant_id)` (PC165, `CLAUDE.md:489`) — relação **1:N** | A frase é uma correção de precisão, não uma reformulação de arquitetura: **1 cliente/domínio pode isolar N projetos/contextos**. É factualmente desatualizada desde PC165 (09/07), que já implementou o Catálogo do Domínio cross-contexto — a imprecisão é anterior ao PRODUCT_MANIFESTO, só ficou visível agora. Sugiro reescrever a linha 151 na próxima revisão de versão do COLLABORATIVE_MANIFESTO (bump de versão, registrar PC). |
| 2 | **TERMINOLÓGICO** (correção de citação) | — | A pista do `contexto-de-produto.md` atribui a frase acima a **`ENGINEERING_MANIFESTO §5.3`** | — | `ENGINEERING_MANIFESTO.md` não contém a frase nem tem uma seção 5 sobre segregação multi-tenant (seu §5 é "LGPD — Camada de Conformidade", tema adjacente mas distinto). A localização real é `COLLABORATIVE_MANIFESTO.md §5.3`. Recomendo corrigir a citação ao arbitrar. |
| 3 | **TERMINOLÓGICO** (maior superfície) | `agents/agent_assistant.py:521` — `═══ PROJETO: {project_name} ═══` (injetado em **todo** system prompt de Vichāra, ou seja, em toda conversa real com o usuário) | Uso de "PROJETO" onde o produto diz "contexto" — este é o ponto de maior visibilidade externa (é literalmente o que o LLM lê antes de cada resposta) | §4: "O termo `projeto` é herança; o produto diz **contexto**" | Não renomear agora (fora do escopo aditivo). Registrar como o item #1 de prioridade se/quando a rodada de renomeação for aberta — é o ponto onde a inconsistência de vocabulário tem mais chance de vazar para a fala do próprio Vichāra. |
| 4 | **TERMINOLÓGICO** (superfície ampla, código) | 100 arquivos `.py` (fora `.venv`), 1471 ocorrências de `project_id`; 34 arquivos com `active_project_id`/`active_project_name`/`require_active_project()`; 28 arquivos `.sql` em `setup/` com coluna/FK `project_id` | Nome de parâmetro/símbolo em praticamente toda função pública de `core/project_store.py`, `core/tools/*.py`, `ui/project_selector.py` | §4, §9: "contexto" é o termo de produto; renomeação global (`project_id`→`context_id`) é "refatoração de risco" que **não deve ser executada sem inventário prévio e arbitragem do Agente 0" | Este relatório **é** o inventário preliminar pedido — ver §3 abaixo. Nenhuma ação de código nesta tarefa. |
| 5 | **TERMINOLÓGICO** (naming do produto) | Nome do repositório GitHub (`pedroregato/process2diagram`), título/`Project Overview` de `CLAUDE.md`, footer/watermark de páginas ao vivo (v5.15), domínio de deploy Streamlit Cloud — 28 arquivos `.py`/`.md` mencionam "process2diagram"/"P2D" | Nome do produto ainda é "Process2Diagram"/"P2D" em toda infraestrutura viva | §5, §9: "*Vichāra* é a tese, a alma e o nome que vem"; "P2D" nomeia uma saída (diagrama), erro de categoria | §9 já classifica isto como "etiqueta histórica" e explicitamente veta execução sem arbitragem — nenhuma ação recomendada além de inventariar (feito, ver §3). Nota: mudar o nome do repositório GitHub tem custo de infraestrutura real (URLs de deploy, links já publicados) — maior que um rename de símbolo Python. |
| 6 | **LACUNA** | `manifestos/README.md:13-17` (Mapa dos Manifestos) e `:33-41` (Ordem de Leitura) | Não mencionam `PRODUCT_MANIFESTO.md` | §10: ao ratificar, o Agente 0 deve "adicionar este arquivo à ordem de leitura obrigatória do README.md" | Esperado — o próprio documento já prescreve essa atualização como parte do rito de ratificação, condicionada à assinatura (ainda pendente). Não é uma omissão a corrigir agora; é passo 3 da ratificação. |
| 7 | **LACUNA** | `manifestos/ENGINEERING_MANIFESTO.md` (nenhuma seção equivalente) | Fail-Open (§2) trata toda falha externa como "degradar graciosamente, nunca bloquear" — não distingue severidade | §4: "Nunca vazar artefato não promovido de um contexto para outro (...) não é bug de qualidade — é quebra de confidencialidade entre silos" | O `ENGINEERING_MANIFESTO` não tem hoje uma regra que eleve vazamento de isolamento multi-tenant a um patamar de severidade diferente de uma falha comum de Fail-Open. Achado agravante: a arquitetura real depende de disciplina manual (`.eq("project_id", ...)` em cada tool; `service_role` do Supabase **bypassa RLS por design** — achado já registrado na avaliação do PC189, que rejeitou uma tool de SQL livre por este exato risco). Recomendo, numa futura revisão do ENGINEERING_MANIFESTO, formalizar isolamento de contexto como regra de primeira classe (paralela a LGPD §5), não apenas herdada implicitamente do Fail-Open. |
| 8 | **LACUNA** (modelo de negócio) | `manifestos/COLLABORATIVE_MANIFESTO.md §7` (planos Starter/Pro/Enterprise, cap de "reuniões" por cliente) | Unidade de cobrança = "cliente", sem menção a contexto | §4: um domínio (cliente) pode ter N contextos, cada um gerando reuniões | Pré-existe a este manifesto (o modelo de negócio foi assinado em 30/06, antes do Catálogo do Domínio de 09/07). Fica ambíguo se o cap de reuniões do plano é por domínio (agregando todos os contextos do cliente) ou faria sentido por contexto. Decisão de produto/comercial — fora do escopo desta auditoria terminológica, mas registrado para o Agente 0 avaliar quando for oportuno. |

---

## 2. Itens "sem contradição, esclarecido"

- **VETO a provedores premium** (`COLLABORATIVE_MANIFESTO §6`) — já auto-resolvido no próprio
  `PRODUCT_MANIFESTO §7` (nota comercial explícita: VETO governa o LLM de runtime/custo; o
  manifesto de produto governa a tese). Confirmado, sem tensão real.
- **Mapeamento domínio=`tenant_id` / contexto=`contexts`/`project_id`** (`PRODUCT_MANIFESTO §4`)
  — já é a arquitetura real desde PC164/165: `list_all_business_assets_for_domain(tenant_id)`,
  `list_contexts(tenant_id)`, toggle "📁 Este contexto / 🌐 Catálogo do Domínio" em
  `pages/AtivosDeNegocio.py` (já documentado com a palavra "Contexto" em `CLAUDE.md:52`, antes
  mesmo deste manifesto). O manifesto nomeia o que o código já fazia.
- **Persistência automática vs. promoção deliberada** (`PRODUCT_MANIFESTO §4`) — é exatamente a
  arquitetura de Ativos de Negócio (PC166 Promoção Explícita): todo artefato persiste por
  padrão no contexto; só o promovido atravessa a fronteira para o domínio.
- **Artefatos como espelhos, sem gating por tipo de reunião** (`PRODUCT_MANIFESTO §3`) — o
  sistema ROI-TR (`pages/MeetingROI.py`, `TYPE_WEIGHTS`) pondera a relevância de um artefato por
  tipo de reunião na **pontuação**, mas nunca impede a geração do artefato em si — é "sinal de
  ordenação/sugestão", nunca "portão", exatamente como o manifesto prescreve.
- **Nome "Vichāra" para o assistente** (`PRODUCT_MANIFESTO §5.1`) — já implementado em código
  desde 2026-07-01 (commits `3edc236`, `89632d3`, *"identidade Vichāra no system prompt"*),
  quase 3 semanas antes deste manifesto existir como arquivo. O manifesto formaliza e explica a
  *razão* de uma decisão que a engenharia já tinha tomado — não introduz nada novo aqui.
- **Regra do lastro / validação em código, não em prompt** (`PRODUCT_MANIFESTO §5.2`) — é
  exatamente o padrão do PC190 (`AgentProvocations._validate_and_rank()`, validador
  determinístico que a LLM não pode contornar) e ecoa o princípio geral de PC83/84 do
  `ENGINEERING_MANIFESTO §6`. A citação da doutrina do rishi já está, literalmente, em
  `skills/skill_provocations.md` desde o PC190.
- **Cautela contra convergência prematura** (`PRODUCT_MANIFESTO §5.3`) — sem contrapartida em
  código ainda (não há hoje uma feature que "acelere consenso"), logo sem contradição — é uma
  diretriz preventiva para decisões futuras, não uma correção de algo existente.

---

## 3. Inventário Preliminar — Renomeação Global (apenas listagem, nada executado)

| Escopo | Extensão medida | Observação |
|---|---|---|
| `project_id` (símbolo/parâmetro) | 1471 ocorrências em 100 arquivos `.py` (fora `.venv`) | Concentrado em `core/project_store.py`, `core/tools/*.py`, `ui/project_selector.py` |
| `active_project_id` / `active_project_name` / `require_active_project()` | 34 arquivos | Session state global (`st.session_state`) — usado por toda página de análise |
| `project_id` como coluna/FK | 28 arquivos `.sql` em `setup/` | Toda migration teria de ser reavaliada (rename de coluna é mudança de schema, não só de código) |
| "process2diagram" / "P2D" (texto) | 28 arquivos `.py`/`.md` | Inclui nome do repositório GitHub, título do `CLAUDE.md`, footer/watermark ao vivo, README |
| `{project_name}` no system prompt de Vichāra | `agents/agent_assistant.py` (linhas 418, 516, 521, 850, 855, 978, 1013, 1409, 1427, 1442) | Maior visibilidade externa — string literalmente lida pelo LLM a cada conversa |

**Não incluído neste inventário** (fora do escopo desta auditoria, exigiria varredura própria):
nomes de tabelas Supabase além de `project_id` (ex.: eventual tabela `projects` vs. `contexts` —
já existe `contexts` real, então pode já não haver conflito aqui — não verificado a fundo),
strings em `pages/*.py` voltadas ao usuário final fora do prompt de Vichāra, nomes de variáveis
locais dentro de funções (baixo risco, alto volume).

---

## 4. Recomendação de Ordem de Ratificação (para o Agente 0)

1. **Ratificar `PRODUCT_MANIFESTO.md` v1.0 isoladamente primeiro** — ele é aditivo por design;
   nenhum item da tabela de atritos acima bloqueia sua ratificação.
2. **Corrigir a citação errada** (`ENGINEERING_MANIFESTO §5.3` → `COLLABORATIVE_MANIFESTO §5.3`)
   e **atualizar a linha 151** do `COLLABORATIVE_MANIFESTO` para refletir a relação 1:N
   domínio→contexto — patch textual pequeno, não é a renomeação global, bump de versão menor.
3. **Atualizar `manifestos/README.md`** (mapa + ordem de leitura) — mecânico, já prescrito pelo
   próprio `PRODUCT_MANIFESTO §10` como parte do rito de ratificação.
4. **(Opcional, revisão futura do `ENGINEERING_MANIFESTO`)** formalizar isolamento de contexto
   como regra de primeira classe, à luz do achado #7 acima.
5. **Só depois, como iniciativa separada e explicitamente arbitrada**: avaliar se/quando abrir a
   rodada de renomeação global (`project_id`→`context_id`, "P2D"→"Vichara"). Grande, arriscado,
   deliberadamente fora do escopo aditivo deste manifesto — item 3 acima é o ponto de partida
   caso essa decisão seja tomada.

---

**Fim do relatório.** Aguardando arbitragem do Engenheiro Humano (Agente 0). Nenhuma correção foi
executada — nem nos manifestos, nem no código, conforme a Regra de Ouro de Edição
(`manifestos/README.md`, "Regra de Ouro de Edição").
