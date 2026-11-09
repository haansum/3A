"""Simulator evaluation bench for the KO framework design (MuJoCo candidate).

Measures, on CPU, the things the build-vs-buy decision hinges on:
  A. rope fidelity   - static sag of a pretensioned rope vs the analytic cable solution
  B. contact         - a 55 kg body dropped on one rope: penetration, stability
  C. full scene      - limp ragdoll walking-speed fall into a 4-rope ring side:
                       NaNs, penetration, velocity spikes, speed, determinism

Run:  python ko/eval/rope_bench.py
Everything here is a stand-in model (assumed rope preload/mass/stiffness, box-and-capsule
ragdoll). It tests the engine, not the final character.
"""
import json
import math
import sys
import time

import mujoco
import numpy as np

L = 6.0          # rope span, m
NSEG = 16        # capsules per span (same discretisation as the old prototype)
R_ROPE = 0.0125  # 25 mm rope
T0 = 2000.0      # preload, N            (ASSUMED, not measured)
K_END = 20000.0  # end spring, N/m each  (ASSUMED)
RHO = 1.0        # rope mass, kg/m       (ASSUMED)
G = 9.81
ROPE_JDAMP = 1.0   # N m s/rad, bend/twist damping per ball joint (ASSUMED)
ROPE_ARM = 0.002    # kg m^2 armature: stops near-zero axial inertia spinning up
END_DAMP = 1000.0   # N s/m at each end = 5% of K_END per second (ASSUMED; old-prototype value)
GAP = 0.15          # m, post-to-rope-end gap spanned by the end tendon
SOLREF = 0.004      # s, rope contact time constant (default 0.02 is far too soft)


def rope_xml(name, y, z, zeta=0.05):
    """Inextensible capsule chain on ball joints, an open tree rooted at post A.
    Elasticity and preload live at the ends: a sprung slider at A, a spring tendon at B.
    No equality constraints (a soft `connect` closure stretched 3 cm under preload)."""
    lc = L - GAP                      # chain length; the tendon spans the remaining gap
    seg = lc / NSEG
    m = RHO * seg
    d = T0 / K_END
    c = END_DAMP
    out = [f'<body name="{name}_a" pos="0 {y} {z}">'
           f'<joint name="{name}_sa" type="slide" axis="1 0 0" stiffness="{K_END}" '
           f'springref="{-d}" damping="{c}"/>'
           f'<inertial pos="0 0 0" mass="0.05" diaginertia="1e-4 1e-4 1e-4"/>']
    for i in range(NSEG):
        out.append(f'<body name="{name}_{i}" pos="{0 if i == 0 else seg} 0 0">'
                   f'<joint name="{name}_b{i}" type="ball" damping="{ROPE_JDAMP}" '
                   f'armature="{ROPE_ARM}"/>'
                   f'<geom name="{name}_g{i}" type="capsule" fromto="0 0 0 {seg} 0 0" '
                   f'size="{R_ROPE}" mass="{m}" friction="0.9" contype="2" conaffinity="1" '
                   f'solref="{SOLREF} 1" solimp="0.95 0.99 0.002"/>')
    out.append(f'<site name="{name}_tip" pos="{seg} 0 0"/>')
    out.append('</body>' * (NSEG + 1))
    out.append(f'<site name="{name}_post" pos="{L} {y} {z}"/>')
    ten = (f'<spatial name="{name}_t" stiffness="{K_END}" damping="{c}" '
           f'springlength="{GAP - d}"><site site="{name}_tip"/><site site="{name}_post"/></spatial>')
    return ''.join(out), ten


def scene(bodies, eqs, dt, extra=''):
    return f'''<mujoco>
  <option timestep="{dt}" integrator="implicitfast" cone="elliptic" impratio="10"/>
  <size memory="200M"/>
  <worldbody>
    <geom name="canvas" type="plane" size="10 10 .1" friction="0.9" conaffinity="1" contype="1"/>
    {bodies}
  </worldbody>
  <tendon>{eqs}</tendon>
  {extra}
</mujoco>'''


