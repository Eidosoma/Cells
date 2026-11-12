"""J1 diagnostic arm A3: R-full with the lumen as an annular slit in N fixed rings.

Registered in validation/division/j1_diagnostic_arms.json (arm A3). numpy/scipy only, beside
cleft_egg_reference.py (R-full), whose transport laws, pulse protocol and calibration it reuses.

Geometry (all declared): the slit lies in the cleavage plane between the bridge radius r_b and the
mouth radius r_m, cut into N rings of equal radial width (ring 0 at the mouth). New membrane is
inserted at the slit's inner edge on the registered schedule: the face area (one blastomere's side)
is A_face(t) = A_new(t)/2, and ring k holds face area min(max(A_face - A_k, 0), full_k), with A_k
the face area at which the inner edge reaches the ring (the last ring is uncapped). Ring k >= 1
switches on with a declared seed face area. Each ring is a lumen node: its membrane is both faces
(2 x face, capacitance c_new x 2 x face), its volume w x face. Neighbouring rings exchange by the
log-mean two-point law with free-solution D across 2 pi r w at their shared radius, over the
distance between their radial centres. Ring 0 reaches the bath through the rim: either the
calibrated A/L x D (registered law) or, for the geometric-access check, D x 2 pi r_m w over the
distance from ring 0's centre to the mouth. New volume appears in the growing ring and fills
with bath fluid (the registered rule); with N = 1 the model is the registered single lumen.

Numerics: the right-hand side takes a batch of states (states x m), so scipy's BDF and Radau
form their finite-difference Jacobian in one call; the declared integrator for A3 is BDF
(Rings.method), cross-checked on one point against Radau.
"""

import math
import time
from dataclasses import dataclass
from functools import partial

import numpy as np
from scipy.integrate import solve_ivp

from validation.division import cleft_egg_reference as ref

F, R, FMOL = ref.F, ref.R, ref.FMOL
Z = np.array(ref.Z, dtype=float)
FLOOR_mM = (
    1e-12  # guards solver trial iterates in nearly empty seed rings; physical states stay far above
)


@dataclass(frozen=True)
class Rings:
    n: int
    r_bridge_m: float
    r_mouth_m: float
    seed_face_m2: float = 1e-11  # face area each ring k >= 1 switches on with (numerical)
    rim: str = "calibrated"  # "calibrated" (A/L x D) or "geometric"
    method: str = "BDF"  # A3's declared integrator (overrides the caller's)


def ring_geometry(bridge_area_m2, face_area_j1_m2):
    """(r_bridge, r_mouth) of the annulus holding face_area_j1 outside a bridge disc."""
    r_b = math.sqrt(bridge_area_m2 / math.pi)
    return r_b, math.sqrt(face_area_j1_m2 / math.pi + r_b * r_b)


def ghk_factor_v(x):
    """x / (1 - exp(-x)) elementwise: series at small |x|; tends to 0 at -inf and to x at inf."""
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        direct = x / -np.expm1(-x)
    return np.where(np.abs(x) < 1e-6, 1.0 + x / 2.0 + x * x / 12.0, direct)


def ghk_flux_v(pa, z, u, c_in, c_out):
    """Outward constant-field flux (mol/s); arrays broadcast."""
    x = z * u
    return pa * (ghk_factor_v(x) * c_in - ghk_factor_v(-x) * c_out)


def logmean_flux_v(k, z, u, c_a, c_b):
    """Log-mean two-point flux a -> b (mol/s): k Lm(c_a, c_b) (ln(c_a/c_b) + z u)."""
    c_a = np.maximum(c_a, FLOOR_mM)
    c_b = np.maximum(c_b, FLOOR_mM)
    d = (c_a - c_b) / c_b
    big = np.abs(d) >= 1e-8
    safe = np.where(big, d, 1.0)  # both np.where branches are evaluated: keep the masked one finite
    lm = np.where(big, (c_a - c_b) / np.log1p(safe), c_b * (1.0 + d / 2.0 - d * d / 12.0))
    return k * lm * (np.log(c_a / c_b) + z * u)


@dataclass
class RingSegment:
    active: np.ndarray  # bool per ring
    act: np.ndarray  # indices of active rings
    growing: int | None  # ring index, or None
    growing_pos: int | None  # its position within act
    current_A: float
    area_t0: float
    area_a0: float
    rate: float


