# -*- coding: utf-8 -*-
"""Ground-station entrypoint.

The active, login-enabled PC app lives in ``data_comm_pc/hajimi``. This
wrapper keeps the original startup command working:

    python data_comm_pc/main.py
"""
import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    pc_dir = Path(__file__).resolve().parent
    hajimi_dir = pc_dir / "hajimi"
    hajimi_main = hajimi_dir / "main.py"

    if not hajimi_main.exists():
        raise FileNotFoundError(f"Missing hajimi entrypoint: {hajimi_main}")

    sys.path.insert(0, str(hajimi_dir))
    os.chdir(str(hajimi_dir))
    runpy.run_path(str(hajimi_main), run_name="__main__")


if __name__ == "__main__":
    main()
