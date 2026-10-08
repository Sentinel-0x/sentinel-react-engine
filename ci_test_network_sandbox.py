"""
CI专用测试：验证沙箱的网络边界。
不只测"守规矩的请求被放行/拦截"，还测"故意绕过代理的直连必须失败"。
"""
from sandbox_executor import run_code_in_sandbox, run_code_in_sandbox_with_network

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

CODE_DIRECT = """
import requests
s = requests.Session()
s.trust_env = False
try:
    r = s.get("https://www.baidu.com", timeout=10)
    print(f"DIRECT ACCESS WORKED: {r.status_code}")
except Exception as e:
    print(f"direct access blocked: {type(e).__name__}")
"""

CODE_OFFLINE = """
import urllib.request
try:
    urllib.request.urlopen("https://www.baidu.com", timeout=10)
    print("OFFLINE MODE REACHED THE NETWORK")
except Exception as e:
    print(f"offline mode blocked: {type(e).__name__}")
"""


def main():
    r1 = run_code_in_sandbox_with_network(CODE_ALLOWED, caller_id="ci_network_test")
    assert r1["status"] == "success", f"whitelisted domain failed: {r1['status']}: {r1['output']}"
    print("PASS 1: whitelisted domain reachable through the proxy")

    r2 = run_code_in_sandbox_with_network(CODE_BLOCKED, caller_id="ci_network_test")
    assert "blocked as expected" in (r2["output"] or ""), f"non-whitelisted domain not blocked: {r2['output']}"
    print("PASS 2: non-whitelisted domain blocked by the proxy")

    r3 = run_code_in_sandbox_with_network(CODE_DIRECT, caller_id="ci_network_test")
    out3 = r3["output"] or ""
    assert r3["status"] == "success" and "direct access blocked" in out3 and "DIRECT ACCESS WORKED" not in out3, \
        f"direct connection was not blocked: {r3['status']}: {out3}"
    print("PASS 3: direct connection that bypasses the proxy is blocked")

    r4 = run_code_in_sandbox(CODE_OFFLINE, caller_id="ci_network_test")
    out4 = r4["output"] or ""
    assert r4["status"] == "success" and "offline mode blocked" in out4 and "REACHED" not in out4, \
        f"offline mode was not isolated: {r4['status']}: {out4}"
    print("PASS 4: offline mode has no network access")


if __name__ == "__main__":
    main()
