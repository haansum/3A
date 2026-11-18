"""Alternate skin texture for a second use of the same character (owner 2026-11-18: the attacker's
arms are Izzy's, with "an alternate texture for her hands"): every given texture is re-toned to a
warmer, deeper tan and written under a new folder with the same file name, so the render can swap
it in on a copy of the material. The originals are never touched. Tone by eye.

    python3 tools/alt_skin.py OUT_DIR SRC_IMAGE [SRC_IMAGE ...] [--tone r,g,b]
"""
import os
import sys

import numpy as np
from PIL import Image

a = sys.argv[1:]
tone = np.array([float(x) for x in a[a.index('--tone') + 1].split(',')]) if '--tone' in a else np.array([0.80, 0.63, 0.50])
srcs = [x for x in a[1:] if not x.startswith('--') and not x.replace(',', '').replace('.', '').isdigit()]
os.makedirs(a[0], exist_ok=True)
for s in srcs:
    im = np.asarray(Image.open(s).convert('RGB')).astype(np.float32) / 255.0
    lin = im ** 2.2
    lin = lin * tone / tone.max() * 0.85
    outp = os.path.join(a[0], os.path.basename(s))
    Image.fromarray((np.clip(lin, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).save(outp, quality=92)
    print('wrote', outp)
