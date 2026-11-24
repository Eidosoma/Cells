"""cells.transporter@1 (B5) through the core's kind seams (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)).

The world: heredity cell D facing its held bath, with a neutral role Y and held fuel rows ATP, ADP
and Pi whose standard potentials the species registry declares (Δ_rG'° = -30.5 kJ/mol). The
neutral law pumps Y out of the cell into the bath. Through the runner, inside a registry scope:
- the move lands in the shared inventory, the held rows never change, and the maintenance's
  record follows the cycles;
- every accepted row passes the host checks, so all ten ledgers close with the kind's terms;
- the first steps' rate is the kernel's at the start (NumPy);
- a planted flipped role fails the material ledger.
"""

import copy
import dataclasses
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import proton_buffer, transporter
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.laws.pumps import atp_transporter as neutral
from cells.laws.pumps import proton_pump as proton
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures

END_S = 0.004
U = np.finfo(float).eps / 2  # The unit roundoff, for the bounds derived from it.
CAPACITY = 0.1  # fmol cycles/s
DRIVE0_J_MOL = -30500.0
ROWS = {"Y": (10.0, 10.0), "ATP": (3.0, 1e-6), "ADP": (0.3, 1e-6), "Pi": (3.0, 1e-6)}  # mM
FLOOR_FMOL = 1e-12


def population(**over):
    entry = dict(
        id="transporter_0",
        patch="membrane_0",
        law=transporter.NEUTRAL_LAW,
        capacity_fmol_s=CAPACITY,
        stoichiometry=1,
        km_role_mM=1.0,
        km_atp_mM=0.1,
        role="Y",
        fuel=dict(
            kind=transporter.HELD,
            node="cell_0",
            rows=["ATP", "ADP", "Pi"],
            ph_ref=None,
            ph_band=None,
        ),
    )
    entry.update(over)
    return entry


def held_world(*entries, potentials=True):
    """Heredity cell D with Y, ATP, ADP and Pi, the registry's potentials and the transporters."""
    raw = water_fixtures.heredity_cell("D", end_time=END_S)
    for row, (cell_mM, bath_mM) in ROWS.items():
        raw = add_inventory_species(
            raw,
            row,
            trace_mM=1e-6,
            diffusivity_m2_per_s=1e-10,
            floor_fmol=FLOOR_FMOL,
            concentrations_mM={"cell_0": cell_mM, "bath_0": bath_mM},
        )
    m = raw["model"]
    rt = R * m["temperature_K"]
    if potentials:
        m["standard_concentration_mM"] = 1000.0
        mu = dict(ATP=0.0, ADP=DRIVE0_J_MOL / rt, Pi=0.0)
        for entry in m["species"]:
            if entry["id"] in mu:
                entry["standard_mu_RT"] = mu[entry["id"]]
    m[transporter.MODEL_KEY] = list(entries or [population()])
    return raw


def scoped(*kinds):
    """A test-local registry holding `kinds` (the transporter by default)."""
    registry = kind_registry.KindRegistry()
    for kind in kinds or (transporter.TRANSPORTER,):
        registry.register(kind)
    return kind_registry.scope(registry)


def test_the_built_in_registers_on_builtin_and_an_undeclared_one_changes_nothing():
    assert kind_registry.active().lookup(transporter.KIND_ID) is transporter.TRANSPORTER
    spec = parse_spec(water_fixtures.heredity_cell("D", end_time=END_S))  # BUILTIN is active.
    model = get_model(spec.model)
    assert model.structure.kinds == ()
    assert model.STATE_TYPE is surface_pump_v3.STATE_TYPE


def test_parse_round_trips_with_a_value_free_structure_entry():
    with scoped():
        spec = parse_spec(held_world())
        ((kind_id, declaration),) = spec.model.kinds
        assert kind_id == transporter.KIND_ID
        assert transporter.to_dict(declaration) == [population()]
        bare = population(law=neutral.LAW_ID)  # A bare law ID resolves to cells.
        assert dict(parse_spec(held_world(bare)).model.kinds)[kind_id] == declaration
        assert transporter.structure_entry(declaration) == (
            (transporter.NEUTRAL_LAW,),
            (transporter.HELD,),
        )
        _, p = surface_pump_v3.initial_values(spec, structure=surface_pump_v3.structure(spec.model))
    assert p.transporter_neutral.shape == (1,) and p.transporter_proton.shape == (0,)  # Static.
    assert p.transporter_drive0_J_mol[0] == pytest.approx(DRIVE0_J_MOL, rel=1e-12, abs=0)


