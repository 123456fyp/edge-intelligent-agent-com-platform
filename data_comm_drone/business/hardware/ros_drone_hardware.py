# -*- coding: utf-8 -*-
"""ROS 无人机硬件实现
特性：
- 所有回调异常捕获，单个话题异常不影响整体
- 数据范围校验，过滤NaN/异常值
- 独立spin线程，异常自动重启
- 点云数据量限制，避免内存溢出
- 读取超时保护
- 详细的错误统计
"""
import threading
from typing import Optional, Dict, List
import math
import time

from .base_drone_hardware import DroneHardwareBase


class RosDroneHardware(DroneHardwareBase):
    """基于 ROS 话题的无人机硬件数据读取实现 - 高可靠版"""

    def __init__(
        self,
        battery_topic: str = "/mavros/battery",
        state_topic: str = "/mavros/state",
        position_topic: str = "/mavros/global_position/global",
        imu_topic: str = "/mavros/imu/data",
        velocity_topic: str = "/mavros/global_position/raw/gps_vel",
        pointcloud_topic: str = "/velodyne_points",
        enable_pointcloud: bool = True,
        max_pointcloud_points: int = 3000,  # 默认3000点预览，留内存/CPU给SLAM
        node_name: str = "drone_comm_hardware"
    ):
        super().__init__()
        self._lock = threading.RLock()

        # 数据缓存
        self._connected = False
        self._flight_mode: Optional[str] = None
        self._battery: Dict[str, float] = {}
        self._position: Optional[Dict] = None
        self._attitude: Optional[Dict] = None
        self._velocity: Optional[Dict] = None
        self._sensors: Dict = {}

        # 点云数据缓存
        self._pointcloud: Optional[List[Dict]] = None
        self._pointcloud_available = False
        self._pointcloud_seq = 0
        self.enable_pointcloud = enable_pointcloud
        self.max_pointcloud_points = max_pointcloud_points
        self._last_pointcloud_time = 0.0

        # 调试计数
        self._state_cb_count = 0
        self._battery_cb_count = 0
        self._pointcloud_cb_count = 0

        # 话题配置
        self.battery_topic = battery_topic
        self.state_topic = state_topic
        self.position_topic = position_topic
        self.imu_topic = imu_topic
        self.velocity_topic = velocity_topic
        self.pointcloud_topic = pointcloud_topic

        self._subscribers = []
        self._ros_available = False
        self._rospy = None
        self._spin_thread = None
        self._running = False
        self._spin_restart_count = 0

        # 初始化ROS
        self._init_ros(node_name)

        # 启动spin线程
        if self._ros_available:
            self._start_spin_thread()

    def _init_ros(self, node_name: str) -> None:
        """初始化ROS节点和订阅，所有异常都在内部捕获"""
        try:
            import rospy
            from sensor_msgs.msg import BatteryState, NavSatFix, Imu, PointCloud2
            from mavros_msgs.msg import State
            from geometry_msgs.msg import TwistStamped
            self._rospy = rospy
            print("[硬件] ROS模块导入成功")

            # 初始化节点
            if not rospy.core.is_initialized():
                rospy.init_node(node_name, anonymous=True, disable_signals=True)
                print(f"[硬件] ROS节点 {node_name} 初始化完成")
            else:
                print("[硬件] 检测到已有ROS环境，复用节点")

            # 逐个订阅话题，单个订阅失败不影响其他
            self._safe_subscribe(self.state_topic, State, self._state_cb, "飞控状态")
            self._safe_subscribe(self.battery_topic, BatteryState, self._battery_cb, "电池")
            self._safe_subscribe(self.position_topic, NavSatFix, self._position_cb, "位置")
            self._safe_subscribe(self.imu_topic, Imu, self._imu_cb, "IMU")
            self._safe_subscribe(self.velocity_topic, TwistStamped, self._velocity_cb, "速度")

            # 订阅点云话题
            if self.enable_pointcloud:
                self._safe_subscribe(self.pointcloud_topic, PointCloud2, self._pointcloud_cb, "点云")

            self._ros_available = True
            print(f"[硬件] 共订阅 {len(self._subscribers)} 个话题")

            # 等待首帧数据到达
            time.sleep(0.5)

        except ImportError as e:
            print(f"[硬件-警告] ROS依赖缺失: {e}，硬件数据不可用")
        except Exception as e:
            print(f"[硬件-错误] 初始化失败: {type(e).__name__}: {e}")

    def _safe_subscribe(self, topic: str, msg_type, callback, name: str) -> None:
        """安全订阅话题，异常不抛出"""
        try:
            sub = self._rospy.Subscriber(topic, msg_type, callback)
            self._subscribers.append(sub)
            print(f"[硬件] 已订阅{name}话题: {topic}")
        except Exception as e:
            print(f"[硬件-警告] {name}话题订阅失败: {e}")

    def _start_spin_thread(self) -> None:
        """启动独立的ROS spin线程，异常自动重启"""
        def _spin_loop():
            while self._running:
                try:
                    if not self._rospy.is_shutdown():
                        self._rospy.spin()
                except Exception as e:
                    self._spin_restart_count += 1
                    print(f"[硬件-错误] ROS spin异常，1秒后重启: {e}")
                    time.sleep(1)
                if self._running and not self._rospy.is_shutdown():
                    time.sleep(0.1)

        self._running = True
        self._spin_thread = threading.Thread(target=_spin_loop, daemon=True, name="ros-spin")
        self._spin_thread.start()

    # ========== 回调函数（全部带异常捕获） ==========
    def _state_cb(self, msg) -> None:
        try:
            with self._lock:
                self._flight_mode = msg.mode
                self._connected = msg.connected
                self._state_cb_count += 1
                if self._state_cb_count == 1:
                    print(f"[硬件-回调] 首次收到飞控状态 | 连接={msg.connected} 模式={msg.mode}")
        except Exception as e:
            self._record_sensor_error("state", e)

    def _battery_cb(self, msg) -> None:
        try:
            with self._lock:
                pct = msg.percentage
                if math.isnan(pct):
                    pct = 0.0
                elif pct <= 1.0:
                    pct = pct * 100

                # 数据校验
                pct = self._validate_value("battery_percent", pct, 0.0)
                voltage = self._validate_value("battery_voltage", msg.voltage, 0.0)
                current = self._validate_value("battery_current", msg.current, 0.0)

                self._battery = {
                    "percent": round(pct, 2),
                    "voltage": round(voltage, 2),
                    "current": round(current, 2)
                }
                self._battery_cb_count += 1
                if self._battery_cb_count == 1:
                    print(f"[硬件-回调] 首次收到电池数据 | 电量={self._battery['percent']}% 电压={self._battery['voltage']}V")
                self._connected = True
        except Exception as e:
            self._record_sensor_error("battery", e)

    def _position_cb(self, msg) -> None:
        try:
            with self._lock:
                lat = msg.latitude
                lon = msg.longitude
                alt = msg.altitude

                # 过滤无效定位数据
                if abs(lat) < 0.001 and abs(lon) < 0.001:
                    return
                if math.isnan(lat) or math.isnan(lon) or math.isnan(alt):
                    return

                # 数据范围校验
                lat = self._validate_value("latitude", lat)
                lon = self._validate_value("longitude", lon)
                alt = self._validate_value("altitude", alt)

                self._position = {"lat": lat, "lon": lon, "alt": alt}
                try:
                    self._sensors["gps_satellites"] = msg.status.service
                except Exception:
                    pass
                self._connected = True
        except Exception as e:
            self._record_sensor_error("position", e)

    def _imu_cb(self, msg) -> None:
        try:
            with self._lock:
                self._attitude = {
                    "x": msg.orientation.x,
                    "y": msg.orientation.y,
                    "z": msg.orientation.z,
                    "w": msg.orientation.w
                }
        except Exception as e:
            self._record_sensor_error("imu", e)

    def _velocity_cb(self, msg) -> None:
        try:
            with self._lock:
                vx = self._validate_value("velocity", msg.twist.linear.x, 0.0)
                vy = self._validate_value("velocity", msg.twist.linear.y, 0.0)
                vz = self._validate_value("velocity", msg.twist.linear.z, 0.0)
                self._velocity = {"vx": vx, "vy": vy, "vz": vz}
        except Exception as e:
            self._record_sensor_error("velocity", e)

    def _pointcloud_cb(self, msg) -> None:
        """点云消息回调 - 带数据量限制和异常捕获"""
        try:
            import sensor_msgs.point_cloud2 as pc2
            points = []
            count = 0
            field_names = ["x", "y", "z", "intensity"]

            for p in pc2.read_points(msg, field_names=field_names, skip_nans=True):
                if count >= self.max_pointcloud_points:
                    break
                # 过滤NaN点
                if any(math.isnan(v) for v in p[:3]):
                    continue
                points.append({
                    "x": float(p[0]),
                    "y": float(p[1]),
                    "z": float(p[2]),
                    "intensity": float(p[3]) if len(p) > 3 else 0.0
                })
                count += 1

            with self._lock:
                self._pointcloud = points
                self._pointcloud_available = True
                self._pointcloud_seq += 1
                self._last_pointcloud_time = time.time()
                self._pointcloud_cb_count += 1
                if self._pointcloud_cb_count == 1:
                    print(f"[硬件-回调] 首次收到点云数据 | 点数={len(points)} 帧ID={msg.header.frame_id}")
        except Exception as e:
            self._record_sensor_error("pointcloud", e)

    # ========== 对外读取接口 ==========
    def is_connected(self) -> bool:
        with self._lock:
            if not self._ros_available or self._rospy is None:
                return False
            try:
                return self._connected and not self._rospy.is_shutdown()
            except Exception:
                return False

    def get_flight_mode(self) -> Optional[str]:
        with self._lock:
            self._read_count += 1
            return self._flight_mode

    def get_battery_detail(self) -> Optional[Dict[str, float]]:
        with self._lock:
            self._read_count += 1
            if self._battery:
                return self._battery.copy()
            return {"percent": 0.0, "voltage": 0.0, "current": 0.0}

    def get_position(self) -> Optional[Dict]:
        with self._lock:
            self._read_count += 1
            return self._position

    def get_attitude(self) -> Optional[Dict[str, float]]:
        with self._lock:
            self._read_count += 1
            return self._attitude

    def get_velocity(self) -> Optional[Dict[str, float]]:
        with self._lock:
            self._read_count += 1
            return self._velocity

    def get_sensors(self) -> Optional[Dict]:
        with self._lock:
            self._read_count += 1
            return self._sensors.copy() if self._sensors else {}

    def get_pointcloud(self) -> Optional[List[Dict]]:
        """获取最新一帧点云数据
        超时5秒未收到新点云则返回None，避免发送过期数据
        """
        with self._lock:
            self._read_count += 1
            # 点云数据过期检查
            if self._pointcloud and (time.time() - self._last_pointcloud_time) > 5.0:
                self._pointcloud_available = False
                return None
            if self._pointcloud is not None:
                return list(self._pointcloud)
            return None

    def has_pointcloud(self) -> bool:
        """是否有新鲜的点云数据可用"""
        with self._lock:
            if not self.enable_pointcloud:
                return False
            if not self._pointcloud_available or self._pointcloud is None:
                return False
            # 5秒内的数据才算新鲜
            return (time.time() - self._last_pointcloud_time) <= 5.0

    def close(self) -> None:
        """安全关闭所有订阅和线程"""
        self._running = False
        for sub in self._subscribers:
            try:
                sub.unregister()
            except Exception:
                pass
        if self._spin_thread and self._spin_thread.is_alive():
            self._spin_thread.join(timeout=2.0)
