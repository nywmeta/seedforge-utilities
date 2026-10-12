"""Private downloaded-file interface checks using temporary files and loopback sockets."""
from email.message import Message
import http.client
import io
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch


HELPER = Path(__file__).resolve().parents[1] / 'helper'
sys.path.insert(0, str(HELPER))
import file_cast


TV_LOCATION = 'http://192.168.1.50:1234/device.xml'


def headers(values):
    result = Message()
    for name, value in values:
        result[name] = value
    return result


class RecordingStream(io.BytesIO):
    def __init__(self, payload):
        super().__init__(payload)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


class FakeSession:
    def __init__(self, upload, tv_ip, tv_port, touch):
        self.upload = upload
        self.tv_ip = tv_ip
        self.tv_port = tv_port
        self.url = 'http://192.168.1.2:40501/fake-token/video.mp4'
        self.closed = False

    def close(self):
        self.closed = True


class AppCase(unittest.TestCase):
    def setUp(self):
        # No power-management subprocesses or physical device calls in tests.
        for name in ('keep_awake', 'release_awake'):
            replacement = patch.object(file_cast.App, name)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.bridge = Mock(return_value={'ok': True})
        self.sessions = []

        def session_factory(*args):
            session = FakeSession(*args)
            self.sessions.append(session)
            return session

        self.app = file_cast.App(bridge=self.bridge, session_factory=session_factory)
        self.addCleanup(self.app.close)
        self.app.origin = 'http://127.0.0.1:40500'

    def upload(self, payload=b'episode data', filename='episode.mp4'):
        return self.app.receive_upload(io.BytesIO(payload), len(payload), filename)

    def cast(self, upload):
        return self.app.command('cast', {'location': TV_LOCATION, 'uploadId': upload['uploadId']})


