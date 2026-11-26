"""The kinetic pump law's binding: declared pump parameters into layout arrays, and the
law's inputs from them.

Shared by the resolved tissues and the pump families (cells.model.resolved_pump_tissue@1-@3), through
surface_kinetic and surface_pump*.
"""

import numpy as np

from cells.laws.pumps import kinetic_pump as pump


def declared_parameters(p):
    m = p.metabolism
    return pump.Parameters(
        p.capacity_fmol_per_s,
        m.atp_mM,
        m.adp_mM,
        m.pi_mM,
        p.km_na_mM,
        p.km_k_mM,
        p.km_atp_mM,
        m.delta_g0_J_per_mol,
    )


def bind_pumps(spec, values):
    """Bind numeric pump roles/parameters into the composing geometry layout."""
    nm = spec.execution.membrane_capacity
    values.update(
        pump_present=np.zeros(nm, dtype=bool),
        pump_sodium_species=np.zeros(nm, dtype=np.int64),
        pump_potassium_species=np.zeros(nm, dtype=np.int64),
    )
    for name in ("atp_mM", "adp_mM", "pi_mM", "km_na_mM", "km_k_mM", "km_atp_mM", "delta_g0_J_mol"):
        neutral = 0.0 if name == "delta_g0_J_mol" else 1000.0 if name == "pi_mM" else 1.0
        values["pump_" + name] = np.full(nm, neutral)
    for i, membrane in enumerate(spec.model.membranes):
        p = membrane.pump
        if p is None:
            continue
        params = declared_parameters(p)
        values["pump_present"][i] = True
        values["pump_sodium_species"][i], values["pump_potassium_species"][i] = (
            spec.model.species_ids.index(s) for s in p.roles
        )
        values["stoichiometry"][:, i] = p.stoichiometry
        values["pump_capacity"][i] = p.capacity_fmol_per_s
        values["pump_drive"][i] = pump.chemical_drive(params, spec.model.temperature_K, xp=np)
        for name, value in zip(params._fields[1:], params[1:], strict=True):
            values["pump_" + name][i] = value


def pump_parameters(layout):
    return pump.Parameters(
        layout.pump_capacity,
        *(getattr(layout, "pump_" + name) for name in pump.Parameters._fields[1:]),
    )


def role_inputs(ci, co, mu, temperature, layout, *, xp):
    # Safe integer gathers precede masking. Only absent routes receive neutral
    # arguments; blocked but physically present pumps retain their real domain.
    slots = xp.arange(layout.pump_capacity.shape[-1])
    present = layout.pump_present
    return (
        xp.where(present, ci[..., layout.pump_sodium_species, slots], 1.0),
        xp.where(present, co[..., layout.pump_potassium_species, slots], 1.0),
        xp.where(present, mu[..., layout.pump_sodium_species, slots], 0.0),
        xp.where(present, mu[..., layout.pump_potassium_species, slots], 0.0),
        xp.where(present, temperature, 298.15),
    )
