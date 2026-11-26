"""The kind interface's rules (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)), on the host.

- Non-commuting hooks on the same rows are refused at binding: two kinds' stage reads on a
  shared row are refused, disjoint rows are admitted, and a stage read must declare its rows.
  Bookings commute by construction: every kind's book receives the same end state, and a booking
  that writes anything but its kind's own state fields is refused.
- Field order and hook order are named apart: reversing the hook order reverses the stage reads'
  calls and moves no field.
- Check-path hooks trace on the device: a domain that branches on a value in Python, a ledger
  term of an unknown role or a non-scalar domain is refused at binding.
- Declared kinds are refused under RK4 (fail-closed): their step guards are the IMEX step's.
- The charge rule's rows at a stage beside a floating node (CALCIUM_STORE_AND_CHANNELS_DESIGN.md
  §8.3): a kind's or a channel's slope counts over the capacitance it relaxes, a loose patch's own
  or its cell's held patches', and a kind that charges a cell with no held patch is refused by name.
"""

import copy
import re

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import KLEAK_LAW_ID, control_values
from cells.laws.electrochemistry import F, R
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures


def planted(name, key, **hooks):
    """A planted kind with one state field, one layout field and one control, plus hooks."""
    return kind_registry.Kind(
        kind_id="tests.kind.planted_kind@1".replace("planted_kind", name),
        model_key=key,
        state_axes=((f"{name}_value", ("cell_slot",)),),
        layout_fields=(f"{name}_rate",),
        control_fields=(f"{name}_availability",),
        parse=lambda entries, base: tuple(sorted(entries.items())),
        to_dict=lambda declaration: dict(declaration),
        structure_entry=lambda declaration: (),
        initial=lambda spec, declaration, layout: (
            {f"{name}_value": np.zeros(spec.execution.capacity)},
            {f"{name}_rate": np.asarray([1.0])},
        ),
        control_values=lambda spec, declaration, times: {
            f"{name}_availability": np.ones(len(times))
        },
        **hooks,
    )


def registry(*kinds):
    out = kind_registry.KindRegistry()
    for kind in kinds:
        out.register(kind)
    return out


def declaring(*keys):
    raw = copy.deepcopy(water_fixtures.heredity_cell("D", end_time=0.004))
    for key in keys:
        raw["model"][key] = {"rate": 1.0}
    return raw


def reader(name, key, rows, calls=None):
    def stage_read(state, p, *, xp):
        if calls is not None:
            calls.append(name)
        return state, True

    return planted(name, key, stage_read=stage_read, stage_rows=lambda declaration: rows)


def host_inputs(spec):
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return impl, state, p, control


def test_stage_reads_on_a_shared_row_are_refused_at_binding():
    shared = (("K", "cell_0"),)
    kinds = registry(reader("alpha", "alpha_block", shared), reader("beta", "beta_block", shared))
    with kind_registry.scope(kinds):
        with pytest.raises(ConfigError, match=r"tests.kind.alpha@1 and tests.kind.beta@1 both read row"):
            parse_spec(declaring("alpha_block", "beta_block"))
    apart = registry(
        reader("alpha", "alpha_block", (("K", "cell_0"),)),
        reader("beta", "beta_block", (("Na", "cell_0"),)),
    )
    with kind_registry.scope(apart):
        parse_spec(declaring("alpha_block", "beta_block"))  # Disjoint rows: admitted.
    unrowed = planted("alpha", "alpha_block", stage_read=lambda state, p, *, xp: (state, True))
    with kind_registry.scope(registry(unrowed)):
        with pytest.raises(ConfigError, match="declares no stage rows"):
            parse_spec(declaring("alpha_block"))