class RequestBoundaryTests(AppCase):
    def test_passive_state_read_does_not_extend_idle_lifetime(self):
        handler_type = file_cast.control_handler(self.app)
        handler = handler_type.__new__(handler_type)
        handler.path = '/' + self.app.token + '/api/state'
        handler.headers = headers([('Host', '127.0.0.1:40500'), ('X-LAN-Cast-CSRF', self.app.csrf)])
        handler.client_address = ('127.0.0.1', 12345)
        handler.json_response = Mock()
        self.app.last_activity = 123.0
        handler.do_GET()
        handler.json_response.assert_called_once_with(200, self.app.state())
        self.assertEqual(self.app.last_activity, 123.0)
        self.bridge.assert_not_called()

    def valid_headers(self):
        return [('Host', '127.0.0.1:40500'), ('Origin', self.app.origin),
                ('X-LAN-Cast-CSRF', self.app.csrf)]

    def test_only_exact_loopback_host_origin_and_csrf_can_mutate(self):
        self.assertTrue(file_cast.protected_request(self.app, headers(self.valid_headers()), '127.0.0.1', True, True))
        invalid = [
            [('Host', 'localhost:40500'), *self.valid_headers()[1:]],
            [('Host', 'evil.example:40500'), *self.valid_headers()[1:]],
            [('Host', '127.0.0.1:40500'), ('Origin', 'https://evil.example'), ('X-LAN-Cast-CSRF', self.app.csrf)],
            [('Host', '127.0.0.1:40500'), ('Origin', 'null'), ('X-LAN-Cast-CSRF', self.app.csrf)],
            [('Host', '127.0.0.1:40500'), ('X-LAN-Cast-CSRF', self.app.csrf)],
            [('Host', '127.0.0.1:40500'), ('Origin', self.app.origin)],
            [('Host', '127.0.0.1:40500'), ('Origin', self.app.origin), ('X-LAN-Cast-CSRF', 'wrong')],
            [*self.valid_headers(), ('Host', '127.0.0.1:40500')],
            [*self.valid_headers(), ('Origin', self.app.origin)],
            [*self.valid_headers(), ('X-LAN-Cast-CSRF', self.app.csrf)],
        ]
        for value in invalid:
            with self.subTest(headers=value):
                self.assertFalse(file_cast.protected_request(self.app, headers(value), '127.0.0.1', True, True))
        for address in ('127.0.0.2', '::1', '192.168.1.50'):
            self.assertFalse(file_cast.protected_request(self.app, headers(self.valid_headers()), address, True, True))

    def test_navigation_without_origin_is_allowed_but_cross_origin_get_is_rejected(self):
        self.assertTrue(file_cast.protected_request(self.app, headers([('Host', '127.0.0.1:40500')]), '127.0.0.1'))
        self.assertFalse(file_cast.protected_request(self.app, headers([
            ('Host', '127.0.0.1:40500'), ('Origin', 'https://evil.example')]), '127.0.0.1'))

    def test_upload_length_is_bounded_and_unambiguous(self):
        self.assertEqual(file_cast.content_length(headers([('Content-Length', '7')]), 8), 7)
        for values in ([], [('Content-Length', '0')], [('Content-Length', '9')],
                       [('Content-Length', '-1')], [('Content-Length', '1.5')],
                       [('Content-Length', '7'), ('Content-Length', '7')],
                       [('Content-Length', '7'), ('Transfer-Encoding', 'chunked')]):
            with self.subTest(headers=values), self.assertRaises(file_cast.FileCastError):
                file_cast.content_length(headers(values), 8)

    def test_tv_targets_are_private_literal_ipv4_only(self):
        for address in ('10.1.2.3', '172.16.0.2', '192.168.1.50'):
            self.assertEqual(file_cast.private_ipv4(address), address)
        for address in ('127.0.0.1', '169.254.1.2', '8.8.8.8', '::1', 'tv.local', '192.168.1.50:1234'):
            with self.subTest(address=address), self.assertRaises(file_cast.FileCastError):
                file_cast.private_ipv4(address)
        for location in ('http://127.0.0.1/device.xml', 'http://8.8.8.8/device.xml'):
            with self.subTest(location=location), self.assertRaises((file_cast.FileCastError, file_cast.host.BridgeError)):
                self.app.command('cast', {'location': location, 'uploadId': 'unused'})
        self.bridge.assert_not_called()


