"""从 Word 简历中提取段落，并在保留原样式的前提下回填改写结果。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


def extract_paragraph_blocks(file_path: str | Path) -> list[dict[str, Any]]:
    """提取 Word 文档中的所有非空段落，包括文本框中的段落。"""

    path = _validate_docx_path(file_path)
    document = Document(path)
    blocks: list[dict[str, Any]] = []

    for block_id, paragraph in enumerate(_iter_paragraphs(document)):
        text = _paragraph_text(paragraph)
        if text:
            blocks.append({"block_id": block_id, "text": text})

    return blocks


def apply_paragraph_replacements(
    source_path: str | Path,
    output_path: str | Path,
    replacements: list[dict[str, Any]],
    removals: list[dict[str, Any]] | None = None,
) -> dict[str, int]:
    """复制 Word 模板并替换或删除指定段落，保留其余原有版式。"""

    source = _validate_docx_path(source_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)

    document = Document(output)
    paragraphs = list(_iter_paragraphs(document))
    applied = 0
    skipped = 0

    for replacement in replacements:
        try:
            block_id = int(replacement["block_id"])
            new_text = str(replacement["new_text"]).strip()
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue

        if not new_text:
            skipped += 1
            continue

        original_text = _normalize(str(replacement.get("original_text", "")))
        paragraph = _resolve_paragraph(paragraphs, block_id, original_text)
        if paragraph is None:
            skipped += 1
            continue

        _set_paragraph_text(paragraph, new_text)
        applied += 1

    removed = 0
    removal_skipped = 0
    for removal in removals or []:
        try:
            block_id = int(removal["block_id"])
        except (KeyError, TypeError, ValueError):
            removal_skipped += 1
            continue

        original_text = _normalize(str(removal.get("original_text", "")))
        paragraph = _resolve_paragraph(paragraphs, block_id, original_text)
        if paragraph is None:
            removal_skipped += 1
            continue

        parent = paragraph._element.getparent()
        if parent is None:
            removal_skipped += 1
            continue

        parent.remove(paragraph._element)
        removed += 1

    document.save(output)
    return {
        "applied": applied,
        "skipped": skipped,
        "removed": removed,
        "removal_skipped": removal_skipped,
    }


def _validate_docx_path(file_path: str | Path) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    if path.suffix.lower() != ".docx":
        raise ValueError("保留原简历模板目前只支持 Word 文档。")
    return path


def _iter_paragraphs(document: Document):
    for paragraph_element in document.element.body.iter(qn("w:p")):
        yield Paragraph(paragraph_element, document)


def _paragraph_text(paragraph: Paragraph) -> str:
    return "".join(node.text or "" for node in paragraph._p.iter(qn("w:t"))).strip()


def _set_paragraph_text(paragraph: Paragraph, text: str) -> None:
    text_nodes = paragraph._p.findall(".//" + qn("w:t"))
    if not text_nodes:
        return
    text_nodes[0].text = text
    for node in text_nodes[1:]:
        node.text = ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u200b", "")).strip()


def _resolve_paragraph(
    paragraphs: list[Paragraph],
    block_id: int,
    original_text: str,
) -> Paragraph | None:
    if block_id < 0 or block_id >= len(paragraphs):
        return None

    paragraph = paragraphs[block_id]
    if not original_text:
        return paragraph

    current_text = _normalize(_paragraph_text(paragraph))
    if current_text == original_text:
        return paragraph

    matching_ids = [
        index
        for index, candidate in enumerate(paragraphs)
        if _normalize(_paragraph_text(candidate)) == original_text
    ]
    if len(matching_ids) != 1:
        return None
    return paragraphs[matching_ids[0]]