def fuel(**over):
    return dict(population()["fuel"], **over)


@pytest.mark.parametrize(
    "over,reason",
    [
        (dict(fuel=fuel(delta_g0_prime_J_mol=-30500.0)), "unknown=.*delta_g0_prime_J_mol"),
        (dict(stoichiometry=5), r"stoichiometry must be an integer in \[1, 4\]"),
        (dict(stoichiometry=1.0), r"stoichiometry must be an integer in \[1, 4\]"),
        (dict(patch="nowhere"), "unknown membrane patch"),
        (dict(law="other@1"), "law is one of"),
        (dict(role="K"), "neutral law's role has valence 0"),
        (dict(role="Q"), "not a species row"),
        (dict(km_role_mM=0.0), "km_role_mM must be finite and positive"),
        (dict(capacity_fmol_s=-1.0), "capacity_fmol_s must be finite and nonnegative"),
        (dict(fuel=fuel(node="bath_0")), "fuel node is the patch's inside cell"),
        (dict(fuel=fuel(rows=["ATP", "ADP"])), "three distinct neutral species rows"),
        (dict(fuel=fuel(rows=["ATP", "ADP", "Y"])), "none of them the role"),
        (dict(fuel=fuel(kind="held")), "fuel kind is one of"),
        (dict(fuel=fuel(ph_ref=7.2, ph_band=0.05)), "declares no pH band"),
        (
            dict(law=transporter.PROTON_LAW, role="Na", fuel=fuel(kind=transporter.FINITE)),
            "runs on held fuel",
        ),
        (dict(law=transporter.PROTON_LAW, role="Y"), "proton pump's role has valence"),
    ],
)
def test_the_parse_refuses_with_its_reason(over, reason):
    with scoped(), pytest.raises(ConfigError, match=reason):
        parse_spec(held_world(population(**over)))


def test_a_second_population_on_a_patch_takes_the_population_axis_and_ids_stay_unique():
    """Version 1's layout holds one population per patch; a declaration with two on one patch
    takes the population axis (the kinds owner's design statement 1, §1), where any number sit on
    a host. IDs stay unique among the model's either way. The trace estimate counts the axis's
    saved rows (the third review's finding 3): a third population raises @3's working size by
    twice its values in each bound state row, which a formula in the capacities leaves unchanged;
    and the definition is refused where the estimate would undercount the bound row (planted: a
    view set one population short). Host only: parsed and bound, never run."""
    with scoped():
        spec = parse_spec(held_world(population(), population(id="transporter_1")))
        ((_, entry),) = surface_pump_v3.structure(spec.model).kinds
        assert isinstance(entry, transporter.CycleAxis)
        with pytest.raises(ConfigError, match="must be unique"):
            parse_spec(held_world(population(id="cell_0")))
        three = parse_spec(held_world(*(population(id=f"transporter_{i}") for i in range(3))))
        states = [get_model(s.model).initial_values(s)[0] for s in (spec, three)]
        rows = [sum(np.size(v) for v in state) for state in states]
        grown = surface_pump_v3.working_size(three) - surface_pump_v3.working_size(spec)
        assert grown == 2 * (rows[1] - rows[0]) > 0

    def short(spec, declaration):  # Planted: a view set one population short, an undercount.
        sets = transporter.view_sets(spec, declaration)
        ids = sets["cycle_population"]["ids"][:-1]
        return sets | {"cycle_population": sets["cycle_population"] | {"ids": ids}}

    with scoped(dataclasses.replace(transporter.TRANSPORTER, view_sets=short)):
        with pytest.raises(ConfigError, match="The trace estimate counts .* undercount"):
            parse_spec(held_world(*(population(id=f"transporter_{i}") for i in range(3))))


def test_the_definition_check_names_its_reasons():
    """The registry's potentials are required, as before; finite fuel under the neutral law, which
    version 1 refused (gap 2), now takes the population axis, where it runs (statement 1, §1)."""
    with scoped():
        with pytest.raises(ConfigError, match="fuel row ATP declares no standard potential"):
            parse_spec(held_world(potentials=False))
        spec = parse_spec(held_world(population(fuel=fuel(kind=transporter.FINITE))))
        ((_, entry),) = surface_pump_v3.structure(spec.model).kinds
        assert isinstance(entry, transporter.CycleAxis)


