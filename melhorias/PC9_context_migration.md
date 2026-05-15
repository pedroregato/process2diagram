# PC9 — Migração `project` → `context`

> **Documento de instrução para Claude Code / PyCharm**
> Leia este arquivo integralmente antes de tocar em qualquer arquivo.

---

## Contexto e motivação

O conceito de "projeto" no sistema é semanticamente restritivo. O Process2Diagram é usado para
processar transcrições de naturezas muito variadas: projetos técnicos, estudos de viabilidade,
reuniões de planejamento estratégico, discussões sobre produtos, séries de reuniões recorrentes, etc.

A palavra **"contexto"** (inglês: `context`) foi escolhida como substituta porque:
- É neutra — não pressupõe prazo, intencionalidade ou entregável
- Descreve o que o sistema realmente precisa: o universo de pessoas, vocabulário e decisões
  dentro do qual um conjunto de reuniões acontece
- Funciona para qualquer natureza de iniciativa

Esta migração é a **base para o PKF (Project Knowledge File → Context Knowledge File)**,
que será implementado na sequência como parte do mesmo PC9.

---

## Escopo da mudança

A mudança tem **4 camadas**, executadas nesta ordem obrigatória:

```
Fase 1 → Banco de dados (DDL + migração)
Fase 2 → Python: project_store + módulos dependentes
Fase 3 → UI: labels e textos visíveis ao usuário
Fase 4 → PKF: nova funcionalidade sobre a base migrada
```

Fases 1+2+3 formam a **v4.16**. Fase 4 começa imediatamente após, como **v4.17**.

---

## Fase 1 — Banco de Dados

### 1.1 — Criar script de migração

Criar o arquivo `setup/migrate_v4_16_context.sql` com o seguinte conteúdo:

```sql
-- ============================================================
-- Process2Diagram — Migration v4.16
-- Rename: projects → contexts
-- Add: contexts.skill_md, contexts.context_type
-- ============================================================

-- 1. Renomear tabela principal
ALTER TABLE projects RENAME TO contexts;

-- 2. Adicionar coluna de tipo de contexto
ALTER TABLE contexts
    ADD COLUMN IF NOT EXISTS context_type TEXT DEFAULT 'project';
-- Valores válidos: 'project' | 'product' | 'feasibility' | 'strategic' | 'meeting_series' | 'discussion' | 'other'

-- 3. Adicionar coluna para o Context Knowledge File (PKF)
ALTER TABLE contexts
    ADD COLUMN IF NOT EXISTS skill_md TEXT;

-- 4. Comentários de documentação
COMMENT ON TABLE contexts IS 'Process2Diagram contexts (formerly: projects). A context groups meetings sharing the same organizational universe.';
COMMENT ON COLUMN contexts.context_type IS 'Nature of the context: project | product | feasibility | strategic | meeting_series | discussion | other';
COMMENT ON COLUMN contexts.skill_md IS 'Context Knowledge File (CKF): markdown with participants, glossary, decisions, goals. Injected into agent prompts.';
```

**Notas importantes:**
- As colunas FK `project_id` nas tabelas filhas (`meetings`, `requirements`, `transcript_chunks`,
  `bpmn_processes`, `sbvr_terms`, `sbvr_rules`) **não são renomeadas nesta fase**.
  Elas continuam como `project_id` — o custo de renomear todas as FKs não justifica o benefício agora.
  O código usará alias internamente.
- Executar este script no Supabase SQL Editor **antes** de fazer deploy de qualquer código.
- Verificar no Supabase Table Editor se a tabela `contexts` aparece corretamente após execução.

### 1.2 — Adicionar migração ao Settings.py

Em `pages/Settings.py`, localizar a seção de migrações SQL (onde ficam os `ALTER TABLE` das fases
anteriores) e adicionar um novo expander ou botão para a Fase 4 (v4.16) com o conteúdo do script acima.
Seguir o padrão visual já existente para as outras migrações.

