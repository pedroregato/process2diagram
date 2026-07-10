# Plano de Melhoria: Promoção Explícita a Ativo de Negócio + Classificação em 3 Dimensões

## 1. Objetivo

Hoje, `pages/AtivosDeNegocio.py` lista **automaticamente** todo requisito, processo BPMN, termo/regra SBVR e ata que existe no projeto — não existe nenhum gesto do usuário que diga "isto é um ativo de negócio". O pedido desta melhoria muda essa premissa:

> Um artefato só é um **ativo de negócio** quando é **promovido** explicitamente. A promoção é a declaração de que aquele artefato tem **interesse para o negócio como um todo** — não é mais só "algo que a reunião gerou".

Quatro mudanças, todas pedidas pelo usuário:

1. **Promoção explícita** — deixa de existir listagem automática; um artefato só vira ativo quando alguém decide promovê-lo.
2. **Classificação em 3 dimensões + justificativa em texto, obrigatórias no momento da promoção**:
   - **Interesse para o Negócio** — Estratégico / Tático / Operacional (§3.1)
   - **Perspectiva** — área/departamento de negócio a que o ativo interessa — Marketing, Financeiro, Jurídico, etc. (§3.2)
   - **Classificação Formal** — taxonomia de 12 classes de Ativo de Negócio (AN-01..AN-12), baseada em ISO 55000/APQC PCF/BIZBOK/TOGAF (§3.3)
   - **Justificativa** — texto livre obrigatório: por que este ativo interessa ao negócio como um todo (§3.5)
3. **Escopo de origem ampliado** — hoje só artefatos do pipeline (requisitos/BPMN/SBVR/atas) podem ser ativos. A promoção passa a valer também para:
   - **Arquivos/documentos** enviados via `DocumentManager.py`;
   - **Conteúdo gerado sob demanda pelo Assistente** dentro de uma conversa (ex.: um relatório ou charter pedido no chat) — hoje isso é 100% efêmero (só existe como download no navegador).

Este documento é o **plano técnico**, para revisão antes de qualquer código ser escrito — não implementa nada.

---

## 2. Estado atual (verificado no código, não suposto)

Levantamento feito por leitura direta do código antes de propor qualquer solução (mesmo método já usado nas entregas anteriores desta área — PC164/PC165):

### 2.1. `asset_metadata` — tabela de governança (`setup/supabase_migration_asset_metadata.sql:9-28`)

```
id UUID PK · project_id UUID NOT NULL → contexts(id) · artifact_type TEXT NOT NULL ·
artifact_id UUID NOT NULL · status TEXT NOT NULL DEFAULT 'rascunho' · tags TEXT[] DEFAULT '{}' ·
owner TEXT · notes TEXT · created_at/updated_at TIMESTAMPTZ · created_by TEXT
UNIQUE (project_id, artifact_type, artifact_id) · RLS habilitado, sem policies neste arquivo
```

`status` é **texto livre** — `rascunho|ativo|arquivado` é só convenção da aplicação (`pages/AtivosDeNegocio.py:78`, `_STATUS_OPTIONS`), não é um `CHECK` no banco. `artifact_type` também é livre no banco; o filtro real está em `core/project_store.py::ASSET_TYPES_WITH_METADATA` (Python).

**Ponto central do problema:** a existência de uma linha em `asset_metadata` **não é** hoje a condição para um artefato aparecer na Central de Ativos. `list_all_business_assets()` (`core/project_store.py:4581-4720`) itera as tabelas de **origem** (`list_requirements_light`, `list_bpmn_processes`, `list_sbvr_terms`, `list_sbvr_rules`, `list_meetings`) e só **enriquece** cada item com a metadata se ela existir — se não existir, o item aparece do mesmo jeito, com metadata "vazia" (`status: "rascunho"` calculado em memória, nunca gravado). Ou seja: **todo requisito é hoje tratado como se já fosse um ativo**, sem nenhuma decisão humana. É exatamente isso que o usuário quer mudar.

Confirmado em `pages/AtivosDeNegocio.py:132-142` — o loop de renderização não checa nenhum "flag de promoção", só filtros de UI (tipo/busca/contexto):

```python
for artifact_type in _TYPE_META:
    if artifact_type not in selected_types:
        continue
    items = assets.get(artifact_type, [])
    ...
```

### 2.2. Documentos (`meeting_documents`, `setup/supabase_migration_documents.sql:98-115`)

```
id UUID PK · project_id TEXT NOT NULL · meeting_id UUID (opcional) · title TEXT NOT NULL ·
doc_type TEXT → document_types(code) · file_name TEXT · content_text TEXT · metadata JSONB ·
created_by TEXT · created_at/updated_at TIMESTAMPTZ
RLS desabilitado (diferente de asset_metadata)
```

