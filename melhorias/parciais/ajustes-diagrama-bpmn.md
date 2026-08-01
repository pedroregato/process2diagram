# Proposta DEEPSEEK:

Analisando seu diagrama BPMN, identifiquei os problemas principais e proponho três ferramentas/soluções específicas:

## 1. Centralização e Contenção de Labels

**Problema identificado:**
- Labels das atividades estão posicionados abaixo dos shapes (ex: `p1_S01_di` com label em `y=132` enquanto shape está em `y=92`)
- Labels não estão centralizados verticalmente

**Solução proposta:**

```javascript
function centralizeLabels(bpmnDiagram) {
    // Para cada shape com label
    bpmnDiagram.shapes.forEach(shape => {
        if (shape.label) {
            const shapeBounds = shape.bounds;
            const labelBounds = shape.label.bounds;
            
            // Centralizar horizontalmente
            const centerX = shapeBounds.x + (shapeBounds.width / 2) - (labelBounds.width / 2);
            
            // Centralizar verticalmente dentro do shape
            const centerY = shapeBounds.y + (shapeBounds.height / 2) - (labelBounds.height / 2);
            
            // Garantir que o label não ultrapasse as bordas
            labelBounds.x = Math.max(shapeBounds.x + 5, centerX);
            labelBounds.y = Math.max(shapeBounds.y + 5, centerY);
            
            // Ajustar se o label for maior que o shape
            if (labelBounds.width > shapeBounds.width - 10) {
                labelBounds.width = shapeBounds.width - 10;
                // Recalcular posição
                labelBounds.x = shapeBounds.x + 5;
            }
        }
    });
    return bpmnDiagram;
}
```

## 2. Evitar Cruzamento de Sequence Flows

**Problema identificado:**
- Vários cruzamentos visíveis, especialmente:
  - `p2_sf_004`, `p2_sf_005`, `p2_sf_006` saindo do gateway com rotas conflitantes
  - `mf_1` cruzando com `p2_sf_001` e `p2_sf_002`

**Solução proposta - Algoritmo de Roteamento com Ortogonalidade:**

```javascript
function routeSequenceFlowsWithoutCrossing(elements, flows) {
    // 1. Identificar todos os pontos de conexão
    const connectionPoints = {};
    flows.forEach(flow => {
        const source = elements.find(e => e.id === flow.sourceRef);
        const target = elements.find(e => e.id === flow.targetRef);
        
        // Calcular pontos de saída/entrada baseado na posição relativa
        connectionPoints[flow.id] = {
            source: calculateConnectionPoint(source, target),
            target: calculateConnectionPoint(target, source)
        };
    });
    
    // 2. Agrupar flows por gateway de origem
    const flowsByGateway = {};
    flows.forEach(flow => {
        if (isGateway(flow.sourceRef)) {
            if (!flowsByGateway[flow.sourceRef]) {
                flowsByGateway[flow.sourceRef] = [];
            }
            flowsByGateway[flow.sourceRef].push(flow);
        }
    });
    
    // 3. Distribuir saídas dos gateways uniformemente
    Object.keys(flowsByGateway).forEach(gatewayId => {
        const gatewayFlows = flowsByGateway[gatewayId];
        const gateway = elements.find(e => e.id === gatewayId);
        
        // Calcular ângulos de saída distribuídos uniformemente
        const angles = distributeAngles(gatewayFlows.length);
        
        gatewayFlows.forEach((flow, index) => {
            // Ajustar ponto de saída baseado no ângulo
            const angle = angles[index];
            const radius = 30; // Distância do centro do gateway
            connectionPoints[flow.id].source = {
                x: gateway.bounds.x + gateway.bounds.width/2 + radius * Math.cos(angle),
                y: gateway.bounds.y + gateway.bounds.height/2 + radius * Math.sin(angle)
            };
        });
    });
    
    // 4. Gerar rotas ortogonais (apenas vertical/horizontal)
    flows.forEach(flow => {
        const sourcePoint = connectionPoints[flow.id].source;
        const targetPoint = connectionPoints[flow.id].target;
        
        // Criar caminho ortogonal com 1-2 pontos intermediários
        flow.waypoints = generateOrthogonalPath(sourcePoint, targetPoint);
    });
    
    return flows;
}

function distributeAngles(count) {
    const angles = [];
    const totalAngle = Math.PI * 1.5; // 270 graus para saídas (evitar entrada)
    const startAngle = -Math.PI/4; // Começar em -45 graus
    
    for (let i = 0; i < count; i++) {
        angles.push(startAngle + (i / (count - 1)) * totalAngle);
    }
    return angles;
}
```

