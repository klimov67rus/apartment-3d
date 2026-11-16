import unittest
import cv2
import numpy as np
from recognizer.openings import detect

class OpeningTest(unittest.TestCase):
    def setUp(self):
        self.image=np.full((400,500,3),255,np.uint8)
        self.data={'kind':'normalized-wall-candidates','units':'px','scale':{'status':'unknown','source':'test'},'image':{'width':500,'height':400,'file':'test.png'},'walls':[]}
    def wall(self,id,a,b):
        return {'id':id,'start':a,'end':b,'thickness':10}
    def test_empty(self):
        self.assertEqual(detect(self.data,self.image)['openings'],[])
    def test_door_evidence_precedes_exterior(self):
        self.data['walls']=[self.wall('a',[10,50],[100,50]),self.wall('b',[160,50],[250,50]),self.wall('c',[10,50],[10,250]),self.wall('d',[250,50],[250,250]),self.wall('e',[10,250],[250,250])]
        cv2.line(self.image,(100,50),(140,95),(0,0,0),2)
        result=detect(self.data,self.image)['openings']
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['kind'],'door')
        self.assertTrue(result[0]['reviewRequired'])
    def test_window_and_occupied_gap(self):
        self.data['walls']=[self.wall('a',[10,50],[100,50]),self.wall('b',[160,50],[250,50]),self.wall('c',[10,50],[10,250]),self.wall('d',[250,50],[250,250]),self.wall('e',[10,250],[250,250])]
        self.assertEqual(detect(self.data,self.image)['openings'][0]['kind'],'window')
        self.data['walls'].append(self.wall('f',[110,50],[150,50]))
        self.assertFalse(any(o['start']==[100,50] and o['end']==[160,50] for o in detect(self.data,self.image)['openings']))
    def test_bad_image(self):
        with self.assertRaises(ValueError): detect(self.data,None)

    def test_parallel_window_lines_classify_interior_hull_gap(self):
        self.data['walls']=[self.wall('a',[10,50],[100,50]),self.wall('b',[160,50],[250,50])]
        cv2.line(self.image,(100,46),(160,46),(0,0,0),1)
        cv2.line(self.image,(100,54),(160,54),(0,0,0),1)
        result=detect(self.data,self.image)['openings']
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['kind'],'window')
        self.assertEqual(result[0]['evidence'],'parallel lines in opening')

    def test_single_line_is_not_sufficient_for_window_evidence(self):
        self.data['walls']=[self.wall('a',[10,50],[100,50]),self.wall('b',[160,50],[250,50])]
        cv2.line(self.image,(100,50),(160,50),(0,0,0),1)
        self.assertEqual(detect(self.data,self.image)['openings'][0]['kind'],'unknown')

    def test_wide_window_gap_requires_parallel_lines(self):
        self.data['walls']=[self.wall('a',[10,50],[100,50]),self.wall('b',[220,50],[300,50])]
        self.assertEqual(detect(self.data,self.image)['openings'],[])
        cv2.line(self.image,(100,45),(220,45),(0,0,0),1)
        cv2.line(self.image,(100,55),(220,55),(0,0,0),1)
        result=detect(self.data,self.image)['openings']
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['kind'],'window')

    def test_wide_window_symbol_without_matching_gap_pair(self):
        self.data['walls']=[self.wall('left',[50,50],[50,300]),self.wall('right',[450,50],[450,300]),self.wall('top',[50,50],[450,50]),self.wall('a',[50,300],[100,300]),self.wall('b',[300,300],[450,300])]
        cv2.line(self.image,(100,295),(300,295),(0,0,0),1)
        cv2.line(self.image,(100,305),(300,305),(0,0,0),1)
        result=detect(self.data,self.image)['openings']
        self.assertTrue(any(o['kind']=='window' and o['evidence']=='parallel exterior symbol' for o in result))

    def test_single_exterior_line_does_not_create_window(self):
        self.data['walls']=[self.wall('left',[50,50],[50,300]),self.wall('right',[450,50],[450,300]),self.wall('top',[50,50],[450,50]),self.wall('a',[50,300],[100,300]),self.wall('b',[300,300],[450,300])]
        cv2.line(self.image,(100,300),(300,300),(0,0,0),1)
        self.assertFalse(any(o['evidence']=='parallel exterior symbol' for o in detect(self.data,self.image)['openings']))

    def test_exterior_symbol_does_not_duplicate_gap_candidate(self):
        self.data['walls']=[self.wall('left',[50,50],[50,300]),self.wall('right',[450,50],[450,300]),self.wall('top',[50,50],[450,50]),self.wall('a',[50,300],[120,300]),self.wall('b',[240,300],[450,300])]
        cv2.line(self.image,(120,295),(240,295),(0,0,0),1)
        cv2.line(self.image,(120,305),(240,305),(0,0,0),1)
        windows=[o for o in detect(self.data,self.image)['openings'] if o['kind']=='window']
        self.assertEqual(len(windows),1)
