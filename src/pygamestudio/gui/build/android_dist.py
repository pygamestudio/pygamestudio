"""Lay the frozen runtime pack out as a buildable app and inject its identity.

The pack is a p4a *dist* skeleton, but nothing here runs Gradle: the APK is
assembled by ``android_apk.py`` straight from the same folders Gradle would
have used (``src/main/res``, ``src/main/java``, ``libs/<abi>``, ``assets``).
This module only has to:

1. copy the pack into the work folder (Gradle's leftovers are ignored),
2. reseed both resource trees from the PRISTINE pack (the previous project's
   icon must not come back),
3. write ``values/strings.xml`` and ``AndroidManifest.xml``,
4. inject the icon / splash / app name.

``build.gradle`` and the wrapper are still in the pack (the freezer keeps a
complete dist), they are simply not used.
"""
import hashlib
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from pygamestudio.common.utils.android_runtime import COMPILE_SDK, MIN_SDK

#: Manifest written for every build. Based on what p4a's SDL2 bootstrap renders
#: (the version that ran on the device in spike 3b). The ``package`` attribute
#: is the application id: without Gradle there is no ``applicationId`` to set it,
#: and aapt2 refuses a manifest that has none.
MANIFEST_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
      package="{package}"
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


class AndroidBuildError(RuntimeError):
    """A build step failed; ``reason`` is a translation key for the window."""

    def __init__(self, message='', reason='android.error_build'):
        super().__init__(message)
        self.detail = message
        self.reason = reason


def _copy_runtime(runtime_dir, dist_dir):
    """Copy the pack over the work folder (leaves anything else alone)."""
    shutil.copytree(runtime_dir, dist_dir, dirs_exist_ok=True)


def _seed_resources(dist_dir, runtime_dir):
    """Restore both resource trees from the PRISTINE pack, not from the work dir.

    p4a restores ``src/main/res`` from ``src/res_initial`` on every packaging
    run, and the injection step patches that copy too - so seeding from the work
    folder would make the previous project's icon and splash come back forever.
    Both trees are rebuilt from ``<pack>/src/res_initial``, which the cache never
    modifies.
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
    """Write ``values/strings.xml`` into both resource trees."""
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


def _write_manifest(dist_dir, package, version_code, version_name, orientation,
                    min_sdk, compile_sdk):
    manifest = MANIFEST_TEMPLATE.format(
        package=str(package),
        version_code=int(version_code),
        version_name=str(version_name),
        orientation=ORIENTATIONS.get(orientation, ORIENTATIONS[DEFAULT_ORIENTATION]),
        min_sdk=int(min_sdk),
        compile_sdk=int(compile_sdk))
    target = Path(dist_dir) / 'src' / 'main' / 'AndroidManifest.xml'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest, encoding='utf-8')
    return target


def prepare_dist(runtime_dir, dist_dir, *, app_name, package, version_code=1,
                 version_name='1.0.0', orientation=DEFAULT_ORIENTATION,
                 min_sdk=MIN_SDK, compile_sdk=COMPILE_SDK,
                 icon='', presplash='', adaptive=True, on_progress=None):
    """Lay the pack out as a buildable project and inject the app's identity.

    :return: summary dict (the files that were written)
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

    report(70)
    manifest = _write_manifest(dist_dir, package, version_code, version_name,
                               orientation, min_sdk, compile_sdk)

    report(75)
    return {'dist_dir': dist_dir, 'manifest': manifest, 'strings': strings,
            'assets': assets.get('files', []), 'splash_color': assets.get('color')}


def write_payload(payload_dir, target, numeric_version=1, min_sdk=MIN_SDK):
    """Write ``src/main/assets/private.tar`` from the prepared payload folder."""
    from pygamestudio.gui.build import runtime_payload

    return runtime_payload.make_payload_tar(payload_dir, target,
                                            numeric_version=numeric_version,
                                            min_sdk=min_sdk)


def signing_environment(signing, config=None):
    """Environment variables ``apksigner`` reads the release key from."""
    if not signing:
        return {}
    config = config or {}
    return {
        'PYGS_KEYSTORE_PASSWORD': str(config.get('store_password') or ''),
        'PYGS_KEY_PASSWORD': str(config.get('key_password') or ''
                                  or config.get('store_password') or ''),
    }


def create_keystore(jdk, path, alias, password, common_name='Pygame Studio Game'):
    """Create a self-signed release key with the JDK's ``keytool``.

    The passwords reach keytool through the environment (``:env``), so they are
    not visible in the process list. Everything else is a normal, valid release
    key: 2048-bit RSA, ten thousand days.
    """
    keytool = Path(jdk) / 'bin' / ('keytool.exe' if platform.system() == 'Windows' else 'keytool')
    if not keytool.is_file():
        raise AndroidBuildError(f'keytool not found in {jdk}', 'android.error_java_too_old')

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment['PYGS_STORE_PASSWORD'] = str(password)
    environment['PYGS_KEY_PASSWORD'] = str(password)
    command = [str(keytool), '-genkeypair', '-v',
               '-keystore', str(path), '-alias', str(alias),
               '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
               '-storepass:env', 'PYGS_STORE_PASSWORD',
               '-keypass:env', 'PYGS_KEY_PASSWORD',
               '-dname', f'CN={common_name}, O=PygameStudio, C=CN']
    completed = subprocess.run(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True,
                               encoding='utf-8', errors='replace',
                               env=environment, timeout=180,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if completed.returncode != 0:
        raise AndroidBuildError(completed.stdout or 'keytool failed',
                                'android.error_keystore')
    return path


def package_name_for(app_name):
    """``My Game 2`` -> ``org.pygamestudio.mygame2`` (a valid, unique default)."""
    slug = re.sub(r'[^a-z0-9]+', '', str(app_name or '').lower())
    return f'org.pygamestudio.{slug or "game"}'


def is_valid_package(text):
    """Java package rules: two or more lowercase segments, no dashes."""
    return re.fullmatch(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+', str(text or '')) is not None
