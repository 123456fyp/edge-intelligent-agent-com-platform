# -*- coding: utf-8 -*-
"""
Qt5 地面站主窗口 - UI层
科技深色主题，可视化连接状态，所有业务数据从 business 层获取
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
        self.setWindowTitle("无人机地面站 v1.0")
        self.resize(1280, 760)

        self._set_global_style()
        self._init_ui()
        self._append_startup_info()

        # 绑定业务层信号，事件驱动刷新
        self.gs.sig_drone_online.connect(self._on_drone_online)
        self.gs.sig_drone_offline.connect(self._on_drone_offline)
        self.gs.sig_data_updated.connect(self._on_data_updated)

        # 定时器仅做每秒1次的离线巡检，不再轮询数据
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._check_offline)
        self.refresh_timer.start(1000)

    def _on_drone_online(self, drone_id: str):
        """设备上线：添加到列表+日志"""
        self.drone_list.addItem(drone_id)
        self._append_log(f"[上线] 无人机 {drone_id} 已接入", "#39d353")
        # 默认选中第一个设备
        if self.drone_list.count() == 1:
            self.drone_list.setCurrentRow(0)

    def _on_drone_offline(self, drone_id: str):
        """设备离线：移除列表项 + 打日志 + 若当前在显示该设备则清空详情"""
        # 先获取当前选中的设备ID
        current_item = self.drone_list.currentItem()
        current_selected_id = current_item.text() if current_item else None

        # 1. 从设备列表中移除该离线设备
        for i in range(self.drone_list.count()):
            if self.drone_list.item(i).text() == drone_id:
                self.drone_list.takeItem(i)
                break

        # 2. 记录离线日志
        self._append_log(f"[离线] 无人机 {drone_id} 已断开连接", "#ff6b6b")

        # 3. 核心：只有当前显示的是这台离线设备，才清空详情面板
        if current_selected_id == drone_id:
            self._clear_drone_detail()

    def _on_data_updated(self, drone_id: str):
        """数据更新：只刷新当前选中的设备，避免无效渲染"""
        current_item = self.drone_list.currentItem()
        if current_item and current_item.text() == drone_id:
            self._update_drone_detail(drone_id)

    def _check_offline(self):
        """定时器触发：检查离线设备"""
        self.gs.check_offline_drones()
        # 更新状态栏
        self.status_bar.showMessage(
            f"  在线设备：{self.drone_list.count()} 架  |  心跳监听：UDP {self.gs.config.heartbeat_port}  |  数据监听：TCP {self.gs.config.data_port}"
        )

    def _clear_drone_detail(self):
        """清空所有详情数据，恢复界面初始状态"""
        # 连接状态重置为未连接
        self.status_label.setText("● 未连接")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 14px;")

        # 所有状态字段重置为初始值
        for label in self.detail_labels.values():
            label.setText("-")

        # 清空原始JSON报文区域
        self.json_view.clear()

    def _set_global_style(self):
        """全局科技深色主题样式"""
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
        """构建界面布局"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ========== 左侧：无人机列表 ==========
        left_box = QGroupBox("设备列表")
        left_layout = QVBoxLayout(left_box)
        self.drone_list = QListWidget()
        self.drone_list.currentItemChanged.connect(self._on_drone_selected)
        left_layout.addWidget(self.drone_list)
        left_box.setFixedWidth(220)

        # ========== 右侧：详情 + JSON + 日志 ==========
        right_splitter = QSplitter(Qt.Vertical)

        # 右上：飞行状态详情
        detail_box = QGroupBox("飞行状态详情")
        detail_layout = QFormLayout(detail_box)
        detail_layout.setLabelAlignment(Qt.AlignRight)
        detail_layout.setVerticalSpacing(9)
        detail_layout.setHorizontalSpacing(16)

        # 连接状态（心跳对应）
        self.status_label = QLabel("● 未连接")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 14px;")
        detail_layout.addRow("连接状态:", self.status_label)

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

        # 关键数据高亮样式
        highlight_style = "color: #00d4ff; font-weight: 500;"
        self.detail_labels["battery_percent"].setStyleSheet(highlight_style)
        self.detail_labels["alt"].setStyleSheet(highlight_style)
        self.detail_labels["mode"].setStyleSheet(highlight_style)

        detail_layout.addRow("无人机ID:", self.detail_labels["drone_id"])
        #detail_layout.addRow("帧序列号:", self.detail_labels["seq"])
        detail_layout.addRow("飞行模式:", self.detail_labels["mode"])
        detail_layout.addRow("剩余电量:", self.detail_labels["battery_percent"])
        detail_layout.addRow("电池电压:", self.detail_labels["battery_voltage"])
        detail_layout.addRow("纬度:", self.detail_labels["lat"])
        detail_layout.addRow("经度:", self.detail_labels["lon"])
        detail_layout.addRow("相对高度:", self.detail_labels["alt"])
        detail_layout.addRow("横滚角:", self.detail_labels["roll"])
        detail_layout.addRow("俯仰角:", self.detail_labels["pitch"])
        detail_layout.addRow("偏航角:", self.detail_labels["yaw"])

        right_splitter.addWidget(detail_box)

        # 右中：原始JSON报文
        json_box = QGroupBox("原始 JSON 报文")
        json_layout = QVBoxLayout(json_box)
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setFont(QFont("Consolas", 9))
        json_layout.addWidget(self.json_view)
        right_splitter.addWidget(json_box)

        # 右下：运行日志
        log_box = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Microsoft YaHei", 9))
        log_layout.addWidget(self.log_view)
        right_splitter.addWidget(log_box)

        # 分割比例
        right_splitter.setSizes([260, 240, 200])

        # 组装主布局
        main_layout.addWidget(left_box)
        main_layout.addWidget(right_splitter, 1)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.logout_button = QPushButton("退出登录")
        self.logout_button.setObjectName("logoutButton")
        self.logout_button.clicked.connect(self._request_logout)
        self.status_bar.addPermanentWidget(self.logout_button)

    def _refresh_ui(self):
        """定时从业务层拉取数据，增量刷新界面"""
        # 1. 检查离线无人机
        offline_drones = self.gs.check_offline_drones()
        for drone_id in offline_drones:
            self._append_log(f"[离线] 无人机 {drone_id} 已断开连接", "#ff6b6b")

        # 2. 增量更新设备列表（只在数量变化时操作）
        online_ids = self.gs.get_online_ids()
        current_count = self.drone_list.count()
        if len(online_ids) != current_count:
            # 全量重建列表（数量少时开销可忽略，避免逐条增删的闪烁）
            self.drone_list.clear()
            for drone_id in online_ids:
                self.drone_list.addItem(drone_id)
                self._append_log(f"[上线] 无人机 {drone_id} 已接入", "#39d353")

        # 3. 只在有选中设备时刷新详情
        current_item = self.drone_list.currentItem()
        if current_item:
            self._update_drone_detail(current_item.text())

        # 4. 状态栏
        self.status_bar.showMessage(
            f"  在线设备：{self.drone_list.count()} 架  |  心跳监听：UDP {self.gs.config.heartbeat_port}  |  数据监听：TCP {self.gs.config.data_port}"
        )

    def _on_drone_selected(self, current, previous):
        if current:
            self._update_drone_detail(current.text())

    def _update_drone_detail(self, drone_id):
        # 1. 连接状态判定
        online_ids = self.gs.get_online_ids()
        if drone_id in online_ids:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: #39d353; font-weight: 600; font-size: 14px;")
        else:
            self.status_label.setText("● 未连接")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: 600; font-size: 14px;")

        # 2. 设备无状态数据（已离线/已清理）→ 清空界面后返回
        status = self.gs.get_drone_status(drone_id)
        if not status:
            self._clear_drone_detail()
            return

        # 3. 正常填充数据（原有逻辑保持不变）
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
        self.detail_labels["roll"].setText(f"{roll:.2f} °" if roll != "-" else "- °")
        self.detail_labels["pitch"].setText(f"{pitch:.2f} °" if pitch != "-" else "- °")
        self.detail_labels["yaw"].setText(f"{yaw:.2f} °" if yaw != "-" else "- °")

        # JSON视图按需更新（调试用，不影响主流程）
        self.json_view.setPlainText(
            json.dumps(status, indent=2, ensure_ascii=False)
        )

    def _append_log(self, text: str, color: str = "#c9d1d9"):
        """带颜色的日志输出，区分上线/离线/普通信息"""
        html = f'<span style="color: {color};">{text}</span>'
        self.log_view.append(html)
        # 自动滚动到底部
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

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
        """窗口关闭时通知业务层释放资源"""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
        if not self._logging_out:
            self.gs.stop()
        event.accept()
