"""Independent image recognition, JSON validation and calibration. Does not import the viewer."""
import argparse
import copy
import json
import math
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / 'schema/apartment.schema.json').read_text())


def validate(data):
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Non-finite coordinate')
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        if isinstance(value, list):
            for item in value:
                finite(item)
    finite(data)
    Draft7Validator(SCHEMA).validate(data)
    ids = [o['id'] for k in ('walls', 'rooms', 'openings', 'furniture') for o in data[k]]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate IDs')
    walls = {w['id']: w for w in data['walls']}
    for w in walls.values():
        if math.dist(w['start'], w['end']) < 1e-6:
            raise ValueError('Zero length wall')
    for o in data['openings']:
        w = walls.get(o['wallId'])
        if not w or o['offset'] + o['width'] > math.dist(w['start'], w['end']) + 1e-8 or o['bottom'] + o['height'] > w['height'] + 1e-8:
            raise ValueError('Opening outside wall')
        if o['kind'] == 'door' and o['bottom'] != 0:
            raise ValueError('Door must start at floor')
        for b in data['openings']:
            if b is not o and b['wallId'] == o['wallId'] and o['offset'] < b['offset'] + b['width'] and b['offset'] < o['offset'] + o['width'] and o['bottom'] < b['bottom'] + b['height'] and b['bottom'] < o['bottom'] + o['height']:
                raise ValueError('Overlapping openings')
    from shapely.geometry import Polygon
    for r in data['rooms']:
        polygon = Polygon(r['polygon'])
        if not polygon.is_valid or polygon.area <= 1e-8:
            raise ValueError('Invalid room polygon')
    for f in data['furniture']:
        if f['modelId'] not in data['models']:
            raise ValueError('Unknown furniture model')
    return data


def calibrate(data, reference_units, meters):
    validate(data)
    if data['units'] != 'px' or data['scale']['status'] != 'unknown':
        raise ValueError('Calibration requires unknown pixel scale')
    if not all(math.isfinite(v) and v > 0 for v in (reference_units, meters)):
        raise ValueError('Reference lengths must be finite and positive')
    result = copy.deepcopy(data)
    factor = meters / reference_units
    for w in result['walls']:
        for key in ('start', 'end'):
            w[key] = [v * factor for v in w[key]]
        for key in ('height', 'thickness'):
            w[key] *= factor
    for r in result['rooms']:
        r['polygon'] = [[v * factor for v in p] for p in r['polygon']]
    for o in result['openings']:
        for key in ('offset', 'width', 'bottom', 'height'):
            o[key] *= factor
    for f in result['furniture']:
        f['position'] = [v * factor for v in f['position']]
    result['units'] = 'm'
    result['scale'] = {'status': 'known', 'source': f'User reference: {reference_units:g} px = {meters:g} m'}
    result['uncertainties'].append('Scale calibrated; wall heights, thicknesses and opening dimensions still require verification')
    return validate(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'calibrate', 'recognize', 'normalize', 'openings', 'generate'])
    parser.add_argument('input', type=Path)
    parser.add_argument('--reference-px', type=float)
    parser.add_argument('--meters', type=float)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    if args.command in ('normalize', 'openings') and (args.output is None or args.image is None):
        parser.error(f'{args.command} requires --image and --output (new directory)')
    if args.command in ('recognize', 'generate') and args.output is None:
        parser.error(f'{args.command} requires --output (new directory)')
    try:
        if args.command == 'generate':
            from recognizer.pipeline import generate
            result = generate(args.input, args.output)
            if result['scale']['status'] == 'unknown':
                print("OK: масштаб неизвестен; сохранены пиксельные кандидаты, 3D-превью не создано")
            else:
                print(f"OK: {len(result['walls'])} walls, {len(result['rooms'])} rooms, {len(result['openings'])} openings")
            return
        if args.command == 'openings':
            from recognizer.openings import run
            result = run(args.input, args.image, args.output)
            print(f"OK: {len(result['openings'])} opening candidates")
            return
        if args.command == 'normalize':
            from recognizer.normalize import run
            result = run(args.input, args.image, args.output)
            print(f"OK: {len(result['walls'])} walls, {len(result['junctions'])} junctions")
            return
        if args.command == 'recognize':
            from recognizer.walls import recognize
            result = recognize(args.input, args.output)
            print(f"OK: {len(result['walls'])} wall candidates; review {args.output / 'overlay.png'}")
            return
        data = validate(json.loads(args.input.read_text(), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(f'Non-finite number: {s}'))))
        if args.command == 'calibrate':
            if args.reference_px is None or args.meters is None or args.output is None:
                parser.error('calibrate requires --reference-px, --meters and --output')
            result = calibrate(data, args.reference_px, args.meters)
            # Exclusive creation protects both source and previous correction files.
            with args.output.open('x') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write('\n')
        print('OK')
    except (ValueError, OSError, ArithmeticError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    except Exception as exc:
        from jsonschema import ValidationError
        if isinstance(exc, ValidationError):
            parser.exit(1, f'Invalid JSON: {exc.message}\n')
        raise


if __name__ == '__main__':
    main()
