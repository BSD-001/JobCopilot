"""JobCopilot 本地网页接口，复用现有分析流水线。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
import sys
import traceback
from typing import Callable
from urllib.parse import quote
from uuid import uuid4

import bleach
import markdown
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import APITimeoutError, OpenAIError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.document_reader import SUPPORTED_SUFFIXES, read_document_bytes
from core.history_store import (
    build_report_filename,
    build_tailored_resume_filename,
    delete_history_record,
    list_history_records,
    load_history_record,
    save_history_record,
)
from core.llm_client import DeepSeekClient
from core.resume_writing import PENDING_PATTERN
from core.runtime_paths import default_history_root
from main import run_pipeline_result


PROJECT_ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)
MAX_UPLOAD_SIZE = 200 * 1024 * 1024
HTML_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em",
    "ul", "ol", "li", "blockquote", "pre", "code", "table", "thead", "tbody",
    "tr", "th", "td", "a",
}


def report_html(text: str) -> str:
    """仅保留报告排版标签，阻止上传材料中的脚本或危险链接。"""

    html = markdown.markdown(text, extensions=["tables", "fenced_code"])
    return bleach.clean(html, tags=HTML_TAGS, attributes={"a": ["href", "title"]}, strip=True)


def record_payload(record: dict) -> dict:
    """移除不可序列化的文件内容，统一新旧结果的页面接口。"""

    analysis = record.get("analysis_data")
    return {
        "status": "completed",
        "record_id": record.get("record_id"),
        "created_at": record.get("created_at", ""),
        "job_title": record.get("job_title", "目标岗位"),
        "report_text": record.get("report_text", ""),
        "report_html": report_html(record.get("report_text", "")),
        "analysis_data": analysis,
        "has_tailored_resume": bool(record.get("tailored_resume_bytes")),
        "warnings": (analysis or {}).get("writing_warnings", []),
    }


def download_response(content: bytes, filename: str, kind: str) -> Response:
    media_type = (
        "text/markdown; charset=utf-8" if kind == "report" else
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "no-store",
    })


async def read_upload(upload: UploadFile) -> bytes:
    """分块读取并校验文件大小，不能只相信浏览器端限制。"""

    try:
        if Path(upload.filename or "").suffix.lower() not in SUPPORTED_SUFFIXES:
            raise HTTPException(400, "支持TXT、MD、PDF和DOCX文件。")
        chunks = []
        size = 0
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                raise HTTPException(413, "单个文件不能超过200MB。")
            chunks.append(chunk)
        if not size:
            raise HTTPException(400, "文件为空，请重新选择。")
        return b"".join(chunks)
    finally:
        await upload.close()


def create_app(
    history_root: str | Path | None = None,
    client_factory: Callable = DeepSeekClient,
) -> FastAPI:
    """可注入模拟客户端和临时历史目录，测试不访问真实AI接口。"""

    app = FastAPI(title="JobCopilot", docs_url=None, redoc_url=None)
    root = Path(default_history_root() if history_root is None else history_root).resolve()
    jobs = {}
    lock = Lock()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jobcopilot")
    app.state.jobs = jobs
    app.state.active_job = None
    app.state.executor = executor
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        port = request.url.port or 80
        allowed = {f"http://localhost:{port}", f"http://127.0.0.1:{port}", "http://testserver"}
        if origin and origin not in allowed and request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "仅允许本地网页访问此接口。"}, status_code=403)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_job(job_id: str) -> dict:
        with lock:
            if job_id not in jobs:
                raise HTTPException(404, "任务不存在或服务已重启，请查看历史记录或重新分析。")
            return deepcopy(jobs[job_id])

    def get_record(record_id: str) -> dict:
        try:
            return load_history_record(record_id, history_root=root)
        except FileNotFoundError:
            raise HTTPException(404, "历史记录不存在，可能已删除。") from None
        except ValueError:
            raise HTTPException(400, "历史记录编号或数据无效。") from None
        except OSError:
            raise HTTPException(500, "无法读取历史文件，请检查本地存储。") from None

    def record_failure(job_id: str, error: Exception, message: str):
        """只记录异常类型、阶段和代码位置，不记录异常正文、Key或局部变量。"""

        with lock:
            stage = jobs[job_id].get("stage", "准备分析")
        details = {
            "stage": stage,
            "exception_type": type(error).__name__,
            "frames": [
                {"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                for frame in traceback.extract_tb(error.__traceback__)
            ],
        }
        LOGGER.error("任务%s失败；阶段=%s；异常类型=%s；代码位置=%s", job_id, stage, details["exception_type"], details["frames"])
        with lock:
            jobs[job_id].update(
                status="failed", error=f"{message} 失败阶段：{stage}；错误类型：{details['exception_type']}。",
                error_details=details,
            )

    def run_analysis(job_id: str, api_key: str, inputs: dict, allow_skill_boosting: bool):
        def progress(stage: str):
            with lock:
                jobs[job_id]["stage"] = stage

        try:
            with lock:
                jobs[job_id]["status"] = "running"
            with TemporaryDirectory(prefix="jobcopilot-") as temporary:
                directory = Path(temporary)
                progress("读取并检查输入材料")
                texts = {}
                resume_path = None
                for kind, item in inputs.items():
                    text = read_document_bytes(item["content"], item["filename"]) if item.get("content") is not None else item["text"]
                    if not text.strip():
                        raise ValueError(f"{'简历' if kind == 'resume' else '岗位描述'}未读取到文字。扫描型PDF需先转为可复制文字。")
                    texts[kind] = text
                    if kind == "resume" and Path(item.get("filename", "")).suffix.lower() == ".docx":
                        resume_path = directory / "resume.docx"
                        resume_path.write_bytes(item["content"])
                tailored_path = directory / "tailored_resume.docx"
                result = run_pipeline_result(
                    resume_text=texts["resume"], job_description_text=texts["jd"],
                    llm_client=client_factory(api_key=api_key), resume_file_path=resume_path,
                    tailored_resume_output=tailored_path,
                    allow_skill_boosting=allow_skill_boosting, on_progress=progress,
                )
                resume_bytes = tailored_path.read_bytes() if tailored_path.exists() else None
                warnings = list(result.analysis_data.get("writing_warnings", []))
                if resume_bytes and PENDING_PATTERN.search(read_document_bytes(resume_bytes, "tailored_resume.docx")):
                    resume_bytes = None
                    warnings.append("原简历仍含待补充标记，暂不提供定制下载。请补齐原文件后重新分析。")
                    result.analysis_data.setdefault("writing_warnings", []).append(warnings[-1])
                progress("保存本地历史记录")
                metadata = {}
                try:
                    metadata = save_history_record(
                        result.job_title, result.report_text,
                        tailored_resume_path=tailored_path if resume_bytes else None,
                        history_root=root, analysis_data=result.analysis_data,
                    )
                except OSError:
                    warnings.append("历史记录保存失败，当前结果仍可查看和下载。请检查本地文件权限或磁盘空间。")
                payload = {
                    "status": "completed", "stage": "分析完成",
                    "job_title": result.job_title or "目标岗位",
                    "record_id": metadata.get("record_id"), "created_at": metadata.get("created_at", ""),
                    "report_text": result.report_text, "report_html": report_html(result.report_text),
                    "analysis_data": result.analysis_data, "has_tailored_resume": bool(resume_bytes),
                    "warnings": warnings,
                }
                with lock:
                    jobs[job_id].update(payload)
                    jobs[job_id]["resume_bytes"] = resume_bytes
        except APITimeoutError as error:
            record_failure(job_id, error, "DeepSeek响应超时，请稍后重试，或缩短输入材料。")
        except OpenAIError as error:
            record_failure(job_id, error, "DeepSeek请求失败，请检查Key、账户额度和网络后重试。")
        except (ValueError, OSError, RuntimeError) as error:
            message = str(error) if isinstance(error, ValueError) else "读取材料或生成文件失败，请检查文件后重试。"
            message = message.replace(api_key, "[已隐藏]")
            record_failure(job_id, error, message)
        except Exception as error:
            record_failure(job_id, error, "分析内部处理失败，请重试；若仍失败，请提供任务链接排查。")
        finally:
            with lock:
                app.state.active_job = None

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(PROJECT_ROOT / "web" / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "application": "JobCopilot", "windows_package": bool(getattr(sys, "frozen", False))}

    @app.post("/api/analyses", status_code=202)
    async def start_analysis(
        api_key: str = Form(""), allow_skill_boosting: bool = Form(True),
        resume_mode: str = Form("file"), jd_mode: str = Form("text"),
        resume_text: str = Form(""), jd_text: str = Form(""),
        resume_file: UploadFile | None = File(None), jd_file: UploadFile | None = File(None),
    ):
        if not api_key.strip():
            raise HTTPException(400, "请填写DeepSeek API Key。")
        with lock:
            if app.state.active_job:
                raise HTTPException(409, "已有分析正在执行，请等待完成后再提交。")
        inputs = {}
        for kind, mode, text, upload in (
            ("resume", resume_mode, resume_text, resume_file),
            ("jd", jd_mode, jd_text, jd_file),
        ):
            label = "简历" if kind == "resume" else "岗位描述"
            if mode == "file":
                if not upload:
                    raise HTTPException(400, f"请选择{label}文件。")
                filename = upload.filename or ""
                inputs[kind] = {"filename": filename, "content": await read_upload(upload)}
            elif mode == "text":
                if not text.strip():
                    raise HTTPException(400, f"请粘贴{label}文字。")
                inputs[kind] = {"text": text.strip()}
                if upload:
                    await upload.close()
            else:
                raise HTTPException(400, "请选择有效的输入方式。")
        with lock:
            if app.state.active_job:
                raise HTTPException(409, "已有分析正在执行，请等待完成后再提交。")
            for old_id in list(jobs)[:-19]:
                if old_id != app.state.active_job:
                    del jobs[old_id]
            job_id = str(uuid4())
            jobs[job_id] = {"status": "queued", "stage": "准备分析", "warnings": []}
            app.state.active_job = job_id
        executor.submit(run_analysis, job_id, api_key.strip(), inputs, allow_skill_boosting)
        return {"job_id": job_id}

    @app.get("/api/analyses/{job_id}")
    def analysis_status(job_id: str):
        job = get_job(job_id)
        job.pop("resume_bytes", None)
        return job

    @app.get("/api/history")
    def history():
        try:
            return list_history_records(root)
        except OSError:
            raise HTTPException(500, "无法读取历史列表，请检查本地存储。") from None

    @app.get("/api/history/{record_id}")
    def history_detail(record_id: str):
        return record_payload(get_record(record_id))

    @app.delete("/api/history/{record_id}")
    def delete_record(record_id: str):
        get_record(record_id)
        try:
            delete_history_record(record_id, history_root=root)
        except (ValueError, OSError):
            raise HTTPException(500, "删除失败，请检查文件是否被其他程序占用。") from None
        with lock:
            for job_id, job in list(jobs.items()):
                if job.get("record_id") == record_id:
                    del jobs[job_id]
        return {"deleted": True}

    @app.get("/api/analyses/{job_id}/downloads/{kind}")
    def download_analysis(job_id: str, kind: str):
        job = get_job(job_id)
        if job["status"] != "completed":
            raise HTTPException(409, "分析尚未完成，暂不能下载。")
        if kind == "report":
            return download_response(job["report_text"].encode("utf-8"), build_report_filename(job["job_title"]), kind)
        if kind == "resume" and job.get("resume_bytes"):
            return download_response(job["resume_bytes"], build_tailored_resume_filename(job["job_title"]), kind)
        raise HTTPException(404, "本次未生成该文件。")

    @app.get("/api/history/{record_id}/downloads/{kind}")
    def download_history(record_id: str, kind: str):
        record = get_record(record_id)
        if kind == "report":
            return download_response(record["report_text"].encode("utf-8"), build_report_filename(record["job_title"]), kind)
        if kind == "resume" and record.get("tailored_resume_bytes"):
            return download_response(record["tailored_resume_bytes"], build_tailored_resume_filename(record["job_title"]), kind)
        raise HTTPException(404, "该记录未包含定制简历。")

    app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "web"), name="static")
    return app


app = create_app()
