"""Conservative normalization of axis-aligned wall candidates."""
import json
from pathlib import Path
import math
import shutil

import cv2
from jsonschema import Draft7Validator
from recognizer.walls import SCHEMA


def normalize(data):
    Draft7Validator(SCHEMA).validate(data)
    walls = []
    for source in data['walls']:
        a, b = source['start'], source['end']
        if not all(math.isfinite(v) for v in (*a, *b, source['thickness'])) or (a[0] != b[0] and a[1] != b[1]) or a == b:
            raise ValueError('Expected finite, nonzero axis-aligned walls')
        horizontal = a[1] == b[1]
        axis = 1 if horizontal else 0
        along = 1 - axis
        lo, hi = sorted((a[along], b[along]))
        if lo < 0 or hi >= data['image']['width' if horizontal else 'height'] or not 0 <= a[axis] < data['image']['height' if horizontal else 'width']:
            raise ValueError('Wall outside image')
        walls.append({'axis': a[axis], 'lo': lo, 'hi': hi, 'thickness': source['thickness'], 'horizontal': horizontal, 'sourceIds': [source['id']]})
    # shortcut: merge only near-identical overlapping strokes; revisit with labeled plans.
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(walls):
            for j in range(i + 1, len(walls)):
                b = walls[j]
                overlap = min(a['hi'], b['hi']) - max(a['lo'], b['lo'])
                shortest = min(a['hi'] - a['lo'], b['hi'] - b['lo'])
                if a['horizontal'] == b['horizontal'] and abs(a['axis'] - b['axis']) <= (a['thickness'] + b['thickness']) / 2 and overlap >= .8 * shortest and min(a['hi'] - a['lo'], b['hi'] - b['lo']) / max(a['hi'] - a['lo'], b['hi'] - b['lo']) >= .7:
                    low = min(a['axis'] - a['thickness']/2, b['axis'] - b['thickness']/2)
                    high = max(a['axis'] + a['thickness']/2, b['axis'] + b['thickness']/2)
                    a.update(axis=(low+high)/2, thickness=high-low, lo=min(a['lo'],b['lo']), hi=max(a['hi'],b['hi']))
                    a['sourceIds'].extend(b['sourceIds']); walls.pop(j); changed = True; break
            if changed: break
    nodes = {}
    for h in (w for w in walls if w['horizontal']):
        for v in (w for w in walls if not w['horizontal']):
            x, y = v['axis'], h['axis']
            tolerance = min(h['thickness'], v['thickness']) / 2
            if h['lo'] - tolerance <= x <= h['hi'] + tolerance and v['lo'] - tolerance <= y <= v['hi'] + tolerance:
                # Extend only to a nearby perpendicular intersection, never bridge parallel gaps.
                h['lo'], h['hi'] = min(h['lo'], x), max(h['hi'], x)
                v['lo'], v['hi'] = min(v['lo'], y), max(v['hi'], y)
                nodes.setdefault((x, y), set()).update((id(h), id(v)))
    output = []
    for i, w in enumerate(walls, 1):
        start, end = ([w['lo'], w['axis']], [w['hi'], w['axis']]) if w['horizontal'] else ([w['axis'], w['lo']], [w['axis'], w['hi']])
        output.append({'id': f'n{i:03}', 'start': start, 'end': end, 'thickness': w['thickness'], 'sourceIds': w['sourceIds'], 'status': 'candidate'})
    graph = [{'position': list(point), 'walls': [output[i]['id'] for i, wall in enumerate(walls) if id(wall) in members]} for point, members in nodes.items()]
    return {'version':'1.0', 'kind':'normalized-wall-candidates', 'units':'px', 'scale':data['scale'], 'image':data['image'], 'reviewRequired':True, 'walls':output, 'junctions':graph, 'uncertainties':data['uncertainties'] + ['Merges and junctions are heuristic and require review; gaps are not classified.']}


def run(source, image_path, output):
    source, image_path, output = Path(source), Path(image_path), Path(output)
    if output.exists(): raise FileExistsError(f'Output already exists: {output}')
    data = json.loads(source.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'Invalid number: {value}')))
    result = normalize(data)
    image = cv2.imread(str(image_path))
    if image is None or image.shape[:2] != (data['image']['height'], data['image']['width']):
        raise ValueError('Image is unreadable or dimensions differ from source')
    before, after = image.copy(), image.copy()
    for canvas, items, color in ((before, data['walls'], (0, 190, 255)), (after, result['walls'], (30, 180, 30))):
        for w in items:
            cv2.line(canvas, tuple(round(x) for x in w['start']), tuple(round(x) for x in w['end']), color, 3)
    for n in result['junctions']:
        cv2.circle(after, tuple(round(x) for x in n['position']), 5, (255, 80, 0), -1)
    ok, encoded = cv2.imencode('.png', cv2.hconcat([before, after]))
    if not ok: raise ValueError('Cannot encode overlay')
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / 'walls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        (output / 'comparison.png').write_bytes(encoded.tobytes())
    except BaseException:
        shutil.rmtree(output); raise
    return result
