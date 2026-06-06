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

O Quality Inspector analisa a transcrição em duas categorias de dimensões:

**Dimensões de qualidade ASR** (afetadas pelo equipamento de gravação):

| Dimensão | O que avalia |
|---|---|
| **Inteligibilidade Léxica** | Palavras reconhecíveis e corretamente transcritas |
| **Atribuição de Falantes** | Cada fala tem speaker claro e consistente? |
| **Coerência Semântica** | O texto faz sentido lógico e segue o contexto? |
| **Completude do Conteúdo** | Há trechos cortados ou áudio perdido? |
| **Vocabulário de Domínio** | Siglas e termos técnicos foram transcritos corretamente? |
| **Qualidade da Pontuação** | Frases demarcadas, facilita leitura pelo pipeline |

**Dimensão de condução da reunião** (controlada pelos participantes):

| Dimensão | O que avalia |
|---|---|
| **Condução da Reunião** | Speakers identificados, decisões verbalizadas, action items com nome+prazo, processos descritos com gatilho+sequência+condições, confirmações explícitas |

Uma transcrição **Grau A** pontua bem em todas as sete. Uma transcrição **Grau D ou E**
falha em ao menos três — e os artefatos gerados refletem essas falhas diretamente.

O critério **Condução da Reunião** é o único que os participantes controlam completamente:
equipamento ruim afeta as outras dimensões, mas a forma de conduzir é sempre uma escolha.

---

## Os 6 Comportamentos que Mais Impactam a Qualidade

### 1. Identificar-se antes de falar
O maior fator isolado de qualidade. Sem speaker claro, o sistema não consegue
atribuir requisitos, decisões e ações a responsáveis.

**Ruim:** "Acho que deveríamos mudar o prazo."
**Bom:** "Aqui é Ricardo Fontes, Operações. Proponho mudar o prazo para 15 de agosto."

### 2. Declarar o escopo na abertura
Definir explicitamente o que está dentro e fora do escopo da reunião no início
dá ao pipeline contexto para classificar e filtrar o conteúdo.

**Ruim:** *(reunião começa sem contexto)* "Então, sobre o módulo de estoque..."
**Bom:** "Esta reunião cobre o processo de gestão de estoque da loja Centro, do pedido de reposição ao recebimento. Não cobriremos a integração com o ERP central nem o processo do CD."

### 3. Verbalizar decisões explicitamente
Gestos, silêncios e assentimentos não aparecem na transcrição. Decisões implícitas
viram lacunas nos artefatos.

**Ruim:** "Todo mundo concorda? Então tá bom."
**Bom:** "Ficamos formalmente decididos: o prazo de go-live é 15 de agosto. Adriana confirma."

### 4. Fechar action items com responsável e prazo
O agente de ata extrai action items por padrões linguísticos. Sem nome e data,
o item fica vago ou é perdido.

**Ruim:** "Alguém tem que levantar os requisitos de integração."
**Bom:** "Camila Teixeira ficará responsável por levantar os requisitos de integração com o PDV até sexta-feira, 11 de julho."

### 5. Usar verbalization echoing
O facilitador resume em voz alta o que cada participante disse e aguarda confirmação.
Este comportamento cria o "rastro de confirmação" mais valioso para o pipeline.

**Conceito:** Quando o SME descreve algo, o facilitador eco-verbaliza:
> "Então, se entendi: o processo começa quando X acontece; se Y, segue para Z;
> caso contrário, apenas W é registrado. Correto?"

O participante corrige se necessário. O "Correto" ou "Confirmo" resultante é o
momento mais rastreável de toda a transcrição — a decisão ou processo tem origem, speaker e validação na mesma sequência.

**Ruim:** *(facilitador segue para o próximo tópico sem resumir)*
**Bom:** "Adriana Lemos: Incorporado. Ficamos com um gateway adicional no recebimento: se mercadoria confere, confirma e encerra; se há divergência, registra e aciona tratativa com o CD." / "Ricardo Fontes: Confirmo."

