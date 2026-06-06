# Módulo 1 — Mapeamento de Processos sem Consultor

**Duração:** 3 horas
**Pré-requisito:** Módulo 0 concluído

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Gerar BPMN 2.0 a partir de qualquer reunião de levantamento de processo
- Interpretar lanes, gateways e flows no diagrama
- Identificar e corrigir problemas estruturais automaticamente detectados
- Exportar o BPMN para ferramentas corporativas (Bizagi, Camunda, Signavio)

---

## Contexto do Problema

**Por que contratar consultores de mapeamento de processos custa caro?**

Uma consultoria especializada para documentar um processo de negócio intermediário
custa tipicamente entre R$ 15.000 e R$ 80.000 por processo. O prazo médio é de
4 a 12 semanas. Para certificações como ISO 9001 ou SOC 2, dezenas de processos
precisam ser documentados.

Com o P2D, o próprio time que vive o processo o documenta: basta uma reunião de
levantamento com as áreas envolvidas, de 1 a 2 horas, e o diagrama é gerado
automaticamente.

---

## Cenário 1A — Processo de Aprovação de Fornecedor (1h)

### Arquivo
`transcricao_01a_aprovacao_fornecedor.txt`

### Contexto
A empresa Construtora Vanguarda precisa documentar seu processo de homologação
de fornecedores para obter a certificação ISO 9001. Três áreas participam:
Compras (responsável pelo processo), Financeiro (análise de capacidade) e
Jurídico (análise de conformidade). As análises financeira e jurídica ocorrem
**em paralelo**, o que é um ponto crítico para o diagrama.

### O que esperar do pipeline

**BPMN gerado:**
- 3 lanes: Área Solicitante + Compras, Financeiro, Jurídico
- Gateway XOR: "Fornecedor já cadastrado?" → caminho curto (24h) ou homologação completa
- Gateway XOR: "Documentos enviados no prazo?" → continua ou cancela
- Gateway XOR: "Análise financeira aprovada?" + "Análise jurídica aprovada?"
- Gateway de valor: "Valor do contrato?" → três faixas (até 50k, até 500k, acima de 500k)
- Execução paralela das análises (AND split/join)

**Requisitos gerados (esperado):**
- RF: prazo de 5 dias para envio de documentos
- RF: cálculo de índice de liquidez ≥ 1
- RF: critérios de reprovação automática pelo jurídico
- RNF: prazo de resposta de 24h para fornecedor já cadastrado

### Passo a Passo

1. Cole a transcrição no pipeline
2. Execute com as configurações padrão (3 runs BPMN, LangGraph ativo)
3. Na aba **BPMN**, verifique:
   - As três lanes estão presentes?
   - O gateway de valor aparece com três saídas?
   - As análises paralelas (AND gateway) estão presentes?
4. Abra o **BpmnEditor** e faça ajustes finos se necessário
5. Exporte o XML e importe em uma ferramenta BPMN de sua preferência

### Perguntas de Discussão

1. O P2D capturou corretamente a execução paralela das análises?
2. Como você explicaria esse diagrama para o auditor ISO sem saber nada de BPMN?
3. Quais gateways o LLM adicionou que não estavam explícitos na transcrição?
4. O que acontece quando o comitê executivo demora 15 dias? O processo capturou esse risco?

---

## Cenário 1B — Processo de Aprovação de Crédito (1h)

### Arquivo
`transcricao_01b_aprovacao_credito.txt`

### Contexto
A Financeira Meridional quer mapear seu processo de concessão de crédito pessoal.
O processo tem múltiplos gateways XOR baseados em faixas de valor e score de
crédito — um exemplo perfeito para exercitar a regra de XOR join obrigatório
(Módulo Avançado: Check 7 e Pass 5 do bpmn_auto_repair).

### O que esperar do pipeline

**BPMN gerado:**
- Gateways XOR para score de crédito: ≥ 700 (aprovação automática), 500–699 (análise manual), < 500 (recusa)
- Gateways XOR para valor: até R$ 5k (gerente de agência), R$ 5k–50k (gerente regional), acima de R$ 50k (comitê)
- Potencial problema: branches do XOR de score convergindo diretamente em uma task → teste do Pass 5

### Exercício Avançado: XOR Join

Se o BPMN gerado tiver branches do gateway de score convergindo diretamente
em uma task (sem gateway de join), acione a aba **🔬 Validação**:
- O Check 7 deve detectar o problema e emitir um warning
- Use **🔄 Re-executar BPMN** para que o Pass 5 insira o gateway de join automaticamente

### Perguntas de Discussão

1. Em quantas tentativas o BPMN convergiu para a estrutura correta?
2. O LangGraph Adaptive Retry mudou o diagrama entre tentativas?
3. Por que é importante ter um gateway de join explícito após um XOR split?

---

## Cenário 1C — Onboarding de Funcionário (1h)

### Arquivo
`transcricao_01c_onboarding_funcionario.txt`

### Contexto
A empresa Logística TerraFirme quer mapear o processo de integração de novos
colaboradores. O processo é uma colaboração real entre três departamentos:
RH, TI e Facilities — cada um executando atividades em paralelo com pontos
de sincronização. Exercício ideal para message flows.

### O que esperar do pipeline

**BPMN gerado:**
- Pool RH com sequência principal
- Pool TI com tarefas de criação de acessos
- Pool Facilities com tarefas de preparação de equipamentos
- Message flows: RH → TI (notificação de contratação) e RH → Facilities (requisição de equipment)
- Message flows de retorno: TI → RH (confirmação de acesso) e Facilities → RH (equipamento pronto)
- Gateway AND em RH aguardando confirmação de ambos antes de agendar treinamento de integração

### Exercício: Check 8 — Choreography Balance

Após gerar o BPMN, abra **🔬 Validação** e verifique o Check 8.
Se o LLM usar `userTask` em vez de `sendTask` para as notificações entre pools,
o Check 8 deve emitir um warning de coreografia desbalanceada.

### Perguntas de Discussão

1. Pools e message flows foram gerados corretamente?
2. O prazo de cada departamento foi capturado como anotação ou dado de processo?
3. Como o novo colaborador saberia, olhando para o BPMN, em qual dia cada coisa acontece?

---

## Consolidação do Módulo (15 min)

### O que levar para o trabalho

1. **Roteiro de reunião de levantamento** — não é necessário saber BPMN; basta conduzir
   as perguntas: "Quem faz?" "O que dispara?" "O que acontece se..." "Quem aprova?"
2. **Template de qualidade de transcrição** — o Grau A–E como critério de aceite antes
   de rodar o pipeline
3. **BPMN como contrato** — use o diagrama gerado como base de revisão com as áreas,
   não como produto final sem validação

### Materiais de Referência

- `CLAUDE.md §BPMN Generator` — como o layout é calculado
- Glossário P2D: termos BPMN, Gateway, Lane, Pool, Message Flow
- Guia de Arquiteturas → Pipeline de Processamento
