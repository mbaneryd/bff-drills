#!/usr/bin/env python3
"""
Extract exercise diagram images from JSK PDF files.
Saves images to static/images/jsk/ and updates exercise markdown files.

Run from project root: python3 tools/extract_jsk_images.py
"""
import json, sys, re, io
from pathlib import Path
import pdfplumber
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from extract_jsk import page_exercise_num, strip_footer, PDFS, TITLE_OVERRIDES
from common import write_exercise_md

IMAGE_OUT = Path('static/images/jsk')
EXERCISE_DIR = Path('content/exercises/jsk')
MANIFEST_PATH = Path('sources/jsk/_exercises.json')


def extract_images_from_pdf(pdf_path, age_group):
    """Return dict: exercise_num -> (image_bytes, extension)."""
    images = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = strip_footer(page.extract_text() or '')
            num, _ = page_exercise_num(text)
            if num is None or num in images:
                continue
            if not page.images:
                continue
            img_meta = page.images[0]
            try:
                data = img_meta['stream'].get_data()
                if data[:3] == b'\xff\xd8\xff':
                    images[num] = (data, 'jpg')
                elif data[:4] == b'\x89PNG':
                    images[num] = (data, 'png')
                else:
                    try:
                        img = Image.open(io.BytesIO(data))
                        buf = io.BytesIO()
                        img.convert('RGB').save(buf, 'JPEG', quality=90)
                        images[num] = (buf.getvalue(), 'jpg')
                    except Exception as ce:
                        print(f'  WARNING: cannot convert image for {age_group} ex {num}: {ce}')
            except Exception as e:
                print(f'  ERROR extracting image for {age_group} ex {num}: {e}')
    return images


def main():
    IMAGE_OUT.mkdir(parents=True, exist_ok=True)
    total_saved = 0

    for pdf_info in PDFS:
        pdf_path = pdf_info['file']
        age_group = pdf_info['age_group']
        age_slug = age_group.replace('-', '_')

        print(f'\nProcessing {age_group} ({pdf_path})...')
        images = extract_images_from_pdf(pdf_path, age_group)
        print(f'  Found images for {len(images)} exercises')

        for ex_num, (img_data, ext) in sorted(images.items()):
            ex_id = f'jsk_{age_slug}_{ex_num}'
            img_filename = f'{ex_id}.{ext}'
            img_path = IMAGE_OUT / img_filename

            img_path.write_bytes(img_data)
            total_saved += 1

        print(f'  Saved {len(images)} images')

    print(f'\nDone. Total images extracted: {total_saved}')
    print(f'Images saved to: {IMAGE_OUT}/')


if __name__ == '__main__':
    main()
