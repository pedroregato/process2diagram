# Plano de POC — Validação de "Provocações" (domínio `p2d` / contexto `Projeto AURORA`)

> Escrito em 2026-08-01. Todos os dados de estado atual abaixo vêm de consulta **read-only** direta ao Supabase de produção (via `psycopg2`, `secrets.toml` local) feita na hora de montar este plano — não são suposição.

## 0. Por que esta POC, e por que agora

`AgentProvocations` foi construído e evoluído em 8 rodadas (PC190→PC207): 4 kinds ativos (`absence`, `asymmetry`, `premise`, `contradiction`), ligado por padrão desde PC205, com diagnóstico dedicado desde PC207. Mas em nenhuma dessas rodadas houve uma validação end-to-end contra um caso real com gabarito conhecido — o que existe hoje é (a) um roteiro de QA genérico e sintético (`pages/TesteProvocacoes.py`, admin-only) e (b) testes ad hoc contra o AURORA real que nunca fecharam o ciclo (a Reunião 5 foi desenhada e processada, mas ninguém confirmou o resultado). Esta POC fecha esse ciclo: prova, com um caso real e um gabarito explícito, que a feature entrega o que promete — ou documenta exatamente onde ela não entrega.

## 1. Estado atual verificado (2026-08-01, consulta direta ao banco)

| Item | Estado |
|---|---|
| Tenant `p2d` | Existe — `domain_slug='p2d'`, `display_name='Process ro Diagram'` (typo pré-existente no display_name, fora de escopo desta POC) |
| Contexto `Projeto AURORA` | Existe — `project_id=e41157b0-ac85-4080-b35e-8634704bff29`, sob o tenant `p2d` |
| Reuniões no contexto | 5 — R1 Kick-off, R2 Requisitos Técnicos/Core Banking, R3 Revisão de Conflitos/Riscos/Priorizações, R4 Aprovação de Orçamento, R5 Revisão de Sprint 3 (= `pocs/projeto-aurora/reuniao-05-revisao-integracao.txt`, processada em 2026-07-26 15:43) |
| `provocations` (tabela) | **0 linhas para o AURORA**, de qualquer kind |
| `llm_telemetry` — chamada do agente `provocations` | 2 registros para 2026-07-26 15:45 (mesmo minuto do processamento de R5), `is_error=False`, `skill_version='1.3'` — **o agente rodou com sucesso**, gerou resposta do DeepSeek, mas nada foi persistido em `provocations` |
| `llm_telemetry` — colunas PC207 | **Migration `setup/supabase_migration_llm_telemetry_pc207.sql` NÃO executada** — tabela real não tem `project_id`/`meeting_id`/`approved_count`/`rejected_count`/`rejected_reasons`. `get_provocations_diagnostics()`/`query_provocations_diagnostics()` estão fail-open, sempre "nenhum registro" |
| `kh_contradictions` (contexto AURORA) | 10 linhas, `status='open'` em todas. Nenhuma passa no filtro do bridge do PC200 hoje — ver achado abaixo |

### Achado novo: por que `contradiction` provavelmente não gerou nada

Das 10 linhas, a única com os dois `meeting_id` preenchidos e apontando pra R5 tem **`meeting_a_id == meeting_b_id` (a própria Reunião 5) em vez de `meeting_a_id=R3` (onde o SLA de 4h foi fechado)**. Isso falha no requisito de "cross-reunião real" do bridge determinístico (PC200), mesmo com `relation_type=contradiction_direct` e `severity=high` corretos. Hipótese: o detector de contradição encontrou as duas menções ao SLA (a antiga "que ficou definido na R3" e a nova "vamos ampliar para 8 horas") **dentro da própria fala de Ricardo em R5** — a transcrição de R5 relata verbalmente a decisão antiga em vez de o sistema linkar de volta ao fato originalmente registrado em R3. As outras 9 linhas têm `meeting_a_id`/`meeting_b_id`/`relation_type` nulos em pelo menos um campo — resíduo do bug do PC206 (Full Scan) ou de scans anteriores.

**Isto não é uma correção a fazer hoje** — é um achado que a Fase 0 da POC (abaixo) precisa investigar com instrumentação adequada antes de decidirmos se é bug ou comportamento esperado.

## 2. Objetivo

Provar — com evidência real, não sintética descartável — que as 4 kinds ativas de Provocações geram observação corretamente lastreada quando processam reuniões reais do contexto `Projeto AURORA`. Concretamente: **recall ≥1 provocação aprovada por kind, com citação verificável**, ou um diagnóstico preciso de por que não.

