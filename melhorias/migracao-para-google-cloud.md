# 🗺️ Plano de Migração — P2D → Google Cloud
> **Versão:** 2.0 | **Autor original:** Antigravity | **Revisão crítica:** Antigravity (v2.0)
> **Data de revisão:** Julho de 2026 | **Referência no ENGINEERING_MANIFESTO:** §10

Mapeando as conquistas técnicas do **Process2Diagram v5.15** (784 testes verdes, isolação de estado, malha de orquestração assíncrona paralelizada e API FastAPI comercial com autenticação SHA-256), a transição para a infraestrutura do Google é o passo natural para escalar comercialmente com robustez de nível *Enterprise*.

---

## ⚠️ Avaliação Crítica do Documento Original (v1.0)

O documento original apresentava 4 lacunas estruturais que comprometiam sua utilidade como guia operacional:

| # | Lacuna | Impacto |
|---|---|---|
| 1 | **Ausência de status de execução** — não diferenciava o que já estava feito do que era plano futuro | Impossível saber por onde começar |
| 2 | **Fases sem sequência de dependência explícita** — fase 2 dependia da fase 1 mas isso não estava documentado | Risco de executar fora de ordem e quebrar o sistema |
| 3 | **Nenhuma estimativa de custo GCP** — apenas custo do n8n estava no COLLABORATIVE_MANIFESTO | Decisão de migrar sem insumo financeiro real |
| 4 | **Sem checklist acionável** — o "próximo passo" era um bloco de prompt para o Claude Code, não um checklist verificável | Execução não rastreável |

Esta v2.0 corrige todas essas lacunas.

---

## 📊 Status Atual de Execução (Julho/2026)

### Infraestrutura Declarativa — ✅ ENTREGUE (PC113–PC114)

| Artefato | Arquivo | Status |
|---|---|---|
| Dockerfile multi-stage | `Dockerfile` | ✅ Produção-ready |
| Cloud Build pipeline | `infra/cloudbuild.yaml` | ✅ Build + push + deploy |
| Cloud Run service spec | `infra/cloudrun/service.yaml` | ✅ Declarativo completo |
| Env template | `infra/cloudrun/env.template.yaml` | ✅ Sem credenciais hardcoded |
| Cloud Tasks client | `services/cloud_tasks.py` | ✅ Fail-open automático |
| requirements API isolado | `requirements.api.txt` | ✅ Sem Streamlit/Plotly |

### O que **ainda não foi executado** (runtime pendente)

- [ ] Artifact Registry criado no GCP (`gcloud artifacts repositories create`)
- [ ] Service account `p2d-api-sa@PROJECT_ID.iam.gserviceaccount.com` criada com IAM mínimo
- [ ] Secrets populados no Secret Manager (`deepseek-api-key`, `supabase-url`, `supabase-service-key`, etc.)
- [ ] Primeira build submetida: `gcloud builds submit . --config infra/cloudbuild.yaml`
- [ ] Cloud Run trigger configurado no console GCP (push to `main`)
- [ ] Liveness probe validada: `curl https://<SERVICE_URL>/health`
- [ ] `.streamlit/secrets.toml` migrado para Secret Manager (bloqueador de segurança)

---

## 🏗️ Arquitetura-Alvo — Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                        │
│                                                                     │
│  ┌─────────────────┐     ┌──────────────────┐    ┌──────────────┐  │
│  │  Cloud Build    │────▶│ Artifact Registry │───▶│  Cloud Run   │  │
│  │  (CI/CD)        │     │ (Docker images)   │    │  (FastAPI)   │  │
│  └─────────────────┘     └──────────────────┘    └──────┬───────┘  │
│                                                          │          │
│  ┌─────────────────┐     ┌──────────────────┐    ┌──────▼───────┐  │
│  │ Secret Manager  │────▶│  env: API Keys   │    │ Cloud Tasks  │  │
│  │ (credenciais)   │     │  (mount via SA)  │    │ (fila Fase2) │  │
│  └─────────────────┘     └──────────────────┘    └──────────────┘  │
│                                                                     │
│  ┌─────────────────┐     ┌──────────────────┐                      │
│  │  Cloud Logging  │◀────│   Cloud Monitor  │                      │
│  │  (audit trail)  │     │  (alertas n8n)   │                      │
│  └─────────────────┘     └──────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
   ┌─────────────┐              ┌────────────────┐
   │   Supabase  │              │   DeepSeek /   │
   │ (dados app) │              │ OpenAI / Groq  │
   └─────────────┘              └────────────────┘
          │
          ▼
   ┌─────────────────────────────┐
   │  Streamlit Cloud            │
   │  (app.py — interface UI)    │
   │  Deploy independente:       │
   │  continua no Streamlit      │
   │  Cloud até Fase 3           │
   └─────────────────────────────┘
