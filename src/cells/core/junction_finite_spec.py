"""Explicit kinetic-pump / physical-time junction composition, finite_extracellular@3."""

from cells.core.bioelectric_spec import positive
from cells.core.finite_extracellular_spec import assembly_to_dict, parse_assembly
from cells.core.kinetic_finite_spec import parse_membrane, pump_to_dict
from cells.core.multispecies_spec import aligned, identifier
from cells.core.specs import (
    JUNCTION_FINITE_EXTRACELLULAR_ID,
    ConfigError,
    JunctionFiniteExtracellularSpec,
    KineticFiniteMembraneSpec,
    RateJunctionSpec,
    _fields,
    _number,
)
from cells.core.voltage_gated_spec import fraction
from cells.processes.junction_gate import LAW_ID, MAX_ABS_VOLTAGE_V

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


def junction_to_dict(p, ids):
    if type(p.permeability_m_per_s) is not tuple or len(p.permeability_m_per_s) != len(ids):
        raise ConfigError("Junction permeability requires a complete immutable species tuple")
    return {
        "id": p.id,
        "from_cell": p.from_cell,
        "to_cell": p.to_cell,
        "area_m2": p.area_m2,
        "permeability_m_per_s": dict(zip(ids, p.permeability_m_per_s, strict=True)),
        "gate": {k: getattr(p, k) for k in sorted(GATE_FIELDS)},
    }


def to_dict(spec):
    return assembly_to_dict(
        spec,
        JUNCTION_FINITE_EXTRACELLULAR_ID,
        KineticFiniteMembraneSpec,
        pump_to_dict,
        junction_type=RateJunctionSpec,
        serialize_junction=junction_to_dict,
    )


def parse(data):
    from cells.models.junction_finite_extracellular import check_definition

    return parse_assembly(
        data,
        JunctionFiniteExtracellularSpec,
        parse_membrane,
        check_definition,
        bind_junction=parse_junction,
        backends=("cpu", "gpu"),
    )
