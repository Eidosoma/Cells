"""The store worlds' cycle laws at the code-blind references' states
(docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, section 14, rows 8 and 9, whose references in
test_cycle_kind.py are independent of the forms but not code-blind): the ATP-driven transporter
at valences 2, 1, -1 and 0 and n = 1 to 4, the sodium-calcium exchanger, and the two
electroneutral symports, at the 153 states of
validation/calcium_store/reference_spec/inputs.json. The references
(validation/calcium_store/references) were written from that folder alone, by someone who had
read nothing of the engine.

Each state is a population of one world's, evaluated in NumPy by the kind's own hooks, the only
one switched on, at the state's concentrations, volumes, voltage, temperature and availability.
Every output the specification asks for is compared: x and the fuel's part of it, S, J and its
forward part, the heat, the work and the current, the slopes of J against the voltage and against
each amount, the moves at both ends, the domain, J at the doubles nearest the reversal and 1
microvolt to each side, and a symport's J at other voltages. Each is within TOLERANCE of the size
of what it is a difference of: a rate, a slope and a move of the one-way rates, so a slope that
is a small difference of large terms (the references' README names five) is judged by those; a
heat and a work of the one-way rates times their free energy. Planted inputs: the voltage's sign
turned, the two ends exchanged, the availability left out, K larger by 1e-9. Every output is
missed by one of them.

Seconds: 8 on the shared CPUs, in NumPy on one CPU, so tier 1.
"""

import math

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.schedule import control_values
from cells.kinds import transporter
from cells.registry.models import get_model
from validation.calcium_store import worlds
from validation.calcium_store.references import api

SPECIFICATION = worlds.specification()
F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
FMOL_CHARGE = 1e-15 * F
TOLERANCE = 2e-13  # Of the one-way rates, as test_cycle_kind.py's JUDGED_TOL.
NKCC = "cells.cycle.na_k_2anion_symport_reversible_tanh@1"
SALT = "cells.cycle.electroneutral_symport_reversible_tanh@1"
VALENCE = dict(Na=1, K=1, M=-1, Ca=2, S=-2, Y=0, ATP=0, Pi=0)
PUMPED = {2: "Ca", 1: "K", -1: "M", 0: "Y"}  # The species a pump state moves, by its valence.
SALTS = dict(salt_1_1=("K", "M"), salt_1_2=("Ca", "M"), salt_2_1=("Na", "S"))
FAMILIES = ("pump", "exchanger", "symport")


def states(family):
    return SPECIFICATION[f"{family}_states"]


def adp(state):
    """Each distinct standard potential of ADP is its own species (a world's species has one)."""
    distinct = sorted({s["mu_adp_RT"] for s in states("pump")})
    return f"ADP_{distinct.index(state['mu_adp_RT'])}"


def entry(family, i, state, k_factor=1.0):
    """A state's population, its N the cell."""
    given = dict(
        id=f"{family}_{i}",
        host="patch",
        orientation={"N": "a"},
        capacity_fmol_s=state["capacity_fmol_per_s"],
        held_rows=[],
    )
    if family == "pump":
        roles = dict(role=PUMPED[state["z"]], ATP="ATP", ADP=adp(state), Pi="Pi")
        parameters = dict(
            stoichiometry=state["n"],
            km_role_mM=k_factor * state["K_role_mM"],
            km_atp_mM=state["K_ATP_mM"],
        )
        held = [list(row) for row in worlds.HELD_FUEL]
        return given | dict(law=worlds.PUMP, roles=roles, parameters=parameters, held_rows=held)
    if family == "exchanger":
        parameters = dict(km_na_mM=k_factor * state["K_Na_mM"], km_ca_mM=state["K_Ca_mM"])
        roles = dict(Na="Na", Ca="Ca")
        return given | dict(law=worlds.EXCHANGER, roles=roles, parameters=parameters)
    if state["law"] == "na_k_2anion":
        return given | dict(law=NKCC, roles=dict(Na="Na", K="K", anion="M"), parameters={})
    (_, _, n_cation), (_, _, n_anion) = SPECIFICATION["symport_laws"][state["law"]]
    roles = dict(zip(("cation", "anion"), SALTS[state["law"]], strict=True))
    parameters = dict(n_cation=n_cation, n_anion=n_anion)
    return given | dict(law=SALT, roles=roles, parameters=parameters)


