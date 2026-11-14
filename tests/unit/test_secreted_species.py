"""Tier-1 tests of the secreted-species definitions (D150 version 1; host side, no compile).

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §1.3, §1.5, §2.6, §5.2, §5.5, §8 and §11.5: the inventory
helper, the 7-species cap with its reason, identity on the declarations (never in the arrays), the
version 1 composition refusals, the stationary analysis' refusal of the composite, the required
energy-guard statement, and the occupant rule (rates belong to the carrier; donor copies admitted
only with the slot's route values; schedules keyed by carrier).
"""

import copy
import re

import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.inventory_species import add_inventory_species
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import species_common, species_exchange, species_turnover
from cells.models.registry import get_model
from validation.tissue import secreted_species_fixtures as fx

EVENT = 0.003


def turnover_world(**kwargs):
    raw = fx.secreting_cell(**kwargs)
    return fx.with_turnover(
        raw,
        [("produce", "cell_0", "production"), ("clear", "ecs_0", "clearance")],
        [("produce", "cell_0", [(0.0, 1e-6)]), ("clear", None, [(0.0, 0.5)])],
    )


def pair(end=0.01):
    """Two cells joined by a junction (donor copies need one), each secreting into its node."""
    return fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5), ("face_1", "ecs_1", "bath", 1e-10, 1e-5)),
        junctions=(("junction_0", "cell_0", "cell_1"),),
        end=end,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=5e-4, ecs_1=5e-4),
    )


SECRETION = [
    ("sec_0", "contact_0", "export", "first_order"),
    ("sec_1", "contact_1", "export", "first_order"),
]


def replaced(events, rates=(0.2, 0.2), *, templates=(), schedules=(), base=None):
    base = pair() if base is None else base
    template = fx.template(base, "cell_0", "T", s_mM=2e-3)
    raw = fx.with_replacement(base, [template, fx.template(base, "cell_0", "U")], events)
    controls = [
        ("sec_0", "cell_0", [(0.0, rates[0])]),
        ("sec_1", "cell_1", [(0.0, rates[1])]),
        *schedules,
    ]
    return fx.with_exchange(raw, SECRETION, controls, templates=templates)


# ------------------------------------------------------------------ the inventory helper


def test_the_helper_declares_a_neutral_impermeant_species_at_a_trace():
    base = pair()
    m = base["model"]
    assert m["species"][-1] == dict(id="S", valence=0)
    for node in (*m["cells"], *m["extracellular"]):
        expected = dict(cell_0=1e-3, cell_1=1e-3, ecs_0=5e-4, ecs_1=5e-4).get(
            node["id"], fx.TRACE_mM
        )
        assert node["initial_amount_fmol"]["S"] == expected * node["volume_pL"]
    assert all(p["permeability_m_per_s"]["S"] == 0.0 for p in (*m["membranes"], *m["junctions"]))
    assert all(f["diffusivity_m2_per_s"]["S"] == fx.D_S for f in m["faces"])
    assert base["execution"]["material_balance_atol_fmol"]["S"] == fx.FLOOR_FMOL
    # Composite replacement templates gain the trace, or a declared loaded amount.
    template = fx.template(base, "cell_0", "T")
    del template["amounts_fmol"]["S"]
    raw = fx.with_replacement(base, [template], [(EVENT, "cell_0", "T", "c0_new")])
    raw["model"]["species"].pop()
    for node in (*raw["model"]["cells"], *raw["model"]["extracellular"]):
        del node["initial_amount_fmol"]["S"]
    for p in (*raw["model"]["membranes"], *raw["model"]["junctions"]):
        del p["permeability_m_per_s"]["S"]
    for f in raw["model"]["faces"]:
        del f["diffusivity_m2_per_s"]["S"]
    out = add_inventory_species(
        raw,
        "S",
        trace_mM=1e-9,
        diffusivity_m2_per_s=1e-10,
        floor_fmol=1e-20,
        template_amounts_fmol=dict(T=1e-4),
    )
    assert out["model"]["operators"][0]["templates"][0]["amounts_fmol"]["S"] == 1e-4
    with pytest.raises(ValueError, match="already declared"):
        add_inventory_species(out, "S", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20)
    parse_spec(out)  # The declared world is a valid definition.


# ------------------------------------------------------------------ cap, identity, composition


