#!/usr/bin/env python3
"""
Extract exercises from JSK (Järna Sportklubb) PDF exercise banks.
Produces Hugo markdown files in content/exercises/jsk/.

Run from project root: python3 tools/extract_jsk.py
"""
import json, re, sys
from pathlib import Path
import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from common import write_exercise_md

EXERCISE_OUT = Path('content/exercises/jsk')
MANIFEST_OUT = Path('sources/jsk')

TITLE_OVERRIDES = {
    ('7-9',   23): 'Domarn hur långt är det kvar',
    ('10-12',  4): 'Utveckling av Teknikdiagonalen',
    ('10-12',  6): 'En mot en med kortlinje som mål',
    ('10-12',  7): 'Stafetter & Teknikbanor Bana 1',
    ('10-12',  8): 'Stafetter & Teknikbanor Bana 2',
    ('10-12', 16): 'Passningsdiamanten',
    ('10-12', 37): 'Grunderna i greppteknik',
}

PDFS = [
    {
        'file': 'sources/jsk/JSK_Ovningbank_7–9_1.0.pdf',
        'age_group': '7-9',
        'game_format': '5v5',
        'source': 'jsk_ovningsbank',
    },
    {
        'file': 'sources/jsk/JSK_Ovningsbank-barn-alder-10-12.pdf',
        'age_group': '10-12',
        'game_format': '7v7',
        'source': 'jsk_ovningsbank',
    },
]

# ─── Helpers ────────────────────────────────────────────────────────────────

def strip_footer(text):
    text = re.sub(r'Järna Sportklubb \| Övningsbank[^\n]*', '', text)
    text = re.sub(r'jarnask\.se[^\n]*', '', text)
    return text.strip()


def clean_line(line):
    return re.sub(r'[ \t]+', ' ', line).strip()


def extract_section_text(text, header_re, stop_re=None):
    m = re.search(header_re, text, re.IGNORECASE)
    if not m:
        return ''
    rest = text[m.end():]
    if stop_re:
        s = re.search(stop_re, rest)
        if s:
            rest = rest[:s.start()]
    return rest.strip()


def parse_bullets(text):
    items = []
    for line in text.split('\n'):
        line = clean_line(line)
        if line.startswith('•') or line.startswith('–'):
            v = re.sub(r'^[•–]\s*', '', line).strip()
            if len(v) > 3:
                items.append(v)
    return items


def parse_numbered_steps(text):
    steps = []
    for m in re.finditer(r'(?m)^(\d+)\.\s+(.+?)(?=\n\d+\.\s|\nVARIATIONER|\nINFÖR|\Z)',
                         text, re.DOTALL):
        step = re.sub(r'\s+', ' ', m.group(2)).strip()
        if len(step) > 5:
            steps.append(step)
    return steps


# ─── Page-by-page exercise parser ───────────────────────────────────────────

