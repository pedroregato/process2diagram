# MELHORIAS_API.md — API Comercial Process2Diagram

> Registro arquitetural do commit `aba7691` e plano de integração do pipeline.
> Referência de implementação: `api.py`, `tests/test_api_security.py`, `setup/supabase_migration_api_keys.sql`

---

## Contexto

A API comercial transforma o pipeline multiagente Process2Diagram em um serviço REST assíncrono.
O commit `aba7691` estabelece as duas camadas críticas de proteção que permitem expor o pipeline
a clientes externos sem comprometer a segurança nem saturar os recursos do servidor.

O ponto de partida foi o rascunho conceitual `drafts/api_draft.py`, produzido pelo agente
Antigravity. O arquivo foi arquivado em `drafts/arquivadas/` após a implementação, conforme
o fluxo co-agente estabelecido no `COLLABORATIVE_MANIFESTO.md`.

---

## 1. Camada de Segurança Criptográfica

### Hashing SHA-256 de API Keys

Nenhuma chave é armazenada em texto claro. O banco guarda exclusivamente o digest SHA-256
da raw key em formato hexadecimal (64 caracteres). A comparação ocorre exclusivamente
entre hashes — a raw key existe apenas na memória da thread HTTP durante a validação.

```python
def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()
```

O schema da tabela reflete essa decisão:

```sql
CREATE TABLE api_keys (
    key_hash     text NOT NULL UNIQUE,   -- SHA-256 hex, nunca o texto claro
    name         text NOT NULL,
    is_active    boolean NOT NULL DEFAULT true,
    last_used_at timestamptz
);
```

### Mascaramento em Logs

A raw key nunca aparece em nenhum log. Quando necessário registrar a identidade da chave
para rastreabilidade operacional, apenas os 8 primeiros caracteres do hash são expostos:

```python
logger.warning("... fail-open (hash_prefix=%s...)", key_hash[:8])
logger.info("... autenticado client='%s' hash_prefix=%s...", name, key_hash[:8])
```

Esse prefixo é suficiente para correlacionar eventos em logs sem revelar informação
suficiente para derivar a chave original.

### Politica de Negacao sem Vazamento de Metadados

Chave inexistente e chave inativa retornam o mesmo status HTTP 403. Usar 404 para
"não encontrada" vazaria a informação de que uma chave existe mas está inativa —
o que poderia orientar ataques de enumeração. A resposta unificada elimina esse vetor:

```python
if not row:
    raise HTTPException(403, "API key inválida ou não reconhecida.")
if not row.get("is_active", False):
    raise HTTPException(403, "API key revogada ou inativa.")
```

### Politica Fail-Open

Se o Supabase estiver indisponível ou lançar exceção, a requisição é liberada com um
`logger.warning` — nunca bloqueada. Isso preserva a disponibilidade do serviço durante
instabilidades de infraestrutura:

```
Supabase None  →  warn + libera (hash_prefix logado, raw key nunca)
Exceção de DB  →  warn + libera (causa da exceção logada)
```

A atualização de `last_used_at` é também fire-and-forget dentro de um `try/except` vazio,
para não bloquear a requisição em falhas de escrita não-críticas.

---

## 2. Controle de Concorrência e Rate Limiting

### Algoritmo de Janela Deslizante O(1)

O rate limit por chave usa uma `collections.deque` de timestamps monotônicos. A operação
de expiração percorre e descarta entradas pelo lado esquerdo — custo O(k) onde k é o número
de entradas expiradas, tipicamente zero ou muito pequeno em uso normal. A inserção é O(1).

```python
_RATE_WINDOW_SECS: int = 60
_RATE_MAX_REQUESTS: int = 10
_key_windows: dict[str, deque] = {}

now = time.monotonic()
window = _key_windows.setdefault(key_hash, deque())

while window and now - window[0] > _RATE_WINDOW_SECS:
    window.popleft()                          # expira entradas antigas — O(1) amortizado

if len(window) >= _RATE_MAX_REQUESTS:
    retry_after = max(1, int(_RATE_WINDOW_SECS - (now - window[0])) + 1)
    raise HTTPException(429, ..., headers={"Retry-After": str(retry_after)})

window.append(now)                            # registra esta requisição — O(1)
```

