# Manifesto de Engenharia — Process2Diagram (P2D)

> **Versão:** 1.1 | **Data:** Junho de 2026 (§8 atualizado em 19 de julho de 2026, PC196) | **Status:** Ativo — leitura obrigatória para todos os agentes e colaboradores.

Este documento é a fonte canônica dos princípios arquiteturais que governam o desenvolvimento do P2D. Ele complementa o `manifestos/COLLABORATIVE_MANIFESTO.md` (governança de equipe), o `manifestos/CONTINUIDADE_ARQUITETURAL.md` (blindagem contra SPOF) e o `CLAUDE.md` (restrições técnicas de runtime).

---
    
## 1. Ecossistema Multi-Agente + Humano

O P2D opera sob um modelo de cooperação especializada entre três papéis:

| Papel | Responsabilidade Principal |
|---|---|
| **Antigravity** (Arquiteto de IA) | Design de alto nível, blueprints em `drafts/`, análise macro de governança |
| **Claude Code** (Operário de Elite) | Implementação, testes (`pytest`), integração, arquivamento de rascunhos em `drafts/arquivadas/` |
| **Engenheiro Humano** (Diretor de Orquestra) | Intenção de negócio, arbitragem arquitetural, critérios de aceite |

**Regra de Ouro:** Nenhum agente anula o outro. A capacidade analítica visual do Antigravity soma com a eficiência bruta de terminal do Claude Code, sob supervisão humana.

**Fluxo de rascunhos:**
1. Antigravity/Humano projetam a solução e salvam o esqueleto em `drafts/modulo_draft.py`.
2. Claude Code lê o draft, implementa nos módulos finais, roda os testes e move o rascunho para `drafts/arquivadas/`.
3. O ciclo se fecha com o Git guardando o estado final da entrega.

---

## 2. Princípio Fail-Open

**Definição:** O sistema nunca bloqueia a operação do usuário por indisponibilidade de um serviço externo ou validação opcional.

### Regras mandatórias:

- **Supabase indisponível** → retornar `[]` ou `None`; nunca propagar exceção para o caller.
- **Validação de schema Pydantic** → emitir `warnings.warn()`; nunca bloquear o pipeline.
- **Pré-condições de agentes** → `_check_preconditions(hub)` levanta `ValueError` apenas para fast-fail interno; o Orchestrator trata e continua.
- **Autenticação da API comercial** → `require_api_key`: se o banco de API keys estiver indisponível, emitir `warnings.warn()` e permitir a requisição (fail-open explícito por decisão de segurança aceitável).
- **Cada operação de persistência** → independente, envolvida em `try/except` próprio; a falha de uma não aborta as demais.

```python
# Exemplo canônico de fail-open em persistência
try:
    save_bpmn_from_hub(hub, meeting_id)
except Exception as e:
    warnings.warn(f"save_bpmn_from_hub falhou: {e}")
```

---

## 3. Isolamento de Estado — Desacoplamento do Streamlit

**Problema resolvido (PC106):** Agentes e pipeline invocados via API FastAPI não devem acessar `st.session_state` — ele não existe fora do contexto Streamlit.

### Padrão de 3 Camadas (implementado em `BaseAgent._call_llm()`):

```python
# Camada 1 — API mode: lê de client_info (dict passado pelo caller)
value = self.client_info.get("chave")

# Camada 2 — Streamlit mode: lê de st.session_state (fallback)
if value is None:
    try:
        import streamlit as st
        value = st.session_state.get("chave")
    except Exception:
        pass

# Camada 3 — Default seguro (nunca None crítico)
if value is None:
    value = DEFAULT_VALUE
```

**Regra:** Todo acesso a `st.session_state` em código compartilhado (agentes, pipeline, módulos) deve seguir este padrão. Código em `pages/` pode acessar `st.session_state` diretamente.

---

## 4. Segurança da API Comercial

A API FastAPI (`api.py`) implementa duas camadas de segurança independentes:

### Camada 1 — Autenticação por API Key

- Header: `X-API-Key: <raw_key>`
- Processamento: `SHA-256(raw_key)` comparado contra tabela `api_keys` no Supabase
- A chave bruta **jamais** é logada, armazenada ou retornada em respostas
- Fail-open: banco indisponível → `warnings.warn()` + requisição permitida

```sql
-- Tabela api_keys
CREATE TABLE api_keys (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash    text UNIQUE NOT NULL,
    name        text NOT NULL,
    is_active   boolean DEFAULT true,
    created_at  timestamptz DEFAULT now(),
    last_used_at timestamptz
);
```

### Camada 2 — Controle de Concorrência e Rate Limiting