def test_a_stage_read_changes_concentrations_never_charge():
    """A read that halves the cell's K for the rates: K's membrane flux changes, the potentials
    do not (the field solve keeps the stored charges; solving on the read's amounts would move
    the cell by about 400 V)."""
    plain = parse_spec(declaring())
    k = list(plain.model.species_ids).index("K")

    def halving(state, p, *, xp):
        amount = p.amount_reference + state.amount_increment
        rows = np.zeros(amount.shape, dtype=bool)
        rows[k, 0] = True
        increment = xp.where(rows, state.amount_increment - 0.5 * amount, state.amount_increment)
        return state._replace(amount_increment=increment), True

    impl, state, p, control = host_inputs(plain)
    base = impl.readouts(state, control, p, xp=np)
    kind = planted(
        "alpha",
        "alpha_block",
        stage_read=halving,
        stage_rows=lambda declaration: (("K", "cell_0"),),
    )
    with kind_registry.scope(registry(kind)):
        impl, state, p, control = host_inputs(parse_spec(declaring("alpha_block")))
        read = impl.readouts(state, control, p, xp=np)
    np.testing.assert_allclose(read.field.potential_V, base.field.potential_V, rtol=0, atol=1e-12)
    flux = read.field.rates.membrane_flux_fmol_s[k], base.field.rates.membrane_flux_fmol_s[k]
    assert not np.allclose(*flux)


def test_a_failed_stage_read_refuses_the_row_and_the_step():
    """Valid while the kind's value is below one half: refused at binding when the initial state
    fails it; a step whose end state fails it is refused (domain_valid reads at the end)."""

    def gated(state, p, *, xp):
        return state, xp.all(state.alpha_value < 0.5)

    def book(applied, start, end, control, p, dt, *, xp):
        return {"alpha_value": end.alpha_value + 1.0}, True

    rows = dict(stage_read=gated, stage_rows=lambda declaration: ())
    with kind_registry.scope(registry(planted("alpha", "alpha_block", book=book, **rows))):
        spec = parse_spec(declaring("alpha_block"))  # The read holds at the start.
        impl, state, p, control = host_inputs(spec)
        assert impl.readouts(state, control, p, xp=np).valid
        new, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert not valid  # The end state's read failed: the step is refused, the state kept.
    assert float(new.alpha_value[0]) == 0.0

    def failing(state, p, *, xp):
        return state, xp.asarray(False)

    with kind_registry.scope(registry(planted("alpha", "alpha_block", stage_read=failing,
                                              stage_rows=lambda declaration: ()))):  # fmt: skip
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(declaring("alpha_block"))


def test_a_stage_check_sees_the_stages_total_rates_and_can_refuse():
    seen = []

    def watching(read, cell, outside, p, *, xp):
        seen.append((np.shape(cell), np.shape(outside), read.amount_increment is not None))
        return xp.all(xp.isfinite(cell))

    with kind_registry.scope(registry(planted("alpha", "alpha_block", stage_check=watching))):
        spec = parse_spec(declaring("alpha_block"))
        impl, state, p, control = host_inputs(spec)
        seen.clear()
        assert impl.readouts(state, control, p, xp=np).valid
        shapes = (state.amount_increment.shape, state.extracellular_amount_increment.shape)
        assert seen == [(*shapes, True)]
        new, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert valid and len(seen) > 2  # Readouts at the start, then every explicit stage.

    def refusing(read, cell, outside, p, *, xp):
        return xp.asarray(False)

    with kind_registry.scope(registry(planted("alpha", "alpha_block", stage_check=refusing))):
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(declaring("alpha_block"))


