-- PC207 — Observabilidade de Provocações: escopo por reunião + motivo de rejeição
--
-- Testando o projeto real AURORA, a aba Provocações mostrou "nenhuma provocação
-- gerada" (resultado válido por design) sem nenhum jeito de perguntar "por quê"
-- sem abrir os logs efêmeros do Streamlit Cloud. A informação já existe em
-- memória (hub.provocations.rejected_count/rejected_reasons, calculada por
-- agents/agent_provocations.py::_validate_and_rank) — só nunca foi persistida.
--
-- Três adições a llm_telemetry, todas fail-open / additive:
--   1) project_id / meeting_id — genéricos no schema (não exclusivos de
--      Provocações), mas só esta rodada os popula. Sem isso, llm_telemetry só
--      responde perguntas agregadas ("qual a taxa de erro do provider X"), não
--      "por que ESTA reunião não gerou nada".
--   2) approved_count / rejected_count — quantas provocações o validador
--      determinístico aprovou/rejeitou na última execução de AgentProvocations
--      pra essa reunião.
--   3) rejected_reasons (JSONB) — breakdown por motivo (mesmos identificadores
--      já usados no validador: reference_not_found, premise_marker_missing,
--      absence_check_missing, etc.), sem tradução.
--
-- Mesmo padrão de evento diagnóstico sem latência/tokens de record_validation()
-- (PC183) — reusa a mesma tabela, não cria tabela nova.
--
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE llm_telemetry
    ADD COLUMN IF NOT EXISTS project_id       UUID REFERENCES contexts(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS meeting_id       UUID REFERENCES meetings(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS approved_count   INTEGER,
    ADD COLUMN IF NOT EXISTS rejected_count   INTEGER,
    ADD COLUMN IF NOT EXISTS rejected_reasons JSONB;

CREATE INDEX IF NOT EXISTS idx_llm_telemetry_meeting
    ON llm_telemetry(meeting_id)
    WHERE meeting_id IS NOT NULL;