def test_a_value_change_reuses_the_implementation():
    """A4: worlds that differ only in values share one implementation object (and program)."""
    with scoped():
        one = parse_spec(held_world(population()))
        two = parse_spec(held_world(population(capacity_fmol_s=2 * CAPACITY, km_atp_mM=0.2)))
        assert get_model(one.model) is get_model(two.model)


def kernel_rate(spec):
    """The neutral kernel's cycle rate (fmol/s) at the world's start, in NumPy."""
    m = spec.model
    ids, cell = list(m.species_ids), m.cells[0]
    c = {row: cell.initial_amount_fmol[ids.index(row)] / cell.volume_pL for row in ROWS}
    bath = m.extracellular[0]
    c_out = bath.initial_amount_fmol[ids.index("Y")] / bath.volume_pL
    i = neutral.Inputs(
        c["Y"], c_out, c["ATP"], c["ADP"], c["Pi"], DRIVE0_J_MOL, 1000.0, m.temperature_K
    )
    return float(neutral.kinetics(i, neutral.Parameters(CAPACITY, 1.0, 1.0, 0.1), 1.0, xp=np)[0])


def test_the_neutral_role_on_held_fuel_runs_with_every_ledger_closing():
    with scoped():
        spec = parse_spec(held_world())
        model = get_model(spec.model)
        assert [k for k, _ in model.structure.kinds] == [transporter.KIND_ID]
        result = run(spec)  # Host checks on every accepted row: all ten ledgers.
        movers = surface_pump_v3.moved_rows(spec.model)
    final, ids = result.final.state, list(spec.model.species_ids)
    y, atp, adp, pi = (ids.index(row) for row in ("Y", "ATP", "ADP", "Pi"))
    cycles = float(final.transporter_cycles[0])
    assert cycles == pytest.approx(kernel_rate(spec) * END_S, rel=1e-4, abs=0)  # Nearly constant.
    assert float(result.observations.transporter_cycle_rate_fmol_s[0, 0]) == pytest.approx(
        kernel_rate(spec), rel=1e-12, abs=0
    )
    # Y's rows, the supply record and the cycles sum the same per-step increments (nu = -1, the
    # supply's +-1; nothing else moves them): each sum within (steps + 1) u of its terms, so twice
    # that apart. (abs=0 throughout: approx's default abs of 1e-12 exceeds these fmol values.)
    rel = 2 * (result.final.step_index + 1) * U
    assert float(final.amount_increment[y, 0]) == pytest.approx(-cycles, rel=rel, abs=0)
    assert float(final.reservoir_supplied[y, 0]) == pytest.approx(-cycles, rel=rel, abs=0)
    for row in (atp, adp, pi):  # Held: read at every stage, never moved.
        assert float(final.amount_increment[row, 0]) == 0.0
        assert float(final.extracellular_amount_increment[row, 0]) == 0.0
    record = final.transporter_fuel_supplied_fmol[:, 0]
    assert [float(record[r]) for r in (atp, adp, pi)] == pytest.approx(
        [cycles, -cycles, -cycles], rel=rel, abs=0
    )
    assert float(np.sum(np.abs(record))) == pytest.approx(3 * cycles, rel=rel + 2 * U, abs=0)
    heat, work = (
        float(final.transporter_dissipated_energy_pJ[0]),
        float(final.transporter_metabolic_work_pJ[0]),
    )
    drive = DRIVE0_J_MOL + R * spec.model.temperature_K * math.log(0.3 * 3.0 / (3.0 * 1000.0))
    assert work == pytest.approx(-1e-3 * cycles * drive, rel=1e-9, abs=0)  # A fixed drive.
    assert 0 < heat < work  # Y climbs its gradient: the stored part is work - heat > 0.
    assert result.diagnostics["max_energy_balance_relative"] < 1e-6
    assert "transporter_cycles" in result.history._fields
    assert any(entry[0] == transporter.KIND_ID for entry in movers["Y"])
    assert "ATP" not in movers and "ADP" not in movers and "Pi" not in movers


def test_a_planted_flipped_role_fails_the_material_ledger():
    def flipped(state, potentials, control, p, *, xp):
        r = transporter.rates(state, potentials, control, p, xp=xp)
        return r._replace(cell=-r.cell, outside=-r.outside)

    planted = dataclasses.replace(transporter.TRANSPORTER, rates=flipped)
    with scoped(planted):
        spec = parse_spec(held_world())
        with pytest.raises(NumericalError, match="accounting failed: local"):
            run(spec)


