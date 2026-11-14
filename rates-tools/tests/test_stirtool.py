"""Tests for the Fed STIR tool's maths.  Run from rates-tools:  python -m unittest discover -s tests"""
import datetime as dt
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stirtool import calendar_us as cal          # noqa: E402
from stirtool import model as mdl                # noqa: E402
from stirtool import scenario as scn             # noqa: E402

D = dt.date
UTC = dt.timezone.utc


def flat_fixings(rate, start=D(2026, 7, 1), end=D(2026, 11, 12)):
    out, d = {}, start
    while d <= end:
        if cal.is_business_day(d):
            out[d] = rate
        d += cal.ONE_DAY
    return out


MEETINGS = [{'date': D(2026, 12, 9), 'assumed': False}, {'date': D(2027, 1, 27), 'assumed': False},
            {'date': D(2027, 3, 17), 'assumed': False}, {'date': D(2027, 4, 28), 'assumed': False},
            {'date': D(2027, 6, 9), 'assumed': False}, {'date': D(2027, 7, 28), 'assumed': False},
            {'date': D(2027, 9, 15), 'assumed': False}]
SYMS = ['ZQX26', 'ZQZ26', 'ZQF27', 'ZQG27', 'ZQH27', 'ZQJ27', 'SR3Z26', 'SR3H27', 'SR3M27']
TODAY = D(2026, 11, 14)


def make_model(effr=3.88, sofr=3.90):
    cons = [mdl.parse_symbol(s) for s in SYMS]
    return mdl.Model(cons, MEETINGS, flat_fixings(effr), flat_fixings(sofr), TODAY)


class Calendar(unittest.TestCase):
    def test_imm_dates(self):
        self.assertEqual(cal.third_wednesday(2026, 12), D(2026, 12, 16))
        self.assertEqual(cal.third_wednesday(2027, 3), D(2027, 3, 17))

    def test_trade_date_and_session(self):
        fri_after_close = dt.datetime(2026, 11, 13, 23, 30, tzinfo=UTC)      # Fri 17:30 CT
        self.assertEqual(cal.trade_date(fri_after_close), D(2026, 11, 16))
        self.assertEqual(cal.trade_date(dt.datetime(2026, 11, 13, 21, 0, tzinfo=UTC)), D(2026, 11, 13))
        start, end = cal.session_bounds(D(2026, 11, 16))
        self.assertEqual(start, dt.datetime(2026, 11, 15, 23, 0, tzinfo=UTC))   # Sun 17:00 CT
        self.assertEqual(end, dt.datetime(2026, 11, 16, 22, 0, tzinfo=UTC))
        self.assertFalse(cal.globex_open(dt.datetime(2026, 11, 14, 14, 0, tzinfo=UTC)))
        self.assertTrue(cal.globex_open(dt.datetime(2026, 11, 16, 14, 0, tzinfo=UTC)))

    def test_dst(self):
        self.assertEqual(cal.to_ct(dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC)).hour, 14)   # CDT
        self.assertEqual(cal.to_ct(dt.datetime(2026, 12, 1, 20, 0, tzinfo=UTC)).hour, 14)  # CST