def kernel_world(family, k_factor=1.0, temperature=310.0):
    """One cell and one finite outside node, a population for each of the family's states on the
    patch between them."""
    mu = {adp(s): s["mu_adp_RT"] for s in states("pump")} | dict(ATP=0.0, Pi=0.0)
    valence = VALENCE | dict.fromkeys(mu, 0)
    species = [
        dict(id=s, valence=z) | (dict(standard_mu_RT=mu[s]) if s in mu else {})
        for s, z in valence.items()
    ]

    def node(name, **over):
        amounts, charge = dict.fromkeys(valence, 1.0), -float(sum(valence.values()))
        return dict(
            id=name,
            volume_pL=1.0,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=charge,
            initial_charge_C=0.0,
            **over,
        )

    patch = dict(
        id="patch",
        inside="cell",
        outside="outside",
        area_m2=1e-10,
        capacitance_F=1e-12,
        permeability_m_per_s=dict.fromkeys(valence, 0.0),
        law="cells.route.constant_field@1",
        pump=None,
        calcium_pump=None,
    )
    model = dict(
        id="cells.model.resolved_pump_tissue@3",
        temperature_K=temperature,
        standard_concentration_mM=1.0,
        species=species,
        cells=[node("cell")],
        extracellular=[node("outside", reservoir=False, boundary_potential_V=0.0)],
        membranes=[patch],
        junctions=[],
        faces=[],
        channels=[],
        closure=dict(
            law="cells.field_closure.resolved_capacitor_components_current_continuity@1", gauge_reference="outside"
        ),
        transporters=[entry(family, i, s, k_factor) for i, s in enumerate(states(family))],
    )
    experiment = dict(
        membrane_controls=[dict(membrane_id="patch", schedule=[dict(time=0.0, availability=1.0)])],
        junction_controls=[],
        pump_controls=[],
        calcium_pump_controls=[],
        channel_controls=[],
        end_time=1e-4,
        observation_times=[0.0],
    )
    execution = dict(
        dt=1e-4,
        capacity=1,
        extracellular_capacity=1,
        membrane_capacity=1,
        edge_capacity=0,
        face_capacity=0,
        channel_capacity=0,
        backend="cpu",
        jit=True,
        precision="float64",
        solver=worlds.IMEX,
        field_solver=worlds.VERSION_2,
        max_steps=8,
        max_trace_bytes=2**28,
        material_balance_atol_fmol=dict.fromkeys(valence, 1e-10),
    )
    return dict(schema_version=1, model=model, experiment=experiment, execution=execution)


class Kernels:
    """A family's kernel_world bound once, and its populations evaluated one state at a time."""

    def __init__(self, family, **over):
        self.family = family
        spec = parse_spec(kernel_world(family, **over))
        impl = get_model(spec.model)
        self.state, self.p = impl.initial_values(spec)
        controls = control_values(spec, [0.0])
        self.control = impl.Control(*(np.asarray(v[0]) for v in controls))
        self.species, self.valence = list(spec.model.species_ids), list(spec.model.valence)

    def at(self, i, *, volts=None, plant=None):
        """What the kind's hooks take at a state (its voltage `volts` where given), under a planted
        input. The state's population is the world's i-th, and the only one switched on."""
        s = states(self.family)[i]
        conc = concentrations(self.family, s)
        if plant == "ends":
            conc = {species: ends[::-1] for species, ends in conc.items()}
        volts = s["V_NP_V"] if volts is None else volts
        volumes = np.array([s["volume_N_pL"]]), np.array([s["volume_P_pL"]])
        amounts = [np.full((len(self.species), 1), v[0]) for v in volumes]
        for species, ends in conc.items():
            for amount, c, v in zip(amounts, ends, volumes, strict=True):
                amount[self.species.index(species), 0] = c * v[0]
        p = self.p._replace(
            temperature=np.asarray(s["temperature_K"]),
            volume=volumes[0],
            extracellular_volume=volumes[1],
            amount_reference=np.zeros_like(self.p.amount_reference),
            extracellular_amount_reference=np.zeros_like(self.p.extracellular_amount_reference),
        )
        state = self.state._replace(
            amount_increment=amounts[0], extracellular_amount_increment=amounts[1]
        )
        availability = np.zeros_like(self.control.cycle_availability)
        availability[i] = 1.0 if plant == "availability" else s["availability"]
        control = self.control._replace(cycle_availability=availability)
        return state, np.array([-volts if plant == "sign" else volts, 0.0]), control, p


