# Estratégia de Integração: Process2Diagram → ATA Engine

**FGV/DTI — Equipe SOLCORP**  
Versão 1.0 · Maio 2026

---

## Contexto

O **ATA Engine** gera atas de reunião como arquivos HTML standalone — interativos, comentáveis, exportáveis indefinidamente, abrindo via `file://` sem servidor. O **Process2Diagram** é um pipeline Streamlit multi-agente que extrai conhecimento de transcrições de reuniões: BPMN, requisitos, minutos, relatórios executivos.

Os dois sistemas têm objetivos complementares mas não se falam. O objetivo desta estratégia é fazer o P2D emitir atas no padrão exato do ATA Engine como output natural do seu pipeline — sem abrir mão da arquitetura de nenhum dos dois lados.

### Diagnóstico comparativo

| Dimensão | ATA Engine | Process2Diagram |
|---|---|---|
| **Input** | Transcrição → geração manual via Claude | Transcrição → pipeline automático multi-agente |
| **Output de ata** | HTML interativo standalone | Markdown / Word / PDF via `AgentMinutes` |
| **Interatividade** | Alta — chips, comentários, export encadeável | Nula — documentos estáticos |
| **Arquitetura** | HTML único, `file://`, sem servidor | Streamlit Cloud, Supabase, agentes LLM |
| **Quem opera** | Claude Projects (geração manual) | App web Streamlit (geração automática) |

O P2D já tem `AgentMinutes` produzindo `MinutesModel` estruturado — participantes com speaker attribution, decisões separadas de ações, pauta organizada. O que falta é uma camada que converta esse `MinutesModel` em um HTML ATA Engine com fidelidade total ao design system e à arquitetura de exportação Base64.

---

## A distinção central: operadores vs. participantes de reunião

Antes de detalhar as camadas técnicas, é necessário estabelecer uma distinção conceitual que organiza toda a modelagem de dados.

O P2D já possui `tenant_users` — as pessoas que **operam o sistema**: rodam o pipeline, gerenciam reuniões no Supabase, acessam o Streamlit. Esses são os engenheiros, analistas e gestores do projeto interno.

Os **participantes de uma reunião** são pessoas diferentes: clientes, auditores, gestores externos, membros técnicos — as pessoas que aparecem *na transcrição*. Eles nunca logam no Streamlit. Precisam existir num cadastro de referência para que o gerador de ata saiba: "quando 'Maria de Fátima' aparecer na transcrição, usar iniciais MF, cor `#0B1E3D`, área Auditoria".

A granularidade correta é **por reunião**, não por projeto — quem *esteve presente naquela reunião específica* determina os chips da ata. O projeto apenas fornece o roster de referência — o universo de quem *pode* participar — a partir do qual cada reunião faz seu recorte.

---

## Camada 1 — Dados: Roster e Participantes de Reunião

### Duas tabelas novas no Supabase

```sql
-- Roster: universo de pessoas que podem aparecer em reuniões de um projeto
CREATE TABLE project_roster (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  initials     TEXT NOT NULL,        -- "MF", "JL", "NC", "PG"
  full_name    TEXT NOT NULL,        -- "Maria de Fátima Duarte Moura"
  area         TEXT,                 -- "Auditoria", "DTI/SOLCORP"
  color_hex    TEXT NOT NULL,        -- "0B1E3D" (sem #, padrão ATA Engine)
  name_aliases TEXT[],               -- ["Maria", "Fátima", "MF"] — variações na transcrição
  is_active    BOOLEAN DEFAULT TRUE,
  created_at   TIMESTAMPTZ DEFAULT now(),
  UNIQUE (project_id, initials)
);

-- Participantes de reunião: quem esteve presente em cada reunião específica
CREATE TABLE meeting_participants (
  meeting_id   UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
  roster_id    UUID NOT NULL REFERENCES project_roster(id) ON DELETE CASCADE,
  confirmed    BOOLEAN DEFAULT TRUE,  -- FALSE = mencionado mas presença duvidosa
  PRIMARY KEY (meeting_id, roster_id)
);

CREATE INDEX idx_roster_project       ON project_roster(project_id);
CREATE INDEX idx_mp_meeting           ON meeting_participants(meeting_id);
CREATE INDEX idx_mp_roster            ON meeting_participants(roster_id);
```

