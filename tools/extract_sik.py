#!/usr/bin/env python3
"""
Extract exercises from SIK (Sundbybergs IK) training session PDFs.
Produces Hugo markdown files in content/exercises/sik/ and content/sessions/sik/,
plus rendered diagram images in static/images/sik/.

Run from project root: python3 tools/extract_sik.py
"""
import json, re, subprocess, os, sys
from pathlib import Path
import pdfplumber

sys.path.insert(0, str(Path(__file__).parent))
from common import write_exercise_md, write_session_md, yaml_str

EXERCISE_OUT = Path('content/exercises/sik')
SESSION_OUT = Path('content/sessions/sik')
IMAGE_OUT = Path('static/images/sik')
MANIFEST_OUT = Path('sources/sik')
PDF_DIR = Path('sources/sik/5v5')

SKIP_PDFS = {'01_traningsinnehall.pdf', '02_temaveckor.pdf'}

TITLE_OVERRIDES = {
    ('04_komma_till_avslut_fardigheter_2.pdf', 5): 'Isolerade skott',
    ('06_komma_till_avslut_forhindra_avslut_4.pdf', 2): 'Lek (fritt val)',
    ('06_komma_till_avslut_forhindra_avslut_4.pdf', 3): 'Stafett med drivning',
    ('06_komma_till_avslut_forhindra_avslut_4.pdf', 6): 'Lek (fritt val)',
    ('07_komma_till_avslut_forhindra_avslut_5.pdf', 2): 'Lek (fritt val)',
    ('07_komma_till_avslut_forhindra_avslut_5.pdf', 5): 'Inte nudda boll',
    ('07_komma_till_avslut_forhindra_avslut_5.pdf', 7): 'Lek (fritt val)',
    ('08_behalla_boll_1.pdf', 4): 'Jaga bollhållare',
    ('08_behalla_boll_1.pdf', 5): 'Blå och gul',
    ('08_behalla_boll_1.pdf', 7): 'Lek (fritt val)',
    ('09_behalla_boll_2.pdf', 4): 'Spel mot 2 mål',
    ('09_behalla_boll_2.pdf', 5): 'Doppboll',
    ('09_behalla_boll_2.pdf', 7): 'Lek (fritt val)',
    ('10_behalla_boll_3.pdf', 3): 'Driva 2 och 2',
    ('10_behalla_boll_3.pdf', 5): 'Lek (fritt val)',
    ('11_behalla_boll_4.pdf', 3): 'Passa behålla boll',
    ('11_behalla_boll_4.pdf', 4): 'Passa ta emot & driv',
    ('11_behalla_boll_4.pdf', 6): 'Lek (fritt val)',
    ('12_behalla_boll_5.pdf', 3): 'Behålla boll i lag',
    ('12_behalla_boll_5.pdf', 5): 'Lek (fritt val)',
    ('13_behalla_boll_6.pdf', 2): 'Intervallträning med boll',
    ('13_behalla_boll_6.pdf', 3): 'Driva till linjer',
    ('13_behalla_boll_6.pdf', 5): 'Lek (fritt val)',
    ('14_fotbollskoordination.pdf', 2): 'Blå och gul',
    ('14_fotbollskoordination.pdf', 3): 'Bollstafett Kasta-Fånga',
    ('14_fotbollskoordination.pdf', 4): 'Kona eller boll',
    ('14_fotbollskoordination.pdf', 5): 'Bollstafett Över-Under',
    ('14_fotbollskoordination.pdf', 6): 'Motorikstopp',
    ('14_fotbollskoordination.pdf', 7): 'Stafettormen',
    ('14_fotbollskoordination.pdf', 8): 'Uppmaningar med boll',
    ('14_fotbollskoordination.pdf', 9): 'Bollring',
    ('14_fotbollskoordination.pdf', 10): 'Uppmaningar parvis',
}

SPELSOVNING_TITLE = 'Spelsövning (match)'
LEK_TITLE = 'Lek (fritt val)'

# ─── Font-based name extraction ────────────────────────────────────────────

def extract_name_by_font(page):
    name_chars = []
    for c in page.chars:
        if 'Staatliches' in c.get('fontname', '') and c.get('size', 0) > 11:
            name_chars.append(c['text'])
    name = ''.join(name_chars).strip()
    if not name:
        return None
    skip_patterns = ['Träningsplanering', 'Stationsträning', 'Station 1', 'Station 2']
    for pat in skip_patterns:
        if pat in name:
            return None
    return name


# ─── Text parsing helpers ──────────────────────────────────────────────────

