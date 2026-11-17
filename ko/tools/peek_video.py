"""Sparse-preview mp4 from a partly rendered video_<v>/frames dir (owner 2026-11-15).
Each missing frame holds the nearest rendered frame before it, so timing is real-time
and the preview sharpens as the bisection-order render fills in.

    python3 tools/peek_video.py FRAMES_DIR NFRAMES OUT.mp4 [--fps 25] [--w 640]
"""
import os
import shutil
import subprocess
import sys
import tempfile

a = sys.argv[1:]
fd, n, out = a[0], int(a[1]), a[2]
fps = a[a.index('--fps') + 1] if '--fps' in a else '25'
w = a[a.index('--w') + 1] if '--w' in a else '640'
have = sorted(int(f[:5]) for f in os.listdir(fd) if f.endswith('.png'))
if not have:
    sys.exit('no frames yet')
tmp = tempfile.mkdtemp()
j = 0
for i in range(n):
    while j + 1 < len(have) and have[j + 1] <= i:
        j += 1
    src = have[j] if have[j] <= i else have[0]
    os.symlink(os.path.join(os.path.abspath(fd), f'{src:05d}.png'), os.path.join(tmp, f'{i:05d}.png'))
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', fps, '-i', f'{tmp}/%05d.png',
                '-vf', f'scale={w}:-2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24',
                '-preset', 'veryfast', out], check=True)
shutil.rmtree(tmp)
print(f'[peek] {len(have)}/{n} frames rendered -> {out}')