Cada documento já tem um `id` UUID estável (gerado em `modules/document_store.py::upload_document`, linha ~89) — pode ser reaproveitado como `artifact_id` exatamente como requisito/BPMN já fazem hoje. **Único atrito real:** `meeting_documents.project_id` é `TEXT`, enquanto `asset_metadata.project_id` é `UUID` (FK para `contexts.id`) — mesmo valor, tipo de coluna diferente. Precisa de `::uuid`/cast explícito na hora de gravar, não é um bloqueio de design.

### 2.3. Conteúdo gerado pelo Assistente — não existe persistência hoje

Busca completa no repositório confirma: **nenhuma tabela guarda hoje um "resultado de conversa" do Assistente.** `gerar_deck_executivo()` e `gerar_project_charter()` (`core/tools/tools_executive_advanced.py:479` e `:572`) só retornam Markdown — nenhum `insert()`. `export_project_charter_docx()` (mesma linha ~699-736) converte para `.docx` e empurra os bytes para `st.session_state["_pending_file_download"]` — é só uma fila de download no navegador (`pages/Assistente.py:1698-1706`), nada vai para o Supabase. **Promover uma saída do Assistente exige criar persistência nova** — hoje, se o usuário fecha a aba, o conteúdo desaparece para sempre.

### 2.4. Já existe um vocabulário de áreas/departamentos — `modules/ner_extractor.py:79-93`

O extrator de entidades (usado para reconhecer atores/lanes em transcrições) já tem uma categoria `AREA` com um regex curado de nomes reais de departamento em português:

```python
r"\b(?:TI|RH|DHO|DP|Financeiro|Contabilidade|Comercial|Jurídico|Juridico|"
r"Operações|Operacoes|Auditoria|Marketing|Logística|Logistica|Compras|"
r"Suprimentos|Compliance|Governança|Governanca|Controladoria|"
r"Recursos\s+Humanos|Tecnologia\s+da\s+Informação|Tecnologia\s+da\s+Informacao)\b"
```

Hoje esse vocabulário só é usado para **extrair** menções de área em texto livre (alimenta `hub.nlp.actors`/entidades do Grafo de Conhecimento) — nunca foi usado como opções de um campo de classificação formal em nenhuma tela. É a base direta da "Perspectiva" proposta em §3.2 — reaproveitado, não reinventado.

### 2.5. `melhorias/cognicao-de-negocio.md` já previa isso, em formato mínimo

Etapa 5 do documento aprovado (linha 92): *"Promoção: Botão 'Promover a Ativo' em `Artefatos.py`. Criação: o usuário decide explicitamente o que vira ativo."* — este plano é a expansão técnica dessa etapa, agora com um requisito novo (classificação de interesse) e um escopo maior (documentos + conteúdo de chat) que o documento original não previa.

---

## 3. Proposta — Classificação em 3 Dimensões

As 3 dimensões são **independentes entre si** e independentes de `status` (`rascunho/ativo/arquivado`, ciclo de vida). `status` descreve **onde** o ativo está no seu ciclo; as 3 dimensões abaixo descrevem **por que**, **para quem** e **o que** ele é. Também são ortogonais a campos já existentes por tipo — ex. `requirements.priority` (alta/média/baixa) mede urgência de implementação, não relevância estratégica do ativo.

### 3.1. Interesse para o Negócio (já definido no plano original)

Único valor, obrigatório em toda promoção:

| Valor (banco) | Rótulo (UI) | Significado |
|---|---|---|
| `estrategico` | 🎯 Estratégico | Impacta objetivos/direção da organização como um todo — normalmente cruza múltiplos contextos/departamentos |
| `tatico` | 📐 Tático | Relevante para uma área/iniciativa específica, mas reutilizável além da reunião que o originou |
| `operacional` | ⚙️ Operacional | Interesse de negócio real, mas de escopo mais local/execução — ainda vale governar, mas não é prioridade de reuso cross-contexto |

### 3.2. Perspectiva (área/departamento de negócio)

**Multi-valor** (diferente de Interesse, que é único) — um mesmo ativo pode legitimamente interessar a mais de uma área ao mesmo tempo (ex.: um BPMN de "aprovação de despesas" interessa a Financeiro **e** Jurídico **e** Operações simultaneamente). Proposta: `TEXT[]`, mesmo formato de `tags`, mas com opções de um vocabulário fechado (multi-select, não texto livre) — para não virar uma segunda coluna de tags sem controle.

