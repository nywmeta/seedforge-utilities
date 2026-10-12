#!/usr/bin/env python3
"""Private browser interface for casting a downloaded file. Python 3.9+.

Importing this module starts no listeners, processes, or native-message reads.
Run with --serve --info PATH; only the private info file contains the UI URL.
"""

import argparse
from dataclasses import dataclass
from email.message import Message
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import host


VERSION = "1.2.1"
MAX_JSON = 16 * 1024
MAX_UPLOAD = 8 * 1024 ** 3
CHUNK_SIZE = 64 * 1024
MEDIA_TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime",
               ".ts": "video/mp2t", ".mkv": "video/x-matroska", ".webm": "video/webm",
               ".avi": "video/x-msvideo"}
PRIVATE_V4 = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"
))


class FileCastError(Exception):
    pass


def private_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError):
        raise FileCastError("Use the TV's private IPv4 address on your local network.")
    if not any(address in network for network in PRIVATE_V4):
        raise FileCastError("Use the TV's private IPv4 address on your local network.")
    return str(address)


def tv_endpoint(location):
    endpoint = host.validate_local_url(location)
    private_ipv4(endpoint.host)
    return endpoint


def route_ip(tv_ip, port):
    """Ask the OS for the route's source address; UDP connect sends no payload."""
    private_ipv4(tv_ip)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((tv_ip, port))
        return private_ipv4(probe.getsockname()[0])


def parse_range(header, size):
    if header is None:
        return 0, size - 1
    match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", header.strip())
    if not match or not size:
        raise FileCastError("Unsatisfiable range")
    first, last = match.groups()
    if not first:
        if not last or not int(last):
            raise FileCastError("Unsatisfiable range")
        return max(0, size - int(last)), size - 1
    start, end = int(first), int(last) if last else size - 1
    if start >= size or end < start:
        raise FileCastError("Unsatisfiable range")
    return start, min(end, size - 1)


def content_length(headers, maximum):
    values = headers.get_all("Content-Length", [])
    if headers.get_all("Transfer-Encoding", []) or len(values) != 1:
        raise FileCastError("Send one Content-Length and an unencoded request body.")
    value = values[0]
    if not re.fullmatch(r"[0-9]{1,12}", value) or not 0 < int(value) <= maximum:
        raise FileCastError("The request is empty or exceeds the size limit.")
    return int(value)


def upload_name(value):
    if not isinstance(value, str) or len(value) > 1024:
        raise FileCastError("Choose a supported downloaded video file.")
    name = unquote(value, encoding="utf-8", errors="strict")
    if not name or len(name) > 256 or any(c in name for c in "/\\") or any(ord(c) < 32 for c in name):
        raise FileCastError("The video filename is invalid.")
    suffix = Path(name).suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise FileCastError("Choose an MP4, M4V, MOV, TS, MKV, WebM or AVI file.")
    return name, suffix, MEDIA_TYPES[suffix]


@dataclass(frozen=True)
class Upload:
    id: str
    path: Path
    name: str
    size: int
    mime: str

    def public(self):
        return {"uploadId": self.id, "name": self.name, "size": self.size, "mimeType": self.mime}


class LimitedServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, handler, allowed_ip, workers=6):
        self.allowed_ip = allowed_ip
        self.slots = threading.BoundedSemaphore(workers)
        self.clients = set()
        self.clients_lock = threading.Lock()
        super().__init__(address, handler)

    def verify_request(self, request, client_address):
        return client_address[0] == self.allowed_ip

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        with self.clients_lock:
            self.clients.add(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            with self.clients_lock:
                self.clients.discard(request)
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.clients_lock:
                self.clients.discard(request)
            self.slots.release()

    def close_clients(self):
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def handle_error(self, request, client_address):
        pass  # Avoid logging secret request paths or local filenames.


class QuietHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        self.request.settimeout(15)
        super().setup()

    def log_message(self, *_args):
        pass

    def respond(self, status, payload=b"", content_type="application/json", extra=None):
        self.send_response(status)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(payload)

    def json_response(self, status, value):
        self.respond(status, json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8"))


def media_handler(upload, file_fd, token_path, stop, touch):
    class MediaHandler(QuietHandler):
        def do_HEAD(self):
            self.serve(False)

        def do_GET(self):
            self.serve(True)

        def serve(self, body):
            if self.path != token_path or stop.is_set():
                self.respond(404)
                return
            ranges = self.headers.get_all("Range", [])
            try:
                if len(ranges) > 1:
                    raise FileCastError("Multiple ranges are not supported.")
                first, last = parse_range(ranges[0] if ranges else None, upload.size)
            except (FileCastError, ValueError):
                self.respond(416, extra={"Content-Range": "bytes */%s" % upload.size,
                                         "Accept-Ranges": "bytes"})
                return
            touch()
            length = max(0, last - first + 1)
            self.send_response(206 if ranges else 200)
            for key, value in {"Content-Type": upload.mime, "Content-Length": str(length),
                               "Accept-Ranges": "bytes", "Connection": "close", "Cache-Control": "no-store"}.items():
                self.send_header(key, value)
            if ranges:
                self.send_header("Content-Range", "bytes %s-%s/%s" % (first, last, upload.size))
            self.end_headers()
            self.close_connection = True
            if not body:
                return
            try:
                # Each response has its own duplicated descriptor and seek offset.
                # This supports Windows too, where os.pread is unavailable.
                with open(upload.path, "rb") as video:
                    video.seek(first)
                    remaining = length
                    while remaining and not stop.is_set():
                        chunk = video.read(min(CHUNK_SIZE, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                        touch()
            except (OSError, TimeoutError):
                pass

    return MediaHandler


class MediaSession:
    def __init__(self, upload, tv_ip, tv_port, touch):
        self.upload = upload
        self.stop = threading.Event()
        bind_ip = route_ip(tv_ip, tv_port)
        path = "/" + secrets.token_urlsafe(32) + "/video" + upload.path.suffix
        self.server = LimitedServer((bind_ip, 0), media_handler(upload, None, path, self.stop, touch), tv_ip, 4)
        self.url = "http://%s:%s%s" % (bind_ip, self.server.server_port, path)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.server.close_clients()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class App:
    def __init__(self, bridge=None, session_factory=MediaSession):
        self.bridge = bridge or host.handle_request
        self.session_factory = session_factory
        self.token = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.origin = None
        self.lock = threading.RLock()
        self.upload_lock = threading.Lock()
        self.temporary = tempfile.TemporaryDirectory(prefix="lan-cast-")
        os.chmod(self.temporary.name, 0o700)
        self.staged = None
        self.active = None
        self.location = None
        self.last_activity = time.monotonic()
        self.awake = None
        self.closed = False

    def touch(self):
        self.last_activity = time.monotonic()

    def state(self):
        with self.lock:
            return {"ok": True, "version": VERSION,
                    "file": self.staged.public() if self.staged else None,
                    "casting": self.active.upload.public() if self.active else None,
                    "location": self.location, "maxUpload": MAX_UPLOAD}

    def receive_upload(self, stream, size, filename):
        name, suffix, mime = upload_name(filename)
        if not 0 < size <= MAX_UPLOAD:
            raise FileCastError("The video is empty or larger than 8 GB.")
        if not self.upload_lock.acquire(blocking=False):
            raise FileCastError("Another file is still being copied.")
        path = None
        try:
            with self.lock:
                if self.closed:
                    raise FileCastError("The local interface is closing.")
            fd, raw_path = tempfile.mkstemp(prefix="video-", suffix=suffix, dir=self.temporary.name)
            path = Path(raw_path)
            deadline = time.monotonic() + 3600
            with os.fdopen(fd, "wb") as destination:
                remaining = size
                while remaining:
                    if self.closed or time.monotonic() >= deadline:
                        raise FileCastError("The file copy was interrupted.")
                    chunk = stream.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise FileCastError("The file copy ended before the whole video arrived.")
                    destination.write(chunk)
                    remaining -= len(chunk)
                    self.touch()
            upload = Upload(secrets.token_urlsafe(24), path, name, size, mime)
            with self.lock:
                if self.closed:
                    raise FileCastError("The local interface is closing.")
                previous = self.staged
                self.staged = upload
                if previous and (not self.active or previous.id != self.active.upload.id):
                    previous.path.unlink(missing_ok=True)
            return dict(ok=True, **upload.public())
        except BaseException:
            if path:
                path.unlink(missing_ok=True)
            raise
        finally:
            self.upload_lock.release()

    def keep_awake(self):
        if sys.platform == "darwin" and self.awake is None:
            try:
                self.awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def release_awake(self):
        if self.awake is not None:
            self.awake.terminate()
            try:
                self.awake.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.awake.kill()
                self.awake.wait(timeout=2)
            self.awake = None

    def command(self, action, data):
        expected = {"discover": set(), "addDevice": {"address"}, "cast": {"location", "uploadId"},
                    "play": set(), "pause": set(), "stop": set(), "status": set()}
        if action not in expected or not isinstance(data, dict) or set(data) != expected[action]:
            raise FileCastError("The playback request is invalid.")
        self.touch()
        if action == "discover":
            result = self.bridge({"action": "discover", "timeout": 4.0})
            if result.get("ok"):
                devices = []
                for device in result.get("devices", []):
                    try:
                        tv_endpoint(device["location"])
                        devices.append(device)
                    except (KeyError, FileCastError, host.BridgeError):
                        pass
                result = dict(result, devices=devices)
            return result
        if action == "addDevice":
            address = data["address"]
            if not isinstance(address, str) or len(address) > host.MAX_URL:
                raise FileCastError("Enter a TV IP address or device-description URL.")
            if address.lower().startswith(("http://", "https://")):
                tv_endpoint(address)
            else:
                private_ipv4(address)
            return self.bridge({"action": "addDevice", "address": address})
        with self.lock:
            if self.closed:
                raise FileCastError("The local interface is closing.")
            if action == "cast":
                endpoint = tv_endpoint(data["location"])
                if not self.staged or data["uploadId"] != self.staged.id:
                    raise FileCastError("Choose and finish copying a video first.")
                candidate = self.session_factory(self.staged, endpoint.host, endpoint.port, self.touch)
                try:
                    result = self.bridge({"action": "cast", "location": data["location"],
                                          "mediaUrl": candidate.url, "title": self.staged.name,
                                          "mimeType": self.staged.mime})
                    if not result.get("ok"):
                        candidate.close()
                        return result
                except BaseException:
                    candidate.close()
                    raise
                old = self.active
                self.active, self.location = candidate, data["location"]
                self.keep_awake()
                if old:
                    old.close()
                    if old.upload.id != self.staged.id:
                        old.upload.path.unlink(missing_ok=True)
                return result
            if not self.active or not self.location:
                raise FileCastError("Cast a video to the TV first.")
            if action == "status":
                return self.bridge({"action": "status", "location": self.location})
            result = self.bridge({"action": "control", "location": self.location, "command": action})
            if action == "stop" and result.get("ok"):
                stopped = self.active
                stopped.close()
                self.active = None
                self.location = None
                if not self.staged or stopped.upload.id != self.staged.id:
                    stopped.upload.path.unlink(missing_ok=True)
                self.release_awake()
            return result

    def close(self):
        self.closed = True
        with self.lock:
            if self.active:
                self.active.close()
                self.active = None
            self.release_awake()
        # Wait for an interrupted upload before deleting its private directory.
        with self.upload_lock:
            self.temporary.cleanup()


def protected_request(app, headers, client_ip, require_csrf=False, require_origin=False):
    if client_ip != "127.0.0.1" or headers.get_all("Host", []) != [app.origin.split("://", 1)[1]]:
        return False
    origins = headers.get_all("Origin", [])
    if origins and origins != [app.origin]:
        return False
    if require_origin and origins != [app.origin]:
        return False
    if require_csrf and headers.get_all("X-LAN-Cast-CSRF", []) != [app.csrf]:
        return False
    return True


def control_handler(app):
    class ControlHandler(QuietHandler):
        def do_GET(self):
            prefix = "/" + app.token + "/"
            if not protected_request(app, self.headers, self.client_address[0]):
                self.respond(403)
                return
            if self.path == prefix:
                nonce = secrets.token_urlsafe(24)
                body = render_ui(prefix, app.csrf, nonce).encode("utf-8")
                self.respond(200, body, "text/html; charset=utf-8", {
                    "Content-Security-Policy": "default-src 'none'; script-src 'nonce-%s'; style-src 'nonce-%s'; connect-src 'self'; img-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'" % (nonce, nonce),
                    "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer"})
            elif self.path == prefix + "health":
                self.json_response(200, {"ok": True, "pid": os.getpid(), "version": VERSION})
            elif self.path == prefix + "api/state" and protected_request(app, self.headers, self.client_address[0], True):
                # Passive window synchronization must not keep an idle helper alive.
                self.json_response(200, app.state())
            else:
                self.respond(404)

        def do_POST(self):
            prefix = "/" + app.token + "/api/"
            if not self.path.startswith(prefix) or not protected_request(app, self.headers, self.client_address[0], True, True):
                self.respond(403)
                return
            action = self.path[len(prefix):]
            try:
                if action == "upload":
                    size = content_length(self.headers, MAX_UPLOAD)
                    names = self.headers.get_all("X-Filename", [])
                    if len(names) != 1:
                        raise FileCastError("Choose one downloaded video file.")
                    result = app.receive_upload(self.rfile, size, names[0])
                else:
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        raise FileCastError("Use a JSON playback command.")
                    size = content_length(self.headers, MAX_JSON)
                    payload = self.rfile.read(size)
                    if len(payload) != size:
                        raise FileCastError("The playback request was incomplete.")
                    data = json.loads(payload.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    result = app.command(action, data)
                self.json_response(200, result)
            except (FileCastError, host.BridgeError, ValueError, UnicodeError, RecursionError) as error:
                message = error.message if isinstance(error, host.BridgeError) else str(error) if isinstance(error, FileCastError) else "The playback request is invalid."
                self.json_response(400, {"ok": False, "error": {"message": message}})
            except (OSError, TimeoutError):
                self.json_response(400, {"ok": False, "error": {"message": "The local file copy or TV connection was interrupted."}})
            except Exception:
                self.json_response(500, {"ok": False, "error": {"message": "The local interface encountered an unexpected error."}})

    return ControlHandler


def publish_info(path, data):
    """Atomically publish a 0600 file without overwriting an existing path."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=".lan-cast-info-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output, ensure_ascii=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        identity = os.stat(temporary)
        os.link(temporary, path)
        return identity
    finally:
        os.unlink(temporary)


def remove_info(path, identity):
    try:
        current = os.lstat(path)
        if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
            os.unlink(path)
    except FileNotFoundError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", required=True)
    parser.add_argument("--info", required=True, type=Path)
    parser.add_argument("--idle-hours", type=float, default=8.0)
    args = parser.parse_args(argv)
    if not 0 < args.idle_hours <= 72:
        parser.error("Idle hours must be between 0 and 72.")
    app, server, identity = App(), None, None
    stop = threading.Event()
    previous = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda *_args: stop.set())
        server = LimitedServer(("127.0.0.1", 0), control_handler(app), "127.0.0.1")
        server.timeout = 0.25
        app.origin = "http://127.0.0.1:%s" % server.server_port
        identity = publish_info(args.info, {"url": app.origin + "/" + app.token + "/",
                                            "pid": os.getpid(), "started_at": int(time.time()), "version": VERSION})
        while not stop.is_set() and time.monotonic() - app.last_activity < args.idle_hours * 3600:
            server.handle_request()
        return 0
    except OSError:
        print("LAN Cast: could not start the private file interface.", file=sys.stderr)
        return 1
    finally:
        if server:
            server.close_clients()
            server.server_close()
        app.close()
        if identity:
            remove_info(args.info, identity)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def render_ui(prefix, csrf, nonce):
    return UI.replace("__NONCE__", nonce).replace("__CONFIG__", json.dumps({"prefix": prefix, "csrf": csrf}))


UI = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LAN Cast · Downloaded video</title>
<style nonce="__NONCE__">
:root{color-scheme:dark;--ink:#edf2ff;--muted:#a4afc5;--line:#2b354b;--accent:#9bf5ca}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% 0,#20372e 0,transparent 45%),#101621;color:var(--ink);font:16px/1.5 system-ui,-apple-system,sans-serif}main{max-width:850px;margin:auto;padding:45px 22px}.brand{display:flex;align-items:center;gap:10px;font-weight:750;letter-spacing:.06em}.logo{display:grid;place-items:center;background:var(--accent);color:#10251b;border-radius:10px;width:34px;height:34px}h1{font-size:clamp(30px,6vw,46px);line-height:1.15;margin:24px 0 12px;letter-spacing:-.04em}.intro{color:var(--muted);max-width:600px;margin-bottom:30px}.card{padding:24px;background:#192131d9;border:1px solid var(--line);border-radius:18px;margin:16px 0}.heading{display:flex;align-items:center;gap:12px;margin-bottom:16px}.number{border:1px solid #456c59;color:var(--accent);border-radius:50%;width:29px;height:29px;display:grid;place-items:center;font-size:14px}h2{font-size:18px;margin:0}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}button,input,select{font:inherit;border-radius:10px;min-height:44px}button{border:1px solid #46536b;background:#263247;color:var(--ink);padding:9px 18px;cursor:pointer;font-weight:650}button:hover{background:#32405a}button:disabled{opacity:.45;cursor:default}.primary{background:var(--accent);border-color:var(--accent);color:#123124}.primary:hover{background:#b5f8d9}input,select{background:#101723;color:var(--ink);border:1px solid #3d4960;padding:9px 12px;width:100%}select{flex:1;min-width:200px}.manual{margin-top:15px}.manual input{flex:1;min-width:180px}.small{font-size:13px;color:var(--muted);margin:10px 0 0}label{display:block;font-size:14px;color:#bdc8db;margin-bottom:7px}.file{border:1px dashed #52617c;border-radius:12px;padding:18px;background:#111b28}input[type=file]{border:0;background:transparent;padding:0;max-width:100%}input[type=file]::file-selector-button{font:inherit;border:0;border-radius:7px;padding:8px 12px;background:#34455c;color:var(--ink);margin-right:10px}progress[hidden]{display:none}progress{display:block;width:100%;height:7px;margin-top:16px;accent-color:var(--accent)}.transport{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}.controls{display:flex;gap:8px;flex-wrap:wrap}.state{font-size:14px;color:var(--accent)}#message{min-height:26px;color:var(--muted);margin:16px 2px}#message.error{color:#ffacac}#current{overflow-wrap:anywhere}footer{font-size:13px;color:var(--muted);margin-top:28px;max-width:700px}details{margin-top:15px}summary{cursor:pointer}.sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #9bf5ca;outline-offset:3px}@media(max-width:480px){main{padding:28px 16px}.card{padding:19px}.row>button{flex:1}.controls button{padding:9px 12px}}
</style></head><body><main>
<div class="brand"><span class="logo" aria-hidden="true">↗</span>LAN CAST <span class="small" style="margin:0">Downloaded video</span></div>
<h1>Your episode.<br>Your TV.</h1><p class="intro">Choose a video you have already downloaded, then play it on a UPnP / DLNA TV on the same local network.</p>
<section class="card" aria-labelledby="tv-heading"><div class="heading"><span class="number">1</span><h2 id="tv-heading">Choose your TV</h2></div><div class="row"><label class="sr" for="tvs">Available TVs</label><select id="tvs"><option value="">Find a TV to get started</option></select><button id="find">Find TVs</button></div><div class="manual"><label for="address">Or add it manually</label><div class="row"><input id="address" placeholder="TV IP or full device-description URL" autocomplete="off" spellcheck="false"><button id="add">Add TV</button></div><p class="small">Wake the TV and enable its media-renderer / DLNA setting if it does not appear.</p></div></section>
<section class="card" aria-labelledby="file-heading"><div class="heading"><span class="number">2</span><h2 id="file-heading">Choose a downloaded episode</h2></div><div class="file"><label for="file">Video file</label><input id="file" type="file" accept=".mp4,.m4v,.mov,.ts,.mkv,.webm,.avi"><progress id="progress" value="0" max="100" hidden aria-label="Copy progress"></progress><p class="small" id="file-note">MP4 is usually the most compatible choice. Maximum 8 GB.</p></div><p class="small">A temporary private copy stays on this computer. Your TV fetches it directly over your local network.</p></section>
<section class="card" aria-labelledby="play-heading"><div class="heading"><span class="number">3</span><h2 id="play-heading">Play on the big screen</h2></div><div class="transport"><div><div id="current">Ready when you are</div><div id="status" class="state">Choose a TV and a video</div><div id="active-tv" class="small"></div></div><button id="cast" class="primary" disabled>Cast to TV</button></div><div class="controls" style="margin-top:18px"><button id="play" disabled>Play</button><button id="pause" disabled>Pause</button><button id="stop" disabled>Stop</button><button id="refresh" disabled>Check status</button></div></section>
<div id="message" role="status" aria-live="polite"></div><footer>Keep this computer on and connected while the TV plays. On a Mac, LAN Cast keeps it awake while serving the video. No video is sent to a cloud service.<details><summary>Playback limitations</summary><p>This serves a downloaded file; it does not capture a browser tab, download protected streams, or bypass website restrictions. The TV must support the video's container, video and audio codecs. There is no transcoding or separate subtitle support. A successful command means the TV accepted it; check the screen to confirm playback. The interface closes after eight hours without activity; ongoing video transfers count as activity.</p></details></footer>
</main><script nonce="__NONCE__">
const config=__CONFIG__; const $=id=>document.getElementById(id); let uploaded=null, casting=false, busy=false, activeLocation=null, activeUploadId=null, stateGeneration=0, pollPending=false; const devices=new Map();
function message(text,error=false){$('message').textContent=text;$('message').classList.toggle('error',error)}
function update(){ $('cast').disabled=busy||!uploaded||!$('tvs').value;for(const id of ['find','add','file','tvs'])$(id).disabled=busy;for(const id of ['play','pause','stop','refresh'])$(id).disabled=busy||!casting }
async function api(action,data={}){const response=await fetch(config.prefix+'api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-LAN-Cast-CSRF':config.csrf},body:JSON.stringify(data)});const result=await response.json();if(!result.ok)throw new Error(result.error?.message||'The command could not be completed.');return result}
function showTarget(location){activeLocation=location;if(!location){$('active-tv').textContent='';return}let name=devices.get(location)?.name;try{if(!name||name==='Current TV')name='TV at '+new URL(location).hostname}catch(_){}$('active-tv').textContent='Playback controls: '+(name||'current TV')}
function addDevice(device,select=true){if(!device?.location)return;devices.set(device.location,device);let option=Array.from($('tvs').options).find(o=>o.value===device.location);if(!option){option=document.createElement('option');option.value=device.location;$('tvs').append(option)}option.textContent=device.name||'TV';if(select||!$('tvs').value)$('tvs').value=device.location;showTarget(activeLocation);update()}
async function task(fn){if(busy)return;stateGeneration++;busy=true;update();try{await fn()}catch(error){message(error.message,true)}finally{busy=false;update()}}
$('find').onclick=()=>task(async()=>{message('Looking for TVs…');const result=await api('discover');for(const device of result.devices||[])addDevice(device);message(result.devices?.length?'Choose your TV above.':'No TV found. Try its local IP address or device-description URL.');});
$('add').onclick=()=>task(async()=>{message('Checking the TV…');const result=await api('addDevice',{address:$('address').value.trim()});addDevice(result.device);message('TV added.');});
$('tvs').onchange=update;
$('file').onchange=()=>task(async()=>{const file=$('file').files[0];if(!file)return;message('Copying the video locally…');$('progress').hidden=false;$('progress').value=0;const result=await new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',config.prefix+'api/upload');xhr.setRequestHeader('X-LAN-Cast-CSRF',config.csrf);xhr.setRequestHeader('X-Filename',encodeURIComponent(file.name));xhr.upload.onprogress=e=>{if(e.lengthComputable)$('progress').value=e.loaded/e.total*100};xhr.onerror=()=>reject(new Error('The local copy was interrupted.'));xhr.onload=()=>{try{const result=JSON.parse(xhr.responseText);result.ok?resolve(result):reject(new Error(result.error?.message||'The video could not be copied.'))}catch(_){reject(new Error('The local interface did not respond.'))}};xhr.send(file)});uploaded=result;$('file-note').textContent=result.name+' · '+(result.size/1024/1024).toFixed(1)+' MB · ready';$('progress').value=100;message('Video ready. Cast when you are ready.');});
$('cast').onclick=()=>task(async()=>{message('Sending the video to your TV…');await api('cast',{location:$('tvs').value,uploadId:uploaded.uploadId});casting=true;activeUploadId=uploaded.uploadId;showTarget($('tvs').value);$('current').textContent=uploaded.name;$('status').textContent='Cast accepted — check your TV';message('The TV accepted the playback command.');});
for(const command of ['play','pause','stop'])$(command).onclick=()=>task(async()=>{await api(command);$('status').textContent=command==='stop'?'Stopped — use Cast to TV to restart':command==='pause'?'Pause accepted':'Play accepted';if(command==='stop'){casting=false;activeUploadId=null;showTarget(null)}message('TV command accepted.');});
$('refresh').onclick=()=>task(async()=>{const state=await api('status');const format=n=>Number.isFinite(n)?Math.floor(n/60)+':'+String(n%60).padStart(2,'0'):'';$('status').textContent=state.transportState+(Number.isFinite(state.position)?' · '+format(state.position)+(Number.isFinite(state.duration)?' / '+format(state.duration):''):'');message('TV status refreshed.');});
function applyState(state){
  if(uploaded?.uploadId!==state.file?.uploadId)$('file').value='';
  uploaded=state.file;
  $('file-note').textContent=uploaded?uploaded.name+' · ready':'MP4 is usually the most compatible choice. Maximum 8 GB.';
  const nextId=state.casting?.uploadId||null, nextLocation=state.location||null;
  const changed=activeUploadId!==nextId||activeLocation!==nextLocation||casting!==!!state.casting;
  casting=!!state.casting;activeUploadId=nextId;
  if(nextLocation&&!devices.has(nextLocation))addDevice({location:nextLocation,name:'Current TV'},false);
  showTarget(nextLocation);
  if(changed){
    $('current').textContent=state.casting?state.casting.name:'Ready when you are';
    $('status').textContent=state.casting?'A video is being served — check status':'No video is being served';
  }
  update();
}
async function syncState(initial=false){
  if(busy||pollPending||(!initial&&document.hidden))return;
  pollPending=true;const generation=stateGeneration, controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),8000);
  try{
    const response=await fetch(config.prefix+'api/state',{headers:{'X-LAN-Cast-CSRF':config.csrf},signal:controller.signal});
    const state=await response.json();
    if(busy||generation!==stateGeneration)return;
    if(!response.ok||!state||state.ok!==true||!['file','casting','location'].every(key=>key in state))throw new Error('Invalid state');
    applyState(state);
  }catch(_){
    if(initial&&!busy&&generation===stateGeneration)message('The local interface is no longer running. Open it again from LAN Cast.',true);
  }finally{clearTimeout(timeout);pollPending=false}
}
syncState(true);
setInterval(()=>syncState(),5000);
window.addEventListener('focus',()=>syncState());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)syncState()});
</script></body></html>'''


if __name__ == "__main__":
    raise SystemExit(main())