## 3. Escopo

**Dentro:** os 4 kinds ativos (`absence`, `asymmetry`, `premise`, `contradiction`), rodando contra as 5 reuniões reais do AURORA + 1 nova reunião a criar se necessário (ver Fase 2).
**Fora:** kind `analogy` (adiada, PC202) · Fase 6 do laço divergência→pauta, que a auditoria de hoje confirmou **não implementada** (`melhorias/parciais/agente-de-provocacoes.md`) — esta POC mede geração, não o ciclo até virar ação · qualquer correção de código como *side effect* automático — bugs achados na Fase 0 viram achado documentado, não patch aplicado sem sua aprovação explícita.

## 4. Pré-condições — resolver antes da Fase 1

- [ ] **Rodar `setup/supabase_migration_llm_telemetry_pc207.sql` em produção.** Sem isso, a Fase 0 (diagnóstico) fica cega — não dá pra saber se o validador rejeitou candidatos ou se o LLM não gerou nenhum.
- [ ] **Decidir o tratamento das 10 linhas antigas de `kh_contradictions`** antes de usá-las como base do teste de `contradiction`: (a) marcar como `resolved`/falso-positivo e confiar só em dado novo gerado nesta POC, ou (b) deixá-las como estão e tratar como ruído conhecido a ignorar na leitura dos resultados. Recomendo (a) — mantém a POC limpa de contaminar métricas com dado histórico quebrado.
- [ ] Confirmar que a chave de API do provider configurado (DeepSeek, per `llm_telemetry`) segue ativa/com saldo — cada reprocessamento é uma chamada real, paga.

## 5. Fase 0 — Diagnóstico instrumentado (por que R5 gerou zero)

1. Aplicar a migration PC207.
2. Rerun do agente único `provocations` para a Reunião 5 (não a reunião inteira — `core/rerun_handlers.py`/botão de rerun de agente).
3. Consultar `get_provocations_diagnostics(5)` pelo Assistente (ou `query_provocations_diagnostics()` direto) — agora deve responder `approved_count`/`rejected_count`/`rejected_reasons` reais.
4. Interpretar:
   - **`rejected_count > 0`**: os motivos dizem exatamente o que não bateu (marcador não encontrado, span de citação inválido, etc.) — vira item de achado, não de correção automática.
   - **`approved_count == 0` e `rejected_count == 0`**: o LLM não gerou nenhum candidato — hipótese diferente, prompt/skill não viu sinal suficiente no texto (menos provável dado que "é claro que" e "não precisa nem discutir" batem no `_PREMISE_MARKERS` — ver `agents/agent_provocations.py:57-65`).
5. Registrar o resultado bruto (JSON de `rejected_reasons`) neste diretório antes de seguir pra Fase 1.

## 6. Fase 1 — Gabarito por kind

| Kind | Onde | Sinal esperado | Status hoje |
|---|---|---|---|
| `contradiction` | R3 → R5 | SLA de resposta do MIB às integrações do Core Banking: 4h (R3) → 8h (R5) | Dado existe, mas bridge não encontra ligação limpa (achado §1) |
| `asymmetry` | R5, fala de Camila (~0:48) | "Mas se o SLA dobrar, isso não muda o tempo de resposta que prometemos pro comitê de crédito?" — Ricardo pivota pro Lex4All sem responder | Sinal presente na transcrição, resultado ainda não confirmado (0 salvo) |
| `premise` | R5, fala de Diego (~0:41) | "É claro que isso não vai impactar o cliente final... não precisa nem discutir isso com o Portal do Cliente" — nunca contestado | Sinal presente, bate no marcador `_PREMISE_MARKERS`, resultado ainda não confirmado (0 salvo) |
| `absence` | **a desenhar** | nenhuma das 5 reuniões reais tem um tema-alvo comprovadamente ausente e conhecido de antemão | Falta gabarito — ver opções abaixo |

### Opções para cobrir `absence`

- **(a) Recomendada — Reunião 6 controlada:** curta, plantando deliberadamente um tema nunca discutido nas 5 reuniões anteriores (ex.: continuidade/rollback do Motor de Risco em caso de falha, ou plano de resposta a incidente do MIB), dentro de um contexto que levantaria a expectativa natural de tocar nisso (ex.: reunião final de homologação). Dá controle total do gabarito — o que torna o `absence` mensurável de verdade.
- **(b) Auditoria manual de R1-R4 reais:** procurar um tema levantado numa reunião e nunca retomado nas seguintes. Mais "achado real", mas sem controle do gabarito e mais lento de verificar (exige ler as 4 transcrições reais na íntegra).

