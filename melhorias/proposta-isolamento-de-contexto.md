# Proposta — Regra de Isolamento de Contexto de Primeira Classe (ENGINEERING_MANIFESTO)

> Redigida por Claude Code (Agente 1) por instrução do Agente 0 (arbitragem sobre
> `memory/reconciliacao_product_manifesto.md`, achado #7, Frente 3). **Este arquivo é uma
> proposta — nenhuma linha do `manifestos/ENGINEERING_MANIFESTO.md` foi alterada.** A
> incorporação (ou não) ao manifesto assinado é decisão exclusiva do Agente 0.
> Data: 2026-07-19.

---

## 1. Por que isto não é só mais um item de Fail-Open

`manifestos/PRODUCT_MANIFESTO.md §4` promete uma fronteira ética, não apenas técnica:

> *"Nunca vazar artefato não promovido de um contexto para outro (...) Vazamento aqui não é
> bug de qualidade — é quebra de confidencialidade entre silos."*

O `ENGINEERING_MANIFESTO.md §2` (Fail-Open) hoje trata **toda** falha do mesmo jeito: degradar
graciosamente, nunca bloquear o usuário. Isso é correto para indisponibilidade de serviço
externo ou validação opcional — mas aplicado sem distinção a um vazamento de isolamento
multi-tenant, o princípio produz o resultado errado: **um vazamento silencioso continuaria
"fail-open"** (a operação segue, o dado vaza, ninguém é bloqueado, nada aparece como erro).

O mecanismo que hoje garante essa fronteira **não é estrutural** — é disciplina manual:

- `service_role` do Supabase **bypassa RLS por design** (decisão de arquitetura já registrada
  no projeto, não um descuido) — não há barreira de banco de dados por trás.
- O isolamento real depende de cada função aplicar `.eq("project_id", ...)` corretamente. Um
  `.eq` esquecido não falha ruidosamente — a query simplesmente retorna dados de outro contexto,
  sem erro, sem exceção, sem log.
- Isto não é hipotético: a avaliação do PC189 (`melhorias/proposta-assistente-20261607.md`)
  **rejeitou** uma tool de SQL livre (`run_sql`) exatamente por este risco — LLM compondo SQL
  ad-hoc poderia vazar dados cross-project porque o isolamento não é imposto pelo banco.

**Conclusão proposta:** vazamento de isolamento de contexto deveria ser a **única classe de
falha que não faz fail-open**. Aqui o sistema deve **bloquear, logar como incidente de
segurança e notificar** — a exceção deliberada ao princípio do §2, no mesmo nível de
severidade hoje reservado à LGPD (§5).

---

## 2. Parágrafo proposto para `ENGINEERING_MANIFESTO.md`

*(Rascunho para incorporação futura — não aplicado. Numeração de seção sugerida: nova §5-bis
ou §12, à critério do Agente 0; segue o mesmo estilo/tom das seções existentes.)*

> ## X. Isolamento de Contexto — a Exceção ao Fail-Open
>
> **Esta é a exceção ao Fail-Open do §2: aqui o sistema bloqueia, não degrada.**
>
> **Definição:** todo artefato pertence a exatamente um contexto (`project_id`/`contexts`) até
> ser explicitamente promovido a Ativo de Negócio (atravessando para o domínio, `tenant_id`).
> Ler, escrever ou retornar um artefato de contexto diferente do solicitado — mesmo que dentro
> do mesmo domínio — é uma falha de **confidencialidade entre silos**, não uma falha de
> qualidade ou disponibilidade.
>
> **Regras mandatórias:**
> - Toda função de leitura/escrita com escopo de contexto **deve** filtrar por `project_id`
>   (ou `tenant_id`, quando a operação é explicitamente de domínio) — nunca confiar em RLS como
>   única barreira, já que `service_role` a *bypassa por design*.
> - Uma tool exposta ao Assistente (LLM) **nunca** deve compor a própria cláusula de
>   isolamento (ex.: SQL livre, filtro dinâmico via string) — o filtro de contexto é aplicado
>   pelo código Python que envolve a chamada, nunca delegado ao modelo. (Precedente: rejeição
>   de `run_sql` no PC189.)
> - Se uma falha de isolamento for detectada (ausência de filtro esperado, mismatch de
>   `project_id` entre o solicitado e o retornado), a operação deve **abortar** (não retornar
>   dado parcial), logar como incidente de segurança (`logger.error`, não `warning`), e
>   notificar o Agente 0 — nunca silenciar com fallback `[]`/`None` como o resto do Fail-Open.
> - Testes de regressão para funções que aceitam `project_id` devem incluir o caso "contexto
>   errado" (chamar com um `project_id` que não é o dono do dado) e afirmar retorno vazio, não
>   apenas o caso feliz.
>
> **Fora do escopo desta regra:** promoção deliberada a Ativo de Negócio (`PRODUCT_MANIFESTO
> §4`) — isso é o mecanismo de exceção intencional, não um vazamento.

---

## 3. Varredura Preliminar — Superfície de Risco (apenas listagem, nada corrigido)

Escopo: `core/project_store.py` + `core/tools/*.py`, ocorrências de `.eq("project_id", ...)`
usadas como mecanismo de isolamento manual. Não inclui outras formas de filtro (`.eq("tenant_id"`,
filtros compostos, RLS) nem outros diretórios — varredura focada, não exaustiva.

| Arquivo | Funções únicas | Ocorrências |
|---|---:|---:|
| `core/project_store.py` | 35 | 52 |
| `core/tools/tools_bpmn_sbvr.py` | 10 | 17 |
| `core/tools/tools_meetings_requirements.py` | 11 | 13 |
| `core/tools/tools_knowledge_requirements2.py` | 9 | 12 |
| `core/tools/tools_meeting_ops_calendar.py` | 6 | 12 |
| `core/tools/tools_executive_advanced.py` | 8 | 9 |
| `core/tools/tools_documents_ibis_diagrams.py` | 4 | 6 |
| `core/tools/tools_admin_charts_entities.py` | 5 | 5 |
| **Total** | **88 funções únicas** | **126 ocorrências** |

Amostra de funções por arquivo (lista completa disponível via
`grep -n '\.eq("project_id"' <arquivo>`):

- **`core/project_store.py`** (35): `_find_or_create_bpmn_process`, `get_asset_metadata_map`,
  `get_feedback_summary`, `get_project_roster`, `list_argumentation_by_project`,
  `list_assistant_artifacts_by_project`, `find_similar_existing_requirements`,
  `get_embedding_coverage`, `is_file_processed` (+ 26 outras).
- **`tools_bpmn_sbvr.py`** (10): `add_sbvr_rule`, `apply_text_correction`, `delete_meeting`,
  `preview_meeting_deletion`, `preview_text_correction`, `update_sbvr_rule`,
  `update_sbvr_term`, `update_sbvr_term_by_id`, `get_meeting_metadata`,
  `_get_fallback_meeting_id`.
- **`tools_meetings_requirements.py`** (11): `get_requirements`, `search_transcript`,
  `pesquisar_multi_contexto`, `estimar_risco_requisito`, `update_requirement_text`,
  `update_requirement_status`, `update_requirement_implementation`,
  `solicitar_revisao_requisito`, `_get_meetings`, `_requirements_for_meeting`, `_count`.
- **`tools_knowledge_requirements2.py`** (9): `diagnostico_projeto`, `sugestoes_plantonista`,
  `verificar_rastreabilidade_obrigatoria`, `analisar_tendencias`, `merge_requirements`,
  `diff_requirement`, `detect_requirement_contradictions`, `get_requirement_history`, `get_bmm`.
- **`tools_meeting_ops_calendar.py`** (6): `calculate_meeting_roi`, `generate_missing_minutes`,
  `reprocess_meeting_requirements`, `batch_reprocess_requirements`,
  `get_speaker_contributions`, `_del`.
- **`tools_executive_advanced.py`** (8): `gerar_deck_executivo`, `gerar_project_charter`,
  `mapa_rastreabilidade`, `simular_cenario`, `verificar_conformidade`, `vincular_regra_debate`,
  `reordenar_requisitos`, `sincronizar_calendario`.
- **`tools_documents_ibis_diagrams.py`** (4): `show_bpmn_diagram`, `render_requirements_table`,
  `_load_ibis_questions`, `_populate_knowledge_hub`.
- **`tools_admin_charts_entities.py`** (5): `get_database_integrity`,
  `fix_missing_llm_provider`, `generate_meeting_embeddings`, `generate_roi_chart`,
  `_requirements_with_meeting_numbers`.

**Leitura do dado:** 88 pontos de código diferentes hoje dependem de um desenvolvedor humano
(ou de uma IA implementando) lembrar de escrever `.eq("project_id", ...)` corretamente, sem
nenhum mecanismo que force isso estruturalmente (não há teste de regressão genérico que
verifique isolamento; RLS existe na tabela mas é ignorado pelo `service_role`). Isto **não**
significa que existam vazamentos hoje — não foi feita uma auditoria função-a-função nesta
rodada (fora de escopo: "listagem, não correção") — significa que a superfície onde um
vazamento *poderia* entrar despercebido é grande e cresce a cada tool nova.

---

## 4. Recomendação

Esta proposta não resolve nada por si — só torna a decisão possível. Ao Agente 0 cabe decidir:

1. Incorporar (ou adaptar) o parágrafo da seção 2 ao `ENGINEERING_MANIFESTO.md`, com bump de
   versão e registro de PC, conforme `manifestos/README.md §Regras de Versionamento`.
2. Decidir se/quando abrir uma iniciativa separada de **teste de isolamento genérico** (um
   helper de teste que, dado um `project_id` A e um B, chama a função com A e afirma que nada
   de B aparece no retorno) — não coberto por esta proposta, que é só a regra de governança.
3. Decidir se a varredura da seção 3 deve virar uma auditoria função-a-função de fato (ex.:
   um Explore agent revisando as 88 funções uma a uma) como iniciativa separada.
