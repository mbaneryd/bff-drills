#!/usr/bin/env python3
"""
Extract training sessions from JSK PDF exercise banks.
Produces Hugo markdown files in content/sessions/jsk/.

Run from project root: python3 tools/extract_jsk_sessions.py
"""
import json, os, re, sys
from collections import defaultdict
from pathlib import Path
import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from common import write_session_md

# ─── Paths ────────────────────────────────────────────────────────────────────
PDF_79 = Path('sources/jsk/JSK_Ovningbank_7–9_1.0.pdf')
PDF_1012 = Path('sources/jsk/JSK_Ovningsbank-barn-alder-10-12.pdf')
SESSION_OUT = Path('content/sessions/jsk')
MANIFEST_OUT = Path('sources/jsk')
EXERCISES_JSON = Path('sources/jsk/_exercises.json')


def load_exercise_lookup():
    with open(EXERCISES_JSON) as f:
        data = json.load(f)
    lookup = {}
    for ex in data:
        eid = ex["exerciseId"]
        num = ex["exerciseNum"]
        title = ex["title"]
        if "7_9" in eid:
            slug = "7_9"
        elif "10_12" in eid:
            slug = "10_12"
        else:
            continue
        lookup[(slug, num)] = {"exerciseId": eid, "title": title}
    return lookup


def in_range(val, r):
    return r[0] <= val <= r[1]


def parse_minutes(s):
    s = str(s).strip()
    m = re.match(r"^(\d+)[–\-](\d+)$", s)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m2 = re.match(r"^(\d+)$", s)
    if m2:
        return int(m2.group(1))
    return None


def group_words_into_rows(word_list, y_tolerance=3):
    rows = defaultdict(list)
    for w in word_list:
        y_bucket = round(w["top"] / y_tolerance) * y_tolerance
        rows[y_bucket].append(w)
    for y in rows:
        rows[y].sort(key=lambda w: w["x0"])
    return rows


def extract_passes_from_page(page, col_defs, y_min, y_max, pass_num_max=30, exclude_x_ranges=None):
    words = page.extract_words()
    section_words = [w for w in words if y_min <= w["top"] <= y_max]
    if exclude_x_ranges is None:
        exclude_x_ranges = []
    pass_markers = []
    for w in section_words:
        x = w["x0"]
        t = w["text"]
        if not t.isdigit():
            continue
        n = int(t)
        if n < 1 or n > pass_num_max:
            continue
        for col in col_defs:
            if in_range(x, col["pass_x"]):
                pass_markers.append({"col": col["col"], "passNum": n, "y": w["top"]})
                break
    pass_markers.sort(key=lambda p: (p["col"], p["y"]))
    col_map = {c["col"]: c for c in col_defs}
    result = []
    for pm in pass_markers:
        ci = pm["col"]
        y_start = pm["y"]
        next_in_col = [p for p in pass_markers if p["col"] == ci and p["y"] > y_start]
        y_end = next_in_col[0]["y"] if next_in_col else y_max + 10
        col = col_map[ci]
        pass_words = []
        for w in section_words:
            x = w["x0"]
            y = w["top"]
            if not (y_start <= y < y_end):
                continue
            if not (col["x_min"] <= x <= col["x_max"]):
                continue
            if in_range(x, col["pass_x"]) and w["text"] == str(pm["passNum"]):
                continue
            excluded = any(lo <= x <= hi for lo, hi in exclude_x_ranges)
            if excluded:
                continue
            if y > y_max - 5:
                continue
            pass_words.append(w)
        pass_words.sort(key=lambda w: (w["top"], w["x0"]))
        rows = group_words_into_rows(pass_words)
        lines = []
        for y in sorted(rows.keys()):
            line_text = " ".join(w["text"] for w in rows[y])
            lines.append(line_text)
        exercises = parse_exercise_lines(lines)
        result.append({"col": ci, "passNum": pm["passNum"], "exercises": exercises})
    return result