Recomendo (a): sem gabarito controlado, não dá pra distinguir "o sistema não achou porque não tem faro" de "o sistema não achou porque eu errei ao escolher o exemplo".

## 7. Fase 2 — Execução e verificação

1. (Se optar por 6(a)) Escrever a transcrição da Reunião 6, seguindo o mesmo padrão de `reuniao-05-revisao-integracao.txt` — vocabulário real do AURORA, sinal plantado explícito, salvar em `pocs/projeto-aurora/reuniao-06-<slug>.txt`.
2. Processar R6 no Pipeline real (domínio p2d, contexto Projeto AURORA), com "Gerar Provocações" ligado.
3. Para cada uma das reuniões relevantes (R5 e, se aplicável, R6), verificar em 3 camadas independentes:
   - **UI:** aba 🎭 Provocações em `pages/ArtefatosQualidade.py`.
   - **Assistente:** `get_provocations_diagnostics(meeting_number)`.
   - **Banco:** `select * from provocations where project_id='e41157b0-ac85-4080-b35e-8634704bff29'` (read-only, mesma via usada para levantar o estado atual deste plano).
4. Cruzar cada provocação aprovada contra a linha correspondente do gabarito (§6): a citação bate literalmente com timestamp+falante da transcrição? O `kind` é o esperado?

## 8. Critérios de sucesso

- **Recall:** pelo menos 1 provocação aprovada e correta por kind (4/4) — ou, se algum kind falhar, um `rejected_reasons` claro o suficiente pra virar um achado acionável (não "não sei por quê").
- **Grounding:** toda citação aprovada é verificável contra o texto real (sem paráfrase, sem invenção).
- **Sem falso-positivo grosseiro:** nenhuma provocação aprovada fora do gabarito sem justificativa plausível na leitura manual.
- **Taxa de rejeição registrada e entendida** — não precisa ser zero, precisa ser explicável.

## 9. Riscos e limitações conhecidas

- Ação em dado de produção real (contexto de um engajamento real, ainda que dentro do domínio interno `p2d`) — reprocessamentos devem ser deliberados, não repetidos "pra ver o que acontece".
- Custo real de LLM por chamada (pequeno, mas não nulo) — cada rerun de agente único gera 1 chamada real.
- Fase 6 do produto (provocação → item de pauta/divergência) não existe — esta POC não pode medir esse elo, só a geração.
- `analogy` permanece fora por decisão já tomada (PC202) — não faz parte do critério de sucesso.

## 10. Registro do resultado

Ao final, gravar `pocs/projeto-aurora/RESULTADO_POC_PROVOCACOES.md` — gabarito x resultado real, taxa de aprovação/rejeição por kind, achados de bug (se houver), e recomendação (feature validada / precisa ajuste / precisa mais dado).

---

## Fase 0 — Resultado do primeiro ciclo (2026-08-01)

**Executado:** migration PC207 aplicada e verificada em produção; rerun do agente único "Provocações" na Reunião 5, disparado pelo usuário na aplicação real.

**Resultado bruto (`provocations`, contexto AURORA):**

| Kind | Resultado |
|---|---|
| `absence` | ✅ **1 provocação salva** — "Testes e critérios de aceite não mencionados antes da homologação" (pergunta: "Quais testes e critérios de aceite ainda são esperados antes da homologação de 30/04?"), confiança média, lastro em termos ausentes (`teste`, `aceite`, `critério`...). **Não estava no gabarito original** — achado genuíno do sistema, não plantado por mim. Bom sinal: a feature encontrou algo real que eu mesmo não tinha antecipado ao desenhar o gabarito. |
| `asymmetry` | ❌ 0 salvas — motivo ainda desconhecido (ver achado de telemetria abaixo) |
| `premise` | ❌ 0 salvas — motivo ainda desconhecido (ver achado de telemetria abaixo) |
| `contradiction` | ❌ 0 salvas — **causa raiz confirmada analiticamente**, ver abaixo |

### Achado 1 (bug confirmado ao vivo, já conhecido): DeepSeek "conteúdo vazio" intermitente

