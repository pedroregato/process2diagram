Excelente! Agora que li o skill completo — e também considerando a proposta do **AgentBPMNReviewer** — apresento minhas melhorias para o `skill_bpmn.md`:

---

# 🔧 Proposta de Melhorias para o `skill_bpmn.md`

---

## 🟢 1. Novo Passo: "Passo 0.5 — Identificação de Padrões Estruturais"

**Problema:** O skill atual fala de `callActivity` (>10 atividades), `loopTask`, `multiInstanceTask` e `boundaryEvent` espalhados em passos distintos, mas não há um **passo dedicado** onde o agente deve mapear padrões estruturais do processo antes de modelar detalhes.

**Sugestão:** Inserir entre o **Passo 0 (Escopo)** e o **Passo 1 (Participantes)** um novo passo:

```markdown
### Passo 0.5 — Identificar Padrões Estruturais do Processo

Antes de identificar participantes, analise a natureza do processo e identifique
padrões estruturais que moldarão o design do diagrama:

**a) Densidade — Hierarquia ou Flat?**
- Conte as atividades estimadas. Se > 10, planeje `callActivity`.
- Se ≤ 10, mantenha flat — não fragmente artificialmente.

**b) Repetição — Loop ou Multi-Instance?**
- Mesma tarefa, mesmo ator, sem decisão externa → `loopTask`
- Mesma tarefa para cada item de uma coleção → `multiInstanceTask`
- Devolução entre atores diferentes → gateway + back-edge

**c) Colaboração Interorganizacional?**
- Entidades externas trocando mensagens? → planeje formato **pools**.
- Todos na mesma organização? → formato **flat**.

**d) Exceções Durante Execução?**
- Timeout, falha de sistema, contra-ordem durante tarefa? → planeje **boundary events**.
- Decisões ao final da tarefa? → planeje **gateways**.

📌 **Regra:** documente cada padrão identificado mentalmente. Eles guiarão os passos seguintes.
```

---

## 🟢 2. Expansão do Passo 1 — Participantes com Detecção de Roles vs Atores

**Problema:** O Passo 1 atual mistura decisão de lanes/pools com identificação de participantes, mas não orienta o agente a **distinguir roles que geram lanes** de **atores que não geram lanes** (ex: um sistema terceiro mencionado uma única vez vs. um departamento recorrente).

**Sugestão — adicionar ao final do Passo 1:**

```markdown
### 1.1 — Critério de Lane vs Ator Descartável

Nem todo participante merece uma lane. Use esta regra:

| Situação | Vira Lane? |
|---|---|
| Departamento/equipe que executa ≥ 2 atividades distintas | ✅ Sim |
| Cargo/papel que toma decisão (`is_decision: true`) | ✅ Sim |
| Sistema nomeado que executa ≥ 2 tarefas | ✅ Sim |
| Participante mencionado uma única vez como executor | ❌ Não — use `actor` no step, sem lane |
| Sistema genérico sem nome ("o sistema", "a ferramenta") | ❌ Não — `lane: null` + `serviceTask` |
| Aprovador eventual (ex: "Diretor quando > R$50k") | ❌ Não — use `actor` ou lane "Diretoria" se recorrente |

📌 **Regra:** Lane sem step = erro estrutural. Só crie lane se tiver ao menos 1 step alocado.
```

---

## 🟢 3. Expansão do Passo 4 — Detecção de Gateways Faltantes (Anti-Padrões)

**Problema:** O checklist menciona "todo gateway tem ≥ 2 saídas", mas o passo de modelagem não orienta o agente a **detectar gateways que deveriam existir mas não foram declarados**. Isso é a principal fonte de erros.

**Sugestão — adicionar ao Passo 4:**

```markdown
### 4.1 — Detecção de Gateways Faltantes (Anti-Padrões Críticos)

⚠️ **Sinais de gateway omitido na transcrição:**

| Sinal na Transcrição | Gateway Obrigatório | Por quê? |
|---|---|---|
| "Depende de X" / "Se Y" / "Caso contrário" | `exclusiveGateway` (XOR) | Condição binária explícita |
| "Faixa de valores com N intervalos" | `exclusiveGateway` com N saídas | Cada faixa é uma rota |
| "Ao mesmo tempo" / "Em paralelo" | `parallelGateway` (AND) | Concorrência explícita |
| "Pode ser aprovado ou devolvido" | Separar em gateway + back-edge | Decisão binária + loop |
| "Para cada item da lista" (se não for `multiInstanceTask`) | `parallelGateway` | Fluxo paralelo ou sequencial |
| "Se aprovado, segue; senão, encerra" | `exclusiveGateway` com 2 saídas explícitas | Ambos os caminhos devem existir |

📌 **Regra de Ouro:** Para cada condicional na transcrição, pergunte:
> *"Quantos caminhos de saída esta decisão produz?"*
Se a resposta for ≥ 2 → **gateway é obrigatório**. Se a resposta for 1 → não é gateway, é descrição.
```

