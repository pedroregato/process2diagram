-- =============================================================================
-- supabase_schema_knowledge_hub.sql
-- Knowledge Hub Persistente — Memória cross-session do Process2Diagram
-- PC9-A · Maio 2026
-- =============================================================================
-- Aplicar via Supabase Dashboard → SQL Editor
-- Ordem: tabelas → índices → triggers → RLS → funções
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- TABELA 1: kh_entities
-- Entidades organizacionais recorrentes (pessoas, times, sistemas, departamentos)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kh_entities (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_type          TEXT        NOT NULL
                                     CHECK (entity_type IN ('person','team','system','department','process','other')),
    canonical_name       TEXT        NOT NULL,
    aliases              TEXT[]      NOT NULL DEFAULT '{}',
    first_seen_meeting_id UUID       REFERENCES meetings(id) ON DELETE SET NULL,
    last_seen_meeting_id  UUID       REFERENCES meetings(id) ON DELETE SET NULL,
    occurrence_count     INT         NOT NULL DEFAULT 1,
    metadata             JSONB       NOT NULL DEFAULT '{}',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT kh_entities_project_name_type_unique
        UNIQUE (project_id, canonical_name, entity_type)
);

COMMENT ON TABLE  kh_entities                   IS 'Entidades organizacionais recorrentes detectadas nas reunioes do projeto';
COMMENT ON COLUMN kh_entities.entity_type       IS 'person | team | system | department | process | other';
COMMENT ON COLUMN kh_entities.canonical_name    IS 'Nome normalizado usado como chave (ex: "Equipe de Compliance")';
COMMENT ON COLUMN kh_entities.aliases           IS 'Variacoes de nome encontradas nas transcricoes';
COMMENT ON COLUMN kh_entities.occurrence_count  IS 'Numero de reunioes onde esta entidade foi mencionada';


-- ─────────────────────────────────────────────────────────────────────────────
-- TABELA 2: kh_processes
-- Processos de negócio identificados e rastreados ao longo das reuniões
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kh_processes (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    process_name      TEXT        NOT NULL,
    description       TEXT,
    version_count     INT         NOT NULL DEFAULT 1,
    first_meeting_id  UUID        REFERENCES meetings(id) ON DELETE SET NULL,
    last_meeting_id   UUID        REFERENCES meetings(id) ON DELETE SET NULL,
    meeting_ids       UUID[]      NOT NULL DEFAULT '{}',
    status            TEXT        NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active','deprecated','merged')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT kh_processes_project_name_unique
        UNIQUE (project_id, process_name)
);

COMMENT ON TABLE  kh_processes             IS 'Processos de negocio identificados e rastreados cross-meeting';
COMMENT ON COLUMN kh_processes.version_count IS 'Numero de vezes que o processo foi revisto ou refinado';
COMMENT ON COLUMN kh_processes.meeting_ids   IS 'Todas as reunioes que mencionaram este processo';


