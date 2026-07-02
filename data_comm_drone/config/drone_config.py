# -*- coding: utf-8 -*-
"""Drone-side configuration.

The drone process sends heartbeat and telemetry to the ground station.
Defaults target localhost so the project can run as a local demo. For a real
drone deployment, set GROUND_STATION_IP to the PC/ground-station address.
"""

import os
from dataclasses import dataclass


@dataclass
class DroneConfig:
    """Drone sender configuration."""

    # Target address: ground station IP and ports.
    target_ip: str = os.getenv("GROUND_STATION_IP", "127.0.0.1")
    heartbeat_port: int = int(os.getenv("GROUND_STATION_HEARTBEAT_PORT", "9000"))
    data_port: int = int(os.getenv("GROUND_STATION_DATA_PORT", "9001"))

    # Optional source IP binding for multi-NIC hosts.
    bind_ip: str = os.getenv("DRONE_BIND_IP", "")

    # Drone identity and send intervals.
    drone_id: str = os.getenv("DRONE_ID", "DRONE-001")
    heartbeat_interval: float = float(os.getenv("DRONE_HEARTBEAT_INTERVAL", "1.0"))
    data_interval: float = float(os.getenv("DRONE_DATA_INTERVAL", "0.2"))
