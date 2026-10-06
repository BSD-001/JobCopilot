"""生成独立Windows便携ZIP；不收集用户材料、不调用模型。"""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import mkdtemp


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_runtime_licenses(bundle: Path):
    """随包保留运行依赖的许可原文，不改变本项目的授权方式。"""

    destination = bundle / "第三方许可"
    destination.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE_PYTHON.txt"
    if python_license.is_file():
        shutil.copyfile(python_license, destination / "Python-LICENSE.txt")
    for name in ("fastapi", "uvicorn", "openai", "python-docx", "pypdf", "lxml", "pillow", "certifi", "bleach", "markdown", "jinja2", "httpx", "httpx2", "httpcore", "httpcore2", "pydantic", "pydantic-core", "h11", "anyio", "idna", "jiter", "distro", "sniffio", "typing_extensions", "webencodings", "annotated-doc", "annotated-types", "typing-inspection", "charset-normalizer", "opentelemetry-api", "packaging", "setuptools", "click", "tzdata", "websockets", "httptools", "markupsafe", "itsdangerous"):
        try:
            package = distribution(name)
        except PackageNotFoundError:
            continue
        licenses = [item for item in package.files or [] if item.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))]
        if licenses:
            folder = destination / name
            folder.mkdir(exist_ok=True)
            for index, item in enumerate(licenses):
                shutil.copyfile(package.locate_file(item), folder / f"{index + 1:02d}-{item.name}")


def main() -> int:
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise RuntimeError("请在64位Windows和64位Python环境中构建。")
    output_root = PROJECT_ROOT / "output" / "windows"
    output_root.mkdir(parents=True, exist_ok=True)
    run_root = Path(mkdtemp(prefix="build-", dir=output_root)).resolve()
    if run_root.parent != output_root.resolve():
        raise RuntimeError("构建路径不在预期目录，停止。")
    command = [
        sys.executable, "-m", "PyInstaller", "--onedir", "--console", "--noupx",
        "--name", "JobCopilot", "--paths", str(PROJECT_ROOT),
        "--distpath", str(run_root / "dist"), "--workpath", str(run_root / "work"),
        "--specpath", str(run_root / "spec"), "--add-data", f"{PROJECT_ROOT / 'web'}:web",
        "--collect-data", "docx", "--copy-metadata", "openai",
        "--hidden-import", "markdown.extensions.tables",
        "--hidden-import", "markdown.extensions.fenced_code",
    ]
    for module in ("streamlit", "pandas", "numpy", "pyarrow", "matplotlib", "scipy", "torch"):
        command.extend(["--exclude-module", module])
    command.append(str(PROJECT_ROOT / "scripts" / "run_web.py"))
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)
    bundle = run_root / "dist" / "JobCopilot"
    executable = bundle / "JobCopilot.exe"
    subprocess.run([str(executable), "--self-check", str(run_root / "self-check.json")], check=True, cwd=run_root)
    for name in ("output", "history", ".env", "tests", "resume-agent"):
        if (bundle / "_internal" / name).exists():
            raise RuntimeError(f"便携包不应包含{name}，停止打包。")
    shutil.copyfile(PROJECT_ROOT / "docs" / "Windows便携版使用说明.txt", bundle / "先读我.txt")
    copy_runtime_licenses(bundle)
    archive = Path(shutil.make_archive(str(run_root / "JobCopilot-Windows-x64"), "zip", root_dir=run_root / "dist"))
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    (run_root / "SHA256SUMS.txt").write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="utf-8")
    print(f"便携包：{archive}")
    print(f"SHA256：{digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
