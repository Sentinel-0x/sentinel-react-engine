<a id="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

<br />
<div align="center">
  <h3 align="center">🛡️ Sentinel ReAct Engine</h3>

  <p align="center">
    A lightweight, production-grade agent runtime engine — AST security guard, fail-closed Docker sandbox, real-time security alerting, and SQLite state persistence.
    <br />
    <a href="https://github.com/Sentinel-0x/sentinel-react-engine"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Sentinel-0x/ai-intel-digest">See it in use</a>
    ·
    <a href="https://github.com/Sentinel-0x/sentinel-react-engine/issues/new?labels=bug">Report Bug</a>
    ·
    <a href="https://github.com/Sentinel-0x/sentinel-react-engine/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a>
      <ul><li><a href="#built-with">Built With</a></li></ul>
    </li>
    <li><a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

## About The Project

Autonomous agents that execute LLM-generated code in production face three recurring problems: **unsafe execution** (generated code can trigger destructive system calls), **no fault tolerance** (a single sandbox failure kills the whole task), and **context loss** (long-running workflows lose all progress on crash or restart).

Sentinel ReAct Engine is a small, dependency-light core addressing all three — built to be dropped into any Python-based agent project.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

* [![Python][Python-badge]][Python-url]
* [![Docker][Docker-badge]][Docker-url]
* [![SQLite][SQLite-badge]][SQLite-url]
* [![OpenAI][OpenAI-badge]][OpenAI-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

* Python 3.10+
* Docker (required — the engine refuses to execute code if Docker isn't available; there is no unsandboxed fallback)

### Installation

1. Clone the repo
```sh
   git clone https://github.com/Sentinel-0x/sentinel-react-engine.git
   cd sentinel-react-engine
```
2. Run the security test suite
```sh
   python3 test_rce.py
   python3 -m unittest test_workflow_fixes.py -v
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

```python
from agent_core.react_agent import ProductionReActAgent

agent = ProductionReActAgent(session_id="my_task", max_retries=3)
result = agent.execute_task(
    task_description="fetch and process data",
    code_to_run='print("hello from sandbox")'
)
print(result)
# {'status': 'success', 'result': 'hello from sandbox', 'retries': 0}
```

Every piece of code passes through `ast_guard.py` before execution — blocking banned imports (`os`, `subprocess`, `shutil`, `socket`) and high-risk calls (`eval()`, `exec()`, `os.system()`). Execution then runs in `sandbox_executor.py`: it checks Docker availability first and, if Docker is unavailable, refuses to execute rather than falling back to the host. When Docker is available, code runs with `--network none --memory 512m --cpus 1.0 --user 1000:1000` and a read-only mount; on timeout the container is actively killed.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Architecture

| Component | File | What it does |
|---|---|---|
| ReAct Loop | `agent_core/react_agent.py` | Runs a task, retries on failure up to `max_retries`, checkpoints state after every attempt |
| Static AST Guard | `ast_guard.py` | Parses code via `ast` before execution; blocks dangerous imports and calls |
| Sandbox Executor | `sandbox_executor.py` | Fail-closed Docker isolated execution, with execution/caller ID tracking |
| Memory & Checkpointing | `agent_core/memory.py` | `SQLiteMemoryStore` persists session state so crashed workflows resume exactly where they left off |
| Security Monitor | `security_monitor.py` | Persists AST-rejection history to SQLite and sends Telegram alerts on isolation failure or burst rejections from one caller |
| Networked Sandbox | `sandbox_executor.py`, `sandbox.dockerfile`, `proxy_config/` | Optional mode routing all egress through a Squid domain-whitelist proxy; image ships a fixed, pre-reviewed dependency set (no runtime `pip install`) |

State is stored via:
```sql
CREATE TABLE IF NOT EXISTS checkpoints (
    session_id TEXT PRIMARY KEY,
    state_data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [x] AST static security guard
- [x] Fail-closed Docker sandbox (no unsandboxed fallback)
- [x] SQLite session checkpointing
- [x] Self-healing retry loop
- [x] Active container kill on timeout
- [x] Execution ID and caller ID audit tracking
- [x] Persistent security monitoring with Telegram alerts
- [x] Whitelisted-network sandbox mode (Squid proxy)
- [x] CI: syntax check, unit tests, AST guard, whitelist and fail-closed verification
- [ ] LLM-driven auto code-repair on failure (see `experimental/agent_loop.py`)
- [ ] Authentication and rate limiting (`caller_id` is currently a self-reported label, not an authenticated identity)
- [ ] Adversarial testing (no container-escape or sustained-attack testing has been performed)
- [ ] Publish as an installable pip package

See the [open issues](https://github.com/Sentinel-0x/sentinel-react-engine/issues) for a full list of proposed features.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

Project Link: [https://github.com/Sentinel-0x/sentinel-react-engine](https://github.com/Sentinel-0x/sentinel-react-engine)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/Sentinel-0x/sentinel-react-engine.svg?style=for-the-badge
[contributors-url]: https://github.com/Sentinel-0x/sentinel-react-engine/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/Sentinel-0x/sentinel-react-engine.svg?style=for-the-badge
[forks-url]: https://github.com/Sentinel-0x/sentinel-react-engine/network/members
[stars-shield]: https://img.shields.io/github/stars/Sentinel-0x/sentinel-react-engine.svg?style=for-the-badge
[stars-url]: https://github.com/Sentinel-0x/sentinel-react-engine/stargazers
[issues-shield]: https://img.shields.io/github/issues/Sentinel-0x/sentinel-react-engine.svg?style=for-the-badge
[issues-url]: https://github.com/Sentinel-0x/sentinel-react-engine/issues
[license-shield]: https://img.shields.io/github/license/Sentinel-0x/sentinel-react-engine.svg?style=for-the-badge
[license-url]: https://github.com/Sentinel-0x/sentinel-react-engine/blob/main/LICENSE
[Python-badge]: https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[Docker-badge]: https://img.shields.io/badge/Docker-sandboxed-2496ED?style=for-the-badge&logo=docker&logoColor=white
[Docker-url]: https://www.docker.com/
[SQLite-badge]: https://img.shields.io/badge/SQLite-checkpointing-003B57?style=for-the-badge&logo=sqlite&logoColor=white
[SQLite-url]: https://www.sqlite.org/
[OpenAI-badge]: https://img.shields.io/badge/LLM-DeepSeek--V3-412991?style=for-the-badge&logo=openai&logoColor=white
[OpenAI-url]: https://www.deepseek.com/

