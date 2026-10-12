"""Launch or reuse LAN Cast's local file interface without sharing native stdout."""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import webbrowser

VERSION = "1.2.1"
START_TIMEOUT = 8.0


def interface_parts(url):
    if not isinstance(url, str) or len(url) > 300:
        raise ValueError("Invalid local interface address.")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or
            parsed.username is not None or parsed.password is not None or
            not parsed.port or parsed.query or parsed.fragment or
            not re.fullmatch(r"/[A-Za-z0-9_-]{32,128}/", parsed.path) or
            parsed.netloc != "127.0.0.1:" + str(parsed.port)):
        raise ValueError("Invalid local interface address.")
    return parsed


def private_directory():
    identity = str(os.getuid()) if hasattr(os, "getuid") else "user"
    directory = Path(tempfile.gettempdir()) / ("lan-cast-files-" + identity)
    directory.mkdir(mode=0o700, exist_ok=True)
    metadata = directory.lstat()
    if (not stat.S_ISDIR(metadata.st_mode) or
            (hasattr(os, "getuid") and metadata.st_uid != os.getuid()) or
            (os.name != "nt" and metadata.st_mode & 0o077)):
        raise ValueError("The local interface folder is not private. Remove only your old LAN Cast temporary folder and try again.")
    return directory


def read_info(path):
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 4096 or
            (hasattr(os, "getuid") and metadata.st_uid != os.getuid()) or
            (os.name != "nt" and metadata.st_mode & 0o077)):
        raise ValueError("The local interface record is not private.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != VERSION:
        raise ValueError("The local interface needs to be reopened after updating LAN Cast.")
    pid = value.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
        raise ValueError("Invalid local interface process.")
    interface_parts(value.get("url"))
    return value


def healthy(value):
    connection = None
    try:
        parsed = interface_parts(value.get("url"))
        connection = http.client.HTTPConnection("127.0.0.1", parsed.port, timeout=0.6)
        connection.request("GET", parsed.path + "health", headers={"Connection": "close"})
        response = connection.getresponse()
        body = response.read(4097)
        if response.status != 200 or len(body) > 4096:
            return False
        reply = json.loads(body)
        return (reply.get("ok") is True and reply.get("pid") == value.get("pid") and
                reply.get("version") == VERSION)
    except (OSError, ValueError, http.client.HTTPException, AttributeError):
        return False
    finally:
        if connection is not None:
            connection.close()


def reusable(path):
    try:
        value = read_info(path)
        return value if healthy(value) else None
    except FileNotFoundError:
        return None
    except (ValueError, json.JSONDecodeError):
        # Do not remove an untrusted/symlinked record as part of normal startup.
        metadata = path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or
                (hasattr(os, "getuid") and metadata.st_uid != os.getuid()) or
                (os.name != "nt" and metadata.st_mode & 0o077)):
            raise
        return None


def open_interface(directory=None):
    directory = Path(directory) if directory is not None else private_directory()
    info = directory / "interface.json"
    lock = directory / "starting.lock"
    deadline = time.monotonic() + START_TIMEOUT
    existing = reusable(info)
    if existing:
        return existing["url"]
    lock_fd = None
    while time.monotonic() < deadline:
        try:
            lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            existing = reusable(info)
            if existing:
                return existing["url"]
            # A crashed launcher should not prevent future use indefinitely.
            metadata = lock.lstat()
            if (stat.S_ISREG(metadata.st_mode) and
                    (not hasattr(os, "getuid") or metadata.st_uid == os.getuid()) and
                    time.time() - metadata.st_mtime > 30):
                lock.unlink()
                continue
            time.sleep(0.1)
    if lock_fd is None:
        raise ValueError("LAN Cast is still opening. Try again in a moment.")
    child = None
    try:
        existing = reusable(info)
        if existing:
            return existing["url"]
        if info.exists():
            info.unlink()  # A private record that failed its loopback health check.
        script = Path(__file__).resolve().with_name("file_cast.py")
        if not script.is_file():
            raise ValueError("The downloaded-video helper is missing. Re-run LAN Cast setup.")
        child = subprocess.Popen([sys.executable, "-B", str(script), "--serve", "--info", str(info)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise ValueError("The downloaded-video window could not start. Re-run LAN Cast setup.")
            existing = reusable(info)
            if existing:
                return existing["url"]
            time.sleep(0.1)
        raise ValueError("The downloaded-video window did not respond. Try again.")
    except Exception:
        if child is not None and child.poll() is None:
            child.terminate()
        raise
    finally:
        os.close(lock_fd)
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Open LAN Cast's downloaded-video window.")
    parser.add_argument("--open", action="store_true", help="Open the local interface in your browser")
    args = parser.parse_args()
    try:
        url = open_interface()
        if args.open:
            webbrowser.open(url)
        else:
            print(url)
        return 0
    except (OSError, ValueError) as error:
        print("LAN Cast: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
