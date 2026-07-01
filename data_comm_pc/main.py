# -*- coding: utf-8 -*-
"""
地面站程序入口
负责组装配置、传输层、业务层、UI层，启动程序
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from config.ground_station_config import GroundStationConfig
from transport.udp_receiver import UDPTransportReceiver
from transport.tcp_receiver import TCPTransportReceiver
from business.ground_station import GroundStation
from ui.main_window import GroundStationWindow


def main():
    # 1. 加载配置
    config = GroundStationConfig()

    # 2. 组装传输层
    hb_receiver = UDPTransportReceiver(
        port=config.heartbeat_port,
        buffer_size=config.buffer_size,
        listen_ip=config.listen_ip
    )
    data_receiver = TCPTransportReceiver(
        port=config.data_port,
        buffer_size=config.buffer_size,
        backlog=config.tcp_backlog,
        listen_ip=config.listen_ip
    )

    # 3. 组装业务层
    gs = GroundStation(config, hb_receiver, data_receiver)
    gs.start()

    # 4. 组装UI层，注入业务层实例
    app = QApplication(sys.argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    window = GroundStationWindow(gs)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()