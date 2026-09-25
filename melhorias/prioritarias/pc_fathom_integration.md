# PC_FATHOM — Integração Fathom AI (Fase A: Pull via API)

> **Versão:** 1.1 · **Base:** v5.15 (commit `a17aee2`)
> **Escopo:** Somente Fase A — importação manual de reuniões via Fathom API. Sem webhook, sem MCP Tool.
> **Prioridade:** Feature nova, sem conflito com código existente.
> **v1.1:** revisão de nomes/estruturas reais do codebase (v1.0 tinha 6 divergências bloqueantes — função inexistente, estrutura de dict errada, session_state keys erradas). Arquitetura trocada de "registrar em `AVAILABLE_PROVIDERS`" para side-channel dedicado, seguindo o precedente real de `EMBEDDING_PROVIDERS` (`modules/embeddings.py`).

---

## Contexto

O Fathom é um AI Notetaker com plano gratuito permanente, API pública somente-leitura e servidor MCP oficial. A integração permite que o usuário selecione uma reunião gravada no Fathom e carregue a transcrição diretamente no pipeline do Vichara — eliminando a etapa manual de copiar/colar.

A API do Fathom retorna transcrição com speaker labels e timestamps, que o pipeline já consome nativamente como texto raw.

---

## Decisão de arquitetura: side-channel, não `AVAILABLE_PROVIDERS`

Fathom **não é um provider LLM** — é só uma credencial de leitura de reuniões. O codebase já tem um precedente exato pra isso: `modules/embeddings.py::EMBEDDING_PROVIDERS`, um **dict separado** de `AVAILABLE_PROVIDERS`, com sua própria chave de sessão (`asst_embed_key`) e sua própria seção em `pages/Settings.py` (aba "🔮 Embeddings & Busca"), sem qualquer registro em `modules/config.py`.

Fathom segue o mesmo molde:

- **Nenhuma mudança em `modules/config.py`** — `AVAILABLE_PROVIDERS` continua só com providers LLM reais (evita poluir os seletores "LLM Principal"/"LLM Assistente" em `Settings.py`, que iteram `AVAILABLE_PROVIDERS.keys()` sem filtro de tipo).
- **Nenhuma mudança em `agents/base_agent.py`** — não existe roteamento a alterar; `_call_llm()` nunca itera todos os providers, é chamado com o `client_type` do provider já selecionado pelo agente.
- Chave da API guardada em `st.session_state["fathom_api_key"]` (mesmo padrão de `asst_embed_key`).

---

## O que será entregue

1. **`services/fathom_client.py`** — cliente HTTP para a API do Fathom (listagem de reuniões + busca de transcrição)
2. **`pages/FathomImport.py`** — nova página Streamlit: listagem de reuniões Fathom, filtros, preview de transcrição, botão de importação para o pipeline
3. **Registro no `app.py`** — página adicionada ao grupo de navegação `"Pipeline"`
4. **Nova aba "🎙️ Integrações" em `pages/Settings.py`** — campo de API Key do Fathom, reaproveitando o helper `_render_api_key_section()` já existente no arquivo (mesmo componente usado por `tab_embed`)

---

## Arquitetura da integração

```
FathomImport.py
    └── services/fathom_client.py
            └── GET https://api.fathom.ai/v1/calls          (lista reuniões)
            └── GET https://api.fathom.ai/v1/calls/{id}/transcript  (transcrição)

Transcrição importada → st.session_state["fathom_imported_transcript"]
    → usuário navega para Pipeline.py → transcript_text preenchida automaticamente
```

A transcrição Fathom é texto puro com speaker labels (`Speaker 1: ...`). O `transcript_preprocessor.py` existente já lida com esse formato.

---

## 1. `services/fathom_client.py` — CRIAR

Sem mudanças em relação à v1.0 — este arquivo é novo, não depende de nenhuma estrutura existente além de `requests` (a adicionar em `requirements.txt`, ver seção 6).