def concentrations(family, s):
    """{species: (mM at N, mM at P)} of a state."""
    if family == "pump":
        fuel = {"ATP": s["atp_mM"], adp(s): s["adp_mM"], "Pi": s["pi_mM"]}
        return {PUMPED[s["z"]]: (s["c_N_mM"], s["c_P_mM"])} | {k: (c, 1.0) for k, c in fuel.items()}
    if family == "exchanger":
        return {ion: (s[f"{ion}_N_mM"], s[f"{ion}_P_mM"]) for ion in ("Na", "Ca")}
    if s["law"] == "na_k_2anion":
        species = dict(Na="Na", K="K", anion="M")
    else:
        species = dict(zip(("cation", "anion"), SALTS[s["law"]], strict=True))
    return {species[role]: (s["c_N_mM"][role], s["c_P_mM"][role]) for role in species}


# ------------------------------------------------------------------ the outputs


def found(kernels, i, *, plant=None):
    """{output: (the engine's value, the size its error is judged by)} at a state, under the
    references' names: the rates that a step takes (the kind's rates hook), and x, S and the slopes
    of the evaluation behind them."""
    family, k, p = kernels.family, i, kernels.p
    s, at = states(family)[i], kernels.at(i, plant=plant)
    e, rates = transporter._evaluate(*at, xp=np), transporter._population_rates(*at, xp=np)
    rt_f = R * s["temperature_K"] / F
    rt = 1e-3 * R * s["temperature_K"]
    phi, terms = float(e.scale[0, k]), float(e.x_terms[0, k])
    charge = abs(float(p.cycle_charge_moved[0, k]))
    j, x, held_x = (float(value[0, k]) for value in (e.j, e.x, e.held_x))
    least = np.finfo(float).eps * terms  # What x is known to; a heat's and a work's other factor.
    out = dict(
        x=(e.x[0, k], terms / 100),  # The sum of x's terms, each rounded once or twice.
        J_fmol_per_s=(rates.derivatives["cycle_count"][0, k], phi),
        heat_rate_pJ_per_s=(
            rates.derivatives["cycle_dissipated_energy_pJ"][k],
            rt * (phi * (abs(x) + least) + abs(j) * terms),
        ),
        in_domain=(bool(e.valid[k]), None),
    )
    if family != "symport":
        valence = dict(zip(kernels.species, kernels.valence, strict=True))
        crossing = zip(kernels.species, rates.membrane_flux[:, 0], strict=True)
        current = FMOL_CHARGE * sum(valence[species] * flux for species, flux in crossing)
        size = math.exp(float(e.log_s[0, k]))
        out |= dict(
            S=(size, size),
            current_N_to_P_A=(current, FMOL_CHARGE * charge * phi),
            dJ_dV_NP_fmol_per_s_per_V=(e.d_j_d_psi[0, k] / rt_f, charge * phi / rt_f),
        )
    else:
        out["one_way_rates_sum_fmol_per_s"] = (phi, phi)
    if family == "pump":
        work = rates.derivatives["cycle_metabolic_work_pJ"][k]
        out |= dict(
            x_fuel=(e.held_x[0, k], terms / 100),
            J_plus_fmol_per_s=(e.j_plus[0, k], float(e.j_plus[0, k])),
            work_rate_pJ_per_s=(work, rt * (phi * (abs(held_x) + least) + abs(j) * terms)),
        )
    nodes = dict(N=rates.cell[:, 0], P=rates.outside[:, 0])  # What a step adds to each node's rows.
    for r in range(p.cycle_row_present.shape[0]):
        if not p.cycle_row_present[r, k] or p.cycle_row_held[r, k]:
            continue
        row, end = int(p.cycle_row_species[r, k]), "N" if p.cycle_row_at_n[r, k] else "P"
        amount = float(e.c[r, k]) * s[f"volume_{end}_pL"]
        nu = abs(float(p.cycle_nu[0, r, k]))
        slope = (float(e.d_j_d_ln_c[0, r, k]) / amount, (nu + 1) * phi / amount)
        move, species = (nodes[end][row], nu * phi), kernels.species[row]
        if family == "pump":
            out |= {f"dJ_dn_{end}_per_s": slope, f"move_{end}_fmol_per_s": move}
        elif family == "exchanger":
            out |= {f"dJ_dn_{species}_{end}_per_s": slope, f"move_{species}_{end}": move}
        else:
            role = next(name for name, sp in roles(s).items() if sp == species)
            out[f"dJ_dn_{end}_per_s {role}"] = slope
            out[f"moves_{end}_fmol_per_s {role}"] = move
    return out


