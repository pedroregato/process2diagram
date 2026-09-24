# tests/test_app_page_icons_unique.py
"""
NAV-10 (melhorias/parciais/navegabilidade.md, PC216): 9 pares de páginas
compartilhavam o mesmo emoji no menu de app.py (ex.: 📄 em Documentos e
Relatório Executivo, 💰 em Estimativa de Custo e Cenários de Custo, 🏗️ em
BPMN Studio e Arquiteturas) — confuso pra localizar a página certa na
sidebar. Cada um dos 9 pares recebeu um ícone novo e único.

Teste estático (regex sobre o texto-fonte de app.py) — evita ter que rodar
o boot completo de app.py (st.set_page_config + st.navigation) só pra
inspecionar os ícones declarados nos st.Page(...).
"""

import re
from collections import Counter
from pathlib import Path

_APP_SRC = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")


def _all_page_icons() -> list[str]:
    return re.findall(r'st\.Page\([^)]*icon="([^"]+)"', _APP_SRC)


def test_no_two_registered_pages_share_the_same_icon():
    icons = _all_page_icons()
    counts = Counter(icons)
    duplicates = {icon: n for icon, n in counts.items() if n > 1}
    assert not duplicates, f"ícones repetidos entre páginas: {duplicates}"


def test_found_a_realistic_number_of_pages():
    # Guarda contra a regex silenciosamente deixar de casar nada (ex.: um
    # refactor de app.py que mude a sintaxe de st.Page) — nesse caso
    # _all_page_icons() devolveria [] e o teste acima passaria vazio,
    # mascarando uma regressão real.
    assert len(_all_page_icons()) >= 40
