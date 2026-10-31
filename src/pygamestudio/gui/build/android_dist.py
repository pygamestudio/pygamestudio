"""Turn the frozen runtime pack + a protected project into an installable APK.

The heavy lifting (compiling Python, pygame-ce, pymunk and SDL2 for Android) is
done once, in CI, and ships as the pack. A build here is therefore small and
offline-capable after the first run:

1. unpack the pack into the cache (``common.utils.android_runtime``);
2. copy it into the build work folder - a plain p4a Gradle project;
3. restore ``src/main/res`` from ``src/res_initial`` (p4a's own rule: the res
   tree is stateless, every packaging run starts from the pristine copy) and
   inject the icon, the splash and the app name;
4. render ``AndroidManifest.xml``, patch ``build.gradle`` (namespace, versions,
   SDK levels) and point ``local.properties`` at the user's SDK;
5. write ``src/main/assets/private.tar`` - the project plus the engine;
6. run Gradle's ``assembleDebug`` and copy the APK out.

No NDK and no p4a: the pack's ``build.gradle`` only packages the prebuilt
``libs/<abi>/*.so`` (``jniLibs.srcDir 'libs'``).
"""
import os
import hashlib
import platform
import re
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from pygamestudio.common.utils.android_runtime import COMPILE_SDK, MIN_SDK

#: APK signing / packaging tasks. Only the debug task is exposed for now: it
#: produces an installable APK with the debug key Android's tooling generates.
DEBUG_TASK = 'assembleDebug'

#: Manifest written for every build. Based on what p4a's SDL2 bootstrap renders
#: (and what ran on the device in spike 3b), with the values a game build needs
#: to change left as placeholders. ``android:debuggable`` is NOT set on purpose:
#: the Android Gradle Plugin adds it to debug builds itself.
MANIFEST_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
      android:versionCode="{version_code}"
      android:versionName="{version_name}"
      android:installLocation="auto">

    <supports-screens
            android:smallScreens="true"
            android:normalScreens="true"
            android:largeScreens="true"
            android:anyDensity="true"
            android:xlargeScreens="true" />

    <uses-sdk android:minSdkVersion="{min_sdk}" android:targetSdkVersion="{compile_sdk}" />

    <!-- OpenGL ES 2.0: pygame's SDL2 renderer needs it. -->
    <uses-feature android:glEsVersion="0x00020000" />

    <application android:label="@string/app_name"
                 android:icon="@mipmap/icon"
                 android:allowBackup="false"
                 android:theme="@android:style/Theme.NoTitleBar"
                 android:hardwareAccelerated="true"
                 android:extractNativeLibs="true">

        <meta-data android:name="wakelock" android:value="0"/>

        <activity android:name="org.kivy.android.PythonActivity"
                  android:label="@string/app_name"
                  android:configChanges="mcc|mnc|locale|touchscreen|keyboard|keyboardHidden|navigation|orientation|screenLayout|fontScale|uiMode|screenSize|smallestScreenSize|layoutDirection|density"
                  android:screenOrientation="{orientation}"
                  android:exported="true"
                  android:theme="@style/KivySupportCutout"
                  android:launchMode="singleTask">

            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
'''

#: Strings and styles the manifest and the bootstrap read. p4a rendered this
#: from ``templates/strings.tmpl.xml`` on every packaging run and never stored it
#: in ``src/res_initial``, so the editor has to write it: ``@string/app_name`` and
#: ``@style/KivySupportCutout`` are referenced by the manifest and AAPT fails
#: without them. ``presplash_color`` and ``private_version`` are read by name at
#: runtime (``ResourceManager.getIdentifier``).
STRINGS_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="KivySupportCutout">
        <item name="android:windowNoTitle">true</item>
        <item name="android:windowLayoutInDisplayCutoutMode">shortEdges</item>
        <item name="android:windowTranslucentStatus">true</item>
        <item name="android:windowTranslucentNavigation">true</item>
        <item name="android:windowFullscreen">true</item>
    </style>
    <string name="app_name">{app_name}</string>
    <string name="private_version">{private_version}</string>
    <string name="presplash_color">{presplash_color}</string>
</resources>
'''

#: Splash background the window starts from (the injector re-reads the real one
#: from the image's corners).
DEFAULT_SPLASH_COLOR = '#1e1e1e'

