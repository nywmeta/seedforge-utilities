#!/usr/bin/env python3
"""LAN Cast native-messaging bridge. Python 3.9+, standard library only.

Each process consumes one Chrome/Edge native-messaging frame, writes one frame,
and exits. stdout is exclusively the binary native-messaging channel.
"""

import concurrent.futures
import hashlib
import http.client
import io
import ipaddress
import json
import math
import mimetypes
import os
import re
import socket
import struct
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass


HOST_NAME = "com.lancast.bridge"
VERSION = "1.2.1"
END_OF_STREAM = object()
MAX_INPUT = 64 * 1024
MAX_OUTPUT = 256 * 1024
MAX_XML = 512 * 1024
MAX_SOAP = 256 * 1024
MAX_URL = 8192
HTTP_TIMEOUT = 3.0
SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_TARGETS = (
    "urn:schemas-upnp-org:device:MediaRenderer:1",
    "urn:schemas-upnp-org:service:AVTransport:1",
)
SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
DIDL_NS = "urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
DC_NS = "http://purl.org/dc/elements/1.1/"
UPNP_NS = "urn:schemas-upnp-org:metadata-1-0/upnp/"
AVTRANSPORT_RE = re.compile(r"^urn:schemas-upnp-org:service:AVTransport:([1-9][0-9]{0,2})$")
RENDERER_RE = re.compile(r"^urn:schemas-upnp-org:device:MediaRenderer:[1-9][0-9]{0,2}$")
MIME_RE = re.compile(r"^[a-zA-Z0-9!#$&^_.+\-]+/[a-zA-Z0-9!#$&^_.+\-]+$")
PRIVATE_V4 = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8",
))
PRIVATE_V6 = tuple(ipaddress.ip_network(value) for value in ("fc00::/7", "fe80::/10", "::1/128"))


class BridgeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)


@dataclass(frozen=True)
class LocalURL:
    url: str
    scheme: str
    host: str
    port: int
    path: str


@dataclass(frozen=True)
class Renderer:
    info: dict
    service_type: str
    control_url: str


def local_ip(value):
    """Only literal RFC1918, link-local, loopback and IPv6 ULA addresses."""
    try:
        if not isinstance(value, str) or "%" in value:
            raise ValueError()
        address = ipaddress.ip_address(value)
    except ValueError:
        raise BridgeError("INVALID_DEVICE_ADDRESS", "Use the TV's local IP address or its full HTTP device-description URL.")
    effective = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped else address
    networks = PRIVATE_V4 if effective.version == 4 else PRIVATE_V6
    if not any(effective in network for network in networks):
        raise BridgeError("UNSAFE_DEVICE_URL", "TV addresses must be private, link-local or loopback IP addresses on your local network.")
    return str(address)


def _url_parts(value, label):
    if not isinstance(value, str) or not value or len(value) > MAX_URL:
        raise BridgeError("INVALID_URL", "%s must be a valid HTTP or HTTPS URL." % label)
    if any(ord(char) < 33 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
           or ord(char) in (0xFFFE, 0xFFFF) for char in value) or "\\" in value:
        raise BridgeError("INVALID_URL", "%s contains invalid URL characters." % label)
    try:
        parts = urllib.parse.urlsplit(value)
        port = parts.port
        hostname = parts.hostname
    except ValueError:
        raise BridgeError("INVALID_URL", "%s must be a valid HTTP or HTTPS URL." % label)
    if parts.scheme.lower() not in ("http", "https") or not hostname:
        raise BridgeError("INVALID_URL", "%s must start with http:// or https://." % label)
    if parts.username is not None or parts.password is not None:
        raise BridgeError("URL_CREDENTIALS", "URLs containing a username or password are not supported.")
    if port is not None and not 1 <= port <= 65535:
        raise BridgeError("INVALID_URL", "%s has an invalid port." % label)
    if parts.fragment:
        raise BridgeError("INVALID_URL", "%s must not contain a URL fragment." % label)
    return parts


def validate_local_url(value, expected_host=None):
    parts = _url_parts(value, "Device URL")
    host = local_ip(parts.hostname)
    if expected_host is not None and host != local_ip(expected_host):
        raise BridgeError("UNSAFE_DEVICE_URL", "The TV advertised a device or service URL on a different host.")
    scheme = parts.scheme.lower()
    path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    return LocalURL(value, scheme, host, parts.port or (443 if scheme == "https" else 80), path)