def test_the_law_domain_refuses_at_the_stage():
    """A slot outside its law's domain (|dG_cyc/RT| > 80: the registry puts Δ_rG'° at -250 RT)
    refuses the definition's initial state through KindRates.valid; within the domain the same
    world is admitted."""
    raw = held_world()
    adp = next(e for e in raw["model"]["species"] if e["id"] == "ADP")
    with scoped():
        adp["standard_mu_RT"] = -70.0  # |a| = 70 + 8 < 80: admitted.
        parse_spec(copy.deepcopy(raw))
        adp["standard_mu_RT"] = -250.0
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(raw)


# ------------------------------------------------------------------ the charged role (FR-4's pump)
# A generic charged world, not FR-4's: the proton pump moves H from heredity cell D, which B4
# buffers (pK 7.2, 50 mM, pH 7.2), into the held bath (unbuffered, pH 7.4), on held fuel. Every
# other route, channel and pump is at availability 0, so the pump is the only charge mover.

PH_CELL, PH_BATH, PK_BUFFER, BUFFER_mM = 7.2, 7.4, 7.2, 50.0
CHARGED_KINDS = (transporter.TRANSPORTER, proton_buffer.PROTON_BUFFER)
PUMP = dict(
    law=transporter.PROTON_LAW,
    role="H",
    stoichiometry=2,
    capacity_fmol_s=8.3027e-3,
    km_role_mM=1e-4,
    km_atp_mM=0.1,
)


def charged_world(*, ph_cell=PH_CELL, **over):
    entry = population(**PUMP, fuel=fuel(ph_ref=PH_CELL, ph_band=0.05))
    entry.update(over)
    raw = held_world(entry)
    m, c0 = raw["model"], 1000.0
    h, k = c0 * 10**-ph_cell, c0 * 10**-PK_BUFFER
    cell, bath = m["cells"][0], m["extracellular"][0]
    v_cell, v_bath = cell["volume_pL"], bath["volume_pL"]
    amounts = {
        cell["id"]: dict(H=v_cell * (h + BUFFER_mM * h / (h + k)), B_c=v_cell * BUFFER_mM),
        bath["id"]: dict(H=v_bath * c0 * 10**-PH_BATH, B_c=v_bath * 1e-6),
    }
    forms = dict(H=dict(), B_c=dict(protonated_standard_mu_RT=-PK_BUFFER * math.log(10.0)))
    for species, z in (("H", 1), ("B_c", -1)):
        m["species"].append(dict(id=species, valence=z, standard_mu_RT=0.0, **forms[species]))
        for node in (cell, bath):
            node["initial_amount_fmol"][species] = amounts[node["id"]][species]
            node["fixed_charge_equivalent_fmol"] -= z * amounts[node["id"]][species]  # Same q.
        for patch in m["membranes"]:
            patch["permeability_m_per_s"][species] = 0.0
        raw["execution"]["material_balance_atol_fmol"][species] = 1e-15
    m["stage_reads"] = [
        dict(
            read_id="rapid_proton_buffer@1",
            proton_row="H",
            buffers={"cell_0": ["B_c"]},
            k_on_per_mM_s={"B_c": 1e7},
        )
    ]
    for group in ("membrane_controls", "channel_controls", "pump_controls"):
        for entry in raw["experiment"][group]:
            entry["schedule"] = [dict(time=0.0, availability=0.0)]
    return raw


def charged():
    return scoped(*CHARGED_KINDS)


def proton_kernel(voltage_V, temperature_K, capacity=PUMP["capacity_fmol_s"]):
    """The proton kernel at the world's start (free h from the declared pH), in NumPy."""
    i = proton.Inputs(
        1e3 * 10**-PH_CELL, 1e3 * 10**-PH_BATH, voltage_V, 3.0, 0.3, 3.0, temperature_K
    )
    q = proton.Parameters(capacity, 2.0, 1e-4, 0.1, DRIVE0_J_MOL, PH_CELL, 0.05)
    return i, q


