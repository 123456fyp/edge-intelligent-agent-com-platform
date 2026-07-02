# -*- coding: utf-8 -*-
"""Ground-station receiver configuration."""

import os
from dataclasses import dataclass


@dataclass
class GroundStationConfig:
    """Configuration for the PC ground station."""

    # Listen on all local interfaces so the drone can reach this PC.
    listen_ip: str = os.getenv("GROUND_STATION_LISTEN_IP", "0.0.0.0")

    # Only accept packets from this drone IP. Set the environment variable to an
    # empty value if local simulation or multi-drone testing should accept all.
    allowed_drone_ip: str = os.getenv("GROUND_STATION_ALLOWED_DRONE_IP", "10.249.53.151")

    heartbeat_port: int = int(os.getenv("GROUND_STATION_HEARTBEAT_PORT", "9000"))
    data_port: int = int(os.getenv("GROUND_STATION_DATA_PORT", "9001"))

    buffer_size: int = int(os.getenv("GROUND_STATION_BUFFER_SIZE", "4096"))
    tcp_backlog: int = int(os.getenv("GROUND_STATION_TCP_BACKLOG", "5"))
    heartbeat_timeout: float = float(os.getenv("GROUND_STATION_HEARTBEAT_TIMEOUT", "5.0"))
