"""2D action marks drawn over full-colour renders (comic-action conventions, original drawing
code): focus/speed lines, motion streaks, twitch marks, shock lines, impact bloom.
Everything is drawn on an RGBA layer at 2x and downsampled, so lines are anti-aliased.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

SS = 2


class Layer:
    def __init__(self, size):
        self.W, self.H = size
        self.im = Image.new('RGBA', (self.W * SS, self.H * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def P(self, p):
        return (p[0] * SS, p[1] * SS)

    def over(self, base):
        lay = self.im.resize((self.W, self.H), Image.LANCZOS)
        return Image.alpha_composite(base.convert('RGBA'), lay)


def focus_lines(L, center, clear=0.30, n=110, rgba=(255, 255, 255, 170), width=(1.5, 6), seed=3, aspect=None):
    """Radial speed lines from the frame edge toward `center`, stopping at a clear ellipse."""
    rnd = random.Random(seed)
    cx, cy = center
    R = math.hypot(L.W, L.H)
    ax = clear * L.W * 0.5
    ay = clear * L.H * 0.5 * (aspect or 1.6)
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.025, 0.025)
        ca, sa = math.cos(a), math.sin(a)
        rin = 1.0 / math.sqrt((ca / ax) ** 2 + (sa / ay) ** 2) * rnd.uniform(1.0, 1.55)
        w = rnd.uniform(*width) / R * 0.5
        p0 = (cx + ca * rin, cy + sa * rin)
        p1 = (cx + math.cos(a - w) * R, cy + math.sin(a - w) * R)
        p2 = (cx + math.cos(a + w) * R, cy + math.sin(a + w) * R)
        L.d.polygon([L.P(p0), L.P(p1), L.P(p2)], fill=rgba)


def streaks(L, center, direction, n=26, length=(120, 420), spread=160, rgba=(255, 255, 255, 190),
            width=(1.5, 4), seed=5, back=40):
    """Motion streaks trailing behind something moving along `direction` (2D px vector)."""
    rnd = random.Random(seed)
    dx, dy = direction
    m = math.hypot(dx, dy) or 1.0
    ux, uy = dx / m, dy / m
    px, py = -uy, ux
    for _ in range(n):
        o = rnd.gauss(0, spread / 2.2)
        s0 = back + rnd.uniform(0, 80)
        ln = rnd.uniform(*length)
        x0, y0 = center[0] - ux * s0 + px * o, center[1] - uy * s0 + py * o
        x1, y1 = x0 - ux * ln, y0 - uy * ln
        w = rnd.uniform(*width) * SS
        L.d.line([L.P((x0, y0)), L.P((x1, y1))], fill=rgba, width=int(w))


def twitch(L, pt, size=34, angle=0.0, seed=0, ink=(25, 22, 28, 255), halo=(255, 255, 255, 235)):
    """Twitch mark: a short jagged zig-zag with two flick ticks, haloed so it reads on any tone."""
    rnd = random.Random(seed)
    ca, sa = math.cos(angle), math.sin(angle)

    def T(x, y):
        return (pt[0] + (x * ca - y * sa) * size, pt[1] + (x * sa + y * ca) * size)

    zz = [(-0.9, 0.0), (-0.45, 0.0), (-0.25, -0.55), (0.0, 0.45), (0.22, -0.35), (0.42, 0.0), (0.9, 0.0)]
    zz = [(x + rnd.uniform(-0.05, 0.05), y * rnd.uniform(0.8, 1.2)) for x, y in zz]
    ticks = [[(-0.75, -0.55), (-0.55, -0.95)], [(0.6, -0.5), (0.85, -0.9)]]
    for col, w in ((halo, 7), (ink, 3)):
        L.d.line([L.P(T(*p)) for p in zz], fill=col, width=w * SS, joint='curve')
        for tk in ticks:
            L.d.line([L.P(T(*p)) for p in tk], fill=col, width=w * SS)


def twitch_cluster(L, pt, outward, size=30, seed=0, k=2):
    """k twitch marks around a body point, pushed outward from the body."""
    rnd = random.Random(seed)
    ox, oy = outward
    m = math.hypot(ox, oy) or 1.0
    base = math.atan2(oy, ox)
    for j in range(k):
        a = base + rnd.uniform(-0.7, 0.7)
        r = size * rnd.uniform(1.4, 2.2)
        q = (pt[0] + math.cos(a) * r, pt[1] + math.sin(a) * r)
        twitch(L, q, size * rnd.uniform(0.8, 1.15), angle=a + math.pi / 2 + rnd.uniform(-0.3, 0.3), seed=seed * 7 + j)


def shock_lines(L, n=70, rgba=(70, 70, 80, 110), seed=9, x_range=None, width=(1, 3)):
    """Vertical shock streaks (the 'stunned' rain), varied length and weight."""
    rnd = random.Random(seed)
    x0, x1 = x_range or (0, L.W)
    for _ in range(n):
        x = rnd.uniform(x0, x1)
        y0 = rnd.uniform(-0.1, 0.6) * L.H
        ln = rnd.uniform(0.15, 0.6) * L.H
        a = int(rgba[3] * rnd.uniform(0.5, 1.0))
        L.d.line([L.P((x, y0)), L.P((x, y0 + ln))], fill=rgba[:3] + (a,), width=int(rnd.uniform(*width) * SS))


def bloom(base, center, radius, strength=0.55):
    """Soft white flash at the impact point."""
    W, H = base.size
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    cx, cy = center
    for k in range(12, 0, -1):
        r = radius * k / 12
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=int(255 * strength * (1 - k / 13)))
    m = m.filter(ImageFilter.GaussianBlur(radius * 0.25))
    white = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    return Image.composite(white, base.convert('RGBA'), m)


def vignette(base, strength=0.35):
    W, H = base.size
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    d.ellipse([-0.15 * W, -0.2 * H, 1.15 * W, 1.2 * H], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(W * 0.08))
    dark = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    inv = m.point(lambda v: int((255 - v) * strength))
    return Image.composite(dark, base.convert('RGBA'), inv)
