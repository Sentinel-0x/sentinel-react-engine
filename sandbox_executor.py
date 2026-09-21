import subprocess
import shutil
import os
import uuid
import logging
from datetime import datetime
from ast_guard import inspect_code_safety

logger = logging.getLogger("sandbox_executor")


def check_docker_available():
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def run_code_in_sandbox(code_str: str, caller_id: str = "unknown") -> dict:
    """
    在隔离沙箱中执行代码。
    严格要求：Docker 不可用时拒绝执行，绝不降级为裸跑。

    参数:
        code_str: 要执行的代码
        caller_id: 调用者标识（比如 "job-hunter-agent"、"test_rce"），
                   用于审计追责。不传则记为 "unknown"，但会被日志明确标注。

    返回:
        dict，包含 execution_id（本次执行的唯一编号）、caller_id、
        status、output、timestamp 等字段，供上层做审计和监控使用。
    """
    execution_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    log_context = f"[execution_id={execution_id}] [caller={caller_id}]"

    result = {
        "execution_id": execution_id,
        "caller_id": caller_id,
        "timestamp": timestamp,
        "status": None,
        "output": None,
    }

    violations = inspect_code_safety(code_str)
    if violations:
        result["status"] = "rejected_by_ast_guard"
        result["output"] = "\n".join([f" - {v}" for v in violations])
        logger.warning(f"{log_context} REJECTED by AST guard: {violations}")
        return result

    if not check_docker_available():
        result["status"] = "refused_no_isolation"
        result["output"] = (
            "Docker is not available on this host. Execution refused rather "
            "than falling back to an unsandboxed environment."
        )
        logger.error(f"{log_context} REFUSED: Docker unavailable, no fallback permitted")
        return result

    temp_file = f"temp_sandbox_{execution_id}.py"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code_str)

    logger.info(f"{log_context} STARTING execution in Docker sandbox")

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
        proc_result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if proc_result.returncode == 0:
            result["status"] = "success"
            result["output"] = proc_result.stdout.strip()
            logger.info(f"{log_context} SUCCESS")
        else:
            result["status"] = "execution_error"
            result["output"] = proc_result.stderr.strip()
            logger.warning(f"{log_context} EXECUTION ERROR: {proc_result.stderr.strip()[:200]}")

    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["output"] = "Execution timed out in Docker sandbox."
        logger.warning(f"{log_context} TIMEOUT")

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    return result