def test_the_charged_pump_reads_free_h_and_closes_charge_field_and_ledgers():
    """FR-4's pump on held fuel through the runner with B4 (gaps 5, 8 and 9 merged):
    - the read: the cycles follow the kernel at free h (pH 7.2), not at the stored H_eq;
    - material: the cell's H_eq falls by 2 x cycles, the bath absorbs it, the held rows hold;
    - charge and field: the bath's electrode answers 2 e per cycle, and the membrane voltage falls
      by the capacitor's closed form;
    - gap 9: the pump's flux is in the patch's membrane flux and current;
    - ledgers: every accepted row passes all ten, the energy ledger with B4's stored term."""
    from cells.definitions.surface_pump_v3_spec import control_values
    from validation.tissue.surface_pump_v3_fixtures import HEREDITY_CAPACITANCE_F

    with charged():
        spec = parse_spec(charged_world())
        model = get_model(spec.model)
        assert [k for k, _ in model.structure.kinds] == [
            "cells.rapid_proton_buffer@1",
            transporter.KIND_ID,
        ]
        result = run(spec)
        state, p = model.initial_values(spec)
        control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
        current_A = model.readouts(state, control, p, xp=np).field.rates.membrane_current_A
    final, obs, ids = result.final.state, result.observations, list(spec.model.species_ids)
    h, atp = ids.index("H"), ids.index("ATP")
    temperature = spec.model.temperature_K
    rate = proton.kinetics(*proton_kernel(obs.membrane_voltage_V[0, 0], temperature), 1.0, xp=np)
    cycles = float(final.transporter_cycles[0])
    assert cycles == pytest.approx(float(rate.cycles_fmol_s) * END_S, rel=1e-4, abs=0)
    # H's rows and the cycles sum the same per-step increments (nu = -2, exact in binary): each
    # sum within (steps + 1) u of its terms, so twice that apart. abs=0 throughout: approx's
    # default abs of 1e-12 exceeds these fmol, coulomb and ampere values.
    rel = 2 * (result.final.step_index + 1) * U
    assert float(final.amount_increment[h, 0]) == pytest.approx(-2 * cycles, rel=rel, abs=0)
    assert float(final.reservoir_supplied[h, 0]) == pytest.approx(-2 * cycles, rel=rel, abs=0)
    assert float(final.amount_increment[atp, 0]) == 0.0
    charge = CHARGE_PER_FMOL * 2 * cycles
    assert float(final.electrode_charge_transferred_C[0]) == pytest.approx(charge, rel=1e-9, abs=0)
    dv = float(obs.membrane_voltage_V[-1, 0] - obs.membrane_voltage_V[0, 0])
    assert dv == pytest.approx(-charge / HEREDITY_CAPACITANCE_F, rel=1e-9, abs=0)
    flux = float(obs.membrane_flux_fmol_s[0, h, 0])  # Gap 9, at the start: 2 H+ per cycle.
    assert flux == pytest.approx(2 * float(rate.cycles_fmol_s), rel=1e-8, abs=0)
    # The readouts at the read and the potentials: the instantaneous rate at free h.
    assert float(obs.transporter_cycle_rate_fmol_s[0, 0]) == pytest.approx(
        float(rate.cycles_fmol_s), rel=1e-8, abs=0
    )
    assert float(obs.transporter_cycle_free_energy_J_mol[0, 0]) == pytest.approx(
        float(rate.cycle_free_energy_J_mol), rel=1e-9, abs=0
    )
    assert float(current_A[0]) == pytest.approx(CHARGE_PER_FMOL * flux, rel=1e-12, abs=0)
    heat = float(final.transporter_dissipated_energy_pJ[0])
    work = float(final.transporter_metabolic_work_pJ[0])
    assert 0 < heat < work
    assert result.diagnostics["max_energy_balance_relative"] < 1e-6


def test_a_held_fuel_row_has_one_writer():
    """Gap 8, for the neutral role's held fuel: held ATP at the cell is refused at binding where
    an @3 route or another kind (a passive route) moves it, naming the writer."""
    from cells.kinds import passive_routes

    raw = held_world()
    raw["model"]["membranes"][0]["permeability_m_per_s"]["ATP"] = 1e-10
    with scoped(), pytest.raises(ConfigError, match="holds ATP at cell_0, which membrane"):
        parse_spec(raw)
    raw = held_world()
    raw["model"]["passive_routes"] = [
        dict(
            id="atp_route_0",
            patch="membrane_0",
            law="passive_neutral_permeation@1",
            species="ATP",
            permeability_m_per_s=1e-9,
        )
    ]
    with scoped(transporter.TRANSPORTER, passive_routes.PASSIVE_ROUTES):
        with pytest.raises(ConfigError, match="holds ATP at cell_0, which cells.passive_routes"):
            parse_spec(raw)
        raw["model"]["passive_routes"][0]["species"] = "Y"  # The role: moved by both, admitted.
        parse_spec(raw)


