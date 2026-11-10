"""Stage 5: automated QA on sim.npz. Cheapest checks first; any FAIL stops the chain before
Blender is touched. Thresholds are first-guess starting values pending owner sign-off.

Not implemented yet (need the baked render mesh): render-mesh penetration, hair/cloth
stability, framing and occlusion. They are listed in the report as 'todo' so nobody reads a
pass as covering them.
"""
import numpy as np

TH = dict(limit_overshoot_deg=5.0, spike_rad_s=30.0, spike_window_s=0.033,
          spike_contact_window_s=0.05, foot_slide_m=0.02, planted_load_frac=0.2,
          sim_penetration_mm=5.0, self_penetration_mm=10.0, jitter_deg_rms=0.5,
          assist_slack=1.02)


def _mask(names, pred):
    return np.array([pred(n) for n in names])


def check(sim_path, lock):
    z = np.load(sim_path, allow_pickle=False)
    t, dt = z['t'], float(z['dt'])
    gn = [str(n) for n in z['geom_names']]
    bn = [str(n) for n in z['body_names']]
    W = float(z['mass']) * 9.81
    t_ko = float(z['t_ko'])
    C = z['contacts']                       # step, geom1, geom2, dist, normal force
    cs, g1, g2, cd, cf, slip = (C[:, 0].astype(int), C[:, 1].astype(int), C[:, 2].astype(int),
                                C[:, 3], C[:, 4], C[:, 5])
    is_rope = _mask(gn, lambda n: n.startswith('rope'))
    is_body = _mask(gn, lambda n: n.startswith('g_'))
    is_canvas = _mask(gn, lambda n: n == 'canvas')
    rep = {'checks': [], 'metrics': {}}

    def add(gate, name, ok, value, limit, note=''):
        rep['checks'].append({'gate': gate, 'name': name, 'pass': bool(ok), 'value': value,
                              'limit': limit, 'note': note})

    # 1. sim sanity -------------------------------------------------------------------------
    add(1, 'finite_and_no_solver_warning', bool(z['ok']), bool(z['ok']), True)
    q = z['qpos'][:, z['joint_qadr']]
    ov = np.degrees(np.maximum(z['joint_range'][:, 0] - q, q - z['joint_range'][:, 1]))
    over = ov.max()
    wj = str(z['joint_names'][ov.max(axis=0).argmax()])
    add(1, 'joint_limit_overshoot_deg', over <= TH['limit_overshoot_deg'], round(float(over), 2),
        TH['limit_overshoot_deg'], f'worst joint {wj} at t={t[ov.max(axis=1).argmax()]:.2f}')

    qd = z['qvel'][:, z['joint_dadr']]
    w = max(1, int(TH['spike_window_s'] / dt))
    dv = np.abs(qd[w:] - qd[:-w]).max(axis=1)
    excused = np.zeros(len(t), bool)                 # a contact or the strike nearby explains it
    cw = int(TH['spike_contact_window_s'] / dt)
    load = np.zeros(len(t))                          # impacts = fast changes in total load
    np.add.at(load, cs, cf)
    hard = np.nonzero(np.abs(load[cw:] - load[:-cw]) > 0.25 * W)[0] + cw
    for s in np.concatenate([hard, np.nonzero(z['struck'])[0]]):
        excused[max(0, s - cw):s + cw + w] = True
    bad = (dv > TH['spike_rad_s']) & ~excused[w:]
    add(1, 'unexplained_velocity_spikes', not bad.any(), int(bad.sum()), 0,
        f'max change {dv.max():.1f} rad/s per {TH["spike_window_s"] * 1000:.0f} ms')

    a = np.linalg.norm(z['assist'][:, :3], axis=1) / W
    cap = lock['motion'].get('assist_cap', 0.15)
    post = t >= t_ko if t_ko >= 0 else np.zeros(len(t), bool)
    add(1, 'root_assist_within_cap', a.max() <= cap * TH['assist_slack'], round(float(a.max()), 3), cap,
        f'mean {a[~post].mean():.3f} of body weight before the KO')
    add(1, 'root_assist_zero_after_ko', not a[post].any(), round(float(a[post].max()) if post.any() else 0, 4), 0)

    # contacts between body and ropes / canvas
    b_rope = (is_rope[g1] & is_body[g2]) | (is_rope[g2] & is_body[g1])
    b_can = (is_canvas[g1] & is_body[g2]) | (is_canvas[g2] & is_body[g1])
    torso = _mask(gn, lambda n: n in ('g_chest', 'g_spine', 'g_pelvis', 'g_upper_arm_L',
                                      'g_upper_arm_R', 'g_forearm_L', 'g_forearm_R', 'g_neck'))
    t_rope = b_rope & (torso[g1] | torso[g2]) & (cf > 1.0)
    chest_z = z['xpos'][:, bn.index('chest'), 2]
    # 'propped' means held up by the ropes: chest still well off the canvas while in contact
    prop_h = (lock.get('outcome') or {}).get('propped_min_chest_z', 0.55)
    rope_steps = np.unique(cs[t_rope])
    rope_time = len(rope_steps) * dt
    propped_time = int((chest_z[rope_steps] > prop_h).sum()) * dt if len(rope_steps) else 0.0
    pelvis_z = z['xpos'][:, bn.index('pelvis'), 2]
    oc = lock.get('outcome') or {}
    if oc.get('name') == 'propped_then_down':
        ok = propped_time >= oc['rope_contact_min_s'] and pelvis_z[-1] <= oc['final_pelvis_max_z']
        add(1, 'outcome_propped_then_down', ok,
            {'rope_contact_s': round(propped_time, 2), 'final_pelvis_z': round(float(pelvis_z[-1]), 3)},
            {'rope_contact_s': oc['rope_contact_min_s'], 'final_pelvis_z': oc['final_pelvis_max_z']})

    if oc.get('name') == 'stiff_back_escalate':
        import json as _json
        ev = _json.loads(str(z['events']))
        hgi = gn.index('g_head')
        hm = b_can & ((g1 == hgi) | (g2 == hgi)) & (cf > 0.05 * W)
        hsteps = np.unique(cs[hm])
        # a bounce = the head leaving the canvas and striking it again hard (> half body weight);
        # resting back down after the core curls is not a bounce
        hload = np.zeros(len(t))
        np.add.at(hload, cs[hm], cf[hm])
        episodes = 0
        if len(hsteps):
            cuts = np.nonzero(np.diff(hsteps) > int(0.04 / dt))[0]
            for seg in np.split(hsteps, cuts + 1):
                episodes += int(hload[seg].max() > 0.5 * W)
        head_p = z['xpos'][:, bn.index('head')]
        ik0 = int(t_ko / dt)
        ih = int(ev['head_impact'] / dt) if 'head_impact' in ev else None
        jn = [str(n) for n in z['joint_names']]
        knee = np.degrees(q[:, [jn.index('shin_L_flex'), jn.index('shin_R_flex')]])
        tone_m = z['tone'].mean(axis=1)
        val = {'head_impact_t_after_ko': round(ev['head_impact'] - t_ko, 2) if ih else None,
               'backward_travel_m': round(float(head_p[-1, 1] - head_p[ik0, 1]), 2),
               'max_knee_flex_before_impact_deg': round(float(knee[ik0 + int(0.3 / dt):ih].max()), 1) if ih else None,
               'head_bounces': max(0, episodes - 1),
               'tone_before_impact': round(float(tone_m[ih - 25:ih].mean()), 2) if ih else None,
               'tone_after_impact': round(float(tone_m[ih + 60:ih + 200].mean()), 2) if ih else None,
               'final_chest_z': round(float(z['xpos'][-1, bn.index('chest'), 2]), 2)}
        lim = {'backward_travel_m': oc.get('min_backward_m', 0.8),
               'max_knee_flex_before_impact_deg': oc.get('max_knee_flex_deg', 30),
               'head_bounces': 1, 'final_chest_z': 0.35}
        ok = (ih is not None and val['backward_travel_m'] >= lim['backward_travel_m']
              and val['max_knee_flex_before_impact_deg'] <= lim['max_knee_flex_before_impact_deg']
              and val['head_bounces'] <= 1 and val['tone_after_impact'] > val['tone_before_impact']
              and val['final_chest_z'] <= lim['final_chest_z'])
        add(1, 'outcome_stiff_back_escalate', ok, val, lim)
        if ih:
            # legs were bent in the stance at the KO instant; 'stiff' is judged once the
            # extensor tone has had 0.3 s to straighten them
            rep['metrics']['head_rebound_height_m'] = round(float(
                head_p[ih + 5:ih + 150, 2].max() - head_p[ih:ih + 15, 2].min()), 3)
            # peak head speed over the 60 ms before the event (the event fires on force, a few
            # ms after first touch, by which time the head has already slowed)
            hv = np.linalg.norm(np.diff(head_p[max(0, ih - 30):ih + 1], axis=0), axis=1) / dt
            rep['metrics']['head_impact_speed_m_s'] = round(float(hv.max()), 2)

    # 2. motion quality ---------------------------------------------------------------------
    pen_rope = -cd[b_rope].min() * 1000 if b_rope.any() else 0.0
    pen_can = -cd[b_can].min() * 1000 if b_can.any() else 0.0
    b_self = is_body[g1] & is_body[g2]
    pen_self = -cd[b_self].min() * 1000 if b_self.any() else 0.0
    add(2, 'sim_penetration_rope_mm', pen_rope <= TH['sim_penetration_mm'], round(float(pen_rope), 1),
        TH['sim_penetration_mm'])
    add(2, 'sim_penetration_canvas_mm', pen_can <= TH['sim_penetration_mm'], round(float(pen_can), 1),
        TH['sim_penetration_mm'])
    add(2, 'sim_penetration_self_mm', pen_self <= TH['self_penetration_mm'], round(float(pen_self), 1),
        TH['self_penetration_mm'])

    slide, slide_note = 0.0, ''
    for f in ('foot_L', 'foot_R'):         # integrate sole slip speed while the foot is loaded
        g = gn.index('g_' + f)
        m = b_can & ((g1 == g) | (g2 == g))
        load = np.zeros(len(t))
        np.add.at(load, cs[m], cf[m])
        sp = np.zeros(len(t))
        cnt = np.zeros(len(t))
        np.add.at(sp, cs[m], slip[m])
        np.add.at(cnt, cs[m], 1)
        sp = sp / np.maximum(cnt, 1)
        planted = (load > TH['planted_load_frac'] * W) & ~post
        sl = float((sp * planted).sum() * dt)
        if sl > slide:
            slide, slide_note = sl, f'{f}, planted {planted.sum() * dt:.2f} s'
    add(2, 'foot_slide_while_planted_m', slide <= TH['foot_slide_m'], round(slide, 3), TH['foot_slide_m'], slide_note)

    # jitter: joint-angle content above 10 Hz, outside +-0.2 s of contacts/strike
    k = max(1, int(0.05 / dt))
    sm = np.apply_along_axis(lambda x: np.convolve(x, np.ones(2 * k + 1) / (2 * k + 1), 'same'), 0, q)
    hf = np.degrees(q - sm)[2 * k:-2 * k]
    calm = ~excused[2 * k:-2 * k]
    jit = float(np.sqrt((hf[calm] ** 2).mean(axis=0)).max()) if calm.any() else 0.0
    add(2, 'jitter_deg_rms', jit <= TH['jitter_deg_rms'], round(jit, 3), TH['jitter_deg_rms'])

    for n in ('render_mesh_penetration', 'hair_cloth_stability', 'framing', 'occlusion'):
        rep['checks'].append({'gate': 3, 'name': n, 'pass': None, 'note': 'todo: not implemented'})

    # metrics for humans and for footage comparison later
    head = z['xpos'][:, bn.index('head')]
    hg = gn.index('g_head')
    hc = cs[b_can & ((g1 == hg) | (g2 == hg))]
    first_can = cs[b_can & ~(_mask(gn, lambda n: 'foot' in n)[g1] | _mask(gn, lambda n: 'foot' in n)[g2])]
    v = z['qvel'][:, :3]
    ik = int(t_ko / dt) if t_ko >= 0 else 0
    speed = np.linalg.norm(z['qvel'][:, :6], axis=1)
    rest = np.nonzero(speed > 0.15)[0]
    rep['metrics'].update({
        't_ko': round(t_ko, 3),
        'pelvis_velocity_at_ko': [round(float(x), 2) for x in v[ik]],
        'fall_azimuth_deg_from_forward': round(float(np.degrees(np.arctan2(
            -(head[-1, 0] - head[ik, 0]), -(head[-1, 1] - head[ik, 1])))), 1),
        'time_to_first_non_foot_canvas_contact': round(float((first_can.min() - ik) * dt), 2) if len(first_can) else None,
        'time_to_head_canvas_contact': round(float((hc.min() - ik) * dt), 2) if len(hc) else None,
        'time_to_rest': round(float((rest.max() - ik) * dt), 2) if len(rest) else 0.0,
        'torso_on_ropes_s': round(rope_time, 2),
        'propped_on_ropes_s': round(propped_time, 2),
        'max_rope_deflection_m': round(float(np.abs(z['rope'][:, :, 1] - z['rope'][0, :, 1]).max()), 3) if z['rope'].shape[1] else 0.0,
        'final_pelvis': [round(float(x), 2) for x in z['xpos'][-1, bn.index('pelvis')]],
        'final_head': [round(float(x), 2) for x in head[-1]],
        'validated_against_footage': False,
    })
    rep['pass'] = all(c['pass'] for c in rep['checks'] if c['pass'] is not None)
    return rep


def show(rep):
    for c in rep['checks']:
        s = 'todo' if c['pass'] is None else 'PASS' if c['pass'] else 'FAIL'
        print(f"  [{s}] gate {c['gate']} {c['name']}: {c.get('value', '')} (limit {c.get('limit', '-')}) {c.get('note', '')}")
    for k, v in rep['metrics'].items():
        print(f'  {k}: {v}')
