# -*- coding: utf-8 -*-
"""Runtime overlay patches for the PC ground-station app.

Only Hajimi-specific behavior lives here. The unchanged protocol, transport,
utility, and base UI/business modules continue to come from ``data_comm_pc``.
"""
import os
import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton


_PATCHED = False


def apply_hajimi_patches() -> None:
    global _PATCHED
    if _PATCHED:
        return

    _patch_config()
    _patch_ground_station()
    window_cls = _build_window_class()
    _patch_app_assembler(window_cls)

    _PATCHED = True


def _patch_config() -> None:
    from config.ground_station_config import GroundStationConfig

    if getattr(GroundStationConfig, "_hajimi_patched", False):
        return

    original_init = GroundStationConfig.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.listen_ip = os.getenv("GROUND_STATION_LISTEN_IP", self.listen_ip)
        self.allowed_drone_ip = os.getenv("GROUND_STATION_ALLOWED_DRONE_IP", "10.249.53.151")
        self.heartbeat_port = int(os.getenv("GROUND_STATION_HEARTBEAT_PORT", str(self.heartbeat_port)))
        self.data_port = int(os.getenv("GROUND_STATION_DATA_PORT", str(self.data_port)))
        self.buffer_size = int(os.getenv("GROUND_STATION_BUFFER_SIZE", str(self.buffer_size)))
        self.tcp_backlog = int(os.getenv("GROUND_STATION_TCP_BACKLOG", str(self.tcp_backlog)))
        self.heartbeat_timeout = float(
            os.getenv("GROUND_STATION_HEARTBEAT_TIMEOUT", str(self.heartbeat_timeout))
        )

    GroundStationConfig.__init__ = __init__
    GroundStationConfig._hajimi_patched = True


def _patch_ground_station() -> None:
    from business.ground_station import GroundStation

    if getattr(GroundStation, "_hajimi_patched", False):
        return

    original_heartbeat = GroundStation._on_heartbeat_message
    original_data = GroundStation._on_data_message

    def _is_allowed_drone(self, addr) -> bool:
        allowed_ip = getattr(self.config, "allowed_drone_ip", "").strip()
        if not allowed_ip:
            return True
        return addr[0] == allowed_ip

    def _on_heartbeat_message(self, raw_data, addr) -> None:
        if not self._is_allowed_drone(addr):
            return
        original_heartbeat(self, raw_data, addr)

    def _on_data_message(self, raw_data, addr) -> None:
        if not self._is_allowed_drone(addr):
            return
        original_data(self, raw_data, addr)

    GroundStation._is_allowed_drone = _is_allowed_drone
    GroundStation._on_heartbeat_message = _on_heartbeat_message
    GroundStation._on_data_message = _on_data_message
    GroundStation._hajimi_patched = True


def _build_window_class():
    import ui.main_window as main_window_module

    BaseWindow = main_window_module.GroundStationWindow
    if getattr(BaseWindow, "_hajimi_window", False):
        return BaseWindow

    class HajimiGroundStationWindow(BaseWindow):
        logout_requested = pyqtSignal()
        _hajimi_window = True

        def __init__(self, ground_station):
            self._logging_out = False
            super().__init__(ground_station)
            self._append_startup_info()

        def _set_global_style(self):
            super()._set_global_style()
            self.setStyleSheet(
                self.styleSheet()
                + """
                QPushButton#logoutButton {
                    background-color: #202c3f;
                    border: 1px solid #2f405a;
                    border-radius: 5px;
                    color: #d8e5f3;
                    font-weight: 600;
                    min-height: 24px;
                    padding: 2px 12px;
                }
                QPushButton#logoutButton:hover {
                    background-color: #2c3d56;
                    color: #ffffff;
                }
                """
            )

        def _init_ui(self):
            super()._init_ui()
            self.logout_button = QPushButton("退出登录")
            self.logout_button.setObjectName("logoutButton")
            self.logout_button.clicked.connect(self._request_logout)
            self.status_bar.addPermanentWidget(self.logout_button)

        def _append_startup_info(self):
            allowed_ip = getattr(self.gs.config, "allowed_drone_ip", "").strip() or "ALL"
            self._append_log(
                f"[监听] UDP {self.gs.config.heartbeat_port} / TCP {self.gs.config.data_port}",
                "#00d4ff",
            )
            self._append_log(f"[允许无人机] {allowed_ip}", "#00d4ff")

        def _request_logout(self):
            self._logging_out = True
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()
            self.logout_requested.emit()

        def closeEvent(self, event):
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()
            if not self._logging_out:
                self.gs.stop()
            event.accept()

    main_window_module.GroundStationWindow = HajimiGroundStationWindow
    return HajimiGroundStationWindow


