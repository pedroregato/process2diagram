# tests/test_artefatos_pages_boot_smoke.py
"""
Boot-smoke coverage for the new "Artefatos" section pages introduced in
PC208 (claude_guideline/roadmap.md) — pages/Artefatos.py was split into a
Visão Geral (KPIs + export + navegação) plus 5 subseções por assunto.

3 of the 5 subseções already had dedicated regression tests before the split
(test_artefatos_provocations_tab.py -> ArtefatosQualidade.py,
test_artefatos_sbvr_pagination.py / test_artefatos_bpmn_toggle_stable_container.py
-> ArtefatosModelagem.py). This file covers the remaining 3 pages that never
had a test of their own: the reduced pages/Artefatos.py (Visão Geral),
ArtefatosRequisitos.py, ArtefatosReunioes.py and ArtefatosDebates.py — each
just asserts the page renders without exception when authenticated with an
active project and all Supabase-backed loaders mocked to return empty data.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

# Mesmo workaround usado nos demais testes de Artefatos: AppTest.from_file()
# roda a página isolada de app.py, então st.page_link() para uma página irmã
# (Home.py, ou as outras páginas da seção) não resolve nesse contexto.
st.page_link = lambda *a, **k: None

_PS = "ui.artefatos_shared"


def _base_app(path: str) -> AppTest:
    at = AppTest.from_file(path, default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = "pc208-boot-smoke"
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


class TestVisaoGeralBootSmoke:
    def test_renders_without_exception(self):
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: []), \
             patch(f"{_PS}.list_requirements_light", lambda pid: []), \
             patch(f"{_PS}.list_contradictions", lambda pid: []), \
             patch(f"{_PS}.list_sbvr_terms", lambda pid: []), \
             patch(f"{_PS}.list_sbvr_rules", lambda pid: []), \
             patch(f"{_PS}.list_bpmn_processes", lambda pid: []), \
             patch(f"{_PS}.bpmn_tables_exist", lambda: False), \
             patch(f"{_PS}.list_documents", lambda pid, **_: []), \
             patch(f"{_PS}.get_asset_metadata_map", lambda pid: {}), \
             patch(f"{_PS}.list_provocations_by_project", lambda pid, status=None: []):
            at = _base_app("pages/Artefatos.py")
            at.run()
        assert not at.exception
        # st.page_link é monkeypatchado para no-op neste arquivo (mesmo
        # workaround dos demais testes de Artefatos — não resolve página
        # irmã fora de app.py), então os cards de navegação não aparecem
        # como elementos; a asserção que importa é a ausência de exceção.
        headers = " ".join(h.value for h in at.markdown if h.value.startswith("####"))
        assert "Requisitos" in headers and "Modelagem Formal" in headers


class TestArtefatosRequisitosBootSmoke:
    def test_renders_without_exception(self):
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: []), \
             patch(f"{_PS}.list_requirements_light", lambda pid: []), \
             patch(f"{_PS}.list_contradictions", lambda pid: []), \
             patch(f"{_PS}.list_documents", lambda pid, **_: []), \
             patch(f"{_PS}.get_asset_metadata_map", lambda pid: {}):
            at = _base_app("pages/ArtefatosRequisitos.py")
            at.run()
        assert not at.exception


class TestArtefatosReunioesBootSmoke:
    def test_renders_without_exception(self):
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: []), \
             patch(f"{_PS}.list_requirements_light", lambda pid: []), \
             patch(f"{_PS}.list_sbvr_terms", lambda pid: []), \
             patch(f"{_PS}.list_sbvr_rules", lambda pid: []), \
             patch(f"{_PS}.list_bpmn_processes", lambda pid: []), \
             patch(f"{_PS}.list_documents", lambda pid, **_: []), \
             patch(f"{_PS}.get_asset_metadata_map", lambda pid: {}):
            at = _base_app("pages/ArtefatosReunioes.py")
            at.run()
        assert not at.exception

    def test_comparar_needs_at_least_2_meetings(self):
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: [
                 {"id": "m1", "meeting_number": 1, "title": "R1", "meeting_date": "2026-01-01"},
             ]), \
             patch(f"{_PS}.list_requirements_light", lambda pid: []), \
             patch(f"{_PS}.list_sbvr_terms", lambda pid: []), \
             patch(f"{_PS}.list_sbvr_rules", lambda pid: []), \
             patch(f"{_PS}.list_bpmn_processes", lambda pid: []), \
             patch(f"{_PS}.list_documents", lambda pid, **_: []), \
             patch(f"{_PS}.get_asset_metadata_map", lambda pid: {}):
            at = _base_app("pages/ArtefatosReunioes.py")
            at.run()
        assert not at.exception
        infos = " ".join(i.value for i in at.info)
        assert "ao menos 2 reuniões" in infos


class TestArtefatosDebatesBootSmoke:
    def test_renders_without_exception(self):
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: []), \
             patch(f"{_PS}.list_argumentation_by_project", lambda pid: []):
            at = _base_app("pages/ArtefatosDebates.py")
            at.run()
        assert not at.exception