def test_a_kinds_conductance_and_bound_term_join_the_step_rules():
    """Gap 5 (B7 for kinds): a kind's stage conductance joins membrane_rate's per-stage refusal,
    and its definition-time bound term joins the host step checks, each at the ordinary bound."""

    def conducting(siemens):
        def stage_term(read, potentials, control, p, *, xp):
            patches = xp.where(p.membrane_active, siemens, 0.0)  # Each patch, at both ends.
            return surface_pump_v3.patch_node_conductance(patches, p, xp=xp)

        return planted("alpha", "alpha_block", stage_term=stage_term)

    for siemens, accepted in ((1e-12, True), (1e-6, False)):  # C = 1.6e-11 F, dt = 1 ms.
        with kind_registry.scope(registry(conducting(siemens))):
            spec = parse_spec(declaring("alpha_block"))
            impl, state, p, control = host_inputs(spec)
            _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert bool(valid) == accepted, siemens

    def reversing(threshold_V):
        """A slope that appears only past a membrane voltage (a pump reversed past its head):
        the stage's potentials reach stage_term (D: V_m about -21.5 mV)."""

        def stage_term(read, potentials, control, p, *, xp):
            n = p.active.size
            voltage = potentials[p.membrane_cell] - potentials[n + p.membrane_outside]
            past = xp.any(xp.abs(voltage) > threshold_V)
            patches = xp.where(p.membrane_active & past, 1e-6, 0.0)
            return surface_pump_v3.patch_node_conductance(patches, p, xp=xp)

        return planted("alpha", "alpha_block", stage_term=stage_term)

    for threshold, accepted in ((0.05, True), (0.01, False)):
        with kind_registry.scope(registry(reversing(threshold))):
            spec = parse_spec(declaring("alpha_block"))
            impl, state, p, control = host_inputs(spec)
            _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert bool(valid) == accepted, threshold

    def bounded(rate):
        return planted("alpha", "alpha_block", bound_rate=lambda spec, declaration: rate)

    steps = np.asarray([1e-3])
    with kind_registry.scope(registry(bounded(500.0))):
        surface_pump_v3.check_steps(parse_spec(declaring("alpha_block")), steps, None)
    with kind_registry.scope(registry(bounded(2000.0))):
        with pytest.raises(ConfigError, match="a declared kind's explicit-rate bound"):
            surface_pump_v3.check_steps(parse_spec(declaring("alpha_block")), steps, None)


def test_declared_kinds_are_refused_under_rk4():
    """@3 refuses declared kinds under RK4, fail-closed (the core's review of refusal 4 version 1.1,
    finding 6; the lead's ruling): the step guards above (the definition-time bound term, the
    per-stage rule, the end-of-step bookings) are the IMEX step's, and an RK4 step runs none of
    them (its step checks read no kind's bound term). A kind whose bound term the IMEX checks
    refuse is refused under RK4 at the definition; the world without it still parses and passes
    its RK4 step checks (D's NaV1.2 at 2.5 us), and the kind is admitted and held under IMEX."""

    def rk4(raw):
        out = copy.deepcopy(raw)
        out["execution"].update(solver="rk4", dt=2.5e-6, max_steps=2000)  # 1600 steps to 4 ms.
        return out

    def bounded(rate):
        return planted("alpha", "alpha_block", bound_rate=lambda spec, declaration: rate)

    with kind_registry.scope(registry(bounded(2e5))):
        refusal = re.escape("(tests.kind.alpha@1) require an IMEX solver")
        with pytest.raises(ConfigError, match=refusal):
            parse_spec(rk4(declaring("alpha_block")))
        imex = parse_spec(declaring("alpha_block"))  # Admitted under IMEX ...
        with pytest.raises(ConfigError, match="a declared kind's explicit-rate bound"):
            surface_pump_v3.check_steps(imex, np.asarray([1e-4]), None)  # ... and held there.
        plain = parse_spec(rk4(declaring()))  # No kind: RK4 as before.
        assert plain.execution.solver == "rk4" and not plain.model.kinds
        surface_pump_v3.check_steps(plain, np.asarray([2.5e-6]), None)


def test_stage_values_give_running_extrema_over_the_steps_stages():
    """Gap 7: a kind's stage values, reduced over the step's explicit stages from the start's
    value as its stage_extrema say; an undeclared reduction is refused."""
    seen = []

    def values(read, cell, outside, p, *, xp):
        seen.append(len(seen))
        return {"alpha_value": xp.where(p.active, 3.0 + len(seen), 0.0)}  # 4, 5, ... by stage.

    for how, expected in (("max", 5.0), ("min", 0.0)):  # Two explicit stages (ARS(2,2,2)).
        kind = planted(
            "alpha", "alpha_block", stage_values=values, stage_extrema=(("alpha_value", how),)
        )
        with kind_registry.scope(registry(kind)):
            spec = parse_spec(declaring("alpha_block"))
            impl, state, p, control = host_inputs(spec)
            seen.clear()
            new, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert valid and len(seen) == 2
        assert float(new.alpha_value[0]) == expected, how
    with kind_registry.scope(registry(planted("alpha", "alpha_block", stage_values=values))):
        spec = parse_spec(declaring("alpha_block"))
        impl, state, p, control = host_inputs(spec)
        with pytest.raises(ValueError, match="declared extremum"):
            impl.imex_step(state, spec.execution.dt, control, p, xp=np)


