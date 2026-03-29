# Especificação de Requisitos — Cadastro de Estrutura e Organograma de Escola

**Total de requisitos:** 16

## Resumo por Tipo

| Tipo | Quantidade |
|------|-----------|
| 🖥️  Campo de tela | 5 |
| ✅  Validação | 3 |
| ⚙️  Funcional | 6 |
| 📊  Não-funcional | 2 |

## 🖥️  Campo de tela

### REQ02 — Código e nome da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter campos para código da escola e nome da escola no formulário de cadastro de organograma.

> **[MF]** *"O Pedro falou para mim o seguinte, você tem que cadastrar o código da escola e o nome da escola."*

### REQ06 — Cadastro de unidades com tipo, código, nome

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter campos para tipo, código, nome e responsável no cadastro de cada unidade do organograma.

> **[MF]** *"Tipo da Trindade perfeito, código da Trindade, nome da Trindade perfeito, perfeito, maravilha, perfeito, responsa, já estou vendo."*

### REQ07 — Hierarquia de unidades

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve permitir vincular cada unidade a sua unidade superior no organograma, com seleção a partir de uma lista das unidades já cadastradas.

> **[NC]** *"Vincular a hierarquia, certo? Aqui eu vou botar a diretoria, que o primeiro certo."*

### REQ08 — Indicação de catálogo técnico por unidade

**Prioridade:** 🟡 Média
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve permitir indicar se cada unidade possui catálogo técnico (sim/não), com campo renomeado de 'documentação' para 'catálogo técnico'.

> **[MF]** *"Esta unidade possui documentação. Por que ainda a documentação já não entra o catálogo bonitinho?"*

### REQ16 — Botão de cancelar em formulários

**Prioridade:** 🟢 Baixa
  **Ator:** usuário

O sistema deve incluir um botão de cancelar em formulários para fechar sem salvar, posicionado distante dos botões de salvar para evitar acionamento acidental.

> **[PG]** *"Cancelar somente feche. Quer dizer o seguinte, feche sem salvar, não salva não, porque eu não quero essa informação."*

## ✅  Validação

### REQ01 — Título do fluxo obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** inicialização do fluxo

O sistema deve exigir que o usuário preencha um título ao iniciar um fluxo de cadastro de organograma, para facilitar a identificação e gestão de múltiplos fluxos pendentes.

> **[PG]** *"Se você não colocar o título no dia seguinte, você não vai achar nada, porque não vai estar nada na sua atividade."*

### REQ03 — Diretor da escola obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve exigir a seleção do diretor da escola no cadastro da primeira unidade (diretoria).

> **[NC]** *"Você vai selecionar o diretor da escola, certo? Quem o responsável? Quem o diretor?"*

### REQ04 — Catálogo mestre obrigatório para escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

No cadastro da primeira unidade (diretoria) de uma escola, o sistema deve exigir a indicação de que possui catálogo mestre.

> **[NC]** *"Catálogo possui catálogo mestre? Sim, obrigatório quando a gente está fazendo o cadastro de escola."*

## ⚙️  Funcional

### REQ05 — Anexo de organograma e aprovação

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve permitir o anexo de arquivos, incluindo pelo menos o organograma (ex: PDF) e o e-mail de aprovação, com validação de mínimo de 2 arquivos.

> **[NC]** *"No mínimo, 2. No mínimo, 2. No mínimo, 2."*

### REQ10 — Salvar e continuar depois

**Prioridade:** 🔴 Alta
  **Ator:** usuário

O sistema deve permitir salvar o progresso do cadastro e retomá-lo posteriormente a partir da tela 'Minhas tarefas'.

> **[NC]** *"Você pode entrar aqui e colocar aqui o 16 escola ABC teste e salvar, fechar essa tela e vir aqui e terminar mais tarde."*

### REQ11 — Validação com opção de devolver

**Prioridade:** 🔴 Alta
  **Ator:** validador
  **Etapa do processo:** validação

O sistema deve permitir que o validador devolva o cadastro para ajustes, com campo obrigatório de observações para justificar a devolução.

> **[NC]** *"Se você botar aqui observação e devolver para ajuste, se você clicar aqui em devolver, devolvendo para a atividade anterior, para que eles façam essa correção, você tem que colocar aqui o que você quer que eles corrijam."*

### REQ12 — Visualização do organograma anexado

**Prioridade:** 🔴 Alta
  **Ator:** validador
  **Etapa do processo:** validação

O sistema deve permitir visualizar o organograma anexado (ex: PDF) durante a validação para conferência.

> **[MF]** *"Clica agora no organogram e você já cadastrou, clica aqui e mostra agora o cadastro desse organogram."*

### REQ09 — Contagem automática de unidades e catálogos

**Prioridade:** 🟡 Média
  **Ator:** sistema
  **Etapa do processo:** cadastro de unidades

O sistema deve calcular e exibir automaticamente o total de unidades cadastradas e o total de catálogos técnicos previstos (baseado nas respostas 'sim'), sem necessidade de preenchimento manual.

> **[NC]** *"Conforme você fizer aqui e você colocar sim e não, eu somo aqui ou eu só somo no total de unidades que essa escola tem?"*

### REQ14 — Prioridade manual via portal

**Prioridade:** 🟡 Média
  **Ator:** gestora

O sistema deve oferecer um portal onde a gestora possa definir e alterar manualmente a prioridade das tarefas pendentes da equipe.

> **[MF]** *"A prioridade, ela vai ter e ter essa prioridade, cada vai ter a sua prioridade diariamente, que eu posso ir lá e mudar."*

## 📊  Não-funcional

### REQ13 — SLA configurável por processo

**Prioridade:** 🟡 Média
  **Ator:** área

O sistema deve permitir configurar acordos de nível de serviço (SLA) com prazos para a execução do processo de cadastro de organograma.

> **[NC]** *"Pra pra gente definir o SLA, eu preciso o quê? Eu preciso definir qual a duração de cada uma dessas atividades aqui e qual o tempo máximo que esse processo pode ser deve ser executado."*

### REQ15 — Identificador único de processo

**Prioridade:** 🟡 Média
  **Ator:** sistema

O sistema deve gerar automaticamente um identificador único para cada fluxo (workflow) de cadastro de organograma.

> **[NC]** *"Cada desses aqui uma demanda. Cada linha dessa uma demanda diferente."*
