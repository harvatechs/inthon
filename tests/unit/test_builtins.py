from inthon import run, run_vm


def test_builtin_print():
    source = 'print("hello", "world")'
    res = run(source)
    assert res.output is None

    res_vm = run_vm(source)
    assert res_vm.output is None


def test_builtin_range_and_loop():
    source = """
    let total = 0
    for i in range(5) {
        total = total + i
    }
    total
    """
    res = run(source)
    assert res.output == 10

    res_vm = run_vm(source)
    assert res_vm.output == 10


def test_builtin_len():
    source = 'let l = len([1, 2, 3]); let s = len("hello"); [l, s]'
    res = run(source)
    assert res.output == [3, 5]

    res_vm = run_vm(source)
    assert res_vm.output == [3, 5]


def test_builtin_type_casts():
    source = """
    let s_int = int("123")
    let s_float = float("1.25")
    let s_str = str(456)
    let s_bool = bool(1);
    [s_int, s_float, s_str, s_bool]
    """
    res = run(source)
    assert res.output == [123, 1.25, "456", True]

    res_vm = run_vm(source)
    assert res_vm.output == [123, 1.25, "456", True]


def test_builtin_math_helpers():
    source = """
    let a = abs(-10)
    let m1 = min(5, 3, 9)
    let m2 = max(5, 3, 9)
    let s = sum([1, 2, 3])
    let r = round(1.234, 2);
    [a, m1, m2, s, r]
    """
    res = run(source)
    assert res.output == [10, 3, 9, 6, 1.23]

    res_vm = run_vm(source)
    assert res_vm.output == [10, 3, 9, 6, 1.23]