### Por que duas tabelas

`project_roster` é o cadastro permanente. Muda raramente — quando entra alguém novo no projeto. Carrega toda a informação de identidade visual (iniciais, cor, área, aliases).

`meeting_participants` é o recorte por reunião. Responde à pergunta: "quem estava presente *nessa* reunião?" — determinado automaticamente pelo `AgentMinutes` ao extrair participantes da transcrição, cruzando com o roster.

```
project_roster            meeting_participants       meetings
──────────────            ────────────────────       ────────
MF · Maria de Fátima ──►  meeting X → MF ◄────────── X · 2026-03-10
JL · João Luís       ──►  meeting X → JL
NC · Natasha         ──►  meeting X → NC
PG · Pedro           ──►   (Pedro faltou à reunião X)
                     ──►  meeting Y → PG ◄────────── Y · 2026-03-20
```

### Lógica de matching: transcrição → roster

O `AgentMinutes` extrai nomes como aparecem na transcrição — às vezes "Maria", às vezes "MF", às vezes "Fátima". O campo `name_aliases` viabiliza o casamento automático:

```python
def match_participant(name_from_transcript: str, roster: list[dict]) -> dict | None:
    name_lower = name_from_transcript.lower().strip()
    for person in roster:
        candidates = [
            person["full_name"].lower(),
            person["initials"].lower(),
        ] + [a.lower() for a in (person["name_aliases"] or [])]
        if any(name_lower in c or c in name_lower for c in candidates):
            return person
    return None
```

Quando não há correspondência — participante externo, convidado eventual — o sistema cria um registro temporário com cor neutra (`8496B0`, o `--muted` do ATA Engine) e iniciais geradas automaticamente a partir do nome. Esses registros não são persistidos no roster a menos que o operador confirme.

### Seed para o projeto SDEA

```sql
INSERT INTO project_roster (project_id, initials, full_name, area, color_hex, name_aliases)
VALUES
  ('<sdea-uuid>', 'MF', 'Maria de Fátima Duarte Moura', 'Auditoria',   '0B1E3D',
   ARRAY['Maria', 'Fátima', 'MF', 'Maria de Fátima']),
  ('<sdea-uuid>', 'JL', 'João Luís F. Chaves',          'Auditoria',   '1A4B8C',
   ARRAY['João', 'João Luís', 'JL']),
  ('<sdea-uuid>', 'NC', 'Natasha Cristine Costa',        'DTI/SOLCORP', '1A7F5A',
   ARRAY['Natasha', 'NC']),
  ('<sdea-uuid>', 'PG', 'Pedro Gentil R. O. Soares',     'DTI/SOLCORP', 'C97B1A',
   ARRAY['Pedro', 'PG']);
```

### Convenção de cores (herdada do ATA Engine)

Participantes da **área cliente** (Auditoria, cliente externo) → tons escuros: `#0B1E3D` navy, `#1A4B8C` blue.  
Participantes da **equipe interna** (DTI/SOLCORP) → tons médios: `#1A7F5A` green, `#C97B1A` amber, `#6B3FA0` purple.

### Funções a adicionar em `core/project_store.py`

```python
def get_project_roster(project_id: str) -> list[dict]:
    """Retorna todos os membros ativos do roster de um projeto."""

def get_meeting_participants(meeting_id: str) -> list[dict]:
    """Retorna participantes confirmados de uma reunião (join com roster)."""

def save_meeting_participants(meeting_id: str, participants: list[dict]) -> None:
    """Persiste a lista de participantes inferida pelo AgentMinutes."""

def upsert_roster_member(project_id: str, member: dict) -> dict:
    """Cria ou atualiza um membro no roster."""
```

