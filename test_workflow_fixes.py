import unittest
import os
from agent_core.react_agent import ProductionReActAgent

class TestWorkflowFixes(unittest.TestCase):
    def setUp(self):
        # 使用独立的测试 session，避免污染真实的 checkpoint 数据
        self.test_session = "test_workflow_session"
        self.test_db = "test_agent_state.db"

    def tearDown(self):
        # 清理测试过程中产生的临时数据库文件
        for suffix in ["", "-shm", "-wal"]:
            path = self.test_db + suffix
            if os.path.exists(path):
                os.remove(path)

    def test_react_agent_max_retries_circuit_breaker(self):
        """验证：当代码持续触发安全拦截时，达到最大重试次数后应正确熔断"""
        agent = ProductionReActAgent(session_id=self.test_session, max_retries=3)
        malicious_code = 'import os; os.system("ls")'

        res = agent.execute_task("test malicious task", malicious_code)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["retries"], 3)
        self.assertIn("Max retries (3) exceeded", res["error"])

    def test_react_agent_success_on_valid_code(self):
        """验证：合法代码应成功执行并记录到 checkpoint"""
        agent = ProductionReActAgent(session_id=self.test_session, max_retries=3)
        safe_code = 'print("Workflow sandbox active")'

        res = agent.execute_task("test safe task", safe_code)
        self.assertEqual(res["status"], "success")
        self.assertIn("Workflow sandbox active", res["result"])

if __name__ == '__main__':
    unittest.main()

