import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "programs"

@pytest.fixture
def parser_fixture():
    from inthon.parser.parser import parse
    return parse
