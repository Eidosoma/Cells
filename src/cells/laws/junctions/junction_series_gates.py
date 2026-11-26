"""cells.junction.junction_series_gates@1: a junction's conductance through two voltage gates in series, each a
two-state gate with a residual conductance (FR-30; docs/JUNCTION_TWO_RELAXATION_DESIGN.md, option
(A), as the lead ruled on 20 November 2026).

**One gate.** Its state is its conductance factor c in [r, 1], where r is its residual and x its
open fraction: c = r + (1 − r)·x. Then dc/dt = α(1 − c) − β(c − r), which is
cells.junction.junction_voltage_relaxation@1's right-hand side with r in place of its minimum. So that law is the
one-gate case, and every gate keeps its `Rates` (alpha, beta, the steady c as target, and α + β as
relaxation) and its exact constant-voltage step.

**Two kinds of gate,** fixed per gate (`kinds`, static):
- `threshold_relaxation`: cells.junction.junction_voltage_relaxation@1's own rates and parameters (a threshold
  and a minimum), reused as they are; BETSE v1.5.0's rates are cited in that module;
- `boltzmann_eyring`: a two-state gate in |V|, for cited constants.
  - With u = A·(|V| − V0), α = λ·exp(−δ·u) opens and β = λ·exp((1 − δ)·u) closes.
  - So α/β = exp(−u): detailed balance. The steady open fraction is the Boltzmann 1/(1 + exp(u)),
    with midpoint V0 and slope A.
  - δ in [0, 1] splits the voltage dependence between the two directions. It is a kinetic choice,
    and it never moves the steady state.
  - A is a fitted slope and nothing more. The source this law was designed against prints no unit
    for it, so no gating charge is derived from it (the lead's ruling).

**Two gates in series,** fast and slow (`GATES`). The junction's relative conductance is
g = c_fast · c_slow.
- **Consistency.** The gates are independent, so the pair is a product of two two-state chains. It
  keeps detailed balance, and its four-state cycle passes Kolmogorov's test exactly.
- **The exact step.** At a fixed voltage each c_i relaxes exactly. So the pair's exact step is two
  of cells.junction.junction_voltage_relaxation@1's `advance_clamped`, and its decay holds three exponentials:
  k_fast, k_slow and their sum.

**Routes** keep tracer transfer apart from electrical coupling. `open_fractions` gives each gate's
x. A route declares its own residual ρ_i per gate, and its factor is Π_i (ρ_i + (1 − ρ_i)·x_i).
Ions take ρ_i = r_i, which gives g; a large tracer may take ρ_i = 0. A route never takes g as a
tracer's factor.

**Registered, development only** (FR-30's @3 integration, D262; the @3 owner's addition to this
module, for its builder's review). Its declaration (`LAW`, a cells.junction_law@1 with gate_count 2
and this module's `conductance`) is registered through @3's model table. @3's parser admits it only
on a junction whose gate block declares `development: true`, and a registered or judged result
whose definition carries that flag is not admissible, until a voltage series qualifies the law.
"""

from typing import Any, NamedTuple

import jax.numpy as jnp

from cells.laws.junctions import junction_voltage_relaxation as relaxation
from cells.modules import Citation, CitedWork, JunctionLaw

LAW_ID = "cells.junction.junction_series_gates@1"
GATES = ("fast", "slow")
GATE_COUNT = len(GATES)
KINDS = ("threshold_relaxation", "boltzmann_eyring")
MAX_ABS_VOLTAGE_V = relaxation.MAX_ABS_VOLTAGE_V
MAX_EXPONENT = 80.0  # the largest |u| admitted on the domain, so every rate stays finite
Rates = relaxation.Rates


class BoltzmannEyring(NamedTuple):
    """A boltzmann_eyring gate's parameters: a numeric pytree, broadcast over [..., edge]."""

    rate_per_s: Any  # λ: α = β = λ at the midpoint
    slope_per_V: Any  # A: a fitted slope (the source prints no unit), never a gating charge
    midpoint_V: Any  # V0: the steady open fraction is one half at |V| = V0
    split: Any  # δ in [0, 1]: the share of the voltage dependence in the opening rate
    residual: Any  # r in [0, 1]: the closed state's relative conductance


def _check_kinds(kinds):
    kinds = tuple(kinds)
    if len(kinds) != GATE_COUNT or any(kind not in KINDS for kind in kinds):
        raise ValueError(f"{LAW_ID} has {GATE_COUNT} gates, each one of {KINDS}, not {kinds}")
    return kinds


