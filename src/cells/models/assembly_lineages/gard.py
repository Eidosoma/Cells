"""GARD's catalysis: one declared law set, used only for comparison (D192, D197).

GARD (Segre, Ben-Eli and Lancet 2000, PNAS 97:4112) lets the members of an assembly catalyse
each type's joining and leaving through a fixed non-negative matrix beta. This module declares the
two forms of that factor as rate-factor laws of the assembly-lineage family. They exist for the
comparison with the Plastic Heredity preprint's reconstructed GARD (D138, D192). Cells' own
origin-of-life engine derives its laws from physical chemistry instead (D197).

The two forms. For a state n with N = sum_i n_i and (beta n)_i = sum_j beta_ij n_j:

- cells.rate_factor.gard_catalysis_single_event@1 (form "single-event"): the preprint's single-event kernel,
  the event split of the original rate law (the preprint's Appendix F; Eq. 4 of Segre et al.
  2000). Both rates of type i carry b_i(n) = 1 + (beta n)_i / N, at the current state, so a
  join from n carries b_i(n) and its reverse leave from n + e_i carries b_i(n + e_i): the
  arriving molecule catalyses its own leaving through the kept diagonal, and every weight is
  diluted from 1/N to 1/(N + 1). Declared driven: in a closed two-type world this kernel
  generically fails Kolmogorov's cycle criterion (the exception is a rank-one 1 + beta, one added
  to every entry, 1 + beta_ij = u_i v_j with positive factors: that chain is reversible, with a
  shifted equilibrium; a rank-one beta alone is not enough. GARD_DESIGN §2.5, corrected on 19
  November 2026 from the Lean proofs project's proof and its exact 81/80 square at beta_11 = 1),
  so it is not microscopically
  reversible there. The finding concerns this single-event kernel in a closed world. The
  original authors' kernel is not established either way: their papers state the rate law but
  no event rates. The preprint's vector-Poisson contracts were not tested, and its driven runs
  (a held reservoir, growth and fission) are not affected, since detailed balance is not
  expected there. Its unsourced cycle affinity is reported, never booked as passive heat.
- cells.rate_factor.gard_catalysis_pair_consistent@1 (form "pair-consistent", passive; the default of this
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

from cells.definitions.specs import ConfigError
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_PAIR_CONSISTENT_V2,
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


# cells.rate_factor.gard_catalysis_pair_consistent@2 (D244, D246): the pair-consistent form above, with its
# cache of beta n held exactly. @1 keeps its cached subtraction and its bits (D148): with
# beta_ii = 2^54 and one other catalyst, its leave factor 1 + ((beta n)_i - beta_ii) / (N - 1) loses
# the catalyst (the Lean proofs project's finding of 19 November 2026).
#
# The cache is an unevaluated pair (hi, lo) of float64 words, hi = fl(beta n) and lo = beta n - hi.
# - A join or leave adds +-beta[:, i] by two error-free two-sums (Knuth's TwoSum gives a rounded sum
#   and its exact error): the error of hi + b and the low word are added exactly, then renormalised.
# - The founder and each daughter refold it from the counts. Each entry is split on the host into
#   its top 33 bits and the rest (at most 20 bits), so every product with a count up to 2^20 (the
#   family's molecule capacity) is exact.
# - The leave forms (beta n)_i - beta_ii exactly and rounds it once.
# So the join from m and the leave from m + e_i both evaluate the correctly rounded
# sum_j beta_ij m_j: the factor cancels from every transfer pair bit for bit, and the cache equals a
# fresh fold bit for bit at every event (it is a function of n alone).
#
# The budget. Every value of row i is a multiple of 2^q_i, q_i the lowest set bit among the row's
# nonzero entries, and at most max_j beta_ij * S, S the fission size (no state the kernel keeps is
# larger). Below 2^(q_i + 106), each two-sum's error and the low word are at most 2^(q_i + 52), so
# their sum, at most 2^(q_i + 53), is exact; at 107 bits a unit can be lost. A world whose row needs
# more is refused at parse (domain_exact), never run inexactly; it runs under @1, or an experiment
# that draws matrices records the draw as refused and handles it as its protocol declares (D246).

BUDGET_BITS = 106
SPLIT_BITS = 33  # An entry's top bits; the rest has at most 53 - 33 = 20.
COUNT_BITS = 20  # So every count up to 2^20 multiplies either part exactly.
# The range (the Lean proofs project's findings of 22 November 2026). The budget bounds a row's span
# of bits, not where it sits:
# - at the top, every value the cache holds is at most M = max_j beta_ij * S, and a two-sum's
#   intermediates stay within 6M (s = a + b, then s - a and a - (s - bb)), as does the leave's
#   (beta n)_i - beta_ii. So M < 2^TOP_BITS keeps every word finite, with a factor 2.6 to spare,
#   where 2^1023 times a founder of 2 had made both words NaN and the run "stalled";
# - at the bottom, an entry with a bit below 2^LOW_BITS (a subnormal part) is refused. Every value
#   the cache holds is then a multiple of 2^LOW_BITS, products, sums, two-sum errors and low words
#   alike, so no word is subnormal and the compiled cache's flush of subnormals (XLA's, where NumPy
#   keeps them) changes nothing; the factors' quotients x/N can be subnormal only where they are
#   added to 1, which absorbs them on either side.
TOP_BITS = 1020
LOW_BITS = -1022


class ExactMatrix(NamedTuple):
    matrix: object  # [C, C] float64, zero-padded.
    diagonal: object  # [C] float64.
    low: object  # [C, C] float64: each entry below its top SPLIT_BITS bits (matrix - low, exact).


def split_low(matrix):
    """Each entry's bits below its top SPLIT_BITS bits, exactly (on the host)."""
    mantissa, exponent = np.frexp(matrix)
    high = np.ldexp(np.floor(np.ldexp(mantissa, SPLIT_BITS)), exponent - SPLIT_BITS)
    return matrix - high


