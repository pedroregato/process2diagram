# Proposta de implementação — `ProvocationsAgent` (artefato: Provocações)

> **Status: IMPLEMENTADA em 2026-07-17 (PC190) — Fases 1-3, escopo `absence`/`asymmetry`.**
>
> Nome final: `AgentProvocations` (não `ProvocationsAgent` — convenção real do repo é
> `Agent<Nome>`), sem persona própria (colisão com "Vichara" do Assistente resolvida pelo
> autor numa 2ª revisão da própria proposta, antes da implementação). `docs/VICHARA-ESCOPO.md`
> referenciado no pré-requisito não existe no repositório — não foi possível ler.
>
> Orquestração não segue o padrão do `AgentCKFUpdater` sugerido implicitamente pela seção 6 —
> esse padrão só funciona pra CKF porque ele não precisa de `meeting_id` real. Provocações
> precisa, então roda via função standalone (`core/pipeline.py::run_provocations()`), mirror
> de `run_knowledge_extraction()`, chamada depois de `create_meeting()` existir (mesmo motivo
> do PC137).
>
> Um problema bloqueante real foi encontrado e corrigido depois da implementação inicial —
> ver `melhorias/arquivados/revisao-plano-provocacoes.md` e a entrada PC190 completa em
> `claude_guideline/roadmap.md`: o validador determinístico conferia PRESENÇA das citações,
> não a alegação de AUSÊNCIA que os dois tipos habilitados realmente fazem.
>
> Fases 4-6 (tipos `contradiction`/`premise`/`analogy`, o laço provocação→divergência) ficam
> para uma rodada futura — dependem de leitura de memória do contexto/domínio, fora do escopo
> desta implementação.

**Alvo:** Claude Code, neste repositório.
**Pré-requisito de leitura:** `docs/VICHARA-ESCOPO.md` (enquadramento de escopo).
**Tipo:** novo agente + novo artefato + nova tabela.
**Status:** proposta. Requer aprovação humana antes da implementação.

> **Nota de honestidade sobre esta proposta.** Ela foi escrita sem acesso ao código-fonte.
> Nomes de arquivos, classes e assinaturas abaixo são **hipóteses baseadas nos padrões conhecidos
> do repositório** e estão marcados com `⟨?⟩`. A primeira tarefa do agente é **verificar** cada
> hipótese contra o código real e reportar divergências antes de escrever qualquer linha.

---

## 1. O que se quer construir

Um agente de pipeline — **`ProvocationsAgent`** — que produz um novo artefato, **Provocações**,
a partir de uma reunião já processada, da **memória do contexto** e da **memória do domínio**.

### Nomenclatura (convenção do repositório — não violar)

**Nome humanizante é privilégio de quem conversa.** `Vichara` é o nome do **assistente**
(`⟨?⟩ agents/agent_assistant.py`), única superfície que dialoga com um humano. Todos os demais
agentes são maquinaria e recebem **nome funcional**, como os já existentes.

| | Nome | Por quê |
|---|---|---|
| Assistente (chat) | **Vichara** | Conversa. Nome descritivo do que ele é: investigação discriminativa |
| Este agente | **`ProvocationsAgent`** | Não fala. Gera artefato. Nome funcional |

As provocações **são atribuídas a Vichara na UI**. Não é inconsistência: é a mesma faculdade
discriminativa operando em outra superfície — síncrona no chat, assíncrona no artefato.
**Não crie uma segunda persona.** Um assistente, muitas faculdades.

> **Correção pendente detectada em `⟨?⟩ agent_assistant.py`:** a persona se apresenta como
> *"curador de conhecimento do {projeto}"*. Dois defeitos:
> 1. `{projeto}` está obsoleto → `{contexto}`.
> 2. **"curador" descreve a faculdade errada.** Curadoria é o que a promoção a Ativo de Negócio
>    faz — selecionar o que transcende o silo. Vichāra não cura: **discrimina**. Se o nome é a
>    tese, a autodescrição precisa acompanhá-la.
>
> Sugestão: *"Sou Vichāra. Investigo o que foi dito neste contexto — e o que não foi."*
> Tarefa separada desta proposta, mas de mesma origem.

> **Escopo de leitura do agente (regra dura):**
> `TODOS os artefatos do contexto da reunião` ∪ `Ativos de Negócio do domínio`.
>
> Note que o primeiro conjunto **não é filtrado por aceitação ou promoção** — todo artefato
> persiste automaticamente e compõe a memória do contexto. O agente lê a memória inteira do
> silo, não uma seleção dela. O segundo conjunto é curado por decisão humana e é o único que
> atravessa a fronteira do contexto.
>
> Isto tem uma consequência prática forte: **o cruzamento intra-contexto está disponível desde
> a segunda reunião**, sem depender de nenhuma promoção. Só a analogia e a contradição
> *cross-contexto* dependem de Ativos de Negócio existirem.

