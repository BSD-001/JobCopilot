"""简历解析智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent


class ResumeParserAgent(StructuredAgent):
    """从简历文本中提取教育、项目、技能和经历。"""

    agent_name = "resume_parser"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        return super().run(input_data)