- **Cap global:** `MAX_CONCURRENT_PIPELINES = 4` via `threading.Lock` (proteção de memória/CPU)
- **Sliding window por key:** 10 requisições por 60 segundos via `deque` (O(1) amortizado)
- Resposta em excesso: HTTP 429 com header `Retry-After`

---

## 5. LGPD — Camada de Conformidade

O P2D implementa três mecanismos independentes de proteção de dados pessoais:

### Tier 1 — Sanitização Estruturada (por chamada, stateless)

Padrões: CPF, CNPJ, e-mail, telefone, valores monetários → tokens `@LABEL_NNN`

### Tier 2 — Pseudonimização de Nomes (por sessão)

- `detect_names(transcript)` via spaCy NER → `hub.meta.name_map`
- Substituição: `[PESSOA:XX]` no wire (LLM nunca vê nomes reais)
- Desanitização antes de salvar no Supabase (RAG preservado com nomes reais)
- O mapa de reversão **nunca é persistido** (dado pessoal em memória apenas)

### Camada LGPD (`modules/compliance/`)

- `detector.py`: detecção de PII pós-pipeline
- `audit.py`: trilha de auditoria imutável (`compliance_audit`)
- `consent.py`: painel de consentimento (`compliance_consent`)

---

## 6. Padrão de Agente — PC83/PC84

Todo agente LLM no pipeline deve implementar o padrão completo:

```python
class MyAgent(BaseAgent):
    name = "my_agent"
    skill_path = "skills/skill_my.md"          # lowercase, git ls-files verificado
    required_hub_fields = ["transcript_clean"]  # dot-paths validados antes de run()
    output_schema = MyOutputSchema              # Pydantic v2, fail-open

    def build_prompt(self, hub, output_language="Auto-detect") -> tuple[str, str]:
        system = self._load_skill()             # lê skill_path, extrai frontmatter
        user = f"...\n{hub.transcript_clean}"
        return system, user

    def run(self, hub, output_language="Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub
```

**Frontmatter obrigatório** em todos os skill files:

```yaml
---
version: X.Y
agent: my_agent
description: Descrição do propósito do skill.
---
```

---

## 7. Matriz de Progresso do Pipeline API (PC107)

Estado do pipeline FastAPI após a entrega do PC107:

| Componente | Status | Implementação |
|---|---|---|
| Autenticação X-API-Key | ✅ Completo | SHA-256 → `api_keys` Supabase, fail-open |
| Rate Limiting por key | ✅ Completo | Sliding window deque O(1), 10 req/60s |
| Cap global de concorrência | ✅ Completo | threading.Lock, MAX=4 pipelines |
| Desacoplamento Streamlit | ✅ Completo | 3-layer resolution em `BaseAgent._call_llm()` |
| Callback de progresso | ✅ Completo | Heurística por agente, thread-safe |
| Persistência real | ✅ Completo | 6 saves independentes, fail-open, espelha Pipeline.py |
| Suite de testes | ✅ 41 testes | 4 classes, 0 dependências de rede |

**Pesos heurísticos do callback:**

| Agente | Peso |
|---|---|
| BPMN | 40% |
| Ata de Reunião | 20% |
| Requisitos | 20% |
| Qualidade da Transcrição | 5% |
| SBVR | 4% |
| BMM | 3% |
| Sintetizador | 3% |
| Outros / Setup | 5% |

---

## 8. Gestão de Memória de Longo Prazo

Para garantir continuidade entre sessões (agentes e humanos):

| Arquivo | Propósito |
|---|---|
| `CLAUDE.md` | Fonte da verdade — restrições de runtime, estrutura do repositório |
| `manifestos/PRODUCT_MANIFESTO.md` | Filosofia de produto — o quê e por quê (a alma); decisões de produto consultam este primeiro |
| `manifestos/COLLABORATIVE_MANIFESTO.md` | Governança de equipe — papéis, dinâmica de cooperação |
| `manifestos/ENGINEERING_MANIFESTO.md` | Este arquivo — princípios arquiteturais e decisões técnicas permanentes |
| `manifestos/CONTINUIDADE_ARQUITETURAL.md` | Blindagem contra SPOF — protocolo de substituição do Arquiteto Sênior |
| `memory/MEMORY.md` | Índice leve de memória entre sessões (Claude Code) |
| `memory/project_state.md` | Estado detalhado — versão atual, compliance, migrations, histórico |
| `claude_guideline/roadmap.md` | Histórico completo de PCs (PC1 em diante) |

**Diretriz:** Ao iniciar qualquer nova sessão ou tarefa, a leitura cruzada dos arquivos de memória é obrigatória para garantir continuidade histórica e evitar regressões.

