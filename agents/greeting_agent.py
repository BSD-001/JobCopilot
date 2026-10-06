"""生成简短的线上投递打招呼语。"""

from __future__ import annotations

import re
from typing import Any

from agents.base import StructuredAgent


MAX_GREETING_CHARACTERS = 65
MAX_FALLBACK_TERM_CHARACTERS = 14
BANNED_GREETING_FRAGMENTS = (
    "非常期待",
    "深感荣幸",
    "贵公司",
    "希望有机会",
    "期待您的回复",
)


class GreetingAgent(StructuredAgent):
    """根据岗位要求、匹配点和定制简历生成短招呼语。"""

    agent_name = "greeting_agent"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        result = super().run(input_data)
        greeting = _normalize(str(result.get("greeting", "")))

        if not greeting:
            greeting = _build_fallback(input_data)
        elif (
            _character_count(greeting) > MAX_GREETING_CHARACTERS
            or any(fragment in greeting for fragment in BANNED_GREETING_FRAGMENTS)
        ):
            shortened = _first_two_sentences(greeting)
            greeting = (
                shortened
                if shortened
                and _character_count(shortened) <= MAX_GREETING_CHARACTERS
                and not any(
                    fragment in shortened for fragment in BANNED_GREETING_FRAGMENTS
                )
                else _build_fallback(input_data)
            )

        result["greeting"] = greeting
        return result


def _build_fallback(input_data: str | dict[str, Any]) -> str:
    if not isinstance(input_data, dict):
        return "您好，我的经历与岗位需求匹配，方便看下简历吗？"

    job_description = _as_dict(input_data.get("job_description"))
    match = _as_dict(input_data.get("match"))
    tailored_resume = _as_dict(input_data.get("tailored_resume"))

    title = _shorten(
        str(job_description.get("job_title", "")),
        MAX_FALLBACK_TERM_CHARACTERS,
    ) or "目标岗位"
    related_points = (
        match.get("matched_points")
        or tailored_resume.get("target_keywords")
        or job_description.get("keywords")
        or []
    )
    if not isinstance(related_points, list):
        related_points = []

    points = [
        _shorten(str(point), MAX_FALLBACK_TERM_CHARACTERS)
        for point in related_points[:2]
        if str(point).strip()
    ]
    if points:
        greeting = (
            f"您好，我应聘{title}。我具备{'、'.join(points)}相关经验，"
            "方便看下简历吗？"
        )
        if _character_count(greeting) <= MAX_GREETING_CHARACTERS:
            return greeting

    return f"您好，我应聘{title}。我的经历与岗位需求匹配，方便看下简历吗？"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _first_two_sentences(text: str) -> str:
    sentences: list[str] = []
    current: list[str] = []
    for character in text:
        current.append(character)
        if character in "。！？!?":
            sentences.append("".join(current).strip())
            current = []
            if len(sentences) == 2:
                break
    if current and len(sentences) < 2:
        sentences.append("".join(current).strip())
    return "".join(sentences).strip()


def _shorten(text: str, max_characters: int) -> str:
    normalized = _normalize(text)
    if len(normalized) <= max_characters:
        return normalized
    return normalized[:max_characters].rstrip("，,、；;：: ")
