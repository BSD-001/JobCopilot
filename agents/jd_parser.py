"""岗位描述解析智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent


class JDParserAgent(StructuredAgent):
    """从岗位描述中提取职责、要求和关键词。"""

    agent_name = "jd_parser"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        return super().run(input_data)
