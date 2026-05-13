Aqui está o resumo do que foi produzido e as decisões relevantes em cada um.

---

### `migration_roster.sql`

Oito fases sequenciais em um único arquivo idempotente:

**Fases 1–2** criam `project_roster` e `meeting_participants` com todas as constraints — formato de iniciais (`^[A-Z]{1,4}$`), hex sem `#` (`^[0-9A-F]{6}$`), enum de `source` (`auto/manual/import`), `ON DELETE CASCADE` nas FKs para não deixar órfãos quando uma reunião ou projeto for excluído.

**Fase 3** adiciona `ata_slug` e `meeting_location` à tabela `projects` existente — os dois campos que o gerador de ata precisa e que hoje não existem em nenhum lugar do P2D.

**Fase 4** cria cinco índices: um parcial em `project_roster` filtrando `is_active = TRUE` (a query mais frequente), um GIN em `name_aliases` para busca por substring, e dois em `meeting_participants` para as queries de geração de ata e analytics.

**Fase 5** é o trigger `updated_at` automático. **Fase 6** é RLS compatível com o padrão já existente no P2D (leitura para autenticados, escrita via service_role). **Fase 7** é a função SQL `get_meeting_participants_full()` que faz o JOIN internamente — evita dois round-trips no Python ao gerar a ata. **Fase 8** é o seed do SDEA, comentado para não executar acidentalmente.

---

### `project_store_roster.py`

Doze funções organizadas em quatro grupos:

**Leitura do roster**: `get_project_roster`, `get_roster_member`, `get_roster_member_by_initials` — todas fail-open, retornam `[]` ou `None` sem levantar exceção.

**Escrita do roster**: `upsert_roster_member` valida formato antes de chegar no Supabase e levanta `ValueError` com mensagem clara — o caller na UI captura e exibe. `deactivate_roster_member` faz soft delete preservando o histórico de `meeting_participants`. `reorder_roster` atualiza `sort_order` em lote.

**Participantes de reunião**: `get_meeting_participants` chama a função RPC do Supabase para fazer o JOIN server-side. `save_meeting_participants` faz upsert em lote. `clear_meeting_participants` limpa antes de re-inferir.

**Matching e inferência**: `match_participant_to_roster` tem três passes — full_name exato, iniciais exatas, aliases por substring bidirecional. `infer_and_save_participants` é o ponto de entrada do pipeline: recebe os nomes extraídos pelo `AgentMinutes`, resolve contra o roster, persiste os confirmados e retorna participantes temporários para não-identificados com `sort_order: 999` para irem ao final dos chips.

**Analytics**: `get_participant_meeting_history` e `get_roster_attendance_summary` alimentam a seção de presença na UI.

---

### `settings_roster_tab.py`

Três seções verticais dentro da função `render_roster_tab()`:

**Tabela de membros**: cada linha tem modo visualização (badge colorido com iniciais, nome, área, hex com preview, aliases) e modo edição inline ativado pelo botão `✏️` — sem abrir modal, sem sair da página. O botão `🗑️` chama `deactivate_roster_member` (soft delete, não apaga). Ações visíveis apenas para admin, em linha com o RBAC já existente no P2D.

**Formulário de novo membro**: validação em tempo real no próprio formulário — o botão fica desabilitado enquanto houver erro, sem precisar de submit para saber que a sigla é inválida ou já existe. Os swatches clicáveis das seis cores padrão do ATA Engine preenchem o campo hex com um clique.

**Resumo de presença**: expander colapsado com `progress` bar por participante, mostrando quantas reuniões cada pessoa participou — alimentado por `get_roster_attendance_summary`.

O arquivo termina com um bloco de comentário mostrando exatamente onde e como encaixar a aba no `Settings.py` existente, incluindo os dois campos novos (`ata_slug`, `meeting_location`) que precisam aparecer na aba de projeto.
