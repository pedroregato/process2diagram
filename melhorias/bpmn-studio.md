# PC116 — BPMN Studio

## Resumo

Hoje o único caminho para gerar um BPMN no P2D é processar uma transcrição de reunião completa pelo pipeline (`Pipeline.py` → `Orchestrator` → `AgentBPMN`). O **BPMN Studio** cria um segundo caminho, independente de reunião: o usuário descreve um processo em texto livre (não precisa ser uma transcrição — pode ser uma descrição direta, tipo "o cliente preenche o formulário X, que é validado pelo analista Y..."), e o sistema gera BPMN 2.0 + Mermaid a partir disso, com opção de salvar (versionado, como hoje) e opcionalmente vincular a uma reunião existente. Inclui também o caminho inverso: dado um XML BPMN qualquer, gerar a descrição textual detalhada do processo.

**Por que agora:** a base necessária já existe quase toda — `AgentBPMN`, `bpmn_generator.py`, `agent_mermaid.py`, o schema `bpmn_processes`/`bpmn_versions`, e a lógica de "BPMN → texto" já roda dentro do Assistente (`describe_bpmn_process`). O trabalho real é costurar essas peças num fluxo autônomo (fora do pipeline de reunião) e resolver uma lacuna concreta de schema (ver §4).

---

## 1. Escopo

**Dentro do escopo:**
- Nova página `pages/BpmnStudio.py` com dois modos: **Gerar** (descrição → BPMN + Mermaid) e **Descrever** (BPMN → descrição).
- Geração reaproveitando `AgentBPMN` via um hub sintético (não uma reunião real).
- Armazenamento reaproveitando `bpmn_processes` / `bpmn_versions` (mesma infraestrutura do `BpmnEditor.py`).
- Vínculo opcional a uma reunião existente do projeto ativo (select, não obrigatório).
- Extração de "BPMN → descrição" refatorada para função reutilizável (hoje está presa dentro do executor do Assistente).

**Fora do escopo (não fazer nesta rodada):**
- Editor visual dedicado para o BPMN Studio — reaproveitar o modeler já existente em `BpmnEditor.py` (não duplicar).
- Geração de ata/requisitos/SBVR a partir da descrição — BPMN Studio gera só BPMN + Mermaid, mesmo que a descrição contenha decisões (isso é escopo do pipeline normal).
- Multiplayer/colaboração em tempo real na descrição.

---

## 2. O que já existe e será reaproveitado (achados da investigação)

| Necessidade | Já existe em | Reaproveitar como |
|---|---|---|
| Extrair steps/edges/lanes de um texto e gerar BPMNModel | `agents/agent_bpmn.py::AgentBPMN` (`required_hub_fields = ["transcript_clean"]`) | Alimentar `hub.transcript_clean` com a descrição do processo digitada pelo usuário — **não precisa ser uma transcrição de reunião**, o agente não distingue a origem do texto |
| Gerar XML BPMN 2.0 a partir do modelo | `AgentBPMN._generate_bpmn_xml()` | Direto, sem mudança |
| Gerar Mermaid a partir do modelo | `AgentBPMN._generate_mermaid()` / `agents/agent_mermaid.py` | Direto, sem mudança |
| Detectar atores/organizações para nomear lanes corretamente | `agents/nlp_chunker.py::NLPChunker` (spaCy, sem LLM) | Rodar opcionalmente sobre a descrição antes do `AgentBPMN`, mesmo padrão do pipeline normal |
| Visualizar o BPMN gerado | `modules/bpmn_viewer.py::preview_from_xml()` | Direto, sem mudança |
| Visualizar o Mermaid gerado | `modules/mermaid_renderer.py::render_mermaid_block()` | Direto, sem mudança |
| Salvar como processo versionado | `core/project_store.py::save_bpmn_from_hub()` / `save_bpmn_new_version()` | Precisa de ajuste de assinatura — ver §4 |
| Editor visual + histórico de versões | `pages/BpmnEditor.py` | Após salvar, o processo criado no Studio aparece no seletor do BpmnEditor normalmente (mesma tabela) |
| **BPMN → descrição textual** | `core/tools/tools_bpmn_sbvr.py::AssistantToolExecutor.describe_bpmn_process()` (linhas ~530+) | **Extrair essa lógica para uma função pura reutilizável** (ver §3.2) — hoje ela só funciona para processos já salvos no banco; o Studio precisa funcionar com qualquer XML colado, salvo ou não |

