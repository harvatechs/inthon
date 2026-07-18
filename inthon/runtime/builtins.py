"""INTHON builtin functions and value methods.

Builtins live in the global scope of every run (print, len, range, ...).
Value methods power method-call syntax ("text".upper(), xs.append(1)).
"""

from __future__ import annotations

import json as _json
import math as _math
from typing import Callable

from ..errors import InthonArityError, InthonFailure, InthonTypeError_, Span
from . import values as V
from .values import (
    NONE,
    InthonBool,
    InthonBoundMethod,
    InthonBuiltin,
    InthonDict,
    InthonFloat,
    InthonInt,
    InthonList,
    InthonPyObject,
    InthonString,
    InthonValue,
    bool_value,
    display,
)


def _err(msg: str) -> InthonTypeError_:
    return InthonTypeError_(msg)


def _num(v: InthonValue, what: str = "value") -> float:
    if isinstance(v, (InthonInt, InthonFloat)):
        return v.to_python()
    if isinstance(v, InthonBool):
        return 1 if v.value else 0
    raise _err(f"{what} must be a number, got {v.type_name}")


# ---------------------------------------------------------------------------
# Builtin functions  (signature: fn(ctx, args, kwargs, span))
# ---------------------------------------------------------------------------
def _b_print(ctx, args, kwargs, span):
    end = kwargs.get("end")
    end_s = "\n" if end is None else display(end)
    ctx.write_out(" ".join(display(a) for a in args) + ("" if end_s == "\n" else end_s))
    return NONE


def _b_len(ctx, args, kwargs, span):
    _arity("len", args, 1)
    v = args[0]
    if isinstance(v, InthonString):
        return InthonInt(len(v.value))
    if isinstance(v, InthonList):
        return InthonInt(len(v.items))
    if isinstance(v, InthonDict):
        return InthonInt(len(v.pairs))
    if isinstance(v, InthonPyObject):
        try:
            return InthonInt(len(v.wrapped))
        except TypeError:
            pass
    raise _err(f"len() not supported for {v.type_name}")


def _b_str(ctx, args, kwargs, span):
    _arity("str", args, 1)
    return InthonString(display(args[0]))


def _b_int(ctx, args, kwargs, span):
    _arity("int", args, 1)
    v = args[0]
    try:
        if isinstance(v, InthonString):
            return InthonInt(int(float(v.value.strip())))
        return InthonInt(int(_num(v)))
    except ValueError:
        raise _err(f"int() cannot convert {display(v)!r}") from None


def _b_float(ctx, args, kwargs, span):
    _arity("float", args, 1)
    v = args[0]
    try:
        if isinstance(v, InthonString):
            return InthonFloat(float(v.value.strip()))
        return InthonFloat(float(_num(v)))
    except ValueError:
        raise _err(f"float() cannot convert {display(v)!r}") from None


def _b_bool(ctx, args, kwargs, span):
    _arity("bool", args, 1)
    return bool_value(args[0].truthy())


def _b_type(ctx, args, kwargs, span):
    _arity("type", args, 1)
    return InthonString(args[0].type_name)


def _b_range(ctx, args, kwargs, span):
    if not (1 <= len(args) <= 3):
        raise InthonArityError(f"range() takes 1..3 arguments, got {len(args)}")
    nums = [int(_num(a)) for a in args]
    if len(nums) == 1:
        start, stop, step = 0, nums[0], 1
    elif len(nums) == 2:
        start, stop, step = nums[0], nums[1], 1
    else:
        start, stop, step = nums
    if step == 0:
        raise _err("range() step cannot be 0")
    return InthonList([InthonInt(i) for i in range(start, stop, step)])


def _b_abs(ctx, args, kwargs, span):
    _arity("abs", args, 1)
    v = args[0]
    return (
        InthonInt(abs(v.value))
        if isinstance(v, InthonInt)
        else InthonFloat(abs(_num(v)))
    )


