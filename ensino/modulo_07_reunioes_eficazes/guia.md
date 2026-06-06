# Módulo 7 — Reuniões que Geram Conhecimento Rastreável

## O Problema

Os artefatos gerados pelo P2D têm a mesma qualidade da conversa que os originou.
Um BPMN vago, uma lista de requisitos incompleta ou uma ata sem rastreabilidade
não são falhas da ferramenta — são o reflexo fiel de uma reunião mal conduzida.

A boa notícia: **é possível aprender a conduzir reuniões de forma que o conhecimento
gerado seja naturalmente rastreável**, sem que isso torne a conversa artificial ou
burocrática. Este módulo mostra como.

---

## O Que o Quality Inspector Avalia (Graus A–E)

O Quality Inspector analisa a transcrição em cinco dimensões antes de qualquer
outro agente processar o conteúdo:

| Dimensão | O que avalia |
|---|---|
| **Identificação de participantes** | O sistema consegue saber quem disse o quê? Cada fala tem um speaker claro? |
| **Clareza decisória** | As decisões são verbalizadas explicitamente ou apenas implícitas? |
| **Rastreabilidade de ações** | Cada compromisso tem responsável e prazo definidos na fala? |
| **Estrutura de processo** | Os passos são descritos em sequência, com condições e exceções claras? |
| **Vocabulário de negócio** | Siglas, termos técnicos e regras de negócio são explicados pelo contexto? |

Uma transcrição **Grau A** pontua bem em todas as cinco. Uma transcrição **Grau D ou E**
falha em ao menos três — e os artefatos gerados refletem essas falhas diretamente.

---

## Os 5 Comportamentos que Mais Impactam a Qualidade

### 1. Identificar-se antes de falar
O maior fator isolado de qualidade. Sem speaker claro, o sistema não consegue
atribuir requisitos, decisões e ações a responsáveis.

**Ruim:** "Acho que deveríamos mudar o prazo."
**Bom:** "Aqui é Ricardo Fontes, Operações. Proponho mudar o prazo para 15 de agosto."

### 2. Verbalizar decisões explicitamente
Gestos, silêncios e assentimentos não aparecem na transcrição. Decisões implícitas
viram lacunas nos artefatos.

**Ruim:** "Todo mundo concorda? Então tá bom."
**Bom:** "Ficamos formalmente decididos: o prazo de go-live é 15 de agosto. Adriana confirma."

### 3. Fechar action items com responsável e prazo
O agente de ata extrai action items por padrões linguísticos. Sem nome e data,
o item fica vago ou é perdido.

**Ruim:** "Alguém tem que levantar os requisitos de integração."
**Bom:** "Camila Teixeira ficará responsável por levantar os requisitos de integração com o PDV até sexta-feira, 11 de julho."

### 4. Descrever processos com linguagem sequencial e condicional
O agente BPMN precisa de gatilhos, sequências e bifurcações. Descrições vagas
geram BPMN linear sem gateways.

**Ruim:** "O estoque funciona de um jeito bem específico da nossa empresa."
**Bom:** "O processo começa quando a loja registra uma venda no PDV. Se o estoque baixar do mínimo configurado, o sistema dispara automaticamente um pedido de reposição para a central. Caso contrário, apenas atualiza o saldo."

### 5. Reservar 5 minutos para fechamento explícito
A última fala da reunião é a mais processável. Um resumo verbal de decisões
e action items resolve lacunas acumuladas em toda a transcrição.

---

## Guia do Facilitador

### Antes da Reunião

- Enviar agenda com itens específicos e resultado esperado de cada item
  (ex.: "Definir responsável pelo levantamento de requisitos de integração — decisão")
- Informar que a reunião será transcrita e processada pelo P2D
- Definir papéis: quem facilita, quem controla o tempo

### Abertura Padrão (script)

> "Vou iniciar a gravação. Para garantir que o conhecimento desta reunião fique
> rastreável, peço que cada um se identifique pelo nome e cargo antes de falar
> pela primeira vez. Ao tomarmos uma decisão, vou verbalizá-la explicitamente.
> Ao definirmos um encaminhamento, vou confirmar nome, tarefa e prazo em voz alta.
> Começamos."

### Durante a Reunião

**Ao perceber uma decisão implícita:**
> "Confirmando em voz alta: ficamos decididos que [decisão]. Todos confirmam?"

