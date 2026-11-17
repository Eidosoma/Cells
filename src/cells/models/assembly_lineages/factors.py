"""The rate-factor interface (cells.assembly_rate_factor@1): an optional law that scales rates.

A rate-factor law multiplies the exchange law's join and leave rates of every type by factors it
computes from the assembly's state. It declares:

- `form`: a word naming its form, which a run records beside its ID (`law.form`);
- `energy_role`: "passive" when the factor of a transfer equals the factor of its reverse, so it
  leaves the exchange law's affinity unchanged; "driven" otherwise, with the unsourced cycle
  affinity reported. The kernel's check (balance.py) verifies the claim; a law declared passive
  that fails it is refused;
- `data`: the world's per-world data it reads (law_data), parsed on the host and bound as layout,
  never closed over, so one compiled program serves every value (P5);
- its kernels, in the xp style (NumPy on the host, jax.numpy on the device, the same arithmetic):
  - state(counts, data, xp): its incremental state computed exactly from the counts;
  - update(state, data, i, sign, xp): that state after one molecule of type i joins (+1) or
    leaves (-1);
  - factors(counts, size, state, data, xp): (join [C], leave [C]) at the current state;
- `probe(rng, count)`: generic data on which the check classifies the law (not a world's data).

Without a rate-factor law the kernel's rates are the exchange law's, and its programs hold no
factor code at all. Laws register here by ID, resolved when a definition is parsed.
"""

from dataclasses import dataclass
from typing import Callable

from cells.core.specs import ConfigError

ROLES = ("passive", "driven")


@dataclass(frozen=True)
class RateFactorLaw:
    law_id: str
    interface: str
    form: str
    energy_role: str
    law_set: str
    data: tuple[str, ...]
    # (raw law_data, type count) -> {field: value}, on the host; refuses with ConfigError.
    parse_data: Callable
    data_to_dict: Callable  # its inverse, for the world record.
    layout: Callable  # (parsed data, capacity) -> NamedTuple of float64 arrays, padded.
    state: Callable
    update: Callable
    factors: Callable
    probe: Callable  # (numpy Generator, count) -> raw law_data.
    provenance: dict
    comparison_only: bool
    note: str


def registered():
    """{law ID: declaration} of every registered rate-factor law."""
    from cells.models.assembly_lineages import gard

    return {law.law_id: law for law in gard.LAWS}


def resolve(law_id):
    laws = registered()
    if law_id not in laws:
        raise ConfigError(
            f"Unknown rate-factor law {law_id!r}; registered: {', '.join(sorted(laws))}"
        )
    law = laws[law_id]
    if law.energy_role not in ROLES:
        raise ConfigError(f"{law_id}: energy_role is one of {ROLES}")
    return law