### 6. Reservar 5 minutos para fechamento explícito
A última fala da reunião é a mais processável. Um resumo verbal de decisões
e action items resolve lacunas acumuladas em toda a transcrição.

---

## Guia do Facilitador

### Antes da Reunião

- Enviar agenda com itens específicos e resultado esperado de cada item
  (ex.: "Definir responsável pelo levantamento de requisitos de integração — decisão")
- Informar que a reunião será transcrita e processada pelo P2D
- Identificar antecipadamente participantes-chave que precisam estar presentes
  (participante ausente = lacuna nos artefatos)
- Definir papéis: quem facilita, quem controla o tempo
- Preparar o **escopo** por escrito antes da reunião

### Abertura Padrão (script)

> "Vou iniciar a gravação. Para garantir que o conhecimento desta reunião fique
> rastreável, peço que cada um se identifique pelo nome e cargo antes de falar
> pela primeira vez.
>
> O escopo desta reunião cobre [descrever]. Não entraremos em [excluir].
>
> Ao tomarmos uma decisão, vou verbalizá-la explicitamente e pedir confirmação.
> Ao definirmos um encaminhamento, vou confirmar nome, tarefa e prazo em voz alta.
> Começamos."

### Durante a Reunião

**Ao perceber uma decisão implícita:**
> "Confirmando em voz alta: ficamos decididos que [decisão]. Todos confirmam?"

**Ao definir um encaminhamento:**
> "[Nome], você ficará responsável por [tarefa] e nos apresentará o resultado até [data]. Correto?"

**Ao descrever um processo (verbalization echoing):**
> "Deixa eu resumir o que você descreveu para ficar registrado: o processo começa
> quando [gatilho]. Se [condição], então [ação A]. Caso contrário, [ação B].
> Há alguma exceção que não mencionamos?"

**Ao identificar compromisso condicional:**
> "Ouvi 'vou tentar' — precisamos de um compromisso formal. Você consegue confirmar
> que [tarefa] estará pronta até [data]?"

### Fechamento Padrão (script)

> "Vou usar os últimos 5 minutos para resumir o que ficou decidido e os encaminhamentos.
> [Lista decisões e action items explicitamente.] Alguém vê algo que ficou faltando?
> Esses resultados serão verificáveis nos artefatos gerados pelo P2D após a reunião."

---

## Perfis de Participantes Desafiadores

Todo facilitador encontra personalidades que dificultam a extração de conhecimento rastreável.
Identificar o perfil e ter a resposta certa evita que um participante comprometa a qualidade
da transcrição inteira.

| Perfil | Comportamento | Efeito na transcrição | Como gerenciar |
|---|---|---|---|
| **O Silencioso** | Participa raramente; responde monossilabicamente | Perspectiva ausente; artefatos parciais | Perguntar diretamente: "João, o que você acha desta etapa do processo?" |
| **O Confrontador** | Questiona a utilidade da reunião desde o início | Interrupções que quebram o fluxo; transcrição fragmentada | Redirecionar: "Vamos executar e avaliar o resultado juntos ao final." |
| **O Cauteloso** | Compromete-se condicionalmente para proteger sua posição | "Vou tentar" e "se der" viram action items vagos e não rastreáveis | Esclarecer o propósito: "O registro protege a todos, inclusive você." |
| **O Monopolizador** | Conduz o conteúdo segundo sua própria agenda | Transcrição desequilibrada; artefatos refletem um único ponto de vista | Técnicas de votação; interromper construtivamente: "Vamos ouvir as outras perspectivas." |
| **O Disperso** | Inicia conversas paralelas; muda de assunto frequentemente | Falas irrelevantes aumentam ruído; chunker segmenta mal | Trazer de volta: "Voltando ao processo que estávamos descrevendo..." |
| **O Contrário** | Critica todas as propostas sem oferecer alternativas | Transcrição cheia de negações sem resolução clara | Transformar crítica em requisito: "O que você sugere no lugar?" |
| **O Brincalhão** | Socializa e desvia o foco com humor | Longos trechos sem conteúdo processável | Lembrar o propósito; usar timer visível; retomar agenda |

