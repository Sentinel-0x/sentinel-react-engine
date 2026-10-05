# 联网沙箱专用镜像：预装经审核的固定依赖清单，供 run_code_in_sandbox_with_network 使用。
# Agent 代码本身不允许动态 pip install（subprocess 被 AST guard 完全禁止），
# 所有可用的第三方库必须在此文件中预先声明、人工审核后再构建镜像。
FROM python:3.10-slim
RUN pip install --no-cache-dir requests pandas beautifulsoup4
