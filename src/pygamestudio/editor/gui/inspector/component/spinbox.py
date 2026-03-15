from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


class SuffixSpinBox(QDoubleSpinBox):
    def __init__(self):
        super().__init__()
        self._suffix = ''
        self._suffix_label = QLabel()

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._suffix_label.setText(self._suffix)
        self._suffix_label.setStyleSheet("""
            QLabel {
                color: gray; 
                padding-right: 5px;                   
            }
        """)
        
    def _set_signal(self):
        ...

    def _set_layout(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch(1)
        main_layout.addWidget(self._suffix_label)

    def set_suffix(self, suffix):
        self._suffix = suffix
        self._suffix_label.setText(self._suffix)

    def enterEvent(self, event):
        self._suffix_label.setText('')
        self.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        return super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._suffix_label.setText(self._suffix)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        return super().leaveEvent(event)


class PosSpinBox(SuffixSpinBox):
    def __init__(self, inspector_window, attr, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(-999999, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        if 'x' in attr:
            self.set_suffix('X')
        elif 'y' in attr:
            self.set_suffix('Y')

        if attr == 'start_x' or attr == 'start_y':
            self.valueChanged.connect(self._inspector_window.set_start_point)
        elif attr == 'end_x' or attr == 'end_y':
            self.valueChanged.connect(self._inspector_window.set_end_point)
        else:
            self.valueChanged.connect(self._inspector_window.move)


class SizeSpinBox(SuffixSpinBox):
    def __init__(self, inspector_window, attr, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        if attr == 'width':
            self.set_suffix('W')
        elif attr == 'height':
            self.set_suffix('H')

        self.valueChanged.connect(self._inspector_window.resize)


class ScaleSpinBox(SuffixSpinBox):
    def __init__(self, inspector_window, attr, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(0, 999999)
        self.setSingleStep(0.01)
        self.setValue(value)
        self.setDecimals(2)

        if attr == 'scale_x':
            self.set_suffix('X')
        elif attr == 'scale_y':
            self.set_suffix('Y')

        self.valueChanged.connect(self._inspector_window.scale)


class AngleSpinBox(QDoubleSpinBox):
    def __init__(self, inspector_window, attr, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(-360, 360)
        self.setSingleStep(0.01)
        self.setValue(value)
        self.setDecimals(2)

        self.valueChanged.connect(self._inspector_window.rotate)


class ThicknessSpinBox(SuffixSpinBox):
    def __init__(self, inspector_window, attr, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        self.valueChanged.connect(self._inspector_window.set_thickness)


class BorderRadiusSpinBox(SuffixSpinBox):
    def __init__(self, inspector_window, attr, value):
        super().__init__()
        self._inspector_window = inspector_window
        self._attr = attr
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        if attr == 'border_top_left_radius':
            self.set_suffix('TL')
        elif attr == 'border_top_right_radius':
            self.set_suffix('TR')
        elif attr == 'border_bottom_left_radius':
            self.set_suffix('BL')
        elif attr == 'border_bottom_right_radius':
            self.set_suffix('BR')
        
        self.valueChanged.connect(self._on_border_radius_changed)

    def _on_border_radius_changed(self):
        self._inspector_window.set_border_radius(self._attr, int(self.value()))
