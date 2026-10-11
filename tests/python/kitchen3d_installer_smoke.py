"""Exercise Windows Setup, shortcuts, an upgrade, and uninstall on a clean runner."""
# SPDX-License-Identifier: GPL-2.0-or-later
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import winreg

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--setup', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
setup = args.setup.resolve()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
key_name = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Kitchen3D_is1'
registry_flags = winreg.KEY_READ | winreg.KEY_WOW64_64KEY


def installed_entry():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name, 0, registry_flags) as key:
            return {name: winreg.QueryValueEx(key, name)[0] for name in ('DisplayName', 'UninstallString')}
    except FileNotFoundError:
        return None


def registry_value(path, name=''):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, registry_flags) as key:
            return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return None


capabilities = r'Software\Kitchen3D\SetupCapabilities'
prog_id = r'Software\Classes\Kitchen3D.Setup.Blend'
user_choice = r'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.blend\UserChoice'
original_choice = registry_value(user_choice, 'ProgId')
original_extension = registry_value(r'Software\Classes\.blend')


def powershell(expression, **extra_env):
    return subprocess.check_output([
        'powershell.exe', '-NoProfile', '-NonInteractive', '-Command', expression,
    ], text=True, env=dict(os.environ, **extra_env)).strip()


if installed_entry() is not None or registry_value(r'Software\RegisteredApplications', 'Kitchen3D') is not None:
    raise SystemExit('Refusing to modify an existing Kitchen 3D installation; use a clean runner')
folders = json.loads(powershell("@{Programs=[Environment]::GetFolderPath('Programs');Desktop=[Environment]::GetFolderPath('DesktopDirectory')} | ConvertTo-Json -Compress"))
shortcuts = [Path(folders[name]) / 'Kitchen 3D.lnk' for name in ('Programs', 'Desktop')]
if not all(folders.values()) or any(link.exists() for link in shortcuts):
    raise SystemExit('Expected a clean Windows user profile with standard shell folders')

with tempfile.TemporaryDirectory(prefix='kitchen3d-setup-') as temp:
    install = Path(temp) / 'Installed Kitchen 3D'
    uninstaller = install / 'unins000.exe'
    flags = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-']
    try:
        subprocess.run([str(setup), *flags, f'/DIR={install}', '/TASKS=standalone,desktopicon',
                        f'/LOG={output / "install.log"}'], check=True, timeout=600)
        assert registry_value(capabilities, 'ApplicationName') is None
        entry = installed_entry()
        assert entry and entry['DisplayName'] == 'Kitchen 3D', entry
        assert str(uninstaller).lower() in entry['UninstallString'].lower(), entry
        for link in shortcuts:
            assert link.is_file(), link
            target = powershell("(New-Object -ComObject WScript.Shell).CreateShortcut($env:KITCHEN_TEST_LINK).TargetPath",
                                KITCHEN_TEST_LINK=str(link))
            assert Path(target).samefile(install / 'kitchen3d-launcher.exe'), target
        user_file = install / 'user-project.blend'
        user_file.write_text('User-owned file must survive upgrade and uninstall')
        # Omit /DIR on the second run: the stable AppId must recover the previous location.
        subprocess.run([str(setup), *flags, '/TASKS=blendfiles,desktopicon', f'/LOG={output / "upgrade.log"}'], check=True, timeout=600)
        assert user_file.read_text().startswith('User-owned')
        assert registry_value(capabilities, 'ApplicationName') == 'Kitchen 3D'
        assert registry_value(capabilities + r'\FileAssociations', '.blend') == 'Kitchen3D.Setup.Blend'
        assert registry_value(prog_id + r'\shell\open\command') == f'"{install / "kitchen3d-launcher.exe"}" "%1"'
        assert registry_value(r'Software\Classes\.blend\OpenWithProgids', 'Kitchen3D.Setup.Blend') is not None
        assert registry_value(user_choice, 'ProgId') == original_choice
        assert registry_value(r'Software\Classes\.blend') == original_extension
        subprocess.run([sys.executable, str(root / 'tests/python/kitchen3d_launcher_smoke.py'),
                        '--install', str(install)], check=True, timeout=120)
        subprocess.run([sys.executable, str(root / 'tests/python/run_kitchen3d_test.py'),
                        '--blender', str(install / 'kitchen3d.exe'),
                        '--script', str(root / 'tests/python/kitchen3d_package_smoke.py'),
                        '--output', str(output / 'installed-runtime')], check=True, timeout=240)
        subprocess.run([str(uninstaller), *flags, f'/LOG={output / "uninstall.log"}'],
                       check=True, timeout=120)
        assert installed_entry() is None
        assert registry_value(capabilities, 'ApplicationName') is None
        assert registry_value(prog_id) is None
        assert registry_value(r'Software\RegisteredApplications', 'Kitchen3D') is None
        assert registry_value(r'Software\Classes\.blend\OpenWithProgids', 'Kitchen3D.Setup.Blend') is None
        assert registry_value(user_choice, 'ProgId') == original_choice
        assert registry_value(r'Software\Classes\.blend') == original_extension
        assert not (install / 'kitchen3d.exe').exists()
        assert all(not link.exists() for link in shortcuts)
        assert user_file.read_text().startswith('User-owned')
    finally:
        # Only remove the install created by this test, never a pre-existing app.
        entry = installed_entry()
        if uninstaller.exists() and entry and str(uninstaller).lower() in entry['UninstallString'].lower():
            subprocess.run([str(uninstaller), *flags], timeout=120, check=True)
print('PASS: setup, shortcuts, upgrade, installed runtime and uninstall')
