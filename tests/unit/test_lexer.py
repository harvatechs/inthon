from hypothesis import given, strategies as st
from inthon.lexer.tokenizer import Tokenizer, LexerError
from inthon.lexer.tokens import TokenType


@given(st.text())
def test_lexer_does_not_crash_on_random_inputs(text: str) -> None:
    try:
        Tokenizer(text).tokenize()
    except LexerError:
        pass


def test_string_literal_round_trips() -> None:
    src = '"hello world"'
    tokens = Tokenizer(src).tokenize()
    assert tokens[0].type == TokenType.STRING_LIT
    assert tokens[0].value == src
    assert tokens[1].type == TokenType.EOF


def test_arrow_token() -> None:
    tokens = Tokenizer("->").tokenize()
    assert tokens[0].type == TokenType.ARROW


def test_span_accuracy() -> None:
    src = "let x = 10"
    tokens = Tokenizer(src, filename="test.inth").tokenize()
    let_tok = next(t for t in tokens if t.type == TokenType.LET)
    assert let_tok.span.line == 1
    assert let_tok.span.col == 1
    assert let_tok.span.offset == 0
    assert let_tok.span.length == 3


def test_comments() -> None:
    src = "// this is a comment\nlet x = 10 /* block comment */"
    tokens = Tokenizer(src).tokenize()
    # Check that comment tokens are skipped/omitted (or parsed but stripped, in our case they are skipped)
    assert tokens[0].type == TokenType.NEWLINE
    assert tokens[1].type == TokenType.LET
    assert tokens[2].type == TokenType.IDENT
    assert tokens[3].type == TokenType.EQ
    assert tokens[4].type == TokenType.INT_LIT


def test_invalid_character() -> None:
    try:
        Tokenizer("@").tokenize()
        assert False, "Expected LexerError"
    except LexerError as e:
        assert "@" in str(e)