---

## 9. Regras de Deploy e Qualidade

- **Deploy:** `git push origin main` → Streamlit Cloud auto-rebuild. Nunca editar arquivos grandes pelo editor web do GitHub.
- **Skill files:** sempre lowercase; verificar com `git ls-files skills/` antes de commitar.
- **KnowledgeHub:** novos campos sempre via `migrate()` — nunca `hasattr` espalhado.
- **Supabase:** sempre fail-open — retornar `[]` ou `None`, nunca propagar exceção.
- **Testes:** `pytest tests/` antes de todo commit de feature.
- **Versões:** toda entrega recebe um código PC (ex: PC107) registrado em `claude_guideline/roadmap.md`.

---

## 10. Checklist de Migração para Google Cloud (Fase Preparatória)

> **Status:** Infraestrutura declarativa criada (`Dockerfile`, `infra/`). Migração de runtime pendente.
> **Referência arquitetural:** `melhorias/migracao-para-google-cloud.md` (plano completo por Antigravity).

### 10.1 — Componentes locais e seus substitutos GCP

| Componente atual (`api.py`) | Substituto GCP | Fase | Status |
|---|---|---|---|
| `threading.Lock` (cap global) | **Cloud Tasks** — fila com concurrency limit nativa | 2 | Pendente |
| `deque` sliding window por key | **Memorystore (Redis)** — rate limiting distribuído | 2 | Pendente |
| `dict _JOBS` em memória | **Supabase `api_jobs` table** ou **Firestore** com TTL | 2 | Pendente |
| `ThreadPoolExecutor` local | **Cloud Run** + **Cloud Tasks** (workers separados) | 2 | Pendente |
| Variáveis de ambiente plaintext | **Secret Manager** — rotação automática, audit trail | 1 | Infraestrutura criada |
| Deploy manual (`git push`) | **Cloud Build trigger** em `infra/cloudbuild.yaml` | 1 | Infraestrutura criada |
| Streamlit Cloud (app web) | **Cloud Run** (segundo serviço — `app.py` com Streamlit) | 3 | Pendente |
| `modules/embeddings.py` (OpenAI) | **Vertex AI Embeddings** (Gemini nativo) | 4 | Pendente |
| Pasta `agents/agent_bpmn/examples/` (estática) | **Vertex AI Vector Search** (busca semântica dinâmica) | 4 | Pendente |

### 10.2 — threading.Lock → Cloud Tasks (Guia de Migração)

O `threading.Lock` em `api.py` garante que no máximo `MAX_CONCURRENT_PIPELINES=4` pipelines rodem simultaneamente **dentro de uma instância**. Ao escalar para múltiplas instâncias no Cloud Run, o lock perde eficácia — cada instância tem seu próprio contador.

**Padrão de substituição (Fase 2):**

```python
# ATUAL — local, volátil, não funciona entre instâncias Cloud Run
MAX_CONCURRENT_PIPELINES = 4
_active_pipeline_count = 0
_active_pipeline_lock = threading.Lock()

# FUTURO — Cloud Tasks gerencia concurrency limit globalmente
from google.cloud import tasks_v2

def enqueue_pipeline(job_id: str, config: dict) -> str:
    """Enfileira job no Cloud Tasks com max_dispatches_per_second=4."""
    client = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(GCP_PROJECT_ID, CLOUD_TASKS_LOCATION, CLOUD_TASKS_QUEUE)
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{WORKER_URL}/internal/run",
            "body": json.dumps({"job_id": job_id, "config": config}).encode(),
            "headers": {"Content-Type": "application/json"},
            "oidc_token": {"service_account_email": SERVICE_ACCOUNT},
        }
    }
    response = client.create_task(parent=queue_path, task=task)
    return response.name
```

**Configuração da fila (gcloud):**
```bash
gcloud tasks queues create p2d-pipeline-queue \
  --location=us-central1 \
  --max-dispatches-per-second=4 \
  --max-concurrent-dispatches=4 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s
```

### 10.3 — Checklist de Pré-Condições (Fase 1 — antes do primeiro deploy)

- [ ] Artifact Registry habilitado: `gcloud artifacts repositories create p2d --repository-format=docker --location=us-central1`
- [ ] Service account criada: `p2d-api-sa@PROJECT_ID.iam.gserviceaccount.com` com roles `roles/secretmanager.secretAccessor` + `roles/run.invoker` + `roles/logging.logWriter`
- [ ] Secrets criados no Secret Manager: `deepseek-api-key`, `supabase-url`, `supabase-service-key` (ver `infra/cloudrun/env.template.yaml`)
- [ ] Cloud Build API habilitada: `gcloud services enable cloudbuild.googleapis.com`
- [ ] Cloud Run API habilitada: `gcloud services enable run.googleapis.com`
- [ ] Primeira build: `gcloud builds submit . --config infra/cloudbuild.yaml`
- [ ] Validar liveness probe: `curl https://<SERVICE_URL>/health`
- [ ] Migrar `.streamlit/secrets.toml` para Secret Manager (nunca deployar `secrets.toml`)