```

> **Separação crítica:** A API FastAPI (`api.py`) e o app Streamlit (`app.py`) são **dois serviços independentes**.
> O Cloud Run hospeda apenas a API. O Streamlit Cloud continua hospedando a interface até a Fase 3.

---

## Fase 1 — Computação e Execução (🔴 Runtime Pendente)

**Objetivo:** Substituir o ambiente FastAPI local por Cloud Run gerenciado.

### 1.1 — Cloud Run (FastAPI API)

O `Dockerfile` usa **multi-stage build**:
- `builder`: instala deps + baixa modelo spaCy `pt_core_news_lg` (~560 MB baked na imagem)
- `runtime`: imagem final sem `build-essential`, usuário não-root `p2d (uid 1001)`

**Configuração de deploy (`infra/cloudbuild.yaml`):**
```
CPU: 2 vCPU | RAM: 2Gi | containerConcurrency: 4 | timeout: 300s
maxInstances: 10 | executionEnvironment: gen2
```

> **Por que `containerConcurrency: 4`?**
> Alinhado com `MAX_CONCURRENT_PIPELINES = 4` em `api.py`. O `threading.Lock` é válido dentro
> de **uma instância**. Na Fase 2, quando o Cloud Tasks assumir o controle de concorrência,
> esse número pode subir para 10+.

> **Por que `minScale: "0"` (scale-to-zero)?**
> Para dev/staging: custo zero sem tráfego. Para produção com SLA de latência:
> mudar para `minScale: "1"` e eliminar cold starts (~60–90s).

**Cold start estimado:** ~60–90s (spaCy baked, mas importação ainda é pesada).
O `initialDelaySeconds: 60` na liveness probe já compensa isso.

### 1.2 — Cloud Tasks (Fila de Pipeline — Fase 2)

`services/cloud_tasks.py` já implementa **detecção automática por variável de ambiente**:

```python
def _detect_mode() -> CloudTasksMode:
    return (
        CloudTasksMode.CLOUD_TASKS
        if os.environ.get("CLOUD_TASKS_QUEUE", "").strip()
        else CloudTasksMode.SYNC_FALLBACK
    )
```

**Para ativar:** descomentar as variáveis em `infra/cloudrun/env.template.yaml`:
```yaml
CLOUD_TASKS_QUEUE: "p2d-pipeline-queue"
CLOUD_TASKS_LOCATION: "us-central1"
```

**Criar a fila no GCP:**
```bash
gcloud tasks queues create p2d-pipeline-queue \
  --location=us-central1 \
  --max-dispatches-per-second=4 \
  --max-concurrent-dispatches=4 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s
```

**Custo Cloud Tasks:** primeiros 1 milhão de tasks/mês são gratuitos.
Com 1.000 reuniões/mês: **R$ 0** até atingir escala de 1M+ reuniões/mês.

---

## Fase 2 — Banco de Dados e Persistência

**Objetivo:** Avaliar evolução da camada de dados (Supabase → GCP nativo).

### 2.1 — Posição atual: Supabase (PostgreSQL + pgvector)

O P2D já usa Supabase com:
- PostgreSQL + pgvector (embeddings `vector(512)`)
- RLS (Row Level Security) por projeto
- Backups automáticos + replicação

### 2.2 — Cloud SQL: quando faz sentido migrar?

| Critério | Supabase | Cloud SQL |
|---|---|---|
| **Custo até 500 reuniões/mês** | ~$0–25/mês (free tier) | ~R$ 150–300/mês (db-g1-small) |
| **Administração** | Zero-ops | Requer DBA |
| **pgvector** | Nativo | Extensão manual |
| **RLS** | Nativo + editor visual | SQL manual |
| **Conformidade LGPD (região BR)** | US-East-1 (risco) | `southamerica-east1` ✅ |

**Recomendação:** Migrar para Cloud SQL **somente quando:**
1. MRR > R$ 10.000/mês (margem justifica complexidade operacional), **ou**
2. Requisito explícito de residência de dados em território brasileiro (clientes governamentais/enterprise).

Por ora: **manter Supabase**. Não é bloqueador de negócio.

### 2.3 — Cloud Storage (GCS): caso de uso válido

| Artefato | Tamanho típico | Solução atual | Proposta GCS |
|---|---|---|---|
| Transcrições brutas (.txt/.docx/.pdf) | 10–500 KB | Supabase (coluna text) | Bucket `p2d-transcripts/` |
| BPMN XML exportado | 5–50 KB | Supabase (coluna text) | Pode ficar no Supabase |
| Relatórios HTML executivos | 50–200 KB | Memória (não persistido) | Bucket `p2d-reports/` |

**Estimativa de custo GCS:** < R$ 5/mês para 10.000 documentos de até 500 KB.

---

## Fase 3 — Segurança e Governança de Chaves

### 3.1 — Secret Manager (bloqueador imediato)

**Este é o item mais urgente** — o único que bloqueia o primeiro deploy seguro em produção.

O `service.yaml` já referencia os secrets via `secretKeyRef`. Falta criá-los:

```bash
echo -n "sk-..." | gcloud secrets create deepseek-api-key --data-file=-
echo -n "https://xxx.supabase.co" | gcloud secrets create supabase-url --data-file=-
echo -n "service_role_key..." | gcloud secrets create supabase-service-key --data-file=-
echo -n "sk-ant-..." | gcloud secrets create anthropic-api-key --data-file=-
echo -n "sk-..." | gcloud secrets create openai-api-key --data-file=-
echo -n "gsk_..." | gcloud secrets create groq-api-key --data-file=-
echo -n "xai-..." | gcloud secrets create xai-api-key --data-file=-

