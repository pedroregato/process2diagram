# tests/test_deep_links_wiring.py
"""
NAV-12: checagem estática de que as páginas listadas no plano
(melhorias/parciais/navegabilidade.md — Diagramas, Editor BPMN, Assistente,
Reuniões) realmente chamam resolve_context_from_query_params() cedo (antes
de qualquer seletor de contexto), e que pages/Home.py gera os links das
"Reuniões recentes" com ?ctx=/?meeting= em vez de st.page_link genérico.

Mesmo padrão de tests/test_report_backfill_admin_gate.py: testar via
AppTest exigiria simular sessão autenticada + Supabase + contexto ativo
pra cada uma das 5 páginas — overhead desproporcional pra confirmar que a
chamada existe e está posicionada antes do seletor de contexto. O
comportamento de resolve_context_from_query_params() em si já tem
cobertura funcional em tests/test_deep_links.py.
"""

from pathlib import Path

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"

_DEEP_LINK_PAGES = [
    "Diagramas.py",
    "BpmnEditor.py",
    "Assistente.py",
    "ArtefatosReunioes.py",
]


def _strip_comment_lines(src: str) -> str:
    # Evita falso-positivo quando um comentário explicativo (ex.: "roda
    # antes de require_active_project()") menciona o nome da função de
    # propósito, antes da chamada real — só o CÓDIGO importa pra ordem.
    return "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("#")
    )


class TestResolveContextCalledBeforeContextSelector:
    def test_all_four_pages_import_and_call_resolve_context(self):
        for fname in _DEEP_LINK_PAGES:
            raw_src = (_PAGES_DIR / fname).read_text(encoding="utf-8")
            assert "resolve_context_from_query_params" in raw_src, (
                f"{fname}: NAV-12 exige resolve_context_from_query_params() "
                "pra ?ctx= funcionar como link compartilhável"
            )
            src = _strip_comment_lines(raw_src)
            call_idx = src.index("resolve_context_from_query_params()")
            # Precisa rodar antes de qualquer seletor de contexto conhecido
            # (require_active_project / render_active_context_picker) —
            # senão o ?ctx= chega tarde demais pra influenciar a escolha.
            for selector in ("require_active_project(", "render_active_context_picker("):
                if selector in src:
                    selector_idx = src.index(selector)
                    assert call_idx < selector_idx, (
                        f"{fname}: resolve_context_from_query_params() roda "
                        f"DEPOIS de {selector} — ?ctx= chega tarde demais"
                    )


class TestPerPageDeepLinkParams:
    def test_diagramas_reads_and_writes_process_and_version(self):
        src = (_PAGES_DIR / "Diagramas.py").read_text(encoding="utf-8")
        assert 'st.query_params["process"]' in src
        assert 'st.query_params["v"]' in src

    def test_bpmn_editor_reads_and_writes_process_and_version(self):
        src = (_PAGES_DIR / "BpmnEditor.py").read_text(encoding="utf-8")
        assert 'st.query_params["process"]' in src
        assert 'st.query_params["v"]' in src

    def test_assistente_reads_meeting_param(self):
        src = (_PAGES_DIR / "Assistente.py").read_text(encoding="utf-8")
        assert "get_query_param_int" in src
        assert '"meeting"' in src

    def test_artefatos_reunioes_reads_meeting_param_and_expands(self):
        src = (_PAGES_DIR / "ArtefatosReunioes.py").read_text(encoding="utf-8")
        assert "_deeplink_meeting_num" in src
        assert "expanded=_is_deeplinked" in src


class TestHomeGeneratesScopedLinks:
    def test_home_uses_switch_page_with_pending_meeting_for_assistant_and_editor(self):
        src = (_PAGES_DIR / "Home.py").read_text(encoding="utf-8")
        assert '_pending_meeting_number' in src
        assert 'st.switch_page("pages/Assistente.py")' in src
        assert 'st.switch_page("pages/BpmnEditor.py")' in src

    def test_home_sets_ctx_query_param_from_active_context_sigla(self):
        src = (_PAGES_DIR / "Home.py").read_text(encoding="utf-8")
        assert "active_context_sigla()" in src
        assert 'st.query_params["ctx"]' in src