def is_title_page(text):
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if len(lines) <= 4 and any('Träningsplanering' in l for l in lines):
        has_content = any(kw in text for kw in [
            'Färdighetsövning', 'Spelsövning', 'Station', 'SIK Färdighets',
            'Spelform:', 'Fysiska moment'
        ])
        if not has_content:
            return True
    return False


def is_stations_info_page(text):
    return ('Stationsträning - ca' in text and 'Dela in' not in text[:200]
            and 'Station 1' not in text[:50])


def is_exercise_page(text):
    if is_title_page(text):
        return False
    if is_stations_info_page(text):
        return False
    has_marker = any(kw in text for kw in [
        'Färdighetsövning', 'Spelsövning', 'SIK Färdighets', 'Lek ', 'Lek\n'
    ])
    has_sidebar = 'Spelform: 5v5' in text or 'Spelarens färdigheter' in text
    return has_marker and has_sidebar


def extract_exercise_type(text):
    if re.search(r'Spelsövning', text):
        return 'Spelsövning'
    if re.search(r'Lek\s+\d+', text):
        return 'Lek'
    if 'Station 1' in text and 'Station 2' not in text:
        return 'Station 1'
    if 'Station 2' in text and 'Station 1' not in text:
        return 'Station 2'
    m = re.search(r'(Färdighetsövning)', text)
    if m:
        return m.group(1)
    return 'Övning'


def extract_duration(text):
    m = re.search(r'(?:Färdighetsövning|Spelsövning|Station \d|Lek)\s+(\d+(?:-\d+)?)\s*min', text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} min"
    m = re.search(r'(?:Färdighetsövning|Spelsövning|Lek)\s+(\d+(?:-\d+)?)\n.*?min', text, re.IGNORECASE)
    if m:
        return f"{m.group(1)} min"
    return None


