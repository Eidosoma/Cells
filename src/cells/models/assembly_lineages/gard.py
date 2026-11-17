"""GARD's catalysis: one declared law set, used only for comparison (D192, D197).

GARD (Segre, Ben-Eli and Lancet 2000, PNAS 97:4112) lets the members of an assembly catalyse
each type's joining and leaving through a fixed non-negative matrix beta. This module declares the
two forms of that factor as rate-factor laws of the assembly-lineage family. They exist for the
comparison with the Plastic Heredity preprint's reconstructed GARD (D138, D192). Cells' own
origin-of-life engine derives its laws from physical chemistry instead (D197).

The two forms. For a state n with N = sum_i n_i and (beta n)_i = sum_j beta_ij n_j:

- cells.gard_catalysis_single_event@1 (form "single-event"): the preprint's single-event kernel,
  the event split of the original rate law (the preprint's Appendix F; Eq. 4 of Segre et al.
  2000). Both rates of type i carry b_i(n) = 1 + (beta n)_i / N, at the current state, so a
  join from n carries b_i(n) and its reverse leave from n + e_i carries b_i(n + e_i): the
  arriving molecule catalyses its own leaving through the kept diagonal, and every weight is
  diluted from 1/N to 1/(N + 1). Declared driven: in a closed two-type world this kernel
  generically fails Kolmogorov's cycle criterion (a rank-one catalysis matrix is the exception:
  that chain is reversible, with a shifted equilibrium), so it is not microscopically
  reversible there. The finding concerns this single-event kernel in a closed world. The
  original authors' kernel is not established either way: their papers state the rate law but
  no event rates. The preprint's vector-Poisson contracts were not tested, and its driven runs
  (a held reservoir, growth and fission) are not affected, since detailed balance is not
  expected there. Its unsourced cycle affinity is reported, never booked as passive heat.
- cells.gard_catalysis_pair_consistent@1 (form "pair-consistent", passive; the default of this
  set): a transfer of type i between n and n + e_i sees the same catalysts, those of n, the
  assembly without the moving molecule: g_i = 1 + (beta n)_i / N. A join from n carries g_i(n);
  a leave from m carries g_i(m - e_i) = 1 + ((beta m)_i - beta_ii) / (N_m - 1), and 1 when the
  leaving molecule is the last (no catalyst remains). The leaving molecule does not catalyse its
  own leave, so the factor cancels from every transfer pair and the chain keeps the exchange
  law's beta-independent equilibrium exactly. It equals the single-event form to O(1/N), except
  for strongly self-catalytic types.

Data, per world (law_data.catalysis_matrix): beta, N_G x N_G, finite and non-negative (so every
factor is at least 1: the domain refuses a factor <= 0, which only a matrix with inhibitory
entries could reach). It is the world's, shared by both forms, and bound as layout.

State: x = beta n, kept incrementally, one column per event (beta[:, i] added or subtracted:
elementwise, so the same on every device), and recomputed exactly by a serial fold over the
types whenever the composition is replaced (the founder; each daughter after a fission).

Source: Segre, Ben-Eli and Lancet (2000); the Plastic Heredity preprint, v5.0, Appendix F
(Zenodo 10.5281/zenodo.22143269, CC BY 4.0). Numbers cited under D186. Independent check of the
reversibility finding: GARD_DESIGN §2.5.
"""

from typing import NamedTuple

import numpy as np

from cells.core.specs import ConfigError
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_SINGLE_EVENT,
    MODEL_ID,
    folds,
)
from cells.models.assembly_lineages.factors import RateFactorLaw
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import laws as law_registry

LAW_SET = "gard"
FIELD = "catalysis_matrix"
DEFAULT = GARD_PAIR_CONSISTENT
PROBE_MU, PROBE_SIGMA = -4.0, 4.0  # The preprint's lognormal regime, for the check's probe.

