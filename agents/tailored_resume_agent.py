"""岗位定制简历智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent
from core.resume_writing import check_experience_text, check_resume_text, normalize_pending_items


class TailoredResumeAgent(StructuredAgent):
    """根据岗位描述定向调整简历段落。"""

    agent_name = "tailored_resume_agent"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        result = super().run(input_data)

        allow_skill_boosting = (
            not isinstance(input_data, dict)
            or input_data.get("allow_skill_boosting", True)
        )
        warnings = []
        raw_boosts = result.get("skill_boosts") or []
        skill_boosts = []
        for item in raw_boosts[:3] if allow_skill_boosting else []:
            wording = str(item.get("suggested_wording", ""))
            if not any(word in wording for word in ("正在学习", "计划学习", "待补齐")) or any(
                word in wording for word in ("熟练", "精通", "已掌握", "实战经验")
            ):
                warnings.append("技能补强未使用待学习表述，已忽略该项，请投递前核对。")
            else:
                skill_boosts.append(item)
        result["skill_boosts"] = skill_boosts

        removals = result.get("removals")
        if isinstance(removals, list):
            result["removals"] = removals[:5]

        pending = normalize_pending_items(result.get("pending_items"))
        replacements = []
        source = "\n".join(
            str(block.get("text", "")) for block in input_data.get("resume_blocks", [])
        ) if isinstance(input_data, dict) else ""
        for replacement in result.get("replacements") or []:
            text = str(replacement.get("new_text", ""))
            problems = check_resume_text(text, source)
            for boost in raw_boosts:
                skill = str(boost.get("skill", "")).strip()
                if skill and skill not in source and skill in text and (
                    boost not in skill_boosts or str(boost.get("suggested_wording", "")) not in text
                ):
                    problems.append("段落补写了未启用或未按待学习表述标注的技能，已保留原文。")
            if replacement.get("kind") == "experience":
                problems.extend(check_experience_text(text))
            if problems:
                warnings.extend(problems)
                pending.append(f"段落{replacement.get('block_id', '')}：建议需核对，定制简历保留原文。")
            else:
                replacements.append(replacement)
        result["replacements"] = replacements
        result["pending_items"] = pending
        result["writing_warnings"] = list(dict.fromkeys(warnings))
        return result
