## Análise Comparativa dos Diagramas BPMN — Projeto Aurora

Vou analisar criticamente ambos os diagramas, destacando melhorias implementadas e apontando oportunidades adicionais de refinamento.

---

## 1. Resumo Comparativo

| Aspecto | Original | Melhorado | Avaliação |
|---|---|---|---|
| **Estrutura de Lanes** | 3 lanes (Cliente, Sistema, Tesouraria) | 2 lanes (Sistema, Gerente) | ✅ Simplificou escopo |
| **Gateways** | Nenhum | 1 exclusiveGateway (S03) | ✅ Decisão explícita |
| **Tamanho das tarefas** | CallActivity (160×90) | CallActivity + ServiceTask | ✅ Tipos corretos |
| **Descrições** | Detalhadas | Detalhadas | ✅ Ambas boas |
| **Roteamento de fluxo** | Sequencial linear | Ramificado com 3 caminhos | ✅ Correto |
| **Nomenclatura** | Verbos no infinitivo | Verbos no infinitivo | ✅ Excelente |
| **Layout** | Colunas alinhadas | Colunas alinhadas | ✅ Consistente |

---

## 2. Pontos Fortes da Versão Melhorada

### ✅ Uso Correto de `exclusiveGateway`

```xml
<exclusiveGateway id="S03" name="Avaliar Alçada">
  <documentation>Decisão automática baseada no score de crédito e valor da proposta. Três caminhos: aprovação automática (score alto e valor baixo), análise manual (score médio), recusa automática (score baixo).</documentation>
</exclusiveGateway>
```

**O que está certo:**
- 3 saídas com labels claros: "Aprovação automática", "Análise manual", "Recusa automática"
- Documentação descreve os critérios de decisão
- Gateway posicionado corretamente após a análise de risco

### ✅ Separação de Responsabilidades

```xml
<lane id="lane_sistema_aurora" name="Sistema AURORA">
  <!-- S02, S03, S04, S06 -->
</lane>
<lane id="lane_gerente_de_credito" name="Gerente de Crédito">
  <!-- S05 -->
</lane>
```

**O que está certo:**
- Sistema AURORA: automação (validação, análise, formalização)
- Gerente de Crédito: intervenção manual em casos de risco médio
- Clareza na separação de responsabilidades

### ✅ Tipos de Tarefa Corretos

```xml
<callActivity id="S04" name="Formalizar Contrato">...</callActivity>
<serviceTask id="S06" name="Gerar Carta de Recusa">...</serviceTask>
```

**O que está certo:**
- `callActivity` para subprocessos complexos
- `serviceTask` para automação simples (carta de recusa)

### ✅ Roteamento Correto

```
S03 (Gateway) → S04 (Aprovação automática)
S03 (Gateway) → S05 (Análise manual) → S04 ou S06
S03 (Gateway) → S06 (Recusa automática)
```

**O que está certo:**
- Todos os caminhos convergem para um End Event
- Labels descritivos em cada saída
- Fluxo lógico e rastreável

---

## 3. Oportunidades de Melhoria

### 🔴 CRÍTICO: Start Event e End Event com Nomes Genéricos

**Original e Melhorado:**

```xml
<startEvent id="ev_start" name="Início" />
<endEvent id="ev_end" name="Fim" />
```

**Problema:** Violação da Regra de Nomenclatura Obrigatória do skill BPMN.

**Correção sugerida:**

```xml
<startEvent id="ev_start" name="Proposta de Crédito Submetida" />
<endEvent id="ev_end" name="Contrato Formalizado e Registrado" />
<endEvent id="ev_end_recusa" name="Proposta Recusada Definitivamente" />
```

**Motivo:** O Start Event deve descrever o **gatilho real**, não "Início". O End Event deve descrever o **estado de negócio alcançado**, não "Fim".

---

### 🟡 Gateway sem End Event Distinto para Recusa

**Problema:** O caminho de recusa (S03 → S06 → ev_end) e o caminho de aprovação (S03 → S04 → ev_end) compartilham o mesmo End Event "Fim".

**Correção sugerida:**

```xml
<sequenceFlow id="sf_end_aprovacao" sourceRef="S04" targetRef="ev_end_aprovacao" />
<sequenceFlow id="sf_end_recusa" sourceRef="S06" targetRef="ev_end_recusa" />
```

