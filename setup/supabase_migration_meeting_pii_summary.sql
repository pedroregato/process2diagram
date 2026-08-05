-- Classificador de PII por transcrição — sinal visível de compliance
-- (melhorias/parciais/classificador-pii-transcricoes.md)
--
-- modules/compliance/detector.py::detect_pii() já roda a cada processamento
-- de reunião (pages/Pipeline.py) e já produz o resultado certo (categorias +
-- contagem + risk_level) — mas hoje só é gravado dentro do JSONB de
-- compliance_audit (evento pipeline_run), que é write-only na prática: não
-- existe consulta agregada nem superfície visual em cima disso.
--
-- Três colunas em `meetings`, todas fail-open / additive, reaproveitando
-- 100% o formato de PIIDetectionResult.summary — sem schema novo:
--   1) pii_risk_level    — "low"|"medium"|"high", pra badge rápido (🟢🟡🔴)
--   2) pii_categories    — JSONB {"CPF": 4, "EMAIL": 2, ...}, contagem bruta
--      por categoria — o card de detalhe mostra isso, não um score único
--   3) pii_persons_count — quantos nomes de pessoa o spaCy detectou
--
-- Total de "informações sensíveis" (ex.: "21 no total") é derivado na UI
-- (soma de pii_categories.values()) — não armazenado, evita redundância.
--
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS pii_risk_level    TEXT,
    ADD COLUMN IF NOT EXISTS pii_categories    JSONB,
    ADD COLUMN IF NOT EXISTS pii_persons_count INTEGER;

CREATE INDEX IF NOT EXISTS idx_meetings_pii_risk_level
    ON meetings(pii_risk_level)
    WHERE pii_risk_level IS NOT NULL;