A provocação é uma observação sobre **o que ficou fechado sem ter sido visto**: o tema ausente,
a contradição no tempo, a premissa não examinada, a objeção sem resposta, a analogia estrutural.

É o par complementar do livro-razão de divergências pendentes: aquele registra o que ficou
**aberto e visível**; este aponta o que ninguém enxergou.

## 2. A restrição central (não é um detalhe de prompt)

**"Pensar fora da caixa sem alucinar" é uma restrição de arquitetura, não uma instrução de tom.**

> **Regra do lastro:** a provocação **não cria conteúdo**. Ela aponta para algo que já está no
> material e que ninguém olhou. Toda provocação carrega evidência verificável:
> citação + timestamp, ID de artefato do domínio, ou afirmação de ausência checável.
>
> **Provocação sem lastro não sai.** Isto é validado em código, não confiado ao modelo.

Razão dupla:
- **Técnica:** elimina alucinação por construção, não por sorte do prompt.
- **Política:** provocação com evidência é discutível. Sem evidência, é opinião de máquina — e
  numa sala sênior ou é descartada em dois segundos, ou é aceita por deferência tecnológica
  (que é pior: seria o discurso poderoso trocando de trono, não sendo desmontado).

## 3. Taxonomia — os cinco tipos permitidos

O agente só emite provocações que se encaixem em um destes tipos. Cada tipo tem um **lastro
característico** e um **método de verificação**.

| # | Tipo | `kind` | Lastro exigido | Verificação em código |
|---|---|---|---|---|
| 1 | **Ausente estrutural** | `ausencia` | Lista de termos buscados + contagem 0 | Busca literal/normalizada no transcript. Rejeita se algum termo ocorrer |
| 2 | **Contradição no tempo** | `contradicao` | ID de artefato da memória do contexto **ou** de Ativo de Negócio + trecho da reunião | ID está no escopo de leitura permitido; trecho localizado no transcript |
| 3 | **Premissa não examinada** | `premissa` | Timestamp único de origem + ausência de contestação | Trecho existe; contagem de menções ≤ limiar |
| 4 | **Assimetria discursiva** | `assimetria` | Timestamp da objeção + timestamp da decisão | Ambos existem; nenhum turno intermediário cita o tema |
| 5 | **Analogia estrutural** | `analogia` | ID do artefato análogo | ID está no escopo permitido. **Analogia cross-contexto só é possível via Ativo de Negócio** — é o caso de maior valor do tipo 5 |

**Intra-contexto vs. cross-contexto.** Os tipos 2 e 3 operam nos dois modos. Intra-contexto,
lastreiam na memória do contexto e funcionam desde a segunda reunião. Cross-contexto, só
lastreiam em Ativo de Negócio. O tipo 5 é quase sempre cross — e é o único tipo que produz uma
observação que **nenhum humano na sala poderia ter feito**.

> **Instrução dura:** não adicione um tipo `insight` ou `sugestao` genérico. Ele seria o
> ralo por onde a alucinação entra. Se uma observação não cabe nos cinco tipos, ela não é emitida.

## 4. Contrato de saída

```json
{
  "provocacoes": [
    {
      "kind": "assimetria",
      "titulo": "Objeção fiscal não respondida antes do fechamento",
      "corpo": "A objeção sobre nota fiscal já emitida foi levantada e não recebeu resposta. A decisão foi declarada fechada 18 minutos depois.",
      "pergunta": "A emissão prévia da nota foi considerada ao fechar o prazo de 24h?",
      "lastro": {
        "tipo": "turnos",
        "referencias": [
          {"timestamp": "00:22:31", "falante": "João", "trecho": "se a nota já foi emitida a gente não consegue"},
          {"timestamp": "00:41:07", "falante": "Ricardo", "trecho": "Fechado então? Todo mundo de acordo."}
        ],
        "ativos_negocio": [],
        "artefatos_contexto": [],
        "termos_ausentes": []
      },
      "confianca": "alta"
    }
  ]
}
```

Regras do contrato:
- `corpo` é **descritivo**, nunca acusatório.
- `pergunta` é obrigatória e é o que vai à pauta. Formato que abre espaço, não que cobra.
- `lastro` é obrigatório e **não pode ser vazio** em nenhum campo relevante ao `kind`.
- `confianca` ∈ `alta | media`. **Não existe `baixa`** — se é baixa, não emite.

