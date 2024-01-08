import math
import sys
from argparse import ArgumentParser

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QPoint, QPointF, QTimer
from PyQt5.QtGui import QColor
from OpenGL.GL import *
from OpenGL.GLU import *


# Radian to degree
def r2d(r):
    return r * 180 / math.pi


# Degree to radian
def d2r(d):
    return d * math.pi / 180


class Camera(object):
    def __init__(self, args):
        self.args = args

        # https://community.gopro.com/s/article/HERO9-Black-Digital-Lenses-FOV-Information?language=en_US
        # Map from camera type to [horiziontal fov (degrees), vertical fov (degrees), ar (vertical / horizontal pixels)]
        # By default, hypersmooth is considered to be off.
        # TODO: consider lens distortion (otherwise tan(vfov/2)/tan(hfov/2) and ar disagree)
        self.intrinsic_library = {
            "gopro9_sv_16_9": (121, 93, 0.5625),
            "gopro9_wide_16_9": (118, 69, 0.5625),
            "gopro9_linear_16_9": (92, 61, 0.5625),
            "gopro9_narrow_16_9": (73, 45, 0.5625),
            "gopro9_wide_4_3": (122, 94, 0.75),
            "gopro9_linear_4_3": (92, 76, 0.75),
            "gopro9_narrow_4_3": (73, 58, 0.75),
            "gopro9_max_sv_16_9": (140, 83, 0.5625),
            "gopro9_max_wide_16_9": (122, 72, 0.5625),
            "gopro9_max_linear_16_9": (86, 55, 0.5625),
            "gopro9_max_sv_4_3": (140, 108, 0.75),
            "gopro9_max_wide_4_3": (122, 94, 0.75),
            "gopro9_max_linear_4_3": (92, 76, 0.75),
        }
        self.hfov_d, self.vfov_d, self.ar = self.intrinsic_library[args.camera_type]
        self.hfov, self.vfov = d2r(self.hfov_d), d2r(self.vfov_d)
        self.near = 1
        self.far = 1000
        self.near_plane_w = self.near * math.tan(self.hfov / 2) * 2
        self.near_plane_h = self.near * math.tan(self.vfov / 2) * 2
        self.far_plane_w = self.far * math.tan(self.hfov / 2) * 2
        self.far_plane_h = self.far * math.tan(self.vfov / 2) * 2
        self.ar = self.near_plane_h / self.near_plane_w

        # Camera center is behind the west goal.
        self.center_x = -self.args.field_length / 2 - self.args.camera_dist_to_field
        self.center_y = 0
        self.center_z = self.args.camera_height

    def apply_intrinsic_transformation(self, win_w, win_h):
        glFrustum(-self.near_plane_w / 2, self.near_plane_w / 2, -self.near_plane_h / 2, self.near_plane_h / 2, self.near, self.far)
        if win_h / win_w > self.ar:
            scaled_h = win_w * self.ar
            glViewport(0, int(win_h / 2 - scaled_h / 2), win_w, int(scaled_h))
        else:
            scaled_w = win_h / self.ar
            glViewport(int(win_w / 2 - scaled_w / 2), 0, int(scaled_w), win_h)

    def apply_extrinsic_transformation(self):
        glRotated(-self.args.camera_pitch, 1, 0, 0)
        glRotated(-self.args.camera_yaw, 0, 1, 0)
        # Camera mount has a 45 degree vertical tilt.
        glRotated(-45.0, 1, 0, 0)
        # Look east from behind the west goal.
        glRotated(90, 0, 0, 1)
        glTranslated(-self.center_x, -self.center_y, -self.center_z)