-- ─────────────────────────────────────────────────────────────────────────────
-- TABELA 3: kh_facts
-- Fatos, regras e decisões consolidados cross-meeting
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kh_facts (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    fact_type           TEXT        NOT NULL
                                    CHECK (fact_type IN ('rule','decision','constraint','nomenclature','insight')),
    content             TEXT        NOT NULL,
    source_meeting_ids  UUID[]      NOT NULL DEFAULT '{}',
    confidence          FLOAT       NOT NULL DEFAULT 1.0
                                    CHECK (confidence BETWEEN 0.0 AND 1.0),
    superseded_by       UUID        REFERENCES kh_facts(id) ON DELETE SET NULL,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  kh_facts              IS 'Fatos, regras e decisoes consolidados extraidos das reunioes';
COMMENT ON COLUMN kh_facts.fact_type    IS 'rule | decision | constraint | nomenclature | insight';
COMMENT ON COLUMN kh_facts.confidence   IS '0.0-1.0 — confianca do extrator; abaixo de 0.7 requer revisao humana';
COMMENT ON COLUMN kh_facts.superseded_by IS 'FK para o fato mais recente que substitui este';
COMMENT ON COLUMN kh_facts.is_active    IS 'FALSE quando superseded ou descartado manualmente';


-- ─────────────────────────────────────────────────────────────────────────────
-- TABELA 4: kh_contradictions
-- Contradições detectadas entre versões de processos ou decisões
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kh_contradictions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    process_name    TEXT,
    description     TEXT        NOT NULL,
    meeting_a_id    UUID        REFERENCES meetings(id) ON DELETE SET NULL,
    meeting_b_id    UUID        REFERENCES meetings(id) ON DELETE SET NULL,
    severity        TEXT        NOT NULL DEFAULT 'medium'
                                CHECK (severity IN ('low','medium','high','critical')),
    status          TEXT        NOT NULL DEFAULT 'open'
                                CHECK (status IN ('open','resolved','false_positive')),
    resolved_by     TEXT,
    resolution_note TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  kh_contradictions           IS 'Contradicoes detectadas entre versoes de processos ou decisoes';
COMMENT ON COLUMN kh_contradictions.severity  IS 'low | medium | high | critical';
COMMENT ON COLUMN kh_contradictions.status    IS 'open | resolved | false_positive';


-- ─────────────────────────────────────────────────────────────────────────────
-- ÍNDICES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_kh_entities_project       ON kh_entities (project_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_kh_entities_occurrence    ON kh_entities (project_id, occurrence_count DESC);
CREATE INDEX IF NOT EXISTS idx_kh_entities_aliases_gin   ON kh_entities USING GIN (aliases);

CREATE INDEX IF NOT EXISTS idx_kh_processes_project      ON kh_processes (project_id);
CREATE INDEX IF NOT EXISTS idx_kh_processes_status       ON kh_processes (project_id, status);

CREATE INDEX IF NOT EXISTS idx_kh_facts_project_type     ON kh_facts (project_id, fact_type);
CREATE INDEX IF NOT EXISTS idx_kh_facts_active           ON kh_facts (project_id) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_kh_contradictions_status  ON kh_contradictions (project_id, status);
CREATE INDEX IF NOT EXISTS idx_kh_contradictions_open    ON kh_contradictions (project_id) WHERE status = 'open';


-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGERS: updated_at automático
-- ─────────────────────────────────────────────────────────────────────────────
-- Reutiliza set_updated_at() criado pela migration_roster.sql
-- Se não existir, cria aqui:
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

DROP TRIGGER IF EXISTS trg_kh_entities_updated_at       ON kh_entities;
DROP TRIGGER IF EXISTS trg_kh_processes_updated_at      ON kh_processes;
DROP TRIGGER IF EXISTS trg_kh_facts_updated_at          ON kh_facts;
DROP TRIGGER IF EXISTS trg_kh_contradictions_updated_at ON kh_contradictions;

CREATE TRIGGER trg_kh_entities_updated_at
    BEFORE UPDATE ON kh_entities FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_kh_processes_updated_at
    BEFORE UPDATE ON kh_processes FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_kh_facts_updated_at
    BEFORE UPDATE ON kh_facts FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_kh_contradictions_updated_at
    BEFORE UPDATE ON kh_contradictions FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE kh_entities       ENABLE ROW LEVEL SECURITY;
ALTER TABLE kh_processes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE kh_facts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE kh_contradictions ENABLE ROW LEVEL SECURITY;

-- Leitura para autenticados
CREATE POLICY kh_entities_select       ON kh_entities       FOR SELECT USING (true);
CREATE POLICY kh_processes_select      ON kh_processes      FOR SELECT USING (true);
CREATE POLICY kh_facts_select          ON kh_facts          FOR SELECT USING (true);
CREATE POLICY kh_contradictions_select ON kh_contradictions FOR SELECT USING (true);

-- Escrita via service_role (camada Python usa service key)
CREATE POLICY kh_entities_write       ON kh_entities       FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY kh_processes_write      ON kh_processes      FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY kh_facts_write          ON kh_facts          FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY kh_contradictions_write ON kh_contradictions FOR ALL USING (auth.role() = 'service_role');


-- ─────────────────────────────────────────────────────────────────────────────
-- VERIFICAÇÃO PÓS-MIGRAÇÃO
-- ─────────────────────────────────────────────────────────────────────────────
/*
SELECT table_name, COUNT(*) AS col_count
FROM information_schema.columns
WHERE table_name IN ('kh_entities','kh_processes','kh_facts','kh_contradictions')
GROUP BY table_name ORDER BY table_name;

SELECT indexname, tablename FROM pg_indexes
WHERE tablename LIKE 'kh_%' ORDER BY tablename, indexname;
*/
