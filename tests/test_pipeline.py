import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from recognizer.pipeline import generate, estimate_scale
from recognizer.cli import validate

class PipelineTest(unittest.TestCase):
    def test_automatic_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); image=np.full((400,500,3),255,np.uint8)
            cv2.rectangle(image,(50,50),(450,350),(0,0,0),12)
            source=base/'plan.png';cv2.imwrite(str(source),image)
            original=source.read_bytes();output=base/'result'
            scene=generate(source,output)
            self.assertEqual(scene['scale']['status'],'unknown')
            self.assertFalse((output/'apartment-preview.json').exists())
            self.assertEqual(json.loads((output/'walls-pixels.json').read_text())['scale']['status'],'unknown')
            self.assertGreater(len(json.loads((output/'walls-pixels.json').read_text())['walls']),0)
            with self.assertRaises(FileExistsError): generate(source,output)
            self.assertEqual(source.read_bytes(),original)
    def test_estimated_scene_is_generated_automatically(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); image=np.full((400,500,3),255,np.uint8)
            cv2.rectangle(image,(50,50),(450,350),(0,0,0),12)
            source=base/'plan.png';cv2.imwrite(str(source),image)
            candidates={'openings':[{'id':'o1','kind':'door','start':[100,50],'end':[200,50]}, {'id':'o2','kind':'door','start':[250,50],'end':[350,50]}]}
            with patch('recognizer.pipeline.detect',return_value=candidates):
                scene=generate(source,base/'result')
            validate(scene)
            self.assertEqual(scene['scale']['status'],'estimated')
            self.assertAlmostEqual(json.loads((base/'result'/'scale.json').read_text())['metersPerPixel'],.008)
            self.assertEqual(len(scene['openings']),2)

    def test_door_scale_and_outlier(self):
        def door(width): return {'kind':'door','start':[0,0],'end':[width,0]}
        self.assertIsNone(estimate_scale([door(100)]))
        self.assertIsNone(estimate_scale([door(100),door(200)]))
        result=estimate_scale([door(100),door(102),door(300)])
        self.assertAlmostEqual(result['metersPerPixel'], .8/101)
        self.assertEqual(result['usedDoorWidthsPixels'], [100,102])
        scaled=estimate_scale([door(200),door(204),door(600)])
        self.assertAlmostEqual(scaled['metersPerPixel'],result['metersPerPixel']/2)

    def test_empty_image_does_not_leave_output(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); source=base/'blank.png';cv2.imwrite(str(source),np.full((100,100,3),255,np.uint8))
            with self.assertRaises(ValueError): generate(source,base/'output')
            self.assertFalse((base/'output').exists())