#: Project setting -> ``android:screenOrientation`` value.
ORIENTATIONS = {
    'landscape': 'landscape',
    'portrait': 'portrait',
    'sensor_landscape': 'sensorLandscape',
    'sensor_portrait': 'sensorPortrait',
    'full_sensor': 'fullSensor',
}
#: Pick used when the project has no orientation (or an unknown value).
DEFAULT_ORIENTATION = 'landscape'

#: Rewrites applied to the pack's ``build.gradle``. Each pattern must match
#: exactly once - if p4a changes the template, the build stops with a message
#: instead of shipping an APK with the spike's package name.
GRADLE_PATCHES = (
    ("namespace\\s+'[^']*'", "namespace '{package}'"),
    ("versionCode\\s+\\d+", 'versionCode {version_code}'),
    ("versionName\\s+'[^']*'", "versionName '{version_name}'"),
    ("compileSdkVersion\\s+\\d+", 'compileSdkVersion {compile_sdk}'),
    ("minSdkVersion\\s+\\d+", 'minSdkVersion {min_sdk}'),
    ("targetSdkVersion\\s+\\d+", 'targetSdkVersion {compile_sdk}'),
)
#: Applied only when a build-tools version is known.
BUILD_TOOLS_LINE = r"^.*buildToolsVersion\s+'[^']*'\s*$\n?"

#: Gradle output fragments (lower case) and the translation key to report.
ERROR_HINTS = (
    ('unsupported class file major version', 'android.error_java_too_old'),
    ('android gradle plugin requires java', 'android.error_java_too_old'),
    ('sdk location not found', 'android.error_sdk_path'),
    ('failed to install the following android sdk packages', 'android.error_sdk_packages'),
    ('failed to find target with hash string', 'android.error_sdk_platform'),
    ('you have not accepted the license agreements', 'android.error_sdk_license'),
    ('could not resolve all files', 'android.error_network'),
    ('unknownhostexception', 'android.error_network'),
    ('could not download', 'android.error_network'),
    ('connection reset', 'android.error_network'),
    ('no space left on device', 'android.error_disk'),
)


class AndroidBuildError(RuntimeError):
    """A build step failed; ``reason`` is a translation key for the window."""

    def __init__(self, message='', reason='android.error_build'):
        super().__init__(message)
        self.detail = message
        self.reason = reason


def _copy_runtime(runtime_dir, dist_dir):
    """Copy the pack over the work folder (leaves ``build/`` alone)."""
    shutil.copytree(runtime_dir, dist_dir, dirs_exist_ok=True)


def _seed_resources(dist_dir, runtime_dir):
    """Restore both resource trees from the PRISTINE pack, not from the work dir.

    p4a restores ``src/main/res`` from ``src/res_initial`` on every packaging
    run, and the injection step patches that copy too - so seeding from the work
    folder would make the previous project's icon and splash come back forever.
    Both trees are rebuilt from ``<pack>/src/res_initial`` instead, which the
    cache never modifies.
    """
    pristine = Path(runtime_dir) / 'src' / 'res_initial'
    if not pristine.is_dir():
        raise AndroidBuildError(f'the runtime pack has no src/res_initial: {runtime_dir}',
                                'android.error_pack_layout')
    for relative in ('src/main/res', 'src/res_initial'):
        target = Path(dist_dir) / relative
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(pristine, target)


def _write_strings(dist_dir, app_name, version_code, version_name):
    """Write ``values/strings.xml`` into both resource trees.

    AAPT resolves ``@string/app_name`` and ``@style/KivySupportCutout`` when the
    APK is packaged, so the file has to exist before Gradle runs; writing it
    into ``res_initial`` too keeps it after the next reseed.
    """
    private_version = hashlib.sha1(
        f'{version_name} {int(version_code)}'.encode('utf-8')).hexdigest()
    text = STRINGS_TEMPLATE.format(
        app_name=xml_escape(str(app_name or '')),
        private_version=private_version,
        presplash_color=DEFAULT_SPLASH_COLOR)

    written = []
    for relative in ('src/main/res', 'src/res_initial'):
        values = Path(dist_dir) / relative / 'values'
        values.mkdir(parents=True, exist_ok=True)
        target = values / 'strings.xml'
        target.write_text(text, encoding='utf-8')
        written.append(target)
    return written


