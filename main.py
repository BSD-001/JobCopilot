"""JobCopilot 命令行入口。"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from openai import OpenAIError

from agents.greeting_agent import GreetingAgent
from agents.interview_agent import InterviewAgent
from agents.jd_parser import JDParserAgent
from agents.learning_plan import LearningPlanAgent
from agents.match_agent import MatchAgent
from agents.report_agent import ReportAgent
from agents.resume_optimizer import ResumeOptimizerAgent
from agents.resume_parser import ResumeParserAgent
from agents.tailored_resume_agent import TailoredResumeAgent
from core.document_reader import read_document
from core.llm_client import DeepSeekClient
from core.resume_template import apply_paragraph_replacements, extract_paragraph_blocks


OUTPUT_PATH = Path("output") / "report.md"
TAILORED_RESUME_PATH = Path("output") / "tailored_resume.docx"
GREETING_HEADING = "## 线上投递打招呼语"
_GREETING_SECTION_PATTERN = re.compile(
    rf"(?ms)^\s*{re.escape(GREETING_HEADING)}\s*$.*\Z"
)


@dataclass(frozen=True)
class PipelineResult:
    """一次完整流水线的页面所需结果。"""

    report_text: str
    job_title: str
    analysis_data: dict[str, Any] = field(default_factory=dict)


def run_pipeline(
    resume_text: str,
    job_description_text: str,
    llm_client: Any | None = None,
    resume_file_path: str | Path | None = None,
    tailored_resume_output: str | Path = TAILORED_RESUME_PATH,
    allow_skill_boosting: bool = True,
) -> str:
    """依次执行所有智能体，返回 Markdown 报告文本。"""

    return run_pipeline_result(
        resume_text=resume_text,
        job_description_text=job_description_text,
        llm_client=llm_client,
        resume_file_path=resume_file_path,
        tailored_resume_output=tailored_resume_output,
        allow_skill_boosting=allow_skill_boosting,
    ).report_text


def run_pipeline_result(
    resume_text: str,
    job_description_text: str,
    llm_client: Any | None = None,
    resume_file_path: str | Path | None = None,
    tailored_resume_output: str | Path = TAILORED_RESUME_PATH,
    allow_skill_boosting: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> PipelineResult:
    """依次执行所有智能体，返回报告和岗位名称。"""

    client = llm_client or DeepSeekClient()

    progress = on_progress or (lambda stage: None)
    progress("解析简历")
    resume_data = ResumeParserAgent(llm_client=client).run(resume_text)
    progress("解析目标岗位")
    job_description_data = JDParserAgent(llm_client=client).run(job_description_text)

    comparison_input = {
        "resume": resume_data,
        "job_description": job_description_data,
    }
    progress("分析匹配优势与差距")
    match_data = MatchAgent(llm_client=client).run(comparison_input)
    progress("优化简历表达")
    optimized_data = ResumeOptimizerAgent(llm_client=client).run(
        {**comparison_input, "source_resume_text": resume_text}
    )
    progress("生成面试问题")
    interview_data = InterviewAgent(llm_client=client).run(comparison_input)
    progress("安排30天学习计划")
    learning_plan_data = LearningPlanAgent(llm_client=client).run(
        {"missing_points": match_data.get("missing_points", [])}
    )

    tailored_resume_data = None
    resume_path = Path(resume_file_path) if resume_file_path else None
    if resume_path and resume_path.suffix.lower() == ".docx":
        progress("读取Word模板段落")
        resume_blocks = extract_paragraph_blocks(resume_path)
        progress("等待模型生成定制简历内容")
        tailored_resume_data = TailoredResumeAgent(llm_client=client).run(
            {
                "resume": resume_data,
                "job_description": job_description_data,
                "resume_blocks": resume_blocks,
                "missing_points": match_data.get("missing_points", []),
                "allow_skill_boosting": allow_skill_boosting,
            }
        )
        progress("将定制内容回填到Word模板")
        write_result = apply_paragraph_replacements(
            source_path=resume_path,
            output_path=tailored_resume_output,
            replacements=tailored_resume_data.get("replacements", []),
            removals=tailored_resume_data.get("removals", []),
        )
        tailored_resume_data["template_write_result"] = write_result
        tailored_resume_data["output_path"] = str(tailored_resume_output)

    progress("生成线上投递招呼语")
    greeting_data = GreetingAgent(llm_client=client).run(
        {
            "resume": resume_data,
            "job_description": job_description_data,
            "match": match_data,
            "tailored_resume": tailored_resume_data or optimized_data,
        }
    )

    progress("整理分析结果")
    report_data = {
        "resume": resume_data,
        "job_description": job_description_data,
        "match": match_data,
        "resume_optimization": optimized_data,
        "interview": interview_data,
        "learning_plan": learning_plan_data,
        "tailored_resume": tailored_resume_data,
        "hr_greeting": greeting_data.get("greeting", ""),
        "pending_items": list(dict.fromkeys(
            (optimized_data.get("pending_items") or [])
            + ((tailored_resume_data or {}).get("pending_items") or [])
        )),
        "writing_warnings": list(dict.fromkeys(
            (optimized_data.get("writing_warnings") or [])
            + ((tailored_resume_data or {}).get("writing_warnings") or [])
        )),
    }
    progress("汇总完整分析报告")
    report_text = ReportAgent(llm_client=client).run(report_data)
    report_text = _preserve_resume_advice(report_text, report_data)
    return PipelineResult(
        report_text=_replace_final_greeting(
            report_text,
            str(greeting_data.get("greeting", "")),
        ),
        job_title=str(job_description_data.get("job_title", "")).strip(),
        analysis_data=report_data,
    )


def _preserve_resume_advice(report_text: str, data: dict[str, Any]) -> str:
    """原样汇总经历建议，避免报告模型再次扩写事实和标签。"""

    report_text = _GREETING_SECTION_PATTERN.sub("", report_text).rstrip()
    sections = ["## 简历优化建议"]
    for project in data["resume_optimization"].get("optimized_projects", []):
        sections.append(f"### {project.get('title', '项目经历')}\n\n{project.get('content', '')}")
    tailored = data.get("tailored_resume") or {}
    for replacement in tailored.get("replacements", []):
        sections.append(f"- {replacement.get('new_text', '')}")
    if tailored.get("removals"):
        sections.append("### 建议删除的低相关内容\n" + "\n".join(
            f"- {item.get('original_text', '')}：{item.get('reason', '')}"
            for item in tailored["removals"]
        ))
    if tailored.get("skill_boosts"):
        sections.append("### 待补齐技能\n" + "\n".join(
            f"- {item.get('skill', '')}：{item.get('suggested_wording', '')}"
            for item in tailored["skill_boosts"]
        ))
    for title, key in (("待补充信息", "pending_items"), ("表达核对提醒", "writing_warnings")):
        if data.get(key):
            sections.append(f"### {title}\n" + "\n".join(f"- {item}" for item in data[key]))
    body = "\n\n".join(sections) + "\n\n"
    pattern = r"(?ms)^## [^\n]*简历优化[^\n]*\n.*?(?=^## |\Z)"
    if re.search(pattern, report_text):
        return re.sub(pattern, lambda match: body, report_text, count=1)
    return report_text.rstrip() + "\n\n" + body


def _replace_final_greeting(report_text: str, greeting: str) -> str:
    body = _GREETING_SECTION_PATTERN.sub("", report_text).rstrip()
    return f"{body}\n\n{GREETING_HEADING}\n\n{greeting.strip()}\n"


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="根据简历和目标岗位生成求职分析报告。"
    )
    parser.add_argument("--resume", required=True, help="简历文件路径")
    parser.add_argument("--jd", required=True, help="岗位描述文件路径")
    parser.add_argument(
        "--tailored-resume",
        default=str(TAILORED_RESUME_PATH),
        help="岗位定制简历输出路径，仅 Word 模板可用",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        resume_text = read_document(args.resume)
        job_description_text = read_document(args.jd)
        report_text = run_pipeline(
            resume_text=resume_text,
            job_description_text=job_description_text,
            resume_file_path=args.resume,
            tailored_resume_output=args.tailored_resume,
        )
    except (OSError, ValueError, RuntimeError, OpenAIError) as error:
        print(f"运行失败：{error}")
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report_text, encoding="utf-8")
    print(f"报告已生成：{OUTPUT_PATH}")
    tailored_path = Path(args.tailored_resume)
    if tailored_path.exists():
        print(f"岗位定制简历已生成：{tailored_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
