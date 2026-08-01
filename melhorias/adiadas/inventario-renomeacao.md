# Inventário da Renomeação Global (Fase B — read-only)

> Executado em paralelo à Fase A, por instrução do Agente 0 (sequenciamento arbitrado sobre
> `melhorias/renomeacao-global-contexto-vichara.md`). **Nenhuma renomeação executada.**
> Reaproveita a mesma varredura da Fase A onde aplicável. Data: 2026-07-19.

---

## B1 — Números atualizados (vs. `reconciliacao_product_manifesto.md §3`, PC195)

| Escopo | PC195 (2026-07-19, antes) | Hoje (2026-07-19, depois de PC195-197) |
|---|---:|---:|
| `project_id` (símbolo Python, `.py`, fora `.venv`) | 1471 ocorrências / 100 arquivos | **1486 ocorrências / 101 arquivos** |
| `active_project_id`/`active_project_name`/`require_active_project()` | 34 arquivos | **34 arquivos** (sem mudança) |
| `project_id` como coluna/FK (`.sql` em `setup/`) | 28 migrations | **28 migrations** (sem mudança) |
| "process2diagram"/"P2D" (texto, `.py`+`.md`) | 28 arquivos | **31 arquivos** |

O crescimento (+15 ocorrências de `project_id`, +1 arquivo, +3 menções a "process2diagram") vem
inteiramente dos próprios artefatos de governança criados nas rodadas PC195-197 (este
inventário, a proposta de isolamento, o teste `test_context_isolation.py` — todos citam
`project_id` ao descrevê-lo). Nenhum código de produção mudou.

---

## B2 — Ondas por risco

### Onda 1 — Símbolos/params Python puros (baixo risco individual, alto volume)
`project_id` como nome de parâmetro/variável em `core/project_store.py` (35 funções, 52
ocorrências) + `core/tools/*.py` (7 arquivos, 74 ocorrências) — total **88 funções únicas, 126
ocorrências** (mesmo escopo mapeado em `proposta-isolamento-de-contexto.md §3`). Rename
mecânico de nome de parâmetro/kwarg — sem mudança de schema, sem mudança de contrato JSON
externo desde que `api.py` seja verificado antes (ver `renomeacao-global-contexto-vichara.md
§2 Fase 2`).

### Onda 2 — `session_state` e strings de UI
`active_project_id`/`active_project_name` → `active_context_id`/`active_context_name`;
`require_active_project()` → `require_active_context()`. 34 arquivos — `ui/project_selector.py`
(definição) + toda página de análise que chama `require_active_project()`. Rename de símbolo +
chave de dicionário (`st.session_state`), sem tocar em queries Supabase.

### Onda 3 — `{project_name}` no system prompt de Vichāra
`agents/agent_assistant.py` (linhas 418, 516, 521, 850, 855, 978, 1013, 1409, 1427, 1442) —
string literal `"═══ PROJETO: {project_name} ═══"` e variável de template. Maior visibilidade
ao usuário final (é lida pelo LLM em toda conversa), menor volume de código tocado.

### Onda 4 — Colunas/FK `.sql` (schema de banco — maior risco)
28 migrations em `setup/` referenciam `project_id` como coluna/FK. Dado já em produção —
qualquer rename aqui precisa de estratégia de migração própria (rename com view/alias de
compatibilidade, ou coordenação de deploy), não é find-and-replace.

---

## B3 — Coincidência com os caminhos de isolamento da Fase A

| Onda | Coincide com os 126 pontos de `.eq("project_id", ...)` da auditoria (`memory/auditoria_isolamento.md`)? | Pode andar antes do guard existir? |
|---|---|---|
| **Onda 1** (símbolos Python) | **SIM — é exatamente o mesmo código.** Renomear `project_id`→`context_id` nos parâmetros de `core/project_store.py`/`core/tools/*.py` significa reescrever, uma a uma, as mesmas 126 chamadas `.eq(...)` que hoje são o único mecanismo de isolamento — incluindo as 11 funções 🟡 AMBÍGUO da auditoria. Renomear sem o guard antes é o vetor exato que a Fase A existe para prevenir: um erro de digitação ou um `.eq()` esquecido durante o rename não falha ruidosamente — vaza em silêncio. | **NÃO.** Trava até Fase A completa (teste de isolamento verde + guard arbitrado). |
| **Onda 2** (session_state/UI) | Não — `active_project_id` é uma chave de `st.session_state`/nome de função (`require_active_project()`); o valor que ela carrega ainda é passado posicionalmente para as funções de `project_store.py`, que continuam com seu próprio parâmetro `project_id` intocado nesta onda. Não toca em nenhuma cláusula `.eq(...)`. | Estruturalmente, sim — mas ainda está sob a trava geral da Fase C ("não iniciar" até liberação explícita), só não tem o motivo de segurança específico da Onda 1. |
| **Onda 3** (`{project_name}` no prompt) | Não — string de exibição, nunca participa de uma query. | Mesma observação da Onda 2. |
| **Onda 4** (schema SQL) | **SIM, e é o ponto de maior risco de todos** — é a própria coluna que `.eq("project_id", ...)` referencia. Um rename de coluna mal coordenado durante a janela de deploy é o cenário de vazamento mais grave possível (código e schema temporariamente dessincronizados). | **NÃO.** Trava até Fase A completa — e, mesmo depois, o texto original da Fase C já exige arbitragem própria do Agente 0 só para esta onda, independente da Fase A. |

**Conclusão da B3:** das 4 ondas, só a Onda 1 e a Onda 4 têm relação direta de segurança com a
Fase A — são exatamente os pontos que a auditoria mapeou. As Ondas 2 e 3 são renomeações de
símbolo/texto sem relação com o mecanismo de isolamento, mas seguem sob a mesma trava geral da
Fase C por instrução explícita ("não pule a trava entre B e C").