def layout_exact(data, capacity):
    base = layout(data, capacity)
    return ExactMatrix(base.matrix, base.diagonal, split_low(base.matrix))


def two_sum(a, b):
    """(fl(a + b), its exact error): Knuth's TwoSum, six operations and no branch."""
    s = a + b
    bb = s - a
    return s, (a - (s - bb)) + (b - bb)


def _add_exact(hi, lo, b):
    """(hi, lo) + b: the error of hi + b and the low word add exactly within the budget."""
    s, e = two_sum(hi, b)
    return two_sum(s, e + lo)


def state_exact(counts, data, xp, unroll=folds.UNROLL):
    """(hi, lo) of beta n, [2, C]: for each i, a serial fold over j of (beta_ij - low_ij) n_j and
    low_ij n_j in declared order, each product exact, each added exactly."""
    count = counts.shape[0]
    high = data.matrix - data.low
    terms = xp.stack((high * counts[None, :], data.low * counts[None, :]))  # [part, i, j]
    terms = xp.transpose(terms, (2, 0, 1)).reshape(2 * count, count)  # [(j, part), i]
    zero = xp.zeros_like(counts)
    if xp is np:
        hi, lo = zero, zero
        for term in terms:
            hi, lo = _add_exact(hi, lo, term)
        return np.stack((hi, lo))
    import jax

    terms = jax.lax.optimization_barrier(terms)  # As folds.py: no product contracted into an add.
    (hi, lo), _ = jax.lax.scan(
        lambda carry, term: (_add_exact(carry[0], carry[1], term), None),
        (zero, zero),
        terms,
        unroll=unroll,
    )
    return xp.stack((hi, lo))


def update_exact(cache, data, i, sign, xp):
    """The cache after one molecule of type i joins (sign +1) or leaves (-1): +-beta[:, i]."""
    hi, lo = _add_exact(cache[0], cache[1], sign * data.matrix[:, i])
    return xp.stack((hi, lo))


def factors_exact(counts, size, cache, data, xp):
    """@1's pair-consistent factors from the exact cache: the join's x_i is hi_i = fl((beta n)_i);
    the leave's (beta n)_i - beta_ii is formed exactly and rounded once."""
    hi, lo = cache[0], cache[1]
    join = _per_member(hi, size, xp)
    s, e = two_sum(hi, -data.diagonal)
    rest = size - 1.0
    safe = xp.where(rest > 0, rest, 1.0)
    leave = xp.where((rest > 0) & (counts > 0), 1.0 + (s + (e + lo)) / safe, 1.0)
    return join, leave


def _lowest_bit(value):
    """The exponent of a positive finite double's lowest set bit."""
    mantissa, exponent = np.frexp(value)
    whole = int(np.ldexp(mantissa, 53))
    return int(exponent) - 53 + (whole & -whole).bit_length() - 1


def _top_bits(entries, size):
    """The t with max(entries) * size < 2^t, exactly: the bit just above the largest value the
    cache holds (0 for no entries)."""
    if not entries:
        return 0
    mantissa, exponent = np.frexp(max(entries))
    top = int(np.ldexp(mantissa, 53)) * int(size)  # max * size = top * 2^(exponent - 53), exactly.
    return top.bit_length() + int(exponent) - 53


def bits_needed(row, size):
    """The bits row i's sums can span: from the lowest set bit among its nonzero entries up to
    max_j beta_ij * size, the largest value the cache holds (0 for a row of zeros)."""
    entries = [float(v) for v in row if v > 0]
    if not entries:
        return 0
    return _top_bits(entries, size) - min(_lowest_bit(v) for v in entries)


