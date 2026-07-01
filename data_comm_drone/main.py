# -*- coding: utf-8 -*-
"""
无人机端入口

直接运行：python main.py
所有配置参数统一在 config/drone.py 中修改
"""

import os
import sys
import time

# 确保能找到项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.drone import DroneConfig
from transport.udp_sender import UDPTransportSender
from transport.tcp_sender import TCPTransportSender
from business.drone_node import DroneNode
from business.hardware import RosDroneHardware


def main():
    """组装并运行无人机端"""
    # 1. 加载配置：所有参数统一从 config/drone.py 读取
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
        bind_ip=config.bind_ip
    )

    # 3. 创建 ROS 硬件数据源
    hardware = RosDroneHardware()

    # 4. 创建业务节点（依赖注入）
    drone = DroneNode(config, hb_transport, data_transport, hardware)

    # 5. 启动
    drone.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        drone.stop()
        print("\n无人机退出")


if __name__ == "__main__":
    main()