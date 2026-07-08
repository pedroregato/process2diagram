Perfeito! Vamos estruturar um **plano de melhoria formal** para o Claude Code refinar a regra de uso de `Event Links`. Este plano transforma a instrução vaga ("evitar teia de aranha") em uma **heurística objetiva e mensurável**, com limites claros, validação e convenções de nomenclatura.

---

## 📋 PLANO DE MELHORIA: REGRA DE USO DE EVENT LINKS

### 1. Objetivo

Refinar a heurística de geração de `Link Events` (`intermediateThrowEvent` / `intermediateCatchEvent`) para que sejam utilizados **exclusivamente** em situações onde uma seta explícita comprometeria a legibilidade, evitando que loops curtos ou fluxos de correção fiquem "invisíveis".

---

### 2. Nova Regra Base (Hierarquia de Decisão)

O agente deve avaliar, **nesta ordem**, antes de decidir entre seta explícita e `Link Event`:

#### Passo 1: Tentar reorganizar o layout
- Antes de usar `Link Events`, verificar se os elementos podem ser reposicionados para **aproximar os pontos de origem e destino**.
- **Regra**: Se a distância entre os elementos puder ser reduzida para < 1000px com um reposicionamento simples (ex: mover tarefa para uma região adjacente), faça o reposicionamento e use uma seta explícita.

#### Passo 2: Avaliar a natureza do fluxo
| Tipo de Fluxo | Decisão |
| :--- | :--- |
| **Loop de correção/retrabalho** (ex: "Documentação Incompleta → Voltar para Submissão") | **Sempre seta explícita**, independentemente da distância. A visibilidade do retorno é essencial para a compreensão do processo. |
| **Fluxo principal sequencial** | Sempre seta explícita. |
| **Salto excepcional** (ex: "Pular para uma etapa muito à frente" ou "Conectar a um ponto distante que não é um loop") | Avaliar critérios de distância/cruzamento. |

#### Passo 3: Aplicar critérios objetivos (se o fluxo for um salto excepcional)
Use `Link Events` somente se **todas** as condições abaixo forem verdadeiras:
- **Distância linear** > 2000px (considerando a localização atual no diagrama).
- **Cruzamento de elementos**: a linha reta entre origem e destino cruza pelo menos **3 outros elementos** (tarefas, gateways, eventos) ou **2 outras setas**.
- **Salto de lanes**: origem e destino estão em **lanes diferentes**, sem uma sequência natural de transição entre elas.

**Se qualquer uma das condições falhar → use seta explícita com waypoints.**

---

### 3. Convenção de Nomenclatura (Obrigatória)

| Tipo | Padrão | Exemplo |
| :--- | :--- | :--- |
| `intermediateThrowEvent` (origem) | `link_throw_{id_origem}_{id_destino}` | `link_throw_S03_S01` |
| `intermediateCatchEvent` (destino) | `link_catch_{id_origem}_{id_destino}` | `link_catch_S03_S01` |
| **Rótulo visual** | "Retorno para {nome_destino}" | "Retorno para Submeter Demanda" |

**Regra adicional**: O nome do `linkEventDefinition` deve ser exatamente igual para o par throw/catch, garantindo a correlação.

---

### 4. Validação Pós-Geração (Checklist Automático)

O agente deve verificar, após gerar o diagrama:

- [ ] Todo `intermediateThrowEvent` com `linkEventDefinition` tem um `intermediateCatchEvent` correspondente com o mesmo `linkEventDefinition` name.
- [ ] O par throw/catch não está sendo usado para um loop de correção (verificar se o destino é um `UserTask` ou `CallActivity` que precede o gateway de decisão).
- [ ] A distância entre throw e catch é > 1500px (caso contrário, alertar para substituição por seta explícita).
- [ ] O nome do `linkEventDefinition` segue o padrão `link_{id_origem}_{id_destino}`.

---

### 5. Tratamento de Exceções (Casos Especiais)

| Caso | Tratamento |
| :--- | :--- |
| **Loop de Correção Curto** (< 1000px) | Jamais usar `Link Events`. Usar seta explícita. |
| **Loop de Correção Longo** (> 2000px) | Priorizar **reorganização do layout** para encurtar a distância. Se impossível, **usar seta explícita com waypoints curvos**, evitando o loop invisível. |
| **Salto entre subprocessos** | Se a origem e destino estão em `CallActivity` diferentes, o salto não faz sentido; rever o fluxo. |

---

### 6. Instrução Final para o Agente (Prompt de Geração)

