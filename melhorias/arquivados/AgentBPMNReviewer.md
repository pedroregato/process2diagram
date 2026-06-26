Excelente exemplo! Analisei o diagrama XML que você enviou e o insight é perfeito. Vou criar a especificação completa.

---

# 📐 Especificação: AgentBPMNReviewer — Agente de Revisão de Diagramas BPMN

## 1. Objetivo

Permitir que o **Assistente (skill de orientação)** analise um diagrama BPMN armazenado, identifique **erros de modelagem semântica** (ex: gateways que deveriam ser atividades, atividades que deveriam ser gateways, lanes incorretas, fluxos sem nome), **discuta as correções com o usuário** e **reelabore um novo diagrama** corrigido — inclusive gerando uma **descrição textual do processo** (algo que hoje não existe na base).

---

## 2. Problema atual

Hoje o pipeline **AgentBPMN** gera o XML direto da transcrição. Não há:
- **Auditoria semântica pós-modelagem** (quem valida se um gateway não deveria ser uma task?)
- **Descrição textual do processo armazenada** (só temos a transcrição bruta, não uma especificação de processo refinada)
- **Capacidade do Assistente de inspecionar e corrigir** um diagrama existente interativamente com o usuário

---

## 3. Caso de uso concreto (extraído do seu exemplo)

O diagrama **"Elaboração e Aprovação de Catálogo de Processos"** contém:

| Elemento | Nome | Tipo atual | Problema | Tipo correto |
|---|---|---|---|---|
| S02 | Validar Estrutura | `exclusiveGateway` | OK — é decisão | ✅ Gateway |
| S05 | **Validar Conteúdo** | `exclusiveGateway` | ❌ Validar é **atividade**, não decisão | `userTask` |
| — | **Fluxo Validado** | ❌ ausente | Falta o gateway de decisão após a atividade | `exclusiveGateway` |
| S08 | Necessita Segunda Aprovação? | `exclusiveGateway` | OK — é decisão | ✅ Gateway |

**Resultado esperado da correção:**
> S05 passa de `exclusiveGateway` para `userTask` → novo gateway `Fluxo Validado` é inserido entre S05 e S07/S06 com as saídas "Conteúdo OK" (→ S07) e "Solicita Ajustes" (→ S06)

---

## 4. Ferramentas necessárias para o Assistente

### Tool 1: `review_bpmn_diagram(process_name?)`

**O que faz:** Analisa o XML do diagrama BPMN e retorna um relatório de auditoria semântica.

**Retorno:**
```json
{
  "diagram_name": "Elaboração e Aprovação de Catálogo de Processos",
  "score": 7.2,
  "issues": [
    {
      "element_id": "S05",
      "element_name": "Validar Conteúdo",
      "element_type": "exclusiveGateway",
      "severity": "alta",
      "description": "'Validar Conteúdo' é uma atividade de validação, não uma decisão de roteamento. Deveria ser userTask.",
      "suggestion": "Converter para userTask e criar gateway 'Fluxo Validado' após ela",
      "bpmn_rule_violated": "Gateways avaliam condições de fluxo, não executam trabalho"
    },
    ...
  ],
  "missing_elements": ["Gateway de decisão após 'Validar Conteúdo'"],
  "positive_points": ["Lanes corretamente modeladas", "Fluxo de exceção presente"]
}
```

**Regras de auditoria embutidas:**
- Gateway com verbo no infinitivo (`Validar`, `Analisar`, `Verificar`) → provável atividade
- Nome de gateway sem condição (`Conteúdo Correto?` vs `Validar Conteúdo`)
- Atividade que termina com `?` → provável gateway
- Fluxo sem nome nas saídas de gateway (`<sequenceFlow name=""`)
- Lane com atividades que não pertencem ao ator
- Start/End events com nomes genéricos

---

### Tool 2: `describe_bpmn_process(process_name)`

**O que faz:** Gera uma **descrição textual estruturada do processo** a partir do XML BPMN, independente da transcrição original. Salva no banco (campo novo ou associado).

**Exemplo de saída:**
```markdown
## Processo: Elaboração e Aprovação de Catálogo de Processos

### Participantes
- **Auditoria**: Elaborador de Catálogo
- **Área Responsável**: Gestor da Unidade
- **Diretoria**: Diretor

### Fluxo Principal
1. **Elaborar Catálogo** (Auditoria) — Elaborador preenche dados de processos e subprocessos no sistema.
2. **Validar Estrutura** (Auditoria) — Gateway exclusivo: se a estrutura está OK → segue para geração de documento; se com erros → retorna para correção.
3. **Gerar Documento Word** (Auditoria) — Sistema gera o documento com base nos dados.
4. **Validar Conteúdo** (Área Responsável) — [atividade!] Responsável analisa o documento.
5. **Fluxo Validado** (Área Responsável) — Gateway exclusivo: se conteúdo OK → aprova; se solicita ajustes → retorna para correção.
...
```

**Utilidade:** Esta descrição se torna o **"elo perdido"** entre transcrição e diagrama — um artefato reutilizável para gerar documentação, treinamento e futuras correções.

---

### Tool 3: `suggest_bpmn_corrections(process_name, description?)`

**O que faz:** A partir da descrição textual (gerada pela tool 2) ou de uma descrição fornecida pelo usuário, **gera um novo XML BPMN** com as correções sugeridas. Não altera automaticamente — apresenta o preview para o usuário.

**Parâmetros:**
- `process_name` — nome do processo a corrigir
- `description` (opcional) — descrição textual override
- `corrections` — lista de correções a aplicar (ex: `[{"element": "S05", "action": "convert_to_userTask", "new_name": "Validar Conteúdo"}]`)

