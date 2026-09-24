# tests/test_active_context_picker.py
"""
NAV-04 (melhorias/parciais/navegabilidade.md, PC213): três sintomas com a
mesma causa raiz — nenhuma fonte única para o contexto de trabalho ativo.

1. pages/Diagramas.py sincronizava o contexto por uma chave de widget
   (diag_sb_proj) guardada com um flag "_diag_synced_pid". O Streamlit
   descarta o valor de widgets de página ao navegar para outra página em
   st.navigation() e voltar — o flag "já sincronizado" ficava obsoleto e o
   seletor voltava ao primeiro contexto da lista, mesmo com um contexto
   diferente ativo em pages/Home.py.
2. pages/CostEstimator.py ignorava active_project_id por completo.
3. ui.project_selector.require_active_project() mandava o usuário para a
   Central de Operações (st.page_link + st.stop()) em vez de deixar
   escolher o contexto na própria página.

Fix: ui/project_selector.py::render_active_context_picker(key) — fonte
única: o índice do selectbox vem sempre de session_state["active_project_id"]
(nunca de uma chave de widget), e a troca só é gravada via on_change (nunca
no valor padrão do primeiro render, evitando ativar silenciosamente o
primeiro item da lista antes do usuário decidir). Diagramas.py e
CostEstimator.py passam a usar esse helper; require_active_project()
renderiza esse mesmo seletor inline quando não há contexto ativo, em vez de
redirecionar.

Este arquivo testa via AppTest: (a) o seletor de Diagramas.py permanece no
contexto ativo em duas execuções independentes com o mesmo
active_project_id (simula "navegar para outra página e voltar" — cada
AppTest.from_file() re-executa a página do zero, igual a uma navegação
real); (b) sem contexto ativo, uma página que chama require_active_project()
(ValidationHub.py) mostra o seletor inline e, após a escolha, renderiza o
conteúdo da página.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

# ui/project_selector.py é importado uma única vez por processo (ao
# contrário de uma pages/*.py, que o AppTest re-executa do zero a cada
# .run()) — os nomes que ele importa via "from core.project_store import
# X" já estão fixados no namespace de ui.project_selector na primeira
# importação. Patch precisa mirar esse namespace, não core.project_store
# (mesma armadilha documentada em tests/test_artefatos_sbvr_pagination.py
# para ui.artefatos_shared).
_PS = "ui.project_selector"

# @st.cache_data é global ao processo — cada teste precisa de um tenant_id
# (chave do cache de _load_tenant_contexts) próprio, nunca reutilizado
# (mesma armadilha documentada em tests/test_artefatos_provocations_tab.py
# e redescoberta em tests/test_validation_hub_pagination.py).
_tenant_counter = iter(range(1, 1000))


def _fake_contexts():
    return [
        {"id": "ctx-a", "name": "Contexto A", "sigla": "CTXA"},
        {"id": "ctx-b", "name": "Contexto B", "sigla": "CTXB"},
    ]


class TestDiagramasPersistsActiveContextAcrossRevisits:
    def test_selector_stays_on_active_context_across_two_independent_runs(self):
        tenant_id = f"nav04-tenant-{next(_tenant_counter)}"

        def _run_once():
            with patch(f"{_PS}.list_contexts", lambda tenant_id=None: _fake_contexts()), \
                 patch("modules.supabase_client.supabase_configured", lambda: True), \
                 patch("core.project_store.list_bpmn_processes", lambda pid: []):
                at = AppTest.from_file("pages/Diagramas.py", default_timeout=30)
                at.session_state["_autenticado"] = True
                at.session_state["_usuario_login"] = "teste"
                at.session_state["_role"] = "user"
                at.session_state["_tenant_id"] = tenant_id
                # Contexto ativo em OUTRA página (ex.: Home.py) — não é o
                # primeiro item de _fake_contexts().
                at.session_state["active_project_id"] = "ctx-b"
                at.session_state["active_project_name"] = "Contexto B"
                at.run()
                return at

        at1 = _run_once()
        assert not at1.exception
        sel1 = [sb for sb in at1.selectbox if sb.key == "diag_sb_proj"]
        assert sel1, "seletor de contexto não encontrado no 1º run"
        assert sel1[0].value == "Contexto B"

        # Segunda execução independente — simula sair da página e voltar
        # (o AppTest anterior não deixa nenhum estado de WIDGET residual
        # aqui; só active_project_id, que é a fonte única, é replicado).
        at2 = _run_once()
        assert not at2.exception
        sel2 = [sb for sb in at2.selectbox if sb.key == "diag_sb_proj"]
        assert sel2, "seletor de contexto não encontrado no 2º run"
        assert sel2[0].value == "Contexto B", (
            "o seletor voltou ao primeiro contexto da lista em vez de "
            "permanecer no contexto ativo — regressão do bug original do NAV-04"
        )


class TestRequireActiveProjectRendersInlinePicker:
    def _base_app(self, tenant_id: str) -> AppTest:
        at = AppTest.from_file("pages/ValidationHub.py", default_timeout=30)
        at.session_state["_autenticado"] = True
        at.session_state["_usuario_login"] = "teste"
        at.session_state["_usuario_nome"] = "Teste"
        at.session_state["_role"] = "admin"
        at.session_state["_tenant_id"] = tenant_id
        # Nenhum contexto ativo — o cenário do NAV-04.
        return at

    def test_no_active_context_shows_inline_picker_not_a_redirect(self):
        tenant_id = f"nav04-tenant-{next(_tenant_counter)}"
        with patch(f"{_PS}.list_contexts", lambda tenant_id=None: _fake_contexts()), \
             patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("core.project_store.list_requirements_light", lambda pid: []), \
             patch("core.project_store.list_meetings", lambda pid: []), \
             patch("core.project_store.list_meetings_quality", lambda pid: []), \
             patch("core.project_store.list_dmn_by_project", lambda pid: []), \
             patch("core.project_store.list_sbvr_terms", lambda pid: []), \
             patch("core.project_store.list_sbvr_rules", lambda pid: []), \
             patch("core.project_store.list_bpmn_processes", lambda pid: []), \
             patch("core.project_store.count_validation_status",
                   lambda pid: {"proposto": 0, "em_revisão": 0, "validado": 0, "ajustado": 0, "rejeitado": 0}):
            at = self._base_app(tenant_id)
            at.run()

        assert not at.exception
        # Seletor inline presente — nunca mandou pra Central de Operações
        # (não há st.page_link para pages/Home.py neste cenário).
        picker = [sb for sb in at.selectbox if sb.key == "require_active_ctx_sel"]
        assert picker, "seletor inline do contexto ativo não encontrado"
        # Conteúdo da página que só renderiza DEPOIS de require_active_project()
        # retornar (o filtro de status da Validação) ainda não deve aparecer —
        # nada foi escolhido nesta execução, a página parou em st.stop().
        assert not [sb for sb in at.selectbox if sb.key == "vhub_filter"]

    def test_choosing_a_context_activates_it_and_renders_page_content(self):
        tenant_id = f"nav04-tenant-{next(_tenant_counter)}"
        with patch(f"{_PS}.list_contexts", lambda tenant_id=None: _fake_contexts()), \
             patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("core.project_store.list_requirements_light", lambda pid: []), \
             patch("core.project_store.list_meetings", lambda pid: []), \
             patch("core.project_store.list_meetings_quality", lambda pid: []), \
             patch("core.project_store.list_dmn_by_project", lambda pid: []), \
             patch("core.project_store.list_sbvr_terms", lambda pid: []), \
             patch("core.project_store.list_sbvr_rules", lambda pid: []), \
             patch("core.project_store.list_bpmn_processes", lambda pid: []), \
             patch("core.project_store.count_validation_status",
                   lambda pid: {"proposto": 0, "em_revisão": 0, "validado": 0, "ajustado": 0, "rejeitado": 0}):
            at = self._base_app(tenant_id)
            at.run()
            assert not at.exception

            picker = [sb for sb in at.selectbox if sb.key == "require_active_ctx_sel"]
            assert picker
            # "Contexto A" já é o valor padrão (índice 0, nenhum contexto
            # ativo ainda) — selecionar o MESMO valor não é uma mudança real,
            # e on_change corretamente não dispararia. "Contexto B" força uma
            # troca genuína.
            assert picker[0].value == "Contexto A"
            picker[0].select("Contexto B").run()

        assert not at.exception
        assert "active_project_id" in at.session_state
        assert at.session_state["active_project_id"] == "ctx-b"
        assert at.session_state["active_project_name"] == "Contexto B"
        assert [sb for sb in at.selectbox if sb.key == "vhub_filter"], (
            "conteúdo da página não renderizou depois de escolher o contexto"
        )
