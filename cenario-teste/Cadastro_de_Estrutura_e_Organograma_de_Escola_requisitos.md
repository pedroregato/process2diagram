# Especificação de Requisitos — Cadastro de Estrutura e Organograma de Escola

**Total de requisitos:** 25

## Resumo por Tipo

| Tipo | Quantidade |
|------|-----------|
| 🖥️  Campo de tela | 11 |
| ✅  Validação | 4 |
| 📋  Regra de negócio | 1 |
| ⚙️  Funcional | 7 |
| 📊  Não-funcional | 2 |

## 🖥️  Campo de tela

### REQ02 — Campo código da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para inserir o código da escola durante o cadastro do organograma.

> **[MF]** *"Você tem que cadastrar o código da escola e o nome da escola."*

### REQ03 — Campo nome da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para inserir o nome da escola durante o cadastro do organograma.

> **[MF]** *"Você tem que cadastrar o código da escola e o nome da escola."*

### REQ06 — Campo diretor da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para selecionar ou inserir o diretor responsável pela escola no cadastro do organograma.

> **[NC]** *"Você vai selecionar o diretor da escola, certo? Quem o responsável? Quem o diretor?"*

### REQ07 — Campo catálogo mestre obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo obrigatório para indicar se a escola possui catálogo mestre, com opções sim/não.

> **[NC]** *"Catálogo possui catálogo mestre? Sim, obrigatório quando a gente está fazendo o cadastro de escola."*

### REQ10 — Botão cadastrar unidades

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um botão para avançar para a etapa de cadastro das unidades inferiores da escola, após concluir o cadastro inicial.

> **[NC]** *"Você vai clicar aqui, cadastrar unidades inferiores, que eu estou entrando dentro do organograma, eu vou fazer as outras coisas que estão lá dentro do organograma."*

### REQ11 — Campo tipo da unidade

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo para especificar o tipo da unidade (ex: vice-diretoria, assessoria) durante o cadastro de unidades.

> **[NC]** *"Tenho aqui o tipo, então vamos dizer que eles estão, eu estou na direção, vou cadastrar aqui a primeira vice-diretoria."*

### REQ12 — Campo código da unidade

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo para inserir um código único para cada unidade cadastrada no organograma.

> **[MF]** *"Tipo da Trindade perfeito, código da Trindade, nome da Trindade perfeito."*

### REQ13 — Campo nome da unidade

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo para inserir o nome descritivo de cada unidade cadastrada no organograma.

> **[MF]** *"Tipo da Trindade perfeito, código da Trindade, nome da Trindade perfeito."*

### REQ14 — Campo responsável da unidade

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo para selecionar ou inserir o responsável por cada unidade cadastrada.

> **[MF]** *"responsa, já estou vendo, ? E hierarquia novo da Trindade Perfeito."*

### REQ15 — Campo hierarquia da unidade

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo para vincular cada unidade à sua unidade superior no organograma, permitindo selecionar entre as unidades já cadastradas.

> **[NC]** *"Vincular a hierarquia, certo? Aqui eu vou botar a diretoria, que o primeiro certo."*

### REQ16 — Campo possui catálogo técnico

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo para indicar se a unidade possui catálogo técnico, com opções sim/não, substituindo a opção genérica 'documentação'.

> **[MF]** *"Se você aqui no sistema só quer documentar, se vai ter catálogo técnico, a pergunta tem que ser objetiva, tem catálogo técnico?"*

## ✅  Validação

### REQ01 — Título do fluxo obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** inicialização do fluxo

O sistema deve exigir que o usuário preencha um título ao iniciar um fluxo de cadastro de organograma, para facilitar a identificação e gestão de múltiplos fluxos pendentes.

> **[PG]** *"Se você não colocar o título no dia seguinte, você não vai achar nada, porque não vai estar nada na sua atividade."*

### REQ04 — Código da escola único

**Prioridade:** 🔴 Alta
  **Ator:** sistema
  **Etapa do processo:** cadastro da escola

O sistema deve validar que o código da escola inserido não esteja já cadastrado, impedindo duplicidades.

> **[NC]** *"Tem que botar outro número, 28 já tem cadastrado isso."*

### REQ09 — Validação mínimo dois arquivos

**Prioridade:** 🔴 Alta
  **Ator:** sistema
  **Etapa do processo:** cadastro da escola