### O que o P2D ganha além da ata

Com `project_roster` e `meeting_participants` populados, o Assistente RAG ganha queries novas sem custo extra — `get_meeting_participants(meeting_number)` passa a retornar dados ricos com área e cor; consultas como "quem participou de todas as reuniões do projeto" ou "quais reuniões o Pedro não esteve" se tornam JOINs triviais.

---

## Camada 2 — Gerador: `modules/ata_engine_generator.py`

Este módulo é o coração da integração. Ele consome `MinutesModel` + dados do roster e emite um HTML standalone no padrão exato do ATA Engine — mesmo CSS, mesmo JS, mesma arquitetura de exportação.

### Interface pública

```python
def generate_ata_html(
    minutes: MinutesModel,
    project_id: str,
    meeting_id: str,
    project_slug: str,          # ex: "sdea", "p2d"
    meeting_date: date,
    local: str = "Videoconferência",
    next_meeting: str = "",
    next_meeting_detail: str = "",
) -> str:
    """
    Retorna HTML string pronto para salvar como ATA-{SLUG}-{DATA}.html.
    Consulta o Supabase para roster e meeting_participants.
    Chama build_b64 internamente para embutir o __src__.
    """
```

### Mapeamento MinutesModel → estrutura HTML

| Campo em `MinutesModel` | Elemento no HTML ATA Engine |
|---|---|
| `participants` | `.part-chip` na sidebar + `.participant-chip` no hero strip |
| `agenda_items` / `topics` | `.topic-card[data-topic="N"]` |
| `decisions` | `<li>` dentro do `.topic-body` do tópico correspondente |
| `action_items` | Array `ORIGINAL` no bloco JS (tabela de pendências) |
| `meeting_date` + `start_time` | Hero info-cards + constantes de localStorage |
| `project` | `<title>`, badge no hero |
| `summary` | Primeiro tópico ou nota introdutória (opcional) |

### Mapeamento de action_items

```python
original_items = []
for i, item in enumerate(minutes.action_items):
    original_items.append({
        "id":     i + 1,
        "desc":   item.description,
        "resp":   item.responsible or "—",
        "prazo":  item.deadline or "A definir",
        "status": "open"
    })
```

### Chaves de localStorage

Geradas deterministicamente a partir do slug e da data — sem ambiguidade entre reuniões:

```python
slug  = project_slug.lower()
y, m, d = meeting_date.year, f"{meeting_date.month:02d}", f"{meeting_date.day:02d}"

STORAGE_KEY          = f"{slug}_{y}_{m}_{d}_v1"
STORAGE_KEY_META     = f"{slug}_{y}_{m}_{d}_meta"
STORAGE_KEY_COMMENTS = f"{slug}_{y}_{m}_{d}_comments"
```

### Chips de participante

O gerador produz os chips **exclusivamente a partir dos participantes presentes na reunião** (tabela `meeting_participants`), não do roster completo. Isso garante que a ata reflita exatamente quem esteve presente — assim como o ATA Engine faz hoje.

```python
def _render_sidebar_chips(participants: list[dict]) -> str:
    """Gera os .part-chip da sidebar. Os chips do modal são derivados automaticamente."""
    chips = []
    for p in participants:
        chips.append(f"""
        <button class="part-chip" data-initials="{p['initials']}" data-color="{p['color_hex']}">
          <span class="part-initials" style="background:#{p['color_hex']}">{p['initials']}</span>
          <span class="part-name">{p['full_name'].split()[0]}</span>
          <span class="part-count" id="pcount-{p['initials']}">0</span>
        </button>""")
    return "\n".join(chips)
```

O modal de boas-vindas **não precisa ser alterado** — ele lê os `.part-chip` da sidebar dinamicamente, como no template de referência.

