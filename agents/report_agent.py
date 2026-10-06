"""最终报告生成智能体。"""

from __future__ import annotations

from typing import Any

from core.llm_client import DeepSeekClient
from core.prompt_templates import REPORT_SYSTEM_PROMPT, build_report_prompt


class ReportAgent:
    """汇总结构化分析结果并生成 Markdown 报告。"""

    def __init__(self, llm_client: DeepSeekClient | None = None) -> None:
        self.llm_client = llm_client or DeepSeekClient()

    def run(self, input_data: dict[str, Any]) -> str:
        if not input_data:
            raise ValueError("报告输入不能为空。")
        return self.llm_client.generate_text(
            system_prompt=REPORT_SYSTEM_PROMPT,
            user_prompt=build_report_prompt(input_data),
            temperature=0.2,
            max_tokens=6000,
        )