Primeira tentativa de rerun (14:33:11) falhou com `is_error=True`, `error_message="LLM retornou conteúdo vazio (finish_reason='length'...)"`. Segunda tentativa (14:34:57) funcionou. Confirma em produção real o issue já registrado em memória (PC183 captura, mas não evita, o erro).

### Achado 2 (gap real de instrumentação, corrigido nesta sessão): rerun de agente único não gravava telemetria PC207 nem rodava a ponte de contradiction

`core/rerun_handlers.py`, branch `"provocations"` (linha 183), chamava só `AgentProvocations.run()` + `save_provocations()` — nunca chamava `record_provocations_outcome()` (telemetria PC207) nem `AgentProvocations.bridge_contradictions()` (ponte PC200). Ambas só existem dentro de `core/pipeline.py::run_provocations()`, que roda 1x no processamento original da reunião. Consequência prática: **`contradiction` é estruturalmente impossível de gerar via rerun de agente único** (só no processamento original ou via backfill dedicado), e `approved_count`/`rejected_count`/`rejected_reasons` continuavam `NULL` mesmo após a migration, porque o rerun nunca gravava esses campos.

**Fix aplicado** (autorizado por você): `core/rerun_handlers.py` agora chama `record_provocations_outcome()` também no rerun de agente único, mesmo padrão best-effort de `run_provocations()`. `py_compile` limpo. **Não adicionei a ponte de contradiction ao rerun** — o caminho correto pra isso continua sendo o backfill dedicado (`backfill_provocations_contradictions`, PC204), por design. **Ainda sem teste automatizado dedicado a este branch — pendência a registrar, não resolvida agora.**

### Achado 3 (causa raiz de `contradiction`=0, confirmada analiticamente): nenhuma linha de `kh_contradictions` do AURORA passa no filtro do bridge para a Reunião 5

Apliquei manualmente o filtro exato de `agents/agent_provocations.py::bridge_contradictions()` (linhas 430-475) contra as 10 linhas reais de `kh_contradictions` do projeto (`status='open'` em todas):

- **9 das 10** têm `meeting_a_id != R5` (ou `None`, ou apontam pra R3) — falham no requisito "só provoca na reunião em que foi detectada" (`meeting_a_id == meeting_id` da reunião sendo processada).
- **A única com `meeting_a_id == R5`** (id `ef5a6675-...`) tem `meeting_b_id == meeting_a_id` (a própria R5 nos dois lados) — falha no requisito "genuinamente cross-reunião" (`meeting_b != meeting_a`), mesmo com `relation_type=contradiction_direct` e `severity=high` corretos.

**Zero candidatos possíveis hoje, com certeza — não precisei rodar o backfill de fato** (tentei; a chave do Supabase local não tem permissão de leitura via REST/PostgREST para `list_meetings()` — limitação de ambiente já conhecida de sessão anterior, não um bug novo). A causa raiz real parece estar em como `agents/agent_contradiction_detector.py` atribui `meeting_a_id`/`meeting_b_id` ao gravar — a linha que deveria representar "R3 decidiu 4h, R5 mudou pra 8h" nunca ficou com `meeting_a_id=R5` (a reunião onde a mudança foi dita) e `meeting_b_id=R3` (a reunião original) simultaneamente corretos. **Isto é uma hipótese de causa raiz, não uma correção — precisa de investigação dedicada em `agent_contradiction_detector.py`, fora do escopo desta POC até decisão explícita.**

### Achado 4 (saga de infraestrutura): mesmo com o Achado 2 corrigido e deployado, a telemetria continuou NULL por várias rodadas — causa real era processo do Streamlit Cloud com código obsoleto, não Supabase

Depois do fix do Achado 2 (commit `6c7747c`), vários reruns seguidos continuaram com `project_id`/`meeting_id`/`approved_count` etc. todos `NULL`, mesmo após: migration confirmada, `NOTIFY pgrst, 'reload schema'`, resave de "Exposed schemas" no painel, e um **restart completo do projeto Supabase**. Testei um INSERT bruto via SQL direto com os mesmos valores exatos (funcionou, descartando FK/tipo/schema), conferi grants por coluna (OK) e RLS (0 políticas, mas isso bloquearia até as escritas normais de telemetria, que claramente funcionam — descartado). Achado real: eu tinha confundido o evento `record_validation()` (PC183, sempre `provider=""`, nunca popula os campos novos, mecanismo diferente e não relacionado) com o evento do meu fix — `record_provocations_outcome()` nunca produzia linha NENHUMA, nem com nulls. A causa real era um **pitfall já documentado no `CLAUDE.md`**: `.pyc`/processo obsoleto no Streamlit Cloud — o deploy mostrava o commit certo e "sem erro", mas o processo Python em memória ainda rodava o módulo antigo. Só um **reboot explícito do app** (não só aguardar o auto-deploy) resolveu — a telemetria passou a popular corretamente a partir daí.

