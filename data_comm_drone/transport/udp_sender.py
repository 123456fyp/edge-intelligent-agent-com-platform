# -*- coding: utf-8 -*-
"""UDP 发送端传输实现"""

import socket

from .base_sender import TransportSender


class UDPTransportSender(TransportSender):
    """UDP 发送端

    无连接、低开销，适合心跳这类可容忍丢包的轻量数据。
    支持绑定源 IP（多网卡时指定用哪个网卡发）。
    """

    def __init__(self, target_ip: str, target_port: int, bind_ip: str = ""):
        """
        Args:
            target_ip: 目标IP地址（接收方的IP）
            target_port: 目标端口
            bind_ip: 绑定源IP，多网卡时指定用哪个网卡发；空字符串表示不绑定
        """
        self.target = (target_ip, target_port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 多网卡时指定源IP
        if bind_ip:
            self._sock.bind((bind_ip, 0))  # 端口0表示系统自动分配

    def send(self, data: bytes) -> None:
        """通过 UDP 发送字节数据"""
        self._sock.sendto(data, self.target)

    def close(self) -> None:
        """关闭 UDP socket"""
        self._sock.close()
