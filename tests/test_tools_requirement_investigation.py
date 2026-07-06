# tests/test_tools_requirement_investigation.py
"""
Tests for the four PC141 investigative tools added to
core/tools/tools_meetings_requirements.py, proposed by the assistant itself
after the PC140 duplication investigation had to rely on slow, paginated
get_requirements calls: sample_requirements, analyze_requirement_quality,
map_transcript_to_requirements, cluster_similar_requirements.

No real DB/LLM/embedding calls — all dependencies mocked at their import
source. Supabase query chain mocked via a small fake client.
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor
from core.tools.tools_meetings_requirements import _cosine_similarity

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


def _executor():
    return AssistantToolExecutor("proj-1", llm_config=_LLM_CONFIG)


class _FakeSelectChain:
    """Mimics db.table(x).select(...).eq(...).eq(...).order(...).execute()."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _FakeSelectChain(self._rows)


_MEETING = {
    "id": "meet-1",
    "meeting_number": 1,
    "title": "Reunião de Teste",
    "transcript_clean": "Primeiro parágrafo sobre login e autenticação de usuários no sistema.\n\n"
                        "Segundo parágrafo sobre validação de CPF e integração com bureaus externos.",
}

_REQ_ROWS = [
    {"req_number": 1, "title": "Validar CPF", "description": "Sistema deve validar CPF do cliente.",
     "req_type": "functional", "priority": "high", "status": "active",
     "source_quote": "validação de CPF e integração com bureaus externos"},
    {"req_number": 2, "title": "CPF deve ser validado", "description": "Validação de CPF obrigatória.",
     "req_type": "functional", "priority": "high", "status": "active",
     "source_quote": "validação de CPF e integração com bureaus externos"},
    {"req_number": 3, "title": "Login de usuário", "description": "Sistema deve permitir login.",
     "req_type": "functional", "priority": "medium", "status": "active",
     "source_quote": "login e autenticação de usuários no sistema"},
]


