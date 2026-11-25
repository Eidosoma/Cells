"""The kinetic Na/K pump's declaration: its parse and its serialization, with maintained chemical
reservoirs as its metabolism.

The pump families (resolved_pump_tissue@1-@3), through surface_kinetic_spec and the surface_pump
schemas, and inner_laws import the two functions from here.
"""

from dataclasses import asdict

from cells.definitions.spec_values import _tuple, identifier, positive, signed_number
from cells.definitions.specs import (
    ConfigError,
    KineticPumpSpec,
    MaintainedMetabolismSpec,
    _fields,
    _number,
)
from cells.laws.pumps.kinetic_pump import LAW_ID

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