def _b_min(ctx, args, kwargs, span):
    vals = _flatten_args("min", args)
    return min(vals, key=lambda v: _num(v))


def _b_max(ctx, args, kwargs, span):
    vals = _flatten_args("max", args)
    return max(vals, key=lambda v: _num(v))


def _b_sum(ctx, args, kwargs, span):
    _arity("sum", args, 1)
    xs = _as_list(args[0], "sum")
    total = 0.0
    all_int = True
    for x in xs:
        all_int = all_int and isinstance(x, InthonInt)
        total += _num(x)
    return InthonInt(int(total)) if all_int else InthonFloat(total)


def _b_round(ctx, args, kwargs, span):
    if not (1 <= len(args) <= 2):
        raise InthonArityError("round() takes 1 or 2 arguments")
    ndigits = int(_num(args[1])) if len(args) == 2 else None
    v = args[0]
    if ndigits is None:
        return InthonInt(round(_num(v)))
    return InthonFloat(round(_num(v), ndigits))


def _b_floor(ctx, args, kwargs, span):
    _arity("floor", args, 1)
    return InthonInt(_math.floor(_num(args[0])))


def _b_ceil(ctx, args, kwargs, span):
    _arity("ceil", args, 1)
    return InthonInt(_math.ceil(_num(args[0])))


def _b_sqrt(ctx, args, kwargs, span):
    _arity("sqrt", args, 1)
    return InthonFloat(_math.sqrt(_num(args[0])))


def _b_sorted(ctx, args, kwargs, span):
    xs = list(_as_list(args[0], "sorted"))
    reverse = kwargs.get("reverse")
    rev = reverse.truthy() if reverse is not None else False
    try:
        out = sorted(xs, key=lambda v: _num(v), reverse=rev)
    except InthonTypeError_:
        out = sorted(xs, key=lambda v: display(v), reverse=rev)
    return InthonList(out)


def _b_keys(ctx, args, kwargs, span):
    _arity("keys", args, 1)
    d = _as_dict(args[0], "keys")
    return InthonList([V.box(k) for k in d.pairs.keys()])


def _b_values(ctx, args, kwargs, span):
    _arity("values", args, 1)
    d = _as_dict(args[0], "values")
    return InthonList(list(d.pairs.values()))


def _b_items(ctx, args, kwargs, span):
    _arity("items", args, 1)
    d = _as_dict(args[0], "items")
    return InthonList([InthonList([V.box(k), v]) for k, v in d.pairs.items()])


def _b_append(ctx, args, kwargs, span):
    _arity("append", args, 2)
    xs = _as_list(args[0], "append")
    xs.append(args[1])
    return args[0]


def _b_push(ctx, args, kwargs, span):
    return _b_append(ctx, args, kwargs, span)


def _b_pop(ctx, args, kwargs, span):
    _arity("pop", args, 1)
    xs = _as_list(args[0], "pop")
    if not xs:
        raise _err("pop() on empty list")
    return xs.pop()


def _b_join(ctx, args, kwargs, span):
    _arity("join", args, 2)
    sep = _as_str(args[0], "join")
    xs = _as_list(args[1], "join")
    return InthonString(sep.join(display(x) for x in xs))


def _b_split(ctx, args, kwargs, span):
    if not (1 <= len(args) <= 2):
        raise InthonArityError("split() takes 1 or 2 arguments")
    s = _as_str(args[0], "split")
    if len(args) == 1:
        parts = s.split()
    else:
        parts = s.split(_as_str(args[1], "split"))
    return InthonList([InthonString(p) for p in parts])


def _b_upper(ctx, args, kwargs, span):
    return InthonString(_as_str(args[0], "upper").upper())


def _b_lower(ctx, args, kwargs, span):
    return InthonString(_as_str(args[0], "lower").lower())


def _b_strip(ctx, args, kwargs, span):
    return InthonString(_as_str(args[0], "strip").strip())


def _b_replace(ctx, args, kwargs, span):
    _arity("replace", args, 3)
    return InthonString(
        _as_str(args[0], "replace").replace(
            _as_str(args[1], "replace"), _as_str(args[2], "replace")
        )
    )


