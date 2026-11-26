"""B4: FR-4's rapid-buffer closure as the inner model's stage read (cells.kind.rapid_proton_buffer@1).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (g) 1, (k); docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §4; the F3
criterion of §15.6. A heredity cell D gains a proton row H and a buffer row B (base valence -1,
pK 7.2 from the registry's potentials at c0 = 1000 mM), 50 mM of buffer at pH 7.2 in the cell
and an unbuffered held bath at pH 7.4:
- the read gives h = 10^-7.2 M at the buffered cell and h = H at the bath;
- charge and field: with or without the closure, the potentials are the same bits; with every
  route at availability 0 the closure moves nothing;
- material and energy: protons carried out of the buffered cell (the planted charged carrier,
  B5's role) leave H_eq by exactly what moved, and the energy ledger closes with the closure's
  declared term as stored free energy; without that term it fails;
- admission: an inner route for H at the buffered node is refused; so is a buffered held bath,
  whose supply @3 values at the stored total; the envelope refuses a k_on outside it at the
  definition and admits the declared one;
- a failed read (the protons gone) refuses the step.
"""

import copy
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import proton_buffer
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures
from validation.tissue import pump_water_fixtures as water_fixtures

LN10 = math.log(10.0)
C0_MM = 1000.0
PK = 7.2
BUFFER_MM = 50.0
CELL_PH, BATH_PH = 7.2, 7.4


def h_mM(ph):
    return C0_MM * 10.0 ** (-ph)


def buffered_world(*, end_time=0.004, k_on=1e7, quiet=False, h_route=0.0, declare=True):
    """Heredity cell D with H and B rows; the closure declared on the cell (B at a trace in the
    bath, undeclared there). quiet: every route, channel and pump at availability 0."""
    raw = copy.deepcopy(water_fixtures.heredity_cell("D", end_time=end_time))
    m = raw["model"]
    m["species"] += [
        dict(id="H", valence=1, standard_mu_RT=0.0),
        dict(id="B", valence=-1, standard_mu_RT=0.0, protonated_standard_mu_RT=-PK * LN10),
    ]
    m["standard_concentration_mM"] = C0_MM
    h0, k = h_mM(CELL_PH), h_mM(PK)
    for node, h_eq, b in (
        (m["cells"][0], h0 + BUFFER_MM * h0 / (h0 + k), BUFFER_MM),
        (m["extracellular"][0], h_mM(BATH_PH), 1e-9),
    ):
        volume = node["volume_pL"]
        node["initial_amount_fmol"] |= dict(H=h_eq * volume, B=b * volume)
        node["fixed_charge_equivalent_fmol"] -= h_eq * volume - b * volume
    for patch in m["membranes"]:
        patch["permeability_m_per_s"] |= dict(H=h_route, B=0.0)
    raw["execution"]["material_balance_atol_fmol"] |= dict(H=1e-10, B=1e-10)
    if quiet:
        for group in ("membrane_controls", "channel_controls", "pump_controls"):
            for entry in raw["experiment"][group]:
                entry["schedule"] = [dict(time=0.0, availability=0.0)]
    if declare:
        m[proton_buffer.MODEL_KEY] = read({m["cells"][0]["id"]: ["B"]}, {"B": k_on})
    return raw


def read(buffers, k_on):
    """The stage_reads declaration in FR-4's form
    (validation/compartment_ph_engine/definitions.py)."""
    return [
        dict(read_id="cells.kind.rapid_proton_buffer@1", proton_row="H", buffers=buffers, k_on_per_mM_s=k_on)
    ]


def host(spec):
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return impl, state, p, control


def test_the_read_gives_free_protons_and_leaves_charge_and_field():
    spec = parse_spec(buffered_world())
    impl, state, p, control = host(spec)
    assert [k for k, _ in impl.structure.kinds] == [proton_buffer.KIND_ID]
    values = impl.readouts(state, control, p, xp=np)
    assert values.valid
    read, valid = proton_buffer.stage_read(state, p, xp=np)
    assert valid
    row = list(spec.model.species_ids).index("H")
    ci = (p.amount_reference + read.amount_increment)[row] / p.volume
    co = (p.extracellular_amount_reference + read.extracellular_amount_increment)[row]
    assert float(ci[0]) == pytest.approx(h_mM(CELL_PH), rel=1e-9)  # Free h at the buffered cell.
    stored = p.extracellular_amount_reference + state.extracellular_amount_increment
    assert float(co[0]) == float(stored[row, 0])  # The bath is read as stored.
    h, ph = proton_buffer.readouts(state, state, None, control, p, xp=np)
    assert float(ph[0]) == pytest.approx(CELL_PH, abs=1e-9)
    assert float(ph[1]) == pytest.approx(BATH_PH, abs=1e-9)
    assert float(np.sum(proton_buffer.ledger_terms(state, p, xp=np)["stored_pJ"])) == 0.0
    plain = parse_spec(buffered_world(declare=False))
    impl0, state0, p0, control0 = host(plain)
    base = impl0.readouts(state0, control0, p0, xp=np)
    assert values.field.potential_V.tobytes() == base.field.potential_V.tobytes()


