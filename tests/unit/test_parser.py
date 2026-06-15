import pytest
from inthon.parser.parser import parse, ParseError
from inthon.ast import nodes as N

def test_parse_let_const():
    src = "let x: int = 10\nconst y = 20"
    prog = parse(src)
    assert len(prog.body) == 2
    assert isinstance(prog.body[0], N.LetStmt)
    assert prog.body[0].name == "x"
    assert isinstance(prog.body[0].type_ann, N.PrimitiveType)
    assert prog.body[0].type_ann.name == "int"
    assert isinstance(prog.body[0].value, N.IntLiteral)
    assert prog.body[0].value.value == 10

    assert isinstance(prog.body[1], N.ConstStmt)
    assert prog.body[1].name == "y"
    assert prog.body[1].type_ann is None
    assert isinstance(prog.body[1].value, N.IntLiteral)
    assert prog.body[1].value.value == 20

def test_parse_expr():
    src = "x = a + b * c ** d"
    prog = parse(src)
    assert len(prog.body) == 1
    assert isinstance(prog.body[0], N.AssignStmt)
    assert prog.body[0].target == "x"
    # Binary operations checks
    val = prog.body[0].value
    assert isinstance(val, N.BinaryOp)
    assert val.op == "+"
    assert isinstance(val.left, N.Identifier)
    assert val.left.name == "a"
    assert isinstance(val.right, N.BinaryOp)
    assert val.right.op == "*"
    assert isinstance(val.right.left, N.Identifier)
    assert val.right.left.name == "b"
    assert isinstance(val.right.right, N.BinaryOp)
    assert val.right.right.op == "**"
    assert isinstance(val.right.right.left, N.Identifier)
    assert val.right.right.left.name == "c"

def test_parse_fn_decl():
    src = "fn add(a: int, b: int = 5) -> int { return a + b }"
    prog = parse(src)
    assert len(prog.body) == 1
    fn = prog.body[0]
    assert isinstance(fn, N.FnDecl)
    assert fn.name == "add"
    assert len(fn.params) == 2
    assert fn.params[0].name == "a"
    assert fn.params[0].type_ann.name == "int"
    assert fn.params[1].name == "b"
    assert fn.params[1].type_ann.name == "int"
    assert fn.params[1].default.value == 5
    assert fn.return_type.name == "int"
    assert len(fn.body) == 1
    assert isinstance(fn.body[0], N.ReturnStmt)

def test_parse_imports():
    src = "use tool web.search\nuse py.pandas as pd\nuse memory.project(\"study\")"
    prog = parse(src)
    assert len(prog.body) == 3
    assert isinstance(prog.body[0], N.UseToolStmt)
    assert prog.body[0].tool_path == "web.search"
    assert isinstance(prog.body[1], N.UsePyStmt)
    assert prog.body[1].module_path == "pandas"
    assert prog.body[1].alias == "pd"
    assert isinstance(prog.body[2], N.UseMemoryStmt)
    assert prog.body[2].namespace == "project"
    assert len(prog.body[2].args) == 1
    assert prog.body[2].args[0].value == "study"

def test_parse_agent_block():
    src = """
    agent Researcher {
        goal "Research a topic"
        policy {
            allow_network: true
            max_tool_calls: 10
        }
        plan {
            let links = web.search("INTHON", limit: 5)
            return links
        }
    }
    """
    prog = parse(src)
    assert len(prog.body) == 1
    agent = prog.body[0]
    assert isinstance(agent, N.AgentDecl)
    assert agent.name == "Researcher"
    assert agent.goal == "Research a topic"
    assert agent.policy is not None
    assert len(agent.policy.entries) == 2
    assert agent.policy.entries[0].key == "allow_network"
    assert agent.policy.entries[0].value is True
    assert agent.policy.entries[1].key == "max_tool_calls"
    assert agent.policy.entries[1].value == 10
    assert len(agent.plan.body) == 2
    assert isinstance(agent.plan.body[0], N.LetStmt)
    assert isinstance(agent.plan.body[1], N.ReturnStmt)

def test_parse_agent_primitives():
    src = """
    approve payment before execute
    remember x in project
    forget x from project
    y = recall "key" from project
    guard x > 5
    """
    prog = parse(src)
    assert len(prog.body) == 5
    assert isinstance(prog.body[0], N.ApproveStmt)
    assert prog.body[0].target == "payment"
    assert prog.body[0].action == "execute"

    assert isinstance(prog.body[1], N.RememberStmt)
    assert isinstance(prog.body[1].value, N.Identifier)
    assert prog.body[1].namespace == "project"

    assert isinstance(prog.body[2], N.ForgetStmt)
    assert isinstance(prog.body[2].key, N.Identifier)
    assert prog.body[2].namespace == "project"

    assert isinstance(prog.body[3], N.RecallStmt)
    assert prog.body[3].var == "y"
    assert prog.body[3].query == "key"
    assert prog.body[3].namespace == "project"

    assert isinstance(prog.body[4], N.GuardStmt)

def test_parse_retry_logic():
    src = """
    retry 3 with backoff exponential {
        let x = 10
    } catch err {
        return none
    }
    """
    prog = parse(src)
    assert len(prog.body) == 1
    retry = prog.body[0]
    assert isinstance(retry, N.RetryStmt)
    assert retry.count == 3
    assert retry.backoff == "exponential"
    assert len(retry.body) == 1
    assert retry.catch_block is not None
    assert retry.catch_block.var == "err"
    assert len(retry.catch_block.body) == 1

def test_parse_error_reporting():
    with pytest.raises(ParseError) as excinfo:
        parse("let x = ")
    assert "INTHON_PARSE_001" in str(excinfo.value)
