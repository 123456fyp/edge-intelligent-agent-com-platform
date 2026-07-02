# -*- coding: utf-8 -*-
"""Hajimi overlay entrypoint for the PC ground-station app."""
import sys
from pathlib import Path

hajimi_dir = Path(__file__).resolve().parent
pc_dir = hajimi_dir.parent

for path in (pc_dir, hajimi_dir):
    path_text = str(path)
    if path_text in sys.path:
        sys.path.remove(path_text)

sys.path.insert(0, str(hajimi_dir))
sys.path.insert(1, str(pc_dir))

from core.app_assembler import AppAssembler


def main():
    assembler = AppAssembler()
    try:
        exit_code = assembler.run()
        sys.exit(exit_code)
    finally:
        assembler.shutdown()


if __name__ == "__main__":
    main()
