"""Needs the VRoid test character built once:  python -m ko.cli build takes/stiff_back_001.yaml --to body"""
import hashlib
import json
import os

import mujoco
import numpy as np
import pytest

from ko import manifest
from ko.body import gen_body
from ko.sim import run, scene

TAKE = os.path.join(manifest.ROOT, 'takes', 'stiff_back_001.yaml')
lock = manifest.resolve(TAKE)
BODY = manifest.stage_dir(lock, 'body')
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(BODY, 'body.json')),
                                reason='character not built')


def fk(joint, deg, body):
    spec = json.load(open(os.path.join(BODY, 'body.json')))
    m = mujoco.MjModel.from_xml_string(scene.build(gen_body.to_mjcf(spec), {'rope_y': None}))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    p0 = d.xipos[m.body(body).id].copy()
    d.qpos[m.joint(joint).qposadr[0]] = np.radians(deg)
    mujoco.mj_forward(m, d)
    return d.xipos[m.body(body).id] - p0


# sign conventions verified numerically on the actual rig, never reasoned by hand
@pytest.mark.parametrize('joint,body,axis,sign', [
    ('thigh_L_flex', 'foot_L', 1, -1), ('thigh_R_flex', 'foot_R', 1, -1),   # forward is -y
    ('shin_L_flex', 'foot_L', 1, +1), ('spine_flex', 'head', 1, -1),
    ('upper_arm_L_abd', 'hand_L', 2, +1), ('upper_arm_R_abd', 'hand_R', 2, +1),
    ('upper_arm_L_flex', 'hand_L', 1, -1), ('upper_arm_R_flex', 'hand_R', 1, -1),
    ('forearm_L_flex', 'hand_L', 1, -1), ('forearm_R_flex', 'hand_R', 1, -1),
    ('thigh_L_abd', 'foot_L', 0, +1), ('thigh_R_abd', 'foot_R', 0, -1),
])
def test_positive_angle_is_the_anatomical_motion(joint, body, axis, sign):
    assert np.sign(fk(joint, 20, body)[axis]) == sign


def test_no_interpenetration_in_neutral_pose():
    spec = json.load(open(os.path.join(BODY, 'body.json')))
    m = mujoco.MjModel.from_xml_string(scene.build(gen_body.to_mjcf(spec), {'rope_y': None}))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    assert all(c.dist > -0.003 for c in d.contact[:d.ncon])


def test_same_manifest_same_simulation_bitwise():
    a = run.run(lock, BODY, None)['qpos']
    b = run.run(lock, BODY, None)['qpos']
    assert hashlib.sha256(a.tobytes()).hexdigest() == hashlib.sha256(b.tobytes()).hexdigest()


def test_root_assist_is_capped_and_zero_after_ko():
    o = run.run(lock, BODY, None)
    W = float(o['mass']) * 9.81
    a = np.linalg.norm(o['assist'][:, :3], axis=1) / W
    assert a.max() <= lock['motion']['assist_cap'] * 1.02
    assert not a[o['t'] >= float(o['t_ko'])].any()


def test_escalation_is_clocked_from_the_head_hitting_the_canvas():
    import json as _json
    o = run.run(lock, BODY, None)
    ev = _json.loads(str(o['events']))
    assert 'head_impact' in ev and ev['head_impact'] > float(o['t_ko'])
    i = int(ev['head_impact'] / float(o['dt']))
    tone = o['tone'].mean(axis=1)
    assert tone[i + 100:i + 200].mean() > tone[i - 25:i].mean() + 0.15
