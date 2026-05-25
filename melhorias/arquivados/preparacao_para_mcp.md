# Especificação Técnica — Evolução Arquitetural do process2diagram AI sem MCP nesta fase

## 1. Objetivo

Implementar uma evolução incremental no projeto RawToInsights AI para consolidar a arquitetura atual baseada em múltiplos agentes, orquestração e tool use, preparando o projeto para uma futura migração parcial para MCP, sem introduzir MCP agora.

A prioridade desta fase é:

* estabilizar as tools existentes;
* padronizar contratos de entrada e saída;
* separar lógica de negócio da lógica de orquestração;
* tornar os artefatos gerados mais previsíveis e auditáveis;
* preparar capabilities reutilizáveis no futuro.

Nesta fase, MCP não deve ser implementado. A arquitetura deve apenas ficar preparada para uma futura camada MCP.

---

## 2. Princípio arquitetural

O projeto deve tratar cada capacidade relevante como uma tool interna bem definida.

Exemplos de capabilities:

* extrair requisitos de uma transcrição;
* gerar resumo executivo;
* identificar decisões;
* identificar pendências;
* gerar BPMN/Mermaid;
* detectar contradições;
* classificar trechos por lente de negócio;
* gerar ata profissional;
* consolidar insights finais.

Cada capability deve possuir:

* nome estável;
* descrição clara;
* schema de entrada;
* schema de saída;
* versão;
* tratamento de erro;
* logs mínimos;
* possibilidade de teste unitário.

---

## 3. Estrutura de diretórios sugerida

Criar ou ajustar a estrutura do projeto para algo próximo de:

```text
rawtoinsights_ai/
│
├── app/
│   ├── main.py
│   └── config.py
│
├── agents/
│   ├── base_agent.py
│   ├── orchestrator_agent.py
│   ├── requirements_agent.py
│   ├── bpmn_agent.py
│   ├── contradiction_agent.py
│   ├── summary_agent.py
│   └── decision_agent.py
│
├── tools/
│   ├── __init__.py
│   ├── base_tool.py
│   ├── registry.py
│   ├── transcript_tools.py
│   ├── requirements_tools.py
│   ├── bpmn_tools.py
│   ├── contradiction_tools.py
│   ├── summary_tools.py
│   └── validation_tools.py
│
├── schemas/
│   ├── __init__.py
│   ├── transcript_schema.py
│   ├── requirements_schema.py
│   ├── bpmn_schema.py
│   ├── contradiction_schema.py
│   ├── summary_schema.py
│   └── tool_schema.py
│
├── prompts/
│   ├── requirements_prompt.md
│   ├── bpmn_prompt.md
│   ├── contradiction_prompt.md
│   ├── summary_prompt.md
│   └── orchestrator_prompt.md
│
├── services/
│   ├── llm_service.py
│   ├── artifact_service.py
│   ├── logging_service.py
│   └── validation_service.py
│
├── outputs/
│   ├── runs/
│   └── artifacts/
│
├── tests/
│   ├── test_tool_contracts.py
│   ├── test_requirements_tool.py
│   ├── test_bpmn_tool.py
│   ├── test_contradiction_tool.py
│   └── test_orchestrator.py
│
└── README.md
```

A estrutura pode ser adaptada ao projeto real, mas a separação entre `agents`, `tools`, `schemas`, `prompts` e `services` deve ser preservada.

---

## 4. Criar classe base para tools internas

Criar o arquivo:

```text
tools/base_tool.py
```

Com uma abstração simples para padronizar as tools.

Exemplo desejado:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    name: str
    description: str
    version: str = "1.0.0"

    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def output_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass
