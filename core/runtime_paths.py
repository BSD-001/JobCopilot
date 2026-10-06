"""区分网页资源和用户数据，避免便携包更新覆盖历史。"""

from pathlib import Path
import os
import sys


def default_history_root() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[1] / "output" / "history"
    local_data = os.environ.get("LOCALAPPDATA")
    directory = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
    return directory / "JobCopilot" / "history"
