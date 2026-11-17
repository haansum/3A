"""Manga / action-comic treatment for renders: screentone halftone, ink edges, speed lines,
impact bursts, sound-effect lettering, caption boxes. Pure PIL + numpy.

Style reference: black-and-white action manga. Everything here is original drawing code and
generic onomatopoeia; no existing artwork or lettering is reproduced.
"""
import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT_SFX = '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'      # JP katakana, heavy
FONT_CAP = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_CAP_I = '/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf'


def font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        return ImageFont.load_default()


def screentone(gray, cell=6, angle=45):
    """Gray (L, 0..255) -> 1-bit-looking halftone dots on a rotated grid."""
    g = np.asarray(gray, float) / 255.0
    h, w = g.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    a = math.radians(angle)
    u = (xx * math.cos(a) + yy * math.sin(a)) / cell
    v = (-xx * math.sin(a) + yy * math.cos(a)) / cell
    d = np.hypot(u - np.round(u), v - np.round(v)) / 0.7071          # 0 at dot centre .. 1 at corner
    ink = (1.0 - g)                                                     # how much black
    dots = d < np.sqrt(np.clip(ink, 0, 1)) * 1.02
    return Image.fromarray(np.where(dots, 0, 255).astype(np.uint8), 'L')


def to_manga(img, cell=5, black=0.22, white=0.80, edge=1.0, mask=None, lo=2, hi=97, gamma=1.0):
    """Render -> manga panel: solid blacks, white highlights, screentone mid-tones, ink lines.
    mask (L image): normalise contrast on those pixels only (the figure), not on the ground."""
    if mask is None:
        g = ImageOps.autocontrast(img.convert('L'), cutoff=1)
    else:
        L_ = np.asarray(img.convert('L'), float)
        sel = L_[np.asarray(mask) > 200]
        a0, a1 = (np.percentile(sel, [lo, hi]) if sel.size > 100 else (0.0, 255.0))
        n = np.clip((L_ - a0) / max(a1 - a0, 1.0), 0, 1) ** gamma
        g = Image.fromarray((n * 255).astype(np.uint8), 'L')
    a = np.asarray(g, float) / 255.0
    tone = screentone(g, cell)
    out = np.asarray(tone, float)
    out = np.where(a < black, 0, out)
    out = np.where(a > white, 255, out)
    # ink lines: edges of the luminance, thickened
    e = g.filter(ImageFilter.GaussianBlur(1.0)).filter(ImageFilter.FIND_EDGES)
    e = np.asarray(e.point(lambda p: 255 if p > 22 / max(edge, 1e-3) else 0).filter(ImageFilter.MaxFilter(3)), float)
    out = np.where(e > 0, 0, out)
    return Image.fromarray(out.astype(np.uint8), 'L').convert('RGB')


def speed_lines(img, center, n=90, inner=0.18, seed=3, color=(0, 0, 0), width=(1, 5)):
    """Radial focus lines toward `center` (px), leaving a clear disc of radius inner*diag."""
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    W, H = img.size
    R = math.hypot(W, H)
    cx, cy = center
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.03, 0.03)
        r0 = R * (inner + rnd.uniform(0.0, 0.12))
        wdt = rnd.uniform(*width) / 180.0
        p1 = (cx + math.cos(a - wdt) * R, cy + math.sin(a - wdt) * R)
        p2 = (cx + math.cos(a + wdt) * R, cy + math.sin(a + wdt) * R)
        p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
        d.polygon([p0, p1, p2], fill=color)
    return img


def burst(img, center, r_in, r_out, spikes=14, seed=1, fill=(255, 255, 255), outline=(0, 0, 0), width=5):
    rnd = random.Random(seed)
    cx, cy = center
    pts = []
    for k in range(spikes * 2):
        a = math.pi * k / spikes + rnd.uniform(-0.08, 0.08)
        r = (r_out * rnd.uniform(0.8, 1.15)) if k % 2 == 0 else r_in * rnd.uniform(0.85, 1.1)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    d = ImageDraw.Draw(img)
    d.polygon(pts, fill=fill, outline=outline, width=width)
    return img


def sfx(img, text, pos, size, angle=-12, fill=(255, 255, 255), stroke=(0, 0, 0), sw=None):
    """Big sound-effect lettering: white fill, heavy black stroke, rotated, pasted at pos."""
    f = font(FONT_SFX, size)
    sw = sw or max(3, size // 9)
    tmp = Image.new('RGBA', (int(size * (len(text) + 1.2)), int(size * 1.7)), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    d.text((sw + 4, sw), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
    tmp = tmp.crop(tmp.getbbox() or (0, 0, 1, 1)).rotate(angle, expand=True, resample=Image.BICUBIC)
    img.paste(tmp, (int(pos[0]), int(pos[1])), tmp)
    return img


def caption(img, xy, lines, size=18, pad=8, italic_first=False):
    """Rectangular caption box (narration style): white, thin black border."""
    d = ImageDraw.Draw(img)
    fs = [font(FONT_CAP_I if (k == 0 and italic_first) else FONT_CAP, size if k == 0 else int(size * 0.8))
          for k in range(len(lines))]
    wd = max(d.textlength(t, font=f_) for t, f_ in zip(lines, fs)) + 2 * pad
    ht = sum(f_.size + 4 for f_ in fs) + 2 * pad
    x, y = xy
    d.rectangle([x, y, x + wd, y + ht], fill=(255, 255, 255), outline=(0, 0, 0), width=3)
    yy = y + pad
    for t, f_ in zip(lines, fs):
        d.text((x + pad, yy), t, font=f_, fill=(0, 0, 0))
        yy += f_.size + 4
    return (wd, ht)


def impact_flash(img, center):
    """Anime-style impact frame: inverted, crushed to near two tones, radial lines."""
    g = ImageOps.autocontrast(img.convert('L'), cutoff=2)
    g = g.point(lambda p: 0 if p < 95 else (255 if p > 170 else 128))
    inv = ImageOps.invert(g).convert('RGB')
    speed_lines(inv, center, n=110, inner=0.10, color=(255, 255, 255), width=(1, 4), seed=11)
    return inv
