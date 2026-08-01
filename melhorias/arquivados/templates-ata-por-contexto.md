# Plano de Melhoria: Modelos (Templates) de Ata por Contexto

## 1. Objetivo

Permitir que cada **contexto** (projeto/iniciativa — ex: SDEA) registre seu próprio modelo de ata em Word, e que a geração de ata para reuniões daquele contexto siga esse modelo — em vez do layout genérico único que o sistema usa hoje para todos os contextos. Do modelo em Word também deve ser derivado um modelo equivalente em Markdown.

**Decisões já tomadas (2026-07-08):**
- Template **só no nível de contexto** — sem nível de domínio/tenant, para simplificar (decisão do usuário; a coluna `tenant_id` fica fora do escopo desta melhoria).
- Só quem for **admin ou master** (papel global já existente — `is_admin()`) pode configurar o template de um contexto. O projeto não tem hoje uma role de "admin restrito a um contexto"; se isso vier a ser necessário, é uma melhoria de RBAC separada.
- Segue a **Fase 1** (modelo declarativo), mas com escopo ampliado: além de estrutura/cor, extrai também **logo, imagem de fundo e demais elementos visuais de identidade** do `.docx` de referência.
- Detecção de estilo **automática** (sem formulário manual de cor/estilo).

Escopo desta primeira fase: **apenas ata**. Relatório executivo e outros artefatos ficam para uma fase futura, reaproveitando a mesma arquitetura.

---

## 2. Estado atual (o que já existe — verificado no código, não suposto)

### 2.1. Hierarquia de domínio/contexto já existe, em 2 níveis (para referência — não usada nesta melhoria)

- **`tenants`** (`setup/supabase_schema_tenant_auth.sql`) — é literalmente o "domínio" do pedido original: `domain_slug` (ex: `"fgv"`), `display_name`, `active`. Já é a tela de login multi-tenant.
- **`contexts`** (`setup/supabase_schema.sql` + `migrate_v4_21_context.sql`) — é o "contexto" (ex: SDEA), o único nível usado por esta melhoria: `id`, `name`, `sigla`, `context_type`, e já tem uma coluna `skill_md` (ver 2.2).
- **Gap encontrado, fora do escopo desta melhoria mas registrado**: `core/project_store.py::list_contexts`/`create_context` já leem/escrevem `contexts.tenant_id`, mas **nenhuma migration versionada em `setup/` cria essa coluna** — deve ter sido adicionada direto no Supabase, fora do controle de versão. Não bloqueia esta melhoria (que não usa `tenant_id`), mas vale corrigir num momento oportuno.

### 2.2. Já existe um mecanismo de "conhecimento por contexto" — o CKF

- `contexts.skill_md` (uma coluna de texto livre) + `context_files` (tabela de arquivos de referência, só texto extraído — HTML/PPTX/PDF/TXT/MD, **sem suporte a `.docx` hoje**).
- `core/project_store.py::get_context_skill()`/`get_context_files_text()` são lidos em `pages/Pipeline.py` e injetados no prompt de **todo agente**, inclusive `AgentMinutes` (`agents/agent_minutes.py::build_prompt()`, linhas ~239-243):
  ```python
  system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill}"
  system += f"\n\n## Documentos de Referência do Contexto\n\n{hub.context_files_text}"
  ```
- Isso já prova o padrão de "customização por contexto injetada no prompt" — a melhoria de template vai **reaproveitar exatamente esse ponto de injeção**, não inventar um novo.
- **Por que não usar `skill_md`/`context_files` diretamente para o template?** Porque ambos descartam formatação binária por design (`context_files.content_text` é só texto extraído). Um modelo em Word carrega fonte, cor, logo, cabeçalho/rodapé — perdido nesse caminho. Precisa de tabela própria.

### 2.3. Como a ata é gerada hoje

