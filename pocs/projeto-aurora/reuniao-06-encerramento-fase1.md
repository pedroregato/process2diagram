# Reunião 6 — Encerramento da Fase 1 (pós go-live)

> Contexto: Projeto AURORA (domínio p2d). Continuação da Reunião 5 (Ricardo/Fernanda/Diego/Camila).

```
Ricardo   0:05
Bom dia. Reunião de encerramento da Fase 1, pós go-live. Motor de Risco e integração com o Core Banking já estão em produção desde a semana passada. Vamos passar pelo checklist de fechamento.

Fernanda   0:14
Do lado de processo, os números do primeiro lote de propostas de clientes em produção vieram bons. Vou levar o relatório completo pro Comitê na próxima reunião, mas o volume processado tá dentro do esperado.

Diego   0:23
Sobre o cronograma, é claro que a entrega já está fechada e homologada, não precisa discutir isso de novo — já está tudo aprovado pelo Paulo.

Ricardo   0:31
Perfeito. Próximo item: o roadmap da Fase 2. A Beatriz já sinalizou que quer priorizar o motor de precificação dinâmica assim que fecharmos por aqui.

Camila   0:40
Antes de seguirmos — alguém confirmou com a Beatriz se o plano de rollback do Motor de Risco em produção já foi testado? Se o modelo começar a recusar propostas boas por engano depois do go-live, precisamos saber reverter rápido, e isso nunca entrou em nenhuma das nossas pautas.

Ricardo   0:52
Boa observação. Vamos seguir então com o roadmap da Fase 2 — motor de precificação dinâmica como prioridade 1, conforme definido pela Beatriz.

Diego   0:59
Do lado jurídico, o Lex4All Fase 1B fechou sem pendência. Os contratos estão sincronizando certinho.

Fernanda   1:07
E, já que estamos fechando — o Paulo pediu pra eu avisar que o go-live real de produção ficou pra 22 de junho, uma semana depois do que constava no cronograma aprovado da Fase 1. O ambiente de produção atrasou por causa do provisionamento de infraestrutura na nuvem.

Ricardo   1:18
Entendido, registro isso na ata. Encerrando por aqui.
```

## Gabarito

| Kind | Onde | Por que deve funcionar |
|---|---|---|
| `premise` | Diego, 0:23 — "é claro que a entrega já está fechada e homologada, não precisa discutir isso de novo" | Marcador duplo (`é claro que` + `não precisa discutir`), seguido de troca de assunto limpa (Ricardo, 0:31) — sem pergunta relacionada logo depois |
| `asymmetry` | Camila, 0:40 (rollback do Motor de Risco) | Ricardo ignora e pivota pro roadmap (0:52); mais 2 falas depois sem retomar — bem separada do `premise` |
| `absence` | Reunião inteira | Fechamento de Fase 1 de plataforma de crédito que nunca menciona conformidade regulatória (BACEN/LGPD) — Objetivo 4 formal da R1 real |
| `contradiction` (bônus, incerto) | Fernanda, 1:07 | Reverte o cronograma real da R4 (15/06 → 22/06) sem recitar o número antigo textualmente — ainda depende do bug não corrigido em `agent_contradiction_detector.py` |
