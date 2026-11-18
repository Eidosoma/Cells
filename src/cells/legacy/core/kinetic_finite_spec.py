"""Strict finite_extracellular@2 host contract; no synthetic-law conversion."""

from cells.definitions.kinetic_pump_spec import parse_pump, pump_to_dict
from cells.definitions.specs import (
    KINETIC_FINITE_EXTRACELLULAR_ID,
    KineticFiniteExtracellularSpec,
    KineticFiniteMembraneSpec,
)
from cells.legacy.core.bioelectric_spec import positive, signed_number
from cells.legacy.core.finite_extracellular_spec import assembly_to_dict, parse_assembly
from cells.legacy.core.multispecies_spec import aligned, identifier


def parse_membrane(p, cell, outside, ids, z, voltage):
    pump = parse_pump(p["pump"], ids, z)
    return KineticFiniteMembraneSpec(
        identifier(p["id"]),
        cell.id,
        outside.id,
        positive(p["area_m2"], "area"),
        positive(p["specific_capacitance_F_per_m2"], "specific capacitance"),
        aligned(p["passive"]["permeability_m_per_s"], ids, "permeability"),
        signed_number(voltage, "initial voltage"),
        pump,
    ), None if pump is None else pump.id


def to_dict(spec):
    return assembly_to_dict(
        spec, KINETIC_FINITE_EXTRACELLULAR_ID, KineticFiniteMembraneSpec, pump_to_dict
    )


def parse(data):
    from cells.legacy.models.kinetic_finite_extracellular import check_definition

    return parse_assembly(data, KineticFiniteExtracellularSpec, parse_membrane, check_definition)
