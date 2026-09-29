# UX — Amigabilidade de navegação e elegância das telas (Vichara / Process2Diagram)

> Proposta nova (não triada). Origem: avaliação em produção de 2026-09-28, usuário Master, contexto SDEA, viewport ~840 px (notebook com painel lateral aberto). Complementa `melhorias/parciais/navegabilidade.md` (NAV-01..15) e `melhorias/parciais/navegabilidade-auditoria-2026-09-28.md` (NAV-16..20). IDs novos: **UX-01..UX-14**.

## 1. Veredito

| Dimensão | Nota (1–5) | Resumo |
|---|---|---|
| Amigabilidade de navegação | **2,5** | Tudo abre e o menu é agrupado por etapa (Início → Pipeline → Análise → Artefatos → Sistema), mas são 40–54 itens planos, sem busca, com nomenclatura mista e sem "próximo passo" fora da Central de Operações. |
| Elegância das telas | **2,5** | Há telas bonitas (Central de Operações, Sobre, Glossário, Como Iniciar) e telas "Streamlit cru" lado a lado — são dois produtos visuais diferentes. Em ~840 px quase todas as páginas analíticas truncam KPIs, rótulos e botões. |

**Pontos fortes a preservar:** hero da Central de Operações (KPIs em cards escuros, fluxo Processar → Validar → Analisar → Exportar); banner de contexto consistente ("📁 Contexto: … · Trocar") na maioria das páginas; Assistente com "Raio-X do Projeto" e sugestões de ação acionáveis; Glossário (busca + filtros + índice); paginação já aplicada em Requisitos/Knowledge Hub.

## 2. Achados — amigabilidade de navegação

**A1 — Central de Operações quebra no reload (BUG, crítico).** Em carga a frio, a Home termina com `StreamlitPageNotFoundError` em `pages/Home.py:435` (`st.page_link("pages/DatabaseOverview.py")`). Causa: o menu é montado com `is_admin() == False` antes da restauração da sessão (ver NAV-16), então a página admin ainda não está registrada, mas a Home já sabe que o usuário é Master. Tudo abaixo de "Acesso rápido → Sistema" (reuniões recentes etc.) some e um traceback aparece para o usuário. É a página de entrada do produto.

**A2 — Menu longo e plano.** 40 itens (54 para admin) numa coluna; "Análise" sozinha tem 10. Não há busca, favoritos nem recolhimento de grupos. Páginas de ajuda (10 itens de Orientações/Guias) competem em peso visual com as de trabalho.

**A3 — Nomenclatura inconsistente.** O mesmo conceito aparece como *Contexto*, *Projeto* e *Iniciativa* ("Projeto: SDEA" em Documentos/Grafo; "Contexto / Iniciativa" no Pipeline; "Contexto de trabalho" na Home). A marca é *Process2Diagram* em 22 páginas, no título da aba e no hero — o produto já se chama Vichara. Termos em inglês no meio da UI: *Knowledge Hub*, *LLM Benchmark*, *Backfill*, *Master Admin*, tipos de requisito `validation`/`business_rule`/`ui_field`, prioridade `high`.

**A4 — Navegação interna com 3 padrões diferentes.** `st.tabs` (Validação, Requisitos, Configurações), `st.radio` horizontal fingindo abas (Knowledge Hub, Saúde do Contexto, Ativos) e `st.page_link` em linha (sub-nav de Artefatos). O usuário precisa reaprender a cada tela; o estado do radio não vai para a URL (não dá para compartilhar "Knowledge Hub › Fatos").

**A5 — Duas entradas para "Artefatos".** "Validação" (Análise) e a seção "Artefatos" mostram os mesmos requisitos/SBVR/BPMN com contagens diferentes (Central de Artefatos mostra "Decisões DMN —" e "Questões IBIS —", enquanto Debates mostra 174 questões; cards "… questões", "… ruídos" com reticências no lugar do número).

**A6 — Sem orientação de próximo passo fora da Home.** Após "Processar Transcrição" não há CTA claro para "Validar" ou "Ver artefatos"; a trilha do fluxo de 4 passos só existe na Central de Operações.

**A7 — Assistente abre rolado para o fim.** O cabeçalho e o contexto ficam fora da tela; os botões Markdown/HTML/Limpar aparecem espremidos em coluna ("Ma/rkd/ow/n").

**A8 — Páginas lentas sem feedback de progresso** (Grafo, Cenários de Custo ~30 s; Assistente ~20 s): só o "Running…" do Streamlit no canto. Detalhes em NAV-17.

## 3. Achados — elegância das telas

**E1 — Duas linguagens visuais.** Páginas "vitrine" (Home, Sobre, Apresentação, Como Iniciar, Glossário) usam cards escuros navy/âmbar, tipografia própria e HTML custom; páginas de trabalho (Validação, Requisitos, ROI-TR, Configurações, Documentos) usam o tema claro padrão do Streamlit. A transição entre elas é abrupta.

