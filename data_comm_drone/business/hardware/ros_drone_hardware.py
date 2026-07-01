# -*- coding: utf-8 -*-
"""ROS 无人机硬件实现 - 修复版
增加独立 spin 线程驱动消息队列，保证回调正常执行
"""
import threading
from typing import Optional, Dict
import math
import time

from .base_drone_hardware import DroneHardwareBase


class RosDroneHardware(DroneHardwareBase):
    """基于 ROS 话题的无人机硬件数据读取实现"""

    def __init__(
        self,
        battery_topic: str = "/mavros/battery",
        state_topic: str = "/mavros/state",
        position_topic: str = "/mavros/global_position/global",
        imu_topic: str = "/mavros/imu/data",
        velocity_topic: str = "/mavros/global_position/raw/gps_vel",
        node_name: str = "drone_comm_hardware"
    ):
        self._lock = threading.Lock()

        # 数据缓存
        self._connected = False
        self._flight_mode: Optional[str] = None
        self._battery: Dict[str, float] = {}
        self._position: Optional[Dict] = None
        self._attitude: Optional[Dict] = None
        self._velocity: Optional[Dict] = None
        self._sensors: Dict = {}

        # 调试计数
        self._state_cb_count = 0
        self._battery_cb_count = 0

        # 话题配置
        self.battery_topic = battery_topic
        self.state_topic = state_topic
        self.position_topic = position_topic
        self.imu_topic = imu_topic
        self.velocity_topic = velocity_topic

        self._subscribers = []
        self._ros_available = False
        self._rospy = None
        self._spin_thread = None
        self._running = False

        try:
            # 1. 导入ROS依赖
            import rospy
            from sensor_msgs.msg import BatteryState, NavSatFix, Imu
            from mavros_msgs.msg import State
            from geometry_msgs.msg import TwistStamped
            self._rospy = rospy
            print("[硬件-调试] ROS模块导入成功")

            # 2. 初始化节点
            if not rospy.core.is_initialized():
                rospy.init_node(node_name, anonymous=True, disable_signals=True)
                print(f"[硬件-调试] ROS节点 {node_name} 初始化完成")
            else:
                print("[硬件-调试] 检测到已有ROS环境，复用节点")

            # 3. 逐个订阅话题，打印确认
            sub_state = rospy.Subscriber(self.state_topic, State, self._state_cb)
            self._subscribers.append(sub_state)
            print(f"[硬件-调试] 已订阅状态话题: {self.state_topic}")

            sub_bat = rospy.Subscriber(self.battery_topic, BatteryState, self._battery_cb)
            self._subscribers.append(sub_bat)
            print(f"[硬件-调试] 已订阅电池话题: {self.battery_topic}")

            sub_pos = rospy.Subscriber(self.position_topic, NavSatFix, self._position_cb)
            self._subscribers.append(sub_pos)
            print(f"[硬件-调试] 已订阅位置话题: {self.position_topic}")

            sub_imu = rospy.Subscriber(self.imu_topic, Imu, self._imu_cb)
            self._subscribers.append(sub_imu)

            sub_vel = rospy.Subscriber(self.velocity_topic, TwistStamped, self._velocity_cb)
            self._subscribers.append(sub_vel)

            self._ros_available = True
            print(f"[硬件-调试] 共订阅 {len(self._subscribers)} 个话题，启动消息处理线程...")

            # 等待首帧数据到达，避免启动瞬间业务层判空
            time.sleep(0.5)

        except ImportError as e:
            print(f"[硬件-错误] ROS依赖缺失: {e}")
        except Exception as e:
            print(f"[硬件-错误] 初始化失败: {type(e).__name__}: {e}")

    # ========== 回调函数 ==========
    def _state_cb(self, msg) -> None:
        with self._lock:
            self._flight_mode = msg.mode
            self._connected = msg.connected
            self._state_cb_count += 1
            # 首次收到打印
            if self._state_cb_count == 1:
                print(f"[硬件-回调] 首次收到飞控状态 | 连接={msg.connected} 模式={msg.mode}")

    def _battery_cb(self, msg) -> None:
        with self._lock:
            # 兼容 0-1 和 0-100 两种电量格式
            pct = msg.percentage
            if math.isnan(pct):
                pct = 0.0
            elif pct <= 1.0:
                pct = pct * 100
            self._battery = {
                "percent": round(pct, 2),
                "voltage": round(msg.voltage, 2),
                "current": round(msg.current, 2)
            }
            self._battery_cb_count += 1
            if self._battery_cb_count == 1:
                print(f"[硬件-回调] 首次收到电池数据 | 电量={self._battery['percent']}% 电压={self._battery['voltage']}V")
            self._connected = True

    def _position_cb(self, msg) -> None:
        with self._lock:
            lat = msg.latitude
            lon = msg.longitude
            alt = msg.altitude
            
            # 过滤无效定位数据（未定位时通常为0或NaN）
            if abs(lat) < 0.001 and abs(lon) < 0.001:
                return
            if math.isnan(lat) or math.isnan(lon) or math.isnan(alt):
                return

            self._position = {
                "lat": lat,
                "lon": lon,
                "alt": alt
            }
            self._sensors["gps_satellites"] = msg.status.service
            self._connected = True

    def _imu_cb(self, msg) -> None:
        with self._lock:
            self._attitude = {
                "x": msg.orientation.x,
                "y": msg.orientation.y,
                "z": msg.orientation.z,
                "w": msg.orientation.w
            }

    def _velocity_cb(self, msg) -> None:
        with self._lock:
            self._velocity = {
                "vx": round(msg.twist.linear.x, 2),
                "vy": round(msg.twist.linear.y, 2),
                "vz": round(msg.twist.linear.z, 2)
            }

    # ========== 对外读取接口 ==========
    def is_connected(self) -> bool:
        with self._lock:
            if not self._ros_available or self._rospy is None:
                return False
            return self._connected and not self._rospy.is_shutdown()

    def get_flight_mode(self) -> Optional[str]:
        with self._lock:
            return self._flight_mode

    def get_battery_detail(self) -> Optional[Dict[str, float]]:
        with self._lock:
            # 修复：只要字典有数据就返回，避免空字典误判；真正无数据时返回默认值
            if self._battery:
                return self._battery.copy()
            # 未收到数据时返回默认值，不返回None，避免业务层跳过敏报文
            return {"percent": 0.0, "voltage": 0.0, "current": 0.0}

    def get_position(self) -> Optional[Dict]:
        with self._lock:
            return self._position

    def get_attitude(self) -> Optional[Dict[str, float]]:
        with self._lock:
            return self._attitude

    def get_velocity(self) -> Optional[Dict[str, float]]:
        with self._lock:
            return self._velocity

    def get_sensors(self) -> Optional[Dict]:
        with self._lock:
            return self._sensors.copy() if self._sensors else {}

    def close(self) -> None:
        for sub in self._subscribers:
            sub.unregister()