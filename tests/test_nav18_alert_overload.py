# tests/test_nav18_alert_overload.py
"""
NAV-18 (melhorias/parciais/navegabilidade.md): pages/ArtefatosDebates.py e
pages/ArtefatosQualidade.py renderizavam um st.info/warning/error/success
por ITEM dentro de laços (174 questões IBIS no SDEA, medido em produção:
293 blocos de alerta em Debates, 96 em Qualidade). Um alerta colorido faz
sentido isolado; centenas deles na mesma tela é ruído visual — perde
significado (o verde de "sucesso" ao lado de dezenas de outros).

Fix: dentro dos laços por item (resolução de questão IBIS, sugestão de
ambiguidade, impacto/recomendação de lacuna, pergunta de provocação),
st.info/warning/error/success vira st.markdown com ícone ou st.caption —
mesmo conteúdo, sem o bloco colorido. Mensagens de estado ÚNICAS (vazio,
erro de configuração, feedback transiente pós-clique) NÃO mudam — seguem
sendo o uso apropriado de alerta; só o padrão "1 alerta por item numa
lista longa" é o problema.

Checagem estática (mesmo padrão de tests/test_report_backfill_admin_gate.py)
sobre os trechos específicos citados na auditoria (ArtefatosDebates.py
L329-331/671-675; ArtefatosQualidade.py L173/206-208/280) — dinamizar via
AppTest exigiria semear 174 questões IBIS fake, overhead desproporcional
pra confirmar que uma chamada de função foi trocada por outra.
"""

from pathlib import Path

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"


def _read(fname: str) -> str:
    return (_PAGES_DIR / fname).read_text(encoding="utf-8")


class TestArtefatosDebatesResolutionNoLongerUsesColoredAlerts:
    def test_per_question_resolution_block_has_no_info_warning_or_error(self):
        src = _read("ArtefatosDebates.py")
        # Ancora no trecho do laço de resolução por questão (modo Lista).
        anchor = src.index('if res_type != "unresolved":')
        block = src[anchor:anchor + 600]
        assert "st.info(" not in block
        assert "st.warning(" not in block
        assert "st.error(" not in block
        assert "st.markdown(f\"💡 **Resolução:**" in block
        assert "st.caption(\"❓ Questão sem resolução" in block

    def test_popover_resolution_block_has_no_info_or_warning(self):
        src = _read("ArtefatosDebates.py")
        anchor = src.index('with st.popover("ℹ️"):')
        block = src[anchor:anchor + 400]
        assert "st.info(" not in block
        assert "st.warning(" not in block


class TestArtefatosQualidadePerItemBlocksNoLongerUseColoredAlerts:
    def test_ambiguity_suggestion_has_no_info(self):
        src = _read("ArtefatosQualidade.py")
        anchor = src.index('if _amb.get("suggestion"):')
        block = src[anchor:anchor + 250]
        assert "st.info(" not in block
        assert "st.markdown(" in block

    def test_gap_impact_and_recommendation_have_no_warning_or_success(self):
        src = _read("ArtefatosQualidade.py")
        anchor = src.index('if _gap.get("impact"):')
        block = src[anchor:anchor + 250]
        assert ".warning(" not in block
        assert ".success(" not in block
        assert ".markdown(" in block

    def test_provocation_question_has_no_info(self):
        src = _read("ArtefatosQualidade.py")
        anchor = src.index('st.markdown(p.get("body", ""))')
        block = src[anchor:anchor + 200]
        assert "st.info(" not in block
        assert "st.markdown(" in block


class TestOneOffStatusAlertsUnchanged:
    """Mensagens de estado únicas (não-por-item) continuam usando alerta —
    não fazem parte do problema do NAV-18, servem exatamente pro que
    st.info/success foi desenhado."""

    def test_debates_empty_state_still_uses_info(self):
        src = _read("ArtefatosDebates.py")
        assert 'st.info("Nenhum mapa argumentativo IBIS registrado' in src

    def test_qualidade_empty_state_still_uses_info_or_success(self):
        src = _read("ArtefatosQualidade.py")
        assert 'st.info("Nenhuma análise de ruídos registrada' in src
        assert "Nenhuma provocação gerada ainda neste projeto" in src