Conclusão: não é necessário criar um novo agente do zero para o fluxo "descrição → BPMN". É necessário um **wrapper fino** que monta um hub sintético e chama `AgentBPMN` — evita duplicar as ~700 linhas de `_enforce_rules` / geração de XML / geração de Mermaid que já existem e são testadas.

---

## 3. Arquitetura proposta

### 3.1 Fluxo "Gerar" (descrição → BPMN + Mermaid)

```
Descrição do processo (texto livre, textarea)
        │
        ▼
  hub sintético: KnowledgeHub(transcript_clean=descrição, ...campos default)
        │
        ▼
  NLPChunker (opcional, sem LLM) — melhora nomeação de lanes
        │
        ▼
  AgentBPMN.run(hub)  ← reaproveitado sem alteração
        │
        ▼
  hub.bpmn (BPMNModel: xml + mermaid prontos)
        │
        ├─► preview_from_xml(hub.bpmn.xml)      → aba "Diagrama BPMN"
        ├─► render_mermaid_block(hub.bpmn.mermaid) → aba "Mermaid"
        └─► [Salvar] → save_bpmn_from_hub(meeting_id=None|selecionado, project_id, hub, ...)
```

Novo arquivo sugerido: `agents/agent_bpmn_studio.py` — **não uma cópia de AgentBPMN**, e sim uma função `generate_bpmn_from_description(description: str, project_id: str, run_nlp: bool = True) -> KnowledgeHub` que:
1. Monta um `KnowledgeHub` mínimo (`KnowledgeHub.migrate()` num hub vazio, depois seta `transcript_clean`).
2. Roda `NLPChunker` se `run_nlp=True` (mesmo padrão do `Pipeline.py`, sem custo de LLM).
3. Chama `AgentBPMN().run(hub)`.
4. Retorna o hub para a página renderizar.

Registrar em `core/agent_registry.py` como entrada on-demand (mesmo padrão de `knowledge_extractor`): `authority_level: "draft"`, `pipeline_step: None`, `skill_path` reaproveita `skills/skill_bpmn.md` (mesmo skill do AgentBPMN — não precisa de skill novo, é o mesmo contrato de extração).

### 3.2 Fluxo "Descrever" (BPMN → descrição)

Refatorar `describe_bpmn_process()` (`core/tools/tools_bpmn_sbvr.py`): hoje o método faz duas coisas misturadas — (a) resolver `process_name` → XML armazenado no banco, (b) andar na árvore XML e montar o texto. Separar em:

```python
# modules/bpmn_describer.py (novo)
def describe_bpmn_from_xml(xml_str: str) -> str:
    """Toda a lógica atual de describe_bpmn_process a partir da linha ~550
    (parsing ET, elem_map, lane_elements, pool_names, flows, montagem do texto)."""
    ...
```

`AssistantToolExecutor.describe_bpmn_process()` passa a: resolver `process_name` → `xml_str` (como já faz) → chamar `describe_bpmn_from_xml(xml_str)`. Zero mudança de comportamento para quem já usa a tool no Assistente — é refatoração pura, sem risco.

`pages/BpmnStudio.py`, aba "Descrever": textarea para colar XML (ou upload `.bpmn`/`.xml`) → `describe_bpmn_from_xml(xml)` → exibe o texto → botão para copiar / baixar `.md`.

Ganho colateral: a lógica de parsing deixa de estar presa a "processo já salvo no projeto" — passa a funcionar com qualquer XML, inclusive um BPMN importado de fora do sistema.

### 3.3 Armazenamento e vínculo a reunião

Reaproveitar 100% a tabela `bpmn_processes` / `bpmn_versions` existente — **não criar tabela nova**. O Studio é só mais um caminho que popula essas tabelas, igual ao pipeline normal e ao `BpmnEditor.py`.

---

## 4. Lacuna de schema — bloqueador real

Investigação em `setup/supabase_schema_bpmn_processes.sql`:

```sql
CREATE TABLE IF NOT EXISTS bpmn_versions (
    ...
    meeting_id   UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,   -- ← bloqueia
    ...
);
```