### Integração com build_b64

O módulo importa e chama `build_b64.py` diretamente, sem subprocess:

```python
# build_b64.py expõe: encode_b64(html_str), build(source_path)
# Para uso programático (sem arquivo em disco):
from build_b64 import encode_b64, NEW_EXPORT_JS, SNAPSHOT_RESTORE_JS

def _embed_b64_source(html_str: str) -> str:
    """Emite o HTML final com __src__ Base64 embutido — equivalente ao build_b64.py."""
    b64 = encode_b64(html_str)
    src_block = f'<script id="__src__" type="text/plain">{b64}<' + '/script>'
    return html_str.replace("</head>", f"{SNAPSHOT_RESTORE_JS}\n{src_block}\n</head>", 1)
```

### Regras de código que o gerador deve obedecer

Herdadas do ATA Engine — obrigatórias para a exportação funcionar:

1. Nunca escrever `</script>` literal dentro de um bloco `<script>`. Sempre usar `'<' + '/script>'`.
2. O Base64 em `__src__` deve ser do HTML *antes* de receber o `__src__` — sem circularidade.
3. O `__snapshot_restore__` deve rodar *antes* do script principal (posicionado no `<head>`).
4. Contadores de participante nos chips usam `DM Sans`, não `JetBrains Mono`.

---

## Camada 3 — Pipeline e UI: integração no Streamlit

### Integração no Orchestrator

Em `agents/orchestrator.py`, após `AgentMinutes` concluir com sucesso:

```python
if run_minutes and hub.minutes.ready:
    from modules.ata_engine_generator import generate_ata_html
    try:
        hub.minutes.ata_html = generate_ata_html(
            minutes      = hub.minutes,
            project_id   = config.get("project_id", ""),
            meeting_id   = config.get("meeting_id", ""),
            project_slug = config.get("project_slug", "p2d"),
            meeting_date = hub.meta.meeting_date or date.today(),
            local        = config.get("meeting_location", "Videoconferência"),
        )
    except Exception as e:
        hub.minutes.ata_html = ""
        hub.minutes.ata_html_error = str(e)
    hub.bump()
```

Adicionar ao `MinutesModel`:
```python
ata_html:       str = ""
ata_html_error: str = ""
```

Com guard em `KnowledgeHub.migrate()`:
```python
if not hasattr(hub.minutes, "ata_html"):
    hub.minutes.ata_html = ""
if not hasattr(hub.minutes, "ata_html_error"):
    hub.minutes.ata_html_error = ""
```

### UI no Streamlit: aba Ata de Reunião

Em `ui/tabs/minutes_tab.py`, adicionar seção logo acima ou abaixo dos downloads existentes:

```python
if hub.minutes.ata_html:
    with st.expander("📄 Ata Interativa — ATA Engine", expanded=True):
        st.caption(
            "HTML standalone com comentários por participante, "
            "tabela de pendências editável e exportação encadeável (file://)."
        )
        fname = f"ATA-{project_slug.upper()}-{meeting_date:%Y-%m-%d}.html"
        st.download_button(
            label    = "⬇️ Baixar HTML Interativo",
            data     = hub.minutes.ata_html.encode("utf-8"),
            file_name= fname,
            mime     = "text/html",
            key      = "dl_ata_html"
        )
elif hub.minutes.ata_html_error:
    st.warning(f"Não foi possível gerar a ata interativa: {hub.minutes.ata_html_error}")
```

### UI de cadastro do roster

Em **Configurações → Projeto**, nova aba "👥 Participantes":

- Tabela editável com os membros do roster do projeto ativo
- Botão "+ Adicionar participante" abre form: nome completo, iniciais, área, color picker, aliases
- Ao salvar, chama `upsert_roster_member()` via `project_store`
- Color picker sugere as cores padrão do ATA Engine como swatches: navy, blue, green, amber, purple

