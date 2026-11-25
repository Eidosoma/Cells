"""Explicit kinetic-pump / physical-time junction composition, finite_extracellular@3."""

from cells.definitions.rate_junction_spec import GATE_FIELDS, parse_junction
from cells.definitions.specs import (
    JUNCTION_FINITE_EXTRACELLULAR_ID,
    ConfigError,
    JunctionFiniteExtracellularSpec,
    KineticFiniteMembraneSpec,
    RateJunctionSpec,
)
from cells.legacy.core.finite_extracellular_spec import assembly_to_dict, parse_assembly
from cells.legacy.core.kinetic_finite_spec import parse_membrane, pump_to_dict


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
    from cells.legacy.models.junction_finite_extracellular import check_definition

    return parse_assembly(
        data,
        JunctionFiniteExtracellularSpec,
        parse_membrane,
        check_definition,
        bind_junction=parse_junction,
        backends=("cpu", "gpu"),
    )
