"""Compare benchmark metrics and report regressions without changing the MVP pipeline."""
import argparse
import json
from pathlib import Path


def regressions(baseline, current, tolerance=.02):
    failures=[]
    for key in ('wallLengthPrecision','wallLengthRecall'):
        before,after=baseline[key],current[key]
        if before is not None and (after is None or after < before-tolerance):
            failures.append(f'{key}: {before} -> {after}')
    for category in ('rooms','windows'):
        for key in ('falsePositive','falseNegative'):
            before,after=baseline[category][key],current[category][key]
            if after>before:
                failures.append(f'{category}.{key}: {before} -> {after}')
    return failures


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path)
    parser.add_argument('current',type=Path)
    args=parser.parse_args()
    before=json.loads(args.baseline.read_text());after=json.loads(args.current.read_text())
    failures=regressions(before,after)
    if failures:
        print('\n'.join(failures))
        raise SystemExit(1)
    print('No measured regression')

if __name__=='__main__': main()
