"""Inspect / rebuild the p4a ``dist`` produced by the spike build (runs on Windows).

The Windows editor never cross-compiles anything: it copies the dist, swaps in
the user's Python code and lets Gradle package the APK. This tool proves both
halves work with nothing but the standard library.

Modern p4a keeps the Python payload as a *directory* inside the dist, and only
packs it into a tarball when building the APK::

    dist/
    ├─ _python_bundle__arm64-v8a/_python_bundle/
    │  ├─ modules/         compiled extension modules (.so)
    │  ├─ site-packages/   pure python + native packages (pygame, pymunk…)
    │  └─ stdlib.zip       standard library
    ├─ libs/arm64-v8a/     libpython, SDL2, libmain …
    ├─ src/main/java/      the Java bootstrap
    └─ templates/AndroidManifest.tmpl.xml

At packaging time p4a tars ``_python_bundle__<arch>`` into
``libs/<abi>/libpybundle.so`` (a gzip tar named like a library) and the app code
into ``assets/private.tar``; the Android side extracts both. Older dists used a
single ``private.tar`` and are still understood.

    # what is inside the payload?
    py -3.10 tools/android_spike/inspect_dist.py inspect <dist_dir>

    # can we rebuild the libpybundle.so payload on Windows?
    py -3.10 tools/android_spike/inspect_dist.py bundle <dist_dir> --out libpybundle.so

``<dist_dir>`` is e.g. ``.buildozer/android/platform/build-arm64-v8a/dists/pygsspike``.
"""

import argparse
import copy
import gzip
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

#: Extension modules the engine actually needs from pygame.
PYGAME_REQUIRED_MODULES = ('base', 'surface', 'display', 'font', 'image', 'mixer', 'time')


