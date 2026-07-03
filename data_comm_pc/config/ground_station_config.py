# -*- coding: utf-8 -*-
"""PC端配置 - 地面站（接收方）"""

from dataclasses import dataclass


@dataclass
class GroundStationConfig:
    """地面站配置（接收方）

    地面站只需要监听端口，不需要提前知道无人机的 IP。
    如果电脑有多个网卡，可以指定 listen_ip 来只监听某个网卡。
    """
    # ===== 监听地址 =====
    listen_ip: str = "0.0.0.0"            # 监听 IP，0.0.0.0 表示所有网卡
    heartbeat_port: int = 9000            # 心跳端口（UDP）
    data_port: int = 9001                 # 数据端口（TCP）
    pointcloud_port: int = 9002           # 点云数据端口（TCP）
    metrics_port: int = 9003              # 系统监控端口（TCP）

    # ===== 功能开关 =====
    enable_pointcloud: bool = True        # 是否启用点云接收
    enable_system_metrics: bool = True    # 是否启用系统监控接收

    # ===== 接收参数 =====
    buffer_size: int = 4096
    pointcloud_buffer_size: int = 4 * 1024 * 1024  # 点云数据缓冲区（4MB）
    tcp_backlog: int = 5
    heartbeat_timeout: float = 5.0        # 心跳超时判定离线（秒）
    pointcloud_timeout: float = 10.0      # 点云数据超时（秒）