```
AgentMinutes (LLM) → JSON estruturado → MinutesModel → hub.minutes.minutes_md
                                              │
                                              ├─→ modules/minutes_exporter.py::to_docx()  (Word)
                                              ├─→ modules/minutes_exporter.py::to_pdf()   (PDF)
                                              └─→ modules/minutes_exporter.py::to_html()  (HTML)
```

- O prompt do `AgentMinutes` (`skills/skill_minutes.md`) dita **conteúdo** (quais seções extrair), nunca **formatação** (fonte/cor/ordem de seção/logo) — isso é decidido só na hora de exportar.
- `to_docx()` constrói o `.docx` programaticamente via `python-docx`, com ordem de seção e paleta de cores **fixas no código** (`NAVY = 0x0B1E3D`, `ACCENT = 0x2E7FD9`): Título → Participantes → Pauta → Resumo → Decisões → Encaminhamentos (tabela) → Próxima Reunião → Rodapé.
- `to_docx()`/`to_pdf()`/`to_html()` são **três implementações independentes**, cada uma com sua própria lógica de seção — um template que só valha para Word deixaria PDF/HTML fora de sincronia (aceitável nesta fase, já que o pedido é especificamente Word, mas vale registrar).

### 2.4. Não existe hoje nenhum mecanismo de armazenar arquivo binário

Toda ingestão de arquivo no projeto (`context_files`, `meeting_documents`) extrai **só texto**, nunca guarda os bytes originais. Não há bucket do Supabase Storage em uso em lugar nenhum do código. `modules/ingest.py::load_transcript()` já sabe abrir `.docx` via `python-docx`, mas descarta toda formatação (só concatena texto de parágrafos/tabelas) — é a ferramenta certa para "ler o texto de um Word", errada para "preservar a formatação de um Word".

---

## 3. Decisão de arquitetura — Fase 1 ampliada (estrutura + estilo + identidade visual)

A pergunta central era: **"seguir o modelo" significa preservar a formatação exata do arquivo Word enviado, ou seguir a estrutura/estilo dele?** Decisão do usuário: Fase 1 (documento construído do zero pelo `python-docx`, não merge no arquivo original), mas **incluindo logo/imagem de fundo/elementos de identidade** extraídos do `.docx` de referência — não só cor e ordem de seção.

### Fase 1 — Modelo declarativo com identidade visual

