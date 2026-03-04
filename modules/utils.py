# modules/utils.py
import json
import dataclasses
from modules.schema import Process


def process_to_json(process: Process) -> str:
    """Serialize a Process to a formatted JSON string."""
    def _serialize(obj):
        if dataclasses.is_dataclass(obj):
            return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}
        return obj

    data = {
        "name": process.name,
        "steps": [dataclasses.asdict(s) for s in process.steps],
        "edges": [dataclasses.asdict(e) for e in process.edges],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
