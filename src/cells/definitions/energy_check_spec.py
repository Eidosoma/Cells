"""execution.energy_check: the opt-in step-doubled energy check of a simulation definition.

FR-18's criterion X2, adopted under D224 as an opt-in check that registered and judged runs select
(docs/FR18_CRITERION_X_2026-11-18.md, its implementation section). Absent, the default, a
definition, its serialization and its run keep today's energy check. Present, cells.execution's
scalar runner and its windows check the energy ledger by step doubling instead
(cells.execution.energy_check). Every field is required:

  check                    "cells.execution.step_doubled_energy@1"
  integration_error_cap    the registration's own cap on the integration error relative to the
                           flows, checked at every row (sum |a| <= cap x F + floor); finite and
                           positive, with no default

The block is execution, not physics: the model, experiment and the other execution fields are
parsed by the model's own parser, unchanged, as for execution.projective. Refused:
- a solver other than ARS(2,2,2), the only scheme whose step doubling the registration tested;
- a model without the step and residual functions the check calls;
- a projective block beside it (the check runs on the fine engine only).
The evidence on FR-8's worlds stops at dt = 5 ms.
"""

from dataclasses import dataclass, replace

from cells.definitions.specs import ConfigError, _fields, _number
from cells.numerics.surface_imex import ARS222_ID, IMPLICIT_CONDUCTANCE_IDS

CHECK_ID = "cells.execution.step_doubled_energy@1"
# The schemes X2 admits: ARS(2,2,2), and N2's IDs on its tableau (D235), whose admission rests on
# RUNG1's I3, X2's qualification rows run under the ID.
SCHEMES = (ARS222_ID, *IMPLICIT_CONDUCTANCE_IDS)
FIELDS = ("check", "integration_error_cap")


@dataclass(frozen=True)
class EnergyCheck:
    """The selected check and its registration's integration-error cap."""

    check: str
    integration_error_cap: float


def parse(data, spec):
    """The energy_check block of an already parsed fine definition."""
    _fields(data, set(FIELDS), "execution.energy_check")
    if data["check"] != CHECK_ID:
        raise ConfigError(f"execution.energy_check requires check {CHECK_ID}")
    cap = _number(data["integration_error_cap"], "execution.energy_check.integration_error_cap",
                  positive=True)  # fmt: skip
    if spec.execution.solver not in SCHEMES:
        raise ConfigError(
            f"execution.energy_check {CHECK_ID} runs only with {ARS222_ID}, the scheme whose step "
            "doubling its registration tested, or N2's ARS(2,2,2) IDs (D235, RUNG1 I3)"
        )
    return EnergyCheck(CHECK_ID, cap)


def to_dict(value):
    return dict(check=value.check, integration_error_cap=value.integration_error_cap)


def parse_definition(data, parse_fine):
    """parse_spec for a definition whose execution block holds an energy_check block."""
    raw = dict(data)
    execution = dict(raw["execution"])
    block = execution.pop("energy_check")
    raw["execution"] = execution
    spec = parse_fine(raw)
    if getattr(spec, "projective", None) is not None:
        raise ConfigError(
            "execution.energy_check runs on the fine engine only, not beside execution.projective"
        )
    from cells.execution.energy_check import require_support
    from cells.registry.models import get_model

    value = parse(block, spec)
    require_support(get_model(spec.model))
    return replace(spec, energy_check=value)