Vocabulário proposto, curado a partir do regex `AREA` já existente (§2.4), consolidando sinônimos (TI/Tecnologia da Informação, RH/Recursos Humanos) num único rótulo cada:

`Comercial · Compliance · Compras e Suprimentos · Contabilidade · Financeiro · Governança · Jurídico · Logística · Marketing · Operações · RH · TI/Tecnologia`

Lista **aberta a ajuste** — é a primeira proposta de consolidação, não uma lista fechada por mim sozinho.

**Por que multi-valor, não único (decisão fechada — ver §8.8):** cenários reais, não hipotéticos, do que o P2D já produz:

- **BPMN com múltiplas lanes** (o mais forte, porque já é assim estruturalmente no produto): um diagrama de "Aprovação de Despesas" tem lanes como Solicitante, Financeiro, Jurídico, Operações — cada lane já é uma unidade organizacional real (`CLAUDE.md`: "Lane names must be organizational units"). Um único `bpmn_process` promovido legitimamente pertence a várias dessas áreas ao mesmo tempo.
- **Regra SBVR de compliance com aplicação operacional**: "Toda contratação acima de R$ 50 mil requer 3 cotações" é uma regra de Jurídico/Compliance (formal), aplicada no dia a dia por Compras e Suprimentos, e auditada por Governança — 3 áreas com interesse legítimo e diferente sobre o mesmo ativo.
- **Documento de contrato de fornecimento de TI**: interessa a TI (especificação), Jurídico (cláusulas), Financeiro (pagamento) e Compras (aquisição) simultaneamente — nenhuma é "a dona única".
- **BMM de expansão estratégica**: Marketing (posicionamento), Financeiro (investimento/ROI), Jurídico (regulação do mercado-alvo) e Operações (capacidade de entrega) — um objetivo estratégico que atravessa a organização é o caso de uso central de "Interesse: Estratégico".

**O motivo decisivo:** se Perspectiva fosse valor único, um ativo promovido "desapareceria" das buscas de todas as áreas exceto a escolhida — contradiz diretamente a promessa central do §4 ("um requisito ou processo validado num projeto fica descobrível para os demais times"). Um Catálogo do Domínio que só deixa cada ativo pertencer a uma área reduz, em vez de aumentar, a descoberta cross-departamental que é o objetivo declarado desta melhoria.

### 3.3. Classificação Formal — taxonomia de Ativos de Negócio (12 classes, baseada em ISO 55000 / APQC PCF / BIZBOK / TOGAF)

**Substitui a proposta anterior deste plano ("Capital Intelectual", Humano/Estrutural/Relacional)** — aquela era um chute meu sem lastro em nenhum framework de referência. Você trouxe uma taxonomia completa (`ISO 55000` — gestão de ativos como atividade coordenada para realizar valor; `APQC PCF` — hierarquia de processos para benchmarking; `BIZBOK` — capacidades, fluxos de valor, informação e organização; `TOGAF` — negócio/dados/aplicações/tecnologia), com 12 classes de ativo de negócio. Adoto essa taxonomia como a "Classificação Formal" — é o vocabulário oficial que você recomendou (§9 do seu documento original).

| Código | Classe | No P2D hoje |
|---|---|---|
| AN-01 | Ativos Estratégicos | ✅ forte — BMM |
| AN-02 | Ativos de Capacidade | ⛔ sem artefato P2D correspondente hoje |
| AN-03 | Ativos de Processo | ✅ forte — BPMN |
| AN-04 | Ativos de Produto e Serviço | ⚠️ fraco — só indiretamente via requisitos de produto |
| AN-05 | Ativos de Informação e Dados | ✅ forte — SBVR Termos (subclasse "Taxonomias e ontologias" é literalmente vocabulário SBVR) |
| AN-06 | Ativos Digitais e Tecnológicos | ⚠️ fraco — só via documentos técnicos enviados (ARQ/API_SPEC/DER) |
| AN-07 | Ativos Documentais e Normativos | ✅ forte — Atas, SBVR Regras, documentos normativos |
| AN-08 | Ativos Contratuais e Relacionais | ✅ forte — documentos da categoria "Contratos e Acordos" |
| AN-09 | Ativos Organizacionais e Humanos | ⚠️ fraco — só via conhecimento tácito em debates IBIS |
| AN-10 | Ativos Financeiros e de Performance | ⛔ sem artefato P2D correspondente hoje (ROI-TR vive fora de `asset_metadata`) |
| AN-11 | Ativos de Governança, Risco e Conformidade | ✅ forte — DMN, contradições do Grafo de Conhecimento |
| AN-12 | Ativos de Conhecimento, IA e Automação | ✅ forte — conteúdo gerado pelo Assistente (Fase C) |