def test_more_than_seven_species_are_refused_with_the_reason():
    raw = turnover_world()
    for i in range(4):  # 3 ions, S and 4 more: 8 species.
        raw = add_inventory_species(
            raw, f"X{i}", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
        )
    with pytest.raises(ConfigError, match="at most 7 species per world") as error:
        parse_spec(raw)
    assert "pairwise summation at 8 or more terms" in str(error.value)
    assert "species-order adds (D148)" in str(error.value)
    seven = turnover_world()
    for i in range(3):
        seven = add_inventory_species(
            seven, f"X{i}", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
        )
    parse_spec(seven)  # Seven are admitted.


def both(turnover_identity, exchange_identity):
    """Turnover and exchange on one species, each declaring its identity."""
    raw = turnover_world()
    raw["model"]["operators"][0]["species"] = turnover_identity
    return fx.with_exchange(
        raw,
        [("sec", "contact_0", "export", "first_order")],
        [("sec", "cell_0", [(0.0, 0.1)])],
        species=exchange_identity,
    )


def test_identities_must_agree_and_never_reach_the_arrays():
    ref = fx.identity(dict(catalogue="cells-proteins@0", entry="GZMK"), "label_only")
    other = fx.identity(dict(catalogue="cells-proteins@0", entry="BMP2B"), "label_only")
    with pytest.raises(ConfigError, match="another identity"):
        parse_spec(both(ref, other))
    with pytest.raises(ConfigError, match="kind of evidence"):
        parse_spec(both(fx.identity(dict(catalogue="c", entry="e"), "rumour"), fx.identity()))
    unassigned, assigned = (
        parse_spec(both(fx.identity(), fx.identity())),
        parse_spec(both(ref, ref)),
    )
    models = [get_model(s.model) for s in (unassigned, assigned)]
    assert models[0] is models[1]
    for a, b in zip(
        models[0].initial_values(unassigned), models[1].initial_values(assigned), strict=True
    ):
        for x, y in zip(a, b, strict=True):
            assert np.asarray(x).tobytes() == np.asarray(y).tobytes()
    assert models[0].batch_signature(unassigned.model) == models[1].batch_signature(assigned.model)
    turnover = models[1].operators[0]
    entry = turnover.summary(assigned, assigned.model.operators[0], None, None)
    assert entry["turnover_species"]["S"] == dict(
        catalogue=["cells-proteins@0", "GZMK"], evidence="label_only"
    )