def _patch_app_assembler(window_cls) -> None:
    import core.app_assembler as app_module
    from auth import MySQLUserRepository
    from business.ground_station import GroundStation
    from config.auth_config import AuthConfig
    from config.ground_station_config import GroundStationConfig
    from transport.factory import TransportFactory, TransportType
    from ui.login_dialog import LoginDialog

    AppAssembler = app_module.AppAssembler
    app_module.GroundStationWindow = window_cls

    if getattr(AppAssembler, "_hajimi_patched", False):
        return

    original_init = AppAssembler.__init__

    def __init__(self):
        original_init(self)
        self.auth_repository = None
        self.current_user = None

    def assemble(self) -> None:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        self.app = QApplication.instance() or QApplication(sys.argv)

        if self._authenticate():
            self._start_ground_station()

    def run(self) -> int:
        if not self.app:
            self.assemble()
        if not self.window:
            return 0
        return self.app.exec_()

    def shutdown(self) -> None:
        self._stop_ground_station()

    def _authenticate(self) -> bool:
        auth_config = AuthConfig()
        self.auth_repository = MySQLUserRepository(auth_config)
        try:
            self.auth_repository.initialize()
        except Exception as exc:
            QMessageBox.critical(
                None,
                "数据库连接失败",
                "无法初始化登录数据库。\n\n"
                f"MySQL: {auth_config.mysql_host}:{auth_config.mysql_port}\n"
                f"Database: {auth_config.mysql_database}\n"
                f"错误信息: {exc}",
            )
            return False

        dialog = LoginDialog(self.auth_repository)
        if dialog.exec_() != QDialog.Accepted:
            return False

        self.current_user = dialog.current_user
        return True

    def _start_ground_station(self) -> None:
        self.config = GroundStationConfig()

        hb_receiver = TransportFactory.create_receiver(
            transport_type=TransportType.UDP,
            port=self.config.heartbeat_port,
            buffer_size=self.config.buffer_size,
            listen_ip=self.config.listen_ip,
        )
        data_receiver = TransportFactory.create_receiver(
            transport_type=TransportType.TCP,
            port=self.config.data_port,
            buffer_size=self.config.buffer_size,
            listen_ip=self.config.listen_ip,
            backlog=self.config.tcp_backlog,
        )

        self.gs = GroundStation(self.config, hb_receiver, data_receiver)
        self.gs.start()

        self.window = window_cls(self.gs)
        self.window.logout_requested.connect(self._handle_logout)
        self.window.show()

    def _stop_ground_station(self) -> None:
        if self.gs:
            self.gs.stop()
            self.gs = None
        self.config = None

    def _handle_logout(self) -> None:
        old_window = self.window
        self.window = None
        if old_window:
            old_window.hide()
            old_window.deleteLater()

        self._stop_ground_station()
        self.current_user = None

        if self._authenticate():
            self._start_ground_station()
        elif self.app:
            self.app.quit()

    AppAssembler.__init__ = __init__
    AppAssembler.assemble = assemble
    AppAssembler.run = run
    AppAssembler.shutdown = shutdown
    AppAssembler._authenticate = _authenticate
    AppAssembler._start_ground_station = _start_ground_station
    AppAssembler._stop_ground_station = _stop_ground_station
    AppAssembler._handle_logout = _handle_logout
    AppAssembler._hajimi_patched = True
