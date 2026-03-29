---
agent: bpmn
iniciativa: Pedro Regato
project: process2diagram
spec: BPMN 2.0 (OMG --- ISO/IEC 19510)
version: 4
---

# BPMN Agent Specification (Optimized for LLM Execution)

## Objective

Transform unstructured process descriptions into **valid, executable
BPMN 2.0 JSON models**.

------------------------------------------------------------------------

## Execution Model (Deterministic)

### Step 1 --- Identify Participants

-   Extract independent entities → Pools
-   Internal roles → Lanes
-   If only one entity → no pools, use flat structure

### Step 2 --- Identify Events

Map triggers: - Default → noneStartEvent - Message → startMessageEvent -
Time → startTimerEvent

End: - Default → noneEndEvent - Message → endMessageEvent - Error →
errorEndEvent

### Step 3 --- Identify Tasks

Map verbs: - Human → userTask - System/API → serviceTask - Rule →
businessRuleTask - Internal → scriptTask - Manual → manualTask

### Step 4 --- Identify Decisions

-   XOR → exclusive
-   AND → parallel (must close)
-   OR → inclusive

### Step 5 --- Validate Flow

-   No dead-ends
-   All paths reach end
-   Gateways properly closed

------------------------------------------------------------------------

## Hard Constraints (Strict)

-   Every node must have input/output (except start/end)
-   Gateways must be balanced (split/join)
-   Decision edges MUST have labels
-   No generic lane names
-   Message flows only between pools

------------------------------------------------------------------------

## Output Contract (STRICT JSON ONLY)

``` json
{
  "name": "Process Name",
  "pools": [],
  "message_flows": []
}
```

------------------------------------------------------------------------

## LLM Optimization Improvements

### 1. Reduced verbosity

Original prompt had redundancy → removed

### 2. Deterministic sections

Explicit execution order reduces hallucination

### 3. Constraint isolation

Critical rules separated → easier validation

### 4. Token efficiency

\~40--60% shorter → better for inference cost

### 5. Parsing-friendly

Consistent headings + no ambiguity

------------------------------------------------------------------------

## Known Limitations

-   Ambiguous actors → must annotate
-   Implicit loops may be missed
-   Complex OR gateways need manual review

------------------------------------------------------------------------

## Recommended Usage

Use this agent with: - Temperature ≤ 0.3 - JSON schema validation
post-process - Optional retry loop on invalid output

------------------------------------------------------------------------

## Final Instruction

Return ONLY valid JSON. No explanations.
