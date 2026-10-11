"""Meaningful bridge checks against a real local HTTP UPnP renderer.

Run: python3 -m unittest discover -s tests -v
No TV, Internet access or external dependency is required.
"""

import io
import json
import socket
import struct
import subprocess
import sys
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

HELPER = Path(__file__).resolve().parents[1] / "helper"
sys.path.insert(0, str(HELPER))
import host


def soap_response(action, values=None, service_type="urn:schemas-upnp-org:service:AVTransport:3"):
    envelope = ET.Element("s:Envelope", {"xmlns:s": host.SOAP_NS})
    body = ET.SubElement(envelope, "s:Body")
    result = ET.SubElement(body, "u:" + action + "Response", {"xmlns:u": service_type})
    for key, value in (values or {}).items():
        ET.SubElement(result, key).text = value
    return ET.tostring(envelope)


class FakeRendererHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        state = self.server.state
        if state.get("trickle"):
            mode = state["trickle"]
            try:
                if mode == "headers":
                    payload = b"HTTP/1.0 200 OK\r\nContent-Length: 1\r\n\r\nx"
                else:
                    self.send_response(200)
                    self.send_header("Content-Length", "60")
                    self.end_headers()
                    payload = b"x" * 60
                for byte in payload:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.025)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if state.get("redirect"):
            self.send_response(302)
            self.send_header("Location", state["redirect"])
            self.end_headers()
            return
        payload = state["description"].encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            # The bridge deliberately closes oversized description responses.
            pass

    def do_POST(self):
        payload = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        document = ET.fromstring(payload)
        body = document.find("{%s}Body" % host.SOAP_NS)
        command = list(body)[0]
        action = host.local_name(command.tag)
        arguments = {host.local_name(element.tag): element.text or "" for element in command}
        state = self.server.state
        state["requests"].append({"action": action, "arguments": arguments,
                                  "soapAction": self.headers.get("SOAPAction"), "path": self.path,
                                  "serviceType": command.tag.rsplit("}", 1)[0][1:]})
        if action in state.get("faults", set()):
            response = (
                '<s:Envelope xmlns:s="%s"><s:Body><s:Fault><faultcode>s:Client</faultcode>'
                '<faultstring>UPnPError</faultstring><detail><UPnPError xmlns="urn:schemas-upnp-org:control-1-0">'
                '<errorCode>701</errorCode><errorDescription>Transition not available</errorDescription>'
                '</UPnPError></detail></s:Fault></s:Body></s:Envelope>' % host.SOAP_NS
            ).encode("utf-8")
            status = 500
        else:
            values = {}
            if action == "Play":
                state["transportState"] = "PLAYING"
            elif action == "Pause":
                state["transportState"] = "PAUSED_PLAYBACK"
            elif action == "Stop":
                state["transportState"] = "STOPPED"
            elif action == "Seek":
                state["position"] = arguments["Target"]
            elif action == "GetTransportInfo":
                values = {"CurrentTransportState": state["transportState"], "CurrentTransportStatus": "OK", "CurrentSpeed": "1"}
            elif action == "GetPositionInfo":
                values = {"Track": "1", "TrackDuration": "00:02:03", "RelTime": state["position"]}
            response = soap_response(action, values)
            status = 200
        self.send_response(status)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


class FakeSocket:
    def __init__(self, packets):
        self.packets = list(packets)
        self.sent = []
        self.timeout = None
        self.bound = None
        self.options = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def bind(self, address):
        self.bound = address

    def setsockopt(self, *args):
        self.options.append(args)

    def settimeout(self, value):
        self.timeout = value

    def sendto(self, payload, address):
        self.sent.append((payload, address))

    def recvfrom(self, size):
        if self.packets:
            return self.packets.pop(0)
        raise socket.timeout()