### 10.4 — Princípios de Isolamento mantidos no Cloud Run

Conforme `ENGINEERING_MANIFESTO §3` (Isolamento de Estado):

1. **`WORKERS=1` por instância** — `_JOBS` dict, `_active_pipeline_count` e `_key_windows` são coerentes dentro de 1 worker. Cloud Run escala criando novas instâncias, não novos workers.
2. **`containerConcurrency=4`** — alinhado com `MAX_CONCURRENT_PIPELINES`; Cloud Run enfileira requests excedentes automaticamente.
3. **Nenhum `st.session_state`** — `BaseAgent._call_llm()` usa padrão 3 camadas (PC106); `client_info` dict é a única fonte de configuração no contexto API.
4. **Fail-open preservado** — Secret Manager indisponível não bloqueia a API; `_get_api_supabase()` retorna `None` + `warnings.warn()`.

---

## 11. Fail-Open em Infraestrutura Cloud

> **Origem:** COLLABORATIVE_MANIFESTO v5.11 §5.4 (30/06/2026) — Decisões assinadas pelo Agente 0.

**Princípio:** O Fail-Open do §2 aplica-se integralmente à infraestrutura gerenciada GCP. Nenhuma falha de serviço cloud bloqueia a operação do usuário.

### 11.1 — 4 Camadas de Fallback (precedência top-down)

| Serviço | Falha | Fallback | Comportamento |
|---|---|---|---|
| **Secret Manager** | offline / permissão negada | Cache local (24h) → ENV var → modo degradado | `get_secret()` retorna None; caller usa default |
| **Cloud Tasks** | indisponível / quota excedida | `ThreadPoolExecutor` local síncrono | `enqueue_pipeline()` detecta via `CLOUD_TASKS_QUEUE` ausente |
| **Cloud SQL / Supabase** | offline / timeout | Retornar `[]` ou `None` | Toda função de `project_store` encapsulada em `try/except` |
| **Vertex AI / LLM externo** | rate limit / indisponível | DeepSeek → OpenAI → Groq (hierarquia do §4) | `BaseAgent._call_llm()` com retry + provider fallback |

### 11.2 — Regras Mandatórias

- **Toda falha deve ser logada** (`logger.warning`) com contexto suficiente para diagnóstico
- **Notificação ao Agente 0** para falhas recorrentes (n8n alertas configurados)
- **Métrica de SLA:** % de requisições atendidas em modo degradado < 5% (target: 0%)
- **Recuperação automática:** auto-restart de container via Cloud Run health probes (`/health` → `livenessProbe`)
- **Audit trail:** toda operação de persistência que falha deve emitir `warnings.warn()` (jamais silenciar com `pass`)

### 11.3 — Cloud Tasks vs. threading.Lock (migração de concorrência)

O `threading.Lock` em `api.py` garante isolamento **dentro de uma instância**. Ao escalar para múltiplas instâncias no Cloud Run, perde eficácia — cada instância tem seu próprio contador.

| Componente | Fase 1 (atual) | Fase 2 (futuro) |
|---|---|---|
| Concorrência | `threading.Lock` + `_active_pipeline_count` (por instância) | Cloud Tasks `max-concurrent-dispatches=4` (global) |
| Fila de jobs | `dict _JOBS` em memória (volátil) | Supabase `api_jobs` table ou Firestore com TTL |
| Executor | `ThreadPoolExecutor` local | Cloud Run workers separados + Cloud Tasks dispatch |
| Rate limiting | `deque` sliding window (por instância) | Memorystore Redis (distribuído, cross-instance) |

**Implementação atual** (`services/cloud_tasks.py`): detecção automática via `CLOUD_TASKS_QUEUE` env var; Fail-Open total — qualquer erro no Cloud Tasks → fallback síncrono transparente.

```python
# Auto-detecção em services/cloud_tasks.py
def _detect_mode() -> CloudTasksMode:
    return (
        CloudTasksMode.CLOUD_TASKS
        if os.environ.get("CLOUD_TASKS_QUEUE", "").strip()
        else CloudTasksMode.SYNC_FALLBACK
    )
```

---

*"Nenhum agente anula o outro. Somamos a capacidade analítica visual com a eficiência bruta de terminal, sob direção humana."*
