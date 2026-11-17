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
    RATE_FACTOR_INTERFACE,
    folds,
)
from cells.models.assembly_lineages.factors import RateFactorLaw

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


PROVENANCE = {
    "kind": "cited",
    "source": "Segre, Ben-Eli and Lancet (2000), PNAS 97:4112; Plastic Heredity preprint v5.0, "
    "Appendix F (Zenodo 10.5281/zenodo.22143269)",
    "place": "Appendix F, 'Common state, kinetics and environment': b_i = 1 + (beta x)_i / N",
    "licence": "CC BY 4.0 (the preprint); numbers cited under D186",
    "departures": [],
}

SINGLE_EVENT = RateFactorLaw(
    law_id=GARD_SINGLE_EVENT,
    interface=RATE_FACTOR_INTERFACE,
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
    provenance=PROVENANCE,
    comparison_only=True,
    note=(
        SCOPE + ". The preprint's single-event form, kept for the reference comparison and "
        "declared driven: in a closed two-type world it generically fails Kolmogorov's cycle "
        "criterion (a rank-one matrix is the exception). The original authors' kernel is not "
        "established either way, and the preprint's driven runs are not affected."
    ),
)

PAIR_CONSISTENT = RateFactorLaw(
    law_id=GARD_PAIR_CONSISTENT,
    interface=RATE_FACTOR_INTERFACE,
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
    provenance={
        **PROVENANCE,
        "departures": [
            "the factor of a transfer is evaluated on the assembly without the moving molecule, "
            "so a transfer and its reverse see the same catalysts (GARD_DESIGN §1.4, 2)",
        ],
    },
    comparison_only=True,
    note=(
        SCOPE + ". The pair-consistent form, passive: the leaving molecule does not catalyse "
        "its own leave, so the chain keeps the beta-independent equilibrium exactly."
    ),
)

LAWS = (SINGLE_EVENT, PAIR_CONSISTENT)
