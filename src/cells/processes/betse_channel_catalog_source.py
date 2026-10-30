# ruff: noqa: E721, F841
"""Literal native catalog class adapters; STATIC PREPARATION, NOT QUALIFIED.

Numerical method bodies adapted from BETSE1.5.0, revision5269a714aa2593ed2a6708c4516289977d8ae1a2.
Original equations by Alexis Pietak and Cecil Curry. Source metadata and exact
AST adaptation audit: validation/betse/betse_normal_catalog_join_inventory.json.
Only docstrings/logging/abstract stubs and class names/inheritance are removed.
No regularization, gate clipping, thermal scaling or implicit calcium inputs.
"""

from types import SimpleNamespace

import numpy as np


class _Clock:
    def update_mh(self, p, time_unit=1000.0):
        dt = p.dt * self.time_unit
        self.m = (self._mTau * self.m + dt * self._mInf) / (self._mTau + dt)
        self.h = (self._hTau * self.h + dt * self._hInf) / (self._hTau + dt)

    def update_ml(self, p, time_unit=1000.0):
        dt = p.dt * self.time_unit
        self.m = (self.m + dt * self.Phi * self._mInf / self._mTau) / (
            1 + dt * self.Phi / self._mTau
        )


class _NaBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = None
            if type(vm) == float or type(vm) == np.float64:
                self.data_length = 1
            else:
                self.data_length = len(vm)
        else:
            self.targets = targets
            self.data_length = len(self.targets)
            self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        self.v_corr = 0.0
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._init_state(V)
        self.ions = ["Na"]
        self.rel_perm = [1.0]

    def run(self, vm, p):
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._calculate_state(V)
        self._implement_state(V, p)

    def _implement_state(self, V, p):
        self.update_mh(p, time_unit=self.time_unit)
        P = self.m**self._mpower * self.h**self._hpower
        if self.targets is None:
            self.P = P
        else:
            self.P = np.zeros(self.mdl)
            self.P[self.targets] = P


