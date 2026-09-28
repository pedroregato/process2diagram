# evals/bpmn_metrics — régua estrutural para o BPMN do Vichāra (V3)

Mede os BPMNs gerados pelo Vichāra com as métricas de qualidade pragmática de
Sánchez-González et al. (2012) e compara com ~5,8 mil processos reais do corpus
[Camunda BPMN for Research](https://github.com/camunda/bpmn-for-research),
por faixa de tamanho. Só stdlib; sem LLM; não grava nada no banco.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `metrics.py` | XML → métricas por `<process>` (TNN, TNSF, eventos, gateways, CFC, AGD, MGD, GM, GH) + sinais estruturais |
| `build_reference.py` | Recalcula a referência a partir dos `.bpmn` originais da Camunda |
| `compare.py` | Compara Vichāra × referência e gera `report.md` + CSV por processo |
| `reference/camunda_metrics.csv` | Referência já calculada (5.781 processos com TNN ≥ 3) |
| `reports/AAAA-MM-DD/` | Relatórios gerados |
| `../../tests/test_bpmn_metrics.py` | Testes das fórmulas |

## Uso

```bash
# 1) (opcional) regenerar a referência
git clone --depth 1 https://github.com/camunda/bpmn-for-research.git ../bpmn-for-research
python -m evals.bpmn_metrics.build_reference ../bpmn-for-research

# 2) comparar — direto do Supabase (usa .streamlit/secrets.toml, como o app)
python -m evals.bpmn_metrics.compare --from-supabase

#    ou a partir de arquivos exportados
python -m evals.bpmn_metrics.compare --from-dir caminho/para/bpmns

pytest tests/test_bpmn_metrics.py
```

## Decisões de medição

- **Unidade = um `<process>`** (uma pool), como no dataset do Kaggle.
- **TNN = eventos + atividades + gateways.** O CSV do Kaggle conta também
  `laneSet`, `textAnnotation` e `association`; por isso a referência é
  recalculada com este mesmo código, e não lida do Kaggle. As colunas de
  contagem (TNSF, TNSE, TNBE, TNIE, TNEE, TNE) foram conferidas contra linhas
  do CSV do Kaggle e batem.
- **Link events são resolvidos.** O gerador troca por link throw/catch todo
  fluxo que cruza ≥ 2 lanes; cada par vira um fluxo direto antes de medir.
- **Complexidade só entre modelos com gateway.** Sem gateway, CFC/GM/AGD são
  0 por construção; misturar os dois grupos puxa as medianas para baixo.
- **CFC:** XOR-split = fan-out; OR-split = 2ⁿ − 1; AND-split = 1.
  **GM:** Σ por tipo |Σ fan-out dos splits − Σ fan-in dos joins|.
  **GH:** entropia dos tipos de gateway em base 3 (0 a 1).
- XML com atributo duplicado na raiz (dois `xmlns=`) é reparado e marcado
  `repaired_xml=True`.

## Limites

Métricas estruturais não avaliam rótulos, semântica de negócio nem correção
(deadlock, eventos de fim por resultado). São uma régua complementar ao
`AgentValidator`, não um substituto. Não treinar modelo para prever essas
notas: elas são fórmulas das próprias colunas.
