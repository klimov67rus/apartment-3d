"""Reviewable raster wall candidates, independent from the 3D apartment format."""
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'schema/wall-candidates.schema.json').read_text())


def _bands(mask, min_length, min_thickness):
    """Track long foreground runs across adjacent scanlines, tolerating edge noise."""
    active, finished = [], []
    for row, pixels in enumerate(mask):
        changes = np.diff(np.pad((pixels > 0).astype(np.int8), (1, 1)))
        runs = [(int(a), int(b) - 1) for a, b in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)) if b - a >= min_length]
        following = []
        for start, end in runs:
            matches = [band for band in active if abs(band['starts'][-1] - start) <= min_thickness and abs(band['ends'][-1] - end) <= min_thickness]
            if matches:
                band = min(matches, key=lambda b: abs(b['starts'][-1] - start) + abs(b['ends'][-1] - end))
                active.remove(band)
                band['high'] = row
                band['starts'].append(start)
                band['ends'].append(end)
            else:
                band = {'low': row, 'high': row, 'starts': [start], 'ends': [end]}
            following.append(band)
        finished.extend(active)
        active = following
    finished.extend(active)
    result = []
    for band in finished:
        thickness = band['high'] - band['low'] + 1
        start, end = float(np.median(band['starts'])), float(np.median(band['ends']))
        if min_thickness <= thickness <= min(mask.shape) * .1 and end - start + 1 >= max(min_length, thickness * 2):
            result.append({'start': start, 'end': end, 'axis': (band['low'] + band['high']) / 2, 'thickness': float(thickness)})
    return result


def _merge(bands, tolerance):
    merged = []
    for band in sorted(bands, key=lambda b: (b['axis'], b['start'])):
        # Only near-collinear runs join; door-sized gaps remain unsupported pixels.
        for previous in merged:
            gap = max(previous['start'], band['start']) - min(previous['end'], band['end']) - 1
            if abs(previous['axis'] - band['axis']) <= tolerance / 2 and gap <= tolerance:
                previous['start'] = min(previous['start'], band['start'])
                previous['end'] = max(previous['end'], band['end'])
                previous['thickness'] = max(previous['thickness'], band['thickness'])
                break
        else:
            merged.append(dict(band))
    return merged


def detect_walls(image):
    if image is None or not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 16:
        raise ValueError('Expected a readable BGR image at least 16 × 16 pixels')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    shortest = min(gray.shape)
    min_thickness = max(3, round(shortest * .004)) | 1
    min_length = max(12, round(shortest * .04)) | 1
    threshold, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    settings = {'method': 'otsu-morphology-scanlines-v1', 'threshold': float(threshold), 'minThicknessPx': min_thickness, 'minLengthPx': min_length, 'mergeGapPx': min_thickness}
    if int(gray.max()) - int(gray.min()) < 2:
        return [], settings
    solid = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_thickness, min_thickness)))
    walls = []
    # shortcut: axis-aligned walls only; extend detection before accepting diagonal plans.
    for vertical in (False, True):
        oriented = np.ascontiguousarray(solid.T if vertical else solid)
        lines = cv2.morphologyEx(oriented, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_length, 1)))
        for band in _merge(_bands(lines, min_length, min_thickness), min_thickness):
            start, end = [band['start'], band['axis']], [band['end'], band['axis']]
            if vertical:
                start, end = start[::-1], end[::-1]
            walls.append({'id': f'w{len(walls) + 1:03}', 'start': start, 'end': end, 'thickness': band['thickness'], 'status': 'candidate'})
    return walls, settings


def recognize(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    if not source.is_file():
        raise ValueError(f'Image file not found: {source}')
    try:
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    except cv2.error as exc:
        raise ValueError(f'Cannot decode image: {source}') from exc
    walls, settings = detect_walls(image)
    result = {
        'version': '1.0', 'kind': 'wall-candidates', 'units': 'px',
        'scale': {'status': 'unknown', 'source': 'No reference length supplied'},
        'image': {'file': source.name, 'width': image.shape[1], 'height': image.shape[0]},
        'reviewRequired': True, 'settings': settings, 'walls': walls,
        'uncertainties': [
            'Heuristic candidates, not verified walls; thick furniture may produce false positives.',
            'Only horizontal and vertical thick strokes are detected; thin or diagonal walls may be missing.',
            'Rooms, doors, windows, wall heights and metric scale have not been inferred.',
            'Gaps no wider than mergeGapPx may be joined; wider gaps are not classified as openings.',
        ],
    }
    if not walls:
        result['uncertainties'].append('No wall candidates found; inspect image contrast and line thickness.')
    Draft7Validator(SCHEMA).validate(result)
    overlay = image.copy()
    for wall in walls:
        start = tuple(round(v) for v in wall['start'])
        end = tuple(round(v) for v in wall['end'])
        cv2.line(overlay, start, end, (80, 220, 255), max(2, round(wall['thickness'])), cv2.LINE_AA)
    overlay = cv2.addWeighted(image, .55, overlay, .45, 0)
    for wall in walls:
        start, end = wall['start'], wall['end']
        point = tuple(round((a + b) / 2) for a, b in zip(start, end))
        # Label background keeps candidate IDs legible over furniture and hatching.
        size = cv2.getTextSize(wall['id'], cv2.FONT_HERSHEY_SIMPLEX, .42, 1)[0]
        x = min(max(0, point[0] + 4), max(0, image.shape[1] - size[0] - 4))
        y = min(max(size[1] + 4, point[1] - 4), image.shape[0] - 4)
        cv2.rectangle(overlay, (x, y - size[1] - 2), (x + size[0] + 2, y + 3), (255, 255, 255), -1)
        cv2.putText(overlay, wall['id'], (x + 1, y), cv2.FONT_HERSHEY_SIMPLEX, .42, (20, 80, 140), 1, cv2.LINE_AA)
    ok, encoded = cv2.imencode('.png', overlay)
    if not ok:
        raise ValueError('Cannot encode diagnostic overlay')
    # Claim a fresh directory before writing; never touch an existing result or source.
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / 'walls.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        (output / 'overlay.png').write_bytes(encoded.tobytes())
    except BaseException:
        shutil.rmtree(output)
        raise
    return result