def roles(s):
    """{role: species} of a symport state."""
    if s["law"] == "na_k_2anion":
        return dict(Na="Na", K="K", anion="M")
    return dict(zip(("cation", "anion"), SALTS[s["law"]], strict=True))


EXCHANGED = dict(Na_N=3, Na_P=-3, Ca_N=-1, Ca_P=1)  # A forward exchange's counts (SPEC 2.5).
REVERSALS = dict(pump="near_V_stall", exchanger="near_V_rev", symport="with_V_NP_changed")
# Outputs that restate another one at the exact real, where J is 0 (the doubles' J are compared).
AT_THE_REAL = ("V_stall_V", "J_at_V_stall", "V_rev_V", "J_at_V_rev")


def misses(kernels, *, plant=None):
    """{(state's tag, output)} of the engine's values that are not the reference's."""
    family, out = kernels.family, set()
    given = getattr(api, f"{family}_states")()
    assert [g["tag"] for g in given] == [s["tag"] for s in states(family)]
    for i, reference in enumerate(given):
        tag = f"{reference.get('law', family)}: {reference['tag']}"
        exact = {}
        for name, value in reference.items():
            if name in ("law", "tag", REVERSALS[family]) or name.startswith(AT_THE_REAL):
                continue
            if isinstance(value, dict):
                exact |= {f"{name} {role}": x for role, x in value.items()}
            else:
                exact[name] = value
        if family == "exchanger":
            j = exact["J_fmol_per_s"]
            exact |= {f"move_{row}": count * j for row, count in EXCHANGED.items()}
        values = found(kernels, i, plant=plant)
        assert set(values) == set(exact), set(values) ^ set(exact)  # Every output, and no other.
        for name, (value, size) in values.items():
            if size is None:
                same = value == exact[name]
            else:
                same = abs(value - exact[name]) <= TOLERANCE * size
            if not same:
                out.add((tag, name))
        nearby = reference[REVERSALS[family]] or dict(V_NP_V=(), J_fmol_per_s=())
        for volts, j in zip(nearby["V_NP_V"], nearby["J_fmol_per_s"], strict=True):
            e = transporter._evaluate(*kernels.at(i, volts=volts, plant=plant), xp=np)
            if not abs(float(e.j[0, i]) - j) <= TOLERANCE * float(e.scale[0, i]):
                out.add((tag, REVERSALS[family]))
    return out


@pytest.fixture(scope="module")
def kernels():
    return {family: Kernels(family) for family in FAMILIES}


@pytest.mark.parametrize("family", FAMILIES)
def test_each_law_meets_the_code_blind_states(kernels, family):
    assert misses(kernels[family]) == set()


@pytest.mark.parametrize("family", FAMILIES)
def test_every_output_is_missed_by_a_planted_input(kernels, family):
    """Each plant misses J, but the voltage's sign a symport's, whose rate reads no voltage; and
    each output the specification asks for is missed by some plant."""
    given = {
        plant: misses(kernels[family], plant=plant) for plant in ("sign", "ends", "availability")
    }
    if family != "symport":
        given["K"] = misses(Kernels(family, k_factor=1 + 1e-9))
    missed = {plant: {output for _, output in found_by} for plant, found_by in given.items()}
    seen = {plant for plant, outputs in missed.items() if "J_fmol_per_s" in outputs}
    assert seen == set(given) - ({"sign"} if family == "symport" else set())
    outputs = {name for i in range(len(states(family))) for name in found(kernels[family], i)}
    assert set().union(*missed.values()) == outputs | {REVERSALS[family]}


def test_the_layouts_temperature_is_one_number(kernels):
    """Kernels.at sets the layout's temperature in place of a parse at that temperature."""
    other = Kernels("pump", temperature=291.6).p
    layout = kernels["pump"].p._replace(temperature=other.temperature)
    for name, value in layout._asdict().items():
        assert np.array_equal(value, getattr(other, name)), name
