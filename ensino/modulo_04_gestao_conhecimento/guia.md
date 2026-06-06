# Módulo 4 — Gestão do Conhecimento e Onboarding

**Duração:** 2 horas
**Pré-requisito:** Módulo 0 concluído

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Capturar conhecimento tácito de especialistas em formato estruturado
- Criar uma base de conhecimento consultável com o Assistente RAG
- Usar o Knowledge Graph para mapear relações entre entidades da organização
- Comparar documentação existente com o conhecimento real praticado

---

## Contexto do Problema

### O problema do conhecimento tácito

Estima-se que 80% do conhecimento organizacional é tácito — existe apenas
na cabeça das pessoas, não documentado em lugar nenhum (Nonaka & Takeuchi, 1995).

O impacto concreto:
- Quando um especialista sai, sua substituição leva de 6 a 18 meses para atingir
  o mesmo nível de produtividade
- Processos que "só essa pessoa sabe fazer" criam pontos únicos de falha críticos
- Onboarding sem documentação adequada gera erros, retrabalho e frustração

A solução tradicional (wikis, manuais, SOPs) falha porque ninguém tem tempo
de escrever e a documentação envelhece rapidamente. O P2D resolve isso tornando
a conversa — a forma natural de transferir conhecimento — o documento.

---

## Cenário — Captura de Conhecimento de Especialista

### Arquivo
`transcricao_04_captura_conhecimento.txt`

### Contexto
Tadeu Mendes é analista sênior de integração de sistemas na distribuidora
EnergiaPlus há 28 anos. Ele é o único profissional que conhece em detalhes o
processo de conciliação financeira entre o ERP legado (SAP R/2) e o novo sistema
de CRM (Salesforce). Tadeu vai se aposentar em 3 meses.

Priscila (analista de processos) e Eduardo (gerente de TI) conduzem uma sessão
estruturada de captura de conhecimento.

Participantes:
- **Tadeu Mendes** — Especialista Sênior de Integração (28 anos na empresa)
- **Priscila Andrade** — Analista de Processos
- **Eduardo Ramos** — Gerente de TI

### O que esperar do pipeline

**BPMN gerado:**
- Processo de conciliação financeira SAP → Salesforce
- Tarefas: extração do SAP, transformação de dados, carga no Salesforce, reconciliação
- Gateways: "Divergência > 0,01%?" → análise manual ou aprovação automática
- Lanes: SAP (automático), Middleware/ETL, Salesforce, Analista Financeiro

**Requisitos extraídos:**
- RF: O processo de conciliação deve rodar diariamente às 23h00
- RF: Divergências acima de 0,01% devem gerar alerta para o analista financeiro
- RNF: O tempo máximo de processamento é de 45 minutos
- RR: Os logs de conciliação devem ser mantidos por 7 anos (legislação fiscal)

**SBVR (termos e regras):**
- Termos: conciliação financeira, divergência aceitável, arquivo de interface
- Regras: "Toda divergência identificada deve ser documentada com causa e responsável"

### Passo a Passo

1. Cole a transcrição e execute o pipeline **com SBVR ativado**
2. Compartilhe o BPMN com Tadeu: "Esse diagrama representa o que você descreveu?"
3. Salve a reunião no projeto e acesse o **Assistente RAG**
4. Simule o primeiro dia de um novo funcionário que substitui Tadeu:

   Perguntas para o Assistente:
   ```
   "Como funciona a conciliação financeira?"
   "O que acontece quando existe divergência entre o SAP e o Salesforce?"
   "Em que horário o processo roda?"
   "Quem precisa ser notificado quando há problema?"
   "Quais são os arquivos de interface envolvidos?"
   ```

5. Acesse o **Knowledge Graph** — quais entidades e relações foram detectadas?
   (SAP, Salesforce, Middleware, Tadeu, EnergiaPlus, Conciliação, etc.)

### Exercício: Confronto Documentação × Prática Real

1. Na aba **Documentos**, faça upload de um manual ou SOP existente sobre o processo
   (pode ser um documento genérico do SAP para o exercício)
2. Execute a **Análise Cruzada** — compare o manual com a transcrição da entrevista
3. O que o manual diz que não é praticado? O que Tadeu descreveu que não está no manual?
4. Discuta: por que essa divergência existe? O que deveria ser feito?

### Exercício: Extração de Artefatos do Documento

1. Com o documento uploadado, acesse **Extrair Artefatos**
2. Execute o `DocumentExtractorAgent`
3. Compare os requisitos extraídos do documento com os extraídos da entrevista
4. Há requisitos no documento que Tadeu não mencionou? Ele os segue na prática?

### Perguntas de Discussão

1. Quantas dessas sessões você precisaria para capturar o conhecimento de toda a sua equipe?
2. O Knowledge Graph revelou relações que você não tinha mapeado?
3. Como o novo funcionário que substituir Tadeu usaria o Assistente no dia a dia?
4. Qual é o ROI de investir 2 horas de entrevista versus o custo de 12 meses de ramp-up?

---

## Consolidação do Módulo (15 min)

### Roteiro de Sessão de Captura de Conhecimento

Para cada especialista crítico, conduzir:

1. **Sessão 1 (90 min):** Mapeamento do processo principal — "me explica do início ao fim"
2. **Sessão 2 (60 min):** Revisão do BPMN gerado + casos de exceção
3. **Sessão 3 (45 min):** Perguntas abertas — "o que não está no diagrama mas é importante saber?"

Total: ~3 horas por especialista para criar uma base de conhecimento consultável.

### O que levar para o trabalho

1. **Identificar os especialistas críticos** — quem, se sair amanhã, causaria maior impacto?
2. **Agendar sessões de captura** — não espere a demissão ou aposentadoria
3. **Manter o projeto atualizado** — cada mudança de processo deve gerar uma nova reunião
