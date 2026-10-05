import subprocess
import shutil
import os
import uuid
import tempfile
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

    temp_dir = tempfile.mkdtemp(prefix="sentinel_sandbox_")
    temp_file = os.path.join(temp_dir, f"script_{execution_id}.py")
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
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    check_and_alert(result)
    return result


def run_code_in_sandbox_with_network(code_str: str, caller_id: str = "unknown") -> dict:
    """
    与 run_code_in_sandbox 相同的安全模型，唯一区别：
    容器接入 sandbox_net 专用网络，所有出站流量强制经过 whitelist_proxy（Squid白名单代理）。
    容器本身依然不能直接连公网，只能到达代理，代理只放行白名单域名。
    仅当任务明确需要网络访问（如pip安装包）时才使用此函数，默认应使用完全断网的 run_code_in_sandbox。
    """
    execution_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    container_name = f"sandbox_net_{execution_id}"

    log_context = f"[execution_id={execution_id}] [caller={caller_id}] [networked]"

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

    temp_dir = tempfile.mkdtemp(prefix="sentinel_sandbox_net_")
    temp_file = os.path.join(temp_dir, f"script_{execution_id}.py")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code_str)

    logger.info(f"{log_context} STARTING execution in networked (whitelist-proxied) sandbox")

    try:
        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "sandbox_net",
            "--memory", "512m",
            "--cpus", "1.0",
            "--user", "1000:1000",
            "-e", "HTTP_PROXY=http://whitelist_proxy:3128",
            "-e", "HTTPS_PROXY=http://whitelist_proxy:3128",
            "-v", f"{os.path.abspath(temp_file)}:/app/script.py:ro",
            "sentinel-sandbox-networked:latest",
            "python", "/app/script.py"
        ]
        proc_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

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
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    check_and_alert(result)
    return result