def boltzmann_eyring_kinetics(voltage, parameters, *, xp=jnp):
    """A boltzmann_eyring gate's Rates at a junction voltage (V, s), the steady c as target."""
    lam, slope, midpoint, split, residual = parameters
    u = slope * (xp.abs(voltage) - midpoint)
    alpha = lam * xp.exp(-split * u)
    beta = lam * xp.exp((1.0 - split) * u)
    open_steady = xp.exp(-xp.logaddexp(0.0, u))  # 1/(1 + exp(u)), stable at both ends
    return Rates(alpha, beta, residual + (1.0 - residual) * open_steady, alpha + beta)


def gate_kinetics(kind, voltage, parameters, *, xp=jnp):
    """One gate's Rates: cells.junction.junction_voltage_relaxation@1's kinetics, or boltzmann_eyring's."""
    if kind == "threshold_relaxation":
        return relaxation.kinetics(voltage, parameters, xp=xp)
    if kind == "boltzmann_eyring":
        return boltzmann_eyring_kinetics(voltage, parameters, xp=xp)
    raise ValueError(f"A gate's kind is one of {KINDS}, not {kind!r}")


def residual_of(kind, parameters):
    """A gate's residual r: threshold_relaxation's minimum, or boltzmann_eyring's residual."""
    if kind == "threshold_relaxation":
        return parameters.minimum_open_fraction
    if kind == "boltzmann_eyring":
        return parameters.residual
    raise ValueError(f"A gate's kind is one of {KINDS}, not {kind!r}")


def kinetics(voltage, parameters, *, kinds, xp=jnp):
    """Each gate's Rates, in GATES order (parameters: one NamedTuple per gate)."""
    kinds = _check_kinds(kinds)
    pairs = zip(kinds, parameters, strict=True)
    return tuple(gate_kinetics(k, voltage, p, xp=xp) for k, p in pairs)


def rhs(gates, voltage, parameters, *, kinds, xp=jnp):
    """Each gate's dc/dt = α(1 − c) − β(c − r): one physical-time derivative per gate."""
    kinds = _check_kinds(kinds)
    out = []
    for c, kind, p in zip(gates, kinds, parameters, strict=True):
        rate = gate_kinetics(kind, voltage, p, xp=xp)
        out.append(rate.alpha_per_s * (1 - c) - rate.beta_per_s * (c - residual_of(kind, p)))
    return tuple(out)


def advance_clamped(gates, voltage, parameters, dt_s, *, kinds, xp=jnp):
    """The exact step over an interval of constant voltage: each gate's own exact step, the
    formula of cells.junction.junction_voltage_relaxation@1's advance_clamped (that function itself for a
    threshold_relaxation gate). Like it, this is not a solver for a freely varying voltage."""
    kinds = _check_kinds(kinds)
    out = []
    for c, kind, p in zip(gates, kinds, parameters, strict=True):
        if kind == "threshold_relaxation":
            out.append(relaxation.advance_clamped(c, voltage, p, dt_s, xp=xp))
            continue
        rate = gate_kinetics(kind, voltage, p, xp=xp)
        out.append(c + (rate.target - c) * (-xp.expm1(-rate.relaxation_per_s * dt_s)))
    return tuple(out)


def conductance(gates, *, xp=jnp):
    """The junction's relative conductance: the product of its gates' factors."""
    out = xp.ones_like(gates[0])
    for c in gates:
        out = out * c
    return out


def steady(voltage, parameters, *, kinds, xp=jnp):
    """The steady relative conductance at a constant voltage: the product of the gates' targets."""
    return conductance(tuple(r.target for r in kinetics(voltage, parameters, kinds=kinds, xp=xp)),
                       xp=xp)  # fmt: skip


def open_fractions(gates, parameters, *, kinds, xp=jnp):
    """Each gate's open fraction x = (c − r)/(1 − r); a gate whose residual is 1 never closes, so
    its x is 1."""
    kinds = _check_kinds(kinds)
    out = []
    for c, kind, p in zip(gates, kinds, parameters, strict=True):
        r = residual_of(kind, p)
        span = 1.0 - r
        out.append(xp.where(span > 0, (c - r) / xp.where(span > 0, span, 1.0), 1.0))
    return tuple(out)


