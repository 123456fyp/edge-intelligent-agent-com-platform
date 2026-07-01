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

    # ===== 接收参数 =====
    buffer_size: int = 4096
    tcp_backlog: int = 5
    heartbeat_timeout: float = 5.0        # 心跳超时判定离线（秒）
