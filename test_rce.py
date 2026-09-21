from ast_guard import inspect_code_safety
from sandbox_executor import run_code_in_sandbox

malicious_code = """
import os
print("=== 尝试读取容器内 passwd ===")
os.system('cat /etc/passwd')
"""

print("正在通过 AST 静态网关对代码进行安全预检...")
violations = inspect_code_safety(malicious_code)

if violations:
    print("❌ [AST 拦截生效] 发现高危违规调用，拒绝送入沙箱：")
    for v in violations:
        print(f"  - {v}")
else:
    print("✅ AST 校验通过，正在送入 Docker 沙箱...")
    result = run_code_in_sandbox(malicious_code, caller_id="test_rce")
    print(f"执行结果反馈 [execution_id={result['execution_id']}]:")
    print(f"状态: {result['status']}")
    print(f"输出: {result['output']}")