**Motivo:** Cada caminho de encerramento deve ter seu próprio End Event com título único descrevendo o resultado.

---

### 🟡 Falta de Gateway de Join Explícito

**Problema:** S05 (Análise Manual) tem duas saídas:
- "Aprovado" → S04
- "Recusado" → S06

**O que está certo:** O fluxo está correto semanticamente.

**O que pode ser melhorado:** Incluir um `exclusiveGateway` de join explícito antes de S04 e S06, para deixar claro que as duas fontes (S03 e S05) convergem para o mesmo destino.

**Solução alternativa (mais simples):** Já está correto do ponto de vista do BPMN 2.0, pois S04 e S06 recebem fluxos de múltiplas fontes (S03 e S05). O que poderia ser adicionado é documentação nos fluxos:

```xml
<sequenceFlow id="sf_005" name="Aprovado (via análise manual)" sourceRef="S05" targetRef="S04" />
<sequenceFlow id="sf_002" name="Aprovado (via automação)" sourceRef="S03" targetRef="S04" />
```

---

### 🟡 Descrição de S03 Muito Longa para Gateway

**Problema:** A descrição do gateway S03 tem **4 linhas** de texto:

```xml
<documentation>Decisão automática baseada no score de crédito e valor da proposta. Três caminhos: aprovação automática (score alto e valor baixo), análise manual (score médio), recusa automática (score baixo).</documentation>
```

**Sugestão:** A documentação de gateway deve ser concisa. As regras de decisão podem ser documentadas nas próprias labels das arestas:

```xml
<sequenceFlow id="sf_002" name="Score ≥ 800 e Valor ≤ R$ 50k" sourceRef="S03" targetRef="S04" />
<sequenceFlow id="sf_003" name="Score 500-799 ou Valor > R$ 50k" sourceRef="S03" targetRef="S05" />
<sequenceFlow id="sf_004" name="Score < 500" sourceRef="S03" targetRef="S06" />
```

**Motivo:** O diagrama deve ser autossuficiente — as condições devem ser legíveis no próprio fluxo, não apenas na documentação.

---

### 🟡 S02 "Validar e Analisar Risco" — Responsabilidade Dupla

**Problema:** A atividade S02 combina duas responsabilidades distintas:
1. Validação cadastral (consultar bureaus)
2. Análise de risco (score via ML)

**Sugestão:** Dividir em duas atividades:

```xml
<callActivity id="S02a" name="Validar Cadastro">
  <documentation>Consulta simultânea a três bureaus de crédito (Boa Vista, SPC, Serasa).</documentation>
</callActivity>
<serviceTask id="S02b" name="Calcular Score de Risco">
  <documentation>Motor de Machine Learning processa score de crédito automaticamente.</documentation>
</serviceTask>
```

**Motivo:** BPMN Method & Style recomenda que cada tarefa tenha uma única responsabilidade (Single Responsibility Principle).

---

### 🟡 Ausência de CallActivity para S03 (Gateway)

**Localização:** O gateway S03 está no mesmo nível hierárquico que as CallActivities.

**Problema:** O gateway não deveria ser uma `callActivity` — já está correto como `exclusiveGateway`. O problema é que a decisão de "Avaliar Alçada" poderia ser um subprocesso de decisão próprio (com regras de negócio complexas).

**Sugestão:** Se as regras de alçada forem complexas (ex: múltiplos critérios, tabelas de limite por perfil), considerar transformar em `businessRuleTask`:

```xml
<businessRuleTask id="S03" name="Avaliar Alçada">
  <documentation>Motor de regras DMN avalia score, valor, perfil do cliente e histórico.</documentation>
</businessRuleTask>
```

**Motivo:** O BPMN 2.0 distingue entre `exclusiveGateway` (decisão simples) e `businessRuleTask` (decisão complexa com regras externas).

---

### 🟡 Ausência de Boundary Events

**Problema:** A descrição de S05 menciona "Se documentos não forem enviados em 30 dias, proposta é cancelada automaticamente", mas isso não é modelado como Boundary Event.

**Correção sugerida:**