def analytic_sag(W):
    """Point load W at midspan, preload T0, two end springs in series (k_eff = K_END/2)."""
    k_eff = K_END / 2
    lo, hi = 0.0, 2.0
    for _ in range(80):
        s = 0.5 * (lo + hi)
        half = math.hypot(L / 2, s)
        T = T0 + k_eff * (2 * half - L)
        if 2 * T * s / half < W:
            lo = s
        else:
            hi = s
    return s


def bench_static(dt):
    """Time-mean sag (the rope keeps ringing: see transverse_ring_cm) vs analytic."""
    b, e = rope_xml('r', 0, 1.0)
    m = mujoco.MjModel.from_xml_string(scene(b, e, dt))
    d = mujoco.MjData(m)
    mid = m.body(f'r_{NSEG // 2}').id

    def settle(T, tail=2.0):
        tr = []
        for _ in range(int(T / dt)):
            mujoco.mj_step(m, d)
            tr.append(1.0 - d.xpos[mid][2])
        tr = np.array(tr[-int(tail / dt):])
        return float(tr.mean()), float(np.ptp(tr))

    self_sag, ring = settle(6.0)
    W = 55 * G
    d.xfrc_applied[mid, 2] = -W
    sag, ring_loaded = settle(8.0)
    return dict(dt=dt,
                self_sag_cm=round(100 * self_sag, 2),
                self_sag_analytic_cm=round(100 * RHO * G * L * L / (8 * T0), 2),
                transverse_ring_cm_after_4s=round(100 * ring, 2),
                load_sag_m=round(sag, 4),
                load_sag_analytic_m=round(analytic_sag(W) + RHO * G * L * L / (8 * T0), 4),
                load_sag_linear_m=round(W * L / (4 * T0), 4),
                loaded_ring_cm=round(100 * ring_loaded, 2))


def bench_drop(dt):
    b, e = rope_xml('r', 0, 1.0)
    b += ('<body name="w" pos="3 0 1.4"><joint name="wz" type="slide" axis="0 0 1"/>'
          '<geom name="wg" type="capsule" fromto="0 -0.25 0 0 0.25 0" size="0.08" mass="55"/></body>')
    m = mujoco.MjModel.from_xml_string(scene(b, e, dt))
    d = mujoco.MjData(m)
    for _ in range(int(1.0 / dt)):   # let the rope settle first
        d.qpos[-1] = 0
        d.qvel[-1] = 0
        mujoco.mj_step(m, d)
    pen, zmin, vmax, crossings, prev = 0.0, 9.0, 0.0, 0, 0.0
    wid = m.body('w').id
    for _ in range(int(3.0 / dt)):
        mujoco.mj_step(m, d)
        if not np.isfinite(d.qpos).all():
            return dict(dt=dt, nan=True)
        for c in d.contact[:d.ncon]:
            pen = min(pen, c.dist)
        zmin = min(zmin, d.xpos[wid][2])
        vz = d.cvel[wid][5]
        vmax = max(vmax, abs(vz))
        if prev < 0 <= vz:
            crossings += 1
        prev = vz
    return dict(dt=dt, nan=False, max_penetration_mm=round(-1000 * pen, 2),
                lowest_z_m=round(float(zmin), 3), rebounds=crossings,
                rest_z_m=round(float(d.xpos[wid][2]), 3),
                held=bool(d.ncon > 0),
                final_speed=round(float(abs(d.qvel[-1])), 4))