class _Nav1p2(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        mAlpha = 0.182 * (V - 10.0 - -35.0) / (1 - np.exp(-(V - 10.0 - -35.0) / 9))
        mBeta = 0.124 * (-(V - 10.0) - 35.0) / (1 - np.exp(-(-(V - 10.0) - 35.0) / 9))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = 1.0 / (1 + np.exp((V - -65.0 - 10.0) / 6.2))
        self._mpower = 3
        self._hpower = 1

    def _calculate_state(self, V):
        mAlpha = 0.182 * (V - 10.0 - -35.0) / (1 - np.exp(-(V - 10.0 - -35.0) / 9))
        mBeta = 0.124 * (-(V - 10.0) - 35.0) / (1 - np.exp(-(-(V - 10.0) - 35.0) / 9))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = 1.0 / (1 + np.exp((V - -65.0 - 10.0) / 6.2))
        self._hTau = 1 / (
            0.024 * (V - 10.0 - -50.0) / (1 - np.exp(-(V - 10.0 - -50.0) / 5))
            + 0.0091 * (-(V - 10.0) - 75.000123) / (1 - np.exp(-(-(V - 10) - 75.000123) / 5))
        )


class _Nav1p3(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        self._mpower = 3
        self._hpower = 1
        mAlpha = 0.182 * (V - -26) / (1 - np.exp(-(V - -26) / 9))
        mBeta = 0.124 * (-V - 26) / (1 - np.exp(-(-V - 26) / 9))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = 1 / (1 + np.exp((V - -65.0) / 8.1))

    def _calculate_state(self, V):
        mAlpha = 0.182 * (V - -26) / (1 - np.exp(-(V - -26) / 9))
        mBeta = 0.124 * (-V - 26) / (1 - np.exp(-(-V - 26) / 9))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = 1 / (1 + np.exp((V - -65.0) / 8.1))
        self._hTau = 0.4 + 0.265 * np.exp(-V / 9.47)


class _NavRat2(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        self._mpower = 3
        self._hpower = 1
        mAlpha = 0.091 * (V + 38) / (1 - np.exp((-V - 38) / 5))
        mBeta = -0.062 * (V + 38) / (1 - np.exp((V + 38) / 5))
        self.m = mAlpha / (mAlpha + mBeta)
        hAlpha = 0.016 * np.exp((-55 - V) / 15)
        hBeta = 2.07 / (np.exp((17 - V) / 21) + 1)
        self.h = hAlpha / (hAlpha + hBeta)

    def _calculate_state(self, V):
        mAlpha = 0.091 * (V + 38) / (1 - np.exp((-V - 38) / 5))
        mBeta = -0.062 * (V + 38) / (1 - np.exp((V + 38) / 5))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        hAlpha = 0.016 * np.exp((-55 - V) / 15)
        hBeta = 2.07 / (np.exp((17 - V) / 21) + 1)
        self._hInf = hAlpha / (hAlpha + hBeta)
        self._hTau = 1 / (hAlpha + hBeta)


class _NavRat1(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        self._mpower = 3
        self._hpower = 1
        mAlpha = 0.182 * (V - -35) / (1 - np.exp(-(V - -35) / 9))
        mBeta = 0.124 * (-V - 35) / (1 - np.exp(-(-V - 35) / 9))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = 1.0 / (1 + np.exp((V - -65) / 6.2))

    def _calculate_state(self, V):
        mAlpha = 0.182 * (V - -35) / (1 - np.exp(-(V - -35) / 9))
        mBeta = 0.124 * (-V - 35) / (1 - np.exp(-(-V - 35) / 9))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = 1.0 / (1 + np.exp((V - -65) / 6.2))
        self._hTau = 1 / (
            0.024 * (V - -50) / (1 - np.exp(-(V - -50) / 5))
            + 0.0091 * (-V - 75.000123) / (1 - np.exp(-(-V - 75.000123) / 5))
        )


class _NavRat3(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        self._mpower = 3
        self._hpower = 1
        mAlpha = 0.182 * (V - -35) / (1 - np.exp(-(V - -35) / 9))
        mBeta = 0.124 * (-V - 35) / (1 - np.exp(-(-V - 35) / 9))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = 1.0 / (1 + np.exp((V - -65) / 6.2))

    def _calculate_state(self, V):
        mAlpha = 0.182 * (V - -35) / (1 - np.exp(-(V - -35) / 9))
        mBeta = 0.124 * (-V - 35) / (1 - np.exp(-(-V - 35) / 9))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = 1.0 / (1 + np.exp((V - -65) / 6.2))
        self._hTau = 1 / (
            0.024 * (V - -50) / (1 - np.exp(-(V - -50) / 5))
            + 0.0091 * (-V - 75.000123) / (1 - np.exp(-(-V - 75.000123) / 5))
        )


class _NaLeak(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.vrev = 50
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0

    def _calculate_state(self, V):
        self._mInf = 1
        self._mTau = 1
        self._hInf = 1
        self._hTau = 1


class _Nav1p6(_NaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        self._mpower = 1.0
        self._hpower = 0.0
        self.m = 1.0 / (1 + np.exp(-0.03937 * 4.2 * (V - -17.0)))
        self.h = 1.0

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp(-0.03937 * 4.2 * (V - -17.0)))
        self._mTau = 1
        self._hInf = 1.0
        self._hTau = 1.0


class _KBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = None
            if type(vm) == float or type(vm) == np.float64:
                self.data_length = 1
            else:
                self.data_length = len(vm)
        else:
            self.targets = targets
            self.data_length = len(self.targets)
            self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        self.v_corr = 0.0
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._init_state(V)
        self.ions = ["K"]
        self.rel_perm = [1.0]

    def run(self, vm, p):
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._calculate_state(V)
        self._implement_state(V, p)

    def _implement_state(self, V, p):
        self.update_mh(p, time_unit=self.time_unit)
        P = self.m**self._mpower * self.h**self._hpower
        if self.targets is None:
            self.P = P
        else:
            self.P = np.zeros(self.mdl)
            self.P[self.targets] = P


class _Kv1p1(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1.0 / (1 + np.exp((V - -30.5) / -11.3943))
        self.h = 1.0 / (1 + np.exp((V - -30.0) / 27.3943))
        self._mpower = 1
        self._hpower = 2

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp((V - -30.5) / -11.3943))
        self._mTau = 30.0 / (1 + np.exp((V - -76.56) / 26.1479))
        self._hInf = 1.0 / (1 + np.exp((V - -30.0) / 27.3943))
        self._hTau = 15000.0 / (1 + np.exp((V - -160.56) / -100.0))


class _Kv1p2(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1.0 / (1 + np.exp(-(V + 21.0) / 11.3943))
        self.h = 1.0 / (1 + np.exp((V + 22.0) / 11.3943))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp(-(V + 21.0) / 11.3943))
        self._mTau = 150.0 / (1 + np.exp((V + 67.56) / 34.1479))
        self._hInf = 1.0 / (1 + np.exp((V + 22.0) / 11.3943))
        self._hTau = 15000.0 / (1 + np.exp(-(V + 46.56) / 44.1479))


class _Kv1p3(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1.0 / (1 + np.exp((V - -14.1) / -10.3))
        self.h = 1.0 / (1 + np.exp((V - -33.0) / 3.7))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp((V - -14.1) / -10.3))
        self._mTau = -0.284 * V + 19.16
        self._hInf = 1.0 / (1 + np.exp((V - -33.0) / 3.7))
        self._hTau = -13.76 * V + 1162.4


class _Kv1p4(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1.0 / (1 + np.exp((V + 21.7) / -16.9))
        self.h = 1.0 / (1 + np.exp((V + 73.6) / 12.8))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp((V + 21.7) / -16.9))
        self._mTau = 3.0
        self._hInf = 1.0 / (1 + np.exp((V + 73.6) / 12.8))
        self._hTau = 119.0


class _Kv1p5(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1.0 / (1 + np.exp((V - -6.0) / -6.4))
        self.h = 1.0 / (1 + np.exp((V - -25.3) / 3.5))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp((V - -6.0) / -6.4))
        self._mTau = -0.1163 * V + 8.33
        self._hInf = 1.0 / (1 + np.exp((V - -25.3) / 3.5))
        self._hTau = -15.5 * V + 1620.0


class _Kv1p6(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1 / (1 + np.exp((V - -20.8) / -8.1))
        self.h = 1 / (1 + np.exp((V - -22.0) / 11.39))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -20.8) / -8.1))
        self._mTau = 30.0 / (1 + np.exp((V - -46.56) / 44.14))
        self._hInf = 1 / (1 + np.exp((V - -22.0) / 11.39))
        self._hTau = 5000.0 / (1 + np.exp((V - -46.56) / -44.14))


class _Kv2p1(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1 / (1 + np.exp((V - -9.2) / -6.6))
        self.h = 1 / (1 + np.exp((V - -19.0) / 5.0))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -9.2) / -6.6))
        self._mTau = 100.0 / (1 + np.exp((V - -46.56) / 44.14))
        self._hInf = 1 / (1 + np.exp((V - -19.0) / 5.0))
        self._hTau = 10000.0 / (1 + np.exp((V - -46.56) / -44.14))


class _Kv2p2(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1 / (1 + np.exp((V - 5.0) / -12.0))
        self.h = 1 / (1 + np.exp((V - -16.3) / 4.8))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - 5.0) / -12.0))
        self._mTau = 130.0 / (1 + np.exp((V - -46.56) / -44.14))
        self._hInf = 1 / (1 + np.exp((V - -16.3) / 4.8))
        self._hTau = 10000.0 / (1 + np.exp((V - -46.56) / -44.14))


