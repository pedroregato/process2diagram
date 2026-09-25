# tests/conftest.py
# Shared fixtures and factory helpers for all test modules.

import types

import pytest
from core.knowledge_hub import (
    BPMNModel, BPMNStep, BPMNEdge, BPMNPoolData, BPMNMessageFlow,
)


# ── Factory helpers ───────────────────────────────────────────────────────────

def step(id, title, *, task_type="userTask", is_decision=False, lane=None, description=""):
    return BPMNStep(id=id, title=title, task_type=task_type,
                    is_decision=is_decision, lane=lane, description=description)


def edge(src, tgt, label=""):
    return BPMNEdge(source=src, target=tgt, label=label)


def model(*steps, edges=None, lanes=None, name="test"):
    return BPMNModel(
        name=name,
        steps=list(steps),
        edges=edges or [],
        lanes=lanes or [],
    )


def pool(pool_id, name, steps, edges=None, lanes=None):
    return BPMNPoolData(
        pool_id=pool_id,
        name=name,
        steps=steps,
        edges=edges or [],
        lanes=lanes or [],
    )


def message_flow(id, source_pool, source_step, target_pool, target_step, name=""):
    return BPMNMessageFlow(id=id, source_pool=source_pool, source_step=source_step,
                            target_pool=target_pool, target_step=target_step, name=name)


def collab(*pools, message_flows=None, name="collab"):
    return BPMNModel(
        name=name,
        is_collaboration=True,
        pool_models=list(pools),
        message_flows_data=message_flows or [],
    )


# ── Guarda: testes nunca falam com o Supabase real ────────────────────────────
# Os testes de página (AppTest) rodam as páginas de verdade: toda chamada ao
# banco que não foi explicitamente mockada caía no projeto de PRODUÇÃO via
# .streamlit/secrets.toml (achado de 25/09/2026: 172 requisições com
# project_id "nav09-*" — 400 por UUID inválido e 401 em INSERTs de llm_cache /
# llm_telemetry). Com uma chave service_role no secrets local, esses INSERTs
# teriam gravado lixo em produção.
#
# Esta fixture troca supabase.create_client por um cliente offline que aceita
# qualquer cadeia (.table().select().eq()...execute()) e devolve data=[].
# Sem secrets (CI), get_supabase_client() continua retornando None como antes.
# Testes que precisam de um fake próprio continuam patchando _db /
# get_supabase_client normalmente — esses patches têm precedência.

class _OfflineQuery:
    """Encadeia qualquer método do supabase-py e responde vazio no execute()."""

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self

    def execute(self, *args, **kwargs):
        return types.SimpleNamespace(data=[], count=0)


class _OfflineSupabaseClient(_OfflineQuery):
    pass


@pytest.fixture(autouse=True)
def _offline_supabase(monkeypatch):
    import modules.supabase_client as sc

    monkeypatch.setattr(sc, "_client", None)
    try:
        import supabase
        monkeypatch.setattr(supabase, "create_client",
                            lambda *a, **k: _OfflineSupabaseClient())
    except ImportError:
        pass
    yield
    sc._client = None
