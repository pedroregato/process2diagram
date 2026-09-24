# tests/test_artefatos_reports_tab.py
"""
NAV-07b (melhorias/parciais/navegabilidade.md, PC218): pages/ReportBackfill.py
(geração/regeneração de Relatório Executivo) virou admin-only no NAV-07a
(PC215) — mas usuários comuns ainda precisam conseguir LER relatórios já
gerados, sem depender de um admin. Fix: seção "📄 Relatórios das Reuniões"
somente-leitura na Central de Artefatos (pages/Artefatos.py), usando
core.project_store.list_reports_by_project() (já existia, sem nenhum
consumidor até agora) + get_report_html().
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_PS = "ui.artefatos_shared"
_pid_counter = iter(range(1, 1000))

_COMMON_MOCKS = dict(
    list_meetings=lambda pid: [],
    list_requirements_light=lambda pid: [],
    list_contradictions=lambda pid: [],
    list_sbvr_terms=lambda pid: [],
    list_sbvr_rules=lambda pid: [],
    list_bpmn_processes=lambda pid: [],
    bpmn_tables_exist=lambda: False,
    list_documents=lambda pid, **_: [],
    get_asset_metadata_map=lambda pid: {},
    list_provocations_by_project=lambda pid, status=None: [],
)


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/Artefatos.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"  # usuário comum — o ponto do NAV-07b
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


def _patched(reports, report_html_map):
    patches = [patch("modules.supabase_client.supabase_configured", lambda: True)]
    for name, fn in _COMMON_MOCKS.items():
        patches.append(patch(f"{_PS}.{name}", fn))
    patches.append(patch("core.project_store.list_reports_by_project", lambda pid: reports))
    patches.append(patch("core.project_store.get_report_html", lambda mid: report_html_map.get(mid)))
    return patches


class TestNoReportsYet:
    def test_shows_empty_state_no_selectbox(self):
        pid = f"nav07b-test-{next(_pid_counter)}"
        patches = _patched(reports=[], report_html_map={})
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
             patches[6], patches[7], patches[8], patches[9], patches[10], patches[11]:
            at = _base_app(pid)
            at.run()

        assert not at.exception
        assert [i for i in at.info if "Nenhum relatório executivo gerado" in i.value]
        assert not [sb for sb in at.selectbox if sb.key == "art_report_sel"]


class TestReportsAvailable:
    def _run(self, pid):
        reports = [
            {"id": "m1", "meeting_number": 1, "title": "Kickoff", "meeting_date": "2026-01-15"},
            {"id": "m2", "meeting_number": 2, "title": "Sprint Review", "meeting_date": "2026-02-01"},
        ]
        html_map = {"m1": "<html><body>Relatório 1</body></html>",
                    "m2": "<html><body>Relatório 2</body></html>"}
        patches = _patched(reports=reports, report_html_map=html_map)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
             patches[6], patches[7], patches[8], patches[9], patches[10], patches[11]:
            at = _base_app(pid)
            at.run()
        return at

    def test_selectbox_renders_and_page_does_not_raise(self):
        # AppTest (nesta versão do Streamlit) não expõe st.download_button
        # na árvore de elementos inspecionável — a cobertura possível aqui é
        # ausência de exceção (cobre o download_button + components.html do
        # preview) e a presença do seletor de reunião.
        pid = f"nav07b-test-{next(_pid_counter)}"
        at = self._run(pid)

        assert not at.exception
        sel = [sb for sb in at.selectbox if sb.key == "art_report_sel"]
        assert sel, "seletor de reunião com relatório não encontrado"
        assert "Kickoff" in sel[0].value

    def test_caption_points_regular_users_to_an_admin_for_generation(self):
        """O ponto central do NAV-07b: usuário comum LÊ relatórios aqui, mas
        gerar/regenerar continua restrito a admin (NAV-07a) — a aba precisa
        deixar isso explícito, não sugerir que dá pra gerar por aqui."""
        pid = f"nav07b-test-{next(_pid_counter)}"
        at = self._run(pid)

        assert not at.exception
        captions = " ".join(c.value for c in at.caption)
        assert "administrador" in captions