def face_free(*, kind=True, contact_F=None, channel=None):
    """FR-1's W as a bare @3 definition: cell_0 with its wall patch (patch 0, 1 pF) on the held
    bath, and contact_0 (patch 1, 0.1 pF or contact_F) alone on the floating node ecs_0. kind: the
    planted kind's block; channel: (patch ID, S), an always-open K population of that slope."""
    from validation.tissue import secreted_species_fixtures as fx
    from validation.tissue import surface_pump_v3_fixtures as v3fx

    raw = fx.face_free(end=0.004)
    m = raw["model"]
    m["id"] = "cells.model.resolved_pump_tissue@3"
    m.pop("inner_model")
    m.pop("operators")
    if kind:
        m["alpha_block"] = {"rate": 1.0}
    if contact_F is not None:
        m["membranes"][1]["capacitance_F"] = contact_F
    if channel is not None:
        patch, siemens = next(p for p in m["membranes"] if p["id"] == channel[0]), channel[1]
        slope = F * F / (R * m["temperature_K"]) * patch["area_m2"] * fx.BATH_mM["K"]
        m["channels"] = [v3fx.channel("leak", 0, KLEAK_LAW_ID, "K", siemens / slope, 1.0, ())]
        m["channels"][0]["membrane_id"] = patch["id"]
        raw["experiment"]["channel_controls"] = [
            dict(channel_id="leak", schedule=[dict(time=0.0, availability=1.0)])
        ]
        raw["execution"]["channel_capacity"] = 1
    return raw


def on_patch(k, siemens):
    """A planted kind with a slope on one patch, at both of the patch's ends."""

    def stage_term(read, potentials, control, p, *, xp):
        hosted = xp.arange(p.membrane_active.size) == k
        patches = xp.where(hosted & p.membrane_active, siemens, 0.0)
        return surface_pump_v3.patch_node_conductance(patches, p, xp=xp)

    return planted("alpha", "alpha_block", stage_term=stage_term)


WALL, CONTACT = 0, 1


def test_a_face_free_compartments_free_node_is_held_to_the_stage_rule():
    """Gap 5 per patch: a charged slope on a face-free compartment's patch (FR-1's W: cell_0 with
    1.1 pF of patches, its node ecs_0 with the contact patch's 0.1 pF only) is held to that
    patch's capacitance. At 5e-10 S and dt = 1 ms the row is 5: refused, where the slope over the
    cell's patches together (0.45) would have passed it; 5e-11 S is accepted."""
    from validation.tissue import secreted_species_fixtures as fx

    for siemens, accepted in ((5e-11, True), (5e-10, False)):
        with kind_registry.scope(registry(on_patch(CONTACT, siemens))):
            spec = parse_spec(face_free())
            impl, state, p, control = host_inputs(spec)
            assert bool(surface_pump_v3.free_outside_nodes(p, xp=np)[1])  # ecs_0 is free.
            rate = impl.membrane_rate(state, control, p, xp=np, potentials=np.zeros(3))
            _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert bool(valid) == accepted, (siemens, rate)
        assert rate == pytest.approx(siemens / fx.CONTACT_C_F, rel=1e-9)  # The patch's row.


