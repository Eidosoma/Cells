"""cells.operator.size_threshold_fission@1: size-triggered fission with an exact random partition.

The trigger (GARD_DESIGN §1.5, 1). An assembly splits when a join brings its size N to the
declared `size`. With single-molecule events the boundary is exact: there is no overshoot, and
nothing is trimmed (the engine refuses, never repairs). A daughter is never larger than its
parent, but a binomial partition can give one daughter every molecule, so a daughter can be born
with N = `size`; it splits at once, at its birth, before any event (unless it is at the run's
fission limit). Its read of N is `current`, a read of the exchange law's own counts within the
family, so no cross-operator gap arises.

The split, a declared random partition of the parent's N molecules into two daughters:
- `exact_fraction` (fraction f): floor(f N) molecules, a uniformly random subset of the N, go to
  the first daughter (the multivariate hypergeometric split: f = 1/2 is T2-02's exact half);
- `binomial` (probability p): each molecule goes to the first daughter independently with
  probability p.
The second daughter is the parent less the first, so no molecule is made or lost.

Its draws, from the partition stream of the parent (streams.py; keyed by the parent's carrier
key, counter 0): one uniform u_k for each of `molecule_capacity` molecule places. The molecules
are listed by type in declared order: places 0 .. n_0 - 1 hold type 0, the next n_1 type 1, and
so on; places at or past N are empty and ignored. exact_fraction ranks the occupied places by
u_k (ties, of probability about N^2 2**-53, by place) and gives the first floor(f N) of that
order to the first daughter; binomial gives it every occupied place with u_k < p.

Bookings and records: the split's change in -ln pi is booked as signed work (ledger.py), and the
fission table records each fission (records.py; GARD_DESIGN §5.2).
"""

from dataclasses import dataclass

from cells.definitions.specs import ConfigError, bounded_integer, finite_number, require_fields
from cells.models.assembly_lineages import FISSION, MODEL_ID
from cells.models.assembly_lineages.lineage_operators import LineageOperator
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import operators as operator_registry

RULES = {"exact_fraction": "fraction", "binomial": "probability"}
MAX_SIZE = 2**20


@dataclass(frozen=True)
class Partition:
    rule: str
    value: float  # The fraction f, or the probability p.


@dataclass(frozen=True)
class Fission:
    operator: str
    size: int
    partition: Partition


CONTRACT = {  # The operator's statements in words, as a run record states them.
    "trigger": "a join that brings the size N to `size` (exact: single-molecule events); a "
    "daughter born with N = `size` (a binomial partition can give one daughter every molecule) "
    "splits at once, at its birth, before any event (the horizon first: a daughter at the "
    "fission limit is not split)",
    "places": "M = execution.molecule_capacity molecule places, by type in declared order: places "
    "0 .. n_0 - 1 hold type 0, the next n_1 type 1, and so on; places N .. M - 1 are empty",
    "draw": "M uniforms u_0 .. u_(M-1), the partition stream's draw at counter 0, keyed by the "
    "parent's carrier key (one per place; only the occupied places' are read)",
    "exact_fraction": "take = floor(f * N) in float64; rank the occupied places by u_k ascending, "
    "ties by place; the first `take` places go to the first daughter",
    "binomial": "an occupied place k goes to the first daughter when u_k < p",
    "second_daughter": "the parent less the first daughter",
}
OPERATOR = operator_registry.BUILTIN.register(
    LineageOperator(
        FISSION,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Plastic Heredity preprint v5.0, Appendix F, contract T2-02 (Zenodo "
            "10.5281/zenodo.22143269)",
            "exact-size multivariate-hypergeometric split, floor(N/2) to the first daughter",
            "CC BY 4.0",
            (),
        ),
        test="tests/unit/test_assembly_lineages_fission.py::"
        "test_a_daughter_born_at_the_fission_size_splits_at_once",
        reads="the assembly's size N (current) and its counts",
        writes="the slot's composition: the followed daughter replaces the parent (continuation)",
        energy_role="work: the split's change in -k_BT ln pi, from an unmodelled agent (signed)",
        rules=dict(RULES),
        stream="partition: one uniform per molecule place, from the parent's carrier key",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()  # As a run record states it (records.py).


def parse(raw):
    require_fields(raw, {"operator", "size", "partition"}, "fission")
    if raw["operator"] != FISSION:
        raise ConfigError(f"fission: the operator is {FISSION}")
    size = bounded_integer(raw["size"], "fission: size", minimum=2, maximum=MAX_SIZE)
    partition = raw["partition"]
    if not isinstance(partition, dict) or partition.get("rule") not in RULES:
        raise ConfigError(f"fission: the partition rule is one of {sorted(RULES)}")
    key = RULES[partition["rule"]]
    require_fields(partition, {"rule", key}, f"fission: the {partition['rule']} partition")
    value = finite_number(partition[key], f"fission: {key}", positive=True)
    if not value < 1:
        raise ConfigError(f"fission: {key} lies strictly between 0 and 1")
    return Fission(raw["operator"], size, Partition(partition["rule"], value))


def to_dict(fission):
    rule = fission.partition.rule
    return {
        "operator": fission.operator,
        "size": fission.size,
        "partition": {"rule": rule, RULES[rule]: fission.partition.value},
    }


def split(parent, size, places, rule, value):
    """The first daughter's counts [C] (int64), on the device.

    parent: [C] int64 counts; size: their sum N; places: [M] open-interval uniforms, one per
    molecule place (M >= N); rule: static; value: the fraction or the probability."""
    import jax.numpy as jnp

    capacity, count = parent.shape[0], places.shape[0]
    index = jnp.arange(count, dtype=jnp.int64)
    ends = jnp.cumsum(parent)  # Integer sums: exact in any order.
    kind = jnp.minimum(jnp.searchsorted(ends, index, side="right"), capacity - 1)
    occupied = index < size
    if rule == "exact_fraction":
        take = jnp.floor(value * size.astype(jnp.float64)).astype(jnp.int64)
        order = jnp.argsort(jnp.where(occupied, places, 2.0), stable=True)
        rank = jnp.zeros(count, dtype=jnp.int64).at[order].set(index)
        chosen = occupied & (rank < take)
    elif rule == "binomial":
        chosen = occupied & (places < value)
    else:
        raise ValueError(f"Unknown partition rule {rule!r}")
    return jnp.zeros(capacity, dtype=jnp.int64).at[kind].add(chosen.astype(jnp.int64))
