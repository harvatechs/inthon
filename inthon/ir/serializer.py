from __future__ import annotations
import json
from typing import Any
from . import nodes as ir_nodes


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        d = {}
        for f in obj.__dataclass_fields__:
            d[f] = _to_dict(getattr(obj, f))
        d["__ir_type__"] = type(obj).__name__
        return d
    if isinstance(obj, list):
        return [_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_to_dict(x) for x in obj]
    return obj


def ir_to_json(program: ir_nodes.IRProgram, indent: int = 2) -> str:
    """Serialize IR to canonical JSON."""
    return json.dumps(_to_dict(program), indent=indent)


def _from_dict(d: Any) -> Any:
    if isinstance(d, dict):
        if "__ir_type__" in d:
            ir_type = d["__ir_type__"]
            cls = getattr(ir_nodes, ir_type)
            kwargs = {}
            for k, v in d.items():
                if k != "__ir_type__":
                    kwargs[k] = _from_dict(v)
            return cls(**kwargs)
        else:
            return {k: _from_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_from_dict(x) for x in d]
    return d


def ir_from_json(raw: str) -> ir_nodes.IRProgram:
    """Deserialise canonical JSON back to IR. Round-trip safe."""
    data = json.loads(raw)
    return _from_dict(data)
