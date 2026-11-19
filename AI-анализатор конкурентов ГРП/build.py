from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def build_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "competitionmonitor",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths",
        str(ROOT),
        "--add-data",
        f"{ROOT / 'frontend'}{os.pathsep}frontend",
        "--add-data",
        f"{ROOT / 'data'}{os.pathsep}data",
        "--collect-all",
        "pydantic_settings",
        "--collect-all",
        "openai",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        str(ROOT / "desktop" / "main.py"),
    ]


def main() -> None:
    command = build_command()
    if "--dry-run" in sys.argv:
        print(" ".join(command))
        return
    if sys.platform != "win32":
        raise SystemExit(
            "competitionmonitor.exe нужно собирать в Windows: PyInstaller не является кросс-компилятором."
        )
    subprocess.run(command, cwd=ROOT, check=True)
    result = ROOT / "dist" / "competitionmonitor.exe"
    if not result.exists() or result.stat().st_size == 0:
        raise SystemExit("Сборка завершилась без файла competitionmonitor.exe")
    print(f"Готово: {result}")


if __name__ == "__main__":
    main()

