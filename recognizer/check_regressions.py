"""Run the automatic pipeline against all annotated regression fixtures."""
import hashlib
import json
from pathlib import Path
import tempfile

from recognizer.benchmark import evaluate
from recognizer.compare_benchmarks import regressions
from recognizer.pipeline import generate

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures/floorplan-benchmark'


def check_all():
    failures=[]
    with tempfile.TemporaryDirectory(prefix='apartment-benchmark-') as tmp:
        for name in ('plan','1-floor','2-floor-1'):
            reference=json.loads((FIXTURES/f'{name}.json').read_text())
            source=ROOT/reference.get('imagePath',str(Path('examples/floor-plans')/reference['image']))
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=reference['imageSha256']:
                failures.append(f'{name}: source image differs from reference'); continue
            output=Path(tmp)/name
            try:
                scene=generate(source,output)
                if scene['scale']['status']=='unknown':
                    failures.append(f'{name}: no estimated scale or preview'); continue
                walls=json.loads((output/'walls-pixels.json').read_text())
                openings=json.loads((output/'openings-pixels.json').read_text())
                scale=json.loads((output/'scale.json').read_text())
                current=evaluate(reference,{'walls':walls['walls'],'openings':openings['openings']},scene,scale)
                baseline=json.loads((FIXTURES/f'{name}-baseline.json').read_text())
                failures.extend(f'{name}: {failure}' for failure in regressions(baseline,current))
            except (ValueError,OSError,ArithmeticError) as exc:
                failures.append(f'{name}: {exc}')
    return failures


def main():
    failures=check_all()
    if failures:
        print('\n'.join(failures))
        raise SystemExit(1)
    print('No measured regression on 3 annotated plans')

if __name__=='__main__': main()