def test_version_1_refuses_volume_providers_area_providers_and_mask_providers():
    from tests import membrane_insertion_fixtures as mfx
    from validation.tissue import pump_water_fixtures as wfx

    base = wfx.heredity_cell("H", dt=1e-3, end_time=0.004)
    base["experiment"]["observation_times"] = [0.0, 0.004]
    water = cs.frozen_definition(wfx.with_water(base, pf_m_s=5e-4))
    water = add_inventory_species(
        water, "S", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    cell = water["model"]["cells"][0]["id"]
    with_water = fx.with_turnover(water, [("p", cell, "production")], [("p", cell, [(0.0, 1e-6)])])
    with pytest.raises(ConfigError, match="reads volume as declared"):
        parse_spec(with_water)
    cleft = mfx.with_operators(mfx.cleft_cell(), mfx.furrow_insertion())
    cleft = add_inventory_species(
        cleft, "S", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    with_insertion = fx.with_turnover(
        cleft, [("c", "cleft", "clearance")], [("c", None, [(0.0, 1.0)])]
    )
    with pytest.raises(ConfigError, match="reads outside_active as declared"):
        parse_spec(with_insertion)
    with_state = mfx.with_operators(mfx.cleft_cell())  # The membrane state alone.
    with_state = add_inventory_species(
        with_state, "S", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    with_state = fx.with_exchange(
        with_state, [("sec", "furrow", "export", "first_order")], [("sec", cell, [(0.0, 0.1)])]
    )
    with pytest.raises(ConfigError, match="reads membrane_area as declared"):
        parse_spec(with_state)


def test_the_stationary_analysis_does_not_admit_the_composite():
    """Version 1 keeps the analysis off the composite (the lead's ruling 2): its own ID check
    refuses it; per-species Newton tolerances are a recorded requirement, not code (§8)."""
    from cells.analysis import stationary

    with pytest.raises(ConfigError, match="not resolved_pump_composite@1"):
        stationary.problem(parse_spec(turnover_world()))


def normalized(text):
    return re.sub(r"\s+", " ", text)


def test_the_energy_guard_statement_is_in_both_operators_and_the_adapter_addition():
    statement = normalized(species_common.GUARD_STATEMENT)
    for doc in (
        species_turnover.__doc__,
        species_exchange.__doc__,
        adapter.species_chemical_free_energy_pJ.__doc__,
    ):
        assert statement.lower() in normalized(doc).lower()


# ------------------------------------------------------------------ the occupant rule (§5.2)


def rates_at(spec, times):
    return cs.control_values(spec, times).exchange_rate


def test_a_newcomer_takes_its_templates_rates_exactly_at_the_event_step():
    """A founder with a nonzero rate replaced by templates with other rates, zero included: the
    slot's controls switch exactly at the event step, and the founder's rate never applies after."""
    for template_rate in (0.05, 0.0):
        spec = parse_spec(
            replaced(
                [(EVENT, "cell_0", "T", "c0_new")],
                templates=[("T", {"sec_0": {"rate": template_rate}})],
            )
        )
        dt = spec.execution.dt
        values = rates_at(spec, [0.0, EVENT - dt, EVENT, EVENT + dt, 0.009])
        assert list(values[:, 0]) == [0.2, 0.2, template_rate, template_rate, template_rate]
        assert np.all(values[:, 1] == 0.2)


def test_newcomer_schedules_are_keyed_by_carrier_and_live_inside_its_life():
    later = [("sec_0", "c0_new", [(0.006, 0.4)])]
    spec = parse_spec(
        replaced(
            [(EVENT, "cell_0", "T", "c0_new")],
            templates=[("T", {"sec_0": {"rate": 0.05}})],
            schedules=later,
        )
    )
    assert list(rates_at(spec, [0.0, EVENT, 0.005, 0.006, 0.009])[:, 0]) == [
        0.2,
        0.05,
        0.05,
        0.4,
        0.4,
    ]
    for bad in (
        [("sec_0", "c0_new", [(EVENT, 0.4)])],
        [("sec_0", "cell_0", [(0.0, 0.2), (0.005, 0.3)])],
    ):
        raw = replaced(
            [(EVENT, "cell_0", "T", "c0_new")], templates=[("T", {"sec_0": {"rate": 0.05}})]
        )
        controls = raw["experiment"]["exchange_controls"]
        for route, carrier, changes in bad:
            entry = next(
                (c for c in controls if (c["route_id"], c["carrier_id"]) == (route, carrier)), None
            )
            schedule = [dict(time=t, rate=v) for t, v in changes]
            if entry is None:
                controls.append(dict(route_id=route, carrier_id=carrier, schedule=schedule))
            else:
                entry["schedule"] = schedule
        with pytest.raises(ConfigError, match="outside its life"):
            parse_spec(raw)


def test_a_template_newcomer_needs_its_rates_and_templates_need_newcomers():
    with pytest.raises(ConfigError, match="takes its rates from the template"):
        parse_spec(replaced([(EVENT, "cell_0", "T", "c0_new")]))
    with pytest.raises(ConfigError, match="no newcomer from template U"):
        parse_spec(
            replaced(
                [(EVENT, "cell_0", "T", "c0_new")],
                templates=[("T", {"sec_0": {"rate": 0.05}}), ("U", {"sec_0": {"rate": 0.05}})],
            )
        )
    with pytest.raises(ConfigError, match="not a replacement template"):
        parse_spec(
            replaced(
                [(EVENT, "cell_0", "T", "c0_new")],
                templates=[("T", {"sec_0": {"rate": 0.05}}), ("V", {"sec_0": {"rate": 0.05}})],
            )
        )


def test_an_admitted_donor_copy_keeps_the_slots_controls_across_the_event():
    spec = parse_spec(replaced([(EVENT, "cell_0", None, "c0_copy", "cell_1")]))
    values = rates_at(spec, [0.0, EVENT - spec.execution.dt, EVENT, 0.009])
    assert np.all(values == 0.2)


def test_a_donor_copy_whose_route_values_differ_is_refused():
    with pytest.raises(ConfigError, match="secretion route values differ"):
        parse_spec(replaced([(EVENT, "cell_0", None, "c0_copy", "cell_1")], rates=(0.2, 0.3)))
    base = pair()
    leaky = next(p for p in base["model"]["membranes"] if p["id"] == "wall_cell_1")
    leaky["permeability_m_per_s"]["Na"] = 1e-14
    with pytest.raises(ConfigError, match="ion route values differ"):
        parse_spec(replaced([(EVENT, "cell_0", None, "c0_copy", "cell_1")], base=base))
    raw = replaced([(EVENT, "cell_0", "R", "c0_copy", "cell_1")])
    raw["model"]["operators"][0]["templates"].append(
        dict(
            id="R",
            volume_pL=None,
            fixed_charge_equivalent_fmol=None,
            amounts_fmol=None,
            channel_gates=None,
            route_values=copy.deepcopy(fx.NO_ROUTES),
        )
    )
    raw["model"]["operators"][0]["template_capacity"] = 3
    with pytest.raises(ConfigError, match="route-only template is refused"):
        parse_spec(raw)


def test_donor_copies_between_heredity_cells_with_pumps_and_channels():
    """The ion check on a real sheet (pumps and gated channels, hashed as dataclasses): identical
    cells are admitted, and the copy is refused once the donor's rates differ from the slot's."""
    from validation.tissue import cell_replacement_fixtures as rfx

    raw = rfx.heredity_sheet(1, 0, dt=1e-3, end_time=0.01)
    raw["experiment"]["observation_times"] = [0.0, 0.01]
    events = [(EVENT, "cell_0", None, "c1", "cell_3")]
    raw = rfx.with_replacement(raw, [rfx.template_from_cell(raw, "cell_1", "h")], events)
    raw = add_inventory_species(
        cs.frozen_definition(raw), "S", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    for rates, admitted in (((0.1, 0.1), True), ((0.1, 0.2), False)):
        world = fx.with_turnover(
            raw,
            [("clear_0", "cell_0", "clearance"), ("clear_3", "cell_3", "clearance")],
            [("clear_0", "cell_0", [(0.0, rates[0])]), ("clear_3", "cell_3", [(0.0, rates[1])])],
        )
        if admitted:
            parse_spec(world)
        else:
            with pytest.raises(ConfigError, match="secretion route values differ"):
                parse_spec(world)


REFERENCE = fx.identity(dict(catalogue="cells-proteins@0", entry="SECRETED"), "model")


def full_world():
    """Both operators, a replacement template with rates, a newcomer's own schedule, a saturable
    route with K_M changing, a node schedule change and a catalogue identity."""
    raw = replaced(
        [(EVENT, "cell_0", "T", "c0_new")],
        templates=[("T", {"sec_0": {"rate": 0.05}})],
        schedules=[("sec_0", "c0_new", [(0.008, 0.4)])],
    )
    block = raw["model"]["operators"][1]
    block["species"] = copy.deepcopy(REFERENCE)
    block["routes"].append(
        dict(id="sink_1", species="S", patch="contact_1", direction="import", law="saturable")
    )
    raw["experiment"]["exchange_controls"].append(
        dict(
            route_id="sink_1",
            carrier_id="cell_1",
            schedule=[
                dict(time=0.0, rate=1e6, saturation_mM=5e-4),
                dict(time=0.004, rate=2e6, saturation_mM=1e-3),
            ],
        )
    )
    return fx.with_turnover(
        raw,
        [("produce", "cell_0", "production"), ("clear", "ecs_1", "clearance")],
        [("produce", "cell_0", [(0.0, 1e-6)]), ("clear", None, [(0.0, 0.5), (0.005, 0.7)])],
        templates=[("T", {"produce": 2e-6})],
        species=copy.deepcopy(REFERENCE),
    )


def test_the_definition_round_trips():
    """Snapshots and rebind re-parse spec.to_dict(): it must give the same definition."""
    spec = parse_spec(full_world())
    again = parse_spec(spec.to_dict())
    assert again == spec
    assert again.to_dict() == spec.to_dict()


@pytest.mark.parametrize("operator", ["turnover", "exchange"])
def test_each_operator_refuses_more_than_seven_species(operator):
    base = fx.secreting_cell()
    if operator == "turnover":
        routes, controls = [("p", "cell_0", "production")], [("p", "cell_0", [(0.0, 1e-6)])]
        raw, law = fx.with_turnover(base, routes, controls), fx.TURNOVER
    else:
        routes = [("s", "contact_0", "export", "first_order")]
        raw = fx.with_exchange(base, routes, [("s", "cell_0", [(0.0, 0.1)])])
        law = fx.EXCHANGE
    for i in range(4):
        raw = add_inventory_species(
            raw, f"X{i}", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
        )
    with pytest.raises(ConfigError, match=re.escape(law) + " admits at most 7 species"):
        parse_spec(raw)


@pytest.mark.parametrize(
    ("operator", "route"),
    [("turnover", "membrane"), ("exchange", "membrane"), ("turnover", "junction")],
)
def test_a_species_with_a_membrane_or_junction_route_is_refused(operator, route):
    """@3's explicit-rate bound covers a neutral species on faces alone (on membranes and junctions
    it bounds the z^2-weighted charge relaxation), so version 1 refuses an inventory species with
    nonzero membrane or junction permeability, with the reason (the lead's question from the
    D152 review)."""
    base = pair()
    if route == "membrane":
        patch = next(p for p in base["model"]["membranes"] if p["id"] == "contact_1")
        patch["permeability_m_per_s"]["S"] = 1e-9
    else:
        base["model"]["junctions"][0]["permeability_m_per_s"]["S"] = 1e-9
    if operator == "turnover":
        raw = fx.with_turnover(
            base, [("p", "cell_0", "production")], [("p", "cell_0", [(0.0, 1e-6)])]
        )
    else:
        raw = fx.with_exchange(
            base, [("s", "contact_0", "export", "first_order")], [("s", "cell_0", [(0.0, 0.1)])]
        )
    expected = "contact_1" if route == "membrane" else "junction_0"
    with pytest.raises(ConfigError, match="zero membrane, junction and channel permeability") as e:
        parse_spec(raw)
    assert expected in str(e.value) and "no material-rate bound" in str(e.value)
    parse_spec(without_permeability(raw))  # The same world with the routes at zero is admitted.


def without_permeability(raw):
    out = copy.deepcopy(raw)
    for p in (*out["model"]["membranes"], *out["model"]["junctions"]):
        p["permeability_m_per_s"]["S"] = 0.0
    return out


def test_padded_capacities_and_a_species_scale_energy_negative_control():
    """With every capacity padded, both half-steps leave the padding at zero and close every host
    check; a misbooked work far below the ions' scale is caught by the energy ledger of this
    species-only world (its flows are the species' own)."""
    from types import SimpleNamespace

    from cells.core.errors import NumericalError

    raw = full_world()
    x = raw["execution"]
    for name in ("capacity", "extracellular_capacity", "membrane_capacity", "face_capacity"):
        x[name] += 1
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    _, exchange, turnover = model.operators
    rates = SimpleNamespace(turnover_rate=np.array([1e-6, 0.5]))
    state, ok = turnover.half_step(state, 5e-4, rates, p, xp=np)
    assert ok
    rates = SimpleNamespace(
        exchange_rate=np.array([0.2, 0.2, 1e6]), exchange_saturation_mM=np.array([0, 0, 5e-4])
    )
    state, ok = exchange.half_step(state, 5e-4, rates, p, xp=np)
    assert ok
    assert np.all(state.amount_increment[:, -1] == 0.0)  # The padded cell slot.
    assert np.all(state.extracellular_amount_increment[:, -1] == 0.0)  # The padded node.
    model.check_values(state, spec, steps=[1])
    misbooked = state.turnover_work_pJ + 1e-7 * (np.arange(state.turnover_work_pJ.size) == 0)
    with pytest.raises(NumericalError, match="energy"):
        model.check_values(state._replace(turnover_work_pJ=misbooked), spec, steps=[1])


def test_a_batch_refuses_worlds_with_different_route_structures():
    """The batch signature carries the static route structure (§7); rates are per-world data."""
    from cells.core.batch import parse_batch

    a = turnover_world()
    b = fx.with_turnover(
        fx.secreting_cell(), [("clear", "ecs_0", "clearance")], [("clear", None, [(0.0, 0.5)])]
    )
    c = copy.deepcopy(a)
    c["experiment"]["turnover_controls"][1]["schedule"][0]["rate"] = 0.9

    def batch(*worlds):
        execution = dict(
            mapping="lax_map", max_worlds=4, max_padded_steps=10**6, max_working_bytes=2**31
        )
        return parse_batch(
            dict(
                schema_version=1,
                kind="independent_worlds",
                worlds=[dict(world_id=i + 1, simulation=w) for i, w in enumerate(worlds)],
                execution=execution,
            )
        )

    batch(a, c)
    with pytest.raises(ConfigError, match="matching model array axes"):
        batch(a, b)
