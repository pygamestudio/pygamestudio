"""Build the APK with the Android SDK's build-tools - no Gradle, no AGP.

Gradle + the Android Gradle Plugin would download ~280 MB the first time (and
need a network), which is the opposite of what this editor wants. Everything an
APK actually needs is a handful of small command line tools that already ship
with the SDK and the JDK, and this project has none of the things AGP is for
(dependency resolution, flavours, R8 shrinking, AAR merging):

1. ``aapt2 compile``  - resources -> compiled resources
2. ``aapt2 link``     - resources + AndroidManifest.xml -> an unsigned APK
3. ``javac``          - the Java bootstrap -> .class files
4. ``jar`` + ``d8``   - .class files -> classes.dex
5. zip                - classes.dex, assets/ and lib/<abi>/*.so into the APK
6. ``zipalign``       - align the archive
7. ``apksigner``      - sign with the debug key or the user's release key

The tool versions come from whatever build-tools the user has; only the
platform (android.jar) has to match the target SDK, which the settings check
already requires.
"""
import locale
import os
import platform
import shutil
import subprocess
import zipfile
from pathlib import Path

#: Name of the APK task in the UI (kept for the progress text).
DEBUG_KEY_ALIAS = 'androiddebugkey'
DEBUG_KEY_PASSWORD = 'android'
#: Validity of a generated debug key, in days (same as Android's own).
DEBUG_KEY_DAYS = '10000'

#: Tools this module calls, in the order they run.
TOOL_NAMES = ('aapt2', 'd8', 'zipalign', 'apksigner')


class ApkBuildError(RuntimeError):
    """A build step failed; ``reason`` is a translation key for the window."""

    def __init__(self, message='', reason='android.error_build'):
        super().__init__(message)
        self.detail = message
        self.reason = reason


def tool_name(name):
    """The executable of a build-tool on this platform."""
    if platform.system() == 'Windows' and name in ('d8', 'apksigner'):
        return f'{name}.bat'
    if platform.system() == 'Windows':
        return f'{name}.exe'
    return name


def find_tools(sdk_dir):
    """Newest build-tools folder and the tools inside it."""
    folder = Path(sdk_dir) / 'build-tools'
    if not folder.is_dir():
        raise ApkBuildError(f'no build-tools in {sdk_dir}', 'android.error_sdk_packages')

    def key(path):
        parts = []
        for piece in path.name.split('.'):
            parts.append(int(piece) if piece.isdigit() else 0)
        return parts

    candidates = sorted((path for path in folder.iterdir() if path.is_dir()), key=key)
    for version in reversed(candidates):
        if all((version / tool_name(name)).is_file() for name in TOOL_NAMES):
            return version
    raise ApkBuildError(f'build-tools in {folder} have no aapt2/d8/zipalign/apksigner',
                        'android.error_sdk_packages')


def android_jar(sdk_dir, compile_sdk):
    """``platforms/android-<n>/android.jar`` (the compile classpath)."""
    jar = Path(sdk_dir) / 'platforms' / f'android-{compile_sdk}' / 'android.jar'
    if not jar.is_file():
        raise ApkBuildError(f'android.jar for API {compile_sdk} is missing: {jar}',
                            'android.error_sdk_platform')
    return jar


def decode_line(raw):
    """Decode one line of tool output.

    javac writes its notes in the platform code page while Gradle-style tools
    write UTF-8, so a plain ``text=True`` decode turned the Chinese notes into
    ``ע: ...`` garbage. Try UTF-8, fall back to the locale encoding.
    """
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode(locale.getpreferredencoding(False), 'replace')


