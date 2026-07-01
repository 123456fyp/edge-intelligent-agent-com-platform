# -*- coding: utf-8 -*-
"""Ground-station configuration."""

import os
from dataclasses import dataclass


@dataclass
class GroundStationConfig:
    """Ground station receiver configuration."""

    # Listen address. Use 0.0.0.0 to accept packets from every network card.
    listen_ip: str = os.getenv("GROUND_STATION_LISTEN_IP", "0.0.0.0")
    heartbeat_port: int = int(os.getenv("GROUND_STATION_HEARTBEAT_PORT", "9000"))
    data_port: int = int(os.getenv("GROUND_STATION_DATA_PORT", "9001"))

    # Receive parameters.
    buffer_size: int = int(os.getenv("GROUND_STATION_BUFFER_SIZE", "4096"))
    tcp_backlog: int = int(os.getenv("GROUND_STATION_TCP_BACKLOG", "5"))
    heartbeat_timeout: float = float(os.getenv("GROUND_STATION_HEARTBEAT_TIMEOUT", "5.0"))
