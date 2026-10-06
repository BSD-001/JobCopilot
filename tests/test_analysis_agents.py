"""匹配分析智能体和简历优化智能体的基础测试。"""

from __future__ import annotations

import unittest

from agents.match_agent import MatchAgent
from agents.resume_optimizer import ResumeOptimizerAgent


class FakeDeepSeekClient:
    def generate_json(self, system_prompt: str, user_prompt: str, **kwargs):
        if "匹配度评分" in user_prompt:
            return {
                "score": 82,
                "matched_points": ["具备内容策划经历"],
                "missing_points": ["缺少数据分析项目"],
                "reason": "整体方向匹配，但数据能力证据不足。",
            }
        return {
            "optimized_projects": [
                {"title": "项目一", "content": "优化后的项目描述一"},
                {"title": "项目二", "content": "优化后的项目描述二"},
                {"title": "项目三", "content": "优化后的项目描述三"},
            ]
        }


class AnalysisAgentTests(unittest.TestCase):
    def test_match_agent_returns_score_and_gaps(self) -> None:
        agent = MatchAgent(llm_client=FakeDeepSeekClient())
        result = agent.run({"resume": {}, "job_description": {}})
        self.assertEqual(result["score"], 82)
        self.assertIn("missing_points", result)

    def test_resume_optimizer_returns_three_projects(self) -> None:
        agent = ResumeOptimizerAgent(llm_client=FakeDeepSeekClient())
        result = agent.run({"resume": {}, "job_description": {}})
        self.assertEqual(len(result["optimized_projects"]), 3)


if __name__ == "__main__":
    unittest.main()
