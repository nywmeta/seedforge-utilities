"""Offline release-verification regressions; never contact GitHub or publish."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
UTILITY = REPOSITORY_ROOT / 'utilities/lan-cast'


def git_blob_sha(payload):
    return hashlib.sha1(b'blob ' + str(len(payload)).encode('ascii') + b'\0' + payload).hexdigest()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('publication_under_test',
                                                    REPOSITORY_ROOT / 'scripts/verify_publication.py')
        self.verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.verifier)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.verifier.ROOT = self.root
        self.original_record = b'{"state":"prepared","verified_at":null}\n'
        self.record = self.root / 'publication.json'
        self.record.write_bytes(self.original_record)
        self.version = json.loads((UTILITY / 'extension/manifest.json').read_text())['version']
        self.tag = 'lan-cast-v' + self.version + '-rc'
        self.archive = self.root / (self.tag + '.zip')
        self.members = {
            'lan-cast/' + file.relative_to(UTILITY).as_posix(): file.read_bytes()
            for file in UTILITY.rglob('*')
            if file.is_file() and '__pycache__' not in file.parts and file.suffix not in ('.pyc', '.pyo')
        }
        self.build_archive()
        self.repo_name = 'fixture/seedforge-utilities'
        self.base = 'https://api.github.com/repos/' + self.repo_name
        self.repo_url = 'https://github.com/' + self.repo_name
        self.commit = 'a' * 40
        self.ref = {'object': {'type': 'commit', 'sha': self.commit}}
        self.repo = {'private': False, 'archived': False, 'html_url': self.repo_url}
        self.release = {
            'draft': False, 'prerelease': True, 'tag_name': self.tag,
            'html_url': self.repo_url + '/releases/tag/' + self.tag,
            'assets': [{'name': name, 'state': 'uploaded',
                        'browser_download_url': self.repo_url + '/releases/download/' + self.tag + '/' + name}
                       for name in (self.archive.name, self.archive.name + '.sha256')],
        }
        self.tree = {'truncated': False, 'tree': [
            {'path': 'LICENSE', 'type': 'blob', 'mode': '100644',
             'sha': git_blob_sha((REPOSITORY_ROOT / 'LICENSE').read_bytes())},
            *[{'path': 'utilities/' + member, 'type': 'blob',
               'mode': '100755' if member.endswith('.command') else '100644',
               'sha': git_blob_sha(payload)} for member, payload in self.members.items()],
        ]}
        self.json_requests = []
        self.download_requests = []

    def build_archive(self, extra_members=()):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for member, payload in [*self.members.items(), *extra_members]:
                archive.writestr(member, payload)
        self.zip_payload = self.archive.read_bytes()
        self.digest = hashlib.sha256(self.zip_payload).hexdigest()
        self.checksum_payload = (self.digest + '  ' + self.archive.name + '\n').encode('ascii')

    def read_json(self, url):
        self.json_requests.append(url)
        if url == self.base:
            return copy.deepcopy(self.repo)
        if url == self.base + '/releases/tags/' + self.tag:
            return copy.deepcopy(self.release)
        if url == self.base + '/git/ref/tags/' + self.tag:
            return copy.deepcopy(self.ref)
        if url == self.base + '/git/trees/' + self.commit + '?recursive=1':
            return copy.deepcopy(self.tree)
        if url == self.base + '/git/tags/' + 'b' * 40:
            return {'object': {'type': 'commit', 'sha': self.commit}}
        raise AssertionError('Unexpected public API request: ' + url)

    def read_url(self, url):
        self.download_requests.append(url)
        prefix = self.repo_url + '/releases/download/' + self.tag + '/'
        if url == prefix + self.archive.name:
            return self.zip_payload
        if url == prefix + self.archive.name + '.sha256':
            return self.checksum_payload
        raise AssertionError('Unexpected download: ' + url)

    def verify(self, tag=None):
        output, errors = io.StringIO(), io.StringIO()
        arguments = ['verify_publication.py', '--repo', self.repo_name,
                     '--tag', tag or self.tag, '--archive', str(self.archive)]
        with patch.object(self.verifier, 'read_json', side_effect=self.read_json), \
                patch.object(self.verifier, 'read_url', side_effect=self.read_url), \
                patch.object(sys, 'argv', arguments), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = self.verifier.main()
        return result, output.getvalue(), errors.getvalue()

    def assert_rejected(self, tag=None):
        result, output, errors = self.verify(tag)
        self.assertEqual(result, 1, (output, errors))
        self.assertEqual(self.record.read_bytes(), self.original_record)
        self.assertTrue(errors)

    def test_matching_public_source_and_downloads_record_publication(self):
        result, output, errors = self.verify()
        self.assertEqual(result, 0, errors)
        record = json.loads(self.record.read_text())
        self.assertEqual(record['state'], 'published')
        self.assertEqual(record['commit'], self.commit)
        self.assertEqual(record['tag'], self.tag)
        self.assertEqual(record['sha256'], self.digest)
        self.assertEqual(record['release_url'], self.release['html_url'])
        self.assertTrue(record['verified_at'])
        self.assertTrue(any('/git/trees/' in url for url in self.json_requests))
        self.assertEqual(len(self.download_requests), 2)

    def test_annotated_tag_is_peeled_to_the_release_commit(self):
        self.ref = {'object': {'type': 'tag', 'sha': 'b' * 40}}
        result, output, errors = self.verify()
        self.assertEqual(result, 0, errors)
        self.assertEqual(json.loads(self.record.read_text())['commit'], self.commit)

    def test_source_code_missing_from_public_commit_rejects_publication(self):
        for path in ('helper/host.py', 'helper/install.py', 'extension/background.js'):
            with self.subTest(path=path):
                original = self.tree['tree']
                self.tree['tree'] = [entry for entry in original
                                     if entry['path'] != 'utilities/lan-cast/' + path]
                self.assert_rejected()
                self.tree['tree'] = original

    def test_source_code_different_from_checked_zip_rejects_publication(self):
        entry = next(entry for entry in self.tree['tree']
                     if entry['path'] == 'utilities/lan-cast/helper/host.py')
        entry['sha'] = '0' * 40
        self.assert_rejected()

    def test_essential_code_missing_from_archive_rejects_publication(self):
        # The public tree may still contain the file; a broken ZIP is insufficient.
        for path in ('helper/host.py', 'helper/install.py', 'extension/background.js'):
            with self.subTest(path=path):
                member = 'lan-cast/' + path
                original = self.members.pop(member)
                self.build_archive()
                self.assert_rejected()
                self.members[member] = original

    def test_tag_version_different_from_archive_rejects_publication(self):
        self.assert_rejected(tag='lan-cast-v99.99.99-rc')

    def test_archive_manifest_version_different_from_tag_rejects_publication(self):
        manifest = json.loads(self.members['lan-cast/extension/manifest.json'])
        manifest['version'] = '99.99.99'
        self.members['lan-cast/extension/manifest.json'] = json.dumps(manifest).encode('utf-8')
        self.build_archive()
        self.assert_rejected()

    def test_missing_zip_or_checksum_asset_rejects_publication(self):
        for missing in (self.archive.name, self.archive.name + '.sha256'):
            with self.subTest(missing=missing):
                original = self.release['assets']
                self.release['assets'] = [asset for asset in original if asset['name'] != missing]
                self.assert_rejected()
                self.release['assets'] = original

    def test_download_different_from_checked_zip_rejects_publication(self):
        self.zip_payload += b'changed download'
        self.assert_rejected()

    def test_published_checksum_different_from_checked_zip_rejects_publication(self):
        self.checksum_payload = ('0' * 64 + '  ' + self.archive.name + '\n').encode('ascii')
        self.assert_rejected()

    def test_truncated_source_tree_cannot_confirm_publication(self):
        self.tree['truncated'] = True
        self.assert_rejected()

    def test_source_symlink_cannot_confirm_packaged_regular_file(self):
        entry = next(entry for entry in self.tree['tree']
                     if entry['path'] == 'utilities/lan-cast/helper/host.py')
        entry['mode'] = '120000'
        self.assert_rejected()

    def test_non_zip_cannot_be_claimed_as_a_checked_release(self):
        self.archive.write_bytes(b'not a release ZIP')
        self.assert_rejected()

    def test_unsafe_zip_member_rejects_publication(self):
        self.build_archive(extra_members=[('lan-cast/../outside.txt', b'outside')])
        self.assert_rejected()

    def test_duplicate_zip_member_rejects_publication(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.build_archive(extra_members=[('lan-cast/extension/manifest.json',
                                               self.members['lan-cast/extension/manifest.json'])])
        self.assert_rejected()


if __name__ == '__main__':
    unittest.main()