def ssdp_packet(location, sender="127.0.0.1"):
    return (('HTTP/1.1 200 OK\r\nLOCATION: %s\r\nST: urn:schemas-upnp-org:device:MediaRenderer:3\r\n\r\n' % location).encode("ascii"), (sender, 1900))


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeRendererHandler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.location = "http://127.0.0.1:%s/device.xml" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.state = {
            "description": self.description(), "requests": [], "faults": set(),
            "transportState": "STOPPED", "position": "00:01:04",
        }

    def description(self, control="/av/control", url_base="", service_type="urn:schemas-upnp-org:service:AVTransport:3"):
        return '''<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0">
        %s<device><deviceType>urn:schemas-upnp-org:device:MediaRenderer:3</deviceType>
        <friendlyName>Test TV &amp; Living Room</friendlyName><manufacturer>Example</manufacturer>
        <modelName>Renderer 3</modelName><UDN>uuid:test-tv</UDN>
        <serviceList><service><serviceType>%s</serviceType><controlURL>%s</controlURL></service>
        </serviceList></device></root>''' % (('<URLBase>%s</URLBase>' % url_base) if url_base else "", service_type, control)

    def request(self, action, **values):
        return host.handle_request(dict(action=action, location=self.location, **values))

    def test_manual_full_description_and_service_version(self):
        result = host.handle_request({"action": "addDevice", "address": self.location})
        self.assertTrue(result["ok"])
        self.assertEqual(result["device"], {
            "id": "uuid:test-tv", "name": "Test TV & Living Room", "location": self.location,
            "model": "Renderer 3", "manufacturer": "Example",
        })
        self.assertEqual(host.load_renderer(self.location).service_type, "urn:schemas-upnp-org:service:AVTransport:3")

    def test_cast_didl_and_soap_escaping(self):
        media = "https://example.test/video.mp4?token=one&quality=hd"
        title = 'Video <one> & "two"'
        result = self.request("cast", mediaUrl=media, title=title, mimeType="video/mp4")
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "CAST_SENT")
        self.assertNotIn("transportState", result)
        requests = self.server.state["requests"]
        self.assertEqual([entry["action"] for entry in requests], ["SetAVTransportURI", "Play"])
        request = requests[0]
        self.assertEqual(request["soapAction"], '"urn:schemas-upnp-org:service:AVTransport:3#SetAVTransportURI"')
        self.assertEqual(request["serviceType"], "urn:schemas-upnp-org:service:AVTransport:3")
        self.assertEqual(request["arguments"]["CurrentURI"], media)
        metadata = ET.fromstring(request["arguments"]["CurrentURIMetaData"])
        item = metadata.find("{%s}item" % host.DIDL_NS)
        self.assertEqual(item.find("{%s}title" % host.DC_NS).text, title)
        self.assertEqual(item.find("{%s}class" % host.UPNP_NS).text, "object.item.videoItem")
        resource = item.find("{%s}res" % host.DIDL_NS)
        self.assertEqual(resource.text, media)
        self.assertEqual(resource.attrib["protocolInfo"], "http-get:*:video/mp4:*")
        self.assertEqual(requests[1]["arguments"], {"InstanceID": "0", "Speed": "1"})

    def test_urlbase_and_relative_control(self):
        base = self.location.rsplit("/", 1)[0] + "/service/"
        self.server.state["description"] = self.description(control="transport", url_base=base)
        self.assertTrue(self.request("control", command="play")["ok"])
        self.assertEqual(self.server.state["requests"][0]["path"], "/service/transport")

    def test_embedded_renderer_has_own_name(self):
        embedded = self.description().split("<device>", 1)[1].rsplit("</root>", 1)[0]
        self.server.state["description"] = '<root><device><friendlyName>Root device</friendlyName><deviceList><device>' + embedded + '</deviceList></device></root>'
        self.assertEqual(host.load_renderer(self.location).info["name"], "Test TV & Living Room")

    def test_control_actions_and_seek(self):
        for command, expected in (("play", "PLAY_SENT"), ("pause", "PAUSE_SENT"), ("stop", "STOP_SENT")):
            with self.subTest(command=command):
                result = self.request("control", command=command)
                self.assertEqual(result["state"], expected)
                self.assertNotIn("transportState", result)
        result = self.request("control", command="seek", position=3661.9)
        self.assertEqual(result["position"], 3661)
        self.assertEqual(self.server.state["requests"][-1]["arguments"], {"InstanceID": "0", "Unit": "REL_TIME", "Target": "01:01:01"})

    def test_status_returns_seconds_at_top_level(self):
        self.server.state["transportState"] = "PLAYING"
        result = self.request("status")
        self.assertEqual(result, {"ok": True, "transportState": "PLAYING", "position": 64, "duration": 123})

    def test_soap_fault_stops_cast_before_play(self):
        self.server.state["faults"] = {"SetAVTransportURI"}
        result = self.request("cast", mediaUrl="http://example.test/video.mp4")
        self.assertEqual(result["error"]["code"], "SOAP_FAULT")
        self.assertIn("701", result["error"]["message"])
        self.assertEqual([entry["action"] for entry in self.server.state["requests"]], ["SetAVTransportURI"])

    def test_soap_control_fault_is_structured(self):
        self.server.state["faults"] = {"Seek"}
        result = self.request("control", command="seek", position=3)
        self.assertEqual(result["error"]["code"], "SOAP_FAULT")

    def test_cross_host_control_is_rejected(self):
        self.server.state["description"] = self.description(control="http://192.168.1.9:3000/control")
        result = self.request("status")
        self.assertEqual(result["error"]["code"], "UNSAFE_DEVICE_URL")
        self.assertEqual(self.server.state["requests"], [])

    def test_avtransport_on_media_server_is_not_a_renderer(self):
        self.server.state["description"] = self.description().replace("device:MediaRenderer:3", "device:MediaServer:3")
        self.assertEqual(self.request("status")["error"]["code"], "NO_AVTRANSPORT")

    def test_wan_urlbase_is_rejected(self):
        self.server.state["description"] = self.description(url_base="http://8.8.8.8/")
        result = self.request("status")
        self.assertEqual(result["error"]["code"], "UNSAFE_DEVICE_URL")

    def test_redirect_to_wan_is_not_followed(self):
        self.server.state["redirect"] = "http://8.8.8.8/description"
        result = self.request("status")
        self.assertEqual(result["error"]["code"], "UNSAFE_REDIRECT")

    def test_trickled_headers_and_body_do_not_restart_http_deadline(self):
        for mode in ("headers", "body"):
            with self.subTest(mode=mode):
                self.server.state["trickle"] = mode
                started = time.monotonic()
                with self.assertRaises(host.BridgeError) as context:
                    host.fetch_http(self.location, timeout=0.15)
                self.assertEqual(context.exception.code, "DEVICE_UNREACHABLE")
                self.assertLess(time.monotonic() - started, 1.0)

    def test_invalid_xml_dtd_and_oversized_response(self):
        for description, expected in (("<broken", "INVALID_XML"),
                                      ('<!DOCTYPE root [<!ENTITY test "hello">]><root>&test;</root>', "INVALID_XML"),
                                      ("x" * (host.MAX_XML + 1), "RESPONSE_TOO_LARGE")):
            with self.subTest(expected=expected):
                self.server.state["description"] = description
                self.assertEqual(self.request("status")["error"]["code"], expected)

    def test_discovery_deduplicates_and_loads_udp_results(self):
        fake = FakeSocket([ssdp_packet(self.location), ssdp_packet(self.location)])
        with mock.patch.object(host.socket, "socket", return_value=fake):
            # Patch only SSDP; HTTPConnection also uses socket.socket, so perform
            # the real description requests after the UDP mock leaves scope.
            locations = host.ssdp_locations(0.5)
        with mock.patch.object(host, "ssdp_locations", return_value=locations):
            result = host.handle_request({"action": "discover", "timeout": 0.5})
        self.assertEqual(len(result["devices"]), 1)
        self.assertEqual(result["devices"][0]["id"], "uuid:test-tv")
        self.assertEqual([packet[1] for packet in fake.sent], [host.SSDP_ADDRESS, host.SSDP_ADDRESS])
        self.assertIn(b"MediaRenderer:1", fake.sent[0][0])
        self.assertIn(b"AVTransport:1", fake.sent[1][0])
        self.assertIn(b'MAN: "ssdp:discover"', fake.sent[0][0])

    def test_manual_ip_uses_unicast_ssdp_not_guessed_http_port(self):
        fake = FakeSocket([ssdp_packet(self.location)])
        with mock.patch.object(host.socket, "socket", return_value=fake):
            locations = host.ssdp_locations(0.5, target="127.0.0.1")
        with mock.patch.object(host, "ssdp_locations", return_value=locations) as search:
            result = host.handle_request({"action": "addDevice", "address": "127.0.0.1"})
        self.assertTrue(result["ok"])
        search.assert_called_once_with(3.0, target="127.0.0.1")
        self.assertTrue(all(destination == ("127.0.0.1", 1900) for _, destination in fake.sent))


