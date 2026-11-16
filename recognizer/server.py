"""Loopback-only image recognition service for the local viewer."""
import json
import os

os.environ['OPENCV_IO_MAX_IMAGE_PIXELS'] = '24000000'

import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from recognizer.pipeline import generate

MAX_BYTES = 15 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/generate':
            self.reply(404, {'error': 'Неизвестный адрес'}); return
        origin = self.headers.get('Origin')
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1'):
                self.reply(403, {'error': 'Недопустимый источник запроса'}); return
        if self.headers.get_content_type() not in ('image/jpeg', 'image/png'):
            self.reply(415, {'error': 'Поддерживаются только JPG и PNG'}); return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.reply(400, {'error': 'Некорректный размер файла'}); return
        if length <= 0 or length > MAX_BYTES:
            self.reply(413, {'error': 'Размер файла должен быть от 1 байта до 15 МиБ'}); return
        try:
            payload = self.rfile.read(length)
            if len(payload) != length: raise ValueError('Файл передан не полностью')
            if not (payload.startswith(b'\xff\xd8\xff') or payload.startswith(b'\x89PNG\r\n\x1a\n')):
                raise ValueError('Файл не является JPG или PNG')
            with TemporaryDirectory(prefix='apartment-upload-') as directory:
                base = Path(directory)
                source = base / ('plan.png' if payload.startswith(b'\x89PNG') else 'plan.jpg')
                source.write_bytes(payload)
                result = generate(source, base / 'result')
                if result['scale']['status'] == 'unknown':
                    self.reply(422, {'error': 'Не удалось оценить масштаб: найдено недостаточно согласующихся дверных проёмов.'}); return
                walls = json.loads((base / 'result/walls-pixels.json').read_text())
                scale = json.loads((base / 'result/scale.json').read_text())
                self.reply(200, {'apartment': result, 'image': walls['image'], 'metersPerPixel': scale['metersPerPixel']})
        except (ValueError, OSError, ArithmeticError, cv2.error) as error:
            self.reply(422, {'error': str(error)})
        except Exception:
            self.reply(500, {'error': 'Ошибка обработки изображения'})


def main():
    server = HTTPServer(('127.0.0.1', 8765), Handler)
    print('Распознавание: http://127.0.0.1:8765', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
