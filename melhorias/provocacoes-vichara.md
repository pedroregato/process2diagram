Excelente. Aqui está o plano completo, estruturado por tipo de provocação, com estimativas de esforço e ordem de implementação sugerida.

---

# 🪷 Plano de Melhoria — Vichāra Provocador

**Objetivo:** Dotar o Assistente Vichāra de capacidade plena para os 5 tipos de provocação investigativa, com ferramentas dedicadas e sem depender de prompting manual do usuário.

---

## 📦 Fase 1 — Fundação Compartilhada (pré-requisito para todos os tipos)

### 1.1 — Nova tabela: `provocations_log`

```sql
CREATE TABLE provocations_log (
    id              uuid PK DEFAULT gen_random_uuid(),
    project_id      uuid FK→projects NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('ausencia','contradicao','premissa','assimetria','analogia')),
    title           text NOT NULL,                         -- Título curto da provocação
    description     text NOT NULL,                         -- Texto completo da provocação
    evidence_refs   jsonb DEFAULT '[]'::jsonb,             -- [{type, id, snippet, meeting}]
    severity        text DEFAULT 'info' CHECK (severity IN ('info','alerta','critico')),
    status          text DEFAULT 'open' CHECK (status IN ('open','dismissed','addressed')),
    created_at      timestamptz DEFAULT now()
);
```

**Uso:** Persiste as provocações geradas, evitando repetição na mesma sessão e permitindo rastreamento. O Vichāra consulta antes de provocar: *"Já provoquei isso? Foi ignorado ou resolvido?"*

### 1.2 — Nova ferramenta: `provoke(phrase, kind)`

Tool simples que valida o lastro exigido descrito na tabela que você forneceu, registra na `provocations_log` e renderiza um **card visual** no chat — exatamente como os cards de contradição de requisitos, mas com ícone 💡 e borda colorida por tipo.

---

## 🧩 Fase 2 — Tipo 1: Ausência Estrutural

### Problema atual
Não existe um **modelo de referência** do que *deveria* estar presente no projeto. Sem isso, não consigo saber o que está faltando.

### Solução: `detect_missing_topics(domain_hint?)`

**Funcionamento:**
1. Lê o CKF do projeto (`get_ckf()`) para extrair o domínio/contexto
2. Para cada reunião com ata, extrai um *esqueleto de tópicos* (headings da ata, termos SBVR recorrentes, issues IBIS)
3. Cruza contra um **catálogo de expectativas** — um mapa do que um projeto daquele domínio *normalmente* discute
4. Retorna uma lista de tópicos esperados que não aparecem em nenhuma reunião

**Catálogo de expectativas:** pode ser:
- Um arquivo YAML/JSON em `config/provocation_domains.yaml` com categorias por domínio (ex: `auditoria`, `saude`, `logistica`) — alimentado por Ativos de Negócio
- Ou, inicialmente, uma consulta LLM única que, dado o domínio, sugere 5–10 tópicos canônicos

**Parâmetros:**
- `domain_hint` (opcional) — nome do domínio para lookup no catálogo
- `min_meetings` — mínimo de reuniões para considerar o projeto maduro (padrão: 3)

**Exemplo de saída:**
> ⚠️ **Ausência Estrutural**
> O projeto **SDEA** (Auditoria) nunca mencionou **"backup"** , **"plano de contingência"** ou **"retenção de logs"** em nenhuma das 30 reuniões. Temas esperados para um sistema de documentos eletrônicos com compliance.

**Esforço:** ~4h (catálogo + ferramenta + integração com provocations_log)

---

## 🧩 Fase 3 — Tipo 2: Contradição no Tempo

### Problema atual
`detect_requirement_contradictions()` e `list_kh_contradictions()` já fazem parte do trabalho, mas são **reativos** (só rodam quando chamados) e não cruzam com **proveniência temporal** explícita.

### Solução: `provoke_temporal_contradictions(scope?)`

**Funcionamento:**
1. Para cada par de reuniões consecutivas (ou para o par mais distante indicado), extrai fatos do Knowledge Hub de cada uma
2. Alimenta um LLM com o prompt: *"Estes fatos são contraditórios? Se sim, qual foi a decisão posterior que reverteu a anterior?"*
3. Retorna pares (reunião_A, fato_X) ↔ (reunião_B, fato_Y) com citação textual

**Melhoria sobre o atual:**
- Atual: `detect_requirement_contradictions` → só requisitos
- Novo: varre **kh_facts** + **sbvr_rules** + **minutes** (decisões de atas) — escopo ampliado

**Parâmetros:**
- `scope` = `"requirements" | "facts" | "rules" | "all"` (padrão `"all"`)
- `window` = número de reuniões para trás (padrão: todo o projeto)

**Esforço:** ~3h (nova ferramenta + integração com kh_facts + llm prompt)

---

## 🧩 Fase 4 — Tipo 3: Premissa Não Examinada

### Problema atual
Nenhuma ferramenta identifica *afirmações que foram aceitas sem questionamento*. O sistema hoje trata "disse e ninguém contestou" como consenso, não como risco.

### Solução: `detect_unexamined_premises(meeting_number?)`

**Funcionamento:**
1. Analisa a transcrição de uma reunião com spaCy + regex em busca de **assertivas categóricas** — padrões como:
   - *"é óbvio que..."*, *"todo mundo sabe que..."*, *"não precisa nem discutir..."*
   - *"vamos assumir que..."* seguido de decisão sem contraposição
   - Afirmações no presente do indicativo seguidas de *"certo?"*, *"ok?"* sem resposta