def route_factor(gates, parameters, route_residuals, *, kinds, xp=jnp):
    """A route's factor through the gates: Π_i (ρ_i + (1 − ρ_i)·x_i), with ρ_i the route's own
    residual at gate i (ions: the gate's r, which gives conductance(); a large tracer: 0)."""
    out = 1.0
    for x, rho in zip(open_fractions(gates, parameters, kinds=kinds, xp=xp), route_residuals,
                      strict=True):  # fmt: skip
        out = out * (rho + (1.0 - rho) * x)
    return out


def domain_valid(gates, voltage, parameters, availability, dt_s=0.0, *, kinds, xp=jnp):
    """The junction's domain, per gate: threshold_relaxation's own, and for boltzmann_eyring λ > 0,
    A ≥ 0 with every exponent within MAX_EXPONENT on the voltage domain, δ and r in [0, 1], and c
    in [r, 1]; the voltage, availability and interval as cells.junction.junction_voltage_relaxation@1's."""
    kinds = _check_kinds(kinds)
    ok = (
        xp.isfinite(voltage)
        & (xp.abs(voltage) <= MAX_ABS_VOLTAGE_V)
        & xp.isfinite(availability)
        & (availability >= 0)
        & (availability <= 1)
        & xp.isfinite(dt_s)
        & (dt_s >= 0)
    )
    for c, kind, p in zip(gates, kinds, parameters, strict=True):
        if kind == "threshold_relaxation":
            ok = ok & relaxation.domain_valid(c, voltage, p, availability, dt_s, xp=xp)
            continue
        lam, slope, midpoint, split, residual = p
        finite = (
            xp.isfinite(lam)
            & xp.isfinite(slope)
            & xp.isfinite(midpoint)
            & xp.isfinite(split)
            & xp.isfinite(residual)
            & xp.isfinite(c)
        )
        bound = slope * (MAX_ABS_VOLTAGE_V + xp.abs(midpoint))
        ok = (
            ok
            & finite
            & (lam > 0)
            & (slope >= 0)
            & (bound <= MAX_EXPONENT)
            & (split >= 0)
            & (split <= 1)
            & (residual >= 0)
            & (residual <= 1)
            & (c >= residual)
            & (c <= 1)
        )
    return ok


# The law's declaration (CORE_SEAMS §8.2): inert, registered through @3's model table (FR-30's
# integration, D262). Development only: @3's parser refuses it without development: true.
# Its call form is the two-gate one, not JunctionLaw's one-gate comment, so no generic caller may
# treat it as one gate: kinetics, rhs and domain_valid take kinds= and one parameter tuple per
# gate; kinetics returns a tuple of Rates and rhs a tuple of dc/dt, and domain_valid one boolean.
LAW = JunctionLaw(
    LAW_ID,
    True,
    kinetics,
    rhs,
    domain_valid,
    MAX_ABS_VOLTAGE_V,
    host="cells.model.resolved_pump_tissue@3",
    gate_count=GATE_COUNT,
    conductance=conductance,
    provenance="cited",
    source=Citation(
        "two voltage gates in series, each a two-state gate with a residual conductance "
        "(docs/JUNCTION_TWO_RELAXATION_DESIGN.md, option (A)), for the two relaxation times one "
        "decay of homotypic Cx43 junctions shows (G. Sahu and A. K. Bera, 2013, PLoS ONE 8(3): "
        "e60506, doi:10.1371/journal.pone.0060506, read for the design note)",
        "docs/JUNCTION_TWO_RELAXATION_DESIGN.md §2.1 and §4",
        "no numbers taken: the law is a form, and its gates' parameters are a definition's values; "
        "the article is CC BY",
        (
            "threshold_relaxation's rates are cells.junction.junction_voltage_relaxation@1's own, cited there",
            "the boltzmann_eyring gate is one Boltzmann in |V|, symmetric in polarity, where the "
            "paper fits each polarity",
            "A is a fitted slope, with no gating charge derived from it",
            "development only until a voltage series qualifies it (D262)",
        ),
        (
            CitedWork(
                ("Giriraj Sahu", "Amal Kanti Bera"),
                2013,
                "Contribution of Intracellular Calcium and pH in Ischemic Uncoupling of Cardiac "
                "Gap Junction Channels Formed of Connexins 43, 40, and 45: A Critical Function "
                "of C-Terminal Domain",
                doi="10.1371/journal.pone.0060506",
            ),
        ),
    ),
)