def page_exercise_num(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return None, None
    first = lines[0]
    if re.match(r'^\d{1,2}$', first):
        num = int(first)
        if num < 1 or num > 60:
            return None, None
        title_parts = []
        for line in lines[1:]:
            if re.match(r'^(Syfte|INFÖR|Instruktioner)', line):
                break
            if re.match(r'^\d{1,2}\s', line):
                break
            if len(line) > 80:
                break
            title_parts.append(line)
            if len(title_parts) >= 3:
                break
        raw_title = ' '.join(title_parts).strip()
    else:
        m = re.match(r'^(\d{1,2})\s+(.*)', first)
        if not m:
            return None, None
        num = int(m.group(1))
        if num < 1 or num > 60:
            return None, None
        raw_title = m.group(2).strip()
        raw_title = re.split(r'\s+Syfte[:\s]', raw_title)[0].strip()
        raw_title = re.sub(r'^[»«›‹"\']+', '', raw_title).strip()
        for line in lines[1:]:
            if re.match(r'^(Syfte|INFÖR|Instruktioner)', line):
                break
            if re.search(r'Syfte', line):
                break
            if line.startswith('•') or re.match(r'^\d{1,2}\s', line):
                break
            if len(line) > 60:
                break
            raw_title = raw_title + ' ' + line.strip()
            break
    raw_title = re.sub(r'\s+', ' ', raw_title).strip()
    if not raw_title:
        return None, None
    return num, raw_title


def parse_exercise_page(ex_num, title, text, meta):
    syfte_raw = extract_section_text(text, r'[Ss]yfte\s*[:\s]+',
                                      stop_re=r'Instruktioner|INFÖR ÖVNINGEN|^\d+\.')
    syfte_raw = re.sub(r'INFÖR.*', '', syfte_raw, flags=re.DOTALL)
    syfte = re.sub(r'\s+', ' ', syfte_raw).strip() if syfte_raw else None

    infor_raw = extract_section_text(text, r'INFÖR ÖVNINGEN', stop_re=r'^\s*1\.\s|VARIATIONER')
    setup_bullets = parse_bullets(infor_raw) if infor_raw else []

    instr_text = extract_section_text(text, r'INFÖR ÖVNINGEN', stop_re=r'\nVARIATIONER\b')
    instructions = parse_numbered_steps(instr_text) if instr_text else []

    var_raw = extract_section_text(text, r'VARIATIONER[:\s]*')
    variations = parse_bullets(var_raw) if var_raw else []
    if var_raw:
        for line in var_raw.split('\n'):
            line = clean_line(line)
            if line.startswith('-') or line.startswith('–'):
                v = re.sub(r'^[-–]\s*', '', line).strip()
                if len(v) > 3 and v not in variations:
                    variations.append(v)

    age_slug = meta['age_group'].replace('-', '_')
    ex_id = f"jsk_{age_slug}_{ex_num}"

    FORMAT_TO_LEVELS = {
        '3v3':   {'3v3': True,  '5v5': False, '7v7': False, '9v9': False, '11v11': False},
        '5v5':   {'3v3': False, '5v5': True,  '7v7': False, '9v9': False, '11v11': False},
        '7v7':   {'3v3': False, '5v5': False, '7v7': True,  '9v9': False, '11v11': False},
    }

    return {
        'exerciseId': ex_id,
        'exerciseNum': ex_num,
        'title': title,
        'ageGroup': meta['age_group'],
        'gameFormat': meta['game_format'],
        'levels': FORMAT_TO_LEVELS.get(meta['game_format'], {}),
        'what': syfte,
        'organization': '\n'.join(setup_bullets),
        'instructions': '\n\n'.join(instructions),
        'progressions': variations,
        'source': meta['source'],
        'sourceFile': Path(meta['file']).name,
    }


def parse_exercises(pdf_path, meta):
    exercises = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ''
            text = strip_footer(text)
            if not text:
                continue
            ex_num, title = page_exercise_num(text)
            if ex_num is None:
                continue
            has_syfte = bool(re.search(r'[Ss]yfte', text))
            has_infor = bool(re.search(r'INFÖR ÖVNINGEN', text))
            has_instructions = bool(re.search(r'\n\s*\d+\.', text))
            if not (has_syfte or has_infor or has_instructions):
                continue
            if ex_num not in exercises:
                override_key = (meta['age_group'], ex_num)
                if override_key in TITLE_OVERRIDES:
                    title = TITLE_OVERRIDES[override_key]
                ex = parse_exercise_page(ex_num, title, text, meta)

                def fix_hyphens(s):
                    s = re.sub(r'(\w)-\n(\w)', r'\1\2', s)
                    s = re.sub(r'([a-zåäö])- ([a-zåäö])', r'\1\2', s)
                    return s

                for field in ('what', 'instructions', 'progressions'):
                    if isinstance(ex.get(field), str):
                        ex[field] = fix_hyphens(ex[field])
                    elif isinstance(ex.get(field), list):
                        ex[field] = [fix_hyphens(s) for s in ex[field]]
                exercises[ex_num] = ex
            else:
                var_raw = extract_section_text(text, r'VARIATIONER[:\s]*')
                if var_raw:
                    new_vars = parse_bullets(var_raw)
                    existing = set(exercises[ex_num].get('progressions', []))
                    for v in new_vars:
                        if v not in existing:
                            exercises[ex_num].setdefault('progressions', []).append(v)
                            existing.add(v)
    return [exercises[k] for k in sorted(exercises.keys())]


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    EXERCISE_OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.mkdir(parents=True, exist_ok=True)

    all_exercises = []

    for pdf_meta in PDFS:
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_meta['file']}")

        exercises = parse_exercises(pdf_meta['file'], pdf_meta)
        print(f"  Exercises found: {len(exercises)}")

        for ex in exercises:
            ex_id = ex['exerciseId']
            write_exercise_md(EXERCISE_OUT / f'{ex_id}.md', ex)

            instr_count = len((ex.get('instructions') or '').split('\n\n'))
            var_count = len(ex.get('progressions', []))
            syfte_short = (ex.get('what') or '')[:50]
            print(f"  [{ex['exerciseNum']:2d}] {ex['title'][:40]:<40} "
                  f"instr={instr_count} var={var_count}  syfte: {syfte_short}")

        all_exercises.extend(exercises)

    (MANIFEST_OUT / '_exercises.json').write_text(
        json.dumps(all_exercises, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(f"\n✓ {len(all_exercises)} exercises → {EXERCISE_OUT}/")
    print(f"✓ Manifest → {MANIFEST_OUT}/_exercises.json")


if __name__ == '__main__':
    main()
