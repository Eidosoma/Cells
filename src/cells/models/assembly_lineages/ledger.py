"""The stochastic thermodynamic ledger of an assembly lineage (GARD_DESIGN §2.4).

"Heat never decreases" is a deterministic, per-element check; a single stochastic leave from a
supersaturated state legitimately goes uphill. For stochastic laws the check becomes three others:
local detailed balance at the kernel (balance.py), the event-heat ledger below, and its closure
against a state function at every saved row.

The state function. With theta_i = K_i rho_i (exchange.py), the exchange law's stationary
measure, unnormalized, gives each assembly the log weight (in k_BT, as every term here)

    Phi(n) = ln pi(n) = ln (N - 1)! + sum_i [ n_i ln theta_i - ln n_i! ]     (N >= 1)
    Phi(empty) = 0                                                         (by convention)

and its free energy is F(n) = -Phi(n) (k_BT). The empty assembly lies outside the measure:
nothing joins it.

The bookings, cumulative from the lineage's start, never restarting:

1. Event heat, per committed exchange event n -> n':  q = ln a(n -> n') - ln a(n' -> n),
   booked into exchange_heat_kT from the kernel's own rates (the forward rate it drew from and
   the reverse rate at the new state). It falls at single events: declared non-monotone.
   - The last molecule's leave (n' empty) has no reverse event. Its heat is booked as the change
     in Phi with Phi(empty) = 0, that is q = -ln theta_i, and the lineage ends extinct.
2. Fission work, per fission of a parent P into daughters D1 and D2:
   W = F(D1) + F(D2) - F(P) = Phi(P) - Phi(D1) - Phi(D2),
   booked into fission_work_kT: work done on the assembly by the splitting agent, an unmodelled
   prescribed operator (as the partition operator books its work); signed.
3. The sink, per fission: the unfollowed daughter D' leaves with its free energy,
   S = F(D') = -Phi(D'), booked into discarded_free_energy_kT (the declared sink, or the held
   phase; continuation.py).

The closure, at every saved row t, with n_0 the founder:

    exchange_heat_kT(t) = [Phi(n_t) - Phi(n_0)] + fission_work_kT(t) - discarded_free_energy_kT(t)

Proof. Within a growth the heat telescopes: q = Phi(n') - Phi(n) for every event of a passive
law (its rate ratio is the measure's ratio). At a fission the slot's state jumps from P to the
followed daughter D, and Phi(D) - Phi(P) = -[Phi(P) - Phi(D) - Phi(D')] + Phi(D') = -W - S; so
Phi(n_t) - Phi(n_0) = heat - work + sink over the lineage, which is the identity.

- For a passive law (the exchange law alone, or with a passive rate factor) the residual
  heat - [Phi(n_t) - Phi(n_0) + W - S], saved as ledger_residual_kT, is zero to rounding at every
  row, and the runner refuses a run where it is not.
- For a driven law (GARD's single-event form) the same bookings leave a residual: the unsourced
  cycle work, which is reported, never closed (GARD_DESIGN §2.4, 2).

Ensemble inequalities are not used as checks: the entropy-production rate is non-negative for any
positive rates, so it cannot fail (§2.4).
"""

import math

import numpy as np

from cells.models.assembly_lineages import folds

CONVENTIONS = {
    "unit": "k_BT",
    "state_function": "Phi(n) = ln (N-1)! + sum_i [n_i ln theta_i - ln n_i!], theta_i = K_i rho_i; "
    "Phi(empty) = 0; the free energy is -Phi",
    "event_heat": "q = ln a(n->n') - ln a(n'->n) per committed event, from the kernel's rates; "
    "the last molecule's leave books q = -ln theta_i (Phi(empty) = 0); declared non-monotone",
    "fission_work": "W = Phi(P) - Phi(D1) - Phi(D2): the split's change in -ln pi, done on the "
    "assembly by the splitting agent; signed",
    "sink": "S = -Phi(D'), the free energy the unfollowed daughter D' takes to the declared sink",
    "closure": "exchange_heat_kT = [Phi(n_t) - Phi(n_0)] + fission_work_kT - "
    "discarded_free_energy_kT at every saved row; the residual is ledger_residual_kT",
}
# Of the ledger's scale (closure_tolerance): rounding only. A lineage of 10^4 events with
# cumulative bookings near 10^4 k_BT can accumulate up to about 10^4 * 2^-53 * 10^4 = 1e-8 in the
# worst case, against a scale near 3e4; GARD's single-event residuals are about 1 k_BT a fission.
RTOL = 1e-10


def log_factorials(count):
    """ln k! for k = 0 .. count, from math.lgamma on the host (bound as layout, so every device
    reads the same values)."""
    return np.asarray([math.lgamma(k + 1.0) for k in range(count + 1)], dtype=np.float64)


def log_weight(counts, size, log_theta, log_factorial, xp):
    """Phi(n) for counts [C] (integers) and their size N; 0 for the empty assembly."""
    terms = counts.astype(np.float64) * log_theta - log_factorial[counts]
    head = log_factorial[xp.maximum(size - 1, 0)]
    return xp.where(size > 0, head + folds.total(terms, xp), 0.0)


def residual(heat, phi, phi_0, work, sink):
    """heat - [Phi(n_t) - Phi(n_0) + W - S], elementwise."""
    return heat - ((phi - phi_0) + work - sink)


def closure_tolerance(heat_magnitude, phi, phi_0, work_magnitude, sink_magnitude):
    """The rounding bound the closure is held to: RTOL times the ledger's scale (every booked
    magnitude and both state-function values), and never below RTOL."""
    scale = heat_magnitude + np.abs(phi) + abs(phi_0) + work_magnitude + sink_magnitude
    return RTOL * np.maximum(scale, 1.0)
