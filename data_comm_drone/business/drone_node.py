# -*- coding: utf-8 -*-
"""无人机业务节点
心跳极简保活，全量飞控数据集中在数据报文上报,读取失败则填充默认值保证链路可用
"""

import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import HeartbeatMessage, DataMessage
from transport.base_sender import TransportSender
from config.drone import DroneConfig
from .hardware.base_drone_hardware import DroneHardwareBase


class DroneNode:
    """无人机业务节点（纯真实数据驱动）"""

    def __init__(
        self,
        config: DroneConfig,
        heartbeat_transport: TransportSender,
        data_transport: TransportSender,
        hardware: DroneHardwareBase
    ):
        self.config = config
        self.heartbeat_transport = heartbeat_transport
        self.data_transport = data_transport
        self.hardware = hardware

        # 业务状态
        self._seq = 0
        self._running = False
        self._threads = []

        # 硬件读取错误计数
        self._hw_error_count = 0
        # 链路健康状态：由心跳循环更新，数据循环依赖该状态
        self._link_healthy = True
        self._link_error_count = 0

    def _heartbeat_loop(self) -> None:
        """心跳发送循环
        负责链路健康检测：发送异常则标记链路断开，恢复则自动重连
        """
        while self._running:
            try:
                msg = HeartbeatMessage.create(drone_id=self.config.drone_id)
                self.heartbeat_transport.send(msg.to_json().encode("utf-8"))

                # 发送成功 → 标记链路健康，重置错误计数
                if not self._link_healthy:
                    self._link_healthy = True
                    self._link_error_count = 0
                    print("[心跳] 链路恢复正常")

            except Exception as e:
                # 发送失败 → 标记链路断开
                self._link_healthy = False
                self._link_error_count += 1
                # 每10次打印一次警告，避免刷屏
                if self._link_error_count % 10 == 0:
                    print(f"[心跳] 链路异常，连接失败: {e}，暂停数据发送")

            time.sleep(self.config.heartbeat_interval)

    def _data_loop(self) -> None:
        """全量飞控数据发送循环
        必填：飞行模式（飞控固有数据）
        选填：电池、位置、速度、姿态、传感器（无数据则填充默认空值，保证报文正常发出）
        """
        while self._running:
            try:
                # 1. 链路健康检查：链路断开时休眠等待恢复
                if not self._link_healthy:
                    time.sleep(self.config.data_interval)
                    continue

                # 2. 硬件连接检查
                if not self.hardware.is_connected():
                    self._hw_error_count += 1
                    if self._hw_error_count % 10 == 0:
                        print("[数据] 警告：未连接真实无人机硬件，使用默认空数据上报")
                    # 硬件未连接也发送默认报文，保证地面站能看到设备状态
                    flight_mode = "DISCONNECTED"
                    battery = {"percent": 0.0, "voltage": 0.0, "current": 0.0}
                    position = {}
                    attitude = {}
                    velocity = {}
                    sensors = {}
                else:
                    # 3. 读取全部飞控数据，单项读取失败则填充默认值
                    flight_mode = self.hardware.get_flight_mode() or "UNKNOWN"
                    
                    battery = self.hardware.get_battery_detail()
                    if not battery or "percent" not in battery:
                        battery = {"percent": 0.0, "voltage": 0.0, "current": 0.0}
                        print("[数据] 警告：电池数据读取失败，已填充默认值")

                    position = self.hardware.get_position() or {}
                    attitude = self.hardware.get_attitude() or {}
                    velocity = self.hardware.get_velocity() or {}
                    sensors = self.hardware.get_sensors() or {}

                # 4. 组装并发送报文（所有字段均有有效值，不会跳过）
                msg = DataMessage.create(
                    drone_id=self.config.drone_id,
                    seq=self._seq,
                    mode=flight_mode,
                    battery=battery,
                    attitude=attitude,
                    position=position,
                    velocity=velocity,
                    sensors=sensors
                )
                self.data_transport.send(msg.to_json().encode("utf-8"))
                
                # 打印状态，区分有无GPS
                gps_status = "有定位" if position and "lat" in position else "无GPS"
                print(f"[数据] seq={self._seq} 模式={flight_mode} 电量={battery.get('percent', 0)}% {gps_status}")
                self._seq += 1

            except ConnectionError:
                print("[数据] 传输链路未连接，等待心跳恢复...")
                self._link_healthy = False
            except Exception as e:
                print(f"[数据] 发送异常: {e}")

            time.sleep(self.config.data_interval)

    def start(self) -> None:
        """启动无人机节点"""
        print("=" * 50)
        print(f"  无人机 {self.config.drone_id} 启动（真实数据模式）")
        print(f"  目标地址: {self.config.target_ip}")
        print(f"  心跳端口(UDP): {self.config.heartbeat_port} (极简保活)")
        print(f"  数据端口(TCP): {self.config.data_port} (全量飞控状态)")
        print("=" * 50)

        if not self.hardware.is_connected():
            print("[初始化] 警告：当前未检测到真实无人机硬件连接")

        self._running = True
        t1 = threading.Thread(target=self._heartbeat_loop, daemon=True)
        t2 = threading.Thread(target=self._data_loop, daemon=True)
        t1.start()
        t2.start()
        self._threads = [t1, t2]

    def stop(self) -> None:
        """停止节点，释放所有资源"""
        self._running = False
        self.hardware.close()
        self.heartbeat_transport.close()
        self.data_transport.close()