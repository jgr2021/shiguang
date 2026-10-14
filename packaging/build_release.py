"""Build clean native distribution files on Windows or macOS. No personal data."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
VERSION = re.search(r'^VERSION = "([0-9.]+)"', (ROOT/'app_config.py').read_text(encoding='utf-8'), re.M)[1]


def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def licenses(destination):
    destination.mkdir(parents=True)
    pending = ['pypdf', 'cryptography', 'keyring', 'pyinstaller', 'pillow']
    seen, notices = set(), []
    from packaging.requirements import Requirement
    while pending:
        name = pending.pop()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        notices.append(dist.metadata['Name'] + ' ' + dist.version)
        for requirement in dist.requires or []:
            req = Requirement(requirement)
            if req.marker is None or req.marker.evaluate():
                pending.append(req.name)
        for relative in dist.files or []:
            if any(part.lower().startswith(('license', 'copying', 'notice', 'authors')) for part in relative.parts):
                source = Path(dist.locate_file(relative))
                if source.is_file() and source.suffix.lower() not in {'.py', '.pyc'}:
                    target = destination/name/str(relative).replace('..', '_').replace(':', '_')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    for candidate in [Path(sys.base_prefix)/'LICENSE.txt', Path(sys.base_prefix)/'Resources/English.lproj/License.rtf']:
        if candidate.is_file():
            shutil.copy2(candidate, destination/candidate.name)
    (destination/'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(sorted(notices)), encoding='utf-8')


def main():
    release = ROOT/'release'
    release.mkdir(exist_ok=True)
    base = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onedir',
            '--name', 'Shiguang', '--icon', ROOT/'shiguang.ico', '--exclude-module', 'numpy']
    if sys.platform == 'darwin':
        arch = platform.machine()
        if arch not in {'arm64', 'x86_64'}:
            raise SystemExit('Unsupported macOS architecture')
        args = base + ['--osx-bundle-identifier', 'org.shiguang.desktop', '--target-arch', arch,
                       '--hidden-import', 'keyring.backends.macOS']
        for name in ['MACOS-START.md', 'GitHub同步说明.md', 'AI连接指南.md']:
            args += ['--add-data', str(ROOT/name) + ':.']
        run(*args, ROOT/'desktop_app.py')
        bundle = ROOT/'dist/Shiguang.app'
        resources = bundle/'Contents/Resources'
        registration = json.loads((ROOT/'github-app.json').read_text(encoding='utf-8-sig'))
        if set(registration) != {'client_id', 'slug'} or not all(isinstance(x, str) for x in registration.values()):
            raise SystemExit('github-app.json must contain only public app registration.')
        (resources/'github-app.json').write_text(json.dumps(registration, indent=2), encoding='utf-8')
        licenses(resources/'licenses')
        info_path = bundle/'Contents/Info.plist'
        info = plistlib.loads(info_path.read_bytes())
        info.update(CFBundleName='Shiguang', CFBundleDisplayName='拾光 Shiguang',
                    CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                    LSMinimumSystemVersion='15.0', NSHighResolutionCapable=True)
        info_path.write_bytes(plistlib.dumps(info))
        # Local code signature required by Apple Silicon; no Developer ID or notarization.
        run('/usr/bin/codesign', '--force', '--deep', '--sign', '-', bundle)
        run('/usr/bin/codesign', '--verify', '--deep', '--strict', bundle)
        prefix = 'Shiguang-' + VERSION + '-macOS-' + arch
        run('/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', bundle, release/(prefix + '.zip'))
        stage = ROOT/'dmg-stage'
        stage.mkdir()
        shutil.copytree(bundle, stage/'Shiguang.app', symlinks=True)
        (stage/'Applications').symlink_to('/Applications')
        shutil.copy2(ROOT/'MACOS-START.md', stage/'MACOS-START.md')
        run('/usr/bin/hdiutil', 'create', '-volname', 'Shiguang ' + VERSION, '-srcfolder', stage,
            '-ov', '-format', 'UDZO', release/(prefix + '.dmg'))
        suffix = 'macOS-' + arch
    elif sys.platform == 'win32':
        run(*base, '--version-file', ROOT/'packaging/version-info.txt', ROOT/'desktop_app.py')
        run(sys.executable, ROOT/'packaging/prepare_release.py', '--binary-dir', ROOT/'dist/Shiguang',
            '--stage', ROOT/'release-stage', '--release', release)
        iscc = shutil.which('ISCC.exe') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        if not Path(iscc).is_file():
            raise SystemExit('Inno Setup 6 is required')
        spec = ROOT/'build/Shiguang.iss'
        spec.write_text((ROOT/'packaging/Shiguang.iss').read_text(encoding='utf-8'), encoding='utf-8-sig')
        run(iscc, '/Qp', '/DAppSource=' + str(ROOT/'release-stage'), '/DReleaseDir=' + str(release),
            '/DChineseLanguage=' + str(ROOT/'packaging/languages/ChineseSimplified.isl'),
            '/DTraditionalLanguage=' + str(ROOT/'packaging/languages/ChineseTraditional.isl'), spec)
        suffix = 'Windows-x64'
    else:
        raise SystemExit('Build on a native Windows or macOS host')
    assets = [p for p in release.iterdir() if p.suffix in {'.exe', '.zip', '.dmg'}]
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in sorted(assets))
    (release/('SHA256SUMS-' + suffix + '.txt')).write_text(sums, encoding='ascii')
    print(json.dumps({'version': VERSION, 'platform': suffix, 'files': [p.name for p in assets]}))


if __name__ == '__main__':
    main()
