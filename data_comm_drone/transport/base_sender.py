# -*- coding: utf-8 -*-
"""发送端传输抽象基类 - 健壮性增强版
添加健康状态、错误统计、重连退避等通用接口
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any
from collections import deque


class TransportSender(ABC):
    """发送端传输抽象接口

    业务层只依赖这个抽象，不关心具体是 UDP、TCP、串口还是其他。
    内置错误统计、健康状态、指数退避重连等通用健壮性机制。
    """

    def __init__(self, max_error_history: int = 100):
        # 错误统计
        self._send_count = 0
        self._success_count = 0
        self._error_count = 0
        self._last_error_time = 0.0
        self._last_error_msg = ""
        self._consecutive_errors = 0
        self._error_history = deque(maxlen=max_error_history)

        # 重连退避参数
        self._reconnect_count = 0
        self._max_reconnect_interval = 30.0  # 最大重连间隔30秒
        self._base_reconnect_interval = 0.5  # 初始重连间隔0.5秒

        # 状态
        self._connected = False
        self._closed = False

    def _calc_backoff(self) -> float:
        """计算指数退避重连等待时间"""
        interval = min(
            self._base_reconnect_interval * (2 ** min(self._reconnect_count, 8)),
            self._max_reconnect_interval
        )
        return interval

    def _record_success(self) -> None:
        """记录发送成功"""
        self._send_count += 1
        self._success_count += 1
        self._consecutive_errors = 0
        self._reconnect_count = 0

    def _record_error(self, error: Exception) -> None:
        """记录发送错误"""
        self._send_count += 1
        self._error_count += 1
        self._consecutive_errors += 1
        self._last_error_time = time.time()
        self._last_error_msg = f"{type(error).__name__}: {str(error)}"
        self._error_history.append({
            "time": self._last_error_time,
            "error": self._last_error_msg
        })

    def get_health_status(self) -> Dict[str, Any]:
        """获取传输通道健康状态"""
        success_rate = self._success_count / max(1, self._send_count)
        return {
            "connected": self._connected,
            "closed": self._closed,
            "send_count": self._send_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "consecutive_errors": self._consecutive_errors,
            "success_rate": round(success_rate, 4),
            "last_error": self._last_error_msg if self._last_error_msg else None,
            "reconnect_count": self._reconnect_count
        }

    def is_healthy(self, error_threshold: int = 10) -> bool:
        """通道是否健康
        连续错误数超过阈值则判定为不健康
        """
        return self._connected and self._consecutive_errors < error_threshold

    @abstractmethod
    def send(self, data: bytes, timeout: float = 5.0) -> None:
        """发送原始字节数据

        Args:
            data: 要发送的原始字节数据
            timeout: 发送超时时间（秒）

        Raises:
            ConnectionError: 连接异常时抛出，由上层处理
            TimeoutError: 发送超时时抛出
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭传输通道，释放资源"""
        pass
