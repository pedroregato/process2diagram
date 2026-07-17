# Revisão do plano — `AgentProvocations` (Fases 1–3)

> **Status: APLICADA em 2026-07-17 (PC190-fix), todos os 4 itens.**
>
> - **Item 1 (bloqueante):** corrigido. `grounding.absence_check.terms` substitui `absent_terms`,
>   obrigatório em `absence` E `asymmetry`. Nova primitiva `_span_text()` — span = transcrição
>   inteira (`absence`) ou janela estritamente entre as duas referências (`asymmetry`, derivada
>   delas, não de um span separado). Achado extra durante a implementação: os 6 padrões regex de
>   `modules/transcript_time_parser.py` (todos exigem `:` no fim da linha) não casam com o formato
>   real de `hub.transcript_clean` pós-Teams (`"Nome   0:03"`, sem dois-pontos) — confirmado
>   rodando `parse_transcript_timings()` contra um fixture real. Fix usa
>   `modules/transcript_preprocessor.py::_SPEAKER_LINE_PAT` como estratégia primária.
> - **Item 2:** allowlist de `kind` já estava em código desde a implementação inicial (não só no
>   prompt) — a alternativa mais limpa (não descrever os 5 tipos no skill) foi aplicada também.
> - **Item 3:** comentário registrado no `.sql`. Não existe documento de dívida técnica dedicado
>   no projeto ainda — só o comentário, conforme "nada mais nesta rodada".
> - **Item 4:** `tenant_id` mantido sem FK (decisão já correta, sem mudança). Taxa de reprovação
>   por motivo (`rejected_reasons`) logada estruturadamente — persistência dedicada (tabela/
>   telemetria própria) fica pra depois, era explicitamente opcional.
>
> Detalhes completos: entrada PC190 em `claude_guideline/roadmap.md`.

**Para:** Claude Code
**Sobre:** o plano de implementação derivado de `melhorias/agente-de-provocacoes.md`
**Veredito:** **aprovado com uma condição bloqueante** (item 1).

---

## Sumário

| # | Item | Severidade | Ação |
|---|---|---|---|
| 1 | Validador não audita a alegação dos tipos `absence` e `asymmetry` | 🔴 **Bloqueante** | Corrigir contrato + validador **antes** da Fase 2 |
| 2 | Allowlist de `kind` vive só no prompt | 🟠 Importante | Mover para o validador (1 linha) |
| 3 | `project_id → contexts(id)`: resíduo nascendo em tabela nova | 🟡 Registro | Manter a decisão, inscrever no inventário |
| 4 | `tenant_id` sem FK / métrica de reprovação só em log | 🔵 Menor | Opcional |

**O que não mexer.** A Fase 0 fez arqueologia real e o plano está melhor que a proposta original
em vários pontos. Ficam como estão, e a proposta é que deve ser corrigida:

- Rejeitar o padrão do `AgentCKFUpdater` por causa do `meeting_id=None` (PC137) e espelhar
  `run_knowledge_extraction()` — achado que só vem de ler o código.
- `AgentProvocations` / `agents/agent_provocations.py` (convenção real `Agent<Nome>` vence
  `ProvocationsAgent`, que eu havia escrito).
- Colunas e enums 100% em inglês (`meeting_id`, `title`, `body`, `grounding`, `status`...),
  conteúdo/UI em português — padrão de `AgentMinutes` → "Ata".
- Opt-in (`default_enabled: False`) em vez de default-on.
- Não executar a migration automaticamente.
- `rerun_handler` extra (não estava na proposta; regenerar provocações após editar a ata tem
  valor real).

---

## 1 — 🔴 O validador valida a decoração, não a alegação

### O problema

O plano especifica:

> *"confere cada referência de `grounding.references[].trecho` contra o transcript (match
> normalizado)"*

Isso verifica que **as citações existem**. Mas os dois tipos escolhidos para a Fase 1 não alegam
existência — alegam **ausência**:

| Tipo | O que a provocação **alega** | O que o validador **confere** |
|---|---|---|
| `absence` | "o termo X não ocorre em lugar nenhum" | Nada. Não há `references` para conferir — **passa direto** |
| `asymmetry` | "a objeção às 00:22:31 **nunca foi respondida** até a decisão às 00:41:07" | Que as duas citações existem — e existem, o modelo copiou do transcript. **O "nunca foi respondida" não é verificado** |

