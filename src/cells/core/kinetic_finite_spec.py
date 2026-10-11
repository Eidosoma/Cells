"""Strict finite_extracellular@2 host contract; no synthetic-law conversion."""

from dataclasses import asdict

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.finite_extracellular_spec import assembly_to_dict, parse_assembly
from cells.core.multispecies_spec import aligned, identifier
from cells.core.physical_ionic_graph_spec import _tuple
from cells.core.specs import (
    KINETIC_FINITE_EXTRACELLULAR_ID,
    ConfigError,
    KineticFiniteExtracellularSpec,
    KineticFiniteMembraneSpec,
    KineticPumpSpec,
    MaintainedMetabolismSpec,
    _fields,
    _number,
)
from cells.processes.kinetic_pump import LAW_ID

METABOLISM_ID = "maintained_chemical_reservoirs@1"


def parse_pump(raw, ids, z):
    if raw is None:
        return None
    _fields(raw, set(KineticPumpSpec.__dataclass_fields__), "kinetic pump")
    _fields(raw["roles"], {"sodium", "potassium"}, "pump roles")
    roles = tuple(identifier(raw["roles"][r]) for r in ("sodium", "potassium"))
    if (
        raw["law"] != LAW_ID
        or roles[0] == roles[1]
        or any(s not in ids or z[ids.index(s)] != 1 for s in roles)
    ):
        raise ConfigError("Kinetic Na/K pump requires its named law and distinct +1 roles")
    nu = _fields(raw["stoichiometry"], set(roles), "pump stoichiometry")
    if any(type(nu[s]) is not int or nu[s] != v for s, v in zip(roles, (-3, 2), strict=True)):
        raise ConfigError("Na/K pump requires exactly -3/+2 coefficients")
    pools = _fields(
        raw["metabolism"], set(MaintainedMetabolismSpec.__dataclass_fields__), "metabolism"
    )
    if pools["kind"] != METABOLISM_ID:
        raise ConfigError("Require explicit maintained chemical reservoirs")
    return KineticPumpSpec(
        identifier(raw["id"]),
        LAW_ID,
        roles,
        tuple(nu.get(s, 0) for s in ids),
        _number(raw["capacity_fmol_per_s"], "pump capacity"),
        *(positive(raw[k], k) for k in ("km_na_mM", "km_k_mM", "km_atp_mM")),
        MaintainedMetabolismSpec(
            METABOLISM_ID,
            *(positive(pools[k], k) for k in ("atp_mM", "adp_mM", "pi_mM")),
            signed_number(pools["delta_g0_J_per_mol"], "standard hydrolysis free energy"),
        ),
    )


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


def pump_to_dict(membrane, ids):
    p = membrane.pump
    if p is None:
        return None
    if type(p) is not KineticPumpSpec or type(p.metabolism) is not MaintainedMetabolismSpec:
        raise ConfigError("Require explicit immutable kinetic pump and metabolism types")
    _tuple(p.roles, str, "pump roles", size=2)
    _tuple(p.stoichiometry, int, "pump stoichiometry", size=len(ids))
    if any(s not in ids for s in p.roles) or any(
        v for s, v in zip(ids, p.stoichiometry, strict=True) if s not in p.roles
    ):
        raise ConfigError("Pump stoichiometry must bind only its declared roles")
    return asdict(p) | {
        "roles": dict(zip(("sodium", "potassium"), p.roles, strict=True)),
        "stoichiometry": {s: p.stoichiometry[ids.index(s)] for s in p.roles},
    }


def to_dict(spec):
    return assembly_to_dict(
        spec, KINETIC_FINITE_EXTRACELLULAR_ID, KineticFiniteMembraneSpec, pump_to_dict
    )


def parse(data):
    from cells.models.kinetic_finite_extracellular import check_definition

    return parse_assembly(data, KineticFiniteExtracellularSpec, parse_membrane, check_definition)
