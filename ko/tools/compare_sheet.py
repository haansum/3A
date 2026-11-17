"""Cross-variant comparison sheet from feature_sheet.py tiles: one row per variant, one column per
(moment, angle) pair, so the same instant is compared from the same fixed camera.

    python3 tools/compare_sheet.py TILE_DIR OUT.jpg --rows name1,name2,... \
        --cols "peak|close 3/4,peak|side low,ratchet|side low" [--labels "A crescendo,B mixed,..."]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
tdir, out = a[0], a[1]
rows = a[a.index('--rows') + 1].split(',')
cols = [c.split('|') for c in a[a.index('--cols') + 1].split(',')]
labels = a[a.index('--labels') + 1].split(',') if '--labels' in a else rows
title = a[a.index('--title') + 1] if '--title' in a else 'variant comparison'


def tile(name, mom, ang):
    return os.path.join(tdir, f'{name}__{mom.replace(" ", "_")}__{ang.replace(" ", "_").replace("/", "")}.png')


first = next(tile(r, *c) for r in rows for c in cols if os.path.exists(tile(r, *c)))
tw, th = Image.open(first).size
sc = 0.6
tw, th = int(tw * sc), int(th * sc)
pad, side, head, lab = 6, 170, 58, 20
W = Image.new('RGB', (side + len(cols) * (tw + pad) + pad, head + len(rows) * (th + pad) + pad), (250, 250, 248))
d = ImageDraw.Draw(W)
try:
    F = ImageFont.truetype('DejaVuSans.ttf', 14)
    FB = ImageFont.truetype('DejaVuSans-Bold.ttf', 18)
except Exception:
    F = FB = ImageFont.load_default()
d.text((pad, 8), title, fill=(30, 30, 28), font=FB)
for c, (mom, ang) in enumerate(cols):
    d.text((side + pad + c * (tw + pad) + 2, 34), f'{mom} · {ang}', fill=(74, 74, 70), font=F)
for r, (name, lb) in enumerate(zip(rows, labels)):
    y = head + pad + r * (th + pad)
    d.text((pad, y + th // 2 - 8), lb, fill=(30, 30, 28), font=F)
    for c, (mom, ang) in enumerate(cols):
        p = tile(name, mom, ang)
        if os.path.exists(p):
            W.paste(Image.open(p).convert('RGB').resize((tw, th)), (side + pad + c * (tw + pad), y))
W.save(out, quality=88)
print('wrote', out)
