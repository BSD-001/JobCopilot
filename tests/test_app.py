"""浏览器界面基础测试。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class BrowserInterfaceTests(unittest.TestCase):
    def test_history_selector_is_visible(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        history_record = {
            "record_id": "20260916-120000-000000",
            "label": "09-16 12:00 | AI产品运营",
        }
        with patch(
            "core.history_store.list_history_records",
            return_value=[history_record],
        ):
            app = AppTest.from_file(str(app_path)).run()

        self.assertEqual(len(app.exception), 0)
        self.assertIn("选择历史记录", [item.label for item in app.selectbox])

    def test_page_loads_without_exception(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("JobCopilot" in item.value for item in app.title))
        self.assertIn("补写未掌握的目标岗位技能", [item.label for item in app.checkbox])

    def test_tailored_resume_download_is_visible(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path))
        app.session_state["jobcopilot_report"] = "# 测试报告"
        app.session_state["jobcopilot_tailored_resume"] = b"demo-document"
        app.session_state["jobcopilot_tailored_name"] = "岗位定制简历.docx"
        app.run()

        labels = [button.label for button in app.download_button]
        self.assertIn("下载 Markdown 报告", labels)
        self.assertIn("下载岗位定制简历", labels)


if __name__ == "__main__":
    unittest.main()
