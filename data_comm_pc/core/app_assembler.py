# -*- coding: utf-8 -*-
"""应用组装器
统一负责各层对象的创建、依赖注入和生命周期管理，入口文件仅负责启动
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from config.ground_station_config import GroundStationConfig
from transport.factory import TransportFactory, TransportType
from business.ground_station import GroundStation
from ui.main_window import GroundStationWindow


class AppAssembler:
    """应用组装器：自底向上完成配置、传输、业务、UI各层的装配"""

    def __init__(self):
        self.config: GroundStationConfig = None
        self.gs: GroundStation = None
        self.window: GroundStationWindow = None
        self.app: QApplication = None

    def assemble(self) -> None:
        """按依赖顺序装配所有模块"""
        # 1. 加载配置层（最底层，无依赖）
        self.config = GroundStationConfig()

        # 2. 创建传输层（通过工厂创建，上层不感知具体UDP/TCP实现）
        hb_receiver = TransportFactory.create_receiver(
            transport_type=TransportType.UDP,
            port=self.config.heartbeat_port,
            buffer_size=self.config.buffer_size,
            listen_ip=self.config.listen_ip
        )
        data_receiver = TransportFactory.create_receiver(
            transport_type=TransportType.TCP,
            port=self.config.data_port,
            buffer_size=self.config.buffer_size,
            listen_ip=self.config.listen_ip,
            backlog=self.config.tcp_backlog
        )

        # 3. 创建业务层，注入配置和传输层抽象
        self.gs = GroundStation(self.config, hb_receiver, data_receiver)
        self.gs.start()

        # 4. 创建UI层：高DPI设置必须在QApplication实例化之前完成（修复原代码顺序bug）
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)  # 高DPI图标适配
        self.app = QApplication(sys.argv)
        self.window = GroundStationWindow(self.gs)
        self.window.show()

    def run(self) -> int:
        """启动应用事件循环，返回退出码"""
        if not self.app:
            self.assemble()
        return self.app.exec_()

    def shutdown(self) -> None:
        """优雅关闭应用，释放资源"""
        if self.gs:
            self.gs.stop()
