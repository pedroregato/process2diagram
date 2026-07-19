# COLLABORATIVE MANIFESTO — Process2Diagram v5.12 (PC195)
## Documento de Governança Multi-Agente — ASSINADO

**Versão:** 5.12  
**Data:** 30 de junho de 2026 (§5.3 corrigido em 19 de julho de 2026, PC195)  
**Arquiteto:** Pedro Regato  
**Status:** ASSINADO — Em execução

---

## 1. FILOSOFIA DE GOVERNANÇA

> *"Nenhum agente opera sozinho. Cada decisão é rastreável. Cada falha é recuperável."*

Este manifesto estabelece as regras de colaboração entre agentes humanos e artificiais no desenvolvimento, operação e monetização do Process2Diagram (P2D).

---

## 2. AGENTES OFICIAIS

### Agente 0 — Arquiteto (Pedro Regato)
- **Papel:** Tomada de decisão estratégica, aprovação de mudanças arquiteturais, validação de propostas comerciais
- **Autoridade:** Veto em qualquer decisão técnica ou de negócio
- **Responsabilidade:** Segurança da informação, conformidade LGPD, visão de produto

### Agente 1 — Claude Code (Anthropic)
- **Papel:** Implementação de código, refatoração, testes, documentação técnica
- **Autoridade:** Decisões de implementação dentro dos princípios do ENGINEERING_MANIFESTO
- **Responsabilidade:** Qualidade de código, cobertura de testes, performance
- **Restrição:** Não decide mudanças de arquitetura sem aprovação do Agente 0

### Agente 2 — NotebookLM (Google — Gemini 1.5 Pro)
- **Papel:** Análise de documentação, geração de insights cruzados, briefings para outros agentes
- **Autoridade:** Recomendações baseadas em análise de múltiplas fontes
- **Responsabilidade:** Consistência documental, identificação de contradições, sumarização
- **Restrição:** Não executa código diretamente; output é sempre análise ou recomendação

### Agente 3 — Antigravity (Visualização & UX)
- **Papel:** Design de interfaces, visualização de dados, experiência do usuário
- **Autoridade:** Decisões de UX/UI dentro das diretrizes de acessibilidade
- **Responsabilidade:** Consistência visual, responsividade, acessibilidade WCAG 2.1
- **Restrição:** Mudanças de layout que afetem performance devem ser validadas pelo Agente 1

### Agente 4 — n8n (Orquestrador de Workflows)
- **Papel:** Automação de processos de negócio, orquestração entre sistemas, integração com clientes
- **Autoridade:** Configuração de workflows dentro dos limites de custo e segurança definidos pelo Agente 0
- **Responsabilidade:**
  - Onboarding automatizado de clientes
  - Pipeline de processamento de reuniões (trigger → API P2D → entrega)
  - Monitoramento de custos LLM e alertas
  - Faturamento e cobrança recorrente
  - Follow-up pós-reunião e nurturing de leads
- **Restrição:**
  - Não armazena credenciais em plaintext (usa Secret Manager)
  - Não executa ações sem logging completo (audit trail)
  - Custo mensal de execução não pode exceder 15% da receita do cliente (aplicado a custos variáveis: LLM + Cloud Tasks + Storage)
- **Infraestrutura:** Google Compute Engine e2-medium (4GB RAM) — R$ 45-60/mês
- **Custo alvo:** Infraestrutura = custo fixo da empresa; variáveis por cliente = cap 15%

---

## 3. DECISÕES ASSINADAS PELO AGENTE 0 (30/06/2026)

### Decisão #1: Infraestrutura n8n
- **Opção aprovada:** Google Compute Engine e2-medium (4GB RAM)
- **Custo:** R$ 45-60/mês (custo fixo da empresa, não alocado por cliente)
- **Justificativa:** e2-micro (1GB) é inviável — n8n Docker requer 4GB mínimo. e2-small (2GB) força swap e degrada performance.
- **Alternativa descartada:** n8n Cloud Starter (R$ 130/mês) — 3x mais caro, dados na UE.
- **Status:** ✅ APROVADO