O campo `Retry-After` no header 429 informa o cliente quanto tempo esperar antes de
tentar novamente, calculado com base no timestamp mais antigo ainda na janela.

Cada chave tem sua própria janela — o saturamento de um cliente não impacta outro.

### Trava Global com threading.Lock

Chamadas LLM são pesadas (ThreadPoolExecutor + latência de rede de 2–30s por agente).
Um contador global limita pipelines simultâneos para evitar esgotamento de memória e
timeouts em cascata quando múltiplos clientes disparam pipelines ao mesmo tempo:

```python
MAX_CONCURRENT_PIPELINES: int = 4
_active_pipeline_count: int = 0
_active_pipeline_lock = threading.Lock()

# Em check_rate_limit (thread HTTP):
with _active_pipeline_lock:
    if _active_pipeline_count >= MAX_CONCURRENT_PIPELINES:
        raise HTTPException(429, "Servidor no limite de 4 pipelines simultâneos.",
                            headers={"Retry-After": "10"})

# Em _run_pipeline_sync (thread worker — início):
with _active_pipeline_lock:
    _active_pipeline_count += 1
```

`threading.Lock` é usado (em vez de `asyncio.Lock`) porque o decremento ocorre na thread
worker do `ThreadPoolExecutor`, fora do event loop do FastAPI.

### Reset do Contador no Bloco Finally

O decremento do contador é protegido por `finally` — garantindo que o slot seja liberado
mesmo que o pipeline falhe com qualquer tipo de exceção, incluindo erros de importação,
falhas de LLM ou crashs inesperados:

```python
def _run_pipeline_sync(...):
    with _active_pipeline_lock:
        _active_pipeline_count += 1
    try:
        ...  # execucao do pipeline
    except Exception as exc:
        job.status = JobStatus.ERROR
        job.error  = str(exc)
    finally:
        with _active_pipeline_lock:
            _active_pipeline_count = max(0, _active_pipeline_count - 1)
```

O `max(0, ...)` é uma salvaguarda adicional contra underflow por decrementos duplos
em condições de corrida extremas.

---

## 3. Suite de Testes — 26/26

Todos os testes usam `fastapi.testclient.TestClient` (síncrono, sem servidor real)
e mockam o Supabase via `unittest.mock.patch`. Nenhum teste faz chamada de rede.

O fixture `reset_rate_state` (autouse) garante isolamento total entre testes, zerando
`_active_pipeline_count` e limpando `_key_windows` antes e após cada caso.

### TestApiKeyValidation — 10 testes

| Teste | Comportamento verificado |
|---|---|
| `test_missing_header_returns_401` | Ausência do header X-API-Key → 401 |
| `test_empty_header_returns_401` | Header com valor em branco → 401 |
| `test_valid_key_with_supabase_passes` | Key ativa no DB → requisição prossegue |
| `test_invalid_key_with_supabase_returns_403` | Key não encontrada → 403 |
| `test_inactive_key_returns_403` | Key com `is_active=False` → 403 |
| `test_supabase_unavailable_fails_open` | DB retorna `None` → fail-open, não 401/403 |
| `test_supabase_db_exception_fails_open` | Exceção de DB → fail-open, não 401/403 |
| `test_raw_key_not_in_logs` | Raw key ausente de todos os logs capturados |
| `test_hash_function_deterministic` | SHA-256 é determinístico, 64 chars hex |
| `test_different_keys_produce_different_hashes` | Colisão de hash não ocorre entre keys distintas |

### TestConcurrencyControl — 5 testes

| Teste | Comportamento verificado |
|---|---|
| `test_first_request_passes_when_below_limit` | Contador zerado → request não bloqueado |
| `test_request_rejected_when_at_capacity` | Contador == MAX → 429 com Retry-After |
| `test_request_passes_after_capacity_freed` | Contador == MAX-1 → request passa |
| `test_counter_decrements_on_pipeline_error` | Finally decrementa mesmo em crash do pipeline |
| `test_counter_never_goes_below_zero` | Contador não fica negativo por decrementos extras |

### TestRateLimiting — 5 testes

| Teste | Comportamento verificado |
|---|---|
| `test_first_requests_within_limit_pass` | Primeiros N requests abaixo do limite passam |
| `test_exceeding_window_returns_429` | Janela cheia → 429 com detalhe do limite |
| `test_expired_timestamps_are_evicted` | Timestamps antigos não contam — janela limpa |
| `test_different_keys_have_independent_windows` | Saturar key A não bloqueia key B |
| `test_retry_after_header_present_on_rate_limit` | Retry-After presente e positivo no 429 |