```xml
<callActivity id="S05" name="Analisar Proposta Manualmente">
  <documentation>Gerente de Crédito analisa proposta em zona de risco médio, podendo solicitar documentação adicional ao cliente.</documentation>
  <boundaryEvent id="S05_timeout" attachedToRef="S05" cancelActivity="true">
    <timerEventDefinition>
      <timeDuration>P30D</timeDuration>
    </timerEventDefinition>
  </boundaryEvent>
</callActivity>

<sequenceFlow id="sf_timeout" sourceRef="S05_timeout" targetRef="S06" />
```

**Motivo:** O timeout é uma exceção que ocorre **durante** a análise manual, não uma decisão após ela. Boundary Events são o mecanismo correto para isso.

---

### 🟡 Ausência de Mensagens entre Pools

**Problema:** O processo atual tem apenas um pool ("Sistema AURORA" + "Gerente de Crédito"), ambos dentro da mesma organização.

**Consideração:** O cliente (que submete a proposta) poderia ser modelado como um pool separado, com message flows entre "Cliente" e "Sistema AURORA".

**Exemplo de colaboração:**

```xml
<pool id="pool_cliente" name="Cliente">
  <lane id="lane_cliente" name="Solicitante">
    <flowNodeRef>C01</flowNodeRef>
  </lane>
</pool>

<pool id="pool_sistema" name="Sistema AURORA">
  <!-- lanes atuais -->
</pool>

<messageFlow id="mf_proposta" sourceRef="C01" targetRef="S02" name="Proposta de Crédito" />
<messageFlow id="mf_resultado" sourceRef="S04" targetRef="C01" name="Contrato Assinado" />
```

**Motivo:** O cliente é uma entidade juridicamente distinta do Sistema AURORA. O uso de pools + message flows torna a colaboração explícita.

---

## 4. Comparação Direta: Original vs Melhorado

| Aspecto | Original | Melhorado | Veredito |
|---|---|---|---|
| **Escopo** | Completo (inclui desembolso) | Fase 1 (exclui desembolso) | ✅ Mais focado |
| **Lanes** | Cliente, Sistema, Tesouraria | Sistema, Gerente | ✅ Eliminou pools desnecessários |
| **Gateway** | Nenhum | ExclusiveGateway com 3 saídas | ✅ Decisão explícita |
| **Tipos de tarefa** | CallActivity (todas) | CallActivity + ServiceTask | ✅ Tipos corretos |
| **End Events** | 1 ("Fim") | 1 ("Fim") | ❌ Ambos genéricos |
| **Start Event** | "Início" | "Início" | ❌ Genérico |
| **Labels** | "aprovado", "Recusado" | "Aprovação automática", "Análise manual", "Recusa automática" | ✅ Mais descritivos |
| **Roteamento** | Linear | Ramificado | ✅ Correto |

---

## 5. Recomendações Finais (Priorizadas)

### 🔴 ALTA PRIORIDADE

1. **Renomear Start/End Events** — Usar nomes descritivos:
   - `StartEvent`: "Proposta de Crédito Submetida"
   - `EndEvent (aprovado)`: "Contrato Formalizado e Registrado"
   - `EndEvent (recusado)`: "Proposta Recusada Definitivamente"

2. **Adicionar Boundary Event para Timeout** — Modelar o timeout de 30 dias em S05

### 🟡 MÉDIA PRIORIDADE

3. **Dividir S02** — Separar validação cadastral de análise de risco

4. **Documentar condições nas labels** — Usar condições explícitas nas saídas do gateway

### 🟢 BAIXA PRIORIDADE

5. **Considerar múltiplos pools** — Cliente como pool separado com message flows

6. **Considerar businessRuleTask** — Se as regras de alçada forem complexas

7. **Adicionar documentação de auditoria** — Incluir evidências de conformidade (BACEN, LGPD)

---

## 6. Conclusão

A versão melhorada do diagrama BPMN do Projeto Aurora representa um **avanço significativo** em relação ao original:

- ✅ **Estrutura correta** de lanes e responsabilidades
- ✅ **Gateway exclusivo** com 3 caminhos de decisão
- ✅ **Tipos de tarefa apropriados** (callActivity vs serviceTask)
- ✅ **Roteamento completo** com convergência de fluxos
- ✅ **Documentação rica** das atividades

**Áreas que ainda merecem atenção:**
- 🔴 Nomenclatura de eventos (Start/End) — **requer correção imediata**
- 🔴 Boundary Event para timeout — **requer correção imediata**
- 🟡 Separação de responsabilidades em S02
- 🟡 Condições explícitas nas labels de gateway

