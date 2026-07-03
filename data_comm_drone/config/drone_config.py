# -*- coding: utf-8 -*-
"""无人机端配置 - 香橙派5 Max (RK3588, 8核, 16G) 保守冗余版
重要：多留性能冗余给飞控、SLAM、路径规划等核心算法
- 通信进程CPU占用控制在 < 8%
- 通信进程内存占用控制在 < 150MB
- 网络带宽控制在 < 3Mbps
- 非关键数据低频发送，关键数据保证频率
- 点云仅做预览，完整点云本地SLAM处理
"""

import os
from dataclasses import dataclass


@dataclass
class DroneConfig:
    """无人机发送端配置 - Orange Pi 5 Max 保守冗余版"""

    # ========== 目标地址配置 ==========
    target_ip: str = os.getenv("GROUND_STATION_IP", "192.168.1.117")
    heartbeat_port: int = int(os.getenv("GROUND_STATION_HEARTBEAT_PORT", "9000"))
    data_port: int = int(os.getenv("GROUND_STATION_DATA_PORT", "9001"))
    pointcloud_port: int = int(os.getenv("GROUND_STATION_POINTCLOUD_PORT", "9002"))
    metrics_port: int = int(os.getenv("GROUND_STATION_METRICS_PORT", "9003"))

    # 多网卡绑定（香橙派双网口时指定出口网卡）
    bind_ip: str = os.getenv("DRONE_BIND_IP", "")
    bind_interface: str = os.getenv("DRONE_BIND_INTERFACE", "")

    # ========== 无人机标识 ==========
    drone_id: str = os.getenv("DRONE_ID", "OPI5MAX-DRONE-001")

    # ========== 发送间隔（保守设置，留足CPU/带宽） ==========
    heartbeat_interval: float = float(os.getenv("DRONE_HEARTBEAT_INTERVAL", "1.0"))   # 1Hz 心跳
    data_interval: float = float(os.getenv("DRONE_DATA_INTERVAL", "0.2"))            # 5Hz 飞控状态（关键数据，保持频率）
    pointcloud_interval: float = float(os.getenv("DRONE_POINTCLOUD_INTERVAL", "1.0"))# 1Hz 点云预览（非关键，降频）
    metrics_interval: float = float(os.getenv("DRONE_METRICS_INTERVAL", "5.0"))      # 0.2Hz 系统监控（非关键，低频）

    # ========== 功能开关 ==========
    enable_pointcloud: bool = os.getenv("DRONE_ENABLE_POINTCLOUD", "true").lower() == "true"
    enable_system_metrics: bool = os.getenv("DRONE_ENABLE_METRICS", "true").lower() == "true"
    pointcloud_topic: str = os.getenv("DRONE_POINTCLOUD_TOPIC", "/cloud_registered")

    # ========== 香橙派硬件看门狗 ==========
    enable_hw_watchdog: bool = os.getenv("DRONE_ENABLE_HW_WATCHDOG", "false").lower() == "true"
    watchdog_timeout: int = int(os.getenv("DRONE_WATCHDOG_TIMEOUT", "15"))

    # ========== 资源冗余保护阈值（主动限流，不抢核心算法资源） ==========
    # CPU超过此值，非关键数据（点云/监控）自动暂停
    cpu_throttle_threshold: float = float(os.getenv("DRONE_CPU_THROTTLE", "60.0"))
    # 内存超过此值，主动降级停发非关键数据
    memory_throttle_threshold: float = float(os.getenv("DRONE_MEM_THROTTLE", "70.0"))
    # 可用内存低于此值，只发心跳和飞控关键数据（保留2G空闲内存）
    memory_low_mb: int = int(os.getenv("DRONE_MEM_LOW_MB", "2048"))

    # ========== 点云参数（仅预览，不传输完整点云） ==========
    # 单帧最多3000点（足够地面站预览，完整点云本地SLAM处理）
    max_pointcloud_points: int = int(os.getenv("DRONE_MAX_PC_POINTS", "3000"))
    # 压缩等级6：高压缩比省带宽，CPU占用可接受
    pointcloud_compression_level: int = int(os.getenv("DRONE_PC_COMPRESS", "6"))
    # 单包最大512KB，避免大包阻塞网络
    max_packet_size: int = int(os.getenv("DRONE_MAX_PACKET", str(512 * 1024)))

    # ========== 可靠传输参数 ==========
    connect_timeout: float = float(os.getenv("DRONE_CONNECT_TIMEOUT", "3.0"))
    send_timeout: float = float(os.getenv("DRONE_SEND_TIMEOUT", "5.0"))
    circuit_breaker_threshold: int = int(os.getenv("DRONE_CB_THRESHOLD", "15"))
    circuit_breaker_recovery: float = float(os.getenv("DRONE_CB_RECOVERY", "15.0"))
