# tests/test_transcript_preprocessor_infer_meta.py
"""
Tests for modules/transcript_preprocessor.py::infer_title_and_date_from_header()
— pre-fill de Título/Data na tela "Nova transcrição" quando os campos estão
vazios, sem LLM. Melhoria pedida pelo usuário (2026-08-13).

Cada regra de negócio ganha teste próprio: heurística de "ausência de sinal
= não preenche" é a parte que mais importa nunca regredir silenciosamente
(campo errado preenchido é pior que campo vazio).
"""

from __future__ import annotations

from datetime import date

from modules.transcript_preprocessor import infer_title_and_date_from_header


HEADER_ESTRUTURADO = """GRUPO MERIDIONAL S.A.
PROJETO AURORA — Plataforma Digital de Crédito
Reunião R1 — Kick-off e Definição de Escopo
Data: 01 de março de 2026 (domingo)
Horário: 09:02 — 10:38
Local: Sala de Reuniões Executivas "Ipê" — Torre Meridional, Av. Paulista 2300, São Paulo
Transcrição gerada por: Sistema de Gravação Corporativa MeridionalREC v3.1 PARTICIPANTES: ALF — Dra. Ana Luísa Ferreira

ALF   0:02
Bom dia a todos.
"""

SEM_CABECALHO = """Ricardo   0:05
Bom dia. Vamos revisar os pontos pendentes.

Fernanda   0:12
Certo.
"""


class TestInferTitleAndDateFromHeader:
    def test_extracts_title_and_date_from_structured_header(self):
        title, dt = infer_title_and_date_from_header(HEADER_ESTRUTURADO)
        assert title == "Reunião R1 — Kick-off e Definição de Escopo"
        assert dt == date(2026, 3, 1)

    def test_skips_all_caps_company_name_line_as_title(self):
        title, _ = infer_title_and_date_from_header(HEADER_ESTRUTURADO)
        assert "MERIDIONAL" not in title

    def test_no_header_returns_empty_title_and_none_date(self):
        """Transcrição sem nenhuma linha antes da primeira fala — heurística
        não deve inventar nada, campo continua em branco como hoje."""
        title, dt = infer_title_and_date_from_header(SEM_CABECALHO)
        assert title == ""
        assert dt is None

    def test_empty_transcript_returns_empty_title_and_none_date(self):
        title, dt = infer_title_and_date_from_header("")
        assert title == ""
        assert dt is None

    def test_never_raises_on_malformed_input(self):
        # Data com dia/mês/ano impossível não deve derrubar a função.
        malformed = "Reunião de Teste\nData: 31 de fevereiro de 2026\n\nA   0:01\nOi.\n"
        title, dt = infer_title_and_date_from_header(malformed)
        assert title == "Reunião de Teste"
        assert dt is None  # data inválida — não inventa uma data errada

    def test_prefers_line_containing_reuniao_keyword_over_first_candidate(self):
        """Quando há mais de uma linha candidata a título, prefere a que
        contém 'reunião' em vez de simplesmente pegar a primeira."""
        header = "Kickoff Bimestral\nReunião de Alinhamento Trimestral\n\nA   0:01\nOi.\n"
        title, _ = infer_title_and_date_from_header(header)
        assert title == "Reunião de Alinhamento Trimestral"
