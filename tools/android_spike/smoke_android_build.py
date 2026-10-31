"""Headless check of the editor's Android build steps (no device needed).

It exercises exactly what ``gui/build/android.py`` does before the SDK tools
run:

1. unpack the shipped runtime pack and check its layout;
2. protect a copy of the spike project (strip + encrypt);
3. stage the engine subset into the payload;
4. write ``assets/private.tar`` and inspect its members;
5. lay the pack out as a buildable app - icon, splash, app name, strings,
   manifest - twice, so the rewrites are proven idempotent;
6. a build without an icon must fall back to the pack's own artwork.

The APK itself is built by ``smoke_android_apk.py`` (it needs a real SDK).

    py -3.10 tools/android_spike/smoke_android_build.py
"""
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / 'src'))

from pygamestudio.common.utils import android_runtime                    # noqa: E402
from pygamestudio.gui.build import android_apk, android_dist, protection, runtime_payload  # noqa: E402

SPIKE_APP = REPO_ROOT / 'tools' / 'android_spike' / 'app'
SPIKE_ICON = REPO_ROOT / 'tools' / 'android_spike' / 'assets' / 'icon.png'
SPIKE_SPLASH = REPO_ROOT / 'tools' / 'android_spike' / 'assets' / 'presplash.jpg'
ENGINE_ROOT = REPO_ROOT / 'src' / 'pygamestudio'

PACKAGE = 'org.pygamestudio.smoke'
VERSION_CODE = 7
VERSION_NAME = '1.2.3'

results = []


def check(name, condition, detail=''):
    results.append((name, bool(condition), detail))
    status = 'ok  ' if condition else 'FAIL'
    print(f'  [{status}] {name}{(" - " + detail) if detail else ""}')


def copy_project(target):
    """The spike project without the staged engine (that is staged later)."""
    shutil.copytree(SPIKE_APP, target,
                    ignore=shutil.ignore_patterns('pygamestudio', '__pycache__',
                                                  '*.pyc', '_spike.png'))
    return target