def converted(raw, c0_mM):
    """raw with every registry potential re-expressed at the standard concentration c0_mM:
    mu°/RT at c0' is mu°/RT at c0 plus ln(c0'/c0), for both forms of a two-form row."""
    raw = copy.deepcopy(raw)
    m = raw["model"]
    shift = math.log(c0_mM / m["standard_concentration_mM"])
    m["standard_concentration_mM"] = c0_mM
    for entry in m["species"]:
        for key in ("standard_mu_RT", "protonated_standard_mu_RT"):
            if key in entry:
                entry[key] += shift
    return raw


def test_the_kinetics_do_not_depend_on_the_registrys_standard_concentration():
    """The proton law's c° is 1000 mM and the neutral law takes the registry's: once the
    potentials are converted, both laws' rates and energies at c0 = 1 mM equal those at 1000 mM."""
    from cells.definitions.surface_pump_v3_spec import control_values
    from cells.kinds import proton_buffer

    def start(raw):
        spec = parse_spec(raw)
        state, p = surface_pump_v3.initial_values(
            spec, structure=surface_pump_v3.structure(spec.model)
        )
        controls = control_values(spec, [0.0])
        control = type(controls)(*(v[0] for v in controls))
        read = (
            proton_buffer.stage_read(state, p, xp=np)[0] if "stage_reads" in raw["model"] else state
        )
        potentials = np.linspace(-0.05, 0.02, p.active.size + p.outside_active.size)
        return transporter.kinetics(read, potentials, control.transporter_availability, p, xp=np)

    for world, kinds in ((held_world(), ()), (charged_world(), CHARGED_KINDS)):
        with scoped(*kinds):
            at_molar, at_millimolar = start(world), start(converted(world, 1.0))
        for a, b in zip(at_molar, at_millimolar, strict=True):
            np.testing.assert_allclose(a, b, rtol=1e-12, atol=0.0)
        assert bool(np.all(at_molar[3]))


def test_the_pumps_slope_joins_the_step_rules():
    """Gap 5: stage_term is the kernel's slope at the pump's static head at the stage's read (bare,
    without potentials), at both of the patch's ends (cells, then outside nodes);
    bound_rate is the host term with the role's saturation at 1, over the cell's capacitance (the
    bath is held), and a capacity that breaches it at 1 ms is refused by the step checks."""
    from cells.definitions.surface_pump_v3_spec import control_values
    from cells.kinds import proton_buffer

    with charged():
        spec = parse_spec(charged_world())
        structure = surface_pump_v3.structure(spec.model)
        state, p = surface_pump_v3.initial_values(spec, structure=structure)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(v[0] for v in controls))
        read, ok = proton_buffer.stage_read(state, p, xp=np)
        term = transporter.stage_term(read, None, control, p, xp=np)  # Bare: the static head.
        n, bath = p.active.size, p.active.size + int(p.membrane_outside[0])
        rate = transporter.bound_rate(spec, dict(spec.model.kinds)[transporter.KIND_ID])
        surface_pump_v3.check_steps(spec, np.asarray([1e-3]), None)
        big = parse_spec(charged_world(capacity_fmol_s=2.0))
        with pytest.raises(ConfigError, match="a declared kind's explicit-rate bound"):
            surface_pump_v3.check_steps(big, np.asarray([1e-3]), None)
    assert bool(ok)
    h_in, temperature = 1e3 * 10**-PH_CELL, spec.model.temperature_K
    s_atp = 3.0 / (3.0 + 0.1)
    s_h = 1.0 / (1.0 + (1e-4 / h_in) ** 2)
    unit = 4 * F / (R * temperature) * CHARGE_PER_FMOL * PUMP["capacity_fmol_s"] * s_atp
    # abs=0: approx's default abs of 1e-12 exceeds these slopes (siemens, about 1e-9).
    assert float(term[:n][0]) == pytest.approx(unit * s_h, rel=1e-6, abs=0)  # The read's free h.
    assert float(term[bath]) == float(term[:n][0])  # Per node: the patch's both ends.
    capacitance = spec.model.membranes[0].capacitance_F
    assert rate == pytest.approx(unit / capacitance, rel=1e-12, abs=0)


