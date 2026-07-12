# Briefing — Verificação cruzada P2D × gap analysis de vaga (IA)

**Data:** 2026-07-12
**Origem:** Claude Code trabalhando diretamente no repositório do Process2Diagram (P2D), verificação de código real — não é inferência, é leitura de código.
**Uso pretendido:** colar este documento na conversa do Claude Code que roda no projeto `myCV`, para incorporar os pontos abaixo em `data/profile_pt.yaml` / `data/profile_en.yaml` e nas seções LinkedIn (`data/linkedin/about_pt.md` / `about_en.md`, `experience/`).

---

## Contexto

O Claude Code do projeto `myCV` gerou uma análise de gap contra um checklist de vaga (requisitos obrigatórios + diferenciais de uma posição de IA). Vários itens ficaram marcados como "?" (sem menção explícita). Esta verificação cruzou cada "?" contra o código real do P2D para separar **honestamente**: (1) o que já é coberto na prática e só faltava aparecer no CV, (2) o que motivou uma pequena implementação nova (Azure OpenAI), e (3) o que é gap real, sem atalho.

## Itens do checklist antes marcados "?" — agora com evidência real

| Item da vaga | Evidência concreta no P2D |
|---|---|
| **Azure AI Services / Azure OpenAI** | Implementado em 2026-07-12 (PC184): provider Azure OpenAI Service (`client_type="azure_openai"` em `modules/config.py`), client dedicado `openai.AzureOpenAI`, 13 testes (mockado). Deixou de ser aspiracional — é capacidade real do código. |
| **Governança de IA / ética / LGPD** | Camada de compliance dedicada e nomeada como tal: `modules/compliance/` (`detector.py`, `audit.py`, `consent.py`) + tabelas `compliance_consent`/`compliance_audit` em produção. Pseudonimização reversível de PII em 2 camadas (dados estruturados via regex + nomes via NER). |
| **Copilots corporativos / assistentes inteligentes** | Assistente RAG com 151 ferramentas especializadas, modo tool-use direto + modo de análise autônoma multi-etapa (15 rounds) — copilot embutido no produto, não wrapper de chat genérico. |
| **MLOps: deploy, versionamento, monitoramento, governança de modelos** | Telemetria fechando o loop (PC183): detecção de anomalia de taxa de erro por provider + rastreamento de "taxa de saída bem-formada" (schema validation) por agente/versão de prompt ao longo do tempo. Versionamento de skill/prompt já rastreado desde antes (PC83). |
| **Observabilidade / monitoramento de modelo / FinOps para IA** | Telemetria (latência, throughput, erro, qualidade) + ferramenta dedicada de modelagem de custo comparando 17 modelos em 6 provedores por cenário (`core/cost_model.py`, `pages/CostBenefitScenarios.py`). |
| **OpenAI ou equivalentes** | Já era match literal antes (integração direta com OpenAI), reforçado agora com Azure OpenAI também. |

## O que continua honestamente em aberto (sem atalho de código)

- **Data Lake / Data Warehouse** — o banco é Postgres transacional (OLTP) + pgvector, não é DW. Não vale forçar isso artificialmente no P2D só para preencher checkbox.
- **Certificações** (Azure AI Engineer, AWS ML Specialty, Google Professional ML Engineer, etc.) — sem atalho de código, é estudo/prova.
- **Cloud em produção real (Azure/AWS/GCP)** — existe infraestrutura GCP *preparada* (Dockerfile multi-stage, Cloud Run `service.yaml`, Cloud Build pipeline) mas **nunca implantada em produção**; o deploy real e ao vivo é Streamlit Cloud. Não afirmar "experiência em produção com GCP" — afirmar "IaC pronta para Cloud Run + deploy contínuo real (CI/CD)".
- **RLS/governança de dados no banco** — isolamento multi-tenant é real na camada de aplicação (`project_id`/`tenant_id`), mas RLS no Postgres está inconsistente entre tabelas (mistura de sem-policy, `USING(true)` permissivo, e RLS explicitamente desabilitada). Não vender como "RLS completo" ou "isolamento a nível de banco".

## Bullets prontos — PT