def main():
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)

        print('1) runtime pack')
        metadata = android_runtime.find_pack()['metadata']
        print(f'   {android_runtime.describe(metadata)}')
        runtime_dir = android_runtime.ensure_unpacked()
        check('python bundle unpacked',
              (runtime_dir / metadata['layout']['python_bundle'] / 'stdlib.zip').is_file())
        check('native libs unpacked',
              len(list((runtime_dir / metadata['layout']['libs']).glob('*.so'))) >= 10)
        check('java bootstrap unpacked', (runtime_dir / metadata['layout']['java']).is_dir())
        check('resources unpacked', (runtime_dir / metadata['layout']['resources']).is_dir())
        check('second call hits the cache', android_runtime.is_unpacked(metadata))

        print('2) protected project')
        payload_root = temp / 'payload'
        project = copy_project(temp / 'project')
        prepared = protection.prepare(project, payload_root)
        payload_dir = prepared['project_dir']
        check('project.pygs is encrypted',
              (payload_dir / 'project.pygs').read_bytes().startswith(b'PGSXA1'))
        check('main.py stays readable', (payload_dir / 'main.py').is_file()
              and not (payload_dir / 'main.py').read_bytes().startswith(b'PGSXA1'))
        check('key blob written', (payload_dir / 'resources.cache').is_file())

        print('3) engine staged into the payload')
        staged = runtime_payload.stage(ENGINE_ROOT, payload_dir)
        check('engine files staged', staged['files'] > 40, f'{staged["files"]} files')
        for relative in ('pygamestudio/api/core/game.py',
                         'pygamestudio/game/object/base.py',
                         'pygamestudio/common/utils/assets.py',
                         'pygamestudio/sdk/__init__.py'):
            check(f'{relative} present', (payload_dir / relative).is_file())
        for relative in ('pygamestudio/gui/build/android.py',
                         'pygamestudio/gui/build/android_apk.py',
                         'pygamestudio/common/utils/config.py',
                         'pygamestudio/common/utils/android_runtime.py'):
            check(f'{relative} excluded', not (payload_dir / relative).exists())

        print('4) assets/private.tar')
        dist_dir = temp / 'dist'
        summary = android_dist.prepare_dist(
            runtime_dir, dist_dir,
            app_name='Smoke Game', package=PACKAGE,
            version_code=VERSION_CODE, version_name=VERSION_NAME,
            orientation='landscape',
            icon=SPIKE_ICON)
        pristine_splash = (runtime_dir / 'src' / 'res_initial' / 'drawable' / 'presplash.jpg').read_bytes()
        shipped_splash = (dist_dir / 'src' / 'main' / 'res' / 'drawable' / 'presplash.jpg').read_bytes()
        check('icon written',
              (dist_dir / 'src' / 'main' / 'res' / 'mipmap-xxxhdpi' / 'icon.png').is_file())
        check('the icon does NOT replace the splash', shipped_splash == pristine_splash)
        check('splash colour still reported (from the pack image)',
              bool(summary['splash_color']), str(summary['splash_color']))

        private_tar = dist_dir / 'src' / 'main' / 'assets' / 'private.tar'
        tar_summary = android_dist.write_payload(payload_dir, private_tar,
                                                 numeric_version=VERSION_CODE)
        with tarfile.open(private_tar, 'r:*') as archive:
            members = {member.name: member for member in archive.getmembers() if member.isfile()}
            main_bytes = archive.extractfile('main.py').read()
            config_bytes = archive.extractfile('project.pygs').read()
        check('payload has main.py', 'main.py' in members)
        check('main.py not byte-compiled', not main_bytes.startswith(b'PGSXA1'))
        check('project.pygs stays encrypted in the tar', config_bytes.startswith(b'PGSXA1'))
        check('engine ships inside the tar',
              'pygamestudio/api/core/game.py' in members)
        check('scene + scripts ship',
              any(name.startswith('scenes/') for name in members)
              and any(name.startswith('scripts/') for name in members))
        check('project assets ship', any(name.startswith('assets/') for name in members))
        check('sitecustomize written', 'sitecustomize.py' in members)
        check('p4a env file written', 'p4a_env_vars.txt' in members)
        check('no .pyc in the tar', not any(name.endswith('.pyc') for name in members))
        check('no __pycache__ in the tar',
              not any('__pycache__' in name for name in members))
        print(f'   private.tar: {tar_summary["files"]} files, {tar_summary["bytes"]} B')

        print('5) app identity')
        manifest = (dist_dir / 'src' / 'main' / 'AndroidManifest.xml').read_text(encoding='utf-8')
        strings = (dist_dir / 'src' / 'main' / 'res' / 'values' / 'strings.xml').read_text(encoding='utf-8')
        pristine_strings = (dist_dir / 'src' / 'res_initial' / 'values' / 'strings.xml').read_text(encoding='utf-8')
        check('manifest carries the package', f'package="{PACKAGE}"' in manifest)
        check('manifest version',
              f'android:versionCode="{VERSION_CODE}"' in manifest
              and f'android:versionName="{VERSION_NAME}"' in manifest)
        check('manifest orientation', 'android:screenOrientation="landscape"' in manifest)
        check('manifest labels the app', 'android:label="@string/app_name"' in manifest)
        check('manifest min/target sdk',
              'android:minSdkVersion="24"' in manifest
              and 'android:targetSdkVersion="34"' in manifest)
        check('manifest launches the bootstrap',
              'org.kivy.android.PythonActivity' in manifest)
        check('app name in res/values', '<string name="app_name">Smoke Game</string>' in strings)
        check('app name in res_initial too',
              '<string name="app_name">Smoke Game</string>' in pristine_strings)
        check('startup style survives', 'KivySupportCutout' in strings)

        print('6) second run is idempotent')
        android_dist.prepare_dist(
            runtime_dir, dist_dir,
            app_name='Smoke Game', package=PACKAGE,
            version_code=VERSION_CODE, version_name=VERSION_NAME,
            orientation='portrait',
            icon=SPIKE_ICON)
        manifest = (dist_dir / 'src' / 'main' / 'AndroidManifest.xml').read_text(encoding='utf-8')
        strings = (dist_dir / 'src' / 'main' / 'res' / 'values' / 'strings.xml').read_text(encoding='utf-8')
        check('one package attribute only', manifest.count('package="') == 1)
        check('orientation follows the second run',
              'android:screenOrientation="portrait"' in manifest)
        check('strings not duplicated', strings.count('app_name') == 1)

        print('7) a build without an icon starts from the pack again')
        pristine_icon = (runtime_dir / 'src' / 'res_initial' / 'mipmap-xxxhdpi' / 'icon.png').read_bytes()
        pristine_splash = (runtime_dir / 'src' / 'res_initial' / 'drawable' / 'presplash.jpg').read_bytes()
        android_dist.prepare_dist(
            runtime_dir, dist_dir,
            app_name='No Icon', package=PACKAGE,
            version_code=1, version_name='1.0.0')
        shipped_icon = (dist_dir / 'src' / 'main' / 'res' / 'mipmap-xxxhdpi' / 'icon.png').read_bytes()
        shipped_splash = (dist_dir / 'src' / 'main' / 'res' / 'drawable' / 'presplash.jpg').read_bytes()
        check('icon is the pack default again', shipped_icon == pristine_icon)
        check('splash is the pack default again', shipped_splash == pristine_splash)

        print('8) helpers')
        check('package helper', android_dist.package_name_for('My Game 2') == 'org.pygamestudio.mygame2')
        check('package validation', android_dist.is_valid_package(PACKAGE)
              and not android_dist.is_valid_package('My Game'))
        environment = android_dist.signing_environment(
            {'keystore': 'C:/keys/game.jks', 'alias': 'game'},
            {'store_password': 's3cret', 'key_password': ''})
        check('signing env carries the store password',
              environment['PYGS_KEYSTORE_PASSWORD'] == 's3cret')
        check('an empty key password falls back to the store one',
              environment['PYGS_KEY_PASSWORD'] == 's3cret')
        check('tool names', android_apk.tool_name('aapt2').startswith('aapt2'))
        chinese = '注: 某些输入文件使用或覆盖了已过时的 API'
        check('decode_line survives GBK output',
              android_apk.decode_line(chinese.encode('gbk')) == chinese)

        empty = android_runtime.check_toolchain('', '')
        check('an empty JDK path is reported, not guessed',
              'android.jdk_not_set' in empty['problems'], ', '.join(empty['problems']))
        check('an empty SDK path is reported, not guessed',
              'android.sdk_not_set' in empty['problems'], ', '.join(empty['problems']))
        check('a filled-in path is used as it is, no scanning',
              android_runtime.check_toolchain('', 'X:/nowhere')['sdk'] == 'X:/nowhere')

        jdk = os.environ.get('PYGS_TEST_JDK', 'D:/JDK')
        sdk = os.environ.get('PYGS_TEST_SDK', 'D:/SDK')
        toolchain = android_runtime.check_toolchain(jdk, sdk)
        if toolchain['ok']:
            tools_dir = android_apk.find_tools(toolchain['sdk'])
            jar = android_apk.android_jar(toolchain['sdk'], android_runtime.COMPILE_SDK)
            check('SDK tools found', tools_dir.is_dir(), tools_dir.as_posix())
            check('android.jar found', jar.is_file(), jar.as_posix())
        else:
            print(f'   (SDK tools not installed here, tool lookup skipped: {toolchain["problems"]})')

    passed = sum(1 for _name, ok, _detail in results if ok)
    failed = [name for name, ok, _detail in results if not ok]
    print(f'\n{passed}/{len(results)} check(s) passed')
    if failed:
        print('FAILED: ' + ', '.join(failed))
        print('RESULT : the editor-side Android build steps are broken')
        return 1
    print('RESULT : payload, assets, strings and manifest are built correctly')
    return 0


if __name__ == '__main__':
    sys.exit(main())
