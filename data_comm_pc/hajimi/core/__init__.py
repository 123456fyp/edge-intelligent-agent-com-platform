# -*- coding: utf-8 -*-
from pathlib import Path

_outer_package = Path(__file__).resolve().parents[2] / "core"
if _outer_package.exists():
    __path__.append(str(_outer_package))

from .app_assembler import AppAssembler


__all__ = [
    "AppAssembler"
]