def test_two_buffers_take_the_kernels_bisection_and_agree_with_one():
    """Two identical buffers of 25 mM at pK 7.2 are one of 50 mM: the kernel's bisection (two
    buffer rows) gives the closed form's h (one row) to rounding, and its declared term too."""
    raw = buffered_world()
    m = raw["model"]
    m["species"].append(dict(m["species"][-1], id="B2"))
    for node in (*m["cells"], *m["extracellular"]):
        half = node["initial_amount_fmol"]["B"] / 2
        node["initial_amount_fmol"] |= dict(B=half, B2=half)
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["B2"] = 0.0
    raw["execution"]["material_balance_atol_fmol"]["B2"] = 1e-10
    cell = m["cells"][0]["id"]
    m[proton_buffer.MODEL_KEY] = read({cell: ["B", "B2"]}, {"B": 1e7, "B2": 1e7})
    two = parse_spec(raw)
    impl, state, p, control = host(two)
    assert impl.structure.kinds == ((proton_buffer.KIND_ID, (2,)),)
    h_two, _ = proton_buffer.readouts(state, state, None, control, p, xp=np)
    one = parse_spec(buffered_world())
    impl1, state1, p1, control1 = host(one)
    h_one, _ = proton_buffer.readouts(state1, state1, None, control1, p1, xp=np)
    assert float(h_two[0]) == pytest.approx(float(h_one[0]), rel=1e-12)
    terms = [
        float(np.sum(proton_buffer._declared_terms(q, proton_buffer._amounts(s, q, np), xp=np)))
        for s, q in ((state, p), (state1, p1))
    ]
    assert terms[0] == pytest.approx(terms[1], rel=1e-9)


def test_with_only_the_closure_nothing_moves():
    result = run(parse_spec(buffered_world(quiet=True)))
    final = result.final.state
    for name in ("amount_increment", "extracellular_amount_increment"):
        assert not np.any(np.asarray(getattr(final, name))), name
    volts = result.observations.membrane_voltage_V
    assert volts[-1].tobytes() == volts[0].tobytes()
    assert result.observations.pH[-1, 0] == pytest.approx(CELL_PH, abs=1e-9)


def with_standard_part(state, p, *, xp):
    """The kernel's term as it stands: B4's term plus the proton's standard part on the stored
    proton equivalents, RT n (mu°_H/RT - ln c0), whose change @3's reservoir work never books."""
    from cells.laws.electrochemistry import R

    amounts = proton_buffer._amounts(state, p, xp)
    start = xp.concatenate((p.amount_reference, p.extracellular_amount_reference), axis=1)
    row = p.proton_buffer_rows[0]
    standard = p.proton_buffer_proton_mu_RT - xp.log(p.proton_buffer_c0_mM)
    extra = 1e-3 * R * p.temperature * (amounts[row] - start[row]) * standard
    stored = proton_buffer.ledger_terms(state, p, xp=xp)["stored_pJ"]
    return dict(stored_pJ=stored + extra)


def carried(*, ledger=True, rate=1e-3, k_on=1e7, end_time=0.004):
    """The buffered world (routes quiet) with H+ carried out of the cell by the planted carrier,
    under a registry holding the carrier and the closure (its stored term dropped if not ledger,
    or taken with the proton's standard part if ledger == "standard")."""
    from dataclasses import replace

    kind = proton_buffer.PROTON_BUFFER
    if not ledger:
        kind = replace(kind, ledger_terms=None)
    elif ledger == "standard":
        kind = replace(kind, ledger_terms=with_standard_part)
    kinds = kind_fixtures.registry(kind_fixtures.carrier(), kind)
    raw = buffered_world(quiet=True, k_on=k_on, end_time=end_time)
    return kinds, kind_fixtures.declare_carrier(raw, species="H", rate=rate)