class TestSampleRequirements:
    def test_meeting_not_found(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=None):
            result = ex.sample_requirements(meeting_number=99)
        assert "não encontrada" in result

    def test_no_requirements_found(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB([])):
            result = ex.sample_requirements(meeting_number=1)
        assert "Nenhum requisito encontrado" in result

    def test_returns_requested_sample_size(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            result = ex.sample_requirements(meeting_number=1, sample_size=2, seed=42)
        assert "Amostra aleatória de 2 de 3" in result

    def test_sample_size_capped_at_available_rows(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            result = ex.sample_requirements(meeting_number=1, sample_size=1000)
        assert "Amostra aleatória de 3 de 3" in result

    def test_seed_makes_sample_reproducible(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            r1 = ex.sample_requirements(meeting_number=1, sample_size=2, seed=7)
            r2 = ex.sample_requirements(meeting_number=1, sample_size=2, seed=7)
        assert r1 == r2


class TestAnalyzeRequirementQuality:
    def test_meeting_not_found(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=None):
            result = ex.analyze_requirement_quality(meeting_number=99)
        assert "não encontrada" in result

    def test_reports_counts_and_ratio(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            result = ex.analyze_requirement_quality(meeting_number=1)
        assert "Total de requisitos: 3" in result
        assert "requisitos por 100 palavras" in result

    def test_flags_high_ratio_as_super_granularity(self):
        ex = _executor()
        # 3 requirements over a very short transcript -> high ratio, must flag.
        short_meeting = {**_MEETING, "transcript_clean": "Poucas palavras aqui apenas."}
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=short_meeting), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            result = ex.analyze_requirement_quality(meeting_number=1)
        assert "super-granularidade" in result

    def test_does_not_flag_normal_ratio(self):
        ex = _executor()
        long_transcript = " ".join(["palavra"] * 1000)
        long_meeting = {**_MEETING, "transcript_clean": long_transcript}
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=long_meeting), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            result = ex.analyze_requirement_quality(meeting_number=1)
        assert "super-granularidade" not in result


class TestMapTranscriptToRequirements:
    def test_meeting_not_found(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=None):
            result = ex.map_transcript_to_requirements(meeting_number=99)
        assert "não encontrada" in result

    def test_no_transcript_stored(self):
        ex = _executor()
        empty_meeting = {**_MEETING, "transcript_clean": "", "transcript_raw": ""}
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=empty_meeting):
            result = ex.map_transcript_to_requirements(meeting_number=1)
        assert "não possui transcrição" in result

    def test_maps_requirements_to_correct_paragraph(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)):
            result = ex.map_transcript_to_requirements(meeting_number=1)
        # 2 requirements share the CPF paragraph, 1 the login paragraph.
        assert "2 requisito(s)" in result
        assert "CPF" in result

    def test_unmatched_quote_counted_separately(self):
        ex = _executor()
        rows = [{**_REQ_ROWS[0], "source_quote": ""}]
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(rows)):
            result = ex.map_transcript_to_requirements(meeting_number=1)
        assert "sem correspondência clara" in result


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors(self):
        assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestClusterSimilarRequirements:
    def test_meeting_not_found(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=None):
            result = ex.cluster_similar_requirements(meeting_number=99)
        assert "não encontrada" in result

    def test_rejects_over_max_requirements(self):
        ex = _executor()
        many_rows = [{"req_number": i, "title": f"T{i}", "description": "d"} for i in range(5)]
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(many_rows)):
            result = ex.cluster_similar_requirements(meeting_number=1, max_requirements=2)
        assert "acima do limite" in result

    def test_missing_embedding_config_returns_error(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)), \
             patch("modules.embeddings.get_active_embedding_params",
                   side_effect=RuntimeError("Provedor de embedding não configurado.")):
            result = ex.cluster_similar_requirements(meeting_number=1)
        assert "Provedor de embedding não configurado" in result

    def test_similar_requirements_grouped_into_same_cluster(self):
        ex = _executor()
        # REQ-001 and REQ-002 (CPF) get near-identical vectors; REQ-003 (login)
        # gets an orthogonal one -- must land in a separate cluster.
        vectors = [[1.0, 0.0, 0.0], [0.99, 0.01, 0.0], [0.0, 1.0, 0.0]]
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)), \
             patch("modules.embeddings.get_active_embedding_params", return_value=("OpenAI", "sk-fake")), \
             patch("modules.embeddings.embed_batch", return_value=vectors):
            result = ex.cluster_similar_requirements(meeting_number=1, threshold=0.9)
        assert "3 requisito(s)" in result
        assert "2 cluster(s)" in result
        assert "1 cluster(s) com mais de 1 requisito" in result
        assert "REQ-001" in result and "REQ-002" in result

    def test_dissimilar_requirements_stay_in_separate_clusters(self):
        ex = _executor()
        vectors = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=_MEETING), \
             patch("modules.supabase_client.get_supabase_client", return_value=_FakeDB(_REQ_ROWS)), \
             patch("modules.embeddings.get_active_embedding_params", return_value=("OpenAI", "sk-fake")), \
             patch("modules.embeddings.embed_batch", return_value=vectors):
            result = ex.cluster_similar_requirements(meeting_number=1, threshold=0.9)
        assert "3 cluster(s)" in result
        assert "0 cluster(s) com mais de 1 requisito" in result


class TestToolDispatchWiring:
    def test_execute_routes_sample_requirements(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "sample_requirements", return_value="ok") as mock_method:
            result = ex.execute("sample_requirements", {"meeting_number": 1, "sample_size": 10, "seed": 3})
        assert result == "ok"
        mock_method.assert_called_once_with(meeting_number=1, sample_size=10, seed=3)

    def test_execute_routes_analyze_requirement_quality(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "analyze_requirement_quality", return_value="ok") as mock_method:
            ex.execute("analyze_requirement_quality", {"meeting_number": 2})
        mock_method.assert_called_once_with(meeting_number=2)

    def test_execute_routes_map_transcript_to_requirements(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "map_transcript_to_requirements", return_value="ok") as mock_method:
            ex.execute("map_transcript_to_requirements", {"meeting_number": 3})
        mock_method.assert_called_once_with(meeting_number=3)

    def test_execute_routes_cluster_similar_requirements(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "cluster_similar_requirements", return_value="ok") as mock_method:
            ex.execute("cluster_similar_requirements", {"meeting_number": 4, "threshold": 0.9, "max_requirements": 50})
        mock_method.assert_called_once_with(meeting_number=4, threshold=0.9, max_requirements=50)

    def test_none_of_the_four_tools_are_admin_only(self):
        from core.assistant_tools import _ADMIN_TOOLS
        for name in ("sample_requirements", "analyze_requirement_quality",
                     "map_transcript_to_requirements", "cluster_similar_requirements"):
            assert name not in _ADMIN_TOOLS