## 3. Distribuição Melhorada de Saídas de Gateways

**Problema identificado:**
- Gateway `p2_S04` tem 3 saídas (`p2_sf_004`, `p2_sf_005`, `p2_sf_006`) todas saindo pelo mesmo ponto
- Labels das condições estão sobrepostas (todas em `y=580`)

**Solução completa:**

```javascript
function optimizeGatewayOutputs(gateway, outgoingFlows, elements) {
    // 1. Ordenar flows por label para distribuição lógica
    const sortedFlows = outgoingFlows.sort((a, b) => {
        // Ordenar numericamente se possível
        const aVal = parseFloat(a.name) || 0;
        const bVal = parseFloat(b.name) || 0;
        return aVal - bVal;
    });
    
    // 2. Distribuir pontos de saída
    const gatewayCenterX = gateway.bounds.x + gateway.bounds.width/2;
    const gatewayCenterY = gateway.bounds.y + gateway.bounds.height/2;
    
    // Usar "leque" de saídas na parte inferior do gateway
    const spreadAngle = Math.PI / 2; // 90 graus de abertura
    const startAngle = -Math.PI/2 - spreadAngle/2; // Começar na diagonal inferior-esquerda
    
    sortedFlows.forEach((flow, index) => {
        const ratio = (index + 1) / (sortedFlows.length + 1);
        const angle = startAngle + (ratio * spreadAngle);
        
        // Ponto de saída na borda do gateway
        const radius = 30; // Raio do gateway + margem
        const exitPoint = {
            x: gatewayCenterX + radius * Math.cos(angle),
            y: gatewayCenterY + radius * Math.sin(angle)
        };
        
        // Encontrar o target
        const target = elements.find(e => e.id === flow.targetRef);
        if (target) {
            // Calcular rota otimizada
            const targetCenterX = target.bounds.x + target.bounds.width/2;
            const targetCenterY = target.bounds.y + target.bounds.height/2;
            
            // Criar waypoints ortogonais
            const waypoints = [];
            
            // Primeiro waypoint: saída do gateway
            waypoints.push(exitPoint);
            
            // Segundo waypoint: ponto intermediário para evitar cruzamentos
            const midX = (exitPoint.x + targetCenterX) / 2;
            const midY = (exitPoint.y + targetCenterY) / 2;
            
            // Decidir se vai primeiro horizontal ou vertical
            const dx = Math.abs(targetCenterX - exitPoint.x);
            const dy = Math.abs(targetCenterY - exitPoint.y);
            
            if (dx > dy) {
                // Ir horizontal primeiro, depois vertical
                waypoints.push({ x: targetCenterX, y: exitPoint.y });
                waypoints.push({ x: targetCenterX, y: targetCenterY });
            } else {
                // Ir vertical primeiro, depois horizontal
                waypoints.push({ x: exitPoint.x, y: targetCenterY });
                waypoints.push({ x: targetCenterX, y: targetCenterY });
            }
            
            // Atualizar waypoints do flow
            flow.waypoints = waypoints;
            
            // Ajustar posição do label para não sobrepor
            if (flow.label) {
                // Posicionar label no primeiro segmento, mas deslocado
                const midPoint = {
                    x: (exitPoint.x + waypoints[1].x) / 2,
                    y: (exitPoint.y + waypoints[1].y) / 2
                };
                // Deslocar perpendicularmente
                const offset = 20;
                const perpX = -(waypoints[1].y - exitPoint.y) / dy || offset;
                const perpY = (waypoints[1].x - exitPoint.x) / dx || offset;
                
                flow.label.bounds.x = midPoint.x + perpX * offset;
                flow.label.bounds.y = midPoint.y + perpY * offset;
            }
        }
    });
    
    return outgoingFlows;
}
```

