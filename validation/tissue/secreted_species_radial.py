"""The held-sphere radial world of the secreted-species guards and qualification (D150 version 1).

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §6, §7, §11.2-§11.4 and Appendix A. A sphere of radius R
is held at c0 by a bath; shells R + i dr to R + (i + 1) dr are finite outside nodes with their exact
volumes; an outer bath at the trace holds the far boundary. The species diffuses on the radial
faces only (every ion diffusivity is 0, every patch impermeable: the species-only world), and is
cleared at every shell by scheduled_species_turnover@1's node clearance k, so the acceptance runs
the operator, not @3 alone. A quiescent cell faces every shell through a capacitive patch, so every
node lies in a capacitor component with a held bath.

**Faces** (the lead's requirement on radial builders, §11.5 item 8): each face joins two points and
is declared with the exact spherical-shell conductance between them, area 4 pi r_a r_b over length
r_b - r_a. The points are the source sphere's surface R, each shell's mid-radius, and the outer
boundary.

**References** (independent NumPy, from Appendix A, never from engine code): the same declared
finite-volume system, dn_i/dt = sum_f kappa_f (c_j - c_i) - k n_i with c = n / V and
kappa_f = D A_f / L_f (pL/s), solved exactly by the matrix exponential, and its steady state.
"""

import math
from dataclasses import dataclass

import numpy as np

from validation.tissue import secreted_species_fixtures as fx

PL_PER_M3 = 1e15


@dataclass(frozen=True)
class Geometry:
    radius_m: float
    width_m: float
    shells: int

    @property
    def edges(self):
        return np.asarray([self.radius_m + i * self.width_m for i in range(self.shells + 1)])

    @property
    def points(self):
        """The source surface, each shell's mid-radius, the outer boundary (m)."""
        e = self.edges
        return np.concatenate(([e[0]], 0.5 * (e[:-1] + e[1:]), [e[-1]]))

    @property
    def volumes_pL(self):
        e = self.edges
        return 4.0 / 3.0 * math.pi * (e[1:] ** 3 - e[:-1] ** 3) * PL_PER_M3

    def faces(self):
        """(sender, receiver, area m^2, length m) of every radial face, source to outer."""
        names = ["source", *(f"shell_{i}" for i in range(self.shells)), "outer"]
        r = self.points
        return [
            (names[i], names[i + 1], 4.0 * math.pi * r[i] * r[i + 1], r[i + 1] - r[i])
            for i in range(len(names) - 1)
        ]


def world(
    geometry,
    *,
    diffusivity,
    clearance,
    c0_mM,
    trace_mM,
    profile_mM=None,
    dt,
    end,
    solver=fx.IMEX,
    observation_every=None,
):
    """The radial composite definition: @3 with S, and turnover's clearance at every shell.

    profile_mM: S in each shell at t = 0 (a pre-formed profile; the trace when None).
    """
    shells = [f"shell_{i}" for i in range(geometry.shells)]
    volumes = geometry.volumes_pL
    base = fx.world(
        cells=(("cell", 1.0),),
        nodes=tuple(zip(shells, (float(v) for v in volumes), strict=True)),
        baths=("bath", "source", "outer"),
        contacts=tuple((f"contact_{i}", "cell", name) for i, name in enumerate(shells)),
        faces=tuple(
            (f"face_{i}", a, b, float(area), float(length))
            for i, (a, b, area, length) in enumerate(geometry.faces())
        ),
        dt=dt,
        end=end,
        solver=solver,
        observation_times=None
        if observation_every is None
        else fx.grid_times(end, dt, observation_every),
        trace_mM=trace_mM,
        concentrations_mM={
            "source": c0_mM,
            **(
                {}
                if profile_mM is None
                else {s: float(c) for s, c in zip(shells, profile_mM, strict=True)}
            ),
        },
        diffusivity=diffusivity,
    )
    return fx.with_turnover(
        base,
        [(f"decay_{i}", name, "clearance") for i, name in enumerate(shells)],
        [(f"decay_{i}", None, [(0.0, clearance)]) for i in range(geometry.shells)],
    )


def operator(geometry, *, diffusivity, clearance, c0_mM, outer_mM):
    """(M, g): the declared system dc/dt = -M c + g on the shells (1/s, mM/s)."""
    n = geometry.shells
    v = geometry.volumes_pL
    a = np.zeros((n, n))
    b = np.zeros(n)
    for i, (_, _, area, length) in enumerate(geometry.faces()):
        kappa = diffusivity * area / length * PL_PER_M3  # pL/s.
        left, right = i - 1, i  # Shell indices on each side (-1: source, n: outer).
        if left >= 0:
            a[left, left] += kappa
        if right < n:
            a[right, right] += kappa
        if left >= 0 and right < n:
            a[left, right] -= kappa
            a[right, left] -= kappa
        if left < 0:
            b[right] += kappa * c0_mM
        if right >= n:
            b[left] += kappa * outer_mM
    a += np.diag(clearance * v)
    return a / v[:, None], b / v


def steady(m, g):
    return np.linalg.solve(m, g)


def solution(m, g, initial, times):
    """The exact solution c(t) = c_ss + expm(-M t) (c(0) - c_ss) at each time [time, shell]."""
    from scipy.linalg import expm

    c_ss = steady(m, g)
    return np.stack([c_ss + expm(-m * t) @ (np.asarray(initial) - c_ss) for t in times])


def shell_concentrations(spec, history_or_observations, geometry):
    """[time, shell] S concentrations (mM) from observations' extracellular amounts."""
    s = list(spec.model.species_ids).index(fx.SPECIES)
    ids = [o.id for o in spec.model.extracellular]
    cols = [ids.index(f"shell_{i}") for i in range(geometry.shells)]
    amounts = np.asarray(history_or_observations.extracellular_amount)[:, s, cols]
    return amounts / geometry.volumes_pL


def pre_formed(geometry, *, diffusivity, clearance, c0_mM, trace_mM, fraction=0.5):
    """The guard worlds' start (the lead's ruling 5): a fraction of the steady profile above the
    trace, so no node changes by decades in a step."""
    m, g = operator(
        geometry, diffusivity=diffusivity, clearance=clearance, c0_mM=c0_mM, outer_mM=trace_mM
    )
    return fraction * (steady(m, g) - trace_mM) + trace_mM


def max_dt_k(geometry, *, diffusivity, clearance, dt):
    """max_i dt K_ii of the declared system (the explicit stages' stiffness)."""
    m, _ = operator(geometry, diffusivity=diffusivity, clearance=clearance, c0_mM=0, outer_mM=0)
    return float(dt * np.max(np.diag(m)))
