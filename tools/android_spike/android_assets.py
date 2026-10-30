"""Write the launcher icon / presplash / app name into a p4a dist.

This is the prototype of the asset-injection step the editor will run before
Gradle packages the APK: it only touches files inside ``src/main/res`` of the
dist, so it works on CI today and on a user machine later.

What p4a's SDL2 bootstrap actually reads (verified against its Java sources):

* ``AndroidManifest.xml``: ``android:icon="@mipmap/icon"`` and
  ``android:label="@string/app_name"``.
* the first screen is built in ``PythonActivity.getLoadingScreen()`` as an
  ``ImageView`` with **ScaleType.FIT_CENTER** showing ``R.drawable.presplash``,
  painted over ``R.string.presplash_color`` - so the image is never cropped and
  never stretched, and the colour fills the bars on screens with another aspect
  ratio. Keeping both in sync makes the splash seamless on any device.

Usage::

    py -3.10 tools/android_spike/android_assets.py <dist_dir> \
        --icon assets/icon.png --presplash assets/presplash.jpg \
        [--app-name "My Game"] [--background auto|#rrggbb] [--no-adaptive]
"""

import argparse
import re
import sys
from pathlib import Path

try:                                                    # editor / developer machine
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    BACKEND = 'PySide6'
except ImportError:                                     # plain build container
    from PIL import Image

    BACKEND = 'Pillow'

#: Launcher icon size per density bucket (48dp).
LAUNCHER_SIZES = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
#: Adaptive icon canvas per density bucket (108dp).
ADAPTIVE_SIZES = {'mdpi': 108, 'hdpi': 162, 'xhdpi': 216, 'xxhdpi': 324, 'xxxhdpi': 432}
#: The artwork of an adaptive icon has to stay inside the centre 66% (72dp of 108dp).
ADAPTIVE_SAFE_ZONE = 72 / 108
#: Longest edge of the written presplash, keeps the APK small.
PRESPLASH_MAX = (1920, 1080)
PRESPLASH_QUALITY = 90

ADAPTIVE_XML = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background"/>
    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
</adaptive-icon>
'''

COLORS_XML = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">{color}</color>
</resources>
'''


def load_image(path, what):
    if BACKEND == 'PySide6':
        image = QImage(path.as_posix())
        if image.isNull():
            raise SystemExit(f'cannot read {what}: {path}')
        return image
    try:
        return Image.open(path.as_posix())
    except Exception as error:                          # noqa: BLE001 - report and stop
        raise SystemExit(f'cannot read {what}: {path} ({error})')


def image_size(image):
    if BACKEND == 'PySide6':
        return image.width(), image.height()
    return image.size


def fit(image, size):
    """Scale to fit inside ``size`` (keeps the aspect ratio, smooth filter)."""
    width, height = size
    if BACKEND == 'PySide6':
        return image.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
    scaled = image.copy()
    scaled.thumbnail((width, height), Image.LANCZOS)
    return scaled