O sistema deve validar que pelo menos dois arquivos sejam anexados: o organograma e a aprovação.

> **[NC]** *"No mínimo, 2. No mínimo, 2. No mínimo, 2."*

### REQ20 — Opção devolver com observação

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** validação

O sistema deve exigir que uma observação seja preenchida obrigatoriamente ao devolver o cadastro para ajustes na validação.

> **[MF]** *"Quando eu clicar na opção voltar, eu tenho que ter aquele campo XPTO que observação campo que você tem que dizer como obrigatório."*

## 📋  Regra de negócio

### REQ19 — Validação por equipe

**Prioridade:** 🔴 Alta
  **Ator:** sistema
  **Etapa do processo:** validação

O sistema deve direcionar o organograma cadastrado para uma equipe de validação, onde um membro pode assumir a tarefa.

> **[NC]** *"Nós combinamos que essa atividade de validação ela cairia numa equipe."*

## ⚙️  Funcional

### REQ05 — Botão salvar e continuar depois

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve permitir salvar o progresso do cadastro e retomar posteriormente, sem perder os dados preenchidos.

> **[NC]** *"Porque você pode entrar aqui e colocar aqui o 16 escola ABC teste e salvar, fechar essa tela e vir aqui e terminar mais tarde."*

### REQ08 — Anexar arquivos do organograma

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve permitir anexar arquivos (ex: PDF, imagem) do organograma durante o cadastro, com suporte a múltiplos arquivos.

> **[NC]** *"Você vai colocar ele aqui, a gente está dentro do sistema que ele não existe aqui ainda, certo? Se eu clicar aqui em aqui inserir arquivos, certo?"*

### REQ17 — Soma automática catálogos previstos

**Prioridade:** 🔴 Alta
  **Ator:** sistema
  **Etapa do processo:** cadastro de unidades

O sistema deve calcular automaticamente o total de catálogos técnicos previstos com base nas unidades marcadas com 'sim' no campo possui catálogo técnico.

> **[NC]** *"Conforme você fizer aqui e você colocar sim e não, eu somo aqui ou eu só somo no total de unidades que essa escola tem?"*

### REQ21 — Visualização do organograma anexado

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** validação

O sistema deve permitir visualizar os arquivos do organograma anexados durante a validação, para conferência.

> **[PG]** *"Os organogramas são acessáveis, acessíveis através da dessa tela aqui do organograma. Olha aqui, só clicar."*

### REQ24 — Identificador único do processo

**Prioridade:** 🔴 Alta
  **Ator:** sistema

O sistema deve gerar automaticamente um identificador único para cada instância do fluxo de cadastro de organograma.

> **[NC]** *"Cada desses aqui uma demanda. Cada linha dessa uma demanda diferente."*

### REQ18 — Edição de unidades cadastradas

**Prioridade:** 🟡 Média
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve permitir editar as informações das unidades já cadastradas antes de finalizar a etapa, com alterações refletidas automaticamente.

> **[NC]** *"Você pode alterar, por exemplo, você viu que digitou errado? Você pode vim aqui e voltar."*

### REQ23 — Prioridade manual no portal

**Prioridade:** 🟡 Média
  **Ator:** gestor

O sistema deve oferecer um portal onde o gestor possa definir e alterar manualmente a prioridade das tarefas pendentes da equipe.

> **[NC]** *"A gente vai ver isso com o João, porque essa questão de prioridade ela também não estava no escopo, mas como o João falou ali, a gente vai ver se consegue botar isso para vocês no portal."*

## 📊  Não-funcional

### REQ22 — SLA configurável por processo

**Prioridade:** 🟡 Média
  **Ator:** administrador

O sistema deve permitir configurar acordos de nível de serviço (SLA) com prazos para a execução do processo de cadastro de organograma.

> **[NC]** *"Pra pra gente definir OSLA, eu preciso o quê? Eu preciso definir qual a duração de cada uma dessas atividades aqui e qual o tempo máximo que esse processo pode ser deve ser executado."*

### REQ25 — Histórico de execução

**Prioridade:** 🟡 Média
  **Ator:** sistema

O sistema deve manter um histórico detalhado de todas as atividades executadas no fluxo, incluindo quem executou e quando.

> **[NC]** *"Você vai ter também o histórico para ter o controle e saber exatamente a mente, o que foi feito, quem executou, como executou?"*
