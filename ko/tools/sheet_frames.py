"""Contact-sheet frames through the render stage's stills path, then tiled in contact_sheet.py's
layout (so comic_sheet.py can crop them back out).

    python3 tools/sheet_frames.py TAKE.yaml OUT_DIR --times t1,t2,... [--shot live] [--res 640]

contact_sheet.py renders from the saved scene.blend and ran >10 min a frame here (2026-11-17);
the stills path renders the same scene at ~10 s a frame once warm.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from ko import cli  # noqa: E402

a = sys.argv[1:]
take, outd = a[0], a[1]
times = [float(x) for x in a[a.index('--times') + 1].split(',')]
shot = a[a.index('--shot') + 1] if '--shot' in a else 'live'
res = int(a[a.index('--res') + 1]) if '--res' in a else 640
os.makedirs(outd, exist_ok=True)
lock, dirs, _ = cli.build(take, None, 'bake', ['noqa'])
lock = dict(lock, render=dict(lock['render'], still_times=times, still_shots=[shot],
                              res=[res, int(res * 9 / 16)]))
from ko.render import render  # noqa: E402
render.run(lock, dirs['bake'], dirs['sim'], outd, stills=True)
fps = lock['render']['fps']
n_frames = None
files = []
for t in times:
    f = max(1, int(t * fps + 1))
    p = os.path.join(outd, f'still_{shot}_{f:04d}.png')
    if not os.path.exists(p):           # clamped to the last frame
        cand = sorted(x for x in os.listdir(outd) if x.startswith(f'still_{shot}_'))
        p = os.path.join(outd, cand[-1])
    files.append((p, f, t))
tw, th = res, int(res * 9 / 16)
pad, lab, head, cols = 6, 22, 40, 4
rows = (len(files) + cols - 1) // cols
W = Image.new('RGB', (cols * (tw + pad) + pad, rows * (th + lab + pad) + pad + head), (250, 250, 248))
d = ImageDraw.Draw(W)
try:
    F, FB = ImageFont.truetype('DejaVuSans.ttf', 14), ImageFont.truetype('DejaVuSans-Bold.ttf', 18)
except Exception:
    F = FB = ImageFont.load_default()
name = lock['take']
d.text((pad, 10), f'{name}  ·  {shot}  ·  {len(files)} frames @ {fps} fps', fill=(30, 30, 28), font=FB)
for i, (p, f, t) in enumerate(files):
    x = pad + (i % cols) * (tw + pad)
    y = head + pad + (i // cols) * (th + lab + pad)
    W.paste(Image.open(p).convert('RGB').resize((tw, th)), (x, y))
    d.text((x + 2, y + th + 3), f'f{f:>3}   {t:5.2f} s', fill=(74, 74, 70), font=F)
sheet = os.path.join(outd, f'{name}_contact_sheet.jpg')
W.save(sheet, quality=92)
print('sheet', sheet)
