# Estratégia de Melhorias — Assistente.py Chat UI
**Process2Diagram v4.15 → v4.16**

---

## Visão Geral

Três melhorias independentes e incrementais na página `pages/Assistente.py`:

| # | Feature | Complexidade | Session State Impact |
|---|---------|--------------|----------------------|
| 1 | Chat UI elegante (estilo Claude Code Web) | Alta | Nenhum — só CSS/HTML |
| 2 | Exportar conversa para Markdown | Baixa | Novo botão + lógica de formatação |
| 3 | Limpar área de conversas | Baixa | `st.session_state["messages"] = []` |

---

## 1. Chat UI Elegante — Estilo Claude Code Web

### Referência visual

O Claude Code Web usa:
- Fundo escuro (`#0d1117` / `#1a1a2e`) com mensagens em cards sutis
- Tipografia monospace para código, sans-serif para prosa
- Bolhas de usuário com fundo levemente destacado (azul escuro ou cinza-médio)
- Mensagens do assistente sem fundo destacado — apenas texto fluido
- Avatar mínimo (ícone ou inicial) à esquerda de cada turno
- Timestamp discreto em cada mensagem
- Separador visual suave entre turnos
- Input box com borda arredondada, fundo semi-transparente, ícone de envio

### Implementação em Streamlit

O Streamlit injeta `st.chat_message()` com classes CSS previsíveis. O override deve usar `st.markdown(..., unsafe_allow_html=True)` para os blocos de mensagem customizados, mantendo `st.chat_input()` padrão (que já tem bom comportamento nativo).

#### Estratégia recomendada: HTML customizado via `st.components.v1.html` para o histórico

Renderizar o histórico de mensagens como um bloco HTML único dentro de um `components.html()` com altura fixa e scroll interno — exatamente como o Claude Code Web faz. O `st.chat_input()` permanece nativo do Streamlit (abaixo do componente).

**Vantagens:**
- Controle total de CSS sem brigar com classes geradas pelo Streamlit
- Scroll interno independente da página
- Suporte a Markdown renderizado (via `marked.js` CDN — mas atenção: **Streamlit Cloud bloqueia eval() no CSP**; usar `marked.parse()` sem eval é seguro pois marked.js não usa `new Function`)
- Fácil integrar timestamp e avatar

#### CSS Theme (alinhado com IBM Plex Mono/Sans já usado no app.py)

```css
/* Variáveis de tema — escuro, alinhado com sidebar atual (#0f172a) */
--chat-bg: #0f172a;
--chat-surface: #1e293b;
--chat-border: #334155;
--chat-user-bubble: #1d4ed8;      /* azul escuro */
--chat-assistant-bg: transparent;
--chat-text: #e2e8f0;
--chat-muted: #64748b;
--chat-code-bg: #0a0f1a;
--font-mono: 'IBM Plex Mono', monospace;
--font-sans: 'IBM Plex Sans', sans-serif;
--radius: 12px;
--radius-sm: 6px;
```

#### Estrutura HTML de cada mensagem

```html
<!-- Turno do usuário -->
<div class="msg-row user">
  <div class="avatar user-avatar">P</div>
  <div class="bubble user-bubble">
    <div class="msg-content">Texto da pergunta</div>
    <div class="msg-meta">14:32</div>
  </div>
</div>

<!-- Turno do assistente -->
<div class="msg-row assistant">
  <div class="avatar asst-avatar">⚙</div>
  <div class="bubble asst-bubble">
    <div class="msg-content"><!-- markdown renderizado --></div>
    <div class="msg-meta">14:32 · DeepSeek · 3 ferramentas usadas</div>
  </div>
</div>
```

#### Renderização de Markdown segura (sem CDN bloqueado)

Para evitar o problema do CSP do Streamlit Cloud com bibliotecas que usam `eval()`, usar **`marked.js` via unpkg com opção `mangle: false`** — ou melhor ainda: **pré-renderizar o Markdown para HTML no Python** usando `markdown` lib antes de passar ao componente:

```python
# No Python (servidor)
import markdown as md_lib

def render_md(text: str) -> str:
    return md_lib.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"]
    )
```

`markdown` já está disponível no ecossistema Python; adicionar ao `requirements.txt` se ausente.

#### Integração com session_state atual

O histórico já vive em `st.session_state["messages"]` como lista de dicts `{"role": ..., "content": ..., "timestamp": ..., "provider": ..., "tools_used": [...]}`. A renderização customizada lê essa lista e gera o HTML correspondente.

```python
def render_chat_html(messages: list[dict]) -> str:
    rows = []
    for msg in messages:
        role = msg["role"]
        content = render_md(msg["content"]) if role == "assistant" else html.escape(msg["content"])
        ts = msg.get("timestamp", "")
        meta_parts = [ts]
        if role == "assistant":
            if prov := msg.get("provider"):
                meta_parts.append(prov)
            if tools := msg.get("tools_used"):
                meta_parts.append(f"{len(tools)} ferramenta(s)")
        meta = " · ".join(filter(None, meta_parts))
        avatar = "P" if role == "user" else "⚙"
        rows.append(f"""
        <div class="msg-row {role}">
          <div class="avatar {'user-avatar' if role=='user' else 'asst-avatar'}">{avatar}</div>
          <div class="bubble {'user-bubble' if role=='user' else 'asst-bubble'}">
            <div class="msg-content">{content}</div>
            <div class="msg-meta">{meta}</div>
          </div>
        </div>
        """)
    return "\n".join(rows)
```

#### Altura e scroll

```python
components.html(
    f"""
    <style>{CHAT_CSS}</style>
    <div id="chat-container">
      {render_chat_html(messages)}
    </div>
    <script>
      // Auto-scroll para o final após render
      const c = document.getElementById('chat-container');
      c.scrollTop = c.scrollHeight;
    </script>
    """,
    height=600,
    scrolling=False,  # scroll interno via CSS overflow-y: auto
)
```

#### Nota sobre o re-edit feature existente

O botão `✏️` de re-edição de mensagens usa `st.session_state["_edit_idx"]`. Com a nova renderização HTML customizada, os botões de edição não podem ficar dentro do `components.html` (iframes não comunicam com Streamlit). Manter os botões de edição como `st.button()` fora do componente, em um expander colapsado "🔧 Editar mensagens anteriores" — ou simplificar: mostrar os botões de edição apenas em modo de lista abaixo do chat (toggle `show_edit_mode`).

---

## 2. Exportar Conversa para Markdown

### Comportamento

Botão **"⬇️ Exportar Conversa"** na toolbar acima do chat. Gera um arquivo `.md` com toda a conversa formatada.

### Formato do arquivo gerado

```markdown
# Conversa — Assistente P2D
**Projeto:** Nome do Projeto  
**Data:** 2026-05-13 14:32  
**Provedor LLM:** DeepSeek  

---

## Turno 1

**Você:** Quais foram as decisões da reunião 3?

**Assistente (14:32 · DeepSeek):**

Com base na reunião 3, as decisões foram:

1. Aprovar o novo fluxo de onboarding
2. Migrar para Supabase até junho

---

## Turno 2
...
```

### Implementação

```python
def export_chat_to_markdown(
    messages: list[dict],
    project_name: str,
    provider: str,
) -> str:
    lines = [
        "# Conversa — Assistente P2D",
        f"**Projeto:** {project_name}",
        f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Provedor LLM:** {provider}",
        "",
        "---",
        "",
    ]
    turn = 0
    for i, msg in enumerate(messages):
        if msg["role"] == "user":
            turn += 1
            lines.append(f"## Turno {turn}")
            lines.append("")
            lines.append(f"**Você:** {msg['content']}")
            lines.append("")
        elif msg["role"] == "assistant":
            ts = msg.get("timestamp", "")
            prov = msg.get("provider", provider)
            tools = msg.get("tools_used", [])
            meta = f"{ts} · {prov}"
            if tools:
                meta += f" · ferramentas: {', '.join(tools)}"
            lines.append(f"**Assistente ({meta}):**")
            lines.append("")
            lines.append(msg["content"])
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines)
```