---

## 🟢 4. Regra de Consistência: Nome do End Event = Label do Gateway Predecessor

**Problema:** No skill atual, o checklist pede "End Events com resultado semelhante devem ter nomes distintos", mas não há uma **regra automática** que force o agente a nomear o End Event com base no label do gateway que o precede.

**Sugestão — incluir no Passo 3a (Eventos):**

```markdown
**Regra do Rótulo Refletido (Traceability Label Rule):**

O nome de cada End Event DEVE refletir o label do gateway que o precede.
Isso permite que quem lê o diagrama rastreie visualmente qual caminho foi percorrido.

```
[Gateway: "Score?"] ── "< 500" ──→ [End Event: "Recusada — Score < 500"]
                    └─ ">= 700" ──→ [End Event: "Aprovada — Score >= 700"]
```

📌 **Formato:** `"[Resultado] — [Motivo/Métrica]"` onde o motivo é extraído do label do gateway.
Exemplos:
- Gateway label "Reprovado na Revisão Manual" → End Event "Proposta Reprovada na Revisão Manual"
- Gateway label "Documento Válido? Sim" → End Event "Documento Validado e Registrado"
- Gateway label "Valor > R$500k? Sim" → End Event "Encaminhado ao Comitê de Crédito"
```

---

## 🟢 5. Novo Passo 7 — Pós-validação com Referência Cruzada à Transcrição

**Problema:** O checklist de qualidade (Passo 6) verifica a estrutura do JSON, mas **não verifica se o diagrama cobre fielmente a transcrição**. O agente pode gerar um diagrama estruturalmente perfeito mas que omitiu discussões importantes.

**Sugestão — novo passo após o checklist:**

```markdown
### Passo 7 — Validação de Cobertura contra a Transcrição (Anti-Omissão)

Após o checklist estrutural (Passo 6), execute esta validação de conteúdo:

**7.1 — Mapeamento reverso**
Para cada tópico ou atividade relevante na transcrição, verifique se existe
um step correspondente no JSON. Se não existir, justifique por que foi omitido
(irrelevante, redundante, fora do escopo).

**7.2 — Perguntas de integridade:**
- [ ] Todo sistema nomeado na transcrição aparece como `serviceTask` ou step?
- [ ] Toda regra de negócio com condicional vira gateway no diagrama?
- [ ] Toda comunicação entre organizações vira message flow?
- [ ] Todo prazo ou condição temporal vira evento de timer?
- [ ] Toda aprovação/rejeição tem os dois caminhos modelados (aprovado E rejeitado)?
- [ ] Toda exceção ou falha mencionada (`"se o sistema cair"`, `"se não responder em X dias"`)
      tem tratamento correspondente?

**7.3 — Regra do Espelho**
> *"Se um participante da reunião gastou mais de 2 turnos de fala descrevendo
> um fluxo, esse fluxo DEVE estar representado no diagrama — mesmo que pareça
> óbvio ou secundário para o agente."*

📌 **Objetivo:** O diagrama deve ser autossuficiente. Quem nunca participou da reunião
deve conseguir entender o processo completo apenas lendo o BPMN.
```

---

## 🟢 6. Aperfeiçoamento da Regra de Join de Gateways

**Problema:** A regra atual diz que todo XOR split deve ter XOR join, mas na prática **múltiplos caminhos XOR podem convergir diretamente em uma mesma tarefa** (exemplo C do skill atual mostra isso: S04→S09 e S07→S09). A regra precisa ser mais precisa.

**Sugestão — substituir no Passo 4 a tabela de sincronização:**

