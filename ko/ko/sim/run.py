"""Stage 4: simulation. Resolved take config + body.json -> sim.npz (500 Hz record).

Deterministic: same config, same MuJoCo build -> bitwise identical sim.npz arrays.
"""
import json
import os

import mujoco
import numpy as np

from ..body import gen_body
from ..character.bonemap import CANON
from . import reference, scene
from .control import REGIONS, Controller


def lowest_foot_z(m, d):
    z = []
    for f in ('g_foot_L', 'g_foot_R'):
        g = m.geom(f).id
        mid = m.geom_dataid[g]
        v = m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid] + m.mesh_vertnum[mid]]
        z.append((d.geom_xpos[g] + v @ d.geom_xmat[g].reshape(3, 3).T)[:, 2].min())
    return min(z)


def run(cfg, char_dir, out_dir=None, record=True):
    spec = json.load(open(os.path.join(char_dir, 'body.json')))
    sim = cfg['sim']
    dt = sim.get('dt', 0.002)
    m = mujoco.MjModel.from_xml_string(scene.build(gen_body.to_mjcf(spec), cfg['arena'], dt))
    d = mujoco.MjData(m)
    assert m.joint('root').dofadr[0] == 0
    ctl_cfg = dict(cfg['controller'], seed=sim.get('seed', 0))
    ctl = Controller(m, spec, ctl_cfg, spec['mass'])
    ref = reference.make(cfg['motion']['reference'])
    fwd = np.array([0.0, -1.0, 0.0])
    rng = np.random.default_rng(sim.get('seed', 0))
    sig = sim.get('perturb', 0.0)       # relative std of strike impulse/direction/timing
    strikes = []
    for i, st in enumerate(([cfg['strike']] if cfg.get('strike') else []) + list(cfg.get('strikes') or [])):
        st = dict(st)
        st.setdefault('name', 'ko_strike' if i == 0 else f'followup_{i}')
        st['impulse'] = st['impulse'] * (1 + sig * rng.standard_normal())
        st['dir'] = (np.array(st['dir'], float) / np.linalg.norm(st['dir'])
                     + sig * rng.standard_normal(3)).tolist()
        if 't' in st and not st.get('after'):
            st['t'] = st['t'] + 0.2 * sig * rng.standard_normal()
        st['ko'] = st.get('ko', i == 0)
        strikes.append(st)
    strike_log = []

    # initial pose: reference at t=0, feet on the canvas
    q0, _, _, _ = ref.sample(0.0)
    d.qpos[ctl.qadr] = ctl.pose_vec(q0)
    mujoco.mj_forward(m, d)
    d.qpos[2] -= lowest_foot_z(m, d) - 0.002
    mujoco.mj_forward(m, d)
    ctl.set_inertia(d)
    p0 = d.xpos[ctl.pelvis].copy()

    body_ids = np.array([m.body(n).id for n in CANON])
    rope_ids = np.array([b for b in range(m.nbody) if m.body(b).name.startswith('rope')
                         and m.body(b).name.split('_')[-1].isdigit()])
    rope_c = scene.ROPE_DEFAULT['transverse_damp'] if not cfg['arena'].get('rope') else \
        dict(scene.ROPE_DEFAULT, **cfg['arena']['rope'])['transverse_damp']
    rope_prev = d.xpos[rope_ids].copy() if len(rope_ids) else None
    br = ctl_cfg.get('breath', {'period': 4.0, 'amp_deg': 1.5})

    def step(t, settle=False):
        nonlocal rope_prev
        q, qd, adv, vadv = ref.sample(max(t, 0.0))
        q_cmd = ctl.pose_vec(q)
        qd_cmd = ctl.rate_vec(qd)
        d.qfrc_applied[:] = 0
        struck = False
        for st in strikes:
            if settle:
                break
            if 't0' not in st:              # resolve the start time once its clock exists
                if st.get('after'):
                    if st['after'] in ctl.events:
                        st['t0'] = ctl.events[st['after']] + st.get('t', 0.0)
                else:
                    st['t0'] = st['t']
            if 't0' not in st:
                continue
            dur = st.get('duration', 0.015)
            hb = m.body(st.get('body', 'head')).id
            if st['t0'] <= t < st['t0'] + dur:
                dirv = np.array(st['dir'], float)
                dirv /= np.linalg.norm(dirv)
                if st.get('frame', 'world') == 'head':
                    dirv = d.xmat[hb].reshape(3, 3) @ dirv
                pt = d.xipos[hb] + d.xmat[hb].reshape(3, 3) @ np.array(st.get('offset', [0, 0, 0]))
                mujoco.mj_applyFT(m, d, st['impulse'] / dur * dirv, np.zeros(3), pt, hb, d.qfrc_applied)
                struck = True
                if 'logged' not in st:
                    st['logged'] = True
                    ctl.events[st['name']] = t
                    strike_log.append({'name': st['name'], 't': t, 'point': pt.tolist(),
                                       'dir': dirv.tolist(), 'prop': st.get('prop')})
            if st['ko'] and ctl.t_ko is None and t >= st['t0'] + st.get('ko_delay', 0.01):
                ctl.trigger_ko(t, q_cmd)
                mujoco.mj_forward(m, d)
        breath = np.radians(br['amp_deg']) * np.sin(2 * np.pi * t / br['period'])
        tone = ctl.apply(d, t, q_cmd, qd_cmd, breath)
        cap = 3.0 if settle else cfg['motion'].get('assist_cap', 0.15)
        wrench = ctl.root_assist(d, t, p0 + fwd * adv, fwd * vadv, cap)
        if rope_prev is not None:           # in-house rope element: transverse damping
            v = (d.xpos[rope_ids] - rope_prev) / dt
            rope_prev = d.xpos[rope_ids].copy()
            v[:, 0] = 0.0                   # ropes run along x
            d.xfrc_applied[rope_ids, :3] = -rope_c * m.body_mass[rope_ids, None] * v
        mujoco.mj_step(m, d)
        return tone, wrench, struck

    for i in range(int(sim.get('settle', 0.6) / dt)):
        step(0.0, settle=True)
    p0[:2] = d.xpos[ctl.pelvis][:2]        # reference starts where she actually settled
    ctl.set_inertia(d)

    n = int(sim['duration'] / dt)
    rec = {k: [] for k in ('qpos', 'qvel', 'xpos', 'xquat', 'rope', 'tone', 'assist', 'struck',
                           'act')}
    con = []
    fbuf, vbuf = np.zeros(6), np.zeros(6)
    canvas = m.geom('canvas').id
    ghead = m.geom('g_head').id
    Wt = spec['mass'] * 9.81
    gfl, gfr = m.geom('g_foot_L').id, m.geom('g_foot_R').id
    foot_geoms = {gfl, gfr}
    body_geoms = {m.geom(g).id for g in range(m.ngeom) if m.geom(g).name.startswith('g_')} - foot_geoms
    ok = True
    for i in range(n):
        t = i * dt
        tone, wrench, struck = step(t)
        if not np.isfinite(d.qpos).all() or d.warning.number.sum() > 0:
            ok = False
            break
        rec['qpos'].append(d.qpos.copy())
        rec['qvel'].append(d.qvel.copy())
        rec['xpos'].append(d.xpos[body_ids].copy())
        rec['xquat'].append(d.xquat[body_ids].copy())
        rec['rope'].append(d.xpos[rope_ids].copy() if len(rope_ids) else np.zeros((0, 3)))
        rec['tone'].append(tone)
        rec['assist'].append(wrench)
        rec['struck'].append(struck)
        rec['act'].append(d.actuator_force[ctl.aid].copy())
        fl = {g: 0.0 for g in foot_geoms}
        for ci in range(d.ncon):
            c = d.contact[ci]
            mujoco.mj_contactForce(m, d, ci, fbuf)
            if c.geom1 == canvas and c.geom2 in fl:
                fl[c.geom2] += fbuf[0]
            if (c.geom1 == canvas and c.geom2 == ghead and fbuf[0] > 0.3 * Wt
                    and 'head_impact' not in ctl.events and ctl.t_ko is not None):
                ctl.events['head_impact'] = t      # next step's control sees it (2 ms later)
            if (c.geom1 == canvas and c.geom2 in body_geoms and fbuf[0] > 0.05 * Wt
                    and 'down' not in ctl.events and ctl.t_ko is not None):
                ctl.events['down'] = t             # first part other than a foot on the canvas
            slip = 0.0
            if c.geom1 == canvas and c.geom2 in foot_geoms:      # slip speed of the sole point
                b = m.geom_bodyid[c.geom2]
                mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, b, vbuf, 0)
                vp = vbuf[3:] + np.cross(vbuf[:3], c.pos - d.xpos[b])
                slip = float(np.hypot(vp[0], vp[1]))
            con.append((i, c.geom1, c.geom2, c.dist, fbuf[0], slip))
        ctl.update_foot_load(fl[gfl], fl[gfr], dt)
    out = {k: np.array(v) for k, v in rec.items()}
    out['contacts'] = np.array(con, dtype=np.float64).reshape(-1, 6)
    out['t'] = np.arange(len(out['qpos'])) * dt
    out['ok'] = np.array(ok)
    out['t_ko'] = np.array(ctl.t_ko if ctl.t_ko is not None else -1.0)
    out['geom_names'] = np.array([m.geom(g).name for g in range(m.ngeom)])
    out['body_names'] = np.array(CANON)
    out['joint_names'] = np.array(ctl.jn)
    out['joint_qadr'] = ctl.qadr
    out['joint_dadr'] = ctl.dadr
    out['joint_range'] = np.stack([ctl.lo, ctl.hi], 1)
    out['regions'] = np.array(REGIONS)
    out['rope_names'] = np.array([m.body(b).name for b in rope_ids])
    out['mass'] = np.array(spec['mass'])
    out['events'] = np.array(json.dumps(ctl.events))
    out['strikes'] = np.array(json.dumps(strike_log))
    out['dt'] = np.array(dt)
    if out_dir and record:
        os.makedirs(out_dir, exist_ok=True)
        np.savez_compressed(os.path.join(out_dir, 'sim.npz'), **out)
    return out
