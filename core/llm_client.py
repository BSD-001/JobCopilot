"""DeepSeek 大模型调用客户端。"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekClient:
    """封装 DeepSeek 的文本生成与结构化结果生成能力。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 90.0,
        max_retries: int = 2,
    ) -> None:
        resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "没有找到 DeepSeek 应用程序密钥。请先设置环境变量 "
                "DEEPSEEK_API_KEY。"
            )

        self.model = model
        self.client = OpenAI(
            api_key=resolved_api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 3000,
    ) -> str:
        """调用大模型并返回纯文本结果。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("大模型返回了空内容。")
        return content.strip()

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        max_parse_retries: int = 2,
    ) -> dict[str, Any]:
        """要求大模型返回结构化数据，并在解析失败时重新请求。"""

        current_prompt = user_prompt
        last_error: Exception | None = None

        for attempt in range(max_parse_retries + 1):
            raw_text = self.generate_text(
                system_prompt=system_prompt,
                user_prompt=current_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                json_text = _extract_json_object(raw_text)
                parsed = json.loads(json_text)
                if not isinstance(parsed, dict):
                    raise ValueError("顶层结果必须是包含字段的结构化对象。")
                return parsed
            except (ValueError, json.JSONDecodeError) as error:
                last_error = error
                if attempt >= max_parse_retries:
                    break
                current_prompt = (
                    user_prompt
                    + "\n\n上一次回答无法被解析。请只返回一个合法的结构化对象，"
                    "不要添加解释、标题或代码围栏。"
                )

        raise ValueError(
            f"连续 {max_parse_retries + 1} 次没有得到可解析的结构化结果："
            f"{last_error}"
        )


def _extract_json_object(text: str) -> str:
    """从模型回答中提取第一个完整的花括号对象文本。"""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("模型回答中没有找到完整的花括号对象。")
    return cleaned[start : end + 1]