def test_the_pumps_slope_follows_the_voltage_past_its_static_head():
    """Item 7 (core-d172 5b1b931e): stage_term takes the stage's node potentials, so the pump's
    slope is the kernel's n F |d cycles/dV| at the patch voltage V, e^a times its static-head
    value with a = n F (V_head - V) / RT: below it while the pump runs forward (V > V_head) and
    above it past the head, where the patch drives it into reverse (V < V_head); called bare it
    is the head's. Through membrane_rate the reversed slope breaches the 1 ms step bound where
    the slope at the head does not."""
    from cells.definitions.surface_pump_v3_spec import control_values

    with charged():
        spec = parse_spec(charged_world())
        structure = surface_pump_v3.structure(spec.model)
        state, p = surface_pump_v3.initial_values(spec, structure=structure)
        controls = control_values(spec, [0.0])
        control = type(controls)(*(v[0] for v in controls))
        read, ok = proton_buffer.stage_read(state, p, xp=np)
        c_in, c_out, fuel = transporter.gather(read, p, xp=np)
        i, q = transporter.proton_law(c_in, c_out, np.zeros_like(c_in), fuel, p, xp=np)
        head = float(transporter.static_head_V(i, q, xp=np)[0])
        n = p.active.size  # stage_term is per node: cells, then outside nodes.
        bare = float(transporter.stage_term(read, None, control, p, xp=np)[:n][0])

        def potentials(voltage):  # The patch's cell at V, its outside node (the bath) at 0.
            out = np.zeros(p.active.size + p.outside_active.size)
            out[p.membrane_cell[0]] = voltage
            return out

        def rate(voltage):
            return 1e-3 * float(
                surface_pump_v3.membrane_rate(
                    state, control, p, xp=np, structure=structure, potentials=potentials(voltage)
                )
            )

        a_unit = 2 * F / (R * spec.model.temperature_K)  # n F / RT, per volt below the head
        for shift in (0.05, 0.0, -0.02, -0.05, -0.1):
            v = head + shift
            term = float(transporter.stage_term(read, potentials(v), control, p, xp=np)[:n][0])
            kernel = float(
                proton.electrogenic_conductance_S(
                    i._replace(voltage_V=np.full_like(c_in, v)), q,
                    control.transporter_availability, xp=np,
                )[0]
            )  # fmt: skip
            # abs=0: approx's default abs of 1e-12 exceeds these slopes (siemens, about 1e-9).
            assert term == pytest.approx(kernel, rel=1e-12, abs=0)
            assert term == pytest.approx(bare * math.exp(-a_unit * shift), rel=1e-9, abs=0), shift
        past = transporter.stage_term(read, potentials(head - 0.05), control, p, xp=np)
        past = float(past[:n][0])
        assert past / bare == pytest.approx(math.exp(0.05 * a_unit), rel=1e-9, abs=0)  # About 42.
        assert -0.3 < head < -0.25  # FR-4's drive: d_rG'_ATP near -51 kJ/mol, n = 2.
        assert rate(head) <= surface_pump_v3.EXPLICIT_STEP_BOUND < rate(head - 0.2)
    assert bool(ok)


def test_the_ph_band_refuses_at_the_stage():
    """The held fuel's band (7.2 +- 0.05) at the read's free h: a cytosol at pH 7.3 is refused at
    the definition (KindRates.valid), at 7.24 admitted."""
    with charged():
        parse_spec(charged_world(ph_cell=7.24))
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(charged_world(ph_cell=7.3))


# ------------------------------------------------------------------ FR-50's one-way records
# fr50-one-way-records-v1 (D327): host rows, judged by the tagged judge's own checks
# (validation/fr50/judge.py) against the builder's closed forms (validation/fr50/closed_forms.py),
# on the registered cases; the compiled K4 row is tests/unit/test_one_way_records_transporter.py.


def _fr50():
    import json

    from validation.fr50 import closed_forms, engine, judge, plants

    cases = json.loads(judge.SPEC.read_text())["cases"]
    return cases, closed_forms, engine, judge, plants