class _Kv3p1(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1 / (1 + np.exp((V - 18.7) / -9.7))
        self.h = 1
        self._mpower = 1
        self._hpower = 0

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - 18.7) / -9.7))
        self._mTau = 20.0 / (1 + np.exp((V - -46.56) / -44.14))
        self._hInf = 1
        self._hTau = 1


class _Kv3p2(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1 / (1 + np.exp((V - -0.373267) / -8.568187))
        self.h = 1
        self._mpower = 2
        self._hpower = 0

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -0.373267) / -8.568187))
        self._mTau = 3.241643 + 19.106496 / (1 + np.exp((V - 19.220623) / 4.451533))
        self._hInf = 1
        self._hTau = 1


class _Kv3p3(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 82.0
        self.m = 1 / (1 + np.exp((V - 35) / -7.3))
        self.h = 0.25 + 0.75 / (1 + np.exp((V - -28.293856) / 29.385636))
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - 35) / -7.3))
        self._mTau = 0.676808 + 27.913114 / (1 + np.exp((V - 22.414149) / 9.704638))
        self._hInf = 0.25 + 0.75 / (1 + np.exp((V - -28.293856) / 29.385636))
        self._hTau = 199.786728 + 2776.119438 * np.exp(-V / 7.309565)


class _Kv3p4(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65.0
        self.m = 1 / (1 + np.exp((V - -3.4) / -8.4))
        self.h = 1 / (1 + np.exp((V - -53.32) / 7.4))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -3.4) / -8.4))
        self._mTau = 10.0 / (1 + np.exp((V - 4.44) / 38.14))
        self._hInf = 1 / (1 + np.exp((V - -53.32) / 7.4))
        self._hTau = 20000.0 / (1 + np.exp((V - -46.56) / -44.14))


class _K_Fast(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.m = 1 / (1 + np.exp(-(V + 47) / 29))
        self.h = 1 / (1 + np.exp(-(V + 56) / -10))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp(-(V + 47) / 29))
        self._mTau = 0.34 + 0.92 * np.exp(-(((V + 71) / 59) ** 2))
        self._hInf = 1 / (1 + np.exp(-(V + 56) / -10))
        self._hTau = 8 + 49 * np.exp(-(((V + 73) / 23) ** 2))


class _KLeak(_KBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.vrev = -65
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0

    def _calculate_state(self, V):
        self._mInf = 1
        self._mTau = 1
        self._hInf = 1
        self._hTau = 1


class _Kir2p1(_KBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -70.6
        self.m = 1 / (1 + np.exp((V - -96.48) / 23.26))
        self.h = 1 / (1 + np.exp((V - -168.28) / -44.13))
        self._mpower = 1
        self._hpower = 2

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -96.48) / 23.26))
        self._mTau = 3.7 + -3.37 / (1 + np.exp((V - -32.9) / 27.93))
        self._hInf = 1 / (1 + np.exp((V - -168.28) / -44.13))
        self._hTau = 0.85 + 306.3 / (1 + np.exp((V - -118.29) / -27.23))


class _CaBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = None
            if type(vm) == float or type(vm) == np.float64:
                self.data_length = 1
            else:
                self.data_length = len(vm)
        else:
            self.targets = targets
            self.data_length = len(self.targets)
            self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        self.v_corr = 0.0
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._init_state(V)
        self.ions = ["Ca"]
        self.rel_perm = [1.0]

    def run(self, vm, p):
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._calculate_state(V)
        self._implement_state(V, p)

    def _implement_state(self, V, p):
        self.update_mh(p, time_unit=self.time_unit)
        P = self.m**self._mpower * self.h**self._hpower
        if self.targets is None:
            self.P = P
        else:
            self.P = np.zeros(self.mdl)
            self.P[self.targets] = P


