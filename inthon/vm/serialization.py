"""
inthon.vm.serialization — Frame and CodeObject serialization for InthonVM.

Enables agent session dehydration and hydration (pause and resume).
"""

from __future__ import annotations
from typing import Any
from .code_object import CodeObject, Instruction
from .frame import Frame, RetryState
from .old_opcodes import OpCode
from ..runtime.values import (
    InthonInt,
    InthonFloat,
    InthonStr,
    InthonBool,
    InthonNone,
    InthonList,
    InthonDict,
    InthonCallable,
    InthonToolRef,
    InthonPyObject,
)


class InthonIterator:
    """A JSON-serializable iterator wrapper for INTHON collections."""

    def __init__(self, sequence: list[Any], index: int = 0) -> None:
        self.sequence = list(sequence)
        self.index = index

    def __next__(self) -> Any:
        if self.index >= len(self.sequence):
            raise StopIteration
        val = self.sequence[self.index]
        self.index += 1
        return val

    def __iter__(self) -> InthonIterator:
        return self


def serialize_value(val: Any) -> Any:
    """Recursively convert Inthon/Python values into JSON-serializable structures."""
    if val is None or isinstance(val, (int, float, str, bool)):
        return val

    if isinstance(val, InthonInt):
        return {"__type__": "inthon_int", "v": val.value}
    if isinstance(val, InthonFloat):
        return {"__type__": "inthon_float", "v": val.value}
    if isinstance(val, InthonStr):
        return {"__type__": "inthon_str", "v": val.value}
    if isinstance(val, InthonBool):
        return {"__type__": "inthon_bool", "v": val.value}
    if isinstance(val, InthonNone):
        return {"__type__": "inthon_none"}

    if isinstance(val, InthonList):
        return {
            "__type__": "inthon_list",
            "items": [serialize_value(x) for x in val.items],
        }
    if isinstance(val, InthonDict):
        return {
            "__type__": "inthon_dict",
            "pairs": {k: serialize_value(v) for k, v in val.pairs.items()},
        }

    if isinstance(val, InthonCallable):
        body_data = (
            serialize_code_object(val.body)
            if isinstance(val.body, CodeObject)
            else val.body
        )
        closure_data = {
            k: serialize_value(v)
            for k, v in val.closure.items()
            if not k.startswith("__")
        }
        return {
            "__type__": "inthon_callable",
            "name": val.name,
            "params": val.params,
            "defaults": {k: serialize_value(v) for k, v in val.defaults.items()},
            "body": body_data,
            "closure": closure_data,
        }

    if isinstance(val, InthonToolRef):
        return {"__type__": "inthon_tool_ref", "tool_path": val.tool_path}

    if isinstance(val, InthonPyObject):
        # Opaque python objects can be serialized if they define a serialize method, or we fallback to str
        obj_repr = val.obj
        if hasattr(val.obj, "to_dict"):
            try:
                obj_repr = val.obj.to_dict()
            except Exception:
                obj_repr = str(val.obj)
        elif not isinstance(val.obj, (int, float, str, bool, list, dict, type(None))):
            obj_repr = str(val.obj)
        return {
            "__type__": "inthon_py_object",
            "source_module": val.source_module,
            "obj": serialize_value(obj_repr),
        }

    if isinstance(val, InthonIterator):
        return {
            "__type__": "inthon_iterator",
            "sequence": [serialize_value(x) for x in val.sequence],
            "index": val.index,
        }

    if isinstance(val, list):
        return [serialize_value(x) for x in val]
    if isinstance(val, dict):
        return {str(k): serialize_value(v) for k, v in val.items()}

    # Fallback to string representation of unsupported Python objects
    return str(val)


def deserialize_value(data: Any) -> Any:
    """Reconstruct Inthon/Python values from JSON-serialized data."""
    if not isinstance(data, dict):
        if isinstance(data, list):
            return [deserialize_value(x) for x in data]
        return data

    t = data.get("__type__")
    if t is None:
        # standard dictionary
        return {k: deserialize_value(v) for k, v in data.items()}

    if t == "inthon_int":
        return InthonInt(data["v"])
    if t == "inthon_float":
        return InthonFloat(data["v"])
    if t == "inthon_str":
        return InthonStr(data["v"])
    if t == "inthon_bool":
        return InthonBool(data["v"])
    if t == "inthon_none":
        return InthonNone()

    if t == "inthon_list":
        return InthonList([deserialize_value(x) for x in data["items"]])
    if t == "inthon_dict":
        return InthonDict({k: deserialize_value(v) for k, v in data["pairs"].items()})

    if t == "inthon_callable":
        body_data = data["body"]
        if isinstance(body_data, dict) and body_data.get("__type__") == "code_object":
            body = deserialize_code_object(body_data)
        else:
            body = body_data
        closure = {k: deserialize_value(v) for k, v in data["closure"].items()}
        defaults = {k: deserialize_value(v) for k, v in data["defaults"].items()}
        return InthonCallable(
            name=data["name"],
            params=data["params"],
            defaults=defaults,
            body=body,
            closure=closure,
        )

    if t == "inthon_tool_ref":
        return InthonToolRef(data["tool_path"])

    if t == "inthon_py_object":
        return InthonPyObject(
            obj=deserialize_value(data["obj"]),
            source_module=data["source_module"],
        )

    if t == "inthon_iterator":
        return InthonIterator(
            sequence=[deserialize_value(x) for x in data["sequence"]],
            index=data["index"],
        )

    return data