`bpmn_processes.first_meeting_id` / `last_meeting_id` **já são nullable** — o processo em si já suporta não ter reunião de origem. O bloqueio real está em `bpmn_versions.meeting_id`, que é `NOT NULL`. Isso significa que **hoje é literalmente impossível salvar uma versão de BPMN sem meeting_id** — condição que o BPMN Studio precisa violar por definição (processo criado antes de qualquer reunião existir).

**Migração necessária** (`setup/supabase_migration_bpmn_studio.sql`):
```sql
ALTER TABLE bpmn_versions ALTER COLUMN meeting_id DROP NOT NULL;
```
Sem outros efeitos colaterais — o `ON DELETE CASCADE` continua válido para linhas onde `meeting_id` está preenchido; linhas com `meeting_id IS NULL` simplesmente não são afetadas por delete de reunião.

**Mudança de código correspondente:**
- `core/project_store.py::save_bpmn_from_hub(meeting_id: str, ...)` → `meeting_id: str | None = None`.
- `core/project_store.py::_find_or_create_bpmn_process(project_id, process_name, meeting_id)` → aceitar `meeting_id=None`.
- Qualquer `INSERT` em `bpmn_versions` que hoje assume `meeting_id` presente precisa tratar `None` (verificar `save_bpmn_new_version()` também).

Este item é o único que toca infraestrutura existente fora do escopo do Studio — todo o resto é aditivo.

---

## 5. Nova página `pages/BpmnStudio.py`

Seguir os padrões já estabelecidos (`require_active_project()`, `render_page_header()`, sem selectbox de projeto local — ver Known Pitfalls do CLAUDE.md):

```
┌─────────────────────────────────────────────┐
│ 🏗️ BPMN Studio                                │
│ [🧩 Gerar]  [📖 Descrever]   ← abas           │
├─────────────────────────────────────────────┤
│ Aba Gerar:                                    │
│   Textarea: "Descreva o processo..."          │
│   [ ] Detectar atores automaticamente (NLP)   │
│   [Gerar BPMN]                                │
│   ── após gerar ──                            │
│   Tabs: [Diagrama BPMN] [Mermaid]             │
│   Nome do processo: [____________]            │
│   Vincular a reunião (opcional): [selectbox]  │
│   [💾 Salvar como novo processo]              │
│   [💾 Salvar como nova versão de: ___]        │
├─────────────────────────────────────────────┤
│ Aba Descrever:                                │
│   [Colar XML] ou [Upload .bpmn/.xml]          │
│   [Gerar descrição]                           │
│   ── após gerar ──                            │
│   Texto formatado + [⬇️ Baixar .md]           │
└─────────────────────────────────────────────┘
```

Navegação: adicionar em `app.py`, grupo **Pipeline** (ao lado de `Pipeline.py`, `Diagramas.py`, `BpmnEditor.py`) — é conceitualmente uma forma alternativa de entrada de processo, não uma página de análise.

---

## 6. Checklist de implementação

Seguindo o checklist padrão do CLAUDE.md (§Checklist de Entrega), adaptado:

- [ ] Migração `setup/supabase_migration_bpmn_studio.sql` — `bpmn_versions.meeting_id` nullable — **executar antes de qualquer outro passo**
- [ ] `core/project_store.py` — `save_bpmn_from_hub` e `_find_or_create_bpmn_process` aceitam `meeting_id=None`
- [ ] `modules/bpmn_describer.py` — novo módulo, função `describe_bpmn_from_xml(xml_str) -> str` (lógica movida de `tools_bpmn_sbvr.py`)
- [ ] `core/tools/tools_bpmn_sbvr.py` — `describe_bpmn_process()` refatorado para chamar `describe_bpmn_from_xml()`; **rodar suite de testes após** para confirmar zero regressão de comportamento
- [ ] `agents/agent_bpmn_studio.py` — novo módulo, função `generate_bpmn_from_description(description, project_id, run_nlp=True) -> KnowledgeHub`
- [ ] `core/agent_registry.py` — registrar entrada on-demand (`pipeline_step: None`, `authority_level: "draft"`)
- [ ] `pages/BpmnStudio.py` — nova página, dois modos (Gerar / Descrever)
- [ ] `app.py` — registrar página no grupo **Pipeline**
- [ ] `claude_guideline/roadmap.md` — registrar como PC116 ao concluir
- [ ] `CLAUDE.md` — adicionar `pages/BpmnStudio.py` na árvore de Repository Structure e na tabela de Navigation Groups