**Tabela de mapeamento por `artifact_type` do P2D** (proposta minha, a confirmar — a promoção continua manual/explícita, esta é só a sugestão que o formulário pode pré-marcar):

| `artifact_type` P2D | Classe(s) plausível(is) | Observação |
|---|---|---|
| `bpmn_process` | AN-03 | Mapeamento direto |
| `requirement` | AN-03 ou AN-04 | Depende se o requisito é de processo ou de produto/serviço — decisão manual |
| `sbvr_term` | AN-05 | Vocabulário/ontologia — mapeamento direto |
| `sbvr_rule` | AN-07 ou AN-11 | Regra formal escrita (Normativo) vs. regra de controle/compliance (Governança) — decisão manual |
| `meeting_minutes` | AN-07 | Ata é o exemplo literal de "Evidência" na subclasse Documental |
| `document` (Fase B) | varia por `document_types.category` — ver abaixo | Único tipo com **sugestão automática plausível**, não só manual |
| `assistant_artifact` (Fase C) | AN-12 | Conteúdo gerado por IA — mapeamento direto, é a própria definição da classe |
| `bmm` (somente-leitura) | AN-01 | Visão/missão/objetivos/estratégia — mapeamento direto |
| `dmn` (somente-leitura) | AN-11 | Tabela de decisão é mecanismo clássico de governança |
| `ibis` (somente-leitura) | AN-09 ou AN-01 | Conhecimento tácito de pessoas vs. decisão estratégica — decisão manual |
| `report` (somente-leitura) | AN-10 ou AN-01 | Painel gerencial vs. síntese estratégica — decisão manual |

**Achado que vale aproveitar na Fase B:** as 9 categorias já existentes em `document_types` (`setup/supabase_migration_documents.sql:23-92` — Iniciação e Planejamento, Requisitos, Processos, Governança, Análise de Negócio, Técnico, Qualidade, Contratos e Acordos, Normas e Políticas) têm correspondência quase direta com as classes AN:

| Categoria de `document_types` | Classe AN sugerida |
|---|---|
| Contratos e Acordos | AN-08 |
| Normas e Políticas | AN-07 |
| Governança | AN-11 |
| Técnico | AN-06 |
| Processos | AN-03 |
| Requisitos | AN-04 |
| Análise de Negócio | AN-01 |
| Qualidade | AN-03 |
| Iniciação e Planejamento | AN-01 |

Proposta: ao promover um **documento**, o formulário de promoção pré-seleciona a Classe com base nessa tabela (lida de `document_types.category`, já gravada em cada documento) — o usuário confirma ou troca, nunca é forçado. Nenhum outro `artifact_type` tem uma sugestão automática tão direta; para os demais, a decisão é manual desde o início (mesmo princípio já usado para Interesse — "usuário decide explicitamente").

**Sobre o nível "Domínio" do modelo hierárquico do seu documento (`Classe → Domínio → Tipo → Instância`):** não incluído neste plano. `Tipo` já existe como `artifact_type`, `Instância` já existe como `artifact_id` — só "Domínio" (ex.: "Gestão de Contratações", "Gestão Documental") seria genuinamente novo. Proponho **não criar uma coluna dedicada agora** — é conceitualmente diferente de Perspectiva (§3.2, que é área/departamento, não capacidade/domínio de processo) e adicionar uma 4ª dimensão de classificação arrisca fadiga de formulário na promoção. Fica registrado como evolução futura possível (reaproveitando `tags`, que já é texto livre, como paliativo se precisar antes disso).

**Sobre os metadados adicionais do seu documento (§5 — Custodiante, Usuários, Valor gerado, Processos/Sistemas/Dados associados, Criticidade, Risco, Controles, Ciclo de vida, Indicadores, Evidências):** revisão campo a campo, para não descartar nada silenciosamente:
- `Criticidade` (Alta/Média/Baixa) **não** vira campo novo — seria redundante com `business_interest` (Estratégico/Tático/Operacional), que já captura a mesma ideia de relevância/urgência.
- `Processos associados` / `Sistemas associados` / `Dados associados` já são cobertos pelas ferramentas de rastreabilidade que o P2D já tem (`mapa_rastreabilidade`, cadeia requisito→BPMN→SBVR→DMN) — não precisam duplicar como texto solto em `asset_metadata`.
- `Dono do ativo` / `Custodiante` — `owner` já existe em `asset_metadata`; a distinção dono-do-valor vs. responsável-técnico não é feita hoje e fica fora de escopo desta melhoria (não há hoje 2 papéis distintos modelados em nenhuma parte do produto).
- `Usuários`, `Valor gerado`, `Risco`, `Controles`, `Indicadores`, `Evidências` — sem campo dedicado nesta fase; `notes` (texto livre já existente) comporta isso informalmente até haver demanda real por um campo estruturado.
- `Status` com valores Planejado/Ativo/Suspenso/Obsoleto — o P2D já tem `status` com `rascunho/ativo/arquivado`; não proponho trocar um enum já em produção sem necessidade concreta, mas registro a alternativa caso você prefira alinhar aos termos do seu documento.

