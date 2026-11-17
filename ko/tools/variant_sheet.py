"""Comic contact map of camera-angle variants (owner 2026-11-14): one row per beat, one column
per variant (A house, B worm, C overhead, D profile, E pov/ringside), regular renders with the
comic marks, labelled so a pick reads as e.g. "impact C".

    python3 tools/variant_sheet.py FRAMES_DIR NAME OUT.jpg [--tile 384] [--beats read,rise,...]
Expects FRAMES_DIR/NAME_<X>/NAME_<X>_<beat>.png (one action_frames run per variant X).
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
fd, name, out = a[:3]
tile = int(a[a.index('--tile') + 1]) if '--tile' in a else 384
beats = (a[a.index('--beats') + 1].split(',') if '--beats' in a else
         ['read', 'rise', 'impact', 'whip', 'snap', 'stagger', 'face', 'canvas', 'climax'])
VAR = [('A', 'house'), ('B', 'worm'), ('C', 'overhead'), ('D', 'profile'), ('E', 'pov / ringside')]
if '--vars' in a:                      # e.g. --vars A,B,C  (A/B/C options per panel)
    VAR = [(x, 'option ' + x) for x in a[a.index('--vars') + 1].split(',')]
PLAN = {p_['name']: p_ for p_ in json.load(open(a[a.index('--plan') + 1]))} if '--plan' in a else {}
CAT = {'A': 'house', 'B': 'worm', 'C': 'overhead', 'D': 'profile', 'E': 'pov/ringside'}
FACE = {'A': 'front 3/4', 'B': 'profile', 'C': 'chin/crown'}
th = tile * 9 // 16
pad, lab, head_h, left = 10, 22, 74, 128
INK, PAPER, MUTED = (20, 20, 20), (246, 243, 236), (120, 116, 108)


def font(sz, bold=False):
    for p in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


F_T, F_B, F_S = font(22, True), font(15, True), font(12)
W = left + len(VAR) * (tile + pad) + pad
H = head_h + len(beats) * (th + lab + pad) + pad
sheet = Image.new('RGB', (W, H), PAPER)
d = ImageDraw.Draw(sheet)
d.text((pad, 12), f'{name} - camera options (pick per panel, e.g. "impact C")', font=F_T, fill=INK)
for j, (X, nm) in enumerate(VAR):
    d.text((left + j * (tile + pad), head_h - 20), f'{X}  {nm}', font=F_B, fill=INK)
for i, beat in enumerate(beats):
    y = head_h + i * (th + lab + pad)
    d.text((pad, y + th // 2 - 10), beat.replace('face_', 'face ').upper(), font=F_B, fill=INK)
    for j, (X, nm) in enumerate(VAR):
        x = left + j * (tile + pad)
        p = os.path.join(fd, f'{name}_{X}', f'{name}_{X}_{beat}.png')
        if os.path.exists(p):
            im = Image.open(p).convert('RGB').resize((tile, th), Image.LANCZOS)
            sheet.paste(im, (x, y))
            d.rectangle([x - 1, y - 1, x + tile, y + th], outline=INK, width=2)
        else:
            d.rectangle([x, y, x + tile, y + th], outline=MUTED, width=1)
            d.text((x + 8, y + 8), 'not rendered', font=F_S, fill=MUTED)
        what = (FACE.get(X, '') if beat.startswith('face_') else
                CAT.get(PLAN.get(beat, {}).get('abc', {}).get(X, ''), '')) if PLAN else ''
        d.text((x, y + th + 4), f'{beat} {X}' + (f'  ({what})' if what else ''), font=F_S, fill=MUTED)
sheet.save(out, quality=88)
print('wrote', out, sheet.size)
