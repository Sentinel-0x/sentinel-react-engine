from sandbox_executor import run_code_in_sandbox

print("=== 正在验证恶意代码拦截 ===")
bad_code = 'import os; os.system("ls")'
result = run_code_in_sandbox(bad_code)
print(result)

print("\n=== 正在验证合法代码放行 ===")
good_code = 'print("Hello, secure world!")'
result_good = run_code_in_sandbox(good_code)
print(result_good)
