"""Inspect / rebuild the p4a ``dist`` produced by the spike build (runs on Windows).

The Windows editor will never cross-compile anything: it only rebuilds
``private.tar`` (stdlib + site-packages + our payload) and lets Gradle package
it. This tool proves that step is possible with nothing but the stdlib:

    # what is inside the payload?
    py -3.10 tools/android_spike/inspect_dist.py inspect <dist_dir>

    # can we rebuild private.tar member by member on Windows?
    py -3.10 tools/android_spike/inspect_dist.py roundtrip <dist_dir> --out rebuilt.tar

``<dist_dir>`` is e.g. ``.buildozer/android/platform/build-arm64-v8a/dists/pygsspike``.
"""

import argparse
import copy
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


def inspect(dist_dir):
    print(f'dist: {dist_dir}')

    private_tar = find_private_tar(dist_dir)
    if private_tar is None:
        print('  !! private.tar not found - is this really a p4a dist?')
    else:
        with tarfile.open(private_tar, 'r:*') as tar:
            members = tar.getmembers()
        _inspect_tar(private_tar, members)

    _inspect_libs(dist_dir)
    _inspect_java(dist_dir)
    _inspect_manifest(dist_dir)


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    inspect_parser = sub.add_parser('inspect', help='print the layout of a p4a dist')
    inspect_parser.add_argument('dist_dir', type=Path)

    roundtrip_parser = sub.add_parser('roundtrip', help='rebuild private.tar and compare member lists')
    roundtrip_parser.add_argument('dist_dir', type=Path)
    roundtrip_parser.add_argument('--out', type=Path, default=Path('private_rebuilt.tar'))

    args = parser.parse_args(argv)
    if not args.dist_dir.is_dir():
        print(f'not a directory: {args.dist_dir}')
        return 1

    if args.command == 'inspect':
        inspect(args.dist_dir)
        return 0
    return roundtrip(args.dist_dir, args.out)


if __name__ == '__main__':
    sys.exit(main())
