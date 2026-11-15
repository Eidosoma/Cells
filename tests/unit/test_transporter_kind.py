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

from cells.core import kind_registry
from cells.core.errors import NumericalError
from cells.core.inventory_species import add_inventory_species
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_pump_v3
from cells.models.inner_kinds import transporter
from cells.models.registry import get_model
from cells.processes import atp_transporter as neutral
from cells.processes.electrochemistry import R
from validation.tissue import pump_water_fixtures as water_fixtures

END_S = 0.004
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


def scoped(kind=transporter.TRANSPORTER):
    registry = kind_registry.KindRegistry()
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
    assert p.transporter_drive0_J_mol[0] == pytest.approx(DRIVE0_J_MOL, rel=1e-12)


def fuel(**over):
    return dict(population()["fuel"], **over)


@pytest.mark.parametrize(
    "over,reason",
    [
        (dict(fuel=fuel(delta_g0_prime_J_mol=-30500.0)), "unknown=.*delta_g0_prime_J_mol"),
        (dict(stoichiometry=5), "integer from 1 to 4"),
        (dict(stoichiometry=1.0), "integer from 1 to 4"),
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


def test_one_population_per_patch_and_unique_ids():
    with scoped():
        with pytest.raises(ConfigError, match="already carries a transporter"):
            parse_spec(held_world(population(), population(id="transporter_1")))
        with pytest.raises(ConfigError, match="must be unique"):
            parse_spec(held_world(population(id="cell_0")))


def test_the_definition_check_names_its_reasons():
    with scoped():
        with pytest.raises(ConfigError, match="fuel row ATP declares no standard potential"):
            parse_spec(held_world(potentials=False))
        with pytest.raises(ConfigError, match=r"finite fuel .*gap 2"):
            parse_spec(held_world(population(fuel=fuel(kind=transporter.FINITE))))
        proton = population(
            law=transporter.PROTON_LAW, role="Na", fuel=fuel(ph_ref=7.2, ph_band=0.05)
        )
        with pytest.raises(ConfigError, match=r"gap 5.*gap 8.*gap 9"):
            parse_spec(held_world(proton))


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
    assert cycles == pytest.approx(kernel_rate(spec) * END_S, rel=1e-4)  # Nearly constant rate.
    assert float(final.amount_increment[y, 0]) == pytest.approx(-cycles, rel=1e-12)
    assert float(final.reservoir_supplied[y, 0]) == pytest.approx(-cycles, rel=1e-12)
    for row in (atp, adp, pi):  # Held: read at every stage, never moved.
        assert float(final.amount_increment[row, 0]) == 0.0
        assert float(final.extracellular_amount_increment[row, 0]) == 0.0
    record = final.transporter_fuel_supplied_fmol[:, 0]
    assert [float(record[r]) for r in (atp, adp, pi)] == pytest.approx(
        [cycles, -cycles, -cycles], rel=1e-12
    )
    assert float(np.sum(np.abs(record))) == pytest.approx(3 * cycles, rel=1e-12)
    heat, work = (
        float(final.transporter_dissipated_energy_pJ[0]),
        float(final.transporter_metabolic_work_pJ[0]),
    )
    drive = DRIVE0_J_MOL + R * spec.model.temperature_K * math.log(0.3 * 3.0 / (3.0 * 1000.0))
    assert work == pytest.approx(-1e-3 * cycles * drive, rel=1e-9)  # Held rows: a fixed drive.
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
    refuses the definition's initial state through the stage's finiteness check (the stopgap
    in the module docstring); within the domain the same world is admitted."""
    raw = held_world()
    adp = next(e for e in raw["model"]["species"] if e["id"] == "ADP")
    with scoped():
        adp["standard_mu_RT"] = -70.0  # |a| = 70 + 8 < 80: admitted.
        parse_spec(copy.deepcopy(raw))
        adp["standard_mu_RT"] = -250.0
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(raw)
