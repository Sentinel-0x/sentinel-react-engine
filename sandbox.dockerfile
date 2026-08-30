FROM python:3.10-slim
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN pip install --no-cache-dir requests pandas beautifulsoup4
CMD ["tail", "-f", "/dev/null"]