def test_one_way_cycle_records_exist_only_where_a_population_asks():
    """D148 in both layouts: without the key the entry, the fields and the record hooks are
    today's; with it, OneWayEntry, the records, the mask and the hooks, and the key round trips.
    On the population axis, a diagram population's records close to cycle_count at rounding over
    four host steps."""
    from tests.unit import test_cycle_kind as ck

    cases, _, engine, _, _ = _fr50()
    case = cases["K4_transporter_equilibrium"]
    for one_way in (False, True):
        spec = parse_spec(engine.transporter_world(case, one_way=one_way))
        declaration = dict(spec.model.kinds)[transporter.KIND_ID]
        entry = transporter.structure_entry(declaration)
        bound = kind_registry.bound(transporter.TRANSPORTER, entry)
        assert isinstance(entry, transporter.OneWayEntry) == one_way
        assert (bound.one_way_fluxes is not None) == one_way == bool(bound.one_way_records)
        assert bound.state_axes == transporter.STATE_AXES + (
            transporter.V1_ONE_WAY_STATE_AXES if one_way else ()
        )
        assert (transporter.ONE_WAY_KEY in transporter.to_dict(declaration)[0]) == one_way
    with ck.scoped():
        spec = parse_spec(ck.exchange_world(ck.exchanger(one_way=True)))
        entry = transporter.structure_entry(dict(spec.model.kinds)[transporter.KIND_ID])
        axis = transporter.CycleAxis(("seamtest.slip_exchanger@1",))
        assert entry == transporter.OneWayEntry(axis)
        _, state, p, control = ck.start(spec)
        impl = get_model(spec.model)
        for _ in range(4):
            state, valid = impl.imex_step(state, 1e-4, control, p, xp=np)
            assert bool(valid)
        moved = state.cycle_forward_fmol - state.cycle_backward_fmol - state.cycle_count
        bound = 2.5 * np.finfo(float).eps * 4 * (
            state.cycle_forward_fmol + state.cycle_backward_fmol + np.abs(state.cycle_count)
        )
        assert np.all(np.abs(moved) <= bound) and np.any(state.cycle_forward_fmol > 0)
        assert np.all(state.cycle_one_way_gap_relative <= 1e-6)


def test_k4h_one_way_cycle_rates_meet_hills_ratio_and_the_inverted_ratio_fails():
    """K4h (check_k4h: J-/J+ = e^(dG/RT) and J+ = k a S within 1e-12) at the registered state off
    equilibrium; plant K4 (b), J- = J+ e^(-dG/RT), fails its ratio."""
    cases, closed_forms, engine, judge, _ = _fr50()
    reference = closed_forms.k4h("K4h", cases["K4h_transporter_off_equilibrium"])
    request = judge.request_for(reference)
    honest = judge.check_k4h(reference, engine.engine(request))
    assert honest["passed"], honest
    planted = judge.check_k4h(reference, engine.engine(dict(request, plant="K4b_ratio_inverted")))
    assert not planted["ratio"]["passed"] and planted["J_plus"]["passed"]


@pytest.mark.parametrize("plant", [None, "K4a_no_saturation"])
def test_k4_plant_a_misses_the_absolute_records(plant):
    """K4 on ten host steps at 0.1 s (check_absolute): honest, each cycle record is k a S t within
    1e-11; plant K4 (a), J+ without its saturation S, misses it by 1/S while the net stays 0."""
    cases, closed_forms, engine, judge, plants = _fr50()
    case = cases["K4_transporter_equilibrium"]
    reference = closed_forms.k4("K4", case, times=("0", "0.5", "1.0"))
    with plants.planted(plant):
        spec = parse_spec(engine.transporter_world(case, dt=0.1, end=1.0))
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in surface_pump_v3_control(spec)))
        j = [patch.id for patch in spec.model.membranes].index(engine.WALL)
        rows = {q: [] for q in ("n", "F", "B", "net", "gap")}
        for n in range(11):
            if n:
                state, valid = impl.imex_step(state, 0.1, control, p, xp=np)
                assert bool(valid)
            for q, value in zip(rows, (
                n, state.transporter_forward_fmol[j], state.transporter_backward_fmol[j],
                state.transporter_cycles[j], state.transporter_one_way_gap_relative[j],
            ), strict=True):  # fmt: skip
                rows[q].append(value)
    rows = {q: np.asarray(v, dtype=np.int64 if q == "n" else np.float64) for q, v in rows.items()}
    assert judge.check_absolute(reference, rows, "0.1")["passed"] == (plant is None)
    assert judge.check_net_and_gap(rows)["passed"] and judge.check_closure(rows)["passed"]


def surface_pump_v3_control(spec):
    from cells.definitions.surface_pump_v3_spec import control_values

    return control_values(spec, [0.0])