### 3.4. Referências técnicas desta classificação

| Framework | Papel nesta melhoria |
|---|---|
| ISO 55000 | Gestão de ativos como atividade coordenada para realizar valor — base conceitual do que conta como "ativo" |
| APQC PCF | Hierarquia de processos para benchmarking — inspira a relação Classe→Domínio→Tipo→Instância |
| BIZBOK | Separação entre capacidades, fluxos de valor, informação e organização — base das classes AN-02/AN-03/AN-05/AN-09 |
| TOGAF | Integração negócio/dados/aplicações/tecnologia — base da classe AN-06 |

### 3.5. Justificativa da Promoção (decisão fechada — ver §8.2)

Campo de texto livre, **obrigatório** em toda promoção — resposta à pergunta "por que este ativo interessa ao negócio como um todo?". Diferente das 3 classificações (valores controlados, para filtro/busca), a Justificativa é a explicação em prosa, curta, que fica registrada junto ao ativo — útil tanto para quem promove (força uma reflexão mínima antes de promover, evitando promoção por reflexo) quanto para quem descobre o ativo depois no Catálogo do Domínio (contexto de por que aquilo foi considerado relevante, sem precisar voltar à reunião de origem).

Distinto de `notes` (texto livre já existente, opcional, para observações gerais de qualquer natureza) — `promotion_justification` é especificamente a razão da promoção, capturada uma vez no momento em que ela acontece.

---

## 4. Proposta — o que "promover" significa tecnicamente

**Decisão de design central:** a partir desta melhoria, **existir uma linha em `asset_metadata` passa a SER a definição de "é um ativo de negócio"**. Não é mais um enriquecimento opcional de algo que já aparece de qualquer forma — é o próprio gatilho de inclusão na Central de Ativos.

Isso inverte a consulta de `list_all_business_assets()`: hoje ela varre as tabelas de origem e junta metadata por fora; passa a varrer `asset_metadata` (as linhas = os ativos promovidos) e, para cada uma, buscar os dados de exibição (título, data, contexto) na tabela de origem correspondente ao `artifact_type`. Mesmo princípio dos 9 tipos já mapeados hoje, só invertendo qual tabela é a "fonte de verdade" da listagem.

**"Despromover"** (decisão fechada — ver §8.5): **mantém histórico** — nunca apaga a linha de `asset_metadata`, move para `status='arquivado'` (valor que já existe). Um ativo arquivado sai da visão padrão da Central de Ativos (mesmo comportamento que `arquivado` já tem hoje), mas toda a classificação (Interesse/Perspectiva/Classificação Formal/Justificativa) e o histórico de quem promoveu/quando ficam preservados — reversível a qualquer momento (reativar = voltar `status` para `ativo`). O artefato de origem nunca é apagado em nenhum dos dois casos.

---

## 5. Modelo de dados proposto

### 5.1. `asset_metadata` — 6 colunas novas (migration aditiva, sem quebrar nada existente)

```sql
ALTER TABLE asset_metadata
  ADD COLUMN business_interest      TEXT NOT NULL DEFAULT 'operacional',
  ADD COLUMN business_perspective   TEXT[] NOT NULL DEFAULT '{}',
  ADD COLUMN formal_classification  TEXT,
  ADD COLUMN promotion_justification TEXT NOT NULL DEFAULT '',
  ADD COLUMN promoted_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN promoted_by            TEXT;

COMMENT ON COLUMN asset_metadata.business_interest IS
  'estrategico | tatico | operacional — validado na aplicação, não via CHECK (mesmo padrão de status)';
COMMENT ON COLUMN asset_metadata.business_perspective IS
  'multi-valor: comercial, compliance, compras_suprimentos, contabilidade, financeiro, governanca, juridico, logistica, marketing, operacoes, rh, ti — validado na aplicação';
COMMENT ON COLUMN asset_metadata.formal_classification IS
  'AN-01..AN-12 (taxonomia de Ativos de Negócio — ISO 55000/APQC PCF/BIZBOK/TOGAF, ver melhorias/promocao-ativos-negocio.md §3.3) — nullable, algumas classes ainda sem artefato P2D correspondente';
COMMENT ON COLUMN asset_metadata.promotion_justification IS
  'texto livre obrigatório em toda promoção nova — por que este ativo interessa ao negócio (§3.5); DEFAULT vazio só para não quebrar linhas já existentes em produção desde PC164/165';
```