### Disciplinas de saída

- **Volume máximo: 5 provocações.** Vinte viram ruído e o humano desiste de ler; três certeiras
  mudam a reunião seguinte. Se o modelo produzir mais, ranqueie e corte.
- **Zero é resultado válido e deve ser exibido como tal.** Um agente que se cala quando não tem
  nada a dizer é o comportamento correto — e, convenientemente, o mais fiel ao nome.
- **Tom:** proibido `"vocês ignoraram"`, `"a equipe falhou"`, `"deveriam ter"`. A provocação
  eficaz é a que pode ser aceita sem que ninguém perca a face. Isto entra no skill como regra
  explícita **e** como checagem de lista negra no validador.

## 5. Pipeline de duas passagens

```
  Transcript + memória do contexto (todos os artefatos) + Ativos de Negócio do domínio
        │
        ▼
  [1] GERAÇÃO      ProvocationsAgent, skill própria, saída JSON
        │
        ▼
  [2] VALIDAÇÃO DE LASTRO   ← código puro, sem LLM
        │   · cada referência existe no transcript? (match normalizado)
        │   · cada ID citado está no escopo de leitura permitido?
        │     (contexto da reunião, ou Ativo de Negócio do domínio — nada além)
        │   · cada termo_ausente realmente não ocorre?
        │   · tom passa na lista negra?
        │   · confianca ≠ baixa?
        │
        ├─ reprovadas ──► descartadas + logadas (métrica de alucinação)
        └─ aprovadas  ──► ranqueadas, cortadas em 5, persistidas
```

**A passagem [2] é o coração da proposta.** Ela é determinística e barata. Não a substitua por
um "agente validador" — validar existência de string não é tarefa para LLM. Um LLM validando
outro LLM só multiplica o custo e a superfície de alucinação.

**Métrica de saúde a instrumentar desde o dia 1:** taxa de reprovação por lastro. Se subir,
o problema está no prompt, e você tem o sinal antes do usuário.

## 6. Integração com a arquitetura existente

Verificar cada item antes de implementar:

- **⟨?⟩ Orquestração.** Nunca instanciar o agente diretamente. Registrar no `Orchestrator` e
  invocar pelo caminho canônico / `handle_rerun()`, como os demais agentes.
- **⟨?⟩ Estado.** As provocações entram no `KnowledgeHub` como mais um artefato. Salvar o hub em
  `session_state` **antes** de renderizar qualquer widget.
- **⟨?⟩ Skill.** Novo arquivo no padrão `SKILL.md` com carregamento progressivo, seguindo os
  demais. **Incluir a regra de consistência de idioma de saída** — o mesmo tratamento aplicado
  aos 14 skills existentes.

  **Abrir o skill com esta doutrina** (é a formulação mais precisa da restrição do lastro):

  > *O rishi não compôs o mantra — ele o viu. O que já estava lá foi percebido por quem tinha o
  > olho para percebê-lo. Você não cria a provocação. Você a vê no material, e mostra a quem não
  > viu. Se não está lá, não existe.*

  Isto é instrução de comportamento, não nome de agente. O agente continua sendo
  `ProvocationsAgent`.
- **⟨?⟩ Persistência.** Nova tabela Supabase. Manter o padrão de UPDATE isolado por grupo.
  Esboço:

  ```sql
  -- ⟨?⟩ conferir convenção de nomes e de FK do projeto
  create table provocacoes (
    id            uuid primary key default gen_random_uuid(),
    reuniao_id    uuid not null references ⟨?⟩,
    contexto_id   uuid not null references ⟨?⟩,   -- silo: SDEA, Projeto Aurora...
    dominio_id    uuid not null references ⟨?⟩,   -- a corporação: FGV. Denormalizado para RLS/scoping
    kind          text not null check (kind in ('ausencia','contradicao','premissa','assimetria','analogia')),
    titulo        text not null,
    corpo         text not null,
    pergunta      text not null,
    lastro        jsonb not null,
    confianca     text not null check (confianca in ('alta','media')),
    estado        text not null default 'nova'
                  check (estado in ('nova','aceita','descartada','vira_divergencia')),
    created_at    timestamptz default now()
  );
  ```

