from ast_guard import inspect_code_safety

malicious_code = """
import os
print("=== 尝试读取容器内 passwd ===")
os.system('cat /etc/passwd')
"""

def main():
    print("正在通过 AST 静态网关对代码进行安全预检...")
    violations = inspect_code_safety(malicious_code)

    # 如果没有发现违规，立即让测试失败；绝不运行危险代码
    assert violations, (
        "FAIL: AST guard 没有拦截危险代码，测试失败。"
    )

    assert any("os" in item for item in violations), (
        "FAIL: 没有识别出 os 模块相关违规。"
    )
    assert any("system" in item for item in violations), (
        "FAIL: 没有识别出 system 调用相关违规。"
    )

    print("PASS: AST guard 成功拦截危险代码，代码未送入沙箱。")
    for item in violations:
        print(f" - {item}")

if __name__ == "__main__":
    main()
