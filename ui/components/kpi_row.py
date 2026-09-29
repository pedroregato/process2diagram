# ui/components/kpi_row.py
# ─────────────────────────────────────────────────────────────────────────────
# UX-02 (melhorias/ux-amigabilidade-e-elegancia.md): st.metric em linhas de
# 5-7 colunas truncava rótulos e valores em viewports estreitos (~840px,
# sidebar aberta) — "9.…", "R…", "deepse…". A causa é simplesmente ter mais
# colunas do que cabem na largura disponível; a correção é limitar quantas
# métricas entram por linha, não mexer no conteúdo de cada métrica.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st


def kpi_row(items: list[dict], max_per_row: int = 4) -> None:
    """Renderiza métricas (st.metric) em linhas de no máx. max_per_row
    colunas, quebrando em novas linhas em vez de espremer todas as
    métricas numa única linha.

    Cada item de ``items`` é um dict com:
        - "label" (obrigatório)
        - "value" (obrigatório)
        - "help" (opcional)
        - "delta" (opcional)
        - "delta_color" (opcional, default "normal")
    """
    for start in range(0, len(items), max_per_row):
        chunk = items[start:start + max_per_row]
        cols = st.columns(len(chunk))
        for col, item in zip(cols, chunk):
            col.metric(
                item["label"],
                item["value"],
                delta=item.get("delta"),
                delta_color=item.get("delta_color", "normal"),
                help=item.get("help"),
            )
