import os
import time
import sqlite3
import logging
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("security_monitor")

BURST_THRESHOLD = 5
BURST_WINDOW_SECONDS = 300  # 5分钟
DB_PATH = "agent_state.db"  # 与 SQLiteMemoryStore 共用同一数据库文件，独立建表


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_id TEXT,
            execution_id TEXT,
            event_type TEXT,
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()


def _record_rejection(caller_id: str, execution_id: str):
    """把一次AST拦截事件写入持久化存储，跨进程重启依然保留"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO security_events (caller_id, execution_id, event_type, timestamp) VALUES (?, ?, ?, ?)',
        (caller_id, execution_id, "rejected_by_ast_guard", time.time())
    )
    conn.commit()
    conn.close()


def _count_recent_rejections(caller_id: str) -> int:
    """查询某个caller在时间窗口内的拦截次数，从持久化存储读取，不依赖进程内存"""
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cutoff = time.time() - BURST_WINDOW_SECONDS
    cursor.execute(
        'SELECT COUNT(*) FROM security_events WHERE caller_id = ? AND event_type = ? AND timestamp >= ?',
        (caller_id, "rejected_by_ast_guard", cutoff)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


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
    规则2：同一caller在时间窗口内密集触发AST拦截即告警（体量异常，持久化存储，跨进程重启依然生效）
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
        _record_rejection(caller_id, execution_id)
        recent_count = _count_recent_rejections(caller_id)

        if recent_count >= BURST_THRESHOLD:
            alert_text = (
                f"🚨 *安全告警: 异常密集的AST拦截*\n"
                f"调用方: `{caller_id}`\n"
                f"{BURST_WINDOW_SECONDS}秒内触发 {recent_count} 次AST拦截（持久化记录，跨进程重启统计）\n"
                f"最新执行ID: `{execution_id}`\n"
                f"可能是在探测安全边界，建议人工核查"
            )
            logger.critical(f"[SECURITY ALERT] burst rejection caller={caller_id} count={recent_count}")
            send_telegram_alert(alert_text)
