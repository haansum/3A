"""Brandless swim-team uniform for a garment, designed on the body (not in UV space).

    python3 tools/swim_uniform.py CHARACTER_BLEND MESH OUT.png [--size 2048] [--to-canonical SKELETON_JSON]

Owner 2026-11-18: Izzy's leotard re-textured "to look like a brandless swimming team uniform".
Every texel of the garment's UV map is rasterised with the rest-pose body position it maps to
(her canonical frame: x = her left, y = back, z = up), and coloured from that position:
navy body, lighter blue side panels from hip to armpit with thin white piping at the panel
edge, and a faint knit noise. No logos, text or marks. The original texture file is not
touched; the render swaps this one in (character preset `texture_overrides`).
Colours and panel widths by eye.
"""
import json
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, mesh_name, out = a[0], a[1], a[2]
size = int(a[a.index('--size') + 1]) if '--size' in a else 2048
bpy.ops.wm.open_mainfile(filepath=src)
ob = bpy.data.objects[mesh_name]
Rinv = Matrix.Identity(4)
if '--to-canonical' in a:
    tc = json.load(open(a[a.index('--to-canonical') + 1]))['to_canonical']
    Rinv = (Matrix.Translation(Vector(tc['origin'])) @ Matrix.Rotation(tc['yaw'], 4, 'Z')
            @ Matrix.Scale(1.0 / tc['scale'], 4)).inverted()
me = ob.data
me.calc_loop_triangles()
uv = me.uv_layers.active.data
M = Rinv @ ob.matrix_world
P = np.array([(M @ v.co)[:] for v in me.vertices])

N = size // 2                                  # raster at half size, upsampled
pos = np.full((N, N, 3), np.nan)
for tri in me.loop_triangles:
    t_uv = np.array([uv[li].uv[:] for li in tri.loops]) * (N - 1)
    t_p = P[list(tri.vertices)]
    x0, y0 = np.floor(t_uv.min(0)).astype(int)
    x1, y1 = np.ceil(t_uv.max(0)).astype(int)
    if x1 < 0 or y1 < 0 or x0 >= N or y0 >= N:
        continue
    xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1, N - 1) + 1), np.arange(max(y0, 0), min(y1, N - 1) + 1))
    q = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1)
    A, B, C = t_uv
    v0, v1, v2 = B - A, C - A, q - A
    den = v0[0] * v1[1] - v1[0] * v0[1]
    if abs(den) < 1e-12:
        continue
    l1 = (v2[:, 0] * v1[1] - v1[0] * v2[:, 1]) / den
    l2 = (v0[0] * v2[:, 1] - v2[:, 0] * v0[1]) / den
    l0 = 1 - l1 - l2
    ok = (l0 >= -0.02) & (l1 >= -0.02) & (l2 >= -0.02)
    if not ok.any():
        continue
    w = np.stack([l0, l1, l2], 1)[ok]
    pts = w @ t_p
    pos[ys.ravel()[ok], xs.ravel()[ok]] = pts
covered = ~np.isnan(pos[..., 0])
print('uv coverage %.1f%%' % (100 * covered.mean()))

# colour from body position
x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
navy = np.array([18, 30, 70], float)
panel = np.array([42, 110, 178], float)
white = np.array([236, 238, 242], float)
col = np.tile(navy, (N, N, 1))
zc = np.nanmedian(z[covered])
# side panels: the outer part of the torso, hip to armpit
side = np.abs(x) - (0.085 + 0.02 * np.clip((z - zc) / 0.25, -1, 1))
in_panel = covered & (side > 0)
col[in_panel] = panel
pipe = covered & (np.abs(side) < 0.006)
col[pipe] = white
# knit noise (fine, low amplitude)
rng = np.random.default_rng(3)
col += rng.normal(0, 3.0, col.shape)
col[~covered] = navy                       # outside the islands: padding colour
img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)[::-1], 'RGB').resize((size, size), Image.LANCZOS)
img.save(out)
print('saved', out, img.size, 'panel texels %.1f%% piping %.1f%%' % (100 * in_panel.mean(), 100 * pipe.mean()))
