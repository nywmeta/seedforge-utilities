"""Offline checks for safe and reproducible utility packaging."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('release_under_test',
                                                    REPOSITORY_ROOT / 'scripts/release.py')
        self.release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.release)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.utility = self.root / 'utilities/lan-cast'
        self.utility.mkdir(parents=True)
        for name in self.release.PACKAGE_MEMBERS:
            destination = self.utility / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPOSITORY_ROOT / 'utilities/lan-cast' / name, destination)
        shutil.copy2(REPOSITORY_ROOT / 'funding.json', self.root / 'funding.json')
        self.release.ROOT = self.root
        self.release.UTILITY = self.utility
        self.version = self.release.release_version()

    def assert_gate_rejected_without_running_checks(self):
        errors = io.StringIO()
        with patch.object(self.release, 'run_checks') as checks, \
                patch.object(sys, 'argv', ['release.py']), contextlib.redirect_stderr(errors):
            status = self.release.main()
        self.assertEqual(status, 1)
        checks.assert_not_called()
        self.assertFalse((self.root / 'dist').exists())
        return errors.getvalue()

    def test_hidden_env_is_rejected_before_checks_and_before_zip_writing(self):
        (self.utility / 'helper/.env').write_text('FAKE_REVIEW_TOKEN=example-only-not-a-secret\n')
        self.assertIn('.env', self.assert_gate_rejected_without_running_checks())
        with self.assertRaisesRegex(ValueError, r'\.env'):
            self.release.package(self.version)
        self.assertFalse((self.root / 'dist').exists())

    def test_external_symlinked_directory_is_rejected_before_checks_and_zip_writing(self):
        external = self.root / 'outside-utility'
        (self.utility / 'extension').rename(external)
        (external / 'private-notes.txt').write_text('review fixture only\n')
        try:
            (self.utility / 'extension').symlink_to(external, target_is_directory=True)
        except OSError as error:
            self.skipTest('This environment cannot create a directory symlink: ' + str(error))
        self.assertIn('symlink', self.assert_gate_rejected_without_running_checks())
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.release.package(self.version)
        self.assertFalse((self.root / 'dist').exists())

    def test_valid_package_is_reproducible_and_preserves_installer_executable_mode(self):
        with contextlib.redirect_stdout(io.StringIO()):
            archive = self.release.package(self.version)
        first = archive.read_bytes()
        first_checksum = archive.with_name(archive.name + '.sha256').read_text()
        self.assertEqual(first_checksum, hashlib.sha256(first).hexdigest() + '  ' + archive.name + '\n')
        with zipfile.ZipFile(archive) as zipped:
            expected_names = {'lan-cast/' + name for name in self.release.PACKAGE_MEMBERS}
            self.assertEqual(set(zipped.namelist()), expected_names)
            self.assertIsNone(zipped.testzip())
            for member in zipped.infolist():
                expected_mode = 0o755 if member.filename.endswith('.command') else 0o644
                self.assertEqual((member.external_attr >> 16) & 0o777, expected_mode)
                self.assertEqual((member.external_attr >> 16) & 0o170000, 0o100000)
                self.assertEqual(member.create_system, 3)
                self.assertEqual(member.date_time, (2026, 1, 1, 0, 0, 0))
                source = self.utility / member.filename.removeprefix('lan-cast/')
                self.assertEqual(zipped.read(member.filename), source.read_bytes())
        # File-system modes/timestamps must not change distributable bytes.
        for file in self.release.checked_files():
            file.chmod(0o600)
            file.touch()
        with contextlib.redirect_stdout(io.StringIO()):
            self.release.package(self.version)
        self.assertEqual(archive.read_bytes(), first)
        self.assertEqual(archive.with_name(archive.name + '.sha256').read_text(), first_checksum)


if __name__ == '__main__':
    unittest.main()