# Permissão para a service account
gcloud secrets add-iam-policy-binding deepseek-api-key \
  --member="serviceAccount:p2d-api-sa@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
# (repetir para cada secret)
```

### 3.2 — Cloud DLP API: avaliação crítica — NÃO PRIORITÁRIA

O documento original propunha a Cloud DLP API como "barreira ortogonal" de PII. **Avaliação: não é prioritária.**

**Por quê?**
- O P2D já implementa sanitização em **2 tiers** nativos (`modules/pii_sanitizer.py`)
- Cloud DLP adiciona latência (~200–800ms por chamada) e custo ($0.001–$3 por unidade de conteúdo)
- Benefício marginal sobre o que já existe

**Recomendação:** Avaliar Cloud DLP apenas para auditoria pós-pipeline em clientes de segmento
governamental/financeiro — nunca no caminho crítico do pipeline.

---

## Fase 4 — Inteligência e Repositório de Padrões

### 4.1 — Vertex AI (Gemini): avaliação crítica — NÃO PRIORITÁRIA

**Contexto atual:**
- DeepSeek v4-flash: R$ 0,053/reunião, 1M tokens de contexto, qualidade validada
- Gemini free tier: **descartado** (PC114) — não aguenta carga de produção
- Gemini via Vertex AI: pricing diferente do free tier, mas ainda não benchmarked no P2D

**Quando considerar Vertex AI:**
1. Se DeepSeek tiver instabilidade de SLA por >3 dias consecutivos
2. Se um cliente exigir que o processamento ocorra inteiramente no GCP (soberania de dados)
3. Quando o custo de Vertex AI for competitivo com DeepSeek após créditos GCP

**Recomendação:** Manter DeepSeek como primário. Vertex AI entra como provider adicional
em `modules/config.py` quando benchmarked e aprovado pelo Agente 0.

### 4.2 — Vertex AI Vector Search: caso de uso legítimo ✅

Este item do documento original tem **valor real e diferenciado**.

**Problema atual:** Os exemplos BPMN de few-shot estão em `agents/agent_bpmn/examples/` como
arquivos Markdown estáticos. O agente lê todos no `build_prompt()`, consumindo tokens fixos
independente da relevância.

**Proposta:** Busca semântica por similaridade com a transcrição do usuário — injeta apenas
o exemplo mais relevante, reduzindo consumo de tokens em ~60–80%.

**Rota recomendada (sem Vertex AI primeiro):** Usar o próprio pgvector do Supabase para
indexar os exemplos. Já temos a infraestrutura de embedding (`modules/embeddings.py`).
Esta é a rota preferida antes de migrar para Vertex AI.

---

## 💰 Estimativa de Custos GCP (Produção Real)

| Componente | Dimensionamento | Custo/mês (R$) |
|---|---|---|
| Cloud Run API | 1.000 req/mês × 300s × 2vCPU | ~R$ 15–40 |
| Artifact Registry | ~1 GB de imagens Docker | ~R$ 3 |
| Cloud Build | 10 builds/mês × 10 min | ~R$ 5 (free tier) |
| Secret Manager | 7 secrets, <10k acessos/mês | ~R$ 2 |
| Cloud Logging | logs básicos de API | ~R$ 0–5 |
| Cloud Tasks (Fase 2) | 1.000 tasks/mês | R$ 0 (free tier) |
| **Total estimado (Fase 1)** | | **~R$ 25–55/mês** |

> Custo fixo de infra GCP (Fase 1) < R$ 60/mês — absorvido como overhead operacional
> conforme COLLABORATIVE_MANIFESTO §7.3.

---

## 🔄 Sequência de Execução — Ordem de Dependências

```
Fase 1a — Pré-requisitos GCP (bloqueadores)
  ├── [1] Criar projeto GCP + habilitar APIs (Cloud Run, Cloud Build, Artifact Registry)
  ├── [2] Criar service account p2d-api-sa com roles mínimas
  ├── [3] Criar secrets no Secret Manager (todos os API keys)
  └── [4] Habilitar Cloud Build trigger (push to main → infra/cloudbuild.yaml)

