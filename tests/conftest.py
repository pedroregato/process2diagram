# tests/conftest.py
# Shared fixtures and factory helpers for all test modules.

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