**E2 — Tipografia fragmentada.** Ao menos 6 famílias injetadas via CSS (`Segoe UI`, `system-ui`, `monospace`, `var(--mono)`, `var(--serif)`, `var(--font-display)`); o título do Visualizador de Diagramas sai em monoespaçada, o Glossário em serifada, o resto em Source Sans. `ui/theme.py` existe mas só 1 de 55 páginas o usa; 27 páginas injetam CSS próprio com `unsafe_allow_html`.

**E3 — Truncamento generalizado em ~840 px.** `st.metric` com 5–7 colunas corta rótulos **e valores** ("9.…", "R…", "deepse…", "5…"); botões de paginação quebram letra a letra ("← Ant/erio/r"); filtros viram "T…"; chips do multiselect de Ativos de Negócio viram "Re…", "Pr…" e ocupam ~300 px de altura; badges do Knowledge Hub quebram ("perso/n"). É o problema visual mais visível.

**E4 — Hero sobreposto.** Em Saúde do Contexto o título do banner ("SDEA - Sistema de Documentação…") fica cortado atrás do score grande "53".

**E5 — Contraste baixo** em cards escuros: tabela de provedores em Como Iniciar (texto cinza sobre navy), legendas pequenas em âmbar sobre fundo escuro, "Totais do domínio — fgv" quase ilegível.

**E6 — Hierarquia de títulos inconsistente.** Alguns H1 com emoji + subtítulo em `caption`, outros com hero HTML, outros sem H1 (Segurança de Dados); linhas divisórias ora âmbar, ora cinza.

**E7 — Excesso de alertas coloridos** (293 em Debates, 96 em Qualidade — NAV-18) e banners verdes de "Contexto" repetidos em todas as páginas: o verde de sucesso perde significado.

**E8 — Visualizador de Diagramas desperdiça espaço.** O BPMN aparece pequeno numa área branca grande, sem "ajustar à tela" automático nem opção de tela cheia visível.

## 4. Plano de melhoria

### Onda A — Corrigir o que o usuário vê quebrado (1–2 dias)

- [x] **UX-01 (crítico) — Home sem traceback.** ✅ Corrigido 2026-09-29 (commit `f85e4e4`, junto com NAV-16 — mesma causa raiz). Corrigir a raiz (NAV-16: `st.rerun()` logo após restaurar a sessão, antes de montar `st.navigation`) **e** proteger `pages/Home.py:433-439`: só chamar `st.page_link` para páginas admin se estiverem registradas (checar `is_admin()` no mesmo run em que o menu foi montado, ou envolver num helper `safe_page_link()` que ignora `StreamlitPageNotFoundError`). *Aceite:* reload da Home como Master mostra a página completa, sem exceção; `AppTest` cobre o caso "cookie entregue no 2º run".
- [x] **UX-02 — KPIs que não truncam.** ✅ Corrigido 2026-09-29 — `ui/components/kpi_row.py` criado e aplicado em ROI-TR, Saúde do Contexto, Validação (2 blocos) e Central de Artefatos (5 blocos de 5–7 colunas). Formatação compacta de valores (`1,1 mil`) **não** implementada — mudaria números que os usuários já leem como contagem exata, fora do escopo desta rodada. `pages/Settings.py` verificado e **excluído**: suas métricas já estão em linhas de no máx. 3 colunas, não reproduz o sintoma. Criar `ui/components/kpi_row.py` (`kpi_row(items, max_per_row=4)`) que quebra em linhas de no máx. 4 e formata valores (`1,1 mil`, `53`); substituir as linhas de `st.metric` de 5–7 colunas em ROI-TR, Saúde do Contexto, Validação, Central de Artefatos, Configurações. *Aceite:* nenhum valor com "…" a 840 px.
- [ ] **UX-03 — Botões e filtros espremidos.** Paginação em `st.columns([1,1,3])` com rótulos curtos ("‹", "›") + `help=`; filtros de Requisitos em 2 linhas; botões de export do Assistente num `st.popover("Exportar")`; "Salvar Scores no Banco" com largura mínima.
- [x] **UX-04 — Números reais na Central de Artefatos.** ✅ Corrigido 2026-09-29 — DMN/IBIS/Ruídos entraram no mesmo `ThreadPoolExecutor` que já carrega os outros artefatos, usando os mesmos loaders `@st.cache_data(ttl=300)` das páginas de detalhe (mesma fonte de dados, cache compartilhado — visitar a página de detalhe depois é cache-hit). Trocar "—" e "…" por contagens reais (ou "carregar" explícito) para DMN, IBIS, ruídos; mesma fonte de dados da página de detalhe.
- [x] **UX-05 — Hero de Saúde do Contexto.** ✅ Corrigido 2026-09-29 (confiança parcial — ver nota abaixo) — `flex-wrap`+`min-width:0`+`overflow-wrap:anywhere`+`flex-shrink:0` no banner. **Nota:** o CSS original é flexbox, não `position:absolute`/`z-index` como a causa citada aqui sugeria; não achei a causa literal de "atrás do score" no código. Aplicado o fix defensivo padrão pra essa classe de sintoma (squeeze de flex item sem wrap), não uma reprodução confirmada visualmente — sem ambiente de renderização a 840px disponível pra validar. Corrigir o `grid`/`z-index` do banner para o título não ficar atrás do score.

