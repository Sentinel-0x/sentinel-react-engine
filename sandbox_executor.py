import subprocess
import shutil
import os
import uuid
import logging
from datetime import datetime, timezone
from ast_guard import inspect_code_safety
from security_monitor import check_and_alert

logger = logging.getLogger("sandbox_executor")


def check_docker_available():
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False


def _kill_container(container_name: str):
    """强制杀死并清理指定名字的容器，用于超时后的主动清理"""
    try:
        subprocess.run(["docker", "kill", container_name], capture_output=True, text=True, timeout=5)
        logger.warning(f"Forcefully killed container: {container_name}")
    except Exception as e:
        logger.error(f"Failed to kill container {container_name}: {e}")


def run_code_in_sandbox(code_str: str, caller_id: str = "unknown") -> dict:
    """
    在隔离沙箱中执行代码。
    严格要求：Docker 不可用时拒绝执行，绝不降级为裸跑。
    超时发生时，主动 kill 容器，不依赖 --rm 被动清理（--rm 只在容器
    正常退出时生效，对死循环等永不退出的代码无效）。
    """
    execution_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    container_name = f"sandbox_{execution_id}"

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
        check_and_alert(result)
        return result

    if not check_docker_available():
        result["status"] = "refused_no_isolation"
        result["output"] = (
            "Docker is not available on this host. Execution refused rather "
            "than falling back to an unsandboxed environment."
        )
        logger.error(f"{log_context} REFUSED: Docker unavailable, no fallback permitted")
        check_and_alert(result)
        return result

    temp_file = f"temp_sandbox_{execution_id}.py"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code_str)

    logger.info(f"{log_context} STARTING execution in Docker sandbox (container={container_name})")

    try:
        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
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
        result["output"] = "Execution timed out and container was forcefully terminated."
        logger.warning(f"{log_context} TIMEOUT — forcefully killing container")
        _kill_container(container_name)

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    check_and_alert(result)
    return result