class CamSimViewport(QtWidgets.QOpenGLWidget):
    def __init__(self, args):
        super(CamSimViewport, self).__init__()
        self.args = args

        self.repaint_timer = QTimer()
        self.repaint_timer.timeout.connect(self.update)
        self.repaint_timer.start(50)
        self.setMouseTracking(True)

        self.camera = Camera(args)

    def initializeGL(self):
        glClearColor(0.1, 0.1, 0.1, 0.0)
        glClearDepth(1.0)
        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w, h):
        self.w = w * 2
        self.h = h * 2
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_P:
            print("Camera extrinsics: ", self.camera.center_x, self.camera.center_y, self.camera.center_z, self.args.camera_yaw, self.args.camera_pitch)
            print("Camera intrinsics: ", self.camera.hfov, self.camera.vfov, self.camera.ar)
        event.accept()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        self.camera.apply_intrinsic_transformation(self.w, self.h)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        self.camera.apply_extrinsic_transformation()

        # Render the field.
        glLineWidth(1)
        # Borders.
        glBegin(GL_LINES)
        # West goal line.
        glColor3d(1, 0, 0)
        glVertex3d(-self.args.field_length / 2, self.args.field_width / 2, 0)
        glVertex3d(-self.args.field_length / 2, -self.args.field_width / 2, 0)
        # East goal line.
        glColor3d(0, 0, 1)
        glVertex3d(self.args.field_length / 2, -self.args.field_width / 2, 0)
        glVertex3d(self.args.field_length / 2, self.args.field_width / 2, 0)
        # North side line.
        glColor3d(0, 1, 0)
        glVertex3d(self.args.field_length / 2, self.args.field_width / 2, 0)
        glVertex3d(-self.args.field_length / 2, self.args.field_width / 2, 0)
        # South side line.
        glColor3d(1, 1, 0)
        glVertex3d(-self.args.field_length / 2, -self.args.field_width / 2, 0)
        glVertex3d(self.args.field_length / 2, -self.args.field_width / 2, 0)
        # Halfway line.
        glColor3d(0.5, 0.5, 0.5)
        glVertex3d(0, -self.args.field_width / 2, 0)
        glVertex3d(0, self.args.field_width / 2, 0)
        glEnd()

        # Goals.
        # West side goal.
        glColor3d(1, 0.7, 0.7)
        glBegin(GL_LINE_STRIP)
        glVertex3d(-self.args.field_length / 2, -self.args.goal_width / 2, 0)
        glVertex3d(-self.args.field_length / 2, self.args.goal_width / 2, 0)
        glVertex3d(-self.args.field_length / 2, self.args.goal_width / 2, self.args.goal_height)
        glVertex3d(-self.args.field_length / 2, -self.args.goal_width / 2, self.args.goal_height)
        glVertex3d(-self.args.field_length / 2, -self.args.goal_width / 2, 0)
        glEnd()
        # East side goal.
        glColor3d(0.7, 0.7, 1)
        glBegin(GL_LINE_STRIP)
        glVertex3d(self.args.field_length / 2, -self.args.goal_width / 2, 0)
        glVertex3d(self.args.field_length / 2, self.args.goal_width / 2, 0)
        glVertex3d(self.args.field_length / 2, self.args.goal_width / 2, self.args.goal_height)
        glVertex3d(self.args.field_length / 2, -self.args.goal_width / 2, self.args.goal_height)
        glVertex3d(self.args.field_length / 2, -self.args.goal_width / 2, 0)
        glEnd()

        # Center circle.
        N = 72
        r = 5
        glColor3d(0.0, 0.5, 0.5)
        glBegin(GL_LINES)
        for i in range(N):
            t0 = 2 * math.pi * i / N
            t1 = 2 * math.pi * (i + 1) / N
            glVertex3d(r * math.cos(t0), r * math.sin(t0), 0)
            glVertex3d(r * math.cos(t1), r * math.sin(t1), 0)
        glEnd()

        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        self.check_opengl_error()

    def check_opengl_error(self):
        error = glGetError()
        if error != GL_NO_ERROR:
            print("OpenGL error: ", gluErrorString(error))


class CamSimWindow(QtWidgets.QMainWindow):
    def __init__(self, qt_app, args):
        super(CamSimWindow, self).__init__()
        self.qt_app = qt_app
        self.args = args

        self.setWindowTitle("Camera Simulator")
        self.viewport = CamSimViewport(self.args)
        self.setCentralWidget(self.viewport)

        self.show()
        self.setFocus()

    def exit(self):
        self.close()

    def paintEvent(self, event):
        QtWidgets.QMainWindow.paintEvent(self, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Q:
            self.exit()
        else:
            self.viewport.keyPressEvent(event)
        event.accept()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("--field_length", type=float, default=56, help="Length of the soccer field.")
    parser.add_argument("--field_width", type=float, default=45, help="Width of the soccer field.")
    parser.add_argument("--goal_width", type=float, default=5, help="Width of the goal.")
    parser.add_argument("--goal_height", type=float, default=2, help="Height of the goal.")
    parser.add_argument("--camera_dist_to_field", type=float, default=2.5, help="Distance from camera's ground projection to the closest point in the field.")
    parser.add_argument("--camera_height", type=float, default=5, help="Camera height from ground.")
    parser.add_argument("--camera_type", type=str, default="gopro9_wide_4_3", help="Camera config type, from which FoV info is inferred. See supported types in code.")
    parser.add_argument("--camera_yaw", type=float, default=0, help="Camera yaw angle (relative to the mount surface) in degrees. CCW for positive.")
    parser.add_argument("--camera_pitch", type=float, default=10, help="Camera pitch angle (relative to the mount surface) in degrees. Up for positive.")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    win = CamSimWindow(app, args)
    win.resize(1600, 900)

    print("Using camera model: ", args.camera_type)
    app.exec_()

