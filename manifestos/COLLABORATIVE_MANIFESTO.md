# 🛸 Manifesto de Arquitetura Colaborativa (Multi-Agente + Humano)
**Projeto:** Process2Diagram (P2D)  
**Data:** Junho de 2026

## 1. Visão Geral do Ecossistema
O desenvolvimento do P2D opera sob um modelo híbrido de cooperação especializada, onde inteligências artificiais com diferentes interfaces e pontos fortes colaboram de forma assíncrona com a supervisão do Engenheiro Humano.

## 2. Divisão de Papéis e ROI (Retorno sobre Investimento)

### 🏛️ Antigravity (O Arquiteto de IA)
- **Perfil:** Interface visual, agnóstico a modelos (Gemini 3.5, Claude Thinking, GPT-OSS).
- **Missão:** Design de alto nível, descoberta arquitetural, análise macro de governança, resolução de desalinhamentos de contexto e documentação complexa.
- **Output:** Documentos de design e arquivos estruturais posicionados em `drafts/`.

### 🦾 Claude Code (Terminal CLI) (O Operário de Elite)
- **Perfil:** Execução direta via terminal, focado na família Claude Sonnet/Opus, integrado ao interpretador local.
- **Missão:** Escovação de bits, escrita pesada de código, integração de sistemas, execução de testes unitários (`pytest`), automação e refatorações massivas em cascata.
- **Output:** Código de produção testado e movimentação de blueprints para `drafts/arquivadas/`.

### 🎛️ Engenheiro Humano (O Diretor de Orquestra)
- **Missão:** Fornecer a intenção real de negócio, arbitrar decisões de arquitetura, aprovar patches de código (segurança *Default* no Antigravity) e garantir os critérios de aceitação.

## 3. Dinâmica de Cooperação Sem Fricção
1. O Humano e o Antigravity discutem e projetam a solução conceitual. O Antigravity salva o esqueleto em `drafts/modulo_draft.py`.
2. O Humano aciona o Claude Code no terminal do PyCharm com o contexto do draft estabelecido.
3. O Claude Code lê o draft, codifica a solução real no sistema, roda os testes locais e move o rascunho para `drafts/arquivadas/`.
4. O ciclo se fecha com o Git guardando o estado final da entrega.

## 🧠 4. Gerenciamento de Memória de Longo Prazo e Estados
Para mitigar a falta de memória nativa entre sessões e evitar o truncamento de contextos longos (limite de ~200 linhas por bloco de carregamento automático), o ecossistema P2D adota a seguinte estrutura de arquivos vivos na raiz e em `melhorias/`:

- **`CLAUDE.md`:** Fonte da verdade para restrições técnicas vigentes, estrutura do repositório e regras rígidas de runtime.
- **`MEMORY.md`:** Índice leve e de alta scannability com o estado atual da sprint.
- **`project_state.md` (e notas em `melhorias/`):** Onde as decisões arquiteturais profundas, logs de refatoração (como o desacoplamento do Streamlit na API) e históricos de banco são detalhados.

**Diretriz para Todos os Agentes (Antigravity e Claude Code):** Ao iniciar QUALQUER nova sessão ou tarefa, a leitura e a atualização cruzada desses três arquivos de memória são OBRIGATÓRIAS para garantir a continuidade histórica e evitar regressões de código.

---
*Regra de Ouro: Nenhum agente anula o outro. Nós somamos a capacidade analítica visual com a eficiência bruta de terminal.*