1. Admin/master faz upload de um `.docx` de referência para o contexto.
2. O sistema **lê a estrutura** do documento via `python-docx` (títulos/estilos de parágrafo, ordem, cores de heading) e deriva:
   - um **esqueleto em Markdown** (`## Participantes`, `## Decisões`, etc. — na mesma ordem e com os mesmos nomes de seção do Word enviado);
   - uma **especificação de estilo** (JSON: cor de destaque, ordem de seções);
   - **imagens de identidade** — todo elemento gráfico encontrado no cabeçalho, rodapé e corpo do documento (logo, ícones, imagem de fundo/marca d'água quando presente). Ver nota técnica abaixo sobre os limites dessa extração.
3. O `.docx` original também é guardado (bytes, base64) — não pra merge automático nesta fase, mas pra: (a) o usuário conseguir baixar/conferir o que foi enviado, (b) servir de base pra uma eventual Fase 2 (fidelidade total, fora de escopo aqui) sem precisar pedir upload de novo.
4. Na geração da ata:
   - o esqueleto Markdown é injetado no prompt do `AgentMinutes`, no **mesmo ponto de injeção do CKF** (`hub.context_skill`) — o LLM passa a nomear/ordenar as seções como no modelo do contexto;
   - `to_docx()` ganha um parâmetro opcional `template_spec` (ordem de seção, cor de destaque, imagens de identidade) que sobrepõe os valores fixos atuais — o logo é inserido no cabeçalho do documento gerado, outras imagens no rodapé/corpo conforme onde foram encontradas no original.
5. **Resultado**: a ata gerada segue a estrutura, a cor e carrega o logo/identidade visual do modelo do contexto — mas continua sendo um documento novo, construído pelo `python-docx`, não o arquivo original com conteúdo inserido dentro.

**Nota técnica sobre "imagem de fundo"**: existem duas coisas diferentes com esse nome no Word — (a) uma imagem no cabeçalho/rodapé (comum para logo/identidade — `python-docx` acessa isso via as partes de relacionamento do cabeçalho/rodapé, com suporte razoável) e (b) um "plano de fundo de página" de verdade (recurso legado baseado em VML, sem API de alto nível no `python-docx`, exigiria manipulação direta do XML). A extração trata (a) com boa confiabilidade; (b) é tentada de forma *best-effort* — se não for detectável com segurança, o sistema segue sem ela, sem quebrar o restante da extração.

**Esforço**: médio-alto (a extração/reinserção de imagens é o item que mais eleva o esforço em relação ao plano original). **Risco**: baixo-médio — ainda não introduz merge de documento nem Storage bucket (imagens cabem em base64 no Postgres, junto do `.docx` original), mas manipulação de imagens via OOXML tem mais variação real-world do que texto/cor.

### Fase 2 — Fidelidade total (futuro, se a Fase 1 não for suficiente)

Abrir o `.docx` enviado como o documento-base e **inserir o conteúdo gerado dentro dele** (em vez de construir um documento novo do zero), preservando logo, cabeçalho/rodapé e estilos exatos do arquivo original. Exige:
- Convenção de marcação no `.docx` de referência (ex: um parágrafo/bookmark `{{PARTICIPANTES}}` por seção) que o usuário precisa seguir ao criar o modelo;
- Lógica de "encontrar o marcador e substituir por conteúdo formatado" via `python-docx` (não existe hoje, é a parte genuinamente nova/arriscada);
- Guardar o `.docx` em bytes é **pré-requisito** já coberto pela Fase 1 — não desperdiça trabalho.

**Esforço**: alto. **Risco**: médio-alto (mail-merge em Word via python-docx é notoriamente cheio de detalhes — preservar `runs`/estilos ao substituir texto não é trivial). Só vale a pena se a Fase 1 não atender (ex: cliente exige o logo/cabeçalho corporativo pixel-perfeito).

**Recomendação**: implementar a Fase 1 primeiro, validar com um contexto real (ex: SDEA), decidir sobre a Fase 2 com base no que realmente faltar.

---

## 4. Modelo de dados proposto (Fase 1)

Duas tabelas — `ata_templates` (um por contexto) + `ata_template_assets` (N imagens por template, já que logo/fundo/outros elementos são, em geral, mais de um arquivo). Segue o mesmo padrão de `context_files` (FK pra `contexts`, sem reinventar convenção):

```sql
CREATE TABLE IF NOT EXISTS ata_templates (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id        UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,                 -- rótulo pro usuário, ex: "Modelo padrão SDEA"
    docx_filename     TEXT NOT NULL,
    docx_base64       TEXT NOT NULL,                 -- bytes do .docx original, base64
    template_markdown TEXT,                          -- esqueleto derivado (## Seção na ordem do Word)
    style_spec        JSONB,                          -- {"accent_color": "...", "section_order": [...]}
    is_active         BOOLEAN NOT NULL DEFAULT true,   -- permite desativar sem apagar
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        TEXT
);

-- Um contexto tem no máximo um template ativo por vez (regra de negócio, não FK):
CREATE UNIQUE INDEX IF NOT EXISTS idx_ata_templates_context_active
    ON ata_templates (context_id) WHERE is_active;

CREATE TABLE IF NOT EXISTS ata_template_assets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id   UUID NOT NULL REFERENCES ata_templates(id) ON DELETE CASCADE,
    asset_type    TEXT NOT NULL,     -- 'logo' | 'background' | 'header_image' | 'footer_image' | 'other'
    origin        TEXT NOT NULL,     -- 'header' | 'footer' | 'body' | 'page_background' — de onde foi extraída
    image_base64  TEXT NOT NULL,
    mime_type     TEXT NOT NULL,     -- 'image/png' | 'image/jpeg' | ...
    width_px      INTEGER,
    height_px     INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Regra de resolução** quando uma reunião é processada: `contexto tem template ativo? usa o dele (estrutura + estilo + assets). senão, layout genérico atual (comportamento de hoje, sem mudança)` — importante para não quebrar nenhum contexto existente que nunca configurou nada.

---

## 5. Novos módulos/funções propostos

**Não como um `BaseAgent` (subclasse com LLM)** — a extração de estrutura/imagens do `.docx` e a aplicação do estilo são determinísticas, sem chamada de LLM nenhuma. Isso já tem precedente direto no projeto: `agent_mermaid.py` e `agent_validator.py` são "agentes" só de nome — pura lógica Python, sem `BaseAgent`, listados explicitamente como isentos do padrão PC83/PC84 no CLAUDE.md. Proponho seguir a mesma convenção:

- **`modules/ata_template_engine.py`** (novo módulo, mesmo espírito de `modules/minutes_exporter.py`):
  - `extract_template_from_docx(docx_bytes: bytes) -> tuple[str, dict, list[dict]]` — abre o `.docx` via `python-docx`, percorre parágrafos com estilo de heading (devolve `template_markdown` + `style_spec`) e percorre cabeçalho/rodapé/corpo em busca de imagens via as partes de relacionamento do documento (devolve lista de assets: bytes/mime/tipo/origem — ver tabela `ata_template_assets`). Extração de plano de fundo de página (VML) é best-effort, conforme nota técnica da seção 3.
  - `apply_template_to_docx(minutes: MinutesModel, style_spec: dict, assets: list[dict]) -> bytes` — wrapper fino sobre `modules/minutes_exporter.py::to_docx()`, repassando `template_spec` (assinatura de `to_docx` ganha um parâmetro novo opcional, retrocompatível — chamada sem o parâmetro continua gerando o layout genérico de hoje). O logo (asset tipo `logo`/`header_image`) é inserido no cabeçalho do documento gerado via `section.header`; demais imagens no rodapé/corpo conforme a origem registrada.
- **`core/project_store.py`** — novas funções CRUD, mesmo padrão de `save_context_file`/`get_context_files_text`:
  - `save_ata_template(context_id, name, docx_filename, docx_bytes, created_by)` — chama `extract_template_from_docx`, persiste o template e os assets extraídos numa operação; checa `is_admin()` antes de escrever (admin ou master, papel global).
  - `get_active_ata_template(context_id)` — resolve pela regra da seção 4 (contexto tem template ativo → retorna com assets já carregados; senão `None`).
  - `list_ata_templates(context_id)`, `delete_ata_template(template_id)`, `deactivate_ata_template(template_id)` — todas exigindo `is_admin()`.
- **`agents/agent_minutes.py::build_prompt()`** — passa a injetar `template_markdown` (quando existir) no mesmo bloco de "Conhecimento do Contexto", com uma instrução curta tipo *"Siga esta estrutura de seções na ata, na mesma ordem"*.
- **`pages/Pipeline.py`** — no ponto onde já carrega `context_skill`/`context_files_text` (linhas ~161-173), também carrega o template ativo (estrutura + estilo + assets) e guarda em `hub` (novo campo, ex: `hub.ata_template_spec`); na hora de salvar/exportar a ata em Word, repassa pra `to_docx()`.
- **UI**: um novo painel de configuração — mais natural em `pages/Settings.py` (que já tem a aba de configuração por contexto, incluindo CKF/`context_files`) do que uma página nova, visível só a admin/master: upload do `.docx`, preview do markdown derivado + miniaturas das imagens extraídas + cor detectada, botão "ativar"/"desativar".

---

## 6. Fluxo passo a passo (Fase 1)

1. Admin/master abre Settings → aba de contexto → "Modelo de Ata" → faz upload de um `.docx`.
2. `extract_template_from_docx()` roda, mostra preview do markdown derivado + cor de destaque detectada + miniaturas das imagens extraídas; admin confirma (ou descarta e tenta outro arquivo).
3. `save_ata_template()` persiste (template + assets); se já havia um template ativo pro mesmo contexto, o antigo é desativado (`is_active=False`), não apagado.
4. Próxima reunião processada nesse contexto: `Pipeline.py` carrega o template ativo junto do CKF, injeta o esqueleto Markdown no prompt do `AgentMinutes`.
5. Ao exportar em Word (Pipeline, Central de Artefatos, ou onde mais existir botão de export), `to_docx()` recebe `style_spec` + `assets` do template e ajusta cor/ordem de seção/logo.
6. Export em `.md`/`.pdf`/`.html` continuam no layout genérico atual nesta fase (fora de escopo — mencionado no pedido original só pra Word).

---

## 7. Riscos e limites conhecidos (sem perguntas em aberto — decisões já tomadas na seção 1)

- Extração de imagem de cabeçalho/rodapé é confiável; extração de "plano de fundo de página" (VML) é best-effort e pode não vir em todo `.docx` — não é um bug se não vier, é um limite conhecido do formato.
- `to_docx()` precisa manter retrocompatibilidade total: todo call site hoje (PC155/PC159) continua funcionando sem alteração se `template_spec` não for passado.
- Só Word nesta fase — `.md`/`.pdf`/`.html` seguem no layout genérico; ficam fora de sincronia visual quando um contexto tem template ativo (aceito, dado o pedido original ser especificamente sobre Word).

---

## 8. Critério de aceite (Fase 1)

- [ ] Migration das tabelas `ata_templates` + `ata_template_assets` executada e validada em produção.
- [ ] Upload de `.docx` extrai um esqueleto Markdown plausível (seções na ordem certa) e pelo menos o logo do cabeçalho, para pelo menos 2 documentos de teste reais com identidade visual diferente.
- [ ] Ata gerada para um contexto com template ativo usa a ordem de seção, cor de destaque e logo do template — ata gerada para um contexto SEM template continua idêntica ao comportamento de hoje (regressão zero).
- [ ] Só admin/master conseguem configurar/ativar/desativar um template — usuário comum não vê a opção ou recebe erro de permissão.
- [ ] `to_docx()` mantém retrocompatibilidade total quando chamado sem `template_spec` (todos os call sites existentes, incluindo os do PC155/PC159, continuam funcionando sem alteração).
- [ ] Testes automatizados cobrindo: extração de estrutura + imagens de um `.docx` de exemplo, resolução de template ativo (contexto com template / contexto sem template), `to_docx()` com e sem `template_spec`, checagem de permissão nas funções de escrita.

---

## 9. Estimativa de esforço

| Item | Esforço |
|---|---|
| Migration `ata_templates` + `ata_template_assets` | Baixo |
| `extract_template_from_docx()` — estrutura/estilo (texto) | Médio |
| `extract_template_from_docx()` — extração de imagens (logo/fundo) | Médio-alto (maior variação real-world; plano de fundo VML é best-effort) |
| `apply_template_to_docx()` / parametrizar `to_docx()` (inserir logo/imagens) | Médio |
| CRUD em `project_store.py` (com checagem `is_admin()`) | Baixo |
| Injeção no prompt do `AgentMinutes` | Baixo (reaproveita ponto existente) |
| UI em Settings.py (upload + preview de miniaturas) | Médio |
| Fase 2 (fidelidade total — merge no arquivo original) | Alto — fora de escopo desta melhoria, só mencionada para referência futura |

## 10. Próximo passo

Plano aprovado com as decisões da seção 1. Aguardando sinal para começar a implementação (sugestão: migration + `extract_template_from_docx()` primeiro, testado isoladamente com um `.docx` real do contexto SDEA, antes de integrar no pipeline e na UI).
