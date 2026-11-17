"""The ledger of version 2: event heat, reservoir work, and their closure against F (§3.3).

**The state function** is the one free energy, F(n) = Σ of its declared terms (k_BT): the ideal
term (ideal_mixing.py) and the excess terms (regular_mixing.py), evaluated exactly on the host at
every saved row from the counts alone. A held species has no term in F.

**The bookings,** cumulative from the run's start (kernel.py):
1. Event heat, per committed event n -> n': q = ln a(n -> n') − ln a(n' -> n), from the kernel's
   own rates (the rate drawn, and its reverse's at the new state). It falls at single events:
   declared non-monotone. For a passive pair q = −ΔF + w. The one event with no reverse (an
   extinction, `last_molecule: extinct`) books q = −ΔF + w with F_mem(empty) = 0.
2. Reservoir work, per event: w = −Σ_held ν μ_held for a forward (its negative for a reverse), the
   free energy the held species' reservoirs supply, μ_held = μ°_sol + ln(c/c0). Signed.
OL1 has no fission, so no fission work and no sink (OL3 adds them, with a payer).

**The closure,** at every saved row t, with n_0 the start:

    F(n_t) − F(n_0) = W(t) − Q(t)

so the residual Q(t) − [W(t) − (F(n_t) − F(n_0))] is zero to rounding. Proof: each event's
q = −ΔF + w, so the sums telescope. A run whose ledger does not close is refused (runner.py):
every law of this family is passive, so a residual beyond rounding is a fault, never reported
work.
"""

import numpy as np

from cells.registry import laws as law_registry

CONVENTIONS = {
    "unit": "k_BT",
    "state_function": "F(n) = the declared terms' sum (cells.free_energy_term@1): the ideal term "
    "and "
    "the excess terms, exactly from the counts; held species have no term",
    "event_heat": "q = ln a(n->n') - ln a(n'->n) per committed event, from the kernel's rates; "
    "an extinction (no reverse) books q = -dF + w with F_mem(empty) = 0; declared non-monotone",
    "reservoir_work": "w = -sum_held nu mu_held for a forward, its negative for a reverse; "
    "mu_held = mu°_sol + ln(c/c0); signed",
    "closure": "F(n_t) - F(n_0) = W - Q at every saved row; the residual is ledger_residual_kT",
    "fission": "none in OL1 (no fission work, no sink)",
}
# The closure's tolerance: rounding only, relative to the ledger's scale (as @1's ledger).
RTOL = 1e-10


def free_energy(counts, tables, terms, term_layouts):
    """F(n) on the host: every declared term's exact value, in declared order (k_BT).

    terms: the world's ((law ID, data), ...); term_layouts: the excess terms' layouts, in order."""
    registry = law_registry.active()
    ids = [law_id for law_id, _ in terms]
    total = registry.lookup(ids[0]).value(counts, tables, ())
    for law_id, term_layout in zip(ids[1:], term_layouts, strict=True):
        total = total + registry.lookup(law_id).value(counts, tables, term_layout)
    return float(total)


def residual(heat, work, f, f_0):
    """Q − [W − (F(n_t) − F(n_0))], elementwise."""
    return heat - (work - (f - f_0))


def closure_tolerance(heat_magnitude, work_magnitude, f, f_0):
    """RTOL times the ledger's scale (every booked magnitude and both state-function values)."""
    scale = heat_magnitude + work_magnitude + np.abs(f) + abs(f_0)
    return RTOL * np.maximum(scale, 1.0)