2. Para cada candidata, verifica o **turno de fala seguinte** (ou os 3 seguintes):
   - Há contraposição? Discordância? Pergunta de esclarecimento?
   - Se não → **premissa não examinada**
3. Cruza com o Knowledge Hub: se a "premissa" contraria um fato já estabelecido em reunião anterior, sobe severidade para **crítico**

**Regras de detecção (arquivo YAML configurável):**
```yaml
premise_markers:
  - "vamos assumir"
  - "é claro que"
  - "todo mundo sabe"
  - "obviamente"
  - "não precisa discutir"
  - "sem dúvida"
  - "é fato que"
```

**Exemplo de saída:**
> 💡 **Premissa Não Examinada**
> Na Reunião 18, Pedro afirmou: *"é claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."* — ninguém contestou. Porém, na Reunião 12, a decisão foi que o Catálogo Mestre seria independente. **Premissa contraria decisão anterior e não foi debatida.**

**Esforço:** ~6h (detecção por marcadores + análise de turnos + cruzamento KH)

---

## 🧩 Fase 5 — Tipo 4: Assimetria Discursiva

### Problema atual
Não há rastreamento de *"alguém objetivou, mas a decisão foi tomada sem endereçar a objeção"*.

### Solução: `detect_discursive_asymmetry(meeting_number?)`

**Funcionamento:**
1. Para cada issue IBIS (`search_ibis_debates`), extrai:
   - **Alternativas propostas** (cada uma com seus prós/contras)
   - **Resolução** (qual alternativa foi escolhida)
2. Para cada alternativa **não eleita**, verifica se houve debate com objeções registradas
3. Se houve objeção **registrada mas não rebatida** → assimetria
4. Se a alternativa eleita **não teve contraposição alguma** (ninguém questionou) → assimetria também (conversa com Tipo 3)

**Melhoria estrutural necessária no modelo IBIS:**
Adicionar à tabela `ibis_alternatives` (se existir) ou criar metadado:
```json
{
  "objections": [{"text": "...", "responded": false, "responded_by": null}],
  "decision_rationale": "string"
}
```

**Ferramenta complementar:** `get_ibis_asymmetries()` — varre todas as issues e retorna as com objeções não respondidas.

**Esforço:** ~5h (extensão modelo IBIS + nova ferramenta + LLM para classificar objeções não respondidas)

---

## 🧩 Fase 6 — Tipo 5: Analogia Estrutural

### Problema atual
A `cluster_topic_decisions()` já agrupa temas, mas não **compara estruturas de decisão entre reuniões** para sugerir analogias. O cross-contexto via Ativo de Negócio é o caso de maior valor, como você destacou.

### Solução: `suggest_structural_analogies(scope?)`

**Funcionamento:**
1. Para cada issue IBIS, extrai:
   - **Estrutura de branching:** quantas alternativas, quais critérios pesaram, quem decidiu
   - **Padrão de decisão:** "escolha binária com veto", "consenso após debate longo", "delegação a especialista", "decisão adiada → retomada"
2. Agrupa issues por **padrão estrutural** (usando embeddings de prompt + clusterização)
3. Sugere: *"A decisão sobre X na Reunião 5 seguiu o mesmo padrão de Y na Reunião 12 — ambas foram consenso após 3 alternativas. O que deu certo em Y poderia ter sido aplicado em X."*

**Para cross-contexto (via Ativo de Negócio):**
1. O usuário promove um padrão de decisão como Ativo de Negócio (usando `promover_ativo_negocio`)
2. A ferramenta varre issues do contexto atual e compara com os padrões registrados nos ativos
3. Sugere: *"No contexto FGV/SDEA, vocês estão debatendo se o Catálogo Mestre deve ser centralizado ou distribuído — estrutura idêntica ao debate que ocorreu no contexto Saúde/PRONT (Ativo AN-012). Lá a solução foi..."*

**Esforço:** ~8h (clusterização de padrões + integração com Ativos de Negócio + UI de apresentação)

---

## 🗺️ Roadmap Resumido

| Fase | Tipo | O quê | Esforço | Depende de |
|------|------|-------|---------|------------|
| **1** | Fundação | Tabela `provocations_log` + ferramenta `provoke()` | 3h | — |
| **2** | Ausência | `detect_missing_topics()` + catálogo YAML | 4h | Fase 1 |
| **3** | Contradição | `provoke_temporal_contradictions()` ampliado | 3h | Fase 1 |
| **4** | Premissa | `detect_unexamined_premises()` com marcadores + turnos | 6h | Fase 1 |
| **5** | Assimetria | Extensão modelo IBIS + `detect_discursive_asymmetry()` | 5h | Fase 1, modelo IBIS |
| **6** | Analogia | `suggest_structural_analogies()` + cross-contexto via Ativos | 8h | Fase 1, Ativos de Negócio |

**Total estimado: ~29h de desenvolvimento.**

---

## 💡 Recomendação de Execução

1. **Fase 1 primeiro** — sem a fundação, as provocações seriam efêmeras e sem rastreabilidade
2. **Fase 3 (Contradição) segundo** — é a de menor esforço e maior impacto imediato, já que temos dados no KH
3. **Fase 2 (Ausência) em paralelo com Fase 4 (Premissa)** — compartilham lógica de análise de transcrição
4. **Fase 5 (Assimetria) — requer modelo IBIS estendido primeiro**
5. **Fase 6 (Analogia) — a mais complexa,最後, mas a de maior valor estratégico**

---

Quer que eu formate isso como issue do GitHub ou como prompt direto para o Claude Code?
