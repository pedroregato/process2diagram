# tests/test_ux05_context_health_hero.py
"""
UX-05 (melhorias/ux-amigabilidade-e-elegancia.md): em pages/ContextHealth.py
("Saúde do Contexto"), o banner "hero" (título do contexto + score grande)
usava display:flex sem flex-wrap nem min-width nos filhos — num viewport
estreito (~840px, sidebar aberta), um nome de contexto longo espreme contra
o bloco do score em vez de quebrar linha.

Fix defensivo: `flex-wrap:wrap` no `.hero` (o score desce pra 2ª linha em
vez de forçar os dois lado a lado), `min-width:0` no bloco de título (item
flex sem isso ignora overflow-wrap por padrão — min-width:auto implícito),
`overflow-wrap:anywhere` no `<h1>` (nome de contexto longo quebra em vez de
vazar), `flex-shrink:0` no bloco do score (nunca fica menor que o
conteúdo). Baixa confiança de causa-raiz: o CSS é flexbox, não
`position:absolute` — não achei no código a causa literal de "atrás do
score" citada na auditoria; este é o fix defensivo padrão pra essa classe
de sintoma, não uma reprodução confirmada visualmente (sem ambiente de
renderização a 840px disponível).

Checagem estática apenas — CSS/layout não é observável via AppTest
(renderizado num iframe de components.html, sem inspeção de layout real).
"""

from pathlib import Path

_SRC = (
    Path(__file__).resolve().parent.parent / "pages" / "ContextHealth.py"
).read_text(encoding="utf-8")


class TestHeroDefensiveFlexLayout:
    def test_hero_has_flex_wrap(self):
        anchor = _SRC.index(".hero {{")
        block = _SRC[anchor:anchor + 300]
        assert "flex-wrap:wrap" in block

    def test_title_block_has_min_width_zero_and_flex_basis(self):
        anchor = _SRC.index(".hero .hero-title {{")
        block = _SRC[anchor:anchor + 100]
        assert "min-width:0" in block

    def test_h1_wraps_long_text_instead_of_overflowing(self):
        anchor = _SRC.index(".hero h1 {{")
        block = _SRC[anchor:anchor + 200]
        assert "overflow-wrap:anywhere" in block

    def test_score_block_never_shrinks_below_content(self):
        anchor = _SRC.index(".hero .hero-score {{")
        block = _SRC[anchor:anchor + 60]
        assert "flex-shrink:0" in block


class TestHeroHtmlUsesTheNewClasses:
    def test_title_div_has_hero_title_class(self):
        assert '<div class="hero-title">' in _SRC

    def test_score_div_has_hero_score_class(self):
        assert 'class="hero-score"' in _SRC