def _b_starts_with(ctx, args, kwargs, span):
    _arity("starts_with", args, 2)
    return bool_value(
        _as_str(args[0], "starts_with").startswith(_as_str(args[1], "starts_with"))
    )


def _b_ends_with(ctx, args, kwargs, span):
    _arity("ends_with", args, 2)
    return bool_value(
        _as_str(args[0], "ends_with").endswith(_as_str(args[1], "ends_with"))
    )


def _b_contains(ctx, args, kwargs, span):
    _arity("contains", args, 2)
    container, item = args
    if isinstance(container, InthonString):
        return bool_value(_as_str(item, "contains") in container.value)
    if isinstance(container, InthonList):
        return bool_value(any(V.values_equal(x, item) for x in container.items))
    if isinstance(container, InthonDict):
        key = item.to_python() if isinstance(item, InthonValue) else item
        return bool_value(key in container.pairs)
    raise _err(f"contains() not supported for {container.type_name}")


def _b_json_encode(ctx, args, kwargs, span):
    _arity("json_encode", args, 1)
    return InthonString(_json.dumps(args[0].to_python()))


def _b_json_decode(ctx, args, kwargs, span):
    _arity("json_decode", args, 1)
    try:
        return V.box(_json.loads(_as_str(args[0], "json_decode")))
    except _json.JSONDecodeError as exc:
        raise _err(f"json_decode() failed: {exc}") from None


def _b_now(ctx, args, kwargs, span):
    import time

    return InthonFloat(time.time())


def _b_fail(ctx, args, kwargs, span):
    msg = display(args[0]) if args else "fail() called"
    raise InthonFailure(
        msg, span=span, hint="The plan called fail(); this is an intentional abort."
    )


def _b_log(ctx, args, kwargs, span):
    if ctx.tracer is not None:
        ctx.tracer.emit("log", span, message=" ".join(display(a) for a in args))
    return NONE


def _b_read_file(ctx, args, kwargs, span):
    _arity("read_file", args, 1)
    path = _as_str(args[0], "read_file")
    ctx.policy.check("filesystem", span, subject="read_file")
    with open(path, "r", encoding="utf-8") as fh:
        return InthonString(fh.read())


def _b_write_file(ctx, args, kwargs, span):
    _arity("write_file", args, 2)
    path = _as_str(args[0], "write_file")
    content = _as_str(args[1], "write_file")
    ctx.policy.check("filesystem_write", span, subject="write_file")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return bool_value(True)


def _b_env(ctx, args, kwargs, span):
    # environment inspection is intentionally unavailable (info-leak vector)
    raise _err("env() is not available in the INTHON sandbox")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _arity(name: str, args: list, n: int):
    if len(args) != n:
        raise InthonArityError(f"{name}() takes {n} argument(s), got {len(args)}")


def _flatten_args(name: str, args: list) -> list:
    if len(args) == 1 and isinstance(args[0], InthonList):
        return list(args[0].items)
    if not args:
        raise InthonArityError(f"{name}() needs at least one argument")
    return list(args)


def _as_list(v: InthonValue, name: str) -> list:
    if isinstance(v, InthonList):
        return v.items
    raise _err(f"{name}() expects a list, got {v.type_name}")


def _as_dict(v: InthonValue, name: str) -> InthonDict:
    if isinstance(v, InthonDict):
        return v
    raise _err(f"{name}() expects a dict, got {v.type_name}")


def _as_str(v: InthonValue, name: str) -> str:
    if isinstance(v, InthonString):
        return v.value
    raise _err(f"{name}() expects a string, got {v.type_name}")


