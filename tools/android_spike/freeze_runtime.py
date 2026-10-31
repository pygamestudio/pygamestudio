"""Freeze a built p4a dist into the runtime artefact the editor ships.

The editor never downloads a toolchain: it downloads (or ships) ONE archive that
contains everything an APK needs except the user's own game - the Python bundle,
the prebuilt native libraries, the Java bootstrap and a Gradle project that binds
them together. This tool turns a dist produced by the spike build into exactly
that archive, so the artefact and the build stay in step.

What goes in (everything else in a dist is build noise and is left out):

    _python_bundle__<abi>/_python_bundle/    stdlib.zip + modules/ + site-packages/
    libs/<abi>/*.so                          python, SDL2 family, freetype, ...
    src/main/java/                           the p4a bootstrap
    src/res_initial/                         pristine resources the editor injects into
    templates/                               manifest / strings templates
    gradle files                             build.gradle, wrapper, gradlew, ...

``build/``, ``obj/``, ``jni/`` (573 MB of SDL sources), ``.gradle/`` and the
app's own ``assets/private.tar`` are NOT part of it. No NDK is involved either:
p4a's Gradle project only packages the prebuilt ``libs/`` (``jniLibs.srcDir``),
so a user needs a JDK, the Android SDK and Gradle - nothing else.

    py -3.10 tools/android_spike/freeze_runtime.py <dist_dir> --out <dir>
"""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

#: Files of the Gradle project (relative to the dist root).
GRADLE_FILES = (
    'build.gradle',
    'settings.gradle',
    'gradle.properties',
    'gradlew',
    'gradlew.bat',
    'ant.properties',
    'project.properties',
    'custom_rules.xml',
    'build.xml',
    'blacklist.txt',
    'whitelist.txt',
)
#: Folders of the Gradle project.
GRADLE_DIRS = (
    'gradle/wrapper',
    'templates',
)
#: Resource folder the editor seeds from (p4a restores res from it every build).
RES_DIRS = ('src/res_initial', 'src/main/res')
#: Never part of an artefact, even inside the copied folders.
IGNORED_SUFFIXES = ('.pyc', '.pyo', '.log', '.tmp')

#: Output name pattern: pygs-android-runtime-<version>-<abi>.zip
NAME = 'pygs-android-runtime-{version}-{abi}.zip'
#: Metadata file written next to the archive contents.
VERSION_FILE = 'VERSION.json'


