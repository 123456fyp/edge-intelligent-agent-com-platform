# -*- coding: utf-8 -*-
"""UI 3D OpenGL控件，仅转发事件、读取logic渲染"""
from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QPoint
try:
    from OpenGL.GL import *
    from OpenGL.GLU import *
except ImportError:
    pass

from ui.view_logic.cloud_3d_logic import PointCloud3DLogic

class PointCloud3DWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        # 绑定ui内部逻辑实例
        self.logic = PointCloud3DLogic()

    def update_points(self, points):
        self.logic.update_point_data(points)
        self._calc_point_color()
        self.update()

    def _calc_point_color(self):
        logic = self.logic
        pts = logic.points
        for pt in pts:
            if logic.color_mode == "intensity" and "intensity" in pt:
                val = pt["intensity"] / 255.0 if pt["intensity"] > 1 else pt["intensity"]
                val = max(0.0, min(1.0, val))
                if val < 0.25:
                    t = val / 0.25
                    r,g,b = 0.1+0.2*t, 0.4+0.4*t, 0.8+0.2*t
                elif val < 0.5:
                    t = (val-0.25)/0.25
                    r,g,b = 0.3+0.15*t, 0.8+0.2*t, 1.0-0.2*t
                elif val < 0.75:
                    t = (val-0.5)/0.25
                    r,g,b = 0.45+0.55*t, 1.0, 0.8-0.6*t
                else:
                    t = (val-0.75)/0.25
                    r,g,b = 1.0, 1.0-0.4*t, 0.2-0.2*t
            else:
                z = pt.get("z",0)
                z_norm = max(0, min(1, (z+5)/10))
                r = 0.4 + 0.6*z_norm
                g = 0.4 + 0.4*(1-abs(z_norm-0.5)*2)
                b = 1.0 - z_norm
            logic.point_colors.append((r,g,b))

    def reset_view(self):
        self.logic.reset_view()
        self.update()

    def set_view_mode(self, mode):
        self.logic.set_view_preset(mode)
        self.update()

    def initializeGL(self):
        glClearColor(0.04, 0.05, 0.09, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glPointSize(2.0)

    def resizeGL(self, w, h):
        glViewport(0,0,w,h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60.0, w/h if h>0 else 1, 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        l = self.logic
        glTranslatef(l.pan_x, l.pan_y, -l.zoom)
        glRotatef(l.rot_x, 1,0,0)
        glRotatef(l.rot_y, 0,1,0)
        if l.show_grid: self._draw_grid()
        if l.show_axes: self._draw_axes()
        self._draw_points()

    def _draw_grid(self):
        glColor4f(0.1,0.15,0.2,0.5)
        glLineWidth(0.5)
        gs, step = 50,10
        glBegin(GL_LINES)
        for i in range(-gs, gs+1, step):
            glVertex3f(i,0,-gs);glVertex3f(i,0,gs)
            glVertex3f(-gs,0,i);glVertex3f(gs,0,i)
        glEnd()
        glColor4f(0.2,0.25,0.35,0.8)
        glLineWidth(1)
        glBegin(GL_LINES)
        glVertex3f(-gs,0,0);glVertex3f(gs,0,0)
        glVertex3f(0,0,-gs);glVertex3f(0,0,gs)
        glEnd()

    def _draw_axes(self):
        axis_len = 5
        glLineWidth(2)
        glBegin(GL_LINES)
        glColor3f(1,0.3,0.3);glVertex3f(0,0,0);glVertex3f(axis_len,0,0)
        glColor3f(0.3,1,0.3);glVertex3f(0,0,0);glVertex3f(0,0,axis_len)
        glColor3f(0.3,0.5,1);glVertex3f(0,0,0);glVertex3f(0,axis_len,0)
        glEnd()

    def _draw_points(self):
        l = self.logic
        pts, cols = l.points, l.point_colors
        if not pts: return
        glBegin(GL_POINTS)
        for i,pt in enumerate(pts):
            x,y,z = pt.get("x",0), pt.get("y",0), pt.get("z",0)
            if i < len(cols):
                r,g,b = cols[i]
                glColor4f(r,g,b,0.9)
            else:
                glColor4f(0.5,0.8,1,0.9)
            glVertex3f(x, z, -y)
        glEnd()

    # 鼠标事件：仅转发坐标，无计算
    def mousePressEvent(self, event):
        l = self.logic
        l.last_mouse_pos = event.pos()
        if event.button() == Qt.LeftButton:
            l.left_pressed = True
            self.setCursor(Qt.SizeAllCursor)
        elif event.button() == Qt.RightButton:
            l.right_pressed = True
            self.setCursor(Qt.OpenHandCursor)
        elif event.button() == Qt.MiddleButton:
            self.reset_view()

    def mouseMoveEvent(self, event):
        l = self.logic
        delta = event.pos() - l.last_mouse_pos
        if l.left_pressed:
            l.handle_rotate(delta.x(), delta.y())
            self.update()
        elif l.right_pressed:
            l.handle_pan(delta.x(), delta.y())
            self.update()
        l.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event):
        l = self.logic
        if event.button() == Qt.LeftButton:
            l.left_pressed = False
        elif event.button() == Qt.RightButton:
            l.right_pressed = False
        if not l.left_pressed and not l.right_pressed:
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        up = event.angleDelta().y() > 0
        self.logic.handle_zoom(up)
        self.update()