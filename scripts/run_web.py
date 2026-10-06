"""启动本地新版网页，保留其他服务，不自动结束已有进程。"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="启动JobCopilot新版网页")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", args.port)) == 0:
            print(f"端口{args.port}已被占用。请先关闭旧服务，或使用 --port 8502。不会自动结束其他进程。")
            return 1
    if not args.no_browser:
        def open_when_ready():
            for _ in range(50):
                with socket.socket() as probe:
                    if probe.connect_ex(("127.0.0.1", args.port)) == 0:
                        webbrowser.open(f"http://localhost:{args.port}/")
                        return
                time.sleep(0.2)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run("webapp:app", host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