- **Provider LLM.** O provider Anthropic **não tem suporte a `json_mode`**. A saída estruturada
  sai por prompt + parsing defensivo (strip de cercas ```json, parse tolerante). Não presuma
  `json_mode` disponível em nenhum caminho.
- **⟨?⟩ Página Streamlit.** `sys.path.insert` no topo. **Não aninhar `st.expander`** — a lista de
  provocações com lastro expansível é exatamente a tentação onde isso quebra. Use um único nível
  de expander, ou renderize o lastro inline.
- **Modelo.** `deepseek-chat` está em depreciação (24/07/2026). Este agente deve nascer já
  apontando para o alvo da migração (`deepseek-v4-flash`) ou para o modelo default vigente na
  data da implementação — **verificar antes de fixar**.

## 7. O laço que fecha o valor

Uma provocação aceita pelo humano tem dois destinos, e **os dois já existem no modelo conceitual**:

1. **Vira divergência pendente** — entra no livro-razão e passa a atravessar reuniões.
2. **Vira item de pauta** — a `pergunta` alimenta a pauta da reunião seguinte.

> Sem esse laço, o artefato é uma curiosidade. Com ele, é o mecanismo que transforma reunião
> isolada em trajetória — que é a tese inteira do produto.

O estado `vira_divergencia` no schema existe para isso. Se o livro-razão de divergências ainda
não estiver implementado, **implemente o agente com o estado previsto e o destino desligado**,
para não criar dívida de migração.

## 8. Fases

| Fase | Entrega | Critério de pronto |
|---|---|---|
| **0** | Verificação de hipóteses `⟨?⟩` contra o código | Relatório de divergências, sem código escrito |
| **1** | Skill + agente, tipos 1 e 4 (`ausencia`, `assimetria`) — lastro só no transcript | Rodam sobre transcript, saída no contrato |
| **2** | Validador de lastro determinístico + métrica de reprovação | Provocação sem lastro **nunca** chega à UI |
| **3** | Persistência + UI (lista, aceitar/descartar) | Estado sobrevive a rerun e a reload |
| **4** | Tipos 2 e 3 (`contradicao`, `premissa`) **intra-contexto** — lastro na memória do contexto | Cruza com artefatos de reuniões anteriores do mesmo contexto |
| **5** | Tipo 5 (`analogia`) e casos **cross-contexto** dos tipos 2 e 3 | Lastro em Ativo de Negócio valida; **nenhum ID fora do escopo permitido passa** |
| **6** | Laço: provocação aceita → divergência / pauta | Ciclo reunião→reunião demonstrável |

**Comece pelos tipos 1 e 4.** São os de lastro mais verificável (ausência de termo e distância
entre turnos), dependem apenas do transcript, e provam a arquitetura antes de qualquer
complexidade semântica.

**A fase 4 não depende de promoção.** Como todo artefato persiste automaticamente, a memória do
contexto existe a partir da segunda reunião. Contradição e premissa intra-contexto são
demonstráveis muito antes de o mecanismo de Ativos de Negócio estar maduro — o que torna esta
a fase de maior retorno por esforço. A promoção só é pré-requisito da fase 5.

## 9. Definição de pronto do experimento

- [ ] Uma reunião real produz entre 0 e 5 provocações.
- [ ] 100% das provocações exibidas têm lastro que **abre e é verificável pelo humano na UI**.
- [ ] A taxa de reprovação no validador está instrumentada e visível.
- [ ] Nenhuma provocação usa linguagem acusatória.
- [ ] Uma provocação aceita gera um item que sobrevive à reunião.
- [ ] O caso "nada a dizer" é exibido com dignidade, não como erro ou vazio.

## 10. Anti-requisitos (o que **não** fazer)

- ❌ Não classificar a reunião para decidir se as provocações são geradas. **Sempre gera.**
- ❌ Não emitir sugestão, opinião ou recomendação sem lastro. O agente não aconselha: discrimina.
- ❌ Não intervir ao vivo. Este agente é assíncrono, por decisão de produto.
- ❌ Não usar LLM para validar lastro.
- ❌ Não deixar o agente ranquear por "interesse". Ranqueia por confiança + verificabilidade.
- ❌ Não expor provocação reprovada "com aviso". Reprovada é descartada.
- ❌ Não dar nome próprio ou persona a este agente. Nome humanizante é privilégio do assistente,
  a única superfície que conversa. Panteão de agentes com nome confunde o usuário sobre com quem
  ele está falando.
- ❌ **Não ler artefato não promovido de outro contexto.** O agente enxerga entre contextos
  apenas o que foi deliberadamente promovido a Ativo de Negócio. Vazamento aqui não é bug de
  qualidade — é quebra de confidencialidade entre silos da corporação.

---

**Aprovação humana necessária antes da Fase 1.** A Fase 0 (verificação) pode prosseguir sem
aprovação adicional.