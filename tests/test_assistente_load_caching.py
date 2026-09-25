# tests/test_assistente_load_caching.py
"""
NAV-09 (melhorias/parciais/navegabilidade.md, PC219): pages/Assistente.py
era a página mais lenta medida em produção (16,9s). Duas queries reais ao
Supabase rodavam sem cache no caminho de carregamento principal —
transcript_chunks_table_exists() e get_embedding_coverage() — repetidas a
CADA rerun do chat (o script inteiro reroda a cada mensagem enviada), só
pra popular badges informativos na sidebar cujo valor não muda durante a
sessão.

Fix: as duas chamadas agora passam por wrappers @st.cache_data (300s e
120s respectivamente). Este teste renderiza a página duas vezes — 2
instâncias de AppTest, mesmo project_id — e confirma que as funções
subjacentes são chamadas 1 vez só, não 2 (a 2ª renderização bate no cache
global de processo preenchido pela 1ª).
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/Assistente.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    at.session_state["asst_api_key"] = "fake-key-for-tests"  # precisa passar do guard "Configure a chave de API"
    return at


class TestExpensiveLoadCallsAreCached:
    def test_chunks_table_check_and_embedding_coverage_called_once_across_two_reruns(self):
        # _chunks_table_ok_cached() não recebe parâmetro nenhum (é uma
        # checagem de schema, não de dado — genuinamente global, não por
        # projeto) — sua chave de cache é a MESMA em toda a sessão pytest,
        # então um resultado cacheado por outro teste (rodando antes deste
        # na mesma sessão) vazaria pra cá. st.cache_data.clear() no início
        # evita a mesma armadilha já documentada em outros arquivos deste
        # projeto (cache global do processo sobrevivendo entre AppTest).
        st.cache_data.clear()
        pid = f"nav09-asst-{next(_pid_counter)}"
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("core.project_store.transcript_chunks_table_exists") as _tce, \
             patch("core.project_store.get_embedding_coverage") as _gec:
            _tce.return_value = True
            _gec.return_value = {"indexed_meetings": 1, "total_meetings": 1, "total_chunks": 10}

            at1 = _base_app(pid)
            at1.run()
            assert not at1.exception, f"1ª execução falhou: {at1.exception}"

            # 2ª renderização — instância NOVA de AppTest (não um 2º .run()
            # na mesma instância: st.feedback ("thumbs", renderizado por
            # mensagem do histórico) tem uma limitação conhecida do
            # framework AppTest ao reintrospectar o widget tree num rerun
            # da MESMA instância). st.cache_data é um cache global do
            # processo — uma instância nova com o mesmo pid ainda deve
            # bater no cache preenchido pela 1ª, o que já prova que a
            # cache sobrevive entre "carregamentos de página".
            at2 = _base_app(pid)
            at2.run()
            assert not at2.exception, f"2ª execução falhou: {at2.exception}"

        assert _tce.call_count == 1, (
            f"transcript_chunks_table_exists() chamada {_tce.call_count}x em 2 reruns "
            "— cache pode ter regredido"
        )
        assert _gec.call_count == 1, (
            f"get_embedding_coverage() chamada {_gec.call_count}x em 2 reruns "
            "— cache pode ter regredido"
        )
