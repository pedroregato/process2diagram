# Especificação de Requisitos — Cadastro de estrutura e organograma de escola

**Total de requisitos:** 18

## Resumo por Tipo

| Tipo | Quantidade |
|------|-----------|
| 🖥️  Campo de tela | 6 |
| ✅  Validação | 3 |
| 📋  Regra de negócio | 1 |
| ⚙️  Funcional | 6 |
| 📊  Não-funcional | 2 |

## 🖥️  Campo de tela

### REQ02 — Campo código da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para inserir o código da escola durante o cadastro do organograma.

> *"Você tem que cadastrar o código da escola e o nome da escola."*

### REQ03 — Campo nome da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para inserir o nome da escola durante o cadastro do organograma.

> *"Você tem que cadastrar o código da escola e o nome da escola."*

### REQ04 — Campo diretor da escola

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para selecionar ou inserir o diretor da escola durante o cadastro do organograma.

> *"Você vai selecionar o diretor da escola, certo? Quem o responsável? Quem o diretor?"*

### REQ05 — Campo catálogo mestre obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um campo para indicar se a escola possui catálogo mestre, sendo obrigatório preenchê-lo durante o cadastro do organograma.

> *"Catálogo possui catálogo mestre? Sim, obrigatório quando a gente está fazendo o cadastro de escola."*

### REQ08 — Botão salvar para continuar depois

**Prioridade:** 🟡 Média
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve ter um botão de salvar que permite ao usuário salvar o progresso e retomar o cadastro posteriormente.

> *"Porque você pode entrar aqui e colocar aqui o 16 escola ABC teste e salvar, fechar essa tela e vir aqui e terminar mais tarde."*

### REQ10 — Campo catálogo técnico por unidade

**Prioridade:** 🟡 Média
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve ter um campo por unidade para indicar se possui catálogo técnico (sim/não), usado para contabilizar previsões.

> *"Esta unidade possui catálogo técnico? eu falo sim ou não?"*

## ✅  Validação

### REQ01 — Título do fluxo obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** inicialização do fluxo

O sistema deve exigir que o usuário preencha um título ao iniciar um fluxo de cadastro de organograma, para facilitar a identificação e gestão de múltiplos fluxos pendentes.

> *"Se você não colocar o título no dia seguinte, você não vai achar nada, porque não vai estar nada na sua atividade."*

### REQ07 — Validação mínimo dois arquivos

**Prioridade:** 🔴 Alta
  **Ator:** sistema
  **Etapa do processo:** cadastro da escola

O sistema deve validar que pelo menos dois arquivos sejam anexados: o organograma e o e-mail de aprovação.

> *"No mínimo, 2. No mínimo, organograma e aprovação."*

### REQ13 — Campo observação na devolução

**Prioridade:** 🔴 Alta
  **Ator:** validador
  **Etapa do processo:** validação

Ao devolver um organograma para ajustes, o validador deve preencher um campo de observação obrigatório explicando os ajustes necessários.

> *"Quando eu clicar na opção voltar, eu tenho que ter aquele campo XPTO que observação campo que você tem que dizer como obrigatório."*

## 📋  Regra de negócio

### REQ12 — Validação de organograma por equipe

**Prioridade:** 🔴 Alta
  **Ator:** sistema
  **Etapa do processo:** validação

O sistema deve direcionar o organograma cadastrado para uma equipe de validação, onde um validador pode aprovar ou devolver com ajustes.

> *"Essa Equipe, você vai me dizer quem vai fazer parte, certo? Vai aparecer daquela forma que estava antes."*

## ⚙️  Funcional

### REQ06 — Anexar arquivos do organograma

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro da escola

O sistema deve permitir anexar arquivos (como PDF) do organograma e e-mail de aprovação durante o cadastro.

> *"Você vai colocar ele aqui, a gente está dentro do sistema que ele não existe aqui ainda, certo? Se eu clicar aqui em aqui inserir arquivos, certo?"*

### REQ09 — Cadastro de unidades do organograma

**Prioridade:** 🔴 Alta
  **Ator:** usuário
  **Etapa do processo:** cadastro de unidades

O sistema deve permitir cadastrar unidades (como vice-diretoria, assessoria) dentro do organograma, com campos para tipo, código, nome e responsável.

> *"Aqui nós vamos cadastrar agora a vice, vice, diretoria, botei 16.1 e eu vou botar aqui vice, diretoria, escola ABC."*

### REQ11 — Contagem automática de catálogos previstos

**Prioridade:** 🟡 Média
  **Ator:** sistema
  **Etapa do processo:** cadastro de unidades

O sistema deve calcular automaticamente o total de catálogos técnicos previstos com base nas unidades marcadas com 'sim' no campo catálogo técnico.

> *"Conforme você fizer aqui e você colocar sim e não, eu somo aqui ou eu só somo no total de unidades que essa escola tem?"*

### REQ14 — Visualização do organograma anexado

**Prioridade:** 🟡 Média
  **Ator:** validador
  **Etapa do processo:** validação

O sistema deve permitir visualizar o arquivo do organograma anexado durante a validação para conferência.

> *"Clica agora no organogram e você já cadastrou, clica aqui e mostra agora o cadastro desse organogram."*

### REQ16 — Prioridade manual de atividades

**Prioridade:** 🟡 Média
  **Ator:** gestor

O sistema deve permitir que um gestor atribua prioridade manualmente às atividades pendentes de uma equipe, para facilitar a gestão de carga de trabalho.

> *"Eu posso ir lá e mudar. Como que fica a prioridade? Fica em morte crescente, 123, como que fica essa prioridade aparece?"*

### REQ18 — Histórico de execução do processo

**Prioridade:** 🟡 Média
  **Ator:** sistema

O sistema deve manter um histórico detalhado de todas as atividades executadas no processo, incluindo datas, responsáveis e ações.

> *"Você vai ter também o histórico para ter o controle e saber exatamente o que foi feito, quem executou, como executou?"*

## 📊  Não-funcional

### REQ17 — Identificador único de processo

**Prioridade:** 🟡 Média
  **Ator:** sistema

O sistema deve gerar automaticamente um identificador único para cada instância de processo (fluxo) de cadastro de organograma.

> *"Cada desses aqui uma demanda. Cada linha dessa uma demanda diferente."*

### REQ15 — SLA configurável por processo

**Prioridade:** 🟢 Baixa
  **Ator:** administrador

O sistema deve permitir configurar acordos de nível de serviço (SLA) com prazos para a execução do processo de cadastro de organograma.

> *"Pra pra gente definir OSLA, eu preciso o quê? Eu preciso definir qual a duração de cada uma dessas atividades aqui e qual o tempo máximo que esse processo pode ser executado."*
