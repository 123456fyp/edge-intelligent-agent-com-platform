# -*- coding: utf-8 -*-
"""无人机硬件抽象基类
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict


class DroneHardwareBase(ABC):
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
    def close(self) -> None:
        """释放硬件连接资源"""
        pass