# Módulo 0 — Fundamentos do Process2Diagram

**Duração:** 1 hora
**Pré-requisito:** Acesso ao sistema com API key configurada

---

## Objetivo

Ao final deste módulo, o participante será capaz de:
- Configurar o provider LLM e o projeto ativo
- Entender o que cada agente do pipeline produz
- Interpretar o Grau de Qualidade A–E de uma transcrição
- Rodar um pipeline completo do zero

---

## Parte 1 — Por que documentar reuniões é difícil? (15 min)

### O problema

Em organizações típicas:
- **60–80% das decisões importantes** são tomadas em reuniões
- Menos de 20% das reuniões produzem ata formal
- Atas manuais levam de 30 minutos a 3 horas para serem redigidas
- Atas não incluem diagramas de processo ou estrutura de requisitos

O resultado: conhecimento perdido, retrabalho, processos não documentados
e rastreabilidade zero sobre o que foi decidido, por quem e quando.

### O que o P2D faz

Transforma uma transcrição de reunião em:

| Artefato | O que é |
|---|---|
| BPMN 2.0 | Diagrama de processo editável (bpmn-js, Bizagi, Camunda) |
| Mermaid | Fluxograma alternativo em texto |
| Ata | Markdown / Word / PDF com participantes, pauta, decisões, action items |
| Requisitos | IEEE 830 — funcional, não-funcional, interface, restrição |
| SBVR | Vocabulário de negócio + regras formais |
| BMM | Visão, missão, metas, estratégias, políticas |
| DMN | Tabelas de decisão |
| Relatório executivo | HTML interativo com todos os artefatos |

---

## Parte 2 — Configuração (10 min)

### Passo 1 — Escolher o provider LLM

Acesse **Configurações → Provedor LLM**. Para o curso, recomendamos:
- **DeepSeek V4 Flash** (padrão) — mais barato, bom para processos simples
- **Claude Sonnet** — melhor qualidade para processos complexos e SBVR

### Passo 2 — Criar um projeto

Acesse a **Home** e crie um projeto com o nome da sua empresa ou do curso.
Todas as reuniões do módulo devem ser salvas neste projeto.

### Passo 3 — Verificar configurações do pipeline

No painel lateral (sidebar), confirme que estão ativados:
- ✅ Quality Inspector
- ✅ BPMN Architect (3 execuções, Adaptive Retry ligado)
- ✅ Meeting Minutes
- ✅ Requirements
- ✅ SBVR (para módulos 3 e 6)
- ✅ BMM (para módulo 6)

---

## Parte 3 — Anatomia de uma Transcrição Boa (10 min)

O sistema avalia cada transcrição e atribui um Grau A–E:

| Grau | Significado | O que falta |
|---|---|---|
| **A** | Excelente | Nada — processar diretamente |
| **B** | Boa | Pequenos ruídos de transcrição |
| **C** | Aceitável | Partes do processo podem faltar |
| **D** | Fraca | Muitos trechos ininteligíveis |
| **E** | Inadequada | Transcrição muito incompleta |

### O que torna uma transcrição processável

✅ Participantes identificados por nome ou papel
✅ Sequência de atividades descrita ("primeiro... depois... se... então...")
✅ Condicionais explícitas ("se o valor for maior que X", "caso aprovado")
✅ Responsáveis nomeados ("a Ana fica responsável por...")
✅ Decisões registradas ("ficou decidido que...", "aprovamos...")
✅ Action items com prazo ("até sexta-feira", "antes da próxima sprint")

### O que prejudica a qualidade

❌ Transcrição de áudio automática sem revisão (muitos erros de ASR)
❌ Participantes não identificados ("alguém disse...")
❌ Processo descrito de forma circular ou incompleta
❌ Muitas siglas sem contexto

**Dica:** Use o botão **🧹 Pré-processar Transcrição** para limpar ruídos antes de rodar o pipeline.

---

## Parte 4 — Hands-on: Primeiro Pipeline (25 min)

### Exercício

1. Abra a transcrição `modulo_01_mapeamento_processos/transcricao_01a_aprovacao_fornecedor.txt`
2. Copie o conteúdo e cole na área de transcrição do pipeline
3. Clique em **🧹 Pré-processar** e observe o resultado
4. Execute o pipeline completo
5. Explore cada aba de resultado:
   - **BPMN** — identifique as lanes e os gateways
   - **Mermaid** — compare com o BPMN
   - **Ata** — verifique participantes, decisões e action items
   - **Requisitos** — quantos foram extraídos? De que tipos?
6. Salve a reunião no projeto criado no Passo 2

### Perguntas para discussão

- O Grau de Qualidade atribuído foi o esperado?
- O BPMN refletiu corretamente os três departamentos (Compras, Financeiro, Jurídico)?
- Os gateways de valor do contrato aparecem no diagrama?
- Algum requisito extraído surpreendeu o grupo?

---

## Referências

- Guia de Início Rápido: menu **Ajuda → Como Iniciar**
- Glossário técnico: menu **Ajuda → Glossário** (termos: BPMN, SBVR, IEEE 830, RAG)
- Arquitetura do pipeline: menu **Ajuda → Arquiteturas**
