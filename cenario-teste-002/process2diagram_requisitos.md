# Especificação de Requisitos — process2diagram

**Total de requisitos:** 15

## Resumo por Tipo

| Tipo | Quantidade |
|------|-----------|
| 🖥️  Campo de tela | 1 |
| 📋  Regra de negócio | 6 |
| ⚙️  Funcional | 6 |
| 📊  Não-funcional | 2 |

## 🖥️  Campo de tela

### REQ06 — Coluna para marcar organograma atual

**Prioridade:** 🟡 Média
  **Ator:** Customer
  **Etapa do processo:** cadastro_organograma

O sistema deve incluir uma coluna ou campo para marcar qual organograma é o atual versus os obsoletos no histórico.

> **[MF]** *"por que você não tem uma coluna de para marcar ali que aquele é o atual e o resto é obsoleto."*

## 📋  Regra de negócio

### REQ04 — Organograma com data de referência

**Prioridade:** 🔴 Alta
  **Ator:** Customer
  **Etapa do processo:** cadastro_organograma

O sistema deve armazenar organogramas com uma data de referência para identificar se estão obsoletos ou atuais.

> **[PG]** *"Data de referência daquele organograma. A data de referência é tanto. eu por aqui eu já vou saber se ele é obsoleto ou não, entendeu?"*

### REQ08 — Quantidade de processos por escola

**Prioridade:** 🔴 Alta
  **Ator:** Customer
  **Etapa do processo:** controle_processos

O sistema deve capturar e exibir a quantidade de processos cadastrados por escola, incluindo informações reais e estimadas.

> **[PG]** *"Quantidade de processos, então todo o resto aqui você vai a revisão."*

### REQ09 — Data de corte para migração

**Prioridade:** 🔴 Alta
  **Ator:** Equipe
  **Etapa do processo:** migracao

O sistema deve considerar uma data de corte específica para migração, onde todas as informações do legado devem estar devidamente cadastradas.

> **[PG]** *"Há uma data de corte. Nesta data de corte, todas as informações de legado."*

### REQ12 — Unidades sem organograma obrigatório

**Prioridade:** 🔴 Alta
  **Ator:** Customer
  **Etapa do processo:** cadastro_unidade

O sistema não deve exigir organograma para unidades, permitindo cadastro simples sem vinculação a estrutura hierárquica complexa.

> **[MF]** *"unidade não tem organodrama, ponto, então esquece do se eu for cadastrar do aqui, eu não vou botar do eu vou botar aqui no seu trabalho aqui eu vou botar aqui."*

### REQ13 — Estrutura hierárquica de unidades

**Prioridade:** 🔴 Alta
  **Ator:** Equipe
  **Etapa do processo:** cadastro_unidade

O sistema deve manter estrutura hierárquica correta entre unidades e subunidades para vinculação de processos e organização.

> **[PG]** *"no nosso sistema, para que a coisa fique correta, se você quiser colocar errado, tudo bem. Mas não é a responsabilidade nossa."*

### REQ10 — Classificação de processos para BI

**Prioridade:** 🟡 Média
  **Ator:** Customer
  **Etapa do processo:** aprovacao_processo

O sistema deve permitir classificar processos por nível de interesse (estratégico, tático, operacional) para direcionar a exibição em diferentes painéis BI.

> **[PG]** *"qual é o seu nível de interesse? Se o nível de interesse é estratégico, aquilo entra para OBI da presidência."*

## ⚙️  Funcional

### REQ01 — Cadastro de unidade com código

**Prioridade:** 🔴 Alta
  **Ator:** Customer
  **Etapa do processo:** cadastro_unidade

O sistema deve permitir o cadastro de unidades, exigindo um código único para identificação, mesmo quando a unidade não tiver número pré-existente.

> **[MF]** *"Quando for unidade, a gente vai colocar começando 0101, vai ser a unidade de tesouraria."*

### REQ05 — Histórico de organogramas por escola

**Prioridade:** 🔴 Alta
  **Ator:** Customer
  **Etapa do processo:** cadastro_organograma

O sistema deve manter histórico de múltiplos organogramas distintos para cada escola, permitindo armazenar versões antigas e atuais.

> **[PG]** *"se vamos supor que você tenha Carla, vamos supor que você tem em histórico de 5 organogramas distintos, é importante para você ter os 5."*

### REQ07 — Planilha Excel para migração

**Prioridade:** 🔴 Alta
  **Ator:** Equipe
  **Etapa do processo:** migracao

O sistema deve utilizar planilhas Excel para coleta de informações de migração, com colunas definidas para unidade, organograma, data de referência, etc.

> **[PG]** *"Então vamos trabalhar no Excel para você,? Mas a ideia, de qualquer forma, a ideia é essa."*

### REQ02 — Pré-visualização de arquivos PDF

**Prioridade:** 🟡 Média
  **Ator:** Customer

O sistema deve oferecer pré-visualização para arquivos PDF, permitindo visualização direta na tela sem necessidade de download ou software externo.

> **[PG]** *"arquivos que são visualizáveis dentro do se Suite. São os arquivos PDFE, os arquivos de imagem."*

### REQ03 — Pré-visualização de arquivos Word e Excel

**Prioridade:** 🟡 Média
  **Ator:** Customer

O sistema deve oferecer pré-visualização para arquivos Word e Excel, permitindo visualização direta na tela.

> **[PG]** *"Word, Word tem previsualização e Excel? Então vamos lá, Word, Excel, PDF, imagens."*

### REQ11 — Validação de cadastro de unidade

**Prioridade:** 🟡 Média
  **Ator:** Equipe
  **Etapa do processo:** cadastro_unidade

O sistema deve incluir uma atividade de validação para cadastro de unidades, permitindo ajustes e roteamento para outras atividades como CT, ITE, fluxo.

> **[NC]** *"essa atividade é que faz hub que pode mandar para todos os locais, que é isso que nós estamos. Te mostrando correto que foi isso que nós combinamos."*

## 📊  Não-funcional

### REQ15 — Entrega completa do sistema até data

**Prioridade:** 🔴 Alta
  **Ator:** Equipe

O sistema deve ser totalmente construído e apresentado até uma data específica (ex: 24 de março) para validação e homologação pelo cliente.

> **[JL]** *"Até o dia. 24 de Marcos. Todo o sistema do dia 24 de Moraes, isso significa que quando a gente mostrar para você."*

### REQ14 — Flexibilidade para futuros BI

**Prioridade:** 🟡 Média
  **Ator:** Equipe

O sistema deve ser flexível para permitir criação de múltiplos painéis BI no futuro, sem necessidade de mudanças estruturais.

> **[PG]** *"a gente quer deixar a coisa flexível o suficiente para que você depois possa ter vários. Precisa, precisa, precisa para a gente não chegar lá na frente e ter que e ter que mudar lá na frente."*