BUILTINS: dict[str, tuple[Callable, str]] = {
    "print": (_b_print, "print(value, ...) — write values to standard output"),
    "len": (_b_len, "len(x) — length of a string, list, or dict"),
    "str": (_b_str, "str(x) — display form of x"),
    "int": (_b_int, "int(x) — convert to integer"),
    "float": (_b_float, "float(x) — convert to float"),
    "bool": (_b_bool, "bool(x) — truthiness of x"),
    "type": (_b_type, "type(x) — the type name of x"),
    "range": (_b_range, "range(stop) | range(start, stop[, step]) — list of ints"),
    "abs": (_b_abs, "abs(x)"),
    "min": (_b_min, "min(...)"),
    "max": (_b_max, "max(...)"),
    "sum": (_b_sum, "sum(list)"),
    "round": (_b_round, "round(x[, ndigits])"),
    "floor": (_b_floor, "floor(x)"),
    "ceil": (_b_ceil, "ceil(x)"),
    "sqrt": (_b_sqrt, "sqrt(x)"),
    "sorted": (_b_sorted, "sorted(list[, reverse: bool])"),
    "keys": (_b_keys, "keys(dict)"),
    "values": (_b_values, "values(dict)"),
    "items": (_b_items, "items(dict) — list of [key, value] pairs"),
    "append": (_b_append, "append(list, value)"),
    "push": (_b_push, "push(list, value)"),
    "pop": (_b_pop, "pop(list)"),
    "join": (_b_join, "join(sep, list)"),
    "split": (_b_split, "split(text[, sep])"),
    "upper": (_b_upper, "upper(text)"),
    "lower": (_b_lower, "lower(text)"),
    "strip": (_b_strip, "strip(text)"),
    "replace": (_b_replace, "replace(text, old, new)"),
    "starts_with": (_b_starts_with, "starts_with(text, prefix)"),
    "ends_with": (_b_ends_with, "ends_with(text, suffix)"),
    "contains": (_b_contains, "contains(container, item)"),
    "json_encode": (_b_json_encode, "json_encode(value)"),
    "json_decode": (_b_json_decode, "json_decode(text)"),
    "now": (_b_now, "now() — epoch seconds"),
    "fail": (_b_fail, "fail(message) — abort the plan with an error"),
    "log": (_b_log, "log(...) — append a message to the trace"),
    "read_file": (_b_read_file, "read_file(path) — requires filesystem capability"),
    "write_file": (
        _b_write_file,
        "write_file(path, content) — requires read_write filesystem",
    ),
}


def install_builtins(env) -> None:
    for name, (fn, doc) in BUILTINS.items():
        env.vars[name] = InthonBuiltin(name, fn, doc)
        env.consts.add(name)


# ---------------------------------------------------------------------------
# Value methods (receiver.method(...))
# ---------------------------------------------------------------------------
def get_method(
    receiver: InthonValue, name: str, span: Span = None
) -> InthonBoundMethod:
    """Resolve a method name on a value, or raise a type error."""
    table = _METHOD_TABLES.get(receiver.type_name)
    fn = table.get(name) if table else None
    if fn is None:
        hint = None
        if table:
            hint = (
                f"Available methods on {receiver.type_name}: {', '.join(sorted(table))}"
            )
        raise InthonTypeError_(
            f"{receiver.type_name} has no method '{name}'", span=span, hint=hint
        )
    return InthonBoundMethod(receiver, name, fn)


def _wrap0(fn):
    return lambda recv, args, kwargs, span: (
        _arity_method(recv, name="?", args=args, n=0),
        fn(recv),
    )[1]


def _arity_method(recv, name, args, n):
    if len(args) != n:
        raise InthonArityError(f"method takes {n} argument(s), got {len(args)}")


def _m(fn):
    """Mark a raw method implementation: fn(receiver, args, kwargs, span)."""
    return fn


