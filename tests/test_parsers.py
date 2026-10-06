"""简历解析智能体和岗位描述解析智能体的基础测试。"""

from __future__ import annotations

import unittest

from agents.jd_parser import JDParserAgent
from agents.resume_parser import ResumeParserAgent


class FakeDeepSeekClient:
    """测试用客户端，不访问网络。"""

    def generate_json(self, system_prompt: str, user_prompt: str, **kwargs):
        if "教育背景" in user_prompt or "education" in user_prompt:
            return {
                "education": [],
                "projects": [],
                "skills": ["Python"],
                "experiences": [],
            }
        return {
            "job_title": "内容运营",
            "responsibilities": ["内容策划"],
            "requirements": ["具备沟通能力"],
            "keywords": ["内容运营", "沟通"],
        }


class ParserAgentTests(unittest.TestCase):
    def test_resume_parser_returns_structured_result(self) -> None:
        agent = ResumeParserAgent(llm_client=FakeDeepSeekClient())
        result = agent.run("教育背景：人工智能专业")
        self.assertIn("education", result)
        self.assertIn("skills", result)

    def test_jd_parser_returns_structured_result(self) -> None:
        agent = JDParserAgent(llm_client=FakeDeepSeekClient())
        result = agent.run("岗位职责：负责内容策划")
        self.assertEqual(result["job_title"], "内容运营")
        self.assertIn("responsibilities", result)
        self.assertIn("keywords", result)

    def test_empty_input_is_rejected(self) -> None:
        agent = ResumeParserAgent(llm_client=FakeDeepSeekClient())
        with self.assertRaises(ValueError):
            agent.run("   ")


if __name__ == "__main__":
    unittest.main()