```python
"""
Fathom AI API client — read-only.
Docs: https://developers.fathom.ai/ (verificar schema exato antes de implementar — não confirmado neste PC)
All calls fail-open: return [] / None on any error.
"""
from __future__ import annotations
import requests
import logging
from typing import Optional

log = logging.getLogger(__name__)

FATHOM_API_BASE = "https://api.fathom.ai/v1"
_TIMEOUT = 15  # segundos


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def list_calls(
    api_key: str,
    limit: int = 25,
    after: Optional[str] = None,      # ISO datetime string para paginação
    participant_email: Optional[str] = None,
) -> list[dict]:
    """
    Retorna lista de chamadas gravadas no Fathom.
    Cada item: {id, title, started_at, duration_seconds, participants: [...]}
    Retorna [] em caso de erro (fail-open).
    """
    if not api_key:
        return []
    params: dict = {"limit": limit}
    if after:
        params["after"] = after
    if participant_email:
        params["participant_email"] = participant_email
    try:
        r = requests.get(
            f"{FATHOM_API_BASE}/calls",
            headers=_headers(api_key),
            params=params,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("calls", data) if isinstance(data, dict) else data
    except Exception as e:
        log.warning("Fathom list_calls error: %s", e)
        return []


def get_transcript(api_key: str, call_id: str) -> Optional[str]:
    """
    Retorna a transcrição completa de uma chamada como texto plain-text
    com speaker labels: 'Speaker Name: texto...'
    Retorna None em caso de erro.
    """
    if not api_key or not call_id:
        return None
    try:
        r = requests.get(
            f"{FATHOM_API_BASE}/calls/{call_id}/transcript",
            headers=_headers(api_key),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # A API retorna lista de segmentos: [{speaker, text, start_time}, ...]
        # Serializar como texto com speaker labels
        segments = data.get("transcript", data) if isinstance(data, dict) else data
        if isinstance(segments, list):
            lines = []
            for seg in segments:
                speaker = seg.get("speaker", "Participante")
                text = seg.get("text", "").strip()
                if text:
                    lines.append(f"{speaker}: {text}")
            return "\n".join(lines)
        # Se já vier como string
        if isinstance(segments, str):
            return segments
        return None
    except Exception as e:
        log.warning("Fathom get_transcript error: %s", e)
        return None


def get_call_summary(api_key: str, call_id: str) -> Optional[str]:
    """
    Retorna o resumo gerado pelo Fathom (opcional — usado como preview).
    Retorna None em caso de erro.
    """
    if not api_key or not call_id:
        return None
    try:
        r = requests.get(
            f"{FATHOM_API_BASE}/calls/{call_id}/summary",
            headers=_headers(api_key),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("summary", "") or None
    except Exception as e:
        log.warning("Fathom get_call_summary error: %s", e)
        return None
```

**Nota de implementação:** A estrutura exata do JSON da API Fathom deve ser verificada contra `https://developers.fathom.ai/` no momento da implementação — não confirmada neste PC. O código acima usa `.get()` defensivamente e é fail-open — qualquer divergência de schema resulta em `[]` / `None`, nunca em exception que quebre a UI.

**Nota de precedente:** não existe hoje, em `services/`, nenhum cliente HTTP com `requests` (o projeto usa `httpx` como dependência HTTP). O analog mais próximo é `modules/calendar_client.py`, mas ele autentica via credencial de service-account em `st.secrets`, não via API key por usuário — não é reaproveitável aqui. Este arquivo introduz o primeiro padrão "raw `requests` + Bearer token de `session_state`" do projeto; é uma escolha nova, não uma continuação de um padrão existente.

---

## 2. `pages/FathomImport.py` — CRIAR

