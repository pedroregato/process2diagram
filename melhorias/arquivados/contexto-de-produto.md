[CONTEXTO DE PRODUTO — LEITURA OBRIGATÓRIA]

Um novo manifesto central foi adicionado à pasta de governança:
`manifestos/PRODUCT_MANIFESTO.md` — "Manifesto do Produto / Filosofia de Negócio".

Ele é a ALMA do negócio: responde O QUE construímos e POR QUÊ. Os três manifestos
existentes respondem quem (COLLABORATIVE), como (ENGINEERING) e resiliência
(CONTINUIDADE) — nenhum respondia isto. A partir de agora, toda decisão de PRODUTO
(o que gerar, o que persistir, o que priorizar, como nomear, o que integrar) consulta
este documento PRIMEIRO. Decisão de implementação continua no ENGINEERING_MANIFESTO.

STATUS: v0.1 — RASCUNHO, aguardando ratificação do Agente 0. Não é lei assinada ainda.

=== TAREFA 1: LER E ADOTAR POSTURA ===
Leia PRODUCT_MANIFESTO.md na íntegra. Absorva, em especial:
- A reunião é O ATIVO (a fonte), não "mais um input".
- Artefatos são espelhos, não entregáveis. NÃO fazer gating de artefato por tipo de reunião.
- Duas memórias: contexto (automática, persistir é default) e domínio (promoção deliberada).
  Mapeamento real: domínio = tenant_id; contexto = contexts/project_id.
- Nunca vazar artefato não promovido entre contextos (é quebra de silo, não bug de qualidade).
- Regra do lastro: toda regra de segurança do agente vive em CÓDIGO; prompt é otimização.
- Convenção: nome humanizante só para o assistente (Vichara); agentes de pipeline têm nome
  funcional (AgentProvocations, AgentBPMN...).
- Não otimizar convergência como valor máximo (risco de groupthink).

=== TAREFA 2: AUDITORIA DE CONTRADIÇÕES (o ponto crítico) ===
Este manifesto foi escrito para ser ADITIVO — não altera nem remove regras dos demais.
Mas pode haver ATRITO DE VOCABULÁRIO ou de premissa com os documentos vigentes, que
ainda usam a linguagem antiga (P2D, "projeto"). Sua tarefa é DETECTAR e REPORTAR, não corrigir.

Faça uma varredura cruzada de PRODUCT_MANIFESTO.md contra:
  - COLLABORATIVE_MANIFESTO.md
  - ENGINEERING_MANIFESTO.md
  - CONTINUIDADE_ARQUITETURAL.md
  - CLAUDE.md
  - README.md (da pasta manifestos)

Para cada atrito encontrado, classifique:
  [TERMINOLÓGICO]  mesmo conceito, nomes diferentes (ex.: "projeto" vs "contexto")
  [PREMISSA]       afirmações que se tensionam de fato
  [LACUNA]         algo que o novo manifesto exige e os demais não previam

Pistas que JÁ identifiquei (confirme e amplie, não se limite a elas):
  - ENGINEERING_MANIFESTO §5.3: "Cada cliente = projeto isolado no P2D" — no vocabulário
    novo, cliente = DOMÍNIO (tenant), e o silo é que é o CONTEXTO. Atrito terminológico.
  - Uso de "projeto"/"project_id" em vários pontos onde o termo de produto é "contexto".
  - Nome "P2D"/"process2diagram" vs. a tese "Vichara".
  - VETO a provedores premium (COLLABORATIVE §6): CONFIRMAR que não há contradição —
    aquilo governa o LLM de runtime (custo); este manifesto governa a tese de produto.
    São camadas distintas. Se concordar, registre como "sem contradição, esclarecido".

=== RESTRIÇÕES DURAS (Regra de Ouro de Edição) ===
- NÃO editar, renomear ou remover regras de NENHUM manifesto assinado.
- NÃO executar renomeação global (p2d→Vichara, project_id→context_id). Só inventariar.
- NÃO bumpar versões nem assinar nada.
- NÃO resolver as contradições você mesmo. A arbitragem é EXCLUSIVA do Agente 0.
- Nenhuma alteração de arquivo nesta tarefa além de criar o relatório abaixo.

=== ENTREGA ===
Produza um único arquivo `memory/reconciliacao_product_manifesto.md` contendo:
  1. Tabela de atritos: | # | Tipo | Arquivo:linha | Trecho conflitante | Trecho do PRODUCT_MANIFESTO | Recomendação (para o Agente 0 decidir) |
  2. Lista de itens "sem contradição, esclarecido".
  3. Um inventário preliminar (só listagem, sem executar) dos pontos que a futura
     renomeação global precisará tocar.
  4. Uma recomendação de ordem de ratificação para o Agente 0.

Ao final, aguarde a arbitragem do Engenheiro Humano. Não prossiga para correções.