def run(command, on_line=None, stop_check=None, environment=None, cwd=None):
    """Run a tool and stream its output line by line (decoded safely).

    :return: ``(exit code, lines)``
    """
    process = subprocess.Popen([str(part) for part in command],
                               cwd=str(cwd) if cwd else None,
                               env=environment,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    lines = []
    try:
        for raw in iter(process.stdout.readline, b''):
            line = decode_line(raw).rstrip()
            if not line:
                continue
            lines.append(line)
            if on_line is not None:
                on_line(line)
            if stop_check is not None and stop_check():
                process.kill()
                break
    finally:
        if process.stdout is not None:
            process.stdout.close()
    return process.wait(), lines


def debug_keystore(cache_dir, jdk, on_line=None):
    """The debug signing key, created once (``androiddebugkey``/``android``)."""
    keystore = Path(cache_dir) / 'debug.keystore'
    if keystore.is_file():
        return keystore

    keytool = Path(jdk) / 'bin' / ('keytool.exe' if platform.system() == 'Windows' else 'keytool')
    if not keytool.is_file():
        raise ApkBuildError(f'keytool not found in {jdk}', 'android.error_java_too_old')
    keystore.parent.mkdir(parents=True, exist_ok=True)

    environment = dict(os.environ)
    environment['PYGS_DEBUG_STORE'] = DEBUG_KEY_PASSWORD
    environment['PYGS_DEBUG_KEY'] = DEBUG_KEY_PASSWORD
    code, lines = run([keytool, '-genkeypair', '-v', '-keystore', keystore,
                       '-alias', DEBUG_KEY_ALIAS, '-keyalg', 'RSA', '-keysize', '2048',
                       '-validity', DEBUG_KEY_DAYS,
                       '-storepass:env', 'PYGS_DEBUG_STORE',
                       '-keypass:env', 'PYGS_DEBUG_KEY',
                       '-dname', 'CN=Android Debug, O=Android, C=US'],
                      on_line=on_line, environment=environment)
    if code != 0 or not keystore.is_file():
        raise ApkBuildError('\n'.join(lines[-8:]), 'android.error_keystore')
    return keystore


def _clean(work_dir):
    shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def build_apk(dist_dir, work_dir, *, sdk_dir, jdk, compile_sdk, min_sdk,
              debug=True, signing=None, cache_dir=None, extra_environment=None,
              on_line=None, on_progress=None, stop_check=None):
    """Turn a prepared dist into a signed APK and return its path.

    ``signing`` is ``{'keystore': path, 'alias': name}`` for a release build;
    ``extra_environment`` carries the passwords (``PYGS_KEYSTORE_PASSWORD``/
    ``PYGS_KEY_PASSWORD``) so they never appear on a command line.
    """
    report = on_progress or (lambda percent: None)
    dist_dir = Path(dist_dir)
    work = _clean(Path(work_dir) / 'apk')
    tools = find_tools(sdk_dir)
    jar = android_jar(sdk_dir, compile_sdk)
    environment = dict(os.environ)
    environment.setdefault('PYTHONIOENCODING', 'utf-8')
    environment.update({key: str(value)
                        for key, value in (extra_environment or {}).items()})

    def fail(code, lines, key, fallback):
        if code != 0:
            raise ApkBuildError('\n'.join(lines[-8:]) or fallback, key)

    res_dir = dist_dir / 'src' / 'main' / 'res'
    manifest = dist_dir / 'src' / 'main' / 'AndroidManifest.xml'
    java_dir = dist_dir / 'src' / 'main' / 'java'
    assets_dir = dist_dir / 'src' / 'main' / 'assets'
    java_files = sorted(java_dir.rglob('*.java'))

    report(5)
    compiled_res = work / 'resources.zip'
    code, lines = run([tools / tool_name('aapt2'), 'compile', '--dir', res_dir,
                       '-o', compiled_res], on_line=on_line,
                      stop_check=stop_check, environment=environment)
    fail(code, lines, 'android.error_resources', 'aapt2 compile failed')

    report(25)
    base_apk = work / 'base.apk'
    link = [tools / tool_name('aapt2'), 'link', '-o', base_apk,
            '-I', jar, '--manifest', manifest,
            '--auto-add-overlay', compiled_res]
    if debug:
        link.append('--debug-mode')
    code, lines = run(link, on_line=on_line, stop_check=stop_check,
                      environment=environment)
    fail(code, lines, 'android.error_resources', 'aapt2 link failed')

    report(45)
    classes = work / 'classes'
    classes.mkdir(parents=True, exist_ok=True)
    javac = Path(jdk) / 'bin' / ('javac.exe' if platform.system() == 'Windows' else 'javac')
    if not javac.is_file():
        raise ApkBuildError(f'javac not found in {jdk}', 'android.error_java_too_old')
    code, lines = run([javac, '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                       '-Xlint:-options', '-nowarn',
                       # android.jar on the CLASSPATH, not the bootclasspath: the
                       # bootstrap uses lambdas, which javac resolves against the
                       # runtime's LambdaMetafactory - d8 desugars them for the
                       # device afterwards. (A bootclasspath replacement hides
                       # that class and the compile fails with "metafactory".)
                       '-classpath', jar, '-d', classes] + java_files,
                      on_line=on_line, stop_check=stop_check, environment=environment)
    fail(code, lines, 'android.error_java', 'javac failed')

    report(65)
    classes_jar = work / 'classes.jar'
    jar_tool = Path(jdk) / 'bin' / ('jar.exe' if platform.system() == 'Windows' else 'jar')
    code, lines = run([jar_tool, '--create', '--file', classes_jar, '-C', classes, '.'],
                      on_line=on_line, stop_check=stop_check, environment=environment)
    fail(code, lines, 'android.error_java', 'jar failed')

    dex_dir = work / 'dex'
    dex_dir.mkdir(exist_ok=True)
    dex_command = [tools / tool_name('d8'), '--min-api', str(int(min_sdk)),
                   '--lib', jar, '--output', dex_dir, classes_jar]
    dex_command.insert(1, '--debug' if debug else '--release')
    code, lines = run(dex_command, on_line=on_line, stop_check=stop_check,
                      environment=environment)
    fail(code, lines, 'android.error_dex', 'd8 failed')

    report(80)
    dex_file = dex_dir / 'classes.dex'
    if not dex_file.is_file():
        raise ApkBuildError('d8 produced no classes.dex', 'android.error_dex')

    # Fill the archive aapt2 linked: code, assets and the prebuilt libraries.
    with zipfile.ZipFile(base_apk, 'a', zipfile.ZIP_DEFLATED) as apk:
        apk.write(dex_file, 'classes.dex')
        if assets_dir.is_dir():
            for path in sorted(assets_dir.rglob('*')):
                if path.is_file():
                    apk.write(path, 'assets/' + path.relative_to(assets_dir).as_posix())
        libs_root = dist_dir / 'libs'
        if libs_root.is_dir():
            for abi_dir in sorted(path for path in libs_root.iterdir() if path.is_dir()):
                for library in sorted(abi_dir.glob('*.so*')):
                    apk.write(library, f'lib/{abi_dir.name}/{library.name}')

    report(90)
    aligned = work / 'aligned.apk'
    code, lines = run([tools / tool_name('zipalign'), '-f', '-p', '4', base_apk, aligned],
                      on_line=on_line, stop_check=stop_check, environment=environment)
    fail(code, lines, 'android.error_build', 'zipalign failed')

    report(95)
    final_apk = work / 'app.apk'
    sign_environment = dict(environment)
    if debug:
        keystore = debug_keystore(Path(cache_dir or Path(work_dir).parent), jdk,
                                  on_line=on_line)
        sign_command = [tools / tool_name('apksigner'), 'sign',
                        '--ks', keystore, '--ks-key-alias', DEBUG_KEY_ALIAS,
                        '--ks-pass', f'pass:{DEBUG_KEY_PASSWORD}',
                        '--key-pass', f'pass:{DEBUG_KEY_PASSWORD}',
                        '--out', final_apk, aligned]
    else:
        if not signing or not signing.get('keystore'):
            raise ApkBuildError('a release build needs a keystore', 'android.error_keystore')
        keystore = Path(signing['keystore'])
        if not keystore.is_file():
            raise ApkBuildError(f'keystore not found: {keystore}', 'android.error_keystore')
        sign_command = [tools / tool_name('apksigner'), 'sign',
                        '--ks', keystore,
                        '--ks-key-alias', str(signing.get('alias') or ''),
                        '--ks-pass', 'env:PYGS_KEYSTORE_PASSWORD',
                        '--key-pass', 'env:PYGS_KEY_PASSWORD',
                        '--out', final_apk, aligned]
    code, lines = run(sign_command, on_line=on_line, stop_check=stop_check,
                      environment=sign_environment)
    if code != 0:
        raise ApkBuildError('\n'.join(lines[-8:]) or 'apksigner failed',
                            'android.error_signing')

    report(100)
    return final_apk
