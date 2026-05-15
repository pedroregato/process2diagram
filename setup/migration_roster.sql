-- =============================================================================
-- migration_roster.sql
-- ATA Engine Integration — Roster de Participantes de Reunião
-- FGV/DTI · Equipe SOLCORP · Maio 2026
-- =============================================================================
-- Aplicar via Supabase Dashboard → SQL Editor, ou via supabase CLI:
--   supabase db push --file migration_roster.sql
--
-- Ordem de execução:
--   1. project_roster       (depende de projects)
--   2. meeting_participants  (depende de meetings + project_roster)
--   3. Índices
--   4. RLS policies
--   5. Funções auxiliares
--   6. Seed SDEA (opcional — remover em produção genérica)
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 1 — TABELA project_roster
-- ─────────────────────────────────────────────────────────────────────────────
-- Universo de pessoas que podem aparecer em reuniões de um projeto.
-- Muda raramente (novo membro no projeto). Carrega toda a identidade visual
-- necessária para o ATA Engine: iniciais, cor hex, área, aliases de transcrição.

CREATE TABLE IF NOT EXISTS project_roster (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID        NOT NULL
                             REFERENCES projects(id)
                             ON DELETE CASCADE
                             ON UPDATE CASCADE,

    -- Identidade no ATA Engine
    initials     TEXT        NOT NULL
                             CONSTRAINT roster_initials_format
                             CHECK (
                                 initials ~ '^[A-Z]{1,4}$'   -- 1 a 4 letras maiúsculas
                             ),
    full_name    TEXT        NOT NULL
                             CONSTRAINT roster_full_name_nonempty
                             CHECK (char_length(trim(full_name)) > 0),
    area         TEXT,                                        -- "Auditoria", "DTI/SOLCORP"

    -- Cor no padrão ATA Engine: hex sem '#', 6 caracteres
    color_hex    TEXT        NOT NULL
                             CONSTRAINT roster_color_hex_format
                             CHECK (color_hex ~ '^[0-9A-Fa-f]{6}$'),

    -- Variações do nome como aparecem em transcrições
    -- Ex: ["Maria", "Fátima", "MF", "Maria de Fátima"]
    name_aliases TEXT[]      NOT NULL DEFAULT '{}',

    -- Slug do projeto para geração das chaves de localStorage da ata
    -- Ex: "sdea", "p2d", "portal"
    -- Quando NULL, herda do campo slug da tabela projects (ver função get_project_slug)
    project_slug TEXT        CONSTRAINT roster_slug_format
                             CHECK (project_slug IS NULL OR project_slug ~ '^[a-z0-9_-]{1,30}$'),

    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    sort_order   SMALLINT    NOT NULL DEFAULT 0,             -- ordem de exibição nos chips
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Unicidade: um par (projeto, iniciais) é inequívoco
    CONSTRAINT roster_project_initials_unique UNIQUE (project_id, initials)
);

COMMENT ON TABLE  project_roster              IS 'Universo de participantes possíveis por projeto — identidade visual para o ATA Engine';
COMMENT ON COLUMN project_roster.initials     IS 'Sigla de 1-4 letras maiúsculas usada nos chips e badges da ata';
COMMENT ON COLUMN project_roster.color_hex    IS 'Cor hexadecimal sem # (ex: 0B1E3D) — tons escuros para cliente, médios para equipe interna';
COMMENT ON COLUMN project_roster.name_aliases IS 'Variações do nome como aparecem em transcrições — usadas no matching automático';
COMMENT ON COLUMN project_roster.project_slug IS 'Slug para chaves localStorage da ata; se NULL herda do projeto';
COMMENT ON COLUMN project_roster.sort_order   IS 'Ordem de exibição nos chips da sidebar (0 = primeiro)';


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 2 — TABELA meeting_participants
-- ─────────────────────────────────────────────────────────────────────────────
-- Quem esteve presente em cada reunião específica.
-- Populada automaticamente pelo AgentMinutes via matching de nomes na transcrição.
-- O operador pode corrigir manualmente via UI de Configurações.

CREATE TABLE IF NOT EXISTS meeting_participants (
    meeting_id   UUID        NOT NULL
                             REFERENCES meetings(id)
                             ON DELETE CASCADE
                             ON UPDATE CASCADE,
    roster_id    UUID        NOT NULL
                             REFERENCES project_roster(id)
                             ON DELETE CASCADE
                             ON UPDATE CASCADE,

    -- TRUE = presença confirmada pela transcrição ou pelo operador
    -- FALSE = mencionado na transcrição mas presença duvidosa (ex: "Pedro enviou por e-mail")
    confirmed    BOOLEAN     NOT NULL DEFAULT TRUE,

    -- Fonte da informação: 'auto' (AgentMinutes), 'manual' (operador), 'import' (backfill)
    source       TEXT        NOT NULL DEFAULT 'auto'
                             CONSTRAINT mp_source_values
                             CHECK (source IN ('auto', 'manual', 'import')),

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (meeting_id, roster_id)
);

COMMENT ON TABLE  meeting_participants            IS 'Participantes presentes em cada reunião — recorte do roster por meeting';
COMMENT ON COLUMN meeting_participants.confirmed  IS 'FALSE = mencionado na transcrição mas presença não confirmada';
COMMENT ON COLUMN meeting_participants.source     IS 'auto=AgentMinutes, manual=operador, import=backfill';


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 3 — CAMPOS NOVOS EM TABELAS EXISTENTES
-- ─────────────────────────────────────────────────────────────────────────────
-- Campos adicionados à tabela projects para suportar geração da ata.
-- ALTER TABLE é seguro com IF NOT EXISTS — idempotente.

ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS ata_slug         TEXT
        CONSTRAINT projects_ata_slug_format
        CHECK (ata_slug IS NULL OR ata_slug ~ '^[a-z0-9_-]{1,30}$'),
    ADD COLUMN IF NOT EXISTS meeting_location TEXT DEFAULT 'Videoconferência';

