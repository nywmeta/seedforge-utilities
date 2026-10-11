"""Exercise installation and framing without changing real browser registrations."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lan_cast_install", ROOT / "helper/install.py")
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)
ID = "abcdefghijklmnopabcdefghijklmnop"


class InstallerTests(unittest.TestCase):
    def test_opera_gx_and_opera_register_in_their_distinct_mac_profiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            args = argparse.Namespace(extension_id=ID, browser="opera-gx", uninstall=False, dry_run=False)
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                INSTALL.run(args)
                args.browser = "opera"
                INSTALL.run(args)
            application = INSTALL.install_directory(home, "darwin")
            gx = home / "Library/Application Support/com.operasoftware.OperaGX/NativeMessagingHosts" / (INSTALL.HOST + ".json")
            opera = home / "Library/Application Support/com.operasoftware.Opera/NativeMessagingHosts" / (INSTALL.HOST + ".json")
            self.assertEqual(INSTALL.manifest_path(home, "darwin", "opera-gx", application), gx)
            self.assertEqual(INSTALL.manifest_path(home, "darwin", "opera", application), opera)
            self.assertTrue(gx.exists() and opera.exists())
            self.assertFalse(INSTALL.manifest_path(home, "darwin", "chrome", application).exists())
            args.browser = "opera-gx"
            args.uninstall = True
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                INSTALL.run(args)
            self.assertFalse(gx.exists())
            self.assertTrue(opera.exists())

    def test_windows_opera_shares_chrome_manifest_and_registry(self):
        home = Path("/tmp/test-home")
        application = Path("/tmp/test-application")
        chrome = INSTALL.manifest_path(home, "win32", "chrome", application)
        for browser in ("opera", "opera-gx"):
            self.assertEqual(INSTALL.manifest_path(home, "win32", browser, application), chrome)
            self.assertEqual(INSTALL.REGISTRY[browser], INSTALL.REGISTRY["chrome"])

    def test_opera_gx_command_line_preview_accepts_target_and_keeps_disk_unchanged(self):
        process = subprocess.run([sys.executable, "-B", str(ROOT / "helper/install.py"),
                                  "--extension-id", ID, "--browser", "opera-gx", "--dry-run"],
                                 capture_output=True, text=True, timeout=5)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Preview only", process.stdout)
        self.assertIn("Register opera-gx", process.stdout)

    def test_install_launcher_can_exchange_native_ping_and_unregister(self):
        with tempfile.TemporaryDirectory(prefix="Lan Cast spaces ") as temporary:
            home = Path(temporary)
            args = argparse.Namespace(extension_id=ID, browser="chrome", uninstall=False, dry_run=False)
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                INSTALL.run(args)
            application = INSTALL.install_directory(home, "darwin")
            manifest = INSTALL.manifest_path(home, "darwin", "chrome", application)
            registration = json.loads(manifest.read_text())
            self.assertEqual(registration["allowed_origins"], ["chrome-extension://" + ID + "/"])
            self.assertTrue(Path(registration["path"]).is_absolute())
            message = json.dumps({"action": "ping"}).encode()
            process = subprocess.run([registration["path"], "chrome-extension://" + ID + "/"],
                                     input=struct.pack("=I", len(message)) + message,
                                     capture_output=True, timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr.decode())
            size = struct.unpack("=I", process.stdout[:4])[0]
            self.assertEqual(len(process.stdout[4:]), size)
            self.assertTrue(json.loads(process.stdout[4:])["ok"])
            args.uninstall = True
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                INSTALL.run(args)
            self.assertFalse(manifest.exists())
            self.assertTrue((application / "host.py").exists())

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            args = argparse.Namespace(extension_id=ID, browser="all", uninstall=False, dry_run=True)
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                INSTALL.run(args)
            self.assertEqual(list(home.iterdir()), [])

    def test_invalid_id_and_unrelated_manifest_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            args = argparse.Namespace(extension_id="not-an-id", browser="chrome", uninstall=False, dry_run=False)
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"):
                with self.assertRaises(ValueError):
                    INSTALL.run(args)
                self.assertEqual(list(home.iterdir()), [])
                application = INSTALL.install_directory(home, "darwin")
                manifest = INSTALL.manifest_path(home, "darwin", "chrome", application)
                manifest.parent.mkdir(parents=True)
                manifest.write_text('{"name":"unrelated"}')
                args.extension_id = ID
                with self.assertRaises(ValueError):
                    INSTALL.run(args)
                self.assertEqual(json.loads(manifest.read_text())["name"], "unrelated")

    def test_registration_retains_valid_previously_allowed_extension(self):
        second = "p" * 32
        value = INSTALL.make_manifest(Path("/tmp/launcher"), ID,
                                      {"name": INSTALL.HOST, "allowed_origins": ["chrome-extension://" + second + "/", "*"]})
        self.assertEqual(value["allowed_origins"], ["chrome-extension://" + second + "/", "chrome-extension://" + ID + "/"])

    def test_malformed_previous_origins_fail_without_replacing_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            application = INSTALL.install_directory(home, "darwin")
            manifest = INSTALL.manifest_path(home, "darwin", "chrome", application)
            manifest.parent.mkdir(parents=True)
            args = argparse.Namespace(extension_id=ID, browser="chrome", uninstall=False, dry_run=False)
            for origins in (None, "chrome-extension://" + ID + "/", {}):
                with self.subTest(origins=origins):
                    original = json.dumps({"name": INSTALL.HOST, "allowed_origins": origins})
                    manifest.write_text(original)
                    with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"):
                        with self.assertRaisesRegex(ValueError, "allowed_origins"):
                            INSTALL.run(args)
                    self.assertEqual(manifest.read_text(), original)
                    self.assertFalse(application.exists())

    def test_windows_batch_has_absolute_quoted_python_and_host(self):
        text = INSTALL.launcher_text(Path("C:/Program Files/Python/python.exe"),
                                     Path("C:/Users/Example/Lan Cast/host.py"), "win32")
        self.assertTrue(text.startswith("@echo off\r\n"))
        self.assertIn('"C:/Program Files/Python/python.exe" -u "C:/Users/Example/Lan Cast/host.py" %*', text)
        with self.assertRaises(ValueError):
            INSTALL.launcher_text(Path("C:/%APP%/python.exe"), Path("C:/host.py"), "win32")


if __name__ == "__main__":
    unittest.main()
