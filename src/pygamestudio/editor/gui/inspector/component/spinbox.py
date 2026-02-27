from PySide6.QtWidgets import *


class PosSpinBox(QSpinBox):
    def __init__(self, inspector_window, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(-999999, 999999)
        self.setSingleStep(1)
        self.setValue(value)

        self.valueChanged.connect(self._inspector_window.move)


class SizeSpinBox(QSpinBox):
    def __init__(self, inspector_window, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)

        self.valueChanged.connect(self._inspector_window.resize)


class ScaleSpinBox(QDoubleSpinBox):
    def __init__(self, inspector_window, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(-999999, 999999)
        self.setSingleStep(0.01)
        self.setValue(value)

        self.valueChanged.connect(self._inspector_window.scale)


class AngleSpinBox(QDoubleSpinBox):
    def __init__(self, inspector_window, value):
        super().__init__()
        self._inspector_window = inspector_window
        self.setRange(-360, 360)
        self.setSingleStep(0.01)
        self.setValue(value)

        self.valueChanged.connect(self._inspector_window.rotate)