Consequência: um `asymmetry` factualmente falso passa no validador desde que as aspas estejam
corretas. O critério de pronto — *"provocação sem lastro nunca chega à UI"* — seria declarado
atingido sem estar. **Na Fase 2 entregaríamos um validador determinístico que aprova exatamente
as duas coisas que ele existe para auditar.**

### A correção (simplifica o código, não complica)

Ambos os tipos se reduzem a **uma primitiva única**: *"estes termos não ocorrem neste span"*.

- `absence` → span = transcrição inteira
- `asymmetry` → span = turnos entre a objeção e a decisão

### Contrato revisado de `grounding`

```jsonc
"grounding": {
  // presença — verificável por match normalizado
  "references": [
    {"timestamp": "00:22:31", "speaker": "João", "trecho": "se a nota já foi emitida"},
    {"timestamp": "00:41:07", "speaker": "Ricardo", "trecho": "Fechado então? Todo mundo de acordo."}
  ],

  // ausência — verificável por varredura de span. OBRIGATÓRIO em absence e asymmetry
  "absence_check": {
    "terms": ["estorno", "reembolso", "devolução do valor"],
    "span": "full"
    // ou: {"from": "00:22:31", "to": "00:41:07"}
  }
}
```

### Regras do validador (determinístico, sem LLM)

```
presença:
  para cada references[].trecho → match normalizado no transcript
  ausente → REPROVA

ausência:
  kind ∈ {absence, asymmetry} e absence_check faltando/vazio → REPROVA
  absence_check.terms vazio                                  → REPROVA
  span resolvido (full | janela entre timestamps)
  qualquer term ocorre no span                               → REPROVA

  span de asymmetry: from/to devem existir no transcript e from < to
```

### Por que isto é melhor, e não só mais correto

- **A alegação vira auditável.** É o objetivo declarado da proposta inteira.
- **Força o modelo a explicitar o que afirma não existir** — e é isso que torna a provocação
  discutível pelo humano na sala. *"Ninguém falou de estorno"* é uma alegação. *"Ninguém falou de
  estorno, reembolso ou devolução do valor, e aqui está o span"* é um argumento.
- **`asymmetry` deixa de exigir julgamento semântico.** "O tema foi endereçado?" era o ponto mais
  frágil da Fase 1. Vira busca de termos numa janela — o tipo mais simples dos dois.
- **UI ganha de graça.** O lastro exibido passa a mostrar os termos buscados e o span — o humano
  confere em dois segundos, sem reler a reunião.

### Impacto no plano

- `core/output_schemas.py` — `GroundingSchema` com `references` **e** `absence_check`.
- `agents/agent_provocations.py` — validador ganha o ramo de ausência.
- `skills/skill_provocations.md` — instruir a emissão de `absence_check` com **termos
  sinônimos**, não um só. Um único termo é uma alegação fraca e fácil de furar.
- `tests/test_agent_provocations.py` — casos novos:
  - `absence` sem `absence_check` → reprova
  - `absence_check.terms` vazio → reprova
  - termo **ocorre** no span → reprova
  - `asymmetry` com `from`/`to` inexistentes ou invertidos → reprova
  - termo ocorre **fora** do span mas não dentro → **aprova** (o caso que prova que o span funciona)

---

## 2 — 🟠 Allowlist de `kind` no validador, não só no prompt

O plano diz:

> *"Define os 5 `kind` na taxonomia mas instrui o modelo a só emitir `absence`/`asymmetry` nesta
> fase (via lista de tipos habilitados no prompt — não uma limitação de schema, que já aceita os 5)."*

**Prompt não é garantia.** Se o modelo emitir um `contradiction` — e ele vai, porque a taxonomia
inteira está no skill — o schema aceita, o validador não tem regra para aquele `kind`, e a
provocação chega à UI com um lastro que **ninguém consegue conferir**, já que a leitura de memória
do contexto não existe nesta fase. É o "ralo genérico" que a proposta proíbe, entrando pela porta
da configuração.

**Correção (uma linha):**

```python
ENABLED_KINDS = {"absence", "asymmetry"}   # Fase 1
# no validador, antes de qualquer outra checagem:
if item.kind not in ENABLED_KINDS:
    reject(item, reason="kind_not_enabled")
```

