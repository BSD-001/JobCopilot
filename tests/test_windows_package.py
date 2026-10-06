"""Windows便携包适配测试，不调用模型或改动用户历史。"""

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from core.runtime_paths import default_history_root
from scripts.run_web import choose_windows_port, is_running_windows_package, main


class WindowsPackageTests(TestCase):
    def test_source_history_stays_in_project(self):
        with patch("core.runtime_paths.sys.frozen", False, create=True):
            self.assertEqual(default_history_root(), Path(__file__).resolve().parents[1] / "output" / "history")

    def test_frozen_history_uses_user_data_not_bundle(self):
        with patch("core.runtime_paths.sys.frozen", True, create=True), patch.dict("os.environ", {"LOCALAPPDATA": r"C:\ExampleUser\AppData\Local"}):
            self.assertEqual(default_history_root(), Path(r"C:\ExampleUser\AppData\Local") / "JobCopilot" / "history")

    def test_health_must_identify_windows_package(self):
        with patch("scripts.run_web.read_health", return_value={"status": "ok", "application": "OtherApp", "windows_package": True}):
            self.assertFalse(is_running_windows_package(8501))
        with patch("scripts.run_web.read_health", return_value={"status": "ok", "application": "JobCopilot", "windows_package": True}):
            self.assertTrue(is_running_windows_package(8501))

    def test_repeated_launch_reuses_existing_package(self):
        with patch("scripts.run_web.is_running_windows_package", side_effect=lambda port: port == 8502), patch("scripts.run_web.port_in_use", return_value=False):
            self.assertEqual(choose_windows_port(8501), (8502, True))

    def test_other_service_is_not_stopped(self):
        with patch("scripts.run_web.is_running_windows_package", return_value=False), patch("scripts.run_web.port_in_use", side_effect=lambda port: port == 8501):
            self.assertEqual(choose_windows_port(8501), (8502, False))

    def test_full_port_range_has_clear_error(self):
        with patch("scripts.run_web.is_running_windows_package", return_value=False), patch("scripts.run_web.port_in_use", return_value=True):
            with self.assertRaises(RuntimeError):
                choose_windows_port(8501)

    def test_repeated_double_click_opens_default_browser(self):
        with patch("scripts.run_web.sys.frozen", True, create=True), patch("scripts.run_web.sys.argv", ["JobCopilot.exe"]), patch("scripts.run_web.choose_windows_port", return_value=(8502, True)), patch("scripts.run_web.webbrowser.open") as open_browser:
            self.assertEqual(main(), 0)
            open_browser.assert_called_once_with("http://localhost:8502/")
