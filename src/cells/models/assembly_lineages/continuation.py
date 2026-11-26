"""cells.operator.daughter_continuation@1: which daughter continues the lineage, and where the other goes.

At each fission (fission.py) one daughter takes the lineage's slot; the slot keeps its place and
changes its occupant (GARD_DESIGN §5.2, the replacement idiom), and the occupant's generation
grows by one. Declared (§1.5, 2):

- `daughter`: `first`, `second`, or `uniform` (either with probability 1/2, from the parent's
  continuation stream: the first when its one uniform is below 1/2);
- `empty`: the rule for an empty selected daughter, `extinct` (the lineage ends, extinct: the
  slot holds the empty assembly, which takes up nothing) or `other` (the other daughter, when it
  is not empty: T2-03's nonempty fallback);
- `sink`: where the unfollowed daughter's material goes, `discard` (a declared sink) or
  `reservoir` (back to the held phase). In a held phase the two are physically the same; the
  ledger says which, and books the material (discarded_total) and its -k_BT ln pi (the sink term,
  ledger.py) either way.

Carrier keys (int64, written at birth): the founder holds 0; each fission gives its two daughters
the lineage's next two keys, the first daughter the lower. A lineage's keys are therefore unique,
and an assembly's random streams follow from its key alone (streams.py).
"""

from dataclasses import dataclass

from cells.definitions.specs import ConfigError, require_fields
from cells.models.assembly_lineages import CONTINUATION, MODEL_ID
from cells.models.assembly_lineages.lineage_operators import LineageOperator
from cells.modules import Citation

# The registration call is the registry's own (the surface exports it in module stage 1).
from cells.registry import operators as operator_registry

DAUGHTERS = ("first", "second", "uniform")
EMPTY = ("extinct", "other")
SINKS = ("discard", "reservoir")


@dataclass(frozen=True)
class Continuation:
    operator: str
    daughter: str
    empty: str
    sink: str


CONTRACT = {  # The operator's statements in words, as a run record states them.
    "uniform": "the continuation stream's draw u at counter 0: u < 1/2 picks the first daughter, "
    "otherwise the second",
    "empty": "extinct: an empty pick is followed and the lineage ends; other: an empty pick moves "
    "to the other daughter when it holds a molecule",
    "carrier_keys": "the founder holds 0:0; each fission gives its first daughter the next key of "
    "its parent's counter and its second the one after; the followed daughter continues the "
    "counter and becomes the slot's occupant (keys.py)",
}
OPERATOR = operator_registry.BUILTIN.register(
    LineageOperator(
        CONTINUATION,
        host=MODEL_ID,
        provenance="cited",
        source=Citation(
            "Plastic Heredity preprint v5.0, Appendix F, contracts T2-02, T1-03 and T2-03 (Zenodo "
            "10.5281/zenodo.22143269)",
            "the continued daughter: first (T2-02), second (T1-03), either with probability 1/2 "
            "with a nonempty fallback (T2-03)",
            "CC BY 4.0",
            (),
        ),
        test="tests/unit/test_assembly_lineages_fission.py::test_continuation_rules",
        reads="the two daughters of a fission",
        writes="the slot's occupant, generation and carrier keys; the discarded material",
        energy_role="none of its own: the unfollowed daughter's -k_BT ln pi leaves to the sink",
        rules={"daughter": list(DAUGHTERS), "empty": list(EMPTY), "sink": list(SINKS)},
        stream="continuation: one uniform, from the parent's carrier key (rule uniform only)",
        contract=CONTRACT,
    )
)
DECLARATION = OPERATOR.record()  # As a run record states it (records.py).


def parse(raw):
    require_fields(raw, {"operator", "daughter", "empty", "sink"}, "continuation")
    if raw["operator"] != CONTINUATION:
        raise ConfigError(f"continuation: the operator is {CONTINUATION}")
    for key, allowed in (("daughter", DAUGHTERS), ("empty", EMPTY), ("sink", SINKS)):
        if raw[key] not in allowed:
            raise ConfigError(f"continuation: {key} is one of {', '.join(allowed)}")
    return Continuation(raw["operator"], raw["daughter"], raw["empty"], raw["sink"])


def to_dict(continuation):
    return {
        "operator": continuation.operator,
        "daughter": continuation.daughter,
        "empty": continuation.empty,
        "sink": continuation.sink,
    }


def choose(daughter, empty, uniform, sizes):
    """The followed daughter, 0 (first) or 1 (second), on the device.

    daughter, empty: static rules; uniform: the continuation stream's draw; sizes: the two
    daughters' sizes. Under `other`, an empty pick moves to the other daughter if it has any
    molecule; under `extinct` it stays (the lineage ends)."""
    import jax.numpy as jnp

    if daughter == "first":
        pick = jnp.int64(0)
    elif daughter == "second":
        pick = jnp.int64(1)
    else:
        pick = jnp.where(uniform < 0.5, 0, 1).astype(jnp.int64)
    if empty == "other":
        mine = jnp.where(pick == 0, sizes[0], sizes[1])
        theirs = jnp.where(pick == 0, sizes[1], sizes[0])
        pick = jnp.where((mine == 0) & (theirs > 0), 1 - pick, pick)
    return pick
