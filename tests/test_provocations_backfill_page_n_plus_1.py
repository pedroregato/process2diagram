# tests/test_provocations_backfill_page_n_plus_1.py
"""
NAV-17 (melhorias/parciais/navegabilidade.md): pages/ProvocationsBackfill.py
chamava AgentProvocations.bridge_contradictions(project_id, m["id"]) dentro
de um laço por reunião (linha ~93-98) sem passar o parâmetro contradictions=
— cada chamada refazia internamente get_contradictions(project_id, ...), uma
query que NÃO depende de meeting_id. N+1 clássico: um projeto com 20
reuniões refazia a mesma consulta 20 vezes.

Fix: get_contradictions() buscada 1x antes do laço, repassada via
contradictions= (comportamento de AgentProvocations.bridge_contradictions()
já coberto em tests/test_agent_provocations.py::TestBridgeContradictions —
aqui só confirma que a PÁGINA está de fato usando o parâmetro).

Checagem estática, mesmo padrão dos demais testes desta rodada — a página
depende de contexto de sessão + Supabase configurado, não vale a pena
simular via AppTest só pra confirmar a ordem de 2 chamadas.
"""

from pathlib import Path

_RAW_SRC = (
    Path(__file__).resolve().parent.parent / "pages" / "ProvocationsBackfill.py"
).read_text(encoding="utf-8")

# Comentários explicativos citam "get_contradictions(" e "bridge_contradictions("
# como prosa — remove linhas de comentário antes de contar/localizar chamadas
# reais, senão o texto explicativo conta como uma chamada.
_SRC = "\n".join(
    line for line in _RAW_SRC.splitlines() if not line.strip().startswith("#")
)


class TestContradictionsFetchedOnceBeforeTheLoop:
    def test_get_contradictions_called_before_the_meeting_loop(self):
        fetch_idx = _SRC.index("_project_contradictions = get_contradictions(")
        loop_idx = _SRC.index("for m in meetings:")
        assert fetch_idx < loop_idx, (
            "get_contradictions() deve ser buscada ANTES do laço por reunião, "
            "não dentro dele"
        )

    def test_bridge_contradictions_call_passes_the_prefetched_rows(self):
        call_idx = _SRC.index("AgentProvocations.bridge_contradictions(")
        block = _SRC[call_idx:call_idx + 200]
        assert "contradictions=_project_contradictions" in block

    def test_only_one_get_contradictions_call_site_in_the_page(self):
        assert _SRC.count("get_contradictions(") == 1
