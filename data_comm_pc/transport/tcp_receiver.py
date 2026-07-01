# -*- coding: utf-8 -*-
"""TCP 接收端传输实现"""

import socket
import threading
from typing import Callable, Tuple, Dict

from .base_receiver import TransportReceiver


class TCPTransportReceiver(TransportReceiver):
    """TCP 接收端

    支持多客户端同时连接，每个客户端独立线程处理。
    内置换行分帧（解决 TCP 粘包问题）。
    适合数据包这类不能丢的重要数据。
    """

    def __init__(self, port: int, buffer_size: int = 4096, backlog: int = 5, listen_ip: str = "0.0.0.0"):
        """
        Args:
            port: 监听端口
            buffer_size: 接收缓冲区大小
            backlog: TCP 监听队列长度
            listen_ip: 监听IP，0.0.0.0表示所有网卡
        """
        self.port = port
        self.listen_ip = listen_ip
        self.buffer_size = buffer_size
        self.backlog = backlog
        self._sock = None
        self._thread = None
        self._running = False
        self._clients: Dict[Tuple[str, int], socket.socket] = {}

    def start(self, on_message: Callable[[bytes, Tuple[str, int]], None]) -> None:
        """启动 TCP 接收服务

        主线程 accept 新连接，每个客户端分配一个子线程处理。

        Args:
            on_message: 消息回调函数 (data_bytes, addr) -> None
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.listen_ip, self.port))
        self._sock.listen(self.backlog)
        self._running = True
        print(f"[TCP] 监听 {self.listen_ip}:{self.port}")

        def _handle_client(conn: socket.socket, addr: Tuple[str, int]):
            """处理单个客户端连接"""
            buffer = b""
            self._clients[addr] = conn
            print(f"[TCP] 新连接: {addr}")
            try:
                while self._running:
                    data = conn.recv(self.buffer_size)
                    if not data:
                        break
                    buffer += data
                    # 按换行符分帧，解决粘包
                    while b"\n" in buffer:
                        frame, buffer = buffer.split(b"\n", 1)
                        if frame:
                            on_message(frame, addr)
            except (ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                conn.close()
                self._clients.pop(addr, None)
                print(f"[TCP] 连接断开: {addr}")

        def _accept_loop():
            """accept 循环，持续接收新连接"""
            while self._running:
                try:
                    conn, addr = self._sock.accept()
                    t = threading.Thread(
                        target=_handle_client,
                        args=(conn, addr),
                        daemon=True
                    )
                    t.start()
                except OSError:
                    break

        self._thread = threading.Thread(target=_accept_loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        """停止 TCP 接收服务，关闭所有客户端连接"""
        self._running = False
        for conn in self._clients.values():
            conn.close()
        if self._sock:
            self._sock.close()