def human(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{size} B'
        size /= 1024


def find_private_tar(dist_dir):
    for name in ('private.tar', 'private.mp3', 'private.tar.gz'):
        candidate = dist_dir / name
        if candidate.is_file():
            return candidate
    matches = sorted(dist_dir.glob('private*'))
    return matches[0] if matches else None


def find_bundle_dir(dist_dir):
    """``_python_bundle`` (inside ``_python_bundle__<arch>``) of a modern dist."""
    for candidate in sorted(dist_dir.glob('_python_bundle__*')):
        inner = candidate / '_python_bundle'
        if inner.is_dir():
            return inner
    return None


def inspect(dist_dir):
    print(f'dist: {dist_dir}')

    bundle_dir = find_bundle_dir(dist_dir)
    if bundle_dir is not None:
        _inspect_bundle(dist_dir, bundle_dir)
    else:
        private_tar = find_private_tar(dist_dir)
        if private_tar is None:
            print('  !! no _python_bundle__* directory and no private.tar - not a p4a dist?')
        else:
            with tarfile.open(private_tar, 'r:*') as tar:
                members = tar.getmembers()
            _inspect_tar(private_tar, members)

    _inspect_libs(dist_dir)
    _inspect_java(dist_dir)
    _inspect_manifest(dist_dir)


def _inspect_bundle(dist_dir, bundle_dir):
    """Report the directory layout the APK gets packed from."""
    files = [path for path in bundle_dir.rglob('*') if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    relative = bundle_dir.relative_to(dist_dir).as_posix()
    print(f'\n-- {relative}: {len(files)} files, {human(total)}')

    stdlib = bundle_dir / 'stdlib.zip'
    stdlib_size = human(stdlib.stat().st_size) if stdlib.is_file() else 'MISSING'
    print(f'   {"stdlib.zip":<22} {stdlib_size:>10}')

    modules_dir = bundle_dir / 'modules'
    modules = sorted(modules_dir.glob('*.so*')) if modules_dir.is_dir() else []
    modules_size = sum(path.stat().st_size for path in modules)
    print(f'   {"modules/":<22} {len(modules):>4} libs {human(modules_size):>10}')

    site_packages = bundle_dir / 'site-packages'
    if not site_packages.is_dir():
        print('   site-packages          MISSING')
        return

    packages = defaultdict(lambda: [0, 0])
    for entry in site_packages.iterdir():
        if entry.is_dir():
            inner = [path for path in entry.rglob('*') if path.is_file()]
            packages[entry.name] = [len(inner), sum(path.stat().st_size for path in inner)]
        else:
            # A single-file module such as _cffi_backend.cpython-314-....so
            packages[entry.name.split('.')[0]] = [1, entry.stat().st_size]

    print('   site-packages (relevant):')
    for package in ('pygame', 'pymunk', 'cffi', '_cffi_backend'):
        count, size = packages.get(package, (0, 0))
        flag = 'ok' if count else 'MISSING'
        print(f'     {package:<18} {count:>5} files {human(size):>10}  {flag}')

    pygame_dir = site_packages / 'pygame'
    if pygame_dir.is_dir():
        found = {path.name.split('.')[0] for path in pygame_dir.iterdir()
                 if path.suffix in ('.so', '.pyd')}
        missing = [module for module in PYGAME_REQUIRED_MODULES if module not in found]
        print(f'   pygame extension modules: {", ".join(sorted(found)) or "-"}')
        print(f'   required modules missing  : {", ".join(missing) if missing else "none"}')
    else:
        print('   pygame extension modules: none found')
        print('   required modules missing  : ALL')


def _inspect_tar(private_tar, members):
    total = sum(m.size for m in members)
    print(f'\n-- {private_tar.name}: {len(members)} entries, {human(total)}')

    per_top = defaultdict(lambda: [0, 0])
    for member in members:
        top = member.name.split('/')[0] or '.'
        per_top[top][0] += 1
        per_top[top][1] += member.size
    for top, (count, size) in sorted(per_top.items()):
        print(f'   {top:<28} {count:>6} entries  {human(size):>10}')

    # python version + where packages landed
    versions = {m.name.split('/')[1] for m in members if m.name.startswith('lib/python')}
    print(f'   python dir: {", ".join(sorted(versions)) or "-"}')

    site_packages = defaultdict(lambda: [0, 0])
    for member in members:
        parts = member.name.split('/')
        if 'site-packages' not in parts:
            continue
        index = parts.index('site-packages')
        if index + 1 >= len(parts):
            continue
        if index + 2 == len(parts):
            # A module that is a single file, e.g. _cffi_backend.cpython-311-....so
            package = parts[index + 1].split('.')[0]
        else:
            package = parts[index + 1]
        site_packages[package][0] += 1
        site_packages[package][1] += member.size
    interesting = ('pygame', 'pymunk', 'cffi', '_cffi_backend', 'pygamestudio')
    print('   site-packages (relevant):')
    for package in interesting:
        count, size = site_packages.get(package, (0, 0))
        flag = 'ok' if count else 'MISSING'
        print(f'     {package:<18} {count:>5} files {human(size):>10}  {flag}')

    pygame_modules = sorted({Path(m.name).name.split('.')[0] for m in members
                             if '/pygame/' in m.name and (m.name.endswith('.so') or m.name.endswith('.pyd'))})
    if pygame_modules:
        missing = [mod for mod in PYGAME_REQUIRED_MODULES if mod not in pygame_modules]
        print(f'   pygame extension modules: {", ".join(pygame_modules)}')
        print(f'   required modules missing  : {", ".join(missing) if missing else "none"}')
    else:
        print('   pygame extension modules: none found')


def _inspect_libs(dist_dir):
    libs_dir = dist_dir / 'libs'
    if not libs_dir.is_dir():
        print('\n-- libs/: not found')
        return
    for abi_dir in sorted(p for p in libs_dir.iterdir() if p.is_dir()):
        sonames = sorted(abi_dir.glob('*.so*'))
        total = sum(p.stat().st_size for p in sonames)
        print(f'\n-- libs/{abi_dir.name}: {len(sonames)} libs, {human(total)}')
        for path in sonames:
            print(f'   {path.name:<34} {human(path.stat().st_size):>10}')


def _inspect_java(dist_dir):
    java_dir = dist_dir / 'src' / 'main' / 'java'
    if not java_dir.is_dir():
        print('\n-- src/main/java: not found')
        return
    packages = sorted({str(p.parent.relative_to(java_dir)).replace('\\', '/')
                       for p in java_dir.rglob('*.java')})
    print(f'\n-- src/main/java: {len(list(java_dir.rglob("*.java")))} files in {len(packages)} packages')
    for package in packages[:12]:
        print(f'   {package}')
    if len(packages) > 12:
        print(f'   ... {len(packages) - 12} more')


def _inspect_manifest(dist_dir):
    for relative in ('templates/AndroidManifest.tmpl.xml', 'AndroidManifest.xml'):
        path = dist_dir / relative
        if path.is_file():
            print(f'\n-- {relative}: {human(path.stat().st_size)}')
            return
    print('\n-- AndroidManifest: not found')


def build_info(member):
    """Comparable identity of a member (mtime/uid are allowed to change)."""
    return (member.name, member.type, member.size, member.linkname, member.mode)


def roundtrip(dist_dir, out_path):
    private_tar = find_private_tar(dist_dir)
    if private_tar is None:
        print('!! private.tar not found')
        return 1

    with tarfile.open(private_tar, 'r:*') as source:
        members = source.getmembers()
        with tarfile.open(out_path, 'w') as target:
            for member in members:
                info = copy.copy(member)
                if member.isreg():
                    extracted = source.extractfile(member)
                    target.addfile(info, extracted)
                else:
                    target.addfile(info)

    with tarfile.open(private_tar, 'r:*') as source:
        before = [build_info(m) for m in source.getmembers()]
    with tarfile.open(out_path, 'r:*') as rebuilt:
        after = [build_info(m) for m in rebuilt.getmembers()]

    print(f'source : {private_tar}  ({human(private_tar.stat().st_size)}, {len(before)} entries)')
    print(f'rebuilt: {out_path}  ({human(Path(out_path).stat().st_size)}, {len(after)} entries)')

    if before == after:
        print('RESULT : identical member list (names, types, sizes, links, modes)')
        return 0

    print('RESULT : MISMATCH')
    for left, right in zip(before, after):
        if left != right:
            print(f'  first difference:\n    source  {left}\n    rebuilt {right}')
            break
    if len(before) != len(after):
        print(f'  entry count differs: {len(before)} vs {len(after)}')
    return 2


def bundle(dist_dir, out_path):
    """Tar ``_python_bundle__<arch>`` exactly like p4a does for libpybundle.so.

    p4a's make_tar() writes a gzip tarball with normalised metadata (uid/gid 0,
    empty owner names, mtime 0) whose members are relative to the
    ``_python_bundle__<arch>`` directory: the Android side extracts it with a
    GZIPInputStream + TarInputStream, so the layout has to match.
    """
    bundle_dir = find_bundle_dir(dist_dir)
    if bundle_dir is None:
        print('!! no _python_bundle__* directory found')
        return 1

    arch_dir = bundle_dir.parent
    files = sorted(path for path in arch_dir.rglob('*') if path.is_file())
    directories = sorted({path.parent for path in files})

    with open(out_path, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as tar:
                for directory in directories:
                    info = tarfile.TarInfo(directory.relative_to(arch_dir).as_posix())
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mtime = 0
                    tar.addfile(info)
                for path in files:
                    info = tar.gettarinfo(path.as_posix(),
                                          arcname=path.relative_to(arch_dir).as_posix())
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mtime = 0
                    with open(path, 'rb') as source:
                        tar.addfile(info, source)

    with tarfile.open(out_path, 'r:gz') as tar:
        members = tar.getmembers()
    tops = {member.name.split('/')[0] for member in members}
    print(f'wrote {out_path}  ({human(Path(out_path).stat().st_size)}, {len(members)} entries)')
    print(f'  top level: {", ".join(sorted(tops))}')
    # p4a tars the contents of _python_bundle__<arch>, so every member starts
    # with the inner "_python_bundle" directory.
    if tops != {bundle_dir.name}:
        print(f'  !! unexpected top level, expected {bundle_dir.name}')
        return 2
    print('RESULT : bundle rebuilt in the layout the Android side expects')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    inspect_parser = sub.add_parser('inspect', help='print the layout of a p4a dist')
    inspect_parser.add_argument('dist_dir', type=Path)

    bundle_parser = sub.add_parser('bundle', help='rebuild the libpybundle.so payload')
    bundle_parser.add_argument('dist_dir', type=Path)
    bundle_parser.add_argument('--out', type=Path, default=Path('libpybundle.so'))

    roundtrip_parser = sub.add_parser('roundtrip', help='(legacy dists) rebuild private.tar')
    roundtrip_parser.add_argument('dist_dir', type=Path)
    roundtrip_parser.add_argument('--out', type=Path, default=Path('private_rebuilt.tar'))

    args = parser.parse_args(argv)
    if not args.dist_dir.is_dir():
        print(f'not a directory: {args.dist_dir}')
        return 1

    if args.command == 'inspect':
        inspect(args.dist_dir)
        return 0
    if args.command == 'bundle':
        return bundle(args.dist_dir, args.out)
    return roundtrip(args.dist_dir, args.out)


if __name__ == '__main__':
    sys.exit(main())
