VERSION = '1.0.3'

#: Canvas of a brand-new project, in game pixels.
#:
#: 16:9 is the shape a phone screen has in landscape (the default Android
#: orientation) and the shape a desktop monitor and the web player expect, so
#: a new game fills the screen on all three. 720p keeps the scene editor
#: usable at 1:1 and scales by whole numbers on the common panels
#: (1.5x = 1080p, 2x = 1440p, 3x = 4K), which matters because the engine
#: presents with nearest-neighbour filtering by default.
DEFAULT_SCREEN_SIZE = (1280, 720)