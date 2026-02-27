# coding=utf-8
"""
    create by pymu
    on 2020/12/10
    at 17:17
"""
import sys
from typing import Tuple

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QDialog



class FrameLessWindowHint(QDialog):
    # 页面上的主要容器，控件应该放在这个里面
    body_widget: QtWidgets.QWidget = None
    # 顶部标题栏
    bar: QtWidgets.QWidget = None
    # 移动坐标
    move_drag_position: QPoint = None
    # 窗口拉伸边界
    border: int = 5

    class EventFlags:
        """扳机状态，用于判定鼠标事件是否触发"""
        event_flag_bar_move = False
        event_flag_border_left = False
        event_flag_border_right = False
        event_flag_border_top = False
        event_flag_border_bottom = False
        event_flag_border_top_left = False
        event_flag_border_top_right = False
        event_flag_border_bottom_left = False
        event_flag_border_bottom_right = False

        # 不得已以为拉伸闪烁问题
        # 只能设定固定方向的拉伸能够使用
        # 当然全部打开也是可以的，只是存在闪烁问题
        # PC端的应用大部分存在这个问题，所以用也可以
        event_switch_border_left = False
        event_switch_border_right = True
        event_switch_border_top = False
        event_switch_border_bottom = True
        event_switch_border_top_left = False
        event_switch_border_top_right = False
        event_switch_border_bottom_left = False
        event_switch_border_bottom_right = True

    def __init__(self, flag=None):
        """自定义窗口"""
        super().__init__(flag)
        self.procedure()

    def procedure(self):
        """
        初始化流程
        """
        self.place()
        self.configure()
        self.set_signal()

    def set_signal(self):
        pass

    def configure(self):
        """
        设置主窗体背景透明；隐藏边框;
        """
        self.resize(1047, 680)
        self.setWindowTitle("应用名称")
        self.setStyleSheet("QWidget{border-radius:7px;background-color:rgb(255,255,255);}")
        self.setMouseTracking(True)
        self.body_widget.setMouseTracking(True)
        # self.setWindowIcon(self.resource.qt_icon_project_ico)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.set_default_window_shadow()
        self.bar = self.body_widget

    def set_default_window_shadow(self):
        """设置默认阴影"""
        effect_shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        # 偏移
        effect_shadow.setOffset(0, 0)
        # 阴影半径
        effect_shadow.setBlurRadius(10)
        # 阴影颜色
        effect_shadow.setColor(QtCore.Qt.red)
        self.set_window_shadow(effect_shadow)

    def set_window_shadow(self, shadow: QtWidgets.QGraphicsDropShadowEffect):
        """设置窗口的阴影"""
        self.body_widget.setGraphicsEffect(shadow)

    def place(self):
        """
        创建一个无边框的窗体，附带界面阴影窗口拉伸
        """
        body_layout = QtWidgets.QHBoxLayout(self)
        self.body_widget = QtWidgets.QWidget()
        body_layout.addWidget(self.body_widget)

    def event_flag(self, event: QtGui.QMouseEvent) -> Tuple[bool, bool, bool, bool]:
        """判断鼠标是否移动到边界"""
        top = self.border < event.pos().y() < self.border + 10
        bottom = self.border + self.body_widget.height() < event.pos().y() < self.height()
        left = self.border < event.pos().x() < self.border + 10
        right = self.border + self.body_widget.width() < event.pos().x() < self.width()
        return top, bottom, left, right

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """重构鼠标点击事件"""
        super(FrameLessWindowHint, self).mousePressEvent(event)
        if not self.body_widget:
            return super(FrameLessWindowHint, self).mousePressEvent(event)
        top, bottom, left, right = self.event_flag(event)
        # 左键事件
        if event.button() == Qt.LeftButton:
            self.move_drag_position = event.globalPos() - self.pos()
            if top and left and self.EventFlags.event_switch_border_top_left:
                self.EventFlags.event_flag_border_top_left = True
            elif top and right and self.EventFlags.event_switch_border_top_right:
                self.EventFlags.event_flag_border_top_right = True
            elif bottom and left and self.EventFlags.event_switch_border_bottom_left:
                self.EventFlags.event_flag_border_bottom_left = True
            elif bottom and right and self.EventFlags.event_switch_border_bottom_right:
                self.EventFlags.event_flag_border_bottom_right = True
            elif top and self.EventFlags.event_switch_border_top:
                self.EventFlags.event_flag_border_top = True
            elif bottom and self.EventFlags.event_switch_border_bottom:
                self.EventFlags.event_flag_border_bottom = True
            elif left and self.EventFlags.event_switch_border_left:
                self.EventFlags.event_flag_border_left = True
            elif right and self.EventFlags.event_switch_border_right:
                self.EventFlags.event_flag_border_right = True
            elif self.bar and event.y() < self.bar.height():
                self.EventFlags.event_flag_bar_move = True
                self.move_drag_position = event.globalPos() - self.pos()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """鼠标移动事件"""
        super(FrameLessWindowHint, self).mouseMoveEvent(event)
        if self.body_widget:
            top, bottom, left, right = self.event_flag(event)
            if top and left and self.EventFlags.event_switch_border_top_left:
                self.setCursor(Qt.SizeFDiagCursor)
            elif bottom and right and self.EventFlags.event_switch_border_bottom_right:
                self.setCursor(Qt.SizeFDiagCursor)
            elif top and right and self.EventFlags.event_switch_border_top_right:
                self.setCursor(Qt.SizeBDiagCursor)
            elif bottom and left and self.EventFlags.event_switch_border_bottom_left:
                self.setCursor(Qt.SizeBDiagCursor)
            elif top and self.EventFlags.event_switch_border_top:
                self.setCursor(Qt.SizeVerCursor)
            elif bottom and self.EventFlags.event_switch_border_bottom:
                self.setCursor(Qt.SizeVerCursor)
            elif left and self.EventFlags.event_switch_border_left:
                self.setCursor(Qt.SizeHorCursor)
            elif right and self.EventFlags.event_switch_border_right:
                self.setCursor(Qt.SizeHorCursor)
            elif Qt.LeftButton and self.EventFlags.event_flag_bar_move:
                self.move(event.globalPos() - self.move_drag_position)
            else:
                self.setCursor(Qt.ArrowCursor)

            # 窗口拉伸
            if self.EventFlags.event_flag_border_top_left:
                self.setGeometry(self.geometry().x() + event.pos().x(), self.geometry().y() + event.pos().y(),
                                 self.width() - event.pos().x(), self.height() - event.pos().y())

            elif self.EventFlags.event_flag_border_bottom_right:
                self.resize(event.pos().x(), event.pos().y())

            elif self.EventFlags.event_flag_border_bottom_left:
                self.setGeometry(self.geometry().x() + event.pos().x(), self.geometry().y(),
                                 self.width() - event.pos().x(), event.pos().y())

            elif self.EventFlags.event_flag_border_top_right:
                self.setGeometry(self.geometry().x(), self.geometry().y() + event.pos().y(),
                                 event.pos().x(), self.height() - event.pos().y())

            elif self.EventFlags.event_flag_border_right:
                self.resize(event.pos().x(), self.height())

            elif self.EventFlags.event_flag_border_left:
                self.setGeometry(self.geometry().x() + event.pos().x(), self.geometry().y(),
                                 self.width() - event.pos().x(), self.height())

            elif self.EventFlags.event_flag_border_bottom:
                self.resize(self.width(), event.pos().y())

            elif self.EventFlags.event_flag_border_top:
                self.setGeometry(self.geometry().x(), self.geometry().y() + event.pos().y(),
                                 self.width(), self.height() - event.pos().y())

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """鼠标释放事件"""
        super(FrameLessWindowHint, self).mouseReleaseEvent(event)
        self.EventFlags.event_flag_bar_move = False
        self.EventFlags.event_flag_border_left = False
        self.EventFlags.event_flag_border_right = False
        self.EventFlags.event_flag_border_top = False
        self.EventFlags.event_flag_border_bottom = False
        self.EventFlags.event_flag_border_top_left = False
        self.EventFlags.event_flag_border_top_right = False
        self.EventFlags.event_flag_border_bottom_left = False
        self.EventFlags.event_flag_border_bottom_right = False


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = FrameLessWindowHint()
    MainWindow.show()
    sys.exit(app.exec_())

