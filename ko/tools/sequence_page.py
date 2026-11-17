"""Build the sequence page (owner 2026-11-14): full-size panels in reading order, sized by the
pacing class from plan.json, act kickers, a time strip of where each panel sits in the take.

    python3 tools/sequence_page.py PLAN_DIR FRAMES_DIR NAME OUT_DIR --title T --sub S --end SECONDS
writes OUT_DIR/index.html and OUT_DIR/panels/<n>.jpg (publish OUT_DIR as an artifact).
"""
import html
import json
import os
import sys

from PIL import Image

a = sys.argv[1:]
pd, fd, name, od = a[:4]
opt = lambda k, d: a[a.index(k) + 1] if k in a else d  # noqa: E731
title = opt('--title', 'KO sequence')
sub = opt('--sub', '')
end = float(opt('--end', '8.5'))
plan = json.load(open(os.path.join(pd, 'plan.json')))
os.makedirs(os.path.join(od, 'panels'), exist_ok=True)

ACT = {'setup': 'The read', 'strike': 'The strike', 'knockdown': 'Knockdown',
       'descent': 'Descent', 'aftermath': 'Aftermath'}
focus = sum(p['act'] in ('knockdown', 'descent', 'aftermath') for p in plan)

panels, ticks, last_act = [], [], None
for i, p in enumerate(plan):
    src = os.path.join(fd, f"{name}_{p['name']}.png")
    im = Image.open(src).convert('RGB')
    rel = f"panels/{i + 1:02d}_{p['name']}.jpg"
    im.save(os.path.join(od, rel), quality=86, optimize=True, progressive=True)
    kicker = ''
    if p['act'] != last_act:
        kicker = f'<h2 class="act act-{p["act"]}">{ACT[p["act"]]}</h2>'
        last_act = p['act']
    before = ' before-release' if p['size'] == 'xl' else ''
    panels.append(f'''{kicker}<figure class="panel size-{p['size']}{before}" id="p{i + 1}">
  <img src="{rel}" alt="Panel {i + 1}: {html.escape(p['name'])}, {html.escape(p['why'])}" loading="{'eager' if i < 3 else 'lazy'}" width="{im.width}" height="{im.height}">
  <figcaption><span class="n">{i + 1:02d}</span><span class="t">{p['t']:.2f} s</span><span class="w">{html.escape(p['why'])}</span></figcaption>
</figure>''')
    ticks.append(f'<a class="tick act-{p["act"]}" href="#p{i + 1}" style="left:{100 * p["t"] / end:.2f}%" title="{i + 1:02d} {p["name"]} {p["t"]:.2f} s"></a>')

doc = f'''<title>{html.escape(title)}</title>
<style>
:root{{--paper:#f4f1ea;--ink:#121212;--muted:#6b665d;--rule:#d8d2c6;--setup:#8a8578;--strike:#c8322a;--knockdown:#1d1d1d;--descent:#1d1d1d;--aftermath:#1d1d1d;--bg:#e9e5dc}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--paper:#151515;--ink:#ecebe7;--muted:#9a958b;--rule:#2b2b2b;--setup:#7c776d;--strike:#e2533b;--knockdown:#ecebe7;--descent:#ecebe7;--aftermath:#ecebe7;--bg:#0c0c0c;color-scheme:dark}}}}
:root[data-theme="dark"]{{--paper:#151515;--ink:#ecebe7;--muted:#9a958b;--rule:#2b2b2b;--setup:#7c776d;--strike:#e2533b;--knockdown:#ecebe7;--descent:#ecebe7;--aftermath:#ecebe7;--bg:#0c0c0c;color-scheme:dark}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}}
.page{{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:28px 80px;background:var(--paper);box-sizing:border-box;min-height:100%}}
header{{display:grid;gap:8px;margin-bottom:28px}}
.kick{{font:600 12px/1 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--strike)}}
h1{{font:800 clamp(28px,5vw,52px)/1.02 "Archivo Black","Arial Black",system-ui,sans-serif;letter-spacing:-.01em;margin:0;text-wrap:balance}}
.sub{{color:var(--muted);max-width:68ch;margin:0}}
.strip{{position:relative;height:34px;margin:18px 0 4px;border-top:2px solid var(--ink)}}
.tick{{position:absolute;top:-9px;width:3px;height:16px;margin-left:-1px;background:var(--ink)}}
.tick.act-setup{{background:var(--setup)}}.tick.act-strike{{background:var(--strike)}}
.strip .lab{{position:absolute;top:12px;font:11px "IBM Plex Mono",ui-monospace,monospace;color:var(--muted);font-variant-numeric:tabular-nums}}
.stat{{font:12px "IBM Plex Mono",ui-monospace,monospace;color:var(--muted)}}
.seq{{display:flex;flex-wrap:wrap;gap:14px;justify-content:center}}
.act{{flex:0 0 100%;font:800 13px/1 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.2em;text-transform:uppercase;margin:34px 0 0;padding-top:12px;border-top:1px solid var(--rule)}}
.act-strike{{color:var(--strike)}}
.panel{{margin:0;min-width:0;display:flex;flex-direction:column;gap:6px}}
.panel img{{display:block;width:100%;height:auto;border:3px solid var(--ink);background:#000}}
.size-s{{flex:0 1 calc(50% - 7px)}}
.size-m{{flex:0 1 72%}}
.size-l{{flex:0 1 86%}}
.size-xl,.size-w{{flex:0 1 100%}}
.size-xl img{{border-width:5px}}
.before-release{{margin-top:36px}}
.size-w{{margin-top:40px}}.size-w img{{border-width:2px}}
figcaption{{display:flex;gap:10px;align-items:baseline;font-size:13px;color:var(--muted);min-width:0}}
figcaption .n{{font:700 12px "IBM Plex Mono",ui-monospace,monospace;color:var(--ink)}}
figcaption .t{{font:12px "IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;white-space:nowrap}}
figcaption .w{{min-width:0}}
footer{{margin-top:48px;color:var(--muted);font-size:13px;max-width:72ch}}
@media (max-width:640px){{.size-s,.size-m,.size-l{{flex-basis:100%}}}}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@400;600&display=swap">
<div class="page">
<header>
  <span class="kick">Sequence</span>
  <h1>{html.escape(title)}</h1>
  <p class="sub">{html.escape(sub)}</p>
  <div class="strip" aria-label="Where each panel sits in the {end:.1f} s take">{''.join(ticks)}<span class="lab" style="left:0">0 s</span><span class="lab" style="right:0">{end:.1f} s</span></div>
  <span class="stat">{len(plan)} panels · {focus} of them ({100 * focus / len(plan):.0f}%) on the knockdown, descent and aftermath</span>
</header>
<main class="seq">
{chr(10).join(panels)}
</main>
<footer>Physics sim (MuJoCo) baked onto the rig and rendered in Cycles at draft settings (1600 px, 32 samples, 1K textures). Comic marks are drawn over the renders: speed lines on motion, focus lines on contact, twitch marks on one extremity; the last panel carries none. Fall direction, timing and contacts come from the sim; strike tuning, tone envelopes and camera choices are set by eye.</footer>
</div>
'''
open(os.path.join(od, 'index.html'), 'w').write(doc)
print('wrote', os.path.join(od, 'index.html'), len(plan), 'panels')
