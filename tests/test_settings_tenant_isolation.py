# tests/test_settings_tenant_isolation.py
"""
NAV-01-bis (achado de passagem no PC219, claude_guideline/roadmap.md):
pages/Settings.py (aba "Banco de Dados") consultava e ATUALIZAVA a tabela
`contexts` via `db.table("contexts")` direto (não via
core.project_store.list_contexts(), por isso passou batido do fix original
do NAV-01/PC211, que corrigiu só os call sites daquela função) — sem
nenhum filtro de `tenant_id`, em 8 pontos: métricas agregadas
(projetos/reuniões/requisitos), listagem+edição de contexto (nome, sigla,
descrição, slug de ata, local padrão — via UPDATE), CKF, upload de
arquivos de contexto e modelo de ata. Qualquer usuário autenticado de
QUALQUER domínio via e EDITAVA contextos de outros tenants.

Fix: todas as 8 chamadas a `db.table("contexts")` agora filtram por
`.eq("tenant_id", _tid)` — os 3 UPDATEs também, como defesa em
profundidade (o id só deveria alcançar o formulário via um SELECT já
filtrado, mas o UPDATE nunca deve conseguir atingir outro tenant mesmo
assim). O link para "Visão do Banco" (admin-only) também ganhou o gate
`is_admin()` que faltava.
"""

import re
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "pages" / "Settings.py"
_CONTEXTS_CALL_RE = re.compile(r'db\.table\("contexts"\)[^\n]*?\.execute\(\)')

TENANT_A = "tenant-a-11111111-1111-1111-1111-111111111111"
TENANT_B = "tenant-b-22222222-2222-2222-2222-222222222222"


class TestEveryContextsQueryIsTenantScoped:
    """Guarda estática — regressão aqui reabriria o vazamento cross-tenant
    sem precisar renderizar a página inteira (que tem 7 abas pesadas, todas
    executadas a cada rerun por causa do st.tabs())."""

    def test_no_contexts_query_or_update_is_missing_tenant_filter(self):
        src = _SETTINGS_PATH.read_text(encoding="utf-8")
        calls = _CONTEXTS_CALL_RE.findall(src)
        assert len(calls) >= 8, (
            f"esperava pelo menos 8 chamadas a db.table(\"contexts\")...execute() "
            f"na aba Banco de Dados, encontradas {len(calls)} — a regex pode ter "
            "parado de casar (ex.: refactor pra multi-linha)"
        )
        unscoped = [c for c in calls if "tenant_id" not in c]
        assert unscoped == [], (
            f"chamada(s) a contexts sem filtro de tenant_id — reabre o NAV-01-bis: {unscoped}"
        )


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict], table: str):
        self._rows = list(rows)
        self._table = table

    def select(self, *a, **k):
        return self

    def update(self, patch):
        self._patch = patch
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _Resp(self._rows)


class _FakeDB:
    """Só a tabela contexts tem dado real (2 tenants semeados) — qualquer
    outra tabela usada pelas demais abas (sempre executadas por causa do
    st.tabs()) devolve vazio, fail-open, sem derrubar a página."""

    def __init__(self, context_rows):
        self._context_rows = context_rows

    def table(self, name):
        if name == "contexts":
            return _FakeQuery(self._context_rows, name)
        return _FakeQuery([], name)


def _seeded_contexts():
    return [
        {"id": "ctx-a1", "tenant_id": TENANT_A, "name": "SECRET-A contexto",
         "description": "", "sigla": "A1"},
        {"id": "ctx-b1", "tenant_id": TENANT_B, "name": "SECRET-B contexto",
         "description": "", "sigla": "B1"},
    ]


class TestContextsSectionRendersOnlyOwnTenant:
    def test_context_edit_list_shows_only_active_tenant_context(self):
        fake_db = _FakeDB(_seeded_contexts())
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("modules.supabase_client.get_supabase_client", lambda: fake_db):
            at = AppTest.from_file("pages/Settings.py", default_timeout=60)
            at.session_state["_autenticado"] = True
            at.session_state["_usuario_login"] = "teste"
            at.session_state["_usuario_nome"] = "Teste"
            at.session_state["_role"] = "user"
            at.session_state["_tenant_id"] = TENANT_A
            at.run()

        assert not at.exception
        labels = " ".join(e.label for e in at.expander)
        assert "SECRET-A contexto" in labels
        assert "SECRET-B contexto" not in labels
