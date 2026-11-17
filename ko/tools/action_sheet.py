"""Contact sheet of action frames: the beats in order, a label with beat name, time and the marks
that fired. Full-size frames stay alongside; this is the review overview.

    python3 tools/action_sheet.py FRAMES.json OUT.jpg [--title T] [--cols 3] [--tile 640]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
src, out = a[0], a[1]
title = a[a.index('--title') + 1] if '--title' in a else ''
cols = int(a[a.index('--cols') + 1]) if '--cols' in a else 3
tw = int(a[a.index('--tile') + 1]) if '--tile' in a else 640
th = tw * 9 // 16
rep = json.load(open(src))
items = sorted(rep.items(), key=lambda kv: kv[1]['t'])


def F(sz, bold=False):
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', sz)
    except Exception:
        return ImageFont.load_default()


pad, lab = 14, 40
rows = (len(items) + cols - 1) // cols
top = 56 if title else pad
W = pad + cols * (tw + pad)
H = top + rows * (th + lab + pad)
sheet = Image.new('RGB', (W, H), (246, 245, 242))
d = ImageDraw.Draw(sheet)
if title:
    d.text((pad, 16), title, font=F(24, True), fill=(24, 24, 28))
for k, (beat, r) in enumerate(items):
    x = pad + (k % cols) * (tw + pad)
    y = top + (k // cols) * (th + lab + pad)
    im = Image.open(r['file']).convert('RGB').resize((tw, th), Image.LANCZOS)
    sheet.paste(im, (x, y))
    d.text((x, y + th + 5), f'{k + 1}  {beat.upper()}', font=F(15, True), fill=(24, 24, 28))
    extra = []
    if r.get('spit'):
        extra.append('spit')
    if r.get('twitch'):
        extra.append('twitch: ' + r['twitch'][0].replace('_', ' '))
    for m in r.get('marks', []):
        if m in ('focus', 'streak', 'bloom'):
            extra.append({'focus': 'focus lines', 'streak': 'speed lines', 'bloom': 'flash'}[m])
    d.text((x, y + th + 23), f"{r['t']:.2f} s · frame {r['frame']}" + ('  ·  ' + ', '.join(extra) if extra else ''),
           font=F(12), fill=(90, 90, 96))
sheet.save(out, quality=92)
print('wrote', out)
