# -*- coding: utf-8 -*-
"""UDP 接收端传输实现"""

import socket
import threading
from typing import Callable, Tuple

from .base_receiver import TransportReceiver


class UDPTransportReceiver(TransportReceiver):
    """UDP 接收端

    单线程循环接收，收到数据后回调业务层。
    适合心跳这类轻量、可容忍丢包的数据。
    """

    def __init__(self, port: int, buffer_size: int = 4096, listen_ip: str = "0.0.0.0"):
        """
        Args:
            port: 监听端口
            buffer_size: 接收缓冲区大小
            listen_ip: 监听IP，0.0.0.0表示所有网卡
        """
        self.port = port
        self.listen_ip = listen_ip
        self.buffer_size = buffer_size
        self._sock = None
        self._thread = None
        self._running = False

    def start(self, on_message: Callable[[bytes, Tuple[str, int]], None]) -> None:
        """启动 UDP 接收线程

        Args:
            on_message: 消息回调函数 (data_bytes, addr) -> None
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((self.listen_ip, self.port))
        self._running = True
        print(f"[UDP] 监听 {self.listen_ip}:{self.port}")

        def _loop():
            while self._running:
                try:
                    data, addr = self._sock.recvfrom(self.buffer_size)
                    on_message(data, addr)
                except Exception as e:
                    if self._running:
                        print(f"[UDP] 接收错误: {e}")

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        """停止 UDP 接收服务"""
        self._running = False
        if self._sock:
            self._sock.close()