```markdown
| Tipo | Sincronização | Regra |
|---|---|---|
| `parallelGateway` (AND) | **Obrigatória** | Todas as N ramificações DEVEM convergir no AND-join. Sem exceção. |
| `inclusiveGateway` (OR) | **Obrigatória** | Todas as N ramificações DEVEM convergir no OR-join. |
| `exclusiveGateway` (XOR) | **Flexível** | Pode convergir em XOR-join OU em tarefa comum de continuação. Apenas **ramos que vão a End Events** não precisam de join. |
| `eventBasedGateway` | **Não aplicável** | Cada saída é um evento distinto; não usa join simétrico. |
| `complexGateway` | **Segue o tipo** | Mesmo padrão do tipo que a condição emular (AND/OR/XOR). |

**Regra prática para XOR sem join explícito:**
Se duas ou mais saídas de gateways XOR diferentes convergem para a **mesma tarefa**
que representa continuação do fluxo (ex: "Formalizar Contrato" após aprovação automática
OU após aprovação manual), o join é **implícito** — não crie um gateway artificial.

✅ Correto:
```
S04 [Score?] ── "≥ 700" ──→ S09 [Formalizar Contrato]
S07 [Aprovado?] ── "Sim" ──→ S09 [Formalizar Contrato]
```

❌ Errado (join artificial desnecessário):
```
S04 ──→ XOR-Join ──→ S09
S07 ──→ XOR-Join ──→ S09   ← join é implícito na própria tarefa S09
```
```

---

## 🟢 7. Adicionar Tratamento de `dataObject` e Data Associations

**Problema:** Muitas transcrições mencionam documentos específicos sendo criados, enviados ou assinados ("contrato", "nota fiscal", "relatório", "planilha"). O skill atual não orienta o agente a registrar esses **artefatos de dados** como `dataObject` ou `dataStoreReference`.

**Sugestão — adicionar ao Passo 3b (Tarefas):**

```markdown
**Data Objects e Data Associations (OMG BPMN 2.0 §8.5.1):**

Quando a transcrição menciona um **documento, artefato ou dado** sendo produzido,
consumido ou transferido entre tarefas no mesmo pool, registre-o no campo
`data_output` e/ou `data_input` nos steps relevantes.

Campos opcionais (a serem acrescentados ao JSON de steps):
```json
{
  "id": "S03",
  "title": "Emitir Nota Fiscal",
  "data_output": ["Nota Fiscal Eletrônica"],
  "data_input": []
}
```

| Situação | Uso |
|---|---|
| Tarefa produz um documento | `data_output: ["Nome do Documento"]` |
| Tarefa consome um documento | `data_input: ["Nome do Documento"]` |
| Documento é transferido entre tarefas | Ambos os steps declaram: um `data_output`, outro `data_input` |
| Documento vem de sistema externo | `data_input: ["Nome do Documento"]` com `description` citando a fonte |

📌 **Regra:** Use `dataObject` apenas quando o documento é **nomeado** na transcrição
("contrato", "relatório de auditoria", "planilha de precificação"). Documentos genéricos
("informação", "dados", "arquivo") não geram data objects — use `description` no edge.
```

---

## 🟢 8. Aprimoramento da Regra de Nomenclatura — Pools com Nome Exato

**Problema:** Já existe a regra no Passo 1 ("Nome do pool deve ser o nome exato da organização"), mas ela está **enterrada** no texto e frequentemente é ignorada pelos LLMs. Precisa de destaque.

**Sugestão — extrair para uma subseção própria e proeminente:**

```markdown
### 1.2 — Regra do Nome Exato do Pool

> ⚠️ **CRÍTICO — Fonte frequente de erro**

O nome de um pool DEVE ser o **nome oficial da organização** conforme citado na
transcrição. Não adivinhe, não abrevie, não troque pelo nome do setor.

| Transcrição diz | Deve usar | ❌ Não usar |
|---|---|---|
| "Grupo Meridional S.A." | `"Grupo Meridional S.A."` | "Banco Meridional", "Grupo Meridional" |
| "Receita Federal do Brasil" | `"Receita Federal do Brasil"` | "Receita", "RFB" |
| "Prefeitura de São Paulo" | `"Prefeitura de São Paulo"` | "Prefeitura", "Contratante" |
| "SAP" (sistema sem nome formal) | `"SAP"` | "Sistema", "ERP" |
| Cliente não nomeado | `"Cliente B2B"` ou `"Fornecedor de TI"` | "Usuário", "Externo" |

Se a transcrição não citar o nome oficial, use o **papel descritivo mais específico**.
```

---