def parse_exercise_lines(lines):
    exercises = []
    pending_num = None
    pending_name_parts = []

    def flush_pending():
        nonlocal pending_num, pending_name_parts
        if pending_num is not None:
            exercises.append({
                "exerciseNum": pending_num,
                "exerciseName": " ".join(pending_name_parts).strip(),
                "minutes": None,
            })
        pending_num = None
        pending_name_parts = []

    def add_exercise(num, name, mins):
        exercises.append({"exerciseNum": num, "exerciseName": name.strip(), "minutes": mins})

    skip_patterns = [
        r"^Tränarnas egna planering", r"^Lyssna på era spelare",
        r"^på vad de vill göra", r"^(PASS|ÖVNING|Övning|min|Ca|ca|SYFTE|eller)$",
        r"^PASS\s+ÖVNING", r"^Järna\s+Sportklubb",
        r"^\d+[–\-]\d+\s+år$", r"^\d+\s+år$",
    ]

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if any(re.match(p, line, re.IGNORECASE) for p in skip_patterns):
            flush_pending()
            continue

        m_plus = re.search(r"\+\s+(\d+)\.\s+(.+?)(?:\s+(\d+))?$", line)
        if m_plus:
            extra_num = int(m_plus.group(1))
            extra_name = m_plus.group(2).strip()
            extra_mins = parse_minutes(m_plus.group(3)) if m_plus.group(3) else None
            if pending_num is not None:
                part_before = line[:m_plus.start()].strip()
                if part_before:
                    pending_name_parts.append(part_before)
                exercises.append({"exerciseNum": pending_num, "exerciseName": " ".join(pending_name_parts).strip(), "minutes": None})
                pending_num = None
                pending_name_parts = []
            add_exercise(extra_num, extra_name, extra_mins)
            continue

        m = re.match(r"^(\d+)\.\s+(.+?)\s+samt\s+(\d+)\.\s+(.+?)\s+(\d+)$", line)
        if m:
            flush_pending()
            mins = parse_minutes(m.group(5))
            add_exercise(int(m.group(1)), m.group(2), mins)
            add_exercise(int(m.group(3)), m.group(4), mins)
            continue

        m = re.match(r"^(\d+),\s*(\d+)\s+(.+?)\s+(\d+)$", line)
        if m:
            flush_pending()
            add_exercise(int(m.group(1)), m.group(3), parse_minutes(m.group(4)))
            continue

        m = re.match(r"^(\d+),\s*(\d+)\s+(.+)$", line)
        if m:
            flush_pending()
            pending_num = int(m.group(1))
            pending_name_parts = [m.group(3).strip()]
            continue

        m = re.match(r"^(\d+)[–\-](\d+)\s+(.+?)\s+(\d+)$", line)
        if m:
            flush_pending()
            add_exercise(int(m.group(1)), m.group(3), parse_minutes(m.group(4)))
            continue

        m = re.match(r"^(\d+)[–\-](\d+)\s+(.+)$", line)
        if m:
            flush_pending()
            pending_num = int(m.group(1))
            pending_name_parts = [m.group(3).strip()]
            continue

        m = re.match(r"^(\d+)\.\s+(.+?)\s+(\d+)$", line)
        if m:
            flush_pending()
            add_exercise(int(m.group(1)), m.group(2), parse_minutes(m.group(3)))
            continue

        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if m:
            flush_pending()
            pending_num = int(m.group(1))
            pending_name_parts = [m.group(2).strip()]
            continue

        m = re.match(r"^(\d+)\s+(.+?)\s+(\d+)$", line)
        if m:
            flush_pending()
            add_exercise(int(m.group(1)), m.group(2), parse_minutes(m.group(3)))
            continue

        m = re.match(r"^(\d+)\s+(.+)$", line)
        if m:
            flush_pending()
            pending_num = int(m.group(1))
            pending_name_parts = [m.group(2).strip()]
            continue

        if pending_num is not None:
            m2 = re.match(r"^(.+?)\s+(\d+)$", line)
            if m2 and not re.match(r"^\d+$", m2.group(1)):
                pending_name_parts.append(m2.group(1).strip())
                exercises.append({"exerciseNum": pending_num, "exerciseName": " ".join(pending_name_parts).strip(), "minutes": parse_minutes(m2.group(2))})
                pending_num = None
                pending_name_parts = []
            else:
                pending_name_parts.append(line)
            continue

    flush_pending()
    return exercises


def extract_79_sessions():
    pdf = pdfplumber.open(str(PDF_79))
    page = pdf.pages[2]
    col_defs_7 = [
        {"col": 0, "pass_x": (60, 80),   "x_min": 60,  "x_max": 196},
        {"col": 1, "pass_x": (228, 238), "x_min": 228, "x_max": 362},
        {"col": 2, "pass_x": (390, 400), "x_min": 390, "x_max": 526},
    ]
    passes_7 = extract_passes_from_page(page, col_defs_7, y_min=100, y_max=529, pass_num_max=22)
    col_defs_89 = [
        {"col": 0, "pass_x": (63, 75),   "x_min": 60,  "x_max": 200},
        {"col": 1, "pass_x": (225, 235), "x_min": 225, "x_max": 360},
        {"col": 2, "pass_x": (383, 395), "x_min": 383, "x_max": 520},
    ]
    passes_89 = extract_passes_from_page(page, col_defs_89, y_min=540, y_max=810, pass_num_max=10)
    pdf.close()
    return passes_7, passes_89


