from inthon.compiler.transpiler import run_transpiled


def test_transpiler_basic_arithmetic():
    source = "let x = 10 + 20 * 2 - 5\nx"
    res = run_transpiled(source)
    assert res.output == 45


def test_transpiler_variables_and_control_flow():
    source = """
    let my_sum = 0
    let i = 1
    while i <= 5 {
        my_sum = my_sum + i
        i = i + 1
    }
    my_sum
    """
    res = run_transpiled(source)
    assert res.output == 15


def test_transpiler_functions():
    source = """
    fn multiply(a, b = 2) {
        return a * b
    }
    let val = multiply(10, b: 3)
    val
    """
    res = run_transpiled(source)
    assert res.output == 30


def test_transpiler_for_loops():
    source = """
    let my_sum = 0
    for x in [1, 2, 3, 4] {
        my_sum = my_sum + x
    }
    my_sum
    """
    res = run_transpiled(source)
    assert res.output == 10


def test_transpiler_if_else_and_indexing():
    source = """
    let list = [10, 20, 30]
    let first = list[0]
    let result = 0
    if first == 10 {
        result = 100
    } else {
        result = 200
    }
    result
    """
    res = run_transpiled(source)
    assert res.output == 100
