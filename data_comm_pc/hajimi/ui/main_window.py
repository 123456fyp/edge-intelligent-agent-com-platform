# -*- coding: utf-8 -*-
"""
Qt5 ?????? - UI?
?????????????????????? business ???
"""
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QFormLayout, QLabel, QTextEdit, QSplitter,
    QStatusBar, QGroupBox, QPushButton
)
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from business.ground_station import GroundStation


class GroundStationWindow(QMainWindow):
    logout_requested = pyqtSignal()

    def __init__(self, ground_station: GroundStation):
        super().__init__()
        self.gs = ground_station
        self._logging_out = False
        self.setWindowTitle("?????? v1.0")
        self.resize(1280, 760)

        self._set_global_style()
        self._init_ui()
        self._append_startup_info()

        # ??????????????
        self.gs.sig_drone_online.connect(self._on_drone_online)
        self.gs.sig_drone_offline.connect(self._on_drone_offline)
        self.gs.sig_data_updated.connect(self._on_data_updated)

        # ???????1?????????????
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._check_offline)
        self.refresh_timer.start(1000)

    def _on_drone_online(self, drone_id: str):
        """??????????+??"""
        self.drone_list.addItem(drone_id)
        self._append_log(f"[??] ??? {drone_id} ???", "#39d353")
        # ?????????
        if self.drone_list.count() == 1:
            self.drone_list.setCurrentRow(0)

    def _on_drone_offline(self, drone_id: str):
        """?????????? + ??? + ??????????????"""
        # ??????????ID
        current_item = self.drone_list.currentItem()
        current_selected_id = current_item.text() if current_item else None

        # 1. ?????????????
        for i in range(self.drone_list.count()):
            if self.drone_list.item(i).text() == drone_id:
                self.drone_list.takeItem(i)
                break

        # 2. ??????
        self._append_log(f"[??] ??? {drone_id} ?????", "#ff6b6b")

        # 3. ?????????????????????????
        if current_selected_id == drone_id:
            self._clear_drone_detail()

    def _on_data_updated(self, drone_id: str):
        """??????????????????????"""
        current_item = self.drone_list.currentItem()
        if current_item and current_item.text() == drone_id:
            self._update_drone_detail(drone_id)

    def _check_offline(self):
        """????????????"""
        self.gs.check_offline_drones()
        # ?????
        self.status_bar.showMessage(
            f"  ?????{self.drone_list.count()} ?  |  ?????UDP {self.gs.config.heartbeat_port}  |  ?????TCP {self.gs.config.data_port}"
        )

    def _clear_drone_detail(self):
        """?????????????????"""
        # ??????????
        self.status_label.setText("? ???")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 14px;")

        # ????????????
        for label in self.detail_labels.values():
            label.setText("-")

        # ????JSON????
        self.json_view.clear()

    def _set_global_style(self):
        """??????????"""
        style = """
        QMainWindow, QWidget {
            background-color: #12161f;
            color: #e0e6ed;
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            font-size: 13px;
        }
        QGroupBox {
            border: 1px solid #2a3447;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 8px;
            background-color: #181d29;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #00d4ff;
            font-weight: 600;
            letter-spacing: 1px;
        }
        QListWidget {
            background-color: #0f131b;
            border: 1px solid #2a3447;
            border-radius: 4px;
            outline: none;
        }
        QListWidget::item {
            padding: 9px 8px;
            border-bottom: 1px solid #1f2736;
        }
        QListWidget::item:selected {
            background-color: #1e3a5f;
            color: #00d4ff;
        }
        QTextEdit {
            background-color: #0f131b;
            border: 1px solid #2a3447;
            border-radius: 4px;
            color: #c9d1d9;
        }
        QStatusBar {
            background-color: #0f131b;
            border-top: 1px solid #2a3447;
            color: #8b949e;
        }
        QSplitter::handle {
            background-color: #2a3447;
            width: 1px;
            height: 1px;
        }
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
        self.setStyleSheet(style)

    def _init_ui(self):
        """??????"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ========== ???????? ==========
        left_box = QGroupBox("????")
        left_layout = QVBoxLayout(left_box)
        self.drone_list = QListWidget()
        self.drone_list.currentItemChanged.connect(self._on_drone_selected)
        left_layout.addWidget(self.drone_list)
        left_box.setFixedWidth(220)

        # ========== ????? + JSON + ?? ==========
        right_splitter = QSplitter(Qt.Vertical)

        # ?????????
        detail_box = QGroupBox("??????")
        detail_layout = QFormLayout(detail_box)
        detail_layout.setLabelAlignment(Qt.AlignRight)
        detail_layout.setVerticalSpacing(9)
        detail_layout.setHorizontalSpacing(16)

        # ??????????
        self.status_label = QLabel("? ???")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 14px;")
        detail_layout.addRow("????:", self.status_label)

        self.detail_labels = {
            "drone_id": QLabel("-"),
            "seq": QLabel("-"),
            "mode": QLabel("-"),
            "battery_percent": QLabel("-"),
            "battery_voltage": QLabel("-"),
            "lat": QLabel("-"),
            "lon": QLabel("-"),
            "alt": QLabel("-"),
            "roll": QLabel("-"),
            "pitch": QLabel("-"),
            "yaw": QLabel("-"),
        }

        # ????????
        highlight_style = "color: #00d4ff; font-weight: 500;"
        self.detail_labels["battery_percent"].setStyleSheet(highlight_style)
        self.detail_labels["alt"].setStyleSheet(highlight_style)
        self.detail_labels["mode"].setStyleSheet(highlight_style)

        detail_layout.addRow("???ID:", self.detail_labels["drone_id"])
        #detail_layout.addRow("????:", self.detail_labels["seq"])
        detail_layout.addRow("????:", self.detail_labels["mode"])
        detail_layout.addRow("????:", self.detail_labels["battery_percent"])
        detail_layout.addRow("????:", self.detail_labels["battery_voltage"])
        detail_layout.addRow("??:", self.detail_labels["lat"])
        detail_layout.addRow("??:", self.detail_labels["lon"])
        detail_layout.addRow("????:", self.detail_labels["alt"])
        detail_layout.addRow("???:", self.detail_labels["roll"])
        detail_layout.addRow("???:", self.detail_labels["pitch"])
        detail_layout.addRow("???:", self.detail_labels["yaw"])

        right_splitter.addWidget(detail_box)

        # ?????JSON??
        json_box = QGroupBox("?? JSON ??")
        json_layout = QVBoxLayout(json_box)
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setFont(QFont("Consolas", 9))
        json_layout.addWidget(self.json_view)
        right_splitter.addWidget(json_box)

        # ???????
        log_box = QGroupBox("????")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Microsoft YaHei", 9))
        log_layout.addWidget(self.log_view)
        right_splitter.addWidget(log_box)

        # ????
        right_splitter.setSizes([260, 240, 200])

        # ?????
        main_layout.addWidget(left_box)
        main_layout.addWidget(right_splitter, 1)

        # ?????
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.logout_button = QPushButton("????")
        self.logout_button.setObjectName("logoutButton")
        self.logout_button.clicked.connect(self._request_logout)
        self.status_bar.addPermanentWidget(self.logout_button)

    def _refresh_ui(self):
        """?????????????????"""
        # 1. ???????
        offline_drones = self.gs.check_offline_drones()
        for drone_id in offline_drones:
            self._append_log(f"[??] ??? {drone_id} ?????", "#ff6b6b")

        # 2. ???????????????????
        online_ids = self.gs.get_online_ids()
        current_count = self.drone_list.count()
        if len(online_ids) != current_count:
            # ???????????????????????????
            self.drone_list.clear()
            for drone_id in online_ids:
                self.drone_list.addItem(drone_id)
                self._append_log(f"[??] ??? {drone_id} ???", "#39d353")

        # 3. ????????????
        current_item = self.drone_list.currentItem()
        if current_item:
            self._update_drone_detail(current_item.text())

        # 4. ???
        self.status_bar.showMessage(
            f"  ?????{self.drone_list.count()} ?  |  ?????UDP {self.gs.config.heartbeat_port}  |  ?????TCP {self.gs.config.data_port}"
        )

    def _on_drone_selected(self, current, previous):
        if current:
            self._update_drone_detail(current.text())

    def _update_drone_detail(self, drone_id):
        # 1. ??????
        online_ids = self.gs.get_online_ids()
        if drone_id in online_ids:
            self.status_label.setText("? ???")
            self.status_label.setStyleSheet("color: #39d353; font-weight: 600; font-size: 14px;")
        else:
            self.status_label.setText("? ???")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 14px;")

        # 2. ???????????/????? ???????
        status = self.gs.get_drone_status(drone_id)
        if not status:
            self._clear_drone_detail()
            return

        # 3. ????????????????
        self.detail_labels["drone_id"].setText(drone_id)
        self.detail_labels["seq"].setText(str(status.get("seq", "-")))
        self.detail_labels["mode"].setText(status.get("mode", "-"))

        battery = status.get("battery", {})
        self.detail_labels["battery_percent"].setText(f"{battery.get('percent', '-')} %")
        self.detail_labels["battery_voltage"].setText(f"{battery.get('voltage', '-')} V")

        position = status.get("position", {})
        lat = position.get("lat", "-")
        lon = position.get("lon", "-")
        alt = position.get("alt", "-")
        self.detail_labels["lat"].setText(f"{lat:.6f}" if lat != "-" else "-")
        self.detail_labels["lon"].setText(f"{lon:.6f}" if lon != "-" else "-")
        self.detail_labels["alt"].setText(f"{alt:.2f} m" if alt != "-" else "- m")

        attitude = status.get("attitude", {})
        roll = attitude.get("roll", "-")
        pitch = attitude.get("pitch", "-")
        yaw = attitude.get("yaw", "-")
        self.detail_labels["roll"].setText(f"{roll:.2f} ?" if roll != "-" else "- ?")
        self.detail_labels["pitch"].setText(f"{pitch:.2f} ?" if pitch != "-" else "- ?")
        self.detail_labels["yaw"].setText(f"{yaw:.2f} ?" if yaw != "-" else "- ?")

        # JSON??????????????????
        self.json_view.setPlainText(
            json.dumps(status, indent=2, ensure_ascii=False)
        )

    def _append_log(self, text: str, color: str = "#c9d1d9"):
        """?????????????/??/????"""
        html = f'<span style="color: {color};">{text}</span>'
        self.log_view.append(html)
        # ???????
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def _append_startup_info(self):
        allowed_ip = getattr(self.gs.config, "allowed_drone_ip", "").strip() or "ALL"
        self._append_log(
            f"[??] UDP {self.gs.config.heartbeat_port} / TCP {self.gs.config.data_port}",
            "#00d4ff",
        )
        self._append_log(f"[?????] {allowed_ip}", "#00d4ff")

    def _request_logout(self):
        self._logging_out = True
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        self.logout_requested.emit()

    def closeEvent(self, event):
        """??????????????"""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        if not self._logging_out:
            self.gs.stop()
        event.accept()
