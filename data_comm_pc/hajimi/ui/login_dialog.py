# -*- coding: utf-8 -*-
"""Login dialog for the ground-station application."""

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from auth import AuthUser, MySQLUserRepository


class LoginDialog(QDialog):
    def __init__(self, user_repository: MySQLUserRepository, parent=None):
        super().__init__(parent)
        self.user_repository = user_repository
        self.current_user: AuthUser = None
        self.settings = QSettings("Hajimi", "GroundStation")

        self.setWindowTitle("用户登录")
        self.setModal(True)
        self.setFixedSize(520, 620)
        self._build_ui()
        self._load_saved_credentials()
        self._set_mode("login")

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #0d1320;
                color: #e5edf7;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }
            QFrame#card {
                background: #151e2e;
                border: 1px solid #253349;
                border-radius: 8px;
            }
            QLabel#brand {
                color: #f7fbff;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #90a4bd;
                font-size: 13px;
            }
            QLabel#fieldLabel {
                color: #9fb2c8;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#message {
                color: #ff7b72;
                font-size: 12px;
                min-height: 24px;
            }
            QLineEdit {
                background: #0f1726;
                border: 1px solid #2a3a52;
                border-radius: 6px;
                color: #ecf3fb;
                min-height: 42px;
                padding: 0 13px;
                selection-background-color: #1f6feb;
            }
            QLineEdit:focus {
                border: 1px solid #35c2ff;
                background: #101c2d;
            }
            QCheckBox {
                color: #9fb2c8;
                spacing: 8px;
                min-height: 26px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #3a4d68;
                background: #0f1726;
            }
            QCheckBox::indicator:checked {
                background: #1f6feb;
                border: 1px solid #35c2ff;
            }
            QPushButton {
                border: 0;
                border-radius: 6px;
                min-height: 40px;
                padding: 0 16px;
                font-weight: 700;
            }
            QPushButton#primary {
                background: #1f6feb;
                color: white;
            }
            QPushButton#primary:hover {
                background: #2f81f7;
            }
            QPushButton#tab {
                background: transparent;
                color: #8fa3bb;
                border-radius: 6px;
                min-height: 34px;
            }
            QPushButton#tab[active="true"] {
                background: #20314b;
                color: #f3f8ff;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(34, 34, 34, 34)
        root_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 16)
        shadow.setColor(QColor(0, 0, 0, 130))
        card.setGraphicsEffect(shadow)
        root_layout.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 34, 36, 34)
        card_layout.setSpacing(18)

        brand = QLabel("边缘智能体通信平台")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(brand)

        subtitle = QLabel("Ground Station Access")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(8)
        self.login_tab = QPushButton("登录")
        self.login_tab.setObjectName("tab")
        self.register_tab = QPushButton("创建账号")
        self.register_tab.setObjectName("tab")
        self.login_tab.clicked.connect(lambda: self._set_mode("login"))
        self.register_tab.clicked.connect(lambda: self._set_mode("register"))
        tab_layout.addWidget(self.login_tab)
        tab_layout.addWidget(self.register_tab)
        card_layout.addLayout(tab_layout)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_page())
        self.stack.addWidget(self._build_register_page())
        card_layout.addWidget(self.stack, 1)

        self.message_label = QLabel("")
        self.message_label.setObjectName("message")
        self.message_label.setWordWrap(True)
        card_layout.addWidget(self.message_label)

        self.login_button.setDefault(True)

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(14)

        self.login_username = self._field(layout, "用户名", "请输入用户名")
        self.login_password = self._field(layout, "密码", "请输入密码", password=True)
        self.login_password.returnPressed.connect(self._login)

        self.remember_checkbox = QCheckBox("记住账号密码")
        layout.addWidget(self.remember_checkbox)

        layout.addSpacing(4)
        self.login_button = QPushButton("进入系统")
        self.login_button.setObjectName("primary")
        self.login_button.clicked.connect(self._login)
        layout.addWidget(self.login_button)
        layout.addStretch(1)
        return page

    def _build_register_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        self.register_username = self._field(layout, "用户名", "3-64 位账号")
        self.register_display_name = self._field(layout, "显示名称", "用于登录后的身份显示")
        self.register_password = self._field(layout, "密码", "至少 6 位", password=True)
        self.register_confirm = self._field(layout, "确认密码", "再次输入密码", password=True)
        self.register_confirm.returnPressed.connect(self._register)

        layout.addSpacing(4)
        self.register_button = QPushButton("创建并返回登录")
        self.register_button.setObjectName("primary")
        self.register_button.clicked.connect(self._register)
        layout.addWidget(self.register_button)
        layout.addStretch(1)
        return page

    def _field(self, layout: QVBoxLayout, label_text: str, placeholder: str, password: bool = False) -> QLineEdit:
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if password:
            field.setEchoMode(QLineEdit.Password)
        layout.addWidget(field)
        return field

    def _set_mode(self, mode: str) -> None:
        is_login = mode == "login"
        self.stack.setCurrentIndex(0 if is_login else 1)
        self._show_message("")
        self.login_tab.setProperty("active", is_login)
        self.register_tab.setProperty("active", not is_login)
        self.login_tab.style().unpolish(self.login_tab)
        self.login_tab.style().polish(self.login_tab)
        self.register_tab.style().unpolish(self.register_tab)
        self.register_tab.style().polish(self.register_tab)
        (self.login_username if is_login else self.register_username).setFocus()

    def _login(self) -> None:
        username = self.login_username.text()
        password = self.login_password.text()
        try:
            user = self.user_repository.authenticate(username, password)
        except Exception as exc:
            self._show_message(f"数据库连接失败：{exc}")
            return

        if not user:
            self._show_message("用户名或密码不正确")
            self.login_password.selectAll()
            self.login_password.setFocus()
            return

        self._save_or_clear_credentials(username, password)
        self.current_user = user
        self.accept()

    def _register(self) -> None:
        username = self.register_username.text()
        display_name = self.register_display_name.text()
        password = self.register_password.text()
        confirm = self.register_confirm.text()

        if password != confirm:
            self._show_message("两次输入的密码不一致")
            self.register_confirm.selectAll()
            self.register_confirm.setFocus()
            return

        try:
            self.user_repository.create_user(username, password, display_name)
        except ValueError as exc:
            self._show_message(str(exc))
            return
        except Exception as exc:
            self._show_message(f"创建账号失败：{exc}")
            return

        self.login_username.setText(username.strip())
        self.login_password.clear()
        self.register_username.clear()
        self.register_display_name.clear()
        self.register_password.clear()
        self.register_confirm.clear()
        self._set_mode("login")
        self._show_message("账号创建成功，请登录。", "#39d353")
        self.login_password.setFocus()

    def _load_saved_credentials(self) -> None:
        remember = self.settings.value("rememberCredentials", False, type=bool)
        self.remember_checkbox.setChecked(remember)
        if not remember:
            return
        self.login_username.setText(self.settings.value("username", "", type=str))
        self.login_password.setText(self.settings.value("password", "", type=str))

    def _save_or_clear_credentials(self, username: str, password: str) -> None:
        if self.remember_checkbox.isChecked():
            self.settings.setValue("rememberCredentials", True)
            self.settings.setValue("username", username.strip())
            self.settings.setValue("password", password)
        else:
            self.settings.remove("rememberCredentials")
            self.settings.remove("username")
            self.settings.remove("password")
        self.settings.sync()

    def _show_message(self, message: str, color: str = "#ff7b72") -> None:
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setText(message)
