"""简历与岗位描述匹配分析智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent


class MatchAgent(StructuredAgent):
    """计算匹配度，并给出匹配点和缺失点。"""

    agent_name = "match_agent"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        return super().run(input_data)