**Nota:** Recomendo submeter o diagrama melhorado à **ferramenta de diagnóstico BPMN** do process2diagram (`bpmn_diagnostics.py`) para detectar automaticamente os problemas de lane assignment, elementos isolados e outras violações estruturais.

## Análise dos Problemas de Layout e Roteamento

Sim, ambos os problemas são **corrigíveis** e já existem mecanismos no sistema para resolvê-los. Vou analisar cada um e apontar as soluções disponíveis.

---

## 1. Labels Não Centralizados

### Problema Identificado

No XML, os labels dos shapes estão **descentralizados** ou **posicionados abaixo** das formas:

```xml
<!-- S02 (CallActivity) - label dentro da forma -->
<bpmndi:BPMNLabel><dc:Bounds x="401" y="143" width="140" height="74" /></bpmndi:BPMNLabel>

<!-- S03 (Gateway) - label abaixo da forma -->
<bpmndi:BPMNLabel><dc:Bounds x="601" y="207" width="100" height="44" /></bpmndi:BPMNLabel>
```

O label do **gateway S03** está posicionado **abaixo** do elemento (`y=207`, sendo que o gateway está em `y=155`, altura=50 → base em `205`). Isso faz com que o texto fique fora da forma.

---

### 🔧 Solução 1: `reformat_bpmn_labels()`

**Localização:** `modules/bpmn_auto_repair.py`, linhas ~450-550

O módulo já tem uma função dedicada para centralizar labels:

```python
def reformat_bpmn_labels(xml_str: str) -> tuple[str, list[str]]:
    """
    Ensure every task BPMNShape has a BPMNLabel with dc:Bounds centered inside
    the shape box, so bpmn-js renders text inside task boxes regardless of viewer.
    """
```

**Como funciona:**
1. Para cada `BPMNShape` com largura entre 100-400px (tarefas):
   - Calcula `x = shape.x + 10`, `y = shape.y + 8`
   - Calcula `width = shape.width - 20`, `height = shape.height - 16`
   - Atualiza `dc:Bounds` do label com esses valores centralizados

2. Para **eventos** (círculos pequenos):
   - Posiciona label **abaixo** do círculo, com largura maior para acomodar texto

3. Para **gateways** (losangos):
   - Posiciona label **abaixo** do losango, com largura maior

**Como ativar:**

O agente BPMN já chama esta função automaticamente:

```python
# agents/agent_bpmn.py, linha ~180
from modules.bpmn_auto_repair import reformat_bpmn_labels
_xml_fmt, _fmt_changes = reformat_bpmn_labels(hub.bpmn.bpmn_xml)
if not any(c.startswith("[ERRO]") for c in _fmt_changes):
    hub.bpmn.bpmn_xml = _xml_fmt
```

**Se não estiver funcionando:** Verifique se a função está sendo chamada e se há alterações reportadas em `_fmt_changes`.

---

### 🔧 Solução 2: `reformat_bpmn_di()` (Wrapper)

```python
def reformat_bpmn_di(xml_str: str) -> tuple[str, list[str]]:
    return reformat_bpmn_labels(xml_str)
```

Chamada via **botão manual** no módulo de diagnóstico ou na UI.

---

### 📋 Checklist de Verificação

| Item | Status no seu XML | Correção |
|---|---|---|
| S02 (CallActivity) | ✅ label dentro da forma | Já corrigido |
| S03 (Gateway) | ❌ label abaixo da forma | `reformat_bpmn_labels` corrige |
| S04 (CallActivity) | ✅ label dentro da forma | Já corrigido |
| S05 (CallActivity) | ✅ label dentro da forma | Já corrigido |
| S06 (ServiceTask) | ✅ label dentro da forma | Já corrigido |
| ev_start (StartEvent) | ❌ label abaixo do círculo | `reformat_bpmn_labels` corrige |
| ev_end (EndEvent) | ❌ label abaixo do círculo | `reformat_bpmn_labels` corrige |

---

## 2. Sequence Flows se Cruzando

### Problema Identificado

No seu diagrama, há **vários cruzamentos** de sequence flows:

1. **sf_002** (Aprovação automática): S03 → S04 — cruza com o fluxo principal?
2. **sf_003** (Análise manual): S03 → S05 — diagonal descendente
3. **sf_004** (Recusa automática): S03 → S06 — diagonal
4. **sf_005** (Aprovado): S05 → S04 — sobe para a lane superior
5. **sf_006** (Recusado): S05 → S06 — sobe para a lane superior

```
        ┌──────────────────────────────────────────────┐
        │           Sistema AURORA                     │
        │                                              │
        │  S02 → S03 → (aprovado) → S04 → ev_end      │
        │              ↘ (manual)                      │
        │              ↘ (recusa) → S06 → ev_end       │
        │                                              │
        ├──────────────────────────────────────────────┤
        │           Gerente de Crédito                 │
        │                                              │
        │              S05 ← (manual)                  │
        │              S05 → (aprovado) → S04  ←───────┼─ diagonal
        │              S05 → (recusado) → S06 ←────────┼─ diagonal
        └──────────────────────────────────────────────┘
```

**Fluxos problemáticos:**
- `sf_003` (S03 → S05): diagonal descendente que cruza a borda da lane
- `sf_005` (S05 → S04): diagonal ascendente que cruza a borda da lane
- `sf_006` (S05 → S06): diagonal ascendente que cruza a borda da lane

---

### 🔧 Solução 1: Link Events (Eliminação de Cruzamentos)

**Localização:** `modules/bpmn_generator.py`, linhas ~100-200

O gerador já tem um sistema de **Link Events** que detecta automaticamente fluxos que se cruzam e os substitui por pares de `intermediateThrowEvent` + `intermediateCatchEvent`:

```python
def _apply_link_events(bpmn, lane_assignment, shapes):
    """
    Detect crossing edges and replace each one with a Link Event pair.

    For a crossing flow  A ──────────────────────> B
    we inject:
        A ──> [throw_link_N]     (in A's lane)
              [catch_link_N] ──> B   (in B's lane)
    """
```

**Como ativar:**

O agente BPMN chama isso automaticamente no `bpmn_generator.py`:

```python
# modules/bpmn_generator.py, linha ~1040
for _iter in range(MAX_ITERATIONS):
    if not _apply_link_events(bpmn, lane_assignment, shapes):
        break   # converged — no new crossings
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
```

**Critérios de detecção:**
1. **Lane-spanning** — fluxo que pula ≥ 2 lanes intermediárias
2. **Large horizontal span** — fluxo que viaja > 395px (≈ 2 colunas)
3. **Backward cross-lane** — fluxo que retorna para uma coluna anterior cruzando lanes

---

### 🔧 Solução 2: Roteamento Inteligente (`_route_waypoints`)

**Localização:** `modules/bpmn_generator.py`, linhas ~750-850

O roteador tem **7 estratégias** para evitar cruzamentos:

| Estratégia | Quando usar | Resultado |
|---|---|---|
| Vertical down | Elementos na mesma coluna, source acima | Linha reta vertical |
| Vertical up | Elementos na mesma coluna, source abaixo | Linha reta vertical |
| U-path backward | Fluxo para trás na mesma lane | Desvia pela margem inferior |
| U-path cross-lane | Fluxo para trás cruzando lanes | Desvia abaixo de ambos |
| L-shape | Cross-lane curto (adjacente) | Horizontal + vertical |
| Boundary detour | Cross-lane longo (span ≥ 2) | Rota pela borda da lane |
| Top-of-lane detour | Same-lane skip longo | Rota pelo topo da lane |

**Exemplo de roteamento cross-lane longo (seu caso):**

```python
# Forward cross-lane com salto longo
if (tx - (sx + sw)) > min_skip_px and src_lid in lane_bounds:
    src_top, src_bottom = lane_bounds[src_lid]
    if src_top > tgt_top:          # source is the lower lane
        boundary_y = src_top + 10   # vai para o topo da lane source
    else:                          # source is the upper lane
        boundary_y = src_bottom - 10  # vai para a base da lane source
    
    return [
        (_ex, _ey),                # sai da source
        (sx + sw, boundary_y),    # dobra na boundary
        (tx, boundary_y),          # cruza horizontal na boundary
        (tx, ty + th / 2),         # entra no target
    ]
```

**O que isso faz:**
- Em vez de uma diagonal direta (S03 → S05), a rota é:
  1. Sai de S03 pela direita
  2. Sobe/desce até a borda da lane (topo ou base)
  3. Cruza horizontalmente pela borda (sem elementos)
  4. Entra em S05 pela esquerda