def ragdoll_xml():
    """Limp 13-body ragdoll, ~60 kg, 1.7 m. Passive damping only: this is the post-KO body."""
    j = 'damping="2" armature="0.01"'
    return f'''
    <body name="pelvis" pos="3 -0.45 0.98"><freejoint name="root"/>
      <geom type="capsule" fromto="-.09 0 0 .09 0 0" size=".10" mass="9"/>
      <body name="torso" pos="0 0 .12">
        <joint type="ball" {j} range="0 35"/>
        <geom type="capsule" fromto="-.10 0 .16 .10 0 .16" size=".12" mass="20"/>
        <body name="head" pos="0 0 .44">
          <joint type="ball" {j} range="0 50"/>
          <geom type="sphere" size=".10" mass="4.5"/>
        </body>
        {''.join(f"""
        <body name="uarm{s}" pos="{x} 0 .30">
          <joint type="ball" {j} range="0 120"/>
          <geom type="capsule" fromto="0 0 0 0 0 -.27" size=".04" mass="1.8"/>
          <body name="farm{s}" pos="0 0 -.27">
            <joint type="hinge" axis="1 0 0" range="-140 0" {j}/>
            <geom type="capsule" fromto="0 0 0 0 0 -.30" size=".035" mass="1.4"/>
          </body>
        </body>""" for s, x in (('L', .2), ('R', -.2)))}
      </body>
      {''.join(f"""
      <body name="thigh{s}" pos="{x} 0 -.04">
        <joint type="ball" {j} range="0 110"/>
        <geom type="capsule" fromto="0 0 0 0 0 -.42" size=".065" mass="6.5"/>
        <body name="shin{s}" pos="0 0 -.42">
          <joint type="hinge" axis="1 0 0" range="0 150" {j}/>
          <geom type="capsule" fromto="0 0 0 0 0 -.40" size=".045" mass="2.8"/>
          <body name="foot{s}" pos="0 0 -.42">
            <joint type="hinge" axis="1 0 0" range="-40 25" {j}/>
            <geom type="box" pos="0 .06 -.03" size=".045 .12 .03" mass=".9"/>
          </body>
        </body>
      </body>""" for s, x in (('L', .09), ('R', -.09)))}
    </body>'''


def ring_scene(dt):
    bodies, eqs = ragdoll_xml(), ''
    for i, z in enumerate((0.45, 0.75, 1.05, 1.35)):
        b, e = rope_xml(f'rope{i}', 0, z)
        bodies += b
        eqs += e
    return scene(bodies, eqs, dt)


def bench_ring(dt, T=4.0, record=False):
    m = mujoco.MjModel.from_xml_string(ring_scene(dt))
    d = mujoco.MjData(m)
    root = m.joint('root')
    qa, va = root.qposadr[0], root.dofadr[0]
    # face +y... ropes run along x at y=0; ragdoll starts at y=-1.2 moving toward them
    d.qvel[va + 1] = 2.5          # 2 m/s toward the ropes (stand-in for real footwork momentum)
    d.qvel[va + 3] = -1.5         # forward pitch rate
    n = int(T / dt)
    pen, wmax, nan = 0.0, 0.0, False
    rope_geoms = {g for g in range(m.ngeom) if m.geom(g).name.startswith('rope')}
    rope_pen = 0.0
    t0 = time.perf_counter()
    for _ in range(n):
        mujoco.mj_step(m, d)
        if not np.isfinite(d.qpos).all():
            nan = True
            break
        for c in d.contact[:d.ncon]:
            pen = min(pen, c.dist)
            if c.geom1 in rope_geoms or c.geom2 in rope_geoms:
                rope_pen = min(rope_pen, c.dist)
        wmax = max(wmax, float(np.abs(d.qvel).max()))
    wall = time.perf_counter() - t0
    res = dict(dt=dt, nv=m.nv, nbody=m.nbody, nan=nan,
               max_penetration_mm=round(-1000 * pen, 2),
               max_rope_penetration_mm=round(-1000 * rope_pen, 2),
               max_dof_speed=round(wmax, 1),
               pelvis_final=[round(float(x), 3) for x in d.qpos[qa:qa + 3]],
               steps_per_s=round(n / wall), realtime_factor=round(n * dt / wall, 1))
    if record:
        res['state'] = d.qpos.copy()
    return res


def main():
    out = {'mujoco': mujoco.__version__,
           'assumed': dict(T0=T0, K_END=K_END, RHO=RHO, NSEG=NSEG, L=L)}
    out['A_static_sag'] = [bench_static(dt) for dt in (0.002, 0.001)]
    out['B_drop_55kg'] = [bench_drop(dt) for dt in (0.005, 0.002, 0.001)]
    ring = []
    for dt in (0.005, 0.002, 0.001):
        ring.append(bench_ring(dt))
    out['C_ring_ragdoll'] = ring
    a = bench_ring(0.002, record=True)['state']
    b = bench_ring(0.002, record=True)['state']
    out['C_deterministic_bitwise'] = bool(np.array_equal(a, b))
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == '__main__':
    main()
