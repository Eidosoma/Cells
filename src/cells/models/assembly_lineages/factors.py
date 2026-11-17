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
- `probe(rng, count)`: generic data on which the check classifies the law (not a world's data);
- `formulas`: its factors, state and update in words and symbols, including the empty-assembly
  and last-molecule cases, which a run record states so that a replay needs no code.

Without a rate-factor law the kernel's rates are the exchange law's, and its programs hold no
factor code at all.

**Registration (seam F; CORE_SEAMS_DESIGN §8.1, §8.3, §8.4).** A rate-factor law is a declaration
on the law template (cells.modules.Law), of the interface `cells.rate_factor_law@1`, which the
family declares in its row of the static model table, and hosted by the family's model. It
registers on the law registry with the public call, `BUILTIN.register(law)`, from a home the
table lists (gard.py for GARD's two forms), which the registry imports by name when it loads. The
family finds its laws in the active registry by interface and host (registered()), never in a
module tuple, so a new rate-factor law is one module and one registration, with no edit here. Its
provenance is the template's: a tag (`cited`) with its Citation.
"""

from dataclasses import dataclass
from typing import Callable, ClassVar

from cells.core.specs import ConfigError
from cells.models.assembly_lineages import MODEL_ID, RATE_FACTOR_INTERFACE
from cells.modules import Law

# The active registry and the registration call are the registry's own (the surface exports them
# in module stage 1).
from cells.registry import laws as law_registry

ROLES = ("passive", "driven")


@dataclass(frozen=True)
class RateFactorLaw(Law):
    """The rate-factor interface (cells.rate_factor_law@1) on the law template."""

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
    comparison_only: bool
    note: str
    formulas: dict  # g_join_i, g_leave_i, the state and its update, as a replay needs them.

    interface: ClassVar[str] = RATE_FACTOR_INTERFACE

    def errors(self):
        out = super().errors()
        if law_registry.qualified(self.host) != law_registry.qualified(MODEL_ID):
            out.append(f"a rate-factor law is hosted by {MODEL_ID}")
        if self.energy_role not in ROLES:
            out.append(f"its energy_role is one of {', '.join(ROLES)}")
        if not (isinstance(self.data, tuple) and all(isinstance(d, str) for d in self.data)):
            out.append("its data names the law_data fields it reads")
        kernels = ("parse_data", "data_to_dict", "layout", "state", "update", "factors", "probe")
        out += [f"its {name} is callable" for name in kernels if not callable(getattr(self, name))]
        return out


def registered():
    """{law ID: declaration} of the rate-factor laws in the active law registry: this family's
    interface, hosted by its model, in canonical (sorted namespaced ID) order."""
    found = law_registry.active().laws(RATE_FACTOR_INTERFACE, MODEL_ID)
    return {law.law_id: law for law in found}


def resolve(law_id):
    laws = registered()
    if not isinstance(law_id, str) or law_id not in laws:
        raise ConfigError(
            f"Unknown rate-factor law {law_id!r}; registered: {', '.join(sorted(laws))}"
        )
    return laws[law_id]