---

## Fase 2 — Camada Python

### 2.1 — `core/project_store.py`

Este é o arquivo central. Todas as queries que referenciam a tabela `projects` devem passar a usar `contexts`.

**Regra geral:** trocar `.table("projects")` por `.table("contexts")` em todas as queries Supabase.

**Funções a renomear** (manter alias de compatibilidade temporário comentado para facilitar rollback):

| Nome atual | Novo nome |
|---|---|
| `list_projects()` | `list_contexts()` |
| `get_project(project_id)` | `get_context(context_id)` |
| `create_project(name, ...)` | `create_context(name, ...)` |
| `update_project(project_id, ...)` | `update_context(context_id, ...)` |
| `delete_project(project_id)` | `delete_context(context_id)` |
| `get_global_stats()` | manter nome, ajustar query interna |

**Adicionar novas funções para o CKF:**

```python
def get_context_skill(context_id: str) -> str | None:
    """Fetch the Context Knowledge File (skill_md) for a context."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        res = client.table("contexts").select("skill_md").eq("id", context_id).single().execute()
        return res.data.get("skill_md") if res.data else None
    except Exception:
        return None


def save_context_skill(context_id: str, skill_md: str) -> bool:
    """Persist the Context Knowledge File for a context. Returns True on success."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("contexts").update({"skill_md": skill_md}).eq("id", context_id).execute()
        return True
    except Exception:
        return False
```

**Padrão de alias temporário** (adicionar ao final do arquivo para não quebrar chamadas existentes
durante a transição — remover após confirmação de que todas as páginas foram atualizadas):

```python
# --- Compatibility aliases (remove after v4.16 rollout) ---
list_projects = list_contexts
get_project = get_context
create_project = create_context
```

### 2.2 — `modules/meeting_roi_calculator.py`

- Renomear `compute_project_roi()` → `compute_context_roi()`
- Adicionar alias: `compute_project_roi = compute_context_roi`
- Ajustar query interna se referenciar a tabela `projects` diretamente

### 2.3 — `modules/cross_meeting_analyzer.py`

- Renomear `save_project_scores()` → `save_context_scores()` se existir
- Ajustar qualquer query interna que referencie `projects`

### 2.4 — `ui/project_selector.py` → `ui/context_selector.py`

Renomear o arquivo. Dentro dele:
- Renomear função `render_project_selector()` → `render_context_selector()`
- Atualizar chamadas internas a `list_projects()` → `list_contexts()`
- Atualizar labels visíveis (ver Fase 3)

Atualizar todos os imports deste módulo nas páginas que o utilizam:
- `pages/Assistente.py`
- `pages/ReqTracker.py`
- Qualquer outra página que importe `project_selector`

### 2.5 — `core/knowledge_hub.py`

Adicionar o campo `context_skill` ao `KnowledgeHub`:

```python
@dataclass
class KnowledgeHub:
    # ... campos existentes ...
    context_skill: str = ""   # Content of the Context Knowledge File (CKF), injected into agents
    context_id: str = ""      # ID of the active context (set by pipeline caller when available)
    context_type: str = ""    # Type of context: project | product | feasibility | etc.
```

Adicionar guard em `KnowledgeHub.migrate()`:

```python
@staticmethod
def migrate(hub):
    if not hasattr(hub, 'context_skill'):
        hub.context_skill = ""
    if not hasattr(hub, 'context_id'):
        hub.context_id = ""
    if not hasattr(hub, 'context_type'):
        hub.context_type = ""
    return hub
```

### 2.6 — `pages/Assistente.py`

- Substituir import de `project_selector` → `context_selector`
- Substituir chamada `render_project_selector()` → `render_context_selector()`
- Atualizar variável interna `project_id` → pode manter o nome internamente (é uma FK column),
  mas o label na UI deve mudar (ver Fase 3)

### 2.7 — `pages/MeetingROI.py`