```python
"""
Fathom Import — importa transcrições do Fathom AI para o pipeline do Vichara.
Grupo de navegação: Pipeline (junto com Pipeline.py).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from ui.components.page_header import render_page_header
from services.fathom_client import list_calls, get_transcript, get_call_summary

st.set_page_config(page_title="Fathom Import · Vichara", layout="wide")
apply_auth_gate()

render_page_header("🎙️", "Fathom Import", "Importe transcrições do Fathom AI diretamente para o pipeline")

require_active_project()

# ── API Key guard ──────────────────────────────────────────────────────────────
# Mesmo padrão de modules/embeddings.py::asst_embed_key — chave em session_state
# puro, sem passar por modules/session_security.py (esse módulo resolve chaves
# via AVAILABLE_PROVIDERS, que Fathom deliberadamente NÃO integra — ver decisão
# de arquitetura no PC).
fathom_key = st.session_state.get("fathom_api_key", "")
if not fathom_key:
    st.warning(
        "**API Key do Fathom não configurada.** "
        "Acesse ⚙️ Configurações → aba 🎙️ Integrações e insira sua API Key.",
        icon="🔑",
    )
    st.stop()

# ── Filtros ────────────────────────────────────────────────────────────────────
with st.expander("🔍 Filtros", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        filter_email = st.text_input(
            "Filtrar por participante (e-mail)",
            placeholder="nome@empresa.com",
            key="fathom_filter_email",
        )
    with col2:
        filter_limit = st.slider("Número de reuniões", 5, 50, 20, key="fathom_filter_limit")

# ── Carregar lista ─────────────────────────────────────────────────────────────
if st.button("🔄 Carregar reuniões do Fathom", type="primary"):
    with st.spinner("Buscando reuniões..."):
        calls = list_calls(
            fathom_key,
            limit=filter_limit,
            participant_email=filter_email or None,
        )
    st.session_state["fathom_calls"] = calls
    if not calls:
        st.error("Nenhuma reunião encontrada. Verifique a API Key ou os filtros.")

calls = st.session_state.get("fathom_calls", [])

if not calls:
    st.info("Clique em **Carregar reuniões do Fathom** para listar suas gravações.")
    st.stop()

# ── Lista de reuniões ──────────────────────────────────────────────────────────
st.markdown(f"**{len(calls)} reunião(ões) encontrada(s)**")

selected_call_id = st.session_state.get("fathom_selected_call_id")

for call in calls:
    call_id = call.get("id", "")
    title = call.get("title") or "Reunião sem título"
    started_at = call.get("started_at", "")
    duration_s = call.get("duration_seconds") or 0
    participants = call.get("participants", [])
    n_participants = len(participants)

    duration_str = ""
    if duration_s:
        m, s = divmod(int(duration_s), 60)
        h, m = divmod(m, 60)
        duration_str = f"{h}h {m}min" if h else f"{m}min"

    date_str = ""
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            date_str = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            date_str = started_at[:10]

    is_selected = call_id == selected_call_id
    label = f"{'✅ ' if is_selected else ''}**{title}**  ·  {date_str}  ·  {duration_str}  ·  {n_participants} participante(s)"

    if st.button(label, key=f"fathom_call_{call_id}", use_container_width=True):
        st.session_state["fathom_selected_call_id"] = call_id
        st.session_state.pop("fathom_preview_transcript", None)
        st.session_state.pop("fathom_preview_summary", None)
        st.rerun()

# ── Preview da reunião selecionada ─────────────────────────────────────────────
if selected_call_id:
    st.divider()
    selected_call = next((c for c in calls if c.get("id") == selected_call_id), None)
    if selected_call:
        st.subheader(f"🎙️ {selected_call.get('title') or 'Reunião selecionada'}")

    col_prev, col_imp = st.columns([3, 1])

    with col_prev:
        if st.button("👁️ Preview da transcrição", key="fathom_preview_btn"):
            with st.spinner("Buscando transcrição..."):
                transcript = get_transcript(fathom_key, selected_call_id)
                summary = get_call_summary(fathom_key, selected_call_id)
            st.session_state["fathom_preview_transcript"] = transcript
            st.session_state["fathom_preview_summary"] = summary

    with col_imp:
        if st.button("🚀 Importar para o Pipeline", type="primary", key="fathom_import_btn"):
            with st.spinner("Carregando transcrição..."):
                transcript = st.session_state.get("fathom_preview_transcript") \
                             or get_transcript(fathom_key, selected_call_id)
            if transcript:
                st.session_state["fathom_imported_transcript"] = transcript
                st.session_state["fathom_imported_title"] = (
                    selected_call.get("title") if selected_call else ""
                )
                st.success(
                    "✅ Transcrição importada! "
                    "Acesse **Processar Transcrição** para processar.",
                    icon="🎙️",
                )
                st.page_link("pages/Pipeline.py", label="Ir para Processar Transcrição →")
            else:
                st.error("Não foi possível obter a transcrição. Tente novamente.")

    preview_transcript = st.session_state.get("fathom_preview_transcript")
    preview_summary = st.session_state.get("fathom_preview_summary")

    if preview_summary:
        with st.expander("📝 Resumo do Fathom", expanded=False):
            st.markdown(preview_summary)

    if preview_transcript:
        with st.expander("📄 Transcrição (primeiras 3.000 chars)", expanded=True):
            st.text(preview_transcript[:3000] + ("..." if len(preview_transcript) > 3000 else ""))
```

