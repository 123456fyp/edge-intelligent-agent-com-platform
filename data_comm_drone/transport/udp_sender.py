# -*- coding: utf-8 -*-
"""UDP 发送端传输实现 - 健壮性增强版
特性：
- 发送超时保护
- 数据包大小检查
- socket异常捕获
- 发送错误统计
"""

import socket
from typing import Optional

from .base_sender import TransportSender


class UDPTransportSender(TransportSender):
    """UDP 发送端 - 健壮版

    无连接、低开销，适合心跳这类可容忍丢包的轻量数据。
    支持绑定源 IP（多网卡时指定用哪个网卡发）。
    """

    # UDP最大安全MTU（避免IP分片）
    MAX_UDP_PACKET_SIZE = 65507

    def __init__(
        self,
        target_ip: str,
        target_port: int,
        bind_ip: str = "",
        send_timeout: float = 2.0
    ):
        super().__init__()
        self.target = (target_ip, target_port)
        self.bind_ip = bind_ip
        self.send_timeout = send_timeout

        self._sock: Optional[socket.socket] = None
        self._init_socket()

    def _init_socket(self) -> None:
        """初始化并配置socket"""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(self.send_timeout)
            # 发送缓冲区
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            # 允许广播
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # 多网卡时指定源IP
            if self.bind_ip:
                self._sock.bind((self.bind_ip, 0))  # 端口0表示系统自动分配

            self._connected = True
        except OSError as e:
            self._record_error(e)
            self._connected = False
            print(f"[UDP:{self.target[1]}] Socket初始化失败: {e}")

    def send(self, data: bytes, timeout: float = None) -> None:
        """通过 UDP 发送字节数据
        数据包过大自动截断，避免发送失败
        """
        if self._closed:
            raise ConnectionError("Socket已关闭")

        if self._sock is None:
            self._init_socket()
            if self._sock is None:
                self._record_error(ConnectionError("Socket不可用"))
                raise ConnectionError(f"UDP {self.target} Socket不可用")

        if timeout is not None:
            self._sock.settimeout(timeout)

        # UDP数据包大小保护
        if len(data) > self.MAX_UDP_PACKET_SIZE:
            data = data[:self.MAX_UDP_PACKET_SIZE]

        try:
            self._sock.sendto(data, self.target)
            self._record_success()
        except (OSError, socket.timeout) as e:
            self._record_error(e)
            # UDP无连接，单次失败不标记断开，只统计错误
            if self._consecutive_errors % 50 == 0 and self._consecutive_errors > 0:
                print(f"[UDP:{self.target[1]}] 发送失败次数: {self._consecutive_errors}, 错误: {e}")
            raise ConnectionError(f"UDP {self.target} 发送失败: {e}") from e

    def close(self) -> None:
        """优雅关闭 UDP socket"""
        self._closed = True
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
