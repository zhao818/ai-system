import subprocess
import shlex
from config import OPENCODE_CONFIG
from models import TaskRequest


def run_opencode(model: str, task: str, **kwargs) -> str:
    cmd = [
        OPENCODE_CONFIG["command"],
        "run",
        "--model", model,
        "--task", task
    ]

    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key}", str(value)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OPENCODE_CONFIG["timeout"]
        )

        if result.returncode != 0:
            raise RuntimeError(f"OpenCode exited with {result.returncode}: {result.stderr}")

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"OpenCode timed out after {OPENCODE_CONFIG['timeout']}s")
    except FileNotFoundError:
        raise RuntimeError("OpenCode not found. Install with: pip install opencode-ai")


def run_opencode_stream(model: str, task: str, **kwargs):
    cmd = [
        OPENCODE_CONFIG["command"],
        "run",
        "--model", model,
        "--task", task
    ]

    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key}", str(value)])

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    for line in process.stdout:
        yield line

    process.wait()
    if process.returncode != 0:
        stderr = process.stderr.read() if process.stderr else "Unknown error"
        raise RuntimeError(f"OpenCode exited with {process.returncode}: {stderr}")