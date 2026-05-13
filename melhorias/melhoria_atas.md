A ideia é utilizar uma criação de html para as atas geradas por nossa solução. 
Já temos um projeto em outra conta Claude que faz uma ata com precisaõ.

Segue o Claud.md desta solução:



---

## Modelagem no Supabase: Roster de Participantes

### O problema central

O P2D já tem `tenant_users` — mas esses são os *operadores do sistema*. Numa reunião de projeto, os participantes extraídos pela transcrição são pessoas diferentes: clientes, gestores externos, auditores. Eles nunca vão logar no Streamlit. Precisam existir num cadastro de referência apenas para que o gerador de ata saiba "quando aparecer 'Maria de Fátima' na transcrição, usar iniciais MF, cor #0B1E3D, área Auditoria".

### Duas tabelas novas

```sql
-- ─── 1. ROSTER: quem pode aparecer como participante em um projeto ──────────
CREATE TABLE project_roster (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  initials    TEXT NOT NULL,          -- "MF", "JL", "NC", "PG"
  full_name   TEXT NOT NULL,          -- "Maria de Fátima Duarte Moura"
  area        TEXT,                   -- "Auditoria", "DTI/SOLCORP"
  color_hex   TEXT NOT NULL,          -- "0B1E3D" (sem #)
  name_aliases TEXT[],                -- ["Maria", "Fátima", "MF"] — variações que podem aparecer na transcrição
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (project_id, initials)
);

-- ─── 2. MEETING_PARTICIPANTS: quem esteve presente em cada reunião ──────────
CREATE TABLE meeting_participants (
  meeting_id  UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
  roster_id   UUID NOT NULL REFERENCES project_roster(id) ON DELETE CASCADE,
  confirmed   BOOLEAN DEFAULT TRUE,  -- FALSE = mencionado na transcrição mas presença duvidosa
  PRIMARY KEY (meeting_id, roster_id)
);
```

### Por que duas tabelas e não uma

`project_roster` é o cadastro permanente — quem *pode* participar de reuniões daquele projeto. Muda raramente (quando entra alguém novo no projeto).

`meeting_participants` é o recorte por reunião — quem *esteve* naquela reunião específica. O `AgentMinutes` extrai os nomes da transcrição, o sistema cruza com o roster e popula essa tabela automaticamente. Um participante do roster que faltou à reunião simplesmente não aparece nos chips daquela ata.

```
project_roster          meeting_participants       meetings
──────────────          ────────────────────       ────────
MF · Maria de Fátima ──► meeting_id: X, MF ◄───── X · 2026-03-10
JL · João Luís       ──► meeting_id: X, JL
NC · Natasha         ──► meeting_id: X, NC
PG · Pedro           ──►   (Pedro faltou)
                     ──► meeting_id: Y, PG ◄───── Y · 2026-03-20
```

### A lógica de matching (AgentMinutes → roster)

O campo `name_aliases` é o que viabiliza o matching automático. O `AgentMinutes` extrai nomes como aparecem na transcrição — às vezes "Maria", às vezes "MF", às vezes "Fátima". O sistema percorre o roster e tenta casar:

```python
def match_participant(name_from_transcript: str, roster: list[dict]) -> dict | None:
    name_lower = name_from_transcript.lower().strip()
    for person in roster:
        # testa full_name, initials e todos os aliases
        candidates = [person["full_name"].lower(), person["initials"].lower()]
        candidates += [a.lower() for a in (person["name_aliases"] or [])]
        if any(name_lower in c or c in name_lower for c in candidates):
            return person
    return None
```

Quando não casa — participante externo, convidado eventual — o sistema cria um registro temporário com cor neutra (`#8496B0`, o `--muted` do design system) e iniciais geradas automaticamente a partir do nome.

### Índices recomendados

```sql
CREATE INDEX idx_roster_project ON project_roster(project_id);
CREATE INDEX idx_meeting_participants_meeting ON meeting_participants(meeting_id);
CREATE INDEX idx_meeting_participants_roster ON meeting_participants(roster_id);
```

### Como alimentar o roster

Duas formas, que coexistem:

**Via UI no Streamlit** — uma aba em Configurações → Projeto → "👥 Participantes" com um formulário simples: nome, iniciais, área, cor (color picker), aliases. Qualquer operador admin cadastra novos participantes quando o projeto tem entrada de uma pessoa nova.

**Via seed no primeiro setup do projeto** — quando um projeto é criado no P2D, o admin já pode colar a lista de participantes esperados. Para o SDEA, por exemplo, os quatro participantes são conhecidos desde o início.

### Integração com o gerador de ata

O fluxo completo na chamada `generate_ata_html()` fica assim:

```python
def generate_ata_html(minutes: MinutesModel, project_id: str, meeting_id: str, ...) -> str:

    # 1. Buscar roster do projeto
    roster = project_store.get_project_roster(project_id)

    # 2. Buscar participantes confirmados desta reunião
    #    (já populados pelo pipeline após AgentMinutes rodar)
    present = project_store.get_meeting_participants(meeting_id)

    # 3. Se meeting_participants ainda vazio, inferir do MinutesModel
    if not present:
        present = infer_and_save_participants(minutes.participants, roster, meeting_id)

    # 4. Gerar chips apenas para quem esteve presente
    chips = [roster_to_chip(p) for p in present]

    # 5. Montar HTML
    ...
```

### Migrations SQL completas

```sql
-- Fase A: criar tabelas
CREATE TABLE project_roster ( ... );
CREATE TABLE meeting_participants ( ... );

-- Fase B: seed SDEA (exemplo)
INSERT INTO project_roster (project_id, initials, full_name, area, color_hex, name_aliases)
VALUES
  ('<sdea-project-uuid>', 'MF', 'Maria de Fátima Duarte Moura', 'Auditoria',    '0B1E3D', ARRAY['Maria', 'Fátima', 'MF']),
  ('<sdea-project-uuid>', 'JL', 'João Luís F. Chaves',          'Auditoria',    '1A4B8C', ARRAY['João', 'João Luís', 'JL']),
  ('<sdea-project-uuid>', 'NC', 'Natasha Cristine Costa',        'DTI/SOLCORP',  '1A7F5A', ARRAY['Natasha', 'NC']),
  ('<sdea-project-uuid>', 'PG', 'Pedro Gentil R. O. Soares',     'DTI/SOLCORP',  'C97B1A', ARRAY['Pedro', 'PG']);
```

### O que o P2D ganha além da ata

Com `project_roster` e `meeting_participants` populados, o Assistente RAG ganha duas ferramentas novas sem custo extra:

- `get_meeting_participants(meeting_number)` já existe — agora retorna dados ricos (área, cor) em vez de só nomes extraídos da transcrição
- É possível perguntar "quem participou de todas as reuniões do projeto" ou "quais reuniões o Pedro não esteve" — queries triviais com JOIN entre as duas tabelas

Quer que eu escreva o DDL completo com constraints, o `project_store.py` atualizado com as funções de roster, e a UI de cadastro no Streamlit?
