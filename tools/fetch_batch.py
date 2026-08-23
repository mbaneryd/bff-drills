#!/usr/bin/env python3
"""
Process results from a browser batch fetch and save as Hugo markdown.
Called with the batch result JSON on stdin or as argument.

Run from project root: python3 tools/fetch_batch.py [batch_file.json]
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract_svff import parse_exercise_html, save_exercise

SCRAPE_LIST = Path('sources/svff/_to_scrape.json')


def main():
    if len(sys.argv) > 1:
        data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    else:
        data = json.load(sys.stdin)

    to_scrape = {}
    if SCRAPE_LIST.exists():
        for ex in json.loads(SCRAPE_LIST.read_text(encoding='utf-8')):
            to_scrape[ex['exerciseId']] = ex

    results = data if isinstance(data, list) else [data]
    total = 0

    for r in results:
        eid = r.get('exerciseId')
        if not eid:
            continue

        meta = to_scrape.get(eid, {})
        parsed = parse_exercise_html(
            exercise_id=eid,
            title=r.get('title', meta.get('title', '')),
            topic=meta.get('topic', ''),
            category=meta.get('category', ''),
            exercise_type=meta.get('exerciseType', ''),
            levels=meta.get('levels', {}),
            raw_html=r.get('html', ''),
        )

        save_exercise(parsed)
        total += 1
        print(f"  [{total}] {parsed['title'][:50]}")

    print(f"\n✓ Saved {total} exercises")


if __name__ == '__main__':
    main()
