# tests/test_report_backfill_admin_gate.py
"""
NAV-07a (melhorias/parciais/navegabilidade.md, PC215): pages/ReportBackfill.py
tinha zero gate de is_admin() e ficava registrado na seção "Análise" de
app.py, visível a QUALQUER usuário autenticado — a única página tipo-
backfill do app fora de "Manutenção" (todas as outras 10 só aparecem
quando _admin é True). Um usuário comum conseguia disparar
AgentSynthesizer (custo real de LLM) pra qualquer reunião do próprio
contexto sem nenhuma checagem de perfil.

Fix: como todo o resto do app, a página não se autogatilha internamente
(nenhuma página de Manutenção faz isso) — a exclusão vem de app.py só
incluir a seção "Manutenção" no dict passado a st.navigation() quando
is_admin() é True. Movido pages/ReportBackfill.py de "Análise" para
"Manutenção", título do menu alinhado à convenção das páginas irmãs
("Backfill — X").

Este teste faz uma checagem estática sobre o texto-fonte de app.py — testar
via AppTest exigiria simular todo o boot de app.py (st.set_page_config +
st.navigation + pg.run() executando a página default), overhead
desproporcional pra confirmar posicionamento de 1 st.Page() num dict.
"""

import re
from pathlib import Path

_APP_SRC = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")


def _section_block(name: str) -> str:
    """Extrai o texto do bloco de uma lista de páginas em app.py, do
    st.Page(...) até o próximo `],` que fecha a lista dessa seção."""
    start = _APP_SRC.index(f'"{name}": [')
    end = _APP_SRC.index("],", start)
    return _APP_SRC[start:end]


def _manutencao_block() -> str:
    marker = 'pages["Manutenção"] = ['
    start = _APP_SRC.index(marker) + len(marker)
    end = _APP_SRC.index("]", start)
    return _APP_SRC[start:end]


class TestReportBackfillNotInAnalise:
    def test_report_backfill_absent_from_analise_section(self):
        assert "ReportBackfill" not in _section_block("Análise")


class TestReportBackfillInManutencao:
    def test_report_backfill_present_in_manutencao_section(self):
        assert "pages/ReportBackfill.py" in _manutencao_block()

    def test_manutencao_section_only_registered_for_admin(self):
        # A seção inteira (inclusive ReportBackfill) só existe dentro do
        # `if _admin:` — sem is_admin() interno na própria página, é essa
        # a checagem real que impede um usuário comum de alcançá-la.
        guard_idx = _APP_SRC.index("if _admin:", _APP_SRC.index("pages = {"))
        manutencao_idx = _APP_SRC.index('pages["Manutenção"]')
        assert guard_idx < manutencao_idx

    def test_menu_title_follows_backfill_sibling_naming_convention(self):
        block = _manutencao_block()
        m = re.search(r'st\.Page\("pages/ReportBackfill\.py",\s*title="([^"]+)"', block)
        assert m, "st.Page(...) do ReportBackfill não encontrado no bloco de Manutenção"
        title = m.group(1)
        assert title.startswith("Backfill"), (
            f'título "{title}" não segue a convenção das páginas irmãs '
            '("Backfill — Provocações", "Backfill — PII")'
        )