`business_interest DEFAULT 'operacional'` e `business_perspective DEFAULT '{}'` cobrem as linhas **já existentes em produção** desde o PC164/165 (usuários que já editaram status/tags de algum artefato antes desta melhoria existir) — ficam automaticamente "promovidas" com classificação mínima, sem perda de dado, coerente com o princípio fail-open do projeto. `formal_classification` fica **nullable** (sem default forçado) — linhas antigas ficam sem essa dimensão até serem reclassificadas manualmente; a UI trata `NULL` como "não classificado", nunca quebra. `promotion_justification` segue o mesmo raciocínio: `DEFAULT ''` cobre linhas antigas (a exigência de preenchimento não-vazio é imposta em `promote_to_business_asset()`, não no banco, mesmo padrão de `business_interest`/`business_perspective`). Todas continuam texto livre (não `CHECK`), mesmo padrão de `status` — permite os valores de hoje e qualquer refinamento futuro sem nova migration.

### 5.2. `document` como novo `artifact_type` — sem migration nova

Só precisa entrar em `ASSET_TYPES_WITH_METADATA` (Python) e ganhar um bloco de leitura em `list_all_business_assets()`. `artifact_id = meeting_documents.id` (já existe, já é UUID).

### 5.3. Tabela nova — `assistant_artifacts` (conteúdo do Assistente passa a poder ser persistido)

```sql
CREATE TABLE assistant_artifacts (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,
  content_markdown TEXT NOT NULL,
  source_tool      TEXT,                 -- ex: 'gerar_project_charter', 'chat_export'
  meeting_id       UUID REFERENCES meetings(id) ON DELETE SET NULL,  -- opcional
  created_by       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_assistant_artifacts_project ON assistant_artifacts(project_id);
ALTER TABLE assistant_artifacts ENABLE ROW LEVEL SECURITY;
```

Mesma forma de `meeting_documents`/`asset_metadata` (RLS habilitado — **atenção**: `asset_metadata` foi criada com RLS ligado sem nenhuma policy neste projeto; se isso já causou fricção de leitura com a chave "publishable" do ambiente local, replicar o mesmo cuidado de configuração de policy/grant ao criar esta tabela, para não repetir o problema).

`artifact_type = "assistant_artifact"`, `artifact_id = assistant_artifacts.id`.

---

## 6. Fases de implementação propostas

Seguindo o mesmo padrão de entregas incrementais independentes já usado em `cognicao-de-negocio.md`:

### Fase A — Promoção explícita dos 5 tipos já existentes (requirement, bpmn_process, sbvr_term, sbvr_rule, meeting_minutes)
- Migration da §5.1.
- `core/project_store.py`: nova `promote_to_business_asset(project_id, artifact_type, artifact_id, business_interest, business_perspective, promotion_justification, formal_classification=None, owner=None, tags=None, notes=None, created_by=None)` (wrapper sobre `upsert_asset_metadata`, mas **exige** `business_interest`, `business_perspective` e `promotion_justification` não-vazios; `formal_classification` opcional, já que várias classes ainda não têm exemplo real no P2D — ver §3.3).
- `list_all_business_assets()` / `list_all_business_assets_for_domain()`: reescritas para partir de `asset_metadata` (ver §4).
- **Sem restrição de perfil** (§8.6, resolvido): qualquer usuário logado pode promover — mesmo nível de acesso que hoje já edita status/tags/owner na Central de Ativos. Sem gate de `is_admin()`. Motivo do usuário: o projeto ainda não tem perfis de usuário bem definidos além de admin/master globais; revisar quando (se) isso mudar.
- Componente de UI reutilizável (`ui/components/promote_asset.py`?) — botão "⭐ Promover a Ativo de Negócio" que abre um mini-formulário: seletor de Interesse (obrigatório, único) + multi-select de Perspectiva (obrigatório, ≥1) + seletor de Classificação Formal (opcional) + campo de Justificativa (obrigatório, texto livre) + owner/tags/notas opcionais — chama `promote_to_business_asset`.
- Esse componente é plugado em `pages/Artefatos.py`, nas abas Requisitos / BPMN / SBVR / Reuniões.
- **Promoção em lote** (§8.4, resolvido — elevada de "Fase D, não incluída" para dentro da Fase A): seleção múltipla (checkboxes) numa aba de `Artefatos.py`, com uma tela de revisão que lista **todos os itens do lote antes de confirmar** (título, tipo, reunião de origem — exigência explícita do usuário, nada é promovido sem o usuário ver a lista completa primeiro). A mesma classificação (Interesse/Perspectiva/Classificação Formal/Justificativa) é aplicada a todos os itens do lote de uma vez — refinamento individual continua possível depois, editando um ativo por vez na Central de Ativos.
- `pages/AtivosDeNegocio.py`: filtros por Interesse, Perspectiva e Classificação Formal (além dos já existentes); badges das 3 dimensões em cada card; mensagem de estado vazio explicando o novo modelo ("nenhum ativo promovido ainda — promova artefatos em Artefatos.py").
- **Transição:** projetos que já usam a página desde o PC164 vão ver a lista "esvaziar" (só artefatos com linha em `asset_metadata` aparecem — hoje quase nada tem linha real, porque a maioria nunca foi salva explicitamente) — mitigado pela promoção em lote acima, que permite recuperar a visibilidade perdida de forma deliberada, revisada, não automática.