---

## Antipadrões de Reunião Processável

Problemas recorrentes que fazem as reuniões produzirem transcrições de baixa qualidade.
Identificar o antipadrão antes ou durante a reunião é mais barato do que corrigir os artefatos depois.

| Antipadrão | Como se manifesta | Efeito nos artefatos | Como evitar |
|---|---|---|---|
| **Participante Ausente** | SME crítico não comparece; outra pessoa responde "vou perguntar para X" | Decisões atribuídas a quem não tem autoridade; action items sem dono real | Confirmar presença individualmente no dia anterior; nenhuma reunião começa sem o SME crítico |
| **Multitarefa** | Celulares, laptops, conversas paralelas; falas incompletas por distração | Frases cortadas; NLPChunker segmenta incorretamente | Regra do grupo: sem dispositivos; acordar no início |
| **Patrocinador Ausente** | Sem declaração de propósito na abertura; ninguém define o que a reunião deve produzir | Pipeline sem contexto de escopo; artefatos sem foco | Briefar o patrocinador antes; coach o script de abertura |
| **Compromisso Condicional** | "Vou tentar", "se der", "talvez a gente consiga" | Action items sem comprometimento real; follow-up impossível | Interromper educadamente: "Precisamos de uma confirmação ou de uma alternativa" |
| **Proxy Sem Autonomia** | Participante que não pode decidir nada sozinho; tudo fica "para confirmar" | Reunião sem decisões; ata vazia; nenhum artefato rastreável | Mapear quem tem autoridade antes e convidá-los diretamente |
| **Facilitador Viesado** | Facilitador emite opiniões de conteúdo como se fossem do grupo | Pipeline atribui decisões ao facilitador; rastro incorreto | Facilitador deve perguntar, nunca afirmar conteúdo |
| **Modelo Rejeitado** | Participantes não reconhecem os artefatos gerados; "isso não é o que eu disse" | Retrabalho; perda de confiança na ferramenta | Promover a sessão de verificação dos artefatos após o pipeline |

---

## Padrões de Linguagem: Processável vs. Ambíguo

| Situação | Linguagem Ambígua | Linguagem Processável |
|---|---|---|
| Decisão | "Vamos fazer assim então." | "Decidimos que o módulo será implementado em duas fases. Adriana confirma." |
| Action item | "Precisa levantar os dados." | "Ricardo vai levantar os dados de consumo médio por SKU até 11/07." |
| Compromisso condicional | "Vou tentar ter isso pronto." | "Confirmo que entregarei o documento até sexta, 11/07." |
| Processo — início | "Quando tem uma venda..." | "O processo inicia quando o caixa confirma o pagamento no PDV." |
| Processo — condição | "Aí depende do estoque." | "Se o saldo estiver abaixo do mínimo, o sistema dispara o pedido. Caso contrário, apenas registra a saída." |
| Responsável vago | "O time de TI cuida disso." | "Adriana Lemos, como Gerente de TI, é a responsável pela configuração da API." |
| Prazo implícito | "Logo, logo a gente resolve." | "A definição técnica precisa estar pronta até a próxima reunião, 18/07." |
| Sigla sem contexto | "Vamos usar o MRP." | "Vamos usar o módulo MRP — Planejamento de Recursos de Materiais — do ERP atual." |
| Verbalization echo | *(facilitador avança sem resumir)* | "Então decidimos que X, com exceção Y se Z acontecer — correto?" / "Correto." |

---

## Exercício do Módulo