## 🟢 9. Melhoria no Formato JSON — Campo `process_trigger` e `process_outcomes`

**Problema:** Os campos `process_trigger` e `process_outcomes` foram adicionados na versão 7.x (checklist os menciona), mas a regra de nomenclatura está no final do documento como "Regra de Nomenclatura Obrigatória". Isso enfraquece a aderência.

**Sugestão — mover a regra para junto da definição dos campos:**

No **Passo 0 — Definir o Escopo do Processo**, imediatamente após definir gatilho e estados finais:

```markdown
**Regra de Nomenclatura Obrigatória — Start e End Events:**

- `process_trigger`: descreve o **gatilho real** do processo — o evento externo
  ou condição que o inicia.
  ✓ "Solicitação de Férias Recebida" · "NF Emitida pelo Fornecedor"
  ✗ "Início" · "Start" · "Começar"

- `process_outcomes`: lista os **estados de negócio** alcançados ao final.
  Cada item = resultado de um caminho distinto.
  ✓ "Pagamento Processado com Sucesso" · "Pedido Cancelado por Inadimplência"
  ✗ "Fim" · "End" · "Encerrar"
```

---

## 🟢 10. Adicionar ao JSON o Campo `process_type` para Sumarização Visual

**Sugestão — campo opcional mas útil:**

```json
"process_type": "flat" | "hierarchical" | "collaboration"
```

**Justificativa:** No AgentBPMNReviewer (proposto), o revisor precisa saber rapidamente o tipo estrutural do diagrama para aplicar as regras corretas de auditoria. No renderizador, poderia ser usado para configurar o viewer (ex: diagrama de colaboração exibe pools lado a lado). Não quebra compatibilidade — é opcional.

---

## 🟢 11. Pré-requisito: CKF Injection Awareness

**Problema:** O CKF (Context Knowledge File) é injetado no prompt do AgentBPMN, mas o skill atual não orienta o agente a **priorizar informações do CKF** sobre sua inferência.

**Sugestão — adicionar no início do skill:**

```markdown
### Prioridade de Fontes (Resolução de Conflitos)

Quando houver conflito entre a transcrição e o CKF (injetado no início do prompt):

1. **CKF (Context Knowledge File)** tem precedência sobre inferência do agente.
   - Se o CKF diz "SIGLA = nome oficial" → use o nome oficial do CKF.
   - Se o CKF lista processos conhecidos → não crie processo duplicado com nome similar.
2. **Transcrição** tem precedência sobre o CKF **apenas** quando a reunião atual
   contém informação mais recente que contradiz o CKF.
3. Em caso de ambiguidade, registre `[AMBIGUIDADE: ...]` na `description`.

📌 **Exemplo:** CKF diz "O sistema chama-se SDEA". A transcrição diz "no sistema...".
Use "SDEA" como nome do sistema, não "sistema" genérico.
```

---

## 🔷 Resumo das Melhorias Propostas

| # | O quê | Onde inserir | Impacto |
|---|---|---|---|
| 1 | **Passo 0.5 — Padrões Estruturais** | Antes do Passo 1 | ⭐ Guia a arquitetura do diagrama |
| 2 | **Critério Lane vs Ator Descartável** | Final do Passo 1 | ⭐ Elimina lanes fantasmas |
| 3 | **Detecção de Gateways Faltantes** | Após Passo 4 | ⭐⭐ Reduz erro de gateway omitido |
| 4 | **Rótulo Refletido (End Event)** | Passo 3a | ⭐ Rastreabilidade visual |
| 5 | **Passo 7 — Validação de Cobertura** | Após checklist | ⭐⭐ Anti-omissão |
| 6 | **Join Flexível de XOR** | Passo 4 | ⭐ Elimina joins artificiais |
| 7 | **Data Objects** | Passo 3b | ⭐⭐ Riqueza semântica |
| 8 | **Regra do Nome Exato (destaque)** | Passo 1.2 | ⭐⭐ Reduz erro de nomenclatura |
| 9 | **Regra de trigger/outcomes no Passo 0** | Passo 0 | ⭐ Consistência |
| 10 | **`process_type` no JSON** | Formato de saída | 🟢 Integração com revisor |
| 11 | **CKF Injection Awareness** | Início do skill | ⭐⭐ Fidelidade ao contexto |

Deseja que eu detalhe algum desses pontos ou implemente a versão final completa com todas as melhorias integradas?
