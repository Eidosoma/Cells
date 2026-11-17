"""The declared type family of an assembly world (GARD_DESIGN §1.3).

A world declares its molecule types as one indexed family, `prefix` then a zero-padded index
(t000 ... t099 for 100 types), never as hand-written entries. Each type is label-only: no
catalogue entry and no valence (the abstract assemblies of option A carry no charge).

One standard transfer potential per type, declared here and nowhere else (the species registry's
one-authority rule, D174/D176). It is declared in its exponential form, the transfer constant
K_i = exp(-dmu_i/RT), where dmu_i is the standard chemical potential of type i in the assembly
less that in the held phase. The exchange law reads it: its join constant is K_i times its leave
constant, so the two constants can never disagree with the potential. (The exponential form keeps
published constants exact: K = 100 with a leave constant of 1e-4 gives a join constant of exactly
0.01 in float64.)

The number of types is the family's own static axis: a capacity bucket (128, 256, 512, ...) that
pads the arrays, so one compiled program serves every world whose family fits it. Padding types
have no supply, no leave constant and no molecules, so every rate of theirs is zero.
"""

import math
import re
from dataclasses import dataclass

from cells.core.specs import ConfigError, bounded_integer, finite_number, require_fields

PREFIX = re.compile(r"[a-z][a-z0-9_]*")
MAX_TYPES = 2**16
BUCKETS = (128, 256, 512, 1024, 2048, 4096)
IDENTITY = "label_only"


@dataclass(frozen=True)
class TypeFamily:
    prefix: str
    count: int
    transfer_constant: tuple[float, ...]  # K_i, one per type.

    @property
    def ids(self):
        width = max(3, len(str(self.count - 1)))
        return tuple(f"{self.prefix}{i:0{width}d}" for i in range(self.count))

    @property
    def standard_transfer_mu_RT(self):
        """dmu_i/RT = -ln K_i, derived from the declared constants."""
        return tuple(-math.log(k) for k in self.transfer_constant)


def bucket(count):
    """The smallest capacity bucket that holds `count` types."""
    for size in BUCKETS:
        if count <= size:
            return size
    raise ConfigError(f"No capacity bucket holds {count} types (largest {BUCKETS[-1]})")


def per_type(value, count, name, *, positive=False):
    """A scalar (the same for every type) or a list of `count` finite numbers, as a tuple."""
    if isinstance(value, list):
        if len(value) != count:
            raise ConfigError(f"{name} lists {len(value)} values for {count} types")
        return tuple(
            finite_number(v, f"{name}[{i}]", positive=positive) for i, v in enumerate(value)
        )
    return (finite_number(value, name, positive=positive),) * count


def compact(values):
    """per_type's inverse for to_dict: a scalar when every type has the same value."""
    return values[0] if len(set(values)) == 1 else list(values)


def parse(raw):
    require_fields(raw, {"prefix", "count", "transfer_constant"}, "types")
    if not isinstance(raw["prefix"], str) or not PREFIX.fullmatch(raw["prefix"]):
        raise ConfigError("types: the prefix is a lowercase word, such as t")
    count = bounded_integer(raw["count"], "types: count", minimum=1, maximum=MAX_TYPES)
    constants = per_type(raw["transfer_constant"], count, "types: transfer_constant", positive=True)
    return TypeFamily(raw["prefix"], count, constants)


def to_dict(family):
    return {
        "prefix": family.prefix,
        "count": family.count,
        "transfer_constant": compact(family.transfer_constant),
    }
