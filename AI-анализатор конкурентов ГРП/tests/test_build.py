import os
import sys

import build


def test_build_command_targets_expected_executable() -> None:
    command = build.build_command()
    assert command[:3] == [sys.executable, "-m", "PyInstaller"]
    assert "competitionmonitor" in command
    assert "--onefile" in command
    assert any(os.path.basename(item) == "main.py" for item in command)