def human(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{size} B'
        size /= 1024


def _add_file(files, source, relative):
    if source.is_file() and source.suffix not in IGNORED_SUFFIXES:
        files.append((source, relative))


def collect(dist_dir, abi):
    """``(source, archive name)`` of every file the artefact carries."""
    dist_dir = Path(dist_dir)
    files = []

    bundle_root = dist_dir / f'_python_bundle__{abi}'
    if not bundle_root.is_dir():
        raise SystemExit(f'not a p4a dist for {abi}: {bundle_root} is missing')
    for path in sorted(bundle_root.rglob('*')):
        if path.is_file():
            _add_file(files, path, f'_python_bundle__{abi}/{path.relative_to(bundle_root).as_posix()}')

    libs_dir = dist_dir / 'libs' / abi
    if not libs_dir.is_dir():
        raise SystemExit(f'not a p4a dist for {abi}: {libs_dir} is missing')
    for path in sorted(libs_dir.iterdir()):
        if path.is_file():
            _add_file(files, path, f'libs/{abi}/{path.name}')

    for path in sorted((dist_dir / 'src' / 'main' / 'java').rglob('*')):
        if path.is_file():
            _add_file(files, path,
                      f'src/main/java/{path.relative_to(dist_dir / "src" / "main" / "java").as_posix()}')

    for name in RES_DIRS:
        base = dist_dir / name
        if base.is_dir():
            for path in sorted(base.rglob('*')):
                if path.is_file():
                    _add_file(files, path, f'{name}/{path.relative_to(base).as_posix()}')
            break                                   # one res source is enough

    for name in GRADLE_DIRS:
        base = dist_dir / name
        if base.is_dir():
            for path in sorted(base.rglob('*')):
                if path.is_file():
                    _add_file(files, path, f'{name}/{path.relative_to(base).as_posix()}')
    for name in GRADLE_FILES:
        _add_file(files, dist_dir / name, name)

    return files


def _read_version(path, patterns):
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def detect_versions(dist_dir, abi):
    """Best-effort versions of the interpreter and the shipped packages.

    The site-packages snapshot carries one ``<name>-<version>.dist-info`` folder
    per installed distribution, which is the authoritative source (the package
    modules themselves may be byte-compiled or vendor a version string).
    """
    bundle = Path(dist_dir) / f'_python_bundle__{abi}' / '_python_bundle'
    site_packages = bundle / 'site-packages'
    info = {'abi': abi}

    modules = bundle / 'modules'
    if modules.is_dir():
        for entry in modules.iterdir():
            # e.g. array.cpython-314-aarch64-linux-android.so -> 3.14
            match = re.match(r'.*cpython-(\d)(\d+)', entry.name)
            if match:
                info['python'] = f'{match.group(1)}.{match.group(2)}'
                break

    packages = {}
    if site_packages.is_dir():
        for entry in sorted(site_packages.iterdir()):
            match = re.match(r'(.+?)-(\d[^-]*?)\.dist-info$', entry.name)
            if entry.is_dir() and match:
                packages[match.group(1)] = match.group(2)
    if packages:
        info['packages'] = packages
    info['pygame_ce'] = packages.get('pygame_ce', packages.get('pygame'))
    info['pymunk'] = packages.get('pymunk')
    info['cffi'] = packages.get('cffi')
    info['site_packages'] = sorted(
        entry.name for entry in site_packages.iterdir()
        if entry.is_dir() and not entry.name.startswith('_')
        and not entry.name.endswith('.dist-info')) if site_packages.is_dir() else []
    return {key: value for key, value in info.items() if value is not None}



def build_metadata(dist_dir, abi, version, files):
    metadata = {
        'format': 2,
        'name': 'pygs-android-runtime',
        'version': version,
        'layout': {
            'python_bundle': f'_python_bundle__{abi}/_python_bundle',
            'libs': f'libs/{abi}',
            'java': 'src/main/java',
            'resources': next((name for name in RES_DIRS if (Path(dist_dir) / name).is_dir()),
                              RES_DIRS[0]),
        },
        'files': len(files),
        'bytes': sum(source.stat().st_size for source, _relative in files),
    }
    metadata.update(detect_versions(dist_dir, abi))
    return metadata


def write_zip(files, target, compression, compresslevel=None):
    """Write the archive; returns its size. Deterministic (sorted, fixed dates)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=compression,
                         compresslevel=compresslevel) as archive:
        for source, relative in sorted(files, key=lambda item: item[1]):
            info = zipfile.ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = compression
            info.external_attr = 0o644 << 16
            with source.open('rb') as handle:
                archive.writestr(info, handle.read())
    return target.stat().st_size


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Freeze a p4a dist into the editor runtime artefact')
    parser.add_argument('dist_dir', type=Path)
    parser.add_argument('--out', type=Path, required=True, help='folder for the archive')
    parser.add_argument('--abi', default='arm64-v8a')
    parser.add_argument('--version', default='1.0.0')
    parser.add_argument('--compressor', choices=('lzma', 'deflate'), default='lzma',
                        help='lzma is ~12%% smaller and only costs time when the '
                             'editor unpacks it (default)')
    parser.add_argument('--compare-compressors', action='store_true',
                        help='write both archives and report the sizes')
    args = parser.parse_args(argv)

    files = collect(args.dist_dir, args.abi)
    raw = sum(source.stat().st_size for source, _relative in files)
    print(f'dist    : {args.dist_dir}')
    print(f'files   : {len(files)}, {human(raw)} raw')

    by_folder = {}
    for source, relative in files:
        top = relative.split('/')[0]
        count, size = by_folder.get(top, (0, 0))
        by_folder[top] = (count + 1, size + source.stat().st_size)
    for top, (count, size) in sorted(by_folder.items()):
        print(f'  {top:<28} {count:>5} files {human(size):>10}')

    metadata = build_metadata(args.dist_dir, args.abi, args.version, files)

    target = args.out / NAME.format(version=args.version, abi=args.abi)
    if args.compressor == 'lzma':
        compression, level = zipfile.ZIP_LZMA, None
    else:
        compression, level = zipfile.ZIP_DEFLATED, 9
    started = __import__('time').perf_counter()
    zipped = write_zip(files, target, compression, level)
    elapsed = __import__('time').perf_counter() - started
    print(f'\n{target.name}: {human(zipped)} '
          f'({raw / zipped:.2f}x smaller, {args.compressor}, {elapsed:.1f}s)')

    if args.compare_compressors:
        other = (zipfile.ZIP_DEFLATED if args.compressor == 'lzma'
                 else zipfile.ZIP_LZMA)
        other_target = target.with_name(target.stem + '-alt.zip')
        other_size = write_zip(files, other_target, other, 9 if other == zipfile.ZIP_DEFLATED else None)
        print(f'{other_target.name}: {human(other_size)} ({raw / other_size:.2f}x smaller)')
        other_target.unlink()

    metadata['archive'] = {'name': target.name, 'bytes': zipped,
                           'sha256': sha256(target)}
    (args.out / VERSION_FILE).write_text(
        json.dumps(metadata, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{VERSION_FILE}: {metadata["files"]} files, python '
          f'{metadata.get("python", "?")}, pygame_ce {metadata.get("pygame_ce", "?")}, '
          f'pymunk {metadata.get("pymunk", "?")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
