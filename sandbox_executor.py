import docker
import os

def run_code_in_sandbox(code_string: str) -> str:
    """
    通过挂载当前目录到一个用完即焚的容器实例中，安全执行大模型生成的代码。
    """
    confirm = input("\n[红队/安全卡点] Agent 即将在 Docker 沙箱中执行动态代码，是否允许？(y/n): ")
    if confirm.strip().lower() != 'y':
        return "执行已被用户人工终止。"

    client = docker.from_env()
    
    # 1. 将代码写入本地文件
    script_path = "temp_agent_script.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code_string)
        
    try:
        # 获取当前目录的绝对路径
        abs_current_path = os.path.abspath(".")
        
        # 2. 使用 run 方法：自动挂载当前目录到容器的 /workspace，执行完毕后自动删除容器 (--rm)
        container_output = client.containers.run(
            image="agent-sandbox",
            command=f"python /workspace/{script_path}",
            volumes={abs_current_path: {'bind': '/workspace', 'mode': 'rw'}},
            working_dir="/workspace",
            remove=True,
            stderr=True,
            stdout=True
        )
        
        return container_output.decode('utf-8')
        
    except docker.errors.ContainerError as ce:
        return f"代码运行报错 (Stderr): {ce.stderr.decode('utf-8') if ce.stderr else str(ce)}"
    except Exception as e:
        return f"沙箱执行发生底层错误: {str(e)}"
    finally:
        # 清理本地临时文件
        if os.path.exists(script_path):
            os.remove(script_path)

if __name__ == "__main__":
    test_code = """
import pandas as pd
df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
print("Pandas 运行正常，数据摘要：")
print(df.describe())
"""
    result = run_code_in_sandbox(test_code)
    print("\n--- 执行结果 ---")
    print(result)