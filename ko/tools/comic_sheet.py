"""Comic-page version of a contact sheet (owner 2026-11-16: "present it in comic style").

    python3 tools/comic_sheet.py SHEET.jpg OUT.jpg [--res 640] [--layout TAKE] [--title TEXT]

Crops the tiles back out of a contact_sheet.py sheet (same layout constants) and lays them out
as a comic page: black-bordered panels of varied size, white gutters, caption boxes and a
few SFX. LAYOUTS holds panel picks and captions per take (default: the original
izzy_uppercut_spring_001 page); picks index the sheet's tiles in order and are weighted to the
knockdown, descent and aftermath (house rule: >= 70% of panels). Comic effects belong on these
sheets only; no blood or injury detail.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
src, out = a[0], a[1]
res = int(a[a.index('--res') + 1]) if '--res' in a else 640
TW, TH = res, int(res * 9 / 16)
PAD, LAB, HEAD, COLS = 6, 22, 40, 4
S = Image.open(src).convert('RGB')


def tile(i):
    x = PAD + (i % COLS) * (TW + PAD)
    y = HEAD + PAD + (i // COLS) * (TH + LAB + PAD)
    return S.crop((x, y, x + TW, y + TH))


def font(sz, bold=True):
    for f in (('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'), 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(f, sz)
        except Exception:
            pass
    return ImageFont.load_default()


# rows of (tile index, relative width, caption, sfx); row height in px
# row height is derived so the narrowest panel keeps ~1.8:1 (close to the 16:9 frames, so the
# crop never takes her head or feet off)
LAYOUTS = {
    'izzy_uppercut_spring_001': ('IZZY  ·  UPPERCUT', [
    [(0, 1.0, 'She steps in.', None), (1, 1.15, None, 'KRAK!')],
    [(3, 1.0, 'Chin snapped up. Lights out.', None), (5, 1.0, None, None), (7, 1.0, 'The knees load...', None)],
    [(9, 1.15, '...and spring her back.', None), (10, 1.0, None, 'THUD')],
    [(12, 1.0, 'Flat out.', None), (13, 1.0, None, 'WHAP!'), (15, 1.0, None, None)],
    [(16, 1.0, None, None), (18, 1.15, 'Locked up: fists clenched, toes pointed, ankles crossed.', None)],
    ]),
}
lay = a[a.index('--layout') + 1] if '--layout' in a else 'izzy_uppercut_spring_001'
TITLE, ROWS = LAYOUTS[lay]
if '--title' in a:
    TITLE = a[a.index('--title') + 1]

W, G, M = 2400, 18, 40


def row_h(panels):
    avail = W - 2 * M - G * (len(panels) - 1)
    return int(avail * min(p[1] for p in panels) / sum(p[1] for p in panels) / 1.8)


ROWS = [(row_h(p), p) for p in ROWS]
H = M * 2 + sum(h for h, _ in ROWS) + G * (len(ROWS) - 1) + 90
page = Image.new('RGB', (W, H), (250, 248, 240))
d = ImageDraw.Draw(page)
d.text((M, 22), TITLE, fill=(20, 20, 20), font=font(52))
y = M + 90
for h, panels in ROWS:
    tot = sum(p[1] for p in panels)
    avail = W - 2 * M - G * (len(panels) - 1)
    x = M
    for idx, rw, cap, sfx in panels:
        w = int(avail * rw / tot)
        im = tile(idx)
        s = max(w / im.width, h / im.height)          # cover-fit, centre crop
        im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
        # crop around her, not the frame centre: centroid of skin-tone pixels (R > G > B, warm)
        import numpy as np
        A = np.asarray(im).astype(int)
        mk = (A[..., 0] > 150) & (A[..., 0] - A[..., 2] > 35) & (A[..., 0] > A[..., 1]) & (A[..., 1] > A[..., 2])
        ys_, xs_ = np.nonzero(mk)
        cx, cy = (xs_.mean(), ys_.mean()) if len(xs_) > 200 else (im.width / 2, im.height / 2)
        ox = int(min(max(cx - w / 2, 0), im.width - w))
        oy = int(min(max(cy - h / 2, 0), im.height - h))
        page.paste(im.crop((ox, oy, ox + w, oy + h)), (x, y))
        d.rectangle((x - 2, y - 2, x + w + 1, y + h + 1), outline=(10, 10, 10), width=6)
        if cap:
            f = font(26, bold=False)
            words, lines, cur = cap.split(), [], ''
            for wd in words:                           # wrap to ~45% of the panel width
                t_ = (cur + ' ' + wd).strip()
                if d.textlength(t_, font=f) > max(260, 0.45 * w):
                    lines.append(cur)
                    cur = wd
                else:
                    cur = t_
            lines.append(cur)
            bw = int(max(d.textlength(l_, font=f) for l_ in lines)) + 28
            bh = 34 * len(lines) + 18
            d.rectangle((x + 10, y + 10, x + 10 + bw, y + 10 + bh), fill=(255, 236, 140), outline=(10, 10, 10), width=3)
            for k, l_ in enumerate(lines):
                d.text((x + 24, y + 18 + 34 * k), l_, fill=(15, 15, 15), font=f)
        if sfx:
            f = font(96)
            tx, ty = x + w - int(d.textlength(sfx, font=f)) - 30, y + h - 140
            for dx in range(-5, 6, 1):                 # heavy black outline, then fill
                for dy in (-5, 0, 5):
                    d.text((tx + dx, ty + dy), sfx, fill=(10, 10, 10), font=f)
            d.text((tx, ty), sfx, fill=(255, 214, 40), font=f)
        x += w + G
    y += h + G
page.save(out, quality=92)
print('comic', out, page.size)