class RingModel:
    def __init__(self, egg, rings, background_fmol):
        assert egg.new_faces == "lumen" and not egg.extended and egg.access_law == "logmean"
        self.egg, self.rings, self.x_i = egg, rings, background_fmol
        n = rings.n
        self.bounds = np.array(
            [rings.r_mouth_m - j * (rings.r_mouth_m - rings.r_bridge_m) / n for j in range(n + 1)]
        )
        self.on_face = math.pi * (rings.r_mouth_m**2 - self.bounds[:-1] ** 2)
        self.full_face = math.pi * (self.bounds[:-1] ** 2 - self.bounds[1:] ** 2)
        self.seed = np.where(np.arange(n) >= 1, rings.seed_face_m2, 0.0)
        self.pa_old = np.array([egg.p_old * w * egg.old_area_m2 for w in egg.old_relative])
        self.p_new = np.array(egg.new_permeability)
        self.D = np.array(egg.access_D)
        self.bath = np.array(egg.bath_mM)

    def faces(self, face_total, active):
        """Face area of each ring (geometric part, seed added for active rings k >= 1)."""
        geo = np.clip(face_total - self.on_face, 0.0, None)
        geo[:-1] = np.minimum(geo[:-1], self.full_face[:-1])
        return np.where(active, geo + self.seed, 0.0), geo

    def inner_radius(self, geo):
        return np.sqrt(np.maximum(self.bounds[:-1] ** 2 - geo / math.pi, 0.0))

    def fields(self, t, Y, seg):
        """Potentials and concentrations for a batch of states Y (states x m)."""
        egg, n = self.egg, self.rings.n
        m = Y.shape[1]
        ci = np.stack([Y[1], Y[2], Y[1] + Y[2] + self.x_i - Y[0]]) * (FMOL / egg.cytosol_volume_m3)
        qi = Y[0] * (FMOL * F)
        act = seg.act
        if len(act) == 0:
            return dict(ci=ci, phi_i=qi / egg.old_capacitance_F, act=act)
        area = seg.area_a0 + seg.rate * (t - seg.area_t0)
        face, geo = self.faces(area / 2.0, seg.active)
        fa = face[act]
        ring = Y[3 : 3 + 3 * n].reshape(n, 3, m)[act]
        q = ring[:, 0, :] * (FMOL * F)
        cap = egg.new_specific_capacitance_F_m2 * 2.0 * fa
        vol = egg.gap_width_m * fa
        cc = np.stack([ring[:, 1, :], ring[:, 2, :], ring[:, 1, :] + ring[:, 2, :] - ring[:, 0, :]])
        cc = cc * (FMOL / vol)[None, :, None]
        phi_i = (qi + q.sum(axis=0)) / egg.old_capacitance_F
        v_new = -q / cap[:, None]
        return dict(
            ci=ci,
            phi_i=phi_i,
            act=act,
            area=area,
            face=face,
            geo=geo,
            fa=fa,
            vol=vol,
            cc=cc,
            v_new=v_new,
            phi=phi_i[None, :] - v_new,
        )

    def rhs(self, t, y, seg):
        Y = y if y.ndim == 2 else y[:, None]
        egg, n = self.egg, self.rings.n
        f = self.fields(t, Y, seg)
        rt = egg.rt
        ci = f["ci"]
        out = ghk_flux_v(
            self.pa_old[:, None], Z[:, None], (F * f["phi_i"] / rt)[None, :], ci, self.bath[:, None]
        )
        dY = np.zeros_like(Y)
        act = f["act"]
        if len(act):
            cc, phi = f["cc"], f["phi"]
            pa = (self.p_new[:, None] * (2.0 * f["fa"])[None, :])[:, :, None]
            j_mem = ghk_flux_v(
                pa, Z[:, None, None], (F * f["v_new"] / rt)[None, :, :], ci[:, None, :], cc
            )
            dn = j_mem.copy()  # into each active ring (mol/s): species x rings x batch
            out = out + j_mem.sum(axis=1)
            if self.rings.rim == "calibrated":
                k_rim = egg.a_over_l_m * self.D
            else:
                inner0 = self.inner_radius(f["geo"])[0]
                dist = 0.5 * (self.bounds[0] - inner0)
                k_rim = self.D * (2.0 * math.pi * self.bounds[0] * egg.gap_width_m) / dist
            dn[:, 0, :] -= logmean_flux_v(
                k_rim[:, None],
                Z[:, None],
                (F * phi[0] / rt)[None, :],
                cc[:, 0, :],
                self.bath[:, None],
            )
            if len(act) > 1:
                inner = self.inner_radius(f["geo"])
                centre = 0.5 * (self.bounds[:-1] + inner)
                dist = centre[act[:-1]] - centre[act[1:]]
                cross = 2.0 * math.pi * self.bounds[act[1:]] * egg.gap_width_m
                k_ab = (self.D[:, None] * (cross / dist)[None, :])[:, :, None]
                j_ab = logmean_flux_v(
                    k_ab,
                    Z[:, None, None],
                    (F * (phi[:-1] - phi[1:]) / rt)[None, :, :],
                    cc[:, :-1, :],
                    cc[:, 1:, :],
                )
                dn[:, :-1, :] -= j_ab
                dn[:, 1:, :] += j_ab
            if seg.growing is not None:
                g = seg.growing_pos
                dn[:, g, :] += self.bath[:, None] * (egg.gap_width_m * seg.rate / 2.0)
                dY[-1] = (
                    0.5 * f["v_new"][g] ** 2 * egg.new_specific_capacitance_F_m2 * seg.rate * 1e12
                )
            rings_dy = dY[3 : 3 + 3 * n].reshape(n, 3, -1)
            rings_dy[act, 0, :] = np.einsum("s,sam->am", Z, dn) / FMOL
            rings_dy[act, 1, :] = dn[0] / FMOL
            rings_dy[act, 2, :] = dn[1] / FMOL
        inj_k = egg.pulses.carrier_K * seg.current_A / F
        dY[1] = -out[0] / FMOL
        dY[2] = (-out[1] + inj_k) / FMOL
        dY[0] = (-(Z[:, None] * out).sum(axis=0) + seg.current_A / F) / FMOL
        return dY if y.ndim == 2 else dY[:, 0]

    def state(self, t, y, seg):
        """Unbatched fields for records, spread over all N rings (NaN where inactive)."""
        f = self.fields(t, y[:, None], seg)
        n = self.rings.n
        out = dict(ci=f["ci"][:, 0], active=seg.active, phi_i=float(f["phi_i"][0]))
        if len(f["act"]) == 0:
            out["face"] = np.zeros(n)
            return out
        act = f["act"]
        phi = np.full(n, np.nan)
        phi[act] = f["phi"][:, 0]
        cc = np.full((3, n), np.nan)
        cc[:, act] = f["cc"][:, :, 0]
        vol = np.zeros(n)
        vol[act] = f["vol"]
        out.update(phi=phi, cc=cc, vol=vol, face=f["face"], geo=f["geo"])
        return out


