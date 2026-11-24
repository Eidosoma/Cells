"""FR-51's engine values for the judge (validation/fr51/judge.py, `--engine
validation.fr51.engine:engine`), read the registration's way (fr51-channel-block-v1 §2).

engine(case_id, voltages_V) returns {name: array over the voltages}:
- I_free and I_blocked (A, outward-positive);
- u;
- slope_part [mode, voltage], each mode's theta (1 - theta);
- T_V (S);
- T_co and T_ci (fmol/s per mM).

**Each case's world** is built from the registered spec's cases.json, and nothing else:
- one cell (1 pL) on a held bath (1 pL). The species are Na, K, Cl (valence -1) and a fixed anion
  P. The case's ion sits at its declared c_i and c_o; the other rows hold fixed values its
  population never reads;
- one patch of area 1e-9 m^2, with no passive permeability and no pump, carrying the case's
  population: its gate-free law, P = 1e-8 m/s, r = 1, its abundance, open fraction 1 and
  availability 1;
- T = 310 K;
- the block, where the case names one, as the engine declares it. cases.json's blocks carry neither
  the law ID (open_channel_block_weighted_modes@1) nor a blocker ID ("blocker"), so both are added;
- C2's units: the composite resolved_pump_composite@1, with membrane_entity_state@1 declaring the
  population at its reference density. Its declared abundance a0 = N0/(A rho_ref) is 1, the 1000
  units. 2000 units are those plus a unit increment of 1000 in the state, read through the
  abundance view a0 A0/A + dN/(A rho_ref).

**Where each value comes from:**
- I_free is the unblocked twin's clamped current: the same world without the block, its
  population's own.
- I_blocked is the world's own clamped current.
- u, the slope parts and T_V, T_c,o and T_c,i come from clamped_channel_flux(block=True): the
  stability rules' own terms (surface_pump_v3.channel_block_terms) at the same inputs.

Every value is the compiled clamped program (jax.jit of the model's clamped_channel_flux, mapped
over the voltages), one compile per world; host() gives the same on NumPy, for the tests. A case
without a block has no terms: u is 1 and the terms are NaN, which no criterion reads.
"""

import copy
import json
import math
from decimal import Decimal
from functools import cache, partial

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws.channels import open_channel_block as block_law
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.registry.models import get_model
from validation.fr51 import judge
from validation.tissue import surface_pump_v3_fixtures as fx

SPECIES = (("Na", 1), ("K", 1), ("Cl", -1), ("P", -1))
# The rows a case's population does not read, fixed; P is a fixed anion, and each node's declared
# fixed charge absorbs the remainder.
INSIDE_mM = {"Na": 10.0, "K": 140.0, "Cl": 20.0, "P": 10.0}
OUTSIDE_mM = {"Na": 145.0, "K": 5.4, "Cl": 120.0, "P": 10.0}
CAPACITANCE_F_PER_M2 = 0.01
REST_V = -0.07  # The cell's declared initial voltage; no clamped value reads it.
BLOCKER_ID = "blocker"


def spec_of():
    return json.loads(judge.SPEC.read_text())


def _decimal(value):
    return float(Decimal(str(value)))


def _block_declaration(block):
    """cases.json's block as the engine's declaration (its numbers as binary64)."""
    blocker = block["blocker"]
    modes = []
    for mode in block["modes"]:
        entry = {"weight": _decimal(mode["weight"]), "k0_mM": _decimal(mode["k0_mM"])}
        for key in ("electrical_distance", "effective_valence"):
            if key in mode:
                entry[key] = _decimal(mode[key])
        modes.append(entry)
    return {
        "law": block_law.LAW_ID,
        "blocker": {
            "id": BLOCKER_ID,
            "valence": int(blocker["valence"]),
            "side": blocker["side"],
            "concentration_mM": _decimal(blocker["concentration_mM"]),
        },
        "reference": copy.deepcopy(block["reference"]),
        "modes": modes,
    }