> *"Regra de uso de `Link Events` (intermediateThrowEvent / intermediateCatchEvent):*
>
> 1. **Nunca** use `Link Events` para loops de correção, retrabalho ou retorno de gateway para etapa anterior. Esses fluxos devem ser representados com `sequenceFlow` explícito (seta visível), mesmo que longos, para garantir a legibilidade do ciclo.
>
> 2. Use `Link Events` **exclusivamente** para saltos excepcionais que:
>    - conectam dois pontos com distância linear > 2000px;
>    - cruzam pelo menos 3 outros elementos ou 2 outras setas;
>    - não fazem parte de um ciclo de correção.
>
> 3. **Sempre** nomeie os `Link Events` com o padrão `link_throw_{id_origem}_{id_destino}` e `link_catch_{id_origem}_{id_destino}`, garantindo que o nome do `linkEventDefinition` seja idêntico para o par.
>
> 4. Antes de gerar `Link Events`, **tente reorganizar o layout** para aproximar os pontos de origem e destino. Se for possível reposicionar elementos para evitar o salto, prefira a seta explícita.
>
> 5. Após a geração, valide se há pares throw/catch correspondentes e se nenhum loop de correção está usando `Link Events`. Se encontrar, substitua por setas explícitas."*

---

### 7. Exemplo de Aplicação (Antes vs. Depois)

#### Cenário: Documentação incompleta (Governança de IA)

| Aspecto | Antes (ruim) | Depois (bom) |
| :--- | :--- | :--- |
| **Elementos** | `S03` (Gateway) → `lnk_throw_1` (salto) → `lnk_catch_1` → `S01` | `S03` (Gateway) → `S01` com seta visível |
| **Legibilidade** | O retorno é invisível; leitor não vê o loop. | O loop é claro; leitor entende o retrabalho. |
| **Nomenclatura** | `lnk_throw_1` (genérico) | `link_throw_S03_S01` (descritivo) |

#### Cenário: Conexão entre duas extremidades do diagrama (sem loop)

| Aspecto | Antes (ruim) | Depois (bom) |
| :--- | :--- | :--- |
| **Elementos** | Seta gigante cruzando o diagrama | `link_throw_Z99_A01` → `link_catch_Z99_A01` |
| **Legibilidade** | Diagrama poluído com cruzamento de 4 setas. | Diagrama limpo; par de link events nomeados. |

---

### 8. Critério de Aceite para Implementação

- [ ] O agente gera diagramas com **0 (zero)** `Link Events` em loops de correção.
- [ ] Todos os `Link Events` possuem nomenclatura descritiva.
- [ ] A validação pós-geração identifica e corrige automaticamente pares não correspondentes.
- [ ] A largura média dos diagramas não aumenta > 10% em relação à versão anterior.

---

## 🚀 Como Enviar para o Claude Code

Copie e cole o seguinte prompt para o Claude Code implementar a melhoria:

---

> **Prompt para Claude Code:**
>
> *"Implemente a melhoria da regra de uso de `Link Events` conforme o plano abaixo:*
>
> *1. Atualize a lógica de geração para que `Link Events` só sejam usados quando:*
>    - *Distância entre origem e destino > 2000px **E***
>    - *Cruzamento de > 3 elementos ou > 2 setas **E***
>    - *O fluxo NÃO for um loop de correção/retrabalho.*
>
> *2. Para loops de correção (ex: documentação incompleta, relatório rejeitado), use sempre `sequenceFlow` com setas visíveis, independentemente da distância.*
>
> *3. Padronize a nomenclatura:*
>    - *Throw: `link_throw_{id_origem}_{id_destino}`*
>    - *Catch: `link_catch_{id_origem}_{id_destino}`*
>    - *O `linkEventDefinition` name deve ser idêntico para o par.*
>
> *4. Adicione uma validação pós-geração que:*
>    - *Verifique se todo throw tem um catch correspondente.*
>    - *Alerta se um loop de correção está usando `Link Events`.*
>
> *5. Antes de gerar `Link Events`, tente reorganizar o layout para aproximar os pontos.*
>
> *Teste a nova regra com o diagrama de Governança de IA, substituindo os `Link Events` de loops por setas explícitas."*

---

## 📌 Resumo

| Ponto | Decisão |
| :--- | :--- |
| **Loops de correção** | ✅ Sempre seta explícita |
| **Saltos excepcionais** | ✅ Link Events permitidos, com critérios objetivos |
| **Nomenclatura** | ✅ Descritiva e padronizada |
| **Validação** | ✅ Automática pós-geração |
| **Layout primeiro** | ✅ Tentar reposicionar antes de link event |

Com este plano, você garante que o agente aplique a regra com **inteligência e consistência**, evitando tanto a "teia de aranha" quanto o "loop invisível".