class ValidationTests(unittest.TestCase):
    def test_private_literal_ip_whitelist(self):
        for address in ("10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.1.1", "127.0.0.1", "::1", "fd12::1", "fe80::1"):
            with self.subTest(address=address):
                self.assertTrue(host.local_ip(address))
        for address in ("8.8.8.8", "100.64.0.1", "192.0.2.1", "0.0.0.0", "239.255.255.250", "localhost", "tv.local", "fe80::1%en0"):
            with self.subTest(address=address):
                with self.assertRaises(host.BridgeError):
                    host.local_ip(address)

    def test_device_url_rejects_wan_credentials_hostname_and_port(self):
        for url in ("http://example.test/device", "http://8.8.8.8/device", "http://user:secret@192.168.1.1/device", "file:///tmp/video", "http://192.168.1.1:65536/x", "http://192.168.1.1:0/x", "http://192.168.1.1/x#fragment", "http://127.0.0.1/\nheader"):
            with self.subTest(url=url):
                with self.assertRaises(host.BridgeError):
                    host.validate_local_url(url)

    def test_media_url_rejects_unsupported_schemes_and_credentials(self):
        for url in ("blob:https://example.test/video", "file:///tmp/movie.mp4", "data:video/mp4,aaaa", "ftp://example.test/movie.mp4", "https://user:secret@example.test/movie.mp4", "https://example.test/movie.mp4\r\nHeader:x"):
            with self.subTest(url=url):
                result = host.handle_request({"action": "cast", "location": "http://127.0.0.1/device", "mediaUrl": url})
                self.assertFalse(result["ok"])
                self.assertIn(result["error"]["code"], ("INVALID_URL", "URL_CREDENTIALS"))
        self.assertEqual(host.validate_media_url("https://example.test/movie.mp4?signature=abc"), "https://example.test/movie.mp4?signature=abc")

    def test_xml_forbidden_url_and_title_characters_fail_before_network(self):
        with mock.patch.object(host, "fetch_http", side_effect=AssertionError("network should not run")):
            for character in ("\ufffe", "\uffff", "\ud800"):
                for field, value in (("title", "Video" + character),
                                     ("mediaUrl", "https://example.test/video.mp4?q=" + character)):
                    with self.subTest(character=repr(character), field=field):
                        request = {"action": "cast", "location": "http://127.0.0.1/device",
                                   "mediaUrl": "https://example.test/video.mp4", field: value}
                        result = host.handle_request(request)
                        self.assertFalse(result["ok"])
                        self.assertIn(result["error"]["code"], ("INVALID_REQUEST", "INVALID_URL"))

    def test_malformed_requests_fail_before_network(self):
        requests = [None, [], "ping", {}, {"action": "unknown"}, {"action": 7},
                    {"action": "discover", "timeout": True}, {"action": "discover", "timeout": -1},
                    {"action": "discover", "timeout": float("nan")}, {"action": "discover", "timeout": 9},
                    {"action": "control", "location": "http://127.0.0.1/device", "command": "restart"},
                    {"action": "control", "location": "http://127.0.0.1/device", "command": "seek", "position": -1},
                    {"action": "control", "location": "http://127.0.0.1/device", "command": "seek"},
                    {"action": "cast", "location": "http://127.0.0.1/device", "mediaUrl": "http://example.test/v", "mimeType": "video/mp4\r\nSOAPAction: x"},
                    {"action": "cast", "location": "http://127.0.0.1/device", "mediaUrl": "http://example.test/v", "title": "bad\0title"}]
        with mock.patch.object(host, "fetch_http", side_effect=AssertionError("network should not run")):
            for request in requests:
                with self.subTest(request=request):
                    result = host.handle_request(request)
                    self.assertFalse(result["ok"])
                    self.assertIn("code", result["error"])

    def test_ssdp_ignores_wan_and_cross_host_locations(self):
        fake = FakeSocket([ssdp_packet("http://8.8.8.8/device"), ssdp_packet("http://192.168.1.2/device"), ssdp_packet("http://127.0.0.1/device")])
        with mock.patch.object(host.socket, "socket", return_value=fake):
            self.assertEqual(host.ssdp_locations(0.5), ["http://127.0.0.1/device"])

    def test_missing_unicast_response_includes_url_fallback(self):
        with mock.patch.object(host, "ssdp_locations", return_value=[]) as search:
            result = host.handle_request({"action": "addDevice", "address": "192.168.1.2"})
        self.assertEqual(result["error"]["code"], "DEVICE_NOT_FOUND")
        self.assertIn("full HTTP device-description URL", result["error"]["message"])
        search.assert_called_once_with(3.0, target="192.168.1.2")

    def test_unknown_position_is_null(self):
        for value in (None, "NOT_IMPLEMENTED", "", "1:60:00"):
            self.assertIsNone(host.parse_position(value))
        self.assertEqual(host.parse_position("01:02:03.456"), 3723)

    def test_utf16_entity_declaration_is_rejected(self):
        payload = '<!DOCTYPE root [<!ENTITY test "hello">]><root>&test;</root>'.encode("utf-16")
        with self.assertRaises(host.BridgeError) as context:
            host.parse_xml(payload)
        self.assertEqual(context.exception.code, "INVALID_XML")

    def test_audio_metadata_uses_audio_class(self):
        metadata = ET.fromstring(host.build_metadata("https://example.test/song.mp3", "Song", "audio/mpeg"))
        self.assertEqual(metadata.find("{%s}item/{%s}class" % (host.DIDL_NS, host.UPNP_NS)).text, "object.item.audioItem")


