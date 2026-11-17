"""A/B/C comic pages from angle_panels.py renders (owner 2026-11-16).

    python3 tools/comic_pages.py ANGLES_DIR NAME_PREFIX TITLE

Reads ANGLES_DIR/shots_done.json (+ the PNGs), writes ANGLES_DIR/<NAME_PREFIX>_<V>_comic.jpg per
variant. Same styling as comic_sheet.py: black-bordered panels, caption boxes, SFX.
Rows of 2-3-2-3 panels; row height keeps the narrowest panel near 16:9 so nothing is cropped off.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

d_, pre, title = sys.argv[1:4]
shots = json.load(open(os.path.join(d_, 'shots_done.json')))
NAMES = {'A': 'A · ringside', 'B': 'B · canvas level', 'C': 'C · overhead + close-ups'}


def font(sz, bold=True):
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', sz)
    except Exception:
        return ImageFont.load_default()


W, G, M = 2400, 18, 40
for v in sorted({s['variant'] for s in shots}):
    ps = [s for s in shots if s['variant'] == v]
    rows, k = [], 0
    for n in (2, 3, 2, 3, 3, 3):
        if k >= len(ps):
            break
        rows.append(ps[k:k + n])
        k += n
    hs = [int((W - 2 * M - G * (len(r) - 1)) / len(r) / 1.78) for r in rows]
    H = M * 2 + 90 + sum(hs) + G * (len(rows) - 1)
    page = Image.new('RGB', (W, H), (250, 248, 240))
    d = ImageDraw.Draw(page)
    d.text((M, 22), f'{title}  ·  {NAMES.get(v, v)}', fill=(20, 20, 20), font=font(52))
    y = M + 90
    for r, h in zip(rows, hs):
        w = int((W - 2 * M - G * (len(r) - 1)) / len(r))
        x = M
        for s in r:
            im = Image.open(os.path.join(d_, s['id'] + '.png')).convert('RGB')
            sc_ = max(w / im.width, h / im.height)
            im = im.resize((int(im.width * sc_ + 0.5), int(im.height * sc_ + 0.5)), Image.LANCZOS)
            ox, oy = (im.width - w) // 2, (im.height - h) // 2
            page.paste(im.crop((ox, oy, ox + w, oy + h)), (x, y))
            d.rectangle((x - 2, y - 2, x + w + 1, y + h + 1), outline=(10, 10, 10), width=6)
            f = font(22, False)
            d.text((x + w - 120, y + h - 34), f"{s['id']} {s['t']:.2f}s", fill=(255, 255, 255), font=f,
                   stroke_width=2, stroke_fill=(0, 0, 0))
            cap = s.get('cap')
            if cap:
                f = font(26, False)
                lines, cur = [], ''
                for wd in cap.split():
                    t_ = (cur + ' ' + wd).strip()
                    if d.textlength(t_, font=f) > max(260, 0.5 * w):
                        lines.append(cur)
                        cur = wd
                    else:
                        cur = t_
                lines.append(cur)
                bw = int(max(d.textlength(l_, font=f) for l_ in lines)) + 28
                d.rectangle((x + 10, y + 10, x + 10 + bw, y + 28 + 34 * len(lines)), fill=(255, 236, 140),
                            outline=(10, 10, 10), width=3)
                for j, l_ in enumerate(lines):
                    d.text((x + 24, y + 18 + 34 * j), l_, fill=(15, 15, 15), font=f)
            sfx = s.get('sfx')
            if sfx:
                f = font(int(min(110, 0.11 * w)))
                tx, ty = x + w - int(d.textlength(sfx, font=f)) - 30, y + h - int(0.11 * w) - 50
                d.text((tx, ty), sfx, fill=(255, 214, 40), font=f, stroke_width=6, stroke_fill=(10, 10, 10))
            x += w + G
        y += h + G
    out = os.path.join(d_, f'{pre}_{v}_comic.jpg')
    page.save(out, quality=92)
    print('comic', out, page.size)
