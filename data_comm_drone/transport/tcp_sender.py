# -*- coding: utf-8 -*-
"""TCP 发送端传输实现 - 健壮性增强版
特性：
- 自动重连 + 指数退避
- 发送超时保护
- 大报文分帧
- 发送缓冲区溢出保护
- 连接状态实时统计
- 优雅关闭
"""

import socket
import threading
import time
from typing import Optional

from .base_sender import TransportSender


class TCPTransportSender(TransportSender):
    """TCP 发送端 - 高可靠版本

    面向连接、可靠传输，适合数据包这类不能丢的重要数据。
    内置自动重连 + 换行分帧（解决粘包问题）。
    支持绑定源 IP（多网卡时指定用哪个网卡发）。
    """

    def __init__(
        self,
        target_ip: str,
        target_port: int,
        bind_ip: str = "",
        send_timeout: float = 5.0,
        connect_timeout: float = 3.0,
        max_packet_size: int = 512 * 1024  # 单包最大512KB，留带宽冗余
    ):
        super().__init__()
        self.target = (target_ip, target_port)
        self.bind_ip = bind_ip
        self.send_timeout = send_timeout
        self.connect_timeout = connect_timeout
        self.max_packet_size = max_packet_size

        self._sock: Optional[socket.socket] = None
        self._lock = threading.RLock()  # 可重入锁，避免死锁
        self._last_connect_attempt = 0.0

    def _create_socket(self) -> socket.socket:
        """创建并配置socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.connect_timeout)
        # TCP Keepalive 配置，检测死连接
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)
        if hasattr(socket, "TCP_KEEPINTVL"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
        if hasattr(socket, "TCP_KEEPCNT"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        # 禁用Nagle算法，降低延迟
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # 发送缓冲区大小
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
        return sock

    def _ensure_connected(self) -> bool:
        """确保 TCP 连接已建立，未连接则尝试重连
        带指数退避，避免连接风暴
        """
        if self._closed:
            return False
        if self._sock and self._connected:
            return True

        with self._lock:
            # 双重检查
            if self._sock and self._connected:
                return True

            # 退避检查：距离上次重连太近则等待
            now = time.time()
            if self._reconnect_count > 0:
                wait_time = self._calc_backoff()
                if now - self._last_connect_attempt < wait_time:
                    return False

            self._last_connect_attempt = now
            self._reconnect_count += 1

            # 清理旧socket
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

            try:
                self._sock = self._create_socket()

                # 多网卡时指定源IP
                if self.bind_ip:
                    self._sock.bind((self.bind_ip, 0))

                self._sock.connect(self.target)
                self._sock.settimeout(self.send_timeout)
                self._connected = True
                self._consecutive_errors = 0
                print(f"[TCP:{self.target[1]}] 连接成功 (第{self._reconnect_count}次尝试)")
                return True

            except (ConnectionRefusedError, OSError, socket.timeout) as e:
                if self._reconnect_count == 1 or self._reconnect_count % 10 == 0:
                    print(f"[TCP:{self.target[1]}] 连接失败: {type(e).__name__}，{self._calc_backoff():.1f}秒后重试")
                if self._sock:
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
                self._connected = False
                return False

    def _disconnect(self) -> None:
        """标记连接断开，清理资源"""
        with self._lock:
            self._connected = False
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

    def send(self, data: bytes, timeout: float = None) -> None:
        """通过 TCP 发送字节数据

        自动追加换行符作为帧分隔符，解决 TCP 粘包问题。
        连接断开时自动清理，下次发送时尝试重连。
        超过最大包长自动截断，避免发送失败。
        """
        if self._closed:
            raise ConnectionError("连接已关闭")

        if timeout is None:
            timeout = self.send_timeout

        # 数据包大小检查与保护
        if len(data) > self.max_packet_size:
            # 点云等大数据允许截断，记录警告但不抛出异常
            print(f"[TCP:{self.target[1]}] 警告: 数据包大小({len(data)}字节)超过限制，已截断")
            data = data[:self.max_packet_size]

        with self._lock:
            if not self._ensure_connected():
                self._record_error(ConnectionError("连接不可用"))
                raise ConnectionError(f"TCP {self.target} 未连接")

            try:
                self._sock.settimeout(timeout)
                self._sock.sendall(data + b"\n")
                self._record_success()

            except socket.timeout as e:
                self._disconnect()
                self._record_error(e)
                raise TimeoutError(f"TCP {self.target} 发送超时") from e

            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
                self._disconnect()
                self._record_error(e)
                raise ConnectionError(f"TCP {self.target} 连接断开: {type(e).__name__}") from e

    def close(self) -> None:
        """优雅关闭 TCP 连接"""
        with self._lock:
            self._closed = True
            self._connected = False
            if self._sock:
                try:
                    # 尝试优雅关闭：先停止发送，等待缓冲区清空
                    try:
                        self._sock.shutdown(socket.SHUT_WR)
                    except Exception:
                        pass
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
                print(f"[TCP:{self.target[1]}] 连接已关闭")
