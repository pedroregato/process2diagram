# Roadmap — Process2Diagram

Histórico completo de entregas por ciclo de projeto.

---

### PC189 — Concluído (v5.15 / 2026-07-16) — Avaliação de `proposta-assistente-20261607.md`: 2 implementadas, 1 rejeitada (segurança), 2 já existiam

**Contexto:** auto-reflexão do próprio Assistente ("Vichāra") propondo 5 melhorias de fricção no dia a dia. Agent Explore investigou as 5 alegações contra o código real ANTES de qualquer implementação — achado recorrente do projeto (mesmo padrão de `solution-manage.md`/`assistente-20260711.md`): a proposta subestimava o quanto já existe, e uma das 5 (SQL direto) contradiz uma garantia de segurança real do app.

- **#1 — "Cache de contexto da conversa" → IMPLEMENTADO, escopo reduzido**: a alegação de "re-busco dados que já vi" está parcialmente errada — dentro do MESMO turno o LLM já vê os resultados de tool (`agent_assistant.py` tool loop); só re-fetch ENTRE turnos é real, e é intencional (`_trim_history()` já remove `charts`/dados brutos do histórico de propósito, por um crash de serialização de `datetime` documentado no próprio código). Implementar o cache de DADOS pedido reintroduziria exatamente esse risco. Em vez disso: `pages/Assistente.py::_build_tools_used_digest()` — digest raso (só nomes de ferramentas já chamadas nesta conversa, deduplicado, sem dados/args) injetado no system prompt via `AgentAssistant._build_system_prompt_tools(..., tools_used_digest=...)`. Zero risco de reintroduzir o crash de serialização.
- **#2 — `run_sql(query)` (SELECT ad-hoc) → REJEITADO, risco de segurança confirmado**: o app usa a chave `service_role` do Supabase (`infra/cloudrun/env.template.yaml`, `setup/supabase_migration_enable_rls.sql`) — RLS habilitado mas **bypassado por design**; o isolamento real entre projetos/tenants hoje é 100% manual, via `.eq("project_id", ...)` em toda query de todo mixin de tool. Uma tool de SQL livre pra um LLM compor, mesmo "SELECT-only", rodaria sob essa mesma chave sem filtro de `project_id` garantido — uma query sem esse WHERE (omissão acidental do LLM ou prompt injection) vazaria dados entre projetos. Não implementado.
- **#3 — `project_dashboard()` → REJEITADO, já coberto por 2 ferramentas quase-gratuitas existentes**: `diagnostico_projeto()` (`core/tools/tools_knowledge_requirements2.py:1898`) já orquestra saúde/integridade/contradições/ROI-TR/pendências num único call sem LLM; `count_artifacts("all")` já cobre os totais brutos (reuniões/requisitos/SBVR/BPMN). O ganho de mesclar as duas em uma terceira tool nova é marginal — não implementado.
- **#4 — Embedding automático ao salvar → IMPLEMENTADO**: alegação confirmada como verdadeira (`save_transcript_embeddings()` só era chamada do admin tool `generate_meeting_embeddings()`, nunca do fluxo normal de save). `pages/Pipeline.py`, logo após `save_transcript()`: se `asst_embed_key` já estiver configurada em Configurações (gate de opt-in que já existia), gera embeddings automaticamente — fail-open (try/except, nunca bloqueia o save da reunião), com `st.spinner()` pro mesmo padrão de UX já usado na extração de Knowledge Hub logo abaixo no mesmo bloco.
- **#5 — "Modo investigativo" → já existe, nenhuma ação**: é literalmente o modo "🔬 Análise Autônoma" já em produção (`agents/agent_analyst.py`, `MAX_ITERATIONS=15`, `pages/Assistente.py::_render_analyst_mode`) — coleta multi-rodada → relatório estruturado, exatamente o fluxo proposto.
- 7 testes novos (`tests/test_pc189_assistant_proposals.py`) cobrindo `_build_tools_used_digest()` (dedup, cap, ordem) e a injeção do digest no system prompt (com/sem digest, sem quebrar as substituições `.replace()` existentes). O #4 (lógica inline em `Pipeline.py`, sempre fail-open) não ganhou teste automatizado dedicado — revisão manual + leitura de escopo de variáveis em vez de harness `AppTest` completo (página tem muitos pré-requisitos de `session_state` não relacionados à mudança).
- REGRA DERIVADA (reforça o padrão já visto em `solution-manage.md`/PC161-163/PC185): antes de implementar uma auto-proposta do próprio Assistente, verificar cada alegação contra o código real primeiro — aqui, 2 das 5 "fricções" relatadas já não existiam (dashboard, modo investigativo), e uma tinha implicação de segurança que a proposta original não tinha como enxergar (ela não sabe que o app roda sob `service_role`).

---

### PC188 — Concluído (v5.15 / 2026-07-15) — Glossário: botão "Abrir em nova janela"

**Contexto:** ideia do usuário — o Glossário já é uma página própria, mas para consultar um termo desconhecido enquanto lê outra página (ex.: o novo guia de Cache LLM) era preciso navegar para fora da página atual. Apresentei 2 opções (botão de nova janela vs. busca inline embutida em cada página de guia) com o trade-off de custo/complexidade; usuário escolheu a primeira.

- **`pages/Orientacoes_Glossario.py`**: botão "↗ Nova janela" na barra de busca — mesmo padrão `openNewTab()` já usado em `ui/architecture_diagram.py` (blob de `document.documentElement.outerHTML` aberto via `window.open`). Abre uma cópia autocontida do Glossário numa aba separada do browser, que o leitor mantém aberta lado a lado com a página que está lendo.
- **Bug pré-existente corrigido de passagem**: `TAG_LABEL` no JavaScript era um dict hardcoded (`bpmn/req/ai/dev/neg`) sem a tag `seg` — os 5 verbetes de Segurança (Segurança, Sanitização de PII, Trilha de Auditoria, Camada de Conformidade LGPD, Consentimento de Dados) mostravam a badge crua "seg" em vez de "Segurança & Privacidade" desde o PC81/82. Corrigido gerando `TAG_LABEL` a partir do `TAG_META` real em Python (`json.dumps({slug: meta["label"] ...})`) em vez de duplicar o dict em JS — elimina o risco de essa mesma categoria de drift acontecer de novo com tags futuras.
- Verificação: `_build_glossary_html()` chamada diretamente confirma a função `openNewTab`, o botão e o label "Segurança & Privacidade" presentes no HTML gerado; `AppTest` sem exceção; suite completa passando.
- REGRA DERIVADA (reforça padrão já visto no projeto): qualquer dict que espelha `TAG_META`/uma fonte de verdade Python só deve existir gerado a partir dela no momento do build da página — nunca reescrito à mão em JS/HTML, mesmo que pareça "só uma cópia rápida". O próprio arquivo já fazia isso corretamente para `css_cat_vars`/`css_tag_classes`/`filter_buttons`; só o `TAG_LABEL` no `<script>` tinha escapado dessa disciplina.

---

### PC187 — Concluído (v5.15 / 2026-07-15) — Glossário: 9 termos novos cobrindo o cache LLM

**Contexto:** sequência do PC186 — usuário pediu para o Glossário cobrir o vocabulário técnico usado na nova página `Orientacoes_CacheSemantico.py` (exemplos dados: hit, cache, embedding, tax).

- **`modules/glossary_data.py`**: 5 termos novos — `Cache Hit / Cache Miss`, `Fuzzy Matching` (nova seção F), `Hash (SHA-256)` (nova seção H), `Tax (Overhead por Chamada)`, `TTL`. `Semantic Cache` atualizado para esclarecer que a implementação real é hash exato normalizado (PC185), não embedding, com cross-links para os termos novos. `Embedding` ganhou cross-link para `Fuzzy Matching`/`Semantic Cache`.
- Corrigido de passagem: comentário de categorias no topo do arquivo listava só 5 tags (`bpmn/req/ai/dev/neg`), faltando `seg` — que já existia em `TAG_META` e em várias entradas (Segurança, Sanitização de PII, Trilha de Auditoria) desde o PC81/82, sem nunca ter sido documentado no comentário.
- **`CLAUDE.md`**: contagem de verbetes atualizada (80 → 89).
- Verificação: script standalone confere 0 termos duplicados, 0 links `related` quebrados, 0 tags desconhecidas contra `TAG_META`; `search_glossary()` testado nas queries "hit/embedding/tax/ttl/hash/fuzzy/miss" — todas retornam os termos esperados. `AppTest` na página do Glossário sem exceção. 878/878 testes passando (nenhum teste automatizado preexistente cobre o glossário — mudança é dado, não lógica).
- Commit a155173, pushed.

---

### PC186 — Concluído (v5.15 / 2026-07-15) — Documentação in-app do cache LLM (páginas de arquitetura, custo, novo guia)

**Contexto:** sequência do PC185 — usuário pediu para atualizar as páginas de arquitetura, os cenários de custo (se fosse o caso) e criar uma página nova explicando o conceito de cache semântico e como o P2D usa.

- **`ui/architecture_diagram.py`** — diagrama Mermaid do splash ganhou subgraph `CACHEG` (⚡ Cache LLM) entre `PIPE` e `LLM`, com 4 arestas mostrando o fluxo real (verifica cache → hit/miss → API real → grava cache). Validado via fetch real em `mermaid.ink` (SVG renderizou, sem erro de sintaxe).
- **`pages/Orientacoes_Arquiteturas.py`** — legenda do Pipeline menciona o cache-first e aponta para o novo guia.
- **`pages/SegurancaDeDados.py`** — seção "Cache Semântico — Segurança entre Sessões" ganhou um card novo sobre a normalização de whitespace (PC185) e a decisão de não usar fuzzy matching; corrigida uma afirmação pré-existente incorreta ("TTL configurável em Qualidade ROI-TR") — TTL é fixo em 30 dias, não há UI de configuração.
- **`pages/CostEstimator.py`** — caption corrigida: dizia "~$0.003/1M no cache hit", um número sem lastro no código real. Um hit evita a chamada por completo (custo ≈ $0, só leitura no Supabase), não uma fração do preço do provider.
- **`pages/CostBenefitScenarios.py`** — nova caption deixando explícito que `project_cost()` não modela taxa de hit de cache (assume cache frio / pior caso de custo) — decisão deliberada de não modelar (taxa de hit depende do padrão de uso do usuário, não é uma constante do sistema).
- **`pages/Orientacoes_CacheSemantico.py`** (NOVA, grupo Ajuda) — guia completo no mesmo padrão HTML dark-navy/âmbar de `Orientacoes_CKF.py`: conceito geral de cache semântico de LLM (exato vs. embedding, tabela comparativa), o que o P2D implementa de fato (hash SHA-256, PII-safe, whitespace-normalizado, global a todos os agentes, 2 exceções deliberadas — torneio BPMN e rerun manual), diagrama de fluxo em ASCII, segurança entre sessões, **a decisão de engenharia do PC185 documentada de forma transparente** (por que fuzzy matching por embedding foi avaliado e rejeitado), onde ver estatísticas reais (aba Cache LLM em Qualidade ROI-TR), FAQ.
- **`app.py`** — página registrada no grupo Ajuda (ícone 🗄️, título "Cache LLM"). **`CLAUDE.md`** — entrada na árvore de `pages/`, na tabela de grupos de navegação, e no comentário de `services/semantic_cache.py`.
- Verificação real: todas as 5 páginas tocadas sobem via `AppTest` sem exceção (chaves de sessão corretas — `_autenticado`, não `authenticated`, lição do PC178); caption da CostBenefitScenarios confirmada presente no output renderizado. 878/878 testes passando (nenhum teste automatizado preexistente cobria essas páginas — mudança é conteúdo/HTML, não lógica).
- REGRA DERIVADA: ao atualizar documentação in-app depois de uma decisão de arquitetura, aproveitar a revisão para auditar afirmações VIZINHAS já existentes no mesmo texto — 2 imprecisões pré-existentes e não relacionadas ao pedido original (TTL "configurável" que não existe, custo de hit "$0.003/1M" sem lastro) foram encontradas e corrigidas só por estarem coladas ao trecho que eu já precisava editar.

---

### PC185 — Concluído (v5.15 / 2026-07-15) — Avaliação de `cache-semantico.md` + normalização de whitespace no cache exato

**Contexto:** usuário trouxe uma spec (`melhorias/cache-semantico.md`) propondo um cache semântico por embedding (pgvector, threshold de similaridade, 2 camadas — roteamento e geração de artefato), pedindo avaliação e implementação do que fosse adequado.

- **Achado principal:** o p2d já tem um cache rodando exatamente onde a spec propõe (`services/semantic_cache.py`, tabela `llm_cache`, plugado em `agents/base_agent.py::_call_llm()`) — global (todos os agentes), PII-safe, com stats/admin tool. Só que é por hash exato (SHA256), não por similaridade de embedding.
- **Mismatches da spec com a arquitetura real:** usa `group_id`/tabela `groups` (não existem — isolamento real é `project_id`/`tenant_id`); a camada de "cache de roteamento" (seção 5.1) pressupõe um classificador de trechos de transcrição dentro do Orchestrator que não existe — o pipeline roda agentes completos sobre a transcrição inteira, não faz triagem por trecho.
- **Decisão (via `AskUserQuestion`, usuário escolheu a opção recomendada):** não construir a infraestrutura de embedding completa — custaria 1 chamada de embedding extra em toda chamada de LLM (hit ou miss) e, para geração de artefato (BPMN/ata), um falso positivo por similaridade entregaria o artefato de uma transcrição errada, sem ganho demonstrado (nenhum relato de "reprocessar quase-idêntico" como problema real de produção).
- **Implementado:** `SemanticCache.compute_hash()` normaliza espaços em branco (`_normalize_for_hash` — colapsa runs de whitespace, strip) antes de hashear `system`/`safe_user` — cobre a motivação nº1 da spec ("revisão marginal" da mesma transcrição) sem custo de embedding e sem risco de falso positivo (mudança de conteúdo real continua gerando hash diferente).
- 4 testes novos (`tests/test_semantic_cache.py`). Spec original arquivada em `melhorias/arquivados/cache-semantico.md` com nota de fechamento documentando a avaliação completa.
- REGRA DERIVADA (reforça PC183/PC184 e os casos de `solution-manage.md`/`assistente-20260711.md`): antes de implementar uma spec de melhoria, verificar se o mecanismo proposto já existe sob outro nome no código real — "cache semântico" no p2d já existia, só que com garantia mais forte (exato) do que a spec assumia; a lacuna real era muito mais estreita que a spec descrita.

---

### PC184 — Concluído (v5.15 / 2026-07-12) — Provider Azure OpenAI Service

**Contexto:** avaliação honesta de gaps de vaga (feita a partir de um checklist de currículo do usuário, cruzado com o código real do P2D) apontou que "Azure AI Services / Azure OpenAI" era um gap literal — o projeto já integra OpenAI diretamente, mas não via Azure. Diferente de gaps que não fazem sentido forçar no P2D (data warehouse, certificações), este era uma extensão pequena e genuína da arquitetura já agnóstica de provider — decisão explícita do usuário via `AskUserQuestion` de implementar de verdade, não só ajustar o texto do CV.

- **`modules/config.py`** — nova entrada `"Azure OpenAI"` em `AVAILABLE_PROVIDERS`: `client_type="azure_openai"`, `api_version` fixo (`2024-10-21`), e um mecanismo novo e genérico `extra_fields` (lista de `{key,label,placeholder,help}`) para providers que precisam de config não-secreta além da API key — Azure precisa de endpoint por recurso (não é um `base_url` fixo igual aos demais providers) e, opcionalmente, do nome do deployment (Azure roteia por deployment, não por model id).
- **`agents/base_agent.py`** — `_call_openai()` refatorado sem mudar comportamento: lógica de montar request/validar resposta extraída para `_run_openai_chat(client, ...)` compartilhada; `_call_azure_openai()` novo monta o `openai.AzureOpenAI` (endpoint+api_version em vez de base_url) e reusa o mesmo helper — mesma checagem de `finish_reason='length'`/conteúdo vazio que os outros providers já tinham. Resolução de endpoint/deployment segue o mesmo padrão 3-camadas já usado em `_is_long_context_enabled()`: `client_info` (modo API) → campo extra da sessão (Streamlit) → erro claro se nenhum dos dois tiver o endpoint.
- **`modules/session_security.py`** — `render_extra_fields()`/`get_extra_field()` novos, genéricos (não hardcoded pra Azure) — qualquer provider futuro com necessidade parecida reusa sem código novo.
- **`ui/sidebar.py`** + **`pages/Settings.py`** — chamam `render_extra_fields()` logo após o campo de API key existente; Settings > Domínio (multi-tenant) automaticamente NÃO lista Azure OpenAI (guard pré-existente `p in PROVIDER_KEY_MAP`) — escopo deliberadamente limitado à config de sessão/usuário único nesta rodada, não ao sistema multi-tenant de chaves por domínio.
- **`services/llm_telemetry.py::run_benchmark_call()`** — branch Azure próprio (caminho paralelo ao de `_call_llm`, sem hub/cache/PII) — sem isso, a aba Benchmark On-Demand falharia silenciosamente pra esse provider.
- 13 testes novos (`test_base_agent_azure_openai.py`, `test_run_benchmark_call_azure.py`) — 100% mockado, zero chamada de rede real. Boot-smoke real de `Settings.py` com Azure OpenAI selecionado confirma os 2 campos extras renderizando sem exceção. 874/874 passando na suite completa.
- REGRA DERIVADA: ao avaliar "gap de currículo" contra um projeto pessoal real, distinguir gap que vale fechar com código genuíno (arquitetura já generaliza, adição tem valor de produto real) de gap que só faria sentido como teatro pra CV (forçar um data warehouse ou MLOps formal sem uso real seria o oposto do que o usuário pediu — "sem exagerar").

---

### PC183 — Concluído (v5.15 / 2026-07-12) — Telemetria fecha o loop: erro por provider vira alerta + taxa de schema válido vira métrica

**Contexto:** discussão sobre RLS/telemetria levou o usuário a explicar que o P2D também serve como POC pessoal de proficiência em engenharia de IA (career motivation, ver memória `user_profile.md`). Avaliação conjunta descartou analytics genéricos (Sentry, page views) por não demonstrarem profundidade específica de IA, e propôs 2 adições que fecham o loop de dado bruto → sinal acionável em cima de infraestrutura 100% existente. Usuário aprovou com "Implemente as duas".

- **Achado crítico na investigação:** `is_error` em `llm_telemetry` estava hard-coded `False` no único ponto de escrita de `_call_llm()` (que só executava DEPOIS de uma chamada bem-sucedida) — uma chamada que falhasse (ex.: o problema intermitente conhecido do DeepSeek, "conteúdo vazio") **nunca gerava registro nenhum** de telemetria. O bug documentado na memória do projeto era literalmente invisível ao próprio sistema de observabilidade.
- **`agents/base_agent.py::_call_llm()`** — chamada a `_call_openai`/`_call_anthropic` agora envolvida em `try/except`: em caso de exceção, grava `TelemetryRecord(is_error=True, error_message=str(exc)[:300])` e **relança a mesma exceção inalterada** — comportamento de retry/escalação de `_call_with_retry()` preservado byte a byte (coberto por regressão explícita).
- **`agents/base_agent.py::_call_with_retry()`** — resultado de `output_schema.model_validate(data)` (padrão PC84), antes só um `warnings.warn()` efêmero, agora também persiste via `_telemetry.record_validation(agent_name, skill_version, valid)` — fail-open, nunca bloqueia o pipeline.
- **`services/llm_telemetry.py`** — `TelemetryRecord` ganhou `error_message`, `is_validation_event`, `schema_valid`; `LLMTelemetry.record_validation()` novo; `query()` passou a filtrar `is_validation_event=False` (não polui médias de latência/throughput); 4 métodos novos: `query_error_rate_by_provider(hours)`, `detect_error_anomalies(hours, min_calls, error_rate_threshold)` (guard de `min_calls` evita falso positivo de baixo volume), `query_recent_errors(hours, limit)`, `query_schema_validation_rate(days, agent_name)`.
- **`pages/LLMBenchmark.py`** — aba "📊 Telemetria Real" ganhou 2 sub-abas: **🚨 Alertas** (taxa de erro por provider, limiar/mínimo de chamadas configuráveis via slider, bar chart com linha de limiar, tabela de últimas falhas com `error_message`) e **✅ Qualidade** (taxa geral e por agente de saída bem-formada, evolução temporal, breakdown por versão de skill quando disponível).
- **Migration** — `setup/supabase_migration_llm_telemetry_pc183.sql` (3 colunas `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` + 2 índices parciais) — **executada em produção** via `psycopg2`/`connection_string` direto.
- 21 testes novos (`tests/test_base_agent_telemetry.py`, `tests/test_llm_telemetry_pc183.py`, `tests/test_page_llm_benchmark_pc183.py`) — cobrem gravação de erro + relançamento da exceção original, fail-open quando a própria telemetria falha, persistência de `schema_valid` true/false sem bloquear o pipeline, cálculo de taxa de erro/anomalia/ruído de baixo volume, e boot-smoke real da página contra o Supabase de produção pós-migração.

---

### PC182 — Concluído (v5.15 / 2026-07-11) — 3º ponto instável do "Bad setIn index" — toggle "Visualizar diagrama interativo" (aba Processos BPMN)

**Contexto:** usuário reportou "Oh no. Error running app" de novo, agora ao entrar na aba Processos BPMN — mesma classe de crash já corrigida 2x nesta sessão (PC172/174: componente de promoção; PC175: toggle "Ver Ata Completa").

- Achado: `st.toggle("Visualizar diagrama interativo", ...)` na aba BPMN condicionava diretamente um `components.html(bpmn_html, height=700)` — variando entre 0 e 1 elemento no mesmo nível hierárquico a cada rerun, sem `st.container()` estável. Agravante em relação aos casos anteriores: o payload condicional aqui é grande (a biblioteca bpmn-js inteira + XML do diagrama embutidos inline), tornando esse provavelmente o gatilho mais forte já encontrado pra essa classe de bug.
- Fix: mesmo padrão já estabelecido — resultado do toggle capturado numa variável, conteúdo condicional movido pra dentro de um `st.container()` que sempre contribui exatamente 1 elemento ao pai, independente do estado do toggle.
- Varredura confirmou que era o **único** `st.toggle()` em todo `Artefatos.py`, e os outros `components.html()` do arquivo (DMN tabelas/DRD) renderizam incondicionalmente a cada execução (sem variar contagem — não têm essa classe de bug, só custo fixo).
- 3 testes novos (`tests/test_artefatos_bpmn_toggle_stable_container.py`) — reproduz a forma exata (toggle dentro de abas aninhadas) via `AppTest.from_string()`, mais uma checagem estática confirmando que o `st.container()` envolve o `components.html()` real no código-fonte.
- 841/841 testes passando; boot-smoke real de `Artefatos.py` (chave de auth correta) sem exceção.

---

### PC181 — Concluído (v5.15 / 2026-07-11) — Página "Casos de Uso — Valor de Negócio" + guia de ferramentas atualizado

**Contexto:** usuário pediu pra "melhorar a documentação incluindo as novas funcionalidades" e criar uma página especial com exemplos de uso do P2D "demonstrando seu valor para o negócio". Escopo confirmado: página nova focada no Assistente (não o pipeline inteiro, que já tem material comercial próprio), como página Streamlit dentro do grupo Ajuda, com botão de exportar pra HTML.

- **`pages/Orientacoes_CasosDeUso.py`** (novo, grupo Ajuda) — 15 cenários de negócio em 5 categorias (Comunicação & Entrega, Acompanhamento & Gestão, Auditoria & Rastreabilidade, Simulação & Risco, Conhecimento Organizacional), cada um estruturado como Cenário → Pergunta literal (copiável) → O que o Assistente entrega → Valor de negócio. Cobre as 3 tools novas do PC179 (`exportar_pacote_completo`, `sugerir_encaminhamentos_pendentes`, `pesquisar_multi_contexto`) e as ferramentas mais fortes já existentes (`simular_cenario`, `verificar_conformidade`, `mapa_rastreabilidade`, `gerar_deck_executivo`, `promover_ativo_negocio`, etc).
- **Fonte única de conteúdo**: os 15 cenários vivem em um único dict Python (`_SCENARIOS`) que alimenta DOIS renderizadores — cards em abas dentro do Streamlit, E um HTML autocontido gerado sob demanda pelo botão "⬇️ Exportar HTML". Decisão deliberada de NÃO criar um segundo arquivo estático mantido à mão (padrão já usado em `ApresentacaoGeral.py`/`apresentacao-geral.html`) — evita o problema de sincronização manual entre 2 arquivos que já exigiu uma rodada inteira de correção nesta mesma sessão.
- **`pages/Orientacoes_Assistente.py`** (guia técnico de ~150 tools) — 3 cards novos (`exportar_pacote_completo`, `sugerir_encaminhamentos_pendentes`, `pesquisar_multi_contexto`) na aba Avançado, mesmo padrão `_card()` já usado nas outras ~64 ferramentas documentadas.
- `app.py` — nova página registrada no grupo Ajuda.
- 5 testes novos (`tests/test_page_casos_de_uso.py`) — boot-smoke real (chave de auth correta) + validação do HTML exportado (bem formado, sem CDN externo, todos os cenários representados, as 3 tools do PC179 mencionadas por nome). Verificação visual real via Playwright screenshot do HTML exportado.
- 838/838 testes passando; boot-smoke de `app.py` confirma navegação íntegra com a página nova registrada.

---

### PC180 — Concluído (v5.15 / 2026-07-11) — Correções de estilo do .docx consolidado (feedback do usuário sobre PC179)

**Contexto:** usuário testou `exportar_pacote_completo` (PC179) e reportou 3 problemas: numeração de página não aparecia, cabeçalho não identificava o projeto, estilo geral podia melhorar.

- **Numeração de página**: a causa raiz não era o campo em si (já estava correto) — Word/LibreOffice não recalculam campos inseridos via XML bruto na abertura, a menos que o documento peça explicitamente. Fix: `_force_field_recalculation()` grava `<w:updateFields w:val="true"/>` em `word/settings.xml`.
- **Identificação do projeto**: `exportar_pacote_completo()` agora resolve o nome real do contexto via `get_context(self.project_id)` (mesmo padrão já usado em `pesquisar_multi_contexto`) e usa em dois lugares — no título do corpo (H1) e num cabeçalho novo que se repete em toda página (`_add_document_header()`, distinto do H1 que só aparece na página 1).
- **Estilo geral**: `markdown_to_docx()`/`_render_markdown_docx()` ganharam `page_break_before_h2` (opcional, default `False`) — cada seção principal do pacote agora começa em página nova, lendo como capítulos de um relatório, em vez de tudo corrido.
- Todos os parâmetros novos (`header_title`, `header_subtitle`, `page_break_before_h2`, `add_page_numbers`) são opt-in — `export_project_charter_docx()` (chamador já existente de `markdown_to_docx`) continua produzindo a mesma saída de antes, sem regressão.
- 2 testes novos (verificação real de bytes do .docx gerado: nome do projeto no cabeçalho E no corpo, setting `updateFields` presente), 833/833 passando.

---

### PC179 — Concluído (v5.15 / 2026-07-11) — 3 tools novas do Assistente (avaliação de `melhorias/assistente-20260711.md`)

**Contexto:** o próprio Assistente gerou uma auto-reflexão (`melhorias/assistente-20260711.md`, criada direto no GitHub) propondo 6 gaps: memória entre conversas, exportação consolidada, grafo de rastreamento, simulação com diff visual, sugestão proativa de encaminhamentos, pesquisa multi-contexto. Pesquisa (agent Explore) contra o código real descartou #3/#4 (grafo/diff visual — ambos dependem de `mapa_rastreabilidade`, que casa por palavra-chave, não FK real; construir visualização em cima disso mostraria ligações não confiáveis) e deixou #1 (memória) fora por ser decisão de produto, não gap técnico. Usuário confirmou implementar #2, #5, #6.

- **`exportar_pacote_completo()`** (`core/tools/tools_executive_advanced.py`) — 1 único .docx consolidando Atas+Requisitos+SBVR+BMM+BPMN+IBIS com sumário e numeração de páginas, em vez de exportar cada artefato separado. Reaproveita `markdown_to_docx()` (já existente, usado por `export_project_charter_docx`) e as mesmas funções de leitura de `pages/Artefatos.py` — não pagina (é export de arquivo, não tela reativa, sem o problema do PC178). Gráficos explicitamente fora de escopo (sem conversor Plotly→imagem estática no projeto). `modules/minutes_exporter.py::markdown_to_docx()` ganhou parâmetro opcional `add_page_numbers` (campo PAGE/NUMPAGES nativo do Word via XML raw, técnica padrão do python-docx) — default `False`, não muda a saída de nenhum chamador já existente.
- **`sugerir_encaminhamentos_pendentes()`** (`core/tools/tools_knowledge_requirements2.py`) — compara Decisões x Encaminhamentos do `minutes_md` (texto livre — não existe tabela `action_items`) via 1 chamada LLM por reunião, apontando decisão sem encaminhamento correspondente e prazo vencido. `meeting_number=None` analisa as 5 reuniões mais recentes.
- **`pesquisar_multi_contexto()`** (`core/tools/tools_meetings_requirements.py`) — busca por palavra-chave em transcrições de TODOS os contextos do mesmo tenant, não só o ativo. Contorna a restrição de `AssistantToolExecutor` (um único `project_id` fixo) reaproveitando o padrão já aprovado em `list_all_business_assets_for_domain` (PC165): resolve `tenant_id` via `get_context(self.project_id)`, itera `list_contexts()`, consulta cada contexto direto na camada de dados — sem instanciar múltiplos executors.
- 23 testes novos (7+9+7), 831/831 passando. Boot-smoke real de `Assistente.py` (chave de auth correta, achado do PC178) sem exceção.

---

### PC178 — Concluído (v5.15 / 2026-07-11) — Paginação da aba SBVR em Artefatos.py (provável causa real do segfault/tela branca) + correção de metodologia de teste

**Contexto:** usuário mandou screenshot real de um contexto de produção: **842 requisitos, 751 termos SBVR, 502 regras SBVR, 28 reuniões, 43 processos BPMN, 113 decisões DMN**. Como `st.tabs()` executa o corpo de TODAS as abas a cada rerun (achado do PC176/177), a aba SBVR — sem paginação — renderizava **1253 expanders** (751+502), cada um com um `_promote_widget()` aninhado, TODA VEZ que a página Artefatos era carregada, mesmo que o usuário estivesse olhando outra aba. Essa é a explicação mais concreta e evidenciada até agora para os episódios de segfault/tela branca/lentidão — mais forte que as hipóteses anteriores (drift de dependência, refutada; volume total do contexto, parcialmente confirmada agora com números reais).

- `pages/Artefatos.py` — aba SBVR (Termos e Regras, cada coluna independente) ganhou paginação de 25 itens/página, mesmo padrão já usado na aba Requisitos (`_REQ_PAGE_SIZE`) — nova constante `_SBVR_PAGE_SIZE = 25`, navegação Anterior/Próximo + contador, reset de página ao mudar filtro (reunião/categoria ou reunião/tipo).
- **Achado crítico de metodologia**: todo "boot-smoke via AppTest" reportado nesta sessão (PC172 a PC177) usava a chave de sessão errada (`"authenticated"` em vez de `"_autenticado"`, a chave real lida por `modules/auth.py::is_authenticated()`) — isso significa que essas verificações só confirmavam que a **tela de login** renderizava sem erro, nunca testaram de fato o conteúdo das páginas alteradas. Corrigido nos testes novos deste PC; os testes de regressão de expander aninhado/Bad-setIn de PC172-175 continuam válidos porque usavam `AppTest.from_string()` com scripts autônomos, sem depender do gate de autenticação.
- 2 testes novos (`tests/test_artefatos_sbvr_pagination.py`) com dado sintético grande (60 termos + 60 regras) e autenticação REAL corrigida — provam que a paginação de fato limita a renderização a 25 itens por coluna, incluindo navegação Próximo→.
- Testado à parte (não é regressão, é achado): com autenticação real e Supabase real configurado localmente, a página completa (mesmo já com paginação) levou ~34s pra carregar contra um `project_id` sintético — não travou (descarta deadlock do `ThreadPoolExecutor` do PC177), mas confirma que o carregamento é genuinamente pesado; sem acesso a um projeto real de produção localmente (RLS bloqueia a chave local), não dá pra medir o ganho exato da paginação em produção.
- 808/808 testes passando.

---

### PC177 — Concluído (v5.15 / 2026-07-10) — Carregamento paralelo dos dados iniciais da Central de Artefatos

**Contexto:** usuário reportou lentidão no carregamento de `pages/Artefatos.py` depois do episódio de segfault (PC176). Investigação prévia (não implementada — decisão explícita do usuário) mostrou que "carregar só a aba ativa" exigiria trocar `st.tabs()` por navegação manual (risco alto, ganho incerto, já que `st.tabs()` executa o código de TODAS as abas a cada rerun independente de qual está visível). O que sobrou como alavanca real de velocidade: as 8 queries independentes do carregamento inicial rodavam sequencialmente.

- `pages/Artefatos.py` — as 8 chamadas `_load_*(project_id)` (reuniões, requisitos, contradições, termos/regras SBVR, processos BPMN, documentos, mapa de metadados de ativos) agora disparam em paralelo via `ThreadPoolExecutor(max_workers=8)`, mesmo padrão já usado no Orchestrator (Minutes+Requirements) e em `modules/bpmn_viewer.py::_load_bpmn_assets`. Como são todas chamadas HTTP ao Supabase (I/O-bound), o tempo total passa a ser ~o da consulta mais lenta, não a soma de todas.
- Não resolve o consumo de memória do primeiro carregamento (mesma quantidade de dados é buscada) — só o tempo de espera (wall clock).
- 806/806 testes passando; boot-smoke via AppTest sem exceção.

---

### PC176 — Concluído (v5.15 / 2026-07-10) — Fixa versões soltas em requirements.txt (segfault em produção)

**Contexto:** usuário relatou 2ª ocorrência de `Segmentation fault` no deploy do Streamlit Cloud (não uma exceção Python — crash no próprio processo). Sem acesso a stack trace/core dump, causa raiz não confirmada com certeza — mas `requirements.txt` violava a própria política do projeto ("Always pin exact versions") em várias linhas com range solto (`spacy>=3.7,<4.0`, `supabase>=2.4.0`, `lxml>=5.0`, etc.), fazendo cada deploy resolver possivelmente versões diferentes de numpy/blis/thinc (dependências nativas do spaCy) — fonte clássica de segfault por incompatibilidade de ABI entre builds.

- Todas as dependências antes soltas em `requirements.txt` fixadas nas versões que já resolviam com sucesso hoje: `spacy==3.8.14`, `google-genai==2.11.0`, `google-generativeai==0.8.6`, `pypdf==6.14.2`, `openpyxl==3.1.5` (já batia), `jsonschema==4.26.0`, `lxml==6.1.1`, `python-dateutil==2.9.0.post0`, `supabase==2.31.0`, `pytest==9.1.1`.
- Adicionado pin explícito de `numpy==2.5.1`, `blis==1.3.3`, `thinc==8.3.13` — dependências nativas transitivas do spaCy que antes nunca apareciam no arquivo (resolvidas implicitamente a cada build, sem controle de versão).
- **Não é confirmação de causa raiz** — é uma medida preventiva de baixo risco alinhada à política já documentada do projeto. Ação imediata recomendada ao usuário: reboot manual do app no painel do Streamlit Cloud (fora do alcance do Claude Code).
- 806/806 testes passando localmente (pin não afeta o venv local já instalado, só builds futuros).

---

### PC175 — Concluído (v5.15 / 2026-07-10) — "Bad 'setIn' index" persistia após PC174: 2º ponto instável achado (toggle "Ver Ata Completa")

**Contexto:** usuário colou o mesmo log de console de novo após o PC174 — erro ainda presente, só que `index 3` virou `index 1`. O fix do PC174 (envolver `render_promote_button` num `st.container()`) estava correto mas incompleto: existia OUTRO ponto com o mesmo padrão instável bem ao lado, dentro do mesmo expander de reunião.

- Achado: `pages/Artefatos.py`, aba Reuniões — o toggle "📄 Ver Ata Completa"/"🙈 Ocultar Ata" (`if st.session_state.get(toggle_key): st.markdown(minutes_md)`) também contribui uma quantidade VARIÁVEL de elementos (0 ou 1) diretamente no corpo do expander da reunião, no mesmo nível hierárquico do `_promote_widget()` já corrigido no PC174. Corrigindo só um dos dois pontos instáveis não bastava — o outro continuava desalinhando a árvore.
- Fix: mesmo padrão do PC174 — o `st.markdown(minutes_md)` condicional agora vive dentro do seu próprio `st.container()` estável.
- Varredura adicional no projeto (`grep -rn "= not st.session_state.get("`) achou o MESMO padrão (botão-toggle variando contagem de elementos, dentro de loop) em `pages/BpmnEditor.py` e `pages/Capacitacao.py` — nenhum dos dois foi alterado (sem relato de erro, fora do escopo deste fix), mas fica registrado aqui como candidato a checar se aparecer relato semelhante nessas páginas.
- **Limite de verificação reconhecido**: este bug é 100% client-side (reconciliação de deltas no frontend React/JS do Streamlit) — `AppTest` só executa o script Python e não pode reproduzi-lo; não há teste automatizado que prove a ausência do erro. Verificação real depende do usuário reproduzir a interação (expandir uma reunião com Ata, alternar "Ver Ata Completa", tentar promover) em produção após o deploy.
- 806/806 testes passando (sem regressão Python); boot-smoke via AppTest sem exceção.

---

### PC174 — Concluído (v5.15 / 2026-07-10) — Fix de produção: "Bad 'setIn' index" no frontend do componente de promoção

**Contexto:** logs de console do navegador colados pelo usuário na Central de Artefatos mostravam `Uncaught Error: Bad 'setIn' index 3 (should be between [0, 0])` — erro JS do frontend do Streamlit (não uma exceção Python), reintroduzido pelo próprio fix do PC172.

- Causa raiz: o PC172 trocou `st.expander()` por um toggle `st.button()` dentro de `render_promote_button()`/`render_promote_assistant_content_button()` — mas isso faz a função contribuir uma quantidade VARIÁVEL de elementos pro container-pai (1 quando o toggle está fechado, vários quando o formulário está aberto). Streamlit quebra no frontend quando a contagem de filhos de um bloco muda entre reruns de um jeito que o motor de aplicação de deltas não consegue reconciliar — mesma classe de bug já documentada (e já resolvida) em `ui/tabs/bpmn_tabs.py` (comentário sobre `st.empty()`/child count estável), só que eu não tinha aplicado esse padrão ao criar o toggle do PC172.
- Fix: as duas funções agora envolvem TODO o corpo (incluindo o branch "já promovido") num único `st.container()` — do ponto de vista do chamador, a função sempre contribui exatamente 1 elemento, e toda a variação de conteúdo fica isolada dentro desse container.
- **CLAUDE.md** ganhou uma nova entrada na tabela de Pitfalls Conhecidos ("Variable child count in a shared UI component") — já apareceu 2x no projeto (`bpmn_tabs.py` original, agora `promote_asset.py`), vale documentar pra não repetir uma 3ª vez.
- 5 testes de regressão do PC172 continuam passando; 806/806 na suíte completa. Não há teste automatizado que capture especificamente o erro JS do frontend (é client-side, fora do alcance do `AppTest`) — verificação por leitura do padrão já validado em produção (`bpmn_tabs.py`) + revisão de código.

---

### PC173 — Concluído (v5.15 / 2026-07-10) — Nome do processo dentro do diagrama BPMN (Pool nomeado)

**Contexto:** usuário perguntou se dava pra mostrar o nome do processo dentro do diagrama; escolheu explicitamente a opção "mais correta" (padrão OMG — Pool nomeado) em vez de um título sobreposto em HTML.

- `agents/agent_bpmn.py::_generate_bpmn_xml_single()` — o `BpmnPool` (que carrega o nome do processo) antes só era criado `if model.lanes:`; processos sem lanes explícitas (o caso comum, um fluxo simples sem raias organizacionais) nunca ganhavam um Pool, e o nome nunca aparecia no canvas. Agora o Pool é sempre criado.
- `modules/bpmn_generator.py::generate_bpmn_xml()` (caminho single-pool) — quando o Pool não tem lanes reais, injeta uma lane sintética única (mesmo mecanismo `_SYN_LANE_SUFFIX` já usado por `_pool_as_process()` no caminho multi-pool/colaboração) só pra `_compute_layout()` ter pelo menos 1 lane pra trabalhar — nunca vaza pro `<bpmn:laneSet>` semântico. Extraído um helper compartilhado `_synthesize_lane_if_needed()` usado pelos dois caminhos (single-pool e multi-pool), eliminando duplicação.
- Verificado visualmente via Playwright: o resultado é uma única faixa lateral limpa com o nome do processo (rotacionado, como qualquer Pool BPMN) — sem barra em branco extra, porque bpmn-js já funde visualmente pool+lane sintética sem nome.
- Achado no caminho: `modules/bpmn_describer.py` (BPMN → descrição textual, usado no BPMN Studio) mostraria uma seção "Participantes (Pools)" redundante repetindo o nome do processo pra todo processo simples agora que ele também tem 1 Pool nomeado — corrigido pra só mostrar essa seção quando há de fato ≥ 2 participantes (colaboração real).
- 7 testes novos (`tests/test_bpmn_process_name_in_diagram.py`), 806/806 passando. Boot-smoke via AppTest em Pipeline/Diagramas/BpmnEditor/BpmnStudio sem exceção.

---

### PC172 — Concluído (v5.15 / 2026-07-10) — Fix de produção: expander aninhado quebrava as abas Reuniões/SBVR de Artefatos e a Biblioteca de Documentos

**Contexto:** erro relatado pelo usuário em produção — `StreamlitAPIException: Expanders may not be nested inside other expanders` ao abrir a aba Reuniões da Central de Artefatos. Causa raiz: `render_promote_button()` (componente de promoção a Ativo de Negócio, PC166) sempre envolvia o formulário num `st.expander()` próprio — funciona quando chamado de um contexto "plano", mas quebra sempre que o chamador já está dentro de outro `st.expander()`.

- 4 pontos de chamada já estavam nessa situação (aninhado, sempre quebrado — só a Ata foi a que o usuário bateu primeiro): `pages/Artefatos.py` aba Reuniões (Ata, dentro do expander por reunião), aba SBVR (Termo e Regra, cada um dentro do seu próprio expander), e `pages/DocumentManager.py` aba Biblioteca (cada documento já é um expander).
- Fix estrutural em vez de pontual: `render_promote_button()` e `render_promote_assistant_content_button()` (`ui/components/promote_asset.py`) não usam mais `st.expander()` — trocado por botão de toggle + flag em `st.session_state`, o mesmo padrão já documentado no pitfall "Nested `st.expander`" do CLAUDE.md. Corrige os 4 pontos de uma vez, e blinda qualquer chamador futuro (não depende de "lembrar" de não aninhar).
- 5 testes de regressão novos (`tests/test_promote_asset_nested_expander.py`) reproduzem a forma exata do bug (expander externo envolvendo `render_promote_button`/`render_promote_assistant_content_button`) via `AppTest.from_string()` — antes do fix, davam `StreamlitAPIException`; agora passam, incluindo o clique no toggle que abre o formulário. Achado no caminho (tooling, não produção): `AppTest.from_string()` neste ambiente Windows descarta widgets silenciosamente (sem exceção) quando o texto do script tem caracteres acentuados — scripts de teste reescritos em ASCII puro pra contornar.
- 799/799 testes passando; boot-smoke via `AppTest` em `Artefatos.py` e `DocumentManager.py` sem exceção.

---

### PC171 — Concluído (v5.15 / 2026-07-10) — Ajuste de mensagem + botão de download HTML + tool `gerar_variacao_apresentacao`

**Contexto:** 3 pedidos do usuário na mesma mensagem sobre o material comercial: (1) trocar "Sem documentação formal" por "Sem rastreabilidade ativa" (mais provocativo/engajador) no slide de problema; (2) botão pra salvar o conteúdo em HTML direto nas páginas Sobre/Apresentação; (3) o Assistente "ter em mente" essas duas páginas e ser capaz de reproduzi-las com variações.

- Texto do slide "O Problema" ajustado em `pages/ApresentacaoGeral.py` + `static/apresentacao-geral.html` (par sincronizado).
- Botão "⬇️ HTML" adicionado no topo de `pages/ApresentacaoGeral.py` e `pages/SobreP2D.py` — baixa o arquivo estático correspondente (`static/apresentacao-geral.html` / `static/sobre-p2d.html`) já existente no repo, sem gerar nada novo.
- **Nova tool `gerar_variacao_apresentacao(base, variacao_pedida)`** (`core/tools/tools_executive_advanced.py` + dispatch em `core/assistant_tools.py`) — usa o HTML estático de referência (Apresentação ou Sobre) como base de design/conteúdo e pede ao LLM uma nova versão HTML autocontida, mantendo CSS/paleta/estrutura mas adaptando texto ao pedido (ex: "focada em clientes de saúde"). Nunca sobrescreve o material oficial — resultado é um HTML avulso para download via `_pending_file_download` (mesmo mecanismo do PC161). Decisões confirmadas com o usuário (`AskUserQuestion`, ambas as recomendações aceitas): saída em HTML autocontido (não Markdown puro) e sem gate de admin.
- Achado no caminho: `static/sobre-p2d.html` tem ~2.7MB por causa da foto do autor embutida em base64 — enviar isso cru pro LLM custaria uma fortuna em tokens à toa. Fix: regex remove o blob base64 da imagem antes de montar o prompt, substituindo por um placeholder curto.
- 9 testes novos (`tests/test_tool_gerar_variacao_apresentacao.py`), 794/794 passando.

---

### PC170 — Concluído (v5.15 / 2026-07-10) — Material comercial: fluxo "A Jornada" + Ativos de Negócio atualizado

**Contexto:** pedido direto do usuário — atualizar as 3 peças de material comercial (Sobre, Apresentação Geral, HTML executivo para clientes) com as novidades do ciclo de Ativos de Negócio (PC166-168), incluindo um fluxo visual "super elegante" mostrando a jornada transcrição → ativo de negócio.

- Novo componente CSS `.journey` (círculos numerados + linha conectora em gradiente) reaproveitado nos 3 materiais: `outputs/apresentacao_executiva_p2d.html`, `pages/ApresentacaoGeral.py` + `static/apresentacao-geral.html` (par sincronizado), `pages/SobreP2D.py` + `static/sobre-p2d.html` (par sincronizado).
- Fluxo de 6 passos: Transcrição → IA Multi-Agente → Artefato Formal → Promoção Explícita → Ativo de Negócio → Catálogo do Domínio.
- `outputs/apresentacao_executiva_p2d.html` — novo slide 12 "A Jornada"; slide de Ativos de Negócio renumerado pra 13 e reescrito (tabela de governança agora cobre também Documentos enviados e Conteúdo do Assistente como promovíveis; texto reflete a classificação em 3 dimensões). Deck: 18 slides.
- `ApresentacaoGeral.py`/`SobreP2D.py` (+ pares estáticos) — texto de Compliance/CKF atualizado pra citar "promoção explícita" em vez do antigo "status/tags/dono".
- Bug encontrado e corrigido via screenshot Playwright (não detectável por validação de HTML): em `sobre-p2d.html`/`SobreP2D.py`, o `<span>` de ênfase dourada no novo `<h2>` da Jornada não herdava a cor porque a regra CSS `.slide-card h1 span` só cobre `h1`; corrigido com `style="color:var(--gold2);"` inline.
- Sem testes automatizados dedicados (páginas HTML/apresentação) — verificado via Playwright (screenshot real do navegador) nas 3 peças.

---

### PC169 — Concluído (v5.15 / 2026-07-10) — Upload de imagens (Documentos + Assistente) + fix de labels cortados no Gantt

**Contexto:** 2 pedidos diretos do usuário. Escopo de imagem restrito por decisão do usuário (`AskUserQuestion`): só `DocumentManager.py` (aba Enviar) e o anexo de contexto do `Assistente.py` — não a transcrição do Pipeline nem os Arquivos de Contexto do CKF. Sem OCR/visão computacional ainda (isso é a Etapa 0, maior, de `melhorias/cognicao-de-negocio.md`, não iniciada) — a decisão foi "aceitar o arquivo, guardar sem extrair texto".

- **`pages/DocumentManager.py`** — aba Enviar aceita `.png/.jpg/.jpeg/.gif/.webp/.bmp` além dos formatos de texto já existentes. Imagem é **guardada de verdade** (base64 em `meeting_documents.metadata`, guarda de 5 MB) e fica **visível na Biblioteca** via `st.image()` — não é só uma nota de texto sem conteúdo recuperável. `content_text` recebe um placeholder explícito ("conteúdo textual não extraído..."); embedding é pulado pra imagem (não tem valor gerar embedding de um placeholder). Achado no caminho: o fallback de `_load_file_content()` pra tipo não suportado tentava decodificar bytes binários como UTF-8 (produziria lixo/mojibake) — agora detecta imagem antes e retorna vazio direto.
- **`pages/Assistente.py`** — anexo de contexto também aceita os mesmos formatos de imagem, mas aqui não há persistência (é contexto efêmero de conversa) nem visão computacional no LLM — em vez de injetar bytes decodificados como "contexto" (que seria lixo no prompt), mostra um aviso claro e não popula `_asst_file_ctx`.
- **Gantt (`generate_gantt_chart`)** — bug relatado pelo usuário: labels do eixo Y (nomes de fase, texto livre) ficavam cortados/ilegíveis. Causa: `_dark_layout()` (compartilhado por todos os gráficos do Assistente) aplica margem esquerda FIXA (`l=50`) — suficiente pra categorias curtas, não pra nomes de fase longos. Fix: `yaxis=dict(automargin=True)` só no Gantt (não mudou `_dark_layout()` em si, pra não afetar os outros ~15 tipos de gráfico que nunca reportaram o problema).
- [x] 1 teste novo pro Gantt (`tests/test_tools_requirement_charts.py`). Upload de imagem não tem teste automatizado dedicado — simulação de `st.file_uploader` não é suportada pela API de teste desta versão do Streamlit (mesma limitação já documentada no PC163); verificado via `AppTest` de boot (sem exceção) + revisão de código.
- [x] 785/785 testes automatizados passando.

---

### PC168 — Concluído (v5.15 / 2026-07-09) — Ativos de Negócio: Promoção de Conteúdo do Assistente (Fase C)

**Contexto:** fecha `melhorias/promocao-ativos-negocio.md` — Fase C, a última do plano. Diferente das Fases A/B (promovem algo que já existia numa tabela), aqui a promoção precisa primeiro **criar** o próprio conteúdo, já que nada do que o Assistente gera sob demanda é persistido hoje (só existe como download efêmero no navegador).

- **Migration `setup/supabase_migration_assistant_artifacts.sql`** (executada e verificada) — tabela nova `assistant_artifacts` (id, project_id, title, content_markdown, source_tool, meeting_id, created_by, created_at). `assistant_artifact` entra em `ASSET_TYPES_WITH_METADATA` (7 tipos governáveis agora).
- **`core/project_store.py`** — `promote_assistant_output_to_asset()`: grava o snapshot em `assistant_artifacts` **e** a linha em `asset_metadata` numa única chamada; recusa (sem tocar o banco) se título/conteúdo estiverem vazios ou as 3 classificações obrigatórias faltarem. `list_assistant_artifacts_by_project()`. `_hydrate_promoted_assets()` ganhou `extra_fn` opcional — usado aqui pra propagar `content_markdown`/`source_tool` pro item exibido (única forma de a Central de Ativos mostrar o conteúdo real, já que este tipo não tem "reunião de origem" pra remeter).
- **Rastreamento de tools por mensagem** (`pages/Assistente.py`) — o histórico do chat (`assistant_history`) não guardava quais tools uma resposta usou; passou a gravar `tools_used` em cada entrada. Critério de promoção (decidido com o usuário: "análises, pesquisas, gráficos, relatórios — não perguntas simples") traduzido em código: mensagem com pelo menos uma tool `generate_*`/`gerar_*`/`simular_cenario`/`diagnostico_projeto`/etc. ganha o botão de promoção; consultas simples (`get_meeting_list`, `get_requirements`...) não.
- **Nova tool do Assistente `promover_ativo_negocio`** (`core/tools/tools_executive_advanced.py` + dispatch em `core/assistant_tools.py`) — permite promoção por linguagem natural no chat ("promova este relatório a ativo estratégico"), sem gate de admin (decisão do usuário — projeto ainda não tem perfis granulares).
- **`pages/AtivosDeNegocio.py`** — novo tipo "🤖 Conteúdo do Assistente", com visualização própria (prévia + expandir texto completo, mesmo padrão de `DocumentManager.py`).
- [x] 17 testes novos (`tests/test_promote_assistant_output.py` — 7; `tests/test_tool_promover_ativo_negocio.py` — 8; 2 novos em `test_list_all_business_assets.py`).
- [x] 4 páginas (`Artefatos.py`, `AtivosDeNegocio.py`, `DocumentManager.py`, `Assistente.py`) verificadas sem erro via `AppTest`.
- [x] 784/784 testes automatizados passando.
- **`melhorias/promocao-ativos-negocio.md` fecha as 3 fases** — promoção explícita agora cobre os 7 tipos de origem possíveis (5 do pipeline + documentos + conteúdo do Assistente). BMM/DMN/IBIS/Relatórios do pipeline padrão seguem somente-leitura (decisão do PC164, não revisitada).

---

### PC167 — Concluído (v5.15 / 2026-07-09) — Ativos de Negócio: Promoção de Documentos (Fase B)

**Contexto:** continuação direta do PC166 na mesma sessão — Fase B de `melhorias/promocao-ativos-negocio.md`. Estende a promoção explícita (já entregue para requisito/BPMN/SBVR/ata) para documentos enviados via `DocumentManager.py`.

- **`core/project_store.py`** — `document` entra em `ASSET_TYPES_WITH_METADATA` (6 tipos agora); `list_all_business_assets()` ganhou o bloco de hidratação de `document` (reaproveita `modules.document_store.list_documents()`, sem query nova). Novo `DOCUMENT_CATEGORY_TO_FORMAL_CLASSIFICATION` + `suggest_formal_classification_for_document(doc_type)` — único `artifact_type` com sugestão automática de Classificação Formal (as 9 categorias de `document_types` mapeiam quase 1:1 nas classes AN-01..AN-12, achado já registrado no plano §3.3); nunca força, só pré-seleciona.
- **`pages/DocumentManager.py`** (aba Biblioteca) — botão "⭐ Promover a Ativo de Negócio" por documento, reaproveitando o mesmo componente `ui/components/promote_asset.py` da Fase A, com a Classificação Formal já vindo pré-marcada pela categoria do `doc_type`.
- **`pages/AtivosDeNegocio.py`** — novo tipo "🗂️ Documentos" na Central de Ativos, mesmo tratamento de filtros/badges/despromoção dos outros 5 tipos governáveis.
- [x] 7 testes novos (`tests/test_document_promotion.py` — 5; `tests/test_list_all_business_assets.py` — 2 novos para o tipo `document`; ajuste em `tests/test_asset_metadata.py` para os 6 tipos suportados).
- [x] `pages/DocumentManager.py` verificado sem erro via `AppTest` (com contexto ativo simulado).
- [x] 767/767 testes automatizados passando.
- **Verificação ao vivo (E2E real) tentada e documentada como bloqueada** — a chave do Supabase no `secrets.toml` local tem RLS sem policy permissiva (limitação já conhecida desde o PC164, não introduzida por este trabalho); confirmado que leitura via `supabase-py` retorna vazio silenciosamente mesmo para dados reais confirmados via `psycopg2` direto. Verificação ficou em: testes unitários com Supabase mockado + `AppTest` de boot sem exceção (mesmo padrão já usado nas fases anteriores).
- **Fase C (conteúdo do Assistente) segue para uma próxima entrega** — exige tabela nova `assistant_artifacts`, ainda não criada.

---

### PC166 — Concluído (v5.15 / 2026-07-09) — Ativos de Negócio: Promoção Explícita + Classificação em 3 Dimensões (Fase A)

**Contexto:** implementa a Fase A de `melhorias/promocao-ativos-negocio.md` — plano escrito e refinado em várias rodadas na mesma sessão (perspectiva multi-valor, taxonomia de 12 classes AN-01..AN-12 baseada em ISO 55000/APQC PCF/BIZBOK/TOGAF trazida pelo usuário, justificativa obrigatória, promoção em lote, despromoção com histórico, permissão aberta). Muda a premissa central da Central de Ativos: **um artefato só é ativo de negócio depois de promovido explicitamente** — deixa de listar automaticamente tudo que existe no projeto (comportamento do PC164).

- **Migration `setup/supabase_migration_asset_promotion.sql`** (executada e verificada via psycopg2) — 6 colunas novas em `asset_metadata`: `business_interest`, `business_perspective` (`TEXT[]`), `formal_classification`, `promotion_justification`, `promoted_at`, `promoted_by`. Linhas já existentes desde PC164/165 recebem defaults (fail-open, sem perda de dado).
- **`core/project_store.py`** — `promote_to_business_asset()` (exige as 3 classificações + justificativa não-vazia, recusa senão); `demote_business_asset()` (move `status` para `arquivado`, nunca apaga); `upsert_asset_metadata()` estendida com as 4 novas colunas e um guard novo: **recusa criar linha nova sem as 3 classificações** — só editar uma linha já promovida continua funcionando sem exigir os campos de novo. `list_all_business_assets()` **reescrita**: em vez de varrer as tabelas de origem e enriquecer com metadata por fora, agora enumera `asset_metadata` (via novo helper `_hydrate_promoted_assets()`) e hidrata título/reunião pela tabela de origem — item cujo artefato de origem sumiu não desaparece, ganha um título de fallback.
- **`ui/components/promote_asset.py`** (novo) — `render_promote_button()` (formulário de promoção por item) e `render_classification_fields()` (os 4 campos, reutilizados por promoção individual, em lote e reclassificação de ativo já promovido, com defaults opcionais para o caso de edição).
- **`pages/Artefatos.py`** — botão de promoção plugado nas abas Requisitos (painel de detalhe), BPMN (processo selecionado), SBVR (termo e regra) e Reuniões (ata); seção "📦 Promoção em Lote" na aba Requisitos — multi-select respeitando os filtros já ativos, **tabela de revisão completa obrigatória antes de confirmar** (exigência explícita do usuário), mesma classificação aplicada a todos os itens do lote.
- **`pages/AtivosDeNegocio.py`** — filtros novos por Interesse/Perspectiva/Classificação Formal; badges das 3 dimensões + justificativa no corpo de cada card; arquivados ocultos por padrão (checkbox "Mostrar arquivados"); formulário de edição ganhou os 4 campos de reclassificação; botão "🗄️ Despromover".
- [x] 23 testes novos (`tests/test_promote_to_business_asset.py` — 9; `tests/test_asset_metadata.py` — 2 novos cobrindo o guard; `tests/test_list_all_business_assets.py` — reescrito para o modelo "só promovidos", 8 testes).
- [x] `pages/Artefatos.py` e `pages/AtivosDeNegocio.py` verificados sem erro via `AppTest`.
- [x] 760/760 testes automatizados passando.
- **Fases B (Documentos) e C (conteúdo do Assistente) do plano ficam para uma entrega futura** — Fase A é auto-contida e já entrega o núcleo (promoção explícita + as 3 classificações) para os 5 tipos com linha própria no banco.

---

### PC165 — Concluído (v5.15 / 2026-07-09) — Ativos de Negócio: Catálogo do Domínio (cross-contexto)

**Contexto:** pedido direto do usuário, na sequência do PC164 — um catálogo de ativos de negócio visualizável em todos os contextos do domínio (tenant), não só no contexto ativo da sessão. Concretiza o item "Reuso cross-contexto" listado como diferencial em `melhorias/cognicao-de-negocio.md` §8.

- **Investigação prévia (Explore agent) sobre o modelo tenant/contexto** antes de codificar: confirmou que "domínio" é sinônimo de tenant (empresa) no app — `tenants(id, domain_slug, display_name, ...)`, sessão grava `_tenant_id`/`_tenant_name` no login — e que `contexts.tenant_id` já é lido/escrito por `list_contexts()`/`create_context()` apesar de não ter uma migration versionada dedicada (schema drift documentado, não corrigido nesta entrega — fora de escopo). Também confirmou que **não existe hierarquia real de domínio→contextos** além do FK `tenant_id`: "domínio" como valor de `context_type` no formulário de novo contexto é um rótulo plano não relacionado.
- **`core/project_store.py::list_all_business_assets_for_domain(tenant_id)`** — reaproveita `list_contexts(tenant_id)` + `list_all_business_assets(project_id)` já existentes (nenhuma query nova): itera cada contexto do tenant, mescla os 9 tipos de ativo, e marca cada item com `context_id`/`context_name`. `tenant_id=None` cai no mesmo fallback de `list_contexts()` (todos os contextos — login local/dev/admin sem tenant). Custo aceito: 1 + ~5×N queries para N contextos do tenant.
- **`pages/AtivosDeNegocio.py`** — toggle "Escopo" (`📁 Este contexto` / `🌐 Catálogo do Domínio`) acima dos filtros existentes; no escopo de domínio, filtro adicional por contexto e subtítulo de cada ativo passa a mostrar o contexto de origem. O formulário de metadados grava sempre em `item.get("context_id") or project_id` — nunca no contexto ativo da sessão — para que editar um ativo de outro contexto não vá parar no projeto errado.
- Decisão de design: estendido o toggle na página já existente (Etapa 1 do PC164), não criada uma página nova — a lista e a governança são as mesmas, só muda o escopo de agregação; separar em duas páginas duplicaria toda a lógica de filtro/formulário sem ganho real.
- [x] 6 testes novos (`tests/test_list_all_business_assets_for_domain.py`), mockando `list_contexts`/`list_all_business_assets` (mesmo padrão de `test_list_all_business_assets.py`) — cobre mesclagem multi-contexto, tag de `context_id`/`context_name`, contexto sem `id` ignorado, `tenant_id=None`, e não-mutação do item original.
- [x] Página verificada sem erro via `AppTest` (para no login gate, mesmo comportamento de qualquer página sem sessão).
- [x] 747/747 testes automatizados passando.

---

### PC164 — Concluído (v5.15 / 2026-07-08) — Ativos de Negócio: Visão Agregada + Metadados (Etapas 1+2)

**Contexto:** implementa Etapas 1 e 2 de `melhorias/cognicao-de-negocio.md` (aprovado no mesmo dia após 5 rodadas de revisão adversarial) — a evolução do RawToInsights AI de "gerador de artefatos por reunião" para "sistema de ativos de negócio governáveis". Etapa 0 (ingestão visual) e Etapas 3-5 (ferramentas do Assistente, dashboard, botão de promoção) ficam para rodadas futuras, dependentes desta entrega.

- **Achado que redefiniu o escopo real, confirmado com o usuário antes de codificar:** o documento aprovado promete metadados "em cada artefato", mas só 5 dos 8 tipos têm linha própria (UUID real) no banco — Requisitos, BPMN, SBVR Termos, SBVR Regras, Atas. BMM/DMN/IBIS/Relatórios só existem como JSON dentro de `meetings.*_json` (`bmm_json`/`dmn_json`/`argumentation_json`/`report_html`), sem `artifact_id` de linha própria. Decisão: `asset_metadata` cobre apenas os 5 tipos com ID real agora; os outros 4 aparecem na Visão Agregada como somente-leitura, com a lacuna documentada na UI (não escondida). Chave sintética (`"meeting_id:decision_id"` como `TEXT`) registrada como estudo de evolução futura, não implementada.
- **`setup/supabase_migration_asset_metadata.sql`** — tabela genérica polimórfica ("Rota B", já decidida no documento): `asset_metadata(project_id, artifact_type, artifact_id, status, tags[], owner, notes)`, `UNIQUE(project_id, artifact_type, artifact_id)`. `status` de ativo (`rascunho`/`ativo`/`arquivado`) é uma dimensão separada do status de negócio já existente em `requirements`/`bpmn_processes`.
- **`core/project_store.py`** — `list_bmm_by_project()` (não existia nenhuma listagem de BMM até agora — só era lido por reunião individual via `load_meeting_as_hub`); `list_reports_by_project()` (não existia listagem project-wide de relatórios — só `get_report_html(meeting_id)`); `get_asset_metadata_map()` / `upsert_asset_metadata()` (preserva campos omitidos — só sobrescreve o que é passado); `list_all_business_assets()` — agregador que junta os 9 tipos numa estrutura única para a página.
- **`pages/AtivosDeNegocio.py`** (nova, grupo "Análise") — uma página cobre as duas etapas juntas (lista unificada + metadados inline), não duas entregas sequenciais: lista sem metadados seria descartável assim que a Etapa 2 chegasse. Filtro por tipo/busca por título; os 5 tipos com suporte ganham formulário inline (status/tags/owner/notas) salvo via `upsert_asset_metadata`; os 4 somente-leitura mostram badge "🔒 Metadados indisponíveis".
- [x] 22 testes novos (`tests/test_asset_metadata.py`, `tests/test_list_bmm_by_project.py`, `tests/test_list_all_business_assets.py`).
- [x] Página verificada sem erro via `streamlit.testing.v1.AppTest` (para no login gate, mesmo comportamento de qualquer página sem sessão autenticada — sem exceção).
- [x] 741/741 testes automatizados passando.
- **Verificação de schema real via `psycopg2` direto antes de codificar** (mesmo método já usado em PC161-163): confirmou `contexts` como nome real da tabela de projeto-pai e ausência prévia de `asset_metadata`; migration executada e schema resultante conferido coluna a coluna.

---

### PC163 — Concluído (v5.15 / 2026-07-08) — Onda 3 de melhorias do Assistente (workflow de revisão + Importador de Planilha)

**Contexto:** fecha `melhorias/avaliacao-proposta-assistente-20260708.md` — última das 3 ondas priorizadas. Diferente de todas as tools anteriores (Ondas 1 e 2), os 2 itens desta onda são de naturezas distintas: um é uma tool de chat pequena, o outro é uma página/UI inteira (não cabe no padrão de tool).

- **`solicitar_revisao_requisito(req_number, motivo, revisor_sugerido=None)`** (`core/tools/tools_meetings_requirements.py`) — fluxo de revisão estruturado, escopo explicitamente reduzido da proposta original #4 (sem notificação por e-mail/Slack — essa infra não existe no projeto). Implementado **direto**, não delegado a `update_requirement_status`: essa função early-retorna "sem alteração" quando `old_status == new_status`, o que dropraria silenciosamente um segundo pedido de revisão num requisito já `revised`. `diagnostico_projeto()` ganhou `include_revision_requests` (padrão `true`) — única forma de visibilidade do pedido, já que não há notificação.
- **Importador de Planilha de Requisitos** (`pages/DocumentManager.py`, 7ª aba "📊 Importar Planilha") — usuário escolheu a versão completa com mapeamento interativo de coluna (não a v1 enxuta de formato fixo). Upload `.xlsx` → preview → mapeamento de coluna (sugestão automática por nome) → análise com checagem leve de duplicata → `st.data_editor` para revisão/edição → confirmação. `core/project_store.py` ganhou `find_similar_existing_requirements()` (screening `difflib`, sem LLM/embedding, nunca bloqueia — só sinaliza) e `import_requirements_from_rows()` (reaproveita `save_new_requirement()` com o **mesmo** padrão de rastreabilidade que `save_artifacts_from_document` já usa: `meeting_id=None`, `origin="documento"`, `doc_ref=<uuid do .xlsx registrado via upload_document>`) — nenhuma migration nova.
  - `cluster_similar_requirements` (dedup por embedding já existente) **não é reaproveitável** aqui — hardcoded a filtrar por `first_meeting_id` de uma reunião específica; requisitos importados de planilha têm `first_meeting_id=NULL` (mesmo padrão do caminho "documento"). `merge_requirements` **é** reaproveitável sem adaptação (não depende de reunião) — mencionado no resultado do import como caminho para consolidar duplicatas remanescentes.
  - `pandas` (antes só dependência transitiva do Streamlit, já usada em `Assistente.py`/aba Taxonomia) promovida a dependência direta pinada (`pandas==2.3.3`) em `requirements.txt`, já que passa a ser essencial (`pandas.read_excel`).
- [x] 18 testes novos (`tests/test_solicitar_revisao_requisito.py`, `tests/test_diagnostico_projeto_revision_requests.py`, `tests/test_import_requirements_from_rows.py`, `tests/test_find_similar_existing_requirements.py`).
- [x] Página verificada sem erro via `streamlit.testing.v1.AppTest` (boot + 7 abas renderizando) — simulação de upload de arquivo não é suportada pela API de teste da versão de Streamlit em uso; o wizard interativo (upload → mapear → confirmar) fica para verificação manual, mesma convenção já usada para outras páginas complexas do projeto.
- [x] 719/719 testes automatizados passando.
- **Onda 3 fecha as 9 propostas viáveis identificadas na avaliação original.** Itens não implementados (Classificador de Maturidade, ADR, Jira/ADO, Benchmarking/Catálogo/Biblioteca cross-projeto) seguem documentados em `melhorias/avaliacao-proposta-assistente-20260708.md`, sem plano de execução — aguardando demanda.

---

### PC162 — Concluído (v5.15 / 2026-07-08) — Onda 2 de melhorias do Assistente (3 tools + 3 bugs reais adicionais)

**Contexto:** continuação de PC161 — `melhorias/avaliacao-proposta-assistente-20260708.md` priorizou 9 propostas em 3 ondas por esforço/reaproveitamento. Onda 1 (3 quick wins) concluída em PC161; esta entrada cobre a Onda 2 (esforço moderado).

- **`gerar_release_notes(meeting_number_inicio, meeting_number_fim)`** (`core/tools/tools_executive_advanced.py`) — consolida todas as mudanças de `requirement_versions` entre 2 reuniões-marco, agrupadas por `change_type`, e sintetiza em prosa via 1 chamada LLM (mesmo padrão de `gerar_deck_executivo`/`gerar_project_charter` — dados agregados em Python, só a redação final via LLM).
- **`analisar_tendencias(top_n=5)`** (`core/tools/tools_knowledge_requirements2.py`) — sem LLM: requisitos mais instáveis (mais versões em `requirement_versions`), temas IBIS mais debatidos (ranking por nº de alternativas via `_load_ibis_questions()`, já existente), contradições por severidade/status (`kh_contradictions`). Decisão explícita de escopo: **não** inclui ranking de "participante com contribuições mais contestadas" (proposta original) — nenhuma tabela liga uma contradição/revisão a um autor específico; aproximar isso a partir de texto livre arriscaria fabricação. Documentado no docstring da tool e coberto por um teste dedicado (`test_never_ranks_participants`).
- **`estimar_risco_requisito(req_number=None, top_n=10)`** (`core/tools/tools_meetings_requirements.py`) — score 0-100 por requisito via fórmula heurística ponderada e transparente: nº de revisões (instabilidade), contradição sinalizada em alguma versão, ausência de `source_quote` (rastreabilidade fraca), descrição curta/vaga (heurística simples de ambiguidade — não NLP), prioridade alta sem status avançado. Sempre mostra os fatores que compuseram o score, nunca um número isolado — evita a aparência de julgamento definitivo de uma heurística simples.
- **3 bugs reais adicionais achados verificando o schema real via `psycopg2` direto antes de codificar** (mesmo método que já tinha pego 2 bugs no fechamento do PC161):
  - `diff_requirement()` (`core/tools/tools_knowledge_requirements2.py`) selecionava `status, changed_at, change_note` de `requirement_versions` — nenhuma dessas colunas existe (as reais são `change_summary`/`created_at`; `status` vive em `requirements`, não em `requirement_versions`). 100% quebrado em produção, confirmado com uma chamada real contra o Supabase antes e depois do fix.
  - `verificar_rastreabilidade_obrigatoria()` (código do próprio PC161, do dia anterior) consultava uma tabela `argumentation_questions` que **não existe** — IBIS vive como JSON em `meetings.argumentation_json`, lido via `_load_ibis_questions()` (helper já compartilhado por `search_ibis_debates`/`get_ibis_timeline`). O gap de IBIS sempre reportava 0 silenciosamente. Corrigido para usar o helper certo; teste de regressão adicionado com um fake DB que **explode** se qualquer tabela fora da lista de tabelas reais for consultada diretamente.
- [x] 16 testes novos (`tests/test_gerar_release_notes.py`, `tests/test_analisar_tendencias.py`, `tests/test_estimar_risco_requisito.py`) + testes de regressão para os 3 bugs achados (`tests/test_diff_requirement_columns.py`, atualização de `tests/test_verificar_rastreabilidade_obrigatoria.py`).
- [x] 701/701 testes automatizados passando.
- **Onda 3 (Importador de Planilha, Workflow de Aprovação sem notificação) fica para quando houver demanda — ver avaliação completa em `melhorias/avaliacao-proposta-assistente-20260708.md`.**

---

### PC161 — Concluído (v5.15 / 2026-07-08) — Onda 1 de melhorias do Assistente (avaliação + 3 tools novas + 2 bugs reais corrigidos)

**Contexto:** o próprio Assistente propôs 18 novas ferramentas em `melhorias/proposta-assistente-20260708.md` (auto-sugestão). Antes de implementar qualquer coisa, foi feita uma avaliação de viabilidade completa (`melhorias/avaliacao-proposta-assistente-20260708.md`) contra o catálogo real de ~140 tools em `core/tools/*.py` — achado: 6 das 18 propostas já existiam sob outro nome, 3 exigiam mudança de arquitetura (cross-project query, hoje `AssistantToolExecutor` opera só 1 `project_id` por vez), e 9 valiam construir. Priorizadas por reaproveitamento de infraestrutura já testada, não por frente temática.

- **`export_project_charter_docx`** (`core/tools/tools_executive_advanced.py`) — mesmo conteúdo de `gerar_project_charter()`, exportado como `.docx` em vez de Markdown no chat. `modules/minutes_exporter.py::markdown_to_docx()` (novo) — conversor genérico Markdown→docx, reaproveitando `_render_markdown_docx()` (já usado como fallback de ata desde PC160) para qualquer artefato LLM que não seja um `MinutesModel`.
- **Mecanismo de download generalizado** — `pages/Assistente.py` + `core/tools/tools_admin_charts_entities.py::get_executive_report()`: `_pending_report_html`/`report_download` (só HTML, só relatório executivo) virou `_pending_file_download`/`file_download` (com `mime`/`label` genéricos) — agora qualquer tool pode enfileirar um binário para download, não só o relatório.
- **`compare_meetings`** (`core/tools/tools_meeting_ops_calendar.py`) — diff visual entre 2 atas específicas (participantes que entraram/saíram, decisões novas, encaminhamentos novos/sumidos). Diferente de `compare_meeting_transcripts` (similaridade textual pra achar duplicatas). Reaproveita o widget `req_diff_html` já cabeado (mesmo padrão visual de `diff_requirement`).
- **`verificar_rastreabilidade_obrigatoria`** (`core/tools/tools_knowledge_requirements2.py`) — gap analysis agregado do projeto inteiro, sem LLM: requisitos sem `source_quote`, questões IBIS sem alternativa nem resolução, processos BPMN sem descrição. Diferente de `diagnostico_projeto` (saúde de pipeline) — aqui o foco é completude de conteúdo.
- **Bug real #1 achado no caminho**: `core/tools/tools_meetings_requirements.py::_section()` estava sem `self` na assinatura — todo `self._section(...)` (13 call sites em 5 arquivos, incluindo `gerar_project_charter`/`gerar_deck_executivo`) quebrava com `TypeError` sempre que chamado. Nunca pego por teste porque nenhum teste existente exercitava esse caminho — só apareceu ao testar de verdade o Tool 1 desta rodada.
- **Bug real #2 achado no caminho**: mesmo depois do fix acima, 7 desses `_section(...)` call sites (extração de "encaminhamentos"/action items) usavam nomes alternativos ("Itens de Ação", "Action Items", "Ações") que nunca batiam com o heading REAL que `AgentMinutes.to_markdown()` escreve ("Encaminhamentos / Action Items") — o regex de `_section()` exige a linha do heading terminar logo após o nome buscado. `gerar_project_charter`, `gerar_deck_executivo` e a tool documentada `get_meeting_action_items` retornavam contexto de encaminhamentos vazio silenciosamente, sem erro, por tempo indeterminado.
- [x] 16 testes novos (`tests/test_markdown_to_docx.py`, `tests/test_tools_executive_advanced.py`, `tests/test_section_action_items_heading.py`, `tests/test_compare_meetings.py`, `tests/test_verificar_rastreabilidade_obrigatoria.py`), incluindo testes que rodam a implementação REAL (não mockada) de `gerar_project_charter`/`get_meeting_action_items` especificamente para provar que os 2 bugs foram corrigidos, não só a feature nova.
- [x] 682/682 testes automatizados passando.
- **Não implementado nesta rodada (ver avaliação completa)**: Classificador de Maturidade, ADR, Jira/ADO (doc próprio precisa reescrita contra a stack real), Edição Visual de BPMN (já existe como `apply_bpmn_corrections`), Trilha de Auditoria (já existe como `get_requirement_history`+`diff_requirement`), Tour Guiado (melhor como página estática), Benchmarking/Catálogo/Biblioteca cross-projeto (mudança de arquitetura, Fase separada), Importador de Planilha e Workflow de Aprovação com notificação (Onda 3, avaliar demanda antes).

---

### PC160 — Concluído (v5.15 / 2026-07-08) — modelo de ata (Word) por contexto

**Contexto:** pedido direto do usuário — domínios/contextos diferentes (ex: fgv/SDEA) têm seus próprios templates visuais de documentos; a ata gerada pelo pipeline deveria seguir o template Word configurado para o contexto ativo, com detecção automática de estilo (cor de destaque, logo/imagens). Fase 1 = apenas ata, um template por contexto, extração automática de elementos de identidade visual; permissão restrita a admin/master (ideia de "admin de contexto" separada e adiada — ver `melhorias/rbac-admin-de-contexto.md`).

- **`modules/ata_template_engine.py`** (novo, sem Streamlit/rede) — `extract_template_from_docx(docx_bytes)`: percorre os parágrafos `Heading N` do `.docx` de referência e monta um esqueleto Markdown (`#`/`##`/`###`) na mesma ordem/nomes; detecta cor de destaque via `_dominant_heading_color()` (cor do primeiro run de heading com `font.color.rgb` explícito); extrai logo/imagens de header/footer/corpo via `_extract_images_from_part()` (percorre `part.rels`, filtra `RELATIONSHIP_TYPE.IMAGE`); tenta extrair fundo de página legado via XML VML (`w:background`/`v:fill`, best-effort). `apply_template_to_docx(minutes, style_spec, assets)` — wrapper fino sobre `to_docx()`.
- **`modules/minutes_exporter.py::to_docx()`** — parametrizado com `template_spec: dict | None = None` opcional; quando presente, aplica `accent_color` nos headings e insere o primeiro asset `logo`/`header_image` no cabeçalho do documento (`doc.sections[0].header`). Retrocompatível: sem `template_spec`, saída idêntica à anterior.
- **`core/project_store.py`** — CRUD novo (`list_ata_templates`, `get_active_ata_template`, `save_ata_template`, `activate_ata_template`, `deactivate_ata_template`, `delete_ata_template`) sobre as tabelas `ata_templates`/`ata_template_assets`; `save_ata_template()` chama `extract_template_from_docx()`, desativa o template ativo anterior do contexto (unicidade via índice parcial) e persiste template + assets (imagens em base64). Sem checagem de `is_admin()` no core — permissão fica na camada de UI, por convenção do projeto.
- **`core/knowledge_hub.py`** — novos campos `ata_template_markdown: str` e `ata_template_spec: dict | None`, com guards em `migrate()`.
- **`agents/agent_minutes.py::build_prompt()`** — quando `hub.ata_template_markdown` está presente, injeta instrução no system prompt para a ata seguir a mesma estrutura/nomes de seção do template (mesmo padrão de injeção usado pelo CKF).
- **`pages/Pipeline.py`** — carrega `get_active_ata_template(context_id)` logo após o carregamento do CKF, populando `hub.ata_template_markdown`/`hub.ata_template_spec`; fail-open (sem template ativo → comportamento de sempre).
- **`ui/tabs/minutes_tab.py`** e **`ui/tabs/export_tab.py`** — passam `template_spec=getattr(hub, "ata_template_spec", None)` para `to_docx()`.
- **`pages/Settings.py`** — nova seção "📝 Modelo de Ata por Contexto" (gated por `is_admin()`): upload de `.docx` de referência, extração + ativação automática, preview do Markdown/cor/imagens detectados, lista de templates existentes com Ativar/Desativar/Excluir.
- **`setup/supabase_migration_ata_templates.sql`** (executada pelo usuário) — tabelas `ata_templates` (com índice parcial único garantindo no máximo 1 template ativo por contexto) e `ata_template_assets`, ambas com `ENABLE ROW LEVEL SECURITY` sem policies (app usa `service_role`, que ignora RLS) — convenção confirmada em `setup/supabase_migration_enable_rls.sql` (a primeira versão do arquivo usava `DISABLE ROW LEVEL SECURITY`, corrigida antes da execução após o Supabase acusar o risco na UI).
- [x] 20 testes novos (`tests/test_ata_template_engine.py`): extração de esqueleto Markdown, detecção de cor de destaque (presente/ausente), extração de logo do header, `to_docx()` com/sem `template_spec` (cor aplicada, cor malformada não quebra, logo inserido), CRUD completo via Supabase mockado, injeção de template no prompt do `AgentMinutes`.
- [x] 642/642 testes automatizados passando.
- **Lição de teste registrada**: `core/project_store.py` importa `get_supabase_client` uma única vez no topo do módulo (diferente dos mixins de `core/tools/*.py`, que importam localmente dentro de cada função) — mockar exige `patch("core.project_store._db", ...)`, não `patch("modules.supabase_client.get_supabase_client", ...)` (que não intercepta nada e deixa a chamada real vazar para a API do Supabase).
- **Gap encontrado e corrigido no teste manual em produção (mesmo dia)**: `hub.ata_template_spec` só era carregado no fluxo "Nova transcrição" de `pages/Pipeline.py` — reunião existente carregada via `load_meeting_as_hub()` (Modo B) e o botão "⬇️ Ata (.docx)" da Central de Artefatos nunca aplicavam cor/logo do modelo ativo, mesmo reprocessando o agente Ata (a estrutura de seções seguia o template porque isso é injeção de prompt, mas o `.docx` exportado saía sem estilo). Corrigido carregando `get_active_ata_template()` também após `load_meeting_as_hub()` em `pages/Pipeline.py`, e em `pages/Artefatos.py` (aba Reuniões) — consulta única por aba, fora do loop de reuniões, não por reunião individual.
- **Bug real encontrado com o `.docx` REAL do usuário (contexto `fgv/FGV Projetos & DTI`), mesmo dia**: `extract_template_from_docx()` só reconhecia heading pelo NOME do estilo Word (`Heading N`/`Título N`). O template real do usuário usa exclusivamente `Normal`/`List Paragraph` com negrito+cor manuais simulando títulos — `accent_color` e `template_markdown` saíam sempre vazios, mesmo com o modelo corretamente cadastrado e ativo. Fix: `_collect_heading_paragraphs()` — fallback (só quando o documento inteiro não tem NENHUM heading de estilo Word) para parágrafos com primeiro run em negrito + cor explícita, nível por ranking de tamanho de fonte. Verificado contra o arquivo real: `accent_color` `None` → `#1F4E79`, `template_markdown` vazio → estrutura completa de 2 partes/seções. 3 testes novos, 645/645 passando.
- **PC160-D — segundo bug real, achado comparando modelo × ata exportada lado a lado (mesmo dia)**: a linha separadora (borda inferior) desenhada sob cada título de seção tinha a cor FIXA no código (`"2E7FD9"`, azul padrão) — nunca usava `accent_color` do template, mesmo com a cor do próprio texto do título corretamente sobrescrita. O caminho de fallback markdown (`_render_markdown_docx`, usado quando a reunião só tem `minutes_md` — exatamente o caso do Modo B / Central de Artefatos) não desenhava separador NENHUM. Fix: `_heading()` usa `str(ACCENT)` (já sobrescrita); headings `##` do fallback ganharam a mesma borda, na cor recebida. 3 testes novos, 648/648 passando.
- **Itens fora do escopo da Fase 1, identificados na mesma comparação**: o modelo real usa TABELAS de verdade para Participantes (Nome/E-mail/Unidade, cabeçalho preenchido na cor de destaque) e para Ações (3 tabelas separadas por status — Realizadas/Em Andamento/Próximas), além de organizar a reunião em blocos "1ª PARTE"/"2ª PARTE" com subseções aninhadas dentro de cada um. A parte de tabelas foi implementada na Fase 2 (ver PC160-E abaixo); a hierarquia de blocos ficou de fora por decisão explícita (ver PC160-E).

---

### PC160-E — Concluído (v5.15 / 2026-07-08) — ata segue tabela/lista/parágrafo de QUALQUER modelo (Fase 2)

**Contexto:** ao perguntar se deveria implementar as tabelas identificadas no PC160-D, o usuário fixou a restrição central desta fase: *"Como os modelos de atas podem ser muito variados só não engesse nosso agente. Ele precisa ser capaz de seguir qualquer modelo."* — nada podia ser hardcoded para o formato específico do template FGV usado como exemplo. Planejamento formal via EnterPlanMode + agente Plan antes de codificar, dado o tamanho da mudança (extração + renderização + 3 pontos de UI).

- **`modules/ata_template_engine.py`** — `_iter_body_blocks(doc)`: percorre `doc.element.body.iterchildren()` para obter parágrafos e tabelas na ORDEM REAL do documento (`doc.paragraphs`/`doc.tables` são duas listas separadas no python-docx, sem ordem relativa entre si — única forma de saber "essa tabela veio logo depois daquele heading"). `_extract_sections(doc, heading_paragraphs)`: casa cada heading (via `_collect_heading_paragraphs`, já existente) com o(s) bloco(s) de conteúdo até o próximo heading; classifica `content_kind` (`table`/`list`/`paragraph`/`empty`) — tabela tem prioridade sobre texto introdutório antes dela — e captura as colunas reais da tabela (`columns=[]` quando o cabeçalho não é legível, nunca inventa nomes). Resultado vira `style_spec["sections"]`, aditivo (não quebra consumidores que só leem `accent_color`).
- **`modules/minutes_exporter.py`** — `_resolve_section_field(heading_text)`: mapeia QUALQUER texto de heading para um campo de `MinutesModel` via sinônimos regex com `\b` (word boundary); sem correspondência = seção pulada, nunca fabricada. `_render_field_as_table()`: desenha tabela com as colunas EXATAS do modelo — coluna sem correspondência de dado (`_COLUMN_FIELD_PATTERNS`) vira "—" em toda linha, nunca inventa e-mail/unidade de participante. Campo com `content_kind="table"` mas sem padrão de coluna conhecido (ex: um campo novo/raro) degrada graciosamente para lista, nunca quebra. `to_docx()` roda o novo caminho templated (`_render_templated_sections`) antes dos blocos default fixos, guardado por um `set` de campos já renderizados — 100% retrocompatível quando `template_spec` não tem `"sections"`.
- **Bug real corrigido durante a implementação (achado testando contra o `.docx` real)**: sinônimos sem `\b` causavam falso-positivo por substring — `"tema"` casava dentro de `"Sistemas"` (mapeando incorretamente pra `agenda`), `"depend"` casaria dentro de `"Independente"`. Corrigido com prefixo `\b` em toda raiz de palavra-chave (`_kw()` helper). Também corrigido: heading composto "Assuntos Discutidos / Decisões Tomadas" resolvia para `summary` em vez de `decisions` (ordem de checagem da lista de padrões, não força do sinal) — reordenado pra padrões mais específicos (`decis`) serem checados antes dos mais genéricos (`assunto`/`discuti`).
- **Gap pré-existente achado e fechado no caminho**: os 5 campos BABOK (`risks_identified`, `dependencies`, `open_questions`, `assumptions`, `stakeholder_needs`) nunca tinham NENHUM renderizador no `.docx` — mesmo antes desta mudança, esses campos (extraídos desde PC-anteriores) simplesmente não apareciam no Word. Adicionado fallback padrão (lista com marcadores), mesmo padrão dos demais campos; `_has_structured` (gate entre renderização estruturada e fallback markdown) ampliado para considerar esses 5 campos também.
- **`pages/Pipeline.py`** (2 pontos: Nova transcrição + Modo B) e **`pages/Artefatos.py`** (Central de Artefatos) — os 3 pontos que montam `template_spec` a partir do `style_spec` salvo passam a incluir `"sections"`; sem isso a extração funcionaria mas a UI real ignoraria silenciosamente as seções.
- **Não-objetivo explícito, documentado no plano**: replicar a hierarquia "1ª PARTE/2ª PARTE" (blocos temáticos repetidos) ficou fora de escopo — `MinutesModel` é uma lista única e achatada por campo, sem noção de bloco; dividir artificialmente uma lista em "partes" seria uma fabricação estrutural tão problemática quanto inventar um e-mail. Mitigação: heading repetido mapeando pro mesmo campo (ex: "Participantes" 2x) é pulado na segunda ocorrência — a lista completa já foi impressa na primeira, nada se perde nem duplica de forma enganosa.
- [x] 16 testes novos (`tests/test_ata_template_engine.py`), incluindo um SEGUNDO modelo de referência deliberadamente diferente do exemplo FGV (nomes de seção/coluna diferentes — inclusive em inglês —, participantes como lista em vez de tabela) para o próprio test suite auditar que nada está hardcoded a um template específico.
- [x] 664/664 testes automatizados passando (suíte completa, zero regressão).

---

### PC159 — Concluído (v5.15 / 2026-07-08) — Download Ata em Word na Central de Artefatos + nomes de arquivo com data da reunião

**Contexto:** pedido direto do usuário — na Central de Artefatos, aba Reuniões, só havia "Download Ata (.md)"; pediu para incluir Word também. Segundo ponto: nomes de arquivo gerados eram genéricos (`{projeto}_minutes{data do download}.html`) — usar a **data da reunião** em vez da data em que o export foi pedido.

- **`services/export_service.py::format_date_suffix(raw_date) -> str`** — normaliza data de reunião (DD/MM/AAAA do LLM, ISO do banco, ou `datetime.date`) para sufixo `AAAA-MM-DD` seguro em nome de arquivo; cai para hoje quando `raw_date` está vazio.
- **`pages/Pipeline.py`** — chokepoint único onde `suffix` é definido para TODOS os exports da sessão viva (`make_filename`, 33 pontos de chamada em `ui/tabs/*.py`) passou a derivar de `hub.minutes.date` (ou `st.session_state.meeting_date` como fallback) em vez de `date.today()` — afeta ata, BPMN, requisitos, SBVR, DMN, argumentação e relatório executivo, em todos os formatos (md/docx/pdf/html/json/bpmn/mmd), de uma vez.
- **`pages/Artefatos.py`** (aba Reuniões) — botão **"⬇️ Ata (.docx)"** adicionado ao lado do `.md` existente (agora renomeado "⬇️ Ata (.md)"); ambos usam `format_date_suffix(m.get("meeting_date"))` no nome (`ata_reuniao_{num}_{AAAA-MM-DD}.ext`).
- **Bug latente corrigido no caminho**: `modules/minutes_exporter.py::to_docx()` não tinha fallback pra `minutes_md` (só `to_html()` tinha, do PC155) — uma reunião carregada do banco (sem campos estruturados, que é exatamente o caso da aba Reuniões) geraria um Word quase vazio (só título/data). Adicionado `_render_markdown_docx()`, espelhando `_md_to_html_fallback()`: headers `#`/`##`/`###`, bullets, listas numeradas, tabelas markdown, parágrafos — tudo renderizado como conteúdo real do Word.
- [x] 11 testes novos (`tests/test_pc159_meeting_date_naming.py`): `format_date_suffix` com todos os formatos de entrada (BR, ISO, ISO timestamp, `date` object, vazio→hoje), fallback markdown→docx produz conteúdo real (não noqueado por dados estruturados quando ambos coexistem), doc vazio não quebra.
- [x] 622/622 testes automatizados passando.

---

### PC158 — Concluído (v5.15 / 2026-07-08) — botão "Nova" reabre Contexto/Reunião em branco

**Contexto:** pedido direto do usuário — na tela "Processar Transcrição" (modo Nova transcrição), o botão de limpar resultados existente ("🆕 Nova Transcrição") não tocava em título/data da reunião nem reabria o formulário "Contexto / Reunião" — só limpava a transcrição/hub, deixando o contexto anterior confirmado.

- `pages/Pipeline.py` — botão renomeado para **"🆕 Nova"** e sua lista de limpeza expandida: além de `hub`/`curated_clean`/`pp_result`/`_last_uploaded_file`/`current_meeting_id`/`transcript_text` (já existente), agora também limpa `project_confirmed` (reabre o expander "📁 Contexto / Reunião"), `meeting_title`/`meeting_date` (valores confirmados) + `meeting_title_input`/`meeting_date_input` (estado dos widgets — sem isso o formulário reaberto mostraria o título antigo "grudado"), `proj_sel`, e o processo BPMN vinculado (`bpmn_process_id`/`bpmn_process_override_name`/`bpmn_process_display`/`bpmn_proc_sel`).
- [x] Verificado end-to-end via `streamlit.testing.v1.AppTest` (não só leitura de código): simulado contexto confirmado com título/data antigos + hub presente, clique no botão, confirmado que TODOS os campos voltam ao estado limpo e que o expander "📁 Contexto / Reunião — obrigatório para salvar resultados" está de fato visível na tela após o clique.
- [x] 611/611 testes automatizados passando (suite completa, sem teste dedicado novo — mudança é um ajuste localizado de UI já coberto pela verificação AppTest ad-hoc).

---

### PC157 — Concluído (v5.15 / 2026-07-08) — loops de correção nunca mais viram Link Events invisíveis

**Contexto:** implementação de `melhorias/event-links-aprimoramento.md` (agora arquivado), plano que pedia uma heurística objetiva pra decidir entre seta explícita e Link Event, com uma regra central: loops de correção/retrabalho (ex: "não aprovada" voltando pro passo anterior) devem **sempre** ser seta visível, nunca Link Event, independente da distância.

- **`_closes_cycle(flow, all_flows)`** (`modules/bpmn_generator.py`) — nova função: detecta via BFS se `target` já consegue alcançar `source` pelos demais flows (ou seja, o flow fecha um ciclo no grafo). Um flow que fecha ciclo é estruturalmente um loop de correção/retrabalho — nunca um salto excepcional para um ponto distante não relacionado.
- **`_detect_crossings()`** agora exclui incondicionalmente qualquer flow que feche ciclo, ANTES de rodar as 5 heurísticas de distância/cruzamento já existentes (calibradas em produção real via PC118/PC131) — essas heurísticas continuam intactas para os saltos genuinamente não-cíclicos.
- **Convenção de nomenclatura** — Link Events trocaram de `lnk_throw_N`/`lnk_catch_N` (genérico, incremental) para `link_throw_{origem}_{destino}`/`link_catch_{origem}_{destino}` (descritivo, conforme o plano), com verificação de colisão defensiva.
- **Bug real de trava (infinite loop) encontrado e corrigido durante os testes**: o passo de "resolução de conflito de coluna cross-lane" em `_compute_layout()` sempre assumiu implicitamente que `bpmn.flows` era acíclico — garantia que antes vinha de TODO loop longo/cross-lane já ter sido cortado em Link Events antes desse passo rodar. Ao parar de converter loops de correção, ciclos reais voltaram a chegar nesse passo, e o loop de propagação "empurra coluna pra frente" (sem guarda de ciclo) trava indefinidamente. Corrigido com limites de segurança (teto de coluna = `len(order)+2`, teto de rodadas = `len(order)*4+20`) — reproduzido e verificado com `faulthandler.dump_traceback_later` antes do fix (travava; 11ms depois).
- **Desvio consciente do plano original**: os critérios numéricos literais do documento (>2000px, ≥3 elementos cruzados) NÃO substituíram as 5 heurísticas de distância/lane-span já existentes — reescrevê-las do zero jogaria fora o ajuste fino validado em produção real (PC118/PC131). A parte de maior valor do plano (loop de correção nunca vira Link Event + nomenclatura descritiva) foi implementada; "tentar reorganizar layout antes" e o rótulo "Retorno para X" não foram implementados literalmente (a exclusão por ciclo já resolve o problema-raiz sem precisar de reposicionamento).
- [x] 4 testes novos (`tests/test_bpmn_generator_link_events.py`): loop de correção de longa distância fica seta direta, salto forward de mesma distância sem ciclo ainda vira Link Event (caso de controle), nomenclatura `link_throw_{src}_{tgt}` confirmada, guarda de trava em grafo cíclico (assert < 5s). 1 teste existente atualizado para refletir o comportamento novo e correto (`sf_017`/"Solicitar Ajustes" — um loop de correção real no fixture de 6 lanes — deixa de virar Link Event).
- [x] Validado contra o XML real de "Reclassificação de Lançamento Contábil" visto nesta mesma sessão (o loop "não aprovada" S08→S06 que antes virava `lnk_throw_1`/`lnk_catch_1`) — confirma zero Link Events gerados, `sf_009` permanece seta direta.
- [x] 611/611 testes automatizados passando.

---

### PC156 — Concluído (v5.15 / 2026-07-08) — correção de termo com grafia errada agora cobre o SBVR

**Contexto:** usuário perguntou se havia funcionalidade para corrigir um termo/sigla com grafia errada trazida pela transcrição (ex: "SASEP" quando o correto é "SACEP") de forma consistente em todos os artefatos onde o termo aparece — incluindo o vocabulário SBVR. Investigação (Explore agent) confirmou: `apply_text_correction`/`preview_text_correction`/`batch_text_correction` já cobriam transcrição/ata/requisitos, mas o `scope` não tinha opção `"sbvr"`, e as ferramentas dedicadas de SBVR (`update_sbvr_term`/`update_sbvr_term_by_id`) só editavam `definition`/`category` — nenhuma tinha parâmetro para renomear `sbvr_terms.term` em si.

- **`core/tools/tools_bpmn_sbvr.py`:**
  - `update_sbvr_term()` e `update_sbvr_term_by_id()` ganharam parâmetro `new_term` — renomeia o termo SBVR, com checagem de duplicidade (`.ilike`) antes de aplicar, recusando o rename se já existir outro termo com o mesmo nome no projeto.
  - `preview_text_correction()`/`apply_text_correction()` ganharam `scope="sbvr"` (e `scope="all"` passou a incluir SBVR) — busca/substitui em `sbvr_terms.term`, `sbvr_terms.definition` e `sbvr_rules.statement`.
- **`core/tools/tools_knowledge_requirements2.py`:** enum de `scope` em `batch_text_correction` atualizado para incluir `"sbvr"` (a implementação já delega pra `apply_text_correction`, sem mudança de lógica).
- **`core/assistant_tools.py`:** dispatch de `update_sbvr_term`/`update_sbvr_term_by_id` atualizado para repassar `new_term`.
- [x] 12 testes novos (`tests/test_tools_sbvr_term_rename.py`): rename com sucesso, rejeição de nome duplicado, termo não encontrado, rename combinado com outros campos, preview/apply com `scope="sbvr"` tocando termo+definição+regra, `scope="all"` cobrindo SBVR, `scope="sbvr"` isolado não tocando `meetings`/`requirements`.
- [x] 607/607 testes automatizados passando.

---

### PC155 — Concluído (v5.15 / 2026-07-07) — export de ata em HTML sob demanda + persistência da Ata Interativa

**Contexto:** pedido direto do usuário — "criar funcionalidade para exportar uma ata de reunião em HTML". Pesquisa prévia (Explore agent) revelou que já existia um export HTML — a "Ata Interativa" via ATA Engine (`modules/ata_engine_generator.py::generate_ata_html()`) — mas gerado só em memória durante o pipeline, sem coluna no banco para persistir; reuniões carregadas do banco (Modo B) nunca exibiam o botão. Perguntado ao usuário qual abordagem seguir (export simples sempre disponível vs. corrigir a Ata Interativa vs. as duas) — escolheu as duas.

- **`modules/minutes_exporter.py::to_html(minutes) -> str`** — novo export sob demanda, mesmo padrão de `to_docx()`/`to_pdf()` já existentes (mesma paleta navy `#0B1E3D`/accent `#2E7FD9`). Renderiza campos estruturados (participantes, pauta, resumo, decisões, tabela de action items) quando presentes; fallback para parse de `minutes_md` (markdown→HTML) quando a reunião foi carregada do banco sem dados estruturados — um caso que nem `.docx`/`.pdf` cobrem hoje. Botão `.html` adicionado em `ui/tabs/minutes_tab.py` (nos dois branches, incluindo o de fallback) e `ui/tabs/export_tab.py`.
- **Persistência da Ata Interativa:** nova coluna `meetings.ata_html` (migration `setup/supabase_migration_minutes_ata_html.sql`, executada e validada em produção). `core/project_store.py::save_meeting_artifacts()`/`load_meeting_as_hub()` passaram a persistir/recarregar o campo.
- **Bug real corrigido no caminho:** `pages/Pipeline.py` gerava `ata_html` via `generate_ata_html()` DEPOIS de `save_meeting_artifacts()` já ter rodado — o valor gerado nunca era capturado na primeira gravação, só ficava disponível na tela até o próximo reload apagar tudo. Reordenado: geração agora roda logo após `meeting_id` ser conhecido, antes dos saves.
- **Botão manual "🔄 Gerar Ata Interativa"** em `minutes_tab.py` — aparece quando há dados estruturados no hub mas `ata_html` está ausente (reunião antiga sem a coluna preenchida, ou rerun do agente de Ata que zera o campo). Gera e persiste na hora, sem precisar rodar o pipeline inteiro de novo (ATA Engine é puro Python, sem chamada de LLM).
- **Limite reconhecido explicitamente:** não é possível regenerar a Ata Interativa automaticamente para reuniões antigas cujo hub só tem `minutes_md` (campos estruturados nunca foram persistidos como dados separados) — o botão de regeneração só aparece quando há dado estruturado de verdade disponível; para esses casos o `to_html()` sob demanda (que processa o markdown puro) é a alternativa correta.
- [x] 595/595 testes automatizados passando.

---

### PC154 — Concluído (v5.15 / 2026-07-07) — labels de BPMN não quebravam linha no bpmn-js (pré-wrap em Python)

**Contexto:** queixa recorrente do usuário — labels de atividade "não centralizados" nas caixinhas do diagrama BPMN gerado via pipeline. Investigação por leitura direta do código-fonte do bpmn-js/diagram-js (GitHub, não por memória) em duas etapas:

1. **Hipótese inicial descartada:** a heurística já existente no projeto (`_build_di()`/`reformat_bpmn_labels()` — escrever `bpmndi:BPMNLabel/dc:Bounds` centrado dentro do shape para tasks) é comprovadamente um no-op no bpmn-js — `renderEmbeddedLabel()` monta o box de layout exclusivamente a partir do `dc:Bounds` do próprio `BPMNShape`, nunca de `BPMNLabel/dc:Bounds`, para elementos de label interno (task/userTask/serviceTask/callActivity/etc.); esse campo só é lido para elementos de label externo (event/gateway/edge — `isLabelExternal()`).
2. **Causa raiz real**, confirmada pelo usuário testando o mesmo diagrama em aba anônima (extensões desabilitadas): bpmn-js mede largura de texto para decidir quebra de linha via `canvas.getContext('2d').measureText(...)`; quando esse contexto retorna `null` — comportamento típico de extensões de bloqueio de fingerprinting via canvas (uBlock avançado, Privacy Badger, proteção nativa do Brave, browsers corporativos endurecidos) — a medição retorna `{width:0}` silenciosamente, e a condição de quebra de linha nunca dispara: o label inteiro renderiza como UMA linha única que ultrapassa a borda da caixa. Não era um bug do código do projeto; era comportamento do navegador do usuário.

**Correção (`modules/bpmn_generator.py`):**
- `_wrap_label(name, chars_per_line, max_lines)` — greedy word-wrap, insere `\n` literal nos pontos de quebra; corta linhas excedentes com "…".
- `_label_for(el)` — dispatcher: `_task_name()` trunca primeiro (limite absoluto já existente), depois `_wrap_label` com limites calibrados por categoria de elemento a partir dos tamanhos de caixa já em uso: tasks 18 chars/4 linhas (caixa 160×90), events 11 chars/2 linhas (label externo ~86px), gateways 13 chars/2 linhas (label externo ~100px).
- `_build_el()` — todos os 6 pontos que antes chamavam `_task_name(el.name)` diretamente (startEvent/endEvent/intermediateThrowEvent/intermediateCatchEvent, boundaryEvent, gateway, subProcess, callActivity, task genérico) agora usam `_label_for(el)`. Cobre single-pool e multi-pool automaticamente, já que ambos os caminhos passam por `_build_process_xml()` → `_build_el()`.
- **Por que funciona independente do canvas do browser:** verificado no código-fonte de `diagram-js/lib/util/Text.js` — `layoutText()` faz `text.split(/­?\r?\n/)` (quebra em `\n` literal) ANTES de qualquer medição de largura via canvas. Pré-inserir `\n` no Python contorna o `measureText` quebrado inteiramente, sem depender de nenhuma condição do navegador.
- **Round-trip XML verificado empiricamente:** `xml.etree.ElementTree` escapa `\n` dentro de valor de atributo como `&#10;` na serialização, e o desserializa de volta para `\n` literal corretamente — sobrevive ao parser padrão do bpmn-moddle sem perda.
- Comentários em `bpmn_generator.py::_build_di()`, `bpmn_auto_repair.py::reformat_bpmn_labels()` e `bpmn_viewer.py::preview_from_xml()` atualizados apontando para o fix real, deixando claro que a escrita de `BPMNLabel/dc:Bounds` para tasks é só compatibilidade com ferramentas externas (Camunda Modeler, Bizagi, draw.io) — não afeta o bpmn-js.
- [x] 3 testes ajustados (comparação de nome exata → normalizada com `.replace("\n"," ")`) em `test_agent_bpmn_multipool_documentation.py` e `test_bpmn_generator_link_events.py::_link_event_names()` — quebravam porque agora comparam contra um `name` com `\n` embutido, comportamento correto e esperado.
- [x] 595/595 testes automatizados passando.

---

### PC152 — Concluído (v5.15 / 2026-07-07) — tabela auxiliar de histórico de processamento de reuniões

**Contexto:** após o PC151 (perda silenciosa de dados de pipeline), o usuário pediu uma tabela auxiliar registrando a data efetiva de cada processamento de transcrição — incluindo reprocessamentos — para saber quantas vezes e quando cada reunião foi processada.

- Nova tabela `meeting_processing_log` (migration `setup/supabase_migration_meeting_processing_log.sql`, executada em produção): `meeting_id`/`project_id` (FK cascade), `processing_type` (`new`|`reprocess_full`|`reprocess_agent`, `CHECK` constraint), `agent_name` (só para `reprocess_agent`), `llm_provider`, `total_tokens`, `success`, `error_message`, `processed_at`.
- `core/project_store.py`: `log_meeting_processing()` (fail-open, insert), `get_meeting_processing_history(meeting_id)` (histórico ordenado, mais recente primeiro), `count_meeting_processings(meeting_id)` (`count="exact"` + `.limit(1)`, imune ao cap de 1000 linhas do PostgREST — mesmo padrão de `_exact_count()`/PC139).
- Hookado nos 4 caminhos de processamento reais do sistema: `pages/Pipeline.py` Modo A (`processing_type=new`, logo após `create_meeting()`+saves bem-sucedidos — mesmo bloco corrigido no PC151) e rerun de agente único (`processing_type=reprocess_agent`, `agent_name=<agente>`, resolvendo `meeting_id`/`project_id` de Modo A ou B); `core/batch_pipeline.py::_run_one()` (`processing_type=new`) e `_reprocess_one()` (`processing_type=reprocess_full`, inclusive registrando falhas — `meeting_id` já existe antes do pipeline rodar nesse caminho, ao contrário de `_run_one`).
- Nova ferramenta do Assistente `get_meeting_processing_history(meeting_number)` (`core/tools/tools_meetings_requirements.py`, categoria "consulta", não-admin) — responde "quantas vezes essa reunião foi processada" e "quando foi processada de verdade" (útil quando a data registrada da reunião não bate com o processamento real, como no cenário do PC151).
- [x] 17 testes novos (`test_meeting_processing_log.py`): helpers de `project_store` (fail-open, payload correto, contagem por reunião), formatação da tool (não encontrada, sem histórico, múltiplos eventos, evento com falha), wiring de dispatch/categoria.
- [x] Migration executada e validada em produção com insert+count+rollback real (sem dado de teste permanente deixado no banco).
- [x] 595/595 testes automatizados passando (578 + 17 novos).

---

### PC151 — Concluído (v5.15 / 2026-07-06) — reuniões processadas mas NUNCA salvas no banco (perda de dados silenciosa)

**Contexto:** usuário reportou que duas transcrições novas carregadas para o projeto SDEA (reuniões esperadas #29/#30, datas 01/07 e 02/07/2026) não apareciam para o Assistente. Investigação com evidência real (psycopg2 direto em produção) revelou algo muito mais grave que um campo de data errado:

- `MAX(meetings.created_at)` em **toda** a base = 2026-06-30 — nenhuma reunião nova em nenhum projeto nos últimos dias.
- `llm_telemetry` mostrava **duas execuções completas do pipeline** no dia do relato (23:07–23:15 e 23:33–23:39 UTC — bpmn, minutes, requirements, sbvr, bmm, dmn, argumentation, synthesizer, todos com sucesso) — ou seja, o pipeline rodou de verdade, com custo real de LLM, mas nada foi persistido.

**Causa raiz:** `ui/project_selector.py::_init()` roda em TODO rerender de `pages/Pipeline.py` (via `render_project_selector()`, chamada antes da lógica do botão "Processar Transcrição" — na MESMA execução de script). Seu bloco de sincronização comparava `active_project_id` (setado em outro lugar, ex.: Home.py) contra o `project_id` já confirmado do Pipeline em TODA execução — não só quando `active_project_id` de fato mudava. Sempre que o usuário confirmava deliberadamente um projeto DIFERENTE no seletor local do Pipeline daquele que por acaso estava "ativo" alhures, essa discrepância persistia em todo rerender seguinte e reacionava o reset a cada vez — revertendo silenciosamente `project_id`/`project_confirmed` de volta ao projeto ativo obsoleto, inclusive na MESMA execução que processa a transcrição. Como o bloco de persistência em `Pipeline.py` é condicionado a `if supabase_configured() and project_confirmed:` sem nenhum `else`, o pipeline de LLM roda normalmente (não depende dessa flag) mas `create_meeting()`/`save_*` são pulados silenciosamente — zero erro, zero aviso, resultados aparecem normalmente na tela (vêm de `hub` em `session_state`, não do banco) dando a falsa impressão de sucesso completo.
- Bug reproduzido e confirmado com um script mínimo antes de corrigir: confirmar "SDEA" com "AURORA" como projeto ativo, chamar `_init()` de novo (simulando o rerender do clique em Processar) — `project_id` voltava sozinho para `aurora-id` e `project_confirmed` para `False`.

**Correção:**
- `ui/project_selector.py::_init()` — novo estado `_last_seen_active_pid` rastreia o último valor visto de `active_project_id`; o reset de `project_confirmed` agora só dispara quando esse valor **muda de fato** (evento real de "usuário trocou de contexto no Home.py"), não mais toda vez que ele simplesmente difere da escolha já confirmada no Pipeline.
- `pages/Pipeline.py` — adicionado `else` quando `create_meeting()` retorna `None` (mostra `st.error()` claro: resultados NÃO foram persistidos) e `elif` quando `project_confirmed` é `False` (mostra `st.warning()`: nada foi salvo, confirme o contexto e processe novamente). Antes, ambos os casos eram 100% silenciosos.
- [x] 6 testes novos (`test_project_selector_confirmed_reset.py`): confirmação de um projeto diferente do ativo sobrevive a múltiplos reruns subsequentes (inclusive com `active_project_id=None`), troca genuína de projeto ativo ainda reseta corretamente, alternância A→B→A reseta em cada transição real.
- [x] 578/578 testes automatizados passando (572 + 6 novos).
- **Ação pendente do usuário:** as duas transcrições de 01/07 e 02/07 do projeto SDEA precisam ser reprocessadas — o trabalho de LLM já foi pago mas nada foi persistido; com o fix, confirmar o projeto e processar deve salvar corretamente desta vez.

---

### PC150 — Concluído (v5.15 / 2026-07-06) — barras de prioridade sempre cinza no gráfico "Requisitos por Tipo e Prioridade"

**Contexto:** usuário reportou (print) que as barras empilhadas de "medium" e "high" apareciam ambas na mesma cor cinza, apesar da legenda distinguir as duas categorias corretamente.

- **Causa:** `_PRIO_COLORS` em `generate_requirements_chart()` (`core/tools/tools_admin_charts_entities.py`) era um dict fixo com chaves capitalizadas em português (`"Alta"`, `"Média"`, `"Baixa"`), mas a coluna `requirements.priority` no banco guarda valores em inglês minúsculo (`"low"`/`"medium"`/`"high"` — confirmado pelo texto exato da legenda no print). Toda chamada `_PRIO_COLORS.get(prio, "#64748b")` não encontrava a chave e caía no cinza padrão, para QUALQUER prioridade — por isso "medium" e "high" (e "low", se presente) sempre ficavam idênticas.
- **Correção:** novo helper `_prio_color(label)` normaliza o rótulo (`.strip().lower()`) antes de consultar um dict expandido com chaves em português E inglês (`"alta"/"high"` → vermelho, `"média"/"media"/"medium"` → âmbar, `"baixa"/"low"` → verde), reutilizado nos dois pontos que antes acessavam `_PRIO_COLORS` diretamente (`group_by="priority"` e `group_by="both"`).
- [x] 3 testes novos (`TestGenerateRequirementsChartPriorityColors`): prioridades em inglês (o cenário exato do bug) recebendo cores distintas e nenhuma caindo no cinza, prioridades em português minúsculo (fixture já existente no arquivo, nunca antes verificada quanto à cor) também corretas, e prioridade desconhecida ainda caindo no cinza de fallback como esperado.
- [x] 572/572 testes automatizados passando (569 + 3 novos).

---

### PC149 — Concluído (v5.15 / 2026-07-06) — barras do Gantt invisíveis (título/eixos/legendas corretos, mas sem barras)

**Contexto:** usuário reportou (print) o gráfico de Gantt renderizando título, eixo Y (nomes das fases) e eixo X (datas) corretamente, mas **sem nenhuma barra visível** na área do gráfico.

- **Causa:** `generate_gantt_chart()` usava `x=[duration_days]` (um inteiro de contagem de dias) como comprimento da barra, com `base=[start_date]` e `xaxis.type="date"`. Em um eixo do tipo data, o Plotly interpreta o valor numérico do comprimento da barra em **milissegundos** (sua unidade interna para eixos de data) — um `x=7` (7 dias) virava uma barra de 7 milissegundos, um traço imperceptível a qualquer nível de zoom. Testado e confirmado experimentalmente antes de corrigir.
- **Tentativa intermediária descartada:** trocar para `datetime.timedelta(days=duration_days)` corrige a renderização (Plotly converte `timedelta` corretamente), mas reintroduz exatamente a classe de bug de PC146/148 — `PlotlyJSONEncoder` (usado no export HTML) **não** tem um encoder para `datetime.timedelta`, então o gráfico voltaria a quebrar a exportação com `TypeError: Object of type timedelta is not JSON serializable`. Confirmado testando o encoder diretamente antes de adotar essa abordagem.
- **Correção final:** `x=[duration_days * 86_400_000]` — duração em milissegundos como `int` puro: correta para o eixo de data (matemática verificada: `base + timedelta(milliseconds=x)` reproduz exatamente a data de fim informada) e nativamente serializável em JSON, sem depender de nenhum encoder especial.
- [x] 2 testes novos (`test_bar_length_is_in_milliseconds_not_raw_days`, `test_bar_base_plus_length_lands_on_end_date` em `test_tools_requirement_charts.py`): comprimento da barra em ms confirmado, e reconstrução da data de fim a partir de `base + x` batendo exatamente com o valor informado.
- [x] 569/569 testes automatizados passando (567 + 2 novos).

---

### PC148 — Concluído (v5.15 / 2026-07-06) — "datetime not JSON serializable" também na chamada de chat (não só no export)

**Contexto:** usuário reportou o mesmo erro de PC146 (`Object of type datetime is not JSON serializable`), desta vez numa pergunta sem nenhuma relação com gráficos — *"O que precisa ser feito para que tenhamos um cronograma do projeto?"* — tanto no caminho principal de tool-use quanto no fallback de busca por keyword.

- **Causa (raiz diferente de PC146):** `pages/Assistente.py` guarda em `st.session_state["assistant_history"]` o dict completo de cada turno, incluindo chaves só-de-UI (`charts`, `tools_used`, `tables`, `widgets`) — por exemplo, o figure Plotly de um Gantt gerado em um turno ANTERIOR da mesma conversa (que embute objetos `datetime.datetime` crus, ver PC146). `agents/agent_assistant.py::_trim_history()` repassava esses dicts praticamente inalterados (só reconstruía o dict ao truncar `content`, preservando as demais chaves via `{**msg, ...}`) — então `charts` entrava direto na lista `messages` passada para `client.chat.completions.create(messages=...)`, tanto em `chat()` quanto em `chat_with_tools()`. O SDK da OpenAI/Anthropic não descarta chaves desconhecidas antes de serializar o corpo da requisição — o `datetime` de um Gantt gerado ANTES quebrava a codificação de QUALQUER pergunta seguinte, mesmo sem relação com gráficos.
- **Correção:** `_trim_history()` agora sempre reconstrói um dict limpo `{"role", "content"}`, descartando qualquer chave extra, independente do ramo de truncamento. Corrige os dois caminhos (`chat()` e `chat_with_tools()`) de uma vez, já que ambos chamam a mesma função.
- [x] 5 testes novos (`test_agent_assistant_trim_history.py`): chaves `charts`/`tables`/`widgets` descartadas, `role`/`content` preservados, truncamento de conteúdo longo ainda funciona e ainda descarta chaves extra, e reprodução exata do cenário de produção — histórico com um Gantt chart anterior serializado com sucesso via `json.dumps()` (o que o SDK faz internamente).
- [x] 567/567 testes automatizados passando (562 + 5 novos).

---

### PC147 — Concluído (v5.15 / 2026-07-06) — legendas dos gráficos ainda ilegíveis após PC145: `st.plotly_chart` sobrescrevia o tema

**Contexto:** usuário confirmou (novo print) que a legenda continuava de baixo contraste mesmo após PC145 ter definido `legend.font.color` explicitamente no figure dict.

- **Causa:** `st.plotly_chart(figure_or_data, use_container_width, *, theme='streamlit', ...)` — o parâmetro `theme` do Streamlit é **`'streamlit'` por padrão**, e nesse modo o componente sobrescreve a formatação visual do figure (incl. cor de fonte) com o tema do próprio app Streamlit, ignorando a estilização explícita que já estava correta no dict (confirmada em PC145 via testes que inspecionavam o dict cru — que nunca passa pelo componente de renderização real, por isso o bug não aparecia nos testes). As duas chamadas `st.plotly_chart(...)` em `pages/Assistente.py` (linha ~551, relatório de análise autônoma; linha ~1578, histórico do chat) nunca passavam `theme=`, então caíam no default.
- **Correção:** `theme=None` adicionado às duas chamadas — instrui o Streamlit a respeitar integralmente o layout do figure (incluindo a correção de PC145), sem overlay do tema padrão.
- **Verificação:** suíte completa (562/562) sem regressão + boot sanity check do app (`streamlit run` respondendo HTTP 200). Não foi possível confirmar visualmente em navegador neste ambiente (sem Playwright/driver de browser instalado) — a correção se apoia no comportamento documentado do parâmetro `theme` do Streamlit, não em captura de tela.

---

### PC146 — Concluído (v5.15 / 2026-07-06) — export de HTML do Assistente derrubava a página inteira com gráfico de Gantt

**Contexto:** produção reportou `TypeError: Object of type datetime is not JSON serializable` derrubando a página inteira do Assistente (crash não capturado no nível do módulo, não apenas do gráfico), em `pages/Assistente.py:1287` dentro de `_export_chat_to_html()`.

- **Causa:** `generate_gantt_chart()` (`core/tools/tools_admin_charts_entities.py`, PC142) guarda objetos `datetime.datetime` crus no campo `base` de cada barra (`go.Bar(..., base=[p["start"]], ...)`) — válido para o Plotly, mas `_export_chat_to_html()` serializava cada `chart_dict` com `json.dumps(chart_dict)` puro (stdlib), que não sabe lidar com `datetime`. A renderização inline no chat (`st.plotly_chart(go.Figure(fig_dict), ...)`, duas ocorrências em `pages/Assistente.py`) já era protegida por `try/except` — só o caminho de exportação HTML, sem proteção nenhuma, quebrava a página inteira.
- **Correção:** `json.dumps(chart_dict, cls=plotly.utils.PlotlyJSONEncoder)` — o encoder nativo do Plotly já sabe serializar `datetime`/`numpy`/`pandas`, tornando a correção genérica para qualquer ferramenta de gráfico atual ou futura, não só o Gantt. Adicionado também `try/except (TypeError, ValueError): continue` ao redor da serialização de cada gráfico — um gráfico que ainda assim falhar é pulado individualmente em vez de derrubar a exportação inteira (e as demais mensagens da conversa).
- [x] 4 testes novos (`test_assistente_html_export.py`): reprodução exata do crash de produção (Gantt com datetime), validação de que o JSON embutido no HTML é válido, resiliência a um gráfico genuinamente não serializável (pulado, resto da exportação intacto), e um gráfico normal ainda funcionando sem regressão.
- [x] 562/562 testes automatizados passando (558 + 4 novos).

---

### PC145 — Concluído (v5.15 / 2026-07-06) — baixo contraste no texto das legendas dos gráficos do Assistente

**Contexto:** usuário reportou (com print) legendas praticamente ilegíveis nos gráficos gerados pelo Assistente — texto escuro/de baixo contraste sobre o fundo azul-marinho escuro do tema.

- **Causa:** `_dark_layout()` (`core/tools/tools_admin_charts_entities.py:1385`, único método compartilhado por todas as ferramentas de gráfico via composição de mixins — inclusive as de IBIS em `tools_documents_ibis_diagrams.py`) definia `font=dict(color="#FAFAF8", ...)` apenas no nível raiz do layout, e `legend=dict(bgcolor=..., bordercolor=..., borderwidth=1)` sem um `font` próprio — a cor do texto da legenda dependia de herança implícita do template Plotly, que nem sempre se propaga de forma confiável para `legend.font` em todos os contextos de renderização.
- **Correção:** `font=dict(color="#FAFAF8", size=12)` adicionado explicitamente dentro de `legend=dict(...)`. Como `fig.update_layout()` faz merge recursivo (não substitui o dict inteiro), ferramentas que depois sobrescrevem só `orientation`/`yanchor`/`y`/`xanchor`/`x` da legenda (ex: `get_ibis_timeline`) preservam o `font` já definido — correção única no helper compartilhado corrige todas as ~13 ferramentas de gráfico de uma vez.
- [x] 2 testes novos (`TestDarkLayoutLegendContrast` em `test_tools_requirement_charts.py`): cor explícita da fonte da legenda, e sobrevivência do `font` após um override parcial de legenda downstream (Sankey).
- [x] 558/558 testes automatizados passando (556 + 2 novos).

---

### PC144 — Concluído (v5.15 / 2026-07-06) — vazamento de tags DSML no chat + roteamento errado "encaminhamentos" → decisões

**Contexto:** usuário relatou que o prompt *"Mostre os encaminhamentos por responsável em gráfico"* — o exemplo canônico documentado para `generate_action_items_chart` (inclusive na página PC143 recém-criada) — resultou em texto bruto de tool-call vazando no chat (`<｜｜DSML｜｜invoke name="get_meeting_decisions">...`) em vez de um gráfico. Dois bugs distintos, ambos corrigidos:

- **Vazamento de DSML (causa raiz):** `agents/agent_assistant.py` já tinha um parser/safety-net para o formato interno de tool-call do DeepSeek que vaza como texto (`<｜DSML｜invoke ...>`), com regex `_P = r'[|｜]'` assumindo exatamente **um** caractere delimitador de cada lado de "DSML". A resposta real usou o delimitador **dobrado** (`<｜｜DSML｜｜invoke ...>`), que o detector (`_DSML_DETECT_RE`) ainda reconhecia (só precisa de 1 barra em algum ponto), mas `_DSML_INVOKE_RE`/`_DSML_PARAM_RE`/`_strip_dsml` falhavam em casar — `_parse_dsml_tool_calls()` retornava `[]`, as ferramentas nunca eram executadas, e o texto bruto vazava sem corte. Corrigido trocando `_P` para `r'[|｜]+'` (uma repetição de 1+ caracteres) em `agents/agent_assistant.py` (definição de `_P` + regex isolada dentro de `_strip_dsml`) e no safety-net duplicado em `pages/Assistente.py` (`_DSML_SAFETY_RE`/`_DSML_CUT_RE`) — tolera qualquer quantidade de delimitadores, sem quebrar o formato de delimitador único já observado antes.
- **Roteamento errado — "encaminhamentos" confundido com "decisões":** o cheat sheet de roteamento do system prompt (`INSTRUÇÕES DE USO DAS FERRAMENTAS`) tinha uma única linha agrupando `get_meeting_decisions` e `get_meeting_action_items` sob "decisões ou ações", sem citar "encaminhamentos", e **nenhuma** das 4 ferramentas de gráfico (na época) era mencionada no cheat sheet — o modelo só as via na lista crua de schemas OpenAI. Corrigido: (1) descrições de `get_meeting_decisions`/`get_meeting_action_items` (`core/tools/tools_meetings_requirements.py`) agora se referenciam mutuamente e citam "encaminhamentos" como sinônimo de itens de ação; (2) descrição de `generate_action_items_chart` (`core/tools/tools_admin_charts_entities.py`) ganhou "encaminhamentos" como gatilho explícito e instrução de preferir o gráfico sobre as ferramentas de texto cru quando o pedido menciona "gráfico"/"visualize"; (3) novo bloco no system prompt (`agents/agent_assistant.py`) separando decisões de ações/encaminhamentos em bullets distintos e listando explicitamente todas as 12 ferramentas `generate_*_chart`/`generate_ibis_map`/`get_ibis_timeline` com a regra "se o pedido mencionar gráfico/visualize/Sankey/heatmap/radar/Gantt, SEMPRE prefira a ferramenta de gráfico".
- [x] 11 testes novos (`test_agent_assistant_dsml.py`): reprodução exata do payload vazado pelo usuário (delimitador dobrado, 4 invokes encadeados, atributo extra `string="false"` no parâmetro), parsing correto de `meeting_number` como inteiro na ordem certa, garantia de não-regressão do formato de delimitador único e ASCII já suportados antes, e `_strip_dsml` produzindo texto limpo idêntico ao esperado.
- [x] 556/556 testes automatizados passando (545 + 11 novos).

---

### PC142 — Concluído (v5.15 / 2026-07-06) — 6 novos tipos de gráfico + correções em ferramentas existentes de visualização

**Contexto:** o assistente propôs um "repertório visual" mais rico para apresentações executivas (Gantt, Sankey, Treemap/Sunburst, Heatmap cruzado, Bolhas, Waterfall, Radar), listando o que já tinha (barras/linha/IBIS) vs o que não conseguia gerar. Avaliadas e implementadas todas em `core/tools/tools_admin_charts_entities.py`, todas não-admin, categoria "grafico":

- [x] **`generate_requirements_flow_chart(view, meeting_number=None)`** — Sankey (Tipo→Prioridade→Status) via `go.Sankey`, ou Treemap/Sunburst (`branchvalues="total"`) da mesma hierarquia.
- [x] **`generate_requirements_heatmap(dimension)`** — matriz Reunião × (Tipo|Prioridade|Status) montada automaticamente do banco (sem exigir que o LLM monte a matriz manualmente, ao contrário de `generate_custom_chart`).
- [x] **`generate_requirements_bubble_chart()`** — X=reunião, Y=prioridade média (1-3), tamanho=volume de requisitos.
- [x] **`generate_requirements_waterfall()`** — evolução cumulativa líquida de requisitos ativos por reunião (`status in {contradicted, deprecated}` conta como saída).
- [x] **`generate_meeting_radar_chart(meeting_numbers=None)`** — radar comparando 2-6 reuniões em Decisões/Ações/Requisitos/Participantes (contagens brutas, não normalizadas).
- [x] **`generate_gantt_chart(title, phases)`** — cronograma a partir de fases fornecidas explicitamente (sem modelo nativo de planejamento com datas); `go.Bar` horizontal com `base=start`.
- [x] Helper compartilhado `_requirements_with_meeting_numbers(meeting_number=None)` — resolve `meeting_number` via `first_meeting_id` (join em memória contra `_get_meetings()`), reutilizado pelas 5 ferramentas acima que precisam de granularidade por reunião.

**Bugs pré-existentes encontrados e corrigidos durante a implementação:**
- `generate_requirements_chart(meeting_number=N)` filtrava diretamente com `.eq("meeting_number", N)` na tabela `requirements` — essa coluna nunca existiu lá (só `first_meeting_id`, um UUID de `meetings.id`); toda chamada com `meeting_number` falhava silenciosamente com "Erro ao buscar requisitos". Corrigido reusando `_requirements_with_meeting_numbers()`.
- `generate_meetings_timeline` tinha o mesmo bug — as barras de "requisitos por reunião" sempre mostravam zero.
- `generate_custom_chart` anunciava `chart_type="heatmap"` no schema/descrição mas não tinha implementação — caía silenciosamente no `bar` default. Adicionados parâmetros `z_matrix`/`y_axis_labels` + branch real.
- `generate_meetings_timeline._extract_actions` — regex `r"Ações|Action Items.*?\n(.*?)..."` sem agrupar a alternação: `|` tem precedência mais baixa que o resto do padrão, então ao casar a variante "Ações" (cabeçalho padrão em português) o `group(1)` não existia, lançando `AttributeError` em produção. Corrigido para `r"(?:Ações|Action Items).*?\n(.*?)..."`.
- Bug análogo introduzido pela própria implementação desta rodada: `generate_meeting_radar_chart`'s `_count_section()` assumia `group(1)` como o conteúdo da seção, mas os padrões de cabeçalho passados por decisões/ações (`r"Decis(ões|oes)"`, `r"(Ações|Acoes|Action Items)"`) já continham seus próprios grupos de captura, deslocando o índice — decisões e ações sempre contavam 0. Corrigido para sempre pegar o último grupo (`section.group(section.re.groups)`), imune a grupos internos no `header_pattern`.
- [x] Registro completo: schemas em `ADMIN_CHARTS_ENTITIES_SCHEMAS`, dispatch em `AssistantToolExecutor.execute()` (incl. `z_matrix`/`y_axis_labels` no dispatch existente de `generate_custom_chart`), categoria "grafico" em `_TOOL_CATEGORIES`, nenhuma em `_ADMIN_TOOLS`. CLAUDE.md `§Tool list` atualizado.
- [x] 33 testes novos (`test_tools_requirement_charts.py`): helper de resolução de meeting_number, os 2 bugfixes de `meeting_number` inexistente, o bugfix do heatmap em `generate_custom_chart`, cada uma das 6 novas ferramentas (views do flow chart, dimensões do heatmap, contagem de bolhas, waterfall com saldo líquido, radar com mínimo de 2 reuniões e eixos corretos, Gantt com ordenação por data e validação de datas), wiring de dispatch, ausência de admin-gate.
- [x] 545/545 testes automatizados passando (512 + 33 novos).

---

### PC141 — Concluído (v5.15 / 2026-07-06) — 4 ferramentas investigativas propostas pelo próprio assistente

**Contexto:** ao final da investigação do bug de duplicação (PC140), o assistente propôs 4 novas ferramentas que teriam acelerado seu próprio diagnóstico — ele só tinha `get_requirements` (paginado, 50/página) para inspecionar centenas de requisitos. Avaliadas e implementadas as 4, todas em `core/tools/tools_meetings_requirements.py`, todas não-admin, escopadas por `meeting_number` → `first_meeting_id` (mesmo padrão de resolução já usado por `get_requirements`):

- [x] **`sample_requirements(meeting_number, sample_size=20, seed=None)`** — amostra aleatória (não paginada) via `random.Random(seed).sample()`; `sample_size` limitado ao total disponível e a 100.
- [x] **`analyze_requirement_quality(meeting_number)`** — relatório determinístico (sem custo de LLM): tamanho médio de título/descrição, palavras mais frequentes nos títulos (stopwords PT/EN removidas), proporção requisitos/100-palavras-da-transcrição com alerta de super-granularidade acima de 2,5/100.
- [x] **`map_transcript_to_requirements(meeting_number)`** — divide a transcrição em parágrafos (fallback para sentenças se não houver quebra de parágrafo) e usa o `source_quote` de cada requisito (campo já obrigatório e instruído em `SKILL_REQUIREMENTS.md`) para contar quantos requisitos cada trecho gerou — substring match direto, com fallback de sobreposição de palavras (Jaccard-like) quando o trecho não bate literalmente.
- [x] **`cluster_similar_requirements(meeting_number, threshold=0.85, max_requirements=200)`** — a "ferramenta matadora" proposta: embeddings via `modules/embeddings.py::embed_batch()` (infraestrutura já existente — coluna `requirements.embedding vector(768)` no schema, nunca antes usada por nenhum código) + clusterização gulosa por similaridade de cosseno (implementada em Python puro — `_cosine_similarity()` — para não adicionar dependência de numpy só para isso). Limite de 200 requisitos por chamada protege contra custo excessivo de API de embedding; acima disso, sugere `sample_requirements` primeiro.
- [x] Registro completo: schemas em `MEETINGS_REQUIREMENTS_SCHEMAS`, dispatch em `AssistantToolExecutor.execute()`, categoria "consulta" (não-admin, mesmo padrão de `describe_bpmn_process`/`ask_bpmn_diagram` apesar do custo real de embedding em `cluster_similar_requirements`). CLAUDE.md `§Tool list` atualizado.
- [x] 26 testes novos (`test_tools_requirement_investigation.py`): resolução de reunião, amostra reprodutível via seed, relatório de qualidade com/sem alerta de granularidade, mapeamento de trechos com correspondência exata e por sobreposição, similaridade de cosseno (idêntico/ortogonal/vetor-zero), clusterização agrupando vetores similares e mantendo dissimilares separados, limite de custo por chamada, erro claro quando o provedor de embedding não está configurado, gate de dispatch (nenhuma das 4 é admin-only).
- [x] 512/512 testes automatizados passando (486 + 26 novos).

---

### PC140 — Concluído (v5.15 / 2026-07-06) — reconciliador de requisitos duplicava reunião inteira a cada reprocessamento

**Achado:** após o PC139 revelar que AURORA tinha 2466 requisitos reais (não 1000 truncados), o usuário pediu para investigar se o número fazia sentido. Um segundo assistente (mesma sessão de chat) ofereceu uma hipótese alternativa — "super-granularidade": o pipeline teria fragmentado cada requisito em dezenas de micro-requisitos (ex: "validar CPF" virando 5 REQs separados), não duplicação literal. **Essa hipótese foi checada e refutada com evidência direta:** consulta ao banco mostrou apenas **47 títulos distintos** em 2466 linhas — e para o título mais repetido (123 ocorrências), a `description` era **100% idêntica** em todas as 123 linhas, criadas em rajadas ao longo de 8 dias diferentes (18/06 a 30/06), com um único dia (30/06) gerando 1000 linhas em ~8 minutos. Fragmentação geraria títulos/descrições DIFERENTES por micro-requisito — o padrão observado só é possível com duplicação literal via reprocessamento repetido.

**Causa raiz confirmada em `agents/agent_req_reconciler.py::run()`:**
```python
existing = [r for r in list_requirements(project_id)
            if r.get("last_meeting_id") != meeting_id]
```
`existing` é buscado UMA vez, ANTES do laço salvar qualquer requisito da rodada atual — portanto jamais poderia conter um "auto-match" da rodada em curso. A única coisa que esse filtro podia excluir eram requisitos criados por uma execução ANTERIOR da MESMA reunião. Resultado: toda vez que uma reunião era reprocessada, os requisitos que ELA MESMA criou da primeira vez ficavam fora do pool de candidatos — garantindo que 100% dos itens fossem classificados "novo" e duplicados integralmente, reunião após reunião, reprocessamento após reprocessamento.

- [x] `agents/agent_req_reconciler.py` — filtro removido; `existing = list_requirements(project_id)` considera TODOS os requisitos do projeto como candidatos, sempre.
- [x] `tests/test_agent_req_reconciler.py` (novo, 5 testes) — regressão direta: requisito com `last_meeting_id` igual à reunião sendo reprocessada agora é corretamente reconhecido como candidato (gera `add_requirement_version`, não `save_new_requirement`); requisitos de outras reuniões continuam funcionando; requisito genuinamente novo ainda cria linha nova; projeto sem histórico ainda cria linha nova.
- [x] **Limpeza de dados do Projeto AURORA (autorizada explicitamente pelo usuário):** dry-run confirmou 47 linhas canônicas (menor `req_number` por título) + 2419 duplicatas exatas (soma bate 100% com os 2466 originais). Antes de remover, o `status` da linha canônica foi promovido para o mais avançado visto entre as duplicatas do mesmo título (contradicted > revised > active, em 10 títulos onde reconciliações corretas entre reuniões diferentes já haviam gerado sinais reais de revisão/contradição) — nenhum sinal genuíno foi perdido. Executado dentro de uma transação com rollback automático em caso de discrepância na contagem esperada. Resultado: **47 requisitos** (24/12/6/5 por R1-R4), `requirement_versions` caiu de 2478 para **59** (histórico real preservado), nenhum outro projeto do banco foi tocado (total geral: 3854 → 1435, exatamente os 2419 removidos).
- [x] 486/486 testes automatizados passando (481 + 5 novos).
- [x] **Varredura de todos os outros projetos do banco (todos os domínios), não só o do usuário:** encontrado um SEGUNDO projeto real e ativo afetado pelo mesmo bug — **"SDEA — Sistema de Documentação Eletrônica da Auditoria"** (domínio `fgv`, 26 reuniões reais, maio–julho/2026): 787 de 1328 linhas eram duplicatas confirmadas (descrições 100% idênticas entre cópias), só que com fator de duplicação bem menor que o AURORA (~3x vs. até 123x) — provavelmente por ter sido reprocessado menos vezes. Outros projetos verificados (Tesouraria, Demandas SRA-SESUITE) já estavam limpos (ratio ~1,0–1,1). **Limpeza autorizada e executada com o mesmo protocolo** (dry-run → promoção de status em 47 títulos com sinal divergente → delete transacional com assert de contagem esperada e rollback automático em discrepância): 545 duplicatas removidas, 783 requisitos únicos mantidos, `requirement_versions` caiu para 946 (histórico real preservado). Nenhum outro projeto do banco foi tocado — total geral confirmado: 890 requisitos (783 SDEA + 51 Tesouraria + 47 AURORA + 9 SESUITE).
- **REGRA DERIVADA:** ao buscar candidatos para reconciliação/deduplicação, nunca filtrar a lista de "já existentes" por um campo que a PRÓPRIA operação em curso vai atualizar (aqui, `last_meeting_id`) — se o filtro só pode excluir itens gravados por uma execução ANTERIOR da mesma operação, ele nunca protege contra nada no caminho feliz e SEMPRE quebra o caminho de reprocessamento. Ao encontrar um bug de dados num projeto, sempre varrer o banco inteiro (todos os domínios/tenants) por sinais do mesmo padrão antes de considerar a correção completa — o bug já havia corrompido um segundo projeto real, silenciosamente, sem qualquer reclamação prévia do usuário.

### PC139 — Concluído (v5.15 / 2026-07-06) — contagens de KPI truncadas em 1000 (limite padrão do PostgREST)

**Achado:** logo após o PC138, usuário reportou que o Projeto AURORA mostrava exatamente 1000 requisitos. Consulta direta ao banco revelou: AURORA tem **2466** requisitos reais (não é bug de filtro — o escopo por `project_id` do PC138 estava correto). Causa: `get_domain_stats()`/`get_context_stats()` (e `get_global_stats()`) contavam via `len(_ok(query.execute()))` — isso só conta as linhas efetivamente **transferidas** na resposta, e o PostgREST/Supabase limita respostas a 1000 linhas por padrão quando não há paginação explícita. Qualquer tabela com mais de 1000 linhas correspondentes ao filtro sempre reportaria exatamente 1000, mascarado como se fosse a contagem real.

- [x] `core/project_store.py` — nova função auxiliar `_exact_count(db, table, filters)`: usa `count="exact"` + `.limit(1)` (padrão já usado em outro lugar do módulo, ex. contagem de `transcript_chunks`) — pede ao PostgREST para computar o agregado real no servidor, transferindo apenas 1 linha de dado. `get_domain_stats()`, `get_context_stats()` e `get_global_stats()` migradas para usar esse helper em vez de `len(_ok(...))`.
- [x] `tests/test_project_store_scoped_stats.py` — fake client do Supabase atualizado para simular fielmente o comportamento real: `.data` sempre limitado a 1000 linhas (ou ao `.limit()` explícito), mas `.count` (quando `count="exact"` é pedido) sempre reflete o total verdadeiro. Nova classe `TestExactCountBeyondPostgrestDefaultCap` (4 testes) reproduz o cenário exato do bug (2466 requisitos) e confirma que `get_context_stats()`/`get_domain_stats()` reportam o número real, não 1000.
- [x] 481/481 testes automatizados passando (477 + 4 novos).
- **Observação para o usuário (não corrigida, fora de escopo):** 2466 requisitos a partir de apenas 4 reuniões é um número atipicamente alto — pode ser um dataset de teste/carga deliberado, ou sintoma de um problema de duplicação na reconciliação de requisitos (`AgentReqReconciler`). Não investigado nesta correção — sinalizado para decisão do usuário se vale a pena auditar.

### PC138 — Concluído (v5.15 / 2026-07-06) — KPIs da Central de Operações misturavam dados de outros domínios

**Achado:** usuário reportou que, com o Projeto AURORA (domínio p2d) ativo, a Central de Operações mostrava 8 contextos, 32 reuniões, 51 processos e 2 documentos — mas o domínio p2d só tem 4 contextos reais. Causa: `pages/Home.py::_load_stats()` chamava `get_global_stats()`, que conta linhas em `contexts`/`meetings`/`requirements`/`bpmn_processes`/`meeting_documents` **sem nenhum filtro** (todos os tenants do banco inteiro) — e exibia esse total como se fosse o número do domínio ativo. Único chamador da função no código todo; o bug estava 100% no uso, não na função em si (que faz exatamente o que o nome diz).

- [x] `core/project_store.py` — duas novas funções: `get_domain_stats(tenant_id)` (soma contextos/reuniões/requisitos/processos/documentos de **um único tenant**, via `contexts.tenant_id` → lista de `project_id`s → `IN`) e `get_context_stats(project_id)` (mesmas contagens para **um único contexto**). Ambas fail-closed: `tenant_id`/`project_id` ausente retorna zeros, nunca cai para dado de outro escopo. `get_global_stats()` mantida (uso correto seria um painel de superadmin cross-tenant, ex. MasterAdmin.py), docstring atualizada avisando para não reutilizá-la em página escopada por domínio/contexto.
- [x] `pages/Home.py` — KPIs viram duas linhas, conforme sugestão do usuário: **"Totais do domínio"** (5 cards: Contextos/Reuniões/Requisitos/Processos/Documentos, sempre visível) e **"Totais do contexto ativo"** (4 cards, sem "Contextos" — não faz sentido nesse nível —, só aparece quando há um contexto ativo selecionado). `_render_kpi_row()` refatorado para indexar ícone/cor por chave de KPI (dict), não por posição — a linha de 4 itens não podia deslocar os ícones das linhas de 5 (bug que apareceria na primeira versão da implementação, pego antes do commit).
- [x] `modules/i18n.py` — novas chaves `kpi_row_domain`/`kpi_row_context` em PT e EN.
- [x] `tests/test_project_store_scoped_stats.py` (novo, 11 testes) — cenário replica o bug real: 2 tenants com 4 contextos cada, confirma que `get_domain_stats()` de um tenant nunca soma os 4 contextos/reuniões/requisitos do outro; `get_context_stats()` isola por projeto mesmo dentro do mesmo tenant; ambas fail-closed com `None`/sem DB.
- [x] Verificado com `AppTest`: as duas linhas renderizam com os valores corretos e nenhuma exceção.
- [x] 477/477 testes automatizados passando (466 + 11 novos).

### PC137 — Concluído (v5.15 / 2026-07-06) — Grafo de Conhecimento sem correlações: meeting_id=None na extração do Knowledge Hub

**Achado:** usuário reportou que o Projeto AURORA não exibia correlações no Grafo de Conhecimento. Consulta direta ao banco (psycopg2) confirmou: as 57 entidades e os 14 processos do projeto tinham `meeting_ids = {}` (vazio) e `first_seen_meeting_id`/`last_seen_meeting_id = NULL` — sem essa ligação, `_build_pyvis_graph()` nunca encontra interseção de reuniões entre entidades/processos, então nenhuma aresta é desenhada, mesmo com dados presentes.

**Causa raiz (bug ativo, não só dado antigo):** em `pages/Pipeline.py` (modo "Nova Transcrição") e em `core/batch_pipeline.py` (caminho de arquivo novo do BatchRunner), `run_pipeline()` é chamado **antes** de `create_meeting()` — o `config` passado nunca contém `"meeting_id"` nesse ponto, porque a reunião ainda não existe no banco. Dentro de `core/pipeline.py`, a extração do Knowledge Hub (`AgentKnowledgeExtractor`) roda **dentro** de `run_pipeline()`, sempre recebendo `meeting_id=None` — que se propaga para `upsert_entity()`/`upsert_process()` (`core/knowledge_store.py`), resultando em `meeting_ids=[]` sempre. Efeito colateral: a detecção de contradições entre reuniões (`_cd_agent.run_for_meeting`) tem a guarda `if _kh_project_id and _kh_meeting_id` — como `_kh_meeting_id` é sempre `None` nesse caminho, ela nunca dispara. Isso afeta **toda reunião nova processada por essas duas vias, em qualquer projeto** — não é específico do AURORA.

- [x] `core/pipeline.py` — extraída a lógica de extração do Knowledge Hub + detecção de contradições para uma nova função pública `run_knowledge_extraction(hub, client_info, provider_cfg, output_lang, meeting_id, project_id, progress_callback)`. `run_pipeline()` só chama essa função internamente quando `config.get("meeting_id")` já está presente (`and config.get("meeting_id")` adicionado à guarda) — preserva o comportamento exato para callers que já operam sobre uma reunião existente (BatchRunner reprocessamento, BpmnBackfill, MinutesBackfill, RequirementsBackfill, api.py).
- [x] `pages/Pipeline.py` — chamada explícita a `run_knowledge_extraction()` adicionada logo após `create_meeting()` ter sucesso, usando o `meeting_id` real, mesmo padrão já usado ali para requisitos/SBVR/BPMN.
- [x] `core/batch_pipeline.py` — mesmo fix aplicado ao caminho de arquivo novo (`_run_one`): chamada explícita após `create_meeting()`, respeitando `agents_config.get("run_knowledge_extractor", True)`. Achado colateral durante a implementação — esse caminho tinha exatamente o mesmo bug, não documentado no diagnóstico inicial. O caminho de reprocessamento (reunião já existente) já passava `meeting_id` corretamente e não foi alterado.
- [x] `tests/test_pipeline_knowledge_extraction.py` (novo, 8 testes): `run_knowledge_extraction()` isolado (chama extractor+detector corretamente, pula quando `meeting_id`/`project_id` ausente, engole exceções sem propagar); guarda de `run_pipeline()` (não dispara sem `meeting_id` mesmo com a flag ligada — cenário exato do bug; dispara normalmente quando `meeting_id` já está no config — compatibilidade retroativa; respeita a flag desligada).
- [x] 466/466 testes automatizados passando (458 + 8 novos).
- **Remediação de dados do Projeto AURORA:** não executável por mim neste ambiente (sem chave de API de LLM disponível — por design de segurança do projeto, chaves só existem em `st.session_state` de uma sessão viva). Para corrigir os dados já gravados, o usuário deve rodar a ferramenta `populate_knowledge_hub` (admin, via Assistente) apontando para as 4 reuniões do AURORA — como o código já testado agora enche `meeting_id` corretamente nesse caminho, isso mescla o vínculo correto nas entidades/processos já existentes sem duplicar nada (upsert por `canonical_name`+`entity_type` / `process_name`).
- **REGRA DERIVADA:** ao passar `config`/parâmetros que dependem de um recurso ainda não persistido (aqui, `meeting_id` antes de `create_meeting()`), nunca assumir que um valor "opcional" ausente é inofensivo — rastrear explicitamente até onde esse `None` se propaga. Um `if _kh_meeting_id:` isolado nesse ponto teria custado uma linha; sua ausência quebrou silenciosamente uma feature inteira (correlações do Grafo de Conhecimento) por múltiplas versões sem nenhum teste pegando isso.

### PC136 — Concluído (v5.15 / 2026-07-05) — elimina duplicação entre "Sobre o P2D" e "Apresentação Geral"

### PC136 — Concluído (v5.15 / 2026-07-05) — elimina duplicação entre "Sobre o P2D" e "Apresentação Geral"

**Achado:** usuário perguntou se as duas páginas do grupo "Início" deveriam ser fundidas. Confirmado: mesmo sistema visual (CSS quase clonado, só com nomes de classe diferentes), as mesmas 4 estatísticas do "paradoxo" (71%/R$8,2k/2,3h/67%), o mesmo diagrama de pipeline de 4 passos e as mesmas 5 métricas de ROI apareciam nas duas páginas. Em vez de fundir num scroll único (perderia a função de navegação de cada página), redistribuído por propósito.

- [x] `pages/SobreP2D.py` — slimmed para "autor + filosofia + aprofundamento técnico": removido o slide "O Paradoxo" (idêntico a "O Problema" da Apresentação Geral); removidos os 5 ROI bars do slide do Criador, substituídos por um parágrafo curto de filosofia sem números (os 4 cards qualitativos de valor foram mantidos — não duplicavam nada); slide "Capacidades" (9 cards parciais) substituído por um resumo compacto + `st.page_link` real para a lista completa de 12 artefatos na Apresentação Geral. Mantidos: Capa, Criador (revisado), O que é o P2D, CKF (aprofundamento único), Multi-LLM/Provedores (aprofundamento único).
- [x] `pages/ApresentacaoGeral.py` — vira dono único de todas as estatísticas/ROI/pipeline/lista de artefatos. Slide "Diferenciais" ganhou menções cruzadas ("aprofundamento em Sobre o P2D") nos cards de CKF e Multi-LLM + `st.page_link` real para "Sobre o P2D".
- [x] Comentários de cabeçalho de ambos os arquivos atualizados declarando explicitamente qual página é dona de qual conteúdo, para evitar reintrodução da duplicação em manutenções futuras.
- [x] Verificado com `AppTest`: as duas páginas renderizam sem exceção após a reestruturação.
- [x] 458/458 testes automatizados inalterados (mudança de conteúdo/UI, sem lógica nova).

### PC135 — Concluído (v5.15 / 2026-07-05) — Assistente ganha poderes de gerar e interpretar diagramas BPMN

**Pedido do usuário:** "Crie funcionalidades (tools) para dar poderes ao assistente de gerar um diagrama como base numa transcrição. Crie também um agente capaz de interpretar e analisar um diagrama BPMN, [...] responder: 'Descreva o subprocesso Contratar Consultoria' dentre outras perguntas."

**Novo agente — `agents/agent_bpmn_analyst.py::AgentBPMNAnalyst`** (on-demand, `skills/skill_bpmn_analyst.md`, registrado em `AGENT_REGISTRY` como `read`):
- [x] `answer(process_name, bpmn_xml, question, detail_context, output_language)` — mesmo padrão de `AgentBPMNReviewer.review()`/`DocumentAnalyzerAgent.analyze()`: resposta em texto livre (Markdown leve), não JSON — `_call_llm` chamado diretamente.
- [x] `_strip_diagram_interchange(xml_str)` — remove `<bpmndi:BPMNDiagram>` (coordenadas visuais, zero valor semântico) antes de enviar ao LLM, reduzindo tokens sem perder nenhuma informação relevante para responder perguntas. Registra namespaces canônicos antes de reserializar — evita mangling `ns0:`.
- [x] Skill instrui: localizar o elemento pelo nome (tolerante a acentuação/plural), descrever via `documentation` + posição no fluxo (predecessor/sucessor) + lane/pool; nunca inventar elementos inexistentes; usar detalhamento de fase já salvo (PC120/PC129) quando disponível em vez de só o resumo.

**3 novas ferramentas do assistente** (`core/tools/tools_bpmn_sbvr.py`):
- [x] `ask_bpmn_diagram(process_name, question)` — não-admin. Resolve o processo, busca detalhamentos de fase salvos cujo nome apareça na pergunta (via `list_bpmn_callactivity_diagrams` na versão atual) e injeta como contexto extra, chama `AgentBPMNAnalyst`.
- [x] `generate_bpmn_diagram(meeting_number=None, description=None, n_runs=1)` — não-admin. Reaproveita `generate_bpmn_from_description()` (mesmo torneio do BPMN Studio) a partir da transcrição de uma reunião existente OU de texto livre. `n_runs` limitado a 1-3 (proteção de custo via chat). **Não salva automaticamente** — retorna nome sugerido, score do torneio, descrição estruturada e o XML completo, instruindo o uso de `save_generated_bpmn` após confirmação do usuário (mesmo padrão de dois passos já usado por `suggest_bpmn_corrections`→`save_bpmn_revision` e `preview_text_correction`→`apply_text_correction` — o XML trafega no próprio texto de retorno da tool, sem depender de estado entre turnos, já que uma nova instância de `AssistantToolExecutor` é criada a cada turno).
- [x] `save_generated_bpmn(process_name, bpmn_xml, mermaid_code="", meeting_number=None)` — **admin only**. Usa `save_bpmn_from_hub()` (mesma função do BPMN Studio) com um `KnowledgeHub` mínimo — cria processo novo OU nova versão de um existente com o mesmo nome, via `_find_or_create_bpmn_process` já implementado em `project_store.py`.
- [x] Registro completo: schemas em `BPMN_SBVR_SCHEMAS`, dispatch em `AssistantToolExecutor.execute()`, `save_generated_bpmn` em `_ADMIN_TOOLS`, categorias em `_TOOL_CATEGORIES` (`ask_bpmn_diagram`/`generate_bpmn_diagram` → consulta, `save_generated_bpmn` → admin). CLAUDE.md `§Tool list` atualizado.
- [x] **Achado colateral (não corrigido, fora de escopo):** `apply_bpmn_corrections` instancia `AgentBPMNReviewer()` sem argumentos — `BaseAgent.__init__` exige `client_info`/`provider_cfg`, então essa chamada levantaria `TypeError` em produção. Bug pré-existente, não introduzido nesta sessão; corrigido o padrão correto (`self.llm_config.get("api_key")`/`self.llm_config.get("provider_cfg")` → novo helper `_resolve_llm_agent_config()`) nas 3 ferramentas novas, mas `apply_bpmn_corrections` em si não foi tocado — sinalizado ao usuário para decisão futura.
- [x] 37 testes novos (`test_agent_bpmn_analyst.py` — 12, `test_tools_bpmn_generation_analysis.py` — 25): DI-stripping, montagem de prompt, resposta via LLM mockado, resolução de processo/versão, contexto de detalhamento por nome, geração a partir de reunião/descrição, cap de `n_runs`, salvamento (novo processo e nova versão), gate admin no dispatch. 458/458 testes automatizados passando.

### PC134 — Concluído (v5.15 / 2026-07-05) — botão de copiar XML restaurado

**Achado:** usuário reportou que a reformatação em múltiplas linhas do PC133 fez desaparecer o botão de copiar o texto do XML. As 4 caixas `st.code(xml, language="xml")` nunca tiveram um botão de copiar explícito próprio — o PC133 só trocou o conteúdo exibido, mas isso deixou mais evidente a ausência de uma forma fácil de copiar o XML inteiro de um bloco agora multi-linha.

- [x] Reaproveitado `ui/components/copy_button.py::copy_button()` (já usado em outras páginas do app) ao lado dos 4 blocos de código XML: `pages/BpmnStudio.py` (diagrama principal + detalhamento de fase) e `pages/BpmnEditor.py` (detalhamentos salvos + XML da versão selecionada). Copia a versão já formatada (pretty-printed) exibida na tela.
- [x] Verificado com `AppTest` ponta-a-ponta: nenhuma exceção após adicionar os botões nos 2 fluxos do BPMN Studio e do BpmnEditor.
- [x] 420/420 testes automatizados inalterados (mudança de UI, sem lógica nova).

### PC133 — Concluído (v5.15 / 2026-07-05) — XML formatado (indentado) nas caixas de código

**Contexto:** usuário reportou que os blocos `st.code(xml, language="xml")` no BPMN Studio e no Editor BPMN mostravam o XML numa única linha contínua, difícil de ler. Causa: `xml.etree.ElementTree.write()` (usado por `modules/bpmn_generator.py`) não insere espaço/quebra entre tags — comportamento correto para armazenamento/bpmn-js/banco, mas ruim para leitura humana em texto puro.

- [x] `modules/bpmn_viewer.py::pretty_print_xml(xml_str)` — novo utilitário **somente de exibição** (nunca grava de volta em `hub.bpmn.bpmn_xml` nem é persistido): usa `xml.dom.minidom` para reindentar, remove as linhas em branco que o `toprettyxml()` espalha entre toda tag, e reanexa a declaração XML original (minidom descarta `encoding="UTF-8"` da declaração por padrão). Fail-open: retorna a string original se o parse falhar.
- [x] Aplicado nos 4 pontos que exibem XML BPMN em `st.code()`: `pages/BpmnStudio.py` (diagrama principal + detalhamento de fase) e `pages/BpmnEditor.py` (detalhamentos salvos + XML da versão selecionada).
- [x] `tests/test_bpmn_viewer_pretty_print.py` (novo, 9 testes) — quebras de linha inseridas, ids/documentation preservados, sem linhas em branco, indentação presente, string vazia/XML malformado tratados sem exceção, declaração original com encoding preservada, resultado ainda é XML válido.
- [x] Verificado com `AppTest` ponta-a-ponta: os dois blocos de código do BPMN Studio (principal + detalhamento) saem com múltiplas linhas, sem exceção.
- [x] 420/420 testes automatizados passando (411 + 9 novos).

### PC132 — Concluído (v5.15 / 2026-07-05) — gateway sem `<documentation>` em diagramas de colaboração (multi-pool)

**Achado:** usuário perguntou se o algoritmo preenche `<documentation>` nos elementos BPMN gerados. Varredura de todos os pontos de construção de `BpmnElement(...)` em `agents/agent_bpmn.py` confirmou: sim, para tarefas/callActivity/subProcess/eventos intermediários, em ambos os caminhos (pool único e colaboração) — exceto um: `_build_pool_elements()` (caminho multi-pool) tinha um branch dedicado para `step.is_decision` (exclusiveGateway) que nunca passava `documentation=step.description`, diferente dos branches de evento e de tarefa logo ao lado, que já passavam. No caminho de pool único esse problema não existe — lá gateway e tarefa reaproveitam o mesmo código. Resultado: um mesmo processo modelado como colaboração perdia silenciosamente o critério de decisão documentado pela LLM no gateway, mesmo quando o skill instrui explicitamente a documentá-lo.

- [x] `agents/agent_bpmn.py::_build_pool_elements()` — branch `elif step.is_decision:` agora inclui `documentation=step.description or ""`, igualando aos outros dois branches.
- [x] `tests/conftest.py::step()` — parâmetro `description=""` adicionado ao factory (aditivo, não quebra chamadas existentes).
- [x] `tests/test_agent_bpmn_multipool_documentation.py` (novo, 2 testes) — confirma que um gateway com `description` num modelo de colaboração agora produz `<documentation>` na tag do `exclusiveGateway`; guarda de regressão confirmando que o caminho de pool único (que já funcionava) continua funcionando.
- [x] 411/411 testes automatizados passando (409 + 2 novos).

### PC131 — Concluído (v5.15 / 2026-07-05) — Heuristic 5 (far lane-span) + guidance de consolidação de decisão em callActivity

**Contexto:** revisão de um processo real de 6 lanes ("Governança de IA", 14 etapas). Antes de reportar qualquer coisa como bug, reconstruí o modelo do jeito CORRETO — como ele existia em `hub.bpmn.steps` no momento em que o torneio pontuou, sem os elementos `lnk_throw_*`/`lnk_catch_*` sintéticos que só existem dentro da string XML final (`_apply_link_events()` escreve em `bpmn.elements`, uma estrutura efêmera de `_generate_bpmn_xml()`, nunca em `hub.bpmn`) — evitando reportar "dead end"/"fan-in" como bugs de scoring que na verdade nunca acontecem no pipeline real (esses eram artefatos da minha primeira reconstrução, feita a partir do XML final por engano). Score real do torneio: **8.9/10** (não os 4.9-6.9 da reconstrução errada). Dois achados sobreviveram à verificação:

1. **Achado 1 (código) — lacuna geométrica em `_detect_crossings()`:** `S13→S14` e `S13→S18` cruzam as mesmas 4 fronteiras de lane que `S13→S05` (já convertido corretamente para Link Events pela Heuristic 4, por ser um loop *para trás*), mas por serem *para frente* e as lanes puladas (Segurança/Jurídico/Arquitetura) terem seus próprios elementos numa faixa de coluna anterior, escapavam da Heuristic 2 (que só converte quando há sobreposição real de coluna com elementos das lanes puladas).
2. **Achado 2 (modelagem) — S04–S08 e S12–S13 são sub-fluxos coesos de decidir-e-convergir** que caberiam num único `callActivity` cada, mas ficaram expandidos no nível 1 (contribuindo para os 18 nós vs. limite de 10).

- [x] `modules/bpmn_generator.py::_detect_crossings()` — nova **Heuristic 5**: qualquer flow cujo `abs(lane_index_src - lane_index_tgt) >= 3` (≥2 lanes intermediárias puladas) é convertido em Link Events incondicionalmente, independente de sobreposição de coluna — complementa (não substitui) a Heuristic 2, que continua tratando o caso de exatamente 1 lane pulada com a checagem de sobreposição.
- [x] `tests/test_bpmn_generator_link_events.py` (novo, 4 testes) — reconstrói o cenário real de 6 lanes via `generate_bpmn_xml()` ponta-a-ponta: confirma que `S13→S14`/`S13→S18` (para frente) agora viram Link Events, que `S13→S05` (para trás, já funcionava) continua funcionando, que flows de lane adjacente permanecem diretos, e que um processo simples de 2 lanes não gera Link Events nenhum (guarda contra falso positivo).
- [x] `skills/skill_bpmn.md` (10.1→10.2) — novo critério 5 em "Critério primário para usar `callActivity`": um gateway cujos ramos reconvergem no mesmo ator sem mudar quem processa o próximo passo deve ser encapsulado inteiro (condição + ramos + reconvergência) num único `callActivity` — com o exemplo real do caso "Avaliar e Classificar Risco" (S04-S08) e uma ressalva explícita para NÃO aplicar quando a decisão determina o próximo ator/lane. Item correspondente adicionado ao checklist de autoverificação (Hierarquia e Densidade).
- [x] 409/409 testes automatizados passando (405 + 4 novos).
- **REGRA DERIVADA:** ao investigar um diagrama gerado, sempre verificar em QUE ESTÁGIO do pipeline o objeto sendo inspecionado realmente existe antes de reportar um achado — reconstruir a partir do XML final (pós-geração) pode incluir elementos sintéticos (Link Events) que o scorer/tournament nunca viu, produzindo "bugs" que não existem no caminho real de decisão.

### PC130 — Concluído (v5.15 / 2026-07-05) — SVGMatrix non-finite no editor bpmn-js (Modeler)

**Achado:** usuário reportou "❌ Erro ao carregar BPMN: Failed to execute 'scale' on 'SVGMatrix': The provided float value is non-finite." ao usar a aba Detalhamento (PC128). Esse é exatamente o pitfall já documentado no CLAUDE.md ("bpmn-js SVGMatrix non-finite"), mas o fix (deferir `canvas.zoom('fit-viewport')` via `setTimeout` com guarda de dimensões finitas) só havia sido aplicado em `modules/bpmn_viewer.py` (visualizador somente-leitura) — nunca em `modules/bpmn_editor.py` (Modeler editável), que chamava `canvas.zoom('fit-viewport', 'auto')` de forma síncrona logo após `importXML().then()`. O PC128 passou a renderizar múltiplas instâncias do Modeler na mesma página (diagrama principal + uma por detalhamento salvo) — aumentando bastante a chance de algum iframe ainda não ter dimensões computadas no momento do zoom.

- [x] `modules/bpmn_editor.py` — nova função `fitView()` (mesmo guard de `bpmn_viewer.py`: só chama `zoom('fit-viewport')` se `viewbox().inner`/`.outer` tiverem width/height finitos e > 0; caso contrário usa `zoom(0.75)` como fallback seguro). Chamada via `setTimeout(fitView, 150)` dentro do `.then()` de `importXML()`, e reaproveitada pelo botão "⊞ Ajustar" (antes chamava `zoom('fit-viewport')` direto).
- [x] Verificado que o HTML gerado por `editor_from_xml()` contém `setTimeout(fitView, 150)` e a definição de `fitView()` uma única vez.
- [x] 405/405 testes automatizados inalterados (mudança isolada em template JS, sem lógica Python nova).
- **REGRA DERIVADA:** ao aplicar um fix de robustez num componente (viewer), verificar se existe um componente irmão com o mesmo padrão JS (editor) que precisa do mesmo fix — não basta corrigir onde o bug foi originalmente visto; `bpmn_viewer.py` e `bpmn_editor.py` compartilham a mesma chamada `canvas.zoom('fit-viewport')` mas divergiram silenciosamente por anos até uma mudança de UI (PC128) aumentar a superfície de exposição do lado não corrigido.

### PC129 — Concluído (v5.15 / 2026-07-05) — detalhamentos de fase salvos ficam visíveis no BpmnEditor

**Achado:** usuário perguntou se a relação processo-pai ↔ detalhamentos já estava garantida no banco. Confirmado que o schema (`bpmn_callactivity_diagrams.bpmn_version_id NOT NULL REFERENCES bpmn_versions(id) ON DELETE CASCADE`, PC120) está correto e a escrita (`save_bpmn_callactivity_diagram`) já amarra corretamente à versão atual. Porém `list_bpmn_callactivity_diagrams()` — a função de leitura, também escrita no PC120 — nunca era chamada em lugar nenhum do app (confirmado via grep no repositório inteiro). Resultado: a relação era **write-only** da perspectiva da UI — detalhamentos salvos ficavam invisíveis assim que a sessão do BpmnStudio terminava, recuperáveis só via SQL direto.

- [x] `pages/BpmnEditor.py` — nova seção "🔍 Detalhamentos de fases salvos (N)" logo após a seleção de processo/versão: chama `list_bpmn_callactivity_diagrams(selected_version["id"])` e renderiza cada detalhamento (nome da fase, pool, score do torneio, diagrama via `preview_from_xml`, código XML). Local escolhido porque `selected_version["id"]` já é estável e conhecido ali — ao contrário de uma regeneração no BpmnStudio, onde os `element_id` de callActivity mudam a cada novo run do LLM e não haveria correspondência confiável com detalhamentos de uma versão anterior.
- [x] **Decisão explícita de escopo:** avaliada a mesma reidratação dentro de `pages/BpmnStudio.py` (segunda opção citada na proposta original) e descartada por análise de fluxo real — BpmnStudio.py hoje não tem NENHUM caminho para "reabrir um processo já salvo" (o hub só existe a partir de uma geração fresca na sessão atual); sem esse recurso mais amplo (fora de escopo desta correção), uma reidratação ali nunca teria uma versão salva para encontrar. Sinalizado ao usuário como feature separada, não implementada.
- [x] Verificado com `AppTest` (Supabase mockado): abrir uma versão com detalhamento salvo mostra a seção corretamente (nome da fase, pool, score); nenhuma exceção. 405/405 testes automatizados inalterados (mudança de UI, sem lógica de agente nova).

### PC128 — Concluído (v5.15 / 2026-07-05) — detalhamento de fase editável + aba própria "Detalhamento"

**Contexto:** usuário confirmou o fix do PC127 com um caso real (score 7.5/10 — detalhamento single-pool correto de "Contratar Fornecedor") e pediu duas melhorias de UX: (1) o diagrama de detalhamento deve ser editável como o principal (PC119 só cobria o diagrama-pai); (2) uma aba própria "Detalhamento" deve aparecer assim que "Gerar BPMN" for bem-sucedido, em vez do detalhamento viver numa seção solta abaixo do botão "Salvar".

- [x] `pages/BpmnStudio.py` — nova aba `🔍 Detalhamento` adicionada ao mesmo nível de `📐 Diagrama BPMN` / `📊 Mermaid` (`st.tabs([...])`), substituindo a antiga seção "🔍 Detalhar uma fase" que ficava fora das abas, após "💾 Salvar". A leitura do XML colado/editado do diagrama principal (`_active_xml`) e `_extract_call_activities()` foram movidos para antes da criação das abas, para ficarem disponíveis nas três.
- [x] Cada diagrama já detalhado (dentro de `hub.bpmn.detail_diagrams`) agora usa `editor_from_xml` (bpmn-js Modeler) + text_area de colagem, exatamente o padrão do diagrama principal (PC119) — antes usava `preview_from_xml` (somente leitura). Chaves de estado com sufixo `__{element_id}` (`bpmns_detail_paste_xml__<id>`, `_bpmns_detail_edited_xml__<id>`) para isolar a edição de cada fase detalhada.
- [x] Botão "↩️ Descartar" por detalhamento, com o mesmo padrão flag+`st.rerun()` já usado no diagrama principal e no BpmnEditor.py (nunca escrever na key do widget após ele já ter sido instanciado no mesmo run) — generalizado para múltiplos detalhamentos via um sweep no topo do script (`for _k in st.session_state.keys(): if _k.startswith("_bpmns_detail_reset_paste__")...`), já que os elementos são dinâmicos (um por callActivity).
- [x] "💾 Salvar detalhamento" agora grava a versão editada (`_d_active_xml`) quando houver, em vez de sempre gravar `_detail_model.bpmn_xml` original — paridade com o Salvar do diagrama principal.
- [x] Import `preview_from_xml` removido de `pages/BpmnStudio.py` (não é mais usado nesta página).
- [x] Verificado com `AppTest` ponta-a-ponta (LLM mockado): gerar → aba Detalhamento aparece → Detalhar fase (com `is_phase_detail=True` confirmado no mock) → editor + paste-back existem → colar XML editado é capturado corretamente → Descartar reseta sem `StreamlitAPIException`. 405/405 testes automatizados inalterados (mudança de UI, sem lógica de agente nova).

### PC127 — Concluído (v5.15 / 2026-07-05) — "Detalhar uma fase" hallucinava um novo processo de 2 pools em vez de detalhar a fase

**Achado:** usuário perguntou se "Detalhar uma fase" roda com os mesmos critérios do diagrama pai. Resposta: mesma infraestrutura (mesmo `generate_bpmn_from_description()`, mesmo torneio, mesmo `AgentValidator`), mas resultado incorreto para o tipo de input. Confirmado com um caso real: detalhar o callActivity "Contratar Fornecedor" (documentation: "Abrir solicitação, elaborar termo de referência, encaminhar a fornecedores, receber e analisar propostas, aprovar ou reabrir concorrência, elaborar e enviar contrato.") devolveu uma nova collaboration de 2 pools ("Contratante"/"Fornecedor") reciclando o próprio nome da fase como callActivity interno — não um detalhamento dos passos internos daquela única fase. Causa: dois mecanismos calibrados para descrições de processo INTEIRAS (não para o texto curto de uma fase) disparam sobre a `documentation` de qualquer callActivity que mencione vocabulário de fornecedor/contrato — vocabulário inevitável numa fase que trata exatamente disso: (1) `_select_canonical_pattern()` conta 2 hits ("fornecedor", "concorrência") e injeta o GABARITO CANÔNICO de `bpmn_pattern_collab_callactivity_phases` (2 pools, 4+3 fases) como esqueleto a seguir; (2) a detecção proativa de colaboração (`_COLLAB_KEYWORDS`) reforça o mesmo mandato de formato multi-pool.

- [x] `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` — novo parâmetro `is_phase_detail: bool = False`; quando True, seta `agent._skip_canonical_pattern = True` e `agent._force_single_pool = True` na instância de `AgentBPMN` antes do torneio.
- [x] `agents/agent_bpmn.py::build_prompt()` — pula `_select_canonical_pattern()` quando `_skip_canonical_pattern` está setado.
- [x] `agents/agent_bpmn.py::run()` — `_collaboration_expected` agora é `False` sempre que `_force_single_pool` está setado (mesmo com hits de keyword/NLP); nesse caso injeta um novo bloco `MANDATORY FORMAT — SINGLE-ACTOR PHASE DETAIL` no system prompt instruindo explicitamente a não criar pools adicionais para a contraparte citada — ela já está modelada em outro lugar no diagrama pai. `_flat_hint` (retry) ganhou o mesmo terceiro ramo.
- [x] `pages/BpmnStudio.py` — a chamada de "🔍 Detalhar" passa `is_phase_detail=True`; a geração principal ("Gerar BPMN") continua sem a flag.
- [x] 9 testes novos (`test_agent_bpmn_studio.py::TestPhaseDetailFlag`, `test_agent_bpmn_canonical_patterns.py::TestForceSinglePoolGuard` + 1 em `TestBuildPromptInjectsPattern`), incluindo regressão explícita: o MESMO texto de fase que antes disparava GABARITO/colaboração agora produz o bloco single-actor e nada de GABARITO. 405/405 testes passando.
- **REGRA DERIVADA:** heurísticas de detecção (canonical pattern, colaboração proativa) calibradas para um tipo de input (descrição de processo completa) não generalizam automaticamente para outro tipo de input que reusa a mesma função (documentation de uma única fase) — mesmo vocabulário de domínio, contexto semântico diferente. Ao reaproveitar uma função para um novo caller com um formato de input distinto, sempre revisar explicitamente que heurísticas de "detecção de formato" internas àquela função ainda fazem sentido para o novo formato, em vez de assumir que "mesma função = mesmo comportamento correto".

### PC126 — Concluído (v5.15 / 2026-07-05) — callActivity/subProcess deixam de ser penalizados como tarefa granular no scorer

**Achado:** com a recalibração dos padrões canônicos (PC123) já produzindo diagramas hierárquicos de verdade (`callActivity` bem usado, message flows completos, nomes específicos), a dimensão `tipo de tarefa` do torneio pontuava só 4.3-4.6/10 num diagrama estruturalmente perfeito (`estrutural 10.0`, `semântica 10.0`). Causa: `_score_tasktype` avalia `callActivity` pela mesma heurística de palavras-chave (`_SERVICE_KW`/`_MANUAL_KW`) usada para tarefas granulares — a `description` de uma fase descreve o que acontece **dentro** dela ("processar pagamento", "notificar fornecedor"), não o tipo do container em si. Isso penalizava a `callActivity` como se "devesse ter sido" `serviceTask` (3.0), exatamente o padrão que o PC121/123 foram construídos para incentivar.

- [x] Nova constante `_ABSTRACTION_TASK_TYPES = {"callActivity", "subProcess", "eventSubProcess"}` em `agents/agent_validator.py`.
- [x] `_score_tasktype` — esses tipos agora pontuam **8.0 se documentados, 5.0 se não** (nunca via matching de palavra-chave) — recompensa a boa prática de documentação exigida pelo skill (Passo 2) sem aplicar uma heurística de tarefa granular a um container de fase.
- [x] **Nota sobre uma segunda análise externa recebida junto com a aprovação:** o pseudocódigo sugerido tinha um bug real — `score = 0.0  # neutro` (0.0 não é neutro, é a pior nota possível; teria piorado o problema). Não implementado dessa forma — os valores reais usados (8.0/5.0) preservam a lógica de keyword matching já existente para os demais tipos, que o pseudocódigo também descartava incorretamente.
- [x] Verificado com o cenário real reportado pelo usuário: score de `tipo de tarefa` subiu de 4.6 para 8.0 na reconstrução exata do diagrama.
- [x] 4 testes novos, incluindo regressão explícita (diagrama hierárquico não pode mais perder para um flat equivalente nesta dimensão). 400/400 testes passando.

### PC125-B — Concluído (v5.15 / 2026-07-05) — tempo total exibido após a geração

Usuário pediu onde ver o tempo que a geração levou — o contador do PC125 desaparece ao concluir (`_status.empty()`), sem deixar registro. Fix: tempo total (`time.time()` antes/depois da chamada) persistido em `st.session_state` e exibido na legenda do score — "🏆 Melhor de N execuções... · ⏱️ Xs" — tanto na geração principal quanto no detalhamento de fase (PC120). Verificado com `AppTest`: legenda renderiza com o sufixo de tempo corretamente. 396/396 testes inalterados.

### PC125 — Concluído (v5.15 / 2026-07-05) — contador de tempo real durante a geração no BPMN Studio

**Contexto:** mesmo com "Passes de Otimização" reduzido para 1 (PC124), o usuário reportou que a espera ainda parecia longa sem nenhum feedback de quanto tempo realmente estava passando — o `st.spinner()` anterior só mostra um ícone girando, sem contagem.

- [x] `pages/BpmnStudio.py::_run_with_live_timer()` — nova função auxiliar: roda a chamada de geração (`generate_bpmn_from_description`) num `ThreadPoolExecutor(max_workers=1)` enquanto a thread principal atualiza um placeholder (`st.empty()`) com os segundos decorridos a cada 1s. Mesmo padrão de segurança já usado em produção para Ata+Requisitos em paralelo (`agents/orchestrator.py`) — só que aqui com 1 worker, unicamente para manter a UI respondendo enquanto a chamada real roda em background. Propaga a exceção original via `Future.result()`, preservando o tratamento de erro existente.
- [x] Aplicado nos dois pontos que chamam `generate_bpmn_from_description` na página: botão principal "🧩 Gerar BPMN" e "🔍 Detalhar uma fase" (PC120).
- [x] Verificado com `AppTest` (LLM mockado): os dois fluxos completam sem exceção, com a thread em background sendo corretamente aguardada e o resultado repassado ao script principal.
- [x] 396/396 testes automatizados inalterados.

### PC124 — Concluído (v5.15 / 2026-07-05) — controle de "Passes de Otimização" visível onde a espera acontece

**Contexto:** usuário com apresentação no dia seguinte notou que o torneio de 3 execuções ficou mais lento (consequência esperada e correta do PC118-D — não tem mais atalho de cache mascarando 2 das 3 chamadas). Procurando reduzir para 1 passe, não encontrou o controle — ele existe em `pages/Settings.py` (aba Preferências → "🔄 Pipeline BPMN") e também escondido dentro do accordion fechado "⚙️ Configuração Avançada" na barra lateral do Pipeline, nenhum dos dois visível a partir de onde a espera realmente acontece.

- [x] `pages/BpmnStudio.py` — `select_slider` "Passes de Otimização" adicionado na aba Gerar, logo acima do botão "🧩 Gerar BPMN". Mesma chave `st.session_state["n_bpmn_runs"]` das outras duas cópias — sem novo estado, só nova superfície. A seção "🔍 Detalhar uma fase" (PC120) herda automaticamente, já que lê a mesma chave.
- [x] `pages/Pipeline.py` — mesmo controle adicionado no corpo principal da página (Modo Nova Transcrição), visível quando "Arquiteto BPMN" está ativo, em vez de só dentro do accordion da barra lateral.
- [x] Levantamento de escopo: existe um 3º lugar que produz BPMN via LLM — `pages/BpmnEditor.py` "🔄 Reconverter com Method & Style v7.0" — mas esse roda o `AgentBPMN` uma única vez, sem torneio nenhum implementado. Dar a ele essa opção exigiria construir a lógica de torneio ali (não é só expor UI). Adiado — usuário sem tempo de validar lógica nova de geração na véspera de uma apresentação; revisitar depois.
- [x] Verificado com `AppTest`: novo slider renderiza (`select_slider` com key `bpmns_n_runs_slider`), sem exceção, fluxo completo (gerar → detalhar → salvar) continua funcionando.
- [x] 396/396 testes automatizados inalterados (mudança de UI em 2 páginas, sem lógica nova).

### PC123 — Concluído (v5.15 / 2026-07-04) — sinais canônicos frágeis demais + gap de nome genérico de fim

**Diagnóstico solicitado pelo usuário** antes de decidir entre recalibrar sinais (opção 2) ou construir correção determinística pós-geração (opção 4): testei `_select_canonical_pattern()` contra 3 descrições naturais e plausíveis do mesmo cenário de consultoria — **2 das 3 pontuaram 0 hits** contra os `trigger_signals` do PC121. Causa: os sinais eram frases quase exatas tiradas do vocabulário de SAÍDA de gerações anteriores ("reabrir concorrência", "avaliação final do fornecedor"), sensíveis a conjugação verbal e ordem de palavras — não capturavam o conceito, só a frase literal.

- [x] `bpmn_pattern_collab_callactivity_phases.json` — `trigger_signals` trocados por fragmentos curtos e genéricos ("fornecedor", "consultoria", "prestação de serviços", "terceirizada", "relatório mensal", "concorrência", "avaliação final", etc.) — mais permissivos individualmente, mas o limiar de ≥2 hits já filtra falsos positivos.
- [x] **Achado adicional durante a mesma investigação:** o XML gerado usava `"Processo Encerrado"` como nome de End Event nas duas pools — regressão frente à versão anterior (`"Contrato Encerrado e Arquivado"` / `"Consultoria Concluída"`, nomes específicos ao resultado). `_GENERIC_END_NAMES` em `agent_validator.py` tinha "encerrar"/"terminar" (infinitivo) mas não pegava "encerrado"/"concluído" (particípio) — falso negativo confirmado (`semantic=10.0` num XML que deveria ter sido penalizado). Adicionadas as formas "processo encerrado/concluído/finalizado/terminado" — o "processo" como sujeito genérico (em vez do resultado de negócio específico) é o sinal certo, não a palavra "encerrado" isolada.
- [x] Teste pré-existente (`test_clean_model_scores_ten`) usava coincidentemente "Processo Concluído" como exemplo de nome "limpo" — corrigido para um nome descritivo de verdade, já que o fixture antigo estava validando exatamente o padrão genérico que agora corrigimos.
- [x] 3 testes novos (2 descrições naturais que antes pontuavam 0 hits agora corretamente selecionam o padrão; 2 casos de nome genérico de fim pegos). 396/396 testes passando.
- **Pendente — opção 4 discutida, não implementada:** mesmo com sinais melhor calibrados, a LLM já demonstrou repetidamente (3+ vezes nesta investigação) que pode ignorar a orientação do gabarito canônico e gerar um diagrama totalmente flat mesmo quando o padrão dispara corretamente. Prompt e scoring são reforço probabilístico, não garantia. Avaliar uma correção determinística pós-geração (reagrupar automaticamente em `callActivity` quando a densidade estoura), no mesmo espírito do `bpmn_auto_repair.py` já existente — decisão de design pendente (heurística de onde cortar as fases: por cruzamento de message flow? por lane? por região entre loops?).

### PC122 — Concluído (v5.15 / 2026-07-04) — backoff antes de retry após conteúdo vazio do provedor

**Achado do usuário:** falha "Failed after 3 attempts... conteúdo vazio (finish_reason='length')" reapareceu logo após o PC121. Antes de mudar código, investiguei se o padrão canônico novo (que injeta um JSON de exemplo grande no prompt) era a causa — descartado: o push do PC121 foi às 00:55 UTC, e as duas chamadas bem-sucedidas mais recentes na telemetria (23:43 e 00:12 UTC) são anteriores ao push; `input_tokens` ficou estável em ~20-21k em toda a sessão, sem salto após o deploy.

- **Evidência a favor de instabilidade transitória do provedor:** chamadas com tamanho de prompt idêntico tiveram sucesso poucos minutos antes da falha reportada, uma delas com só 4784 tokens de saída (bem abaixo do teto) — não é um padrão de "sempre falha com esse prompt", é intermitente.
- [x] `agents/base_agent.py::_call_with_retry` — quando o erro é especificamente conteúdo **vazio** (zero tokens, não truncamento parcial do PC118-E), aguarda 2s antes da próxima tentativa. Não se aplica a truncamento não-vazio (que já escala o orçamento, não precisa de espera) nem a erro de parsing comum (retry imediato já funciona bem para isso).
- [x] 3 testes novos: backoff dispara só para conteúdo vazio, não dispara para truncamento não-vazio nem para JSON malformado. Testes usam `call(2) in mock_sleep.call_args_list` em vez de `assert_called_once`/`assert_not_called` — outras atividades em background (telemetria assíncrona, cliente Supabase) também chamam `time.sleep` com durações não relacionadas nesse ambiente de teste, e o mock de `agents.base_agent.time.sleep` intercepta o módulo `time` inteiro, não só as chamadas do próprio código.
- [x] 393/393 testes passando (3 novos).
- **Pendente:** ainda não há confirmação definitiva se é 100% instabilidade do provedor ou se há algum gatilho reproduzível — o backoff é uma mitigação razoável para o cenário mais provável (evidenciado pela telemetria), não uma correção de causa raiz confirmada. Se o erro persistir com alta frequência mesmo com o backoff, vale considerar fallback automático para outro provedor/modelo após N falhas totais.

### PC121 — Concluído (v5.15 / 2026-07-04) — fix real: mecanismo de padrão canônico (PC111) nunca funcionou + novo padrão collab_callactivity_phases

**Contexto:** usuário trouxe uma proposta externa de "prompt rígido" (nomes, IDs e coordenadas fixas) pra forçar sempre o mesmo diagrama de 2 pools + callActivity que tinha ficado bom. Proposta rejeitada — LLM não controla coordenadas nem IDs (isso é o gerador determinístico); um prompt fixo por cenário não generaliza. Alternativa: usar o mecanismo de padrões canônicos já existente (PC111), que é exatamente pra isso.

**Achado ao investigar como adicionar o novo padrão:** nenhum dos 9 arquivos `agents/agent_bpmn/examples/bpmn_pattern_*.json` tinha o campo `trigger_signals` que `AgentBPMN._select_canonical_pattern()` usa pra decidir qual gabarito injetar (`hits = sum(1 for s in pattern.get("trigger_signals", []) ...)`— sempre `0` pra todo mundo). **O mecanismo inteiro de injeção automática de few-shot (Passo 0 do skill, "[GABARITO CANÔNICO: ...]") estava morto desde que foi implementado** — a LLM só conhecia os padrões pela tabela textual do skill (auto-seleção manual), nunca recebia o `ideal_json_output` de verdade injetado no prompt. Zero teste cobria isso.

- [x] Adicionado `trigger_signals` aos 9 arquivos de padrão existentes, usando os mesmos sinais já documentados na tabela do Passo 0 do skill (fonte de verdade já existia, só não tinha sido copiada pro JSON).
- [x] Novo padrão `bpmn_pattern_collab_callactivity_phases.json` — colaboração multi-pool (contratante + fornecedor/consultoria nomeados) com fases de negócio via `callActivity`, baseado no diagrama real que funcionou bem nesta conversa (contratação → início → execução mensal → encerramento). `ideal_json_output` no formato `pools` (2 participantes, 6 message_flows, 7 callActivity com `description` obrigatória).
- [x] `skill_bpmn.md` v10.1 — nova linha na tabela de sinais do Passo 0; corrigidos 3 IDs que estavam divergentes entre a tabela (`collab_four_eyes`, `business_rule_delegation`, `periodic_continuous`) e o `id` real do arquivo JSON (`bpmn_pattern_collab_four_eyes` etc.) — divergência que fazia a LLM registrar um ID errado em `"Padrão canônico aplicado: <id>"` na seleção manual.
- [x] 10 testes novos (`tests/test_agent_bpmn_canonical_patterns.py`) — regressão específica para o bug (todo padrão precisa ter `trigger_signals` não-vazio), matching correto por transcrição sintética para 3 padrões incluindo o novo, e `build_prompt()` realmente injetando o marcador `[GABARITO CANÔNICO: ...]`.
- [x] 390/390 testes passando (10 novos).
- **REGRA DERIVADA:** um mecanismo de seleção automática (few-shot, feature flag, roteamento) que depende de um campo específico em dados externos (aqui, JSON de exemplo) precisa de um teste que force pelo menos um caso real a *de fato selecionar* algo — sem isso, um campo nunca preenchido em nenhum arquivo passa despercebido indefinidamente, porque o código "funciona" (não lança exceção, só nunca faz o que deveria).

### PC120 — Concluído (v5.15 / 2026-07-04) — diagramas de detalhe sob demanda por callActivity

**Objetivo:** evolução do BPMN Studio — gerar, sob demanda, um diagrama BPMN detalhado para cada `callActivity` (antes opaca, só com `documentation` em texto listando subatividades). Decisão de arquitetura (validada com o usuário e uma segunda análise cruzada): geração **sob demanda** (não expansão automática de todas as fases) + diagramas **separados** por fase (bpmn-js não faz drill-down nativo de `calledElement` → outro `<process>`).

**Etapa 1 — fundação (migration + modelo):**
- [x] `setup/supabase_migration_bpmn_callactivity_diagrams.sql` — nova tabela `bpmn_callactivity_diagrams`: `bpmn_version_id` (FK → `bpmn_versions.id`, `ON DELETE CASCADE`), `element_id`/`element_name`/`pool_name`, `source_description` (documentation usada como entrada do agente, para auditoria/regeneração), `bpmn_xml`/`mermaid_code`/`bpmn_score`, `is_current` + índice único parcial em `(bpmn_version_id, element_id) WHERE is_current` — mesmo padrão de versionamento de `bpmn_versions`. **Migration executada em produção** via psycopg2 local.
- [x] `core/knowledge_hub.py::BPMNModel.detail_diagrams: dict[str, BPMNModel]` — cache em memória dos detalhamentos gerados antes de salvar; guard em `KnowledgeHub.migrate()`.

**Etapa 2 — CRUD + UI + geração:**
- [x] `core/project_store.py` — `get_current_bpmn_version_id(process_id)`, `save_bpmn_callactivity_diagram(...)` (mesmo padrão de desmarcar `is_current` anterior + inserir novo, igual a `save_bpmn_from_hub`), `list_bpmn_callactivity_diagrams(bpmn_version_id)`.
- [x] `pages/BpmnStudio.py` — seção "🔍 Detalhar uma fase (callActivity)": parseia o XML ativo (`ElementTree`, namespace-aware, mapeia `<collaboration>/<participant>` → nome do pool) para listar as `callActivity` por nome; botão gera o detalhamento reaproveitando `generate_bpmn_from_description()` com a `documentation` da callActivity como entrada (mesmo torneio de N execuções da geração principal); resultado cacheado em `hub.bpmn.detail_diagrams` e exibido num `st.expander` por fase (viewer read-only + código XML + score do torneio); "💾 Salvar detalhamento" habilitado só depois que o diagrama principal foi salvo (precisa de um `bpmn_version_id` real).
- [x] `hub.bpmn.db_process_id` agora é setado após o "💾 Salvar" principal ter sucesso — antes ficava sempre vazio no fluxo do Studio, o que teria bloqueado silenciosamente o salvamento de qualquer detalhamento.
- [x] **Bug real encontrado e corrigido durante a verificação:** o código de exibição do detalhamento tinha um `st.expander` aninhado dentro de outro (`StreamlitAPIException` — pitfall já documentado no CLAUDE.md, mas cometido de novo). Fix: `st.caption()` + `st.code()` direto, sem expander interno.
- [x] Verificado com `streamlit.testing.v1.AppTest` usando o XML real de 2 pools desta conversa (com `callActivity` de verdade): fluxo completo sem exceção — selecionar fase → gerar detalhamento (LLM mockado) → exibir sem erro → simular diagrama principal salvo → salvar detalhamento (Supabase mockado) → sucesso, com os kwargs corretos (`element_id` batendo com a callActivity escolhida).
- [x] 380/380 testes automatizados inalterados (mudança de página + `project_store.py`, sem cobertura unitária nesse nível — a verificação foi via AppTest).
- **Decisão revista sobre `calledElement`:** ao planejar a implementação, percebi que preenchê-lo de verdade exigiria um mecanismo de referência entre documentos (`bpmn:import` com URI/namespace do arquivo detalhado) — sem isso, um `calledElement` apontando para um `id` que não existe no mesmo documento é uma referência pendente, tecnicamente pior que não ter nada. Decisão: **não preencher** `calledElement` por enquanto (contrário ao que eu mesmo tinha planejado no roadmap anterior) — a ligação entre callActivity e diagrama detalhado fica só no nosso banco (`element_id` + `bpmn_version_id`), não no XML exportado. Revisitar se algum dia quisermos exportação multi-arquivo de verdade.

### PC118-E — Concluído (v5.15 / 2026-07-04) — detecção de truncamento mesmo com conteúdo não-vazio

**Achado do usuário:** "melhor de 1 execuções" (em vez de 3) e um diagrama voltando a ser pool única com sendTask/receiveTask — parecia regressão do PC118. Investigação via consulta direta a `llm_telemetry` (banco local, `psycopg2`): **26 das últimas 30 chamadas do agente `bpmn` bateram exatamente em 8192 tokens de saída** (o teto do DeepSeek), e `long_context` nunca foi `True` em nenhuma — a escalada do PC118-D nunca disparou.

**Causa raiz:** PC118-D só detecta truncamento quando o conteúdo retornado vem **vazio** (`finish_reason='length'` + `content=""`). Mas o padrão real observado é outro: a resposta vem **truncada no meio de um valor não-vazio** (ex: `{"steps": [...` cortado no meio do array) — `_parse_json()`'s fallback via `json_repair` "conserta" esse JSON cortado fechando chaves/colchetes automaticamente, produzindo um objeto sintaticamente válido mas **faltando seções inteiras** (ex: a segunda pool inteira nunca chegou a ser escrita). Isso nunca lança exceção — parece uma chamada bem-sucedida, e por isso nunca aparece como `is_error=True` na telemetria nem aciona a escalada.

- [x] `agents/base_agent.py::_call_openai` — agora verifica `finish_reason == "length"` **incondicionalmente** (não só quando o conteúdo está vazio); levanta o mesmo tipo de erro que já alimenta a escalada do PC118-D.
- [x] `agents/base_agent.py::_call_anthropic` — equivalente para Claude: `stop_reason == "max_tokens"`. Usa a mesma string `"finish_reason='length'"` na mensagem para reaproveitar a checagem existente em `_call_with_retry` sem duplicar lógica.
- [x] 5 testes novos: `_call_openai`/`_call_anthropic` reais (SDK mockado) levantam erro com conteúdo não-vazio truncado e não levantam em conclusão normal; integração confirmando que a nova mensagem de erro aciona a mesma escalada do PC118-D.
- [x] 380/380 testes passando (5 novos)
- **REGRA DERIVADA:** ao adicionar uma proteção contra "resposta vazia", verificar também o caso "resposta não-vazia mas incompleta" — para saída estruturada (JSON), truncamento é truncamento independente de o conteúdo parecer não-vazio; `finish_reason`/`stop_reason` é o sinal confiável, não a checagem de vazio-ou-não. Telemetria com contagem de tokens de saída (`output_tokens`) é o instrumento certo para detectar esse padrão — um valor repetidamente igual ao teto configurado é o sintoma, mesmo sem nenhum erro registrado.

### PC119-B — Concluído (v5.15 / 2026-07-04) — fix real: botão "Descartar" do BpmnEditor.py

**Confirmação do achado colateral do PC119:** o botão "🗑️ Descartar" (`pages/BpmnEditor.py`, então linhas 328-332) tinha exatamente a mesma forma de bug corrigida no BPMN Studio — `st.session_state["bpme_paste_xml"] = ""` executado **depois** do `st.text_area(key="bpme_paste_xml", ...)` já instanciado no mesmo rerun (linha 242), o que o Streamlit proíbe (`StreamlitAPIException`).

- [x] Fix: reaproveita a flag `_bpme_reset_fields` que **já existe** no arquivo (lido no topo do script, linhas 54-55, criado originalmente só para o fluxo de "Salvar") — o botão Descartar agora seta essa mesma flag em vez de escrever direto na chave do widget.
- [x] Efeito colateral (desejável): descartar agora também limpa o campo de notas (`bpme_notes`), já que a flag reaproveitada limpa os dois campos — antes só a versão de Salvar fazia isso.
- [x] Verificado com `streamlit.testing.v1.AppTest`: mockando `bpmn_tables_exist`/`list_bpmn_processes`/`list_bpmn_versions` (sem Supabase real), reproduzido o fluxo completo — colar XML editado → clicar Descartar → sem exceção, `_bpme_captured_xml` removido, campo de texto limpo. Antes do fix, esse mesmo teste reproduzia o `StreamlitAPIException` (confirmado indiretamente pela reprodução idêntica no BPMN Studio, mesma forma de código).
- [x] 375/375 testes automatizados inalterados (mudança restrita a uma página Streamlit, sem cobertura de teste unitário nesse nível).

### PC119 — Concluído (v5.15 / 2026-07-04) — BPMN Studio: diagrama editável na aba Gerar

**Pedido do usuário:** poder editar a apresentação do diagrama enquanto o BPMN Studio processa a descrição — útil para corrigir manualmente os problemas encontrados nesta mesma sessão (gateway ausente, message flow faltando, título duplicado) sem precisar regenerar do zero.

- [x] `pages/BpmnStudio.py`, aba "🧩 Gerar" → "📐 Diagrama BPMN": troca o `bpmn_viewer.preview_from_xml()` (somente leitura) pelo `bpmn_editor.editor_from_xml()` (bpmn-js Modeler completo, mesmo componente já usado em `pages/BpmnEditor.py`) — paleta de edição, arrastar elementos, redesenhar conexões.
- [x] **Ponte JS→Python**: reaproveita o único mecanismo existente no projeto para isso — sem `postMessage`/bridge real, o usuário clica "Exportar XML" dentro do editor, copia o texto e cola num `st.text_area` (`bpmns_paste_xml`) fora do iframe; o Python lê esse valor **antes** de renderizar o editor no próximo rerun e usa como XML ativo (`_bpmns_edited_xml` sobrepõe `hub.bpmn.bpmn_xml` só para exibição/salvamento — o hub original do agente nunca é sobrescrito, permitindo descartar a edição).
- [x] Botão "↩️ Descartar edição" volta à versão gerada pelo agente; **Salvar** grava a versão editada (se houver) em vez da original; accordion "Código BPMN (XML)" e caption explicam que o Mermaid da aba ao lado não é recalculado a partir de edições manuais no BPMN (limitação conhecida — Mermaid vem do modelo de steps, não do XML).
- [x] **Bug real encontrado e corrigido durante a verificação** (não no código do usuário, no meu próprio código novo): o clique em "Descartar edição" tentava `st.session_state["bpmns_paste_xml"] = ""` **depois** do widget já ter sido instanciado no mesmo rerun — Streamlit proíbe isso (`StreamlitAPIException`). Fix: flag `_bpmns_reset_paste` lida e aplicada **antes** da criação do widget, no topo do script, seguindo o padrão já usado em `pages/BpmnEditor.py` linhas 54-55.
- [x] **Achado colateral, não corrigido (fora do escopo desta tarefa):** `pages/BpmnEditor.py` linhas 328-332 (botão "🗑️ Descartar") tem a mesma forma de código (`st.session_state[key] = ""` depois do `st.text_area(key=...)` já instanciado no mesmo rerun, linha 242) — muito provavelmente o mesmo bug já existe em produção nessa página. Vale verificar/corrigir separadamente.
- **Verificação:** sem Playwright/chromium-cli disponíveis neste ambiente, a verificação foi feita com `streamlit.testing.v1.AppTest` (execução real do script da página, sem browser) — sessão simulada (login + projeto ativo via injeção direta de `session_state`, sem credenciais reais) exercitando o fluxo completo: geração simulada → renderização do editor sem exceção → colar XML editado → rerun → confirma caption "editado manualmente" e `_bpmns_edited_xml` capturado → clicar "Descartar" → confirma limpo sem exceção. 375/375 testes automatizados (pytest) inalterados, sem regressão.
- **REGRA DERIVADA:** ao adicionar um botão que limpa um widget `key=X` via `st.session_state[X] = valor`, verificar se esse código roda **antes** de `st.text_area/st.text_input(..., key=X)` no mesmo script — se vier depois (comum quando o botão fica visualmente ao lado/abaixo do campo), Streamlit lança `StreamlitAPIException` em tempo de execução; o padrão seguro é uma flag lida e aplicada no topo do script, antes de qualquer instanciação de widget, seguida de `st.rerun()` no clique do botão.

### PC118-D — Concluído (v5.15 / 2026-07-04) — retry escala para o orçamento de long-context após truncamento

**Achado do usuário:** após PC118-C, uma nova geração no BPMN Studio falhou com `[bpmn] Failed after 3 attempts. Last error: ValueError("... LLM retornou conteúdo vazio (finish_reason='length' ...)")`. Causa raiz: `AgentBPMN._min_output_tokens=8192` é igual ao `max_tokens` padrão do DeepSeek (também 8192) — não oferece nenhuma margem real. A descrição complexa de 2 pools usada em toda essa investigação gera um JSON denso o bastante (título+descrição+ator+lane por step, ~20+ steps, edges, message_flows) para estourar 8192 tokens de saída, e as 3 tentativas de `_call_with_retry()` repetiam exatamente o mesmo truncamento porque o hint de retry ("retorne apenas JSON válido") não ataca um problema de orçamento de tokens.

- [x] `agents/base_agent.py` — `_call_with_retry()` agora detecta `"finish_reason='length'"` na mensagem da exceção e seta `self._force_long_context = True` antes da próxima tentativa; `_call_llm()` passou a considerar essa flag em paralelo à heurística de tamanho de entrada (`use_long_ctx = should_use_long_context(...) or getattr(self, "_force_long_context", False)`).
- [x] **Por que é seguro por provedor:** a escalada usa o `long_context_max_tokens` já configurado por provedor em `modules/config.py` — DeepSeek/DeepSeek Pro/Thinking e Grok têm 32768 (ganho real); provedores sem essa chave (Claude, OpenAI, Groq, Gemini) caem no fallback `max(max_tokens, 8192)` — sem mudança nenhuma, sem risco de estourar o teto real da API desses provedores.
- [x] 3 testes novos em `tests/test_base_agent.py` (novo arquivo): escalada dispara só após truncamento (não após erro de parsing comum), 2ª tentativa usa `long_context=True`, falha após esgotar tentativas ainda é reportada corretamente.
- [x] 375/375 testes passando (3 novos)
- **REGRA DERIVADA:** um `_min_output_tokens` fixo por agente só protege se for **maior** que o `max_tokens` padrão do provedor mais usado — igual ao padrão não oferece margem nenhuma. Quando o teto de saída pode variar por provedor (e elevá-lo incondicionalmente arrisca estourar o limite real de provedores mais restritos), reagir ao sintoma real (`finish_reason='length'`) e escalar só para provedores que já têm um orçamento maior configurado é mais seguro do que subir o piso global.

### PC118-C — Concluído (v5.15 / 2026-07-04) — penalidade de densidade proporcional + detecção de responsabilidade duplicada entre pools

**Contexto:** terceira rodada de verificação do BPMN Studio para a mesma descrição complexa. Com os checks 9–13 (PC118/PC118-B) em produção, o torneio produziu um candidato no sentido oposto do problema original: abandonou completamente o `callActivity` e "explodiu" as 2 pools em 22 e 14 nós no nível 1 (Contratante 4150px de largura), duplicando responsabilidades entre organizações ("Definir Escopo Detalhado" e "Planejar Cronograma de Entregas" apareciam em ambas as pools, quando a descrição atribui cada atividade a um único lado). Investigação com números (não só leitura visual): o candidato explodido pontuava `weighted=6.58`, quase empatado com o candidato compacto-mas-incompleto da rodada anterior (`weighted=6.6`) — o Check 10 (densidade) penalizava um pool 2 nós acima do limite e um pool 12 nós acima do limite quase da mesma forma (-2.5 fixo por erro), então o torneio podia escolher o exagero por puro ruído de amostragem.

- [x] **Check 10 revisado** (`modules/bpmn_structural_validator.py`) — penalidade agora escala com a magnitude do excesso: 1 issue "error" a cada bloco cheio de 5 nós acima do limite de 10, mais 1 "warning" para o resto — em vez de um único error/warning binário. Um pool 12 nós acima do limite agora custa ~2x mais que um 3 nós acima.
- [x] **Check 14 novo** (`_check_duplicate_task_titles_across_pools`) — título de step (não-evento, não-gateway) idêntico, case-insensitive, em 2+ pools distintos → warning (nunca erro — replicação legítima existe, ex: "Assinar Contrato" nas duas pontas). Exclui eventos/gateways do comparativo para não gerar ruído com nomes genéricos coincidentes.
- [x] Verificado com reconstrução exata dos 2 XMLs desta investigação: candidato explodido caiu de `weighted=6.58` para `5.78`; candidato compacto (com os defeitos do PC118-B) permanece em `6.6` — margem real de 0.82 pontos a favor do compacto, resolvendo o empate técnico anterior.
- [x] 7 testes novos (`test_penalty_scales_with_excess_magnitude`, `test_twelve_over_yields_two_error_blocks`, `TestDuplicateTaskTitleAcrossPools` × 5); 372/372 testes passando.
- **REGRA DERIVADA:** ao adicionar uma penalidade de "não fazer X" a um validador de torneio, verificar também o extremo oposto ("fazer X demais") — um scorer que só sabe punir a ausência de uma prática pode, sem querer, deixar o excesso da mesma prática competitivo por empate técnico com o defeito que ele deveria corrigir.

### PC118-B — Concluído (v5.15 / 2026-07-04) — 2 checks estruturais adicionais: split implícito e cobertura de message flow

**Contexto:** com PC118 (checks 9–11) e o fix do cache do torneio já em produção, o usuário gerou um novo diagrama no BPMN Studio para a mesma descrição complexa — desta vez com 2 pools genuínas, densidade correta por pool (6 e 7 nós) e nenhum beco sem saída, confirmando que os fixes anteriores funcionaram. Uma segunda análise cruzada (revisão externa do diagrama + conferência contra `skill_bpmn.md`) revelou 2 lacunas novas, ainda sem cobertura: (1) `p1_S04` (sendTask "Enviar Escopo Definido") não tinha nenhum `message_flow` associado — só existia 1 message_flow no XML inteiro; e (2) `p2_S02` (callActivity) bifurcava em 2 arestas sem gateway, que reconvergiam num `parallelGateway` de join explícito — um split implícito sem simetria com o join, o espelho do Check 5 (split sem join) já existente.

- [x] `modules/bpmn_structural_validator.py` — 2 novos checks determinísticos:
  - **Check 12:** nó não-gateway com ≥2 arestas de saída cujos ramos reconvergem (via BFS de alcançabilidade) num `parallelGateway`/`inclusiveGateway` com múltiplas entradas → erro, citando a Regra de Sincronização Split↔Join (Passo 4). Não dispara em fan-out que reconverge em nós comuns (padrão XOR implícito, explicitamente permitido pelo skill) nem quando o próprio nó de fan-out já é um gateway (já coberto pelo Check 5).
  - **Check 13 (`_check_message_flow_coverage`):** em colaboração com ≥2 pools, todo `sendTask`/`receiveTask` precisa aparecer em algum `message_flow` como source/target — senão, erro citando o checklist do Passo 6. Só roda com 2+ pools (colaboração de 1 pool já é tratada pelo Check 11 do PC118).
- [x] Verificado com reconstrução exata do XML relatado pelo usuário: os 2 checks disparam corretamente (`p2_S02` fan-out sem gateway + `p1_S04`/`p2_S04` sem message_flow), derrubando `structural` de 10.0 para 2.5.
- [x] 7 testes novos (`TestImplicitSplit` × 3, `TestMessageFlowCoverage` × 4) + `message_flow()` factory helper adicionado a `tests/conftest.py`; 1 teste do PC118 (`test_two_pools_with_send_receive_task_not_flagged`) ajustado para incluir um message_flow real, já que agora é coberto pelo Check 13.
- [x] 365/365 testes passando (7 novos)

### PC118 — Concluído (v5.15 / 2026-07-04) — AgentValidator ganha 3 checks estruturais que faltavam para o torneio pegar violações "nunca" do skill_bpmn.md

**Achado do usuário:** mesmo após PC116-D (torneio + AgentValidator no BPMN Studio), um novo XML gerado ainda apresentava exatamente os defeitos que o torneio deveria evitar — pool única simulando uma segunda organização via sendTask/receiveTask, um nível 1 com ~20 nós (limite do método é 10), e (achado numa segunda análise cruzada com uma revisão externa do diagrama) um nó terminal ("Reabrir Concorrência") sem nenhuma aresta de saída, um beco sem saída silencioso. Investigação confirmou: as 5 dimensões de `AgentValidator.score()` (granularidade, tipo de tarefa, gateways, estrutural, semântica) não tinham NENHUM check para essas 3 violações — `_score_granularity` só compara contagem de tarefas × tamanho do texto (cego a hierarquia), e `bpmn_structural_validator.py` só verifica balanceamento de message flow quando `message_flows_data` não está vazio (com 1 pool só, nunca há message flow, então o check nunca dispara). Conclusão: o torneio protege contra ruído aleatório entre execuções, mas não contra um viés sistemático que as N execuções compartilham — porque o scorer não consegue distinguir um candidato conforme de um não-conforme nessas 3 dimensões.

- [x] `modules/bpmn_structural_validator.py` — 3 novos checks determinísticos, puro Python, sem LLM:
  - **Check 9 (dead-end):** um sink (0 arestas de saída) só é sinalizado como erro se o modelo já declara um evento de fim explícito em outro lugar — evita falso positivo no padrão comum onde o passo terminal não tem tipo explícito e o gerador injeta um "Fim" sintético depois dele.
  - **Check 10 (densidade):** nível 1 com mais de 10 nós (Bruce Silver) → warning (11–15) ou error (16+), citando a Regra de Densidade Cognitiva do Passo 0.1.
  - **Check 11 (`_check_single_pool_choreography`):** collaboration com exatamente 1 participant que ainda usa sendTask/receiveTask → error por step — pega exatamente o defeito "pool única fingindo colaboração" que a Regra 3 do skill proíbe.
- [x] `agents/agent_validator.py::_score_semantic` — penalidade de gateway-com-verbo-de-atividade subiu de -2.5 para -4.0 por ocorrência; uma única violação sobrevivia ao torneio com pontuação "boa o suficiente" nas outras dimensões — essa é uma regra "nunca" do skill e deveria dominar a dimensão semântica quase sozinha.
- [x] Verificado com reconstrução exata do XML relatado pelo usuário (script standalone, não fixture de teste): as 3 novas checks disparam corretamente (9 issues estruturais, incluindo os 6 sendTask/receiveTask + o dead-end + a densidade), derrubando `structural` de um score "aceitável" para 0.0 e o `weighted` final para 4.44 — esse candidato agora perde decisivamente contra qualquer alternativa do torneio que evite ao menos parte dos defeitos.
- [x] 22 testes novos em `tests/test_bpmn_structural_validator.py` (3 classes: `TestDeadEndNode`, `TestDensityLimit`, `TestSinglePoolChoreography`) — nenhuma fixture existente usa sendTask/receiveTask, >10 nós, ou declara evento de fim explícito, então as 3 checks novas têm zero risco de falso positivo nos testes anteriores.
- [x] 354/354 testes passando (22 novos + todos os anteriores, incluindo o ajuste de `test_multiple_gateway_verbs_cumulate` para o novo valor de penalidade)

### PC116-D — Concluído (v5.15 / 2026-07-04) — BPMN Studio ganha o mesmo torneio + AgentValidator do pipeline principal

**Achado do usuário:** ao inspecionar o XML gerado para a descrição complexa do guia, duas organizações citadas nominalmente ("Contratante" e "TechAdvisor Ltda") viraram só uma pool — a interação com a segunda foi representada via sendTask/receiveTask dentro do mesmo pool, sem o segundo participante que `skill_bpmn.md` (Regra 3 — Especificidade de Co-Participantes) exige para terceiros nomeados. Um sub-ciclo detalhado no texto (validar relatório → corrigir se incompleto → aprovar → pagar) foi colapsado num único `callActivity` opaco. A pergunta do usuário — "estamos usando o mesmo rigor... as mesmas ferramentas?" — expôs que a resposta era não: PC116-B (`max_attempts`) só reiniciava a mesma chamada única do zero em caso de EXCEÇÃO; não havia comparação de qualidade entre execuções alternativas, então uma extração "válida mas estruturalmente pobre" (sem lançar exceção) passava direto, sem chance de ser substituída por uma melhor.

- [x] `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` — substitui o retry simples pelo MESMO mecanismo de `core/pipeline.py` quando `n_bpmn_runs > 1` (o caminho padrão do pipeline, já que `n_bpmn_runs=3` por default): roda `n_runs` execuções independentes do `AgentBPMN`, pontua cada uma com `AgentValidator` (granularidade, tipo de tarefa, gateways, estrutural, semântica) e retorna a de maior `.weighted`. Uma execução que lança exceção é descartada do torneio sem abortar as demais.
- [x] `pages/BpmnStudio.py` — lê `st.session_state.n_bpmn_runs`/`bpmn_weights` (mesmas chaves do pipeline principal, não uma config paralela) e exibe o score da versão vencedora após gerar.
- [x] Verificado com dois cenários mockados: torneio de 3 execuções com qualidades propositalmente diferentes confirma que a de maior `.weighted` é sempre a retornada (não a primeira, não a última — a de maior score); tolerância a falha parcial (1 de 3 execuções lança exceção) confirma que o torneio completa normalmente com as 2 restantes em vez de abortar.
- [x] 345/345 testes passando

### PC116-C — Concluído (v5.15 / 2026-07-03) — BPMN Viewer: zoom com roda do mouse + arrasto + fix do botão "Janela"

**Pedido do usuário:** a área do diagrama BPMN deveria ter as mesmas funcionalidades de mouse que o diagrama Mermaid já tem (zoom com a roda, arrasto com clique+arraste), e o botão "↗ Janela" abria uma nova aba onde os botões da toolbar não respondiam.

- [x] `modules/bpmn_viewer.py` — zoom com roda do mouse (`wheel` listener em `#bpmn-container`, `canvas.zoom(scale, {x,y})` centrado no cursor) e arrasto com clique (`mousedown`/`mousemove`/`mouseup`, `canvas.scroll()`) — mesmo modelo de interação do `mermaid_renderer.py`. Aplicado nos dois templates (`_TEMPLATE` e `_TEMPLATE_CDN_FALLBACK`).
- [x] Fix do botão "Janela": a causa provável era capturar `document.documentElement.outerHTML` **depois** do bpmn-js já ter renderizado o SVG no container — a nova aba reexecuta o script e chama `importXML()` de novo sobre um container que já contém elementos/marcadores SVG com os mesmos ids (colisão). Corrigido capturando um snapshot do documento **antes** de qualquer renderização (`_pristineHtml`, no topo do script) e usando esse snapshot no popup.
- [x] Verificado por inspeção de código + renderização funcional dos dois templates via `.format()` (sem erros de chave/placeholder); sem browser automatizado disponível neste ambiente para clique real — pendente de confirmação do usuário em produção.
- [x] 345/345 testes passando

### PC116-B — Concluído (v5.15 / 2026-07-03) — resiliência da geração no BPMN Studio (retry de tentativa completa)

**Achado em uso real:** primeiro teste com a descrição de processo complexa do guia (`Orientacoes_BpmnStudio.py`, 2 organizações + paralelismo + 2 decisões com loop-back) falhou: `[bpmn] Failed after 3 attempts. Last error: ValueError("Incomplete BPMN: pool 'Contratante' has 20 steps but 0 edges — sequence flows missing.")`. Causa: o pipeline normal tem duas redes de segurança que o BPMN Studio v1 ("modo simples", por decisão deliberada do plano original) não tem — torneio `n_bpmn_runs=3` + LangGraph adaptativo (até 5 tentativas). O Studio dependia só do retry interno do `AgentBPMN` (3 tentativas), que reforça a MESMA correção sobre a MESMA extração — se o modelo fica preso num padrão de falha, as 3 tentativas falham identicamente (exatamente o que aconteceu).

- [x] `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` — novo parâmetro `max_attempts=2`: reinicia a chamada inteira ao `AgentBPMN` do zero (pedido "limpo", sem o histórico da correção que não funcionou) em vez de só confiar no retry interno. Cada tentativa opera sobre `copy.copy(hub)` — isola estado parcial de tentativas malsucedidas.
- [x] Verificado com dois cenários mockados na fronteira de rede: (1) 1ª tentativa completa falha 3/3 identicamente (reproduz o bug relatado), 2ª tentativa sucede — `hub.bpmn.ready=True`; (2) todas as tentativas falham — levanta a exceção da última tentativa normalmente, sem mascarar erro real.
- [x] 345/345 testes passando

### PC116 — Concluído (v5.15 / 2026-07-03) — BPMN Studio

Plano em `melhorias/bpmn-studio.md` implementado: nova página `pages/BpmnStudio.py` (grupo Pipeline) com dois modos —

- **Gerar** (descrição → BPMN + Mermaid): `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` monta um `KnowledgeHub` sintético (`transcript_clean = descrição`), roda `NLPChunker` opcionalmente e reaproveita `AgentBPMN` sem alteração — não é um agente novo, é um wrapper fino. Salva via `save_bpmn_from_hub()` com vínculo a reunião opcional (selectbox) ou como processo autônomo.
- **Descrever** (BPMN → descrição textual): lógica de `AssistantToolExecutor.describe_bpmn_process()` extraída para `modules/bpmn_describer.py::describe_bpmn_from_xml()` — pura, sem acesso a banco, funciona com qualquer XML colado ou salvo. `describe_bpmn_process()` passou a delegar para essa função (refatoração verificada byte-a-byte idêntica ao comportamento anterior).

**Migração de schema necessária e aplicada:** `bpmn_versions.meeting_id` era `NOT NULL`, impossibilitando salvar uma versão sem reunião vinculada — bloqueador real identificado no plano. `setup/supabase_migration_bpmn_studio.sql` (`ALTER TABLE ... DROP NOT NULL`) executada em produção. `save_bpmn_from_hub()` e `_find_or_create_bpmn_process()` aceitam `meeting_id=None`; guard adicionado para não sobrescrever `last_meeting_id` com `None` ao salvar uma versão sem reunião.

- [x] `core/agent_registry.py` — entrada `bpmn_studio` on-demand (`pipeline_step: None`, `authority_level: "draft"`, reaproveita `skills/skill_bpmn.md`)
- [x] `app.py` — página registrada no grupo Pipeline
- [x] Verificação ponta-a-ponta com chamada LLM mockada na fronteira de rede (sem chave de API real disponível fora da sessão Streamlit ao vivo): hub sintético → NLPChunker → AgentBPMN → XML/Mermaid válidos → encadeado com sucesso em `describe_bpmn_from_xml()`
- [x] 345/345 testes passando

### PC117 — Concluído (v5.14 / 2026-07-03) — fix diagrama BPMN volta ao anterior após reprocessar + salvar (Modo B)

**Diagnóstico:** No Modo B (Reunião Existente), o botão "Salvar" chamava `save_bpmn_from_hub()` sem `bpmn_process_id`, caindo sempre na resolução por `slug(hub.bpmn.name)`. Reprocessar o agente BPMN pode mudar o nome inferido do processo o suficiente para o slug não bater mais com o processo já vinculado à reunião — criando um `bpmn_processes` órfão e uma segunda linha `is_current=True` para a mesma reunião. `load_meeting_as_hub()` fazia `.limit(1)` sem `ORDER BY`, então qual das duas linhas "current" voltava ao recarregar era não-determinístico. Diagnóstico em produção: **14 de 32 reuniões com `bpmn_versions` duplicadas em `is_current=True`** (uma com 4 linhas).

- [x] **`core/knowledge_hub.py`** — `BPMNModel.db_process_id` (novo campo) + guard em `migrate()`
- [x] **`core/project_store.py`** — `load_meeting_as_hub()` popula `db_process_id`; query de BPMN ganha `ORDER BY created_at DESC` antes do `LIMIT 1` (hardening — neutraliza o sintoma mesmo para as 14 reuniões já afetadas, sem migração de dados)
- [x] **`pages/Pipeline.py`** — Modo B passa `bpmn_process_id=hub.bpmn.db_process_id` explicitamente ao salvar, eliminando a resolução por slug para reuniões com processo já conhecido
- [x] 345/345 testes passando

### PC116 — Plano (não implementado, 2026-07-02) — BPMN Studio

Plano de melhoria em `melhorias/bpmn-studio.md`: gerar BPMN 2.0 + Mermaid a partir de descrição de processo em texto livre (fora do fluxo de reunião), com opção de salvar versionado e vincular a uma reunião existente; caminho inverso (BPMN → descrição textual). Levantamento técnico já identifica reaproveitamento de `AgentBPMN` via hub sintético e um bloqueador real de schema (`bpmn_versions.meeting_id` `NOT NULL` — impede salvar sem reunião vinculada).

### PC115 — Concluído (v5.14 / 2026-07-02) — split de core/assistant_tools.py em 7 módulos por domínio

`core/assistant_tools.py` (13.827 linhas) dividido: `AssistantToolExecutor` passa a herdar de 7 mixins em `core/tools/` (tools_meetings_requirements, tools_bpmn_sbvr, tools_meeting_ops_calendar, tools_admin_charts_entities, tools_documents_ibis_diagrams, tools_knowledge_requirements2, tools_executive_advanced), cada um com seus métodos + schemas OpenAI (`*_SCHEMAS`) correspondentes. Arquivo principal caiu para ~830 linhas (só `__init__`, `execute()` dispatch, e getters de schema/catálogo). Split feito por script (AST-driven), não manual. Efeito colateral: removidos 2 métodos mortos (`rename_meeting`/`batch_rename_meetings` definidos duas vezes na mesma classe — a segunda definição sempre sobrescrevia a primeira silenciosamente).

- [x] Reorganização de pastas da raiz (`notes/`, `test-scenarios/`) + limpeza de `.pyc` versionados e worktree órfão
- [x] Exportação HTML da conversa do Assistente passa a incluir diagramas BPMN/Mermaid e demais widgets A2UI (antes só texto + gráficos Plotly)
- [x] Generalização de material comercial (`static/apresentacao-geral.html`, `outputs/apresentacao_executiva_p2d.html` — ex-FGV) para uso com qualquer cliente

### PC113–PC114 — Concluído (v5.13 / 2026-06-30 a 2026-07-01) — Infraestrutura Google Cloud + Governança v5.11

PC113: `Dockerfile` multi-stage (builder + runtime, Python 3.13-slim, spaCy lg baked, non-root), `.dockerignore`, `infra/cloudrun/service.yaml` (Cloud Run declarativo, Secret Manager, probes), `infra/cloudrun/env.template.yaml`, `infra/cloudbuild.yaml` (CI/CD: build → push Artifact Registry → deploy Cloud Run).

PC114: API Google Cloud completa — Secret Manager 4 camadas, Cloud Tasks com fallback síncrono, endpoints `/api/v1/projects` + `/api/v1/process` + `/internal/run`, `Dockerfile` usando `requirements.api.txt`, 345 testes passando.

Governança v5.11: `COLLABORATIVE_MANIFESTO.md` assinado por 5 agentes (30/06/2026) — n8n formalizado como Agente 4, modelo de negócio definido (Starter/Pro/Enterprise), hierarquia LLM com custos reais BRL.

---

### PC112-K — Concluído (v5.12 / 2026-06-30) — fix setIn ao carregar reunião: mermaid bloqueante

**Diagnóstico:** `render_mermaid_block()` fazia 2 chamadas HTTP sequenciais para `mermaid.ink`
(timeout 15s cada = até 30s de bloqueio no thread do script). Na primeira renderização do hub após
carregar reunião do banco, o WebSocket ficava ocioso durante o bloqueio. Se a conexão caía e o
cliente reconectava com árvore vazia, o servidor continuava enviando deltas a partir do índice 2+
→ `Bad 'setIn' index 2 (should be between [0, 0])`.

**Correções:**
- [x] **`modules/mermaid_renderer.py`**:
  - Timeout reduzido de 15s → 5s por fetch (fail-fast)
  - Fetches paralelos via `ThreadPoolExecutor(max_workers=2)` — bloqueio máximo 5s (era 30s)
  - Cache em `st.session_state` por hash MD5 do mermaid_text — reruns seguintes: 0ms
- [x] **`modules/bpmn_viewer.py`**:
  - `_load_bpmn_assets()`: lê `static/bpmn-viewer.production.min.js` se presente → elimina
    fetch de 500KB do internet na primeira renderização (era ~8s)
  - CSS ainda fetched do CDN em paralelo (3 arquivos pequenos, rápido)

---

### PC88 — Concluído (v4.79 / 2026-06-28) — PC83+PC84 compliance nos agentes pipeline restantes

- [x] **`core/output_schemas.py`** — 4 novos schemas Pydantic v2 (fail-open, extra='allow'):
  - `ArgumentationOutputSchema` (+ `IBISQuestionSchema`, `IBISAlternativeSchema`, `IBISResolutionSchema`)
  - `CommunicationNoiseOutputSchema` (+ `AmbiguityItemSchema`, `CommunicationGapSchema`)
  - `KnowledgeExtractorOutputSchema` (+ `KHEntitySchema`, `KHProcessSchema`, `KHFactSchema`, `KHContradictionSchema`)
  - `QuerySummaryOutputSchema` (+ `PerspectiveSummarySchema`)

- [x] **`agents/agent_argumentation.py`** — `required_hub_fields = ["transcript_clean"]` + `output_schema = ArgumentationOutputSchema`
- [x] **`agents/agent_communication_noise.py`** — `required_hub_fields = ["transcript_clean"]` + `output_schema = CommunicationNoiseOutputSchema`
- [x] **`agents/agent_knowledge_extractor.py`** — `required_hub_fields = ["transcript_clean"]` + `output_schema = KnowledgeExtractorOutputSchema`
- [x] **`agents/agent_query_summarizer.py`** — `required_hub_fields = []` + `output_schema = QuerySummaryOutputSchema`
- [x] **`agents/agent_ckf_updater.py`** — `required_hub_fields = []` (Markdown output — sem output_schema)

Agentes isentos (padrão não-padrão):
- `agent_bpmn_reviewer` — Markdown output, on-demand, `_MinimalHub` stub
- `agent_contradiction_detector` / `agent_entity_consolidator` — entry points próprios, hub stubs internos
- `agent_meeting_namer` / `agent_req_reconciler` — `skill_path = None`, prompts inline

**Resultado:** 56/56 testes existentes passando; 4 novos schemas + 5 agentes com compliance completa.

---

### PC102 — Concluído (v4.78 / 2026-06-28) — skill improvements batch 4: query_summarizer, ner, analyst, context_template

- [x] **`skills/skill_query_summarizer.md`** v1.0 → v1.1: move `{output_language}` to Rules section; add perspective differentiation guide table
- [x] **`skills/skill_ner.md`** v1.0 → v1.1: add difficult cases guide (pronouns, company names, ASR distortion, name deduplication)
- [x] **`skills/skill_analyst.md`** v1.0 → v1.1: add tool call efficiency rule, quality criteria section (evidence/facts/specificity)
- [x] **`skills/skill_context_template.md`**: add YAML frontmatter v1.0 (user-editable template — content unchanged)

---

### PC101 — Concluído (v4.77 / 2026-06-28) — skill improvements batch 3: document_extractor, cross_doc_analyzer

- [x] **`skills/skill_document_extractor.md`** v1.0 → v1.1: add 5-pass extraction method; harmonize `req_type`/`priority` to PT pipeline schema (Funcional/Não-Funcional/Negócio/Restrição/Qualidade and Alta/Média/Baixa); add `{output_language}` in Rules with 7 formal rules
- [x] **`skills/skill_cross_doc_analyzer.md`** v1.0 → v1.1: add Rules section with `{output_language}` and 5 formal rules; clarify `gaps` key requirements

---

### PC100 — Concluído (v4.76 / 2026-06-28) — skill improvements batch 2: knowledge_extractor, contradiction_detector, communication_noise, document_analyzer

- [x] **`skills/skill_knowledge_extractor.md`** v1.0 → v1.1: add calibration table (include vs omit per entity/fact type); Regras section with `{output_language}`
- [x] **`skills/skill_contradiction_detector.md`** v1.0 → v1.1: add Regras section with `{output_language}` + 7 formal rules
- [x] **`skills/skill_communication_noise.md`** v1.0 → v1.1: add per-type examples table for ambiguities and gaps
- [x] **`skills/skill_document_analyzer.md`** v1.0 → v1.1: add 6-step analysis method (inventory → req mapping → process alignment → stakeholders → decisions → synthesis)

---

### PC99 — Concluído (v4.75 / 2026-06-28) — skill improvements batch 1: transcript_quality, argumentation, ckf_updater, entity_consolidator

- [x] **`skills/skill_transcript_quality.md`** v1.0 → v2.0: add `overall_score`, `grade`, `artifact_ratio`, `metadata_issues` to JSON schema; add Weighted Score Formula section; add `{output_language}` in Rules
- [x] **`skills/skill_argumentation.md`** v1.0 → v2.0: fix all missing Portuguese accents throughout; add signal recognition table, meeting type calibration table, `## Regras` section with `{output_language}`; add `confidence` field to each question
- [x] **`skills/skill_ckf_updater.md`** v1.0 → v2.0: full rewrite — section-by-section guidance for all 7 CKF sections, conflict handling table (5 scenarios), update conventions, 5-item checklist
- [x] **`skills/skill_entity_consolidator.md`** v1.0 → v2.0: full rewrite — similarity scoring table, 0.80 fusion threshold, edge case guide, examples table, `confidence` field in output

---

### PC98 — Concluído (v4.74 / 2026-06-28) — skill_sbvr.md v2.1 — SBVR vs DMN, enforcement, Exemplo C

- [x] **`skills/skill_sbvr.md`** — v2.0 (518 linhas) → v2.1 (662 linhas), edições cirúrgicas
  - Fronteira SBVR vs DMN: tabela detalhada com 5 padrões e regra prática ("3+ variações → avalie DMN")
  - Campo `enforcement` (opcional): automated / manual / contractual / regulatory com orientação de preenchimento
  - Campo `bmm_policy_ref` documentado: quando e como usar para rastreabilidade SBVR↔BMM
  - Seção `## Regras` adicionada; `{output_language}` solto removido do final
  - JSON schema atualizado com `enforcement` como campo opcional
  - Checklist expandido com 3 novos itens (DMN boundary, enforcement, bmm_policy_ref)
  - Exemplo C: kickoff técnico com regras regulatórias (BACEN 4.557, LGPD, KMS, DPO) demonstrando enforcement regulatory/automated/manual e a decisão de NÃO extrair a regra de score como SBVR (→ DMN)

---

### PC97 — Concluído (v4.73 / 2026-06-28) — skill_bmm.md v2.1 — Cadeia BMM, modal, deadline, Exemplo C

- [x] **`skills/skill_bmm.md`** — v2.0 (446 linhas) → v2.1 (586 linhas), edições cirúrgicas
  - Seção "Cadeia de Rastreabilidade BMM" explicando por que `supports` é obrigatório (diagrama Fins←Meios)
  - Campo opcional `deadline` para metas com prazo explícito na transcrição
  - Campo `modal` obrigatório em políticas: `must` / `must_not` / `may` com tabela de exemplos
  - Seção `## Regras` adicionada com output_language e regras de conservadorismo
  - `{output_language}` removido do final solto — integrado à seção Regras
  - JSON schema atualizado com `deadline` em goals e `modal` em policies
  - Exemplo C — kickoff estratégico (Meridional-style): visão explícita, 4 metas mistas, 3 políticas com modals distintos, 1 influenciador weakness quantificado; com notas explicando cada decisão de classificação

---

### PC96 — Concluído (v4.72 / 2026-06-27) — SKILL_SYNTHESIZER.md v3.0 — Narrativa Executiva Calibrada

- [x] **`skills/SKILL_SYNTHESIZER.md`** — reescrito de v2.0 (77 linhas) para v3.0 (208 linhas)
  - Persona expandida com audiência explícita (diretores/gestores não-presentes)
  - Tabela de inputs com coluna "quando presente, priorize" (antes: coluna "obrigatória")
  - Método de síntese em 4 passos: inventário, temas transversais, calibração por riqueza, ordem de redação
  - Calibração por riqueza: tabela com 5 cenários (BPMN isolado → todos os 6 inputs)
  - Checklist pré-retorno de 6 itens
  - Guia por campo com estrutura de parágrafos para `executive_summary` (5 §)
  - Arc narrativo para `process_narrative` (abertura, corpo, fechamento, exceções)
  - Taxonomia de insights em 7 categorias com exemplos concretos
  - Guia de recomendações SMART com exemplos ✗/✓
  - Integração SBVR: usar termos do domínio no corpo do texto (não listar separado)
  - Integração BMM: §1 do summary + key_insights de alinhamento + recomendações coerentes
  - Anti-padrões: tabela de termos proibidos + estruturas de insight proibidas

---

### PC95 — Concluído (v4.71 / 2026-06-27) — skill_bpmn.md v9.1 — Anti-Omissão: Alçada, Timer, Notificação, Log

- [x] **`skills/skill_bpmn.md`** — v9.0 (952 linhas) → v9.1 (1002 linhas)
  - Diagnóstico por regressão real (transcrição Grupo Meridional / Projeto AURORA)
  - Gateway de alçada adicionado à tabela 4.1 de detecção de gateways faltantes
  - Seção 3e "Padrões Implícitos de Alta Frequência" (4 padrões sistemáticos):
    - SLA de tarefa ("em menos de 30s") → `boundaryTimerEvent` com exemplo JSON
    - Notificações ("enviar e-mail/SMS") → tarefa explícita antes do End Event
    - Logs de auditoria ("log auditável", "audit trail") → `serviceTask` de registro
    - Regras de alçada ("até R$X / de R$X a R$Y") → gateway com N saídas por nível
  - Checklist Passo 6 "Completude e Fechamento": 4 novos itens (alçada, SLA, notificação, log)
  - Checklist Passo 7.2 "Perguntas de integridade": 4 novos itens correspondentes

---

### PC94 — Concluído (v4.70 / 2026-06-27) — skill_bpmn.md v9.0 — Cobertura BPMN 2.0 OMG §10 Completa

- [x] **`skills/skill_bpmn.md`** — v8.0 (873 linhas) → v9.0 (952 linhas), edições cirúrgicas
  - `description:` adicionado ao frontmatter
  - Signal events na tabela de eventos: `intermediateCatchSignalEvent`, `intermediateThrowSignalEvent`, `escalationBoundaryEvent`
  - `subProcess` e `eventSubProcess` na tabela de task_types
  - Nova seção 3d: `subProcess` vs `callActivity` — distinção crítica com tabela de critérios
  - Black box pool documentado: pool com entidade externa sem processo conhecido (`steps: []`)
  - `is_interrupting: false` documentado com campo JSON e exemplo de boundary não-interrompente
  - Distinção crítica XOR vs OR (`exclusiveGateway` vs `inclusiveGateway`) com tabela de critérios e regra rápida
  - OR join obrigatório: `inclusiveGateway` split exige join que sincroniza apenas caminhos ativos
  - Exemplo concreto de `eventBasedGateway` com JSON e armadilha documentada
  - Checklist expandido com 6 novos itens (subProcess, is_interrupting, OR vs XOR, signal pairs, black box)

---

### PC93 — Concluído (v4.69 / 2026-06-27) — SKILL_REQUIREMENTS.md v2.0 — Cobertura IEEE 830 / ISO/IEC 29148

- [x] **`skills/SKILL_REQUIREMENTS.md`** — reescrito de v1.0 (100 linhas) para v2.0 (201 linhas)
  - Persona com fronteiras explícitas de escopo (✅ extrai / ❌ não extrai)
  - Convenção de iniciais de participantes (padrão compartilhado com skill_minutes.md)
  - Método de extração em 5 passos: leitura completa, domínio, classificação, IEEE 830, checklist
  - 6 tipos de requisito (adiciona `integration`) com tabela de sinais típicos
  - Tabela distinção crítica `validation` vs `business_rule` com teste diagnóstico
  - Tabela distinção crítica `functional` vs `non_functional`
  - Regra de atomicidade com exemplos de decomposição (campo CNPJ → 4 requisitos)
  - Tabela "O que NÃO Extrair" (6 linhas: BPMN/SBVR/BMM/ata/action items/problemas)
  - Documentação de campos `sphere` e `business_rule_refs` (antes implícitos)
  - Critérios de qualidade IEEE 830: específico, verificável, rastreável, não-ambíguo
  - Checklist final (5 itens) no Passo 4

---

### PC92 — Concluído (v4.68 / 2026-06-27) — skill_minutes.md v2.0

- [x] **`skills/skill_minutes.md`** — reescrito de v1.0 (190 linhas) para v2.0 (244 linhas)
  - Método de extração em 5 passos sequenciais
  - Passo 0: leitura completa obrigatória + tabela de tipos de reunião (8 tipos) com calibração de ênfase
  - Passo 3: formulação padrão de decisões (declarativa/passado) com exemplos ✓/✗
  - Tabela de distinção crítica Decisão vs Action Item (natureza, responsável, tempo, verificação)
  - Regra de não-duplicação entre decisões e action items
  - Calibração de densidade do resumo por contexto (4 cenários)
  - Antipadrões em formato de tabela com coluna "como identificar"
  - Regra 6 explícita: sem duplicação entre campos

---

### PC91 — Concluído (v4.67 / 2026-06-27) — skill_bpmn_reviewer.md v2.0

- [x] **`skills/skill_bpmn_reviewer.md`** — reescrito de v1.0 (242 linhas) para v2.0 (328 linhas)
  - Português com acentos corretos (v1.0 sem acentos)
  - 3 níveis de severidade: 🔴 Crítico (−2 pts), ❌ Violação (−0,5 pt), ⚠️ Atenção
  - Cálculo explícito do score com regra: score_max=5 se houver qualquer crítico
  - Checklist expandido de 25 → 38 itens em 8 seções (adiciona Eventos, Colaboração)
  - Novos itens críticos: gateway com 1 saída, AND-fork sem AND-join, dead end, elemento órfão
  - Novos itens de violação: sendTask/receiveTask fora de pools, message_flow dentro do mesmo pool, coreografia desbalanceada, End Event na lane errada em aprovações, Traceability Label Rule
  - Seção "Quando NÃO gerar JSON" (> 5 críticos, intenção não inferível, colaboração complexa)
  - Checklist pré-retorno do JSON na Fase 4

---

### PC90 — Concluído (v4.66 / 2026-06-27) — skill_sbvr.md v2.0 — Cobertura Normativa SBVR 1.5

- [x] **`skills/skill_sbvr.md`** — reescrito de v1.0 (111 linhas, inglês) para v2.0 (517 linhas, PT)
  - Tabela de distinções SBVR vs BMM vs DMN vs BPMN com regra de ouro
  - 5 categorias de vocabulário: concept, fact_type, role, process, **individual** (novo)
  - 5 padrões formais de formulação SBVR com templates: obrigação, proibição, permissão, condicional, estrutural
  - Regra de atomicidade com exemplos de decomposição de afirmações compostas
  - 5 `rule_type`: constraint, permission, behavioral, structural, **conditional** (novo)
  - Tabela expandida de `short_title` com 5 exemplos de inferência
  - Checklist de qualidade (12 critérios) em 3 categorias
  - 2 exemplos anotados completos: compras/fornecedores e contratos/compliance

---

### PC89 — Concluído (v4.65 / 2026-06-27) — skill_bmm.md v2.0 — Cobertura Normativa BMM 1.3

- [x] **`skills/skill_bmm.md`** — reescrito de v1.0 (83 linhas, inglês) para v2.0 (445 linhas, PT)
  - Tabela de construtos BMM: Fins (Visão/Missão/Meta) e Meios (Estratégia/Política)
  - 4 distinções críticas com anti-padrões: Vision vs Mission, Meta vs Estratégia, Estratégia vs Política, Política vs SBVR
  - Método de extração em 6 passos com sinais de reconhecimento por artefato
  - `category` de políticas expandido de 4 para 6 (adiciona `strategic` e `people`)
  - Campo `influencers` (opcional, SWOT) com tipos e `impact_on` (extra=allow no schema)
  - Checklist de qualidade (15 critérios): integridade, distinções, conservadorismo
  - 2 exemplos anotados: planejamento estratégico completo e reunião operacional

---

### PC88 — Concluído (v4.64 / 2026-06-27) — skill_dmn.md v2.0 — Cobertura Normativa DMN 1.4

- [x] **`skills/skill_dmn.md`** — reescrito de v1.1 (115 linhas) para v2.0 (569 linhas)
  - Todas as 11 variantes de hit policy: U, A, F, P, R, C, C+, C<, C>, C#, O com semântica exata
  - Árvore de decisão para seleção de hit policy
  - Referência completa FEEL: intervalos `[N..M]`/`(N..M]`, listas (OR), negação, wildcard
  - Regras de completude e sobreposição para hit policy U
  - DRD: campo `depends_on` para decisões em cadeia
  - Multi-output: campo `outputs` (lista) para tabelas com 2+ colunas de output
  - Checklist de qualidade (15 critérios) por categoria
  - 4 exemplos anotados: F com exceção, U multi-output, C+ acumulativo, DRD em cadeia

---

### PC84 — Concluído (v4.62 / 2026-06-27) — Output Schemas com Pydantic v2

- [x] **`core/output_schemas.py`** — 7 schemas Pydantic v2 fail-open (`_PermissiveModel` com `extra='allow'`):
  - `BPMNOutputSchema` — `name` obrigatório; suporta flat (`steps`/`edges`/`lanes`) e collaboration (`pools`/`message_flows`)
  - `MinutesOutputSchema` — todos os campos opcionais com defaults
  - `RequirementsOutputSchema` — `requirements` obrigatório e não-vazio
  - `SBVROutputSchema` — `vocabulary` + `rules` com listas
  - `BMMOutputSchema` — visão/missão/metas/estratégias/políticas
  - `TranscriptQualityOutputSchema` — `criteria` obrigatório; `grade` validado em A–E
  - `SynthesizerOutputSchema` — `executive_summary` obrigatório
- [x] **`agents/base_agent.py`** — `output_schema = None` class attr; `_call_with_retry()` chama `schema.model_validate(data)` e `warnings.warn()` em falha — pipeline nunca bloqueado
- [x] **7 agentes** — `output_schema = XxxOutputSchema` + import de `core.output_schemas`
- [x] **`requirements.txt`** — `pydantic==2.12.5` fixado explicitamente

---

### PC83 — Concluído (v4.61 / 2026-06-27) — Skill Version em Telemetria + Pré-condições

- [x] **`services/llm_telemetry.py`** — `TelemetryRecord.skill_version: Optional[str]`; campo incluído em `_write()` e `query()` select
- [x] **`setup/supabase_migration_skill_version.sql`** — `ALTER TABLE llm_telemetry ADD COLUMN IF NOT EXISTS skill_version TEXT` + índice parcial — **migração executada**
- [x] **`agents/base_agent.py`** — `self.skill_version` setado por `_load_skill()` via parse de `version:` no YAML frontmatter; passado ao `TelemetryRecord` em `_call_with_retry()`
- [x] **Pré-condições** — `required_hub_fields: list = []` class attr; `_check_preconditions(hub)` valida dot-paths (`transcript_clean`, `bpmn.ready`) antes de `run()`; 7 agentes com seus campos declarados

---

### PC82 — Concluído (v4.60 / 2026-06-27) — Pseudonimização Reversível de Nomes (Tier-2 PII)

**Contexto:** Decisão de design anterior mantinha nomes reais nas chamadas LLM (necessários para lanes BPMN). PC82 implementa pseudonimização reversível com iniciais — nomes não saem no wire para APIs externas, mas são restaurados nos artefatos antes de qualquer persistência (RAG preservado).

- [x] **`modules/pii_sanitizer.py`** — Tier-2 adicionado ao módulo existente (backward-compat total):
  - `detect_names(text) -> dict[str, str]` — spaCy `pt_core_news_lg` NER; apenas nomes com >=2 palavras; desambiguação de colisões de iniciais (PG -> PGOMES -> PG2); cap 50k chars; fail-open (retorna {} se spaCy indisponível)
  - `sanitize(text, name_map=None)` — novo arg opcional; nomes substituídos antes de PII estruturado (longest-match first); variantes título+sobrenome ("Sr. Gentil" -> [PESSOA:PG]); token_map unificado Tier1+Tier2
  - Token format `[PESSOA:XX]` — >95% de preservação pelo LLM vs ~70% para `{}`
  - `desanitize()` inalterado — já lida com ambos os tipos de token
- [x] **`core/knowledge_hub.py`** — `SessionMetadata.name_map: dict` (token -> nome original); guard em `migrate()` para sessões existentes
- [x] **`agents/base_agent.py`** — `_call_llm()` integrado: lê `hub.meta.name_map` (fail-safe getattr); passa para `sanitize()`; injeta `_NOME_INSTRUCTION` no system prompt quando name_map não-vazio; guard idempotente `_NOME_PRIVACY_MARKER` previne duplicação em retries
- [x] **`pages/Pipeline.py`** — `detect_names(hub.transcript_clean)` chamado uma vez antes de `run_pipeline()`; resultado salvo em `hub.meta.name_map`; fail-open

**Fluxo:** transcript (nomes reais) -> detect_names() -> hub.meta.name_map -> por chamada LLM: sanitize(user, name_map) -> API externa vê [PESSOA:PG] -> desanitize(raw, token_map) -> artefatos com nomes reais -> Supabase (RAG preservado)

**Decisões de design:** mapa em memória apenas (nunca persiste no Supabase); nomes reais no banco (RAG funciona); nomes parciais (primeiro nome isolado) fora do MVP (ambíguos para regex segura)

---

### PC81 — Concluído (v4.59) — LGPD Compliance Layer (Sprint 1 + 2)
- [x] `modules/compliance/` package: `detector.py`, `audit.py`, `consent.py`, `__init__.py`
- [x] `detector.py` — PII classification only (CPF, CNPJ, EMAIL, TEL, VALOR via regex + NOME_PESSOA via spaCy NER); no anonymization; `PIIDetectionResult` with `risk_level` (low/medium/high)
- [x] `audit.py` — async daemon thread write to `compliance_audit` table; fail-open; supports: `pipeline_run`, `consent_granted`, `data_accessed`, `data_deleted`, `pii_detected`
- [x] `consent.py` — post-pipeline LGPD consent panel (`render_consent_panel()`); legal basis dropdown (4 options); participant type radio; retention slider (30–365 days); saves to `compliance_consent` + triggers audit event
- [x] `pages/Pipeline.py` — two hooks: (1) after `save_meeting_artifacts()`: runs `detect_pii()`, caches result in session_state, logs `pipeline_run` audit; (2) before tabs: renders `render_consent_panel()` (fail-open wrapper)
- [x] `setup/supabase_migration_compliance.sql` — `compliance_consent` + `compliance_audit` tables with FK cascade, indexes, COMMENT metadata
- Architecture: consent form shown AFTER pipeline saves (meeting_id available) — solves chicken-and-egg; spaCy reuses same lazy-load cache pattern as nlp_chunker; panel is non-blocking (expander, expanded only on high-risk); all compliance ops fail-open

---

### PC1 — Concluído (v3.4)
- [x] Pipeline sequencial: Quality → Preprocessor → NLP → BPMN → Minutes → Requirements → Synthesizer
- [x] BPMN 2.0 XML com layout absoluto, pools/lanes, Link Events
- [x] `_enforce_rules()` — defesa programática contra erros LLM de lane/gateway
- [x] Backward-flow U-routing em `_build_di` — sem invasão visual de elementos
- [x] `AgentRequirements` — 5 tipos IEEE 830, speaker attribution por citação
- [x] `AgentTranscriptQuality` — grade A–E, critérios ponderados, recomendação
- [x] `AgentSynthesizer` — relatório executivo HTML interativo (sidebar, colapsável, filtros, comentários, localStorage)
- [x] Minutes com transcrição completa + iniciais de participantes
- [x] Export da Ata em Markdown, Word (.docx) e PDF
- [x] `KnowledgeHub.migrate()` para evolução de schema sem quebrar sessões
- [x] `_load_skill()` com path absoluto — resolve CWD e case-sensitivity no Linux

### PC2 — Concluído (v4.6 → v4.7)
- [x] `AgentValidator` — pure-Python BPMN quality scorer (granularity, task type, gateways)
- [x] Multi-run BPMN optimization (1/3/5 passes, weighted scoring, best candidate selection)
- [x] UI modularizada: `ui/sidebar.py`, `ui/input_area.py`, `ui/tabs/*`, `ui/components/*`
- [x] `core/pipeline.py`, `core/session_state.py`, `core/rerun_handlers.py` — separação de responsabilidades
- [x] `services/` package — export_service, file_ingest, preprocessor_service
- [x] Re-execução individual de agentes (sidebar + corpo principal)
- [x] `MermaidGenerator` classe — sanitização robusta, sem LLM
- [x] `modules/mermaid_renderer.py` — `render_mermaid_block()` compartilhado (pan/zoom/fit, TD/LR toggle)
- [x] `modules/requirements_mindmap.py` + `modules/mindmap_interactive.py` — mind map interativo de requisitos
- [x] `pages/Diagramas.py` — visualizador full-screen multi-diagrama (BPMN, Mermaid, Mind Map)
- [x] `modules/bpmn_diagnostics.py` — painel de diagnóstico BPMN isolado
- [x] Upload suporta `.txt`, `.docx`, `.pdf`
- [x] Pré-processamento com curadoria editável antes de executar o pipeline

### PC2.1 — Melhorias BPMN (v4.7)
- [x] Mermaid edge label syntax corrigido (`-->|label|` em vez de `-- label -->`) em single e multi-pool
- [x] `_enforce_rules` Rule 2 expandida para todos os tipos de gateway, não só `is_decision`
- [x] `_infer_lane_name` — três prioridades: actor fields → NLP actors → regex; recebe `hub.nlp.actors`
- [x] `modules/bpmn_structural_validator.py` — 6 verificações estruturais (dangling refs, isolated/unreachable nodes, XOR sem labels, AND/OR sem join, gateway com saída única)
- [x] Diagnóstico estrutural exibido no tab BPMN como expander com severidade (error/warning/info)
- [x] `_align_parallel_branches` no gerador de layout — elimina setas longas em branches paralelas desiguais
- [x] `AgentMinutes` + `AgentRequirements` executados em paralelo via `ThreadPoolExecutor` — hub shallow-copied com `meta` isolado por worker; deltas de token mergeados; fallback automático para sequencial; `threading.Lock` protege o progress callback

### PC3 — Concluído
- [x] `AgentSBVR` — OMG SBVR extraction: business vocabulary (5–15 terms) + business rules (3–10); default OFF; skills/skill_sbvr.md
- [x] `AgentBMM` — OMG BMM extraction: vision, mission, goals, strategies (with goal links), policies; default OFF; skills/skill_bmm.md
- [x] Suite de testes automatizados — 106 tests, 0 LLM calls; covers auto-repair, structural validator, AgentValidator, MermaidGenerator
- [x] LangGraph integration — adaptive BPMN retry loop (`core/lg_pipeline.py`); opt-in "🔄 Adaptive Retry" checkbox (single-pass mode only); configurable quality threshold (0–10, default 6.0) and max retries (1/2/3/5, default 3); best-scoring candidate committed to hub; `hub.bpmn.lg_attempts` + `hub.bpmn.lg_final_score` shown in BPMN tab

### PC4 — Concluído (v4.8 → v4.11)
- [x] **Authentication layer** — `modules/auth.py` + `ui/auth_gate.py`; SHA-256 session-based login gate; all pages protected; credentials hardcoded (no secrets.toml dependency for auth)
- [x] **Supabase integration** — `modules/supabase_client.py` + `core/project_store.py`; CRUD for projects, meetings, requirements, transcript chunks; fail-open when unconfigured
- [x] **Embedding pipeline** — `modules/embeddings.py`; `chunk_text()` + `embed_text()` + `embed_batch()`; Google Gemini (`gemini-embedding-001`) and OpenAI (`text-embedding-3-small`); 1536 dims; auto-retry on 429 with extracted retry_delay; 1.2s inter-call delay for free tier
- [x] **Supabase schema** — `setup/supabase_schema_transcript_chunks.sql`; `transcript_chunks` table with `vector(1536)` column; `ivfflat` cosine index; `match_transcript_chunks()` SQL function for semantic search
- [x] **`pages/Assistente.py`** — RAG-powered Q&A over meeting transcripts; keyword search + semantic search via `match_transcript_chunks`; embedding generation; re-edit feature (✏️ button, history truncation, `_resubmit_question` pattern)
- [x] **Tool-use mode** — `core/assistant_tools.py`; `AssistantToolExecutor` with 10 tools; `get_tool_schemas_openai()` + `get_tool_schemas_anthropic()`; `AgentAssistant.chat_with_tools()` with ≤5-round loop; automatic fallback to classic RAG on exception
- [x] **RAG quality improvement** — `project_store._extract_minutes_summary()` injects Participantes/Pauta/Decisões unconditionally in `format_context()`
- [x] **`pages/BatchRunner.py`**, **`pages/BpmnBackfill.py`**, **`pages/ReqTracker.py`**, **`pages/TranscriptBackfill.py`**, **`pages/CostEstimator.py`**
- [x] **`ui/project_selector.py`**, **`ui/assistant_diagram.py`**, **`modules/cost_estimator.py`**, **`modules/text_utils.py`**, **`modules/reqtracker_exporter.py`**
- [x] **Google Gemini SDK migration** — `google-generativeai` for `embed_content()` + `list_models()`; `google-genai` kept as secondary

### PC5 — Concluído (v4.12)
- [x] **ROI-TR sensível ao tipo de reunião** — `modules/meeting_roi_calculator.py` v2; 11 tipos, TYPE_WEIGHTS matrix; DC ponderado substitui fórmula linear fixa
- [x] **`classify_meeting_type()`** — classificação LLM; 1 chamada por reunião; JSON `{type, confidence}`; fallback heurístico; resultado persistido em `meetings.meeting_type`
- [x] **`fulfillment_score`** — indicador 0–1: DC gerado / DC mínimo esperado para o tipo
- [x] **`MeetingROIData` v2** — campos: `meeting_type`, `meeting_type_confidence`, `fulfillment_score`, `n_sbvr`, `n_bpmn_procs`
- [x] **`compute_project_roi()` v2** — busca SBVR + BPMN por meeting; retrocompatível sem coluna `meeting_type`
- [x] **`pages/MeetingROI.py` v2** — sidebar com classificação IA; 6 KPIs; gráfico de Fulfillment; pesos por artefato no detalhe
- [x] **`delete_meeting` fix** — cascade limpo: `requirement_versions` → nullify FK → `sbvr_terms/rules/transcript_chunks` → `bpmn_versions` → `bpmn_processes` → `meetings`
- [x] **SQL migração** — `ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_type TEXT`

### PC6 — Concluído (v4.13)
- [x] **Navegação reestruturada** — `app.py` migrado para `st.navigation()` com 4 grupos; pipeline movido para `pages/Pipeline.py`
- [x] **Sidebar simplificada** — opções avançadas em `st.expander("⚙️ Configuração Avançada")`; apenas provider + API key + idioma sempre visíveis
- [x] **Tabs do Pipeline reorganizadas** — abas primárias + "🔬 Análise Avançada" em expander; re-run buttons exclusivos na sidebar
- [x] **DatabaseOverview** — health score panel, KPI cards, 5 expanders de correção inline
- [x] **DatabaseOverview — aba 🔮 Embeddings** — gestão completa: cobertura por projeto, geração em lote, drill-down por reunião, teste de gravação
- [x] **RBAC no Assistente** — `is_admin()` aceita `admin` e `master`; admin gate em `AssistantToolExecutor.execute()`
- [x] **3 novas ferramentas admin** — `get_database_integrity()`, `fix_missing_llm_provider()`, `generate_meeting_embeddings()`
- [x] **Tool catalog em Configurações** — expander em Settings → aba Assistente
- [x] **Streamlit 1.42.0 → 1.45.1** — fix "Bad message format"
- [x] **Fix `st.page_link("app.py")`** — corrigido para `pages/Pipeline.py`

### PC7 — Concluído (v4.14)
- [x] **`pages/Home.py`** — header (nome, role badge, tenant, data), 4 KPIs globais, guia de 4 etapas, acesso rápido, reuniões recentes com links contextuais; `@st.cache_data(ttl=60)`
- [x] **`pages/BpmnEditor.py`** — bpmn-js Modeler; seletores projeto/processo/versão; histórico em dataframe; session-state-first paste pattern; salva via `save_bpmn_new_version()`
- [x] **`modules/bpmn_editor.py`** — `editor_from_xml(xml, height)` HTML self-contained; toolbar Ajustar/Desfazer/Refazer/Exportar; `navigator.clipboard` + fallback manual
- [x] **`core/project_store.py` novas funções** — `get_global_stats()`, `list_recent_meetings()`, `list_bpmn_processes()`, `list_bpmn_versions()`, `save_bpmn_new_version()`, `get_bpmn_version()`
- [x] **Navegação atualizada** — grupo "Início" como primeiro; BpmnEditor.py no grupo Pipeline

### PC8 — Concluído (v4.15 / 2026-05-03)
- [x] **`modules/calendar_client.py`** — 8 funções públicas; `_load_calendar_id(project_id)` resolve: Supabase → secrets → arquivo → "primary"
- [x] **9 ferramentas de calendário no Assistente** — `calendar_list_events`, `calendar_get_event`, `calendar_suggest_time` (todos); `calendar_create_event`, `calendar_schedule_action_items`, `calendar_share_with_user`, `calendar_revoke_access`, `calendar_diagnose` (admin)
- [x] **Multi-projeto Google Calendar** — tabela `project_calendar_config`; `get/set/delete/list_project_calendar_id()` em `project_store.py`
- [x] **Compartilhamento de agenda** — `calendar_share_with_user()` via ACL API; requer permissão "owner" da Service Account
- [x] **Contas de integração por usuário** — `tenant_users.google_account` + `tenant_users.ms_teams_account`; `update_user_accounts()` em `tenant_auth.py`
- [x] **Google Calendar embed na Home** — iframe via `_load_calendar_id()`; fallback caption
- [x] **MCP Google Calendar** (`mcp/google_calendar_server.py`) — servidor MCP (8 tools via FastMCP/stdio); timezone bug corrigido (UTC→Sao_Paulo)
- [x] **Documentação de integrações** — `mcp/integration_guide.html`; `CLAUDE_MS365.md`
- [ ] **Microsoft 365 (Outlook + Teams)** — PENDENTE: bloqueado por Azure AD admin consent; plano em `CLAUDE_MS365.md`

### PC9 — Concluído (v4.16 / 2026-05-09)
- [x] **`modules/bpmn_viewer.py` rewrite** — server-side asset fetch via `urllib` + `lru_cache`; bpmn-js native zoom; CDN fallback template
- [x] **`ui/components/copy_button.py` fix** — `navigator.clipboard.writeText()` + execCommand fallback dentro do mesmo user-gesture
- [x] **`ui/components/page_header.py`** (novo) — `render_page_header(icon, title, caption)` com amber accent HR
- [x] **`pages/Pipeline.py`** — progress via `st.status()` context manager
- [x] **`ui/sidebar.py`** — agent checkboxes agrupados; SBVR + BMM rerun buttons; `st.code` → `st.caption` para model display
- [x] **`app.py`** — role-aware navigation; Manutenção + admin pages só quando `is_admin()`
- [x] **BatchRunner reprocess** — `_reprocess_one()` em `core/batch_pipeline.py`; ferramenta `reprocess_meeting_full`

### PC10 — Concluído (v4.17 / 2026-05-11)
- [x] **Gráficos interativos no Assistente** — 5 ferramentas Plotly: `generate_requirements_chart`, `generate_meetings_timeline`, `generate_action_items_chart`, `generate_roi_chart`, `generate_custom_chart`; figs como `fig.to_dict()` em `_pending_charts`; retornadas como 4º elemento de `chat_with_tools()`; renderizadas com `st.plotly_chart()`
- [x] **Paleta de cores configurável** — `core/chart_config.py` (zero imports); 6 paletas nomeadas; `AssistantToolExecutor.__init__` lê `chart_palette` de `llm_config`; selectbox + swatches na sidebar do Assistente
- [x] **`core/chart_config.py`** — arquivo independente; evita ImportError ao importar `core.assistant_tools` no nível de módulo; chaves ASCII-only

### PC11 — Concluído (v4.18 / 2026-05-12)
- [x] **Projeto de trabalho global** — `active_project_id` + `active_project_name` em `st.session_state`; set only via Home.py ou `set_active_project` tool
- [x] **`require_active_project()`** — retorna `(project_id, project_name)` ou exibe warning + `st.page_link("pages/Home.py")` + `st.stop()`; chamada no topo de Assistente, ReqTracker, BpmnEditor, MeetingROI, ValidationHub
- [x] **Home.py — seletor de projeto** — auto-seleciona com 1 projeto; badge `st.success` + botão "Trocar" quando ativo; seta `prefix` = `sigla + "_"`
- [x] **`set_active_project` tool** — match parcial de nome (case-insensitive); atualiza `session_state["active_project_id/name/prefix"]`
- [x] **`delete_meeting` cascade fix** — Step 1: deleta `requirement_versions` por `meeting_id` (FK direto que bloqueava exclusão); `preview_meeting_deletion` atualizado
- [x] **Assistente chat styling** — user: fundo `#0d2a4a`, borda-esq azul; assistant: fundo `#0f2235`, borda-esq âmbar; chat input: fundo preto
- [x] **BPMN viewer timing fix** — `canvas.zoom('fit-viewport')` via `setTimeout(fn, 150)`; guard duplo width/height > 0

### PC18 — Concluído (v4.20+ / 2026-05-19)
- [x] **`api_key_alias` — chave compartilhada entre providers** — `modules/config.py`: `DeepSeek V4 Pro` e `DeepSeek V4 Flash (Thinking)` recebem `api_key_alias="DeepSeek"`; `session_security.py`: `render_api_key_gate` exibe "Key active (via DeepSeek)" sem pedir nova entrada; `get_session_llm_client` e `render_api_key_readonly` resolvem via alias — zero re-digitação de chave
- [x] **Settings "Status de todas as chaves"** — coluna Uso (Pipeline/Assistente/Embeddings); alias providers mostram `✅ Via DeepSeek`; linhas extras para `asst_api_key` (Assistente LLM) e `asst_embed_key` (Embeddings) — OpenAI configurada para embeddings aparece corretamente
- [x] **CostEstimator** — paleta de cores cíclica (10 cores) no gráfico de barras; data de preços atualizada para mai/2026; caption menciona DeepSeek V4 Flash + cache semântico
- [x] **CLAUDE.md** — padrão `api_key_alias` documentado na seção LLM Providers; tabela de providers atualizada com V4 Flash, V4 Pro, Thinking e Grok; nota sobre `reasoning_effort` e `api_key_alias`
- [x] **Decisão documentada** — reprocessamento de reuniões NÃO necessário: `deepseek-chat` aponta para `deepseek-v4-flash` durante o período de transição (até 24/07/2026); artefatos existentes válidos; cache semântico será repovoado naturalmente

### PC17 — Concluído (v4.20+ / 2026-05-19)
- [x] **Migração DeepSeek V4** — `modules/config.py`: `deepseek-chat` → `deepseek-v4-flash` (deprecated 24/07/2026); novo provider `DeepSeek V4 Pro` (`deepseek-v4-pro`, $0.435/1M, 1M context); novo provider `DeepSeek V4 Flash (Thinking)` com `reasoning_effort=high`, `supports_json_mode=False`, sem `temperature`
- [x] **Thinking mode em `_call_openai`** — se `provider_cfg["reasoning_effort"]` presente: passa `reasoning_effort` + `extra_body={"thinking":{"type":"enabled"}}`, remove `temperature` (não suportado); zero impacto nos outros providers
- [x] **`modules/cost_estimator.py`** — preços DeepSeek atualizados ($0.14/$0.28); entradas V4 Pro e Thinking adicionadas
- [x] **Fallbacks limpos** — `agents/agent_analyst.py` e `pages/Assistente.py`: `deepseek-chat` → `deepseek-v4-flash`

### PC16 — Concluído (v4.20+ / 2026-05-19)
- [x] **FASE 2 — Long Context Handler** — `services/context_analyzer.py`: `estimate_tokens()` (tiktoken cl100k_base + fallback len/4), `should_use_long_context()` (threshold 50k tokens), `inject_long_context_instruction()`, `LONG_CONTEXT_AGENTS={bpmn,sbvr,bmm}`
- [x] **`agents/base_agent.py`** — `_call_llm()` detecta transcrições longas: modifica system prompt (instrução de contexto completo), aumenta `max_tokens` de saída (8192), aumenta timeout (180s); `_call_openai`/`_call_anthropic` recebem `timeout` e `long_context` params; `hub.meta.long_context_calls` rastreado
- [x] **`core/session_state.py`** — `enable_long_context = True` padrão
- [x] **`core/knowledge_hub.py`** — `long_context_calls: int = 0` em `SessionMetadata`; migrate guard v4.26
- [x] **`ui/sidebar.py`** — checkbox "📄 Contexto Longo (BPMN/SBVR/BMM)" na Configuração Avançada
- [x] **`pages/Pipeline.py`** — banner `st.info` exibe número de agentes com contexto longo ativado
- [x] **`pages/MeetingROI.py`** — seção "📄 Contexto Longo (sessão atual)" no tab Cache LLM
- [x] **`tests/test_context_analyzer.py`** — 16 unit tests (TestEstimateTokens, TestShouldUseLongContext, TestInjectLongContextInstruction, TestLongContextAgentsSet); zero LLM/Supabase calls

### PC24 — Concluído (v4.24 / 2026-05-22)
- [x] **Renomeação ReqTracker → Central de Artefatos** — `pages/ReqTracker.py` → `pages/Artefatos.py` (git mv); título "Central de Artefatos" icon 🗂️; referências atualizadas em `app.py`, `pages/Home.py`, `core/assistant_tools.py`; nome de página mais amplo e em pt-br, cobrindo os 9+ tipos de artefato
- [x] **B) Badges de origem nos artefatos** — CSS `.badge-transcricao` (azul) + `.badge-documento` (verde); helpers `doc_map`, `doc_label()`, `_origin_badge()`; Tab Requisitos: 4º filtro "Origem" (Todas/Transcrição/Documento) + badge em cada card + fonte adaptada (mostra nome do documento quando origin=documento); Tab SBVR: badge de origem em termos e regras com fonte correta
- [x] **A) Nova aba Rastreabilidade (10ª)** — matriz consolidada: Requisitos + Termos SBVR + Regras SBVR; filtros tipo × origem; colunas Tipo/ID/Título/Origem/Fonte/Status/Prio.; KPIs (total/transcrições/documentos); exportação CSV
- [x] **C) KPI Documentos no Home** — `get_global_stats()` inclui `n_documents` (count de `meeting_documents`); Home.py: 5ª coluna KPI "Documentos" (rosa, ícone 📄, 5 colunas); métricas da Central de Artefatos: segunda linha agora com 4 métricas fixas incluindo Documentos

### PC23 — Concluído (v4.23 / 2026-05-22)
- [x] **`setup/supabase_migration_artifact_origin.sql`** — adiciona `origin TEXT DEFAULT 'transcricao'` e `doc_ref UUID REFERENCES meeting_documents(id)` às tabelas `requirements`, `requirement_versions`, `sbvr_terms`, `sbvr_rules`; remove NOT NULL de `first_meeting_id`/`last_meeting_id`/`meeting_id` para permitir artefatos sem reunião; 8 índices (`idx_*_origin`, `idx_*_doc_ref`)
- [x] **`core/knowledge_hub.py`** — campos `origin: str = "transcricao"` + `doc_ref: Optional[str] = None` adicionados a 7 dataclasses: `RequirementItem`, `BusinessTerm`, `BusinessRule`, `BMMGoal`, `BMMStrategy`, `BMMPolicy`, `DMNDecision`; guards `migrate()` v4.23 iterando sobre listas de artefatos
- [x] **`core/project_store.py`** — `save_new_requirement`: `meeting_id` agora nullable; `base_req`/`base_ver` condicionais (omitem meeting FK quando None); `origin`/`doc_ref` incluídos no attempt-1 payload (fallback transparente); `save_requirements_from_hub`: passa `origin`/`doc_ref` de cada item; `save_sbvr_from_hub`: refatorado com two-attempt pattern para origin/doc_ref, `meeting_id` nullable; nova função `save_artifacts_from_document(project_id, doc_id, extracted)`: salva todos os tipos de artefato (req/termos/regras SBVR/BMM e DMN via document metadata)
- [x] **`skills/skill_document_extractor.md`** — system prompt para extração de artefatos de documentos; JSON schema completo: requirements (title/description/req_type/priority/source_quote), sbvr_terms (term/definition/category), sbvr_rules (id/statement/rule_type/source/short_title), bmm_goals, bmm_strategies (com `supports`), bmm_policies, dmn_decisions (com confidence 0–1); guidelines por tipo de artefato
- [x] **`agents/agent_document_extractor.py`** — `DocumentExtractorAgent(BaseAgent)`; standalone on-demand; `extract(doc_title, doc_content, output_language) → Optional[dict]`; truncagem inteligente (head 8000 + tail 2000 chars); `_MinimalHub` stub satisfaz interface de hub sem necessitar pipeline completo
- [x] **`pages/DocumentManager.py`** — expandido de 4 para 5 abas; nova aba ⚗️ Extrair Artefatos: seleciona documento → run `DocumentExtractorAgent` → KPI row (7 métricas) → preview por tipo em expanders → download JSON → botão "Salvar no projeto" (chama `save_artifacts_from_document`)
- [x] **Pendente:** executar `setup/supabase_migration_artifact_origin.sql` no Supabase SQL Editor

### PC22 — Concluído (v4.22 / 2026-05-22)
- [x] **`setup/supabase_migration_documents.sql`** — 3 tabelas: `document_types` (taxonomia pré-populada com 53 tipos em 9 categorias), `meeting_documents`, `document_chunks` (`vector(1536)`); função pgvector `match_document_chunks()` para busca semântica filtrada por projeto; indexes; triggers updated_at; RLS desabilitado
- [x] **Taxonomia de documentos** — 53 tipos cobrindo: Iniciação e Planejamento (TAP/PGP/EAP/RACI), Requisitos (BRD/SRS/Backlog/User Stories/Casos de Uso), Processos (AS-IS/TO-BE/POP/SIPOC/VSM/Fluxograma/BPMN), Governança (Ata/Status Report/Riscos/Issues/Change Request/Lições), Análise de Negócio (SWOT/BMC/VPC/BIA/Business Case), Técnico (Arquitetura/API Spec/DER/C4/Runbook), Qualidade (Plano Teste/DoD/Checklist), Contratos e Acordos (Contrato/SLA/MOU/NDA/Proposta), Normas e Políticas (Política/ISO/Código de Conduta)
- [x] **`modules/document_store.py`** — CRUD fail-open: `upload_document`, `get_document`, `list_documents`, `delete_document`, `update_document_meta`; pipeline de embedding: `embed_document` (reusa `chunk_text`+`embed_batch` de `modules/embeddings.py`, inserts em batches de 50), `get_chunks_count`; busca: `search_documents_semantic` (pgvector via RPC), `search_documents_keyword` (ilike title+content, deduplica); `get_types_by_category` para UI
- [x] **`skills/skill_document_analyzer.md`** — system prompt para análise cruzada; JSON schema completo com: document_summary, alignment_score (0–100 com rubrica), aligned/conflicting/undocumented_requirements, process_alignment, process_gaps, stakeholders_mentioned, decisions_referenced (status: confirmed/conflicts/new/partial), implied_actions, temporal_analysis, key_insights, recommendations
- [x] **`agents/agent_document_analyzer.py`** — `DocumentAnalyzerAgent(BaseAgent)`; standalone on-demand (não entra no pipeline automático); `analyze(doc_title, doc_content, hub, output_language) → Optional[dict]`; conteúdo truncado inteligente (head 4500 + tail 1000 chars); `build_prompt` injeta minutos/requisitos/BPMN do hub formatados
- [x] **`pages/DocumentManager.py`** — 4 abas: (1) 📤 Enviar: seleção por categoria→tipo (53 tipos), vinculação opcional a reunião, upload .txt/.pdf/.docx ou paste, embed automático com spinner + contagem de chunks; (2) 📚 Biblioteca: busca keyword ou semântica, filtro por tipo, prévia de conteúdo, re-indexar, excluir; (3) 🔍 Análise Cruzada: seleciona doc+reunião+idioma → `DocumentAnalyzerAgent.analyze()` → score colorido + insights + expanders por seção (requisitos/processo/decisões/ações/stakeholders) + export JSON; (4) 🏷️ Taxonomia: tabela paginada por categoria
- [x] **`core/assistant_tools.py`** — 4 novas ferramentas: `list_meeting_documents` (filtra por reunião/tipo), `get_document_content` (conteúdo completo cap 8k), `search_documents` (semantic/keyword), `get_document_types` (taxonomia completa); métodos executor; entradas em `_TOOL_CATEGORIES`
- [x] **`app.py`** — `pages/DocumentManager.py` registrado no grupo Análise (icon 📄)
- [x] **Pendente:** executar `setup/supabase_migration_documents.sql` no Supabase SQL Editor

### PC21 — Concluído (v4.21 / 2026-05-22)
- [x] **`modules/billing.py`** — `Plan` dataclass + `PLANS` catálogo (5 planos: R$10/15cr, R$20/40cr destaque, R$35/80cr, R$50/120cr, R$80/ilimitado); CRUD Supabase fail-open: `get_user_credits`, `upsert_credits`, `set_contribuidor`, `reset_trial`, `log_payment`, `list_users_credits`, `list_payments`
- [x] **`setup/supabase_migration_billing.sql`** — tabela `user_credits` (user_id UNIQUE, creditos_restantes, degustacao_ativa, data_expiracao_degustacao, is_contribuidor, plano) + trigger updated_at + índices; tabela `pagamentos` (log imutável: user_id, email, valor, plano, creditos, status, external_id) + índices; RLS desabilitado
- [x] **`pages/PaymentAdmin.py`** — 4 abas admin: (1) Preview das mensagens: simulação interativa do banner de doação (PIX QR + agradecimento) + modal de plano pago (QR + balloons) + mensagem "pagamento não encontrado" + badge contribuidor; (2) Simular Pagamento: form com user/email/plano → `upsert_credits` + `log_payment(status='simulated')` + download SQL migration; (3) Usuários e Créditos: DataFrame + ações inline (delta créditos, toggle contribuidor, reset trial); (4) Log de Transações: DataFrame + 4 KPIs (total pago, créditos distribuídos, contribuidores, simulações)
- [x] **`app.py`** — `pages/PaymentAdmin.py` registrado no grupo Manutenção (admin only, icon 💳)
- [x] **Pendente:** executar `setup/supabase_migration_billing.sql` no Supabase SQL Editor

### PC20 — Concluído (v4.20+ / 2026-05-19)
- [x] **`ui/sidebar.py`** — `st.expander("Pesos de Seleção")` aninhado em `st.expander("⚙️ Configuração Avançada")` → substituído por `st.caption()` (Streamlit proíbe expanders aninhados; causava `StreamlitAPIException` ao mudar Passes de Otimização)
- [x] **`core/session_state.py`** — `run_query_summarizer` default `False` → `True`; `n_bpmn_runs` default `1` → `3`
- [x] **`modules/tenant_config.py`** — `PROVIDER_KEY_MAP` + `"Grok (xAI)": "grok_key"` (faltava no mapeamento de domínio)
- [x] **`pages/Settings.py`** aba Domínio — lista de provedores derivada de `AVAILABLE_PROVIDERS` (única fonte de verdade); alias providers ignorados automaticamente; ícone 🟡 para chave em sessão não salva no domínio; modelo visível no header
- [x] **`pages/Orientacoes_CKF.py`** seção 5 — diagrama CKF Evolutivo redesenhado: box AgentCKFUpdater, leituras alinhadas com labels dim, dois outputs em colunas (hub.context_skill / Supabase)

### PC35 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/modulo_07_reunioes_eficazes/guia.md`** — guia de facilitação: 5 dimensões do Quality Inspector, 5 comportamentos de maior impacto (com exemplos ruim vs. bom), scripts de abertura/fechamento, tabela de linguagem processável vs. ambígua (7 situações), exercício passo a passo, dois checklists de bolso (facilitador + participante)
- [x] **`ensino/modulo_07_reunioes_eficazes/transcricao_07a_reuniao_ruim.txt`** — RetailPro, kick-off módulo de estoque, sem speaker ID, decisões implícitas, action items sem dono/prazo; esperado Grau D/E no Quality Inspector
- [x] **`ensino/modulo_07_reunioes_eficazes/transcricao_07b_reuniao_eficaz.txt`** — mesma reunião com facilitação estruturada: script de abertura, speakers identificados, processo descrito com gatilho→condição→exceção, 4 encaminhamentos com nome+tarefa+prazo, resumo de fechamento; esperado Grau A
- [x] **`ensino/PLANO_DO_CURSO.md`** — Módulo 7 adicionado à tabela de estrutura; total 14h→15h; seção completa com descrição dos dois cenários e exercício central
- [x] **`pages/Capacitacao.py`** — Módulo 7 adicionado a `_MODULES` (2 cenários: 7A e 7B); isolamento de contexto por usuário: botão "▶ Carregar" agora chama `_get_or_create_course_project()` que cria/resolve o projeto "Curso P2D - {usuario}" no Supabase antes de redirecionar ao Pipeline — evita mistura com projetos reais da empresa; fail-open quando Supabase não configurado

### PC47 — Concluído (sem PC / 2026-06-16)
- [x] **BPMN quality — regra de gateway com saída única** (`skill_bpmn.md` v7.3 + `agents/agent_validator.py`)
  - `skill_bpmn.md` v7.3: nova **REGRA CRÍTICA** em Passo 4 — todo gateway exige ≥ 2 sequence flows de saída; gateway com 1 saída indica ramificação omitida; exemplo explícito (Valor Abaixo do Limite? — 2 caminhos obrigatórios); checklist item adicionado em Passo 6
  - `agents/agent_validator.py` — `_score_gateways()`: new single-exit guard antes dos checks de XOR/AND; qualquer gateway com `len(out_edges) < 2` recebe `scores.append(0.0)` e `continue`; condição de XOR/AND corrigida para `if len > 1` implícito via continue

### PC46 — Concluído (sem PC / 2026-06-16)
- [x] **LangGraph expandido — Minutes + Requirements com adaptive retry** (`core/lg_pipeline.py`, `core/pipeline.py`, `core/knowledge_hub.py`, `agents/orchestrator.py`, `ui/sidebar.py`, `ui/tabs/bpmn_tabs.py`, `core/session_state.py`, `pages/Pipeline.py`)
  - `LGFullPipelineRunner` com 8 nós: bpmn → validate_bpmn → commit_bpmn → minutes → validate_minutes → requirements → validate_req → coordinator → END
  - Coordinator node: fuzzy word-overlap lanes ↔ participants + coverage check; notas em `hub.validation.lg_coordination_notes`
  - `ValidationReport` estendido: `lg_minutes_retries`, `lg_req_retries`, `lg_coordination_notes`
  - Bug fix (❌ icons): progress messages padronizadas para "running (...)" / "done (...)"
  - Bug fix (double preprocessing): `run_prereqs=True` param em `Orchestrator.run()`; Step 3 passa `run_prereqs=False`
  - Bug fix (identical scores): `_lg_skip_cache` instance attr em `BaseAgent._call_llm()`; setado True em retentativas > 1
  - Sidebar: 2 novos selectboxes `max_minutes_retries` + `max_req_retries` quando LG ativo
  - BPMN tab: banner expandido mostra retentativas Minutes/Req + expander coordination notes

### PC45 — Concluído (sem PC / 2026-06-16)
- [x] **Agent Cards — metadados semânticos por agente** (`skills/agent_cards/*.yaml`, `core/agent_registry.py`, `core/assistant_tools.py`, `pages/MasterAdmin.py`)
  - 18 YAML cards cobrindo todos os agentes: transcript_quality, bpmn, mermaid, minutes, requirements, sbvr, bmm, dmn, argumentation, synthesizer, query_summarizer, knowledge_extractor, contradiction_detector, communication_noise, ckf_updater, validator, document_analyzer, document_extractor
  - `core/agent_registry.py`: `get_agent_cards()` (lru_cache), `get_agent_card(name)`, `get_pipeline_agents()`, `get_on_demand_agents()`, `format_card_summary()`; ordenado por pipeline_phase
  - `get_system_capabilities()` atualizado para usar registry; agrupa por fase
  - `pages/MasterAdmin.py` Seção 6 — visualizador elegante: 4 KPIs, filtros phase/mode, grid CSS 3 colunas com hover, badges coloridos por fase, painel de inspeção de detalhe

### PC44 — Concluído (sem PC / 2026-06-14)
- [x] **`core/assistant_tools.py`** (`5b02b1c`) — `generate_ibis_map` corrigido:
  - Labels Q-nodes globalmente únicos: `"Q1<br>R9"` em vez de `"Q1"` local por reunião — elimina ambiguidade de leitura horizontal
  - Tooltip de A-nodes inclui `"— R{mnum}"` para rastreabilidade
  - Anotações de cabeçalho de reunião migradas para `yref="paper"` — sempre visíveis no topo independente do range de dados Y; badge navy com borda azul (`bgcolor="#1e3a5f"`, `bordercolor="#2563eb"`)
  - Margem superior 80 → 100px para acomodar os badges de reunião

### PC43 — Concluído (sem PC / 2026-06-14)
- [x] **`pages/Orientacoes_Assistente.py`** (`6f267ab`) — nova seção "Exportação da conversa" com tip-box documentando `⬇️ Markdown` e `⬇️ HTML`, gráficos Plotly interativos e nota sobre CDN

### PC42 — Concluído (sem PC / 2026-06-14)
- [x] **`pages/Assistente.py`** (`b452f22`) — exportação da conversa como HTML auto-contido:
  - `_export_chat_to_html(messages, project_name, provider) → str` — percorre `assistant_history`, renderiza mensagens user/assistant com dark-navy CSS, embute gráficos Plotly via `Plotly.js` CDN (incluído somente quando há charts), renderiza Markdown client-side via `marked.js` CDN, badges de ferramentas por mensagem, tabelas/código/blockquotes estilizados
  - `_html_escape(text)` + `_html_escape_attr(text)` — helpers de sanitização HTML segura
  - Toolbar atualizada: `⬇️ Markdown` (texto simples) + `⬇️ HTML` (auto-contido com gráficos) lado a lado

### PC41 — Concluído (sem PC / 2026-06-14)
- [x] **`ui/assistant_diagram.py`** — novo subgrupo `TD` "🗺️ Debates IBIS" com `search_ibis_debates`, `get_ibis_timeline`, `generate_ibis_map`; contador 35 → 38 ferramentas
- [x] **`ui/comms_diagram.py`** — novo `TG4` "🗺️ Debates IBIS" (3 tools); aresta `TG4 → MSBC` adicionada; contador 35 → 38 ferramentas

### PC40 — Concluído (sem PC / 2026-06-14)
- [x] **`pages/Orientacoes_Assistente.py`** — Guia do Assistente atualizado com 3 cards IBIS: `search_ibis_debates` (aba Análise, seção "Debates argumentativos — IBIS") + `get_ibis_timeline` e `generate_ibis_map` (aba Gráficos, seção "Debates argumentativos — IBIS"); inclui prompt canônico, campos `proposed_by/supported_by/opposed_by` e filtro de resolução documentados
- [x] **`CLAUDE.md`** — `search_ibis_debates`, `get_ibis_timeline`, `generate_ibis_map` adicionadas à lista Non-admin; nova seção "IBIS tools (3)" com campos, filtros, helper interno e prompt exemplo

### PC39 — Concluído (sem PC / 2026-06-14)
- [x] **`core/assistant_tools.py`** — `search_ibis_debates` agora inclui `proposed_by`, `supported_by` e `opposed_by` por alternativa — alinhado com o nível de detalhe da aba IBIS da Central de Artefatos

### PC38 — Concluído (sem PC / 2026-06-13)
- [x] **`core/assistant_tools.py`** — 3 novas ferramentas IBIS no `AssistantToolExecutor`:
  - `_load_ibis_questions(topic_filter, meeting_number)` — helper privado; query `meetings.argumentation_json` por projeto; parseia JSON; injeta `_mid/_mnum/_mtitle/_mdate`; filtra por Jaccard PT-BR (stop-word filtered tokens)
  - `search_ibis_debates(query, meeting_number?, resolution_filter?)` — busca keyword; grupos por reunião; formata Markdown estruturado com enunciado, raised_by, alternativas completas, resolução e ressalvas; filtro `all|decided|deferred|unresolved`
  - `get_ibis_timeline(topic?)` — Plotly stacked bar (decidido/adiado/em aberto por reunião número); `self._pending_charts`
  - `generate_ibis_map(topic?)` — Plotly hierárquico: Q-nodes círculo (cor por status: verde/âmbar/vermelho), A-nodes diamante (verde=eleita, azul=alternativa); colunas por reunião; arestas Q→A; legenda via traces invisíveis; appended como `fig.to_dict()` em `_pending_charts`
  - Schemas OpenAI + Anthropic, `_TOOL_CATEGORIES` (consulta/grafico), dispatch em `execute_tool()` todos conectados

### PC37 — Concluído (sem PC / 2026-06-13)
- [x] **`pages/DmnBackfill.py`** (novo) — página Manutenção dedicada ao DMN; `_missing(m) = not m.get("dmn_json")`; SELECT inclui apenas `dmn_json`; executa somente `AgentDMN`; tabela de resultados com "Decisões DMN"; session keys `dmn_bf_*`
- [x] **`pages/IbisBackfill.py`** (novo) — página Manutenção dedicada ao IBIS; `_missing(m) = not m.get("argumentation_json")`; SELECT inclui apenas `argumentation_json`; executa somente `AgentArgumentation`; tabela de resultados com "Questões IBIS"; session keys `ibis_bf_*`
- [x] **`pages/DmnIbisBackfill.py`** — removido via `git rm` (substituído pelas duas páginas acima)
- [x] **`app.py`** — Manutenção: entrada única `DmnIbisBackfill` substituída por `DmnBackfill.py` (icon ⚖️) + `IbisBackfill.py` (icon 🗺️)
- [x] **`pages/Artefatos.py`** — Mapa Visual IBIS com paridade do KnowledgeGraph: toolbar (⏸/▶ física, ＋/－ zoom, ⊡ Fit, 💾 Imagem, ⛶ Nova aba), focus mode (click node → dim não-vizinhos + bring-to-front via remove+re-add), `_ibis_physics` toggle + `_ibis_height` select_slider no expander de opções, tooltip CSS `white-space:pre-line`, legenda como badges Markdown `st.markdown` acima de `components.html()`

### PC36 — Concluído (v4.28 / 2026-06-06)
- [x] **`ensino/modulo_07_reunioes_eficazes/guia.md`** — enriquecimento baseado em análise dos capítulos 8 e 9 de "Business Modeling: A Practical Guide" (Bridgeland & Zahavi): tabela de 7 perfis de participantes desafiadores (Mouse→Otter) com comportamento + efeito na transcrição + resposta do facilitador; tabela de 7 antipadrões de reunião processável (Participante Ausente, Multitarefa, Patrocinador Ausente, Compromisso Condicional, Proxy Sem Autonomia, Facilitador Viesado, Modelo Rejeitado) com manifestação + impacto + prevenção; 6º comportamento "Verbalization Echoing" (facilitador resume + aguarda confirmação verbal, criando o rastro de confirmação mais rastreável da transcrição); "Declarar o escopo na abertura" como 2º comportamento; exercício expandido em 3 passos (comparação de pipeline, identificação de antipadrões na 7A, sessão de verificação dos artefatos da 7B); checklist do facilitador atualizado com 11 itens; atualização da tabela do Quality Inspector para mostrar as 7 dimensões (6 ASR + 1 Condução)
- [x] **`skills/skill_transcript_quality.md`** — 7º critério "Condução da Reunião" (Weight: 15%): avalia 5 práticas (A: identificação de speakers, B: verbalização de decisões, C: action items nome+tarefa+prazo, D: estrutura de processo gatilho→sequência→condições, E: verbalization echoing com confirmação); guia de pontuação 0/5→5/5 práticas; pesos redistribuídos (Coerência 20→15%, Vocabulário 15→10%, Pontuação 10→5%, Condução 0→15%); output JSON atualizado com 7 entradas; regra "exactly 7 entries" atualizada
- [x] **`agents/agent_transcript_quality.py`** — `_CRITERIA_WEIGHTS` atualizado com 7 critérios (soma 1.0); `_CONDUCAO_DEFAULT_SCORE = 50` para respostas em cache sem o 7º critério (evita penalizar transcrições antigas)
- [x] **`core/knowledge_hub.py`** — `MinutesModel.meeting_antipatterns: list[dict]` (cada item: `{type, description, examples}`); `migrate()` guard v4.28
- [x] **`skills/skill_minutes.md`** — seção "Detecção de Antipadrões de Reunião": 7 antipadrões a detectar (Participante Ausente, Compromisso Condicional, Proxy Sem Autonomia, Multitarefa, Patrocinador Ausente, Facilitador Viesado, Decisão Implícita); campo `meeting_antipatterns` adicionado ao schema JSON de saída
- [x] **`agents/agent_minutes.py`** — `_EMBEDDED_SKILL` atualizado com seção de antipadrões + schema JSON; `_build_model()` parseia `meeting_antipatterns`; `to_markdown()` inclui seção "⚠️ Alertas de Condução" quando antipadrões detectados; novo método estático `to_verification_report(minutes)` — gera roteiro de verificação em Markdown (header + decisões com checkbox + action items com confirmação + perguntas em aberto + riscos + alertas de condução + encerramento)
- [x] **`ui/tabs/export_tab.py`** — botão "⬇️ Roteiro de Verificação (.md)" na seção Meeting Minutes (usa `AgentMinutes.to_verification_report()`, `make_filename("verificacao", "md", ...)`)

### PC35 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/modulo_07_reunioes_eficazes/`** — Módulo 7 "Reuniões que Geram Conhecimento Rastreável" criado do zero: `guia.md` (5 comportamentos, guia do facilitador, padrões de linguagem, exercício passo a passo, checklists); `transcricao_07a_reuniao_ruim.txt` (RetailPro kick-off, sem identificação de speaker, decisões vagas, Grau D esperado); `transcricao_07b_reuniao_eficaz.txt` (mesma pauta, Adriana Lemos como facilitadora com script de abertura, verbalization echoing, 4 encaminhamentos com nome+tarefa+prazo, fechamento explícito, Grau A esperado)
- [x] **`pages/Capacitacao.py`** — Módulo 7 adicionado ao `_MODULES` com 2 cenários (7A e 7B); importações `get_current_user` e `list_contexts/create_context` adicionadas; função `_get_or_create_course_project()` cria/resolve projeto Supabase "Curso P2D - {usuario}" fail-open; botão "▶ Carregar" atualizado para resolver projeto antes de injetar transcrição e redirecionar
- [x] **`ensino/PLANO_DO_CURSO.md`** — Módulo 7 adicionado na estrutura (tabela de módulos + seção detalhada); duração total 14h→15h

### PC34 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/PLANO_DO_CURSO.md`** — narrativa reposicionada com chave "conhecimento rastreável": subtítulo, seção Sobre o Curso (distinção ata vs. conhecimento rastreável, pergunta de valor), Módulo 0 item 1 reformulado, item 5 de rastreabilidade na prática adicionado; Público-Alvo expandido com coluna "Quem é e o que enfrenta" (definição de papel + dor específica para cada um dos 7 perfis)
- [x] **`ensino/ativo-intangivel-de-maior-impacto-tangivel.md`** — "conhecimento rastreável" inserido como conceito-âncora: Tese Central ("transformar em conhecimento rastreável" + parágrafo de definição), Parte III subtítulo "Da conversa ao conhecimento rastreável" + frase "cada artefato sabe de onde veio" + coluna da tabela renomeada; Conclusão com parágrafo que distingue a categoria ("não é documentação melhorada") + citação final reforçada

### PC33 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/ativo-intangivel-de-maior-impacto-tangivel.md`** — white paper completo reescrito: 6 partes estruturadas (O Ativo, Amnésia Corporativa, Tangibilização, ROI-TR/TRC, Implementação, Críticas); Parte VI incorpora análise crítica independente (Manuis AI) com 5 objeções respondidas diretamente (qualidade de entrada, resistência cultural, complexidade, privacidade/LGPD, dependência tecnológica); síntese "IA com limitações gerenciáveis vs. caos institucional crônico"

### PC32 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/`** — curso de aplicações corporativas com 7 módulos + 8 transcrições fictícias realistas:
  - `PLANO_DO_CURSO.md` — visão geral, público-alvo, 14h de conteúdo, 3 formatos de entrega
  - `modulo_00_fundamentos/guia.md` — configuração, Quality Inspector, primeiro pipeline
  - `modulo_01_mapeamento_processos/` — guia + 3 transcrições (aprovação fornecedor, crédito pessoal, onboarding); exercícios de Check 7/Pass 5/Check 8
  - `modulo_02_rastreabilidade_requisitos/` — guia + kickoff portal cliente (requisitos IEEE 830, LGPD, Assistente RAG)
  - `modulo_03_auditoria_compliance/` — guia + comitê de contratos R$ 2,3M (SBVR, ata, dossiê de auditoria)
  - `modulo_04_gestao_conhecimento/` — guia + captura de especialista (conciliação SAP×Salesforce, Knowledge Graph)
  - `modulo_05_governanca_roi/` — guia + retrospectiva de sprint (ROI-TR, CommunicationNoise, TRC)
  - `modulo_06_estrategia_bmm/` — guia + planejamento estratégico anual (BMM, IBIS, rastreabilidade vertical)
- [x] **`pages/Capacitacao.py`** — página Streamlit no grupo Ajuda (🎓 Curso Corporativo): cards por módulo com guia inline, botão "▶ Carregar" injeta transcrição em `session_state.transcript_text` e redireciona para Pipeline, preview + download .txt
- [x] **`app.py`** — `Capacitacao.py` registrada no grupo Ajuda

### PC31 — Concluído (v4.27 / 2026-06-04)
- [x] **`ui/architecture_diagram.py`** — LLM providers 5→8 (DeepSeek V4 Pro, Thinking, Grok xAI adicionados); pipeline estendido com A9(DMN), A10(Argumentation/IBIS), A11(CommunicationNoise/CKF), A12(Synthesizer); artefatos 7→10 (R8 DMN, R9 Argumentação, R10 Análise de Ruído); ASST "21 ferramentas" → "35 ferramentas"
- [x] **`ui/assistant_diagram.py`** — TOOLS subgraph "21→35 Ferramentas"; TA: `list_bpmn_versions` adicionada após `list_bpmn_processes`; TC Admin: `★ delete_bpmn_version` adicionada
- [x] **`ui/comms_diagram.py`** — header "22→35 ferramentas"; TG1 "11→12 tools" + `list_bpmn_versions`; TG2 corrigido "7→8 tools"; TG3 "4→5 tools" + `★ delete_bpmn_version`
- [x] **`pages/Orientacoes_Arquiteturas.py`** — texto "22 ferramentas" → "35 ferramentas"

### PC30 — Concluído (v4.26 / 2026-06-04)
- [x] **`core/project_store.py`** — `delete_bpmn_version(version_id)`: exclui versão BPMN com segurança (recusa única versão; promove versão anterior se is_current; atualiza version_count)
- [x] **`core/assistant_tools.py`** — `list_bpmn_versions` (consulta): lista versões de um processo por nome com ID, status, reunião e notas; `delete_bpmn_version` (admin): exclui versão pelo version_id; ambas registradas em schemas OpenAI/Anthropic, `_TOOL_CATEGORIES`, `_ADMIN_TOOLS` e dispatcher
- [x] **`CLAUDE.md`** + **`pages/Orientacoes_Assistente.py`** — documentação atualizada: tool list e cards do Guia de Ferramentas com `list_bpmn_versions` e `delete_bpmn_version`
- [x] **Check 8** (`bpmn_structural_validator.py`): detecta coreografia desbalanceada em colaborações — sender não-sendTask ou receiver não-receiveTask em message flows; `skill_bpmn.md` atualizado com regra de balanceamento sendTask↔receiveTask

### PC29 — Concluído (v4.26 / 2026-06-04)
- [x] **`skills/skill_bpmn.md`** — XOR join promovido de "Recomendada" para "Obrigatória"; checklist atualizado para exigir join em AND/OR/XOR/complex splits
- [x] **`modules/bpmn_structural_validator.py` Check 7** — detecta task com `in_degree >= 2` cujos predecessores são todos não-gateway (fan-in direto); emite `warning` recomendando XOR join explícito
- [x] **`modules/bpmn_auto_repair.py` Pass 5** — insere `exclusiveGateway` join automaticamente quando branches de um XOR split convergem diretamente em uma task; algoritmo de ancestral-comum-2-hops evita falsos positivos em AND/OR; gateway anônimo inserido na mesma lane da task alvo

### PC28 — Concluído (v4.26 / 2026-06-04)
- [x] **`AgentCommunicationNoise`** — novo agente não-fatal (default OFF) que detecta 4 tipos de ambiguidade (lexical, referencial, vague_commitment, sintática) e 4 tipos de lacuna (unanswered_question, abandoned_topic, implicit_disagreement, missing_info); `noise_score` 0–10
- [x] **`core/knowledge_hub.py`** — `AmbiguityItem`, `CommunicationGap`, `CommunicationNoiseModel` dataclasses; campo `communication_noise` no `KnowledgeHub`; `migrate()` guard
- [x] **`skills/skill_communication_noise.md`** — skill com taxonomia de 8 tipos de ruído e tabela de pontuação
- [x] **`ui/tabs/communication_noise_tab.py`** — 4 KPIs, cards expandíveis por ambiguidade (confiança, interpretações, sugestão) e lacuna (impacto, recomendação, evidência)
- [x] **Pipeline step 6e** — `run_communication_noise` em `orchestrator.py`, `pipeline.py`, `rerun_handlers.py`, `sidebar.py` e `Pipeline.py`
- [x] **`pages/BpmnEditor.py`** — expander "Reconverter com Method & Style v7.0": re-executa `AgentBPMN` sobre a transcrição da versão selecionada e carrega o XML gerado no editor para revisão antes de salvar

### PC27a — Concluído (v4.25 / 2026-05-31)
- [x] **`skills/skill_bpmn.md` v7.0** — rewrite completo seguindo a metodologia Top-Down de Bruce Silver (*BPMN Method and Style*):
  - **Passo 0** (novo): definir escopo — identificar trigger, end states e volume de atividades antes de modelar
  - **Regra de Densidade Cognitiva**: sequências lineares com > 10 atividades são proibidas; `callActivity` obrigatório para agrupar fases lógicas (máx 10 nós por nível)
  - **Passo 2** (novo): High-Level Map — 3–7 fases com `callActivity` quando processo tem > 10 atividades
  - **Novos `task_type`**: `callActivity` (fase agrupadora), `loopTask` (repetição embutida), `multiInstanceTask` (para cada item de coleção), `boundaryTimerEvent`, `boundaryErrorEvent` (exceções durante tarefas)
  - **Nomenclatura estrita**: todos os títulos seguem `[Verbo Infinitivo] + [Objeto]` — noun-phrases são falha de qualidade
  - **Checklist expandido**: 20 itens cobrindo estrutura, hierarquia, semântica e padrões especiais (vs 12 itens anteriores)
  - **Dois exemplos**: processo flat simples + processo hierárquico com `callActivity`
- [x] **`agents/agent_bpmn.py`** — `_TASK_TYPE_MAP` expandido: `callActivity` (renderiza com dupla borda no bpmn-js), `sendTask`, `receiveTask`, `eventBasedGateway`, `complexGateway`, `loopTask`, `multiInstanceTask`, `boundaryTimerEvent`, `boundaryErrorEvent`; tipos não-nativos do gerador mapeiam para `userTask` até PC27b
- [x] **`claude_guideline/acceptance_criteria.md`** — AgentBPMN expandido com critérios Silver Level 1: densidade (callActivity obrigatório > 10 atividades), nomenclatura Verbo+Objeto, end states distintos, padrões de iteração e boundary events

### PC26 — Concluído (v4.25 / 2026-05-31)
- [x] **`claude_guideline/acceptance_criteria.md`** (novo) — Quality Contract: critérios testáveis por agente (TranscriptQuality, NLPChunker, BPMN, Mermaid, Minutes, Requirements, SBVR, BMM, Synthesizer, Validator) + critérios de Pipeline Integration, Supabase/Persistência e UI/Streamlit; referenciado em CLAUDE.md
- [x] **`core/knowledge_hub.py`** — `AgentOutcomeScore` dataclass (`agent_name`, `passed`, `score 0–10`, `checks dict`, `warnings list`); `ValidationReport.agent_scores: dict`; `migrate()` guard v4.26
- [x] **`agents/agent_validator.py`** — `validate_all(hub, weights) → dict[str, AgentOutcomeScore]`; 8 validadores fail-open: `_validate_quality`, `_validate_nlp`, `_validate_bpmn_outcomes`, `_validate_mermaid`, `_validate_minutes`, `_validate_requirements`, `_validate_sbvr`, `_validate_bmm`; helper `_make_score()`; método `score()` (torneio multi-run) intocado
- [x] **`agents/orchestrator.py`** — Step 8 (fail-open): após synthesizer, chama `AgentValidator().validate_all(hub, bpmn_weights)` e persiste em `hub.validation.agent_scores`
- [x] **`ui/components/quality_badge.py`** (novo) — `render_quality_badge(hub, agent_name)`: lê `hub.validation.agent_scores`, exibe badge colorido (✅ ≥ 8.0 / ⚠️ 6–8 / ❌ < 6) com `st.popover` listando checks individuais; silencioso se `agent_scores` ausente
- [x] **Badges nas tabs do Pipeline** — `bpmn_tabs.py`, `quality_tab.py`, `minutes_tab.py`, `requirements_tab.py`, `sbvr_tab.py`, `bmm_tab.py`: cada tab recebeu header em duas colunas com `render_quality_badge(hub, agent_name)` à direita
- [x] **Fix `pages/Home.py`** — "Reuniões recentes" filtradas por `active_project_id`; `list_recent_meetings()` aceita `project_id` opcional; join `projects(name)` inválido removido (tabela é `contexts`); `@st.cache_data` usa `project_id` como cache key

### PC25 — Concluído (v4.25 / 2026-05-23 + 2026-05-31)
- [x] **`modules/transcript_time_parser.py`** — pure-Python parser de timestamps ASR; detecta 6 formatos (`[HH:MM:SS] Speaker:`, `Speaker (HH:MM):`, `HH:MM:SS - Speaker:`, etc.); computa `duration_seconds` e `speaker_times` (dict nome→segundos); fallback `estimate_timings_from_wordcount()` quando sem timestamps; `format_duration()` + `format_speaker_table()` para display
- [x] **`MeetingTimeModel`** em `core/knowledge_hub.py` — `has_timestamps`, `format_detected`, `duration_seconds`, `speaker_times`, `speaker_turns`, `ready`; propriedade `duration_minutes`; `migrate()` guard v4.25
- [x] **Orchestrator Step 1.5** — `parse_transcript_timings()` + fallback `estimate_timings_from_wordcount()` após NLP Chunker; popula `hub.meeting_time`; fail-open (não quebra pipeline)
- [x] **`setup/supabase_migration_meeting_time.sql`** — colunas `duration_minutes INTEGER` e `speaker_times JSONB` na tabela `meetings`
- [x] **`core/project_store.py`** — `save_meeting_artifacts()` persiste `duration_minutes` e `speaker_times` quando disponíveis
- [x] **`pages/Pipeline.py`** — painel "⏱️ Tempo de reunião e fala por participante" (expander): `st.metric` duração + `st.dataframe` breakdown por participante (tempo, turnos, %); indicação de fonte (timestamp vs estimativa); sugestão de título do agente de ata com botão "Usar este título" + `update_meeting_title()` automático
- [x] **Fix ícone de pipeline** — `pages/Pipeline.py`: status `"skipped"` exibe `⏭️` em vez de `❌`; `❌` reservado exclusivamente para erros reais (resolve ambiguidade reportada em `duvidas/gerar_insights.md`)
- [x] **`core/cost_model.py`** (novo) — `ModelPricing`, `AgentTokenProfile`, `ScenarioConfig`, `ScenarioResult`; `PRICING_CATALOG` (17 modelos / 6 provedores: DeepSeek, Claude, OpenAI, Groq, Gemini, Grok); `DEFAULT_TOKEN_PROFILES` (9 agentes com perfis heurísticos e `context_multiplier`); `project_cost(scenario, word_count, catalog) → ScenarioResult` — cálculo 100% local, sem LLM, sem rede (NF-1, NF-3); `get_effective_catalog(overrides)`, `cheapest_model()`, `best_quality_model()`, `estimate_tokens()`
- [x] **`pages/CostBenefitScenarios.py`** (novo) — página no grupo Análise; layout coluna única; status de cenário ativo no topo com badge + ações; Cenário Default somente-leitura (espelha provider/modelo global atual); editor de até 5 cenários em tabs com nome editável, 3 presets (Custo Mínimo / Qualidade Máx. / Balanceado), selectboxes provedor→modelo por agente com custo parcial via `st.metric`; botão "Aplicar ao Pipeline" por aba; backup de cenário anterior + "Restaurar 'X'" + "Voltar ao Default"; gráfico barras empilhadas custo/agente; scatter Custo×Qualidade com zona ideal; tabela resumo; catálogo editável via `st.data_editor` persistido em `session_state["cost_catalog_overrides"]`
- [x] **`agents/base_agent.py`** — `_call_llm()`: lê `st.session_state["scenario_assignments"]` (dict `agent_name→model_id`) e sobrescreve `model` antes do cache lookup; fail-open se ausente (NF-5); não altera `client_type` nem `api_key`
- [x] **`pages/Pipeline.py`** — badge informativo `st.info` quando `scenario_assignments` ativo (nome do cenário + até 4 pares agente:modelo)
- [x] **`core/session_state.py`** — `asst_embed_provider` default corrigido de `"Google Gemini"` para `"OpenAI"` (alinha com configuração de uso real)

### PC19 — Concluído (v4.20+ / 2026-05-19)
- [x] **`services/llm_telemetry.py`** — `TelemetryRecord` dataclass; `LLMTelemetry` (async daemon thread, fail-open Supabase write); `run_benchmark_call()` (timed raw LLM call, sem cache/PII/hub); `BENCHMARK_TASKS` (5 agentes: bpmn/minutes/requirements/sbvr/bmm com prompts representativos); `TRANSCRIPTS` (short ~150w / medium ~350w); `_telemetry` singleton
- [x] **`agents/base_agent.py`** — `_call_openai`/`_call_anthropic` retornam `(raw, tokens_in, tokens_out)`; `_call_llm` desempacota e registra `TelemetryRecord` por chamada (latency_ms, input/output tokens, provider, model, long_context, from_cache=False, benchmark_run=False); thinking mode: `reasoning_effort` → `extra_body={"thinking":{"type":"enabled"}}` + sem temperature
- [x] **`pages/LLMBenchmark.py`** — duas abas: (1) 🧪 Benchmark On-Demand: multi-select providers (só configurados) + agentes, N runs slider, seleção de transcrição, save_to_db checkbox, progress bar por tarefa, tabela de resultados + bar charts de latência e throughput; (2) 📊 Telemetria Real: filtros (provider/agente/dias/cache/benchmark), 4 KPIs, 4 sub-tabs: Latência (box plot p5/p25/mediana/p75/p95), Throughput (bar agrupado tokens/s), Histórico (line chart por dia), Heatmap (agente × provider latência mediana)
- [x] **`setup/supabase_migration_llm_telemetry.sql`** — tabela `llm_telemetry` + 4 índices + `delete_old_llm_telemetry()` PL/pgSQL (90 dias)
- [x] **`app.py`** — `pages/LLMBenchmark.py` registrado em Sistema group (icon ⚡)

### PC15 — Concluído (v4.20+ / 2026-05-19)
- [x] **`pages/Orientacoes_Assistente.py`** — guia completo de ferramentas do Assistente em Ajuda → 💬 Ferramentas do Assistente; dark-navy CSS; modos Assistente (tool-use/RAG) vs Análise Autônoma; 6 abas: Reuniões / Análise / Gráficos / Calendário / Knowledge Hub / Admin; 33 tool cards com badge colorido por categoria (consulta/escrita/grafico/calendario/admin) + descrição + 2–3 exemplos de prompt; registrada em `app.py` Ajuda entre "Como Iniciar" e "Glossário"

### PC14 — Concluído (v4.20+ / 2026-05-19)
- [x] **Cache hit indicator no Pipeline** — `st.status()` label exibe `⚡ N cache hit(s)`; banner verde pré-abas com tokens economizados + ~USD; `st.metric(help=...)` ⓘ explica cache semântico + PII token_map + link para ROI-TR → Cache LLM
- [x] **Ferramentas do Assistente para cache** — `get_cache_stats(agent_name?)`: Markdown table com entradas/hits/tokens/USD + breakdown por agente; `clear_llm_cache(agent_name?)`: invalida cache (admin only); wired em schema OpenAI/Anthropic, `_TOOL_CATEGORIES`, `_ADMIN_TOOLS`, dispatcher

### PC13 — Concluído (v4.20+ / 2026-05-19)
- [x] **Semantic LLM Cache** — `services/semantic_cache.py`: `SemanticCache` com SHA256(provider|model|system|sanitized_user); armazena raw output pré-desanitize; na recuperação aplica `desanitize(cached_raw, token_map_atual)` — PII-safe entre sessões; `get_stats()` + `invalidate()`; fail-open em todo lugar
- [x] **`setup/supabase_migration_llm_cache.sql`** — tabela `llm_cache` + índices + `delete_expired_llm_cache()` PL/pgSQL
- [x] **`agents/base_agent.py`** — `_call_llm()` integra cache antes de chamar API; armazena resultado após; `skip_cache=True` param; `hub.meta.cache_hits` + `tokens_saved` rastreados
- [x] **`core/knowledge_hub.py`** — `cache_hits` + `tokens_saved` em `SessionMetadata`; migrate() guard v4.25
- [x] **`pages/MeetingROI.py`** — nova aba "💾 Cache LLM": 4 KPIs, breakdown por agente, economia USD estimada, limpar cache (admin)

### PC12 — Concluído (v4.20+ / 2026-05-18–19)
- [x] **Phase F — AgentQuerySummarizer** — `agents/agent_query_summarizer.py` + `skills/skill_query_summarizer.md`; 4 perspectivas (Executivo, Técnico, Gestor, Conformidade); `QuerySummaryModel` + `PerspectiveSummary` em `knowledge_hub.py`; `ui/tabs/query_summary_tab.py` (icon + headline blockquote + highlights + open_items + actions); Orchestrator Step 6d; sidebar checkbox + re-run button; export Markdown; `migrate()` guard v4.24; default False
- [x] **Multi-sphere SBVR (Fase G)** — `BusinessRule` com `sphere`, `sphere_owner`, `bmm_policy_ref`, `speaker_quote`; `RequirementItem` com `business_rule_refs: list` + `sphere: Optional[str]`; `_VALID_SPHERES` frozenset; **SBVR reordenado para Step 2.5** (antes de Minutes+Requirements) para rastreabilidade de BR-IDs; `skill_sbvr.md` atualizado com tabela de esferas; `sbvr_tab.py` reescrito com métricas, agrupamento por esfera, filtro, speaker_quote, bmm_policy_ref, requisitos vinculados
- [x] **Glossário** — `pages/Orientacoes_Glossario.py`; 6 abas de categoria (BPMN/Process, Requisitos, Linguagem de Negócio, Qualidade, Tecnologia, Metodologia) + aba Referências (16 specs/libs); CSS dark-navy matching outras páginas Orientações; registrado em `app.py` Ajuda após "Como Iniciar"
- [x] **Cobertura completa de reprocessamento** — `run_knowledge_extractor` + `run_query_summarizer` adicionados aos 3 caminhos: `core/batch_pipeline.py _reprocess_one()`, `core/assistant_tools.py reprocess_meeting_full()`, `pages/BatchRunner.py` (seção batch + expander reprocessar); UI expandida para 12 colunas com 🕸️ Grafo + 🔎 Sumário

### PC79 — Concluído (v4.60 / 2026-06-26)

**Precisão do Assistente — keyword search robusto + regras de paginação/contagem**

- [x] **`core/assistant_tools.py` — `get_requirements` keyword search**:
  - Corrigida busca por `req_number`: comparação type-safe (`int` e `str`) — resolve bug onde `REQ-229` não era encontrado quando `req_number` era string no banco
  - Adicionado `cited_by` ao filtro de keyword — permite buscar "quem sugeriu" diretamente
- [x] **`agents/agent_assistant.py` — `_SYSTEM_TOOLS_TEMPLATE`**: nova seção "BUSCA E LISTAGEM DE REQUISITOS" com regras explícitas:
  - Fluxo de busca por REQ-NNN (keyword → cited_by → fallback ReqTracker)
  - Paginação: nunca somar itens de uma página como total; iterar `page+1` se houver mais
  - Autoria: `cited_by` disponível no retorno de `get_requirements(keyword="REQ-NNN")`
  - Reforço: `count_artifacts` obrigatório para totais, nunca `get_requirements` sem filtros
- [x] **`melhorias/estrategia_para_precisao.md`** → `melhorias/arquivados/`

---

### PC78 — Concluído (v4.59 / 2026-06-26)

**Housekeeping — arquivamento de 22 propostas implementadas**

- [x] `git mv` de 22 arquivos de `melhorias/` → `melhorias/arquivados/` (histórico preservado)
- [x] Propostas arquivadas: BPMN (skill v7.9, method-and-style, AgentBPMNReviewer), Assistente (xlsx, UI, chat export, 4 novas ferramentas), Glossário, ATA Engine, Knowledge Hub Persistente, SemanticCache + ContextAnalyzer, migração DeepSeek v4-flash, ClaudeCodeWorkflow, BMIF Strategic Plan
- [x] Mantidos em `melhorias/`: propostas futuras não implementadas (Jira, LGPD, multi-esfera 2.0, MCP/A2A, PII, Grok multi-agent, precisão Assistente)

---

### PC77 — Concluído (v4.59 / 2026-06-26)

**AgentValidator — 5ª dimensão de scoring: semântica de nomenclatura BPMN**

- [x] **`agents/agent_validator.py`** — nova dimensão `semantic` (0–10, pure Python, sem LLM):
  - Constantes: `_ACTIVITY_VERBS` (23 verbos PT), `_GENERIC_START_NAMES`, `_GENERIC_END_NAMES`
  - Penalizações: gateway com verbo de atividade (−2.5/viol), task terminando com `?` (−2.0), evento Start/End genérico (−1.0)
  - `_score_semantic(steps) → tuple[float, int]`; peso via `weights.get("semantic", 5)` — fail-open
- [x] **`core/knowledge_hub.py`** — `BPMNValidationScore`: campos `semantic: float` + `n_semantic_violations: int`; `migrate()` guard v4.59
- [x] **`core/session_state.py`** — `bpmn_weights` default inclui `"semantic": 5`
- [x] **`ui/sidebar.py`** — slider "Semântico" adicionado ao bloco de pesos do torneio
- [x] **`modules/i18n.py`** — chave `"semantic"` em pt-BR e en-US
- [x] **`tests/test_agent_validator.py`** — 9 novos testes em `TestSemantic`; constantes `WEIGHTS_*_ONLY` atualizadas com `"semantic": 0`

---

### PC76 — Concluído (v4.58 / 2026-06-26)

**skill_bpmn_reviewer v1.1 — emojis na tabela de violações**

- [x] `skills/skill_bpmn_reviewer.md` — tabela de violações com emojis de severidade

---

### PC75 — Concluído (v4.58 / 2026-06-26)

**AgentBPMNReviewer completo — apply_bpmn_corrections + agent LLM + DB tables**

- [x] **`agents/agent_bpmn_reviewer.py`** (novo) — agente LLM standalone (padrão `_MinimalHub`):
  - `review(bpmn_xml, process_name)` → str — relatório Markdown completo em 4 fases via `skill_bpmn_reviewer.md`; chama `_call_llm` diretamente (resposta Markdown, não JSON)
  - `apply_corrections(bpmn_xml, process_name, corrections)` → dict | None — aplica lista de correções cirúrgicas; prompt focado em JSON puro (retorna formato AgentBPMN flat); usa `_call_with_retry` (3 tentativas)
- [x] **`apply_bpmn_corrections(process_name, corrections, version_notes?)`** — ferramenta admin no Assistente:
  - Obtém XML atual do banco; chama `AgentBPMNReviewer.apply_corrections()`; constrói `BPMNModel` via `AgentBPMN._build_model()` + `_enforce_rules()` + `_generate_bpmn_xml()`; salva como nova versão via `save_bpmn_new_version()`; loga em `bpmn_review_log` (fail-open)
  - Ações suportadas: `convert_to_task`, `convert_to_gateway`, `rename`, `add_edge_labels`, `add_missing_gateway`
- [x] **`setup/supabase_migration_bpmn_review.sql`** — 2 novas tabelas:
  - `bpmn_process_descriptions`: armazena descrição Markdown por processo/versão (`process_id FK`, `version_id FK nullable`, `description_md`, `generated_by`)
  - `bpmn_review_log`: audit log de correções (`project_id`, `process_name`, `version_before/after`, `issues_found/corrected`, `review_report jsonb`, `user_approved`)
- [x] **`core/project_store.py`** — `save_bpmn_review_log()` fail-open; insere em `bpmn_review_log`
- [x] **`core/assistant_tools.py`** — schema OpenAI, categoria "admin", `_ADMIN_TOOLS`, executor `apply_bpmn_corrections()`, dispatch
- [x] **Fluxo completo implementado:** `suggest_bpmn_corrections` → usuário confirma → `apply_bpmn_corrections` → nova versão BPMN salva → log de auditoria

---

### PC74 — Concluído (v4.57 / 2026-06-26)

**BPMN + Assistente — describe_bpmn_process + suggest_bpmn_corrections + Rule 4 + process_type/description_md**

- [x] **`describe_bpmn_process(process_name)`** — gera descrição textual estruturada do processo a partir do XML BPMN; parse puro Python (`xml.etree`); extrai participantes (pools/lanes), fluxo numerado em ordem topológica (BFS), rótulos de saída de gateways, resultados possíveis (endEvents); escopo "consulta"
- [x] **`suggest_bpmn_corrections(process_name)`** — plano de correção estruturado sem aplicar alterações; detecta: gateways com verbos de atividade → propõe conversão para userTask + novo gateway; tasks com `?` → propõe conversão para gateway; XOR sem labels → sugere "Sim"/"Não" ou "Caminho N"; eventos genéricos → sugere nomes de trigger/resultado; escopo "consulta"
- [x] **`core/assistant_tools.py`** — schemas OpenAI, categorias, implementações e dispatch para as 2 novas ferramentas
- [x] **Rule 4 (`_enforce_rules`)** — XOR gateways com arestas sem rótulo recebem labels padrão automaticamente: 2 saídas → "Sim"/"Não"; N saídas → "Caminho 1..N" (só preenche lacunas, não sobrescreve labels existentes)
- [x] **`BPMNModel.process_type`** — campo opcional `"flat"|"hierarchical"|"collaboration"` (LLM-supplied via skill v7.9); `migrate()` guard v4.57
- [x] **`BPMNModel.process_description_md`** — campo Markdown para descrição textual do processo (AgentBPMN ou revisor); `migrate()` guard v4.57

---

### PC73 — Concluído (v4.56 / 2026-06-26)

**skill_bpmn v7.9 + AgentBPMNReviewer + review_bpmn_diagram + save_bpmn_revision**

- [x] **`skills/skill_bpmn.md` v7.9** — 11 melhorias de prompt engineering: CKF Injection Awareness, Passo 0.5 (padrões estruturais), §1.1 Lane vs Ator Descartável, §1.2 Regra do Nome Exato, Rótulo Refletido (traceability label), Data Objects §8.5.1, §4.1 Detecção de Gateways Faltantes, Join Flexível de XOR, checklist "Gateway NÃO tem verbo", Passo 7 (Validação de Cobertura + Regra do Espelho), `process_type` no JSON de saída
- [x] **`skills/skill_bpmn_reviewer.md`** (novo) — skill completo do AgentBPMNReviewer: 4 fases (parse → auditoria 25 regras → reelaboração textual → JSON); checklists: nomenclatura (R1–R7), gateway (R8–R12), tasks (R13–R16), fluxos (R17–R20), pools/lanes (R21–R23), hierarquia (R24–R25)
- [x] **`review_bpmn_diagram(process_name)`** — auditoria pura Python via `xml.etree`; detecta: gateways com verbos, tasks como gateways, eventos genéricos, lanes genéricas, fluxos XOR sem rótulo, elementos órfãos; score /10; escopo "consulta"
- [x] **`save_bpmn_revision(process_name, bpmn_xml, ...)`** — salva nova versão via `save_bpmn_new_version`; persiste `process_description` em `bpmn_processes` (best-effort); escopo "admin"

---

### PC72 — Concluído (v4.55 / 2026-06-26)

**Assistente — 3 novas ferramentas de edição de req/SBVR**

- [x] **`update_requirement_text(req_number, new_description, new_title, change_note)`** — atualiza título e/ou descrição completa de um requisito pelo número; registra versão em `requirement_versions` com `change_type='text_edit'`; resolve o caso de aspas simples que `apply_text_correction` não suportava; escopo "escrita"
- [x] **`update_sbvr_rule(rule_id, new_statement, new_rule_type)`** — atualiza enunciado de uma regra SBVR pelo ID (ex: BR002, BR006); escopo "escrita"
- [x] **`update_sbvr_term_by_id(term_id, new_definition, new_category)`** — atualiza termo SBVR pelo UUID; necessário quando múltiplos termos têm o mesmo nome; escopo "escrita"
- [x] **`core/assistant_tools.py`** — schemas OpenAI, categorias, implementações e dispatch para as 3 ferramentas

---

### PC71 — Concluído (v4.54 / 2026-06-26)

**Assistente — novas ferramentas: resolve_contradiction + delete_contradiction**

- [x] **`resolve_contradiction`** — marca contradição como resolvida (ou esclarecida/descartada); identifica por busca parcial na descrição; registra `resolution_note` + `resolved_by` + novo `status`; chama `knowledge_store.resolve_contradiction()`; escopo "escrita" (todos os perfis)
- [x] **`delete_contradiction`** — exclua permanentemente uma contradição; requer `confirm=true`; identifica por busca parcial; delete direto via Supabase; escopo "escrita"
- [x] **Proteção multi-match** — se a query ambígua retorna >1 contradição, lista até 5 candidatos e pede refinamento; sem exclusão/resolução acidental
- [x] **`core/assistant_tools.py`** — schemas OpenAI (+ dispatch), permissões no `_TOOL_PERMISSION_MAP`, implementações `resolve_contradiction()` + `delete_contradiction()`
- [x] **`update_requirement_status`** — já existia (PC anterior); confirmado funcional — trigger: "Evolua o status do requisito X para Y"

---

### PC70 — Concluído (v4.53 / 2026-06-26)

**skill_bpmn.md v7.8 — Todo pool em colaboração deve ter startEvent/endEvent explícitos**

- [x] **Causa raiz** — Example C, pool_1 (Cliente) só tinha `sendTask`/`receiveTask` sem `noneStartEvent`/`noneEndEvent` → gerador injetava "Início"/"Fim" genéricos violando a regra de nomenclatura
- [x] **Example C — pool_1 atualizado** — adicionados S00 (`noneStartEvent` = "Necessidade de Crédito Identificada") e S03 (`noneEndEvent` = "Resultado de Crédito Recebido"); edges atualizadas: S00→S01→S02→S03; message_flows inalterados (continuam em S01/S02)
- [x] **Nova regra em Passo 3** — "REGRA CRÍTICA — Formato colaboração: todo pool deve ter Start Event e End Event explícitos"; estrutura mínima S00 (noneStartEvent) … Sm (noneEndEvent) documentada com exemplos ✓/✗
- [x] **Nota de rodapé atualizada** — observações do Example C reforçam que `sendTask`/`receiveTask` NÃO dispensam os eventos explícitos
- [x] **`skills/skill_bpmn.md`** — versão v7.8

---

### PC69 — Concluído (v4.52 / 2026-06-26)

**BPMN — fix validação cega a steps/edges sob sub-chave "process"**

- [x] **Causa raiz identificada** — `_build_model_multi` lê steps/edges de `pool["process"]["steps"]` mas a validação lia de `pool["steps"]` (top level); quando o LLM aninha steps sob `"process"` a validação via `_p.get("steps")` retornava `[]`, `_p_steps = 0`, condição `_p_steps > 2` ficava `False` → validação nunca disparava → pool 2 com 15 steps e 0 edges (sequence flows ausentes) passava intacto
- [x] **Fix 1 — Validação** (`_bpmn_call_with_retry`) — helper `_pf(p, key)` busca o campo primeiro no top-level do pool, depois em `pool["process"]`; total_steps/total_edges e per-pool check usam `_pf` em vez de `_p.get()`
- [x] **Fix 2 — Model builder** (`_build_model_multi`) — `raw_steps/edges/lanes` agora usam `proc.get() or pool_data.get() or []`; aceita tanto o formato `pool.process.steps` quanto `pool.steps` sem perder dados
- [x] **`agents/agent_bpmn.py`** — ambas as correções aplicadas

**Problema resolvido:** "15 nós isolados — no incoming or outgoing edges" no pool "Grupo Meridional S.A." — o LLM retornava steps corretamente aninhados sob `"process"` mas sem edges (ou edges no nível errado); validação era cega a esse caso e modelo ficava sem sequenceFlows.

---

### PC68 — Concluído (v4.51 / 2026-06-25)

**Pipeline.py — Fix widget-tree desync (setIn index N, should be between [0, 0])**

- [x] **Root cause identified** — during background-agent polling, `st.rerun()` at line 521 stopped Python execution before the hub section (tabs), leaving the client with a "no-tabs" widget tree. After 660 s of 1-second reruns, the WebSocket desync caused `setIn index 134 (should be between [0, 0])` on completion, resulting in a blank screen
- [x] **Fix: hub section moved BEFORE rerun handler + polling block** — hub now renders on every Streamlit render cycle (including during polling), keeping the widget tree structurally identical throughout; the polling info (`st.info`) appears at the bottom of the page and disappears cleanly when the agent completes
- [x] **sleep(2) instead of sleep(1)** — halved polling frequency to reduce WebSocket stress during extended LLM calls (LangGraph + PC67 validation can run 10+ min)
- [x] **`pages/Pipeline.py`** — reordered: deferred messages → hub section → rerun handler → polling block → footer

**Problema resolvido:** re-execução do agente BPMN (com PC67 validações + LangGraph retries) rodava em múltiplos ciclos longos; ao final o cliente tinha widget-tree desync e mostrava tela em branco.

---

### PC67 — Concluído (v4.50 / 2026-06-25)

**BPMN — validação de message_flows órfãos + skill v7.7**

- [x] **`agents/agent_bpmn.py` — validação de message_flows órfãos** — após validação de edges por pool, verifica que todo `endMessageEvent` e `sendTask` em cada pool tem uma entrada correspondente em `message_flows` com `source.pool/step` apontando para ele; se qualquer um estiver sem message_flow → `ValueError` com lista dos elementos órfãos → retry com `_retry_suffix` semântico que preserva multi-pool e cita os elementos específicos; `endMessageEvent` sem message_flow = evento mudo (não comunica nada)
- [x] **`skills/skill_bpmn.md` v7.7 — Instrução Final** — adicionada verificação obrigatória pré-retorno: contar N `endMessageEvent` + N `sendTask` que iniciam comunicação → deve haver N entradas cobrindo-os em `message_flows`

**Problema resolvido:** o LLM gerava endMessageEvents corretos no banco (recusa automática, recusa manual, aprovação) mas omitia os message_flows correspondentes para o cliente — a coreografia ficava incompleta, p1_S03 (receiveTask) sem nenhum message_flow de entrada.

---

### PC66 — Concluído (v4.49 / 2026-06-25)

**skill_bpmn v7.6 — Exemplo C reescrito + regras de colaboração/gateways/lanes fortalecidas**

- [x] **Exemplo C reescrito completamente** — causa raiz identificada: o exemplo anterior tinha (1) aresta combinando "≥700 ou <500" em uma só saída de gateway, ensinando o LLM que 2 branches bastam para 3 intervalos; (2) único `endMessageEvent "Notificar Cliente"` servindo tanto recusa quanto aprovação; (3) 2 lanes apenas; (4) nome "Banco Meridional" contraditório com a regra de nomenclatura na linha 67. Novo Exemplo C: gateway S04 com 3 saídas distintas ("< 500", "500-699", ">= 700"), gateway S07 com 2 saídas fechadas (Não → End Event específico; Sim → Formalizar), 3 End Events distintos nomeados por resultado, 6 message flows cobrindo toda comunicação, 2 lanes, pool "Banco ABC" (nome fictício genérico)
- [x] **Colaboração obrigatória — triggers explícitos** — adicionado após tabela flat/pools no Passo 1: lista de sinais que tornam pools OBRIGATÓRIO (entidade externa, órgão nomeado, comunicação interorganizacional, troca formal de docs); regra de desempate "quando em dúvida → sempre prefira pools"; "formato flat é PROIBIDO quando há entidade externa"
- [x] **Lanes obrigatórias** — adicionado após regra de ordenação de lanes: "Lanes são OBRIGATÓRIAS quando o pool tem 2+ papéis com responsabilidades distintas — nunca omita lanes para simplificar"
- [x] **Density rule por pool** — adicionado ao Passo 0: "em formato pools, a contagem é feita por pool — cada pool aplica a regra de densidade independentemente"
- [x] **Gateways obrigatórios** — adicionado após regra de labels no Passo 4: triggers explícitos para quando gateway é obrigatório (threshold numérico com N intervalos → N saídas, alçada escalonada → N saídas, aprovação/rejeição em pontos distintos → gateways separados); "nunca combine intervalos distintos numa única aresta"
- [x] **Checklist** — novo item: "Em formato pools, message_flows cobre TODOS os pontos de comunicação interorganizacional? Pool sem message_flow = pool isolado (erro)"

**Causa raiz do problema:** o Exemplo C era o principal professor do LLM e ensinava padrões errados — gateway com branches combinadas, End Event único para resultados distintos, poucas lanes, nome contraditório.

---

### PC65 — Concluído (v4.48 / 2026-06-25)

**BPMN — prevenção de format escape: detecção proativa de colaboração + hints separados por tipo de erro**

- [x] **`agents/agent_bpmn.py` — detecção proativa de colaboração** — calcula `_collaboration_expected` combinando dois sinais: `hub.nlp.actors >= 2` (NLP estruturado) + scan de keywords no transcript (≥2 hits: cliente, fornecedor, banco, bureau, serasa, quod, receita federal, parceiro, externo, contratante, contratado, prestador, tomador); quando positivo, injeta diretiva `## MANDATORY FORMAT — COLLABORATION` com template multi-pool no system prompt ANTES da chamada LLM
- [x] **Hints separados por tipo de erro em `_bpmn_call_with_retry`** — `ValueError` (validação semântica: pool sem edges) → `_retry_suffix` semântico que preserva estrutura multi-pool e cita o erro específico; nunca menciona flat format quando `_collaboration_expected`; `KeyError` (parse JSON) → `_flat_hint` contextualizado (quando colaboração esperada, proíbe explicitamente formato flat)
- [x] **`_flat_hint` context-aware** — quando `_collaboration_expected`, o hint de parse também proíbe flat; quando não, mantém comportamento original (escolha baseada no transcript)
- [x] **Detecção de format escape + logging** — após `_build_model()`, se colaboração era esperada mas LLM retornou flat: `WARNING [AgentBPMN] Format escape detected`; registrado em `execution_log["collaboration"]` com `expected`, `nlp_actors`, `keyword_hits`, `format_escape`
- [x] **`execution_log["collaboration"]`** — novo bloco de diagnóstico adicionado ao log de execução para rastreabilidade de fugas de formato

**Problema resolvido:** o hint `_flat_hint` era injetado em TODOS os retries (incluindo `ValueError` de validação semântica); o LLM explorava a menção de flat format para escapar do per-pool check, gerando diagramas sem pools/gateways/raias que passavam silenciosamente em todas as validações.

---

### PC64 — Concluído (v4.47 / 2026-06-24)

**Assistente — tool `compare_meeting_transcripts` (detecção de duplicatas)**

- [x] **`core/assistant_tools.py`** — nova tool `compare_meeting_transcripts(meeting_numbers: list[int])`: compara pares de transcrições por similaridade de texto; score ponderado = `char_sim × 0.50 + jaccard × 0.35 + len_ratio × 0.15`; veredictos: DUPLICATA (≥80%), MUITO SIMILAR (≥60%), PARCIALMENTE SIMILAR (≥35%), DISTINTOS; evidências: até 4 trechos comuns com ≥80 chars
- [x] `SequenceMatcher` char-level (amostra 12k chars), Jaccard sobre palavras >3 chars sem stopwords PT, razão de comprimento; aceita 2–5 reuniões; schema + categoria `"consulta"` + roteamento duplo (non-admin + admin dispatch)

---

### PC63 — Concluído (v4.46 / 2026-06-24)

**Renomear título de reunião — UI + assistente**

- [x] **`pages/Pipeline.py`** (Modo B) — expander "✏️ Renomear reunião" com `text_input` + botão "💾 Salvar"; chama `update_meeting_title(meeting_id, new_title)`; atualiza `st.session_state["load_meet_select"]` para manter seleção sincronizada; atualiza `hub.minutes.title` se disponível
- [x] **`core/assistant_tools.py`** — nova tool `rename_meeting(meeting_number, new_title)`: localiza reunião via `_find_meeting`, chama `update_meeting_title`, invalida cache; retorna diff de título; categoria `"escrita"` + roteamento duplo

---

### PC62 — Concluído (v4.45 / 2026-06-24)

**Assistente — tool `render_mermaid_code` (geração de diagramas Mermaid)**

- [x] **`core/assistant_tools.py`** — nova tool `render_mermaid_code`: o LLM gera código Mermaid válido como parâmetro da chamada; o executor faz `_pending_widgets.append({type: mermaid, code: ...})` para renderização inline no chat; funciona com qualquer tipo Mermaid (`flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, etc.)
- [x] Schema registrado em `get_tool_schemas_openai()` (Anthropic derivado automaticamente); categoria `"consulta"` em `_TOOL_CATEGORIES`; roteamento no executor
- **Diferença de `show_mermaid_diagram`:** essa tool busca Mermaid salvo no banco para uma reunião existente; `render_mermaid_code` renderiza qualquer Mermaid gerado sob-demanda pelo LLM — inclui diagramas de sequência, estado, etc.

---

### PC61 — Concluído (v4.44 / 2026-06-24)

**UI — diagnóstico estrutural BPMN não roda em hub carregado do DB**

- [x] **`ui/tabs/bpmn_tabs.py`** — guard `if not hub.bpmn.steps:` envolve chamada ao `validate_bpmn_structure`; quando hub carregado do banco (`steps` vazio), exibe nota informativa em vez do falso "✅ Nenhum problema estrutural detectado"
- **Root cause:** `load_meeting_as_hub` persiste apenas `bpmn_xml`, não os campos estruturados `steps/edges/lanes`; o validador iterava sobre lista vazia e reportava zero issues (falso positivo enganoso)

---

### PC60 — Concluído (v4.43 / 2026-06-24)

**BPMN skill — Exemplo C (colaboração multi-pool) + corrige retry hint**

- [x] **`skills/skill_bpmn.md`** — adicionado Exemplo C mostrando colaboração com 3 pools (Cliente, Banco Meridional com 2 lanes internas, Bureaus de Crédito); nota explícita: "Receita Federal/Serasa → pool separado, NUNCA lane interna do banco"; dá ao LLM template concreto para processos multi-organização
- [x] **`agents/agent_bpmn.py`** — `_flat_hint` no retry corrigido: antes proibia pools mesmo em processos multi-org; agora instrui o LLM a escolher o formato correto baseado na transcrição
- **Root cause da regressão:** LLM gerou flat format porque não havia exemplo de colaboração no skill; o retry hint reforçava o erro ao dizer "DO NOT use pools format"

---

### PC59 — Concluído (v4.42 / 2026-06-24)

**BPMN viewer auto-repair + Pass F waypoint ordering**

- [x] **`modules/bpmn_viewer.py` `preview_from_xml`** — aplica `reformat_bpmn_labels` automaticamente antes de renderizar; garante que XMLs carregados do banco (salvos antes das correções de waypoints) recebam reparos completos (Pass F + Pass G); elimina o problema de sequence flows saindo do centro dos elementos em todas as visualizações (pipeline, Diagramas.py, meetings existentes)
- [x] **`modules/bpmn_auto_repair.py` Pass F** — waypoints sintéticos inseridos com `_edge.insert(0, wp1)` / `_edge.insert(1, wp2)` ao invés de `_ET.SubElement`; garante que waypoints precedam qualquer `BPMNLabel` existente no `BPMNEdge` (exigência da spec BPMN DI); fix aplica-se tanto a `sequenceFlow` quanto a `messageFlow`
- **Root cause:** quando um edge tinha `BPMNLabel` filho mas zero waypoints (ex: `p2_sf_004`, `sf_end`), `SubElement` appendava os waypoints *após* o label; bpmn-js ignorava a ordem inválida e renderizava center-to-center; com `insert(0, ...)` os waypoints ficam antes do label e bpmn-js usa-os corretamente como border-to-border

---

### PC58 — Concluído (v4.41 / 2026-06-23)

**BPMN generator — resolução de conflito de coluna em retorno cross-lane**

- [x] **`modules/bpmn_generator.py` `_compute_layout`** — novo post-pass após `_align_parallel_branches`: detecta quando um flow cross-lane (source em lane diferente do target) aterrissa o target na mesma coluna que outro elemento na lane do target; empurra o target (e todos os seus successores downstream) uma coluna à frente; repete até estável
- **Root cause:** no padrão "detour cross-lane" (S04→S07[Gerente]→S08[Aurora] em paralelo com S04→S05→S06[Aurora]), `_assign_columns` atribuía S06 e S08 à mesma coluna 5 em Sistema AURORA; end event circle (36px) ficava centrado dentro do range horizontal da callActivity (160px), com apenas 20px de gap vertical — visual de sobreposição
- **Resultado após fix:** S06 fica sozinho na coluna 5 (width=36px); S08 vai para coluna 6; S05→S06 fica horizontal perfeito (ambos centrados em y=425 na lane); pool 2% mais largo mas layout muito mais limpo

---

### PC57 — Concluído (v4.40 / 2026-06-23)

**BPMN auto-repair — Pass D: threshold 70px + isenção de messageFlow**

- [x] **`modules/bpmn_auto_repair.py` Pass D** — threshold de detecção de diagonais alterado de 1px para 70px (`_DIAG_THRESHOLD = 70`, ≈ H_GAP); flows com `|Δy| ≤ 70px` são preservados (misalignment legítimo de lane por diferença de altura entre elemento: `endEvent` 36×36 vs `task` 90×90)
- [x] **Isenção de messageFlow em Pass D** — `_eid in _mf_map` pula o check diagonal; evita que Pass D remova os waypoints verticais recém-gerados por Pass F
- **Root cause identificada:** `p2_sf_004` (dy≈-12 por port offset de gateway), `p2_sf_006` (dy=-55), `p2_sf_008` (dy=-28) e `mf_1` (diagonal vertical entre pools) eram todos removidos pelo threshold=1px; cross-lane flows têm `|Δy| ≥ 100px`, logo threshold=70px distingue corretamente os dois casos

---

### PC56 — Concluído (v4.39 / 2026-06-23)

**BPMN auto-repair — Pass F cobre messageFlow BPMNEdges (bpmn-comparativa-v3)**

- [x] **`modules/bpmn_auto_repair.py`** — Pass F agora constrói `_mf_map` indexando `messageFlow` além de `sequenceFlow`; BPMNEdge de message flow sem waypoints recebe 2 waypoints sintéticos com roteamento vertical entre pools: `bottom-centre → top-centre` se source acima de target, reverso caso contrário; contadores e log separados por tipo

---

### PC55 — Concluído (v4.38 / 2026-06-23)

**BPMN — Start/End Event com nomes descritivos (bpmn-comparativa-001.md)**

- [x] **`core/knowledge_hub.py`** — novos campos `process_trigger: str` e `process_outcomes: list[str]` em `BPMNModel`; guard em `migrate()` v4.37
- [x] **`agents/agent_bpmn.py`** — `_build_model_flat()` parseia `process_trigger`/`process_outcomes` do JSON LLM; Rule 0 captura `title` dos steps de evento antes de removê-los (fallback sem mudança no JSON); `_generate_bpmn_xml_single()` usa `_start_name`/`_end_name` em vez de strings fixas "Início"/"Fim"
- [x] **`skills/skill_bpmn.md` v7.5** — schema flat atualizado com campos `process_trigger` + `process_outcomes`; regra de nomenclatura obrigatória com exemplos corretos/incorretos
- [x] **`modules/bpmn_diagnostics.py`** — `_build_single_process()` usa campos do `BPMNModel` em vez de hardcodes
- **Itens não implementados (justificativa):** Boundary Events (item 🔴 2 do doc) — generator tem placeholder PC27b; é trabalho arquitetural separado. Múltiplos End Events distintos — requer mudança no algoritmo de terminal detection do generator.

---

### PC54 — Concluído (v4.37 / 2026-06-23)

**BPMN — 3 melhorias de qualidade de análise (inspeção inspecao-bpmn.md)**

- [x] **`modules/bpmn_auto_repair.py` — import Pass 5 para nível de módulo** — `BPMNStep`/`BPMNEdge` importados uma única vez no topo do módulo com `try/except ImportError`; eliminado re-import a cada execução de `_repair_pool()` (melhora legibilidade + evita overhead repetido)
- [x] **`modules/bpmn_structural_validator.py` — Check 8: eventBasedGateway** — valida que todos os flows saintes de `eventBasedGateway` apontam para `intermediateTimerCatchEvent`, `intermediateMessageCatchEvent` ou `receiveTask`; emite `BPMNIssue("warning")` com referência à OMG BPMN 2.0 §13.2.1 para qualquer violação
- [x] **`modules/bpmn_diagnostics.py` — suporte multi-pool** — refatorado `_build_bpmn_process()` em dispatcher + `_build_single_process()` (lógica original) + `_build_collaboration_process()` (nova, itera `pool_models`, gera IDs com namespace por pool: `ev_start_{pool_id}`, `lane_{pool_id}_...`); diagnóstico BPMN agora funciona corretamente em modelos de colaboração

---

### PC53 — Concluído (v4.36 / 2026-06-22)

**BPMN auto-repair — 3 fixes de qualidade visual (Pass C/F/G)**

- [x] **Pass C — stagger 15 → 30 px** — flows em skip channel sobrepostos agora têm separação mínima de 30px (era 15px), evitando sobreposição visual mesmo em canais próximos ao topo do pool
- [x] **Pass F (novo) — waypoints sintéticos para edges vazias** — detecta `BPMNEdge` com zero waypoints (bug gerado pelo LLM ao não emitir `<bpmndi:BPMNEdge>` corretamente); constrói mapa `bpmnElement→Bounds` + mapa `sequenceFlow→(sourceRef,targetRef)`; adiciona 2 waypoints (right-center da shape source → left-center da shape target) garantindo que bpmn-js renderize o conector
- [x] **Pass G (novo) — separar saídas sobrepostas** — detecta grupos de flows com os mesmos 2 primeiros waypoints (mesma shape source, mesmo ponto intermediário); ordena por Y final (flows que vão para cima recebem offset negativo); aplica offset `±(n-1)/2 × 18px` em `wp[0].y` e `wp[1].y` para criar fan-out visível direto da shape source
- [x] **`core/assistant_tools.py`** — fix `get_bpmn_execution_log`: lê hub de `st.session_state.get("hub")` em vez de `self.hub` inexistente (AttributeError silencioso causava retorno "log não disponível")

---

### PC52 — Concluído (v4.35 / 2026-06-21)

**BPMN — Labels explicitamente centrados + Log de execução do agente**

**Fix label: centrado determinístico (modules/bpmn_generator.py + bpmn_auto_repair.py)**
- [x] **Causa raiz** — generator emitia `<bpmndi:BPMNLabel />` vazio confiando no auto-centering do bpmn-js; para `callActivity` o marcador "+" reduz a área de texto e o auto-centering falha; em re-render o texto aparece fora da forma
- [x] **`modules/bpmn_generator.py`** — constantes `_LBL_PAD_X=10` / `_LBL_PAD_Y=8` adicionadas; ambos os loops DI (single-pool e multi-pool) agora emitem `dc:Bounds` explícitos centrados para todo tipo task/subprocess/callActivity (events e gateways mantêm posicionamento externo)
- [x] **`modules/bpmn_auto_repair.py` — Pass B reescrito** — em vez de remover bounds, insere/corrige `dc:Bounds` centrados com `SNAP_TOL=1px` (atualiza apenas se fora de tolerância); cobre XML gerado por versões antigas sem bounds ou com bounds incorretos
- [x] **Resultado** — labels sempre dentro da forma, centrados, independentemente do tipo de task ou comportamento do viewer bpmn-js

**Log de execução do agente BPMN**
- [x] **`core/knowledge_hub.py`** — campo `execution_log: Optional[dict] = None` adicionado a `BPMNModel`; guard em `migrate()` (v4.35)
- [x] **`agents/agent_bpmn.py`** — log capturado após cada run: fonte (`llm_call`), provider/model/tokens/cache/latência, alterações de `_enforce_rules`, `repair_bpmn` passes, `reformat_bpmn_labels` passes, métricas (steps/edges/lanes/gateways/tipos de task, alert de títulos >35 chars)
- [x] **`core/rerun_handlers.py`** — fast-path rerun também atualiza `execution_log` com fonte `fast_path_rerun` e métricas do diagrama regenerado
- [x] **`core/assistant_tools.py`** — nova tool `get_bpmn_execution_log` (schema + executor + dispatch + categoria `consulta`); lê `hub.bpmn.execution_log` da sessão atual; formata relatório Markdown com todas as seções do log
- [x] **149 testes passando**, zero regressões

---

### PC51 — Concluído (v4.34 / 2026-06-21)

**BPMN — Fix visual: fluxos cruzados, skip sobrepostos e labels fora do pool**

- [x] **`modules/bpmn_auto_repair.py` — Pass C** — detecta flows com 4 waypoints e segmento horizontal no mesmo y-channel; os ordena por comprimento de span (menor fica, maiores recebem +15px por nível); elimina sobreposição visual de múltiplos skip flows em `reformat_bpmn_labels`
- [x] **`modules/bpmn_auto_repair.py` — Pass D** — detecta BPMNEdge com exatamente 2 waypoints diagonais (Δx≠0 e Δy≠0); remove waypoints → bpmn-js aplica roteamento Manhattan (L-shaped) que elimina cruzamentos em X ao convergir no mesmo alvo (padrão sf_end/sf_end_1)
- [x] **`modules/bpmn_auto_repair.py` — Pass E** — clamp de labels de sequências com y < 5 para y=5; impede labels invisíveis fora dos limites do pool (situação anterior: skip a y=10 → label a y=-6 não renderizado)
- [x] **`modules/bpmn_generator.py` — `_label_pos()`** — adicionado `max(5, ...)` para garantir label y ≥ 5 em todos os diagramas gerados; previne y=-6 em novos XMLs desde a geração
- [x] **Resultado** — labels de fluxos de sequência visíveis no viewer; flows de skip paralelos em canais distintos; flows diagonais convergentes deixam de se cruzar em X; "Ajustar Labels" agora relata as correções feitas em vez de falso positivo
- [x] **84 testes passando**, zero regressões

**`skill_bpmn.md` v7.4 — 4 correções de qualidade**

- [x] **Limite de caracteres harmonizado** — corpo e checklist alinhados em `≤ 35 chars` (antes: corpo dizia 30, checklist dizia 40, absoluto dizia 35 — 3 valores conflitantes)
- [x] **Critério de coesão para `callActivity`** — adicionado critério primário "coesão, não contagem": 4 critérios qualitativos de Bruce Silver (fase de negócio distinta, compreensível isoladamente, lógica interna complexa, terceirizável); proíbe explicitamente fragmentar só para reduzir contagem
- [x] **Boundary Events completos** — tabela do Passo 3c ampliada com `boundaryMessageEvent` ("cliente cancela durante análise") e `boundaryConditionalEvent` ("mudança de regulação em vigor"); adicionada distinção interrompente vs. não-interrompente
- [x] **Regra End Event ↔ label de gateway** — novo item no checklist do Passo 6: nome do End Event deve corresponder ao label do gateway que o precede (estilo de rastreabilidade visual de Bruce Silver)

---

### PC50 — Concluído (v4.33 / 2026-06-20)

**Pipeline — Background Thread para Reexecução de Agentes (fix "CONNECTING")**

- [x] **Causa raiz** — `handle_rerun()` era chamado sincronamente no script thread do Streamlit; LLM calls de 60–180s bloqueavam o WebSocket → browser mostrava "CONNECTING" / "Página sem Resposta"
- [x] **`core/rerun_handlers.py`** — removidos todos `st.info()` / `st.warning()` da função; substituídos por `messages.append((level, text))`; retorno alterado de `hub` para `(hub, messages)` — função agora thread-safe
- [x] **`pages/Pipeline.py`** — handler síncrono substituído por `threading.Thread(daemon=True)` + polling de 1s (`sleep(1)` + `st.rerun()`); WebSocket permanece vivo durante toda a execução; mensagens exibidas no main thread após conclusão
- [x] **Resultado** — reprocessamento de qualquer agente (especialmente BPMN) não causa mais "CONNECTING"; progresso visível com spinner "⏳ Executando agente…"

**Reexecução BPMN — Fix DeepSeek retornando conteúdo vazio**

- [x] **Causa raiz** — `_lg_skip_cache = True` adicionado a todos os agentes em `handle_rerun()` para forçar chamadas frescas à API; chamadas DeepSeek a partir do background thread retornavam conteúdo vazio (sem ScriptRunContext); resultado: `ValueError: No JSON object found in LLM response` após 3 tentativas
- [x] **`agents/base_agent.py`** — guard `and raw` em `_cache.set()`: respostas vazias nunca persistidas no cache semântico (previne cache poisoning)
- [x] **`agents/base_agent.py`** — `_call_openai` levanta `ValueError` descritivo com `finish_reason` quando conteúdo é `None`/vazio (diagnóstico mais claro em logs)
- [x] **`core/rerun_handlers.py`** — `_lg_skip_cache = True` removido de todos os 11 agentes; cache semântico reutilizado no rerun (respostas válidas do pipeline inicial disponíveis imediatamente); guard `and raw` garante que falhas anteriores não contaminem o cache
- [x] **Resultado** — reexecução do agente BPMN via DeepSeek restaurada; rerun retorna do cache quando disponível (instantâneo) ou faz chamada fresca quando necessário

**BPMN — Labels de Tasks Centrados (fix "Ajustar Labels")**

- [x] **Problema** — `reformat_bpmn_labels()` (Pass B) removia `dc:Bounds` deixando `<bpmndi:BPMNLabel />` vazio; bpmn-js renderizava label abaixo do shape em vez de centralizado; função reportava falso positivo "labels já centralizados" para shapes 160×90
- [x] **`modules/bpmn_auto_repair.py`** — Pass B reescrito: em vez de remover bounds, insere `dc:Bounds` explícitos centrados (`exp_lx = sx + PAD_X=10`, `exp_ly = sy + PAD_Y=8`, largura/altura inset); "já centralizados" agora só reportado quando todos os bounds estão dentro de 1px de tolerância (`SNAP_TOL`)
- [x] **`modules/bpmn_generator.py`** — ambos os geradores (single-pool e multi-pool) passaram a emitir `dc:Bounds` explícitos centrados para tasks desde a geração (`_LBL_PAD_X=10`, `_LBL_PAD_Y=8`), eliminando a necessidade de repair posterior

---

### PC49 — Concluído (v4.33 / 2026-06-20)

**BPMN — Gateway Port Assignment + Parallel Edge Gap (Melhoria A+B)**

- [x] **`_GATEWAY_TYPES`** — frozenset centralizado em `modules/bpmn_generator.py` com os 5 tipos de gateway
- [x] **`_compute_gateway_exits(flows, el_map, shapes)`** — para gateways com ≥2 saídas, distribui exits no right edge com Y-spread de ±12px (total 24px para n=3), ordenados por target-centre-Y; retorna `{flow_id: (exit_x, exit_y)}`
- [x] **`_route_waypoints(..., src_exit=None)`** — novo parâmetro opcional; quando fornecido, substitui o ponto de partida `(sx+sw, sy+sh/2)` sem alterar nenhuma das 7 estratégias de roteamento (cross-lane, backward, skip, default)
- [x] **Integração nos dois loops de DI** — `_build_di` (single-pool) e `_generate_bpmn_xml_multi` (multi-pool) computam `_gw_exits` antes do loop de flows e passam `src_exit` ao roteador
- [x] **Resultado visual** — 3 saídas do mesmo gateway passam de `y=235, 235, 235` para `y=223, 235, 247` (fanning); labels de condição ficam separados visualmente
- [x] **149 testes passando**, zero regressões

**BPMN Viewer — Parallel Asset Fetch (hotfix)**

- [x] **`modules/bpmn_viewer.py`** — `_load_bpmn_assets()` buscava 4 URLs sequencialmente (timeout 20s cada → até 80s bloqueando o servidor Python); isso causava "CONNECTING" no browser e "Página sem Resposta" no Windows
- [x] **Fix:** fetch paralelo via `ThreadPoolExecutor(max_workers=4)`; timeout reduzido 20s → 8s; `@lru_cache` movido de `_fetch_text` para `_load_bpmn_assets`; worst-case blocking 80s → 8s
- [x] **Resultado:** aba BPMN carrega normalmente após reprocessamento de agente

**CLAUDE.md — Redução de tamanho (37.8k)**

- [x] **CLAUDE.md** reduzido de 42.4k → 37.8k chars (−11%); 12 blocos de descrição de grupos de ferramentas do Assistente migrados para `claude_guideline/architecture_details.md §Tool list`
- [x] **`claude_guideline/architecture_details.md`** — nova seção `## Tool list — Assistente (core/assistant_tools.py)` com todos os 14 grupos de ferramentas

---

### PC48 — Concluído (v4.33 / 2026-06-19)

**Top-10 Ferramentas do Assistente — Fases 1–4** (`melhorias/top-10-ferramamentas-assistente.md`)

#### Fase 1 — Plantonista e Diagnóstico (pré-sessão)
- [x] **`sugestoes_plantonista`** — ferramenta não-admin em `core/assistant_tools.py`; analisa atas + requisitos pendentes + IBIS sem resposta + encaminhamentos vencidos; retorna lista priorizada de sugestões de ação para o usuário
- [x] **`diagnostico_projeto`** — ferramenta não-admin; varre cobertura de artefatos por reunião (BPMN, ata, DMN, IBIS, relatório), contagem de requisitos por status, score ROI-TR médio, pendências IBIS abertas; retorna relatório de saúde consolidado em Markdown
- [x] **Plantonista auto-trigger** — `pages/Assistente.py` exibe sugestões automaticamente ao abrir o Assistente com projeto ativo, sem precisar digitar comando

#### Fase 2 — Editor Estrutural
- [x] **`reordenar_requisitos`** — ferramenta de escrita; aceita `nova_ordem: array[str]` (lista de req_numbers) ou `agrupar_por: enum[tipo,prioridade]`; atualiza campo `sort_order` na tabela `requirements` via Supabase; retorna confirmação com nova sequência
- [x] **`inserir_secao_ata`** — ferramenta admin; aceita `meeting_number`, `titulo`, `conteudo`, `posicao: enum[inicio,fim,antes_X,apos_X]`; faz parse do `minutes_md`, injeta nova seção `## titulo`, persiste no Supabase
- [x] **`vincular_regra_debate`** — ferramenta de escrita; faz upsert na tabela `sbvr_ibis_links` (rule_id, ibis_question_id, relacao: justifica|contradiz|limita); cria rastreabilidade bidirecional SBVR ↔ IBIS
- [x] **`mesclar_reunioes`** — ferramenta admin; modo `preview=True` (padrão) mostra impacto antes de executar; modo execute reassigna requisitos/SBVR/BPMN/chunks da reunião absorvida, concatena atas, deleta meeting absorvida; parâmetro `razao` registrado nos metadados
- [x] **`sincronizar_calendario`** — ferramenta admin; lê action items das atas, cria eventos Google Calendar via `modules/calendar_client.py create_event()`; rastreia status em `calendar_sync_items`; suporta `direction: to_calendar|from_calendar|bidirectional`; parâmetros de janela de trabalho (`default_work_start/end`)
- [x] **Migration SQL** — `setup/supabase_migration_fase2.sql`: coluna `sort_order INTEGER` em `requirements`; tabela `sbvr_ibis_links` (project_id, rule_id, ibis_question_id, relacao, created_at); tabela `calendar_sync_items` (project_id, meeting_id, action_text, google_event_id, sync_direction, status, last_sync_at); ambas com `ENABLE ROW LEVEL SECURITY` (service_role ignora RLS; bloqueia anon/authenticated); índices em project_id e meeting_id — **migration executada com sucesso**

#### Fase 3 — Rastreabilidade, What-If e Conformidade
- [x] **`mapa_rastreabilidade`** — ferramenta de consulta; coordena `search_transcript()`, `list_bpmn_processes()`, `get_sbvr_rules()`, `_load_ibis_questions()` para construir mapa Markdown de rastreabilidade de um requisito ou tópico; flags booleanas `include_transcript|bpmn|sbvr|ibis` controlam escopo; sem SQL novo (usa tabelas existentes)
- [x] **`simular_cenario`** — ferramenta de consulta; recebe `descricao` + `requisitos_afetados: array` + `restricoes: object`; agrega requisitos + regras SBVR + contradições do KnowledgeGraph; chama LLM via `_llm_call()` para análise de impacto; fallback heurístico automático se LLM falhar; sem SQL novo
- [x] **`verificar_conformidade`** — ferramenta de consulta; keyword-match de títulos/descrições de requisitos contra conteúdo de documento (`meeting_documents` + `document_chunks`); classifica Coberto/Parcial/Não Mapeado por threshold configurável; retorna relatório de lacunas; suporta `mode: keyword|llm`; sem SQL novo

#### Fase 4 — Geração de Documentos Estratégicos
- [x] **`sugerir_processos`** — ferramenta de consulta; single-linkage clustering de questões IBIS por overlap Jaccard de keywords; filtra clusters com ≥ `min_reunioes` reuniões; verifica contra BPMNs existentes para evitar duplicatas; infere etapas das alternativas IBIS escolhidas; sem LLM (algoritmo determinístico)
- [x] **`gerar_deck_executivo`** — ferramenta de consulta; coleta BMM, CKF, breakdown de requisitos, processos BPMN, ROI-TR, encaminhamentos; chama LLM para gerar deck de 7 slides em Markdown (`incluir_secoes` configurável); suporta `tema_cores` para personalização visual
- [x] **`gerar_project_charter`** — ferramenta de consulta; agrega todos os artefatos do projeto; chama LLM para gerar Project Charter formal PMO em Markdown (10 seções); flags booleanas `incluir_riscos|cronograma|stakeholders|escopo`
- [x] **`_llm_call()` helper** — método privado compartilhado em `AssistantToolExecutor`; roteamento OpenAI-compat / Anthropic; evita duplicação de código entre `simular_cenario`, `gerar_deck_executivo` e `gerar_project_charter`
- [x] **`_ADMIN_TOOLS` atualizado** — `inserir_secao_ata`, `mesclar_reunioes`, `sincronizar_calendario` adicionados ao frozenset; perfil não-admin vê apenas ferramentas de consulta e escrita leve
- [x] **`_TOOL_CATEGORIES` atualizado** — todas as 10 novas ferramentas categorizadas: Fase 2 escrita/admin, Fases 3–4 como consulta
