"""历史分析记录存储测试。"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.history_store import (
    build_tailored_resume_filename,
    list_history_records,
    load_history_record,
    save_history_record,
)


class HistoryStoreTests(unittest.TestCase):
    def test_saves_and_loads_history_record(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            history_root = directory / "history"
            resume_path = directory / "tailored.docx"
            resume_path.write_bytes(b"demo-resume")

            saved = save_history_record(
                job_title="AI产品运营",
                report_text="# 测试报告",
                tailored_resume_path=resume_path,
                history_root=history_root,
            )

            self.assertEqual(
                saved["tailored_resume_filename"],
                "AI产品运营岗位-定制简历.docx",
            )
            records = list_history_records(history_root)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["job_title"], "AI产品运营")

            loaded = load_history_record(saved["record_id"], history_root)
            self.assertEqual(loaded["report_text"], "# 测试报告")
            self.assertEqual(loaded["tailored_resume_bytes"], b"demo-resume")

    def test_builds_safe_resume_filename(self) -> None:
        self.assertEqual(
            build_tailored_resume_filename("产品/运营:*?"),
            "产品_运营___岗位-定制简历.docx",
        )
        self.assertEqual(
            build_tailored_resume_filename("产品运营岗"),
            "产品运营岗位-定制简历.docx",
        )


if __name__ == "__main__":
    unittest.main()
