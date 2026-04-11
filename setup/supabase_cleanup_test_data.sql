-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Limpeza de dados de teste
-- Execute no SQL Editor do Supabase Dashboard
--
-- Remove TODOS os dados derivados do projeto (reuniões, artefatos, requisitos,
-- SBVR, BPMN, batch_log) mantendo apenas o registro do projeto em si.
-- Útil para re-processar transcrições durante desenvolvimento/homologação.
--
-- ⚠️  IRREVERSÍVEL — faça backup se necessário.
-- ─────────────────────────────────────────────────────────────────────────────

-- Substitua o valor abaixo pelo UUID do seu projeto (consulte: SELECT id, name FROM projects)
-- ou use a subquery comentada para selecionar o único projeto existente.

-- Opção A: informar o project_id diretamente
-- \set project_id 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'

-- Opção B: usar o único projeto existente (ambiente de desenvolvimento com 1 projeto)
DO $$
DECLARE
    v_project_id UUID;
BEGIN
    SELECT id INTO v_project_id FROM projects ORDER BY created_at LIMIT 1;

    IF v_project_id IS NULL THEN
        RAISE EXCEPTION 'Nenhum projeto encontrado.';
    END IF;

    RAISE NOTICE 'Limpando dados do projeto: %', v_project_id;

    -- Versões BPMN (antes dos processos)
    DELETE FROM bpmn_versions  WHERE project_id = v_project_id;

    -- Processos BPMN
    DELETE FROM bpmn_processes WHERE project_id = v_project_id;

    -- Regras e termos SBVR
    DELETE FROM sbvr_rules     WHERE project_id = v_project_id;
    DELETE FROM sbvr_terms     WHERE project_id = v_project_id;

    -- Versões de requisitos (antes dos requisitos — FK)
    DELETE FROM requirement_versions
    WHERE requirement_id IN (
        SELECT id FROM requirements WHERE project_id = v_project_id
    );

    -- Requisitos
    DELETE FROM requirements   WHERE project_id = v_project_id;

    -- Log de batch
    DELETE FROM batch_log      WHERE project_id = v_project_id;

    -- Reuniões (por último — outras tabelas referenciam meetings.id)
    DELETE FROM meetings       WHERE project_id = v_project_id;

    RAISE NOTICE 'Concluído. Projeto % mantido, todos os dados derivados removidos.', v_project_id;
END $$;
