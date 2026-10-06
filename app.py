"""JobCopilot 浏览器界面。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from openai import APITimeoutError, OpenAIError

from core.document_reader import read_document_bytes
from core.history_store import (
    build_report_filename,
    build_tailored_resume_filename,
    list_history_records,
    load_history_record,
    save_history_record,
)
from core.llm_client import DeepSeekClient
from main import OUTPUT_PATH, TAILORED_RESUME_PATH, run_pipeline_result


st.set_page_config(
    page_title="JobCopilot",
    page_icon="J",
    layout="wide",
)


def get_text_input(uploaded_file, pasted_text: str) -> str:
    """优先读取上传文件，否则使用用户粘贴的文字。"""

    if uploaded_file is not None:
        return read_document_bytes(
            content=uploaded_file.getvalue(),
            file_name=uploaded_file.name,
        )
    return pasted_text.strip()


def get_resume_input(uploaded_file, pasted_text: str):
    """返回简历文字和可选 Word 模板临时路径。"""

    if uploaded_file is None:
        return pasted_text.strip(), None

    content = uploaded_file.getvalue()
    text = read_document_bytes(content=content, file_name=uploaded_file.name)
    if Path(uploaded_file.name).suffix.lower() != ".docx":
        return text, None

    temporary_file = tempfile.NamedTemporaryFile(
        suffix=".docx",
        delete=False,
    )
    temporary_file.write(content)
    temporary_file.close()
    return text, Path(temporary_file.name)


st.title("JobCopilot 求职分析助手")
st.caption("上传简历和岗位描述，一键生成匹配分析、简历优化、面试题和学习计划。")

with st.sidebar:
    st.header("运行配置")
    api_key = st.text_input(
        "DeepSeek 应用程序密钥",
        value=os.getenv("DEEPSEEK_API_KEY", ""),
        type="password",
        help="不会写入项目文件，关闭本地服务后自动消失。",
    )
    allow_skill_boosting = st.checkbox(
        "补写未掌握的目标岗位技能",
        value=True,
        help=(
            "最多补写 3 项，只写入已有技能栏，并使用“了解、正在学习、"
            "可快速上手”等待补强表述。请在面试前补齐。"
        ),
    )
    st.info("支持文本、Markdown、PDF 和 Word 文档。")

    st.divider()
    st.subheader("历史分析")
    history_records = list_history_records()
    if history_records:
        history_ids = [record["record_id"] for record in history_records]
        history_labels = {
            record["record_id"]: record["label"] for record in history_records
        }
        preferred_history_id = st.session_state.get("jobcopilot_history_id")
        default_index = (
            history_ids.index(preferred_history_id)
            if preferred_history_id in history_ids
            else 0
        )
        selected_history_id = st.selectbox(
            "选择历史记录",
            options=history_ids,
            index=default_index,
            format_func=lambda record_id: history_labels.get(record_id, record_id),
        )
        if st.button("查看历史记录", use_container_width=True):
            try:
                history_record = load_history_record(selected_history_id)
            except (OSError, ValueError) as error:
                st.error(f"历史记录读取失败：{error}")
            else:
                st.session_state["jobcopilot_report"] = history_record["report_text"]
                st.session_state["jobcopilot_report_name"] = history_record.get(
                    "report_filename",
                    "JobCopilot-report.md",
                )
                resume_bytes = history_record.get("tailored_resume_bytes")
                if resume_bytes:
                    st.session_state["jobcopilot_tailored_resume"] = resume_bytes
                    st.session_state["jobcopilot_tailored_name"] = (
                        history_record.get("tailored_resume_filename")
                        or "岗位定制简历.docx"
                    )
                else:
                    st.session_state.pop("jobcopilot_tailored_resume", None)
                    st.session_state.pop("jobcopilot_tailored_name", None)
                st.session_state["jobcopilot_history_id"] = selected_history_id
                st.rerun()
    else:
        st.caption("暂无历史记录")

left_column, right_column = st.columns(2)

with left_column:
    st.subheader("一、简历")
    resume_file = st.file_uploader(
        "上传简历文件",
        type=["txt", "md", "pdf", "docx"],
        key="resume_file",
    )
    st.caption("上传 Word 简历可额外生成保留原模板的岗位定制简历。")
    resume_text = st.text_area(
        "或者直接粘贴简历文字",
        height=280,
        placeholder="在这里粘贴简历内容。",
    )

with right_column:
    st.subheader("二、岗位描述")
    job_description_file = st.file_uploader(
        "上传岗位描述文件",
        type=["txt", "md", "pdf", "docx"],
        key="job_description_file",
    )
    job_description_text = st.text_area(
        "或者直接粘贴岗位描述文字",
        height=280,
        placeholder="在这里粘贴目标岗位描述。",
    )

start_analysis = st.button(
    "开始分析",
    type="primary",
    use_container_width=True,
)

if start_analysis:
    history_saved = False
    try:
        if not api_key.strip():
            raise ValueError("请先填写 DeepSeek 应用程序密钥。")

        resolved_resume_text, resume_template_path = get_resume_input(
            resume_file,
            resume_text,
        )
        resolved_job_description_text = get_text_input(
            job_description_file,
            job_description_text,
        )
        if not resolved_resume_text:
            raise ValueError("请上传简历或粘贴简历内容。")
        if not resolved_job_description_text:
            raise ValueError("请上传岗位描述或粘贴岗位描述内容。")

        os.environ["DEEPSEEK_API_KEY"] = api_key.strip()
        tailored_path = Path(TAILORED_RESUME_PATH)
        tailored_path.unlink(missing_ok=True)
        with st.status("正在执行完整分析流程……", expanded=True) as status:
            st.write("解析简历和岗位描述")
            st.write("执行匹配分析和内容优化")
            st.write("生成面试问题、学习计划和最终报告")
            pipeline_result = run_pipeline_result(
                resume_text=resolved_resume_text,
                job_description_text=resolved_job_description_text,
                llm_client=DeepSeekClient(),
                resume_file_path=resume_template_path,
                tailored_resume_output=tailored_path,
                allow_skill_boosting=allow_skill_boosting,
            )
            report_text = pipeline_result.report_text
            output_path = Path(OUTPUT_PATH)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_text, encoding="utf-8")
            status.update(label="分析完成", state="complete")

        st.session_state["jobcopilot_report"] = report_text
        st.session_state["jobcopilot_report_name"] = build_report_filename(
            pipeline_result.job_title
        )
        if tailored_path.exists():
            st.session_state["jobcopilot_tailored_resume"] = tailored_path.read_bytes()
            st.session_state["jobcopilot_tailored_name"] = (
                build_tailored_resume_filename(pipeline_result.job_title)
            )
        else:
            st.session_state.pop("jobcopilot_tailored_resume", None)
            st.session_state.pop("jobcopilot_tailored_name", None)

        history_record = None
        try:
            history_record = save_history_record(
                job_title=pipeline_result.job_title,
                report_text=report_text,
                tailored_resume_path=(
                    tailored_path if tailored_path.exists() else None
                ),
            )
        except OSError as error:
            st.warning(f"历史记录保存失败：{error}")
        else:
            st.session_state["jobcopilot_history_id"] = history_record["record_id"]
            history_saved = True

        if resume_template_path:
            resume_template_path.unlink(missing_ok=True)
    except APITimeoutError:
        st.error("DeepSeek 响应超时。请稍后重试，或缩短简历和岗位描述后重试。")
    except OpenAIError as error:
        st.error(f"DeepSeek 请求失败：{error}")
    except (OSError, ValueError, RuntimeError) as error:
        st.error(f"运行失败：{error}")
    if history_saved:
        st.rerun()

if "jobcopilot_report" in st.session_state:
    st.divider()
    st.subheader("分析报告")
    report_text = st.session_state["jobcopilot_report"]
    st.download_button(
        "下载 Markdown 报告",
        data=report_text,
        file_name=st.session_state.get(
            "jobcopilot_report_name",
            "JobCopilot-report.md",
        ),
        mime="text/markdown",
        use_container_width=True,
    )
    if "jobcopilot_tailored_resume" in st.session_state:
        st.download_button(
            "下载岗位定制简历",
            data=st.session_state["jobcopilot_tailored_resume"],
            file_name=st.session_state.get(
                "jobcopilot_tailored_name",
                "岗位定制简历.docx",
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True,
        )
    st.markdown(report_text)
