"""保存和读取浏览器端的历史分析记录。"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


HISTORY_ROOT = Path("output") / "history"
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RECORD_ID_PATTERN = re.compile(r"\d{8}-\d{6}-\d{6}")
_MAX_FILENAME_COMPONENT_LENGTH = 60


def build_tailored_resume_filename(job_title: str) -> str:
    return f"{_build_job_filename_prefix(job_title)}-定制简历.docx"


def build_report_filename(job_title: str) -> str:
    return f"{_build_job_filename_prefix(job_title)}-求职分析报告.md"


def save_history_record(
    job_title: str,
    report_text: str,
    tailored_resume_path: str | Path | None = None,
    history_root: str | Path = HISTORY_ROOT,
    analysis_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """保存一次分析，返回带 record_id 的元数据。"""

    normalized_title = str(job_title).strip() or "目标岗位"
    now = datetime.now()
    while True:
        record_id = now.strftime("%Y%m%d-%H%M%S-%f")
        record_directory = Path(history_root) / record_id
        try:
            record_directory.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            now += timedelta(microseconds=1)

    report_filename = build_report_filename(normalized_title)
    (record_directory / "report.md").write_text(report_text, encoding="utf-8")
    if analysis_data is not None:
        (record_directory / "analysis.json").write_text(
            json.dumps(analysis_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    tailored_filename = None
    source_resume = Path(tailored_resume_path) if tailored_resume_path else None
    if source_resume and source_resume.exists():
        tailored_filename = build_tailored_resume_filename(normalized_title)
        shutil.copyfile(source_resume, record_directory / "tailored_resume.docx")

    metadata = {
        "record_id": record_id,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "job_title": normalized_title,
        "report_filename": report_filename,
        "tailored_resume_filename": tailored_filename,
    }
    (record_directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata


def list_history_records(
    history_root: str | Path = HISTORY_ROOT,
) -> list[dict[str, Any]]:
    """返回按时间倒序排列的历史记录。"""

    root = Path(history_root)
    if not root.exists():
        return []

    records: list[dict[str, Any]] = []
    for record_directory in sorted(root.iterdir(), reverse=True):
        metadata_path = record_directory / "metadata.json"
        if not record_directory.is_dir() or not metadata_path.exists():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(metadata, dict):
            continue

        metadata["record_id"] = record_directory.name
        metadata["label"] = _build_history_label(metadata)
        records.append(metadata)
    return records


def load_history_record(
    record_id: str,
    history_root: str | Path = HISTORY_ROOT,
) -> dict[str, Any]:
    """读取指定历史记录的报告和定制简历。"""

    record_directory = _get_record_directory(record_id, history_root)
    metadata = json.loads(
        (record_directory / "metadata.json").read_text(encoding="utf-8")
    )
    metadata["record_id"] = record_id
    metadata["label"] = _build_history_label(metadata)
    metadata["report_text"] = (
        record_directory / "report.md"
    ).read_text(encoding="utf-8")

    resume_path = record_directory / "tailored_resume.docx"
    metadata["tailored_resume_bytes"] = (
        resume_path.read_bytes() if resume_path.exists() else None
    )
    analysis_path = record_directory / "analysis.json"
    metadata["analysis_data"] = (
        json.loads(analysis_path.read_text(encoding="utf-8"))
        if analysis_path.exists() else None
    )
    return metadata


def delete_history_record(record_id: str, history_root: str | Path = HISTORY_ROOT) -> None:
    """校验真实路径后永久删除单条历史，不触及其他输出文件。"""

    record_directory = _get_record_directory(record_id, history_root)
    shutil.rmtree(record_directory)


def _build_job_filename_prefix(job_title: str) -> str:
    title = _sanitize_filename_component(job_title)
    if title.endswith("岗位"):
        return title
    if title.endswith("岗"):
        return f"{title}位"
    return f"{title}岗位"


def _sanitize_filename_component(value: str) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("_", str(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    cleaned = cleaned[:_MAX_FILENAME_COMPONENT_LENGTH].rstrip(" .")
    return cleaned or "目标岗位"


def _build_history_label(metadata: dict[str, Any]) -> str:
    created_at = str(metadata.get("created_at", "")).strip()
    job_title = str(metadata.get("job_title", "")).strip() or "目标岗位"
    short_time = created_at[5:16] if len(created_at) >= 16 else created_at
    return f"{short_time} | {job_title}" if short_time else job_title


def _get_record_directory(
    record_id: str,
    history_root: str | Path,
) -> Path:
    if not _RECORD_ID_PATTERN.fullmatch(record_id):
        raise ValueError("无效的历史记录编号。")
    record_directory = Path(history_root) / record_id
    root = Path(history_root).resolve()
    if record_directory.is_symlink() or record_directory.resolve().parent != root:
        raise ValueError("历史记录路径超出存储范围。")
    if not record_directory.is_dir():
        raise FileNotFoundError("历史记录不存在。")
    return record_directory
