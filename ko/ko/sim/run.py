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


def lowest_z(m, d, names):
    z = []
    for f in names:
        g = m.geom(f).id
        if m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
            z.append(d.geom_xpos[g][2] - m.geom_size[g, 0])
            continue
        mid = m.geom_dataid[g]
        v = m.mesh_vert[m.mesh_vertadr[mid]:m.mesh_vertadr[mid] + m.mesh_vertnum[mid]]
        z.append((d.geom_xpos[g] + v @ d.geom_xmat[g].reshape(3, 3).T)[:, 2].min())
    return min(z)


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
    frag = gen_body.to_mjcf(spec, self_pairs=sim.get('self_pairs'), exclude_pairs=sim.get('exclude_pairs'))
    fc_ = sim.get('flesh_contact')
    paired_ = {}                                # segment -> (friction, solref, solimp)
    names_ = {b_['name'] for b_ in spec['bodies']}
    ar_ = cfg['arena']
    f0_ = max(ar_.get('canvas_friction', 0.9), 0.9)  # what MuJoCo's max-mix gave before
    if fc_:
        # soft flesh on the canvas (2026-11-17): a rigid hull meeting the canvas stopped in one 2 ms
        # step (38-51 BW single-step spikes, the 'furniture' landing). Fleshy segments get their own
        # canvas contact through explicit pairs: softer and wider, so a landing decelerates over tens
        # of ms. Only canvas contacts change; self contacts and bony segments keep the stiff contact.
        # The extra sink (<= 11 mm) is what the render-time flattening deformer shows. Off by default.
        for s_ in fc_.get('segments', scene.FLESH_SEGMENTS):
            if s_ in names_:
                paired_[s_] = (f0_, fc_.get('solref', '0.010 1'), fc_.get('solimp', '0.9 0.95 0.005'))
    for s_, pc_ in (sim.get('canvas_pairs') or {}).items():
        # per-segment canvas contact (2026-11-17): e.g. the head slides on its hair layer instead of
        # gripping like rubber, so a face-first landing rolls onto a cheek instead of tucking under
        if s_ in names_:
            # default = what MuJoCo's equal-solmix average of body geom and canvas gave before
            avg_ = lambda a, b: ' '.join(f'{(float(x) + float(y)) / 2:g}' for x, y in zip(a.split(), b.split()))
            f_, r_, i_ = paired_.get(s_, (f0_, avg_('0.005 1', str(ar_.get('canvas_solref', '0.006 1'))),
                                          avg_('0.95 0.99 0.001', str(ar_.get('canvas_solimp', '0.9 0.98 0.002')))))
            paired_[s_] = (pc_.get('friction', f_), pc_.get('solref', r_), pc_.get('solimp', i_))
    flesh_ = list(paired_)
    if paired_:
        frag = frag[:3] + (frag[3] + ''.join(
            f'<pair geom1="canvas" geom2="g_{s_}" condim="3" friction="{f_} {f_} 0.005 0.0001 0.0001" '
            f'solref="{r_}" solimp="{i_}" margin="{ar_.get("canvas_margin", 0)}"/>'
            for s_, (f_, r_, i_) in paired_.items()),)
    G = None
    xml = scene.build(frag, cfg['arena'], dt)
    if cfg.get('grapple'):
        # a hold (handoff track G): attacker arms + unseen torso anchor, soft-welded to targets
        from .grapple import Grapple
        G = Grapple(cfg['grapple'])
        gb_, ge_ = G.mjcf()
        xml = xml.replace('</worldbody>', gb_ + '</worldbody>', 1).replace('</mujoco>', f'<equality>{ge_}</equality></mujoco>', 1)
    m = mujoco.MjModel.from_xml_string(xml)
    if flesh_:
        # filter the flesh segments' automatic canvas contact (the pair above replaces it): canvas
        # moves to bit 4 (keeping rope affinity on bit 2), every other body geom gains bit 4
        cv_ = m.geom('canvas').id
        m.geom_contype[cv_], m.geom_conaffinity[cv_] = 4, 6
        fid_ = {m.geom('g_' + s_).id for s_ in flesh_}
        for g_ in range(m.ngeom):
            if g_ != cv_ and m.geom_bodyid[g_] != 0 and g_ not in fid_ and m.geom_contype[g_] & 1:
                m.geom_contype[g_] |= 4
                m.geom_conaffinity[g_] |= 4
    slide_ = None
    if sim.get('slide'):
        # {after: event, t: s after it, ramp: s, friction: value, segments: [...]}; see the step loop
        sl_ = sim['slide']
        cvs_ = m.geom('canvas').id
        bids_ = {m.body(s_).id for s_ in sl_.get('segments', ('foot_L', 'foot_R', 'shin_L', 'shin_R'))}
        sg_ = [g_ for g_ in range(m.ngeom) if m.geom_bodyid[g_] in bids_]
        rz_ = [g_ for g_ in range(m.ngeom) if g_ != cvs_ and m.geom_bodyid[g_] != 0 and g_ not in sg_]
        slide_ = {'after': sl_.get('after', 'release'), 't': float(sl_.get('t', 0.0)), 'ramp': float(sl_.get('ramp', 0.3)),
                  'friction': float(sl_['friction']), 'canvas': cvs_, 'f0': float(m.geom_friction[cvs_, 0]),
                  'geoms': sg_, 'raise': rz_, 'own': {g_: float(m.geom_friction[g_, 0]) for g_ in range(m.ngeom)}}
    if sim.get('limit_solref'):
        # soft end of range (owner 2026-11-17: joints spring at the end of their range; a hard
        # stop also chattered when limp feet rested on it): [time constant s, damping ratio] for
        # every body joint's limit; ropes untouched. Off by default, so old takes are unchanged.
        tc_, dr_ = (float(x) for x in sim['limit_solref'])
        for b_ in spec['bodies']:
            for j_ in b_['joints']:
                m.jnt_solref[m.joint(j_['name']).id] = (tc_, dr_)
    d = mujoco.MjData(m)
    assert m.joint('root').dofadr[0] == 0
    ctl_cfg = dict(cfg['controller'], seed=sim.get('seed', 0), dt=dt)
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
    if sim.get('start') == 'seated':        # sits on the canvas: lowest part of her, not the feet
        d.qpos[2] -= lowest_z(m, d, [m.geom(g).name for g in range(m.ngeom) if m.geom(g).name.startswith('g_')
                                     and m.geom_contype[g]]) - 0.002
    else:
        d.qpos[2] -= lowest_foot_z(m, d) - 0.002
    mujoco.mj_forward(m, d)
    jerks = None
    if G is not None:
        G.bind(m)
        G.start(m, d)
        mujoco.mj_forward(m, d)
        if cfg['grapple'].get('jerks', 'pronounced'):
            from .jerks import Jerks
            jerks = [Jerks(cfg['grapple'].get('jerks', 'pronounced'), ctl, np.random.default_rng(sim.get('seed', 0) + 7))]
            if cfg['grapple'].get('wake_jerks'):
                jerks.append(Jerks(cfg['grapple']['wake_jerks'], ctl, np.random.default_rng(sim.get('seed', 0) + 11)))
            for j_ in jerks:
                j_.gain_changes = cfg['grapple'].get('jerk_changes')
            if (cfg['controller'].get('ko') or {}).get('wake_motor'):
                # organic coming-round model (waking.py, owner 2026-11-27)
                from .waking import WakeMotor
                ctl.wake_motor = WakeMotor(cfg['controller']['ko']['wake_motor'], ctl,
                                           np.random.default_rng(sim.get('seed', 0) + 13))
                jerks.append(ctl.wake_motor)
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
        if G is not None:
            if not settle and ctl.t_ko is None and t >= cfg['grapple'].get('close_at', 0.3):
                ctl.trigger_ko(t, q_cmd)        # the hold is on: the choke driver takes over L
            G.step(d, t, ctl.events)
            ctl.cons.released = 'release' in ctl.events
        if slide_ is not None and slide_['after'] in ctl.events:
            # heels slide (owner 2026-11-26: "the legs slide down and extend, limp"): from an
            # event on, the listed segments meet the canvas at a lower friction, ramped in.
            # Contact friction is the max of the two geoms, so the canvas geom drops to the slide
            # value and every other body geom is raised to the canvas value it met before: only
            # the listed segments' canvas contacts change (self contacts between body geoms
            # already at >= that value are unchanged). Explicit pairs keep their own friction.
            w_ = min(1.0, max(0.0, (t - ctl.events[slide_['after']] - slide_['t']) / max(slide_['ramp'], 1e-6)))
            if w_ > 0.0:
                fs_ = slide_['f0'] + (slide_['friction'] - slide_['f0']) * w_
                m.geom_friction[slide_['canvas'], 0] = fs_
                for g_ in slide_['raise']:
                    m.geom_friction[g_, 0] = max(slide_['own'][g_], slide_['f0'])
                for g_ in slide_['geoms']:
                    m.geom_friction[g_, 0] = min(slide_['own'][g_], fs_)
            if jerks is not None and not settle:
                for j_ in jerks:
                    j_.apply(d, t, ctl.events)
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
                           'act', 'L', 'authority')}
    con = []
    fbuf, vbuf = np.zeros(6), np.zeros(6)
    canvas = m.geom('canvas').id
    ghead = m.geom('g_head').id
    gchest = m.geom('g_chest').id
    Wt = spec['mass'] * 9.81
    gfl, gfr = m.geom('g_foot_L').id, m.geom('g_foot_R').id
    foot_geoms = {gfl, gfr}
    body_geoms = {m.geom(g).id for g in range(m.ngeom) if m.geom(g).name.startswith('g_')} - foot_geoms
    ok = True
    hbody = m.body('head').id
    head_state = {'last_on': None, 'armed': False, 'n': 1}
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
        rec['L'].append(ctl.cons.level(t))
        rec['authority'].append(ctl.cons.authority(ctl.cons.level(t)))
        if G is not None:
            fl_, fr_, sc_ = G.squeeze(d, Wt)
            ctl.cons.feed(t, sc_, dt)
            G.record(d, fl_, fr_, sc_)
        fl = {g: 0.0 for g in foot_geoms}
        head_f = 0.0
        for ci in range(d.ncon):
            c = d.contact[ci]
            mujoco.mj_contactForce(m, d, ci, fbuf)
            if c.geom1 == canvas and c.geom2 in fl:
                fl[c.geom2] += fbuf[0]
            if c.geom1 == canvas and c.geom2 == ghead:
                head_f += fbuf[0]
            if (c.geom1 == canvas and c.geom2 == ghead and fbuf[0] > 0.3 * Wt
                    and 'head_impact' not in ctl.events and ctl.t_ko is not None):
                ctl.events['head_impact'] = t      # next step's control sees it (2 ms later)
                mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, hbody, vbuf, 0)
                ctl.event_data['head_impact'] = {'speed': float(np.linalg.norm(vbuf[3:])),
                                                 'force_bw': float(fbuf[0] / Wt)}
            if (c.geom1 == canvas and c.geom2 in body_geoms and fbuf[0] > 0.05 * Wt
                    and 'down' not in ctl.events and ctl.t_ko is not None):
                ctl.events['down'] = t             # first part other than a foot on the canvas
            if (c.geom1 == canvas and c.geom2 == gchest and fbuf[0] > 0.1 * Wt
                    and 'chest_down' not in ctl.events and ctl.t_ko is not None):
                ctl.events['chest_down'] = t       # trunk landed: the body's roll is decided by now
            slip = 0.0
            if c.geom1 == canvas and c.geom2 in foot_geoms:      # slip speed of the sole point
                b = m.geom_bodyid[c.geom2]
                mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, b, vbuf, 0)
                vp = vbuf[3:] + np.cross(vbuf[:3], c.pos - d.xpos[b])
                slip = float(np.hypot(vp[0], vp[1]))
            con.append((i, c.geom1, c.geom2, c.dist, fbuf[0], slip))
        # later head impacts (bounce, re-contact): head off the canvas >= 0.12 s, then back
        if 'head_impact' in ctl.events:
            if head_f < 0.02 * Wt:
                if head_state['last_on'] is not None and t - head_state['last_on'] >= 0.12:
                    head_state['armed'] = True
            else:
                if head_state['armed'] and head_f > 0.25 * Wt:
                    head_state['n'] += 1
                    nm = f'head_impact_{head_state["n"]}'
                    ctl.events[nm] = t
                    mujoco.mj_objectVelocity(m, d, mujoco.mjtObj.mjOBJ_BODY, hbody, vbuf, 0)
                    ctl.event_data[nm] = {'speed': float(np.linalg.norm(vbuf[3:])),
                                          'force_bw': float(head_f / Wt)}
                    head_state['armed'] = False
                head_state['last_on'] = t
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
    if getattr(ctl, 'wake_motor', None) is not None:
        ctl.event_data['wake_motor'] = {'moves': ctl.wake_motor.log, 'twitches': len(ctl.wake_motor.pulses)}
    out['event_data'] = np.array(json.dumps(ctl.event_data))
    out['strikes'] = np.array(json.dumps(strike_log))
    out['dt'] = np.array(dt)
    if G is not None:
        out.update(G.arrays())
    if out_dir and record:
        os.makedirs(out_dir, exist_ok=True)
        np.savez_compressed(os.path.join(out_dir, 'sim.npz'), **out)
    return out
