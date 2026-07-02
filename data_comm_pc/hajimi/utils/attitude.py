# -*- coding: utf-8 -*-
"""姿态解算工具集
独立算法模块，可被业务层、UI层复用
"""
import math
from typing import Tuple


def quaternion_to_euler(x: float, y: float, z: float, w: float) -> Tuple[float, float, float]:
    """四元数转欧拉角（ZYX 内旋顺序，单位：度）

    Args:
        x, y, z, w: 四元数分量

    Returns:
        (roll, pitch, yaw) 横滚角、俯仰角、偏航角，单位为度
    """
    # 横滚角 roll (x轴)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # 俯仰角 pitch (y轴)
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    # 偏航角 yaw (z轴)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)