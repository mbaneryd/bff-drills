#!/usr/bin/env python3
"""
Shared utilities for exercise extraction scripts.
All paths are relative to the project root (bff-drills/).
Run scripts from the project root: python3 tools/extract_sik.py
"""
import re
from pathlib import Path

PROJECT_ROOT = Path.cwd()

CONTENT_EXERCISES = PROJECT_ROOT / 'content' / 'exercises'
CONTENT_SESSIONS = PROJECT_ROOT / 'content' / 'sessions'
STATIC_IMAGES = PROJECT_ROOT / 'static' / 'images'
SOURCES = PROJECT_ROOT / 'sources'


def yaml_str(value):
    """Quote a string for YAML frontmatter if it contains special chars."""
    if value is None:
        return '""'
    s = str(value)
    if not s:
        return '""'
    if any(c in s for c in ':{}[]&*?|>!%@`,"\'#') or s.startswith('-') or s.startswith(' '):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return '"' + s + '"'


def write_exercise_md(path, exercise):
    """Write an exercise as a Hugo markdown file with YAML frontmatter."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ['---']
    lines.append(f'title: {yaml_str(exercise.get("title", ""))}')
    lines.append(f'exerciseId: {yaml_str(exercise.get("exerciseId", ""))}')
    lines.append(f'source: {yaml_str(exercise.get("source", ""))}')

    for field in ['category', 'exerciseType', 'topic', 'tema',
                  'ageGroup', 'gameFormat', 'duration', 'areaSize',
                  'sourceFile', 'sourceUrl']:
        val = exercise.get(field)
        if val:
            lines.append(f'{field}: {yaml_str(val)}')

    if exercise.get('sourcePage'):
        lines.append(f'sourcePage: {exercise["sourcePage"]}')

    if exercise.get('exerciseNum'):
        lines.append(f'exerciseNum: {exercise["exerciseNum"]}')

    if exercise.get('videoUrl'):
        lines.append(f'videoUrl: {yaml_str(exercise["videoUrl"])}')
    if exercise.get('videoThumb'):
        lines.append(f'videoThumb: {yaml_str(exercise["videoThumb"])}')

    # Levels
    levels = exercise.get('levels', {})
    if levels:
        lines.append('levels:')
        for k in ['3v3', '5v5', '7v7', '9v9', '11v11']:
            v = levels.get(k, False)
            lines.append(f'  "{k}": {str(v).lower()}')

    # Image
    if exercise.get('image'):
        lines.append(f'image: {yaml_str(exercise["image"])}')

    # Player skills (list)
    if exercise.get('playerSkills'):
        lines.append('playerSkills:')
        for skill in exercise['playerSkills']:
            lines.append(f'  - {yaml_str(skill)}')

    lines.append('---')

    # Markdown body
    body_parts = []

    what = exercise.get('what')
    if what:
        body_parts.append(f'## Vad?\n\n{what}')

    why = exercise.get('why')
    if why:
        body_parts.append(f'## Varför?\n\n{why}')

    how = exercise.get('how')
    if how:
        body_parts.append(f'## Hur?\n\n{how}')

    org = exercise.get('organization')
    if org:
        body_parts.append(f'## Organisation\n\n{org}')

    instr = exercise.get('instructions')
    if instr:
        body_parts.append(f'## Anvisningar\n\n{instr}')

    progs = exercise.get('progressions', [])
    if progs:
        items = '\n'.join(f'- {p}' for p in progs)
        body_parts.append(f'## Progressioner\n\n{items}')

    body = '\n\n'.join(body_parts) + '\n' if body_parts else ''
    content = '\n'.join(lines) + '\n' + body
    path.write_text(content, encoding='utf-8')


def write_session_md(path, session):
    """Write a training session as a Hugo markdown file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ['---']
    lines.append(f'title: {yaml_str(session.get("title", ""))}')
    lines.append(f'sessionId: {yaml_str(session.get("sessionId", ""))}')
    lines.append(f'source: {yaml_str(session.get("source", ""))}')

    for field in ['category', 'topic', 'tema', 'fokus',
                  'ageGroup', 'gameFormat', 'sourceFile', 'sourceUrl']:
        val = session.get(field)
        if val:
            lines.append(f'{field}: {yaml_str(val)}')

    lines.append(f'exerciseCount: {session.get("exerciseCount", 0)}')
    lines.append(f'totalMinutes: {session.get("totalMinutes", 0)}')

    # Rich exercise list with minutes
    exercises = session.get('exercises', [])
    if exercises and isinstance(exercises[0], dict) and 'id' in exercises[0]:
        lines.append('exercises:')
        for ex in exercises:
            lines.append(f'  - id: {yaml_str(ex["id"])}')
            if ex.get('name'):
                lines.append(f'    name: {yaml_str(ex["name"])}')
            if ex.get('minutes') is not None:
                lines.append(f'    minutes: {ex["minutes"]}')

    # Exercise ID list
    exercise_ids = session.get('exerciseIds', [])
    if exercise_ids:
        lines.append('exerciseIds:')
        for eid in exercise_ids:
            lines.append(f'  - {yaml_str(eid)}')

    lines.append('---')

    # Body
    desc = session.get('description', '')
    content = '\n'.join(lines) + '\n'
    if desc:
        content += f'\n{desc}\n'

    path.write_text(content, encoding='utf-8')