## Implementação Integrada

```javascript
function optimizeBPMNDiagram(bpmnXML) {
    // Parse do XML
    const diagram = parseBPMN(bpmnXML);
    
    // 1. Centralizar labels
    centralizeLabels(diagram);
    
    // 2. Otimizar rotas dos gateways
    const gateways = diagram.elements.filter(e => e.type === 'exclusiveGateway');
    gateways.forEach(gateway => {
        const outgoingFlows = diagram.flows.filter(f => f.sourceRef === gateway.id);
        optimizeGatewayOutputs(gateway, outgoingFlows, diagram.elements);
    });
    
    // 3. Evitar cruzamentos entre todos os flows
    const allFlows = diagram.flows;
    while (hasCrossings(allFlows)) {
        // Iterativamente resolver cruzamentos
        resolveCrossings(allFlows, diagram.elements);
    }
    
    // 4. Gerar novo XML
    return generateBPMN(diagram);
}
```

## Recomendações Adicionais

1. **Para labels muito longos**: Implementar wrap automático com quebra de linha a cada 20 caracteres.

2. **Para pools e lanes**: Ajustar automaticamente as alturas baseado no conteúdo.

3. **Para message flows**: Dar prioridade para que não cruzem com sequence flows, posicionando-os nas bordas.

4. **Layout hierárquico**: Considere usar um algoritmo de layout hierárquico (Sugiyama) para organizar os elementos verticalmente por ordem de execução.

Essas soluções devem melhorar significativamente a legibilidade do seu diagrama, eliminando cruzamentos e centralizando os textos adequadamente.

# Proposta CHATGPT:

Sim, Pedroka. Para o seu pipeline BPMN, eu proporia **3 tools pós-geração**, executadas depois que o XML BPMN já foi criado, mas antes da entrega/renderização final. Elas atuariam diretamente sobre o bloco `bpmndi:BPMNDiagram`, ajustando `BPMNShape`, `BPMNEdge`, `BPMNLabel` e `di:waypoint`. A necessidade fica clara no exemplo enviado, especialmente nos labels vazios ou externos aos shapes, nos fluxos saindo do gateway `p2_S04` pelo mesmo ponto e em rotas sobrepostas como `p2_sf_004`, `p2_sf_005` e `p2_sf_006`. 

## 1) Tool: `normalize_bpmn_labels`

**Objetivo:** centralizar e conter os labels das atividades dentro dos próprios shapes.

### Problema observado

No XML, várias atividades têm:

```xml
<bpmndi:BPMNLabel />
```

Isso deixa o comportamento de renderização dependente do visualizador BPMN. Em alguns viewers, o texto pode aparecer desalinhado, fora do shape ou com quebra ruim.

### Proposta

Criar uma tool que percorre todos os `BPMNShape` associados a:

```text
task
userTask
serviceTask
sendTask
receiveTask
manualTask
businessRuleTask
scriptTask
callActivity
subProcess
```

E injeta um `BPMNLabel` interno com bounds calculado a partir do próprio shape.

### Regra prática

Para uma atividade com:

```xml
<dc:Bounds x="381.0" y="385.0" width="160" height="90" />
```

A label poderia ficar assim:

```xml
<bpmndi:BPMNLabel>
  <dc:Bounds x="391.0" y="395.0" width="140" height="70" />
</bpmndi:BPMNLabel>
```

Ou seja:

```python
label_x = shape_x + padding_x
label_y = shape_y + padding_y
label_width = shape_width - 2 * padding_x
label_height = shape_height - 2 * padding_y
```

### Interface sugerida

