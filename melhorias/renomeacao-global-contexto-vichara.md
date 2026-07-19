# Iniciativa — Renomeação Global: `project_id`→`context_id`, "P2D"→"Vichara"

> Aberta como iniciativa separada por instrução do Agente 0, após a ratificação de
> `manifestos/PRODUCT_MANIFESTO.md` (v1.0, PC196). **Este documento só abre e escopa a
> iniciativa — nenhum código, schema ou nome de arquivo foi alterado.** Execução de qualquer
> fase exige nova autorização explícita, fase por fase.
> Data de abertura: 2026-07-19.

---

## 1. Por que isto é uma iniciativa própria, não um patch

`PRODUCT_MANIFESTO.md §9` já classifica esta renomeação como "refatoração de risco" que "não
deve ser executada sem inventário prévio e sem arbitragem do Agente 0". O inventário prévio já
existe (PC195, `memory/reconciliacao_product_manifesto.md §3`):

| Escopo | Extensão medida |
|---|---:|
| `project_id` (símbolo/parâmetro Python) | 1471 ocorrências em 100 arquivos `.py` |
| `active_project_id` / `active_project_name` / `require_active_project()` | 34 arquivos |
| `project_id` como coluna/FK | 28 migrations `.sql` em `setup/` |
| "process2diagram" / "P2D" (texto) | 28 arquivos `.py`/`.md` — inclui nome do repositório GitHub |
| `{project_name}` no system prompt de Vichāra | Visibilidade máxima — literalmente lido pelo LLM a cada conversa |

Isto não é um find-and-replace de uma tarde. Há pelo menos três categorias de risco
**qualitativamente diferentes** dentro do mesmo pedido, e tratá-las como uma coisa só é o
principal risco de execução:

1. **Texto puro** (prompts, docs, comentários) — risco baixo, reversível, sem impacto de schema.
2. **Símbolos Python** (nomes de parâmetro/variável/função em 100 arquivos) — risco médio;
   mecânico se bem testado, mas qualquer contrato externo que dependa do nome do parâmetro
   (ex.: `api.py`, chamadas de tool do Assistente que já usam `project_id` como chave JSON)
   precisa de compatibilidade, não só rename.
3. **Schema de banco** (28 migrations, coluna `project_id` em produção) — risco alto. Renomear
   coluna em tabela já populada em produção exige plano de migração próprio (rename com
   view/alias de compatibilidade, ou coordenação de deploy), não é "mais um PC".
4. **Identidade de produto** ("P2D" → "Vichara" no nome do repositório GitHub, domínio de
   deploy Streamlit Cloud, links já publicados) — risco de infraestrutura, não de código;
   fora do controle só de `git`/`pytest`.

---

## 2. Fases propostas (nenhuma executada — para aprovação individual)

### Fase 0 — Texto do prompt de Vichāra (menor risco, maior visibilidade)
`agents/agent_assistant.py:521` — `═══ PROJETO: {project_name} ═══` → `═══ CONTEXTO:
{project_name}═══` (ou renomear a variável para `{context_name}` também, se o Agente 0
preferir consistência total já nesta fase). Zero impacto de schema/API — é a string mais
visível de todas (lida pelo LLM em toda conversa) e a de menor custo de execução.
**Pode ser feita isoladamente, sem depender das fases seguintes.**

### Fase 1 — Símbolos Python internos (session state + parâmetros)
`active_project_id`/`active_project_name` → `active_context_id`/`active_context_name`;
`require_active_project()` → `require_active_context()` (34 arquivos). Requer decisão: manter
alias de compatibilidade temporário (`require_active_project = require_active_context`) ou
big-bang com suite completa de testes como rede de segurança. **Depende de decisão de
nomenclatura de parâmetro** — ver §3 abaixo antes de iniciar.

### Fase 2 — `project_id` como parâmetro/variável em `core/`
1471 ocorrências, 100 arquivos. Maior volume, mas mecanicamente mais simples que a Fase 3 —
é rename de símbolo, não de schema. Ponto de atenção: `api.py` (API comercial FastAPI) pode
já ter clientes externos que enviam `project_id` como chave JSON — mudar isso quebra contrato
de API sem versionamento. Recomendo checar `api.py`/`docs/externa/` antes de iniciar esta fase.

### Fase 3 — Schema de banco (coluna `project_id`)
28 migrations em `setup/`. A tabela `contexts` já existe (contexto = `contexts`/`project_id`
por definição do próprio `PRODUCT_MANIFESTO §4`) — o rename aqui é da **coluna de FK**
(`project_id` → `context_id`), não da tabela em si. Maior risco: produção já tem dados. Exige
plano de migração próprio (não cabe neste documento) — sugiro tratar como sub-iniciativa com
seu próprio ciclo de teste/rollback antes de tocar em produção.

### Fase 4 — Identidade de produto (P2D → Vichara)
Nome do repositório GitHub, título do `CLAUDE.md`, footer/watermark de páginas ao vivo,
domínio de deploy. `PRODUCT_MANIFESTO §9` já trata isto como "etiqueta histórica" — a fase de
menor urgência técnica e maior custo de infraestrutura (links publicados, SEO, deploy).

---

## 3. Decisões que precisam ser tomadas antes de qualquer execução

- **Nome final do parâmetro:** `context_id` (alinhado a `contexts`, a tabela real) é a leitura
  mais direta de `PRODUCT_MANIFESTO §4`, mas vale confirmar — não há ambiguidade técnica, só
  quero que a primeira linha de código escrita já use o nome definitivo.
- **Estratégia de compatibilidade vs. big-bang:** manter alias temporário (`project_id` como
  kwarg aceito e traduzido internamente) reduz risco de quebra em runtime, mas prolonga a
  convivência dos dois nomes — o próprio problema que motivou a queixa original. Big-bang com
  suite completa (950 testes) como rede é mais limpo, mas é um PR maior e mais arriscado de
  revisar.
- **Ordem real de execução:** este documento sugere Fase 0 → 1 → 2 → 3 → 4, mas cada fase deve
  ser autorizada e executada como seu próprio PC, com sua própria rodada de testes — nunca
  como uma única entrega.
- **Fase 3 (schema) especificamente:** decidir se cabe neste projeto (Streamlit Cloud + Supabase
  direto) ou se deve esperar a migração para Google Cloud já planejada em
  `manifestos/ENGINEERING_MANIFESTO.md §10` — combinar as duas migrações trabalhosas na mesma
  janela pode ser mais eficiente, ou pode ser mais arriscado por acumular mudanças. Decisão do
  Agente 0.

---

## 4. O que este documento NÃO é

Não é uma ordem de serviço. Nenhuma fase começa sem uma instrução explícita e específica —
"execute a Fase 0" ou equivalente. Este documento existe para que essa instrução, quando vier,
já tenha escopo, ordem e riscos mapeados, em vez de ser decidida ad-hoc no meio da execução.