def test_carried_protons_close_material_and_energy_with_the_declared_term():
    kinds, raw = carried()
    with kind_registry.scope(kinds):
        spec = parse_spec(raw)
        result = run(spec)  # Every row's host checks, the energy ledger with the stored term.
    final, obs = result.final.state, result.observations
    row = list(spec.model.species_ids).index("H")
    moved = 1e-3 * spec.experiment.end_time
    assert float(final.carrier_transferred[row, 0]) == pytest.approx(moved, rel=1e-12)
    assert float(final.amount_increment[row, 0]) == pytest.approx(-moved, rel=1e-12)  # H_eq.
    b = list(spec.model.species_ids).index("B")
    assert float(final.amount_increment[b, 0]) == 0.0  # Buffer totals never move.
    assert obs.pH[-1, 0] > CELL_PH  # Protons left: the cell alkalinises a little.
    # Gap 7: the running extrema over every stage (the margin; a breach would refuse the step).
    lag = np.asarray(final.proton_buffer_max_lag_pH)
    assert 0.0 < float(lag[0]) <= 1e-3 and float(lag[1]) == 0.0  # Buffered cell; bath.
    low, high = np.asarray(final.proton_buffer_min_pH), np.asarray(final.proton_buffer_max_pH)
    assert float(low[0]) == pytest.approx(CELL_PH, abs=1e-9)  # The start's stage: pH rises.
    assert CELL_PH < float(high[0]) <= float(obs.pH[-1, 0])  # The last stage precedes the end.
    charge = CHARGE_PER_FMOL * moved
    assert float(final.electrode_charge_transferred_C[0]) == pytest.approx(charge, rel=1e-9)
    assert result.diagnostics["max_energy_balance_relative"] < 1e-3
    for planted in (False, "standard"):  # No term; the kernel's term with the standard part.
        kinds, raw = carried(ledger=planted)
        with kind_registry.scope(kinds):
            with pytest.raises(NumericalError, match="accounting failed: energy"):
                run(parse_spec(raw))


def test_the_closure_runs_on_the_vector_window_path():
    """The carried-proton world through one compiled window: every row passes the device checks,
    the closure's read and its stored term included (traced under jax.numpy)."""
    from cells.execution import vector_windows
    from cells.execution.batch import BatchSpec, WorldSpec
    from cells.execution.windows import WindowPolicy

    steps, big = 4, 2**53 - 1
    kinds, raw = carried()
    with kind_registry.scope(kinds):
        spec = parse_spec(raw)
        batch = BatchSpec((WorldSpec(1, spec),), 1, big, big)
        window = next(
            iter(vector_windows.iter_vector_windows(batch, WindowPolicy(steps, "checkpoints")))
        )
        names = get_model(spec.model).STATE_TYPE._fields
    final = window.checkpoints[1].state
    row = list(spec.model.species_ids).index("H")
    moved = float(np.asarray(final[names.index("carrier_transferred")])[row, 0])
    assert moved == pytest.approx(1e-3 * steps * spec.execution.dt, rel=1e-9)
    increment = np.asarray(final[names.index("amount_increment")])
    assert float(increment[row, 0]) == pytest.approx(-moved, rel=1e-9)


LEAK_M_S = 6e-7  # FR-4's proton leak (6e-5 cm/s).


def leak_route(**overrides):
    """The proton leak in FR-4's form (validation/compartment_ph_engine/definitions.py)."""
    entry = dict(
        id="proton_leak_0",
        patch="membrane_0",
        law="cells.route.proton_constant_field_leak@1",
        permeability_m_per_s=LEAK_M_S,
    )
    return entry | overrides


def leaky_world(**kwargs):
    raw = buffered_world(**kwargs)
    raw["model"]["passive_routes"] = [leak_route()]
    return raw


def test_the_proton_leak_reads_free_h_and_joins_the_stage_rule():
    """cells.kind.passive_routes@1's charged law: its flux is the kernel's at the closure's free h (not
    H_eq / V) and the patch voltage, it is the patch's only H flux (gap 9), and its slope
    conductance joins membrane_rate (gap 5)."""
    from cells.kinds import passive_routes
    from cells.laws.transport import proton_leak
    from validation.tissue.surface_pump_v3_fixtures import HEREDITY_AREA_M2

    spec = parse_spec(leaky_world())
    impl, state, p, control = host(spec)
    kinds = {k for k, _ in impl.structure.kinds}
    assert kinds == {passive_routes.KIND_ID, proton_buffer.KIND_ID}
    values = impl.readouts(state, control, p, xp=np)
    assert values.valid
    row = list(spec.model.species_ids).index("H")
    t = spec.model.temperature_K
    voltage = float(values.field.rates.membrane_voltage_V[0])
    args = (h_mM(CELL_PH), h_mM(BATH_PH), voltage, t, HEREDITY_AREA_M2, LEAK_M_S, 1.0)
    inward = float(proton_leak.flux_fmol_s(*args, xp=np))
    outward = float(values.field.rates.membrane_flux_fmol_s[row, 0])
    assert outward == pytest.approx(-inward, rel=1e-8)  # At free h, the patch's only H mover.
    plain = parse_spec(buffered_world())
    impl0, state0, p0, control0 = host(plain)
    added = impl.membrane_rate(state, control, p, xp=np) - impl0.membrane_rate(
        state0, control0, p0, xp=np
    )
    slope = float(proton_leak.conductance_S(*args, xp=np))
    assert float(added) == pytest.approx(slope / p.membrane_capacitance[0], rel=1e-9)


