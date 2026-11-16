import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from jsonschema import Draft7Validator

from recognizer.walls import detect_walls, recognize

ROOT = Path(__file__).resolve().parents[1]


def blank():
    return np.full((400, 500, 3), 255, dtype=np.uint8)


def has_wall(walls, start, end, tolerance=4):
    return any(np.linalg.norm(np.array(w['start']) - start) <= tolerance
               and np.linalg.norm(np.array(w['end']) - end) <= tolerance for w in walls)


class WallRecognitionTest(unittest.TestCase):
    def test_coordinates_thickness_and_furniture(self):
        image = blank()
        cv2.rectangle(image, (50, 50), (450, 61), (100, 100, 100), -1)
        cv2.rectangle(image, (50, 50), (61, 350), (100, 100, 100), -1)
        cv2.rectangle(image, (120, 130), (350, 220), (60, 60, 60), 1)
        cv2.putText(image, '17.2', (180, 300), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 0), 1)
        walls, settings = detect_walls(image)
        self.assertEqual(len(walls), 2)
        self.assertTrue(has_wall(walls, [50, 55.5], [450, 55.5]))
        self.assertTrue(has_wall(walls, [55.5, 50], [55.5, 350]))
        self.assertTrue(all(abs(w['thickness'] - 12) <= 1 for w in walls))
        self.assertGreater(settings['minThicknessPx'], 0)

    def test_short_thick_pier(self):
        image = blank()
        cv2.rectangle(image, (100, 100), (129, 160), (0, 0, 0), -1)
        walls, _ = detect_walls(image)
        self.assertEqual(len(walls), 1)
        self.assertTrue(has_wall(walls, [114.5, 100], [114.5, 160]))

    def test_door_gap_not_closed(self):
        image = blank()
        cv2.rectangle(image, (40, 100), (200, 111), (0, 0, 0), -1)
        cv2.rectangle(image, (260, 100), (450, 111), (0, 0, 0), -1)
        walls, _ = detect_walls(image)
        self.assertEqual(len(walls), 2)
        self.assertTrue(all(not (w['start'][0] < 230 < w['end'][0]) for w in walls))

    def test_collinear_small_break_merged(self):
        image = blank()
        cv2.rectangle(image, (40, 100), (200, 111), (0, 0, 0), -1)
        cv2.rectangle(image, (203, 100), (450, 111), (0, 0, 0), -1)
        walls, _ = detect_walls(image)
        self.assertEqual(len(walls), 1)
        self.assertTrue(has_wall(walls, [40, 105.5], [450, 105.5]))

    def test_resized_plan(self):
        image = blank()
        cv2.rectangle(image, (50, 50), (450, 61), (90, 90, 90), -1)
        first, _ = detect_walls(image)
        resized, _ = detect_walls(cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
        self.assertEqual(len(first), len(resized))
        np.testing.assert_allclose(np.array(resized[0]['start']) / 2, first[0]['start'], atol=1)
        np.testing.assert_allclose(np.array(resized[0]['end']) / 2, first[0]['end'], atol=1)
        self.assertAlmostEqual(resized[0]['thickness'] / 2, first[0]['thickness'], delta=1)

    def test_blank_and_bad_image(self):
        self.assertEqual(detect_walls(blank())[0], [])
        for image in (None, np.empty((0, 0, 3), dtype=np.uint8), np.zeros((10, 10), dtype=np.uint8)):
            with self.assertRaises(ValueError):
                detect_walls(image)

    def test_outputs_and_no_overwrite(self):
        schema = json.loads((ROOT / 'schema/wall-candidates.schema.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'source.png'
            image = blank()
            cv2.rectangle(image, (50, 50), (450, 61), (100, 100, 100), -1)
            cv2.imwrite(str(source), image)
            original = source.read_bytes()
            output = base / 'result'
            result = recognize(source, output)
            Draft7Validator(schema).validate(result)
            self.assertEqual(result['units'], 'px')
            self.assertEqual(result['scale']['status'], 'unknown')
            self.assertEqual(result['walls'][0]['status'], 'candidate')
            self.assertNotIn('height', result['walls'][0])
            self.assertEqual(cv2.imread(str(output / 'overlay.png')).shape, image.shape)
            before = (output / 'walls.json').read_bytes()
            with self.assertRaises(FileExistsError):
                recognize(source, output)
            self.assertEqual((output / 'walls.json').read_bytes(), before)
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(ValueError):
                recognize(base / 'missing.png', base / 'missing-output')
            self.assertFalse((base / 'missing-output').exists())

    def test_failed_write_cleans_new_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'source.png'
            cv2.imwrite(str(source), blank())
            original = source.read_bytes()
            output = base / 'output'
            with patch.object(Path, 'write_bytes', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    recognize(source, output)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), original)

    def test_cli_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'not-image.txt'
            source.write_text('not an image')
            result = subprocess.run([sys.executable, '-m', 'recognizer.cli', 'recognize', str(source), '--output', str(base / 'output')], capture_output=True, text=True, cwd=ROOT)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Error:', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse((base / 'output').exists())


if __name__ == '__main__':
    unittest.main()
