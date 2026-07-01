# PLANO DE 90 DIAS — Process2Diagram v5.11 (PC112-J)
## n8n + Google Cloud: Da Fase Early Access ao Produto Enterprise Ready

**Versão:** 5.11  
**Data:** 30 de junho de 2026  
**Arquiteto:** Pedro Regato  
**Status:** ASSINADO — Em execução

---

## 🎯 VISÃO GERAL

O P2D v5.11 é um **produto funcional em fase de maturidade** — não um MVP. Com 312 testes automatizados, pipeline multi-agente operacional e 12 artefatos formais, o desafio agora é **escalar comercialmente** com infraestrutura enterprise, automação de negócio e modelo de receita sustentável.

Este plano integra:
- **n8n (Agente 4)** como orquestrador de automação comercial
- **Google Cloud** como infraestrutura escalável e LGPD-ready
- **DeepSeek** como provedor LLM primário (custo irrisório: R$ 0,057/reunião)

---

## 📊 DIAGNÓSTICO ATUAL (Dia 0)

### O Que Já Existe (Produto Funcional)
| Componente | Status | Qualidade |
|------------|--------|-----------|
| Pipeline multi-agente (9 agentes) | ✅ | 312 testes verdes |
| BPMN 2.0 + torneio multi-pass | ✅ | Qualidade auditável |
| 12 artefatos formais | ✅ | IEEE 830, SBVR, BMM, DMN |
| CKF (Context Knowledge File) | ✅ | Memória institucional |
| Grafo de Conhecimento | ✅ | Análise cruzada |
| Assistente RAG (90+ ferramentas) | ✅ | Busca semântica |
| Semantic Cache (SHA-256) | ✅ | Redução 98% input |
| Multi-LLM (DeepSeek, OpenAI, Claude, Groq) | ✅ | Fallback automático |

### O Que Falta (Para Produto Final)
| Componente | Status | Impacto Comercial |
|------------|--------|-------------------|
| Google Cloud (infra enterprise) | ⚠️ Em migração | Escalabilidade, LGPD, credibilidade |
| n8n (automação comercial) | ⚠️ Em deploy | Onboarding, faturamento, monitoramento |
| Faturamento automatizado | ❌ Não existe | Dinheiro entra sem intervenção |
| Onboarding self-service | ❌ Manual | Escala sem sua intervenção |
| SLA 99.5% uptime | ❌ Não existe | Contratos enterprise |
| Suporte tickets | ❌ Não existe | Retenção de clientes |
| API pública documentada | ⚠️ Parcial | Integrações parceiras |
| White-label / Custom domain | ❌ Não existe | Agências revendem |

---

## 🏗️ FASE 1: FUNDAÇÃO (Dias 1-30)
### Objetivo: Infraestrutura Core GCP + n8n Operacional

### Semana 1-2: Google Cloud (Infraestrutura)

| Dia | Tarefa | Responsável | Output |
|-----|--------|-------------|--------|
| 1-2 | Criar projeto GCP, ativar APIs (Run, SQL, Storage, Tasks, Secret Manager) | Agente 1 | Projeto ativo |
| 3-5 | Criar Dockerfile otimizado para FastAPI (stateless) | Agente 1 | Build validado |
| 6-8 | Criar pasta `infra/` com configuração declarativa Cloud Run | Agente 1 | YAML/Terraform pronto |
| 9-11 | Deploy PostgreSQL + pgvector no Cloud SQL (São Paulo) | Agente 1 | Banco migrado |
| 12-13 | Configurar Secret Manager (DeepSeek, OpenAI, Supabase fallback) | Agente 1 | Segredos centralizados |
| 14-15 | Deploy FastAPI no Cloud Run + teste de carga | Agente 1 | API no ar |

**Comando Claude Code:**
```text
[CONTEXTO] DeepSeek é primário (R$ 0,053/reunião). OpenAI embedding é obrigatório. 
Gemini gratuito está DESCARTADO. Execute as 6 tarefas do BRIEFING_AGENTE1_FASE1_FINAL.md.
```

### Semana 3-4: n8n (Automação Core)

| Dia | Tarefa | Responsável | Output |
|-----|--------|-------------|--------|
| 16-18 | Deploy n8n em e2-medium (4GB RAM) no Compute Engine | Agente 1 | n8n operacional |
| 19-22 | Workflow 1: Recebimento → Cloud Tasks → FastAPI → Entrega | Agente 4 | Pipeline funcionando |
| 23-25 | Workflow 2: Onboarding automático de clientes | Agente 4 | Clientes entram sozinhos |
| 26-28 | Workflow 3: Monitoramento de custos LLM + alertas | Agente 4 | Controle de gastos |
| 29-30 | Testes end-to-end + ajustes | Agente 1 + Agente 4 | Sistema estável |