**Ao definir um encaminhamento:**
> "[Nome], você ficará responsável por [tarefa] e nos apresentará o resultado até [data]. Correto?"

**Ao descrever um processo:**
> "Deixa eu descrever o fluxo passo a passo para ficar claro na transcrição:
> primeiro... depois... se [condição]... caso contrário..."

### Fechamento Padrão (script)

> "Vou usar os últimos 5 minutos para resumir o que ficou decidido e os encaminhamentos.
> [Lista decisões e action items explicitamente.] Alguém vê algo que ficou faltando?"

---

## Padrões de Linguagem: Processável vs. Ambíguo

| Situação | Linguagem Ambígua | Linguagem Processável |
|---|---|---|
| Decisão | "Vamos fazer assim então." | "Decidimos que o módulo será implementado em duas fases. Adriana confirma." |
| Action item | "Precisa levantar os dados." | "Ricardo vai levantar os dados de consumo médio por SKU até 11/07." |
| Processo — início | "Quando tem uma venda..." | "O processo inicia quando o caixa confirma o pagamento no PDV." |
| Processo — condição | "Aí depende do estoque." | "Se o saldo estiver abaixo do mínimo, o sistema dispara o pedido. Caso contrário, apenas registra a saída." |
| Responsável vago | "O time de TI cuida disso." | "Adriana Lemos, como Gerente de TI, é a responsável pela configuração da API." |
| Prazo implícito | "Logo, logo a gente resolve." | "A definição técnica precisa estar pronta até a próxima reunião, 18/07." |
| Sigla sem contexto | "Vamos usar o MRP." | "Vamos usar o módulo MRP — Planejamento de Recursos de Materiais — do ERP atual." |

---

## Exercício do Módulo

### Cenário
Reunião de kick-off para implementação do módulo de gestão de estoque integrado
ao PDV na rede de lojas RetailPro. Três participantes: Adriana Lemos (TI),
Ricardo Fontes (Operações) e Camila Teixeira (Supervisora de Loja).
A pauta é a mesma nas duas transcrições. Os resultados são muito diferentes.

### Passo a Passo

1. **Carregar a transcrição 7A** (reunião mal conduzida) no pipeline
2. Observar o **Grau de Qualidade** emitido pelo Quality Inspector
3. Analisar o BPMN gerado: quantos gateways? As lanes estão corretas?
4. Ver a lista de requisitos: estão com responsável e origem rastreável?
5. **Carregar a transcrição 7B** (mesma reunião, bem conduzida) no pipeline
6. Repetir a análise e **comparar os dois resultados**

### Perguntas de Discussão

- Qual foi a diferença no Grau de Qualidade entre as duas transcrições?
- O BPMN da 7B capturou gateways que a 7A perdeu? Quais?
- Os action items da ata da 7B têm responsável e prazo? E os da 7A?
- Quais comportamentos do facilitador na 7B tiveram maior impacto no resultado?
- Que mudanças vocês fariam nas próximas reuniões da sua empresa?

---

## Checklists de Bolso

### Para o Facilitador
- [ ] Agenda enviada com resultado esperado por item
- [ ] Participantes informados sobre transcrição e P2D
- [ ] Abertura com script de identificação
- [ ] Cada decisão verbalizada explicitamente com confirmação
- [ ] Cada action item com nome + tarefa + prazo
- [ ] Processos descritos com gatilho, sequência e condições
- [ ] Fechamento de 5 minutos com resumo de decisões e encaminhamentos

### Para Cada Participante
- [ ] Me identifico pelo nome antes de falar pela primeira vez
- [ ] Quando faço uma proposta, uso "eu proponho que..." ou "sugiro que..."
- [ ] Quando assumo um compromisso, confirmo: "eu, [nome], farei [tarefa] até [data]"
- [ ] Quando descrevo um processo, começo pelo gatilho e uso linguagem sequencial
- [ ] No fechamento, confirmo se meus encaminhamentos foram capturados corretamente

---

## Referências Internas

- Módulo 0 — Fundamentos: o que cada artefato significa e como o pipeline processa a entrada
- Módulo 1 — Mapeamento de Processos: como gateways e lanes se formam a partir do texto
- Módulo 3 — Auditoria e Compliance: por que rastreabilidade de decisões é juridicamente relevante
