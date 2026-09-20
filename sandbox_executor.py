import subprocess
import shutil
import os
from ast_guard import inspect_code_safety


def check_docker_available():
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def run_code_in_sandbox(code_str: str) -> str:
    """
    在隔离沙箱中执行代码。
    严格要求：Docker 不可用时拒绝执行，绝不降级为裸跑。
    没有隔离，就不执行——这是唯一诚实的选择。
    """
    violations = inspect_code_safety(code_str)
    if violations:
        return f"❌ [Security Error] Code execution rejected by AST Static Guard:\n" + "\n".join([f" - {v}" for v in violations])

    if not check_docker_available():
        return (
            "❌ [Isolation Unavailable] Docker is not available on this host. "
            "Code execution has been refused rather than falling back to an "
            "unsandboxed environment. Start the Docker daemon and retry."
        )

    temp_file = "temp_sandbox_script.py"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code_str)
    try:
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "--user", "1000:1000",
            "-v", f"{os.path.abspath(temp_file)}:/app/script.py:ro",
            "python:3.10-slim",
            "python", "/app/script.py"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"Execution Success (Docker Mode):\n{result.stdout.strip()}"
        else:
            return f"Execution Error (Docker Mode):\n{result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "❌ [Timeout Error] Execution timed out in Docker sandbox."
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