```python
@dataclass
class LabelNormalizerConfig:
    padding_x: float = 10
    padding_y: float = 8
    min_label_width: float = 80
    min_label_height: float = 30
    apply_to_events: bool = False
    apply_to_gateways: bool = False
```

```python
class BpmnLabelNormalizerTool:
    def run(self, bpmn_xml: str, config: LabelNormalizerConfig) -> str:
        ...
```

### Resultado esperado

Antes:

```xml
<bpmndi:BPMNShape id="p2_S03_di" bpmnElement="p2_S03">
  <dc:Bounds x="601.0" y="385.0" width="160" height="90" />
  <bpmndi:BPMNLabel />
</bpmndi:BPMNShape>
```

Depois:

```xml
<bpmndi:BPMNShape id="p2_S03_di" bpmnElement="p2_S03">
  <dc:Bounds x="601.0" y="385.0" width="160" height="90" />
  <bpmndi:BPMNLabel>
    <dc:Bounds x="611.0" y="393.0" width="140" height="74" />
  </bpmndi:BPMNLabel>
</bpmndi:BPMNShape>
```

Essa tool não precisa fazer quebra de linha real no XML, porque a maioria dos renderizadores BPMN quebra o texto automaticamente com base nos bounds. Mas, se o seu renderizador for próprio, a tool também pode gerar metadados auxiliares com `wrappedText`.

---

## 2) Tool: `reduce_sequence_flow_crossings`

**Objetivo:** reduzir cruzamentos e sobreposições de `sequenceFlow`.

### Problema observado

No exemplo, os fluxos que saem do gateway `p2_S04` usam rotas parecidas ou sobrepostas:

```xml
p2_sf_004: gateway -> recusar proposta
p2_sf_005: gateway -> revisão manual
p2_sf_006: gateway -> formalizar e sincronizar
```

Há uso repetido de pontos como:

```xml
<di:waypoint x="876" y="430" />
<di:waypoint x="876" y="580" />
<di:waypoint x="1166" y="580" />
```

Isso cria um efeito visual de “trilho compartilhado” e pode gerar cruzamentos ou ambiguidade visual.

### Proposta

Criar uma tool de roteamento ortogonal para recalcular os `di:waypoint` de cada `BPMNEdge`.

Ela deve:

1. Ler todos os shapes e seus bounds.
2. Construir uma grade lógica de ocupação.
3. Marcar shapes como obstáculos.
4. Roteirizar cada fluxo com segmentos horizontais/verticais.
5. Aplicar pequenas separações quando múltiplos fluxos compartilham o mesmo corredor.
6. Reposicionar o `BPMNLabel` do fluxo no segmento mais longo.

### Interface sugerida

```python
@dataclass
class FlowRouterConfig:
    grid_size: float = 20
    obstacle_margin: float = 20
    lane_margin: float = 16
    min_segment_length: float = 30
    prefer_left_to_right: bool = True
    separate_parallel_edges: bool = True
    parallel_edge_gap: float = 14
```

```python
class BpmnSequenceFlowRouterTool:
    def run(self, bpmn_xml: str, config: FlowRouterConfig) -> str:
        ...
```

### Estratégia de roteamento

Para um fluxo entre dois shapes:

```text
source shape -> target shape
```

A tool calcula os pontos de ancoragem:

```python
source_anchor = right_center(source_shape)
target_anchor = left_center(target_shape)
```

Depois escolhe uma rota ortogonal:

```text
source_anchor
→ horizontal até um corredor livre
→ vertical até alinhar com o destino
→ horizontal até target_anchor
```

### Exemplo conceitual

Para o fluxo `p2_sf_004`, em vez de sair do gateway e compartilhar a mesma vertical com outros fluxos, a rota poderia usar um corredor específico:

```xml
<bpmndi:BPMNEdge id="p2_sf_004_di" bpmnElement="p2_sf_004">
  <di:waypoint x="876" y="430" />
  <di:waypoint x="930" y="430" />
  <di:waypoint x="930" y="500" />
  <di:waypoint x="1161" y="500" />
</bpmndi:BPMNEdge>
```

