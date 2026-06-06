# Módulo 2 — Rastreabilidade de Requisitos em Projetos de TI

**Duração:** 2 horas
**Pré-requisito:** Módulo 0 concluído

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Gerar requisitos IEEE 830 com origem rastreada a partir de reuniões de projeto
- Usar o Assistente RAG para responder perguntas sobre escopo e decisões
- Criar uma base de requisitos consultável por toda a equipe

---

## Contexto do Problema

### O custo do escopo mal rastreado

Em projetos de TI, mudanças de escopo não documentadas custam em média 20–40%
do orçamento do projeto (PMI, 2023). O problema não é a mudança em si — é não
saber o que foi decidido, por quem e em que reunião.

Perguntas que o time não consegue responder sem rastreabilidade:
- "Por que implementamos essa funcionalidade?"
- "Quem aprovou o requisito de biometria?"
- "O que mudou entre a reunião 3 e a reunião 7?"
- "Esse requisito veio do cliente ou foi assumção interna?"

O P2D resolve isso indexando cada reunião e mantendo a citação original
de onde cada requisito surgiu.

---

## Cenário — Kick-off do Portal do Cliente

### Arquivo
`transcricao_02_kickoff_portal_cliente.txt`

### Contexto
A empresa de seguros SegurançaTotal está desenvolvendo um portal de autoatendimento
para que clientes possam fazer cotações, contratar apólices e registrar sinistros
online. Esta é a reunião de kick-off com o time de projeto e o representante do cliente.

Participantes:
- **Fernanda** — Gerente de Projeto (PM)
- **Diego** — Desenvolvedor Sênior
- **Lívia** — Designer UX/UI
- **Paulo** — Product Owner
- **Kátia** — Representante do cliente (SegurançaTotal)

### O que esperar do pipeline

**Requisitos gerados (esperado: 12–18 requisitos):**

Funcionais:
- RF-01: Portal deve permitir cotação de seguro em até 3 minutos
- RF-02: Cliente pode fazer upload de documentos para sinistros
- RF-03: Sistema deve integrar com o legado SIS-SEG via API REST
- RF-04: Notificações por e-mail e SMS em cada etapa do sinistro
- RF-05: Histórico completo de apólices e pagamentos acessível pelo cliente

Não-funcionais:
- RNF-01: Disponibilidade de 99,5% (exceto janela de manutenção)
- RNF-02: Tempo de resposta máximo de 2 segundos para 95% das requisições
- RNF-03: Conformidade com LGPD — consentimento explícito e opção de exclusão de dados

Interface:
- RI-01: Compatível com Chrome, Firefox e Safari versões recentes
- RI-02: Design responsivo para mobile (smartphone e tablet)

Restrição:
- RR-01: Entrega da primeira versão em 4 meses
- RR-02: Orçamento máximo de R$ 380.000

### Passo a Passo

1. Cole a transcrição e execute o pipeline
2. Acesse a aba **Requisitos** — observe:
   - A coluna "Origem" mostra o trecho da fala de onde veio o requisito?
   - O responsável foi atribuído corretamente?
   - Os requisitos estão categorizados por tipo?
3. Abra o **Mind Map de Requisitos** — a hierarquia por tipo está clara?
4. Salve a reunião no projeto e abra o **Assistente RAG**

### Exercício com o Assistente RAG

Com a reunião indexada, faça as seguintes perguntas ao Assistente:

```
1. "Quem levantou o requisito de integração com o SIS-SEG?"
2. "Quais requisitos têm a Kátia como origem?"
3. "O prazo de entrega foi definido pelo cliente ou pelo time?"
4. "Existe algum requisito relacionado à LGPD?"
5. "Quais action items ficaram pendentes ao final da reunião?"
```

### Exercício Avançado: Análise de Evolução (requer 2 reuniões)

Se o grupo tiver tempo, rode também a reunião de refinamento (exercício extra):
1. Crie uma segunda reunião fictícia onde o requisito de biometria é adicionado
2. Use o Assistente para comparar: "O que mudou nos requisitos de autenticação entre a reunião 1 e a reunião 2?"

### Perguntas de Discussão

1. Quantos requisitos o P2D extraiu vs. quantos você esperava encontrar?
2. Algum requisito extraído surpreendeu o grupo — algo que estava implícito na conversa?
3. Como você usaria isso na prática para responder ao cliente quando ele diz "isso não estava no escopo"?
4. Qual a diferença entre requisito funcional e não-funcional no contexto deste projeto?

---

## Consolidação do Módulo (15 min)

### Fluxo de trabalho recomendado

```
Reunião de kick-off
    → Transcrição (automática ou manual)
    → Pipeline P2D
    → Revisão dos requisitos com o time (30 min)
    → Aprovação do PO
    → Base de requisitos indexada no projeto
    → Assistente disponível para toda a equipe
```

### O que levar para o trabalho

1. **Gravar reuniões de projeto** — mesmo que a transcrição precise de revisão,
   o custo é muito menor do que reconstruir requisitos depois
2. **Usar o Assistente como "memória do projeto"** — qualquer membro do time
   pode consultar decisões tomadas em reuniões anteriores
3. **Revisão de requisitos como cerimônia** — após cada rodada de P2D, uma sessão
   de 30 minutos com o time para validar e aprovar o que foi extraído