**Alternativa mais limpa, e recomendada:** não colocar os 5 tipos no skill desta fase. Descreva só
os dois. A taxonomia completa vive no documento de proposta, não no prompt — **o modelo não
precisa saber o que ainda não pode fazer**. Menos superfície, menos deriva.

Regra geral que vale registrar: **toda regra de segurança do agente existe em código; o prompt é
otimização, nunca garantia.** Vale para o allowlist, para o limite de 5 e para a lista negra de
tom (esta o plano já acertou ao pôr nos dois lugares).

---

## 3 — 🟡 `project_id → contexts(id)`: dívida nova, deliberada

O plano está **certo no mérito**: consistência com `asset_metadata` e `assistant_artifacts` ganha
de pureza. Não brigar com isso agora, e não introduzir um terceiro padrão.

Mas o registro importa. Foi definido que `projeto` → **contexto** já ocorreu no vocabulário do
produto — e a tabela `provocations` **nasce carregando o resíduo**. É dívida nova, criada
deliberadamente, num artefato que ainda não existe.

- ✅ Aceitável **se** entrar no inventário da renomeação global (`p2d` → Vichara, `projeto` →
  `contexto`, `project_id` → `context_id`).
- ❌ Inaceitável se for esquecido: daqui a um ano ninguém vai lembrar que `project_id` aponta para
  `contexts` por herança e não por design.

**Ação:** comentário no `.sql` e linha no documento de dívida técnica. Nada mais nesta rodada.

```sql
-- project_id → contexts(id): nome herdado. O termo de produto é "contexto".
-- Mantido por consistência com asset_metadata/assistant_artifacts.
-- Renomear para context_id no inventário da renomeação global. Não corrigir isoladamente.
```

---

## 4 — 🔵 Menores

### `tenant_id` denormalizado sem FK

O argumento ("não ser mais rígido que o precedente que estou copiando") é razoável e mantenho a
decisão. Registro apenas que ele **não compra nada agora**: RLS está habilitado *sem policy*, então
a coluna não serve a scoping nenhum, e `tenant_id` é derivável por join em `contexts`. É YAGNI com
risco de drift silencioso. Manter é defensável — só saiba que é aposta no futuro, não necessidade.

### Métrica de reprovação

O plano diz: *"loga contagem de reprovação (para métrica futura)"*.

A proposta pedia instrumentação **desde o dia 1**, e a razão é concreta: **a taxa de reprovação é o
sinal de alucinação**, e precisa ser observável antes do usuário notar. Log em stdout no Streamlit
Cloud é efetivamente invisível.

Sugestão mínima, sem tabela nova: persistir o agregado da rodada junto às provocações salvas.

```sql
-- em provocations, ou numa coluna jsonb de run metadata:
-- {"generated": 7, "rejected": 4, "reasons": {"grounding_missing": 2, "term_present": 1, "tone": 1}}
```

Se a taxa subir, o problema está no prompt — e você tem o sinal antes do usuário.

---

## Critérios de pronto revisados (substituem os do plano)

- [ ] **Nenhuma provocação de `kind` não habilitado chega à UI** — garantido em código, não no prompt.
- [ ] **`absence` e `asymmetry` sem `absence_check` válido são reprovados** — teste próprio para cada.
- [ ] **Termo presente no span reprova; termo presente fora do span não reprova** — o teste que prova a primitiva.
- [ ] Referência inexistente no transcript reprova.
- [ ] Lista negra de tom reprova.
- [ ] `confidence` fora de `high/medium` reprova.
- [ ] \> 5 aprovadas → ranqueia e corta.
- [ ] 0 aprovadas → resultado vazio **válido**, com mensagem própria na UI, não erro.
- [ ] Taxa de reprovação observável fora do stdout.
- [ ] Suite completa passando, sem regressão.

---

## Ordem sugerida

1. **Contrato primeiro.** `GroundingSchema` com `absence_check` + testes do validador — **antes**
   de escrever o skill. Se o contrato mudar depois, o prompt inteiro é retrabalho.
2. Validador determinístico com os dois ramos (presença/ausência) + allowlist.
3. Skill, descrevendo **apenas** `absence` e `asymmetry`.
4. Agente, persistência, UI — como o plano já descreve.

O resto do plano segue sem alteração.