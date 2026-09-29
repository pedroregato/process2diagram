# tests/test_document_manager_caching.py
"""
NAV-17 (melhorias/parciais/navegabilidade.md): pages/DocumentManager.py usa
st.tabs (7 abas — todos os corpos executam a cada rerun, não só a visível)
e chamava list_documents(project_id, ...) sem cache em 4 pontos diferentes
(Biblioteca, Extrair Artefatos, Análise Cruzada, Doc × Doc), e a query de
reuniões (_list_meetings, antes sem @st.cache_data e fechada sobre
project_id via closure em vez de parâmetro — bug latente de cache-key se
algum dia virasse cache_data sem essa correção) em mais 2. Até 6 idas ao
Supabase por load, mesmo mudando só um widget de outra aba.

Fix: um único _cached_list_documents(pid, ...) e _list_meetings(pid) com
@st.cache_data(ttl=...) — todas as 4/2 chamadas passam a usar os wrappers,
compartilhando cache entre abas. _list_meetings virou parâmetro explícito
de project_id (era closure sobre a variável do módulo) — pré-condição pra
cachear corretamente (senão a 1ª chamada travaria o resultado no cache
para qualquer projeto, cache key teria que incluir project_id de algum
jeito).

Checagem estática — a página depende de contexto de sessão + Supabase
configurado; simular via AppTest só pra confirmar wiring de cache não
compensa o overhead.
"""

from pathlib import Path

_SRC = (
    Path(__file__).resolve().parent.parent / "pages" / "DocumentManager.py"
).read_text(encoding="utf-8")


class TestCachedWrappersExist:
    def test_cached_list_documents_wrapper_defined_with_cache_data(self):
        anchor = _SRC.index("def _cached_list_documents(")
        block = _SRC[max(0, anchor - 150):anchor]
        assert "@st.cache_data(" in block

    def test_list_meetings_now_takes_project_id_as_a_parameter_and_is_cached(self):
        anchor = _SRC.index("def _list_meetings(pid: str)")
        block = _SRC[max(0, anchor - 150):anchor]
        assert "@st.cache_data(" in block


class TestAllCallSitesUseTheCachedWrappers:
    def test_no_raw_list_documents_call_remains(self):
        # list_documents(...) só deve aparecer na própria definição do
        # wrapper (import + chamada interna "return list_documents(pid...")
        # — nenhum call site solto fora dele.
        raw_calls = [
            line for line in _SRC.splitlines()
            if "list_documents(" in line
            and "_cached_list_documents" not in line
            and "import" not in line
            and not line.strip().startswith("#")
            and "return list_documents(pid" not in line
        ]
        assert raw_calls == [], f"chamadas diretas a list_documents() ainda existem: {raw_calls}"

    def test_no_raw_list_meetings_call_without_project_id_remains(self):
        assert "_list_meetings()" not in _SRC  # sem argumento = versão antiga
        assert _SRC.count("_list_meetings(project_id)") == 2
