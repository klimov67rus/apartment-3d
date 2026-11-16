import copy
import json
from pathlib import Path
import unittest
from recognizer.normalize import normalize

class NormalizeTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path('artifacts/plan-walls/walls.json').read_text())
        self.data['walls'] = []

    def wall(self, id, start, end, thickness=10):
        return {'id':id, 'start':start, 'end':end, 'thickness':thickness, 'status':'candidate'}

    def test_duplicates_junction_and_door_gap(self):
        self.data['walls'] = [self.wall('w1',[10,50],[100,50]), self.wall('w2',[12,55],[99,55]), self.wall('w3',[100,52],[100,120]), self.wall('w4',[130,50],[180,50])]
        before = copy.deepcopy(self.data)
        result = normalize(self.data)
        self.assertEqual(self.data, before)
        self.assertEqual(len(result['walls']), 3)
        self.assertEqual(set(result['walls'][0]['sourceIds']), {'w1','w2'})
        self.assertEqual(len(result['junctions']), 1)
        self.assertEqual(len(result['junctions'][0]['walls']), 2)
        self.assertTrue(all(not (w['start'][0] < 115 < w['end'][0]) for w in result['walls']))
        self.assertEqual(result['scale']['status'], 'unknown')

    def test_invalid_diagonal(self):
        self.data['walls'] = [self.wall('w1',[10,10],[20,20])]
        with self.assertRaises(ValueError): normalize(self.data)