SCOPE = (
    "GARD comparison law set (D192, D197): for comparison with the Plastic Heredity preprint's "
    "reconstructed GARD only; Cells' own origin-of-life laws are derived from physical chemistry"
)


class Matrix(NamedTuple):
    matrix: object  # [C, C] float64, zero-padded.
    diagonal: object  # [C] float64.


def parse_data(raw, count):
    if not isinstance(raw, dict) or set(raw) != {FIELD}:
        raise ConfigError(f"GARD catalysis reads exactly one law_data field, {FIELD}")
    rows = raw[FIELD]
    if not isinstance(rows, list) or len(rows) != count:
        raise ConfigError(f"{FIELD} has one row per type ({count})")
    values = []
    for r, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != count:
            raise ConfigError(f"{FIELD} row {r} has one entry per type ({count})")
        for c, value in enumerate(row):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(f"{FIELD}[{r}][{c}] must be a number")
            value = float(value)
            if not np.isfinite(value) or value < 0:
                raise ConfigError(
                    f"{FIELD}[{r}][{c}] = {value!r}: catalysis is finite and non-negative "
                    "(a factor <= 0 is outside the law's domain)"
                )
        values.append(tuple(float(v) for v in row))
    return {FIELD: tuple(values)}


def data_to_dict(data):
    return {FIELD: [list(row) for row in data[FIELD]]}


def layout(data, capacity):
    rows = np.asarray(data[FIELD], dtype=np.float64)
    count = rows.shape[0]
    matrix = np.zeros((capacity, capacity), dtype=np.float64)
    matrix[:count, :count] = rows
    return Matrix(matrix, np.ascontiguousarray(np.diagonal(matrix)))


def probe(rng, count):
    """Generic data for the check: one lognormal matrix in the preprint's regime."""
    z = rng.standard_normal((count, count))
    return {FIELD: np.exp(PROBE_MU + PROBE_SIGMA * z).tolist()}


def state(counts, data, xp, unroll=folds.UNROLL):
    """x = beta n, exactly: for each i, a serial fold over j of beta_ij n_j in declared order."""
    terms = data.matrix * counts[None, :]  # [i, j]; folded over j.
    return folds.total(terms.T, xp, unroll)


def update(x, data, i, sign, xp):
    """x after one molecule of type i joins (sign +1) or leaves (-1): one column of beta."""
    return x + sign * data.matrix[:, i]


def _per_member(x, size, xp):
    """1 + x / N, and 1 for the empty assembly (no members, no catalysis)."""
    safe = xp.where(size > 0, size, 1.0)
    return xp.where(size > 0, 1.0 + x / safe, 1.0)


def factors_single_event(counts, size, x, data, xp):
    """b_i(n) = 1 + (beta n)_i / N for both directions, at the current state."""
    b = _per_member(x, size, xp)
    return b, b


def factors_pair_consistent(counts, size, x, data, xp):
    """Join: g_i(n) = 1 + (beta n)_i / N. Leave from m: g_i(m - e_i), 1 for the last molecule."""
    join = _per_member(x, size, xp)
    rest = size - 1.0
    safe = xp.where(rest > 0, rest, 1.0)
    leave = xp.where((rest > 0) & (counts > 0), 1.0 + (x - data.diagonal) / safe, 1.0)
    return join, leave


STATE_FORMULAS = {
    "state": "x = beta n, x_i = sum_j beta_ij n_j: a serial left fold over j in declared order, "
    "computed exactly for the founder and for each followed daughter",
    "update": "after an event of type i with sign s (+1 join, -1 leave): x <- x + s * beta[:, i]",
    "replay": "a replay that recomputes x at every event agrees with the incremental x to "
    "rounding: event sequences exactly (but for a threshold coincidence at rounding), times to a "
    "relative 1e-15",
}

