"""针对目标岗位优化项目经历的智能体。"""

from __future__ import annotations

from typing import Any

from agents.base import StructuredAgent
from core.resume_writing import check_experience_text, check_resume_text, normalize_pending_items


class ResumeOptimizerAgent(StructuredAgent):
    """根据岗位要求重写项目经历描述。"""

    agent_name = "resume_optimizer"

    def run(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        result = super().run(input_data)
        warnings = []
        source = input_data.get("source_resume_text") if isinstance(input_data, dict) else None
        projects = []
        pending = normalize_pending_items(result.get("pending_items"))
        for project in result.get("optimized_projects") or []:
            content = str(project.get("content", ""))
            warnings.extend(check_experience_text(content))
            problems = check_resume_text(content, source) if source is not None else []
            if problems:
                warnings.extend(problems)
                pending.append(f"{project.get('title', '项目')}：生成表达需核对，未采用该条建议。")
            else:
                projects.append(project)
        result["optimized_projects"] = projects
        result["pending_items"] = pending
        result["writing_warnings"] = list(dict.fromkeys(warnings))
        return result
