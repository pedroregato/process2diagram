# Plano de Melhorias — Vichāra

> **Data:** 2026-09-28 · **Autor:** Pedro Gentil (com Claude)
> **Base:** README e `melhorias/MANIFESTO_MELHORIAS.md` do `process2diagram` (v5.15, PC218) e o levantamento de recursos do Kaggle Data Hub feito nesta sessão.
> **Princípio (herdado do Text Intelligence Lab):** *toda complexidade adicional deve ser justificada por evidência.* O plano, portanto, começa por instrumentos de medição e só depois propõe otimizações.
> **Plano irmão:** [`docs/plano-melhorias-til.md`](https://github.com/pedroregato/text-intelligence-lab/blob/main/docs/plano-melhorias-til.md) no repositório `text-intelligence-lab` (Text Intelligence Lab).

---

## 0. Diagnóstico

| | Vichāra (process2diagram) |
|---|---|
| **Maturidade** | Produto em produção, multi-tenant, 1060 testes, ~40 páginas, 5 providers LLM |
| **Força** | Governança de propostas (manifesto com 71 itens auditados), auto-repair determinístico, telemetria LLM |
| **Lacuna principal** | **Não há conjunto de avaliação com gabarito externo** — a qualidade é medida por scorers internos (`AgentValidator`, grade A–E), sem ground truth |
| **Risco aberto** | Guard de isolamento de contexto não implementado (bloqueia a renomeação global) |

**Tese do plano:** o TIL já sabe *medir*; o Vichāra já sabe *fazer*. A maior alavanca é transferir o método de evidência do TIL para o Vichāra, e usar o Vichāra como caso real do TIL.

---

## 1. Onda 1 — Segurança e medição (fazer primeiro)

### V1 · Guard de isolamento de contexto — 🔴 Prioridade máxima
- **Situação:** `proposta-isolamento-de-contexto.md` está em `parciais/`. A auditoria (A1–A3) e `tests/test_context_isolation.py` **provaram vazamento real** em funções sem validação de `project_id`. O NAV-01 corrigiu o vazamento entre tenants em `list_contexts`, mas o guard geral (`_scoped_select` / `ContextIsolationError`) não existe.
- **Por que agora:** é o único item do manifesto com vazamento comprovado, e ele trava a Fase C da renomeação global (`adiadas/`).
- **Entregáveis:**
  1. Registrar no `ENGINEERING_MANIFESTO.md` a exceção ao Fail-Open: *isolamento falha fechado*.
  2. Implementar `_scoped_select(table, context_id, …)` em `core/project_store.py` e migrar as funções apontadas pela auditoria.
  3. Fazer os testes de `test_context_isolation.py` passarem de "provam vazamento" para "provam bloqueio".
- **Relacionado:** a preocupação já registrada de que o cache por hash depende só da sanitização de PII como fronteira de segurança. Incluir `context_id` na chave do cache no mesmo PC.

### V2 · Eval harness com gabarito externo — 🔴 Alta
- **Problema:** hoje não dá para responder "a v5.16 extrai decisões melhor que a v5.15?" com um número.
- **Recursos do Kaggle (licenças verificadas):**
  - **[Teams Meeting Transcripts](https://www.kaggle.com/datasets/yusufayta/teams-meeting-transcripts)** (MIT): trechos com *action items* e *decisões* rotulados, mais responsável, prazo e prioridade. É o gabarito direto para `AgentMinutes`.
  - **[Structured Output Benchmark](https://www.kaggle.com/datasets/interfazeai/structured-output-benchmark)** (CC BY-SA 4.0): fatia `audio` com 115 tarefas sobre o **AMI Meeting Corpus**, cada uma com JSON Schema e resposta de referência avaliada por valor. É o gabarito para a extração tipada.
- **Entregáveis:**
  1. `evals/` com `datasets/` (snapshot versionado + licença), `runners/` (sem Streamlit, chama os agentes direto) e `reports/`.
  2. Métricas: precisão/recall de action items e decisões (match por similaridade + responsável), acurácia por valor no SOB, custo e latência (reaproveitando `services/llm_telemetry.py`).
  3. Um CSV de evidência no mesmo formato do TIL (`evidence_status`, hardware, versões, proveniência).
  4. Execução obrigatória antes de todo PC que mexa em skills de extração.
- **Limitação a registrar:** os dois datasets estão em inglês (o Teams tem também turco). Para PT-BR, montar um **gold set interno pequeno** (20–30 trechos anonimizados de reuniões reais) — nenhum dataset aberto em PT-BR encontrado serve para isso sem restrição de licença.
- **Efeito colateral:** reabre com os nomes reais a proposta `backlog/pipeline-metrics.md` (que o manifesto marcou como especulativa). O `pipeline_metrics` passa a ser alimentado pelo harness e pela telemetria real, não por um módulo inexistente.

### V3 · Qualidade BPMN comparada com diagramas reais — 🟠 Média
- **Recurso:** **[Camunda's BPMN 2.0 Exploratory Dataset](https://www.kaggle.com/datasets/andreykopp/camundas-bpmn-2-0-exploratory-dataset)** (MIT): métricas de mais de 3,7 mil BPMNs reais (TNN, TNSF, gateways, eventos…), baseadas em Sánchez-González et al. (2012).
- **Entregáveis:** calcular as mesmas métricas nos BPMNs gerados pelo Vichāra, comparar as distribuições e sinalizar diagramas fora da faixa típica (por exemplo, densidade de gateways acima do percentil 95). Isso vira um critério adicional no `AgentValidator` e no badge de qualidade.
- **Não fazer:** treinar modelo com esses dados. O uso é só como régua de referência.

---

## 2. Onda 2 — Economia guiada por evidência

### V4 · Cascade/routing medido (aplicar o EDU-ORCH-002 ao Vichāra) — 🟠 Média
- **Situação:** o `Plano_Economia_Arquitetura` (parcial) deixou pendente `n_bpmn_runs` adaptativo (hoje fixo em 3), early exit em transcrição nota E e seleção de agentes por `meeting_type`. O `plano-acao-deepseek-avancado` deixou pendente o roteamento thinking/non-thinking.
- **Proposta:** tratar esses quatro itens como **um único experimento de routing**, no molde do EDU-ORCH-002 do TIL:
  - Variável de roteamento: grade A–E do `AgentTranscriptQuality` e/ou score do `AgentValidator` no 1º passe.
  - Matriz de testes: {1, 3, 5 passes} × {thinking, non-thinking} × {thresholds de grade}.
  - Métricas: score de qualidade (V2 + V3), custo, latência e escalation rate.
- **Critério de aceite:** só adotar a política se houver economia de pelo menos X% com queda de qualidade dentro do intervalo de ruído medido. O valor de X fica a definir depois da primeira rodada.

### V5 · Fechar o laço das provocações (Fase 6) — 🟠 Média
- **Situação:** 4 dos 5 tipos de provocação estão em produção, mas o destino (`became_divergence` → item de pauta ou livro-razão de divergências) está desligado. O próprio documento chama esse laço de "a tese inteira do produto".
- **Entregáveis:** ação "Aceitar provocação" que cria um item de pauta ou divergência; contador no `pipeline_metrics` (provocações aceitas / geradas); feedback 👍/👎 reaproveitando `ui/components/artifact_feedback.py`.
- **Por que importa:** é a métrica mais direta de *melhoria da qualidade da deliberação*, que é a proposta de valor do Vichāra.

---

## 3. Onda 3 — Produto e operação

| ID | Item | Origem | Nota |
|---|---|---|---|
| V6 | NAV-09: paginação das 5 páginas pesadas | `parciais/navegabilidade.md` | Padrão já provado duas vezes (PC178/PC212) |
| V7 | NAV-06: reorganização do menu | idem | Maior risco da onda. Fazer depois do V6, com teste de ícones e rotas |
| V8 | Limpeza de `user_sessions` expiradas | PC214 (fora de escopo) | Job simples ou `pg_cron` no Supabase |
| V9 | Teste manual do timing do cookie pós-deploy | PC214 (não verificado) | Checklist de 5 minutos |
| V10 | Bug `route_y` / `boundary_y` em `_route_waypoints()` | `parciais/inspecao-bpmn.md` | Bug conhecido e ainda aberto. Barato de fechar |
| V11 | Múltiplos End Events por resultado de negócio | `parciais/bpmn-comparativa-001.md` | Medir impacto com o V3 antes de implementar |

---

## 4. Pesquisa (sem compromisso de entrega)

- **V12 · Métricas de deliberação sem conteúdo.** Inspirado no **[Hermion QMSum Interaction Dynamics](https://www.kaggle.com/datasets/marioegie/hermion-qmsum-interaction-dynamics)** (CC BY 4.0), que calcula a dinâmica de interação de equipes sem ler as falas. Hipótese: parte dos indicadores (distribuição de turnos, dominância, tempo até a decisão) pode ser calculada **antes** da sanitização de PII e **sem enviar texto ao LLM**. Isso daria um modo de baixo custo e alta privacidade, útil para clientes como FGV e DTI.
- **V13 · Reconciliar o "modo ao vivo".** O manifesto registra que o módulo Live Transcription (Extractor/Synthesizer, `session_events`) **não existe no código principal**, mas houve um protótipo com `schema_session_events.sql` e UI com auto-refresh. Ação: decidir se o protótipo vira branch/PC formal ou se é arquivado, e registrar a decisão no manifesto.

## 5. Não fazer (decisões registradas)
- **Não** usar o *Portuguese Spontaneous Dialogue Speech* (Nexdata): a licença é CC BY-**NC** e o arquivo é só uma amostra de um produto pago.
- **Não** reabrir o cache semântico enquanto o V2 não mostrar taxa de acerto do cache exato. A decisão do PC185 continua válida.

---

## 6. Sinergias com o Text Intelligence Lab

```
TIL (método)                               Vichāra (produto)
─────────────────────────────              ─────────────────────────────
ADR / evidence CSV / headless   ───────▶   V2 eval harness no mesmo formato
EDU-ORCH-002 (cascade medido)   ───────▶   V4 routing de passes BPMN / thinking
T5 GPU preflight                ───────▶   notebooks Kaggle do Vichāra
                                ◀───────   Caso real para o capstone (T7)
                                ◀───────   llm_telemetry / PII como material das Aulas 19 e 22
```

Recursos compartilhados: **Teams Meeting Transcripts** (V2 + T7 do TIL), **SOB** (V2 + T6 do TIL).

---

## 7. Roadmap

| Onda | Itens | Critério de saída |
|---|---|---|
| **1 — Base** | V1 isolamento · V2 eval harness | Zero vazamento nos testes de isolamento; primeiro CSV de evidência do Vichāra |
| **2 — Evidência** | V3 BPMN vs. Camunda · V4 routing · V5 provocações | Política de routing adotada ou descartada **com número** |
| **3 — Expansão** | V6–V11 (NAV e BPMN) | Onda 2 do NAV fechada |
| **Pesquisa** | V12 métricas sem conteúdo · V13 modo ao vivo | Decisão registrada no manifesto |

**Registro:** cada item vira proposta em `melhorias/backlog/` e ganha linha no `MANIFESTO_MELHORIAS.md`.

---

## 8. Premissas e riscos

- **Premissa:** o estado do código é o descrito no README e no manifesto em 2026-09-28. Itens podem ter avançado localmente sem push.
- **Idioma:** os gabaritos abertos encontrados estão em inglês. O desempenho em PT-BR exige o gold set interno do V2, e essa é a maior limitação deste plano.
- **Qualidade dos datasets do Kaggle:** vários têm notas de usabilidade baixas ou são sintéticos. Todos os recomendados aqui tiveram a licença conferida na página do dataset, mas o conteúdo deve ser inspecionado antes de entrar em avaliação oficial.
- **Custo de LLM do V2 e do V4:** a matriz de experimentos multiplica chamadas. Rodar primeiro com amostra pequena, usando o Estimador de Custo do próprio Vichāra.
