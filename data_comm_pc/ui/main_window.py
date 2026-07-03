# -*- coding: utf-8 -*-
"""
Qt5 地面站主窗口 - UI层
科技深色主题，左侧侧边栏导航切换界面，支持飞行状态、激光雷达点云、运行日志等页面
"""
import json
import math

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QFormLayout, QLabel, QTextEdit, QSplitter,
    QStatusBar, QGroupBox, QPushButton, QStackedWidget,
    QFrame, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QSlider, QComboBox, QCheckBox, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt, QRectF, QPointF, QPoint
from PyQt5.QtGui import QFont, QColor, QPen, QBrush, QPainter, QPolygonF
from PyQt5.QtWidgets import QOpenGLWidget

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False

from ui.widgets.sidebar_btn import SidebarButton
from ui.widgets.cloud_3d_widget import PointCloud3DWidget
from business.ground_station import GroundStation


class SidebarButton(QPushButton):
    """侧边栏导航按钮 - 自定义样式"""
    def __init__(self, text, icon_text="", parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.setText(text)
        self.setCheckable(True)
        self.setMinimumHeight(48)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: none;
                border-left: 3px solid transparent;
                text-align: left;
                padding-left: 20px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1a2332;
                color: #c9d1d9;
            }
            QPushButton:checked {
                background-color: #1e3a5f;
                color: #00d4ff;
                border-left: 3px solid #00d4ff;
                font-weight: 600;
            }
        """)


class PointCloudView(QGraphicsView):
    """点云可视化视图 - 基于QGraphicsView的2D俯视图展示
    坐标系：上方为前方（X轴正方向），左方为左方（Y轴正方向），原点为无人机位置
    交互：中键拖拽平移，滚轮缩放，右键重置视图
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setBackgroundBrush(QBrush(QColor("#0a0e17")))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCursor(Qt.OpenHandCursor)

        # 点云数据
        self._points = []
        self._point_items = []
        self._drone_marker = None
        self._direction_arrow = None

        # 视图参数
        self._zoom = 1.0
        self._grid_size = 10  # 网格大小（米）
        self._max_range = 50  # 最大显示范围（米）
        self._default_range = 30  # 默认显示范围（米）

        # 视图模式：top(俯视图XY)、front(前视图XZ)、side(侧视图YZ)
        self._view_mode = "top"

        # 左键拖拽状态
        self._panning = False
        self._pan_start_pos = None

        # 中键切换视图状态
        self._view_switching = False
        self._view_switch_start = None
        self._switch_threshold = 50  # 切换阈值（像素）

        # 首次加载标记
        self._first_frame = True

        self._setup_scene()

    def _setup_scene(self):
        """初始化场景元素"""
        self.scene.setSceneRect(
            -self._max_range, -self._max_range,
            self._max_range * 2, self._max_range * 2
        )
        self._setup_grid()
        self._setup_drone_marker()
        self._setup_direction_labels()

    def _setup_grid(self):
        """绘制网格背景"""
        pen = QPen(QColor("#1a2332"))
        pen.setWidthF(0.3)

        # 绘制网格线
        for i in range(-self._max_range, self._max_range + 1, self._grid_size):
            self.scene.addLine(-self._max_range, i, self._max_range, i, pen)
            self.scene.addLine(i, -self._max_range, i, self._max_range, pen)

        # 中心十字线
        center_pen = QPen(QColor("#2a3447"))
        center_pen.setWidthF(0.8)
        self.scene.addLine(-self._max_range, 0, self._max_range, 0, center_pen)
        self.scene.addLine(0, -self._max_range, 0, self._max_range, center_pen)

        # 距离刻度圆环
        circle_pen = QPen(QColor("#1f2937"))
        circle_pen.setWidthF(0.5)
        circle_pen.setStyle(Qt.DashLine)
        for r in [10, 20, 30, 40, 50]:
            self.scene.addEllipse(-r, -r, r * 2, r * 2, circle_pen)

    def _setup_drone_marker(self):
        """绘制无人机位置标记"""
        # 无人机主体（青色圆点）
        drone_radius = 0.8
        self._drone_marker = self.scene.addEllipse(
            -drone_radius, -drone_radius,
            drone_radius * 2, drone_radius * 2,
            QPen(QColor("#00d4ff"), 2),
            QBrush(QColor("#00d4ff"))
        )
        self._drone_marker.setZValue(100)

        # 前向箭头（绿色，指示无人机朝向）
        arrow_pen = QPen(QColor("#39d353"))
        arrow_pen.setWidthF(2)
        arrow_brush = QBrush(QColor("#39d353"))

        arrow = QPolygonF([
            QPointF(0, -2.5),
            QPointF(-0.6, -1.7),
            QPointF(0, -2.0),
            QPointF(0.6, -1.7),
        ])
        self._direction_arrow = self.scene.addPolygon(arrow, arrow_pen, arrow_brush)
        self._direction_arrow.setZValue(101)

    def _setup_direction_labels(self):
        """绘制方向标签和距离刻度"""
        font = QFont("Microsoft YaHei", 9, QFont.Bold)

        # 前（上）
        label = self.scene.addText("前")
        label.setDefaultTextColor(QColor("#4a5568"))
        label.setFont(font)
        label.setPos(-0.8, -self._max_range + 1)

        # 后（下）
        label = self.scene.addText("后")
        label.setDefaultTextColor(QColor("#4a5568"))
        label.setFont(font)
        label.setPos(-0.8, self._max_range - 2.5)

        # 左
        label = self.scene.addText("左")
        label.setDefaultTextColor(QColor("#4a5568"))
        label.setFont(font)
        label.setPos(-self._max_range + 1, -0.8)

        # 右
        label = self.scene.addText("右")
        label.setDefaultTextColor(QColor("#4a5568"))
        label.setFont(font)
        label.setPos(self._max_range - 2, -0.8)

        # 距离刻度
        for r in [10, 20, 30, 40, 50]:
            label = self.scene.addText(f"{r}m")
            label.setDefaultTextColor(QColor("#374151"))
            label.setFont(QFont("Arial", 7))
            label.setPos(0.3, -r - 0.5)

    def update_points(self, points):
        """更新点云数据
        支持三种视图模式：top(俯视图XY)、front(前视图YZ)、side(侧视图XZ)
        """
        # 清除旧点
        for item in self._point_items:
            self.scene.removeItem(item)
        self._point_items.clear()

        self._points = points
        if not points:
            return

        # 计算点云范围
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')

        for pt in points:
            px = pt.get("x", 0)  # ROS: x 向前
            py = pt.get("y", 0)  # ROS: y 向左
            pz = pt.get("z", 0)  # ROS: z 向上
            intensity = pt.get("intensity", 0.5)

            # 根据视图模式选择坐标映射
            if self._view_mode == "top":
                # 俯视图(XY)：左右→水平，前后→垂直（上=前）
                view_x = -py
                view_y = -px
            elif self._view_mode == "front":
                # 前视图(XZ)：前后→水平，上下→垂直（上=高）
                view_x = px
                view_y = -pz
            elif self._view_mode == "side":
                # 侧视图(YZ)：左右→水平，上下→垂直（上=高）
                view_x = -py
                view_y = -pz
            else:
                view_x = -py
                view_y = -px

            if abs(view_x) > self._max_range or abs(view_y) > self._max_range:
                continue

            min_x = min(min_x, view_x)
            max_x = max(max_x, view_x)
            min_y = min(min_y, view_y)
            max_y = max(max_y, view_y)

            # 强度着色（蓝→青→绿→黄→橙渐变）
            if "intensity" in pt:
                val = intensity / 255.0 if intensity > 1.0 else intensity
                val = max(0.0, min(1.0, val))
                if val < 0.25:
                    t = val / 0.25
                    r, g, b = int(30+50*t), int(100+100*t), int(200+55*t)
                elif val < 0.5:
                    t = (val - 0.25) / 0.25
                    r, g, b = int(80+40*t), int(200+55*t), int(255-55*t)
                elif val < 0.75:
                    t = (val - 0.5) / 0.25
                    r, g, b = int(120+135*t), 255, int(200-150*t)
                else:
                    t = (val - 0.75) / 0.25
                    r, g, b = 255, int(255-100*t), int(50-50*t)
            else:
                z_norm = max(0, min(1, (pz + 5) / 10))
                r = int(100 + 155 * z_norm)
                g = int(100 + 100 * (1 - abs(z_norm - 0.5) * 2))
                b = int(255 * (1 - z_norm))

            color = QColor(r, g, b, 220)
            size = 0.12

            item = self.scene.addEllipse(
                view_x - size/2, view_y - size/2, size, size,
                QPen(Qt.NoPen), QBrush(color)
            )
            item.setZValue(10)
            self._point_items.append(item)

        # 首次有点云时自动适配视图
        if self._first_frame and len(points) > 0:
            self._first_frame = False
            self._fit_to_points(min_x, max_x, min_y, max_y)

    def _fit_to_points(self, min_x, max_x, min_y, max_y):
        """自动适配点云范围"""
        padding = 5
        x_range = max(max_x - min_x, 10)
        y_range = max(max_y - min_y, 10)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        rect = QRectF(
            center_x - x_range/2 - padding,
            center_y - y_range/2 - padding,
            x_range + padding * 2,
            y_range + padding * 2
        )
        self.fitInView(rect, Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self._zoom *= factor

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MiddleButton:
            self._view_switching = True
            self._view_switch_start = event.pos()
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
        elif event.button() == Qt.RightButton:
            self.reset_view()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._panning and self._pan_start_pos is not None:
            delta = event.pos() - self._pan_start_pos
            transform = self.transform()
            sx, sy = transform.m11(), transform.m22()
            if sx != 0 and sy != 0:
                self.translate(-delta.x() / sx, -delta.y() / sy)
            self._pan_start_pos = event.pos()
            event.accept()
        elif self._view_switching and self._view_switch_start is not None:
            # 中键拖拽时可以添加视觉反馈，这里暂不处理
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self._panning = False
            self._pan_start_pos = None
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        elif event.button() == Qt.MiddleButton:
            if self._view_switching and self._view_switch_start is not None:
                delta = event.pos() - self._view_switch_start
                dx = delta.x()
                dy = delta.y()
                distance = (dx * dx + dy * dy) ** 0.5

                if distance >= self._switch_threshold:
                    # 判断主要方向
                    if abs(dy) > abs(dx):
                        # 垂直方向为主
                        if dy < 0:
                            # 向上拖 → 前视图
                            self.set_view_mode("front")
                        else:
                            # 向下拖 → 俯视图
                            self.set_view_mode("top")
                    else:
                        # 水平方向为主 → 侧视图
                        self.set_view_mode("side")

            self._view_switching = False
            self._view_switch_start = None
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def reset_view(self):
        """重置视图 - 以无人机为中心"""
        self.resetTransform()
        self.fitInView(
            QRectF(-self._default_range, -self._default_range,
                   self._default_range * 2, self._default_range * 2),
            Qt.KeepAspectRatio
        )
        self._zoom = 1.0
        self._first_frame = True

    def set_view_mode(self, mode: str):
        """切换视图模式
        Args:
            mode: "top"(俯视图XY)、"front"(前视图YZ)、"side"(侧视图XZ)
        """
        if mode not in ["top", "front", "side"]:
            return
        self._view_mode = mode
        self._first_frame = True
        # 重新绘制点云
        if self._points:
            self.update_points(self._points)

'''PointCloud3DView(QOpenGLWidget) 3D点云可视化视图 - 基于OpenGL，支持自由旋转视角
class PointCloud3DView(QOpenGLWidget):
    """3D点云可视化视图 - 基于OpenGL，支持自由旋转视角
    交互：左键旋转、右键平移、滚轮缩放
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

        # 点云数据
        self._points = []
        self._point_colors = []

        # 相机参数
        self._rot_x = 15.0  # 俯仰角
        self._rot_y = -30.0   # 偏航角
        self._zoom = 35.0   # 缩放距离
        self._pan_x = 0.0   # 平移X
        self._pan_y = 0.0   # 平移Y

        # 鼠标状态
        self._last_pos = QPoint()
        self._left_pressed = False
        self._right_pressed = False

        # 显示设置
        self._show_grid = True
        self._show_axes = True
        self._color_mode = "intensity"  # intensity 或 height

    def update_points(self, points):
        """更新点云数据"""
        self._points = points
        self._update_colors()
        self.update()

    def _update_colors(self):
        """更新点云颜色"""
        self._point_colors = []
        if not self._points:
            return

        for pt in self._points:
            if self._color_mode == "intensity" and "intensity" in pt:
                val = pt["intensity"] / 255.0 if pt["intensity"] > 1.0 else pt["intensity"]
                val = max(0.0, min(1.0, val))
                # 蓝→青→绿→黄→橙渐变
                if val < 0.25:
                    t = val / 0.25
                    r, g, b = 0.1+0.2*t, 0.4+0.4*t, 0.8+0.2*t
                elif val < 0.5:
                    t = (val - 0.25) / 0.25
                    r, g, b = 0.3+0.15*t, 0.8+0.2*t, 1.0-0.2*t
                elif val < 0.75:
                    t = (val - 0.5) / 0.25
                    r, g, b = 0.45+0.55*t, 1.0, 0.8-0.6*t
                else:
                    t = (val - 0.75) / 0.25
                    r, g, b = 1.0, 1.0-0.4*t, 0.2-0.2*t
            else:
                z = pt.get("z", 0)
                z_norm = max(0.0, min(1.0, (z + 5) / 10))
                r = 0.4 + 0.6 * z_norm
                g = 0.4 + 0.4 * (1 - abs(z_norm - 0.5) * 2)
                b = 1.0 - z_norm
            self._point_colors.append((r, g, b))

    def reset_view(self):
        """重置视角 - 默认斜俯视视角"""
        self._rot_x = 15.0
        self._rot_y = -30.0
        self._zoom = 35.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    def initializeGL(self):
        """OpenGL初始化"""
        glClearColor(0.04, 0.05, 0.09, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPointSize(2.0)

    def resizeGL(self, w, h):
        """窗口大小变化"""
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60.0, w / h if h > 0 else 1.0, 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        """绘制场景"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # 应用相机变换
        glTranslatef(self._pan_x, self._pan_y, -self._zoom)
        glRotatef(self._rot_x, 1.0, 0.0, 0.0)
        glRotatef(self._rot_y, 0.0, 1.0, 0.0)

        # 绘制网格
        if self._show_grid:
            self._draw_grid()

        # 绘制坐标轴
        if self._show_axes:
            self._draw_axes()

        # 绘制点云
        self._draw_points()

    def _draw_grid(self):
        """绘制地面网格"""
        glColor4f(0.1, 0.15, 0.2, 0.5)
        glLineWidth(0.5)
        grid_size = 50
        grid_step = 10

        glBegin(GL_LINES)
        for i in range(-grid_size, grid_size + 1, grid_step):
            glVertex3f(i, 0, -grid_size)
            glVertex3f(i, 0, grid_size)
            glVertex3f(-grid_size, 0, i)
            glVertex3f(grid_size, 0, i)
        glEnd()

        # 中心十字线
        glColor4f(0.2, 0.25, 0.35, 0.8)
        glLineWidth(1.0)
        glBegin(GL_LINES)
        glVertex3f(-grid_size, 0, 0)
        glVertex3f(grid_size, 0, 0)
        glVertex3f(0, 0, -grid_size)
        glVertex3f(0, 0, grid_size)
        glEnd()

    def _draw_axes(self):
        """绘制坐标轴"""
        axis_len = 5.0
        glLineWidth(2.0)
        glBegin(GL_LINES)
        # X轴 - 红色（向前）
        glColor3f(1.0, 0.3, 0.3)
        glVertex3f(0, 0, 0)
        glVertex3f(axis_len, 0, 0)
        # Y轴 - 绿色（向左）
        glColor3f(0.3, 1.0, 0.3)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, axis_len)
        # Z轴 - 蓝色（向上）
        glColor3f(0.3, 0.5, 1.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, axis_len, 0)
        glEnd()

    def _draw_points(self):
        """绘制点云"""
        if not self._points:
            return

        glBegin(GL_POINTS)
        for i, pt in enumerate(self._points):
            x = pt.get("x", 0)
            y = pt.get("y", 0)
            z = pt.get("z", 0)
            if i < len(self._point_colors):
                r, g, b = self._point_colors[i]
                glColor4f(r, g, b, 0.9)
            else:
                glColor4f(0.5, 0.8, 1.0, 0.9)
            # ROS坐标: x向前, y向左, z向上
            # OpenGL坐标: x向右, y向上, z向里
            # 转换: x→x, z→y, -y→z
            glVertex3f(x, z, -y)
        glEnd()

    def mousePressEvent(self, event):
        """鼠标按下"""
        self._last_pos = event.pos()
        if event.button() == Qt.LeftButton:
            self._left_pressed = True
            self.setCursor(Qt.SizeAllCursor)
        elif event.button() == Qt.RightButton:
            self._right_pressed = True
            self.setCursor(Qt.OpenHandCursor)
        elif event.button() == Qt.MiddleButton:
            self.reset_view()

    def mouseMoveEvent(self, event):
        """鼠标移动"""
        delta = event.pos() - self._last_pos

        if self._left_pressed:
            # 左键旋转
            self._rot_y += delta.x() * 0.4
            self._rot_x += delta.y() * 0.4
            # 限制俯仰角
            self._rot_x = max(-89.0, min(89.0, self._rot_x))
            self.update()
        elif self._right_pressed:
            # 右键平移
            factor = self._zoom * 0.002
            self._pan_x += delta.x() * factor
            self._pan_y -= delta.y() * factor
            self.update()

        self._last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        if event.button() == Qt.LeftButton:
            self._left_pressed = False
        elif event.button() == Qt.RightButton:
            self._right_pressed = False
        if not self._left_pressed and not self._right_pressed:
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        """滚轮缩放反向：滚轮上滑缩小，下滑放大"""
        if event.angleDelta().y() > 0:
            # 滚轮向上 → 缩小
            factor = 1 / 1.15
        else:
            # 滚轮向下 → 放大
            factor = 1.15
        self._zoom *= factor
        self._zoom = max(2.0, min(200.0, self._zoom))
        self.update()

    def set_view_mode(self, mode):
        """兼容旧接口，切换预设视角"""
        if mode == "top":
            self._rot_x = -90.0
            self._rot_y = 0.0
        elif mode == "front":
            self._rot_x = 0.0
            self._rot_y = 0.0
        elif mode == "side":
            self._rot_x = 0.0
            self._rot_y = -90.0
        self.update()
'''

class GroundStationWindow(QMainWindow):
    def __init__(self, ground_station: GroundStation):
        super().__init__()
        self.gs = ground_station
        self.setWindowTitle("无人机地面站 v2.0")
        self.resize(1400, 850)

        self._current_page = "flight"  # 当前页面
        self._nav_buttons = {}

        self._set_global_style()
        self._init_ui()

        # 绑定业务层信号，事件驱动刷新
        self.gs.sig_drone_online.connect(self._on_drone_online)
        self.gs.sig_drone_offline.connect(self._on_drone_offline)
        self.gs.sig_data_updated.connect(self._on_data_updated)
        self.gs.sig_pointcloud_updated.connect(self._on_pointcloud_updated)

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

        # 3. 核心：只有当前显示的是这台离线设备，才清空详情
        if current_selected_id == drone_id:
            self._clear_drone_detail()
            self._clear_pointcloud_view()

    def _on_data_updated(self, drone_id: str):
        """数据更新：只刷新当前选中的设备，避免无效渲染"""
        current_item = self.drone_list.currentItem()
        if current_item and current_item.text() == drone_id:
            if self._current_page == "flight":
                self._update_drone_detail(drone_id)

    def _on_pointcloud_updated(self, drone_id: str):
        """点云数据更新：刷新点云视图"""
        current_item = self.drone_list.currentItem()
        if current_item and current_item.text() == drone_id:
            if self._current_page == "pointcloud":
                self._update_pointcloud_view(drone_id)

    def _check_offline(self):
        """定时器触发：检查离线设备"""
        self.gs.check_offline_drones()
        # 更新状态栏
        self.status_bar.showMessage(
            f"  在线设备：{self.drone_list.count()} 架  |  "
            f"心跳监听：UDP {self.gs.config.heartbeat_port}  |  "
            f"数据监听：TCP {self.gs.config.data_port}  |  "
            f"点云监听：TCP {self.gs.config.pointcloud_port}"
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

    def _clear_pointcloud_view(self):
        """清空点云视图"""
        self.pointcloud_view.update_points([])
        self.pc_info_labels["num_points"].setText("-")
        self.pc_info_labels["frame_id"].setText("-")
        self.pc_info_labels["seq"].setText("-")
        self.pc_info_labels["timestamp"].setText("-")

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
        QGraphicsView {
            background-color: #0a0e17;
            border: 1px solid #2a3447;
            border-radius: 4px;
        }
        QComboBox {
            background-color: #0f131b;
            border: 1px solid #2a3447;
            border-radius: 4px;
            padding: 4px 8px;
            color: #e0e6ed;
        }
        QComboBox:hover {
            border-color: #00d4ff;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox QAbstractItemView {
            background-color: #181d29;
            border: 1px solid #2a3447;
            selection-background-color: #1e3a5f;
            selection-color: #00d4ff;
        }
        QCheckBox {
            color: #8b949e;
            spacing: 6px;
        }
        QCheckBox::indicator {
            width: 14px;
            height: 14px;
            border: 1px solid #2a3447;
            border-radius: 3px;
            background-color: #0f131b;
        }
        QCheckBox::indicator:checked {
            background-color: #00d4ff;
            border-color: #00d4ff;
        }
        """
        self.setStyleSheet(style)

    def _init_ui(self):
        """构建界面布局 - 左侧侧边栏导航 + 右侧内容区"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== 左侧：侧边栏 ==========
        self._init_sidebar(main_layout)

        # ========== 右侧：内容堆叠区 ==========
        self._init_content_stack(main_layout)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 默认选中飞行状态页面
        self._switch_page("flight")

    def _init_sidebar(self, main_layout):
        """初始化左侧侧边栏"""
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background-color: #0f131b; border-right: 1px solid #1f2736;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo/标题区域
        title_widget = QWidget()
        title_widget.setFixedHeight(60)
        title_widget.setStyleSheet("background-color: #0a0e17; border-bottom: 1px solid #1f2736;")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(20, 0, 0, 0)

        title_label = QLabel("地面控制站")
        title_label.setStyleSheet("color: #00d4ff; font-size: 16px; font-weight: 700; letter-spacing: 1px;")
        title_layout.addWidget(title_label)

        subtitle_label = QLabel("Ground Control Station")
        subtitle_label.setStyleSheet("color: #4a5568; font-size: 10px; letter-spacing: 2px;")
        title_layout.addWidget(subtitle_label)

        sidebar_layout.addWidget(title_widget)

        # 设备列表区域
        device_box = QWidget()
        device_layout = QVBoxLayout(device_box)
        device_layout.setContentsMargins(12, 12, 12, 8)

        device_title = QLabel("在线设备")
        device_title.setStyleSheet("color: #4a5568; font-size: 11px; font-weight: 600; letter-spacing: 1px; margin-bottom: 4px;")
        device_layout.addWidget(device_title)

        self.drone_list = QListWidget()
        self.drone_list.setFixedHeight(120)
        self.drone_list.currentItemChanged.connect(self._on_drone_selected)
        device_layout.addWidget(self.drone_list)

        sidebar_layout.addWidget(device_box)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #1f2736;")
        sidebar_layout.addWidget(separator)

        # 导航标题
        nav_title = QLabel("功能导航")
        nav_title.setStyleSheet("color: #4a5568; font-size: 11px; font-weight: 600; letter-spacing: 1px; padding: 12px 20px 4px;")
        sidebar_layout.addWidget(nav_title)

        # 导航按钮组
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        # 飞行状态按钮
        self.btn_flight = SidebarButton("飞行状态")
        self.btn_flight.clicked.connect(lambda: self._switch_page("flight"))
        nav_layout.addWidget(self.btn_flight)
        self._nav_buttons["flight"] = self.btn_flight

        # 激光雷达点云按钮
        self.btn_pointcloud = SidebarButton("激光雷达点云")
        self.btn_pointcloud.clicked.connect(lambda: self._switch_page("pointcloud"))
        nav_layout.addWidget(self.btn_pointcloud)
        self._nav_buttons["pointcloud"] = self.btn_pointcloud

        # 运行日志按钮
        self.btn_log = SidebarButton("运行日志")
        self.btn_log.clicked.connect(lambda: self._switch_page("log"))
        nav_layout.addWidget(self.btn_log)
        self._nav_buttons["log"] = self.btn_log

        sidebar_layout.addWidget(nav_container)

        # 弹性伸缩
        sidebar_layout.addStretch()

        # 底部版本信息
        version_label = QLabel("v2.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #4a5568; font-size: 10px; padding: 12px;")
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

    def _init_content_stack(self, main_layout):
        """初始化右侧内容堆叠区"""
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #12161f;")

        # 页面1：飞行状态
        self._init_flight_page()

        # 页面2：激光雷达点云
        self._init_pointcloud_page()

        # 页面3：运行日志
        self._init_log_page()

        main_layout.addWidget(self.content_stack, 1)

    def _init_flight_page(self):
        """初始化飞行状态页面"""
        flight_page = QWidget()
        flight_layout = QVBoxLayout(flight_page)
        flight_layout.setContentsMargins(16, 16, 16, 16)
        flight_layout.setSpacing(12)

        # 页面标题
        page_title = QLabel("飞行状态监控")
        page_title.setStyleSheet("color: #e0e6ed; font-size: 18px; font-weight: 600;")
        flight_layout.addWidget(page_title)

        # 内容分割器
        content_splitter = QSplitter(Qt.Vertical)

        # 上：飞行状态详情
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
        detail_layout.addRow("飞行模式:", self.detail_labels["mode"])
        detail_layout.addRow("剩余电量:", self.detail_labels["battery_percent"])
        detail_layout.addRow("电池电压:", self.detail_labels["battery_voltage"])
        detail_layout.addRow("纬度:", self.detail_labels["lat"])
        detail_layout.addRow("经度:", self.detail_labels["lon"])
        detail_layout.addRow("相对高度:", self.detail_labels["alt"])
        detail_layout.addRow("横滚角:", self.detail_labels["roll"])
        detail_layout.addRow("俯仰角:", self.detail_labels["pitch"])
        detail_layout.addRow("偏航角:", self.detail_labels["yaw"])

        content_splitter.addWidget(detail_box)

        # 下：原始JSON报文
        json_box = QGroupBox("原始 JSON 报文")
        json_layout = QVBoxLayout(json_box)
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setFont(QFont("Consolas", 9))
        json_layout.addWidget(self.json_view)
        content_splitter.addWidget(json_box)

        # 分割比例
        content_splitter.setSizes([300, 300])

        flight_layout.addWidget(content_splitter, 1)

        self.content_stack.addWidget(flight_page)

    def _init_pointcloud_page(self):
        """初始化激光雷达点云页面"""
        pc_page = QWidget()
        pc_layout = QVBoxLayout(pc_page)
        pc_layout.setContentsMargins(16, 16, 16, 16)
        pc_layout.setSpacing(12)

        # 页面标题
        title_layout = QHBoxLayout()

        page_title = QLabel("激光雷达点云")
        page_title.setStyleSheet("color: #e0e6ed; font-size: 18px; font-weight: 600;")
        title_layout.addWidget(page_title)

        title_layout.addStretch()

        # 视图控制按钮
        self.btn_reset_view = QPushButton("重置视图")
        self.btn_reset_view.setFixedHeight(32)
        self.btn_reset_view.setCursor(Qt.PointingHandCursor)
        self.btn_reset_view.setStyleSheet("""
            QPushButton {
                background-color: #1e3a5f;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 0 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a4a73;
            }
        """)
        self.btn_reset_view.clicked.connect(self._reset_pointcloud_view)
        title_layout.addWidget(self.btn_reset_view)

        pc_layout.addLayout(title_layout)

        # 主内容区：左侧点云视图，右侧信息面板
        main_splitter = QSplitter(Qt.Horizontal)

        # 点云视图
        self.pointcloud_view = PointCloud3DWidget()
        main_splitter.addWidget(self.pointcloud_view)

        # 右侧信息面板
        info_panel = QWidget()
        info_panel.setFixedWidth(240)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(12)

        # 点云信息
        info_box = QGroupBox("点云信息")
        info_form = QFormLayout(info_box)
        info_form.setLabelAlignment(Qt.AlignRight)
        info_form.setVerticalSpacing(8)

        self.pc_info_labels = {
            "num_points": QLabel("-"),
            "frame_id": QLabel("-"),
            "seq": QLabel("-"),
            "timestamp": QLabel("-"),
        }

        highlight_style = "color: #00d4ff; font-weight: 500;"
        self.pc_info_labels["num_points"].setStyleSheet(highlight_style)

        info_form.addRow("点数量:", self.pc_info_labels["num_points"])
        info_form.addRow("坐标系:", self.pc_info_labels["frame_id"])
        info_form.addRow("帧序号:", self.pc_info_labels["seq"])
        info_form.addRow("时间戳:", self.pc_info_labels["timestamp"])

        info_layout.addWidget(info_box)

        # 显示设置
        display_box = QGroupBox("显示设置")
        display_layout = QVBoxLayout(display_box)
        display_layout.setSpacing(8)

        # 视图模式
        view_mode_label = QLabel("视图模式:")
        view_mode_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        display_layout.addWidget(view_mode_label)

        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["俯视图 (XY)", "前视图 (XZ)", "侧视图 (YZ)"])
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        display_layout.addWidget(self.view_mode_combo)

        # 显示选项
        self.show_grid_check = QCheckBox("显示网格")
        self.show_grid_check.setChecked(True)
        display_layout.addWidget(self.show_grid_check)

        self.show_axes_check = QCheckBox("显示坐标轴")
        self.show_axes_check.setChecked(True)
        display_layout.addWidget(self.show_axes_check)

        info_layout.addWidget(display_box)

        # 操作提示
        tip_box = QGroupBox("操作提示")
        tip_layout = QVBoxLayout(tip_box)

        tips = [
            "• 鼠标滚轮：缩放视图",
            "• 按住左键拖拽：旋转视角",
            "• 按住右键拖拽：平移视图",
            "• 鼠标中键：重置视角",
            "  （类似 rviz 操作方式）",
        ]
        for tip in tips:
            tip_label = QLabel(tip)
            tip_label.setStyleSheet("color: #6b7280; font-size: 11px;")
            tip_layout.addWidget(tip_label)

        info_layout.addWidget(tip_box)

        info_layout.addStretch()

        main_splitter.addWidget(info_panel)

        # 分割比例
        main_splitter.setSizes([800, 240])

        pc_layout.addWidget(main_splitter, 1)

        self.content_stack.addWidget(pc_page)

    def _init_log_page(self):
        """初始化运行日志页面"""
        log_page = QWidget()
        log_layout = QVBoxLayout(log_page)
        log_layout.setContentsMargins(16, 16, 16, 16)
        log_layout.setSpacing(12)

        # 页面标题
        title_layout = QHBoxLayout()

        page_title = QLabel("运行日志")
        page_title.setStyleSheet("color: #e0e6ed; font-size: 18px; font-weight: 600;")
        title_layout.addWidget(page_title)

        title_layout.addStretch()

        # 清空日志按钮
        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.setFixedHeight(32)
        self.btn_clear_log.setCursor(Qt.PointingHandCursor)
        self.btn_clear_log.setStyleSheet("""
            QPushButton {
                background-color: #1e3a5f;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 0 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a4a73;
            }
        """)
        self.btn_clear_log.clicked.connect(self._clear_log)
        title_layout.addWidget(self.btn_clear_log)

        log_layout.addLayout(title_layout)

        # 日志视图
        log_box = QGroupBox("系统运行日志")
        log_box_layout = QVBoxLayout(log_box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Microsoft YaHei", 9))
        log_box_layout.addWidget(self.log_view)

        log_layout.addWidget(log_box, 1)

        self.content_stack.addWidget(log_page)

    def _switch_page(self, page_name: str):
        """切换页面"""
        self._current_page = page_name

        # 更新导航按钮状态
        for name, btn in self._nav_buttons.items():
            btn.setChecked(name == page_name)

        # 切换堆叠页面
        page_index = {
            "flight": 0,
            "pointcloud": 1,
            "log": 2,
        }.get(page_name, 0)

        self.content_stack.setCurrentIndex(page_index)

        # 切换到对应页面时刷新数据
        current_item = self.drone_list.currentItem()
        if current_item:
            drone_id = current_item.text()
            if page_name == "flight":
                self._update_drone_detail(drone_id)
            elif page_name == "pointcloud":
                self._update_pointcloud_view(drone_id)

    def _on_drone_selected(self, current, previous):
        """设备选中事件"""
        if current:
            drone_id = current.text()
            if self._current_page == "flight":
                self._update_drone_detail(drone_id)
            elif self._current_page == "pointcloud":
                self._update_pointcloud_view(drone_id)

    def _update_drone_detail(self, drone_id):
        """更新飞行状态详情"""
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

        # 3. 正常填充数据
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

        # JSON视图按需更新
        self.json_view.setPlainText(
            json.dumps(status, indent=2, ensure_ascii=False)
        )

    def _update_pointcloud_view(self, drone_id):
        """更新点云视图"""
        pointcloud_data = self.gs.get_drone_pointcloud(drone_id)
        if not pointcloud_data:
            return

        # 解码点云
        points = pointcloud_data.decode_points()

        # 更新视图
        self.pointcloud_view.update_points(points)

        # 更新信息面板
        self.pc_info_labels["num_points"].setText(f"{pointcloud_data.num_points} 点")
        self.pc_info_labels["frame_id"].setText(pointcloud_data.frame_id)
        self.pc_info_labels["seq"].setText(str(pointcloud_data.seq))
        self.pc_info_labels["timestamp"].setText(pointcloud_data.timestamp[11:23] if len(pointcloud_data.timestamp) > 11 else pointcloud_data.timestamp)

    def _reset_pointcloud_view(self):
        """重置点云视图"""
        self.pointcloud_view.reset_view()

    def _on_view_mode_changed(self, index):
        """视图模式切换"""
        modes = ["top", "front", "side"]
        if 0 <= index < len(modes):
            self.pointcloud_view.set_view_mode(modes[index])

    def _clear_log(self):
        """清空日志"""
        self.log_view.clear()

    def _append_log(self, text: str, color: str = "#c9d1d9"):
        """带颜色的日志输出，区分上线/离线/普通信息"""
        html = f'<span style="color: {color};">{text}</span>'
        self.log_view.append(html)
        # 自动滚动到底部
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """窗口关闭时通知业务层释放资源"""
        self.refresh_timer.stop()
        self.gs.stop()
        event.accept()
