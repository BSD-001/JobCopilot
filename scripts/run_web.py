"""启动本地新版网页，保留其他服务，不自动结束已有进程。"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if not getattr(sys, "frozen", False) and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def read_health(port: int) -> dict:
    """只访问本机服务，不受系统代理影响。"""

    try:
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/api/health", timeout=0.4) as response:
            data = json.load(response)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def is_running_windows_package(port: int) -> bool:
    health = read_health(port)
    return health.get("status") == "ok" and health.get("application") == "JobCopilot" and health.get("windows_package") is True


def port_in_use(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def choose_windows_port(start: int) -> tuple[int, bool]:
    """重复双击只打开已运行的便携版；其他服务占用时选择空闲端口。"""

    ports = range(start, start + 10)
    for port in ports:
        if is_running_windows_package(port):
            return port, True
    for port in ports:
        if not port_in_use(port):
            return port, False
    raise RuntimeError("附近端口均被占用。请关闭不用的服务后重试，不会自动结束其他进程。")


def main() -> int:
    parser = argparse.ArgumentParser(description="启动JobCopilot新版网页")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--self-check", metavar="RESULT_JSON", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_check:
        from scripts.windows_self_check import run_self_check
        return run_self_check(Path(args.self_check))
    port = args.port
    if getattr(sys, "frozen", False):
        try:
            port, already_running = choose_windows_port(port)
        except RuntimeError as error:
            print(error)
            input("按回车键退出。")
            return 1
        if already_running:
            print(f"JobCopilot已在运行：http://localhost:{port}/")
            if not args.no_browser:
                webbrowser.open(f"http://localhost:{port}/")
            return 0
    elif port_in_use(port):
        print(f"端口{port}已被占用。请先关闭旧服务，或使用 --port 8502。不会自动结束其他进程。")
        return 1

    from webapp import app

    print(f"JobCopilot网页地址：http://localhost:{port}/")
    print("请保留此运行窗口，分析结束后再关闭。若浏览器未自动打开，可复制上方网址。")
    if not args.no_browser:
        def open_when_ready():
            for _ in range(50):
                if read_health(port).get("application") == "JobCopilot":
                    webbrowser.open(f"http://localhost:{port}/")
                    return
                time.sleep(0.2)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, loop="asyncio", http="h11", ws="none", log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