Para `p2_sf_006`, outro corredor:

```xml
<bpmndi:BPMNEdge id="p2_sf_006_di" bpmnElement="p2_sf_006">
  <di:waypoint x="876" y="430" />
  <di:waypoint x="930" y="430" />
  <di:waypoint x="930" y="380" />
  <di:waypoint x="1161" y="380" />
</bpmndi:BPMNEdge>
```

E para `p2_sf_005`:

```xml
<bpmndi:BPMNEdge id="p2_sf_005_di" bpmnElement="p2_sf_005">
  <di:waypoint x="851" y="455" />
  <di:waypoint x="851" y="700" />
  <di:waypoint x="941" y="700" />
</bpmndi:BPMNEdge>
```

Isso já melhora a leitura porque cada saída do gateway ganha uma rota visualmente distinta.

---

## 3) Tool: `distribute_gateway_outgoing_flows`

**Objetivo:** distribuir melhor as saídas de gateways, evitando que todos os fluxos saiam do mesmo ponto.

### Problema observado

No seu exemplo, o gateway `p2_S04` tem três saídas:

```xml
<sequenceFlow id="p2_sf_004" name="&lt; 500" sourceRef="p2_S04" targetRef="p2_S05" />
<sequenceFlow id="p2_sf_005" name="500 - 699" sourceRef="p2_S04" targetRef="p2_S06" />
<sequenceFlow id="p2_sf_006" name="≥ 700" sourceRef="p2_S04" targetRef="p2_S07" />
```

Mas no DI, todas praticamente partem de:

```xml
<di:waypoint x="876" y="430" />
```

Ou seja, todas usam o mesmo ponto de saída à direita do gateway.

### Proposta

Criar uma tool especializada em gateways que:

1. Detecta gateways com mais de uma saída.
2. Classifica os destinos por posição relativa: acima, centro, abaixo, esquerda, direita.
3. Distribui os pontos de saída do gateway por lados diferentes.
4. Recalcula os primeiros waypoints dos fluxos.
5. Reposiciona os labels das condições.

### Interface sugerida

```python
@dataclass
class GatewayFlowDistributionConfig:
    gateway_padding: float = 0
    outgoing_gap: float = 8
    prefer_cardinal_ports: bool = True
    sort_by_target_position: bool = True
    label_offset: float = 12
```

```python
class BpmnGatewayFlowDistributorTool:
    def run(self, bpmn_xml: str, config: GatewayFlowDistributionConfig) -> str:
        ...
```

### Regra recomendada

Para gateway com 3 saídas:

```text
destino acima    -> porta superior ou direita-superior
destino central  -> porta direita
destino abaixo   -> porta inferior ou direita-inferior
```

No seu caso:

| Fluxo       |    Condição | Destino                    | Porta sugerida        |
| ----------- | ----------: | -------------------------- | --------------------- |
| `p2_sf_006` |     `≥ 700` | `p2_S07`, acima            | topo/direita superior |
| `p2_sf_004` |     `< 500` | `p2_S05`, levemente abaixo | direita inferior      |
| `p2_sf_005` | `500 - 699` | `p2_S06`, abaixo           | baixo                 |

Para o gateway:

```xml
<dc:Bounds x="826" y="405" width="50" height="50" />
```

Os pontos úteis seriam:

```python
top = (851, 405)
right = (876, 430)
bottom = (851, 455)
left = (826, 430)
```

Então os fluxos poderiam sair assim:

```text
p2_sf_006: sai por cima
p2_sf_004: sai pela direita
p2_sf_005: sai por baixo
```

Isso deixa a semântica visual muito mais clara.

---

## Ordem recomendada no pipeline

Eu usaria as tools nesta ordem:

```text
1. BpmnGatewayFlowDistributorTool
2. BpmnSequenceFlowRouterTool
3. BpmnLabelNormalizerTool
4. BpmnDiagramValidationTool
```

A quarta tool seria opcional, mas útil.

## 4) Tool auxiliar: `validate_bpmn_diagram_layout`

**Objetivo:** medir se o layout melhorou.