### Fase B — Promoção de Documentos (`DocumentManager.py`)
- `document` entra em `ASSET_TYPES_WITH_METADATA`; bloco novo em `list_all_business_assets()`.
- Botão de promoção (mesmo componente da Fase A) na aba Biblioteca, por documento — Classificação Formal **pré-selecionada** a partir de `document_types.category` (tabela de §3.3), usuário confirma ou troca.
- Resolver o cast `TEXT → UUID` de `meeting_documents.project_id` (§2.2).

### Fase C — Promoção de conteúdo gerado pelo Assistente
- Migration da §5.3 (agora com `promotion_justification` incluído).
- `promote_assistant_output_to_asset(project_id, title, content_markdown, source_tool, business_interest, business_perspective, promotion_justification, formal_classification=None, meeting_id=None, ...)` — grava em `assistant_artifacts` **e** `asset_metadata` numa única chamada (atômica o quanto o Supabase client permitir; se uma falhar, não deixar órfão).
- **Escopo do que é promovível (§8.3, resolvido)** — não qualquer resposta do chat, e mais amplo que só "gera arquivo para download": o usuário definiu como escopo respostas que produzem **análises, pesquisas, gráficos ou relatórios** — não perguntas simples de consulta/lookup. Sinal técnico confirmado para decidir quais mensagens ganham o botão de promoção: mensagem cujo rastro de chamadas de tool inclui ao menos uma de um conjunto curado de tools de síntese (lista abaixo — refinável na implementação, a partir do uso real, ver nota de encerramento de §8) —
  - Prefixo `generate_` (os 13 gráficos Plotly do Assistente + `generate_ibis_map`, `generate_next_agenda`);
  - Prefixo `gerar_` (`gerar_deck_executivo`, `gerar_project_charter`, `gerar_release_notes`);
  - `simular_cenario`, `verificar_conformidade`, `verificar_rastreabilidade_obrigatoria`, `analisar_tendencias`, `diagnostico_projeto`, `estimar_risco_requisito`, `sugerir_processos`, `mapa_rastreabilidade`, `cluster_topic_decisions`, `cluster_similar_requirements`;
  - O relatório estruturado final do modo **🔬 Análise Autônoma**.
  Explicitamente **fora**: tools de consulta pura sem síntese (`get_meeting_list`, `get_requirements`, `search_transcript`, `get_sbvr_terms`, etc.) — perguntar "quantos requisitos temos?" não deve oferecer "Promover a Ativo".
- UI: botão "⭐ Promover a Ativo de Negócio" ao lado das mensagens do chat que batem no critério acima (substitui a proposta anterior, que só olhava o sinal `_pending_file_download` — mensagens com gráfico inline, por exemplo, não passam por esse sinal e agora entram no escopo).
- Nova tool do Assistente (`core/tools/tools_executive_advanced.py` ou um arquivo novo `tools_ativos_negocio.py`, dado o crescimento de escopo): `promover_ativo_negocio(...)` — permite pedir a promoção por linguagem natural no próprio chat ("promova este relatório a ativo estratégico"), consistente com o padrão dual UI+tool já usado em todo o resto do produto.
- `pages/AtivosDeNegocio.py` ganha um 10º tipo ("Conteúdo do Assistente") com visualização própria (renderiza o Markdown salvo, já que não tem uma "reunião de origem" necessariamente).

### Fase D — Não incluído nesta melhoria (mantém decisão já tomada no PC164)
- Chave sintética para BMM/DMN/IBIS/Relatórios do pipeline padrão continua um estudo futuro, não uma entrega aqui — mesma decisão já confirmada com o usuário via `AskUserQuestion` no PC164.