_STR_METHODS = {
    "upper": _m(lambda r, a, k, s: InthonString(r.value.upper())),
    "lower": _m(lambda r, a, k, s: InthonString(r.value.lower())),
    "strip": _m(lambda r, a, k, s: InthonString(r.value.strip())),
    "split": _m(
        lambda r, a, k, s: InthonList(
            [
                InthonString(p)
                for p in (r.value.split(a[0].value) if a else r.value.split())
            ]
        )
    ),
    "replace": _m(
        lambda r, a, k, s: InthonString(r.value.replace(a[0].value, a[1].value))
    ),
    "starts_with": _m(lambda r, a, k, s: bool_value(r.value.startswith(a[0].value))),
    "ends_with": _m(lambda r, a, k, s: bool_value(r.value.endswith(a[0].value))),
    "contains": _m(lambda r, a, k, s: bool_value(a[0].value in r.value)),
    "len": _m(lambda r, a, k, s: InthonInt(len(r.value))),
    "join": _m(
        lambda r, a, k, s: InthonString(r.value.join(display(x) for x in a[0].items))
    ),
}

_LIST_METHODS = {
    "append": _m(lambda r, a, k, s: (r.items.append(a[0]), r)[1]),
    "push": _m(lambda r, a, k, s: (r.items.append(a[0]), r)[1]),
    "pop": _m(
        lambda r, a, k, s: (
            r.items.pop()
            if r.items
            else (_ for _ in ()).throw(_err("pop() on empty list"))
        )
    ),
    "top": _m(lambda r, a, k, s: InthonList(r.items[: int(a[0].to_python())])),
    "len": _m(lambda r, a, k, s: InthonInt(len(r.items))),
    "contains": _m(
        lambda r, a, k, s: bool_value(any(V.values_equal(x, a[0]) for x in r.items))
    ),
    "join": _m(
        lambda r, a, k, s: InthonString(a[0].value.join(display(x) for x in r.items))
    ),
    "map": _m(lambda r, a, k, s: _method_map(r, a, s)),
    "filter": _m(lambda r, a, k, s: _method_filter(r, a, s)),
    "sorted": _m(
        lambda r, a, k, s: InthonList(
            sorted(
                r.items,
                key=lambda v: (
                    v.to_python()
                    if isinstance(v, (InthonInt, InthonFloat, InthonString))
                    else display(v)
                ),
            )
        )
    ),
    "reversed": _m(lambda r, a, k, s: InthonList(list(reversed(r.items)))),
}

_DICT_METHODS = {
    "keys": _m(lambda r, a, k, s: InthonList([V.box(x) for x in r.pairs.keys()])),
    "values": _m(lambda r, a, k, s: InthonList(list(r.pairs.values()))),
    "items": _m(
        lambda r, a, k, s: InthonList(
            [InthonList([V.box(x), y]) for x, y in r.pairs.items()]
        )
    ),
    "get": _m(
        lambda r, a, k, s: r.pairs.get(a[0].to_python(), a[1] if len(a) > 1 else NONE)
    ),
    "contains": _m(lambda r, a, k, s: bool_value(a[0].to_python() in r.pairs)),
    "len": _m(lambda r, a, k, s: InthonInt(len(r.pairs))),
}

_METHOD_TABLES = {
    "str": _STR_METHODS,
    "list": _LIST_METHODS,
    "dict": _DICT_METHODS,
}


def _method_map(receiver: InthonList, args, span):
    from .values import InthonCallable

    fn = args[0]
    if not isinstance(fn, InthonCallable):
        raise _err("map() expects a function")
    interp = _active_interpreter.get("interp")
    if interp is None:
        raise _err("map() is unavailable in this context")
    out = []
    for item in receiver.items:
        out.append(interp.call_value(fn, [item], {}, span))
    return InthonList(out)


def _method_filter(receiver: InthonList, args, span):
    from .values import InthonCallable

    fn = args[0]
    if not isinstance(fn, InthonCallable):
        raise _err("filter() expects a function")
    interp = _active_interpreter.get("interp")
    if interp is None:
        raise _err("filter() is unavailable in this context")
    out = []
    for item in receiver.items:
        if interp.call_value(fn, [item], {}, span).truthy():
            out.append(item)
    return InthonList(out)


_active_interpreter: dict = {}


def set_active_interpreter(interp) -> None:
    _active_interpreter["interp"] = interp