class UploadLifecycleTests(AppCase):
    def test_upload_reads_bounded_chunks_and_exposes_no_local_path(self):
        payload = b'a' * (file_cast.CHUNK_SIZE * 2 + 17)
        stream = RecordingStream(payload)
        result = self.app.receive_upload(stream, len(payload), 'An%20episode.mp4')
        self.assertTrue(result['ok'])
        self.assertEqual(self.app.staged.path.read_bytes(), payload)
        self.assertEqual(result['name'], 'An episode.mp4')
        self.assertEqual(stream.read_sizes, [file_cast.CHUNK_SIZE, file_cast.CHUNK_SIZE, 17])
        self.assertNotIn('path', result)
        self.assertNotIn(str(self.app.staged.path), json.dumps(self.app.state()))
        if os.name != 'nt':
            self.assertEqual(self.app.staged.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(self.app.temporary.name).stat().st_mode & 0o777, 0o700)

    def test_invalid_filename_or_oversized_upload_is_rejected_before_reading(self):
        for filename in ('../episode.mp4', 'folder%2Fepisode.mp4', 'episode.exe', 'bad%00.mp4'):
            stream = RecordingStream(b'video')
            with self.subTest(filename=filename), self.assertRaises(file_cast.FileCastError):
                self.app.receive_upload(stream, 5, filename)
            self.assertEqual(stream.read_sizes, [])
        stream = RecordingStream(b'video')
        with self.assertRaises(file_cast.FileCastError):
            self.app.receive_upload(stream, file_cast.MAX_UPLOAD + 1, 'episode.mp4')
        self.assertEqual(stream.read_sizes, [])
        self.assertEqual(list(Path(self.app.temporary.name).iterdir()), [])

    def test_incomplete_upload_deletes_partial_copy_and_preserves_previous_file(self):
        first = self.upload(b'first video')
        previous = self.app.staged.path
        with self.assertRaisesRegex(file_cast.FileCastError, 'whole video'):
            self.app.receive_upload(io.BytesIO(b'partial'), 100, 'second.mp4')
        self.assertEqual(self.app.staged.id, first['uploadId'])
        self.assertEqual(list(Path(self.app.temporary.name).iterdir()), [previous])
        self.assertTrue(previous.is_file())
        self.assertTrue(self.upload(b'new video')['ok'])  # Failed uploads release the lock.

    def test_io_failure_deletes_partial_copy_and_releases_upload_lock(self):
        stream = Mock()
        stream.read.side_effect = [b'partial', OSError('simulated disk/input failure')]
        with self.assertRaises(OSError):
            self.app.receive_upload(stream, 100, 'episode.mp4')
        self.assertEqual(list(Path(self.app.temporary.name).iterdir()), [])
        self.assertIsNone(self.app.staged)
        self.assertTrue(self.upload()['ok'])

    def test_simultaneous_upload_is_rejected_without_writing(self):
        self.app.upload_lock.acquire()
        try:
            with self.assertRaisesRegex(file_cast.FileCastError, 'still being copied'):
                self.upload()
        finally:
            self.app.upload_lock.release()
        self.assertEqual(list(Path(self.app.temporary.name).iterdir()), [])

    def test_replacing_staged_file_deletes_it_but_preserves_active_video(self):
        first = self.upload(b'first')
        first_path = self.app.staged.path
        self.cast(first)
        self.upload(b'second', 'second.mp4')
        second_path = self.app.staged.path
        self.upload(b'third', 'third.mp4')
        self.assertTrue(first_path.exists())
        self.assertFalse(second_path.exists())
        self.assertFalse(self.sessions[0].closed)

    def test_successful_replacement_closes_old_session_and_deletes_old_copy(self):
        first = self.upload(b'first')
        first_path = self.app.staged.path
        self.cast(first)
        second = self.upload(b'second', 'second.mp4')
        self.cast(second)
        self.assertTrue(self.sessions[0].closed)
        self.assertFalse(first_path.exists())
        self.assertIs(self.app.active, self.sessions[1])
        self.assertFalse(self.sessions[1].closed)

    def test_rejected_replacement_closes_candidate_and_preserves_active_session(self):
        first = self.upload(b'first')
        first_path = self.app.staged.path
        self.cast(first)
        second = self.upload(b'second', 'second.mp4')
        self.bridge.return_value = {'ok': False, 'error': {'message': 'TV rejected playback.'}}
        self.assertFalse(self.cast(second)['ok'])
        self.assertIs(self.app.active, self.sessions[0])
        self.assertFalse(self.sessions[0].closed)
        self.assertTrue(self.sessions[1].closed)
        self.assertTrue(first_path.exists())
        self.assertTrue(self.app.staged.path.exists())

    def test_exception_during_replacement_also_closes_candidate(self):
        first = self.upload(b'first')
        self.cast(first)
        second = self.upload(b'second', 'second.mp4')
        self.bridge.side_effect = OSError('simulated bridge failure')
        with self.assertRaises(OSError):
            self.cast(second)
        self.assertTrue(self.sessions[1].closed)
        self.assertIs(self.app.active, self.sessions[0])
        self.assertFalse(self.sessions[0].closed)

    def test_stop_deletes_old_active_copy_when_a_different_video_is_staged(self):
        first = self.upload(b'first')
        first_path = self.app.staged.path
        self.cast(first)
        self.upload(b'second', 'second.mp4')
        staged_path = self.app.staged.path
        self.assertTrue(self.app.command('stop', {})['ok'])
        self.assertTrue(self.sessions[0].closed)
        self.assertIsNone(self.app.active)
        self.assertFalse(first_path.exists())
        self.assertTrue(staged_path.exists())

    def test_failed_stop_preserves_serving_session(self):
        uploaded = self.upload()
        self.cast(uploaded)
        self.bridge.return_value = {'ok': False}
        self.assertFalse(self.app.command('stop', {})['ok'])
        self.assertIs(self.app.active, self.sessions[0])
        self.assertFalse(self.sessions[0].closed)
        self.assertTrue(self.app.staged.path.exists())

    def test_close_removes_private_copies_and_active_session(self):
        first = self.upload()
        self.cast(first)
        temporary = Path(self.app.temporary.name)
        self.app.close()
        self.assertTrue(self.sessions[0].closed)
        self.assertFalse(temporary.exists())


