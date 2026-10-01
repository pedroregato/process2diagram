# tests/test_ux07_page_header_migration.py
"""
UX-07 (melhorias/ux-amigabilidade-e-elegancia.md, Onda B): confirma que as
paginas de trabalho migradas usam os componentes padronizados
(render_page_header / render_context_chip) em vez do padrao antigo
(st.markdown("# ...") solto + st.success(f"Contexto: ...") verde).

Rodada 1 (2026-10-01) -- 9 paginas tinham o padrao completo (titulo solto
+ banner verde de contexto + link Trocar): Artefatos.py e as 5 subsecoes
(ArtefatosDebates/Modelagem/Qualidade/Requisitos/Reunioes), BpmnEditor.py,
EntityRecognition.py, ValidationHub.py. 3 paginas so tinham titulo solto,
sem banner de contexto (nada pra preservar alem do titulo):
CostEstimator.py, KnowledgeGraph.py, Diagramas.py (2 ocorrencias, uma no
fallback Supabase, uma no fluxo principal).

Rodada 2 (2026-10-01) -- avaliacao das ~25 paginas restantes mostrou que
a maioria nunca teve o banner verde pra substituir (AtivosDeNegocio,
KnowledgeHub, LLMBenchmark, CostBenefitScenarios: sem banner; Pipeline.py:
seletor de contexto proprio, diferente; Settings.py/DocumentManager.py:
st.success() ali sao feedback de acao pontual, uso legitimo). So 2 paginas
tinham o padrao identico: BpmnStudio.py e MeetingROI.py (ambas ja usavam
render_page_header, so faltava o chip).

Checagem estatica (mesmo padrao de tests/test_report_backfill_admin_gate.py
e outros desta sessao) -- renderizar as paginas via AppTest exigiria
simular sessao + Supabase + varios loaders por pagina; a garantia que
importa (uso do componente certo, ausencia do padrao antigo) e observavel
direto no codigo-fonte.
"""

from pathlib import Path

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"

_CONTEXT_CHIP_PAGES = [
    "Artefatos.py",
    "ArtefatosDebates.py",
    "ArtefatosModelagem.py",
    "ArtefatosQualidade.py",
    "ArtefatosRequisitos.py",
    "ArtefatosReunioes.py",
    "EntityRecognition.py",
    "ValidationHub.py",
    "BpmnEditor.py",
    "BpmnStudio.py",
    "MeetingROI.py",
]

_PAGE_HEADER_ONLY_PAGES = [
    "CostEstimator.py",
    "KnowledgeGraph.py",
    "Diagramas.py",
]


def _read(fname: str) -> str:
    return (_PAGES_DIR / fname).read_text(encoding="utf-8")


class TestContextChipPagesMigrated:
    def test_all_eleven_pages_import_render_context_chip(self):
        for fname in _CONTEXT_CHIP_PAGES:
            src = _read(fname)
            assert "render_context_chip" in src, f"{fname}: nao importa/usa render_context_chip"

    def test_no_green_success_context_banner_remains(self):
        for fname in _CONTEXT_CHIP_PAGES:
            src = _read(fname)
            assert 'st.success(f"\U0001f4c1 **Contexto' not in src, (
                f"{fname}: ainda tem o banner verde st.success de contexto"
            )

    def test_no_dead_col_proj_col_change_pattern_remains(self):
        for fname in _CONTEXT_CHIP_PAGES:
            src = _read(fname)
            assert "_col_proj, _col_change = st.columns([5, 1])" not in src
            assert "_col_p, _col_ch = st.columns([5, 1])" not in src


class TestPageHeaderOnlyPagesMigrated:
    def test_all_three_pages_import_render_page_header(self):
        for fname in _PAGE_HEADER_ONLY_PAGES:
            src = _read(fname)
            assert "render_page_header" in src, f"{fname}: nao importa/usa render_page_header"

    def test_diagramas_both_occurrences_migrated(self):
        src = _read("Diagramas.py")
        assert src.count("render_page_header(") == 2, (
            "Diagramas.py deveria ter 2 chamadas a render_page_header "
            "(fallback Supabase + fluxo principal)"
        )
        assert 'st.markdown("## \U0001f4d0 Visualizador de Diagramas")' not in src


class TestBpmnStudioAndMeetingRoiMigratedInRound2:
    """BpmnStudio.py e MeetingROI.py ja usavam render_page_header antes
    desta rodada -- so o banner verde de contexto precisava virar
    render_context_chip(). Confirma que os dois continuam usando
    render_page_header (nao regrediu) alem de ganhar o chip."""

    def test_both_pages_still_use_render_page_header(self):
        for fname in ("BpmnStudio.py", "MeetingROI.py"):
            src = _read(fname)
            assert "render_page_header(" in src, f"{fname}: perdeu render_page_header"

    def test_both_pages_call_render_context_chip_with_project_name(self):
        for fname in ("BpmnStudio.py", "MeetingROI.py"):
            src = _read(fname)
            assert "render_context_chip(project_name)" in src


class TestArtefatosSixPagesUseIdenticalCallPattern:
    """As 6 paginas Artefatos*.py tinham o bloco de contexto byte-identico
    -- confirma que a migracao manteve esse padrao consistente (uma unica
    chamada render_context_chip(project_name), sem variacao acidental)."""

    def test_render_context_chip_called_with_project_name_only(self):
        artefatos_pages = [
            "Artefatos.py", "ArtefatosDebates.py", "ArtefatosModelagem.py",
            "ArtefatosQualidade.py", "ArtefatosRequisitos.py", "ArtefatosReunioes.py",
        ]
        for fname in artefatos_pages:
            src = _read(fname)
            assert "render_context_chip(project_name)" in src, (
                f"{fname}: chamada esperada 'render_context_chip(project_name)' nao encontrada"
            )
