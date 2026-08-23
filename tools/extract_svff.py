#!/usr/bin/env python3
"""
SvFF exercise parser: parses exercise detail HTML from SvFF Övningsbanken.

The actual fetching is done via Playwright browser (browser_evaluate MCP tool)
since the site requires authentication. This module provides:
  - parse_exercise_html(): parse raw HTML into structured data
  - save_exercise(): save as Hugo markdown + download image

Run from project root. Usage:
  1. Use Playwright to fetch exercise HTML pages
  2. Call parse_exercise_html() to extract data
  3. Call save_exercise() to save markdown + image

Output:
  - content/exercises/svff/{id}.md
  - static/images/svff/{id}.png
  - sources/svff/_listing.json (manifest)
"""
import json, re, os, html, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import write_exercise_md

EXERCISE_OUT = Path('content/exercises/svff')
IMAGE_OUT = Path('static/images/svff')
MANIFEST_OUT = Path('sources/svff')


def parse_exercise_html(exercise_id, title, topic, category, exercise_type, levels, raw_html):
    """Parse the detail page HTML and return structured data."""

    img_match = re.search(r'src="(/globalassets/[^"]*ovningsbilder[^"]*)"', raw_html)
    img_url = f"https://ovningsbanken.svenskfotboll.se{img_match.group(1)}" if img_match else None
    if not img_url:
        img_match = re.search(r'src="(https://ovningsbanken[^"]*ovningsbilder[^"]*)"', raw_html)
        img_url = img_match.group(1) if img_match else None

    video_match = re.search(r'href="(/LemonwhaleVideoDisplay/\?id=[^"#]+)', raw_html)
    video_url = f"https://ovningsbanken.svenskfotboll.se{video_match.group(1)}" if video_match else None

    thumb_match = re.search(r'background-image: url\(&quot;([^&]+)&quot;\)', raw_html)
    if not thumb_match:
        thumb_match = re.search(r'background-image:\s*url\(["\']?([^"\')\s]+)["\']?\)', raw_html)
    video_thumb = thumb_match.group(1) if thumb_match else None

    text_match = re.search(r'<div class="c-exercise__text[^"]*">(.*?)</div>\s*</div>\s*</div>', raw_html, re.DOTALL)
    text_html = text_match.group(1) if text_match else ''

    def extract_section(section_name, html_content):
        pattern = rf'<h3>{re.escape(section_name)}</h3>\s*<p>(.*?)</p>'
        m = re.search(pattern, html_content, re.DOTALL)
        if not m:
            return None
        text = re.sub(r'<br\s*/?>', '\n', m.group(1))
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text).strip()
        text = re.sub(r'\xa0', ' ', text)
        return text

    what = extract_section('Vad?', text_html)
    why = extract_section('Varför?', text_html)
    org = extract_section('Organisation', text_html)

    how_match = re.search(r'<h3>Hur\?</h3>(.*?)(?=<h3>|$)', text_html, re.DOTALL)
    how_text = None
    if how_match:
        how_raw = how_match.group(1)
        how_raw = re.sub(r'<br\s*/?>', '\n', how_raw)
        how_raw = re.sub(r'</p>\s*<p>', '\n\n', how_raw)
        how_raw = re.sub(r'<[^>]+>', '', how_raw)
        how_text = html.unescape(how_raw).strip().replace('\xa0', ' ')

    anv_match = re.search(r'<h3>Anvisningar</h3>(.*?)(?=<h3>|$)', text_html, re.DOTALL)
    instructions = None
    progressions = []
    if anv_match:
        anv_raw = anv_match.group(1)
        paragraphs = re.findall(r'<p>(.*?)</p>', anv_raw, re.DOTALL)
        main_parts = []
        for p in paragraphs:
            p_clean = re.sub(r'<br\s*/?>', '\n', p)
            p_clean = re.sub(r'<[^>]+>', '', p_clean)
            p_clean = html.unescape(p_clean).strip().replace('\xa0', ' ')
            if p_clean.startswith('Progression'):
                progressions.append(p_clean)
            else:
                main_parts.append(p_clean)
        instructions = '\n\n'.join(main_parts) if main_parts else None

    return {
        'exerciseId': exercise_id,
        'title': title,
        'sourceUrl': f'https://ovningsbanken.svenskfotboll.se/fotboll/tranare/ovningsbanken/ovningar/ShowExercise/?exerciseId={exercise_id}',
        'category': category,
        'exerciseType': exercise_type,
        'topic': topic,
        'levels': levels,
        'imageUrl': img_url,
        'image': f'svff/{exercise_id}.png' if img_url else None,
        'videoUrl': video_url,
        'videoThumb': video_thumb,
        'what': what,
        'why': why,
        'how': how_text,
        'organization': org,
        'instructions': instructions,
        'progressions': progressions,
        'source': 'svff_ovningsbanken',
    }


def save_exercise(data):
    """Save exercise as Hugo markdown and download image."""
    EXERCISE_OUT.mkdir(parents=True, exist_ok=True)
    IMAGE_OUT.mkdir(parents=True, exist_ok=True)

    eid = data['exerciseId']

    # Download image
    if data.get('imageUrl'):
        img_path = IMAGE_OUT / f'{eid}.png'
        if not img_path.exists():
            try:
                urllib.request.urlretrieve(data['imageUrl'], str(img_path))
            except Exception as e:
                print(f'  WARNING: Failed to download image for {eid}: {e}')

    # Save markdown
    write_exercise_md(EXERCISE_OUT / f'{eid}.md', data)
    return True


if __name__ == '__main__':
    print("SvFF parser module ready.")
    print("Usage: import and use parse_exercise_html() + save_exercise()")
    print(f"Output: {EXERCISE_OUT}/ and {IMAGE_OUT}/")