def time_of_area(egg, target):
    """Time at which the registered schedule's new-membrane area reaches target (m2)."""
    a = egg.activation_area_m2
    if target <= a:
        return egg.onset_s
    for i, (start, rate) in enumerate(egg.schedule):
        stop = egg.schedule[i + 1][0] if i + 1 < len(egg.schedule) else math.inf
        reach = a + rate * (stop - start)
        if target <= reach and rate > 0:
            return start + (target - a) / rate
        a = reach
    return math.inf


def simulate(egg, t_end, *, rings, record=(), rtol=1e-10, method=None):
    """Integrate the ring model from t = 0 to t_end; returns an R-full Run (ring detail in .at).

    The integrator is rings.method when set (A3's declaration), else `method`.
    """
    started = time.perf_counter()
    method = rings.method or method or "BDF"
    vectorized = method in ("BDF", "Radau")
    n = rings.n
    y0, background, v0 = ref.initial_state(egg)
    y = np.zeros(3 + 3 * n + 1)
    y[:3] = y0[: ref.QC]
    model = RingModel(egg, rings, background)
    switch_on = [time_of_area(egg, 2.0 * f) for f in model.on_face]
    switch_on[0] = egg.onset_s
    points = ref.breakpoints(egg, t_end, record)
    points = sorted({*points, *(t for t in switch_on if 0.0 < t < t_end)})
    p = egg.pulses
    pulse_of_onset, pulse_of_sample = {}, {}
    if p.enabled:
        k = 0
        while p.onset(k) <= t_end:
            pulse_of_onset[p.onset(k)] = k
            pulse_of_sample[p.onset(k) + p.sample_s] = k
            k += 1
    atol = np.full(y.size, 1e-9)
    atol[1:3] = 1e-6
    atol[-1] = 1e-12
    active = np.zeros(n, dtype=bool)
    onset_V, sample_V, at = {}, {}, {}
    steps = 0
    record = set(record)

    def segment_for(t0, t1):
        act = np.flatnonzero(active)
        if t0 < egg.onset_s:
            return RingSegment(
                active.copy(), act, None, None, ref.current_at(egg, t0), t0, 0.0, 0.0
            )
        face_mid = egg.area(0.5 * (t0 + t1)) / 2.0
        growing = None
        for k in act:
            if face_mid >= model.on_face[k] and (
                k == n - 1 or face_mid < model.on_face[k] + model.full_face[k]
            ):
                growing = int(k)
        pos = None if growing is None else int(np.flatnonzero(act == growing)[0])
        return RingSegment(
            active.copy(),
            act,
            growing,
            pos,
            ref.current_at(egg, t0),
            t0,
            egg.area(t0),
            egg.rate(t0, t1),
        )

    def snapshot(t, y, seg):
        s = model.state(t, y, seg)
        act = s["active"]
        if act.any():
            vol = s["vol"]
            mean = (s["cc"][:, act] * vol[act]).sum(axis=1) / vol[act].sum()
            ring_mM = [list(map(float, s["cc"][:, k])) if act[k] else None for k in range(n)]
            ring_phi = [float(s["phi"][k]) if act[k] else None for k in range(n)]
        else:
            mean, ring_mM, ring_phi = None, None, None
        return dict(
            V=s["phi_i"],
            cytosol_mM=list(map(float, s["ci"])),
            ring_active=act.tolist(),
            ring_face_m2=list(map(float, s["face"])),
            ring_potential_V=ring_phi,
            ring_mM=ring_mM,
            lumen_mean_mM=None if mean is None else list(map(float, mean)),
            heat_pJ=float(y[-1]),
            state=y.tolist(),
        )

    for t0, t1 in zip(points, points[1:], strict=False):
        for k in range(n):
            if not active[k] and t0 >= switch_on[k]:
                active[k] = True
                face0 = (egg.area(t0) / 2.0) if k == 0 else rings.seed_face_m2
                vol0 = egg.gap_width_m * face0
                base = 3 + 3 * k
                y = y.copy()
                y[base] = 0.0
                y[base + 1] = egg.bath_mM[0] * vol0 / FMOL
                y[base + 2] = egg.bath_mM[1] * vol0 / FMOL
        seg = segment_for(t0, t1)
        if t0 in pulse_of_onset:
            onset_V[pulse_of_onset[t0]] = model.state(t0, y, seg)["phi_i"]
        if t0 in record:
            at[t0] = snapshot(t0, y, seg)
        sol = solve_ivp(
            model.rhs,
            (t0, t1),
            y,
            method=method,
            rtol=rtol,
            atol=atol,
            args=(seg,),
            vectorized=vectorized,
        )
        if not sol.success:
            raise RuntimeError(f"integration failed on [{t0}, {t1}]: {sol.message}")
        steps += sol.t.size - 1
        y = sol.y[:, -1].copy()
        if t1 in pulse_of_sample:
            sample_V[pulse_of_sample[t1]] = model.state(t1, y, seg)["phi_i"]
    if t_end in record:
        at[t_end] = snapshot(t_end, y, seg)
    if t_end in pulse_of_onset:
        onset_V[pulse_of_onset[t_end]] = model.state(t_end, y, seg)["phi_i"]
    return ref.Run(egg, background, v0, onset_V, sample_V, at, steps, time.perf_counter() - started)


def runner(rings):
    """An R-full runner (for rm_at, calibrate_* and j1_readout) bound to one ring geometry."""
    return partial(simulate, rings=rings)
