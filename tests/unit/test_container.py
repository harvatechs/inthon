import pytest
from pathlib import Path
from inthon.runtime.container import run_in_container


def test_run_in_container_raises_when_no_docker(monkeypatch):
    # Mock shutil.which to return None so that Docker is considered missing
    import shutil

    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    # Test file path (does not need to exist for this check since docker check is first)
    dummy_file = Path("dummy.inth")

    with pytest.raises(RuntimeError) as exc:
        run_in_container(dummy_file)

    assert "INTHON_CONTAINER_001" in str(exc.value)
    assert "Docker is not installed" in str(exc.value)
