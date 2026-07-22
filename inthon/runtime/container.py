from __future__ import annotations
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from .. import RunResult


def run_in_container(
    file_path: Path | str,
    mock_tools: bool = True,
    max_cost_usd: float = 1.0,
    max_runtime_sec: float = 300.0,
) -> RunResult:
    """
    Run an INTHON program inside a sandboxed Docker container for absolute defense-in-depth isolation.
    If Docker is not installed/running, raises a RuntimeError.
    """
    docker_path = shutil.which("docker")
    if not docker_path:
        raise RuntimeError(
            "INTHON_CONTAINER_001: Docker is not installed or not available on PATH. "
            "Containerized execution (SB-23) requires a running Docker daemon."
        )

    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Create temporary directory for building the Docker context
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Copy the input program
        prog_name = file_path.name
        shutil.copy2(file_path, tmp_path / prog_name)

        # Find the repository root of inthon to copy it into the container
        # inthon package is located at e:\AITHON\inthon
        inthon_package_src = Path(__file__).parent.parent
        inthon_package_dest = tmp_path / "inthon"
        shutil.copytree(inthon_package_src, inthon_package_dest)

        # Write pyproject.toml / requirements to ensure dependency installation
        # We write a basic Dockerfile
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        dockerfile_content = f"""FROM python:{py_version}-slim

WORKDIR /app

# Install dependencies required by inthon package
RUN pip install --no-cache-dir lark typer rich pydantic fastapi jsonschema structlog

# Copy inthon source and input program
COPY inthon /app/inthon
COPY {prog_name} /app/{prog_name}

ENV PYTHONPATH=/app

# Run the program and print output/trace
CMD ["python", "-m", "inthon", "run", "/app/{prog_name}", "--trace-out", "/app/trace.json", "--max-cost", "{max_cost_usd}"]
"""
        (tmp_path / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")

        # Build the Docker image
        image_tag = f"inthon-sandbox-{tmp_path.name.lower()}"
        build_res = subprocess.run(
            [docker_path, "build", "-t", image_tag, "."],
            cwd=tmp_dir,
            capture_output=True,
            text=True,
        )
        if build_res.returncode != 0:
            raise RuntimeError(
                f"INTHON_CONTAINER_002: Docker image build failed:\n{build_res.stderr}"
            )

        try:
            # Run the container and mount a volume to retrieve trace.json
            run_res = subprocess.run(
                [
                    docker_path,
                    "run",
                    "--rm",
                    "--network",
                    "none",  # complete network isolation unless policy allows it
                    image_tag,
                ],
                capture_output=True,
                text=True,
                timeout=max_runtime_sec,
            )
            stdout = run_res.stdout
            stderr = run_res.stderr

            if run_res.returncode != 0:
                raise RuntimeError(
                    f"INTHON_CONTAINER_003: Isolated execution failed with exit code {run_res.returncode}:\n{stderr}\n{stdout}"
                )

            # Return success with parsed stdout
            # Note: For production use we can parse output and trace file logs.
            # We return output as stdout string.

            return RunResult(
                ok=True,
                result_python=stdout.strip(),
                result_display=stdout.strip(),
                trace={"container_execution": True, "stdout": stdout},
                stdout=stdout,
                backend="container",
            )

        finally:
            # Clean up the built Docker image
            subprocess.run(
                [docker_path, "rmi", image_tag],
                capture_output=True,
            )