class Pricing(unittest.TestCase):
    def test_contract_periods_and_ticks(self):
        z = mdl.parse_symbol('SR3Z26')
        self.assertEqual((z.start, z.end), (D(2026, 12, 16), D(2027, 3, 17)))
        self.assertEqual(mdl.tick_size(mdl.parse_symbol('ZQX26'), TODAY), 0.0025)   # spot month
        self.assertEqual(mdl.tick_size(mdl.parse_symbol('ZQZ26'), TODAY), 0.005)
        self.assertEqual(mdl.tick_size(mdl.parse_symbol('SR3U26'), TODAY), 0.0025)  # nearest SR3
        self.assertEqual(mdl.tick_size(z, TODAY), 0.005)

    def test_flat_path(self):
        m = make_model()
        p = dict(zip(SYMS, m.prices(np.zeros(m.K), 2.0)))
        self.assertAlmostEqual(p['ZQZ26'], 100 - 3.88, places=9)
        # SR3 compounding: 3.90% daily-compounded over ~91 days is ~1.9bp above 3.90
        r = 100 - p['SR3H27']
        self.assertGreater(r, 3.90)
        self.assertLess(r, 3.90 + 0.03)

    def test_zq_meeting_split(self):
        m = make_model()
        x = np.zeros(m.K)
        x[0] = 25.0                                     # +25 at Dec 9, effective Dec 10
        p = dict(zip(SYMS, m.prices(x, 2.0)))
        self.assertAlmostEqual(100 - p['ZQZ26'], 3.88 + 0.25 * 22 / 31, places=9)
        self.assertAlmostEqual(100 - p['ZQF27'], 3.88 + 0.25, places=9)

    def test_jacobian_matches_finite_difference(self):
        m = make_model()
        x = np.linspace(20, 2, m.K)
        J = m.jacobian(x, 2.0)
        h = 1e-4
        for k in (0, 2, m.K - 1):
            e = np.zeros(m.K)
            e[k] = h
            fd = (m.rates(x + e, 2.0) - m.rates(x - e, 2.0)) / (2 * h)
            np.testing.assert_allclose(J[:, k], fd, rtol=1e-6, atol=1e-9)

    def test_fit_recovers_path(self):
        m = make_model()
        true_x, true_sp = np.array([26.0, 18.0, 16.0, 8.0, 9.0, 7.0][:m.K]), 2.5
        market = dict(zip(SYMS, m.prices(true_x, true_sp)))
        fit = m.fit(market)
        self.assertLess(max(abs(v) for v in fit.resid.values()), 0.3)
        np.testing.assert_allclose(np.cumsum(fit.x)[:3], np.cumsum(true_x)[:3], atol=0.5)


class Scenarios(unittest.TestCase):
    x = np.array([26.0, 18.0, 16.0, 8.0])

    def test_whole(self):
        c = np.cumsum(scn.apply_edits(self.x, {0: 50}, 'whole'))
        np.testing.assert_allclose(c, [50, 68, 84, 92])

    def test_pull_forward_keeps_end_rate(self):
        c = np.cumsum(scn.apply_edits(self.x, {0: 50}, 'pull'))
        np.testing.assert_allclose(c, [50, 50, 60, 68])
        c = np.cumsum(scn.apply_edits(self.x, {0: 0}, 'pull'))      # dovish: Dec hold, rest unchanged
        np.testing.assert_allclose(c, [0, 44, 60, 68])

    def test_pull_forward_in_a_cutting_path(self):
        cuts = np.array([-10.0, -20.0, -15.0])                       # cumulative -10, -30, -45
        c = np.cumsum(scn.apply_edits(cuts, {0: 0}, 'pull'))         # Dec hold: cuts pushed back
        np.testing.assert_allclose(c, [0, -30, -45])
        c = np.cumsum(scn.apply_edits(cuts, {0: -35}, 'pull'))       # deeper Dec cut pulled forward
        np.testing.assert_allclose(c, [-35, -35, -45])

    def test_fade(self):
        c = np.cumsum(scn.apply_edits(self.x, {0: 50}, 'fade', 0.5))
        np.testing.assert_allclose(c, [50, 44 + 12, 60 + 6, 68 + 3])

    def test_reprice_direction(self):
        m = make_model()
        fit = m.fit(dict(zip(SYMS, m.prices(np.array([26, 18, 16, 8, 9, 7.0])[:m.K], 2.5))))
        hawk = scn.reprice(m, fit, {}, scn.apply_edits(fit.x, {0: 50}, 'whole'), TODAY)
        self.assertLess(hawk['ZQF27']['ticks'], -40)                   # ~+24bp -> ~-47 ticks
        self.assertAlmostEqual(hawk['ZQX26']['ticks'], 0.0, places=6)  # November has no meeting
        dove = scn.reprice(m, fit, {}, scn.apply_edits(fit.x, {0: -25}, 'whole'), TODAY)
        self.assertGreater(dove['SR3H27']['ticks'], 90)


if __name__ == '__main__':
    unittest.main()