### TestSecurityIntegration — 6 testes

| Teste | Comportamento verificado |
|---|---|
| `test_health_endpoint_unauthenticated` | /health sem X-API-Key → 200 |
| `test_both_layers_block_independently` | Key válida + servidor saturado → 429 (não 401) |
| `test_no_key_blocked_before_rate_limit_check` | Sem key → contador não é alterado |
| `test_upload_then_run_flow` | Fluxo completo upload → run → 202 |
| `test_status_endpoint_reflects_job_state` | /status reflete progresso e status correto |
| `test_status_endpoint_nonexistent_job_returns_404` | Job inexistente → 404 |

---

## 4. Proximos Passos — Backlog

### 4.1 Integrar _run_pipeline_sync com core/pipeline.py

O worker atual já chama `run_pipeline(hub, config, callback)` via importação local,
mas a integração com `st.session_state` (onde `BaseAgent` busca provider e api_key)
é feita por patch mínimo. O próximo passo é refatorar `BaseAgent._call_llm()` para
aceitar um `config dict` explícito como alternativa ao `st.session_state`:

```python
# Proposta de interface (BaseAgent):
def _call_llm(self, system, user, hub, *, config: dict | None = None):
    provider = (config or {}).get("provider") or st.session_state.get("provider")
    api_key  = (config or {}).get("api_key")  or st.session_state.get("api_key")
    ...
```

Isso eliminaria a dependência de Streamlit no contexto API sem quebrar o fluxo existente.

### 4.2 Mapeamento de Progresso Real no JobRecord

O campo `progress` (0–100) no `JobRecord` é atualizado manualmente em pontos fixos do
worker. A integração ideal usa o callback de `run_pipeline()` para refletir o progresso
real de cada agente:

```python
def _build_progress_callback(job: JobRecord) -> Callable:
    agent_weights = {
        "quality": 5, "bpmn": 40, "minutes": 15,
        "requirements": 15, "sbvr": 10, "bmm": 10, "synthesizer": 5,
    }
    completed: list[str] = []

    def callback(agent_name: str, pct: float) -> None:
        completed_weight = sum(agent_weights.get(a, 0) for a in completed)
        current_weight   = agent_weights.get(agent_name, 0) * pct
        job.progress     = min(99, int(completed_weight + current_weight))
        job.updated_at   = time.time()
        if pct >= 1.0:
            completed.append(agent_name)

    return callback
```

### 4.3 Persistencia no project_store com Barreira Fail-Open

A função `_persist_hub()` é hoje um stub documentado. A implementação real requer
`save_hub_to_db(hub, project_id)` em `core/project_store.py` — equivalente ao que
`pages/Pipeline.py` executa no fluxo Streamlit após cada pipeline:

```python
def _persist_hub(hub: KnowledgeHub, project_id: str) -> None:
    try:
        from core.project_store import save_hub_to_db
        save_hub_to_db(hub, project_id)
        logger.info("_persist_hub: salvo — project_id=%s meeting_id=%s",
                    project_id, hub.meta.hub_id)
    except Exception as exc:
        # Fail-open: falha de persistência não desfaz o resultado do pipeline
        logger.warning("_persist_hub: falha silenciosa — %s", exc)
```

A barreira fail-open é deliberada: o cliente já recebeu os artefatos no campo `result`
do `JobRecord`. A persistência no Supabase é conveniência, não pré-condição do retorno.

---

## Dependencias Adicionadas

```
fastapi==0.115.0          # framework REST
uvicorn[standard]==0.49.0 # servidor ASGI
python-multipart==0.0.9   # upload de arquivos via Form()
httpx==0.28.1             # cliente HTTP async + TestClient dos testes
```

## Execucao Local

```bash
# Iniciar a API
SUPABASE_URL=<url> SUPABASE_KEY=<key> uvicorn api:app --reload --port 8000

# Swagger UI disponível em:
# http://localhost:8000/docs

# Executar os testes de segurança
pytest tests/test_api_security.py -v
```

---

*Commit de referencia: `aba7691` — branch `main`*