**Principal (resumo/experiência):**
> Arquitetura de orquestração multi-agente (13 agentes especializados, retry adaptativo via LangGraph com autocorreção baseada em validação estrutural) sobre 7 provedores LLM intercambiáveis — DeepSeek, Anthropic Claude, OpenAI, Azure OpenAI Service, Google Gemini, Groq e xAI Grok — com deploy contínuo em produção.

**Governança e LGPD:**
> Camada de conformidade LGPD em produção: pseudonimização reversível de dados pessoais em duas camadas (PII estruturado + nomes via NER), trilha de auditoria e consentimento versionadas em banco, isolamento multi-tenant por projeto/organização.

**RAG e copilot corporativo:**
> Assistente conversacional (RAG) com 151 ferramentas especializadas sobre busca semântica (pgvector, embeddings Matryoshka 512-dim) e modo de análise autônoma multi-etapa — copilot corporativo embutido no produto, não um chatbot genérico.

**FinOps para IA:**
> Ferramenta de modelagem de custo comparando 17 modelos em 6 provedores por cenário de uso, com projeção de custo antes da execução — decisão de trade-off custo×qualidade orientada por dado, não por intuição.

**Observabilidade / LLMOps:**
> Telemetria de chamadas LLM com detecção de anomalia de taxa de erro por provedor e rastreamento de qualidade de saída estruturada (schema validation rate) por agente/versão de prompt ao longo do tempo — fecha o ciclo entre chamada de modelo e sinal acionável.

**Cloud e API:**
> Containerização multi-stage (Docker) e infraestrutura como código para Google Cloud Run (Cloud Build CI/CD), com API comercial própria (FastAPI, autenticação por chave + rate limiting) — deploy real em produção via CI/CD (Streamlit Cloud).

## Bullets prontos — EN

> Multi-agent orchestration architecture (13 specialized agents, LangGraph-based adaptive retry with structural-validation self-correction) across 7 interchangeable LLM providers — DeepSeek, Anthropic Claude, OpenAI, Azure OpenAI Service, Google Gemini, Groq, and xAI Grok — with continuous production deployment.

> Production LGPD compliance layer: two-tier reversible PII pseudonymization (structured data + NER-based name tokenization), versioned consent/audit trail, multi-tenant isolation by project/organization.

> Conversational RAG assistant with 151 specialized tools over semantic search (pgvector, 512-dim Matryoshka embeddings) and a multi-step autonomous analysis mode — an embedded enterprise copilot, not a generic chatbot.

> Cost-modeling tool comparing 17 models across 6 providers per usage scenario, with pre-execution cost projection — data-driven cost/quality trade-off, not guesswork.

> LLM call telemetry with per-provider error-rate anomaly detection and structured-output quality tracking (schema validation rate) by agent/prompt version over time — closes the loop from model call to actionable signal.

> Multi-stage Docker containerization and infrastructure-as-code for Google Cloud Run (Cloud Build CI/CD), plus a proprietary commercial API (FastAPI, key auth + rate limiting) — live production deployment via CI/CD (Streamlit Cloud).

## Instrução para o Claude Code do myCV

Incorporar os bullets acima em `data/profile_pt.yaml` / `data/profile_en.yaml` (seção de experiência/projetos referente ao P2D) e nas seções LinkedIn correspondentes (`data/linkedin/about_pt.md` / `about_en.md`, `experience/`). Manter o restante honesto: não estender essas afirmações além do que está listado — os gaps reais (data warehouse, certificações, produção efetiva em Azure/AWS/GCP) continuam gaps.

## Nota — `career/portfolio_process2diagram.md` já foi atualizado

O blurb citava números antigos ("9 agentes", "~125 ferramentas", "6 provedores LLM", "345 testes automatizados"). Já foi corrigido para os números verificados nesta sessão: **13 agentes** orquestrados no pipeline principal (via `Orchestrator._PLAN`, contando só os passos com LLM), **151 ferramentas** (contagem real via `get_tool_schemas_openai()`, não estimativa), **7 provedores LLM** (DeepSeek, Claude, OpenAI, Azure OpenAI, Gemini, Groq, Grok — Azure OpenAI é uma configuração adicional, não uma 8ª marca distinta), **874 testes automatizados**.