### Configuração do projeto: campos novos

Ao criar ou editar um projeto no P2D, adicionar campos:

```python
project_slug: str   # ex: "sdea" — usado nas chaves de localStorage da ata
meeting_location: str = "Videoconferência"  # default para o hero da ata
```

Esses campos alimentam `generate_ata_html()` via `config` no Orchestrator.

---

## Arquivos a criar/copiar no repositório do P2D

| Ação | Arquivo | Observação |
|---|---|---|
| Copiar sem alteração | `build_b64.py` | Script genérico do ATA Engine |
| Criar | `modules/ata_engine_generator.py` | Gerador HTML — núcleo da integração |
| Modificar | `agents/orchestrator.py` | Chamar gerador após AgentMinutes |
| Modificar | `core/knowledge_hub.py` | Campos `ata_html`, `ata_html_error` em MinutesModel |
| Modificar | `ui/tabs/minutes_tab.py` | Botão de download do HTML interativo |
| Modificar | `core/project_store.py` | Funções de roster e meeting_participants |
| Modificar | `pages/Settings.py` | Aba de cadastro de participantes |
| SQL | migration_roster.sql | DDL das duas novas tabelas |

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| `AgentMinutes` não separa tópicos de forma granular | Usar `agenda_items` como skeleton; agrupar decisões e ações por tópico via matching de keywords. Fallback: um tópico único "Pontos Discutidos" |
| Nome na transcrição não casa com nenhum alias do roster | Criar participante temporário com cor `--muted` (`8496B0`). Operador pode promover ao roster depois |
| Streamlit Cloud sem `node` para `gerar_docx.mjs` | Manter `.docx` gerado pelo `minutes_exporter.py` existente. O `.mjs` fica disponível para uso local |
| Template HTML do ATA Engine evolui neste projeto | Versionar o template embutido no `ata_engine_generator.py`. Atualizar manualmente ao haver breaking changes no CSS/JS |
| `build_b64.py` chamado sobre HTML já buildado | O script é idempotente — remove `__src__` e `__snapshot__` anteriores antes de re-injetar |

---

## Convenção de nomenclatura de arquivos gerados

```
ATA-{SLUG}-{ANO}-{MÊS}-{DIA}.html                          → gerado pelo P2D, buildado
ATA-{SLUG}-{ANO}-{MÊS}-{DIA}_compartilhado_{DATA}.html     → exportado pelo participante
ATA-{SLUG}-{ANO}-{MÊS}-{DIA}.docx                          → via minutes_exporter.py
```

Exemplo para reunião SDEA de 17 de março de 2026:
```
ATA-SDEA-2026-03-17.html
ATA-SDEA-2026-03-17_compartilhado_2026-03-18.html
ATA-SDEA-2026-03-17.docx
```

---

## Resumo executivo

A integração se apoia em três decisões de arquitetura:

**Dados:** separar o roster do projeto (quem *pode* participar, com suas cores e aliases) dos participantes de cada reunião (quem *esteve presente*). Essa separação garante atas corretas sem impor uma lista fixa, e viabiliza o matching automático nome-por-nome a partir da transcrição.

**Gerador:** um único módulo Python (`ata_engine_generator.py`) que conhece o design system e a arquitetura de exportação do ATA Engine e traduz `MinutesModel` para HTML — isolando o P2D de qualquer detalhe de implementação do ATA Engine.

**Pipeline:** a geração da ata interativa acontece automaticamente como etapa final do `AgentMinutes`, sem nenhuma interação extra do operador. O resultado aparece como botão de download na aba "Ata de Reunião" do Streamlit, ao lado dos formatos já existentes (Markdown, Word, PDF).

O `build_b64.py` é copiado sem alteração — ele é genérico por design e garante a cadeia de exportação encadeável que é o requisito central do ATA Engine.

---

*Equipe de Soluções Corporativas — FGV/DTI/SOLCORP · Maio 2026*