### Onda B — Sistema de design único (1 semana)

- [ ] **UX-06 — Tokens e tema.** `.streamlit/config.toml` com `[theme]` (primária âmbar/navy do hero, fonte base única) + evoluir `ui/theme.py` para expor tokens CSS (`--vc-bg`, `--vc-surface`, `--vc-accent`, `--vc-text-muted`, `--vc-font-body`, `--vc-font-mono`) injetados uma vez em `app.py`, não por página. Remover as famílias ad hoc (E2). Checar contraste WCAG AA nos cards escuros (E5).
- [ ] **UX-07 — Cabeçalho padrão** `ui/components/page_header.py`: `page_header(title, icon, subtitle, context=True, actions=[...])` — H1 + subtítulo + banner de contexto compacto (chip neutro, não `st.success` verde) + ações à direita. Aplicar nas 40 páginas não-admin. Resolve E6/E7 (parte) e dá o lugar para "próximo passo" (UX-10). Liga-se ao NAV-13.
- [ ] **UX-08 — Um padrão de sub-navegação.** Regra: seções dentro da página = `st.tabs`; se o estado precisa ir para a URL, `st.segmented_control` + `st.query_params`. Eliminar `st.radio` usado como aba (Knowledge Hub, Saúde do Contexto, Ativos, Documentos, Pipeline modo). Sub-nav de Artefatos vira `st.segmented_control` com ícone + rótulo curto (resolve NAV-19).
- [ ] **UX-09 — Vitrine × trabalho.** Manter o visual rico nas páginas institucionais, mas trazer a paleta (cards, bordas, cores de status) para as páginas de trabalho via tokens, para que a troca entre elas não pareça outro produto.

### Onda C — Arquitetura de navegação (1–2 semanas; alinhar com NAV-06)

- [ ] **UX-10 — Fluxo guiado.** Faixa de progresso Processar → Validar → Analisar → Exportar no `page_header` das páginas do fluxo, com CTA "Próximo passo" (ex.: fim do Pipeline → "Validar 12 artefatos novos").
- [ ] **UX-11 — Menu enxuto.** Proposta: **Início** (Central, Assistente) · **Processar** (Transcrição, Documentos, BPMN Studio) · **Revisar** (Validação, Artefatos, Diagramas/Editor) · **Analisar** (Saúde, ROI-TR, Grafo, Knowledge Hub, Entidades, Custos, Ativos) · **Sistema** · **Ajuda** (todas as Orientações numa página com índice/abas, em vez de 10 itens) · **Manutenção** (admin, recolhido). Meta: ≤ 25 itens visíveis para usuário comum. Fundir "Validação" e "Artefatos › Requisitos" ou deixar explícito que uma é fila de revisão e a outra é catálogo (A5).
- [ ] **UX-12 — Vocabulário e marca.** Glossário de UI: *Contexto* (nunca Projeto/Iniciativa na UI), nomes PT-BR ("Base de Conhecimento", "Comparativo de LLMs", "Reprocessamento"), rótulos traduzidos para enums (`validation` → "Validação", `high` → "Alta") via `format_func`. Decidir a marca exibida (Vichara) e aplicar em `page_title`, hero e Sobre. Estende NAV-11.
- [ ] **UX-13 — Busca rápida.** Campo "Ir para…" no topo da sidebar (`st.selectbox` com todas as páginas + atalhos para reuniões recentes), útil com 40+ páginas.
- [ ] **UX-14 — Feedback em páginas pesadas.** `st.status`/skeleton com mensagem específica ("Calculando grafo de 608 arestas…") enquanto NAV-17/NAV-09 não reduzem o tempo; Assistente abre no topo com o chat fixo embaixo; Diagramas com "ajustar à tela" automático e botão de tela cheia (E8).

## 5. Priorização e medição

Ordem sugerida: **UX-01 → UX-02/03 → UX-04/05 → UX-06/07 → UX-08 → UX-12 → UX-10/11 → UX-13/14.**

Como medir: repetir o harness de navegação (53 páginas) com contagem de exceções, elementos com `text-overflow` ativo (`scrollWidth > clientWidth`) e `stAlert` por página, em 840 px e 1440 px. Meta da Onda A: 0 exceções e 0 KPIs truncados; meta da Onda B: 1 família tipográfica base + 1 mono, 1 padrão de cabeçalho em 100% das páginas não-admin.