SOURCE = (
    "Segre, Ben-Eli and Lancet (2000), PNAS 97:4112; Plastic Heredity preprint v5.0, Appendix F "
    "(Zenodo 10.5281/zenodo.22143269)"
)
PLACE = "Appendix F, 'Common state, kinetics and environment': b_i = 1 + (beta x)_i / N"
LICENCE = "CC BY 4.0 (the preprint); numbers cited under D186"
TESTS = {
    GARD_SINGLE_EVENT: "tests/unit/test_assembly_lineages_kernel.py::"
    "test_a_row_for_column_update_is_caught",
    GARD_PAIR_CONSISTENT: "tests/unit/test_assembly_lineages_balance.py::"
    "test_the_check_admits_pair_consistent_as_passive_and_refuses_single_event_as_passive",
}

SINGLE_EVENT = RateFactorLaw(
    GARD_SINGLE_EVENT,
    host=MODEL_ID,
    provenance="cited",
    source=Citation(SOURCE, PLACE, LICENCE, ()),
    test=TESTS[GARD_SINGLE_EVENT],
    form="single-event",
    energy_role="driven",
    law_set=LAW_SET,
    data=(FIELD,),
    parse_data=parse_data,
    data_to_dict=data_to_dict,
    layout=layout,
    state=state,
    update=update,
    factors=factors_single_event,
    probe=probe,
    comparison_only=True,
    formulas={
        "g_join_i(n)": "1 + x_i / N, at the current state; 1 when N = 0",
        "g_leave_i(n)": "1 + x_i / N, at the current state (the leaving molecule counted); 1 "
        "when N = 0",
        "last_molecule": "the last molecule's leave (N = 1, n_i = 1) carries 1 + beta_ii: the "
        "molecule catalyses its own leave",
        **STATE_FORMULAS,
    },
    note=(
        SCOPE + ". The preprint's single-event form, kept for the reference comparison and "
        "declared driven: in a closed two-type world it generically fails Kolmogorov's cycle "
        "criterion (a rank-one matrix is the exception). The original authors' kernel is not "
        "established either way, and the preprint's driven runs are not affected."
    ),
)

PAIR_CONSISTENT = RateFactorLaw(
    GARD_PAIR_CONSISTENT,
    host=MODEL_ID,
    provenance="cited",
    source=Citation(
        SOURCE,
        PLACE,
        LICENCE,
        (
            "the factor of a transfer is evaluated on the assembly without the moving molecule, "
            "so a transfer and its reverse see the same catalysts (GARD_DESIGN §1.4, 2)",
        ),
    ),
    test=TESTS[GARD_PAIR_CONSISTENT],
    form="pair-consistent",
    energy_role="passive",
    law_set=LAW_SET,
    data=(FIELD,),
    parse_data=parse_data,
    data_to_dict=data_to_dict,
    layout=layout,
    state=state,
    update=update,
    factors=factors_pair_consistent,
    probe=probe,
    comparison_only=True,
    formulas={
        "g_join_i(n)": "1 + x_i / N, on n (the state without the moving molecule); 1 when N = 0",
        "g_leave_i(n)": "1 + (x_i - beta_ii) / (N - 1), on n - e_i (the state without the "
        "leaving molecule), when N >= 2 and n_i >= 1; 1 otherwise (the last molecule leaves "
        "uncatalysed; a type with n_i = 0 has no leave)",
        "last_molecule": "the last molecule's leave (N = 1, n_i = 1) carries 1: no catalyst "
        "remains (this form only; the single-event form's carries 1 + beta_ii)",
        **STATE_FORMULAS,
    },
    note=(
        SCOPE + ". The pair-consistent form, passive: the leaving molecule does not catalyse "
        "its own leave, so the chain keeps the beta-independent equilibrium exactly."
    ),
)

# Registered from this home, which the static model table lists, through the public call.
LAWS = tuple(law_registry.BUILTIN.register(law) for law in (SINGLE_EVENT, PAIR_CONSISTENT))
