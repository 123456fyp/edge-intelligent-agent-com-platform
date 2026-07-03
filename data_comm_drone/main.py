# -*- coding: utf-8 -*-
"""
无人机端入口 - 香橙派5 Max (RK3588, 16G) 性能版

直接运行：python main.py
所有配置参数统一在 config/drone_config.py 中修改

端口分配：
- UDP 9000: 心跳保活 (1Hz)
- TCP 9001: 飞控状态数据 (10Hz)
- TCP 9002: LiDAR点云数据 (5Hz, 单帧最大5万点, zlib压缩)
- TCP 9003: 系统性能监控 (1Hz, CPU/内存/RK3588温度/通道状态)

健壮性特性：
- 自动重连 + 指数退避
- 错误熔断保护
- 看门狗线程监控
- 内存/CPU过高自动降级
- 所有异常捕获，不崩溃
"""

import os
import sys
import time

# 确保能找到项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.drone_config import DroneConfig
from transport.udp_sender import UDPTransportSender
from transport.tcp_sender import TCPTransportSender
from business.drone_node import DroneNode
from business.hardware import RosDroneHardware, SystemMetricsCollector


def main():
    """组装并运行无人机端 - 香橙派5 Max性能版"""
    # 1. 加载配置
    config = DroneConfig()

    # 2. 创建传输层实例
    hb_transport = UDPTransportSender(
        target_ip=config.target_ip,
        target_port=config.heartbeat_port,
        bind_ip=config.bind_ip
    )
    data_transport = TCPTransportSender(
        target_ip=config.target_ip,
        target_port=config.data_port,
        bind_ip=config.bind_ip,
        max_packet_size=config.max_packet_size,
        connect_timeout=config.connect_timeout,
        send_timeout=config.send_timeout
    )

    # 点云数据传输通道（TCP，大数据可靠传输，4MB包支持）
    pc_transport = None
    if config.enable_pointcloud:
        pc_transport = TCPTransportSender(
            target_ip=config.target_ip,
            target_port=config.pointcloud_port,
            bind_ip=config.bind_ip,
            max_packet_size=config.max_packet_size,
            connect_timeout=config.connect_timeout,
            send_timeout=config.send_timeout
        )

    # 系统性能监控传输通道（TCP）
    metrics_transport = None
    if config.enable_system_metrics:
        metrics_transport = TCPTransportSender(
            target_ip=config.target_ip,
            target_port=config.metrics_port,
            bind_ip=config.bind_ip,
            max_packet_size=512 * 1024,  # 监控数据小，512KB足够
            connect_timeout=config.connect_timeout,
            send_timeout=config.send_timeout
        )

    # 3. 创建 ROS 硬件数据源 - 传入点云性能参数
    hardware = RosDroneHardware(
        enable_pointcloud=config.enable_pointcloud,
        pointcloud_topic=config.pointcloud_topic,
        max_pointcloud_points=config.max_pointcloud_points * 2  # 硬件层缓存两倍上限，业务层再降采样
    )

    # 4. 创建业务节点（依赖注入）
    drone = DroneNode(
        config=config,
        heartbeat_transport=hb_transport,
        data_transport=data_transport,
        hardware=hardware,
        pointcloud_transport=pc_transport,
        metrics_transport=metrics_transport
    )

    # 5. 启动
    drone.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        drone.stop()
        print("\n无人机安全退出")


if __name__ == "__main__":
    main()