class _Cav3p3(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 30
        Texpt = 0.0
        self.qt = 1.0
        self.m = 1 / (1 + np.exp((V - -45.454426) / -5.073015))
        self.h = 1 / (1 + np.exp((V - -74.031965) / 8.416382))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -45.454426) / -5.073015))
        self._mTau = 3.394938 + 54.187616 / (1 + np.exp((V - -40.040397) / 4.110392))
        self._hInf = 1 / (1 + np.exp((V - -74.031965) / 8.416382))
        self._hTau = 109.701136 + 0.003816 * np.exp(-V / 4.781719)


class _Cav2p1(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 135.0
        Texpt = 0.0
        self.qt = 1.0
        mAlpha = 8.5 / (1 + np.exp((V - 8) / -12.5))
        mBeta = 35 / (1 + np.exp((V + 74) / 14.5))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = 1.0
        self._mpower = 1
        self._hpower = 0

    def _calculate_state(self, V):
        mAlpha = 8.5 / (1 + np.exp((V - 8) / -12.5))
        mBeta = 35 / (1 + np.exp((V + 74) / 14.5))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = 1.0
        self._hTau = 1.0


class _Cav1p3(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 113.0
        Texpt = 21.0
        self.m = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self.h = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self._mTau = 5.0 + 20.0 / (1 + np.exp((V - -25.0) / 5))
        self._hInf = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._hTau = 20.0 + 50.0 / (1 + np.exp((V - -40.0) / 7))


class _Cav1p2(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 131.0
        Texpt = 21.0
        V = V - 10
        self.m = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self.h = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        V = V - 10
        self._mInf = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self._mTau = 5.0 + 20.0 / (1 + np.exp((V - -25.0) / 5))
        self._hInf = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._hTau = 20.0 + 50.0 / (1 + np.exp((V - -40.0) / 7))


class _Cav2p3(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 30
        Texpt = 0.0
        self.qt = 1.0
        mAlpha = 2.6 / (1 + np.exp((V + 7) / -8))
        mBeta = 0.18 / (1 + np.exp((V + 26) / 4))
        hAlpha = 0.0025 / (1 + np.exp((V + 32) / 8))
        hBeta = 0.19 / (1 + np.exp((V + 42) / -10))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = hAlpha / (hAlpha + hBeta)
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        mAlpha = 2.6 / (1 + np.exp((V + 7) / -8))
        mBeta = 0.18 / (1 + np.exp((V + 26) / 4))
        hAlpha = 0.0025 / (1 + np.exp((V + 32) / 8))
        hBeta = 0.19 / (1 + np.exp((V + 42) / -10))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = hAlpha / (hAlpha + hBeta)
        self._hTau = 1 / (hAlpha + hBeta)


class _Cav2p2(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 135
        Texpt = 36.0
        self.qt = 1.0
        mAlpha = 0.1 * (V - 20) / (1 - np.exp(-(V - 20) / 10))
        mBeta = 0.4 * np.exp(-(V + 25) / 18)
        hAlpha = 0.01 * np.exp(-(V + 50) / 10)
        hBeta = 0.1 / (1 + np.exp(-(V + 17) / 17))
        self.m = mAlpha / (mAlpha + mBeta)
        self.h = hAlpha / (hAlpha + hBeta)
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        mAlpha = 0.1 * (V - 20) / (1 - np.exp(-(V - 20) / 10))
        mBeta = 0.4 * np.exp(-(V + 25) / 18)
        hAlpha = 0.01 * np.exp(-(V + 50) / 10)
        hBeta = 0.1 / (1 + np.exp(-(V + 17) / 17))
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        self._hInf = hAlpha / (hAlpha + hBeta)
        self._hTau = 1 / (hAlpha + hBeta)


class _Cav3p1(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 30
        Texpt = 0.0
        self.qt = 1.0
        self.m = 1 / (1 + np.exp((V - -42.921064) / -5.163208))
        self.h = 1 / (1 + np.exp((V - -72.90742) / 4.575763))
        self._mpower = 1
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1 / (1 + np.exp((V - -42.921064) / -5.163208))
        inds_gt10 = (V >= -0.01).nonzero()
        self._mTau = -0.855809 + 1.493527 * np.exp(-V / 27.414182)
        self._mTau[inds_gt10] = 1.0
        self._hInf = 1 / (1 + np.exp((V - -72.90742) / 4.575763))
        self._hTau = 9.987873 + 0.002883 * np.exp(-V / 5.598574)


class _Ca_L2(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 131.0
        Texpt = 36.0
        self.qt = 1.0
        self.m = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self.h = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        self._mInf = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self._mTau = 10.0
        self._hInf = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._hTau = 59.0


class _Ca_L3(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 131.0
        Texpt = 36.0
        self.qt = 1.0
        V = V - 15
        self.m = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self.h = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        V = V - 15
        self._mInf = 1.0 / (1 + np.exp((V - -30.0) / -6))
        self._mTau = 10.0
        self._hInf = 1.0 / (1 + np.exp((V - -80.0) / 6.4))
        self._hTau = 59.0


class _Cav_G(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 131.0
        Texpt = 36.0
        self.qt = 1.0
        mAlpha = 0.055 * (-27 - V) / (np.exp((-27 - V) / 3.8) - 1)
        mBeta = 0.94 * np.exp((-75 - V) / 17)
        self.m = mAlpha / (mAlpha + mBeta)
        hAlpha = 0.000457 * np.exp((-13 - V) / 50)
        hBeta = 0.0065 / (np.exp((-V - 15) / 28) + 1)
        self.h = hAlpha / (hAlpha + hBeta)
        self._mpower = 2
        self._hpower = 1

    def _calculate_state(self, V):
        mAlpha = 0.055 * (-27 - V) / (np.exp((-27 - V) / 3.8) - 1)
        mBeta = 0.94 * np.exp((-75 - V) / 17)
        self._mInf = mAlpha / (mAlpha + mBeta)
        self._mTau = 1 / (mAlpha + mBeta)
        hAlpha = 0.000457 * np.exp((-13 - V) / 50)
        hBeta = 0.0065 / (np.exp((-V - 15) / 28) + 1)
        self._hInf = hAlpha / (hAlpha + hBeta)
        self._hTau = 1 / (hAlpha + hBeta)


class _CaLeak(_CaBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.vrev = 30
        Texpt = 23
        self.qt = 1.0
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0

    def _calculate_state(self, V):
        self._mInf = 1
        self._mTau = 1
        self._hInf = 1
        self._hTau = 1


class _ClBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = None
            if type(vm) == float or type(vm) == np.float64:
                self.data_length = 1
            else:
                self.data_length = len(vm)
        else:
            self.targets = targets
            self.data_length = len(self.targets)
            self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        self.v_corr = 0.0
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._init_state(V)
        self.ions = ["Cl"]
        self.rel_perm = [1.0]

    def run(self, vm, p):
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._calculate_state(V)
        self._implement_state(V, p)

    def _implement_state(self, V, p):
        self.update_mh(p, time_unit=self.time_unit)
        P = self.m**self._mpower * self.h**self._hpower
        if self.targets is None:
            self.P = P
        else:
            self.P = np.zeros(self.mdl)
            self.P[self.targets] = P


class _ClLeak(_ClBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0

    def _calculate_state(self, V):
        self._mInf = 1
        self._mTau = 1
        self._hInf = 1
        self._hTau = 1


class _FunBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = None
            if type(vm) == float or type(vm) == np.float64:
                self.data_length = 1
            else:
                self.data_length = len(vm)
        else:
            self.targets = targets
            self.data_length = len(self.targets)
            self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        self.v_corr = 0.0
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._init_state(V)
        self.ions = ["Na", "K", "Ca"]
        self.rel_perm = [self._PmNa, 1.0, self._PmCa]

    def run(self, vm, p):
        if self.targets is None:
            V = vm * 1000 + self.v_corr
        else:
            V = vm[self.targets] * 1000 + self.v_corr
        self._calculate_state(V)
        self._implement_state(V, p)

    def _implement_state(self, V, p):
        self.update_mh(p, time_unit=self.time_unit)
        P = self.m**self._mpower * self.h**self._hpower
        if self.targets is None:
            self.P = P
        else:
            self.P = np.zeros(self.mdl)
            self.P[self.targets] = P


class _HCN2(_FunBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.v_corr = 0
        V = V - 10
        self.m = 1.0 / (1 + np.exp((V - -99) / 6.2))
        self.h = 1
        self._mpower = 1
        self._hpower = 0
        self._PmCa = 0.05
        self._PmNa = 0.2

    def _calculate_state(self, V):
        self.vrev = -45
        V = V - 10
        self._mInf = 1.0 / (1 + np.exp((V - -99) / 6.2))
        self._mTau = 184.0
        self._hInf = 1
        self._hTau = 1


class _HCN4(_FunBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.v_corr = 0
        V = V - 10
        self.m = 1.0 / (1 + np.exp((V - -100) / 9.6))
        self.h = 1
        self._mpower = 1
        self._hpower = 0
        self._PmCa = 0.05
        self._PmNa = 0.2

    def _calculate_state(self, V):
        self.vrev = -45
        V = V - 10
        self._mInf = 1.0 / (1 + np.exp((V - -100) / 9.6))
        self._mTau = 461.0
        self._hInf = 1
        self._hTau = 1


class _HCN1(_FunBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.m = 1.0 / (1 + np.exp((V - -94) / 8.1))
        self.h = 1
        self._mpower = 1
        self._hpower = 0
        self._PmCa = 0.05
        self._PmNa = 0.2

    def _calculate_state(self, V):
        self.vrev = -45
        self._mInf = 1.0 / (1 + np.exp((V - -94) / 8.1))
        self._mTau = 30.0
        self._hInf = 1
        self._hTau = 1


class _HCNLeak(_FunBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.v_corr = 0
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0
        self._PmCa = 0.05
        self._PmNa = 0.33

    def _calculate_state(self, V):
        self.vrev = -45
        self._mInf = 1.0
        self._mTau = 1.0
        self._hInf = 1.0
        self._hTau = 1.0


class _HCN2_cAMP(_FunBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.v_corr = 0
        V = V - 20
        self.m = 1.0 / (1 + np.exp((V + 99) / 6.2))
        self.h = 1
        self._mpower = 1
        self._hpower = 0
        self._PmCa = 0.05
        self._PmNa = 0.2

    def _calculate_state(self, V):
        self.vrev = -45
        V = V - 20
        self._mInf = 1.0 / (1 + np.exp((V + 99) / 6.2))
        self._mTau = 184.0
        self._hInf = 1
        self._hTau = 1


class _HCN4_cAMP(_FunBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.v_corr = 0
        V = V - 20
        self.m = 1.0 / (1 + np.exp((V + 100) / 9.6))
        self.h = 1
        self._mpower = 1
        self._hpower = 0
        self._PmCa = 0.05
        self._PmNa = 0.2

    def _calculate_state(self, V):
        self.vrev = -45
        V = V - 24
        self._mInf = 1.0 / (1 + np.exp((V + 100) / 9.6))
        self._mTau = 461.0
        self._hInf = 1
        self._hTau = 1


class _CatBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = cells.mem_i
        else:
            self.targets = targets
        self.data_length = len(self.targets)
        self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        self.v_corr = 0.0
        V = vm[self.targets] * 1000 + self.v_corr
        self._init_state(V)
        self.ions = ["Na", "K", "Ca"]
        self.rel_perm = [self._pmNa, 1.0, self._pmCa]

    def run(self, vm, p):
        V = vm[self.targets] * 1000
        self._calculate_state(V)
        self._implement_state(V, p)

    def _implement_state(self, V, p):
        self.update_mh(p, time_unit=self.time_unit)
        P = self.m**self._mpower * self.h**self._hpower
        self.P = np.zeros(self.mdl)
        self.P[self.targets] = P


class _CatLeak(_CatBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.v_corr = 0
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0
        self._pmNa = 1.0
        self._pmCa = 0.0

    def _calculate_state(self, V):
        self._mInf = 1.0
        self._mTau = 1.0
        self._hInf = 1.0
        self._hTau = 1.0


class _CatLeak2(_CatBase):
    def _init_state(self, V):
        self.time_unit = 1.0
        self.v_corr = 0
        self.m = np.ones(self.data_length)
        self.h = np.ones(self.data_length)
        self._mpower = 0
        self._hpower = 0
        self._pmNa = 1.0
        self._pmCa = 1.0

    def _calculate_state(self, V):
        self._mInf = 1.0
        self._mTau = 1.0
        self._hInf = 1.0
        self._hTau = 1.0


class _MLBase(_Clock):
    def init(self, vm, cells, p, targets=None):
        if targets is None:
            self.targets = None
            if type(vm) == float or type(vm) == np.float64:
                self.data_length = 1
            else:
                self.data_length = len(vm)
        else:
            self.targets = targets
            self.data_length = len(self.targets)
            self.mdl = len(cells.mem_i)
        self.modulator = 1.0
        if self.targets is None:
            V = vm * 1000
        else:
            V = vm[self.targets] * 1000
        self._init_state(V)

    def run(self, vm, p):
        if self.targets is None:
            V = vm * 1000
        else:
            V = vm[self.targets] * 1000
        self._calculate_state(V)
        if self.kinetic_gate:
            self.update_ml(p, time_unit=self.time_unit)
        else:
            self.m = self._mInf
        if self.targets is None:
            self.P = self.m
        else:
            self.P = np.zeros(self.mdl)
            self.P[self.targets] = self.m


class _Kv_ML1(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -85
        self.ions = ["K"]
        self.rel_perm = [1]
        self.kinetic_gate = True
        self.Phi = 0.066
        self.m = 0.5 * (1 + np.tanh((V - 12.0) / 17.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V - 12) / 17))
        self._mTau = 1 / np.cosh((V - 12) / (2 * 17))


class _Kv2p1_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K"]
        self.rel_perm = [1]
        self.kinetic_gate = True
        self.Phi = 0.066
        self.m = 0.5 * (1 + np.tanh((V - 14.0) / 30.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V - 14) / 30))
        self._mTau = 1 / np.cosh((V - 14) / (2 * 30))


class _Kv1p3_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K"]
        self.rel_perm = [1]
        self.kinetic_gate = True
        self.Phi = 0.066
        self.m = 0.5 * (1 + np.tanh((V + 14.0) / 20.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 14) / 20))
        self._mTau = 1 / np.cosh((V + 14) / (2 * 20))


class _Kv1p5_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K"]
        self.rel_perm = [1]
        self.kinetic_gate = True
        self.Phi = 0.066
        self.m = 0.5 * (1 + np.tanh((V + 6.0) / 15.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 6) / 15))
        self._mTau = 1 / np.cosh((V + 6) / (2 * 15))


class _Kv1p5S_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K"]
        self.rel_perm = [1]
        self.kinetic_gate = True
        self.Phi = 0.00066 * 2
        self.m = 0.5 * (1 + np.tanh((V + 6.0) / 15.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 6) / 15))
        self._mTau = 1 / np.cosh((V + 6) / (2 * 15))


class _Nav_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 50
        self.ions = ["Na"]
        self.rel_perm = [1]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 17.0) / 18.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 17) / 18))
        self._mTau = 1


class _Cav_L_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 80
        self.ions = ["Ca"]
        self.rel_perm = [1]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 20.0) / 24.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 20) / 24))
        self._mTau = 1


class _Cav_L_ML2(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 80
        self.ions = ["Ca"]
        self.rel_perm = [1]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 20.0) / 12.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 20) / 12))
        self._mTau = 1


class _Cav_N_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 80
        self.ions = ["Ca"]
        self.rel_perm = [1]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 1.0) / 18.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 1.0) / 18.0))
        self._mTau = 1


