Com base na metodologia de Bruce Silver descrita no livro **"BPMN Method and Style"** e na estrutura atual do seu arquivo de instruções, este plano visa elevar a qualidade da modelagem do agente de um nível descritivo básico para um nível **analítico e hierárquico profissional**.

Este plano foca na implementação da **Modelagem Hierárquica Top-Down** e na expansão para o **Level 2** de BPMN.

---

# Plano de Implementação: BPMN Method and Style (Level 1 & 2)

## 1. Reestruturação do Processo de Modelagem (The Method)
O atual "Passo a Passo" do `skill_bpmn.md` deve ser reorganizado para seguir rigorosamente os 5 passos do método de Bruce Silver:

*   **Passo 1 — Definir o Escopo (Process Scope):** Antes de mapear tarefas, o agente deve identificar claramente o estado inicial (gatilho) e os estados finais (resultados de negócio).
*   **Passo 2 — Mapa de Alto Nível (High-Level Map):** Se a transcrição sugerir complexidade, o agente deve primeiro listar os **milestones** ou fases lógicas (5 a 10 passos).
*   **Passo 3 — Diagrama de Nível Superior (Top-Level):** Criar o fluxo principal usando subprocessos para esconder detalhes operacionais.
*   **Passo 4 — Expansão de Nível Filho (Child-Level Expansion):** Detalhar o conteúdo de cada subprocesso criado no passo anterior.
*   **Passo 5 — Fluxos de Mensagem (Message Flows):** Adicionar a comunicação entre pools distintos.

## 2. Implementação de Regras de Estilo Críticas (BPMN Style)
Devem ser adicionadas regras baseadas no Capítulo 6 para garantir a legibilidade ("Style Rules"):

*   **Regra de Densidade Cognitiva:** **Proibido** criar sequências lineares com mais de 10 atividades. O uso de **Subprocesses** torna-se obrigatório para manter cada nível com 5 a 10 nós .
*   **Nomenclatura Semântica:** Atividades devem seguir o padrão estrito de **[Verbo no Infinitivo] + [Objeto]** (ex: "Validar Crédito"). Subprocessos devem ter nomes que resumam o objetivo de toda a fase.
*   **Sincronização de Gateways:** Reforçar a regra de que caminhos abertos por um gateway de split (AND/OR) devem obrigatoriamente ser fechados por um join do mesmo tipo para garantir a integridade lógica.

## 3. Expansão para a Paleta Level 2 (Eventos e Iteração)
Enriquecer o `skill_bpmn.md` com conceitos avançados de execução e controle:

*   **Tratamento de Exceções (Events):**
    *   Implementar **Boundary Events** em subprocessos para tratar erros (Error Events) ou interrupções por tempo (Timer Events).
    *   Diferenciar claramente entre eventos que interrompem o fluxo e eventos que não interrompem (Non-interrupting).
*   **Repetição e Instâncias (Iteration):**
    *   Identificar padrões de "Para cada..." ou "Repetir até..." na transcrição e mapear como **Multi-instance Activity** ou **Loop Activity**.

## 4. Atualização do Checklist de Validação (Passo 6)
O checklist deve ser expandido para incluir critérios de qualidade do livro:

*   [ ] O diagrama de nível 1 cabe em uma "única página" (mentalmente) sem sobrecarga?
*   [ ] O uso de subprocessos foi aplicado para esconder detalhes que não alteram o fluxo principal?
*   [ ] Todos os **End States** (estados finais) representam resultados de negócio distintos e nomeados corretamente?
*   [ ] Gateways de decisão (is_decision: true) possuem rótulos em todas as saídas descrevendo a condição de negócio?

---

### Instrução para o Claude Code implementar no `skill_bpmn.md`:

> "Claude, atualize as instruções do `skill_bpmn.md` para seguir a metodologia **Top-Down** do livro 'BPMN Method and Style'. Substitua o fluxo atual pelos 5 passos de modelagem de Bruce Silver. Implemente uma regra rígida de densidade: sequências lineares com mais de 10 tarefas devem ser convertidas em **Subprocesses** lógicos (High-Level Map). Adicione suporte para **Loop/Multi-instance Tasks** e **Boundary Events** (Timer/Error) para capturar exceções descritas nas transcrições. Garanta que o checklist final valide não apenas a sintaxe JSON, mas a clareza hierárquica e a semântica dos nomes de eventos e atividades."