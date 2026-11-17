"""'<pose>_auto' picks the cheek the head is already turning toward, once per phase."""
import math
from types import SimpleNamespace

import numpy as np

from ko.sim.control import Controller
from ko.sim.reference import POSES


def _ctl(twist_deg, rate_deg_s):
    return SimpleNamespace(idx={'neck_twist': 0}, off=np.array([0.0]), _auto={}, event_data={},
                           _q_now=np.array([math.radians(twist_deg)]),
                           _qd_now=np.array([math.radians(rate_deg_s)]))


def test_follows_turn():
    c = _ctl(-30, 0)
    assert Controller.auto_pose(c, 6, 'head_rest_cheek_auto') == 'head_rest_cheek_R'
    c = _ctl(20, 0)
    assert Controller.auto_pose(c, 6, 'head_rest_cheek_auto') == 'head_rest_cheek_L'


def test_rate_leads():
    c = _ctl(10, -250)                 # still left of centre but swinging hard right
    assert Controller.auto_pose(c, 6, 'head_rest_cheek_auto') == 'head_rest_cheek_R'


def test_locked_once_and_recorded():
    c = _ctl(-30, 0)
    Controller.auto_pose(c, 6, 'head_rest_cheek_auto')
    c._q_now[0] = math.radians(40)
    assert Controller.auto_pose(c, 6, 'head_rest_cheek_auto') == 'head_rest_cheek_R'
    assert c.event_data['auto_side_phase6']['side'] == 'R'


def test_plain_name_untouched_and_both_sides_exist():
    assert Controller.auto_pose(_ctl(0, 0), 0, 'neck_neutral') == 'neck_neutral'
    assert 'head_rest_cheek_R' in POSES and 'head_rest_cheek_L' in POSES