def extract_1012_sessions():
    pdf = pdfplumber.open(str(PDF_1012))
    page = pdf.pages[2]
    col_defs_1012 = [
        {"col": 0, "pass_x": (63, 75),   "x_min": 60,  "x_max": 228},
        {"col": 1, "pass_x": (315, 325), "x_min": 315, "x_max": 480},
    ]
    exclude = [(226, 318), (481, 600)]
    passes_1012 = extract_passes_from_page(page, col_defs_1012, y_min=252, y_max=810, pass_num_max=10, exclude_x_ranges=exclude)
    pdf.close()
    return passes_1012


PDF_NAME_OVERRIDES = {
    ("10_12", "mot 1 med kortlinje som mål"): 6,
    ("10_12", "Kvadratpass"): 12,
}


def resolve_exercise_num(ex_slug, ex_num, ex_name, exercise_lookup):
    for (slug, fragment), correct_num in PDF_NAME_OVERRIDES.items():
        if slug == ex_slug and fragment.lower() in ex_name.lower():
            key = (ex_slug, correct_num)
            if key in exercise_lookup:
                info = exercise_lookup[key]
                return correct_num, info["exerciseId"], info["title"]
    key = (ex_slug, ex_num)
    if key in exercise_lookup:
        info = exercise_lookup[key]
        return ex_num, info["exerciseId"], info["title"]
    return ex_num, None, ex_name


def assemble_sessions(passes, age_group, game_format, source_file, ex_slug):
    exercise_lookup = load_exercise_lookup()
    sessions = []
    for p in passes:
        exs = p["exercises"]
        enriched = []
        for ex in exs:
            num = ex["exerciseNum"]
            name = ex.get("exerciseName", "") or ""
            corrected_num, eid, title = resolve_exercise_num(ex_slug, num, name, exercise_lookup)
            if not title:
                title = name
            enriched.append({
                "exerciseNum": corrected_num,
                "exerciseName": title,
                "minutes": ex.get("minutes"),
                "exerciseId": eid,
            })
        if not enriched:
            continue
        total_mins = sum(e["minutes"] for e in enriched if e["minutes"] is not None)
        if age_group == "7":
            session_id = f"jsk_7_pass_{p['passNum']}"
        elif age_group == "8-9":
            session_id = f"jsk_8_9_pass_{p['passNum']}"
        else:
            session_id = f"jsk_10_12_pass_{p['passNum']}"
        sessions.append({
            "sessionId": session_id,
            "passNum": p["passNum"],
            "ageGroup": age_group,
            "gameFormat": game_format,
            "exercises": enriched,
            "totalMinutes": total_mins,
            "source": "jsk_ovningsbank",
            "sourceFile": source_file,
        })
    return sessions


def main():
    SESSION_OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.mkdir(parents=True, exist_ok=True)

    print("Extracting training sessions from JSK PDFs...")

    passes_7, passes_89 = extract_79_sessions()
    sessions_7 = assemble_sessions(passes_7, "7", "5v5", PDF_79.name, "7_9")
    sessions_89 = assemble_sessions(passes_89, "8-9", "5v5", PDF_79.name, "7_9")

    passes_1012 = extract_1012_sessions()
    sessions_1012 = assemble_sessions(passes_1012, "10-12", "7v7", PDF_1012.name, "10_12")

    all_sessions = sessions_7 + sessions_89 + sessions_1012

    print(f"\nFound {len(all_sessions)} sessions total:\n")
    for s in all_sessions:
        ex_count = len(s["exercises"])
        total = s["totalMinutes"]
        print(f"  {s['sessionId']:35s}  {ex_count} exercises  {total} min")

    # Save manifest
    (MANIFEST_OUT / '_sessions.json').write_text(
        json.dumps(all_sessions, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"\nSaved manifest: {MANIFEST_OUT}/_sessions.json")

    # Save session markdown files
    for session in all_sessions:
        sid = session["sessionId"]
        age = session["ageGroup"]
        pnum = session["passNum"]

        session_data = {
            'sessionId': sid,
            'title': f"JSK {age} år – Pass {pnum}",
            'source': 'jsk_ovningsbank',
            'ageGroup': age,
            'gameFormat': session['gameFormat'],
            'exerciseCount': len(session['exercises']),
            'totalMinutes': session['totalMinutes'],
            'exercises': [
                {
                    'id': ex.get('exerciseId', ''),
                    'name': ex.get('exerciseName', ''),
                    'minutes': ex.get('minutes'),
                }
                for ex in session['exercises']
            ],
            'exerciseIds': [
                ex['exerciseId'] for ex in session['exercises'] if ex.get('exerciseId')
            ],
            'sourceFile': session['sourceFile'],
        }
        write_session_md(SESSION_OUT / f'{sid}.md', session_data)

    print(f"Saved {len(all_sessions)} session markdown files → {SESSION_OUT}/")
    print("\nDone!")


if __name__ == "__main__":
    main()