def _write_manifest(dist_dir, version_code, version_name, orientation, min_sdk,
                    compile_sdk):
    manifest = MANIFEST_TEMPLATE.format(version_code=int(version_code),
                                        version_name=str(version_name),
                                        orientation=ORIENTATIONS.get(orientation,
                                                                     ORIENTATIONS[DEFAULT_ORIENTATION]),
                                        min_sdk=int(min_sdk),
                                        compile_sdk=int(compile_sdk))
    target = dist_dir / 'src' / 'main' / 'AndroidManifest.xml'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest, encoding='utf-8')
    return target


def _patch_build_gradle(dist_dir, package, version_code, version_name,
                        compile_sdk, min_sdk):
    """Rewrite the app identity of the pack's Gradle project, in place."""
    target = dist_dir / 'build.gradle'
    if not target.is_file():
        raise AndroidBuildError(f'the runtime pack has no build.gradle: {dist_dir}',
                                'android.error_pack_layout')
    text = target.read_text(encoding='utf-8')

    values = {'package': package, 'version_code': int(version_code),
              'version_name': str(version_name), 'compile_sdk': int(compile_sdk),
              'min_sdk': int(min_sdk)}

    for pattern, replacement in GRADLE_PATCHES:
        text, count = re.subn(pattern, lambda match, r=replacement: r.format(**values),
                              text, count=1)
        if count != 1:
            raise AndroidBuildError(
                f'build.gradle no longer matches "{pattern}" - the runtime pack changed',
                'android.error_pack_layout')

    # The pack pins the build-tools of the CI machine. Every Android Gradle
    # Plugin has its own minimum (8.11 refuses anything below 35) and installs
    # that version itself, so a pinned value only produces a warning here.
    text = re.sub(BUILD_TOOLS_LINE, '', text, count=1, flags=re.MULTILINE)

    # AGP 8 takes the application id from the namespace unless it is set, and a
    # project may want a different one; keep it explicit and stable.
    if re.search(r"applicationId\s+'[^']*'", text):
        text = re.sub(r"applicationId\s+'[^']*'",
                      f"applicationId '{package}'", text, count=1)
    else:
        text = text.replace('defaultConfig {',
                            f"defaultConfig {{\n        applicationId '{package}'",
                            1)

    target.write_text(text, encoding='utf-8')
    return target


def _write_local_properties(dist_dir, sdk_dir):
    """Point Gradle at the SDK (forward slashes: it is a .properties file)."""
    target = dist_dir / 'local.properties'
    target.write_text(f'sdk.dir={Path(sdk_dir).as_posix()}\n', encoding='utf-8')
    return target


def _patch_gradle_wrapper(dist_dir):
    """Use the ``-bin`` distribution instead of ``-all``.

    ``-all`` only adds the sources and the docs of Gradle itself; it is ~100 MB
    more to download on the first build and the editor downloads it into its own
    ``GRADLE_USER_HOME``, so nobody has it cached yet. The version is kept.
    """
    target = Path(dist_dir) / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
    if not target.is_file():
        return None
    text = target.read_text(encoding='utf-8')
    patched, count = re.subn(r'(distributionUrl=.*?gradle-[\d.]+)-all\.zip',
                             r'\1-bin.zip', text, count=1)
    if count:
        target.write_text(patched, encoding='utf-8')
    return target


def _patch_gradle_properties(dist_dir):
    """Give Gradle a heap that can dex a game (the pack's file is empty)."""
    target = Path(dist_dir) / 'gradle.properties'
    text = target.read_text(encoding='utf-8') if target.is_file() else ''
    if 'org.gradle.jvmargs' not in text:
        text = text.rstrip('\n') + '\norg.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8\n'
    target.write_text(text, encoding='utf-8')
    return target


