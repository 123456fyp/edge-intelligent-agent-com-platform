# -*- coding: utf-8 -*-
"""无人机端配置 - 发送方"""

from dataclasses import dataclass


@dataclass
class DroneConfig:
    """无人机端配置（发送方）

    无人机需要知道把数据发给谁（地面站的 IP 和端口）。
    如果无人机有多个网卡，可以指定 bind_ip 来选择用哪个网卡发。
    """
    # ===== 目标地址（地面站的 IP 和端口）=====
    target_ip: str = "192.168.1.117"     # 地面站（电脑）的 IP 地址
    heartbeat_port: int = 9000            # 心跳端口（UDP）
    data_port: int = 9001                 # 数据端口（TCP）

    # ===== 可选：绑定源 IP（多网卡时指定用哪个网卡发）=====
    # 留空字符串表示不绑定，系统自动选
    bind_ip: str = ""

    # ===== 无人机自身参数 =====
    drone_id: str = "DRONE-001"
    heartbeat_interval: float = 1.0       # 心跳间隔（秒）
    data_interval: float = 0.2            # 数据发送间隔（秒）