**Infraestrutura n8n:**
- Instância: Google Compute Engine e2-medium (4GB RAM)
- Custo: R$ 45-60/mês (custo fixo da empresa)
- Decisão: e2-micro (1GB) é inviável — n8n Docker requer 4GB mínimo

---

## 🏗️ FASE 2: INTEGRAÇÃO (Dias 31-60)
### Objetivo: n8n como Orquestrador Central + Primeiros Clientes

### Semana 5-6: Workflows Comerciais

| Dia | Tarefa | Responsável | Output |
|-----|--------|-------------|--------|
| 31-35 | Workflow 4: Faturamento + cobrança recorrente (PIX/boleto) | Agente 4 | Dinheiro entra automaticamente |
| 36-40 | Workflow 5: Follow-up pós-reunião (3 dias) + nurturing | Agente 4 | Retenção de clientes |
| 41-45 | Workflow 6: Qualidade automática + reprocessamento (score < 0,85) | Agente 4 | Qualidade consistente |

### Semana 7-8: Go-to-Market Inicial

| Dia | Tarefa | Responsável | Output |
|-----|--------|-------------|--------|
| 46-50 | Publicar 3 posts LinkedIn (problema → solução → case) | Agente 0 | Leads qualificados |
| 51-55 | Enviar 20 mensagens personalizadas (ex-colegas, network) | Agente 0 | 5 calls agendados |
| 56-60 | Realizar 3 análises gratuitas de reuniões | Agente 0 | Cases comprovados |

**Script de vendas LinkedIn:**
> *"Você já calculou quanto custa uma reunião estratégica que não gera nenhum artefato? Em média, R$ 8.200/hora de reunião executiva no Brasil. 67% do conhecimento gerado nunca é formalizado. O Process2Diagram transforma transcrições em 12 artefatos formais — BPMN, requisitos, atas, SBVR, BMM — automaticamente, em minutos. Estou oferecendo 3 análises gratuitas para validar o valor. Interessado?"*

---

## 🏗️ FASE 3: MONETIZAÇÃO (Dias 61-90)
### Objetivo: Primeiros Clientes Pagantes + Modelo Sustentável

### Semana 9-10: Propostas e Fechamento

| Dia | Tarefa | Responsável | Output |
|-----|--------|-------------|--------|
| 61-65 | Enviar propostas comerciais (Setup R$ 1.500 + R$ 197/mês) | Agente 0 | Propostas no ar |
| 66-70 | Negociar e fechar primeiros 2 clientes | Agente 0 | MRR inicial |
| 71-75 | Onboarding dos primeiros clientes (n8n automatizado) | Agente 4 | Clientes ativos |

### Semana 11-12: Otimização e Escala

| Dia | Tarefa | Responsável | Output |
|-----|--------|-------------|--------|
| 76-80 | Configurar domínio customizado + SSL (p2d.com.br) | Agente 1 | Marca profissional |
| 81-85 | Implementar SLA 99.5% + monitoramento avançado | Agente 1 | Enterprise ready |
| 86-90 | Revisão mensal + planejamento próximos 90 dias | Agente 0 + Todos | Roadmap v6.0 |

---

## 💰 MODELO DE NEGÓCIO (Híbrido — Recomendado)

### Planos Comerciais

| Plano | Preço | Reuniões | Setup Fee | Público-Alvo |
|-------|-------|----------|-----------|--------------|
| **Starter** | R$ 97/mês | 10 | — | Freelancers, pequenas equipes |
| **Pro** | R$ 297/mês | 50 | — | Empresas médias, consultorias |
| **Enterprise** | R$ 997/mês | Ilimitado | R$ 1.500 | Grandes empresas, órgãos públicos |

### Custo Real por Cliente (Plano Pro — 50 reuniões)

| Item | Custo | % da Receita |
|------|-------|--------------|
| LLM (DeepSeek, 50 reuniões) | R$ 2,65 | 0,9% |
| Embedding (OpenAI, 50 reuniões) | R$ 0,20 | 0,1% |
| Cloud Tasks (50 execuções) | R$ 1,50 | 0,5% |
| Storage (artefatos 50 reuniões) | R$ 2,00 | 0,7% |
| **Subtotal — Custos Variáveis** | **R$ 6,35** | **2,1%** |
| | | |
| Infra n8n (compartilhada) | R$ 45-60 | 15-20% |
| Cloud SQL (compartilhada) | R$ 15-30 | 5-10% |
| **Subtotal — Infraestrutura** | **R$ 60-90** | **20-30%** |
| | | |
| **Margem bruta por cliente** | **R$ 201-231** | **68-78%** |

