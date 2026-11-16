"""Contract checks runnable with the system jsonschema, without OpenCV/Shapely."""
import copy
import json
from pathlib import Path
import unittest
from jsonschema import Draft7Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]

class ContractTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / 'schema/apartment.schema.json').read_text())
        self.data = json.loads((ROOT / 'viewer/public/examples/apartment.json').read_text())
        self.validator = Draft7Validator(self.schema)

    def test_schema_and_fixture(self):
        Draft7Validator.check_schema(self.schema)
        self.validator.validate(self.data)

    def test_unknown_scale(self):
        self.data['units'] = 'px'
        self.data['scale']['status'] = 'unknown'
        self.validator.validate(self.data)
        self.data['units'] = 'm'
        with self.assertRaises(ValidationError):
            self.validator.validate(self.data)

    def test_negative_dimensions_and_unknown_properties(self):
        for key, value in [('height', -2), ('thickness', 0), ('typo', 3)]:
            data = copy.deepcopy(self.data)
            data['walls'][0][key] = value
            with self.assertRaises(ValidationError):
                self.validator.validate(data)

if __name__ == '__main__':
    unittest.main()