def extract_area_size(text):
    m = re.search(r'(?:ca\s+)?(\d+\s*x\s*\d+\s*m(?:\s*per\s*plan)?)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def extract_tema(text):
    m = re.search(r'Tema\s*\n(?:⚽\s*\n)*(.*?)(?:\n(?:Lagets|⚽|TR\b))', text, re.DOTALL)
    if m:
        tema = m.group(1).strip()
        tema = re.sub(r'⚽\s*', '', tema).strip()
        return tema
    return None


def extract_spelarens_fardigheter(text):
    m = re.search(r'Spelarens färdigheter\s*\n(.*?)(?:Fysiska moment|Fotbollspsykologi)', text, re.DOTALL)
    if m:
        skills = []
        for line in m.group(1).split('\n'):
            line = line.strip()
            if line and line not in ('', '⚽') and len(line) < 30:
                if not any(kw in line for kw in ['Färdighetsövning', 'Spelsövning', 'Station',
                                                   'SIK', 'per plan', 'min', 'Lek']):
                    skills.append(line)
        return skills
    return []


def extract_content_text(text):
    lines = text.split('\n')
    sidebar_labels = {
        'Träningsplanering', 'Spelform: 5v5', 'Tema', 'Lagets Färdigheter',
        'Spelarens färdigheter', 'Fysiska moment', 'Fotbollspsykologi',
    }
    sidebar_skills = {
        'Driva', 'Springa', 'Bryta', 'Passa', 'Avslut', 'Orientering',
        'Fotarbete', 'Snabbhet', 'Kasta', 'Fånga', 'Drivning', 'Vändning',
        'Rulla', 'Täcka', 'Spelbarhet', 'Passning', 'Markering', 'Dribbling',
        'Dribbla', 'Komma till avslut', 'Brytning/Tackling', 'Mottagning',
    }
    content_lines = []
    in_content = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == '⚽':
            continue
        if stripped in sidebar_labels or stripped in sidebar_skills:
            continue
        if stripped.startswith('Springa och driva'):
            in_content = True
            continue
        if any(kw in stripped for kw in ['SIK Färdighets', 'Färdighetsövning', 'Spelsövning',
                                          'per plan', 'Färdighetskvadrat']):
            in_content = True
            continue
        if re.match(r'^(Lek|Station \d)\s+\d+', stripped):
            in_content = True
            continue
        if in_content:
            content_lines.append(stripped)
    return '\n'.join(content_lines)


def extract_description_and_syfte(content_text):
    syfte = None
    progressions = []
    syfte_match = re.search(r'Syfte[:\s]*\n?', content_text)
    prog_matches = list(re.finditer(r'Progression[:\s]*(?:\d+[:\s]*)?', content_text))
    first_marker = len(content_text)
    if syfte_match:
        first_marker = min(first_marker, syfte_match.start())
    if prog_matches:
        first_marker = min(first_marker, prog_matches[0].start())
    desc = content_text[:first_marker].strip()
    if syfte_match:
        after_syfte = content_text[syfte_match.end():]
        end_match = re.search(r'(?:Progression|Exempel|Utmana)', after_syfte)
        if end_match:
            syfte = after_syfte[:end_match.start()].strip()
        else:
            syfte = after_syfte.strip()
        syfte = re.sub(r'\s+', ' ', syfte)
    for i, pm in enumerate(prog_matches):
        end = prog_matches[i + 1].start() if i + 1 < len(prog_matches) else len(content_text)
        prog_text = content_text[pm.end():end]
        if 'Syfte' in prog_text:
            prog_text = prog_text[:prog_text.index('Syfte')]
        prog_text = re.sub(r'\s+', ' ', prog_text).strip()
        if prog_text and len(prog_text) > 3:
            progressions.append(prog_text)
    return desc, syfte, progressions


def parse_exercise(page, page_idx, pdf_name, session_tema, exercise_counter):
    text = page.extract_text() or ''
    override_key = (pdf_name, page_idx + 1)
    if override_key in TITLE_OVERRIDES:
        name = TITLE_OVERRIDES[override_key]
    else:
        name = extract_name_by_font(page)
        if not name:
            ex_type = extract_exercise_type(text)
            if ex_type == 'Spelsövning':
                name = SPELSOVNING_TITLE
            elif ex_type == 'Lek':
                name = LEK_TITLE
            elif 'Blås i pipan' in text:
                name = LEK_TITLE
            else:
                name = f"Övning {exercise_counter}"
    name = re.sub(r'\s+', ' ', name).strip()
    if name and name[0].islower():
        name = name[0].upper() + name[1:]
    ex_type = extract_exercise_type(text)
    duration = extract_duration(text)
    area_size = extract_area_size(text)
    tema = extract_tema(text) or session_tema
    skills = extract_spelarens_fardigheter(text)
    content = extract_content_text(text)
    desc, syfte, progressions = extract_description_and_syfte(content)
    pdf_stem = Path(pdf_name).stem
    ex_id = f"sik_5v5_{pdf_stem}_p{page_idx + 1}"
    return {
        'exerciseId': ex_id,
        'title': name,
        'exerciseType': ex_type,
        'tema': tema,
        'gameFormat': '5v5',
        'levels': {'3v3': False, '5v5': True, '7v7': False, '9v9': False, '11v11': False},
        'duration': duration,
        'areaSize': area_size,
        'what': syfte,
        'instructions': desc,
        'progressions': progressions,
        'playerSkills': skills,
        'source': 'sik_traningsplanering',
        'sourceFile': pdf_name,
        'sourcePage': page_idx + 1,
    }


# ─── Image rendering ──────────────────────────────────────────────────────

def find_diagram_bbox(page):
    imgs = page.images
    if len(imgs) < 2:
        return None
    xs, ys, x2s, y2s = [], [], [], []
    for img in imgs:
        ix, iy = img['x0'], img['top']
        iw, ih = img['width'], img['height']
        if ix < 60 and iy < 60 and iw < 50:
            continue
        if iw < 15 and ih < 15:
            continue
        xs.append(ix)
        ys.append(iy)
        x2s.append(ix + iw)
        y2s.append(iy + ih)
    if not xs:
        return None
    pad = 12
    return (max(0, min(xs) - pad), max(0, min(ys) - pad),
            min(page.width, max(x2s) + pad), min(page.height, max(y2s) + pad))


def render_diagram_image(pdf_path, page_num, output_path, page):
    bbox = find_diagram_bbox(page)
    if not bbox:
        return render_full_page_image(pdf_path, page_num, output_path)
    x1, y1, x2, y2 = bbox
    dpi = 250
    scale = dpi / 72.0
    crop_x = int(x1 * scale)
    crop_y = int(y1 * scale)
    crop_w = int((x2 - x1) * scale)
    crop_h = int((y2 - y1) * scale)
    base = str(output_path).replace('.png', '')
    subprocess.run([
        'pdftoppm', '-png', '-r', str(dpi),
        '-f', str(page_num), '-l', str(page_num),
        '-x', str(crop_x), '-y', str(crop_y),
        '-W', str(crop_w), '-H', str(crop_h),
        str(pdf_path), base
    ], capture_output=True)
    for suffix in [f'-{page_num}', f'-0{page_num}', f'-00{page_num}', '']:
        candidate = f'{base}{suffix}.png'
        if os.path.exists(candidate):
            if candidate != str(output_path):
                os.rename(candidate, str(output_path))
            return True
    return render_full_page_image(pdf_path, page_num, output_path)


def render_full_page_image(pdf_path, page_num, output_path):
    from PIL import Image as PILImage
    base = str(output_path).replace('.png', '_tmp')
    subprocess.run([
        'pdftoppm', '-png', '-r', '250', '-f', str(page_num), '-l', str(page_num),
        str(pdf_path), base
    ], capture_output=True)
    tmp_path = None
    for suffix in [f'-{page_num}', f'-0{page_num}', f'-00{page_num}', '']:
        candidate = f'{base}{suffix}.png'
        if os.path.exists(candidate):
            tmp_path = candidate
            break
    if not tmp_path:
        return False
    img = PILImage.open(tmp_path)
    w, h = img.size
    left = int(w * 0.42)
    top = int(h * 0.02)
    right = int(w * 0.98)
    bottom = int(h * 0.58)
    cropped = img.crop((left, top, right, bottom))
    cropped.save(str(output_path))
    os.remove(tmp_path)
    return True


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    EXERCISE_OUT.mkdir(parents=True, exist_ok=True)
    SESSION_OUT.mkdir(parents=True, exist_ok=True)
    IMAGE_OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.mkdir(parents=True, exist_ok=True)

    all_exercises = []
    all_sessions = []

    pdf_files = sorted(f for f in os.listdir(PDF_DIR) if f.endswith('.pdf') and f not in SKIP_PDFS)

    for pdf_name in pdf_files:
        pdf_path = PDF_DIR / pdf_name
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_name}")

        session_exercises = []

        with pdfplumber.open(pdf_path) as pdf:
            title_text = pdf.pages[0].extract_text() or ''
            session_tema = None
            session_fokus = None
            for line in title_text.split('\n'):
                line = line.strip()
                if not line or line == 'Träningsplanering':
                    continue
                if line.startswith('Fokus'):
                    session_fokus = line.replace('Fokus ', '').replace('Fokus: ', '').strip()
                elif session_tema is None:
                    session_tema = line

            print(f"  Session tema: {session_tema}")
            exercise_counter = 0

            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text() or ''
                if not is_exercise_page(text):
                    continue

                exercise_counter += 1
                ex = parse_exercise(page, page_idx, pdf_name, session_tema, exercise_counter)

                # Render diagram image
                img_name = f"{ex['exerciseId']}.png"
                img_path = IMAGE_OUT / img_name
                if render_diagram_image(pdf_path, page_idx + 1, img_path, page):
                    ex['image'] = f"sik/{img_name}"
                else:
                    ex['image'] = None

                # Save markdown
                write_exercise_md(EXERCISE_OUT / f"{ex['exerciseId']}.md", ex)

                dur = ex.get('duration') or 'N/A'
                has_syfte = 'yes' if ex.get('what') else 'no'
                desc_len = len(ex.get('instructions') or '')
                print(f"  [{exercise_counter}] {ex['title']:<40} "
                      f"type={ex['exerciseType']:<20} dur={dur:<10} "
                      f"syfte={has_syfte:<4} desc={desc_len} chars")

                all_exercises.append(ex)
                session_exercises.append(ex)

        # Build session
        pdf_stem = Path(pdf_name).stem
        session_id = f"sik_5v5_{pdf_stem}"

        total_mins = 0
        for ex in session_exercises:
            d = ex.get('duration', '')
            if d:
                m = re.search(r'(\d+)', d)
                if m:
                    total_mins += int(m.group(1))

        session = {
            'sessionId': session_id,
            'title': f"SIK 5v5 – {session_tema or pdf_stem}",
            'tema': session_tema or '',
            'fokus': session_fokus or '',
            'gameFormat': '5v5',
            'exerciseCount': len(session_exercises),
            'totalMinutes': total_mins,
            'exerciseIds': [ex['exerciseId'] for ex in session_exercises],
            'source': 'sik_traningsplanering',
            'sourceFile': pdf_name,
        }
        all_sessions.append(session)

        write_session_md(SESSION_OUT / f"session_{session_id}.md", session)
        print(f"  → Session: {session['title']} ({len(session_exercises)} exercises, ~{total_mins} min)")

    # Save manifests
    (MANIFEST_OUT / '_exercises.json').write_text(
        json.dumps(all_exercises, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    sessions_manifest = [{k: v for k, v in s.items() if k != 'exercises'} for s in all_sessions]
    (MANIFEST_OUT / '_sessions.json').write_text(
        json.dumps(sessions_manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(f"\n✓ {len(all_exercises)} exercises → {EXERCISE_OUT}/")
    print(f"✓ {len(all_sessions)} sessions → {SESSION_OUT}/")
    print(f"✓ Images → {IMAGE_OUT}/")
    print(f"✓ Manifests → {MANIFEST_OUT}/")


if __name__ == '__main__':
    main()
