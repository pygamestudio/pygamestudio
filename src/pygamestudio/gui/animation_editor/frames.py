"""Dropped frame images for the animation editor.

The animation editor accepts image files (or a folder of images) dropped
onto it from the file manager or the asset panel and turns them into one
keyframe per image. The helpers here are pure: they read a drag's MIME data
and collect the image files, naturally sorted, so 'frame2.png' comes before
'frame10.png' - the same order the frame-sequence object and the sprite
sheet slicer use.
"""
from pathlib import Path

from pygamestudio.game.object.frame_sequence import _natural_key

#: Formats a keyframe image can be shown in (the runtime loads them with
#: pygame, which reads all of these).
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tga')


def mime_paths(mime):
    """The local file paths carried by a drag ([] when there are none)."""
    if mime is None:
        return []
    paths = []
    if mime.hasUrls():
        for url in mime.urls():
            local = url.toLocalFile()
            if local:
                paths.append(local)
    elif mime.hasText():
        # Some sources only publish plain text paths; keep those working too.
        paths.extend(line.strip() for line in mime.text().splitlines()
                     if line.strip())
    return paths


def collect_frame_images(paths):
    """The image files of the dropped paths, naturally sorted by file name.

    A dropped folder expands to the image files directly inside it (the
    sprite sheet slicer writes its frames to a '<name>_frames' folder, so
    that folder can be dropped as a whole); files of other types are
    ignored.
    """
    found = []
    for text in paths:
        path = Path(text)
        if path.is_dir():
            found.extend(child for child in path.iterdir()
                         if child.is_file()
                         and child.suffix.lower() in IMAGE_SUFFIXES)
        elif path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            found.append(path)
    return sorted(found, key=lambda path: _natural_key(path.name))