Fase 1b — Primeiro Deploy
  ├── [5] gcloud builds submit . --config infra/cloudbuild.yaml
  ├── [6] Validar /health endpoint
  └── [7] Teste de smoke: POST /pipeline com transcrição real

Fase 1c — Produção-Ready
  ├── [8] Configurar Cloud Monitoring + alertas (custo LLM > R$ 0,10/reunião)
  ├── [9] minScale=1 no service.yaml (eliminar cold start para produção)
  └── [10] Documentar URL da API em CLAUDE.md + memory/project_state.md

Fase 2 — Concorrência Distribuída (quando: >4 instâncias Cloud Run simultâneas)
  ├── [11] Criar fila Cloud Tasks p2d-pipeline-queue
  ├── [12] Popular CLOUD_TASKS_QUEUE em Secret Manager
  └── [13] Validar fallback síncrono com CLOUD_TASKS_QUEUE=""

Fase 3 — Dados (quando: MRR > R$ 10.000 ou exigência de residência BR)
  └── [14] Avaliar migração Supabase → Cloud SQL southamerica-east1

Fase 4 — Inteligência (quando: Fase 1 estável + benchmarks Vertex AI concluídos)
  ├── [15] Indexar exemplos BPMN no pgvector Supabase (MVP sem Vertex AI)
  └── [16] Avaliar Vertex AI Embeddings como alternativa ao OpenAI embeddings
```

---

## 🛡️ Governança e Fail-Open na Migração

Todos os princípios do `ENGINEERING_MANIFESTO.md §2` (Fail-Open) e `§11` (Fail-Open Cloud) se aplicam:

- **Secret Manager offline** → `get_secret()` retorna `None`; caller usa ENV var como fallback
- **Cloud Tasks indisponível** → `services/cloud_tasks.py` cai para `ThreadPoolExecutor` local automaticamente
- **Cloud Run cold start** → readiness probe retira instância do LB até aquecer; clientes recebem retry automático
- **Build failure** → Cloud Build não promove imagem; versão anterior continua servindo (zero-downtime)

---

## 📌 Próximos Passos — Comandos para o Primeiro Deploy

```bash
# [1] Criar projeto e habilitar APIs
gcloud projects create p2d-production --name="Process2Diagram"
gcloud config set project p2d-production
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

# [2] Criar service account com IAM mínimo
gcloud iam service-accounts create p2d-api-sa \
  --display-name="P2D API Service Account"
gcloud projects add-iam-policy-binding p2d-production \
  --member="serviceAccount:p2d-api-sa@p2d-production.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding p2d-production \
  --member="serviceAccount:p2d-api-sa@p2d-production.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

# [3] Criar Artifact Registry
gcloud artifacts repositories create p2d \
  --repository-format=docker \
  --location=us-central1

# [4] Popular secrets (ver Fase 3 §3.1 acima)

# [5] Primeiro build e deploy
gcloud builds submit . --config infra/cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_SERVICE=process2diagram-api

# [6] Validar
curl https://$(gcloud run services describe process2diagram-api \
  --region us-central1 --format 'value(status.url)')/health
```

---

> *"A infraestrutura não é o produto. Ela é o que permite que o produto exista em escala.
> Cada componente cloud deve ganhar seu lugar provando que reduz custo operacional ou aumenta
> resiliência — não por modismo tecnológico."*
> — Antigravity, revisão v2.0 — Julho de 2026