def domain_exact(world):
    """@2's domain, at parse: every row's sums fit the budget at the world's fission size."""
    size = world.fission.size
    if size > 2**COUNT_BITS:
        raise ConfigError(
            f"{GARD_PAIR_CONSISTENT_V2}: the fission size {size} exceeds 2^{COUNT_BITS}, beyond "
            "which a count's products with the matrix are not exact"
        )
    for i, row in enumerate(world.data[FIELD]):
        entries = [float(v) for v in row if v > 0]
        lowest = min((_lowest_bit(v) for v in entries), default=0)
        if lowest < LOW_BITS:
            raise ConfigError(
                f"{GARD_PAIR_CONSISTENT_V2}: {FIELD} row {i} has an entry with a bit at "
                f"2^{lowest}, below the normal range (2^{LOW_BITS}): its cache would hold "
                "subnormal words, which the compiled kernel flushes to zero and the host keeps. "
                "Refused"
            )
        top = _top_bits(entries, size)
        if top > TOP_BITS:
            raise ConfigError(
                f"{GARD_PAIR_CONSISTENT_V2}: {FIELD} row {i}'s largest value, its largest entry "
                f"times the fission size {size}, is at least 2^{top - 1}: not below 2^{TOP_BITS}, "
                "within which the cache's two-sums keep every word finite. Refused (a word that "
                "overflows would make the rates NaN)"
            )
        bits = bits_needed(row, size)
        if bits > BUDGET_BITS:
            raise ConfigError(
                f"{GARD_PAIR_CONSISTENT_V2}: {FIELD} row {i} needs {bits} bits (its largest entry "
                f"times the fission size {size}, down to its entries' lowest set bit), beyond the "
                f"{BUDGET_BITS}-bit budget within which the cache holds beta n exactly. Refused "
                "(D246): run the world under @1, or, in an experiment that draws matrices, record "
                "the draw as refused and redraw or exclude it as its protocol declares"
            )


TEST_V2 = (
    "tests/unit/test_assembly_lineages_kernel.py::test_the_exact_cache_keeps_the_reverse_factor"
)

PAIR_CONSISTENT_EXACT = RateFactorLaw(
    GARD_PAIR_CONSISTENT_V2,
    host=MODEL_ID,
    provenance="cited",
    source=Citation(
        SOURCE,
        PLACE,
        LICENCE,
        (
            "the factor of a transfer is evaluated on the assembly without the moving molecule, "
            "so a transfer and its reverse see the same catalysts (GARD_DESIGN §1.4, 2)",
            "beta n is held exactly, as a pair of float64 words, within a declared budget (D246)",
        ),
    ),
    test=TEST_V2,
    form="pair-consistent",
    energy_role="passive",
    law_set=LAW_SET,
    data=(FIELD,),
    parse_data=parse_data,
    data_to_dict=data_to_dict,
    layout=layout_exact,
    state=state_exact,
    update=update_exact,
    factors=factors_exact,
    probe=probe,
    comparison_only=True,
    formulas={
        "g_join_i(n)": "1 + x_i / N, on n (the state without the moving molecule), x_i = hi_i, "
        "the correctly rounded (beta n)_i; 1 when N = 0",
        "g_leave_i(n)": "1 + fl((beta n)_i - beta_ii) / (N - 1), on n - e_i, the difference formed "
        "exactly from (hi, lo) and rounded once, when N >= 2 and n_i >= 1; 1 otherwise (the last "
        "molecule leaves uncatalysed; a type with n_i = 0 has no leave)",
        "last_molecule": "the last molecule's leave (N = 1, n_i = 1) carries 1: no catalyst "
        "remains",
        "state": "(hi, lo) with hi + lo = beta n exactly and hi = fl(beta n): a serial fold over j "
        "in declared order of (beta_ij - low_ij) n_j and low_ij n_j, low_ij being beta_ij below "
        "its top 33 bits (so each product is exact for n_j <= 2^20), each added by two error-free "
        "two-sums; computed for the founder and for each followed daughter",
        "update": "after an event of type i with sign s (+1 join, -1 leave): (hi, lo) <- (hi, lo) "
        "+ s * beta[:, i], by two error-free two-sums, exactly",
        "domain": "every row i: max_j beta_ij * S < 2^(q_i + 106), S the fission size and q_i the "
        "lowest set bit among the row's nonzero entries; a world beyond it is refused at parse",
        "replay": "a replay that recomputes beta n in rationals and rounds once agrees bit for "
        "bit: the cache equals a fresh fold at every event",
    },
    note=(
        SCOPE + ". The pair-consistent form, passive, with its cache of beta n held exactly "
        "within a declared budget, so the factor cancels from every transfer pair bit for bit; a "
        "world beyond the budget is refused at parse. @1 keeps its cached subtraction and its "
        "bits (D148)."
    ),
    domain=domain_exact,
)

# Appended to the set's registrations, after @1's, from the same home.
LAWS = (*LAWS, law_registry.BUILTIN.register(PAIR_CONSISTENT_EXACT))