```

Critérios:

* toda tool deve herdar de `BaseTool`;
* toda tool deve expor nome, descrição e versão;
* toda tool deve retornar sempre um dicionário estruturado;
* erros devem ser retornados em formato previsível.

Formato padrão de retorno:

```json
{
  "success": true,
  "tool_name": "nome_da_tool",
  "version": "1.0.0",
  "data": {},
  "warnings": [],
  "errors": [],
  "metadata": {}
}
```

Em caso de erro:

```json
{
  "success": false,
  "tool_name": "nome_da_tool",
  "version": "1.0.0",
  "data": null,
  "warnings": [],
  "errors": ["descrição objetiva do erro"],
  "metadata": {}
}
```

---

## 5. Criar registry de tools

Criar o arquivo:

```text
tools/registry.py
```

Objetivo:

* registrar tools disponíveis;
* permitir descoberta interna;
* permitir chamada por nome;
* preparar arquitetura para futura exposição via MCP.

Exemplo conceitual:

```python
from typing import Dict, Any
from tools.base_tool import BaseTool


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")
        return self._tools[name]

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "version": tool.version,
                "input_schema": tool.input_schema(),
                "output_schema": tool.output_schema(),
            }
            for name, tool in self._tools.items()
        }

    def run(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get(name)
        return tool.run(payload)
```

---

## 6. Criar schemas com Pydantic

Usar Pydantic para padronizar entradas e saídas das principais tools.

Criar schemas iniciais para:

### 6.1 TranscriptInput

Arquivo:

```text
schemas/transcript_schema.py
```

Campos sugeridos:

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class TranscriptInput(BaseModel):
    transcript_text: str = Field(..., description="Texto integral da transcrição da reunião")
    meeting_title: Optional[str] = None
    meeting_date: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 6.2 RequirementItem

Arquivo:

```text
schemas/requirements_schema.py
```

Campos sugeridos:

```python
from pydantic import BaseModel, Field
from typing import Optional, List


class RequirementItem(BaseModel):
    id: str
    description: str
    type: str = Field(..., description="functional, non_functional, business_rule, constraint, assumption")
    source_excerpt: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    related_speakers: List[str] = []
```

### 6.3 ContradictionItem

Arquivo:

```text
schemas/contradiction_schema.py
```

Campos sugeridos:

```python
from pydantic import BaseModel, Field
from typing import Optional, List


class ContradictionItem(BaseModel):
    id: str
    statement_a: str
    statement_b: str
    contradiction_type: str
    severity: str = Field(..., description="low, medium, high, critical")
    explanation: str
    evidence: List[str] = []
    confidence: float = Field(..., ge=0, le=1)
```

### 6.4 ArtifactOutput

Arquivo:

```text
schemas/tool_schema.py
```

Campos sugeridos:

```python
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class ToolResult(BaseModel):
    success: bool
    tool_name: str
    version: str
    data: Optional[Any] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## 7. Implementar tools prioritárias desta fase

Implementar inicialmente apenas as tools mais importantes para estabilizar o produto.

### 7.1 Tool: extract_requirements

Arquivo sugerido:

```text
tools/requirements_tools.py
```

Nome:

```text
extract_requirements
```

Responsabilidade:

Extrair requisitos, regras de negócio, restrições e premissas a partir da transcrição.

Entrada:

```json
{
  "transcript_text": "...",
  "meeting_title": "...",
  "metadata": {}
}
```

Saída:

```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "description": "...",
      "type": "functional",
      "source_excerpt": "...",
      "confidence": 0.91
    }
  ]
}
```

Critérios:

* não retornar texto livre puro;
* sempre retornar lista estruturada;
* incluir evidência textual quando possível;
* incluir confiança estimada.

---

### 7.2 Tool: detect_contradictions

Arquivo sugerido:

```text
tools/contradiction_tools.py
```

Nome:

```text
detect_contradictions
```

Responsabilidade:

Identificar possíveis contradições entre requisitos, decisões, regras de negócio e afirmações da reunião.

Entrada:

```json
{
  "items": [
    {
      "id": "REQ-001",
      "description": "..."
    }
  ],
  "transcript_text": "..."
}
```

Saída:

```json
{
  "contradictions": [
    {
      "id": "CON-001",
      "statement_a": "...",
      "statement_b": "...",
      "contradiction_type": "business_rule_conflict",
      "severity": "high",
      "explanation": "...",
      "evidence": ["...", "..."],
      "confidence": 0.84
    }
  ]
}
```

Critérios:

* diferenciar contradição real de ambiguidade;
* incluir evidência;
* classificar severidade;
* evitar conclusões categóricas quando a evidência for fraca.

---

### 7.3 Tool: generate_bpmn_mermaid

Arquivo sugerido:

```text
tools/bpmn_tools.py
```

Nome:

```text
generate_bpmn_mermaid
```

Responsabilidade:

Gerar uma representação inicial do processo em Mermaid ou pseudo-BPMN a partir dos passos identificados na transcrição.

Entrada:

```json
{
  "transcript_text": "...",
  "requirements": [],
  "decisions": []
}
```

Saída:

```json
{
  "diagram_type": "mermaid_flowchart",
  "diagram_code": "flowchart TD\n...",
  "assumptions": [],
  "warnings": []
}
```

Critérios:

* retornar código Mermaid válido sempre que possível;
* separar assumptions de fatos extraídos;
* não inventar etapas críticas sem indicar como premissa;
* preparar futura evolução para BPMN 2.0 real.

---

### 7.4 Tool: generate_executive_summary

Arquivo sugerido:

```text
tools/summary_tools.py
```

Nome:

```text
generate_executive_summary
```

Responsabilidade:

Gerar resumo executivo da reunião.

Entrada:

```json
{
  "transcript_text": "...",
  "requirements": [],
  "decisions": [],
  "contradictions": []
}
```

Saída:

```json
{
  "summary": "...",
  "key_points": [],
  "risks": [],
  "next_steps": []
}
```

Critérios:

* linguagem profissional;
* foco em valor de negócio;
* separar fatos, riscos e próximos passos.

---

## 8. Orquestrador

Criar ou ajustar o agente orquestrador para não depender diretamente de implementações internas das tools.

Arquivo sugerido:

```text
agents/orchestrator_agent.py
```

Fluxo mínimo esperado:

```text
1. Receber transcrição.
2. Chamar extract_requirements.
3. Chamar detect_contradictions.
4. Chamar generate_bpmn_mermaid.
5. Chamar generate_executive_summary.
6. Consolidar resultado final.
7. Salvar artefatos em outputs/runs/<run_id>/.
```

O orquestrador deve chamar tools pelo registry:

```python
registry.run("extract_requirements", payload)
```

E não diretamente:

```python
extract_requirements(payload)
```

---

## 9. Registro de execução

Cada execução deve gerar uma pasta em:

```text
outputs/runs/<timestamp_or_uuid>/
```

Contendo, no mínimo:

```text
input_transcript.txt
requirements.json
contradictions.json
bpmn_mermaid.mmd
summary.md
final_report.md
run_metadata.json
```

O arquivo `run_metadata.json` deve conter:

```json
{
  "run_id": "...",
  "started_at": "...",
  "finished_at": "...",
  "tools_used": [],
  "llm_model": "...",
  "status": "success|partial|failed",
  "warnings": [],
  "errors": []
}
```

---

## 10. Tratamento de falhas

O pipeline não deve quebrar completamente se uma tool falhar.

Exemplo:

* se `generate_bpmn_mermaid` falhar, ainda gerar resumo e requisitos;
* se `detect_contradictions` falhar, registrar erro e continuar;
* se `extract_requirements` falhar, encerrar com erro controlado, pois é dependência central.

Status possíveis:

```text
success
partial
failed
```

---

## 11. Testes mínimos

Criar testes para garantir que as tools cumpram contrato.

### 11.1 Teste de registry

Arquivo:

```text
tests/test_tool_contracts.py
```

Verificar:

* tool registrada aparece em `list_tools()`;
* tool inexistente gera erro controlado;
* retorno possui os campos obrigatórios.

### 11.2 Teste de cada tool

Cada tool deve possuir pelo menos um teste com uma transcrição curta fictícia.

Critérios:

* `success` deve ser booleano;
* `tool_name` deve estar preenchido;
* `data` deve seguir estrutura esperada;
* `errors` deve ser lista;
* `warnings` deve ser lista.

---

## 12. Prompts externos

Evitar prompts grandes hardcoded dentro do Python.

Colocar prompts em arquivos Markdown dentro de:

```text
prompts/
```

Exemplo:

```text
prompts/requirements_prompt.md
prompts/contradiction_prompt.md
prompts/bpmn_prompt.md
prompts/summary_prompt.md
```

Cada prompt deve conter:

* objetivo da tarefa;
* formato de saída esperado;
* restrições;
* critérios de qualidade;
* exemplo mínimo de JSON esperado, quando aplicável.

---

## 13. Preparação futura para MCP

Nesta fase, não implementar MCP.

Mas cada tool deve estar preparada para futura exposição via MCP.

Para isso:

* usar schemas explícitos;
* manter tools independentes de framework específico;
* evitar dependência direta do orquestrador;
* manter nome, descrição e versão;
* garantir serialização JSON dos inputs/outputs;
* evitar retorno de objetos Python complexos não serializáveis.

A futura migração para MCP deverá ser possível criando uma camada adaptadora:

```text
MCP Server
   └── chama ToolRegistry
          └── executa tools já existentes
```

---

## 14. Fora do escopo desta fase

Não implementar agora:

* MCP Server;
* autenticação complexa;
* banco vetorial;
* RAG avançado;
* UI nova;
* deploy em cloud;
* BPMN 2.0 completo;
* integração com Draw.io;
* integração com ECM;
* integração com Teams;
* múltiplos providers LLM avançados.

Esses itens poderão ser tratados em fases posteriores.

---

## 15. Entregáveis esperados do Claude Code

Implementar incrementalmente:

1. Criar estrutura de diretórios, se ainda não existir.
2. Criar `BaseTool`.
3. Criar `ToolRegistry`.
4. Criar schemas Pydantic mínimos.
5. Refatorar ou criar tools prioritárias.
6. Ajustar orquestrador para usar registry.
7. Criar persistência dos outputs por execução.
8. Criar testes mínimos.
9. Atualizar README com instruções de uso.

---

## 16. Critério de aceite

A implementação será considerada satisfatória se:

* o projeto executar uma transcrição de exemplo de ponta a ponta;
* as tools forem chamadas pelo registry;
* os outputs forem gerados em pasta de execução;
* cada tool retornar JSON padronizado;
* os testes mínimos passarem;
* a arquitetura ficar preparada para futura exposição via MCP sem nova refatoração profunda.

---

## 17. Comando sugerido para execução local

Criar um fluxo executável semelhante a:

```bash
python -m app.main --input examples/transcript_sample.txt
```

Ou, se o projeto já tiver outro padrão de execução, adaptar mantendo o mesmo princípio.

---

## 18. Observação final

O foco desta fase é maturidade arquitetural sem overengineering.

A solução deve continuar simples, testável e evolutiva.

A prioridade é consolidar capabilities internas bem definidas. MCP deve ser visto como uma etapa futura natural, não como requisito atual.
