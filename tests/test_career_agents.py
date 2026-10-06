"""面试预测智能体和学习计划智能体的基础测试。"""

from __future__ import annotations

import unittest

from agents.interview_agent import InterviewAgent
from agents.learning_plan import LearningPlanAgent


class FakeDeepSeekClient:
    def generate_json(self, system_prompt: str, user_prompt: str, **kwargs):
        if "面试问题" in user_prompt:
            return {
                "questions": [
                    {
                        "question": f"面试问题 {index}",
                        "answer": "参考回答",
                        "focus": "岗位匹配",
                    }
                    for index in range(1, 11)
                ]
            }
        return {
            "weeks": [
                {
                    "week": week,
                    "goal": f"第 {week} 周目标",
                    "tasks": ["学习任务一", "学习任务二"],
                    "deliverable": "学习成果",
                }
                for week in range(1, 5)
            ],
            "summary": "完成三十天学习计划。",
        }


class CareerAgentTests(unittest.TestCase):
    def test_interview_agent_returns_ten_questions(self) -> None:
        agent = InterviewAgent(llm_client=FakeDeepSeekClient())
        result = agent.run({"resume": {}, "job_description": {}})
        self.assertEqual(len(result["questions"]), 10)

    def test_learning_plan_returns_four_weeks(self) -> None:
        agent = LearningPlanAgent(llm_client=FakeDeepSeekClient())
        result = agent.run({"missing_points": ["数据分析"]})
        self.assertEqual(len(result["weeks"]), 4)


if __name__ == "__main__":
    unittest.main()