def raw_world(case_id, *, blocked=True):
    """The case's raw definition: @3, or C2's composite with membrane state."""
    spec = spec_of()
    case = next(c for c in spec["cases"] if c["id"] == case_id)
    population = spec["populations"][case["population"]]
    ion = population["ion"]
    inside, outside = dict(INSIDE_mM), dict(OUTSIDE_mM)
    inside[ion], outside[ion] = _decimal(case["c_i_mM"]), _decimal(case["c_o_mM"])
    raw = fx.heredity_cells([(REST_V, 10.0, 140.0, 20.0)], dt=1e-5, end_time=1e-4, solver="rk4")
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    z = dict(SPECIES)
    m["temperature_K"] = _decimal(spec["constants"]["T_K"])
    m["species"] = [dict(id=s, valence=v) for s, v in SPECIES]
    area = _decimal(population["area_m2"])
    capacitance = CAPACITANCE_F_PER_M2 * area
    cell_amounts = dict(inside)
    charge = capacitance * REST_V
    m["cells"][0].update(
        volume_pL=1.0,
        initial_amount_fmol=cell_amounts,
        fixed_charge_equivalent_fmol=charge / CHARGE_PER_FMOL
        - math.fsum(z[s] * cell_amounts[s] for s in cell_amounts),
        initial_charge_C=charge,
    )
    bath_amounts = dict(outside)
    m["extracellular"][0].update(
        volume_pL=1.0,
        initial_amount_fmol=bath_amounts,
        fixed_charge_equivalent_fmol=-math.fsum(z[s] * bath_amounts[s] for s in bath_amounts),
    )
    m["membranes"][0].update(
        area_m2=area,
        capacitance_F=capacitance,
        permeability_m_per_s=dict.fromkeys(z, 0.0),
        pump=None,
    )
    channel = dict(
        id="population",
        membrane_id=m["membranes"][0]["id"],
        kinetic_law=population["law"],
        max_permeability_m_per_s=_decimal(population["permeability_m_per_s"]),
        abundance=_decimal(case.get("abundance", population["abundance"])),
        initial_gate=[],
        permeant_ions=[dict(species_id=ion, relative_permeability=1.0)],
    )
    if blocked and case["block"] is not None:
        channel["block"] = _block_declaration(spec["blocks"][case["block"]])
    m["channels"] = [channel]
    e["pump_controls"] = []
    always = [dict(time=0.0, availability=1.0)]
    e["channel_controls"] = [dict(channel_id="population", schedule=always)]
    x["channel_capacity"] = 1
    x["material_balance_atol_fmol"] = dict.fromkeys(z, 1e-10)
    if "units" not in case:
        return raw
    composite = cs.frozen_definition(raw)
    composite["model"]["operators"] = [
        dict(
            law="membrane_entity_state@1",
            populations=[
                dict(
                    channel_id="population",
                    functional_unit="population",
                    catalogue=None,
                    reference_density_per_m2=_decimal(case["units"]["reference_density_per_m2"]),
                )
            ],
        )
    ]
    return composite


@cache
def world(case_id, blocked=True):
    """(model, state, control, layout, block) of the case's world, on the host. C2's state carries
    its units beyond the declared 1000 as the increment dN."""
    raw = raw_world(case_id, blocked=blocked)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    if "operators" in raw["model"]:  # C2's composite.
        control = model.CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
        case = next(c for c in spec_of()["cases"] if c["id"] == case_id)
        area = _decimal(spec_of()["populations"][case["population"]]["area_m2"])
        density = _decimal(case["units"]["reference_density_per_m2"])
        increment = np.asarray(state.population_abundance_increment).copy()
        increment[0] = _decimal(case["units"]["count"]) - round(area * density)
        state = state._replace(population_abundance_increment=increment)
        structure = model.inner.structure
    else:
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        structure = model.structure
    return model, state, control, p, blocked and bool(structure.blocked_channels)


