# -*- coding: utf-8 -*-
"""Ground-station entrypoint.

This file is the stable startup command:

    python data_comm_pc/main.py

If ``data_comm_pc/hajimi`` exists, its overlay patches are loaded first. If the
folder is removed, the original PC app starts normally without Hajimi features.
"""
import sys
from pathlib import Path


def _prepare_imports() -> None:
    pc_dir = Path(__file__).resolve().parent
    hajimi_dir = pc_dir / "hajimi"
    patches_file = hajimi_dir / "patches.py"

    for path in (pc_dir, hajimi_dir):
        path_text = str(path)
        if path_text in sys.path:
            sys.path.remove(path_text)

    sys.path.insert(0, str(pc_dir))

    if patches_file.exists():
        sys.path.insert(0, str(hajimi_dir))
        from patches import apply_hajimi_patches

        apply_hajimi_patches()


def main() -> None:
    _prepare_imports()

    from core.app_assembler import AppAssembler

    assembler = AppAssembler()
    try:
        exit_code = assembler.run()
        sys.exit(exit_code)
    finally:
        assembler.shutdown()


if __name__ == "__main__":
    main()
