# -*- coding: utf-8 -*-
"""TCP 发送端传输实现"""

import socket
import threading
from typing import Optional

from .base_sender import TransportSender


class TCPTransportSender(TransportSender):
    """TCP 发送端

    面向连接、可靠传输，适合数据包这类不能丢的重要数据。
    内置自动重连 + 换行分帧（解决粘包问题）。
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
        self.bind_ip = bind_ip
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def _ensure_connected(self) -> bool:
        """确保 TCP 连接已建立，未连接则尝试连接"""
        if self._sock:
            return True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # 多网卡时指定源IP
            if self.bind_ip:
                self._sock.bind((self.bind_ip, 0))

            self._sock.connect(self.target)
            print(f"[TCP] 已连接 {self.target}")
            return True
        except (ConnectionRefusedError, OSError):
            self._sock = None
            return False

    def send(self, data: bytes) -> None:
        """通过 TCP 发送字节数据

        自动追加换行符作为帧分隔符，解决 TCP 粘包问题。
        连接断开时自动置空，下次发送时尝试重连。
        """
        with self._lock:
            if not self._ensure_connected():
                raise ConnectionError("TCP 未连接")
            try:
                self._sock.sendall(data + b"\n")
            except (BrokenPipeError, ConnectionResetError):
                self._sock.close()
                self._sock = None
                raise

    def close(self) -> None:
        """关闭 TCP 连接"""
        with self._lock:
            if self._sock:
                self._sock.close()
                self._sock = None