### Cenário
Reunião de kick-off para implementação do módulo de gestão de estoque integrado
ao PDV na rede de lojas RetailPro. Três participantes: Adriana Lemos (TI),
Ricardo Fontes (Operações) e Camila Teixeira (Supervisora de Loja).
A pauta é a mesma nas duas transcrições. Os resultados são muito diferentes.

### Passo 1 — Comparação de pipeline

1. **Carregar a transcrição 7A** (reunião mal conduzida) no pipeline
2. Observar o **Grau de Qualidade** — especialmente a dimensão "Condução da Reunião"
3. Analisar o BPMN gerado: quantos gateways? As lanes estão corretas?
4. Ver a lista de requisitos: estão com responsável e origem rastreável?
5. Verificar a ata: os action items têm nome e prazo?
6. **Carregar a transcrição 7B** (mesma reunião, bem conduzida) no pipeline
7. Repetir a análise e **comparar os dois resultados**

### Passo 2 — Identificar os antipadrões e perfis na 7A

Releia a transcrição 7A e identifique:
- Qual antipadrão de reunião está presente?
- Qual perfil de participante desafiador aparece?
- Em que momento a falta de verbalization echoing causou ambiguidade?

### Passo 3 — Sessão de verificação dos artefatos da 7B

Na guia de Exportação, baixe o **Roteiro de Verificação** gerado pelo P2D
para a transcrição 7B. Use-o como pauta de uma simulação:

1. Um participante faz o papel de Adriana Lemos
2. O facilitador apresenta cada item do roteiro:
   - Lê cada decisão: "A decisão registrada foi X — correto?"
   - Lê cada action item: "Ricardo ficará responsável por Y até Z — confirma?"
3. O participante confirma ou corrige
4. Observe como artefatos gerados de uma transcrição bem conduzida precisam
   de mínimas correções na verificação

### Perguntas de Discussão

- Qual foi a diferença no Grau de Qualidade entre as duas transcrições?
- O BPMN da 7B capturou gateways que a 7A perdeu? Quais?
- Os action items da ata da 7B têm responsável e prazo? E os da 7A?
- Quais comportamentos do facilitador na 7B tiveram maior impacto no resultado?
- Que mudanças vocês fariam nas próximas reuniões da sua empresa?

---

## Checklists de Bolso

### Para o Facilitador
- [ ] Escopo definido e escrito antes da reunião
- [ ] Agenda enviada com resultado esperado por item
- [ ] SMEs críticos confirmados individualmente no dia anterior
- [ ] Participantes informados sobre transcrição e P2D
- [ ] Abertura com script de escopo + identificação
- [ ] Verbalization echoing após cada descrição de processo
- [ ] Cada decisão verbalizada explicitamente com confirmação
- [ ] Cada action item com nome + tarefa + prazo
- [ ] Processos descritos com gatilho, sequência e condições
- [ ] Fechamento de 5 minutos com resumo de decisões e encaminhamentos
- [ ] Roteiro de Verificação gerado e agendado para revisão com os participantes

### Para Cada Participante
- [ ] Me identifico pelo nome antes de falar pela primeira vez
- [ ] Quando faço uma proposta, uso "eu proponho que..." ou "sugiro que..."
- [ ] Quando assumo um compromisso, confirmo: "eu, [nome], farei [tarefa] até [data]"
- [ ] Não uso "vou tentar" ou "se der" — confirmo ou proponho alternativa
- [ ] Quando descrevo um processo, começo pelo gatilho e uso linguagem sequencial
- [ ] No fechamento, confirmo se meus encaminhamentos foram capturados corretamente
- [ ] Estou presente e focado — sem celular nem conversas paralelas

---

## Referências Internas

- Módulo 0 — Fundamentos: o que cada artefato significa e como o pipeline processa a entrada
- Módulo 1 — Mapeamento de Processos: como gateways e lanes se formam a partir do texto
- Módulo 3 — Auditoria e Compliance: por que rastreabilidade de decisões é juridicamente relevante
