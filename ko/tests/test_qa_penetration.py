"""Canvas penetration gate: bony segments keep the 5 mm limit, fleshy segments get their own limit."""
import numpy as np

from ko.qa.gates import TH, canvas_penetration

GN = ['canvas', 'g_pelvis', 'g_head', 'g_shin_L', 'rope0_g0']


def _c(pairs):
    g1 = np.array([a for a, b, d in pairs]); g2 = np.array([b for a, b, d in pairs])
    return g1, g2, np.array([d for a, b, d in pairs])


def test_split_by_segment():
    g1, g2, cd = _c([(0, 1, -0.009), (2, 0, -0.003), (0, 3, -0.001), (4, 2, -0.02)])
    bone, flesh = canvas_penetration(GN, g1, g2, cd)
    assert abs(bone - 3.0) < 1e-6 and abs(flesh - 9.0) < 1e-6     # rope contact ignored


def test_deep_head_still_fails():
    g1, g2, cd = _c([(0, 2, -0.008), (0, 1, -0.002)])
    bone, flesh = canvas_penetration(GN, g1, g2, cd)
    assert bone > TH['sim_penetration_mm'] and flesh <= TH['flesh_penetration_mm']


def test_no_contact():
    g1, g2, cd = _c([(1, 2, -0.004)])
    assert canvas_penetration(GN, g1, g2, cd) == (0.0, 0.0)
