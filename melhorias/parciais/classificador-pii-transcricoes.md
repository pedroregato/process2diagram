# Classificador de PII por transcrição — indicador de confiabilidade/compliance

**Status:** Implementado (parcial) — a detecção e a persistência já existem e rodam em produção; falta inteiramente a camada de agregação/superfície que transforma o dado em sinal visível.
**Origem:** proposta do usuário (2026-08-05) — "saber quanta informação sensível foi encontrada na transcrição, quais os tipos e frequências, como indicador de confiabilidade do produto".

---

## 1. O que já existe (fundação real, verificada no código)

- **Detecção estruturada (regex):** `modules/compliance/detector.py::detect_pii()` reconhece CPF, CNPJ, EMAIL, TEL, VALOR — mesmos padrões usados por `modules/pii_sanitizer.py` (a camada que de fato tokeniza antes de mandar pro LLM).
- **Detecção de nomes:** via spaCy NER (`PER`), lista até 20 pessoas detectadas.
- **Classificação de risco:** heurística já implementada — `high` se tem CPF/CNPJ/EMAIL, `medium` se tem qualquer PII, `low` se não tem nada.
- **Persistência:** `pages/Pipeline.py:409-419` chama `detect_pii(hub.transcript_raw)` a cada processamento de reunião e grava o resultado (`.summary` — categorias+contagem+risk_level, formato JSONB) em `compliance_audit`, evento `pipeline_run`, retido 365 dias.
- **UI:** `render_consent_panel()` mostra o resultado **uma única vez**, na própria página Pipeline, logo após o processamento — não é revisitável depois, não aparece em nenhum outro lugar do sistema.

**Conclusão da auditoria:** isto não é uma feature a construir do zero. É uma feature com a metade cara (detecção correta, persistência correta, formato de dado já bom) pronta — e a metade barata (ler o que já foi gravado e mostrar de volta) never construída.

---

## 2. O que falta

- Nenhuma função de leitura agregada de `compliance_audit` existe hoje em `core/project_store.py` (grep confirma: a tabela é write-only na prática).
- Nenhum dashboard, badge ou trend — o dado de uma reunião processada há 3 meses está lá, mas ninguém consegue vê-lo sem SQL direto.
- Nenhuma tool do Assistente pra perguntar "qual o risco de PII da Reunião X" ou "quais reuniões desse projeto têm risco alto".
- `pages/SegurancaDeDados.py` hoje é só documentação estática (HTML explicando a arquitetura) — não lê dado real nenhum.

---

## 3. Estratégia proposta — 4 camadas, cada uma reaproveitando o que já existe

### Camada 1 — Persistência de 1ª classe
Hoje o resultado só existe dentro do JSONB de auditoria (difícil de consultar em lote). Adicionar 3 colunas em `meetings` (`pii_risk_level`, `pii_categories` JSONB, `pii_persons_count`) — ou uma tabela `meeting_pii_summary` 1:1 se preferir manter `meetings` enxuta. A escrita já acontece no ponto certo do código (`Pipeline.py:409`), só falta persistir aqui também, não só no log de auditoria. Reaproveita 100% o formato de `PIIDetectionResult.summary` — não precisa desenhar schema novo.

### Camada 2 — Consulta agregada
Nova função `list_meetings_pii_summary(project_id)` em `core/project_store.py`, mesmo padrão de `list_meetings_quality()` já existente (a que alimenta o Radar de Qualidade da Home/ValidationHub) — 1 query, sem N+1.

### Camada 3 — Superfície visual
- Badge de risco (🟢🟡🔴) na listagem de reuniões (`ArtefatosReunioes.py`, Home).
- Aba "Dashboard" real em `pages/SegurancaDeDados.py` (hoje só tem documentação estática) — reaproveitar o padrão visual já existente do Radar de Qualidade (Scatterpolar Plotly), com dimensões tipo "% reuniões com CPF exposto", "% reuniões com e-mail", distribuição de risco por período.

### Camada 4 — Ferramenta do Assistente
Tool nova `get_pii_risk_summary(meeting_number)` / `list_high_risk_meetings()`, categoria "consulta" (não-admin — é awareness/disclosure, não mutação), mesmo padrão de `get_cache_stats`/`get_provocations_diagnostics`.

---

## 4. O que eu **não** faria agora

- **Trocar a lógica de detecção por LLM.** Regex + spaCy já é adequado e testado; pagar chamada de LLM pra reclassificar algo que um padrão determinístico já resolve bem é custo sem ganho demonstrado — mesmo princípio já aplicado na decisão do cache semântico (`langchain-langgraph-cache-semantico.md`).
- **Bloquear o pipeline com base no risco.** Mudaria o comportamento fail-open do sistema — é uma decisão de produto que merece discussão própria, não deveria vir de carona nesta proposta.
- **Reduzir tudo a um único "score de confiabilidade".** Um número único esconde detalhe e pode ser mal-interpretado como "seguro/inseguro" binário — melhor manter a categorização multi-dimensional já existente (tipo + contagem + risk_level por categoria) visível, do que comprimir em 1 métrica. Se um score único fizer sentido depois, desenhar com dado real de uso das camadas 1-4 em mãos, não especulativamente.

---

## 5. Esforço / sequenciamento sugerido

| Camada | Esforço | Depende de |
|---|---|---|
| 1 — Persistência | Pequeno | — |
| 2 — Consulta agregada | Pequeno | Camada 1 |
| 3a — Badge simples | Pequeno-médio | Camada 2 |
| 3b — Dashboard/radar completo | Médio | Camada 2 |
| 4 — Tool do Assistente | Médio | Camada 2 |
| Score único (não recomendado agora) | — | Dado real das camadas 1-4 |

**Paralelo direto com o já feito neste projeto:** é a mesma dinâmica do PC183 (telemetria de erro de LLM) — o dado certo já estava sendo calculado e gravado, só nunca virou sinal visível. Fechar esse loop é historicamente onde esse projeto ganhou os achados mais valiosos até agora.