Ela não altera o XML; apenas gera métricas.

### Métricas úteis

```text
- quantidade de cruzamentos entre sequence flows
- quantidade de fluxos sobrepostos
- quantidade de labels fora do shape
- quantidade de labels sem bounds
- quantidade de fluxos saindo do mesmo ponto de gateway
- quantidade de waypoints dentro de shapes
```

### Interface sugerida

```python
@dataclass
class DiagramLayoutIssue:
    issue_type: str
    element_id: str
    severity: str
    message: str
```

```python
class BpmnDiagramLayoutValidatorTool:
    def run(self, bpmn_xml: str) -> list[DiagramLayoutIssue]:
        ...
```

---

## Especificação resumida para entregar ao Claude Code

```markdown
# Objetivo

Implementar tools pós-processamento para melhorar a qualidade visual do BPMN DI gerado pela aplicação.

## Tools necessárias

### 1. BpmnLabelNormalizerTool

Responsável por garantir que labels de atividades fiquem centralizados dentro dos shapes.

Regras:
- Aplicar a task, sendTask, receiveTask, serviceTask, userTask, manualTask, businessRuleTask, scriptTask, callActivity e subProcess.
- Se o BPMNShape tiver BPMNLabel vazio, criar dc:Bounds interno.
- Se tiver BPMNLabel sem dc:Bounds, adicionar.
- Se tiver dc:Bounds fora do shape, recalcular.
- Usar padding configurável.
- Não aplicar por padrão a events e gateways.

### 2. BpmnGatewayFlowDistributorTool

Responsável por distribuir saídas de gateways.

Regras:
- Detectar gateways com 2 ou mais outgoing sequence flows.
- Calcular posição relativa dos destinos.
- Atribuir portas de saída diferentes: top, right, bottom, left.
- Atualizar o primeiro waypoint de cada BPMNEdge.
- Evitar que múltiplos fluxos saiam exatamente do mesmo ponto.
- Reposicionar label de condição próximo ao primeiro segmento do fluxo.

### 3. BpmnSequenceFlowRouterTool

Responsável por reduzir cruzamentos e sobreposições de sequence flows.

Regras:
- Ler todos os BPMNShape e BPMNEdge.
- Tratar shapes como obstáculos.
- Gerar rotas ortogonais usando waypoints horizontais/verticais.
- Preferir fluxo esquerda → direita.
- Separar fluxos paralelos com pequeno gap.
- Evitar waypoints atravessando shapes.
- Preservar bpmnElement e ids existentes.
- Atualizar BPMNLabel dos fluxos para o segmento mais longo.

### 4. BpmnDiagramLayoutValidatorTool

Responsável por gerar relatório de qualidade do layout.

Regras:
- Detectar labels vazios.
- Detectar labels fora dos shapes.
- Detectar fluxos com waypoints dentro de shapes.
- Detectar cruzamentos entre sequence flows.
- Detectar sobreposição de segmentos.
- Detectar múltiplos fluxos saindo do mesmo ponto de gateway.
```

---

## Recomendação técnica

Eu começaria pela **`BpmnGatewayFlowDistributorTool`**, porque ela resolverá diretamente um dos maiores problemas do exemplo: as três saídas do gateway `Score do Cliente?` partindo praticamente do mesmo ponto.

Depois implementaria a **`BpmnLabelNormalizerTool`**, que é mais simples e terá ganho visual imediato.

Por fim, implementaria a **`BpmnSequenceFlowRouterTool`**, que é a mais complexa, porque exige cálculo geométrico de interseções, obstáculos e rotas ortogonais.

A arquitetura ideal seria:

```text
BPMN XML gerado pelos agentes
        ↓
GatewayFlowDistributor
        ↓
SequenceFlowRouter
        ↓
LabelNormalizer
        ↓
LayoutValidator
        ↓
BPMN XML final
```

Isso mantém a geração semântica separada da etapa de embelezamento/layout, o que combina bem com a evolução do seu Process2Diagram/RawToInsights AI.




