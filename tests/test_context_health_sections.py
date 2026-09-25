# tests/test_context_health_sections.py
"""
NAV-09 (melhorias/parciais/navegabilidade.md, PC219): pages/ContextHealth.py
(Saúde do Contexto) usava st.tabs() pras 5 seções — Streamlit executa o
corpo de TODAS as abas a cada rerun, independente de qual está visível.
Medido em produção: 13,2s de carregamento (5 abas, 20 expanders — nenhum
deles em loop realmente ilimitado, os 20 vêm da soma das 5 abas inteiras
sempre computando/renderizando juntas). Fix: st.radio(horizontal=True) no
lugar de st.tabs() — só a seção escolhida executa.

Também corrigido (mesmo achado do plano): a mensagem "Nenhum requisito
encontrado para este contexto" não distinguia "genuinamente vazio" de
"a busca falhou" (exceção engolida silenciosamente em _load_requirements,
sem nenhum log) — achado em produção com um contexto de 885 requisitos
reais mostrando essa mensagem. Não foi possível reproduzir a causa exata
em revisão de código; a mensagem agora não afirma categoricamente que não
há requisitos, e a exceção é logada (antes: silenciosa, sem rastro algum).
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from modules.meeting_roi_calculator import MeetingROIData

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def single(self):
        return self

    def execute(self):
        return _Resp(self._data)


class _FakeDB:
    """Devolve lista vazia pra qualquer tabela — cada loader de
    ContextHealth.py já trata isso como "sem dados" (fail-open)."""
    def table(self, name):
        return _FakeQuery([])


def _fake_meeting_roi(n: int) -> list[MeetingROIData]:
    return [
        MeetingROIData(
            meeting_number=i, title=f"Reunião {i}", date="2026-01-01", meeting_id=f"m{i}",
            has_minutes=True, has_transcript=True,
            n_participants=3, n_decisions=2, n_actions_total=4, n_actions_complete=2,
            n_requirements=5, n_sbvr=1, n_bpmn_procs=1,
            word_count=1200, duration_min=45.0, duration_hours=0.75,
            cycle_signals=0, trc=10.0,
            meeting_type="planning", meeting_type_confidence=0.9, fulfillment_score=0.8,
            dc_score=0.7, cost_estimate=100.0, roi_tr=8.0,
            cost_per_hour=150.0,
        )
        for i in range(1, n + 1)
    ]


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/ContextHealth.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


def _run(pid: str) -> AppTest:
    with patch("modules.supabase_client.supabase_configured", lambda: True), \
         patch("modules.supabase_client.get_supabase_client", lambda: _FakeDB()), \
         patch("modules.meeting_roi_calculator.compute_project_roi",
               lambda pid, cost_per_hour=150.0: _fake_meeting_roi(3)), \
         patch("core.project_store.list_contradictions", lambda pid: []):
        at = _base_app(pid)
        at.run()
    return at


class TestSectionsRenderOnlyTheSelected:
    def test_default_section_renders_without_exception(self):
        pid = f"nav09-ch-{next(_pid_counter)}"
        at = _run(pid)
        assert not at.exception
        radio = [r for r in at.radio if r.key == "ch_view"]
        assert radio, "seletor de seção (st.radio) não encontrado"
        assert radio[0].value == "📈 Qualidade & Evolução"

    def test_default_section_does_not_render_alerts_content(self):
        pid = f"nav09-ch-{next(_pid_counter)}"
        at = _run(pid)
        assert not at.exception
        headers = " ".join(m.value for m in at.markdown)
        assert "Contradições em Versões de Requisitos" not in headers, (
            "conteúdo da seção Alertas apareceu com Qualidade & Evolução "
            "selecionada — st.tabs() pode ter voltado (renderiza tudo sempre)"
        )

    def test_switching_to_alerts_renders_its_content_not_others(self):
        pid = f"nav09-ch-{next(_pid_counter)}"
        at = _run(pid)
        radio = [r for r in at.radio if r.key == "ch_view"]
        radio[0].set_value("⚡ Alertas & Insights").run()

        assert not at.exception
        headers = " ".join(m.value for m in at.markdown)
        assert "Contradições em Versões de Requisitos" in headers
