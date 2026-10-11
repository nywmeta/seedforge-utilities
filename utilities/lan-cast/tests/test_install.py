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
HELPER_ASSETS = ("host.py", "file_cast.py", "companion.py")


class InstallerTests(unittest.TestCase):
    def test_mac_opera_gx_opera_and_chrome_use_the_documented_shared_path(self):
        home = Path("/tmp/test-home")
        application = Path("/tmp/test-application")
        expected = home / "Library/Application Support/Google/Chrome/NativeMessagingHosts" / (INSTALL.HOST + ".json")
        for browser in ("opera-gx", "opera", "chrome"):
            with self.subTest(browser=browser):
                self.assertEqual(INSTALL.manifest_path(home, "darwin", browser, application), expected)
        for browser in ("edge", "chromium"):
            self.assertNotEqual(INSTALL.manifest_path(home, "darwin", browser, application), expected)

    def test_mac_shared_registration_retains_all_installed_browser_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            args = argparse.Namespace(extension_id=ID, browser="opera-gx", uninstall=False, dry_run=False)
            browser_ids = (("chrome", "c" * 32), ("opera-gx", ID), ("opera", "p" * 32))
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                for browser, extension_id in browser_ids:
                    args.browser, args.extension_id = browser, extension_id
                    INSTALL.run(args)
                # Installing an already-authorized ID must keep one origin and
                # preserve IDs authorized through the other browser aliases.
                args.browser, args.extension_id = "opera-gx", ID
                INSTALL.run(args)
            application = INSTALL.install_directory(home, "darwin")
            manifest = INSTALL.manifest_path(home, "darwin", "chrome", application)
            value = json.loads(manifest.read_text())
            self.assertEqual(value["allowed_origins"], ["chrome-extension://" + extension_id + "/" for _, extension_id in browser_ids])
            for product in ("com.operasoftware.Opera", "com.operasoftware.OperaGX"):
                self.assertFalse((home / "Library/Application Support" / product / "NativeMessagingHosts" / (INSTALL.HOST + ".json")).exists())

    def test_mac_uninstalling_any_shared_browser_removes_registration_and_explains_impact(self):
        for browser in ("opera-gx", "opera", "chrome"):
            with self.subTest(browser=browser), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                args = argparse.Namespace(extension_id=ID, browser="opera-gx", uninstall=False, dry_run=False)
                with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(io.StringIO()):
                    INSTALL.run(args)
                    args.browser, args.extension_id = "chrome", "c" * 32
                    INSTALL.run(args)
                application = INSTALL.install_directory(home, "darwin")
                manifest = INSTALL.manifest_path(home, "darwin", "chrome", application)
                args.browser, args.uninstall = browser, True
                output = io.StringIO()
                with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(output):
                    INSTALL.run(args)
                self.assertFalse(manifest.exists())
                self.assertTrue((application / "host.py").exists())
                self.assertIn("Opera GX, Opera and Chrome share", output.getvalue())
                self.assertIn("also disconnects", output.getvalue())
                self.assertIn("each remaining browser's extension ID", output.getvalue())

    def test_mac_install_all_deduplicates_shared_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            args = argparse.Namespace(extension_id=ID, browser="all", uninstall=False, dry_run=False)
            output = io.StringIO()
            with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), redirect_stdout(output):
                INSTALL.run(args)
            application = INSTALL.install_directory(home, "darwin")
            registrations = {INSTALL.manifest_path(home, "darwin", browser, application) for browser in INSTALL.BROWSERS}
            self.assertEqual(len(registrations), 3)
            self.assertTrue(all(path.is_file() for path in registrations))
            self.assertEqual(output.getvalue().count("Registered Lan Cast for "), 3)

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
            for name in HELPER_ASSETS:
                target = application / name
                self.assertEqual(target.read_bytes(), (ROOT / "helper" / name).read_bytes())
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
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
            for name in HELPER_ASSETS:
                self.assertEqual((application / name).read_bytes(), (ROOT / "helper" / name).read_bytes())

    def test_missing_or_invalid_helper_asset_cannot_modify_installed_companions(self):
        for asset in HELPER_ASSETS:
            for invalid in (False, True):
                with self.subTest(asset=asset, invalid=invalid), tempfile.TemporaryDirectory() as temporary:
                    temporary = Path(temporary)
                    home, package = temporary / "home", temporary / "package"
                    package.mkdir()
                    for name in HELPER_ASSETS:
                        if name != asset:
                            (package / name).write_text("VALUE = 1\n")
                    if invalid:
                        (package / asset).write_text("def broken(:\n")
                    application = INSTALL.install_directory(home, "darwin")
                    application.mkdir(parents=True)
                    for name in HELPER_ASSETS + ("launch-host",):
                        (application / name).write_text("existing installed " + name)
                    before = {path: path.read_bytes() for path in home.rglob("*") if path.is_file()}
                    args = argparse.Namespace(extension_id=ID, browser="opera-gx", uninstall=False, dry_run=False)
                    with patch.object(INSTALL.Path, "home", return_value=home), patch.object(INSTALL.sys, "platform", "darwin"), patch.object(INSTALL, "__file__", str(package / "install.py")):
                        with self.assertRaisesRegex(ValueError, asset):
                            INSTALL.run(args)
                    after = {path: path.read_bytes() for path in home.rglob("*") if path.is_file()}
                    self.assertEqual(after, before)

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
