import unittest
from recognizer.benchmark import evaluate, match_rooms, match_segments
from shapely.geometry import Polygon

class BenchmarkTest(unittest.TestCase):
    def test_complete_match_and_missing_window(self):
        ref={'rooms':[{'name':'room','polygon':[[0,0],[10,0],[10,10],[0,10]]}], 'sampledWalls':[[[0,0],[10,0]]], 'sampledWindows':[[[0,0],[10,0]]]}
        candidates={'walls':[{'start':[0,0],'end':[10,0]}], 'openings':[]}
        scene={'rooms':[{'polygon':[[0,0],[10,0],[10,10],[0,10]]}]}
        result=evaluate(ref,candidates,scene,{'metersPerPixel':1})
        self.assertEqual(result['sampledWallCoverage'],1)
        self.assertEqual(result['sampledWindowCoverage'],0)
        self.assertEqual(result['roomBestIoU']['room'],1)

    def test_one_detection_cannot_match_two_rooms(self):
        box=Polygon([(0,0),(10,0),(10,10),(0,10)])
        self.assertEqual(len(match_rooms([box,box],[box])),1)

    def test_matching_reassigns_to_maximize_count(self):
        a=Polygon([(0,0),(10,0),(10,10),(0,10)])
        b=Polygon([(0,0),(6,0),(6,10),(0,10)])
        matches=match_rooms([a,b],[a,b])
        self.assertEqual(len(matches),2)
        self.assertEqual(len({m['detectedIndex'] for m in matches}),2)

    def test_segment_matching_is_one_to_one_and_rejects_crossing(self):
        expected=[[[0,0],[100,0]],[[0,2],[100,2]]]
        detected=[[[0,0],[100,0]],[[50,-50],[50,50]]]
        self.assertEqual(len(match_segments(expected,detected,tolerance=5)),1)
        self.assertEqual(match_segments([[[0,0],[100,0]]],[[[300,0],[400,0]]]),[])

    def test_complete_metrics_penalize_false_positives_and_missing(self):
        ref={'rooms':[{'name':'room','polygon':[[0,0],[100,0],[100,100],[0,100]]}],
             'sampledWalls':[], 'sampledWindows':[],
             'walls':[[[0,0],[100,0]]], 'windows':[[[0,0],[100,0]]]}
        candidates={'walls':[{'start':[0,0],'end':[100,0]},{'start':[0,100],'end':[100,100]}],
                    'openings':[{'kind':'window','start':[0,0],'end':[100,0]}, {'kind':'window','start':[0,100],'end':[100,100]}]}
        scene={'rooms':[{'polygon':[[0,0],[100,0],[100,100],[0,100]]}, {'polygon':[[200,200],[300,200],[300,300],[200,300]]}]}
        result=evaluate(ref,candidates,scene,{'metersPerPixel':1})
        self.assertAlmostEqual(result['wallLengthPrecision'],.5)
        self.assertEqual(result['wallLengthRecall'],1)
        self.assertEqual(result['windows']['truePositive'],1)
        self.assertEqual(result['windows']['falsePositive'],1)
        self.assertEqual(result['rooms']['falsePositive'],1)

    def test_split_wall_is_counted_by_length(self):
        ref={'rooms':[], 'sampledWalls':[], 'sampledWindows':[], 'walls':[[[0,0],[100,0]]], 'windows':[]}
        candidates={'walls':[{'start':[0,0],'end':[50,0]},{'start':[50,0],'end':[100,0]}], 'openings':[]}
        result=evaluate(ref,candidates,{'rooms':[]},{'metersPerPixel':1})
        self.assertEqual(result['wallLengthRecall'],1)
        self.assertEqual(result['wallLengthPrecision'],1)

    def test_regression_gate_checks_precision_and_false_positives(self):
        from recognizer.compare_benchmarks import regressions
        baseline={'wallLengthPrecision':.9,'wallLengthRecall':.8,'rooms':{'falsePositive':1,'falseNegative':2},'windows':{'falsePositive':0,'falseNegative':1}}
        current={'wallLengthPrecision':.7,'wallLengthRecall':.85,'rooms':{'falsePositive':2,'falseNegative':1},'windows':{'falsePositive':0,'falseNegative':1}}
        failures=regressions(baseline,current)
        self.assertTrue(any('wallLengthPrecision' in f for f in failures))
        self.assertTrue(any('rooms.falsePositive' in f for f in failures))
        self.assertEqual(regressions(baseline,baseline),[])

    def test_annotations_are_valid_and_match_source_images(self):
        import hashlib
        import json
        from pathlib import Path
        from shapely.geometry import LineString, Polygon
        root=Path('tests/fixtures/floorplan-benchmark')
        for name in ('plan','1-floor','2-floor-1'):
            data=json.loads((root/f'{name}.json').read_text())
            source=Path(data.get('imagePath',str(Path('examples/floor-plans')/data['image'])))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),data['imageSha256'])
            width,height=data['imageSize']
            for room in data['rooms']:
                self.assertTrue(Polygon(room['polygon']).is_valid,room['name'])
                self.assertGreater(Polygon(room['polygon']).area,0)
            for segment in data['walls']+data['windows']:
                self.assertGreater(LineString(segment).length,0)
                self.assertTrue(all(0<=x<width and 0<=y<height for x,y in segment))

    def test_current_pipeline_does_not_regress_on_annotated_plans(self):
        from recognizer.check_regressions import check_all
        self.assertEqual(check_all(),[])
