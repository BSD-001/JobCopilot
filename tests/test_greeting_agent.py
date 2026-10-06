"""线上投递打招呼语智能体测试。"""

from __future__ import annotations

import unittest

from agents.greeting_agent import GreetingAgent, MAX_GREETING_CHARACTERS


class FakeDeepSeekClient:
    def __init__(self, greeting: str) -> None:
        self.greeting = greeting

    def generate_json(self, system_prompt: str, user_prompt: str, **kwargs):
        return {"greeting": self.greeting}


class GreetingAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.input_data = {
            "job_description": {
                "job_title": "AI产品运营",
                "keywords": ["内容运营", "AI工具"],
            },
            "match": {
                "matched_points": ["活动策划", "AI内容生产"],
            },
            "tailored_resume": {
                "target_keywords": ["内容运营"],
            },
        }

    def test_returns_short_greeting(self) -> None:
        greeting = "您好，我应聘AI产品运营。我有活动策划和AI内容生产经验，方便看下简历吗？"
        agent = GreetingAgent(llm_client=FakeDeepSeekClient(greeting))

        result = agent.run(self.input_data)

        self.assertEqual(result["greeting"], greeting)
        self.assertLessEqual(
            len(result["greeting"].replace(" ", "")),
            MAX_GREETING_CHARACTERS,
        )

    def test_shortens_overlong_greeting(self) -> None:
        greeting = (
            "您好，我应聘AI产品运营，有活动策划和AI内容生产经验。"
            "方便看下简历吗？我非常期待能够加入贵公司，"
            "希望有机会进一步沟通，也期待您的回复。"
        )
        agent = GreetingAgent(llm_client=FakeDeepSeekClient(greeting))

        result = agent.run(self.input_data)

        self.assertLessEqual(
            len(result["greeting"].replace(" ", "")),
            MAX_GREETING_CHARACTERS,
        )
        self.assertNotIn("非常期待", result["greeting"])
        self.assertIn("AI产品运营", result["greeting"])

    def test_builds_fallback_when_greeting_is_empty(self) -> None:
        agent = GreetingAgent(llm_client=FakeDeepSeekClient(""))

        result = agent.run(self.input_data)

        self.assertIn("AI产品运营", result["greeting"])
        self.assertIn("活动策划", result["greeting"])
        self.assertIn("方便看下简历吗", result["greeting"])
        self.assertLessEqual(
            len(result["greeting"].replace(" ", "")),
            MAX_GREETING_CHARACTERS,
        )


if __name__ == "__main__":
    unittest.main()
