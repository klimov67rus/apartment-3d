import json
from http.client import HTTPConnection
from pathlib import Path
import threading
import unittest
from http.server import HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from recognizer.server import Handler, MAX_BYTES


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/api/generate'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def request(self, data, content_type='image/jpeg', origin='http://127.0.0.1:5173'):
        request = Request(self.url, data=data, headers={'Content-Type': content_type, 'Origin': origin}, method='POST')
        try:
            with urlopen(request, timeout=20) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_actual_plan_generates_scene(self):
        status, data = self.request(Path('plan.jpg').read_bytes())
        self.assertEqual(status, 200)
        self.assertEqual(data['apartment']['scale']['status'], 'estimated')
        self.assertEqual(data['image']['width'], 1052)
        self.assertGreater(data['metersPerPixel'], 0)

    def test_rejects_untrusted_origin_and_non_image(self):
        self.assertEqual(self.request(b'abc', origin='https://example.com')[0], 403)
        self.assertEqual(self.request(b'abc', content_type='text/plain')[0], 415)
        self.assertEqual(self.request(b'abc')[0], 422)
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.putrequest('POST', '/api/generate')
        connection.putheader('Content-Type', 'image/jpeg')
        connection.putheader('Content-Length', str(MAX_BYTES + 1))
        connection.endheaders()
        self.assertEqual(connection.getresponse().status, 413)
        connection.close()
