from __future__ import annotations
import json
from .schema import ProcessModel

def to_json(proc: ProcessModel) -> str:
    return json.dumps(proc.model_dump(), ensure_ascii=False, indent=2)
