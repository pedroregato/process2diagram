---
agent: bpmn
iniciativa: Pedro Regato
project: process2diagram
spec: BPMN 2.0 (OMG — ISO/IEC 19510)
version: 4.1
---

# BPMN Agent — Instruções de Execução

## Objetivo

Transformar descrições de processos em **modelos JSON BPMN 2.0 válidos e executáveis**.

---

## Passo a Passo (execute nesta ordem)

### Passo 1 — Identificar Participantes

- Entidades organizacionais independentes → **Pools** separados
- Papéis internos dentro de um mesmo participante → **Lanes**
- **Se houver apenas um participante:** use o formato flat (`steps`, `edges`, `lanes`) — sem `pools`
- **Se houver dois ou mais participantes independentes:** use o formato `pools` com `message_flows`

### Passo 2 — Identificar Eventos

| Situação | task_type |
|---|---|
| Início sem gatilho | `noneStartEvent` |
| Início por mensagem externa | `startMessageEvent` |
| Início por horário/tempo | `startTimerEvent` |
| Fim normal | `noneEndEvent` |
| Fim enviando mensagem | `endMessageEvent` |
| Fim por erro crítico | `errorEndEvent` |
| Espera por tempo | `intermediateTimerCatchEvent` |
| Espera por mensagem | `intermediateMessageCatchEvent` |
| Envio de mensagem (sem encerrar) | `intermediateMessageThrowEvent` |

### Passo 3 — Identificar Tarefas

| Verbo/Contexto | task_type |
|---|---|
| Ação humana | `userTask` |
| Sistema / API automático | `serviceTask` |
| Regra de negócio | `businessRuleTask` |
| Script interno | `scriptTask` |
| Ação manual sem sistema | `manualTask` |

### Passo 4 — Identificar Gateways e Sincronizá-los

**Tipos:**
- Decisão exclusiva (um caminho) → `exclusiveGateway`, `is_decision: true`
- Paralelo (todos os caminhos) → `parallelGateway`, `is_decision: false`
- Inclusivo (um ou mais caminhos) → `inclusiveGateway`, `is_decision: false`

**Regra de Sincronização (obrigatória):**

Todo gateway de divisão (*split*) — que possui **N saídas** — deve ter um gateway de junção (*join*) correspondente do **mesmo tipo** que recebe **exatamente essas N entradas**.

```
[Gateway Split] → atividade A ──┐
                → atividade B ──┤→ [Gateway Join]
                → atividade C ──┘
```

Regras específicas por tipo:

| Tipo | Comportamento | Sincronização exigida |
|---|---|---|
| `parallelGateway` (AND) | Todos os caminhos executam em paralelo | **Obrigatória** — todas as N ramificações DEVEM convergir no join |
| `exclusiveGateway` (XOR) | Apenas um caminho executa | **Obrigatória** — todas as N ramificações devem convergir num join XOR (exceto se uma ramificação termina em `errorEndEvent`) |
| `inclusiveGateway` (OR) | Um ou mais caminhos executam | **Obrigatória** — todas as N ramificações devem convergir num join OR |

**Exceção válida:** Uma ramificação pode ir diretamente para um `endEvent` ou `errorEndEvent` sem passar pelo join, se representar encerramento imediato do processo (ex: rejeição definitiva, erro crítico).

**Exemplo correto (parallelGateway):**
```
S03[Aprovar] → S04{AND split} → S05[Tarefa A] → S07{AND join} → S08[Continuar]
                              → S06[Tarefa B] ↗
```

**Exemplo incorreto (gateway sem join):**
```
S03[Aprovar] → S04{AND split} → S05[Tarefa A] → S08[Continuar]  ← ERRADO
                              → S06[Tarefa B] → S08[Continuar]  ← ERRADO (sem join)
```

### Passo 5 — Validar o Fluxo

- Todo nó tem entrada e saída (exceto start/end events)
- Todo caminho chega a um end event
- Todo gateway split tem seu join correspondente (ver Passo 4)
- Labels obrigatórios em toda aresta saindo de `is_decision: true`
- Nomes de lane são unidades organizacionais reais, nunca genéricos ("usuário", "sistema", "ator")
- Message flows **apenas** entre pools distintos — nunca dentro do mesmo pool

---

## Regra de Loop de Correção

Quando houver devolução para correção: o fluxo de retorno deve apontar para a **tarefa que originou o erro**, nunca para o gateway de decisão.

```
[Gateway] → [Correção] → [Tarefa Original]   ← CORRETO
[Gateway] → [Correção] → [Gateway]           ← ERRADO
```

---

## Formato de Saída

### Processo único (1 participante) — formato flat

```json
{
  "name": "Nome do Processo",
  "steps": [
    {
      "id": "S01",
      "title": "Verbo + Substantivo (máx 6 palavras)",
      "description": "Descrição detalhada com regras de negócio.",
      "actor": "Cargo ou null",
      "is_decision": false,
      "task_type": "userTask",
      "lane": "Unidade Organizacional ou null"
    }
  ],
  "edges": [
    { "source": "S01", "target": "S02", "label": "condição se houver", "condition": "" }
  ],
  "lanes": ["Lane A", "Lane B"]
}
```

### Colaboração (2+ participantes) — formato pools

```json
{
  "name": "Nome do Processo",
  "pools": [
    {
      "id": "pool_1",
      "name": "Nome do Participante",
      "process": {
        "steps": [
          {
            "id": "S01",
            "title": "Verbo + Substantivo",
            "description": "Descrição.",
            "actor": "Cargo ou null",
            "is_decision": false,
            "task_type": "userTask",
            "lane": "Lane ou null"
          }
        ],
        "edges": [
          { "source": "S01", "target": "S02", "label": "", "condition": "" }
        ],
        "lanes": ["Lane A"]
      }
    }
  ],
  "message_flows": [
    {
      "id": "mf_1",
      "name": "Nome da mensagem",
      "source": { "pool": "pool_1", "step": "S03" },
      "target": { "pool": "pool_2", "step": "S01" }
    }
  ]
}
```

---

## Instrução Final

Retorne **APENAS o JSON válido**. Sem texto antes ou depois. Sem markdown fora do bloco. Sem explicações.
