# tests/test_guides_scroll_fix.py
"""
NAV-13, parte "guias nativos" (melhorias/parciais/navegabilidade.md):
Glossário, Guia CKF, Cache LLM e Avaliação e Feedback rodam dentro de
st.components.v1.html() com altura fixa (860/900px) e scrolling=True —
conteúdo maior que isso cria uma 2ª barra de rolagem (a do iframe, além da
da página do Streamlit). Glossário tinha ainda um problema mais concreto:
o índice alfabético lateral (nav) tinha sua PRÓPRIA rolagem independente
(overflow-y: auto + height: calc(100vh - 97px)) — rolar o índice não
rolava o conteúdo, e vice-versa.

Fix: altura fixa aumentada pra 1600px nas 4 páginas (reduz a frequência da
rolagem interna pra conteúdo típico — não há mecanismo de auto-altura via
JS nesta rodada, o plano documenta isso como fallback aceitável); rolagem
independente do índice do Glossário removida.

Teste estático (regex sobre o texto-fonte) — não uma checagem visual real
(AppTest não renderiza CSS/iframe), mas evita regressão do valor numérico
e da CSS específica que causava a rolagem dupla concreta do Glossário.
"""

import re
from pathlib import Path

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"

_GUIDE_FILES = [
    "Orientacoes_Glossario.py",
    "Orientacoes_CKF.py",
    "Orientacoes_CacheSemantico.py",
    "Orientacoes_Feedback.py",
]


class TestGuideIframeHeightIncreased:
    def test_all_four_guides_use_a_taller_fixed_height(self):
        for fname in _GUIDE_FILES:
            src = (_PAGES_DIR / fname).read_text(encoding="utf-8")
            m = re.search(r"components\.v?1?\.?html\([^)]*?height=(\d+)", src)
            assert m, f"{fname}: chamada a components.html com height= não encontrada"
            height = int(m.group(1))
            assert height >= 1600, (
                f"{fname}: height={height}, esperava >= 1600 (era 860/900 antes do NAV-13)"
            )


class TestGlossarioNavNoLongerHasIndependentScroll:
    def test_nav_sidebar_css_has_no_own_overflow_or_fixed_height(self):
        src = (_PAGES_DIR / "Orientacoes_Glossario.py").read_text(encoding="utf-8")
        nav_block = re.search(r"nav\s*\{\{(.*?)\}\}", src, re.DOTALL)
        assert nav_block, "bloco de CSS do seletor 'nav' não encontrado"
        block_text = nav_block.group(1)
        assert "overflow-y" not in block_text, (
            "nav ainda tem overflow-y próprio — reabre a rolagem dupla "
            "(índice rola independente do conteúdo)"
        )
        assert "height: calc(100vh" not in block_text, (
            "nav ainda tem altura fixa baseada em 100vh — reabre a rolagem dupla"
        )
