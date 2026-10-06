"""三十天学习计划智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent


class LearningPlanAgent(StructuredAgent):
    """根据缺失技能生成按周拆解的学习计划。"""

    agent_name = "learning_plan"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        return super().run(input_data)