---

## 7. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Central de Ativos "esvazia" para quem já usa a página desde PC164/165 | Mensagem de estado vazio explicativa + promoção em lote (Fase A, §8.4) — revisão completa da lista antes de confirmar, nunca automática |
| `assistant_artifacts` sem policy de RLS trava leitura como já aconteceu com `asset_metadata` num ambiente local | Replicar a mesma configuração de grant/policy usada nas tabelas mais recentes; validar leitura real antes de fechar a fase C |
| `meeting_documents.project_id` (TEXT) vs `asset_metadata.project_id` (UUID) | Cast explícito documentado na Fase B; não requer mudar o tipo da coluna existente |
| Promoção de conteúdo de chat duplicando dado (mesmo relatório promovido 2x gera 2 linhas) | Fora de escopo de deduplicação nesta fase — cada promoção é um snapshot independente, como um "salvar como"; mencionar ao usuário na UI |

---

## 8. Perguntas em aberto (decisão do usuário antes de implementar)

0. ~~**Classificação Formal (§3.3) / Domínio**~~ — **respondido**: adotada a taxonomia de 12 classes (AN-01..AN-12). Sobre o nível "Domínio": usuário seguiu a recomendação de **não** criar coluna dedicada agora — reaproveita `tags` se precisar antes de uma fase futura. Ver cenários prós/contras registrados na conversa (volume de uso ainda inexistente é o motivo decisivo para adiar).
1. ~~**Interesse Operacional conta como ativo pleno**~~ — **respondido**: sim, os 3 níveis (Estratégico/Tático/Operacional) são igualmente passíveis de promoção.
2. ~~**Justificativa em texto obrigatória**~~ — **respondido**: sim. Campo `promotion_justification`, obrigatório em toda promoção nova, detalhado em §3.5.
3. ~~**Escopo de quem gera conteúdo promovível no chat**~~ — **respondido**: confirmada a tradução técnica proposta em §6 Fase C (lista curada `generate_*`/`gerar_*`/`simular_cenario`/`diagnostico_projeto`/etc. + relatório da Análise Autônoma) para o critério de negócio do usuário ("análises, pesquisas, gráficos, relatórios"). Ajuste fino da lista fica para quando houver uso real — ver nota de encerramento no fim desta seção.
4. ~~**Transição / promoção em lote**~~ — **respondido**: promoção em lote incluída (elevada para dentro da Fase A, não mais "Fase D"), com exigência explícita de mostrar a lista completa dos itens do lote antes de confirmar — ver §6 Fase A.
5. ~~**"Despromover"**~~ — **respondido**: mantém histórico. Move `status` para `arquivado`, nunca apaga a linha — ver §4.
6. ~~**Permissão**~~ — **respondido**: qualquer usuário logado pode promover nesta fase, sem gate de admin — projeto ainda não tem perfis de usuário granulares o suficiente para justificar restrição agora.
7. ~~**Lista de Perspectiva (§3.2)**~~ — **respondido**: confirmados os 12 rótulos de §3.2 ("os 22" foi confirmado como erro de digitação, não uma lista diferente).
8. ~~**Perspectiva múltipla**~~ — **respondido**: confirmado multi-valor. Justificativa (cenários reais) registrada em §3.2 — BPMN multi-lane, regra SBVR aplicada por área diferente de quem a define, documento de contrato que interessa a 4 áreas, BMM estratégico transversal. Motivo decisivo: valor único faria o ativo desaparecer das buscas das áreas não-escolhidas, contradizendo a promessa de descoberta cross-departamental do Catálogo do Domínio (§4).

**Todas as 9 perguntas resolvidas.** O usuário adotou explicitamente uma postura de refinamento iterativo para os detalhes mais finos (ex.: a lista curada de tools em §8.3, a lista de 12 Perspectivas em §8.7): implementar com o critério já definido e ajustar depois, a partir do uso real do P2D — não travar a implementação buscando fechar cada detalhe por antecipação. Vale para decisões de granularidade fina; não se aplica às decisões estruturais já fechadas neste documento (modelo de dados, fases, o que fica de fora).

---

## 9. Não incluído neste plano

- Mudança em `requirements.priority` ou qualquer campo de prioridade já existente por tipo — permanecem como estão, dimensão separada de `business_interest`.
- BMM/DMN/IBIS/Relatórios do pipeline padrão (decisão já fechada no PC164, ver §6 Fase D).
- Dashboard dedicado de ativos por nível de interesse na Home — possível evolução futura, não faz parte desta entrega.
