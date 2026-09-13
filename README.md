# 🛡️ Sentinel ReAct Engine

**A Lightweight, Production-Grade Agent Runtime Engine**
*Security Isolation · Self-Healing Retry · Long-term State Persistence*

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Sandbox](https://img.shields.io/badge/Sandbox-Docker%20%2B%20Fallback-orange) ![Storage](https://img.shields.io/badge/Storage-SQLite-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Why This Engine

Autonomous agents that execute LLM-generated code in production face three recurring problems:

- **Unsafe execution** — generated code can trigger destructive system calls (`os.system`, `eval`, etc.)
- **No fault tolerance** — if the execution environment (e.g. Docker) is unavailable, the task simply fails
- **Context loss** — long-running workflows lose all progress on crash or restart

This engine is a small, dependency-light core addressing all three, built to be dropped into any Python-based agent project.

## Architecture

| Component | File | What it actually does |
|---|---|---|
| **ReAct Loop** | `agent_core/react_agent.py` | `ProductionReActAgent.execute_task()` — runs a task, retries on failure up to `max_retries`, checkpoints state after every attempt |
| **Static AST Guard** | `ast_guard.py` | Parses code with Python's `ast` module before execution; blocks banned imports (`os`, `subprocess`, etc.) and high-risk calls (`eval`, `exec`, `os.system`) |
| **Sandbox Executor** | `sandbox_executor.py` | Checks Docker availability first (`docker info`); if available, runs code in a `--network none --memory 512m` isolated container; if not, transparently falls back to a local `subprocess` with a 5-second timeout |
| **Memory & Checkpointing** | `agent_core/memory.py` | `SQLiteMemoryStore` persists `{session_id, state_data, updated_at}` to SQLite via `INSERT OR REPLACE`, so a crashed session resumes exactly where it left off |

### Execution Flow

