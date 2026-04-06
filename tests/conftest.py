# tests/conftest.py
# Shared fixtures and factory helpers for all test modules.

import pytest
from core.knowledge_hub import (
    BPMNModel, BPMNStep, BPMNEdge, BPMNPoolData, BPMNMessageFlow,
)


# ── Factory helpers ───────────────────────────────────────────────────────────

def step(id, title, *, task_type="userTask", is_decision=False, lane=None):
    return BPMNStep(id=id, title=title, task_type=task_type,
                    is_decision=is_decision, lane=lane)


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


def collab(*pools, message_flows=None, name="collab"):
    return BPMNModel(
        name=name,
        is_collaboration=True,
        pool_models=list(pools),
        message_flows_data=message_flows or [],
    )