def prepare_dist(runtime_dir, dist_dir, *, app_name, package, version_code=1,
                 version_name='1.0.0', orientation=DEFAULT_ORIENTATION,
                 min_sdk=MIN_SDK, compile_sdk=COMPILE_SDK,
                 sdk_dir='', icon='', presplash='', adaptive=True,
                 on_progress=None):
    """Lay the pack out as a buildable project and inject the app's identity.

    :return: summary dict (paths of the files that were rewritten)
    """
    from pygamestudio.gui.build import android_assets

    report = on_progress or (lambda percent: None)
    runtime_dir = Path(runtime_dir)
    dist_dir = Path(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    report(0)
    _copy_runtime(runtime_dir, dist_dir)

    report(40)
    _seed_resources(dist_dir, runtime_dir)

    report(45)
    strings = _write_strings(dist_dir, app_name, version_code, version_name)

    report(50)
    assets = android_assets.run(dist_dir, icon or None, presplash or None,
                                app_name=app_name, adaptive=adaptive)

    report(60)
    manifest = _write_manifest(dist_dir, version_code, version_name, orientation,
                               min_sdk, compile_sdk)
    report(70)
    gradle = _patch_build_gradle(dist_dir, package, version_code, version_name,
                                 compile_sdk, min_sdk)
    _patch_gradle_wrapper(dist_dir)
    _patch_gradle_properties(dist_dir)
    local_properties = _write_local_properties(dist_dir, sdk_dir) if sdk_dir else None

    report(75)
    return {'dist_dir': dist_dir, 'manifest': manifest, 'build_gradle': gradle,
            'local_properties': local_properties, 'strings': strings,
            'assets': assets.get('files', []), 'splash_color': assets.get('color')}


def write_payload(payload_dir, target, numeric_version=1, min_sdk=MIN_SDK):
    """Write ``src/main/assets/private.tar`` from the prepared payload folder."""
    from pygamestudio.gui.build import runtime_payload

    return runtime_payload.make_payload_tar(payload_dir, target,
                                            numeric_version=numeric_version,
                                            min_sdk=min_sdk)


def gradle_executable(dist_dir):
    """``gradlew`` of the work folder, made executable on POSIX."""
    dist_dir = Path(dist_dir)
    if platform.system() == 'Windows':
        return dist_dir / 'gradlew.bat'
    launcher = dist_dir / 'gradlew'
    if launcher.is_file():
        try:
            launcher.chmod(0o755)
        except OSError:
            pass
    return launcher


def gradle_environment(jdk, sdk, gradle_home, proxy=None):
    """Environment for a Gradle run: the user's JDK/SDK and a private cache."""
    environment = dict(os.environ)
    environment['JAVA_HOME'] = str(jdk)
    environment['ANDROID_HOME'] = str(sdk)
    environment['ANDROID_SDK_ROOT'] = str(sdk)
    environment['GRADLE_USER_HOME'] = str(gradle_home)
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['PYTHONUTF8'] = '1'
    # A stale JAVA_TOOL_OPTIONS from the user's shell can break the Gradle JVM.
    environment.pop('JAVA_TOOL_OPTIONS', None)

    # Java ignores the system proxy, so a machine that reaches the internet
    # through one (the common Clash/v2ray setup) would time out on the very
    # first download. The caller passes the proxy only after a direct attempt
    # failed, see gui/build/android.py.
    #
    # Both variables are set on purpose: GRADLE_OPTS reaches the launcher (the
    # wrapper download) and JAVA_TOOL_OPTIONS reaches every JVM Gradle forks -
    # the build runs in a daemon, and a JVM option handed to the launcher only
    # never gets there. The user's own JAVA_TOOL_OPTIONS is dropped either way,
    # because a stale one breaks the daemon.
    if proxy:
        host, port = proxy
        options = (f'-Dhttp.proxyHost={host} -Dhttp.proxyPort={port} '
                   f'-Dhttps.proxyHost={host} -Dhttps.proxyPort={port}')
        environment['GRADLE_OPTS'] = options
        environment['JAVA_TOOL_OPTIONS'] = options
    return environment


def windows_proxy():
    """``(host, port)`` of the Windows system proxy, or None.

    Reads ``ProxyEnable``/``ProxyServer`` of the current user, the same setting
    Android Studio and the browsers follow. ``ProxyServer`` is either
    ``host:port`` or a per-protocol list (``http=host:port;https=host:port``).
    """
    if platform.system() != 'Windows':
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
            enabled = winreg.QueryValueEx(key, 'ProxyEnable')[0]
            server = winreg.QueryValueEx(key, 'ProxyServer')[0]
    except (OSError, ImportError, IndexError):
        return None
    if not enabled or not server:
        return None
    entry = str(server).split(';')[0]
    if '=' in entry:
        entry = entry.split('=', 1)[1]
    host, _, port = entry.partition(':')
    return (host, port) if host and port.isdigit() else None


def use_proxy(dist_dir, proxy):
    """Write the proxy into ``gradle.properties`` for the Gradle daemon too.

    The connection limit is part of the proxy setup on purpose: a local proxy
    (Clash, v2ray) drops most of Gradle's parallel TLS handshakes with "remote
    host terminated the handshake", so a smaller pool is what makes the first
    build work at all. The timeouts cover a slow proxy line.
    """
    target = Path(dist_dir) / 'gradle.properties'
    text = target.read_text(encoding='utf-8') if target.is_file() else ''
    text = '\n'.join(line for line in text.splitlines()
                     if not line.startswith(('systemProp.http', 'systemProp.https',
                                             'org.gradle.internal.http')))
    host, port = proxy
    text = text.rstrip('\n') + ('\n'
                                f'systemProp.http.proxyHost={host}\n'
                                f'systemProp.http.proxyPort={port}\n'
                                f'systemProp.https.proxyHost={host}\n'
                                f'systemProp.https.proxyPort={port}\n'
                                'systemProp.org.gradle.internal.http.connectionTimeout=60000\n'
                                'systemProp.org.gradle.internal.http.socketTimeout=120000\n'
                                'org.gradle.internal.http.maxConnections=4\n'
                                'org.gradle.internal.repository.max.retries=6\n')
    target.write_text(text, encoding='utf-8')
    return target


def run_gradle(dist_dir, jdk, sdk, gradle_home, task=DEBUG_TASK,
               on_line=None, on_progress=None, stop_check=None, proxy=None):
    """Run a Gradle task in the work folder and stream its output.

    :return: the process exit code (0 on success)
    """
    dist_dir = Path(dist_dir)
    launcher = gradle_executable(dist_dir)
    if not launcher.is_file():
        raise AndroidBuildError(f'gradlew is missing from {dist_dir}',
                                'android.error_pack_layout')

    command = [str(launcher), '--console=plain', task]
    process = subprocess.Popen(command,
                               cwd=str(dist_dir),
                               env=gradle_environment(jdk, sdk, gradle_home, proxy),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace',
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    tasks = 0
    try:
        for line in iter(process.stdout.readline, ''):
            line = line.rstrip()
            if not line:
                continue
            if on_line is not None:
                on_line(line)
            if line.lstrip().startswith('> Task :'):
                tasks += 1
                if on_progress is not None:
                    on_progress(min(95, 75 + tasks * 2))
            if stop_check is not None and stop_check():
                process.kill()
                break
    finally:
        if process.stdout is not None:
            process.stdout.close()
    return process.wait()


def find_apk(dist_dir):
    """The APK the task produced (newest one, since the folder is reused)."""
    outputs = Path(dist_dir) / 'build' / 'outputs' / 'apk'
    if not outputs.is_dir():
        return None
    candidates = sorted(outputs.rglob('*.apk'), key=lambda path: path.stat().st_mtime,
                        reverse=True)
    return candidates[0] if candidates else None


def translate_error(text):
    """Map a Gradle failure to a translation key ('' when nothing matches)."""
    lowered = (text or '').lower()
    for needle, key in ERROR_HINTS:
        if needle in lowered:
            return key
    return ''


#: Fragments that mean "the network, not the project" (they trigger the proxy retry).
NETWORK_FAILURES = ('connection timed out', 'connectexception', 'connection reset',
                    'unknownhostexception', 'could not resolve', 'timed out',
                    'network is unreachable', 'failed to connect')


def is_network_failure(text):
    """True when the Gradle output looks like a download/connection problem."""
    lowered = (text or '').lower()
    return any(needle in lowered for needle in NETWORK_FAILURES)


def package_name_for(app_name):
    """``My Game 2`` -> ``org.pygamestudio.mygame2`` (a valid, unique default)."""
    slug = re.sub(r'[^a-z0-9]+', '', str(app_name or '').lower())
    return f'org.pygamestudio.{slug or "game"}'


def is_valid_package(text):
    """Java package rules: two or more lowercase segments, no dashes."""
    return re.fullmatch(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+', str(text or '')) is not None
