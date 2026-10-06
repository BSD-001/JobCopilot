"""面试问题预测智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent


class InterviewAgent(StructuredAgent):
    """根据岗位要求和简历生成高频面试问题与参考回答。"""

    agent_name = "interview_agent"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        return super().run(input_data)