### Decisão #2: Cap de Custo do Agente 4
- **Opção aprovada:** 15% da receita por cliente, aplicado APENAS a custos variáveis (LLM + Cloud Tasks + Storage do cliente)
- **Custo fixo (infra n8n, Cloud SQL, Cloud Run, Secret Manager):** Absorvido pela empresa como overhead operacional
- **Justificativa:** Com DeepSeek primário (R$ 0,053/reunião), custos variáveis são irrisórios (0,6-1,1% da receita). O cap é um freio de segurança contra uso indevido de provedores premium.
- **Status:** ✅ APROVADO

### Decisão #3: VETO Automático para Provedores Premium
- **Opção aprovada:** VETO automático para Claude (Anthropic) e Grok Multi-Agent (xAI) sem autorização explícita do Agente 0
- **Custo comparativo:**
  - DeepSeek: R$ 0,053/reunião (baseline)
  - Claude: R$ 1,849/reunião (34,9x mais caro)
  - Grok Multi-Agent: R$ 0,916/reunião (17,3x mais caro)
- **Justificativa:** Um único cliente usando Claude no plano Pro gera prejuízo de R$ 89,60/mês — destrói a margem de 10 clientes.
- **Status:** ✅ APROVADO

### Decisão #4: Provedor LLM Primário
- **Opção aprovada:** DeepSeek v4-flash como primário para todos os agentes
- **Fallback hierárquico:**
  1. DeepSeek v4-flash (default)
  2. OpenAI gpt-4o-mini (qualidade BPMN < 0,85)
  3. Grok xAI (transcrições > 100K tokens)
  4. DeepSeek V4 Pro (premium, com desconto 75% até 31/05/2026)
- **Google Gemini gratuito:** DESCARTADO — tier gratuito (1.500 req/dia) não aguenta carga de produção
- **Status:** ✅ APROVADO

---

## 4. PROTOCOLOS DE COMUNICAÇÃO INTER-AGENTE

### 4.1 Formato de Handoff

Todo handoff entre agentes deve seguir o template:

```
## HANDOFF — [Origem] → [Destino]
**Data:** YYYY-MM-DD HH:MM
**Contexto:** [Resumo do que foi feito/decidido]
**Decisões pendentes:** [Lista de itens que precisam de decisão]
**Riscos identificados:** [Lista de riscos com severidade Baixa/Média/Alta]
**Próximos passos:** [Ações concretas com responsável e prazo]
```

### 4.2 Canais de Comunicação

| Canal | Uso | Exemplo |
|-------|-----|---------|
| **GitHub Issues** | Bugs, features, tasks técnicas | Agente 1 ↔ Agente 0 |
| **NotebookLM Chat** | Análise documental, briefings | Agente 2 → Todos |
| **n8n Workflows** | Automação operacional | Agente 4 → Clientes/Sistemas |
| **Email/Slack** | Comunicação externa (clientes) | Agente 0 + Agente 4 |
| **Notion/Google Docs** | Documentação viva | Todos |

### 4.3 Escalonamento de Conflitos

1. **Conflito técnico:** Agente 1 propõe → Agente 2 analisa impacto documental → Agente 0 decide
2. **Conflito de custo:** Agente 4 reporta → Agente 0 avalia ROI → Decisão em 24h
3. **Conflito de UX vs. Performance:** Agente 3 propõe → Agente 1 avalia impacto → Agente 0 decide
4. **Conflito de segurança:** VETO automático do Agente 0; análise posterior

---

## 5. REGRAS DE SEGURANÇA E COMPLIANCE

### 5.1 LGPD — Dados de Clientes

- **Dados pessoais:** Nomes, emails, transcrições de reuniões → Cloud SQL (São Paulo region)
- **Dados sensíveis:** Conteúdo de reuniões estratégicas → Criptografia AES-256 em repouso
- **Retenção:** 7 anos (conforme lei brasileira) ou conforme contrato cliente
- **Exclusão:** Workflow n8n automatizado para anonimização após prazo
- **DPO:** Agente 0 (Pedro Regato) — pedro.regato@gmail.com

### 5.2 Segurança de APIs

- **Autenticação:** X-API-Key (SHA-256) + JWT para sessões
- **Rate limiting:** 100 req/min por cliente (configurável no n8n)
- **Logging:** Todo acesso logado no Cloud Logging (GCP) com retenção de 30 dias
- **Backup:** Cloud SQL backups automáticos diários + snapshots semanais

