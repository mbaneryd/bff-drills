#!/usr/bin/env python3
"""
Process batch JSON results from SvFF browser scraping.
Reads batch result files and saves exercises as Hugo markdown.

Run from project root: python3 tools/process_batch.py
"""
import json, re, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract_svff import parse_exercise_html, save_exercise

BATCH_DIR = Path('sources/svff/_batches')
SCRAPE_LIST = Path('sources/svff/_to_scrape.json')


def main():
    if not BATCH_DIR.exists():
        print(f"No batch directory found at {BATCH_DIR}")
        return

    batch_files = sorted(BATCH_DIR.glob('_batch*.json'))
    if not batch_files:
        print("No batch result files found")
        return

    to_scrape = {}
    if SCRAPE_LIST.exists():
        for ex in json.loads(SCRAPE_LIST.read_text(encoding='utf-8')):
            to_scrape[ex['exerciseId']] = ex

    total = 0
    for bf in batch_files:
        print(f"\nProcessing {bf.name}...")
        results = json.loads(bf.read_text(encoding='utf-8'))

        for r in results:
            eid = r.get('exerciseId')
            if not eid:
                continue

            meta = to_scrape.get(eid, {})
            data = parse_exercise_html(
                exercise_id=eid,
                title=r.get('title', meta.get('title', '')),
                topic=meta.get('topic', ''),
                category=meta.get('category', ''),
                exercise_type=meta.get('exerciseType', ''),
                levels=meta.get('levels', {}),
                raw_html=r.get('html', ''),
            )

            save_exercise(data)
            total += 1
            print(f"  [{total}] {data['title'][:50]}")

    print(f"\n✓ Processed {total} exercises from {len(batch_files)} batch files")


if __name__ == '__main__':
    main()
