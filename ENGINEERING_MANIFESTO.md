# Manifesto de Engenharia — Process2Diagram (P2D)

> **Versão:** 1.0 | **Data:** Junho de 2026 | **Status:** Ativo — leitura obrigatória para todos os agentes e colaboradores.

Este documento é a fonte canônica dos princípios arquiteturais que governam o desenvolvimento do P2D. Ele complementa o `COLLABORATIVE_MANIFESTO.md` (governança de equipe) e o `CLAUDE.md` (restrições técnicas de runtime).

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
| `COLLABORATIVE_MANIFESTO.md` | Governança de equipe — papéis, dinâmica de cooperação |
| `ENGINEERING_MANIFESTO.md` | Este arquivo — princípios arquiteturais e decisões técnicas permanentes |
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

*"Nenhum agente anula o outro. Somamos a capacidade analítica visual com a eficiência bruta de terminal, sob direção humana."*
