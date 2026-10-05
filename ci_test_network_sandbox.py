"""
CI专用测试脚本：验证白名单联网沙箱机制。
独立文件而非内嵌在YAML里，避免shell/YAML多层转义导致的语法错误。
"""
from sandbox_executor import run_code_in_sandbox_with_network

CODE_ALLOWED = """
import urllib.request
resp = urllib.request.urlopen("https://pypi.org", timeout=10)
print(f"status: {resp.status}")
"""

CODE_BLOCKED = """
import urllib.request
try:
    urllib.request.urlopen("https://www.baidu.com", timeout=10)
    print("SHOULD NOT REACH HERE")
except Exception as e:
    print(f"blocked as expected: {e}")
"""


def main():
    result1 = run_code_in_sandbox_with_network(CODE_ALLOWED, caller_id="ci_network_test")
    assert result1["status"] == "success", (
        f"Expected success for whitelisted domain, got {result1['status']}: {result1['output']}"
    )
    print("PASS: whitelisted domain (pypi.org) accessible")

    result2 = run_code_in_sandbox_with_network(CODE_BLOCKED, caller_id="ci_network_test")
    assert "blocked as expected" in result2["output"], (
        f"Expected non-whitelisted domain to be blocked, got: {result2['output']}"
    )
    print("PASS: non-whitelisted domain (baidu.com) correctly blocked")


if __name__ == "__main__":
    main()
