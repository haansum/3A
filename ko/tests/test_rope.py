"""Rope element against the analytic cable solution (assumed rope parameters)."""
import math

import mujoco
import numpy as np

from ko.sim import scene

P = scene.ROPE_DEFAULT


def model(spacers=False):
    p = dict(P, heights=(1.0,))
    b, t = scene.rope_xml('rope0', 0.0, 1.0, -p['span'] / 2, p)
    xml = f'''<mujoco><option timestep="0.002" integrator="implicitfast"/>
      <worldbody>{b}</worldbody><tendon>{t}</tendon></mujoco>'''
    return mujoco.MjModel.from_xml_string(xml)


def settle(m, d, T, load_body=None, W=0.0, damp=P['transverse_damp']):
    ids = np.array([b for b in range(m.nbody) if m.body(b).name.split('_')[-1].isdigit()])
    prev = d.xpos[ids].copy()
    tr = []
    mid = m.body(f"rope0_{P['nseg'] // 2}").id
    for _ in range(int(T / 0.002)):
        v = (d.xpos[ids] - prev) / 0.002
        prev = d.xpos[ids].copy()
        v[:, 0] = 0
        d.xfrc_applied[ids, :3] = -damp * m.body_mass[ids, None] * v
        if load_body is not None:
            d.xfrc_applied[load_body, 2] -= W
        mujoco.mj_step(m, d)
        tr.append(1.0 - d.xpos[mid][2])
    return np.array(tr)


def test_self_weight_sag_matches_cable_formula():
    m = model()
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    tr = settle(m, d, 4.0)
    analytic = P['rho'] * 9.81 * P['span'] ** 2 / (8 * P['preload'])
    assert abs(tr[-500:].mean() - analytic) / analytic < 0.10


def test_transverse_ringing_dies_within_a_second_or_so():
    m = model()
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    tr = settle(m, d, 3.0)
    assert np.ptp(tr[-250:]) < 0.002          # < 2 mm peak-to-peak after 2.5 s
    undamped = settle(m, mujoco.MjData(m), 3.0, damp=0.0)
    assert np.ptp(undamped[-250:]) > 5 * np.ptp(tr[-250:])   # the in-house element is what does it


def test_loaded_sag_within_ten_percent_of_nonlinear_cable():
    m = model()
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    settle(m, d, 2.0)
    W = 55 * 9.81
    tr = settle(m, d, 5.0, load_body=m.body(f"rope0_{P['nseg'] // 2}").id, W=W)
    k_eff, L, T0 = P['k_end'] / 2, P['span'], P['preload']
    lo, hi = 0.0, 2.0
    for _ in range(60):
        s = 0.5 * (lo + hi)
        half = math.hypot(L / 2, s)
        lo, hi = (s, hi) if 2 * (T0 + k_eff * (2 * half - L)) * s / half < W else (lo, s)
    assert abs(tr[-500:].mean() - s) / s < 0.10