@cache
def program(case_id, blocked=True):
    """The case's compiled clamped program, mapped over voltages (one compile per world)."""
    model, _, _, _, block = world(case_id, blocked)
    clamp = partial(model.clamped_channel_flux, xp=jnp, block=block)
    return jax.jit(jax.vmap(clamp, in_axes=(None, None, None, 0)))


def _clamped(case_id, blocked, voltages, compiled):
    model, state, control, p, block = world(case_id, blocked)
    if compiled:
        return program(case_id, blocked)(state, control, p, voltages)
    rows = [model.clamped_channel_flux(state, control, p, v, xp=np, block=block) for v in voltages]
    stack = partial(jax.tree.map, lambda *x: np.stack(x))
    return tuple(stack(*column) for column in zip(*rows, strict=True))


@cache
def _values(case_id, voltages, compiled=True):
    voltages = np.asarray(voltages, dtype=float)
    free = np.asarray(_clamped(case_id, False, voltages, compiled)[1])[:, 0]
    out = _clamped(case_id, True, voltages, compiled)
    blocked = np.asarray(out[1])[:, 0]
    n = voltages.size
    values = dict(I_free=free, I_blocked=blocked)
    if len(out) == 2:  # No block: no terms.
        nan = np.full(n, np.nan)
        return values | dict(u=np.ones(n), slope_part=np.zeros((0, n)), T_V=nan, T_co=nan,
                             T_ci=nan)  # fmt: skip
    terms = out[2]
    part = np.asarray(terms.block.theta) * np.asarray(terms.block.free)  # [V, mode, channel]
    return values | dict(
        u=np.asarray(terms.block.u)[:, 0],
        slope_part=np.moveaxis(part[:, :, 0], 0, 1),
        T_V=np.asarray(terms.voltage_term_S)[:, 0],
        T_co=np.asarray(terms.outside_term)[:, 0],
        T_ci=np.asarray(terms.inside_term)[:, 0],
    )


def host(case_id, voltages_V):
    """The same values on the host (NumPy), for the tests' host rows."""
    return _values(case_id, tuple(float(v) for v in np.asarray(voltages_V, dtype=float)), False)


def engine(case_id, voltages_V):
    """The judge's engine function: {name: array} over voltages_V (V)."""
    return _values(case_id, tuple(float(v) for v in np.asarray(voltages_V, dtype=float)))


RUN_SOLVER = "imex_ars222_face_electromigration@1"


def run_world(*, start_V=0.055, dt=1e-4, steps=300, na_m_per_s=3e-11, blocked=True):
    """RUN's world (fr51-channel-block-v1 §3): B1's block on a gate-free K population and an
    unblocked Na leak on the same patch of one cell on a held bath. The cell starts at start_V,
    inside the K population's negative-slope region (above -17.5 mV), and is observed every step
    under the IMEX solver. The Na leak is weak, so the K population's slope dominates the per-stage
    rate there and RUN's plant shows."""
    raw = raw_world("B1_two_modes_E1", blocked=blocked)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    cell, capacitance = m["cells"][0], m["membranes"][0]["capacitance_F"]
    charge = capacitance * start_V
    z = dict(SPECIES)
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - math.fsum(
        z[s] * a for s, a in cell["initial_amount_fmol"].items()
    )
    m["channels"].append(
        dict(
            id="na_leak",
            membrane_id=m["membranes"][0]["id"],
            kinetic_law="naleak_always_open@1",
            max_permeability_m_per_s=na_m_per_s,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
        )
    )
    e["channel_controls"].append(
        dict(channel_id="na_leak", schedule=[dict(time=0.0, availability=1.0)])
    )
    e["end_time"] = steps * dt
    e["observation_times"] = [i * dt for i in range(steps + 1)]
    x.update(dt=dt, solver=RUN_SOLVER, channel_capacity=2, max_steps=steps + 2)
    return raw
