#!/usr/bin/env python3
"""Verify a public GitHub release against a checked local ZIP, without authentication."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD = 5 * 1024 * 1024
PACKAGE_MEMBERS = tuple(json.loads(Path(__file__).with_name('package-manifest.json').read_text()))


def read_url(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Seedforge-publication-check',
                                                  'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError('Public response exceeded size limit')
    return data


def read_json(url):
    return json.loads(read_url(url))


def blob_sha(payload):
    return hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='Public owner/repository')
    parser.add_argument('--tag', required=True)
    parser.add_argument('--archive', required=True, type=Path, help='ZIP made by the release gate')
    args = parser.parse_args()
    try:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
            raise ValueError('Use owner/repository')
        if not re.fullmatch(r'lan-cast-v\d+\.\d+\.\d+-rc', args.tag):
            raise ValueError('Use a LAN Cast release-candidate tag')
        archive = args.archive.resolve()
        expected = hashlib.sha256(archive.read_bytes()).hexdigest()
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            if len(names) != len(set(names)) or any(not name.startswith('lan-cast/')
                    or '..' in Path(name).parts or name.endswith('/') for name in names):
                raise ValueError('Unsafe or duplicate release ZIP members')
            if set(names) != {'lan-cast/' + name for name in PACKAGE_MEMBERS}:
                raise ValueError('Release ZIP does not match the approved package file list')
            if sum(info.file_size for info in zipped.infolist()) > MAX_DOWNLOAD:
                raise ValueError('Release ZIP contents exceeded size limit')
            members = {name: zipped.read(name) for name in names}
        version = json.loads(members['lan-cast/extension/manifest.json'])['version']
        if args.tag != 'lan-cast-v' + version + '-rc' or archive.name != args.tag + '.zip':
            raise ValueError('Tag, ZIP name and packaged version must match')
        base = 'https://api.github.com/repos/' + args.repo
        repo = read_json(base)
        if repo.get('private') is not False or repo.get('archived'):
            raise ValueError('Repository is not an active public repository')
        release = read_json(base + '/releases/tags/' + args.tag)
        if release.get('draft') or not release.get('prerelease'):
            raise ValueError('Expected a published, clearly marked prerelease')
        ref = read_json(base + '/git/ref/tags/' + args.tag)['object']
        for unused in range(4):
            if ref['type'] == 'commit':
                break
            if ref['type'] != 'tag':
                raise ValueError('Unexpected tag object')
            ref = read_json(base + '/git/tags/' + ref['sha'])['object']
        if ref['type'] != 'commit':
            raise ValueError('Could not resolve tag to a commit')
        sha = ref['sha']
        # Verify every packaged source/asset, not merely that docs exist.
        tree = read_json(base + '/git/trees/' + sha + '?recursive=1')
        if tree.get('truncated'):
            raise ValueError('Public source tree is incomplete')
        source = {entry['path']: entry for entry in tree['tree']}
        for name, payload in members.items():
            path = 'utilities/' + name
            entry = source.get(path, {})
            if entry.get('type') != 'blob' or entry.get('mode') not in ('100644', '100755') \
                    or entry.get('sha') != blob_sha(payload):
                raise ValueError('Public source differs from checked package: ' + path)
        if source.get('LICENSE', {}).get('sha') != blob_sha(members['lan-cast/LICENSE']):
            raise ValueError('Repository license differs from packaged license')
        assets = {asset['name']: asset for asset in release.get('assets', [])}
        if archive.name not in assets or archive.name + '.sha256' not in assets:
            raise ValueError('Release ZIP/checksum assets missing')
        for name in (archive.name, archive.name + '.sha256'):
            url = assets[name]['browser_download_url']
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != 'github.com' or not parsed.path.startswith(
                    '/' + args.repo + '/releases/download/' + args.tag + '/'):
                raise ValueError('Unexpected asset URL')
            payload = read_url(url)
            if name == archive.name:
                if hashlib.sha256(payload).hexdigest() != expected:
                    raise ValueError('Downloaded release ZIP differs from checked local ZIP')
            elif payload.decode().strip() != expected + '  ' + archive.name:
                raise ValueError('Published checksum differs from checked ZIP')
        record = {'state': 'published', 'repository_url': repo['html_url'], 'commit': sha,
                  'tag': args.tag, 'release_url': release['html_url'],
                  'verified_at': datetime.now(timezone.utc).isoformat(), 'sha256': expected}
        (ROOT / 'publication.json').write_text(json.dumps(record, indent=2) + '\n')
        print('Verified public source and release: ' + record['release_url'])
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print('Publication remains unverified: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
