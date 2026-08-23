#!/usr/bin/env python3
"""
Migrate exercise JSON data to Hugo markdown.
Reads JSON exercise/session files from sources/ and regenerates
Hugo markdown content in content/.

Run from project root: python3 tools/migrate_to_hugo.py

This is useful for re-generating all markdown from the JSON manifests
without re-extracting from PDFs.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import write_exercise_md, write_session_md


def migrate_source(source_name, json_path, out_dir, image_prefix):
    """Migrate exercises from a JSON manifest file."""
    if not json_path.exists():
        print(f"  Skipping {source_name}: {json_path} not found")
        return 0

    exercises = json.loads(json_path.read_text(encoding='utf-8'))
    out_dir.mkdir(parents=True, exist_ok=True)

    for ex in exercises:
        if ex.get('image') and not ex['image'].startswith(image_prefix):
            ex['image'] = f"{image_prefix}/{ex['image']}"
        write_exercise_md(out_dir / f"{ex['exerciseId']}.md", ex)

    return len(exercises)


def migrate_sessions(source_name, json_path, out_dir):
    """Migrate sessions from a JSON manifest file."""
    if not json_path.exists():
        print(f"  Skipping {source_name} sessions: {json_path} not found")
        return 0

    sessions = json.loads(json_path.read_text(encoding='utf-8'))
    out_dir.mkdir(parents=True, exist_ok=True)

    for s in sessions:
        sid = s.get('sessionId', '')
        session_data = {
            'sessionId': sid,
            'title': s.get('title', sid),
            'source': s.get('source', ''),
            'category': s.get('category', ''),
            'topic': s.get('topic', ''),
            'tema': s.get('tema', ''),
            'fokus': s.get('fokus', ''),
            'ageGroup': s.get('ageGroup', ''),
            'gameFormat': s.get('gameFormat', ''),
            'exerciseCount': s.get('exerciseCount', len(s.get('exerciseIds', []))),
            'totalMinutes': s.get('totalMinutes', 0),
            'sourceFile': s.get('sourceFile', ''),
            'sourceUrl': s.get('url', ''),
            'exerciseIds': s.get('exerciseIds', []),
        }

        # Rich exercise data with minutes
        if s.get('exercises'):
            session_data['exercises'] = [
                {
                    'id': ex.get('exerciseId', ex.get('id', '')),
                    'name': ex.get('exerciseName', ex.get('name', '')),
                    'minutes': ex.get('minutes'),
                }
                for ex in s['exercises']
            ]

        write_session_md(out_dir / f"{sid}.md", session_data)

    return len(sessions)


def main():
    print("Migrating JSON data to Hugo markdown...\n")

    # Exercises
    total_ex = 0
    total_ex += migrate_source('SvFF', Path('sources/svff/_exercises.json'),
                                Path('content/exercises/svff'), 'svff')
    total_ex += migrate_source('JSK', Path('sources/jsk/_exercises.json'),
                                Path('content/exercises/jsk'), 'jsk')
    total_ex += migrate_source('SIK', Path('sources/sik/_exercises.json'),
                                Path('content/exercises/sik'), 'sik')
    print(f"\n✓ {total_ex} exercises migrated")

    # Sessions
    total_sess = 0
    total_sess += migrate_sessions('SvFF', Path('sources/svff/_sessions.json'),
                                    Path('content/sessions/svff'))
    total_sess += migrate_sessions('JSK', Path('sources/jsk/_sessions.json'),
                                    Path('content/sessions/jsk'))
    total_sess += migrate_sessions('SIK', Path('sources/sik/_sessions.json'),
                                    Path('content/sessions/sik'))
    print(f"✓ {total_sess} sessions migrated")


if __name__ == '__main__':
    main()