### 5.3 Segregação de Dados (Multi-tenant)

- Um cliente (domínio, `tenant_id`) pode conter **múltiplos** projetos/contextos isolados no
  P2D — a relação é 1:N, não 1:1 (corrigido PC195; a redação anterior — "cada cliente = projeto
  isolado" — ficou desatualizada a partir do Catálogo do Domínio cross-contexto, PC165, que já
  opera com `tenant_id` ⊃ N `contexts`). Ver `manifestos/PRODUCT_MANIFESTO.md §4` para o
  vocabulário de produto completo (domínio × contexto).
- CKF (Context Knowledge File) isolado por projeto/contexto
- Grafo de conhecimento segmentado por tenant_id
- n8n workflows com variáveis de ambiente por cliente

### 5.4 Fail-Open em Infraestrutura Cloud

**Princípio:** O Fail-Open do ENGINEERING_MANIFESTO aplica-se mesmo em infraestrutura gerenciada.

**Camadas de Fallback:**
1. **Secret Manager offline:** Usar cache local (24h) → fallback ENV → modo degradado
2. **Cloud Tasks indisponível:** Processamento síncrono direto (sem fila)
3. **Cloud SQL offline:** Retornar `[]` ou `None` (dados em memória ou modo demo)
4. **Vertex AI indisponível:** Fallback para DeepSeek/Groq (multi-LLM nativo)
5. **Toda falha** deve ser logada, notificada ao Agente 0, e recuperada automaticamente

**Métrica:** % de requisições atendidas em modo degradado < 5% (target: 0%)

---

## 6. HIERARQUIA DE PROVEDORES LLM (CUSTO-REAL)

**Princípio:** Usar sempre o provedor de menor custo que atenda ao score de qualidade mínimo (0,85).

| Prioridade | Provedor | Modelo | Custo/Reunião | Gatilho de Uso |
|------------|----------|--------|---------------|----------------|
| 1 | **DeepSeek** | deepseek-v4-flash | **R$ 0,053** | Default — todos os agentes |
| 2 | OpenAI | gpt-4o-mini | R$ 0,081 | Fallback se DeepSeek indisponível ou score < 0,85 |
| 3 | Grok (xAI) | grok-4-1-fast-reasoning | R$ 0,084 | Transcrições > 100K tokens (2M context) |
| 4 | DeepSeek V4 Pro | deepseek-v4-pro | R$ 0,165 | Premium — 75% discount até 31/05/2026 |
| 5 | **Claude (Anthropic)** | claude-sonnet-4 | **R$ 1,849** | **VETO automático** — requer autorização explícita do Agente 0 |
| 6 | **Grok Multi-Agent (xAI)** | grok-4.20-multi-agent | **R$ 0,916** | **VETO automático** — requer autorização explícita do Agente 0 |

**Regras:**
- DeepSeek cache reduz input em ~98% — manter ativo para fallback econômico
- Nunca usar Claude ou Grok Multi-Agent sem aprovação explícita do Agente 0 (custo > 10x)
- Monitoramento: n8n alerta se custo/reunião > R$ 0,10 (2x do baseline DeepSeek)
- Google Gemini gratuito: **DESCARTADO** — tier gratuito não aguenta carga de produção

---

## 7. MODELO DE NEGÓCIO E MONETIZAÇÃO

### 7.1 Estrutura de Receita

| Fonte | Descrição | Margem Estimada |
|-------|-----------|-----------------|
| **SaaS Mensal** | Planos Starter/Pro/Enterprise | 70-80% |
| **Setup Fee** | Configuração inicial + treinamento | 90%+ |
| **Serviço Gerenciado** | Projetos de mapeamento de processos | 60-70% |
| **Excedentes** | Reuniões além do plano (R$ 15/unidade) | 85%+ |

### 7.2 Planos Comerciais (Híbrido — Recomendado)

| Plano | Preço | Reuniões | Setup Fee | Público |
|-------|-------|----------|-----------|---------|
| **Starter** | R$ 97/mês | 10 | — | Freelancers, pequenas equipes |
| **Pro** | R$ 297/mês | 50 | — | Empresas médias, consultorias |
| **Enterprise** | R$ 997/mês | Ilimitado | R$ 1.500 | Grandes empresas, órgãos públicos |