class _Cav_T_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = 80
        self.ions = ["Ca"]
        self.rel_perm = [1]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 43.0) / 24.0))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 43) / 24.0))
        self._mTau = 1


class _Kir_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K"]
        self.rel_perm = [1]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 1 / np.cosh((V + 135) / 37)

    def _calculate_state(self, V):
        self._mInf = 1 / np.cosh((V + 135) / 37)
        self._mTau = 1


class _HCN2_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K", "Na"]
        self.rel_perm = [1, 0.2]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 99.0) / 12.4))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 99.0) / 12.4))
        self._mTau = 1


class _HCN4_ML(_MLBase):
    def _init_state(self, V):
        self.time_unit = 1000.0
        self.vrev = -65
        self.ions = ["K", "Na"]
        self.rel_perm = [1, 0.2]
        self.kinetic_gate = False
        self.Phi = 1.0
        self.m = 0.5 * (1 + np.tanh((V + 99.0) / 19.2))

    def _calculate_state(self, V):
        self._mInf = 0.5 * (1 + np.tanh((V + 99.0) / 19.2))
        self._mTau = 1


CLASSES = {
    "Nav1p2": _Nav1p2,
    "Nav1p3": _Nav1p3,
    "NavRat2": _NavRat2,
    "NavRat1": _NavRat1,
    "NavRat3": _NavRat3,
    "NaLeak": _NaLeak,
    "Nav1p6": _Nav1p6,
    "Kv1p1": _Kv1p1,
    "Kv1p2": _Kv1p2,
    "Kv1p3": _Kv1p3,
    "Kv1p4": _Kv1p4,
    "Kv1p5": _Kv1p5,
    "Kv1p6": _Kv1p6,
    "Kv2p1": _Kv2p1,
    "Kv2p2": _Kv2p2,
    "Kv3p1": _Kv3p1,
    "Kv3p2": _Kv3p2,
    "Kv3p3": _Kv3p3,
    "Kv3p4": _Kv3p4,
    "K_Fast": _K_Fast,
    "KLeak": _KLeak,
    "Kir2p1": _Kir2p1,
    "Cav3p3": _Cav3p3,
    "Cav2p1": _Cav2p1,
    "Cav1p3": _Cav1p3,
    "Cav1p2": _Cav1p2,
    "Cav2p3": _Cav2p3,
    "Cav2p2": _Cav2p2,
    "Cav3p1": _Cav3p1,
    "Ca_L2": _Ca_L2,
    "Ca_L3": _Ca_L3,
    "Cav_G": _Cav_G,
    "CaLeak": _CaLeak,
    "ClLeak": _ClLeak,
    "HCN2": _HCN2,
    "HCN4": _HCN4,
    "HCN1": _HCN1,
    "HCNLeak": _HCNLeak,
    "HCN2_cAMP": _HCN2_cAMP,
    "HCN4_cAMP": _HCN4_cAMP,
    "CatLeak": _CatLeak,
    "CatLeak2": _CatLeak2,
    "Kv_ML1": _Kv_ML1,
    "Kv2p1_ML": _Kv2p1_ML,
    "Kv1p3_ML": _Kv1p3_ML,
    "Kv1p5_ML": _Kv1p5_ML,
    "Kv1p5S_ML": _Kv1p5S_ML,
    "Nav_ML": _Nav_ML,
    "Cav_L_ML": _Cav_L_ML,
    "Cav_L_ML2": _Cav_L_ML2,
    "Cav_N_ML": _Cav_N_ML,
    "Cav_T_ML": _Cav_T_ML,
    "Kir_ML": _Kir_ML,
    "HCN2_ML": _HCN2_ML,
    "HCN4_ML": _HCN4_ML,
}
ROUTES = {
    "Nav1p2": (("Na", 1.0),),
    "Nav1p3": (("Na", 1.0),),
    "NavRat2": (("Na", 1.0),),
    "NavRat1": (("Na", 1.0),),
    "NavRat3": (("Na", 1.0),),
    "NaLeak": (("Na", 1.0),),
    "Nav1p6": (("Na", 1.0),),
    "Kv1p1": (("K", 1.0),),
    "Kv1p2": (("K", 1.0),),
    "Kv1p3": (("K", 1.0),),
    "Kv1p4": (("K", 1.0),),
    "Kv1p5": (("K", 1.0),),
    "Kv1p6": (("K", 1.0),),
    "Kv2p1": (("K", 1.0),),
    "Kv2p2": (("K", 1.0),),
    "Kv3p1": (("K", 1.0),),
    "Kv3p2": (("K", 1.0),),
    "Kv3p3": (("K", 1.0),),
    "Kv3p4": (("K", 1.0),),
    "K_Fast": (("K", 1.0),),
    "KLeak": (("K", 1.0),),
    "Kir2p1": (("K", 1.0),),
    "Cav3p3": (("Ca", 1.0),),
    "Cav2p1": (("Ca", 1.0),),
    "Cav1p3": (("Ca", 1.0),),
    "Cav1p2": (("Ca", 1.0),),
    "Cav2p3": (("Ca", 1.0),),
    "Cav2p2": (("Ca", 1.0),),
    "Cav3p1": (("Ca", 1.0),),
    "Ca_L2": (("Ca", 1.0),),
    "Ca_L3": (("Ca", 1.0),),
    "Cav_G": (("Ca", 1.0),),
    "CaLeak": (("Ca", 1.0),),
    "ClLeak": (("Cl", 1.0),),
    "HCN2": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "HCN4": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "HCN1": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "HCNLeak": (("Na", 0.33), ("K", 1.0), ("Ca", 0.05)),
    "HCN2_cAMP": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "HCN4_cAMP": (("Na", 0.2), ("K", 1.0), ("Ca", 0.05)),
    "CatLeak": (("Na", 1.0), ("K", 1.0), ("Ca", 0.0)),
    "CatLeak2": (("Na", 1.0), ("K", 1.0), ("Ca", 1.0)),
    "Kv_ML1": (("K", 1.0),),
    "Kv2p1_ML": (("K", 1.0),),
    "Kv1p3_ML": (("K", 1.0),),
    "Kv1p5_ML": (("K", 1.0),),
    "Kv1p5S_ML": (("K", 1.0),),
    "Nav_ML": (("Na", 1.0),),
    "Cav_L_ML": (("Ca", 1.0),),
    "Cav_L_ML2": (("Ca", 1.0),),
    "Cav_N_ML": (("Ca", 1.0),),
    "Cav_T_ML": (("Ca", 1.0),),
    "Kir_ML": (("K", 1.0),),
    "HCN2_ML": (("K", 1.0), ("Na", 0.2)),
    "HCN4_ML": (("K", 1.0), ("Na", 0.2)),
}