**Correção vs. v1.0:** removida a importação `from modules.session_security import get_api_key` — essa função **não existe** em `modules/session_security.py`. A chave é lida direto de `st.session_state["fathom_api_key"]`, mesmo padrão de `asst_embed_key` em `modules/embeddings.py`.

---

## 3. `app.py` — MODIFICAR

Navegação real (`app.py:52-104`) é um **dict de grupos**, não uma lista solta. O grupo `"Pipeline"` existe (`app.py:60-65`) com este conteúdo atual:

```python
"Pipeline": [
    st.Page("pages/Pipeline.py",    title="Processar Transcrição", icon="🚀"),
    st.Page("pages/Diagramas.py",   title="Diagramas",             icon="📐"),
    st.Page("pages/BpmnEditor.py",  title="Editor BPMN",           icon="✏️"),
    st.Page("pages/BpmnStudio.py",  title="BPMN Studio",           icon="🏗️"),
],
```

Adicionar uma linha dentro dessa mesma lista:

```python
"Pipeline": [
    st.Page("pages/Pipeline.py",      title="Processar Transcrição", icon="🚀"),
    st.Page("pages/FathomImport.py",  title="Fathom Import",         icon="🎙️"),  # NOVO
    st.Page("pages/Diagramas.py",     title="Diagramas",             icon="📐"),
    st.Page("pages/BpmnEditor.py",    title="Editor BPMN",           icon="✏️"),
    st.Page("pages/BpmnStudio.py",    title="BPMN Studio",           icon="🏗️"),
],
```

**Correção vs. v1.0:** a página de Pipeline se chama `"Processar Transcrição"` na navegação, não `"Pipeline"` — o título é só o nome do arquivo.

---

## 4. `pages/Pipeline.py` — MODIFICAR (mínimo)

O textarea da transcrição (`ui/input_area.py:14-21`) é vinculado à chave de widget `"transcript_input"`, mas seu valor de origem — o que de fato precisa ser pré-preenchido — é `st.session_state.transcript_text` (`ui/input_area.py:16`, sincronizado por `update_transcript()` a cada mudança). **Não existe** chave `transcricao_input` em nenhum lugar do código.

`pages/Pipeline.py` não chama `init_session_state()` nem `require_active_project()` — quem chama `init_session_state()` é `app.py:32`, uma vez, antes de `st.navigation()`; toda página herda o session_state já inicializado. `Pipeline.py` usa `render_project_selector()` (linha 130), não `require_active_project()`.

O ponto de inserção correto é **antes** da chamada a `render_input_area()` (`pages/Pipeline.py:170`) e **depois** de `render_project_selector()` (linha 130) — antes do widget `key="transcript_input"` ser instanciado nesta run, para não disparar o erro do Streamlit "widget value cannot be set after instantiation":

