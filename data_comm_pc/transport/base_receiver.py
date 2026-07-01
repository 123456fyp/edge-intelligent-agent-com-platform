# -*- coding: utf-8 -*-
"""接收端传输抽象基类"""

from abc import ABC, abstractmethod
from typing import Callable, Tuple


class TransportReceiver(ABC):
    """接收端传输抽象接口

    业务层只依赖这个抽象，不关心具体传输方式。
    通过回调机制解耦：传输层收到数据后调用回调，业务层自己处理。
    """

    @abstractmethod
    def start(self, on_message: Callable[[bytes, Tuple[str, int]], None]) -> None:
        """启动接收服务

        Args:
            on_message: 收到消息后的回调函数
                        参数1: 消息字节数据
                        参数2: 对端地址 (ip, port)
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """停止接收服务，释放资源"""
        pass
