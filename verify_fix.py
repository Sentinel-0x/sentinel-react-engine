from sandbox_executor import run_code_in_sandbox

print("=== 正在验证恶意代码拦截 ===")
bad_code = 'import os; os.system("ls")'
result = run_code_in_sandbox(bad_code, caller_id="verify_fix")
print(f"[{result['execution_id']}] 状态: {result['status']} | 输出: {result['output']}")

print("\n=== 正在验证合法代码放行 ===")
good_code = 'print("Hello, secure world!")'
result_good = run_code_in_sandbox(good_code, caller_id="verify_fix")
print(f"[{result_good['execution_id']}] 状态: {result_good['status']} | 输出: {result_good['output']}")
