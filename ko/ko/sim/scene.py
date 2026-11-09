"""Scene assembly: canvas + ring ropes + character body -> one MJCF string.

Rope model (see eval/rope_bench.py for the evidence): inextensible capsule chain on ball
joints, open tree rooted at one post, elasticity and preload in the end elements (a sprung
slider and a spring tendon). No equality constraints; armature on the ball joints.
Rope preload, mass, end stiffness, spacer stiffness are ASSUMED values, not measurements.
"""
import math

ROPE_DEFAULT = dict(span=6.0, nseg=16, radius=0.0125, preload=2000.0, k_end=20000.0,
                    rho=1.0, end_damp=1000.0, gap=0.15, joint_damp=1.0, armature=0.002,
                    heights=(0.46, 0.76, 1.07, 1.37), spacer_k=8000.0, spacer_damp=60.0,
                    spacers_at=(0.33, 0.67), transverse_damp=8.0,
                    contact='solref="0.005 1" solimp="0.95 0.99 0.001"', friction=0.9)


def rope_xml(name, y, z, x0, p):
    lc = p['span'] - p['gap']
    seg = lc / p['nseg']
    m = p['rho'] * seg
    d = p['preload'] / p['k_end']
    out = [f'<body name="{name}_a" pos="{x0} {y} {z}">'
           f'<joint name="{name}_sa" type="slide" axis="1 0 0" stiffness="{p["k_end"]}" '
           f'springref="{-d}" damping="{p["end_damp"]}"/>'
           f'<inertial pos="0 0 0" mass="0.05" diaginertia="1e-4 1e-4 1e-4"/>']
    for i in range(p['nseg']):
        out.append(f'<body name="{name}_{i}" pos="{0 if i == 0 else seg} 0 0">'
                   f'<joint name="{name}_b{i}" type="ball" damping="{p["joint_damp"]}" '
                   f'armature="{p["armature"]}"/>'
                   f'<geom name="{name}_g{i}" type="capsule" fromto="0 0 0 {seg} 0 0" '
                   f'size="{p["radius"]}" mass="{m}" friction="{p["friction"]}" contype="2" '
                   f'conaffinity="1" {p["contact"]} rgba=".8 .1 .1 1"/>'
                   f'<site name="{name}_s{i}" pos="{seg / 2} 0 0" size="0.005"/>')
    out.append(f'<site name="{name}_tip" pos="{seg} 0 0"/>')
    out.append('</body>' * (p['nseg'] + 1))
    out.append(f'<site name="{name}_post" pos="{x0 + p["span"]} {y} {z}"/>')
    ten = (f'<spatial name="{name}_t" stiffness="{p["k_end"]}" damping="{p["end_damp"]}" '
           f'springlength="{p["gap"] - d}"><site site="{name}_tip"/>'
           f'<site site="{name}_post"/></spatial>')
    return ''.join(out), ten


def build(body_frag, arena, dt=0.002):
    """arena: {'rope_y': float|None (rope side at this y, running along x), 'rope': overrides,
               'canvas_friction': float}"""
    assets, body, acts, excl = body_frag
    p = dict(ROPE_DEFAULT, **(arena.get('rope') or {}))
    world, tendons = [], []
    if arena.get('rope_y') is not None:
        x0 = -p['span'] / 2
        hs = list(p['heights'])
        for i, z in enumerate(hs):
            b, t = rope_xml(f'rope{i}', arena['rope_y'], z, x0, p)
            world.append(b)
            tendons.append(t)
        for i in range(len(hs) - 1):          # vertical spacer straps between neighbours
            for f in p['spacers_at']:
                k = int(round(f * (p['nseg'] - 1)))
                tendons.append(
                    f'<spatial name="sp{i}_{k}" stiffness="{p["spacer_k"]}" '
                    f'damping="{p["spacer_damp"]}" springlength="{hs[i + 1] - hs[i]}">'
                    f'<site site="rope{i}_s{k}"/><site site="rope{i + 1}_s{k}"/></spatial>')
    fr = arena.get('canvas_friction', 0.9)
    return f'''<mujoco model="ko_take">
  <option timestep="{dt}" integrator="implicitfast" cone="elliptic" impratio="10">
    <flag multiccd="enable"/>
  </option>
  <size memory="400M"/>
  <asset>{assets}</asset>
  <worldbody>
    <light pos="0 0 6" dir="0 0 -1"/>
    <geom name="canvas" type="plane" size="12 12 .1" friction="{fr}" solref="0.006 1"
          solimp="0.9 0.98 0.002" rgba=".75 .78 .8 1"/>
    {body}
    {''.join(world)}
  </worldbody>
  <tendon>{''.join(tendons)}</tendon>
  <contact>{excl}</contact>
  <actuator>{acts}</actuator>
</mujoco>'''
