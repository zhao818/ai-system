import subprocess
from config import EXECUTOR_CONFIG


def _build_cmd(model: str, task: str, **kwargs) -> list:
    cmd = [
        EXECUTOR_CONFIG["opencode_cmd"],
        "run",
        task,
        "-m", model,
    ]

    if EXECUTOR_CONFIG.get("auto_approve"):
        cmd.append("--auto")

    # 可选: 指定工作目录
    workdir = kwargs.pop("dir", None)
    if workdir:
        cmd.extend(["--dir", workdir])

    for key, value in kwargs.items():
        if value is not None:
            cmd.extend([f"--{key}", str(value)])

    return cmd


def run_opencode(model: str, task: str, **kwargs) -> str:
    cmd = _build_cmd(model, task, **kwargs)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXECUTOR_CONFIG["timeout"]
        )

        if result.returncode != 0:
            raise RuntimeError(f"OpenCode exited with {result.returncode}: {result.stderr[:500]}")

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"OpenCode timed out after {EXECUTOR_CONFIG['timeout']}s")
    except FileNotFoundError:
        raise RuntimeError("OpenCode not found. Install with: pip install opencode-ai")


def run_opencode_stream(model: str, task: str, **kwargs):
    cmd = _build_cmd(model, task, **kwargs)

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