@pytest.mark.parametrize(
    "mover, host, contact_F",
    [
        ("kind", CONTACT, 1e-11),  # Read once, at the cell too, the slope would bind at its wall.
        ("channel", CONTACT, 1e-13),  # Dropped, or over the cell's patches, it would be admitted.
        ("kind", WALL, 3.3e-12),  # Beside a store of 3.3 times the wall's capacitance.
        ("channel", WALL, 3.3e-12),
    ],
)
def test_the_stage_rule_holds_a_slope_over_the_capacitance_it_relaxes(mover, host, contact_F):
    """Gap 5 per patch (§8.3): a slope on a face-free compartment's patch, the kinds' or an open
    channel's with no kind declared, relaxes that patch's voltage alone, so its row is the patch's
    and its cell's is 0; a slope on the cell's held patch relaxes the cell's against the held
    patch's capacitance, the store's left out. At twice the bound the step is refused, at half
    admitted."""
    farads = 1e-12 if host == WALL else contact_F
    for factor, accepted in ((0.5, True), (2.0, False)):
        siemens = factor * surface_pump_v3.EXPLICIT_STEP_BOUND * farads / 1e-3
        kinds = registry(on_patch(host, siemens)) if mover == "kind" else registry()
        channel = (("wall_cell_0", "contact_0")[host], siemens) if mover == "channel" else None
        with kind_registry.scope(kinds):
            raw = face_free(kind=mover == "kind", contact_F=contact_F, channel=channel)
            impl, state, p, control = host_inputs(parse_spec(raw))
            assert impl.structure.floating_nodes
            assert bool(surface_pump_v3.free_outside_nodes(p, xp=np)[1])  # ecs_0 floats.
            rows = impl.charge_rows(state, control, p, xp=np, potentials=np.zeros(3))
            rate = impl.membrane_rate(state, control, p, xp=np, potentials=np.zeros(3))
            _, valid = impl.imex_step(state, 1e-3, control, p, xp=np)
        expected = siemens / farads
        assert rate == pytest.approx(expected, rel=1e-12)
        patches = [0.0, expected] if host == CONTACT else [0.0, 0.0]
        assert rows.patch == pytest.approx(patches, rel=1e-12, abs=0)
        assert rows.cell == pytest.approx([0.0 if host == CONTACT else expected], rel=1e-12, abs=0)
        assert bool(valid) == accepted, factor


def test_fr4s_movers_charge_the_lumens_patch_and_not_the_cells_row():
    """FR-4's world: every mover, the K+ route, the proton pump and the leak, sits on the lumen's
    bounding patch, and the plasma patch is silent. So the cell's row is exactly 0 and the rate is
    the bounding patch's; read once, at the cell too, the pump's and the leak's slopes would stand
    in the cell's row. The pump's own definition-time term is its slope over its patch's
    capacitance, on the bounding patch (loose) as on the plasma patch (held, the cell's only one),
    in both of the transporter's layouts."""
    from cells.kinds import transporter
    from validation.compartment_ph_engine import definitions as defs

    def world(patch=defs.BOUNDING, general=False):
        raw = defs.development_world(defs.fr4_world())  # 0.3 s to parse.
        pump = raw["model"]["transporters"][0]
        pump["patch"] = patch
        if general:  # The same pump on the population axis.
            fuel, fuel_roles = pump.pop("fuel"), ("ATP", "ADP", "Pi")
            parameters = {k: fuel[k] for k in ("ph_ref", "ph_band")}
            parameters |= {k: pump.pop(k) for k in ("stoichiometry", "km_role_mM", "km_atp_mM")}
            pump.update(
                host=pump.pop("patch"),
                orientation=dict(N="a"),
                roles=dict(zip(fuel_roles, fuel["rows"], strict=True), proton=pump.pop("role")),
                parameters=parameters,
                held_rows=[[role, "N"] for role in fuel_roles],
            )
        return parse_spec(raw)

    spec = world()
    impl, state, p, control = host_inputs(spec)
    phi = impl.readouts(state, control, p, xp=np).field.potential_V
    rows = impl.charge_rows(state, control, p, xp=np, potentials=phi)
    bounding = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    assert rows.cell.tolist() == [0.0]
    assert np.flatnonzero(rows.patch).tolist() == [bounding]
    rate = float(impl.membrane_rate(state, control, p, xp=np, potentials=phi))
    assert rate == float(rows.patch[bounding]) > 0

    def slope(spec, patch):
        rate = transporter.bound_rate(spec, dict(spec.model.kinds)[transporter.KIND_ID])
        return rate * next(m.capacitance_F for m in spec.model.membranes if m.id == patch)

    expected = slope(spec, defs.BOUNDING)
    assert expected > 0
    for patch, general in ((defs.PLASMA, False), (defs.BOUNDING, True)):
        found = slope(world(patch, general), patch)
        assert found == pytest.approx(expected, rel=1e-12, abs=0), (patch, general)