### Cap do Agente 4 (n8n)
- **15% da receita por cliente** — aplicado APENAS a custos variáveis (LLM + Tasks + Storage)
- **Infraestrutura (n8n, Cloud SQL, Cloud Run)** — custo fixo da empresa, não alocado por cliente
- **Alerta:** Se custo/reunião > R$ 0,10 (2x baseline) → alerta automático
- **Ação:** Se custo > R$ 0,15/reunião por 3 dias → revisão pelo Agente 0

---

## 📊 MÉTRICAS E KPIs

| KPI | Meta Dia 30 | Meta Dia 60 | Meta Dia 90 |
|-----|-------------|-------------|-------------|
| Workflows n8n ativos | 3 | 6 | 8 |
| Reuniões processadas via n8n | 10 | 50 | 150 |
| Tempo médio de onboarding | 2h | 30min | 15min |
| Custo LLM por reunião | R$ 0,057 | R$ 0,055 | R$ 0,050 |
| Clientes ativos pagantes | 0 | 2 | 5 |
| MRR (Monthly Recurring Revenue) | R$ 0 | R$ 394 | R$ 985 |
| NPS cliente | — | > 50 | > 60 |
| Uptime P2D | > 99% | > 99.5% | > 99.5% |

---

## 🔧 ARQUITETURA ALVO (Dia 90)

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTE                                  │
│         (Upload transcrição → Recebe artefatos)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         n8n (Agente 4)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Webhook    │  │  Cloud Tasks│  │  Faturamento            │  │
│  │  Receiver   │→ │  Router     │→ │  & Cobrança             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Onboarding │  │  Follow-up  │  │  Monitoramento          │  │
│  │  Automático │  │  Pós-reunião│  │  de Custos LLM          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD (Infraestrutura)                  │
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐  │
│  │  Cloud Run      │    │  Cloud SQL      │    │  Cloud       │  │
│  │  (FastAPI API)  │◄──►│  (PostgreSQL    │    │  Storage     │  │
│  │                 │    │   + pgvector)   │    │  (GCS)       │  │
│  └─────────────────┘    └─────────────────┘    └──────────────┘  │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐  │
│  │  Cloud Tasks    │    │  Secret Manager │    │  Cloud       │  │
│  │  (Filas +       │    │  (Credenciais   │    │  Logging     │  │
│  │   Retries)      │    │   + Rotação)    │    │  (Audit)     │  │
│  └─────────────────┘    └─────────────────┘    └──────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROVEDORES LLM (Multi-LLM)                   │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  DeepSeek   │  │  OpenAI     │  │  Grok (xAI)             │  │
│  │  (Primário) │  │  (Fallback) │  │  (Contexto longo)         │  │
│  │  R$ 0,053   │  │  R$ 0,081   │  │  R$ 0,084               │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │  VETO AUTOMÁTICO: Claude (R$ 1,849) e Grok Multi-Agent   │      │
│  │  (R$ 0,916) — requerem autorização explícita do Agente 0 │      │
│  └─────────────────────────────────────────────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📚 FONTES PARA NOTEBOOKLM (5 Documentos)

| # | Fonte | Tipo | Status |
|---|-------|------|--------|
| 1 | **PLANO_90_DIAS_v5.11_EXECUTIVO.md** (este documento) | Plano estratégico | ✅ Gerado |
| 2 | **RESUMO_SESSAO_30_06_2026.md** | Contexto histórico | ✅ Existente |
| 3 | **COLLABORATIVE_MANIFESTO_v5.11_ASSINADO.md** | Governança multi-agente | ✅ Gerado |
| 4 | **ENGINEERING_MANIFESTO.md** | Princípios técnicos | ⚠️ Atualizar com Cloud Tasks |
| 5 | **migracao-para-google-cloud.md** | Arquitetura cloud detalhada | ✅ Documento oficial |

---

## ✅ CHECKLIST DIÁRIO (Últimas 2 Semanas — Dias 76-90)

| Dia | Tarefa | Status |
|-----|--------|--------|
| 76-80 | Configurar domínio customizado + SSL | ⬜ |
| 81-83 | Publicar 3 posts no LinkedIn | ⬜ |
| 84-85 | Enviar 20 mensagens personalizadas | ⬜ |
| 86-88 | Agendar 5 calls de descoberta | ⬜ |
| 89-90 | Fechar primeiro cliente pagante | ⬜ |

---

## 🎯 MENSAGEM-CHAVE

> *"O n8n é o sistema nervoso que conecta o cérebro do P2D (os agentes LLM) ao mundo real (clientes, cobrança, suporte). O Google Cloud é o esqueleto que sustenta tudo com credibilidade enterprise. Juntos, transformam um produto funcional em uma máquina de negócios."*

---

> *"Não vendemos tokens. Vendemos tempo. R$ 297/mês para economizar 2-3h de trabalho analítico por reunião — ROI de 5.500% para o cliente."*
> — Pedro Regato, 30 de junho de 2026