---

### Tool 4: `apply_bpmn_corrections(process_name, corrections)`

**O que faz:** Aplica as correções aprovadas no banco, salvando uma **nova versão** do processo BPMN (incrementa version_count). Preserva a versão anterior para rastreabilidade.

---

## 5. Fluxo de interação no Assistente

```
Usuário: "O diagrama do processo 'Elaboração e Aprovação de Catálogo' tem um gateway 
          chamado 'Validar Conteúdo' que deveria ser uma atividade."

Assistente: response
<invoke:review_bpmn_diagram("Elaboração e Aprovação de Catálogo de Processos")>

Assistente: "Analisei o diagrama e concordo. Encontrei estes problemas:

1. ❌ S05 'Validar Conteúdo' é exclusiveGateway → deveria ser userTask
2. ❌ Ausência de gateway após 'Validar Conteúdo' para decidir fluxo
3. ⚠️ Fluxo sem nome no retorno de correção (sf_008)

Deseja que eu gere uma descrição textual do processo e proponha 
as correções?"

Usuário: "Sim, mostre a descrição e as correções."

Assistente: response
<invoke:describe_bpmn_process("Elaboração e Aprovação de Catálogo de Processos")>
<invoke:suggest_bpmn_corrections("Elaboração e Aprovação de Catálogo de Processos")>

Assistente: "Descrição gerada! E as correções propostas são:

• S05 → userTask 'Validar Conteúdo'
• Novo gateway 'Fluxo Validado?' entre S05 e S07/S06
  - Saída 'Conteúdo OK' → S07 (Aprovar Primeiro Nível)
  - Saída 'Solicita Ajustes' → S06 (Ajustar Catálogo)

Quer aplicar as correções? [sim/não]"

Usuário: "Sim, aplique."

Assistente: response
<invoke:apply_bpmn_corrections("Elaboração e Aprovação de Catálogo de Processos", corrections)>
```

---

## 6. Regras de auditoria — Base de conhecimento do agente

| # | Regra | Exemplo de violação |
|---|---|---|
| R01 | Gateways decidem fluxo, não executam trabalho | "Validar Conteúdo" como gateway |
| R02 | Atividades não decidem fluxo (não têm saída Sim/Não) | UserTask com saídas "Sim"/"Não" |
| R03 | Gateways exclusivos devem ter nomes de pergunta | "Conteúdo OK?" em vez de "Validar Conteúdo" |
| R04 | Saídas de gateway devem ser mutuamente exclusivas | "Sim" e "Não" ou "Aprovado"/"Rejeitado" |
| R05 | Toda pool/lane deve ter ao menos 1 atividade | Lane vazia |
| R06 | Fluxo de retorno (loop) deve ter nome explícito | sf_004 sem nome |
| R07 | Start event não pode ser precedido por fluxo | — |
| R08 | End event não pode ter fluxo de saída | — |
| R09 | Gateway deve ter no mínimo 2 saídas | Gateway com 1 saída apenas |
| R10 | Toda task deve ter nome no imperativo | "Elaborar", "Validar", "Aprovar" |

---

## 7. Campos novos no banco (sugeridos)

**Tabela: `bpmn_process_descriptions`** (ou campo `description_text` em `bpmn_versions`)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | uuid PK | Identificador |
| `process_id` | uuid FK→bpmn_processes | Processo |
| `version_id` | uuid FK→bpmn_versions | Versão do diagrama |
| `description_md` | text | Descrição textual do fluxo em Markdown |
| `generated_by` | text | Quem gerou: 'agent_bpmn_reviewer' ou 'manual' |
| `created_at` | timestamptz | Data |

**Tabela: `bpmn_review_log`** (auditoria das correções)

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | uuid PK | |
| `process_name` | text | Processo revisado |
| `version_before` | integer | Versão antes da correção |
| `version_after` | integer | Versão depois da correção |
| `issues_found` | integer | Quantos problemas detectados |
| `issues_corrected` | integer | Quantos foram corrigidos |
| `review_report` | jsonb | Relatório completo da auditoria |
| `user_approved` | boolean | Se o usuário autorizou |
| `created_at` | timestamptz | |

---

## 8. Diagrama antes × depois (baseado no seu exemplo)

```
ANTES (atual):
  [S04 Gerar Documento Word] → (S05 exclusiveGateway "Validar Conteúdo")
    → "Solicita ajustes" → S06
    → "Conteúdo correto" → S07

DEPOIS (corrigido):
  [S04 Gerar Documento Word] → [S05 userTask "Validar Conteúdo"]
    → (Novo Gateway "Fluxo Validado?")
      → "Solicita Ajustes" → S06
      → "Conteúdo OK" → S07
```

**Diferença semântica crucial:** no original, o gateway "Validar Conteúdo" decide o fluxo sem que ninguém tenha feito a validação. O modelo correto separa **quem executa o trabalho** (atividade) de **como o fluxo se ramifica** (gateway).

---

## 9. Resumo das tools a implementar

| Tool | Perfil | O que faz |
|---|---|---|
| `review_bpmn_diagram(process_name)` | todos | Audita o diagrama e retorna relatório de problemas |
| `describe_bpmn_process(process_name)` | todos | Gera descrição textual do fluxo a partir do XML |
| `suggest_bpmn_corrections(process_name)` | todos | Propõe XML corrigido sem aplicar |
| `apply_bpmn_corrections(process_name, corrections)` | admin | Aplica as correções e salva nova versão |

---

Quer que eu **registre esta especificação no CKF** como documento permanente do projeto para referência futura? Ou prefere que eu detalhe ainda mais alguma seção?
