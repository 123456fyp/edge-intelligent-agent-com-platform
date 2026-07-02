# -*- coding: utf-8 -*-
"""Application assembler for the ground-station process."""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

from auth import AuthUser, MySQLUserRepository
from business.ground_station import GroundStation
from config.auth_config import AuthConfig
from config.ground_station_config import GroundStationConfig
from transport.factory import TransportFactory, TransportType
from ui.login_dialog import LoginDialog
from ui.main_window import GroundStationWindow


class AppAssembler:
    """Create and wire the config, transport, business, auth, and UI layers."""

    def __init__(self):
        self.config: GroundStationConfig = None
        self.gs: GroundStation = None
        self.window: GroundStationWindow = None
        self.app: QApplication = None
        self.auth_repository: MySQLUserRepository = None
        self.current_user: AuthUser = None

    def assemble(self) -> None:
        """Initialize Qt, show login, then start the main application."""
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        self.app = QApplication.instance() or QApplication(sys.argv)

        if self._authenticate():
            self._start_ground_station()

    def run(self) -> int:
        """Start the Qt event loop and return the process exit code."""
        if not self.app:
            self.assemble()
        if not self.window:
            return 0
        return self.app.exec_()

    def shutdown(self) -> None:
        """Release application resources."""
        self._stop_ground_station()

    def _authenticate(self) -> bool:
        auth_config = AuthConfig()
        self.auth_repository = MySQLUserRepository(auth_config)
        try:
            self.auth_repository.initialize()
        except Exception as exc:
            QMessageBox.critical(
                None,
                "???????",
                "???????????\n\n"
                f"MySQL: {auth_config.mysql_host}:{auth_config.mysql_port}\n"
                f"Database: {auth_config.mysql_database}\n"
                f"????: {exc}",
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

        self.window = GroundStationWindow(self.gs)
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
