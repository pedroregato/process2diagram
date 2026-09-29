# tests/test_ux04_real_artifact_counts.py
"""
UX-04 (melhorias/ux-amigabilidade-e-elegancia.md): a Visão Geral de
Artefatos (pages/Artefatos.py) mostrava "—" nos KPIs de Decisões DMN e
Questões IBIS, e "…" nas legendas dos cards de Debates/Qualidade &
Sinais, sempre que o usuário ainda não tivesse visitado a subseção
correspondente NESTA sessão — o valor real só vinha de session_state
populado por ArtefatosModelagem/Debates/Qualidade.py. Ambíguo: "—" lê
como zero ou "quebrado", não como "ainda não carregado".

Fix: DMN/IBIS/Ruídos passam a ser buscados no mesmo ThreadPoolExecutor
que já carrega meetings/requirements/etc. — usando os MESMOS loaders
@st.cache_data(ttl=300) de ui/artefatos_shared.py que as páginas de
detalhe usam (mesma fonte de dados, por isso um cache-hit se o usuário
depois visitar Modelagem Formal/Debates/Qualidade — não paga a consulta
2x). KPIs e legendas mostram contagem real sempre, sem placeholder.

Checagem estática (mesmo padrão de tests/test_report_backfill_admin_gate.py)
— dinamizar exigiria simular sessão + Supabase fake pra um pool de 12
loaders; o teste unitário do que importa (dado real em vez de placeholder
ambíguo) é observável direto no código-fonte.
"""

from pathlib import Path

_ARTEFATOS_SRC = (
    Path(__file__).resolve().parent.parent / "pages" / "Artefatos.py"
).read_text(encoding="utf-8")


class TestNoAmbiguousPlaceholders:
    def test_no_em_dash_placeholder_in_dmn_or_ibis_metrics(self):
        assert '"—"' not in _ARTEFATOS_SRC
        assert "'—'" not in _ARTEFATOS_SRC

    def test_no_ellipsis_placeholder_in_card_captions(self):
        assert "'…'" not in _ARTEFATOS_SRC
        assert '"…"' not in _ARTEFATOS_SRC

    def test_metrics_no_longer_branch_on_none(self):
        assert "if dmn_decisions is not None" not in _ARTEFATOS_SRC
        assert "if ibis_questions is not None" not in _ARTEFATOS_SRC
        assert "if noise_items is not None" not in _ARTEFATOS_SRC


class TestDmnIbisNoiseLoadedFromSharedCache:
    def test_dmn_ibis_noise_no_longer_read_from_session_state_only(self):
        assert "st.session_state.get(dmn_session_key" not in _ARTEFATOS_SRC
        assert "st.session_state.get(ibis_session_key" not in _ARTEFATOS_SRC
        assert "st.session_state.get(noise_session_key" not in _ARTEFATOS_SRC

    def test_dmn_ibis_noise_submitted_to_the_shared_pool(self):
        pool_idx = _ARTEFATOS_SRC.index("with _TPE(")
        pool_end = _ARTEFATOS_SRC.index("\n\n", pool_idx)
        pool_block = _ARTEFATOS_SRC[pool_idx:pool_end]
        assert "_load_dmn" in pool_block
        assert "_load_argumentation" in pool_block
        assert "_load_noise" in pool_block

    def test_pool_worker_count_covers_all_12_loaders(self):
        assert "max_workers=12" in _ARTEFATOS_SRC