class ControlHttpTests(AppCase):
    def setUp(self):
        super().setUp()
        self.server = file_cast.LimitedServer(('127.0.0.1', 0), file_cast.control_handler(self.app), '127.0.0.1')
        self.app.origin = 'http://127.0.0.1:%s' % self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.prefix = '/' + self.app.token + '/'

    def close_server(self):
        self.server.close_clients()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, payload=b'', extra=()):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for name, value in [('Host', self.app.origin.split('://')[1]), *extra]:
                connection.putheader(name, value)
            connection.endheaders(payload)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post_headers(self, payload):
        return [('Origin', self.app.origin), ('X-LAN-Cast-CSRF', self.app.csrf),
                ('Content-Type', 'application/json'), ('Content-Length', str(len(payload)))]

    def test_ui_has_token_path_and_frame_referrer_csp_protections(self):
        status, values, payload = self.request('GET', self.prefix)
        self.assertEqual(status, 200)
        self.assertIn(self.app.csrf, payload.decode())
        self.assertIn("frame-ancestors 'none'", values['Content-Security-Policy'])
        self.assertIn("default-src 'none'", values['Content-Security-Policy'])
        self.assertEqual(values['X-Frame-Options'], 'DENY')
        self.assertEqual(values['Referrer-Policy'], 'no-referrer')
        self.assertEqual(values['Cache-Control'], 'no-store')
        self.assertEqual(self.request('GET', '/unknown-token/')[0], 404)

    def test_post_rejects_cross_origin_missing_csrf_and_duplicate_host_before_bridge(self):
        payload = b'{}'
        cases = [
            [('Content-Length', '2'), ('Content-Type', 'application/json')],
            [('Origin', 'https://evil.example'), ('X-LAN-Cast-CSRF', self.app.csrf), ('Content-Length', '2')],
            [('Origin', self.app.origin), ('Content-Length', '2')],
            [*self.post_headers(payload), ('Host', 'evil.example')],
            [*self.post_headers(payload), ('X-LAN-Cast-CSRF', self.app.csrf)],
        ]
        for extra in cases:
            with self.subTest(headers=extra):
                self.assertEqual(self.request('POST', self.prefix + 'api/discover', payload, extra)[0], 403)
        self.bridge.assert_not_called()

    def test_valid_api_request_reaches_only_the_injected_bridge(self):
        self.bridge.return_value = {'ok': True, 'devices': []}
        payload = b'{}'
        status, _, result = self.request('POST', self.prefix + 'api/discover', payload, self.post_headers(payload))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(result)['ok'])
        self.bridge.assert_called_once_with({'action': 'discover', 'timeout': 4.0})

    def test_http_upload_enforces_length_before_reading_and_valid_upload_is_private(self):
        extra = [('Origin', self.app.origin), ('X-LAN-Cast-CSRF', self.app.csrf),
                 ('X-Filename', 'episode.mp4'), ('Content-Length', str(file_cast.MAX_UPLOAD + 1))]
        self.assertEqual(self.request('POST', self.prefix + 'api/upload', extra=extra)[0], 400)
        self.assertIsNone(self.app.staged)
        payload = b'file bytes'
        extra[-1] = ('Content-Length', str(len(payload)))
        status, _, response = self.request('POST', self.prefix + 'api/upload', payload, extra)
        self.assertEqual(status, 200)
        self.assertEqual(self.app.staged.path.read_bytes(), payload)
        self.assertNotIn('path', json.loads(response))

    def test_state_requires_csrf_even_for_same_origin_get(self):
        self.assertEqual(self.request('GET', self.prefix + 'api/state')[0], 404)
        self.assertEqual(self.request('GET', self.prefix + 'api/state', extra=[('X-LAN-Cast-CSRF', self.app.csrf)])[0], 200)


