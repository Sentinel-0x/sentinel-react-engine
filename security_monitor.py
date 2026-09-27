import os
import time
import logging
import requests
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("security_monitor")

# 短时间窗口内，同一caller触发多少次AST拦截算异常（参考HF事件教训：靠体量识破，不是单次事件）
BURST_THRESHOLD = 5
BURST_WINDOW_SECONDS = 300  # 5分钟

# 内存中记录每个caller最近的拦截时间戳
_rejection_history = defaultdict(lambda: deque(maxlen=50))


def send_telegram_alert(text: str):
    """发送安全告警到Telegram"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("Telegram未配置，无法发送安全告警")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        logger.error(f"安全告警发送失败: {e}")


def check_and_alert(sandbox_result: dict):
    """
    检查一次沙箱执行结果，判断是否需要触发安全告警。
    规则1：refused_no_isolation 出现一次即告警（隔离失效）
    规则2：同一caller在时间窗口内密集触发AST拦截即告警（体量异常，参考HF事件教训）
    """
    status = sandbox_result.get("status")
    caller_id = sandbox_result.get("caller_id", "unknown")
    execution_id = sandbox_result.get("execution_id", "unknown")

    if status == "refused_no_isolation":
        alert_text = (
            f"🚨 *安全告警: 隔离失效*\n"
            f"调用方: `{caller_id}`\n"
            f"执行ID: `{execution_id}`\n"
            f"原因: Docker不可用，执行被拒绝（系统已正确拒绝裸跑，但请检查Docker服务状态）"
        )
        logger.critical(f"[SECURITY ALERT] refused_no_isolation caller={caller_id} execution={execution_id}")
        send_telegram_alert(alert_text)
        return

    if status == "rejected_by_ast_guard":
        now = time.time()
        _rejection_history[caller_id].append(now)

        recent = [t for t in _rejection_history[caller_id] if now - t <= BURST_WINDOW_SECONDS]
        if len(recent) >= BURST_THRESHOLD:
            alert_text = (
                f"🚨 *安全告警: 异常密集的AST拦截*\n"
                f"调用方: `{caller_id}`\n"
                f"{BURST_WINDOW_SECONDS}秒内触发 {len(recent)} 次AST拦截\n"
                f"最新执行ID: `{execution_id}`\n"
                f"可能是在探测安全边界，建议人工核查"
            )
            logger.critical(f"[SECURITY ALERT] burst rejection caller={caller_id} count={len(recent)}")
            send_telegram_alert(alert_text)
            _rejection_history[caller_id].clear()
