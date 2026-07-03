# -*- coding: utf-8 -*-
"""系统性能消息 - 协议层
无人机机载计算机性能监控：CPU、内存、磁盘、网络、通信通道状态
"""
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class SystemMetricsMessage:
    """无人机系统性能监控消息"""
    drone_id: str
    seq: int
    timestamp: str
    # CPU
    cpu: Dict[str, float]  # {"percent": 35.2, "core_count": 4, "freq_mhz": 1800}
    # 内存
    memory: Dict[str, float]  # {"total_mb": 8192, "used_mb": 3200, "percent": 39.1}
    # 磁盘
    disk: Dict[str, float]  # {"total_gb": 256, "used_gb": 80, "percent": 31.2}
    # 网络
    network: Dict[str, Any]  # {"send_bytes": 102400, "recv_bytes": 51200, "interfaces": {...}}
    # 通信通道状态
    comm_channels: Dict[str, Any]  # {"udp_heartbeat": "healthy", "tcp_data": "healthy", ...}
    # 进程信息
    process: Dict[str, Any]  # {"pid": 1234, "cpu_percent": 5.2, "memory_mb": 128}
    # 系统运行时间
    uptime_seconds: float
    # 温度(可选)
    temperature: Optional[Dict[str, float]] = None

    @classmethod
    def create(cls, drone_id: str, seq: int,
               cpu: Dict[str, float], memory: Dict[str, float],
               disk: Dict[str, float], network: Dict[str, Any],
               comm_channels: Dict[str, Any], process: Dict[str, Any],
               uptime_seconds: float,
               temperature: Optional[Dict[str, float]] = None) -> "SystemMetricsMessage":
        return cls(
            drone_id=drone_id, seq=seq, timestamp=datetime.now().isoformat(),
            cpu=cpu, memory=memory, disk=disk, network=network,
            comm_channels=comm_channels, process=process,
            uptime_seconds=uptime_seconds, temperature=temperature
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "SystemMetricsMessage":
        return cls(**json.loads(raw))