def square_on_transparent(image, size, fill_ratio=1.0):
    """Centre the artwork on a transparent square canvas of ``size``.

    ``fill_ratio`` shrinks the artwork into a smaller centred box - the adaptive
    icon needs that safe zone because launchers may crop the outer third.
    """
    box = max(1, int(round(size * fill_ratio)))
    scaled = fit(image, (box, box))
    scaled_w, scaled_h = image_size(scaled)

    if BACKEND == 'PySide6':
        canvas = QImage(size, size, QImage.Format.Format_ARGB32)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawImage((size - scaled_w) // 2, (size - scaled_h) // 2, scaled)
        painter.end()
        return canvas

    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(scaled.convert('RGBA'), ((size - scaled_w) // 2, (size - scaled_h) // 2))
    return canvas


def flatten(image, background):
    """Composite onto a flat colour (JPEG has no alpha channel)."""
    if BACKEND == 'PySide6':
        canvas = QImage(image.size(), QImage.Format.Format_RGB32)
        canvas.fill(QColor(background))
        painter = QPainter(canvas)
        painter.drawImage(0, 0, image)
        painter.end()
        return canvas
    canvas = Image.new('RGB', image_size(image), background)
    rgba = image.convert('RGBA')
    canvas.paste(rgba, (0, 0), rgba)
    return canvas


def save_png(image, path):
    if BACKEND == 'PySide6':
        image.save(path.as_posix(), 'PNG')
    else:
        image.save(path.as_posix(), 'PNG')


def save_jpeg(image, path, quality):
    if BACKEND == 'PySide6':
        ok = image.save(path.as_posix(), 'JPEG', quality)
    else:
        image.convert('RGB').save(path.as_posix(), 'JPEG', quality=quality)
        ok = True
    if not ok:
        raise SystemExit(f'could not write {path}')


def corner_color(image, fallback='#000000'):
    """The colour the splash bars should be painted in."""
    width, height = image_size(image)
    points = ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))

    if BACKEND == 'PySide6':
        colors = {image.pixelColor(x, y).name() for x, y in points}
    else:
        rgb = image.convert('RGB')
        colors = {'#%02x%02x%02x' % rgb.getpixel(point) for point in points}

    if len(colors) == 1:
        return colors.pop()
    print(f'  presplash corners differ ({", ".join(sorted(colors))}), using {fallback}')
    return fallback


def write_launcher_icon(res_dir, image):
    written = []
    for density, size in LAUNCHER_SIZES.items():
        folder = res_dir / f'mipmap-{density}'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'icon.png'
        save_png(square_on_transparent(image, size), target)
        written.append(target)

        # p4a's launcher resources use the same picture, keep them in sync.
        drawable = res_dir / f'drawable-{density}'
        drawable.mkdir(parents=True, exist_ok=True)
        target = drawable / 'ic_launcher.png'
        save_png(square_on_transparent(image, size), target)
        written.append(target)

    # Density-less fallback the dist ships.
    fallback = res_dir / 'mipmap'
    fallback.mkdir(parents=True, exist_ok=True)
    target = fallback / 'icon.png'
    save_png(square_on_transparent(image, LAUNCHER_SIZES['xxxhdpi']), target)
    written.append(target)
    return written


def write_adaptive_icon(res_dir, image, background):
    written = []
    for density, size in ADAPTIVE_SIZES.items():
        folder = res_dir / f'drawable-{density}'
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'ic_launcher_foreground.png'
        # The launcher may crop everything outside the centre safe zone.
        save_png(square_on_transparent(image, size, ADAPTIVE_SAFE_ZONE), target)
        written.append(target)

    folder = res_dir / 'mipmap-anydpi-v26'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'icon.xml'
    target.write_text(ADAPTIVE_XML, encoding='utf-8')
    written.append(target)

    values = res_dir / 'values'
    values.mkdir(parents=True, exist_ok=True)
    target = values / 'colors.xml'
    target.write_text(COLORS_XML.format(color=background), encoding='utf-8')
    written.append(target)
    return written


def write_presplash(res_dir, image, background):
    folder = res_dir / 'drawable'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'presplash.jpg'

    # JPEG has no alpha channel: flatten onto the splash colour first.
    flattened = flatten(image, background)
    width, height = image_size(flattened)
    scaled = flattened if (width <= PRESPLASH_MAX[0] and height <= PRESPLASH_MAX[1]) \
        else fit(flattened, PRESPLASH_MAX)
    save_jpeg(scaled, target, PRESPLASH_QUALITY)
    return [target]


def update_strings(res_dir, app_name=None, presplash_color=None):
    """Patch values/strings.xml in place (p4a renders app_name/presplash_color)."""
    path = res_dir / 'values' / 'strings.xml'
    if not path.is_file():
        raise SystemExit(f'missing {path}')
    text = path.read_text(encoding='utf-8')
    changed = []

    def replace(name, value):
        nonlocal text
        pattern = rf'(<string name="{name}">)(.*?)(</string>)'
        if re.search(pattern, text, flags=re.S):
            text = re.sub(pattern, lambda m: f'{m.group(1)}{value}{m.group(3)}',
                          text, count=1, flags=re.S)
        else:
            text = text.replace('</resources>', f'    <string name="{name}">{value}</string>\n</resources>')
        changed.append(f'{name} = {value}')

    if app_name:
        replace('app_name', app_name)
    if presplash_color:
        replace('presplash_color', presplash_color)

    path.write_text(text, encoding='utf-8')
    return path, changed


def update_template(dist_dir, app_name=None, presplash_color=None):
    """Pin the values in templates/strings.tmpl.xml.

    p4a re-renders res/values/strings.xml from that template on every packaging
    run (``{{ args.name }}``, ``{{ args.presplash_color }}``), so a value written
    only into strings.xml would be reset the next time the APK is packaged.
    Replacing the placeholders with literals keeps both paths identical.
    """
    path = dist_dir / 'templates' / 'strings.tmpl.xml'
    if not path.is_file():
        return None
    text = path.read_text(encoding='utf-8')
    if presplash_color:
        text = text.replace('{{ args.presplash_color }}', presplash_color)
    if app_name:
        text = text.replace('{{ args.name }}', app_name)
    path.write_text(text, encoding='utf-8')
    return path


def run(dist_dir, icon, presplash, app_name=None, background='auto', adaptive=True):
    res_dir = dist_dir / 'src' / 'main' / 'res'
    if not res_dir.is_dir():
        raise SystemExit(f'not a p4a dist (no src/main/res): {dist_dir}')

    print(f'backend: {BACKEND}')
    written = []
    color = None
    if presplash:
        splash_image = load_image(presplash, 'presplash')
        color = corner_color(splash_image) if background == 'auto' else background
        written += write_presplash(res_dir, splash_image, color)

    if icon:
        icon_image = load_image(icon, 'icon')
        written += write_launcher_icon(res_dir, icon_image)
        if adaptive:
            written += write_adaptive_icon(res_dir, icon_image, color or '#000000')

    if app_name or color:
        path, changed = update_strings(res_dir, app_name, color if presplash else None)
        written.append(path)
        for line in changed:
            print(f'  {line}')
        template = update_template(dist_dir, app_name, color if presplash else None)
        if template is not None:
            written.append(template)

    for path in written:
        print(f'  wrote {path.relative_to(dist_dir).as_posix()}   {path.stat().st_size} B')
    print(f'\n{len(written)} file(s) updated in {res_dir}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('dist_dir', type=Path)
    parser.add_argument('--icon', type=Path, help='square PNG, 1024x1024 recommended')
    parser.add_argument('--presplash', type=Path, help='splash image (JPEG/PNG)')
    parser.add_argument('--app-name', help='value for values/strings.xml app_name')
    parser.add_argument('--background', default='auto',
                        help='"auto" samples the presplash corners, or pass #rrggbb')
    parser.add_argument('--no-adaptive', action='store_true',
                        help='skip the Android 8+ adaptive icon')
    args = parser.parse_args(argv)

    if not args.icon and not args.presplash and not args.app_name:
        parser.error('nothing to do: pass --icon, --presplash and/or --app-name')

    return run(args.dist_dir, args.icon, args.presplash, args.app_name,
               args.background, adaptive=not args.no_adaptive)


if __name__ == '__main__':
    sys.exit(main())