COMMENT ON COLUMN projects.ata_slug         IS 'Slug usado nas chaves localStorage das atas (ex: sdea). Fallback para project_roster.project_slug';
COMMENT ON COLUMN projects.meeting_location IS 'Local padrão das reuniões do projeto — usado no hero da ata';


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 4 — ÍNDICES
-- ─────────────────────────────────────────────────────────────────────────────

-- Listagem do roster por projeto (query mais frequente)
CREATE INDEX IF NOT EXISTS idx_roster_project_active
    ON project_roster (project_id, sort_order)
    WHERE is_active = TRUE;

-- Lookup de membro por iniciais dentro de um projeto (matching)
CREATE INDEX IF NOT EXISTS idx_roster_project_initials
    ON project_roster (project_id, initials);

-- Participantes de uma reunião (geração da ata)
CREATE INDEX IF NOT EXISTS idx_mp_meeting
    ON meeting_participants (meeting_id)
    WHERE confirmed = TRUE;

-- Reuniões de um membro do roster (analytics: "quais reuniões o Pedro não esteve")
CREATE INDEX IF NOT EXISTS idx_mp_roster
    ON meeting_participants (roster_id);

-- GIN em name_aliases para busca por alias (matching de transcrição)
CREATE INDEX IF NOT EXISTS idx_roster_aliases_gin
    ON project_roster USING GIN (name_aliases);


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 5 — TRIGGER: updated_at automático
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_roster_updated_at ON project_roster;
CREATE TRIGGER trg_roster_updated_at
    BEFORE UPDATE ON project_roster
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 6 — ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────
-- Herda o modelo de segurança já existente no P2D.
-- Leitura: qualquer usuário autenticado.
-- Escrita: somente admin/master (verificado na camada Python via is_admin()).
-- As políticas abaixo são permissivas na leitura e restritivas na escrita,
-- compatíveis com o padrão já usado nas tabelas meetings e requirements.

ALTER TABLE project_roster       ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_participants ENABLE ROW LEVEL SECURITY;

-- Leitura pública para autenticados
DROP POLICY IF EXISTS roster_select_authenticated ON project_roster;
CREATE POLICY roster_select_authenticated
    ON project_roster FOR SELECT
    USING (true);

DROP POLICY IF EXISTS mp_select_authenticated ON meeting_participants;
CREATE POLICY mp_select_authenticated
    ON meeting_participants FOR SELECT
    USING (true);

-- Escrita apenas via service_role (a camada Python usa a service key)
DROP POLICY IF EXISTS roster_write_service ON project_roster;
CREATE POLICY roster_write_service
    ON project_roster FOR ALL
    USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS mp_write_service ON meeting_participants;
CREATE POLICY mp_write_service
    ON meeting_participants FOR ALL
    USING (auth.role() = 'service_role');


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 7 — FUNÇÃO AUXILIAR: get_meeting_participants_full
-- ─────────────────────────────────────────────────────────────────────────────
-- Retorna participantes confirmados de uma reunião com todos os campos do roster.
-- Usada diretamente pelo project_store.py para montar os chips da ata.

CREATE OR REPLACE FUNCTION get_meeting_participants_full(p_meeting_id UUID)
RETURNS TABLE (
    roster_id    UUID,
    initials     TEXT,
    full_name    TEXT,
    area         TEXT,
    color_hex    TEXT,
    name_aliases TEXT[],
    sort_order   SMALLINT,
    confirmed    BOOLEAN,
    source       TEXT
)
LANGUAGE sql STABLE AS $$
    SELECT
        r.id          AS roster_id,
        r.initials,
        r.full_name,
        r.area,
        r.color_hex,
        r.name_aliases,
        r.sort_order,
        mp.confirmed,
        mp.source
    FROM meeting_participants mp
    JOIN project_roster r ON r.id = mp.roster_id
    WHERE mp.meeting_id = p_meeting_id
      AND mp.confirmed  = TRUE
    ORDER BY r.sort_order, r.initials;
$$;

COMMENT ON FUNCTION get_meeting_participants_full IS
    'Participantes confirmados de uma reunião com dados completos do roster — usado pelo gerador de ata';


-- ─────────────────────────────────────────────────────────────────────────────
-- FASE 8 — SEED (removido do migration genérico)
-- ─────────────────────────────────────────────────────────────────────────────
-- Para popular o roster de um projeto específico, use a UI em
-- Configurações → 👥 Participantes, ou insira diretamente via SQL:
--
-- INSERT INTO project_roster (project_id, initials, full_name, area, color_hex, name_aliases, sort_order)
-- VALUES ('<uuid-do-projeto>', 'AB', 'Nome Completo', 'Área', '1A4B8C', ARRAY['Nome', 'NomeAlias'], 0)
-- ON CONFLICT (project_id, initials) DO UPDATE SET ...;


-- ─────────────────────────────────────────────────────────────────────────────
-- VERIFICAÇÃO PÓS-MIGRAÇÃO
-- ─────────────────────────────────────────────────────────────────────────────
-- Execute após aplicar para confirmar que tudo foi criado corretamente:

/*
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('project_roster', 'meeting_participants')
ORDER BY table_name, ordinal_position;

SELECT indexname, tablename FROM pg_indexes
WHERE tablename IN ('project_roster', 'meeting_participants')
ORDER BY tablename, indexname;

SELECT proname FROM pg_proc WHERE proname = 'get_meeting_participants_full';
*/
