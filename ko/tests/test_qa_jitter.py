"""The jitter gate measures motion above 12 Hz and leaves authored tremor (5-9.5 Hz) alone."""
import numpy as np

from ko.qa.gates import band_rms, jitter_rms


def _sig(hz, amp_deg, T=4.0, dt=0.002):
    t = np.arange(int(T / dt)) * dt
    return np.radians(amp_deg) * np.sin(2 * np.pi * hz * t)[:, None], dt


def test_tremor_is_not_jitter():
    q, dt = _sig(8.0, 1.5)                       # 1.5 deg amplitude tremor at 8 Hz
    ex = np.zeros(len(q), bool)
    assert jitter_rms(q, dt, ex) < 0.05
    assert abs(band_rms(q, dt, ex, 5.0, 9.5) - 1.5 / np.sqrt(2)) < 0.05


def test_high_frequency_rattle_is_jitter():
    q, dt = _sig(25.0, 1.0)                      # 1 deg rattle at 25 Hz
    ex = np.zeros(len(q), bool)
    assert abs(jitter_rms(q, dt, ex) - 1.0 / np.sqrt(2)) < 0.05


def test_old_moving_average_counted_tremor():
    q, dt = _sig(8.0, 1.5)
    k = int(0.05 / dt)
    sm = np.convolve(q[:, 0], np.ones(2 * k + 1) / (2 * k + 1), 'same')
    old = np.degrees(q[:, 0] - sm)[2 * k:-2 * k]
    assert np.sqrt((old ** 2).mean()) > 0.7      # the old gate saw most of an 8 Hz tremor as jitter
