#!/usr/bin/env python3
"""Test and reproducibly package LAN Cast. Never publishes or spends money."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
UTILITY = ROOT / 'utilities/lan-cast'
PACKAGE_MEMBERS = tuple(json.loads(Path(__file__).with_name('package-manifest.json').read_text()))
FILES = ('README.md', 'LICENSE', 'PRIVACY.md', 'VALIDATION.md', 'CHANGELOG.md',
         'Install on Mac.command', 'Install on Windows.cmd')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def release_version():
    manifest = json.loads((UTILITY / 'extension/manifest.json').read_text())
    version = manifest['version']
    require(bool(re.fullmatch(r'\d+\.\d+\.\d+', version)), 'Invalid release version')
    tree = ast.parse((UTILITY / 'helper/host.py').read_text())
    versions = [ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == 'VERSION' for target in node.targets)]
    require(versions == [version], 'Helper and extension versions differ')
    require(set(manifest['permissions']) == {'activeTab', 'scripting', 'nativeMessaging', 'storage'},
            'Review changed permissions before release')
    require(not manifest.get('host_permissions'), 'Review persistent website access before release')
    for name in FILES:
        require((UTILITY / name).is_file(), 'Missing release document: ' + name)
    for name in list(manifest['icons'].values()) + [manifest['background']['service_worker'],
                                                   manifest['action']['default_popup']]:
        require((UTILITY / 'extension' / name).is_file(), 'Missing extension asset: ' + name)
    return version


def validate_funding():
    data = json.loads((ROOT / 'funding.json').read_text())
    require(isinstance(data.get('enabled'), bool), 'Funding enabled must be a boolean')
    if data['enabled']:
        require(isinstance(data.get('url'), str) and bool(re.fullmatch(
            r'https://(?:www\.)?paypal\.me/[A-Za-z0-9_-]+/?', data['url'])),
            'Only a confirmed PayPal.Me recipient URL is configured for this pipeline')
        require(all(isinstance(data.get(key), str) and data[key].strip()
                    for key in ('recipient', 'owner_confirmed_at', 'public_page_verified_at')),
                'Funding requires a recipient, owner confirmation and live page verification')
    else:
        require(not (ROOT / '.github/FUNDING.yml').exists(), 'Remove disabled funding links before packaging')


def checked_files():
    require(not UTILITY.is_symlink(), 'Refusing a symlinked utility directory')
    observed = set()
    for path in UTILITY.rglob('*'):
        if '__pycache__' in path.parts or path.name == '.DS_Store':
            continue
        require(not path.is_symlink(), 'Refusing symlink: ' + path.relative_to(UTILITY).as_posix())
        if path.is_file():
            observed.add(path.relative_to(UTILITY).as_posix())
    require(observed == set(PACKAGE_MEMBERS),
            'Package file list changed; review package-manifest.json. Unexpected: %s; missing: %s' %
            (sorted(observed - set(PACKAGE_MEMBERS)), sorted(set(PACKAGE_MEMBERS) - observed)))
    files = [UTILITY / name for name in sorted(PACKAGE_MEMBERS)]
    for file in files:
        require(file.resolve() == file.absolute(), 'Refusing symlinked release path: ' + file.name)
    return files


def run_checks(node):
    require(sys.version_info >= (3, 9), 'Python 3.9+ is required')
    resolved = shutil.which(node)
    require(bool(resolved), 'Node is unavailable; pass --node with its executable path')
    major = int(subprocess.check_output([resolved, '--version'], text=True).strip().lstrip('v').split('.')[0])
    require(major >= 22, 'Node 22+ is required for release checks')
    subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                   cwd=UTILITY, check=True)
    subprocess.run([resolved, '--test', *[str(path.relative_to(UTILITY))
                    for path in sorted((UTILITY / 'tests').glob('*.test.mjs'))]], cwd=UTILITY, check=True)
    subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                   cwd=ROOT, check=True)
    for script in sorted((UTILITY / 'extension').glob('*.js')):
        subprocess.run([resolved, '--check', str(script)], check=True)
    if sys.platform != 'win32':
        subprocess.run(['bash', '-n', str(UTILITY / 'Install on Mac.command')], check=True)


def package(version):
    files = checked_files()
    for file in files:
        require(not file.is_symlink(), 'Refusing symlink: ' + str(file))
        require(file.suffix.lower() not in ('.pem', '.key'), 'Refusing private-key file')
        if file.suffix.lower() in ('.md', '.py', '.js', '.mjs', '.html', '.css', '.json', '.cmd', '.command'):
            content = file.read_text(encoding='utf-8')
            require(str(Path.home()) + '/' not in content and str(ROOT) not in content,
                    'Remove user-specific absolute paths from ' + file.name)
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    archive = destination / ('lan-cast-v' + version + '-rc.zip')
    temporary = destination / (archive.name + '.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for file in files:
            info = zipfile.ZipInfo('lan-cast/' + file.relative_to(UTILITY).as_posix(), (2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o755 if file.suffix == '.command' else 0o644
            info.external_attr = (0o100000 | mode) << 16
            zipped.writestr(info, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(temporary) as zipped:
        require(zipped.testzip() is None, 'ZIP integrity failed')
        require(len(zipped.namelist()) == len(files), 'ZIP file count mismatch')
    temporary.replace(archive)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / (archive.name + '.sha256')).write_text(checksum + '  ' + archive.name + '\n')
    print('Checked release candidate: ' + archive.name)
    print('Files: %s; SHA-256: %s' % (len(files), checksum))
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', default='node', help='Node 22+ executable or absolute path')
    args = parser.parse_args()
    try:
        version = release_version()
        validate_funding()
        checked_files()
        run_checks(args.node)
        package(version)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Release gate failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