- Atualizar chamada de `compute_project_roi()` → `compute_context_roi()`
- Atualizar labels (ver Fase 3)

---

## Fase 3 — UI e Labels

Substituições textuais nas páginas. **Não alterar nomes de variáveis Python** nesta fase —
apenas strings visíveis ao usuário.

### Substituições globais (find & replace em todos os arquivos `pages/` e `ui/`):

| De | Para |
|---|---|
| `"Projeto"` | `"Contexto"` |
| `"projeto"` (início de frase) | `"contexto"` |
| `"Selecionar Projeto"` | `"Selecionar Contexto"` |
| `"Criar Projeto"` | `"Criar Contexto"` |
| `"Novo Projeto"` | `"Novo Contexto"` |
| `"Projetos"` | `"Contextos"` |
| `"projetos"` | `"contextos"` |
| `"nenhum projeto"` | `"nenhum contexto"` |
| `"sem projeto"` | `"sem contexto"` |
| `"X projetos"` (KPIs) | `"X contextos"` |

**Atenção:** não alterar:
- Nomes de variáveis Python como `project_id` (FK column — não muda nesta fase)
- Nomes de funções ainda com alias antigo
- Comentários técnicos internos (podem ser atualizados, mas não é obrigatório agora)

### Adicionar seletor de `context_type` na criação de novo contexto

Onde houver formulário de criação de novo projeto/contexto, adicionar campo:

```python
context_type = st.selectbox(
    "Tipo de Contexto",
    options=["project", "product", "feasibility", "strategic", "meeting_series", "discussion", "other"],
    format_func=lambda x: {
        "project": "🏗️ Projeto",
        "product": "📦 Produto",
        "feasibility": "🔍 Estudo de Viabilidade",
        "strategic": "🎯 Planejamento Estratégico",
        "meeting_series": "🔄 Série de Reuniões",
        "discussion": "💬 Discussão",
        "other": "📋 Outro",
    }[x],
    index=0,
    help="Define a natureza deste contexto. Usado para orientar os agentes e o Knowledge File."
)
```

---

## Fase 4 — Context Knowledge File (CKF)

> Implementar **após** confirmar deploy estável das Fases 1–3.

### 4.1 — Template do CKF

Criar `skills/skill_context_template.md`:

```markdown
---
context_slug: {slug}
context_name: "{nome}"
context_type: {tipo}
owner: {responsavel}
status: active
last_updated: {data}
ckf_version: 1
---

## 1. Identidade do Contexto

**Objetivo:** {descreva o propósito central deste contexto}
**Escopo:** {o que está dentro / o que está fora}
**Período:** {datas ou duração esperada}
**Entregável esperado:** {o que se espera produzir}

## 2. Pessoas e Relacionamentos

| Nome | Papel | Área | Notas |
|------|-------|------|-------|
| {Nome} | {Papel} | {Área} | {Observações de comportamento/postura} |

**Hierarquia decisória:**
1. {Nome} — {motivo da autoridade}

**Notas de sentimento / padrões observados:**
- {observação sobre participante ou dinâmica de grupo}

## 3. Conhecimento Acumulado

### Terminologia Canônica
| Termo usado na reunião | Significado no contexto |
|------------------------|------------------------|
| {termo} | {definição interna} |

### Processos Já Mapeados
- `{NomeProcesso_vN}` — status: {aprovado | em revisão}

### Decisões Já Tomadas (não reabrir)
- {decisão} — {data ou reunião de referência}

### Tensões Abertas
- {descrição da tensão em aberto}

### Metas e KPIs
- {meta} — indicador: {KPI}
```

### 4.2 — Injeção do CKF nos agentes

Adicionar injeção condicional em `agents/agent_minutes.py` e `agents/agent_bpmn.py`:

