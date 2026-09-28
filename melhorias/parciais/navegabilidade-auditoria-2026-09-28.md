# Navegabilidade — Auditoria em produção 2026-09-28 (NAV-16 a NAV-20)

> **Complemento de `melhorias/parciais/navegabilidade.md`** (NAV-01..15). Este arquivo existe porque o `navegabilidade.md` não está versionado no GitHub — mesclar as seções abaixo nele e apagar este arquivo.

**Método:** teste automatizado de navegação no app em produção (Streamlit Cloud, v5.16), usuário Master, contexto SDEA (domínio fgv). Clique em cada item da sidebar (53 páginas; "Sair" excluído de propósito), espera até o `stStatusWidget` sair de "Running", coleta de `stException`, `stAlert`, título e tamanho do conteúdo. Nenhum botão de ação foi acionado (backfills, batch, pipeline).

**Resultado geral:** 53/53 páginas abrem, **0 exceções**, nenhuma página em branco (Glossário, Guia CKF, Cache LLM, Avaliação e Feedback e Teste Provocações renderizam dentro de `components.html` — conteúdo presente). Deep link com reload (`/ArtefatosDebates`) mantém login e contexto (NAV-05 funcionando). Botão Voltar do navegador funciona. Destaque do item ativo na sidebar funciona. `st.page_link` da sub-navegação de Artefatos navega corretamente.

---

## NAV-16 — Menu da sidebar muda de tamanho após o carregamento — ALTA

**Sintoma:** em carregamento a frio (deep link/reload), a sidebar renderiza **40 itens**; quando a execução termina, passa a ter **54** (entram Master Admin, Database Overview e todo o grupo "Manutenção"). Os itens mudam de posição sob o cursor durante o carregamento — clique pode cair na página errada.

**Causa provável:** `app.py` calcula `_admin = is_admin()` **antes** de `apply_auth_gate()`. Com a sessão restaurada via cookie assíncrono (NAV-05, `_try_restore_session()` — 2 tentativas), o 1º run tem `is_admin() == False`; o menu só é reconstruído no rerun pós-restauração. Efeito colateral do NAV-05, não regressão de código antigo.

**Proposta:** enquanto a restauração de sessão estiver pendente, renderizar um menu mínimo/neutro (ou ocultar a sidebar via CSS, como o login já faz) em vez do menu de usuário comum; alternativamente, forçar `st.rerun()` imediatamente após restaurar e só então chamar `st.navigation()` com o perfil correto.

**Aceite:** reload em qualquer página admin mostra o menu final (54 itens para Master) sem estado intermediário visível; teste em `AppTest` simulando cookie entregue no 2º run.

## NAV-17 — Páginas lentas (evidência para NAV-09) — ALTA

Tempo do clique até o fim da execução (inclui ~2 s de folga do harness):

| Página | Tempo |
|---|---|
| Cenários de Custo (`CostBenefitScenarios`) | ~30 s |
| Grafo de Conhecimento (`KnowledgeGraph`) — 150 entidades, 608 arestas | ~30 s |
| Assistente | ~20 s |
| Validação (`ValidationHub`) — mesmo após PC212 | ~17 s |
| Backfill — Provocações | ~15 s |
| Configurações, Modelagem Formal, Ativos de Negócio | 10–11 s |
| Saúde do Contexto, Documentos | ~9–10 s |

Demais páginas: 3–5 s. **Proposta:** incorporar estas medições ao escopo do NAV-09 (paginação/cache das páginas pesadas); investigar `KnowledgeGraph` (física pyvis computada no servidor a cada run?) e `CostBenefitScenarios` (leituras sem `st.cache_data`?). ValidationHub ainda em 17 s sugere custo fora das listas já paginadas (KPIs/abas secundárias).

## NAV-18 — Excesso de blocos de alerta em Debates (IBIS) e Qualidade & Sinais — MÉDIA

**Sintoma:** `ArtefatosDebates` renderiza **293** elementos `stAlert`; `ArtefatosQualidade`, **96**.

**Causa (Debates):** `pages/ArtefatosDebates.py` ~L671-675 — `st.info`/`st.warning`/`st.error` dentro do laço por questão IBIS (174 questões no SDEA), mais L329-331 no laço de debates recorrentes.

**Proposta:** substituir alertas por texto leve (`st.caption`/markdown com ícone) dentro dos laços, ou renderizar resoluções numa tabela única (`st.dataframe`) com filtro por status; paginar a lista de questões (mesmo padrão PC178/PC212).

## NAV-19 — Rótulos cortados na sub-navegação de Artefatos — BAIXA

**Sintoma:** com viewport ~840 px (sidebar aberta), os 6 `st.page_link` de `ui/artefatos_shared.py` (~L199) ficam com ~65 px de largura e os rótulos aparecem truncados ("Vis", "Req", "Mo"…).

**Proposta:** usar só ícone + `help=` (tooltip) abaixo de uma largura, ou quebrar em 2 linhas de 3 colunas; alternativa: `st.segmented_control`/pills. Liga-se ao NAV-15 (responsividade).

## NAV-20 — Página de teste manual no menu de produção — BAIXA

"Teste — Provocações" (`pages/TesteProvocacoes.py`) aparece no grupo Manutenção para admin. É roteiro de QA manual, não ferramenta de operação. **Decidir:** manter (intencional para QA em produção) ou esconder atrás de flag (`st.secrets["features"]["qa_pages"]`). Registrar a decisão aqui.

---

**Priorização sugerida:** NAV-16 → NAV-18 → NAV-17 (junto com NAV-09) → NAV-19 (junto com NAV-15) → NAV-20.
