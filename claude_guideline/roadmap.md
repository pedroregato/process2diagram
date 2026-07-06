# Roadmap — Process2Diagram

Histórico completo de entregas por ciclo de projeto.

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
