"""The gated rate junction's declaration: a junction between two cells with the junction-gate law.

The resolved tissues' schema (surface_kinetic_spec) parses its junctions with it.
"""

from cells.definitions.spec_values import aligned, fraction, identifier, positive
from cells.definitions.specs import ConfigError, RateJunctionSpec, _fields, _number
from cells.laws.junctions.junction_gate import LAW_ID, MAX_ABS_VOLTAGE_V

GATE_FIELDS = {"law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate"}


def parse_junction(raw, ids):
    _fields(
        raw, {"id", "from_cell", "to_cell", "area_m2", "permeability_m_per_s", "gate"}, "junction"
    )
    g = _fields(raw["gate"], GATE_FIELDS, "junction gate")
    threshold = _number(g["threshold_voltage_V"], "junction threshold")
    minimum, initial = (fraction(g[k], k) for k in ("minimum_open_fraction", "initial_gate"))
    if g["law"] != LAW_ID or threshold > MAX_ABS_VOLTAGE_V or initial < minimum:
        raise ConfigError(
            "Junction requires its named rate law, threshold in [0,0.120] V and gate in [minimum,1]"
        )
    return RateJunctionSpec(
        *(identifier(raw[k]) for k in ("id", "from_cell", "to_cell")),
        positive(raw["area_m2"], "junction area"),
        aligned(raw["permeability_m_per_s"], ids, "junction permeability"),
        LAW_ID,
        threshold,
        minimum,
        initial,
    )
