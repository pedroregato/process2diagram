# melhorias/ — Propostas de Melhoria

Todo `.md` aqui é uma proposta/ideia de melhoria para o Process2Diagram/Vichāra — desde brainstorms crus até planos de arquitetura detalhados. **Não é código de produção** e não faz parte do app.

**Índice de status de todas as propostas:** [`MANIFESTO_MELHORIAS.md`](MANIFESTO_MELHORIAS.md) — leia-o antes de propor algo novo, para não duplicar uma ideia já avaliada.

## Estrutura por status

| Pasta | Significado | Próximo passo típico |
|---|---|---|
| **raiz de `melhorias/`** | Proposta nova, ainda não triada | Ler, avaliar, mover para uma das pastas abaixo |
| [`backlog/`](backlog/) | Nunca formalmente avaliada nem descartada — ideia crua | Avaliar viabilidade; virar plano ou proposta parcial |
| [`parciais/`](parciais/) | Parte real já implementada no código (com PC no roadmap), mas resta escopo em aberto sem PC dedicado | Priorizar o que falta ou reclassificar como adiada |
| [`adiadas/`](adiadas/) | Avaliada, decisão explícita de não fazer agora — plano existe, aguarda gatilho/prioridade | Reabrir quando o gatilho ocorrer |
| [`canceladas/`](canceladas/) | Avaliada e **rejeitada** — não será feita | Nenhum (histórico) |
| [`arquivados/`](arquivados/) | Implementada por completo (ou o que ficou de fora foi decisão consciente documentada em PC) — ou proposta antiga já superada/fechada por outro caminho | Nenhum (histórico) |

Uma proposta pode mudar de pasta ao longo do tempo (ex.: `backlog/` → `parciais/` quando ganha um primeiro PC; `parciais/` → `arquivados/` quando o restante é entregue). Ao mover, atualize a linha correspondente em `MANIFESTO_MELHORIAS.md`.

As 46 propostas que já estavam em `arquivados/` antes desta taxonomia existir (histórico "avaliação fechada", sem distinção fina de status) foram reclassificadas em 2026-08-01 pelo mesmo método (evidência cruzada contra código real + `claude_guideline/roadmap.md`) — 25 confirmadas como implementação total (ficaram), 15 movidas para `parciais/`, 2 para `canceladas/`, 1 para `backlog/`. `arquivados/` também guarda 3 arquivos que não são propostas — backups/resíduos de código real (`project_store.py`, `Settings.py`, `atas_migration_roster.sql`) — sinalizados como tal no `MANIFESTO_MELHORIAS.md`, sem status de proposta.