class MediaHttpTests(unittest.TestCase):
    def setUp(self):
        self.temporary = file_cast.tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / 'episode.mp4'
        self.payload = b'0123456789abcdef'
        path.write_bytes(self.payload)
        self.upload = file_cast.Upload('test', path, 'episode.mp4', len(self.payload), 'video/mp4')
        self.token_path = '/simulated-tv-token/video.mp4'
        self.stop = threading.Event()
        self.touch = Mock()
        self.server = file_cast.LimitedServer(('127.0.0.1', 0),
            file_cast.media_handler(self.upload, None, self.token_path, self.stop, self.touch), '127.0.0.1')
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.close_clients()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method='GET', path=None, ranges=()):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.putrequest(method, path or self.token_path)
            for value in ranges:
                connection.putheader('Range', value)
            connection.endheaders()
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_only_selected_tv_ip_can_connect(self):
        self.assertTrue(self.server.verify_request(None, ('127.0.0.1', 1)))
        for address in ('127.0.0.2', '192.168.1.50', '8.8.8.8'):
            self.assertFalse(self.server.verify_request(None, (address, 1)))
        self.server.allowed_ip = '192.168.1.50'
        with self.assertRaises((http.client.HTTPException, OSError)):
            self.request()
        self.touch.assert_not_called()

    def test_full_and_head_responses_preserve_length_and_format(self):
        status, values, payload = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(payload, self.payload)
        self.assertEqual(values['Content-Type'], 'video/mp4')
        self.assertEqual(values['Accept-Ranges'], 'bytes')
        status, values, payload = self.request('HEAD')
        self.assertEqual(status, 200)
        self.assertEqual(values['Content-Length'], str(len(self.payload)))
        self.assertEqual(payload, b'')

    def test_single_suffix_open_ended_and_clamped_ranges(self):
        for header, start, end in [('bytes=2-5', 2, 5), ('bytes=-3', 13, 15),
                                   ('bytes=12-', 12, 15), ('bytes=14-99', 14, 15)]:
            with self.subTest(range=header):
                status, values, payload = self.request(ranges=[header])
                self.assertEqual(status, 206)
                self.assertEqual(payload, self.payload[start:end + 1])
                self.assertEqual(values['Content-Range'], 'bytes %s-%s/16' % (start, end))
                self.assertEqual(values['Content-Length'], str(end - start + 1))

    def test_unsatisfiable_and_multiple_ranges_are_rejected(self):
        for ranges in [['bytes=99-'], ['bytes=5-2'], ['bytes=-0'], ['bytes=0-1,4-5'],
                       ['bytes=0-1', 'bytes=2-3'], ['items=0-2']]:
            with self.subTest(ranges=ranges):
                status, values, payload = self.request(ranges=ranges)
                self.assertEqual(status, 416)
                self.assertEqual(values['Content-Range'], 'bytes */16')
                self.assertEqual(payload, b'')

    def test_wrong_token_query_and_stopped_session_reveal_no_media(self):
        for path in ('/wrong/video.mp4', self.token_path + '?extra=1', '/..' + self.token_path):
            with self.subTest(path=path):
                status, _, payload = self.request(path=path)
                self.assertEqual(status, 404)
                self.assertEqual(payload, b'')
        self.stop.set()
        self.assertEqual(self.request()[0], 404)
        self.touch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
