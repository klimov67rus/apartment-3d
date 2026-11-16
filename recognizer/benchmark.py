"""Approximate annotated regression benchmark; never used by the generator."""
import argparse
import json
import hashlib
from pathlib import Path
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


def match_rooms(expected_rooms, detected_rooms, threshold=.5):
    """Maximum-cardinality one-to-one matching for room polygons above an IoU threshold."""
    scores = [[a.intersection(b).area / a.union(b).area if a.is_valid and b.is_valid and a.union(b).area else 0 for b in detected_rooms] for a in expected_rooms]
    assigned = {}
    def assign(expected, visited):
        for detected in sorted(range(len(detected_rooms)), key=lambda i: scores[expected][i], reverse=True):
            if detected in visited or scores[expected][detected] < threshold:
                continue
            visited.add(detected)
            if detected not in assigned or assign(assigned[detected], visited):
                assigned[detected] = expected
                return True
        return False
    for expected in range(len(expected_rooms)):
        assign(expected, set())
    return [{'referenceIndex': expected, 'detectedIndex': detected, 'iou': scores[expected][detected]} for detected, expected in sorted(assigned.items(), key=lambda pair: pair[1])]


def match_segments(reference, detected, tolerance=25, minimum_overlap=.5):
    """Match collinear line segments one-to-one by overlap with a tolerance corridor."""
    scores=[]
    for expected in reference:
        a=LineString(expected)
        row=[]
        for actual in detected:
            b=LineString(actual)
            if not a.length or not b.length:
                row.append(0); continue
            av=(expected[1][0]-expected[0][0],expected[1][1]-expected[0][1])
            bv=(actual[1][0]-actual[0][0],actual[1][1]-actual[0][1])
            parallel=abs(av[0]*bv[0]+av[1]*bv[1])/(a.length*b.length)
            row.append(min(a.intersection(b.buffer(tolerance)).length/a.length, b.intersection(a.buffer(tolerance)).length/b.length) if parallel >= .95 else 0)
        scores.append(row)
    assigned={}
    def visit(i,seen):
        for j in sorted(range(len(detected)),key=lambda j:scores[i][j],reverse=True):
            if j in seen or scores[i][j]<minimum_overlap: continue
            seen.add(j)
            if j not in assigned or visit(assigned[j],seen):
                assigned[j]=i
                return True
        return False
    for i in range(len(reference)): visit(i,set())
    return [{'referenceIndex':i,'detectedIndex':j,'overlap':scores[i][j]} for j,i in sorted(assigned.items(),key=lambda pair:pair[1])]


def evaluate(reference, candidates, scene, scale):
    factor=scale['metersPerPixel']
    detected_walls=[LineString([w['start'],w['end']]) for w in candidates['walls']]
    predicted_rooms=[Polygon([[x/factor,y/factor] for x,y in room['polygon']]) for room in scene['rooms']]
    detected_windows=[LineString([o['start'],o['end']]) for o in candidates['openings'] if o['kind']=='window']
    def sample_recall(samples, detected, tolerance):
        if not samples: return None
        coverage=unary_union([line.buffer(tolerance) for line in detected])
        # Samples are incomplete: false positives cannot be measured from them.
        return sum(LineString(p).intersection(coverage).length for p in samples)/sum(LineString(p).length for p in samples)
    room_scores=[]
    for room in reference['rooms']:
        expected=Polygon(room['polygon'])
        room_scores.append(max((expected.intersection(actual).area/expected.union(actual).area for actual in predicted_rooms if actual.is_valid),default=0))
    matches=match_rooms([Polygon(r['polygon']) for r in reference['rooms']], predicted_rooms)
    reference_windows=reference.get('windows',reference['sampledWindows'])
    window_matches=match_segments(reference_windows, [[o['start'],o['end']] for o in candidates['openings'] if o['kind']=='window'])
    result={'windowOneToOneMatches':window_matches, 'unmatchedSampledWindows':len(reference_windows)-len(window_matches), 'unmatchedDetectedWindows':len(detected_windows)-len(window_matches), 'roomOneToOneMatches':matches, 'unmatchedReferenceRooms':len(reference['rooms'])-len(matches), 'unmatchedDetectedRooms':len(predicted_rooms)-len(matches), 'sampledWallCoverage':sample_recall(reference['sampledWalls'],detected_walls,20), 'sampledWindowCoverage':sample_recall(reference['sampledWindows'],detected_windows,25), 'roomBestIoU':dict(zip((r['name'] for r in reference['rooms']),room_scores))}
    if 'walls' not in reference or 'windows' not in reference:
        result['warning']='Partial annotation: unmatched detections are not necessarily false positives.'
        return result
    def coverage(lines, other, tolerance):
        union=unary_union(lines)
        if union.is_empty: return None
        return union.intersection(unary_union([line.buffer(tolerance) for line in other])).length/union.length
    reference_walls=[LineString(p) for p in reference['walls']]
    result['wallLengthPrecision']=coverage(detected_walls,reference_walls,20)
    result['wallLengthRecall']=coverage(reference_walls,detected_walls,20)
    def counts(matched, expected, detected):
        return {'truePositive':matched,'falsePositive':detected-matched,'falseNegative':expected-matched}
    result['windows']=counts(len(window_matches),len(reference_windows),len(detected_windows))
    result['rooms']=counts(len(matches),len(reference['rooms']),len(predicted_rooms))
    result['warning']='Reference is hand-annotated and approximate; wall metrics use union length within 20 px, window matches use 25 px and 50% overlap, room IoU threshold is 0.5.'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('reference',type=Path);parser.add_argument('result',type=Path);args=parser.parse_args()
    def read(path): return json.loads(path.read_text())
    ref=read(args.reference);walls=read(args.result/'walls-pixels.json');openings=read(args.result/'openings-pixels.json');scene=read(args.result/'apartment-preview.json');scale=read(args.result/'scale.json')
    if ref['image'] != walls['image']['file']: parser.error('Reference and result refer to different images')
    if 'imageSize' in ref and ref['imageSize'] != [walls['image']['width'], walls['image']['height']]: parser.error('Image dimensions differ from reference')
    if 'imageSha256' in ref:
        source=Path(ref.get('imagePath',str(Path('examples/floor-plans')/ref['image'])))
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=ref['imageSha256']: parser.error('Source image differs from annotated reference')
    print(json.dumps(evaluate(ref,{'walls':walls['walls'],'openings':openings['openings']},scene,scale),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
