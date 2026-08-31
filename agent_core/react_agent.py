import time
from agent_core.memory import SQLiteMemoryStore
from sandbox_executor import run_code_in_sandbox

class ProductionReActAgent:
    def __init__(self, session_id: str = "default_session", max_retries: int = 3):
        self.session_id = session_id
        self.max_retries = max_retries
        self.memory = SQLiteMemoryStore()
        self.state = self.memory.load_checkpoint(self.session_id)
        if not self.state:
            self.state = {"step": 0, "history": []}

    def execute_task(self, task_description: str, code_to_run: str):
        retries = 0
        last_error = None

        print(f"[Agent] Starting task for session: {self.session_id}")
        
        while retries < self.max_retries:
            try:
                result = run_code_in_sandbox(code_to_run)
                if "Error" in result or "Rejected" in result:
                    raise RuntimeError(result)

                self.state["step"] += 1
                self.state["history"].append({"task": task_description, "status": "success", "result": result})
                self.memory.save_checkpoint(self.session_id, self.state)
                return {"status": "success", "result": result, "retries": retries}

            except Exception as e:
                retries += 1
                last_error = str(e)
                print(f"[ReAct Warning] Attempt {retries} failed: {last_error}. Self-healing & retrying...")

        self.state["history"].append({"task": task_description, "status": "failed", "error": last_error})
        self.memory.save_checkpoint(self.session_id, self.state)
        return {
            "status": "failed",
            "retries": retries,
            "error": f"Max retries ({self.max_retries}) exceeded. Loop forcefully terminated to protect tokens."
        }
