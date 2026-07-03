# -*- coding: utf-8 -*-
"""无人机硬件抽象基类 - 健壮性增强版
添加数据校验、错误隔离、健康状态统计
"""
import math
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from collections import deque


class DroneHardwareBase(ABC):
    """无人机硬件抽象基类 - 高可靠版
    所有读取方法都有默认值兜底，单个传感器异常不影响整体运行
    """

    def __init__(self, max_error_history: int = 50):
        # 错误统计
        self._read_count = 0
        self._error_count = 0
        self._sensor_errors: Dict[str, int] = {}
        self._last_error_time = 0.0
        self._error_history = deque(maxlen=max_error_history)

        # 数据有效性范围（可被子类覆盖）
        self.VALID_RANGES = {
            "battery_percent": (0.0, 100.0),
            "battery_voltage": (5.0, 26.0),  # 2S-6S锂电池
            "battery_current": (-100.0, 100.0),
            "latitude": (-90.0, 90.0),
            "longitude": (-180.0, 180.0),
            "altitude": (-100.0, 10000.0),
            "velocity": (-50.0, 50.0),  # m/s
        }

    def _validate_value(self, name: str, value: float, default: float = 0.0) -> float:
        """校验数值是否在合法范围内，异常值返回默认值"""
        if value is None:
            return default
        if math.isnan(value) or math.isinf(value):
            return default
        if name in self.VALID_RANGES:
            min_v, max_v = self.VALID_RANGES[name]
            if value < min_v or value > max_v:
                return default
        return value

    def _record_sensor_error(self, sensor_name: str, error: Exception) -> None:
        """记录传感器读取错误"""
        self._error_count += 1
        self._sensor_errors[sensor_name] = self._sensor_errors.get(sensor_name, 0) + 1
        self._last_error_time = time.time()
        self._error_history.append({
            "time": self._last_error_time,
            "sensor": sensor_name,
            "error": f"{type(error).__name__}: {str(error)}"
        })

    def get_hardware_health(self) -> Dict[str, Any]:
        """获取硬件层健康状态"""
        error_rate = self._error_count / max(1, self._read_count)
        return {
            "connected": self.is_connected(),
            "read_count": self._read_count,
            "error_count": self._error_count,
            "error_rate": round(error_rate, 4),
            "sensor_errors": dict(self._sensor_errors),
            "sensors_with_error": [k for k, v in self._sensor_errors.items() if v > 0]
        }

    @abstractmethod
    def is_connected(self) -> bool:
        """检查飞控是否正常连接"""
        pass

    @abstractmethod
    def get_flight_mode(self) -> Optional[str]:
        """读取飞行模式，读取失败返回 None"""
        pass

    @abstractmethod
    def get_battery_detail(self) -> Optional[Dict[str, float]]:
        """读取电池详情：电量百分比、电压、电流
        返回示例: {"percent": 85.2, "voltage": 11.8, "current": -2.3}
        """
        pass

    @abstractmethod
    def get_position(self) -> Optional[Dict]:
        """读取位置信息，读取失败返回 None"""
        pass

    @abstractmethod
    def get_attitude(self) -> Optional[Dict[str, float]]:
        """读取姿态角，读取失败返回 None"""
        pass

    @abstractmethod
    def get_velocity(self) -> Optional[Dict[str, float]]:
        """读取速度，读取失败返回 None"""
        pass

    @abstractmethod
    def get_sensors(self) -> Optional[Dict]:
        """读取传感器汇总数据，读取失败返回 None"""
        pass

    @abstractmethod
    def get_pointcloud(self) -> Optional[List[Dict]]:
        """读取点云数据，返回点列表或None
        返回示例: [{"x": 1.2, "y": 0.5, "z": -0.3, "intensity": 120}, ...]
        """
        pass

    @abstractmethod
    def has_pointcloud(self) -> bool:
        """是否有点云数据可用"""
        pass

    @abstractmethod
    def close(self) -> None:
        """释放硬件连接资源"""
        pass
