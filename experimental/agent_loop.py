import docker
import os
import ast
import tempfile
import hashlib
from pydantic import BaseModel
from openai import OpenAI

class AgentActionSchema(BaseModel):
    thought: str
    code: str

def call_llm_to_fix_code(faulty_code: str, error_message: str) -> str:
    client = OpenAI(
        base_url="https://api.siliconflow.cn/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )

    prompt = (
        "你是一个精通 Python 的 AI 编程助手。当前代码在执行时遇到了致命错误。\n"
        "请结合最新的错误信息进行针对性修复，并严格以 JSON 格式返回。\n\n"
        "【当前出错代码】\n```python\n" + faulty_code + "\n```\n\n"
        "【最新错误日志】\n```\n" + error_message + "\n```\n\n"
        "【硬性要求】\n"
        "1. 必须修正错误。\n"
        "2. 必须输出严格的 JSON 格式，包含两个字段：'thought' (你的思考过程) 和 'code' (修复后的纯 Python 代码字符串，严禁包含任何 markdown 符号)。"
    )

    print("[控制层] 正在请求大模型进行结构化反思与自愈（已开启状态剪枝与防呆截断）...")
    
    response = client.chat.completions.create(
        model="deepseek-ai/DeepSeek-V3",
        messages=[
            {"role": "system", "content": "You are a precise automated code debugging assistant. You must output a JSON object with 'thought' and 'code' fields."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        frequency_penalty=0.5
    )
    
    raw_content = response.choices[0].message.content.strip()
    
    # 【新增防呆机制 1】：对 LLM 返回的原始内容进行硬截断保护（如超过 15000 字符强行截断，防止垃圾文本刷屏）
    if len(raw_content) > 15000:
        print("[控制层警告] 捕获到大模型超长异常输出，已触发硬截断机制！")
        raw_content = raw_content[:15000]
    
    parsed_data = AgentActionSchema.model_validate_json(raw_content)
    fixed_code = parsed_data.code.strip()
    
    if fixed_code.startswith("```python"):
        fixed_code = fixed_code[9:]
    elif fixed_code.startswith("```"):
        fixed_code = fixed_code[3:]
    if fixed_code.endswith("```"):
        fixed_code = fixed_code[:-3]
        
    return fixed_code.strip()

def run_code_in_sandbox_with_retry(initial_code: str, max_retries: int = 3, timeout_seconds: int = 10) -> str:
    client = docker.from_env()
    abs_current_path = os.path.abspath(".")
    current_code = initial_code
    
    history_code_hashes = set() # 【新增防呆机制 2】：用于记录历次修复后的代码指纹，防止陷入原地打转的死循环
    
    for attempt in range(1, max_retries + 1):
        print(f"\n[控制层] 尝试执行代码循环 (第 {attempt}/{max_retries} 次)...")
        
        # 计算当前代码指纹
        code_hash = hashlib.md5(current_code.encode('utf-8')).hexdigest()
        if code_hash in history_code_hashes:
            print("[控制层熔断] 检测到大模型进入‘无效重复修复’状态（前后代码逻辑完全一致），触发防呆熔断，终止重试！")
            return f"任务因陷入重复修复循环而安全熔断。最后代码指纹: {code_hash}"
        history_code_hashes.add(code_hash)
        
        try:
            print("[控制层防线] 正在进行 AST 静态语法检查...")
            ast.parse(current_code)
            print("[控制层防线] AST 语法检查通过。")
        except SyntaxError as se:
            syntax_error_msg = f"AST SyntaxError: {se.text} (line {se.lineno}): {str(se)}"
            print(f"[控制层警告] 静态语法预检失败:\n{syntax_error_msg}")
            
            if attempt == max_retries:
                return f"达到最大重试次数 ({max_retries})，静态语法修正失败。错误: \n{syntax_error_msg}"
            
            current_code = call_llm_to_fix_code(current_code, syntax_error_msg)
            continue

        confirm = input("[红队/安全卡点] Agent 即将在 Docker 沙箱中执行动态代码，是否允许？(y/n): ")
        if confirm.strip().lower() != 'y':
            return "执行已被用户人工终止。"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir='.', delete=False, encoding='utf-8') as tf:
            tf.write(current_code)
            script_filename = os.path.basename(tf.name)

        container = None
        try:
            container = client.containers.create(
                image="agent-sandbox",
                command=f"python /workspace/{script_filename}",
                volumes={abs_current_path: {'bind': '/workspace', 'mode': 'rw'}},
                working_dir="/workspace",
                mem_limit="512m",
                nano_cpus=1000000000
            )
            
            container.start()
            
            result = container.wait(timeout=timeout_seconds)
            logs = container.logs(stdout=True, stderr=True).decode('utf-8')
            
            if result.get('StatusCode', 0) != 0:
                raise RuntimeError(f"容器内执行异常退出 (Exit Code: {result.get('StatusCode')}), 日志:\n{logs}")
            
            print("[控制层] 代码执行成功，未捕获到异常！")
            return logs
            
        except (docker.errors.ContainerError, RuntimeError, Exception) as e:
            error_msg = str(e)
            if "Read timed out" in error_msg or "timeout" in error_msg.lower():
                error_msg = f"沙箱执行超时（超过 {timeout_seconds} 秒），可能存在死循环或阻塞操作。"
                
            print(f"[控制层警告] 沙箱捕获到运行时错误/超时:\n{error_msg}")
            
            if container:
                try:
                    container.kill()
                except Exception:
                    pass
            
            if attempt == max_retries:
                return f"达到最大重试次数 ({max_retries})，任务终止。最后错误: \n{error_msg}"
            
            current_code = call_llm_to_fix_code(current_code, error_msg)
            
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
                    
            target_path = os.path.join(abs_current_path, script_filename)
            if os.path.exists(target_path):
                os.remove(target_path)
                
    return "未知状态终止。"

if __name__ == "__main__":
    infinite_loop_code = """
import time
print("开始执行死循环测试...")
while True:
    time.sleep(1)
"""
    result = run_code_in_sandbox_with_retry(infinite_loop_code, max_retries=2, timeout_seconds=5)
    print("\n--- 最终执行闭环结果 ---")
    print(result)