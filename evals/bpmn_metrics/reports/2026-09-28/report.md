# Métricas BPMN — Vichāra × referência Camunda

_Gerado em 2026-09-28 por `evals/bpmn_metrics/compare.py`._

- Processos avaliados: **91** (TNN ≥ 3)
- Referência: **5781** processos do corpus Camunda BPMN for Research
- Links throw/catch resolvidos como fluxo direto antes de medir.

## Distribuição por tamanho (TNN)

| Faixa | Vichāra | Referência |
|---|---|---|
| <10 | 65 (71%) | 2030 (35%) |
| 10–19 | 25 (27%) | 3314 (57%) |
| 20–29 | 1 (1%) | 431 (7%) |
| ≥30 | 0 (0%) | 6 (0%) |

## Complexidade por faixa (só processos com gateway)

Mediana do Vichāra / p50 da referência / p95 da referência.

| Faixa | n Vichāra | n ref | CFC | GM | AGD | MGD |
|---|---|---|---|---|---|---|
| <10 | 31 | 1179 | 2 / 2 / 3 | 2 / 2 / 3 | 3 / 3 / 4 | 3 / 3 / 4 |
| 10–19 | 25 | 2951 | 2 / 5 / 8 | 2 / 2 / 7 | 3 / 3 / 4 | 3 / 3 / 5 |
| 20–29 | 0 | 430 | — / 7 / 10 | — / 3 / 8 | — / 3.25 / 3.5 | — / 4 / 5 |
| ≥30 | 0 | 6 | — / 10 / 14 | — / 8.5 / 13.5 | — / 3.23 / 3.7 | — / 4 / 5.5 |

## Sinais estruturais (% dos processos)

| Sinal | Vichāra | Referência |
|---|---|---|
| no_start | 0% | 3% |
| no_end | 0% | 7% |
| no_gateway | 38% | 21% |
| orphan_nodes | 0% | 6% |
| pass_through_gateways | 0% | 8% |
| mixed_gateways | 2% | 9% |
| implicit_joins | 59% | 23% |
| implicit_splits | 11% | 7% |
| goto_events | 3% | 7% |
| link_pairs | 18% | 0% |

## Mix de gateways

| | AND | XOR | OR |
|---|---|---|---|
| Vichāra | 2% | 98% | 0% |
| Referência | 21% | 77% | 2% |

## Processos acima do p95 da faixa (8)

| Processo | Pool | Faixa | TNN | CFC | GM | Alertas |
|---|---|---|---|---|---|---|
| 91146252 | 1 | 10–19 | 19 | 9 | 9 | CFC,GM |
| a2a51223 | 1 | 10–19 | 12 | 8 | 8 | GM |
| e848817d | 2 | 10–19 | 17 | 8 | 8 | GM |
| 505e40d5 | 1 | <10 | 8 | 4 | 4 | CFC,GM |
| 23a0b8f3 | 1 | <10 | 9 | 4 | 4 | CFC,GM |
| 012285f6 | 2 | <10 | 9 | 4 | 4 | CFC,GM |
| 6b954a26 | 1 | <10 | 7 | 4 | 4 | CFC,GM |
| 930e92e5 | 1 | <10 | 8 | 4 | 4 | CFC,GM |

## Leitura (2026-09-28)

Base: última versão de cada um dos 64 processos em `bpmn_versions` (abr–ago/2026), 93 pools, 91 com TNN ≥ 3.

1. **Os diagramas do Vichāra são pequenos.** 71% têm menos de 10 nós, contra 35% na referência; só 1 passa de 20 nós. Complexidade baixa aqui pode ser sinal de modelo enxuto ou de processo sub-representado; a métrica sozinha não distingue os dois.
2. **Na mesma faixa de tamanho, a complexidade está dentro do normal.** Com gateway, as medianas de CFC, AGD e MGD ficam no p50 da referência (<10 nós) ou abaixo dele (10–19 nós: CFC 2 contra 5). Oito processos passam do p95, e todos por GM.
3. **Joins implícitos são válidos pela spec — GM alto não é defeito.** 59% dos processos têm uma tarefa ou evento recebendo dois ou mais fluxos sem gateway (23% na referência), e é isso que infla o GM. A spec OMG 2.0.2 permite explicitamente: "If all the incoming flow is alternative, then a Gateway is not needed" (p.36) e loops por fluxo de volta a um objeto "upstream" (p.36). Como 98% dos gateways do Vichāra são XOR, os ramos que convergem são alternativos. O GM de Sánchez-González mede compreensibilidade, não validade: tratar como ESTILO de baixa prioridade.
3b. **Achado real — split paralelo não intencional (RISCO).** Em 10 processos (11%), uma atividade tem duas ou mais saídas diretas — em 9 deles o XML não tem nenhuma `conditionExpression` —, em geral uma voltando a uma tarefa anterior e outra indo ao fim (ex.: `serviceTask → [userTask anterior, endEvent]`). Pela spec (p.151), múltiplas saídas não condicionais de uma atividade criam caminhos **paralelos**: o processo terminaria um ramo e reentraria no loop ao mesmo tempo. A intenção é claramente uma decisão; falta um XOR. Só 4 `conditionExpression` e nenhum `default` existem em toda a base.
3c. **Link events sem nome (ERRO pela spec).** Os 19 processos com link events usam `<linkEventDefinition>` sem atributo `name`, e a spec exige: "If the trigger is a Link, then the name MUST be entered" (Tabela 10.98, p.269). O pareamento throw→catch é pelo nome (p.258); hoje só o `name` do evento e o id carregam essa informação.
4. **Quase não há paralelismo.** 98% dos gateways são XOR e 2% AND, contra 77% e 21% na referência. Ou as reuniões raramente descrevem trabalho paralelo, ou o prompt puxa para XOR. O V2 (eval com gabarito) pode separar as duas hipóteses.
5. **Higiene estrutural melhor que a referência.** Nenhum processo sem início ou fim, nenhum nó órfão, nenhum gateway de passagem: efeito do gerador e do `repair_bpmn()`.
6. **Dois XMLs malformados** (jun/2026): `xmlns` e `xmlns:xsi` declarados duas vezes na raiz. O Postgres e parsers XML estritos recusam o arquivo. Vale corrigir na origem e sanear os dois registros.

**Limite da medição desta rodada:** as métricas foram extraídas via SQL (estrutura apenas, sem rótulos). Quatro pares de link events não puderam ser pareados nessa extração e aparecem como `goto_events`; rodando `compare.py --from-supabase` localmente, o pareamento é feito pelo id e esse resíduo some.
