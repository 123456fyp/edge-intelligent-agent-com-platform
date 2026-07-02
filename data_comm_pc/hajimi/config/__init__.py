# -*- coding: utf-8 -*-
from pathlib import Path

_outer_package = Path(__file__).resolve().parents[2] / "config"
if _outer_package.exists():
    __path__.append(str(_outer_package))

from .ground_station_config import GroundStationConfig
from .auth_config import AuthConfig

__all__ = ["GroundStationConfig", "AuthConfig"]