---

### 🔧 Solução 3: Stagger Overlapping Flows (`reformat_bpmn_labels`)

**Localização:** `modules/bpmn_auto_repair.py`, linhas ~530-560

A função `reformat_bpmn_labels` também escalona fluxos que compartilham o mesmo canal:

```python
# ── Pass C: Stagger overlapping same-channel skip flows ──────────────
# Flows with 4 waypoints where wp[1].y ≈ wp[2].y (horizontal detour
# near the top/bottom of a lane) may overlap when multiple flows share
# the same y-channel.  Sort by span length (shorter stays, longer gets
# offset +15 px each) so the skip routes are visually distinct.
```

**Como funciona:**
1. Detecta fluxos com 4 waypoints que compartilham o mesmo `y`
2. Ordena por comprimento (span)
3. Aplica offset de 30px entre cada fluxo adjacente

---

## 3. Recomendações Práticas para seu Diagrama

### 🔴 Imediato: Executar o Diagnóstico

No Streamlit, execute o **Diagnóstico BPMN** (botão no Tab BPMN). Ele vai reportar:

```python
from modules.bpmn_diagnostics import render_bpmn_diagnostics
render_bpmn_diagnostics(hub.bpmn)
```

O relatório mostrará:
- Quantos fluxos serão substituídos por Link Events
- Quais elementos têm lane suspeita
- Resumo dos cruzamentos detectados

### 🔴 Imediato: Executar `reformat_bpmn_labels`

Se o diagnóstico não estiver sendo executado automaticamente, chame manualmente:

```python
from modules.bpmn_auto_repair import reformat_bpmn_labels
xml_fixed, changes = reformat_bpmn_labels(hub.bpmn.bpmn_xml)
print(changes)  # Ver o que foi corrigido
hub.bpmn.bpmn_xml = xml_fixed
```

### 🟡 Melhorias Manuais no Layout

Se os mecanismos automáticos não resolverem todos os cruzamentos, considere:

1. **Reorganizar colunas**:
   - S02 → coluna 1
   - S03 → coluna 2 (gateway)
   - S04 → coluna 3 (aprovação)
   - S06 → coluna 3 (recusa) — **alinhado verticalmente com S04**
   - S05 → coluna 3 (análise manual) — **na lane inferior**

2. **Ajustar posicionamento**:
   ```
   Coluna 1    Coluna 2    Coluna 3    Coluna 4
   ───────────────────────────────────────────────
   S02   →    S03   →    S04   →    ev_end
   (Sistema)   (Sistema)   (Sistema)
   
                  ↘
                  S05   →    S06   →    ev_end
   (Gerente)   (Gerente)   (Sistema)
   ```

3. **Usar múltiplos End Events**:
   - S04 → ev_end_aprovacao (na lane Sistema)
   - S06 → ev_end_recusa (na lane Sistema)

---

## 4. Resumo das Ações

| Problema | Solução Automática | Ação Manual |
|---|---|---|
| Labels descentralizados | `reformat_bpmn_labels()` | Verificar se chamada no agente |
| Labels de gateway abaixo | `reformat_bpmn_labels()` | Aplica correção |
| Cruzamento S03→S05 | `_apply_link_events()` | Substitui por Link Events |
| Cruzamento S05→S04 | `_apply_link_events()` | Substitui por Link Events |
| Cruzamento S05→S06 | `_apply_link_events()` | Substitui por Link Events |
| Labels de fluxo sobrepostos | `reformat_bpmn_labels()` Pass C | Escalona automaticamente |
| Roteamento diagonal | `_route_waypoints()` | Usa boundary detour |

---

## 5. Verificação Final

Após aplicar as correções, o diagrama deve ter:

- ✅ Labels centralizados dentro das formas (tarefas)
- ✅ Labels abaixo dos círculos (eventos)
- ✅ Labels abaixo dos losangos (gateways)
- ✅ Fluxos roteados por bordas de lane (sem diagonais)
- ✅ Fluxos substituídos por Link Events (quando necessário)
- ✅ Sem sobreposição de labels de fluxo

**Para validar:** Use o **Diagnóstico BPMN** antes e depois das correções para ver a redução nos cruzamentos detectados.