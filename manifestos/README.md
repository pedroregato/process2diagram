# 📜 Central de Governança — Manifestos P2D

Bem-vindo à camada de **Diretrizes e Governança Macro** do *Process2Diagram (P2D)*.

Diferente da pasta `skills/`, que guarda as instruções técnicas e prompts operacionais de execução dos agentes individuais, esta pasta reúne os **contratos canônicos e filosofias arquiteturais** que regem o ecossistema como um todo.

Estes documentos servem como a **memória institucional imutável** do projeto. Eles balizam as tomadas de decisão e garantem que qualquer nova inteligência artificial (ou engenheiro humano) integrada ao ecossistema opere sob o mesmo nível de rigor corporativo e segurança.

---

## 🗺️ Mapa dos Manifestos

| Arquivo | Público-Alvo | Função Estratégica |
| :--- | :--- | :--- |
| **`PRODUCT_MANIFESTO.md`** | Todos (IAs e humanos) | *(v1.0 — ASSINADO, PC196)* Filosofia de negócio — o **porquê** e o **o quê** do produto. Responde a pergunta que os demais manifestos não respondem: reunião como o ativo, artefatos como espelhos não-gateados, as duas memórias (contexto automático × domínio por promoção), a regra do lastro, e a identidade de Vichāra. Decisão de *produto* consulta este documento primeiro; decisão de *implementação* continua no `ENGINEERING_MANIFESTO`. |
| **`COLLABORATIVE_MANIFESTO.md`** | Engenheiros e IAs | Define a cultura de cooperação multiagente. Estabelece a esteira assíncrona de produção entre o *Antigravity* (Arquiteto), o *Claude Code* (Operário) e o *Engenheiro Humano* (Diretor de Orquestra). |
| **`ENGINEERING_MANIFESTO.md`** | Stakeholders e Devs | Documenta o blueprint de arquitetura, a matriz de pesos do pipeline (PC107), os mecanismos de segurança de API Keys, proteção de concorrência global e as políticas estritas de sanitização de PII (LGPD Default). |
| **`CONTINUIDADE_ARQUITETURAL.md`** | Governança e IAs | Estabelece o protocolo de blindagem de ritmo contra pontos únicos de falha cognitiva (SPOF). Ensina os agentes de terminal a assumirem a postura de um Arquiteto Sênior caso ocorram interrupções em APIs ou limites de cotas externas. |

---

## 🧠 Como as IAs Utilizam Esta Pasta

O ecossistema P2D utiliza um sistema de **auto-memory de inicialização** através do arquivo `CLAUDE.md` na raiz do projeto.

Toda nova sessão aberta por um agente de desenvolvimento (como o *Claude Code* ou o *Antigravity*) realiza uma varredura obrigatória nesta pasta para:

1. **Adotar Postura:** Mudar o comportamento de mero codificador de scripts para Guardião da Arquitetura Comercial.
2. **Prevenir Regressões:** Validar se uma alteração proposta em banco de dados ou endpoints viola alguma regra de segurança descrita no `ENGINEERING_MANIFESTO.md`.
3. **Garantir Consistência:** Manter o fluxo de escrita de código isolado de estados de interface gráfica, respeitando o desacoplamento nativo da plataforma.

---

## 📚 Ordem de Leitura Recomendada

Para uma integração eficaz ao ecossistema, recomenda-se a leitura nesta sequência:

```
1. PRODUCT_MANIFESTO.md         → Entender o quê e por quê (a alma do produto)
2. COLLABORATIVE_MANIFESTO.md   → Entender os papéis e o fluxo de trabalho
3. ENGINEERING_MANIFESTO.md     → Absorver os princípios técnicos e de segurança
4. CONTINUIDADE_ARQUITETURAL.md → Conhecer o protocolo de resiliência e substituição
```

Após a leitura dos manifestos, consulte os documentos companheiros na raiz:

| Documento | Função |
| :--- | :--- |
| `CLAUDE.md` | Restrições de runtime, estrutura do repositório, pitfalls conhecidos |
| `memory/project_state.md` | Estado atual do projeto — versão, PCs concluídos, migrations aplicadas |
| `memory/MEMORY.md` | Índice leve de sessão — links rápidos para referências críticas |
| `claude_guideline/roadmap.md` | Histórico completo de entregas (PC1 em diante) |

---

## ✏️ Regras de Versionamento e Edição

Cada manifesto possui uma versão declarada no cabeçalho do documento. Ao propor alterações:

1. **Bumpar a versão** no cabeçalho do manifesto modificado.
2. **Registrar a mudança** em `memory/project_state.md` com o código PC correspondente.
3. **Não remover regras estabelecidas** — apenas adicionar ou refinar. Remoções exigem aprovação explícita do Engenheiro Humano.
4. **Atualizar o `CLAUDE.md`** caso a mudança altere algum comportamento de runtime esperado dos agentes.

---

> ⚠️ **Regra de Ouro de Edição:**
> Nenhuma regra contida nestes manifestos pode ser alterada ou removida de forma automática por uma IA sem a arbitragem expressa e o critério de aceite do **Engenheiro Humano**. Eles representam as leis fundamentais do produto.