def validate_media_url(value):
    _url_parts(value, "Video URL")
    return value


def _remaining_timeout(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise socket.timeout("Device response deadline expired")
    return remaining


class _DeadlineReader(io.RawIOBase):
    """Apply a wall-clock deadline to each underlying socket read.

    A socket's ordinary timeout restarts whenever a device sends another byte.
    Buffered HTTP reads must also stop a peer that keeps trickling bytes.
    """
    def __init__(self, sock, deadline):
        super().__init__()
        self.sock = sock
        self.deadline = deadline
        self.raw = None
        self.raw = sock.makefile("rb", buffering=0)

    def readable(self):
        return True

    def readinto(self, buffer):
        self.sock.settimeout(_remaining_timeout(self.deadline))
        return self.raw.readinto(buffer)

    def close(self):
        try:
            if self.raw is not None:
                self.raw.close()
        finally:
            super().close()


class _DeadlineSocket:
    def __init__(self, sock, deadline):
        self.sock = sock
        self.deadline = deadline

    def makefile(self, mode):
        return io.BufferedReader(_DeadlineReader(self.sock, self.deadline))


def fetch_http(url, method="GET", body=None, headers=None, limit=MAX_XML, timeout=HTTP_TIMEOUT):
    """Direct numeric-IP connection: no DNS, proxy, or redirect following."""
    endpoint = validate_local_url(url)
    connection_type = http.client.HTTPSConnection if endpoint.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(endpoint.host, endpoint.port, timeout=timeout)
    deadline = time.monotonic() + timeout
    connection.response_class = lambda sock, *args, **kwargs: http.client.HTTPResponse(
        _DeadlineSocket(sock, deadline), *args, **kwargs)
    response = None
    request_headers = {"User-Agent": "LAN-Cast/%s UPnP/1.0" % VERSION, "Connection": "close"}
    request_headers.update(headers or {})
    try:
        connection.connect()
        connection.sock.settimeout(_remaining_timeout(deadline))
        connection.request(method, endpoint.path, body=body, headers=request_headers)
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise BridgeError("UNSAFE_REDIRECT", "The TV redirected its device or control URL; redirects are not followed.")
        content_length = response.getheader("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) < 0 or int(content_length) > limit:
                    raise BridgeError("RESPONSE_TOO_LARGE", "The TV's response exceeded the safe size limit.")
            except ValueError:
                raise BridgeError("INVALID_RESPONSE", "The TV returned an invalid HTTP response.")
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise BridgeError("RESPONSE_TOO_LARGE", "The TV's response exceeded the safe size limit.")
        return response.status, payload
    except BridgeError:
        raise
    except (OSError, http.client.HTTPException, ValueError):
        raise BridgeError("DEVICE_UNREACHABLE", "Could not reach the TV. Check that it is awake and on the same local network.")
    finally:
        if response is not None:
            response.close()
        connection.close()


def parse_xml(payload):
    if len(payload) > MAX_XML:
        raise BridgeError("RESPONSE_TOO_LARGE", "The TV's XML response exceeded the safe size limit.")
    # ElementTree ignores external entities, but rejecting all declarations also
    # prevents internal entity expansion and keeps device XML deterministic.
    declaration_probe = payload.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in declaration_probe or b"<!ENTITY" in declaration_probe:
        raise BridgeError("INVALID_XML", "The TV returned XML containing an unsupported document declaration.")
    try:
        return ET.fromstring(payload)
    except (ET.ParseError, ValueError):
        raise BridgeError("INVALID_XML", "The TV returned an invalid XML response.")


def local_name(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def child(node, name):
    return next((element for element in node if local_name(element.tag) == name), None)


def child_text(node, name, default=""):
    element = child(node, name)
    return (element.text or "").strip() if element is not None else default


def load_renderer(location, timeout=HTTP_TIMEOUT):
    source = validate_local_url(location)
    status, payload = fetch_http(location, timeout=timeout)
    if status != 200:
        raise BridgeError("DESCRIPTION_FAILED", "The TV's device description returned HTTP %s." % status)
    root = parse_xml(payload)
    url_base = child_text(root, "URLBase")
    base = urllib.parse.urljoin(location, url_base) if url_base else location
    validate_local_url(base, expected_host=source.host)
    candidates = []
    for device in root.iter():
        if local_name(device.tag) != "device":
            continue
        if not RENDERER_RE.fullmatch(child_text(device, "deviceType")):
            continue
        services = child(device, "serviceList")
        if services is None:
            continue
        for service in services:
            service_type = child_text(service, "serviceType")
            match = AVTRANSPORT_RE.fullmatch(service_type)
            control_path = child_text(service, "controlURL")
            if not match or not control_path:
                continue
            control_url = urllib.parse.urljoin(base, control_path)
            validate_local_url(control_url, expected_host=source.host)
            candidates.append((int(match.group(1)), device, service_type, control_url))
    if not candidates:
        raise BridgeError("NO_AVTRANSPORT", "This device does not advertise a UPnP AVTransport service for video casting.")
    _, device, service_type, control_url = max(candidates, key=lambda entry: entry[0])
    info = {
        "id": child_text(device, "UDN")[:256] or "location:" + hashlib.sha256(location.encode("utf-8")).hexdigest()[:24],
        "name": child_text(device, "friendlyName")[:256] or "TV at " + source.host,
        "location": location,
        "model": child_text(device, "modelName")[:256],
        "manufacturer": child_text(device, "manufacturer")[:256],
    }
    return Renderer(info, service_type, control_url)


def ssdp_locations(timeout=4.0, target=None):
    """M-SEARCH; a manual IP is queried by unicast at the standard SSDP port."""
    if target is not None:
        target = local_ip(target)
    family = socket.AF_INET6 if target is not None and ":" in target else socket.AF_INET
    destination = (target, 1900) if target is not None else SSDP_ADDRESS
    host_header = "[%s]:1900" % target if family == socket.AF_INET6 else "%s:1900" % destination[0]
    deadline = time.monotonic() + timeout
    locations = []
    seen = set()
    try:
        with socket.socket(family, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
            sock.bind(("::" if family == socket.AF_INET6 else "", 0))
            if target is None:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            for search_target in SSDP_TARGETS:
                message = (
                    "M-SEARCH * HTTP/1.1\r\nHOST: %s\r\nMAN: \"ssdp:discover\"\r\n"
                    "MX: %d\r\nST: %s\r\n\r\n"
                ) % (host_header, max(1, min(5, math.ceil(timeout))), search_target)
                sock.sendto(message.encode("ascii"), destination)
            for _ in range(128):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                sock.settimeout(remaining)
                try:
                    packet, sender = sock.recvfrom(8192)
                except socket.timeout:
                    break
                try:
                    sender_ip = local_ip(sender[0])
                    if target is not None and sender_ip != target:
                        continue
                    lines = packet.decode("iso-8859-1").split("\r\n")
                    if not re.match(r"^HTTP/1\.[01] 200(?:\s|$)", lines[0]):
                        continue
                    values = [line.split(":", 1)[1].strip() for line in lines[1:]
                              if ":" in line and line.split(":", 1)[0].strip().lower() == "location"]
                    if len(values) != 1:
                        continue
                    location = values[0]
                    validate_local_url(location, expected_host=sender_ip)
                    if location not in seen:
                        seen.add(location)
                        locations.append(location)
                    if len(locations) >= 32:
                        break
                except (BridgeError, ValueError, IndexError):
                    continue
    except (OSError, ValueError):
        raise BridgeError("DISCOVERY_FAILED", "Could not search the local network. Check your firewall and local-network permissions.")
    return locations


def discover(timeout):
    locations = ssdp_locations(timeout)
    devices = {}
    failed = 0
    # At most eight description requests run together. A response deadline also
    # prevents a device from extending discovery by slowly trickling XML bytes.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(load_renderer, location) for location in locations]
        for future in concurrent.futures.as_completed(futures):
            try:
                renderer = future.result()
                devices.setdefault(renderer.info["id"], renderer.info)
            except BridgeError:
                failed += 1
    result = {"devices": sorted(devices.values(), key=lambda device: (device["name"].casefold(), device["id"]))}
    if failed:
        result["warnings"] = ["Some devices did not provide a usable UPnP AVTransport description."]
    return result


def add_device(address):
    if re.match(r"^https?://", address, re.IGNORECASE):
        return load_renderer(address).info
    raw_address = address[1:-1] if address.startswith("[") and address.endswith("]") else address
    ip = local_ip(raw_address)
    locations = ssdp_locations(3.0, target=ip)
    for location in locations:
        try:
            return load_renderer(location).info
        except BridgeError:
            continue
    raise BridgeError("DEVICE_NOT_FOUND", "The TV did not advertise a usable renderer at that IP. Wake the TV or enter its full HTTP device-description URL, including the advertised port and path.")


def build_metadata(media_url, title, mime_type):
    # Use the general http-get protocolInfo without claiming an unverified DLNA
    # codec profile, byte seeking, or transcoding capability for the source.
    didl = ET.Element("DIDL-Lite", {"xmlns": DIDL_NS, "xmlns:dc": DC_NS, "xmlns:upnp": UPNP_NS})
    item = ET.SubElement(didl, "item", {"id": "0", "parentID": "-1", "restricted": "1"})
    ET.SubElement(item, "dc:title").text = title
    ET.SubElement(item, "upnp:class").text = "object.item.audioItem" if mime_type.lower().startswith("audio/") else "object.item.videoItem"
    ET.SubElement(item, "res", {"protocolInfo": "http-get:*:%s:*" % mime_type}).text = media_url
    return ET.tostring(didl, encoding="unicode")


def soap_action(renderer, action, arguments):
    envelope = ET.Element("s:Envelope", {"xmlns:s": SOAP_NS, "s:encodingStyle": "http://schemas.xmlsoap.org/soap/encoding/"})
    body = ET.SubElement(envelope, "s:Body")
    command = ET.SubElement(body, "u:" + action, {"xmlns:u": renderer.service_type})
    for name, value in arguments.items():
        ET.SubElement(command, name).text = str(value)
    payload = ET.tostring(envelope, encoding="utf-8", xml_declaration=True)
    status, response = fetch_http(renderer.control_url, "POST", payload, {
        "Content-Type": 'text/xml; charset="utf-8"',
        "SOAPAction": '"%s#%s"' % (renderer.service_type, action),
    }, limit=MAX_SOAP)
    xml = parse_xml(response)
    fault = next((node for node in xml.iter() if local_name(node.tag) == "Fault"), None)
    if fault is not None:
        code = next((node.text or "" for node in fault.iter() if local_name(node.tag) == "errorCode"), "")
        description = next((node.text or "" for node in fault.iter() if local_name(node.tag) == "errorDescription"), "")
        fault_message = description.strip()[:256] or "The TV rejected the playback command."
        # Keep the structured error code stable; the UPnP code aids troubleshooting.
        if code.strip().isdigit():
            fault_message = "UPnP %s: %s" % (code.strip(), fault_message)
        raise BridgeError("SOAP_FAULT", fault_message)
    if status != 200:
        raise BridgeError("CONTROL_FAILED", "The TV's playback command returned HTTP %s." % status)
    result = next((node for node in xml.iter() if local_name(node.tag) == action + "Response"), None)
    if result is None:
        raise BridgeError("INVALID_RESPONSE", "The TV did not return the expected playback response.")
    return {local_name(node.tag): (node.text or "") for node in result}


def format_position(seconds):
    value = int(seconds)
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def parse_position(value):
    match = re.fullmatch(r"(\d{1,6}):([0-5]\d):([0-5]\d)(?:\.\d+)?", value or "")
    if not match:
        return None
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def get_status(renderer):
    transport = soap_action(renderer, "GetTransportInfo", {"InstanceID": 0})
    position = soap_action(renderer, "GetPositionInfo", {"InstanceID": 0})
    return {
        "transportState": transport.get("CurrentTransportState", "UNKNOWN")[:64],
        "position": parse_position(position.get("RelTime")),
        "duration": parse_position(position.get("TrackDuration")),
    }


def require_string(request, name, maximum=MAX_URL, default=None):
    value = request.get(name, default)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise BridgeError("INVALID_REQUEST", "Provide a valid %s." % name)
    return value


def numeric_value(request, name, default, minimum, maximum):
    value = request.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum or not math.isfinite(value):
        raise BridgeError("INVALID_REQUEST", "%s must be a number between %s and %s." % (name, minimum, maximum))
    return value


def handle_request(request):
    try:
        if not isinstance(request, dict):
            raise BridgeError("INVALID_REQUEST", "The native message must be a JSON object.")
        action = require_string(request, "action", maximum=32)
        if action == "ping":
            return {"ok": True, "version": VERSION, "host": HOST_NAME}
        if action == "open_file_cast":
            try:
                from companion import open_interface
                return {"ok": True, "url": open_interface()}
            except (OSError, ValueError, ImportError) as error:
                raise BridgeError("FILE_HELPER_UNAVAILABLE", str(error))
        if action == "discover":
            result = discover(numeric_value(request, "timeout", 4.0, 0.5, 8.0))
            return dict(ok=True, **result)
        if action == "addDevice":
            return {"ok": True, "device": add_device(require_string(request, "address"))}
        if action not in ("cast", "control", "status"):
            raise BridgeError("UNKNOWN_ACTION", "Unknown bridge action.")
        location = require_string(request, "location")
        # Validate all user parameters before making a network request.
        if action == "cast":
            media_url = validate_media_url(require_string(request, "mediaUrl"))
            title = require_string(request, "title", maximum=512, default="Video")
            if any((ord(char) < 32 and char not in "\t\n\r") or 0xD800 <= ord(char) <= 0xDFFF
                   or ord(char) in (0xFFFE, 0xFFFF) for char in title):
                raise BridgeError("INVALID_REQUEST", "The video title contains unsupported characters.")
            mime_type = request.get("mimeType") or mimetypes.guess_type(urllib.parse.urlsplit(media_url).path)[0] or "video/mp4"
            if not isinstance(mime_type, str) or len(mime_type) > 128 or not MIME_RE.fullmatch(mime_type):
                raise BridgeError("INVALID_REQUEST", "Provide a valid video MIME type.")
        elif action == "control":
            command = require_string(request, "command", maximum=16)
            if command not in ("play", "pause", "stop", "seek"):
                raise BridgeError("INVALID_REQUEST", "Control must be play, pause, stop or seek.")
            if command == "seek":
                position = numeric_value(request, "position", None, 0, 35999999)
        renderer = load_renderer(location)
        if action == "status":
            return dict(ok=True, **get_status(renderer))
        if action == "cast":
            soap_action(renderer, "SetAVTransportURI", {
                "InstanceID": 0, "CurrentURI": media_url,
                "CurrentURIMetaData": build_metadata(media_url, title, mime_type),
            })
            soap_action(renderer, "Play", {"InstanceID": 0, "Speed": "1"})
            return {"ok": True, "state": "CAST_SENT"}
        if command == "seek":
            soap_action(renderer, "Seek", {"InstanceID": 0, "Unit": "REL_TIME", "Target": format_position(position)})
            return {"ok": True, "state": "SEEK_SENT", "position": int(position)}
        soap_action(renderer, command.capitalize(), {"InstanceID": 0, **({"Speed": "1"} if command == "play" else {})})
        return {"ok": True, "state": command.upper() + "_SENT"}
    except BridgeError as error:
        return {"ok": False, "error": {"code": error.code, "message": error.message}}


def read_exact(stream, length, allow_eof=False):
    chunks = []
    remaining = length
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            if allow_eof and remaining == length:
                return None
            raise BridgeError("INVALID_FRAME", "The native message frame was incomplete.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_message(stream):
    header = read_exact(stream, 4, allow_eof=True)
    if header is None:
        return END_OF_STREAM
    length = struct.unpack("=I", header)[0]
    if not 0 < length <= MAX_INPUT:
        raise BridgeError("INVALID_FRAME", "The native message exceeded the safe size limit or was empty.")
    raw = read_exact(stream, length)
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise BridgeError("INVALID_JSON", "The native message was not valid UTF-8 JSON.")


def write_message(stream, message):
    raw = json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_OUTPUT:
        raw = b'{"ok":false,"error":{"code":"RESPONSE_TOO_LARGE","message":"The bridge response exceeded the safe size limit."}}'
    stream.write(struct.pack("=I", len(raw)))
    stream.write(raw)
    stream.flush()


def main(stdin=None, stdout=None):
    if sys.platform == "win32" and stdin is None and stdout is None:
        # The four-byte length and JSON payload must never undergo CR/LF
        # translation when launched through a Windows native-host wrapper.
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    try:
        request = read_message(stdin)
        if request is END_OF_STREAM:
            return 0
        response = handle_request(request)
    except BridgeError as error:
        response = {"ok": False, "error": {"code": error.code, "message": error.message}}
    except Exception as error:
        # Avoid dumping URLs, signed queries, or message bodies in diagnostics.
        print("LAN Cast bridge: unexpected %s" % type(error).__name__, file=sys.stderr)
        response = {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "The local casting bridge encountered an unexpected error."}}
    try:
        write_message(stdout, response)
    except (BrokenPipeError, OSError):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
