import argparse
import hashlib
import json
from pathlib import Path
import sys

from .compare import compare
from .render import render
from .review import review


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare two text documents and write an evidence-linked report.')
    parser.add_argument('old', type=Path)
    parser.add_argument('new', type=Path)
    parser.add_argument('--out', type=Path, default=Path('reports/latest'))
    parser.add_argument('--live', action='store_true', help='Send changed clauses to OpenAI for optional explanations')
    args = parser.parse_args(argv)
    try:
        paths = [args.old, args.new]
        # Bound disk reads as well as the subsequent parser input.
        for path in paths:
            if path.stat().st_size > 1_000_000:
                raise ValueError('Input files must be smaller than 1 MB')
        contents = [path.read_text(encoding='utf-8-sig') for path in paths]
        report = compare(*contents)
        report['documents'] = {side: {'name':path.name, 'sha256':hashlib.sha256(text.encode()).hexdigest()}
                               for side, path, text in zip(('old','new'), paths, contents)}
        args.out.mkdir(parents=True, exist_ok=True)
        outputs = [args.out/'report.json', args.out/'index.html']
        if any(out.resolve() in {path.resolve() for path in paths} for out in outputs):
            raise ValueError('Output paths must not overwrite an input document')
    except (ValueError, OSError, UnicodeError) as error:
        parser.error(str(error))
    review_failed = False
    if args.live:
        try:
            report['review'] = review(report['changes'])
        except (RuntimeError, ValueError, OSError) as error:
            # Preserve the deterministic report even when the provider is unavailable.
            report['review'] = {'mode':'failed', 'notes':[], 'rejected':[], 'error':str(error)}
            review_failed = True
    (args.out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (args.out/'index.html').write_text(render(report), encoding='utf-8')
    print(json.dumps({'counts':report['counts'], 'review':report['review']['mode'],
                      'html':str((args.out/'index.html').resolve()),
                      'json':str((args.out/'report.json').resolve())}, indent=2))
    if review_failed:
        print(report['review']['error'], file=sys.stderr)
        return 2
    return 0