```python
def build_prompt(self, hub, output_language="Auto-detect") -> tuple[str, str]:
    # ... código existente ...

    context_block = ""
    if getattr(hub, 'context_skill', ''):
        context_block = f"""
## Contexto do Projeto/Iniciativa
{hub.context_skill}

Instruções de uso:
- Use os nomes canônicos dos participantes listados acima (não variações)
- Aplique a terminologia do glossário deste contexto
- Não reabra decisões marcadas como "já tomadas"
- Respeite a hierarquia decisória ao atribuir responsabilidades
"""

    system_prompt = self._load_skill() + context_block
    # ... restante do método ...
```

Fazer o mesmo em `agents/agent_sbvr.py` e `agents/agent_bmm.py` (glossário e metas são especialmente
relevantes para estes agentes).

### 4.3 — Carregamento do CKF no pipeline

Em `core/pipeline.py` ou no caller em `pages/Pipeline.py`, ao selecionar um contexto:

```python
# Após selecionar context_id na UI:
if context_id:
    skill_md = project_store.get_context_skill(context_id)
    if skill_md:
        hub.context_skill = skill_md
    hub.context_id = context_id
```

### 4.4 — Edição do CKF no Assistente

Em `pages/Assistente.py`, adicionar comando de atualização via chat. Quando o usuário digitar
algo como `"atualizar contexto: ..."` ou `"adicionar ao knowledge file: ..."`, o AgentAssistant
deve reconhecer e chamar `save_context_skill()`.

Adicionar ferramenta ao `AssistantToolExecutor` em `core/assistant_tools.py`:

```python
# Tool: save_context_skill (admin)
# Params: context_id (str), skill_md (str)
# Categoria: admin (requer is_admin())
```

---

## Checklist de Deploy

```
[ ] Script SQL executado no Supabase (verificar tabela contexts no Table Editor)
[ ] project_store.py atualizado e aliases criados
[ ] meeting_roi_calculator.py atualizado
[ ] cross_meeting_analyzer.py atualizado (se aplicável)
[ ] ui/project_selector.py renomeado para ui/context_selector.py
[ ] Imports atualizados em todas as páginas que usavam project_selector
[ ] knowledge_hub.py: campos context_skill, context_id, context_type adicionados + migrate()
[ ] Labels UI atualizados (Fase 3)
[ ] Seletor de context_type adicionado no formulário de criação
[ ] Deploy para Streamlit Cloud (push para main)
[ ] Verificar: Home.py KPIs mostram "contextos"
[ ] Verificar: Assistente.py carrega lista de contextos
[ ] Verificar: ReqTracker.py carrega lista de contextos
[ ] Verificar: MeetingROI.py funciona com compute_context_roi()
[ ] Verificar: criação de novo contexto funciona com context_type
[ ] skill_context_template.md criado em skills/
[ ] CLAUDE.md atualizado: versão → v4.16, seção project_store documentada com novos nomes
```

---

## Arquivos a NÃO tocar

- `setup/supabase_schema_transcript_chunks.sql` — não altera a tabela `transcript_chunks`
- Testes em `tests/` — não referenciam `projects` diretamente
- `modules/auth.py` — sem relação com esta mudança
- `modules/bpmn_generator.py` e afins — sem relação

---

## Observações finais para o Claude Code

1. **Executar Fase 1 antes de qualquer deploy** — código que tenta ler `contexts` antes da
   migração SQL vai falhar em produção.

2. **Os aliases de compatibilidade** (`list_projects = list_contexts`) devem ser mantidos até
   confirmação de que todas as páginas foram atualizadas. Só então remover.

3. **Não renomear `project_id` nas colunas FK** das tabelas filhas nesta versão.
   Isso é trabalho para uma futura v4.x quando houver tempo para uma migração mais abrangente.

4. **Atualizar o CLAUDE.md** ao final com:
   - Versão → v4.16
   - Tabela de banco: `projects` → `contexts` em todas as referências
   - Funções do project_store com novos nomes
   - Seção sobre CKF (Context Knowledge File)
   - Roadmap: marcar PC9 Fases 1–3 como concluídas
