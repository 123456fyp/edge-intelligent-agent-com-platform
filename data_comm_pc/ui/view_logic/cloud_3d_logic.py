# -*- coding: utf-8 -*-
"""UI内部 3D点云视图，仅相机/鼠标数学计算"""
from PyQt5.QtCore import QPoint

class PointCloud3DLogic:
    def __init__(self):
        # 默认初始视角（匹配截图）
        self._rot_x = 15.0
        self._rot_y = -30.0
        self._zoom = 25.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        # 鼠标灵敏度参数统一配置
        self.rot_sensitivity = 0.25
        self.pan_sensitivity = 0.001
        self.zoom_step = 1.15

        # 鼠标状态缓存
        self.last_mouse_pos = QPoint()
        self.left_pressed = False
        self.right_pressed = False

        # 显示配置
        self.show_grid = True
        self.show_axes = True
        self.color_mode = "intensity"

        # 点云缓存
        self.points = []
        self.point_colors = []

    def reset_view(self):
        """重置到默认斜俯视视角"""
        self._rot_x = 15.0
        self._rot_y = -30.0
        self._zoom = 35.0
        self._pan_x = 0.0
        self._pan_y = 0.0

    def handle_rotate(self, delta_x: int, delta_y: int):
        """左键旋转计算"""
        self._rot_y += delta_x * self.rot_sensitivity
        self._rot_x += delta_y * self.rot_sensitivity
        self._rot_x = max(-89.0, min(89.0, self._rot_x))

    def handle_pan(self, delta_x: int, delta_y: int):
        """右键平移计算"""
        factor = self._zoom * self.pan_sensitivity
        self._pan_x += delta_x * factor
        self._pan_y -= delta_y * factor

    def handle_zoom(self, scroll_up: bool):
        """滚轮反向缩放计算：上滚缩小，下滚放大"""
        factor = 1 / self.zoom_step if scroll_up else self.zoom_step
        self._zoom *= factor
        self._zoom = max(2.0, min(200.0, self._zoom))

    def set_view_preset(self, mode: str):
        """切换预设俯视图/前视图/侧视图"""
        if mode == "top":
            self._rot_x = -90.0
            self._rot_y = 0.0
        elif mode == "front":
            self._rot_x = 0.0
            self._rot_y = 0.0
        elif mode == "side":
            self._rot_x = 0.0
            self._rot_y = -90.0

    def update_point_data(self, points):
        self.points = points
        self.point_colors.clear()

    # 只读参数接口
    @property
    def rot_x(self): return self._rot_x
    @property
    def rot_y(self): return self._rot_y
    @property
    def zoom(self): return self._zoom
    @property
    def pan_x(self): return self._pan_x
    @property
    def pan_y(self): return self._pan_y