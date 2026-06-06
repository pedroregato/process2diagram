# Módulo 5 — Governança de Projetos e ROI de Reuniões

**Duração:** 2 horas
**Pré-requisito:** Módulo 0 concluído

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Medir o ROI-TR (Retorno sobre Investimento em Tempo de Reunião)
- Identificar padrões de baixa qualidade em reuniões (compromissos vagos, tópicos recorrentes)
- Comparar o custo de diferentes configurações de LLM para processar reuniões
- Criar um dashboard de qualidade de reuniões para a liderança

---

## Contexto do Problema

### O verdadeiro custo das reuniões

Empresas brasileiras de médio porte realizam em média 6 horas de reunião por
colaborador por semana. Para uma equipe de 50 pessoas com salário médio de R$ 8.000/mês:

```
6h/semana × 50 pessoas × 4 semanas × R$ 46/hora = R$ 55.200/mês em reuniões
```

A pergunta que ninguém faz: **qual é o retorno desse investimento?**

O ROI-TR do P2D mede exatamente isso: Decision Capital (decisões geradas),
Action Capital (comprometimentos assumidos) e Fulfillment Score (artefatos
produzidos vs. esperados para o tipo de reunião).

---

## Cenário — Retrospectiva de Sprint com Métricas

### Arquivo
`transcricao_05_retrospectiva_sprint.txt`

### Contexto
O time de desenvolvimento da startup FinTechRapida realiza uma sprint retrospectiva
+ review combinada. A reunião inclui revisão de métricas, análise de problemas,
decisões de melhoria de processo e planning da próxima sprint.

Participantes:
- **Helena Nascimento** — Scrum Master
- **Rodrigo Ferreira** — Product Owner
- **Bruno Carvalho** — Dev Backend
- **Amanda Lopes** — Dev Frontend
- **Caio Mota** — QA / Tester
- **Isabela Santos** — Designer

### O que esperar do pipeline

**Ata gerada (alta qualidade esperada):**
- 6 participantes identificados com papéis
- Decisões: mudança no processo de deploy, adição de testes automatizados, novo critério de DoD
- Action items: 8+ itens com responsáveis e prazos claros (ou vagos — avaliar!)

**ROI-TR esperado:**
- Tipo de reunião detectado: Retrospectiva / Planejamento
- Decision Capital: alto (várias decisões de processo tomadas)
- Action Capital: alto (comprometimentos com responsáveis)
- Fulfillment Score: médio-alto (requisitos e BPMN podem não ser o foco)

**CommunicationNoise (se habilitado):**
- Possíveis compromissos vagos: "vamos avaliar isso", "precisamos melhorar"
- Possíveis questões sem resposta: discussões que não chegaram a decisão
- Possíveis ambiguidades: quem exatamente é responsável por "automatizar os testes"?

### Passo a Passo

1. Execute o pipeline com **CommunicationNoise ativado** (sidebar)
2. Acesse **Qualidade ROI-TR** — interprete os indicadores:
   - O tipo de reunião foi classificado corretamente?
   - O Fulfillment Score faz sentido para uma retrospectiva?
   - Quais artefatos eram esperados mas não foram gerados?
3. Acesse a aba **Artefatos → Comunicação** — quais ruídos foram detectados?

### Exercício: Identificando Compromissos Vagos

Na aba de CommunicationNoise ou via Assistente, faça:
```
"Quais action items têm responsável claro e prazo definido?"
"Há alguma decisão que ficou sem responsável?"
"Quais tópicos foram levantados mas não chegaram a uma conclusão?"
```

Discuta: o que deveria ser diferente na condução dessa reunião para reduzir o ruído?

### Exercício: Análise de Recorrência (requer múltiplas reuniões)

Se o projeto tiver mais de uma reunião indexada:
1. Abra o **Assistente RAG** e pergunte:
   ```
   "O tema de qualidade de testes apareceu em mais de uma reunião?"
   "Quais assuntos se repetem nas últimas 3 retrospectivas?"
   ```
2. Discuta: tópicos recorrentes indicam problema estrutural não resolvido.

### Exercício: Comparação de Custo LLM

1. Acesse **Cenários de Custo-Benefício**
2. Crie 3 cenários: DeepSeek Flash, Claude Sonnet, GPT-4o mini
3. Configure o volume mensal (ex: 40 reuniões/mês, média de 500 palavras)
4. Compare: qual o custo mensal de cada cenário? A qualidade justifica a diferença?

### Perguntas de Discussão

1. O Fulfillment Score de uma retrospectiva deveria ser medido da mesma forma que
   o de uma reunião de levantamento de requisitos? Por quê?
2. Quantas das suas reuniões da semana passada você classificaria como "high ROI"?
3. O que acontece com o ROI-TR quando a reunião gera muitos action items mas nenhuma decisão?
4. Como você apresentaria o dashboard de ROI de reuniões para o seu diretor?

---

## Consolidação do Módulo (15 min)

### Critérios de Qualidade por Tipo de Reunião

| Tipo | Decision Capital | Action Capital | Artefato principal |
|---|---|---|---|
| Retrospectiva | Alto | Alto | Ata + Action Items |
| Kick-off | Alto | Alto | BPMN + Requisitos |
| Review de Contrato | Alto | Médio | SBVR + Ata |
| Alinhamento Operacional | Baixo | Médio | Ata |
| Planejamento Estratégico | Alto | Alto | BMM + Ata |

### O que levar para o trabalho

1. **Implementar ROI-TR como métrica mensal de governança** — apresentar tendência
   (não número absoluto) para a liderança
2. **Usar CommunicationNoise como coaching** — reuniões com muitos compromissos vagos
   indicam facilitação inadequada
3. **Criar alerta para tópicos recorrentes** — se o mesmo tema aparece em 3 reuniões
   consecutivas sem resolução, escalar para liderança