def test_a_kind_that_charges_a_cell_with_no_held_patch_is_refused_by_name():
    """cell_1's only patch faces the floating node it shares with cell_0, so a kind's slope there
    that is not that patch's (a route on a junction, say) has no capacitance to be held to. It is
    refused at binding, naming the cell and the kind; a slope that opens later makes the row
    infinite and refuses the step; a world whose cells are held is not read."""
    from validation.tissue import secreted_species_fixtures as fx

    def world(*, held):
        raw = fx.world(
            cells=(("cell_0", 1.0), ("cell_1", 1.0)),
            contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
            faces=(),
        )
        m, e = raw["model"], raw["experiment"]
        m["id"] = "cells.model.resolved_pump_tissue@3"
        m.pop("inner_model")
        m.pop("operators")
        m["alpha_block"] = {"rate": 1.0}
        if not held:
            m["membranes"] = [p for p in m["membranes"] if p["id"] != "wall_cell_1"]
            e["membrane_controls"] = [
                c for c in e["membrane_controls"] if c["membrane_id"] != "wall_cell_1"
            ]
            raw["execution"]["membrane_capacity"] = len(m["membranes"])
        return raw

    calls = []

    def charging(opens):
        def stage_term(read, potentials, control, p, *, xp):
            calls.append(p)
            slope = xp.where(read.alpha_value[0] >= opens, 1e-12, 0.0)
            nodes = p.active.size + p.outside_active.size
            return xp.where(xp.arange(nodes) == 1, slope, 0.0)  # cell_1, by no patch of its own.

        return planted("alpha", "alpha_block", stage_term=stage_term)

    with kind_registry.scope(registry(charging(0.0))):
        with pytest.raises(
            ConfigError, match="Cell cell_1 has no held patch.*kind tests.kind.alpha@1, not through"
        ):
            parse_spec(world(held=False))
        calls.clear()
        parse_spec(world(held=True))
        assert calls == []  # A world with no such cell pays nothing for the check.
    with kind_registry.scope(registry(charging(0.5))):
        impl, state, p, control = host_inputs(parse_spec(world(held=False)))
        for value, accepted in ((0.0, True), (1.0, False)):
            at = state._replace(alpha_value=np.full(state.alpha_value.shape, value))
            rate = impl.membrane_rate(at, control, p, xp=np, potentials=np.zeros(4))
            assert rate == (0.0 if accepted else np.inf)
            _, valid = impl.imex_step(at, 1e-3, control, p, xp=np)
            assert bool(valid) == accepted


def test_a_held_row_has_one_writer():
    """Gap 8: a row a kind holds is moved by nothing in the step: refused where a route or another
    kind moves it, admitted where nothing does."""
    from cells.registry.inventory_species import add_inventory_species
    from tests import kind_fixtures

    def holding(species):
        return planted("alpha", "alpha_block", held_rows=lambda d: ((species, "cell_0"),))

    with kind_registry.scope(registry(holding("K"))):
        with pytest.raises(ConfigError, match="holds K at cell_0, which .* moves in the step"):
            parse_spec(declaring("alpha_block"))
    raw = add_inventory_species(
        declaring("alpha_block"), "B", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
    )
    with kind_registry.scope(registry(holding("B"))):
        parse_spec(raw)  # Nothing moves B: admitted.
    with kind_registry.scope(kind_fixtures.registry(holding("B"))):
        with pytest.raises(ConfigError, match="which tests.kind.exchange@1 moves"):
            parse_spec(kind_fixtures.declare(raw))


def test_a_kinds_stored_term_joins_the_energy_ledger():
    kind = planted(
        "alpha",
        "alpha_block",
        ledger_terms=lambda state, p, *, xp: {"stored_pJ": state.alpha_value},
    )
    with kind_registry.scope(registry(kind)):
        impl, state, p, _ = host_inputs(parse_spec(declaring("alpha_block")))
        before = impl.balances(state, p)["energy"]
        after = impl.balances(state._replace(alpha_value=state.alpha_value + 2.5), p)["energy"]
    assert after - before == pytest.approx(2.5 * len(state.alpha_value), rel=1e-12)


