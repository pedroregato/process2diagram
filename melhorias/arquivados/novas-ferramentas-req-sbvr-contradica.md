Agora tenho a visão completa. Aqui está a especificação do que precisei de ferramentas para cada pendência:

---

## Especificação das ferramentas necessárias

### 1️⃣ REQ-710 — Trocar `'IT-001'` por `'AUD-IT-001'`

| Item | Detalhe |
|---|---|
| **Texto exato** | `'IT-001'` (com aspas simples) no trecho: *"no formato 'AUD-CP-001', 'IT-001', etc."* |
| **Ferramenta que faltou** | Uma variante de `apply_text_correction` que aceite **escape de caracteres especiais** (aspas simples) dentro do `find_text` — ou um `update_requirement_text(req_number, new_value)` que substitua o texto completo da descrição de um requisito específico |
| **Alternativa** | `update_requirement_description(req_number=710, description="...texto completo corrigido...")` — substituir a descrição inteira |

---

### 2️⃣ 4 Regras SBVR desatualizadas

| Regra | Texto atual (desatualizado) | Texto que deveria ter |
|---|---|---|
| **BR002** — Padronização de identificador | `'Audit CP' seguido do código e nome da unidade` | `'AUD-CP-{sequencial}'` |
| **BR006** — Padrão de identificador (2 ocorrências) | `'Audit' seguido da sigla do tipo de documento` | `'AUD' seguido da sigla e sequencial: AUD-CP-001` |
| **BR006** — Identificador com prefixo AUDIT | `'AUDIT' seguido da sigla` | `'AUD' seguido da sigla e sequencial: AUD-CP-001` |
| **BR007** — Identificador do documento | `AUD seguido da sigla e número sequencial` | `AUD-{sigla}-{sequencial} (ex: AUD-CP-001)` |

**Ferramenta que faltou:** `update_sbvr_rule(rule_id, statement, rule_type)` — para editar o enunciado de uma regra SBVR existente.

---

### 3️⃣ 3 Termos SBVR "Identificador do Documento"

| Entrada atual (as 3) | O que diz |
|---|---|
| 1 | `'Audit CP' seguido de informações da unidade` |
| 2 | `'Audit CP' para catálogos de processos` |
| 3 | `prefixo (ex.: AUD CP) e sequencial` |

✅ **Eu tenho** `update_sbvr_term`, **mas ela busca por nome** — como os 3 têm o mesmo nome `"Identificador do Documento"`, a ferramenta atualizaria apenas **o primeiro**. Precisaria de uma ferramenta que aceitasse **ID do termo** (além do nome) para atualizar cada um individualmente.

**Ferramenta necessária:** `update_sbvr_term_by_id(term_id, definition, category)` — para endereçar cada entrada específica pelo seu UUID.

---

### 4️⃣ Contradição no Knowledge Hub

| Contradição | Fatos conflitantes |
|---|---|
| **Identificação do catálogo de processos** (open) | Fato A: `"CP código unidade nome"` vs Fato B: `"AUDIT-CP-001"` |
| **Padronização de identificadores** (open) | Fato A: `"Audit CP"` vs Fato B: `"AUDIT-CP-001"` |

Com a sua decisão (`AUD-CP-001`), ambas podem ser resolvidas.

**Ferramenta que faltou:** `resolve_contradiction(contradiction_id, resolution, note)` — para marcar uma contradição como **resolvida** e registrar a decisão que a solucionou.

---

## Resumo da especificação

| Pendência | Ferramenta necessária |
|---|---|
| REQ-710 — `'IT-001'` residual | `update_requirement_text(req_number, new_full_text)` |
| 4 regras SBVR (BR002, BR006 ×2, BR007) | `update_sbvr_rule(rule_id, new_statement)` |
| 3 termos SBVR "Identificador do Documento" | `update_sbvr_term_by_id(term_id, new_definition)` |
| Contradições no Knowledge Hub | `resolve_contradiction(contradiction_id, resolution, note)` |

Com essas 4 ferramentas adicionais, eu conseguiria resolver **todas as pendências** em uma única rodada. Deseja que eu registre essa solicitação de novas ferramentas para o desenvolvimento?