```python
# Inserir em pages/Pipeline.py, depois de render_project_selector() (linha 130)
# e antes de render_input_area() (linha 170):
_fathom_transcript = st.session_state.pop("fathom_imported_transcript", None)
_fathom_title = st.session_state.pop("fathom_imported_title", None)

if _fathom_transcript:
    st.session_state["transcript_text"] = _fathom_transcript
    if _fathom_title:
        st.session_state["meeting_title_input"] = _fathom_title
    st.info("📥 Transcrição importada do Fathom. Revise e processe normalmente.", icon="🎙️")
```

`meeting_title_input` é uma chave real — o widget que a usa vive em `ui/project_selector.py:163`, dentro de `render_project_selector()`, então essa atribuição precisa acontecer **antes** de `render_project_selector()` já ter sido chamada nesta run para não colidir com o mesmo erro de widget. Como `render_project_selector()` roda na linha 130 e o snippet acima é inserido depois dela, **a pré-preenchida de `meeting_title_input` só terá efeito no próximo rerun** (o de quando o usuário navega da página Fathom Import para Pipeline) — que é exatamente o caso de uso real (o `st.session_state["fathom_imported_title"]` é setado em `FathomImport.py` numa run anterior, então na primeira run de `Pipeline.py` após o import, `render_project_selector()` ainda não rodou "depois" desta atribuição — está tudo na mesma run, mas a ordem das linhas garante que a atribuição acontece antes do widget ser instanciado). Testar esse fluxo manualmente é o item mais importante do checklist abaixo.

**Correção vs. v1.0:** chave errada (`transcricao_input` → `transcript_text`), ponto de inserção inexistente (`init_session_state()`/`require_active_project()` não são chamados neste arquivo) substituído pelas chamadas reais que existem.

**Pitfall (mantido da v1.0):** usar `.pop()` para consumir o valor após uso — evita que o rerun automático do Streamlit recarregue a transcrição indefinidamente.

---

## 5. Nova aba "🎙️ Integrações" em `pages/Settings.py` — CRIAR

**Correção de arquitetura vs. v1.0:** a v1.0 propunha registrar Fathom em `modules/config.py::AVAILABLE_PROVIDERS` com um `client_type: "api_only"` novo. Isso foi descartado porque:

- `pages/Settings.py` itera `AVAILABLE_PROVIDERS.keys()` **sem nenhum filtro de `client_type`** (linhas 124 e 213) para alimentar os seletores "LLM Principal" e "LLM Assistente" — registrar Fathom ali faria "Fathom" aparecer como opção de LLM selecionável, o que é incorreto.
- Não existe aba "Provedores" genérica em `Settings.py` — as 7 abas reais são `tab_llm, tab_asst, tab_embed, tab_db, tab_roster, tab_pref, tab_domain` (`pages/Settings.py:102-110`).
- O codebase já tem o precedente certo para "credencial não-LLM": `EMBEDDING_PROVIDERS` (dict próprio) + aba própria + helper `_render_api_key_section()` (`pages/Settings.py:40+`), reaproveitável sem alterar `AVAILABLE_PROVIDERS`.

Adicionar uma 8ª aba, reaproveitando o helper existente:

```python
# pages/Settings.py — no st.tabs(), adicionar "🎙️ Integrações":
tab_llm, tab_asst, tab_embed, tab_db, tab_roster, tab_pref, tab_domain, tab_integrations = st.tabs([
    "🤖 LLM Principal",
    "💬 LLM Assistente",
    "🔮 Embeddings & Busca",
    "🗄️ Banco de Dados",
    "👥 Participantes",
    "🌐 Preferências",
    "🔑 Domínio",
    "🎙️ Integrações",   # NOVO
])

# ... (final do arquivo, junto às outras abas)
with tab_integrations:
    st.markdown(
        "Credenciais de integrações externas que **não são providers de LLM** — "
        "guardadas apenas em `st.session_state`, mesmo padrão da aba Embeddings."
    )
    st.markdown("---")
    st.markdown("#### 🎙️ Fathom AI — API Key")
    _render_api_key_section(
        section_title="Fathom",
        state_key="fathom_api_key",
        label="Fathom API Key",
        placeholder="...",
        help_text="Gere em developers.fathom.ai — verificar URL/fluxo exato na implementação.",
        save_btn_key="settings_save_fathom_key",
        clear_btn_key="settings_clear_fathom_key",
        input_key="settings_input_fathom_key",
        persist_key="",   # sem persistência em tenant_config nesta fase (Fase A = sessão apenas)
    )
```

