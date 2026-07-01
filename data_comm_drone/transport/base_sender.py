# -*- coding: utf-8 -*-
"""发送端传输抽象基类"""

from abc import ABC, abstractmethod


class TransportSender(ABC):
    """发送端传输抽象接口

    业务层只依赖这个抽象，不关心具体是 UDP、TCP、串口还是其他。
    """

    @abstractmethod
    def send(self, data: bytes) -> None:
        """发送原始字节数据

        Args:
            data: 要发送的原始字节数据

        Raises:
            ConnectionError: 连接异常时抛出，由上层处理
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭传输通道，释放资源"""
        pass
