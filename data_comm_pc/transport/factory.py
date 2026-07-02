# -*- coding: utf-8 -*-
"""传输层工厂类
统一创建传输接收器实例，上层仅依赖抽象接口，无需感知具体实现
"""
from typing import Any

from .base_receiver import TransportReceiver
from .udp_receiver import UDPTransportReceiver
from .tcp_receiver import TCPTransportReceiver


class TransportType:
    """传输类型常量"""
    UDP = "udp"
    TCP = "tcp"


class TransportFactory:
    """传输接收器工厂"""

    @staticmethod
    def create_receiver(
        transport_type: str,
        port: int,
        buffer_size: int,
        listen_ip: str = "0.0.0.0",
        **kwargs: Any
    ) -> TransportReceiver:
        """
        创建对应类型的传输接收器
        Args:
            transport_type: 传输类型，见TransportType常量
            port: 监听端口
            buffer_size: 接收缓冲区大小
            listen_ip: 监听IP
            **kwargs: 不同传输类型的额外参数，如TCP需要backlog
        Returns:
            TransportReceiver抽象实例
        """
        if transport_type == TransportType.UDP:
            return UDPTransportReceiver(
                port=port,
                buffer_size=buffer_size,
                listen_ip=listen_ip
            )
        elif transport_type == TransportType.TCP:
            return TCPTransportReceiver(
                port=port,
                buffer_size=buffer_size,
                listen_ip=listen_ip,
                backlog=kwargs.get("backlog", 5)
            )
        else:
            raise ValueError(f"不支持的传输类型: {transport_type}，支持类型: {TransportType.UDP}, {TransportType.TCP}")