---

## 7. Critérios de aceite

(formato consistente com `claude_guideline/acceptance_criteria.md`)

## AgentBpmnStudio (geração)
- Dada uma descrição de processo em texto livre (sem transcrição de reunião), gera um `BPMNModel` válido com XML BPMN 2.0 renderizável no bpmn-js e Mermaid correspondente.
- Descrições envolvendo 2+ organizações distintas produzem formato multi-pool (mesma lógica de detecção de colaboração já existente em `AgentBPMN.run()`).
- Falha de forma clara (mensagem ao usuário, não exceção não tratada) quando a descrição é vazia, curta demais ou não descreve um processo reconhecível.

## BpmnDescriber (reverso)
- Dado qualquer XML BPMN 2.0 válido (salvo no projeto ou colado livremente), retorna descrição textual estruturada: participantes, fluxo numerado passo-a-passo, resultados possíveis.
- Comportamento idêntico ao `describe_bpmn_process` atual para processos já salvos — refatoração não muda output para os casos existentes.
- XML malformado retorna mensagem de erro de parsing clara, não crash.

## Persistência
- Processo gerado no Studio pode ser salvo sem `meeting_id` (novo processo, sem vínculo a reunião).
- Processo gerado no Studio pode ser salvo com `meeting_id` de uma reunião existente do projeto ativo (selectbox).
- Processo salvo no Studio aparece no seletor do `BpmnEditor.py` e pode receber novas versões por lá normalmente (mesma tabela, sem tratamento especial).

## UI / Streamlit
- Página usa `require_active_project()` — sem selectbox de projeto local.
- Nenhuma chamada de `st.download_button` após geração sem antes persistir o hub em `session_state` (pitfall conhecido do projeto).

---

## 8. Riscos e decisões em aberto

- **Custo de LLM por geração:** cada clique em "Gerar BPMN" é uma chamada real ao provedor configurado (mesmo custo de uma execução normal do AgentBPMN). Sem novo mecanismo de cache — o `SemanticCache` (SHA256) já cobre isso automaticamente se a descrição for repetida.
- **Qualidade sem contexto de reunião:** descrições curtas ou ambíguas (sem os "sinais" que uma transcrição real oferece — quem disse o quê, hesitações, correções) tendem a gerar BPMNs mais genéricos. Vale considerar, numa iteração futura, um placeholder/exemplo na textarea orientando o nível de detalhe esperado — não bloqueante para a v1.
- **Nome do processo:** `AgentBPMN` já infere `hub.bpmn.name` a partir do conteúdo; permitir que o usuário sobrescreva antes de salvar (campo editável), como o `BpmnEditor.py` já faz via `bpmn_process_override_name`.
- ~~**Torneio multi-run (`n_bpmn_runs > 1`) e LangGraph adaptativo:** decidir se o Studio expõe esses controles avançados... recomendação: modo simples na v1, adicionar como opção avançada só se o uso demonstrar necessidade.~~ **Atualizado (PC116-D, 2026-07-04):** o uso demonstrou a necessidade na primeira sessão de testes real — sem torneio, uma extração podia "passar" na validação mínima mas ainda assim ser estruturalmente pobre (organização externa nomeada colapsada num sendTask em vez de um segundo pool; sub-ciclo detalhado colapsado num callActivity opaco). O Studio agora usa o mesmo torneio + `AgentValidator` do pipeline normal (não LangGraph, que só é o caminho padrão quando `n_bpmn_runs<=1` — uma config não-default).

---

## 9. Estimativa

| Etapa | Esforço |
|---|---|
| Migração de schema + ajuste `project_store.py` | Pequeno |
| Refatoração `describe_bpmn_process` → `bpmn_describer.py` | Pequeno (é só extração de código já existente) |
| `agent_bpmn_studio.py` (wrapper) | Pequeno-médio |
| `pages/BpmnStudio.py` (UI completa, 2 abas) | Médio |
| Testes + registro em roadmap/CLAUDE.md | Pequeno |

Nenhuma etapa depende de infraestrutura nova (sem migração de provedor, sem nova biblioteca, sem novo padrão arquitetural) — é composição de peças já existentes e testadas, com uma correção pontual de schema.
