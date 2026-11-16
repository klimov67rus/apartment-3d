import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from recognizer.cli import calibrate, validate

SAMPLE = Path(__file__).resolve().parents[1] / 'viewer/public/examples/apartment.json'

class CalibrationTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(SAMPLE.read_text())

    def test_sample(self):
        validate(self.data)

    def test_calibration(self):
        self.data['units'] = 'px'
        self.data['scale']['status'] = 'unknown'
        before = copy.deepcopy(self.data)
        result = calibrate(self.data, 100, 2)
        self.assertEqual(result['walls'][0]['end'], [.16, 0])
        self.assertEqual(result['units'], 'm')
        self.assertEqual(self.data, before)
        for value in (0, -1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                calibrate(self.data, value, 2)

    def test_bad_reference(self):
        self.data['openings'][0]['wallId'] = 'missing'
        with self.assertRaises(ValueError):
            validate(self.data)

    def test_no_overwrite(self):
        import sys
        self.data['units'] = 'px'
        self.data['scale']['status'] = 'unknown'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'input.json'
            content = json.dumps(self.data)
            path.write_text(content)
            run = subprocess.run([sys.executable, '-m', 'recognizer.cli', 'calibrate', str(path), '--reference-px', '100', '--meters', '2', '--output', str(path)], capture_output=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn(b'File exists', run.stderr)
            self.assertEqual(path.read_text(), content)

if __name__ == '__main__':
    unittest.main()