def test_bookings_see_one_end_state_and_write_only_their_own_fields():
    seen = {}

    def probe(name, ok=True):
        def book(applied, start, end, control, p, dt, *, xp):
            seen[name] = end
            seen[name + "_control"] = control
            return {f"{name}_value": getattr(end, f"{name}_value") + dt}, ok

        return planted(name, f"{name}_block", book=book)

    with kind_registry.scope(registry(probe("alpha"), probe("beta"))):
        spec = parse_spec(declaring("alpha_block", "beta_block"))
        impl, state, p, control = host_inputs(spec)
        new, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert valid
    assert seen["alpha"] is seen["beta"]  # One end state for every kind: bookings commute.
    assert seen["alpha_control"] is seen["beta_control"] is control  # The step's held control.
    assert float(new.alpha_value[0]) == float(new.beta_value[0]) == spec.execution.dt

    with kind_registry.scope(registry(probe("alpha"), probe("beta", ok=False))):
        spec = parse_spec(declaring("alpha_block", "beta_block"))
        impl, state, p, control = host_inputs(spec)
        new, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert not valid  # A booking that refuses (a negative exact share) refuses the step.
    assert float(new.alpha_value[0]) == 0.0

    def trespass(applied, start, end, control, p, dt, *, xp):
        return {"amount_increment": end.amount_increment}, True

    with kind_registry.scope(registry(planted("alpha", "alpha_block", book=trespass))):
        spec = parse_spec(declaring("alpha_block"))
        impl, state, p, control = host_inputs(spec)
        with pytest.raises(ValueError, match="writes only its own state fields"):
            impl.imex_step(state, spec.execution.dt, control, p, xp=np)


def test_hook_order_is_named_apart_from_field_order(monkeypatch):
    calls = []
    kinds = registry(
        reader("alpha", "alpha_block", (("K", "cell_0"),), calls),
        reader("beta", "beta_block", (("Na", "cell_0"),), calls),
    )
    with kind_registry.scope(kinds):
        spec = parse_spec(declaring("beta_block", "alpha_block"))
        impl, state, p, control = host_inputs(spec)
        fields = impl.STATE_TYPE._fields
        assert fields[-2:] == ("alpha_value", "beta_value")  # Field order: canonical.
        calls.clear()
        impl.readouts(state, control, p, xp=np)
        # Each evaluation of the reads (the stage entry, then domain_valid) runs in hook order,
        # which in version 1 equals the field order.
        assert calls and calls == ["alpha", "beta"] * (len(calls) // 2)
        monkeypatch.setattr(
            surface_pump_v3,
            "hook_order",
            lambda structure: tuple(reversed([k for k, _ in structure.kinds])),
        )
        calls.clear()
        impl.readouts(state, control, p, xp=np)
        assert calls and calls == ["beta", "alpha"] * (len(calls) // 2)  # Another hook order...
        assert surface_pump_v3.kind_types(impl.structure).STATE_TYPE._fields == fields
        assert surface_pump_v3.kind_types(impl.structure).STATE_TYPE is impl.STATE_TYPE
        # ...moves no field, so no snapshot layout or compile-key tree.


def test_check_path_hooks_must_trace_on_the_device():
    def branching(state, p, *, xp):
        if state.alpha_value[0] >= 0:  # A value branch: fine on the host, not traceable.
            return xp.asarray(True)
        return xp.asarray(False)

    def unknown_role(state, p, *, xp):
        return {"momentum": xp.zeros(())}

    def per_cell(state, p, *, xp):
        return xp.isfinite(state.alpha_value)

    for hooks, message in (
        (dict(domain=branching), "domain hook does not trace on the device"),
        (dict(ledger_terms=unknown_role), r"returns unknown terms \['momentum'\]"),
        (dict(domain=per_cell), "domain hook must return one boolean"),
        (dict(control_domain=lambda c, p, *, xp: c.membrane), "control_domain hook must return"),
    ):
        with kind_registry.scope(registry(planted("alpha", "alpha_block", **hooks))):
            with pytest.raises(ConfigError, match=message):
                parse_spec(declaring("alpha_block"))
    traceable = planted(
        "alpha",
        "alpha_block",
        domain=lambda state, p, *, xp: xp.all(state.alpha_value >= 0),
        ledger_terms=lambda state, p, *, xp: {"work_pJ": state.alpha_value},
    )
    with kind_registry.scope(registry(traceable)):
        parse_spec(declaring("alpha_block"))  # Admitted.