### 7.3 Controle de Custos

- **Target:** Custo operacional < 30% da receita
- **Cap Agente 4:** 15% sobre custos variáveis por cliente (LLM + Cloud Tasks + Storage)
- **Alerta:** n8n dispara alerta se custo LLM > R$ 0,10/reunião (2x baseline)
- **Ação:** Se custo > R$ 0,15/reunião por 3 dias consecutivos → revisão de arquitetura pelo Agente 0

### 7.4 Faturamento Automatizado (n8n)

```
Trigger: Cron (1º dia do mês, 06:00 BRT)
├── Node 1: Contar reuniões processadas por cliente (API P2D)
├── Node 2: Calcular valor conforme plano + excedentes
├── Node 3: Gerar fatura PDF (template HTML → Puppeteer)
├── Node 4: Enviar email com fatura + link PIX/boleto (API bancária)
├── Node 5: Criar registro no Notion/HubSpot (CRM)
├── Node 6: Alertar Agente 0 se fatura > R$ 5.000 (revisão manual)
└── Node 7: Agendar follow-up de cobrança (D+5, D+15, D+30)
```

---

## 8. MÉTRICAS E KPIs DE GOVERNANÇA

| Métrica | Meta | Responsável | Frequência |
|---------|------|-------------|------------|
| Uptime P2D | > 99.5% | Agente 1 + Agente 4 | Diária |
| Tempo de processamento/reunião | < 5 min | Agente 1 | Por reunião |
| Custo LLM/reunião | < R$ 0,10 | Agente 4 | Diária |
| NPS cliente | > 50 | Agente 0 | Mensal |
| MRR (Monthly Recurring Revenue) | Crescimento 20% m/m | Agente 0 | Mensal |
| Churn rate | < 5%/mês | Agente 4 | Mensal |
| Cobertura de testes | > 80% | Agente 1 | Por release |
| Incidentes de segurança | 0 | Agente 0 | Contínuo |

---

## 9. PLANO DE CONTINGÊNCIA (SPOF)

### 9.1 Falha do n8n
- **Detecção:** Health check a cada 60s via Cloud Monitoring
- **Fallback:** Processamento manual via API P2D (script Python)
- **Recuperação:** Auto-restart do container (Cloud Run) ou failover para instância backup (Compute Engine)
- **RTO:** < 15 minutos
- **RPO:** < 1 hora de dados

### 9.2 Falha do Google Cloud
- **Cenário:** Indisponibilidade da região southamerica-east1
- **Fallback:** Multi-region deploy (us-central1 como standby)
- **Dados:** Replicação assíncrona Cloud SQL cross-region
- **Ativação:** Manual pelo Agente 0 (decisão em < 30 min)

### 9.3 Falha de LLM (DeepSeek, OpenAI, Claude)
- **Estratégia:** Multi-LLM com fallback automático (já implementado no P2D)
- **n8n workflow:** Monitora latência e erro de cada provedor; alterna automaticamente
- **Fallback final:** Modo "degradado" — gera apenas ata e requisitos (sem BPMN)

---

## 10. REVISÃO E EVOLUÇÃO

- **Revisão mensal:** Primeira segunda-feira de cada mês, 09:00 BRT
- **Participantes:** Agente 0 (obrigatório) + Agentes 1-4 (conforme agenda)
- **Pauta:** Métricas do mês, decisões pendentes, riscos, próximos 30 dias
- **Output:** ATA publicada no Notion + notificação via n8n

---

## 11. ASSINATURAS DIGITAIS

| Agente | Função | Assinatura | Data |
|--------|--------|------------|------|
| Agente 0 | Arquiteto | [Pedro Regato] | 2026-06-30 |
| Agente 1 | Implementação | [Claude Code] | 2026-06-30 |
| Agente 2 | Análise | [NotebookLM] | 2026-06-30 |
| Agente 3 | Visualização | [Antigravity] | 2026-06-30 |
| Agente 4 | Orquestração | [n8n] | 2026-06-30 |

---

> *"A governança não é burocracia. É a estrutura que permite escalar sem perder a alma do produto."*
> — Pedro Regato, 30 de junho de 2026