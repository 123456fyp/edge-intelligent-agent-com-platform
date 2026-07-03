# -*- coding: utf-8 -*-
"""地面站业务节点 - 接收端
事件驱动模式：数据更新通过信号通知UI，替代轮询
"""
import json
import time
import threading
from typing import Dict, Set, Tuple, Optional

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from config.ground_station_config import GroundStationConfig
from transport.base_receiver import TransportReceiver
from protocol import HeartbeatMessage, DataMessage, PointCloudMessage
from utils import quaternion_to_euler


class GroundStation(QObject):
    """地面站接收业务节点，支持Qt信号事件通知"""
    # 信号定义：设备上线、设备离线、数据更新、点云更新
    sig_drone_online = pyqtSignal(str)
    sig_drone_offline = pyqtSignal(str)
    sig_data_updated = pyqtSignal(str)  # 参数为无人机ID
    sig_pointcloud_updated = pyqtSignal(str)  # 点云数据更新信号

    def __init__(
        self,
        config: GroundStationConfig,
        heartbeat_receiver: TransportReceiver,
        data_receiver: TransportReceiver,
        pointcloud_receiver: Optional[TransportReceiver] = None,
        parent=None
    ):
        super().__init__(parent)
        self.config = config
        self.heartbeat_receiver = heartbeat_receiver
        self.data_receiver = data_receiver
        self.pointcloud_receiver = pointcloud_receiver

        # 无人机状态管理
        self._last_heartbeat: Dict[str, float] = {}
        self._drone_status: Dict[str, dict] = {}
        self._drone_pointcloud: Dict[str, PointCloudMessage] = {}
        self._last_pointcloud_time: Dict[str, float] = {}

        self._running = False
        self._lock = threading.Lock()

        # 离线检测定时器
        self._offline_check_timer = QTimer(self)
        self._offline_check_timer.timeout.connect(self.check_offline_drones)
        self._offline_check_timer.setInterval(1000)

    # ========== 回调处理 ==========
    def _on_heartbeat_message(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        """心跳消息回调：仅维护在线状态"""
        try:
            msg = HeartbeatMessage.from_json(raw_data.decode("utf-8"))
            is_new = False

            with self._lock:
                self._last_heartbeat[msg.drone_id] = time.time()
                if msg.drone_id not in self._drone_status:
                    self._drone_status[msg.drone_id] = {}
                    is_new = True

            # 锁外发射信号，避免阻塞
            if is_new:
                self.sig_drone_online.emit(msg.drone_id)
                print(f"[接入] 新无人机上线: {msg.drone_id} 地址:{addr[0]}:{addr[1]}")

        except Exception as e:
            print(f"[心跳解析] 异常: {e}")

    def _on_data_message(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        """数据消息回调：解析报文、聚合状态、格式转换"""
        try:
            raw_json = raw_data.decode("utf-8")
            msg = DataMessage.from_json(raw_json)

            # 姿态解算放在锁外执行
            attitude = self._normalize_attitude(msg.attitude)

            is_new = False
            with self._lock:
                # 收到数据也更新心跳时间，避免心跳丢包误判离线
                self._last_heartbeat[msg.drone_id] = time.time()

                # 先收到数据也判定新设备，触发上线，避免心跳晚到导致不显示
                if msg.drone_id not in self._drone_status:
                    is_new = True

                # 锁内仅做纯内存赋值
                self._drone_status[msg.drone_id] = {
                    "seq": msg.seq,
                    "timestamp": msg.timestamp,
                    "mode": msg.mode,
                    "battery": msg.battery,
                    "position": msg.position,
                    "attitude": attitude,
                    "velocity": msg.velocity,
                    "sensors": msg.sensors
                }

            # 新设备上线也从数据通道触发
            if is_new:
                self.sig_drone_online.emit(msg.drone_id)
                print(f"[接入] 新无人机上线(数据通道): {msg.drone_id} 地址:{addr[0]}:{addr[1]}")

            # 锁外发射信号，通知UI立即刷新
            self.sig_data_updated.emit(msg.drone_id)

            # 控制台打印
            alt = msg.position.get("alt", "N/A")
            bat = msg.battery.get("percent", "N/A")
            print(f"[数据] {msg.drone_id} seq={msg.seq} 模式={msg.mode} 高度={alt}m 电量={bat}%")

        except Exception as e:
            print(f"[数据解析] 异常: {e}")

    def _on_pointcloud_message(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        """点云消息回调：接收并解析点云数据"""
        try:
            raw_json = raw_data.decode("utf-8")
            msg = PointCloudMessage.from_json(raw_json)

            with self._lock:
                # 更新点云数据
                self._drone_pointcloud[msg.drone_id] = msg
                self._last_pointcloud_time[msg.drone_id] = time.time()

                # 收到点云也更新心跳时间
                self._last_heartbeat[msg.drone_id] = time.time()

                # 新设备判定
                if msg.drone_id not in self._drone_status:
                    self._drone_status[msg.drone_id] = {}
                    is_new = True
                else:
                    is_new = False

            # 新设备上线
            if is_new:
                self.sig_drone_online.emit(msg.drone_id)
                print(f"[接入] 新无人机上线(点云通道): {msg.drone_id} 地址:{addr[0]}:{addr[1]}")

            # 发射点云更新信号
            self.sig_pointcloud_updated.emit(msg.drone_id)

            print(f"[点云] {msg.drone_id} seq={msg.seq} 点数={msg.num_points} 帧={msg.frame_id}")

        except Exception as e:
            print(f"[点云解析] 异常: {e}")

    def _normalize_attitude(self, atti_raw: dict) -> dict:
        """姿态数据归一化：统一输出角度格式的欧拉角"""
        if "x" in atti_raw and "w" in atti_raw:
            try:
                roll, pitch, yaw = quaternion_to_euler(
                    float(atti_raw.get("x", 0)),
                    float(atti_raw.get("y", 0)),
                    float(atti_raw.get("z", 0)),
                    float(atti_raw.get("w", 1))
                )
                return {
                    "roll": round(roll, 2),
                    "pitch": round(pitch, 2),
                    "yaw": round(yaw, 2)
                }
            except Exception:
                return atti_raw
        return atti_raw

    # ========== 对外业务接口 ==========
    def get_online_ids(self) -> list:
        """获取所有在线无人机ID列表"""
        with self._lock:
            return list(self._last_heartbeat.keys())

    def get_drone_status(self, drone_id: str) -> Optional[dict]:
        """获取单架无人机状态字典"""
        with self._lock:
            data = self._drone_status.get(drone_id)
            return data.copy() if data else None

    def get_drone_pointcloud(self, drone_id: str) -> Optional[PointCloudMessage]:
        """获取单架无人机最新点云数据"""
        with self._lock:
            return self._drone_pointcloud.get(drone_id)

    def check_offline_drones(self) -> Set[str]:
        """基于心跳超时检测离线设备，每秒调用一次即可"""
        now = time.time()
        offline = set()
        timeout = self.config.heartbeat_timeout

        with self._lock:
            for drone_id, last_time in self._last_heartbeat.items():
                if now - last_time > timeout:
                    offline.add(drone_id)

            for drone_id in offline:
                self._last_heartbeat.pop(drone_id, None)
                self._drone_status.pop(drone_id, None)
                self._drone_pointcloud.pop(drone_id, None)
                self._last_pointcloud_time.pop(drone_id, None)

        # 发射离线信号
        for drone_id in offline:
            self.sig_drone_offline.emit(drone_id)
            print(f"[离线] 无人机超时下线: {drone_id}")

        return offline

    def get_all_status_json(self, indent: int = 2) -> str:
        """获取全量设备状态 JSON（兼容保留）"""
        with self._lock:
            return json.dumps(self._drone_status, indent=indent, ensure_ascii=False)

    def get_drone_status_json(self, drone_id: str, indent: int = 2) -> str:
        """获取单架设备状态 JSON（兼容保留）"""
        with self._lock:
            status = self._drone_status.get(drone_id, {})
            return json.dumps(status, indent=indent, ensure_ascii=False)

    def start(self) -> None:
        """启动业务：注册回调、开启接收、启动离线检测"""
        print("=" * 60)
        print("  地面站启动")
        print(f"  心跳监听端口(UDP): {self.config.heartbeat_port}")
        print(f"  数据监听端口(TCP): {self.config.data_port}")
        if self.pointcloud_receiver and self.config.enable_pointcloud:
            print(f"  点云监听端口(TCP): {self.config.pointcloud_port}")
        print(f"  心跳超时时间: {self.config.heartbeat_timeout}s")
        print("=" * 60)

        self._running = True
        self.heartbeat_receiver.start(on_message=self._on_heartbeat_message)
        self.data_receiver.start(on_message=self._on_data_message)

        # 启动点云接收
        if self.pointcloud_receiver and self.config.enable_pointcloud:
            self.pointcloud_receiver.start(on_message=self._on_pointcloud_message)

        # 启动离线检测定时器
        self._offline_check_timer.start()

    def stop(self) -> None:
        """停止业务、释放资源"""
        self._running = False
        # 停止离线检测定时器
        self._offline_check_timer.stop()
        self.heartbeat_receiver.close()
        self.data_receiver.close()

        # 停止点云接收
        if self.pointcloud_receiver:
            self.pointcloud_receiver.close()

        print("地面站已停止")