### Achado 5 (causa raiz real de `asymmetry`/`premise` = 0, CORRIGIDA — commit `de7b5bb`)

Com a telemetria finalmente funcionando, o primeiro diagnóstico real veio: `rejected_reasons: {"span_unresolved": 1}`. Investigação: `agents/agent_provocations.py::_TEAMS_SPEAKER_LINE` reusava `_SPEAKER_LINE_PAT` (`modules/transcript_preprocessor.py`), que exige 2+ espaços entre nome e timestamp — desenhada pro texto BRUTO. `hub.transcript_clean` (o que `AgentProvocations` de fato recebe) já passou pela limpeza final do preprocessador, que colapsa qualquer sequência de 2+ espaços em 1 — inclusive essa. Confirmado direto no banco: a regex antiga achava **0 turnos** no `transcript_clean` real da Reunião 5 (deveria achar 10) → `_span_text()` sempre `None` → todo `asymmetry` que dependesse de span reprovado com `span_unresolved`. **Bug sistêmico**, não específico da R5 — a limpeza roda em toda transcrição do pipeline normal, então isso provavelmente afetava `asymmetry` (e parte do `premise`, mesma `_turn_positions()`) desde o PC190/PC201, silenciosamente (fail-closed nunca aprova por omissão, então nunca virou falso-positivo visível). Fix: `_TEAMS_SPEAKER_LINE` ganhou seu próprio pattern (`\s+` em vez de `\s{2,}`), sem tocar `_SPEAKER_LINE_PAT` original. 2 testes de regressão novos, suíte completa 1010/1010.

**Resultado depois do fix + reboot:** rerun seguinte aprovou `asymmetry` pela primeira vez — "Objeção sobre impacto no comitê de crédito não respondida", confiança **alta**, citando literalmente a fala da Camila (00:00:48) e o fechamento da Fernanda (00:01:09), exatamente o par previsto no gabarito (§6). `premise` foi proposto mas rejeitado (`premise_marker_missing`) — ainda não confirmado se é bug ou rejeição legítima (candidato pode não ter sido a fala do Diego).

### Estado depois deste ciclo

- `absence`: **validado** — 3 variações geradas, todas lastreadas.
- `asymmetry`: **validado** — aprovado com confiança alta, bate exatamente no gabarito.
- `premise`: **pendente** — 1 tentativa rejeitada (`premise_marker_missing`), não confirmado se é bug real ou rejeição correta de um candidato fraco.
- `contradiction`: **diagnosticado, não corrigido** — bloqueado por dado quebrado em `kh_contradictions` (achado 3), causa raiz em `agent_contradiction_detector.py`, fora do escopo até decisão explícita.

## Próxima ação — decisões que dependem de você

~~1. Autorizar rodar a migration PC207 em produção~~ — ✅ feito.
~~2. Escolher (a) ou (b) para o gabarito de `absence`~~ — resolvido sozinho: R5 já gerou um `absence` real sem precisar de Reunião 6.
~~4. Autorizar o reprocessamento real de R5~~ — ✅ feito, resultado no diagnóstico acima.

Restam, agora com mais contexto do que quando este plano foi escrito:

1. **Rodar um novo rerun de "Provocações" na Reunião 5**, agora que o fix do Achado 2 está aplicado — é o único jeito de saber se `asymmetry`/`premise` estão sendo propostos e rejeitados (e por quê) ou nunca propostos. Custa 1 chamada LLM real, você precisa disparar na aplicação (mesmo passo de antes).
2. **Decidir se investigamos `agent_contradiction_detector.py`** (Achado 3 — por que a linha R3→R5 nunca fica com `meeting_a_id`/`meeting_b_id` corretos) agora, ou se isso vira um item separado depois de fechar `absence`/`asymmetry`/`premise` primeiro. É uma investigação de causa raiz, não um fix de 5 minutos como o Achado 2.
3. As 10 linhas antigas de `kh_contradictions` — dado o Achado 3, provavelmente nenhuma delas está "certa" mesmo depois de qualquer fix futuro (foram gravadas com a lógica antiga). Decisão de limpeza fica pra quando o Achado 3 for resolvido, não antes.
