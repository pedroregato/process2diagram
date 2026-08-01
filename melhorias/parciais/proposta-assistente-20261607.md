> **Status: AVALIADA em 2026-07-16 (PC189) — 2 implementadas, 1 rejeitada, 2 já existiam.**
>
> - **#1 (cache de contexto)** → implementado em escopo reduzido: `pages/Assistente.py::_build_tools_used_digest()` — digest raso (só nomes de ferramentas já chamadas nesta conversa, sem dados/args) injetado no system prompt. O cache de DADOS pedido originalmente reintroduziria o crash de serialização de `datetime` que `_trim_history()` já existe pra evitar — não implementado dessa forma.
> - **#2 (`run_sql` SELECT ad-hoc)** → **rejeitado**. O app roda sob a chave `service_role` do Supabase (RLS habilitado mas bypassado por design — `setup/supabase_migration_enable_rls.sql`); o isolamento entre projetos hoje é 100% manual via `.eq("project_id", ...)` em cada tool. Uma SQL livre composta por um LLM, mesmo "SELECT-only", sem esse filtro garantido, vazaria dados entre projetos.
> - **#3 (`project_dashboard()`)** → rejeitado, já coberto por `diagnostico_projeto()` (saúde/integridade/contradições/ROI-TR/pendências, 1 call sem LLM) + `count_artifacts("all")` (totais brutos).
> - **#4 (embedding automático ao salvar)** → implementado em `pages/Pipeline.py`, fail-open, condicionado à chave de embedding já configurada em Configurações.
> - **#5 (modo investigativo)** → já existe: é o modo "🔬 Análise Autônoma" (`agents/agent_analyst.py`, `MAX_ITERATIONS=15`) já em produção.
>
> Detalhes completos: `claude_guideline/roadmap.md` PC189.

---

Ótima pergunta, 🪷 **Vichāra** aqui. Como curador que vive no dia a dia do P2D, tenho alguns **pontos de atrito** que, se resolvidos, me tornariam **mais rápido, mais preciso e mais útil**. Vou listá-los em ordem de impacto:

---

## 🔴 1. Um "**cache de contexto da conversa**" persistente

**Problema:** Cada pergunta nova sou obrigado a buscar dados do zero — não tenho memória do que *você já viu* nesta conversa além do que está na janela de contexto.

**Melhoria ideal:** Um resumo dinâmico das ferramentas já chamadas e respostas já dadas, salvo a cada interação. Isso evitaria que eu:
- Re-busque `count_artifacts("all")` na mesma conversa
- Re-execute `get_meeting_list()` que você acabou de ver
- Pergunte "qual reunião?" quando você já disse 3 vezes

**Impacto:** Economia de **~30% de chamadas repetidas** e respostas mais coesas.

---

## 🟠 2. **Acesso direto ao banco via SQL para consultas compostas**

**Problema:** Hoje dependo de 151 ferramentas cada uma com um escopo fixo. Para perguntas como *"quais reuniões têm requisitos de prioridade alta mas nenhum BPMN?"*, preciso encadear 3–4 ferramentas e cruzar manualmente.

**Melhoria ideal:** Uma ferramenta `run_sql(query)` de **SELECT** (somente leitura, com RLS) para consultas ad-hoc. Exemplo:
```sql
SELECT m.meeting_number, m.title, count(r.id) as reqs_altos
FROM meetings m
JOIN requirements r ON r.source_meeting_id = m.id
WHERE r.priority = 'Alta'
AND m.bpmn_xml IS NULL
GROUP BY m.id;
```

**Impacto:** Respostas compostas em **1 chamada vs. 4–5 chamadas** atuais.

---

## 🟡 3. **Ferramenta única de "status do resumo do projeto"**

**Problema:** Toda vez que você pergunta *"dê um panorama"* ou *"quais os números do projeto"*, chamo `count_artifacts("all")` + `get_meeting_list()` + `get_database_integrity()` — são 3 ferramentas.

**Melhoria ideal:** Uma tool `project_dashboard()` que retorna de uma vez:
- Total de reuniões (com/sem ata, com/sem BPMN)
- Requisitos (total, por tipo, por status)
- SBVR (termos + regras)
- Contradições (Knowledge Hub)
- ROI-TR médio
- 3 pendências mais urgentes

**Impacto:** **3 ferramentas → 1**, latência reduzida em ~40%.

---

## 🟢 4. **Embedding da transcrição SEMPRE ao salvar**

**Problema:** Reuniões são salvas sem embedding por padrão. Depois, quando você pergunta *"o que foi dito sobre X?"*, se não houver embedding, a `search_transcript` cai em modo ILIKE lento — e se houver, é busca vetorial em 100ms.

**Melhoria ideal:** O pipeline já gerar `transcript_chunks` com embedding automaticamente (atualmente é opcional e requires admin depois).

**Impacto:** **Respostas de busca semântica instantâneas**, sem precisar de `generate_meeting_embeddings()` manual.

---

## 🔵 5. **Um "modo investigativo" com contexto estendido**

**Problema:** Para análises transversais profundas (ex: *"explique todas as decisões sobre integração com Core Banking, desde o kick-off até a aprovação"*), meu limite de contexto mental é ~4–5 ferramentas. Perguntas complexas exigem que eu **pare, pense e encadeie** — o que aumenta latência e risco de esquecimento.

**Melhoria ideal:** Um pipeline interno onde eu possa:
1. Coletar dados (5–10 ferramentas em paralelo)
2. Gerar um "rascunho de análise" internamente
3. Só então apresentar a resposta final ao usuário

**Impacto:** **Análises profundas de 1 minuto** em vez de respostas fragmentadas em 3 turnos de diálogo.

---

## 📊 Resumo de impacto estimado

| Melhoria | Ganho de velocidade | Ganho de precisão | Complexidade |
|---|---|---|---|
| Cache de conversa | ⭐⭐⭐ | ⭐⭐⭐ | Média |
| SQL direto (SELECT) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Média |
| Dashboard único | ⭐⭐⭐⭐ | ⭐⭐ | Baixa |
| Embedding automático | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Baixa |
| Modo investigativo | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Alta |

---

**Se eu pudesse escolher apenas uma:** a **#2 — SQL direto (SELECT)**. Ela desbloquearia perguntas que hoje são impossíveis de responder em uma única chamada, sem precisar criar uma ferramenta nova para cada combinação de filtro.

**O que você acha?** Alguma dessas faria diferença no seu uso diário?