class InitializationRefused(ValueError):
    def __init__(self, reason, cache):
        super().__init__(str(reason))
        self.cache = cache
        self.source_exception = type(reason).__name__


def initialize(class_name, voltage, targets):
    core = CLASSES[class_name]()
    # The native network constructor does not force an integer dtype for an
    # empty profile list; retain its initialization refusal.
    try:
        core.init(
            voltage,
            SimpleNamespace(mem_i=np.arange(len(voltage))),
            SimpleNamespace(),
            targets=np.asarray(targets),
        )
    except Exception as error:
        raise InitializationRefused(error, dict(vars(core))) from error
    core.chan_flux = np.zeros(len(voltage))
    core.DChan = None
    return dict(vars(core))


def update(class_name, incoming, voltage, dt_s, modulator):
    core = object.__new__(CLASSES[class_name])
    vars(core).update(
        {
            key: value.copy() if isinstance(value, np.ndarray) else value
            for key, value in incoming.items()
        }
    )
    core.modulator = modulator
    core.run(voltage, SimpleNamespace(dt=dt_s))
    return dict(vars(core))


CALCULATED_FIELDS = {
    "CaLeak": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Ca_L2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Ca_L3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "CatLeak": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "CatLeak2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav1p2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav1p3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav2p1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav2p2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav2p3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav3p1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav3p3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav_G": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Cav_L_ML": ("_mInf", "_mTau"),
    "Cav_L_ML2": ("_mInf", "_mTau"),
    "Cav_N_ML": ("_mInf", "_mTau"),
    "Cav_T_ML": ("_mInf", "_mTau"),
    "ClLeak": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "HCN1": ("_hInf", "_hTau", "_mInf", "_mTau", "vrev"),
    "HCN2": ("_hInf", "_hTau", "_mInf", "_mTau", "vrev"),
    "HCN2_ML": ("_mInf", "_mTau"),
    "HCN2_cAMP": ("_hInf", "_hTau", "_mInf", "_mTau", "vrev"),
    "HCN4": ("_hInf", "_hTau", "_mInf", "_mTau", "vrev"),
    "HCN4_ML": ("_mInf", "_mTau"),
    "HCN4_cAMP": ("_hInf", "_hTau", "_mInf", "_mTau", "vrev"),
    "HCNLeak": ("_hInf", "_hTau", "_mInf", "_mTau", "vrev"),
    "KLeak": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "K_Fast": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kir2p1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kir_ML": ("_mInf", "_mTau"),
    "Kv1p1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv1p2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv1p3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv1p3_ML": ("_mInf", "_mTau"),
    "Kv1p4": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv1p5": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv1p5S_ML": ("_mInf", "_mTau"),
    "Kv1p5_ML": ("_mInf", "_mTau"),
    "Kv1p6": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv2p1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv2p1_ML": ("_mInf", "_mTau"),
    "Kv2p2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv3p1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv3p2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv3p3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv3p4": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Kv_ML1": ("_mInf", "_mTau"),
    "NaLeak": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Nav1p2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Nav1p3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Nav1p6": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "NavRat1": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "NavRat2": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "NavRat3": ("_hInf", "_hTau", "_mInf", "_mTau"),
    "Nav_ML": ("_mInf", "_mTau"),
}
