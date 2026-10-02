# tests/test_ux12_vocabulario_contexto.py
"""
UX-12 (melhorias/ux-amigabilidade-e-elegancia.md, Onda C): o mesmo
conceito aparecia na UI como "Contexto", "Projeto" e "Iniciativa" em
pontos diferentes ("Contexto / Iniciativa" no seletor do Pipeline,
"Projeto de Trabalho" na sidebar do Assistente) -- achado A3 do audit.

Fix (escopo desta rodada -- só vocabulário, sem decisão de marca):
- ui/project_selector.py: "Contexto / Iniciativa" -> "Contexto"
- pages/Assistente.py: "Projeto de Trabalho" -> "Contexto de Trabalho"

A parte de marca exibida (Vichara vs Process2Diagram) do UX-12 NÃO foi
tocada aqui -- já é uma iniciativa própria em aberto (PC197, 5 fases,
nada executado), não uma decisão a tomar de passagem numa correção de
vocabulário de UI.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


class TestProjectSelectorUsesContextoOnly:
    def test_no_contexto_iniciativa_label_remains(self):
        src = (_ROOT / "ui" / "project_selector.py").read_text(encoding="utf-8")
        assert "Contexto / Iniciativa" not in src

    def test_selectbox_label_is_just_contexto(self):
        src = (_ROOT / "ui" / "project_selector.py").read_text(encoding="utf-8")
        assert 'st.selectbox("Contexto", options,' in src


class TestAssistenteSidebarUsesContextoNotProjeto:
    def test_no_projeto_de_trabalho_label_remains(self):
        src = (_ROOT / "pages" / "Assistente.py").read_text(encoding="utf-8")
        assert "Projeto de Trabalho" not in src

    def test_sidebar_header_says_contexto_de_trabalho(self):
        src = (_ROOT / "pages" / "Assistente.py").read_text(encoding="utf-8")
        assert "Contexto de Trabalho" in src