def test_the_proton_leak_runs_with_every_ledger():
    result = run(parse_spec(leaky_world()))  # Host checks: material, charge, energy.
    heat = np.asarray(result.final.state.passive_dissipated_energy_pJ)
    assert float(heat[0]) > 0.0  # Tableau-booked, never exact: a charged route.


def test_the_proton_leaks_admission():
    # A single-form row of another valence is the kind's own refusal (M, the world's valence -1
    # anion). The buffer's two-form row B is refused first by the species registry, whose checks
    # run ahead of the kinds': its moved_in_step joins the kinds' moved_rows (the operators'
    # registry join), so check_two_form_rows sees the leak's route.
    for overrides, message in (
        (dict(patch=None, junction="j"), "the proton leak sits on a membrane patch"),
        (dict(species="Na"), "is not the closure's proton row"),
        (dict(species="M"), "carries a valence \\+1 proton row"),
        (
            dict(species="B"),
            "species B has two forms .*cells.route.proton_constant_field_leak@1\\) at cell_0 moves its cell "
            "rows, and no law declares how it moves the forms",
        ),
        # The routing door (§7.4 (n), 207393ba): factors are factor-source IDs, and binding
        # refuses an ID that no declared kind exposes (FR-5's sources are the FR lane's kinds).
        (dict(factors=[dict(law="damage", id="damage_0")]), "a list of distinct factor-source IDs"),
        (dict(factors=["damage_0"]), "names unknown factor sources \\['damage_0'\\]"),
    ):
        raw = buffered_world()
        entry = {k: v for k, v in leak_route(**overrides).items() if v is not None}
        raw["model"]["passive_routes"] = [entry]
        with pytest.raises(ConfigError, match=message):
            parse_spec(raw)
    raw = buffered_world(h_route=1e-9)
    raw["model"]["passive_routes"] = [leak_route()]
    with pytest.raises(ConfigError, match="has its own permeability for H"):
        parse_spec(raw)


def test_an_inner_route_for_the_proton_at_a_buffered_node_is_refused():
    with pytest.raises(ConfigError, match="moves the proton row H at a buffered node"):
        parse_spec(buffered_world(h_route=1e-9))
    parse_spec(buffered_world(h_route=1e-9, declare=False))  # Unbuffered, @3's route is fine.


def test_a_buffered_held_bath_is_refused():
    """A held bath's supply is valued at its stored total's concentration (@3's reservoir work),
    while every route there books against the free proton, so a buffered held bath's energy ledger
    cannot close; it is refused at parse. The control: the cell's closure beside the unbuffered
    bath is admitted. Planted: the same declaration with the bath named among the buffered nodes."""
    parse_spec(buffered_world())
    raw = buffered_world()
    m = raw["model"]
    cell, bath = m["cells"][0]["id"], m["extracellular"][0]["id"]
    assert m["extracellular"][0]["reservoir"]
    m[proton_buffer.MODEL_KEY] = read({cell: ["B"], bath: ["B"]}, {"B": 1e7})
    with pytest.raises(ConfigError, match=f"node {bath} is a held bath"):
        parse_spec(raw)


def test_the_envelope_refuses_a_k_on_outside_it():
    kinds, raw = carried(k_on=1e-9)  # Far outside: the lag at the carried flux is huge.
    with kind_registry.scope(kinds):
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(raw)
    kinds, raw = carried()  # The declared k_on: admitted.
    with kind_registry.scope(kinds):
        parse_spec(raw)


def test_a_root_that_misses_the_residual_check_refuses(monkeypatch):
    """The kernel's convergence check (|g|/H <= 1e-13) is the read's validity: with the check made
    impossible, the row and the step's end state are refused (domain_valid reads them)."""
    from cells.laws.reactions import rapid_proton_buffer as closure

    spec = parse_spec(buffered_world())
    impl, state, p, control = host(spec)
    assert impl.readouts(state, control, p, xp=np).valid
    monkeypatch.setattr(closure, "RESIDUAL_RTOL", -1.0)
    assert not impl.readouts(state, control, p, xp=np).valid
    assert not impl.domain_valid(state, p, p.active, xp=np)
    plain = parse_spec(buffered_world(declare=False))  # The same state without the closure.
    impl0, state0, p0, _ = host(plain)
    assert impl0.domain_valid(state0, p0, p0.active, xp=np)