class FrameTests(unittest.TestCase):
    def frame(self, value):
        payload = json.dumps(value).encode("utf-8")
        return struct.pack("=I", len(payload)) + payload

    def test_fragmented_frame_exact_reads(self):
        class PartialReader(io.BytesIO):
            def read(self, size=-1):
                return super().read(min(size, 2))
        self.assertEqual(host.read_message(PartialReader(self.frame({"action": "ping"}))), {"action": "ping"})

    def test_invalid_header_payload_and_json(self):
        cases = [(b"\1", "INVALID_FRAME"), (struct.pack("=I", 0), "INVALID_FRAME"),
                 (struct.pack("=I", host.MAX_INPUT + 1), "INVALID_FRAME"),
                 (struct.pack("=I", 5) + b"{}", "INVALID_FRAME"),
                 (struct.pack("=I", 1) + b"\xff", "INVALID_JSON"),
                 (struct.pack("=I", 3) + b"bad", "INVALID_JSON"),
                 (struct.pack("=I", 3) + b"NaN", "INVALID_JSON")]
        for payload, code in cases:
            with self.subTest(code=code, payload=payload):
                output = io.BytesIO()
                self.assertEqual(host.main(io.BytesIO(payload), output), 0)
                output.seek(0)
                result = host.read_message(output)
                self.assertEqual(result["error"]["code"], code)

    def test_clean_eof_does_not_emit_frame(self):
        output = io.BytesIO()
        self.assertEqual(host.main(io.BytesIO(), output), 0)
        self.assertEqual(output.getvalue(), b"")

    def test_json_null_is_invalid_request_and_not_clean_eof(self):
        output = io.BytesIO()
        self.assertEqual(host.main(io.BytesIO(self.frame(None)), output), 0)
        output.seek(0)
        self.assertEqual(host.read_message(output)["error"]["code"], "INVALID_REQUEST")

    def test_response_limit_emits_small_error(self):
        output = io.BytesIO()
        host.write_message(output, {"value": "x" * host.MAX_OUTPUT})
        output.seek(0)
        self.assertEqual(host.read_message(output)["error"]["code"], "RESPONSE_TOO_LARGE")

    def test_actual_native_host_process_one_request(self):
        process = subprocess.run([sys.executable, str(HELPER / "host.py")],
                                 input=self.frame({"action": "ping"}) + self.frame({"action": "unknown"}),
                                 capture_output=True, timeout=5, check=True)
        output = io.BytesIO(process.stdout)
        response = host.read_message(output)
        self.assertEqual(response, {"ok": True, "version": host.VERSION, "host": "com.lancast.bridge"})
        self.assertEqual(output.read(), b"")
        self.assertEqual(process.stderr, b"")


if __name__ == "__main__":
    unittest.main()
