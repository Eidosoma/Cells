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
