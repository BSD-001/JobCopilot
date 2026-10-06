"""检查通用简历表达，不导入个人知识库或专用提示词。"""

from __future__ import annotations

import json
import re
from typing import Any


PENDING_PATTERN = re.compile(r"[\[【]\s*待(?:补充|确认)[：:][^\]】]*[\]】]")
LABEL_PATTERN = re.compile(r"^【[\u4e00-\u9fff]{4}】")
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")


def normalize_pending_items(value: Any) -> list[str]:
    """兼容模型返回的文字或对象，完整保留待补充信息并按顺序去重。"""

    items = value if isinstance(value, list) else [value]
    normalized = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            item = "；".join(
                f"{key}：{json.dumps(content, ensure_ascii=False) if isinstance(content, (dict, list)) else content}"
                for key, content in item.items() if content is not None
            )
        elif isinstance(item, list):
            item = json.dumps(item, ensure_ascii=False)
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def check_experience_text(text: str) -> list[str]:
    """标明标签问题，不截断、不伪造或自动修补正文。"""

    warnings = []
    previous = None
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", line).strip()
        if not line:
            continue
        match = LABEL_PATTERN.match(line)
        if not match:
            warnings.append("经历要点缺少句首四字能力标签，请在投递前检查。")
            continue
        label = match.group()
        if label == previous:
            warnings.append(f"相邻经历重复使用{label}，请核对能力表述。")
        previous = label
    return list(dict.fromkeys(warnings))


def check_resume_text(text: str, source: str) -> list[str]:
    """拦截占位内容和来源中未出现的数字，语义事实仍需人工核验。"""

    warnings = []
    if PENDING_PATTERN.search(text):
        warnings.append("生成正文含待补充标记，已保留原文，请查看待补充信息。")
    unsupported = set(NUMBER_PATTERN.findall(text)) - set(NUMBER_PATTERN.findall(source))
    if unsupported:
        warnings.append("生成正文包含原材料未体现的数字，已保留原文，请核对事实。")
    return warnings
