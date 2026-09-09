from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class SuffixSpinBox(QDoubleSpinBox):
    def __init__(self):
        super().__init__()
        self._suffix = ''
        self._suffix_label = QLabel()

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_layout()

    def _set_widget(self):
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._suffix_label.setText(self._suffix)
        self._suffix_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                padding-right: 2px;
                font-size: 10px;
                font-family: Times New Roman;
            }
        """)

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
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setRange(-999999, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        if 'x' in attr:
            self.set_suffix('X')
        elif 'y' in attr:
            self.set_suffix('Y')

        if attr == 'start_x' or attr == 'start_y':
            self.valueChanged.connect(self._inspector_container.set_object_start_point)
        elif attr == 'end_x' or attr == 'end_y':
            self.valueChanged.connect(self._inspector_container.set_object_end_point)
        else:
            self.valueChanged.connect(self._inspector_container.move_object)


class SizeSpinBox(SuffixSpinBox):
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        if attr == 'width':
            self.set_suffix('W')
        elif attr == 'height':
            self.set_suffix('H')

        self.valueChanged.connect(self._inspector_container.resize_object)


class ScaleSpinBox(SuffixSpinBox):
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setRange(0, 999999)
        self.setSingleStep(0.01)
        self.setValue(value)
        self.setDecimals(2)

        if attr == 'scale_x':
            self.set_suffix('X')
        elif attr == 'scale_y':
            self.set_suffix('Y')

        self.valueChanged.connect(self._inspector_container.scale_object)


class AngleSpinBox(QDoubleSpinBox):
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setRange(-360, 360)
        self.setSingleStep(0.01)
        self.setValue(value)
        self.setDecimals(2)

        self.valueChanged.connect(self._inspector_container.rotate_object)


class ThicknessSpinBox(SuffixSpinBox):
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        self.valueChanged.connect(self._inspector_container.set_object_thickness)


class BorderRadiusSpinBox(SuffixSpinBox):
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
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
        self._inspector_container.set_object_border_radius(self._attr, int(self.value()))


class FontSizeSpinBox(QDoubleSpinBox):
    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setValue(value)
        self.setDecimals(0)

        self.valueChanged.connect(self._inspector_container.set_object_font_size)


class TextInputParameterSpinBox(SuffixSpinBox):
    """Integer spinbox for a text-input box numeric parameter such as
    max_length (0 = unlimited)."""

    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setDecimals(0)
        self.setValue(value)

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self):
        self._inspector_container.set_object_text_input_parameter(
            self._attr, int(self.value()))


class ParticleParameterSpinBox(SuffixSpinBox):
    """Spinbox for one particle-emitter parameter (emission rate, lifetime,
    speed, gravity, ...)."""

    _SUFFIXES = {
        'emission_rate': '/s',
        'max_particles': '',
        'particle_lifetime': 's',
        'particle_speed': 'px/s',
        'particle_size': 'px',
        'gravity': 'px/s2',
        'spread_angle': '°',
    }

    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setDecimals(0)
        self.setValue(value)
        self.set_suffix(self._SUFFIXES.get(attr, ''))

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self):
        self._inspector_container.set_object_particle_parameter(self._attr, int(self.value()))


class FrameSequenceSpinBox(SuffixSpinBox):
    """Spinbox for one frame-sequence parameter (frame rate, ...)."""

    _SUFFIXES = {
        'frame_rate': 'fps',
    }

    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        self.setRange(0, 999999)
        self.setSingleStep(1 if attr == 'frame_rate' else 0.1)
        self.setDecimals(2 if attr == 'frame_rate' else 0)
        self.setValue(value)
        self.set_suffix(self._SUFFIXES.get(attr, ''))

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self):
        new_value = float(self.value()) if self.decimals() > 0 else int(self.value())
        self._inspector_container.set_object_frame_sequence_parameter(self._attr, new_value)


class CollisionSpinBox(SuffixSpinBox):
    """Spinbox for one collision parameter: offset x/y or box size w/h. All
    values are integers (content pixels)."""

    _SUFFIXES = {
        'collision_offset_x': 'X',
        'collision_offset_y': 'Y',
        'collision_width': 'W',
        'collision_height': 'H',
    }

    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        if 'offset' in attr:
            self.setRange(-999999, 999999)
        else:
            self.setRange(0, 999999)
        self.setSingleStep(1)
        self.setDecimals(0)
        self.setValue(value)
        self.set_suffix(self._SUFFIXES.get(attr, ''))

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self):
        self._inspector_container.set_object_collision_parameter(self._attr, int(self.value()))


class TileMapSpinBox(SuffixSpinBox):
    """Spinbox for one tile-map parameter: tile_width/tile_height in px, or
    the grid size columns/rows (in tiles). Minimum value is 1."""

    _SUFFIXES = {
        'tile_width': 'px',
        'tile_height': 'px',
        'columns': '',
        'rows': '',
    }

    def __init__(self, inspector_container, value, attr=''):
        super().__init__()
        self._inspector_container = inspector_container
        self._attr = attr
        self.setRange(1, 999999)
        self.setSingleStep(1)
        self.setDecimals(0)
        self.setValue(value)
        self.set_suffix(self._SUFFIXES.get(attr, ''))

        self.valueChanged.connect(self._on_value_changed)

    def _on_value_changed(self):
        self._inspector_container.set_object_tile_map_parameter(
            self._attr, int(self.value()))