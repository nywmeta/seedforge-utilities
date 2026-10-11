#!/usr/bin/env python3
"""Register the Lan Cast native messaging host for this user (no administrator needed)."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import sys

HOST = "com.lancast.bridge"
HELPER_FILES = ("host.py", "file_cast.py", "companion.py")
BROWSERS = ("opera-gx", "opera", "chrome", "edge", "chromium")
SHARED_CHROME_HOST = {"opera-gx", "opera"}
REGISTRY = {
    "chrome": r"Software\Google\Chrome\NativeMessagingHosts" + "\\" + HOST,
    "edge": r"Software\Microsoft\Edge\NativeMessagingHosts" + "\\" + HOST,
    "chromium": r"Software\Chromium\NativeMessagingHosts" + "\\" + HOST,
}
REGISTRY.update({browser: REGISTRY["chrome"] for browser in SHARED_CHROME_HOST})


def install_directory(home, platform):
    if platform == "darwin":
        return home / "Library/Application Support/Lan Cast"
    if platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local"))) / "Lan Cast"
    return home / ".local/share/lan-cast"


def manifest_path(home, platform, browser, application):
    if platform == "darwin":
        product = {"chrome": "Google/Chrome", "edge": "Microsoft Edge", "chromium": "Chromium",
                   "opera": "Google/Chrome", "opera-gx": "Google/Chrome"}[browser]
        # Opera's documented macOS native-host lookup uses Chrome's directory,
        # shared by Opera GX, Opera and Chrome. Retain their allowed IDs below.
        return home / "Library/Application Support" / product / "NativeMessagingHosts" / (HOST + ".json")
    if platform == "win32":
        # Opera's documented Windows native-host registration uses Chrome's
        # registry key. Share its manifest too, preserving allowed extension IDs.
        product = "chrome" if browser in SHARED_CHROME_HOST else browser
        return application / (product + "-" + HOST + ".json")
    product = {"chrome": "google-chrome", "edge": "microsoft-edge", "chromium": "chromium",
               "opera": "opera", "opera-gx": "opera-gx"}[browser]
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    return config / product / "NativeMessagingHosts" / (HOST + ".json")


def make_manifest(launcher, extension_id, previous=None):
    if not re.fullmatch(r"[a-p]{32}", extension_id):
        raise ValueError("Extension ID must be the 32 lowercase letters shown on the browser's extensions page.")
    origins = []
    if previous and previous.get("name") == HOST:
        previous_origins = previous.get("allowed_origins", [])
        if not isinstance(previous_origins, list):
            raise ValueError("Existing host manifest has an invalid allowed_origins list.")
        origins = [item for item in previous_origins
                   if isinstance(item, str) and re.fullmatch(r"chrome-extension://[a-p]{32}/", item)]
    origin = "chrome-extension://" + extension_id + "/"
    return {
        "name": HOST,
        "description": "Lan Cast UPnP video bridge",
        "path": str(launcher.resolve()),
        "type": "stdio",
        "allowed_origins": list(dict.fromkeys(origins + [origin])),
    }


def launcher_text(python, host, platform):
    if platform == "win32":
        # Native messaging batches are supported by Chromium's official sample.
        if any(char in str(python) + str(host) for char in '%\r\n"'):
            raise ValueError("Windows installation paths cannot contain %, quotes, or line breaks.")
        return '@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\n"' + str(python) + '" -u "' + str(host) + '" %*\r\n'
    return "#!/bin/sh\nexec " + shlex.quote(str(python)) + " -u " + shlex.quote(str(host)) + ' "$@"\n'


def read_previous(path):
    if not path.exists():
        return None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Existing host manifest is unreadable: " + str(path)) from exc
    if not isinstance(previous, dict) or previous.get("name") != HOST:
        raise ValueError("Refusing to replace an unrelated manifest: " + str(path))
    return previous


def register_windows(browser, path):
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REGISTRY[browser], 0,
                            winreg.KEY_WRITE | winreg.KEY_WOW64_32KEY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(path.resolve()))


def unregister_windows(browser, path):
    import winreg
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY[browser], 0,
                                winreg.KEY_READ | view) as key:
                registered = winreg.QueryValueEx(key, "")[0]
            if Path(registered).resolve() != path.resolve():
                raise ValueError("Registry points to a different installation; leaving it untouched: " + registered)
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, REGISTRY[browser], view, 0)
        except FileNotFoundError:
            pass


def run(args):
    if sys.version_info < (3, 9):
        raise ValueError("Use Python 3.9 or newer.")
    home = Path.home()
    application = install_directory(home, sys.platform)
    browsers = BROWSERS if args.browser == "all" else (args.browser,)
    launcher = application / ("launch-host.cmd" if sys.platform == "win32" else "launch-host")
    host = application / "host.py"
    python = Path(sys.executable).resolve()

    if not args.uninstall and not args.extension_id:
        raise ValueError("Supply --extension-id with the ID from opera://extensions, chrome://extensions, or edge://extensions.")
    helper_files = []
    launcher_bytes = None
    if not args.uninstall:
        # Read and validate every required module and launcher before touching
        # an installed helper, including when repairing an older installation.
        launcher_bytes = launcher_text(python, host, sys.platform).encode("utf-8")
        for name in HELPER_FILES:
            source = Path(__file__).with_name(name)
            if not source.is_file():
                raise ValueError(name + " is missing. Keep install.py beside all helper files in the downloaded package.")
            content = source.read_bytes()
            try:
                compile(content, name, "exec")
            except (SyntaxError, ValueError) as exc:
                raise ValueError(name + " is not a valid Python helper file.") from exc
            helper_files.append((application / name, content))

    manifests = []
    planned_paths = set()
    for browser in browsers:
        path = manifest_path(home, sys.platform, browser, application)
        if path in planned_paths:
            continue
        planned_paths.add(path)
        previous = read_previous(path)
        value = None if args.uninstall else make_manifest(launcher, args.extension_id, previous)
        manifests.append((browser, path, value))

    if (args.uninstall and sys.platform in ("darwin", "win32")
            and any(browser in SHARED_CHROME_HOST or browser == "chrome" for browser in browsers)):
        print("Opera GX, Opera and Chrome share this native-host registration. Unregistering it also disconnects Lan Cast in those browsers.")
        print("Re-run the installer with each remaining browser's extension ID to restore access.")

    if args.dry_run:
        print("Preview only; no files or settings were changed.")
        print("Helper folder: " + str(application))
        for browser, path, value in manifests:
            print(("Remove " if args.uninstall else "Register ") + browser + ": " + str(path))
            if value:
                print(json.dumps(value, indent=2))
        return

    if not args.uninstall:
        application.mkdir(parents=True, exist_ok=True)
        for target, content in helper_files:
            target.write_bytes(content)
            if sys.platform != "win32":
                target.chmod(0o600)
        launcher.write_bytes(launcher_bytes)
        if sys.platform != "win32":
            launcher.chmod(0o700)

    for browser, path, value in manifests:
        if args.uninstall:
            if sys.platform == "win32":
                unregister_windows(browser, path)
            if path.exists():
                path.unlink()
            print("Unregistered Lan Cast for " + browser + ".")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            if sys.platform == "win32":
                register_windows(browser, path)
            else:
                path.chmod(0o600)
            print("Registered Lan Cast for " + browser + ".")
    if args.uninstall:
        print("Helper files remain in " + str(application) + "; other browser registrations may use them.")
    else:
        print("Reload the extension, then open Lan Cast. The helper runs only when the extension requests it.")
        print("Python used: " + str(python))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-id", help="32-letter extension ID from your browser")
    parser.add_argument("--browser", choices=BROWSERS + ("all",), default="opera-gx")
    parser.add_argument("--uninstall", action="store_true", help="Remove this user's browser registration")
    parser.add_argument("--dry-run", action="store_true", help="Preview paths without changing anything")
    parser.add_argument("--interactive", action="store_true", help="Ask for browser and extension ID")
    args = parser.parse_args()
    try:
        if args.interactive:
            print("Lan Cast helper setup — installs for your user account only.")
            print("First load the extension folder using Load unpacked on your browser's extensions page.")
            browser = input("Browser: opera-gx, opera, chrome, edge, or chromium [opera-gx]: ").strip().lower() or "opera-gx"
            if browser not in BROWSERS:
                raise ValueError("Choose opera-gx, opera, chrome, edge, or chromium.")
            args.browser = browser
            args.extension_id = input("Paste the 32-letter extension ID: ").strip()
        run(args)
    except (OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
        print("Installation error: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
