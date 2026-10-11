"""Checks for the short-lived native host's long-lived local window launcher."""
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

HELPER = Path(__file__).resolve().parents[1] / "helper"
sys.path.insert(0, str(HELPER))
import companion
import host

URL = "http://127.0.0.1:49876/" + "a" * 43 + "/"


class CompanionTests(unittest.TestCase):
    def test_only_tokenized_literal_loopback_interfaces_are_opened(self):
        self.assertEqual(companion.interface_parts(URL).port, 49876)
        for url in (URL.replace("127.0.0.1", "localhost"), URL.replace("http:", "https:"),
                    URL.replace("127.0.0.1", "192.168.1.5"), URL + "?x=y", URL + "#x",
                    URL.replace("127.0.0.1", "user@127.0.0.1"),
                    URL.replace("49876", "65536"), URL.replace("a" * 43, "short"),
                    URL.replace("a" * 43, "a" * 43 + "/nested"),
                    URL.replace(":49876", ""), URL.replace(":49876", ":049876")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                companion.interface_parts(url)

    def test_reuses_healthy_window_without_launching_a_second_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = {"url": URL, "pid": 123, "version": companion.VERSION}
            with patch.object(companion, "reusable", return_value=value), patch.object(companion.subprocess, "Popen") as launch:
                self.assertEqual(companion.open_interface(temporary), URL)
                launch.assert_not_called()
            self.assertEqual(list(Path(temporary).iterdir()), [])

    @unittest.skipUnless(os.name != "nt", "Unix file ownership and mode")
    def test_private_info_refuses_symlinks_and_world_readable_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "record.json"
            record.write_text(json.dumps({"url": URL, "pid": 123, "version": companion.VERSION}))
            record.chmod(0o600)
            self.assertEqual(companion.read_info(record)["url"], URL)
            record.chmod(0o644)
            with self.assertRaises(ValueError):
                companion.read_info(record)
            record.chmod(0o600)
            link = Path(temporary) / "interface.json"
            link.symlink_to(record)
            with self.assertRaises(ValueError):
                companion.reusable(link)
            self.assertTrue(link.is_symlink())
            self.assertTrue(record.is_file())

    def test_health_must_match_process_and_version(self):
        expected = {"url": URL, "pid": 123, "version": companion.VERSION}
        for reply, result in (({"ok": True, "pid": 123, "version": companion.VERSION}, True),
                              ({"ok": True, "pid": 456, "version": companion.VERSION}, False),
                              ({"ok": True, "pid": 123, "version": "old"}, False)):
            connection = Mock()
            connection.getresponse.return_value.status = 200
            connection.getresponse.return_value.read.return_value = json.dumps(reply).encode()
            with patch.object(companion.http.client, "HTTPConnection", return_value=connection):
                self.assertEqual(companion.healthy(expected), result)
            connection.close.assert_called_once()

    def test_failed_child_does_not_leave_startup_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            child = Mock()
            child.poll.return_value = 1
            with patch.object(companion, "reusable", return_value=None), patch.object(companion.subprocess, "Popen", return_value=child):
                with self.assertRaisesRegex(ValueError, "could not start"):
                    companion.open_interface(temporary)
            self.assertFalse((Path(temporary) / "starting.lock").exists())

    def test_native_action_writes_one_framed_response_only(self):
        message = json.dumps({"action": "open_file_cast"}).encode()
        output = io.BytesIO()
        with patch.object(companion, "open_interface", return_value=URL):
            self.assertEqual(host.main(io.BytesIO(struct.pack("=I", len(message)) + message), output), 0)
        encoded = output.getvalue()
        length = struct.unpack("=I", encoded[:4])[0]
        self.assertEqual(length, len(encoded) - 4)
        self.assertEqual(json.loads(encoded[4:]), {"ok": True, "url": URL})


if __name__ == "__main__":
    unittest.main()
