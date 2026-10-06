"""结构化智能体的公共基类。"""

from __future__ import annotations

from typing import Any

from core.llm_client import DeepSeekClient
from core.prompt_templates import STRUCTURED_OUTPUT_SYSTEM_PROMPT, build_json_prompt


class StructuredAgent:
    """负责把输入交给大模型，并要求返回结构化对象。"""

    agent_name: str = ""

    def __init__(self, llm_client: DeepSeekClient | None = None) -> None:
        if not self.agent_name:
            raise ValueError("智能体必须定义 agent_name。")
        self.llm_client = llm_client or DeepSeekClient()

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        """执行智能体任务并返回结构化对象。"""

        if isinstance(input_data, str) and not input_data.strip():
            raise ValueError("输入内容不能为空。")

        prompt = build_json_prompt(self.agent_name, input_data)
        return self.llm_client.generate_json(
            system_prompt=STRUCTURED_OUTPUT_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
