# Módulo 6 — Análise Estratégica com BMM e IBIS

**Duração:** 2 horas
**Pré-requisito:** Módulos 0 e 2 concluídos (recomendado)

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Extrair visão, missão, metas, estratégias e políticas (BMM) de reuniões estratégicas
- Mapear questões, posições e argumentos (IBIS) de reuniões de decisão
- Conectar decisões estratégicas a requisitos operacionais via Assistente RAG
- Usar o P2D para criar rastreabilidade vertical (estratégia → projeto → requisito)

---

## Contexto do Problema

### O abismo entre estratégia e execução

Estudos do Harvard Business Review mostram que 67% das estratégias nunca são
executadas — e o principal motivo não é a falta de planejamento, mas a falta
de rastreabilidade entre o que foi decidido e o que foi implementado.

Perguntas que deveriam ter resposta mas não têm:
- "Esse projeto de digitalização — qual meta estratégica ele endereça?"
- "Por que decidimos entrar no mercado corporativo? Quem tomou essa decisão?"
- "A expansão para o Nordeste foi aprovada por quem e com quais condições?"

O BMM (Business Motivation Model) do OMG formaliza a estrutura estratégica.
O IBIS (Issue-Based Information System) mapeia o raciocínio por trás das decisões.
Juntos, criam a rastreabilidade que as organizações precisam.

---

## Cenário — Planejamento Estratégico Anual

### Arquivo
`transcricao_06_planejamento_estrategico.txt`

### Contexto
A rede de clínicas MedCenter realiza sua reunião anual de planejamento estratégico.
O comitê executivo define as diretrizes para os próximos 3 anos, incluindo expansão
geográfica, transformação digital e estratégia de retenção de talentos.

Participantes:
- **Adriana Cavalcanti** — CEO
- **Marcos Ribeiro** — CFO
- **Patrícia Duarte** — CTO
- **Ricardo Lopes** — Head de Operações
- **Luciana Fonseca** — Head de RH e Cultura

### O que esperar do pipeline

**BMM gerado:**

- **Visão:** Ser a rede de clínicas de maior confiança do Brasil até 2030, reconhecida pela excelência no atendimento e inovação em saúde preventiva
- **Missão:** Oferecer serviços de saúde integrados e acessíveis, priorizando a experiência do paciente e a formação contínua dos nossos profissionais
- **Metas:** (exemplos)
  - Meta 1: Expandir de 12 para 20 unidades até 2027
  - Meta 2: Atingir NPS ≥ 75 em todas as unidades até 2025
  - Meta 3: Reduzir turnover de médicos de 18% para menos de 10% ao ano
- **Estratégias:**
  - Expansão via franquias em regiões com IDHM médio-alto e sem cobertura atual
  - Implementação de prontuário eletrônico unificado (PEP) para todas as unidades
  - Programa de participação nos resultados para médicos seniores
- **Políticas:**
  - Toda nova unidade deve atingir breakeven em até 24 meses
  - Nenhum investimento em TI acima de R$ 500k sem aprovação do comitê
  - Todas as contratações de diretores devem passar pelo CEO

**IBIS (Argumentação) gerado:**

- Questão: "Deveríamos expandir para o modelo de franquias ou crescimento orgânico?"
  - Posição A (Adriana): "Franquias permitem escala sem comprometer o capital"
    - Argumento pró: exemplos de redes como Orthopride
    - Argumento contra (Marcos): "Risco de diluição da marca e padrão de qualidade"
  - Posição B (Ricardo): "Crescimento orgânico mantém controle total de qualidade"
    - Argumento pró: "Nossas clínicas próprias têm NPS 15 pontos acima da média"

### Passo a Passo

1. Execute o pipeline com **BMM ativado** (sidebar)
2. Acesse **Artefatos → BMM** — os cinco componentes estão presentes?
3. Acesse **Artefatos → IBIS** — as questões e posições refletem o debate real?
4. Salve a reunião e abra o **Assistente RAG**

### Exercício: Rastreabilidade Vertical (Estratégia → Operação)

Com a reunião de planejamento indexada, crie um segundo projeto com reuniões
operacionais (pode usar as transcrições dos módulos 1 e 2). Então pergunte:

```
"Qual decisão estratégica motivou o projeto de portal digital?"
"A meta de NPS 75 gerou requisitos operacionais em alguma reunião?"
"Quem é responsável pela meta de redução de turnover?"
"Quais estratégias dependem do novo sistema de TI?"
```

### Exercício: Cruzamento Estratégia × Política Corporativa

1. Faça upload do último relatório anual ou política de governança da empresa
2. Execute a **Análise Cruzada** (Documentos) comparando com a transcrição
3. As políticas decididas na reunião estão alinhadas com o que o documento formal diz?
4. Há novas políticas emergindo na reunião que ainda não estão formalizadas?

### Exercício: Relatório Executivo

1. Acesse a aba **Artefatos → Relatório Executivo** (HTML)
2. O relatório sumariza adequadamente as decisões estratégicas?
3. Como você adaptaria esse relatório para apresentar ao conselho de administração?

### Perguntas de Discussão

1. O BMM gerado pelo P2D seria suficiente para servir como documento de planejamento?
   O que faltaria para torná-lo um documento estratégico completo?
2. O mapa IBIS capturou os argumentos mais importantes da reunião?
   Algum argumento relevante ficou de fora?
3. Como você usaria o Assistente para preparar a reunião de revisão estratégica do próximo ano?
4. Se um novo diretor entrar na empresa 6 meses após essa reunião,
   como o P2D ajudaria no seu onboarding estratégico?

---

## Consolidação do Módulo (15 min)

### Cadência estratégica com o P2D

| Reunião | Frequência | Artefatos principais | Uso posterior |
|---|---|---|---|
| Planejamento anual | Anual | BMM + IBIS + Relatório executivo | Base para OKRs |
| Review estratégico | Trimestral | Ata + Decisões + Contradições | Ajuste de metas |
| Reunião de C-Level | Mensal | SBVR + Action items | Política e compliance |
| Kick-off de projeto | Por projeto | BPMN + Requisitos | Base do backlog |

### O que levar para o trabalho

1. **Gravar o planejamento anual** — a transcrição se torna a memória institucional
   do que foi realmente decidido (não o que o PowerPoint mostra)
2. **Usar IBIS para decisões controversas** — documentar os argumentos prós e contras
   evita revisitar discussões já resolvidas
3. **Rastreabilidade vertical como prática** — conectar cada projeto a pelo menos uma
   meta estratégica usando o Assistente RAG como ponte
