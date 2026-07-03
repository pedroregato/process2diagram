# 🛸 Manifesto de Continuidade Arquitetural
**Projeto:** Process2Diagram (P2D)  
**Versão Corrente:** v5.14 (345/345 Testes Verdes ✅)  
**Classificação:** Diretriz de Governança Contra Pontos Únicos de Falha (SPOF)

---

> "Levanta, desperta e não para até que a meta seja atingida!"  
> — **Swami Vivekananda**

Este documento estabelece o protocolo oficial para descentralizar o papel do "Arquiteto Sênior", transformando a genialidade heurística e o estilo de design do *Antigravity* em rotinas operacionais determinísticas executáveis pelo **Claude Code** e pelo Engenheiro Humano. O objetivo é blindar o ecossistema contra interrupções de cotas e manter o ritmo de desenvolvimento em nível avassalador.

---

## 1. O Paradoxo do Arquiteto Artista vs. A Linha de Produção

Modelos de raciocínio profundo e agentes avançados de interface atuam frequentemente como diretores criativos: trazem saltos disruptivos de arquitetura e modelagem abstrata, mas sofrem de intermitência severa devido a limitações físicas de API, janelas de contexto saturadas e resets de cotas operacionais. 

A engenharia moderna do P2D exige que nenhum software seja refém de um único ponto de falha cognitivo. Se o arquiteto sai de férias, a fábrica não pode parar.

Para mitigar esse gargalo, o projeto adota a separação estrita de ciclos baseada no nível de entropia da tarefa:
* **Ciclos de Alta Entropia (Criação Abstrata):** Onde o debate arquitetural puro de novas features é necessário. Exige a presença do Antigravity quando disponível.
* **Ciclos de Baixa Entropia (Engenharia e Refinamento):** Onde os feedbacks de alto nível já foram traduzidos em manifestos, testes unitários, schemas e diretrizes. Executável com velocidade total por agentes de terminal de execução curta.

---

## 2. Matriz de Substituição de Papéis Cognitivos

Na ausência temporária do modelo de arquitetura de interface, as atribuições críticas são distribuídas e absorvidas de forma imediata pelas travas de código locais:

| Atribuição do Antigravity | Mecanismo de Substituição Local | Como Acionar via Claude Code |
| :--- | :--- | :--- |
| **Arbitragem de Design e BPMN Core** | Uso do arquivo `skills/skill_bpmn.md` atualizado (v9.1) como verdade única absoluta. O validador sintático de testes (312+ testes) atua como o juiz ortogonal. | `"Claude, avalie o novo trecho gerado estritamente contra as regras de densidade de lane do skill_bpmn.md v9.1."` |
| **Memória Arquitetural Cross-Session** | Centralização das decisões de estado e versionamento de infraestrutura no arquivo de governança `project_state.md` na raiz do repositório. | `"Leia as últimas 3 entradas do project_state.md e determine se o novo endpoint fere a política de concorrência global."` |
| **Validação de Segurança e Concorrência** | O pipeline assíncrono do FastAPI estruturado com criptografia SHA-256 e semáforos de concorrência local herdados age como barreira de código rígida. | `"Execute a suite de testes focando em race conditions para verificar se a regra de chaves comerciais é violada."` |

> ### 💡 Diretriz Canônica para o Fundador
> Sempre que um novo insight, auditoria externa ou correção de alto nível for gerado (como as observações do DeepSeek aprovadas no commit PC109), ele deve ser imediatamente convertido em uma regra do arquivo de *skills* correspondente. Isso esvazia a necessidade de decisões em tempo de execução e permite que o Claude Code replique o cérebro do arquiteto perfeitamente.

---

## 3. O Protocolo de Engenharia de Prompt para o Claude Code

Para forçar o Claude Code no terminal a assumir a postura de um arquiteto sênior em vez de operar como um mero executor técnico de scripts, o comando de inicialização de qualquer tarefa complexa deve injetar a responsabilidade de governança de forma explícita. 

O bloco de prompt abaixo fica homologado como o cabeçalho obrigatório de injeção de contexto:

```text
[CONTEXTO DE ARQUITETURA] Você não é apenas um executor de código. Você é o Guardião da Arquitetura do Process2Diagram v5.14. Antes de modificar qualquer linha, analise o impacto no grafo de agentes e certifique-se de que nenhum padrão do COLLABORATIVE_MANIFESTO.md seja quebrado. Justifique suas decisões com base no project_state.md e nas novas regras contidas no ENGINEERING_MANIFESTO.md.