def serialize_code_object(co: CodeObject) -> dict:
    """Serialize a CodeObject tree to a dictionary."""
    constants_data = []
    for c in co.constants:
        if isinstance(c, CodeObject):
            constants_data.append(serialize_code_object(c))
        else:
            constants_data.append(serialize_value(c))

    instructions_data = []
    for instr in co.instructions:
        arg_val = instr.arg
        if isinstance(arg_val, CodeObject):
            arg_val = serialize_code_object(arg_val)
        else:
            # OpCode arguments might be integers, names, or tuples
            if isinstance(arg_val, tuple):
                arg_val = list(arg_val)
            arg_val = serialize_value(arg_val)

        instructions_data.append(
            {
                "op": instr.op.name,
                "arg": arg_val,
                "lineno": instr.lineno,
                "colno": instr.colno,
            }
        )

    return {
        "__type__": "code_object",
        "name": co.name,
        "filename": co.filename,
        "varnames": co.varnames,
        "param_names": co.param_names,
        "defaults": {k: serialize_value(v) for k, v in co.defaults.items()},
        "constants": constants_data,
        "instructions": instructions_data,
    }


def deserialize_code_object(data: dict) -> CodeObject:
    """Deserialize a CodeObject from a dictionary."""
    co = CodeObject(name=data["name"], filename=data["filename"])
    co.varnames = list(data["varnames"])
    co.param_names = list(data.get("param_names", []))
    co.defaults = {k: deserialize_value(v) for k, v in data.get("defaults", {}).items()}

    # First populate constants placeholder to allow recursion refer back
    co.constants = []
    for c in data["constants"]:
        if isinstance(c, dict) and c.get("__type__") == "code_object":
            co.constants.append(deserialize_code_object(c))
        else:
            co.constants.append(deserialize_value(c))

    co.instructions = []
    for inst_data in data["instructions"]:
        op_name = inst_data["op"]
        op = OpCode[op_name]
        arg = inst_data["arg"]
        if isinstance(arg, dict) and arg.get("__type__") == "code_object":
            arg = deserialize_code_object(arg)
        else:
            arg = deserialize_value(arg)
            if isinstance(arg, list):
                arg = tuple(arg)  # standard argument format for multi-args is tuple

        co.instructions.append(
            Instruction(
                op=op,
                arg=arg,
                lineno=inst_data.get("lineno", 0),
                colno=inst_data.get("colno", 0),
            )
        )

    return co


def serialize_frame(frame: Frame) -> dict:
    """Dehydrate a Frame and its call chain into a JSON-serializable dict."""
    retry_stack_data = []
    for r in frame.retry_stack:
        retry_stack_data.append(
            {
                "count": r.count,
                "backoff": r.backoff,
                "attempt": r.attempt,
                "last_error": str(r.last_error) if r.last_error else None,
            }
        )

    parent_data = serialize_frame(frame.parent) if frame.parent else None

    return {
        "__type__": "frame",
        "code": serialize_code_object(frame.code),
        "ip": frame.ip,
        "stack": [serialize_value(x) for x in frame.stack],
        "locals": {k: serialize_value(v) for k, v in frame.locals.items()},
        "return_val": serialize_value(frame.return_val),
        "finished": frame.finished,
        "retry_stack": retry_stack_data,
        "parent": parent_data,
    }


def deserialize_frame(data: dict) -> Frame:
    """Rehydrate a Frame and its parents from a dictionary."""
    code = deserialize_code_object(data["code"])
    locals_dict = {k: deserialize_value(v) for k, v in data["locals"].items()}
    parent_frame = deserialize_frame(data["parent"]) if data.get("parent") else None

    frame = Frame(code=code, locals=locals_dict, parent=parent_frame)
    frame.ip = data["ip"]
    frame.stack = [deserialize_value(x) for x in data["stack"]]
    frame.return_val = deserialize_value(data.get("return_val"))
    frame.finished = data.get("finished", False)

    retry_stack = []
    for r_data in data.get("retry_stack", []):
        err = Exception(r_data["last_error"]) if r_data.get("last_error") else None
        retry_stack.append(
            RetryState(
                count=r_data["count"],
                backoff=r_data["backoff"],
                attempt=r_data["attempt"],
                last_error=err,
            )
        )
    frame.retry_stack = retry_stack

    return frame