### Renderização no Streamlit

```python
# Na toolbar acima do chat
col_export, col_clear, col_spacer = st.columns([1, 1, 6])

with col_export:
    if st.session_state.get("messages"):
        md_content = export_chat_to_markdown(
            st.session_state["messages"],
            project_name=st.session_state.get("selected_project_name", "Projeto"),
            provider=selected_provider,
        )
        # Persistir em session_state ANTES do botão para sobreviver ao rerun
        st.session_state["_export_md"] = md_content
        
        st.download_button(
            label="⬇️ Exportar",
            data=st.session_state["_export_md"],
            file_name=f"conversa_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            key="btn_export_chat",
        )
```

**Atenção Streamlit:** `st.download_button` dispara rerun. Persistir `_export_md` em `session_state` **antes** de renderizar o botão — padrão já conhecido no projeto.

---

## 3. Botão Limpar Conversa

### Comportamento

Botão **"🗑️ Limpar"** na toolbar. Reseta o histórico de mensagens e estados relacionados. Pede confirmação (simples, via `st.session_state` toggle — sem `st.dialog` para evitar complexidade).

### Implementação

```python
# Toolbar
with col_clear:
    if st.session_state.get("messages"):
        if st.button("🗑️ Limpar", key="btn_clear_chat"):
            st.session_state["_confirm_clear"] = True
            st.rerun()

# Confirmação inline (aparece acima da toolbar quando ativo)
if st.session_state.get("_confirm_clear"):
    st.warning("⚠️ Limpar toda a conversa? Esta ação não pode ser desfeita.")
    col_yes, col_no, _ = st.columns([1, 1, 6])
    with col_yes:
        if st.button("✅ Confirmar", key="btn_clear_yes"):
            # Limpar todos os estados relacionados ao chat
            for key in ["messages", "_edit_idx", "_edit_draft", "_resubmit_question",
                        "_confirm_clear", "_export_md"]:
                st.session_state.pop(key, None)
            st.rerun()
    with col_no:
        if st.button("❌ Cancelar", key="btn_clear_no"):
            st.session_state.pop("_confirm_clear", None)
            st.rerun()
```

---

## Ordem de Implementação Recomendada

```
1. Botão Limpar (15 min) — menor risco, impacto imediato
       ↓
2. Exportar para Markdown (30 min) — sem dependências de CSS
       ↓
3. Chat UI elegante (2-3h) — maior esforço, testar em Streamlit Cloud
```

## Arquivos a modificar

| Arquivo | Mudança |
|---------|---------|
| `pages/Assistente.py` | Toolbar, botões, nova função `render_chat_html()`, nova função `export_chat_to_markdown()` |
| `requirements.txt` | Adicionar `markdown>=3.5` se ausente |
| `CLAUDE.md` | Atualizar seção Assistente.py com novas features |

## Riscos & Mitigações

| Risco | Mitigação |
|-------|-----------|
| `components.html` + iframe isola botões de edição existentes | Manter botões ✏️ fora do componente; ou desativar feature de edição dentro do novo layout e usar só o expander |
| Markdown lib pesada no cold start | `markdown` é leve (~200KB), sem impacto perceptível |
| CSP bloqueia JS no Streamlit Cloud | Pré-renderizar MD no Python; não carregar marked.js de CDN externo |
| `download_button` rerun apaga `_export_md` | Persistir antes do botão (padrão já aplicado no projeto) |
| Chat HTML muito alto em mobile | Usar `height=500` com `overflow-y: auto` interno |

---

*Estratégia gerada em 2026-05-13 para Process2Diagram v4.15 → v4.16*
