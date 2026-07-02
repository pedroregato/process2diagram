# PC112 — Plano de Correção: Tela Branca após "Reexecutar Agente BPMN"

**Data:** 2026-06-30
**Status:** PC112-I (implementação neste documento)
**Tentativas anteriores:** A, B, C, D, E, F, G, H

---

## 1. Sintoma

Ao clicar "Reexecutar Agente BPMN" em uma reunião carregada do banco (Modo B):

1. O `st.status()` aparece com "RUNNING"
2. O RUNNING termina ✓ (fast path PC112-H funciona)
3. A tela muda para a aba de transcrição
4. Aparece CONNECTING
5. Tela branca

Console do browser:
```
WebSocket onclose   ← primeiro fechamento (mid-render)
WebSocket onclose   ← segundo fechamento (após reconexão)
Error: Bad 'setIn' index 1 (should be between [0, 0])
```

---

## 2. Diagnóstico Definitivo

### O que NÃO é a causa (análise DeepSeek incorreta)

A substituição Python `hub.bpmn = new_object` **não causa o setIn**. O protocolo delta do Streamlit opera sobre a árvore de componentes React no browser — a identidade de objetos Python é invisível ao cliente. Substituir um objeto Python não muda a árvore de widgets.

### O que É a causa

```
Timeline de uma script run PC112-G (sem st.rerun()):

[0ms]   Script começa
[50ms]  st.status() renderiza (RUNNING)
[800ms] fast path (PC112-H) conclui → hub atualizado
[850ms] status.update(state="complete")
[900ms] Hub section começa a renderizar...
        → render_input_area()
        → st.tabs(["📝 Transcrição", "📐 BPMN", "📊 Mermaid", "📄 Ata", ...])
        → render_quality(), render_bpmn(), render_mermaid()...
        → render_minutes() ← centenas de markdowns → centenas de LaTeX warnings
        → render_requirements()...
[3500ms] WS FECHA (mid-render, muitos deltas)
         ↓
         Cliente tem árvore PARCIAL (hub renderizado até o ponto do crash)
         ↓
[3600ms] Cliente reconecta → worker novo / sessão perdida
         → Servidor renderiza árvore MÍNIMA (ou vazia)
         → Deltas aplicados contra árvore parcial do cliente
         → setIn(1, [0, 0])
```

**Root cause**: A script run que executa o handler TAMBÉM renderiza o hub inteiro (todos os tabs, BPMN viewer, markdown das atas/requisitos). Isso gera CENTENAS de deltas. O WS fecha durante esse render. Após reconexão, o servidor tem uma árvore menor que o cliente espera → setIn.

### Por que PC112-G falhou (tentou remover st.rerun())

A ideia era: "handler + hub na mesma script run → sem segundo render". Mas a própria script run é longa demais porque o hub tem muito conteúdo.

### Por que PC112-F falhou (tinha st.rerun())

PC112-F tinha `st.rerun()` mas o handler ainda podia chamar o LLM (caminho lento, minutos). O WS caia DURANTE o handler (não após). Com sessão perdida, `st.rerun()` não resolvia.

### Por que PC112-I funciona

PC112-H garantiu que o handler completa em <1s (fast path). Agora o WS **não cai durante o handler**. Ao adicionar `st.rerun()` após o handler:

```
[0ms]   Script run 1 inicia
[50ms]  st.status() renderiza
[800ms] fast path conclui → hub stored → messages stored → st.rerun()
        ← Script run 1 termina. MUITO CURTA. WS estável.

[820ms] Script run 2 inicia (Streamlit rerun controlado)
        → Hub section renderiza normalmente
        → Árvore sincronizada pelo Streamlit (não pelo WS-close/reconnect)
        → Nenhum setIn possível
```

A diferença chave: `st.rerun()` instrui o Streamlit a reiniciar o script de forma CONTROLADA, sincronizando a árvore cliente-servidor. Um `WS close/reconnect` é DESCONTROLADO e não sincroniza.

---

## 3. Solução: PC112-I

### Mudança em `pages/Pipeline.py`

No bloco do handler (após `st.session_state.hub = _result_hub`):

1. Salvar mensagens em `st.session_state["_rr_pending_messages"]` (já consumido no início da próxima run)
2. Chamar `st.rerun()` **antes de renderizar o hub section**

```python
# ANTES (PC112-G):
st.session_state.hub = _result_hub
_rr_status.update(label="✅ ...", state="complete", expanded=False)
st.toast(...)
for _lv, _mg in (_messages or []):
    st.toast(...)
# ← sem st.rerun()

# DEPOIS (PC112-I):
st.session_state.hub = _result_hub
st.session_state["_rr_pending_messages"] = list(_messages or [])
_rr_status.update(label="✅ ... Recarregando…", state="complete", expanded=False)
st.rerun()  # ← hub renderiza em script run separada, limpa
```

### O que NÃO muda

- `core/rerun_handlers.py` — PC112-H mantido (fast path)
- `agents/agent_bpmn.py` — sem mudanças (substituição Python não é a causa)
- `core/pipeline.py` — sem mudanças
- `core/knowledge_hub.py` — sem mudanças

---

## 4. Implementação

Ver commit PC112-I em `pages/Pipeline.py`.

---

## 5. Verificação Esperada

Após PC112-I, ao clicar "Reexecutar Agente BPMN":
1. `st.status()` aparece → fast path roda → status vira "complete" brevemente
2. Streamlit faz rerun CONTROLADO (não WS-close)
3. Hub renderiza normalmente, mesma estrutura do load inicial
4. Nenhum setIn — a árvore está sincronizada
5. Toast "✅ BPMN re-executado com sucesso" aparece na próxima run

---

## 6. Histórico de Tentativas

| Versão | Abordagem | Resultado | Causa da Falha |
|--------|-----------|-----------|----------------|
| PC112-A | Thread em background + polling | Falhou | race condition na árvore |
| PC112-B | Flags virtuais de estado | Falhou | mesma causa |
| PC112-C | JS reload iframe | Falhou | HTTP 405 Streamlit Cloud |
| PC112-D | JS error listener | Falhou | timing: setIn antes do listener |
| PC112-E | Simplificação polling | Falhou | Mudou a árvore para sessões ativas |
| PC112-F | `st.spinner()` + `st.rerun()` | Falhou | WS caía DURANTE handler lento (LLM) |
| PC112-G | `st.status()` sem `st.rerun()` | Falhou | WS caía DURANTE render do hub |
| PC112-H | Fast path steps sem LLM | Parcial | Handler OK mas hub render ainda causa WS drop |
| **PC112-I** | Fast path + `st.rerun()` | **Esperado: OK** | Combina os dois fixes corretos |