`_render_api_key_section()` já existe em `pages/Settings.py` (usado por `tab_embed` para `asst_embed_key`) — não precisa ser criado, só chamado com os parâmetros do Fathom.

---

## 6. `modules/config.py` — SEM MUDANÇAS

**Correção vs. v1.0:** a v1.0 propunha adicionar uma entrada Fathom em `AVAILABLE_PROVIDERS` com `client_type: "api_only"` (novo) e uma guarda equivalente em `agents/base_agent.py::_call_llm()`. Isso não é necessário: `_call_llm()` nunca itera todos os providers — é chamado com o `client_type` do provider específico já selecionado pelo agente (`self.provider_cfg["client_type"]`), então um `client_type` desconhecido em Fathom nunca seria alcançado por esse caminho de qualquer forma. A raiz do problema era outra (item 5 acima: os seletores de LLM em Settings.py, não o roteamento de `_call_llm()`), e a solução de side-channel evita o problema pela raiz, sem precisar de nenhuma guarda nova.

---

## Arquivo não tocado: `services/semantic_cache.py`, `agents/`, `core/pipeline.py`, `modules/config.py`

A transcrição importada entra no pipeline exatamente como se o usuário tivesse colado — nenhuma alteração no core do pipeline é necessária.

---

## Dependência externa

`requests` **não está** em `requirements.txt` hoje (confirmado — o projeto usa `httpx` como cliente HTTP). Adicionar:
```
requests==2.32.3
```

---

## Checklist de Entrega

- [ ] `services/fathom_client.py` criado e fail-open em todos os métodos
- [ ] `pages/FathomImport.py` criado com guard de API Key (`st.session_state["fathom_api_key"]`)
- [ ] `app.py` atualizado com a nova página dentro da lista do grupo `"Pipeline"` (dict `pages`)
- [ ] `pages/Pipeline.py` lê e consome `fathom_imported_transcript`/`fathom_imported_title` com `.pop()`, escrevendo em `transcript_text`/`meeting_title_input`, entre `render_project_selector()` e `render_input_area()`
- [ ] `pages/Settings.py` ganha aba "🎙️ Integrações" reaproveitando `_render_api_key_section()`
- [ ] `modules/config.py` e `agents/base_agent.py` **não** modificados
- [ ] `requirements.txt` atualizado com `requests==2.32.3`
- [ ] Versão registrada em `claude_guideline/roadmap.md`
- [ ] Testado manualmente: importar uma reunião real do Fathom, confirmar que `transcript_text` E `meeting_title_input` chegam pré-preenchidos em Pipeline.py, e processar no pipeline
- [ ] Testado: schema real da API Fathom confere com o `.get()` defensivo de `fathom_client.py` — ajustar parsing se divergir

---

## O que NÃO está no escopo deste PC

- Webhook automático pós-reunião (Fase B — PC separado)
- MCP Tool no AgentAssistant (Fase C — PC separado)
- Suporte a múltiplas contas Fathom por domínio
- Filtro por data na listagem (pode ser adicionado na Fase B)
- Sincronização automática de reuniões antigas
- Persistência da API Key do Fathom em `tenant_config` (Fase A guarda só em sessão — se necessário, seguir o mesmo padrão opcional de `persist_key` que `_render_api_key_section()` já suporta)
