"""Tier-1 smoke test of species_regulated_availability@1: the contract fit and every refusal.

docs/INVENTORY_COUPLING_DESIGN.md §1 (accepted 14 November 2026, rulings in §6.3). The registration
and round trip; every definition refusal of §1.11 with its message; and the operator's parts on the
bound seven-cell sheet in NumPy (no compile): the factors and their product, exactly 1 on untargeted
and switched-off elements; the exact two-state half-step; zero rates selecting the start state; the
event map (crossing record, writes, switches, counter, a stale write refused); static idleness
from the declaration alone; the summary's unrecorded final crossing; a non-finite factor refused;
a cell's prior condition, by a per-cell initial value or by a write at time 0 (FR-6, D162);
and the composition structure (every provider of volumes and closer of masks refused, §1.12).
The compiled runs are in the _runs and _bitwise files.
"""

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.inventory_species import add_inventory_species
from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import OPERATORS
from cells.models.operators import species_regulated_availability as sra
from cells.models.operators.contract import check_declarations
from cells.models.registry import get_model
from validation.tissue import cell_replacement_fixtures as crfx
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import regulated_availability_fixtures as rf

LAW = sra.LAW_ID


def base(**kwargs):
    """A valid world: a Hill factor of R on junction_0's first side, and a state of Na in cell_0
    and cell_3 (junction_0's two cells) on junction_0, side both, with a basal level."""
    raw = rf.sheet(**kwargs)
    return rf.with_coupling(
        raw,
        species=["R", "Na"],
        states=[
            rf.state(
                "s",
                ["cell_0", "cell_3"],
                [("hill_activation", "Na", 12.0, 2.0)],
                on=5.0,
                off=1.0,
                initial=0.2,
                level=0.5,
            )
        ],
        couplings=[
            rf.hill_coupling(
                "c_r", "junction", ["junction_0"], "R", "hill_inhibition", 1e-3, 1.0, side="first"
            ),
            rf.coupling(
                "c_s",
                "junction",
                ["junction_0"],
                ("state", "s"),
                "state_complement",
                side="both",
                basal=0.25,
            ),
        ],
    )


def block(raw):
    return next(b for b in raw["model"]["operators"] if b["law"] == LAW)


def test_registered_with_its_declarations():
    op = OPERATORS[LAW]
    assert check_declarations(type(op)) is type(op)
    assert op.CONTROL_FACTORS == ("junction", "channel")
    assert op.EVENT and op.SPLIT and op.RK4 == "split"
    assert not op.ENTITY_WRITES and not op.LEDGERS and not op.HEAT_FIELDS and not op.WORK_FIELDS


def test_parses_and_round_trips():
    spec = parse_spec(base())
    again = parse_spec(cs.to_dict(spec))
    assert again.model.operators == spec.model.operators
    assert again.experiment.operators == spec.experiment.operators


def _edit(path_fn):
    def make():
        raw = base()
        path_fn(raw)
        return raw

    return make


def _coupling(raw, index=0):
    return block(raw)["couplings"][index]


def _state(raw):
    return block(raw)["states"][0]


def _add_species(count):
    def make():
        raw = rf.sheet()
        for k in range(count):
            raw = add_inventory_species(
                raw, f"Z{k}", trace_mM=1e-5, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
            )
        return rf.with_coupling(
            raw,
            species=["R"],
            couplings=[
                rf.hill_coupling(
                    "c", "junction", ["junction_0"], "R", "hill_activation", 1e-3, 1.0, side="first"
                )
            ],
        )

    return make


def _replaced(branch):
    """replacement@1 replaces cell_1 at 8 ms; a coupling on junction_1 (its contact), or a state
    declared in cell_1 whose coupling reads cell_0 only."""

    def make():
        raw = crfx.heredity_sheet(radius=1, disc=0, end_time=0.02)
        raw["experiment"]["observation_times"] = [0.0, 0.02]
        template = crfx.template_from_cell(raw, "cell_1", "T")
        rep = crfx.with_replacement(raw, [template], [(0.008, "cell_1", "T", "c1_new")])
        comp = add_inventory_species(
            cs.frozen_definition(rep),
            "R",
            trace_mM=1e-3,
            diffusivity_m2_per_s=1e-10,
            floor_fmol=1e-20,
        )
        if branch == "coupling":
            return rf.with_coupling(
                comp,
                species=["R"],
                couplings=[
                    rf.hill_coupling(
                        "c",
                        "junction",
                        ["junction_1"],
                        "R",
                        "hill_activation",
                        1e-3,
                        1.0,
                        side="first",
                    )
                ],
            )
        return rf.with_coupling(
            comp,
            species=["R"],
            states=[rf.frozen("s", ["cell_0", "cell_1"], 0.5)],
            couplings=[rf.fraction("c", "junction", ["junction_0"], "s", side="first")],
        )

    return make


def _watered():
    raw = crfx.heredity_sheet(radius=1, disc=0, end_time=0.02)
    raw["experiment"]["observation_times"] = [0.0, 0.02]
    raw = add_inventory_species(
        raw, "R", trace_mM=1e-3, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    comp = cs.frozen_definition(wfx.with_water(raw))
    return rf.with_coupling(
        comp,
        species=["R"],
        couplings=[
            rf.hill_coupling(
                "c", "junction", ["junction_0"], "R", "hill_activation", 1e-3, 1.0, side="first"
            )
        ],
    )


def _identity_mismatch():
    raw = base()
    block(raw)["species"][0]["catalogue"] = dict(catalogue="cells-proteins", entry="example")
    block(raw)["species"][0]["evidence"] = "label_only"
    return rf.with_turnover(raw, "cell_0", 1.0)


REFUSALS = {
    "unknown species": (
        _edit(lambda r: block(r)["species"].append(dict(id="Q", catalogue=None, evidence=None))),
        "does not declare",
    ),
    "charged instantaneous source": (
        _edit(lambda r: _coupling(r).update(source={"species": "Na"})),
        "charged species",
    ),
    "unlisted source": (_edit(lambda r: block(r)["species"].pop(0)), "not a listed species"),
    "other operator's control": (
        _edit(lambda r: _coupling(r)["target"].update(operator="scheduled_species_turnover@1")),
        "inner model's controls only",
    ),
    "leak control": (
        _edit(lambda r: _coupling(r)["target"].update(control="membrane")),
        "admitted targets",
    ),
    "side on a channel": (
        _edit(
            lambda r: _coupling(r)["target"].update(control="channel", ids=["kir_0"], side="first")
        ),
        "channel target takes no side",
    ),
    "unknown channel": (
        _edit(
            lambda r: _coupling(r)["target"].update(control="channel", ids=["kir_99"], side=None)
        ),
        "unknown channel",
    ),
    "state not in the channel's cell": (
        _edit(
            lambda r: _coupling(r, 1)["target"].update(control="channel", ids=["kir_1"], side=None)
        ),
        "is not declared",
    ),
    "unknown junction": (
        _edit(lambda r: _coupling(r)["target"].update(ids=["junction_99"])),
        "unknown junction",
    ),
    "element twice": (
        _edit(lambda r: _coupling(r)["target"].update(ids=["junction_0", "junction_0"])),
        "names an element twice",
    ),
    "junction side": (
        _edit(lambda r: _coupling(r)["target"].update(side="sender")),
        "side is one of",
    ),
    "species through a state law": (
        _edit(
            lambda r: block(r).update(
                couplings=[
                    rf.coupling(
                        "x",
                        "junction",
                        ["junction_0"],
                        ("species", "R"),
                        "state_fraction",
                        side="first",
                    )
                ]
            )
        ),
        "through a Hill law",
    ),
    "state through a Hill law": (
        _edit(
            lambda r: block(r).update(
                couplings=[
                    dict(
                        rf.coupling(
                            "x",
                            "junction",
                            ["junction_0"],
                            ("state", "s"),
                            "hill_activation",
                            side="first",
                        ),
                        half_saturation_mM=1.0,
                        hill_coefficient=1.0,
                    )
                ]
            )
        ),
        "through a state law",
    ),
    "half-saturation zero": (
        _edit(lambda r: _coupling(r).update(half_saturation_mM=0.0)),
        "positive",
    ),
    "coefficient negative": (
        _edit(lambda r: _coupling(r).update(hill_coefficient=-1.0)),
        "positive",
    ),
    "basal one": (_edit(lambda r: _coupling(r, 1).update(basal=1.0)), "[0, 1)"),
    "negative rate": (_edit(lambda r: _state(r).update(on_rate_per_s=-1.0)), "nonnegative"),
    "initial above one": (_edit(lambda r: _state(r).update(initial=1.5)), "initial value lies in"),
    "initial per cell above one": (
        _edit(lambda r: _state(r).update(initial={"cell_0": 0.2, "cell_3": 1.5})),
        "initial value in cell_3 lies in",
    ),
    "initial missing a cell": (
        _edit(lambda r: _state(r).update(initial={"cell_0": 0.2})),
        "names each of its cells once",
    ),
    "initial in another cell": (
        _edit(lambda r: _state(r).update(initial={"cell_0": 0.2, "cell_3": 0.2, "cell_5": 0.2})),
        "names each of its cells once",
    ),
    "level above one": (
        _edit(lambda r: _state(r).update(crossing_level=2.0)),
        "crossing level lies in",
    ),
    "state without input": (_edit(lambda r: _state(r).update(inputs=[])), "at least one input"),
    "state not in the target's cell": (
        _edit(lambda r: _state(r).update(cells=["cell_0"])),
        "is not declared",
    ),
    "rate limit": (
        _edit(lambda r: _state(r).update(on_rate_per_s=900.0, off_rate_per_s=200.0)),
        "dt (k_on + k_off)",
    ),
    "switch not from zero": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0].update(
                schedule=[dict(time=0.005, enabled=1)]
            )
        ),
        "starts at 0",
    ),
    "switch value": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0].update(
                schedule=[dict(time=0.0, enabled=0.5)]
            )
        ),
        "enabled (1) or not (0)",
    ),
    "missing switch schedule": (
        _edit(lambda r: r["experiment"]["coupling_controls"].pop()),
        "its schedule",
    ),
    "switch off the dt grid": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0]["schedule"].append(
                dict(time=0.0055, enabled=0)
            )
        ),
        "exact multiple of dt",
    ),
    "switch outside the horizon": (
        _edit(
            lambda r: r["experiment"]["coupling_controls"][0]["schedule"].append(
                dict(time=0.02, enabled=0)
            )
        ),
        "inside the horizon",
    ),
    "write off the dt grid": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.0055, value=0.5)
            )
        ),
        "exact multiple of dt",
    ),
    "write outside the horizon": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.03, value=0.5)
            )
        ),
        "inside the horizon",
    ),
    "write at the horizon's end": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.02, value=0.5)
            )
        ),
        "0 <= t < end",
    ),
    "write above one": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_0", time=0.005, value=1.5)
            )
        ),
        "written value lies in",
    ),
    "two writes at one time": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].extend(
                [dict(state_id="s", cell_id="cell_0", time=0.005, value=0.5)] * 2
            )
        ),
        "two writes",
    ),
    "write to an undeclared slot": (
        _edit(
            lambda r: r["experiment"]["regulatory_writes"].append(
                dict(state_id="s", cell_id="cell_5", time=0.005, value=0.5)
            )
        ),
        "undeclared state and cell",
    ),
    "unknown key": (_edit(lambda r: _coupling(r).update(gain=2.0)), "unknown="),
    "duplicate coupling": (
        _edit(lambda r: block(r)["couplings"].append(copy.deepcopy(_coupling(r)))),
        "unique",
    ),
    "duplicate state": (
        _edit(lambda r: block(r)["states"].append(copy.deepcopy(_state(r)))),
        "state IDs are unique",
    ),
    "species listed twice": (
        _edit(lambda r: block(r)["species"].append(copy.deepcopy(block(r)["species"][0]))),
        "lists a species twice",
    ),
    "identity mismatch": (_identity_mismatch, "another identity"),
    "species cap": (_add_species(3), "at most 7 species"),
    "replaced slot": (_replaced("coupling"), "coupling c targets junction_1"),
    "state on a replaced slot": (_replaced("state"), "state s is declared in cell_1"),
    "permeant instantaneous source": (
        _edit(lambda r: r["model"]["junctions"][1]["permeability_m_per_s"].update(R=1e-9)),
        "zero membrane, junction and channel permeability",
    ),
    "volume provider": (_watered, "volume"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_refusals(case):
    make, message = REFUSALS[case]
    with pytest.raises(ConfigError, match=None) as error:
        parse_spec(make())
    assert message in str(error.value), str(error.value)


REFUSED = {  # Operator lists with each provider or closer (requirements first) and the reason.
    "water": (("ideal_osmosis_linear_compliance_water@1",), "reads volume as declared"),
    "replacement@2": (
        ("ideal_osmosis_linear_compliance_water@1", "scheduled_cell_replacement@2"),
        "reads volume as declared",
    ),
    "lumen@1": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@1", "restricted_cleft_lumen@1"),
        "reads extracellular_volume as declared",
    ),
    "lumen@2": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@2", "restricted_cleft_lumen@2"),
        "reads extracellular_volume as declared",
    ),
    "insertion@1": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@1"),
        "reads outside_active as declared",
    ),
    "insertion@2": (
        ("membrane_entity_state@1", "scheduled_membrane_insertion@2"),
        "reads outside_active as declared, but scheduled_membrane_insertion@2 closes it",
    ),
    "partition": (
        ("membrane_entity_state@1", "isopotential_partition@1"),
        "reads active as declared, but isopotential_partition@1 closes it",
    ),
    "bridge": (
        ("membrane_entity_state@1", "isopotential_partition@1", "cytoplasmic_bridge_closure@1"),
        "reads active as declared, but isopotential_partition@1 closes it",
    ),
}
ADMITTED = (  # The note's §1.12 "composes" rows (replacement@1 on slots it does not replace).
    (),
    ("electrode_current_injection@1",),
    ("membrane_entity_state@1",),
    ("scheduled_cell_replacement@1",),
    ("scheduled_species_turnover@1",),
    ("scheduled_species_exchange@1",),
    ("scheduled_species_turnover@1", "scheduled_species_exchange@1"),
    ("local_species_reactions@1",),
    ("scheduled_species_turnover@1", "local_species_reactions@1"),
)


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_providers_and_closers_of_what_it_reads_as_declared_are_refused(name):
    laws, message = REFUSED[name]
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(e.startswith(LAW) and message in e for e in errors), (order, errors)


@pytest.mark.parametrize("laws", ADMITTED, ids=lambda laws: "+".join(laws) or "alone")
def test_the_operators_version_1_composes_with_are_admitted(laws):
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert not [e for e in errors if LAW in e], (order, errors)


# ------------------------------------------------------------- the parts, in NumPy (no compile)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(base())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    return spec, model, op, state, p


def control(switch, count, value):
    return SimpleNamespace(
        coupling_switch=np.asarray(switch, dtype=float),
        regulatory_write_count=np.asarray(count, dtype=np.int64),
        regulatory_write_value=np.asarray(value, dtype=float),
    )


def _hill(x, k, n, law):
    act = x**n / (k**n + x**n)
    return act if law == "hill_activation" else 1.0 - act


def _concentration(spec, state, p, species, cell):
    row = list(spec.model.species_ids).index(species)
    col = [c.id for c in spec.model.cells].index(cell)
    amount = np.asarray(p.amount_reference)[row, col] + np.asarray(state.amount_increment)[row, col]
    return amount / np.asarray(p.volume)[col]


def test_factors_at_the_bound_state(bound):
    """junction_0 takes the product of its three routes in declared order (an inhibition of R on
    its first side, the complement of s on both sides with basal 1/4); every other junction 1."""
    spec, _, op, state, p = bound
    factors = op.control_factors(state, p, xp=np)
    assert set(factors) == {"junction"}
    junctions = [j.id for j in spec.model.junctions]
    j0 = junctions.index("junction_0")
    r = _hill(_concentration(spec, state, p, "R", "cell_0"), 1e-3, 1.0, "hill_inhibition")
    s = np.asarray(state.regulatory_state)
    assert list(s) == [0.2, 0.2]
    complement = 0.25 + 0.75 * (1.0 - 0.2)
    np.testing.assert_allclose(factors["junction"][j0], r * complement * complement, rtol=1e-14)
    others = np.delete(np.asarray(factors["junction"]), j0)
    assert np.all(others == 1.0)  # Untargeted elements select exactly 1.


def test_channel_factors_at_the_bound_state():
    """A state coupling on cell_0's Kir population: its factor is s there; every other channel 1,
    and the junction product is unchanged by the channel route."""
    raw = base()
    block(raw)["couplings"].append(
        rf.coupling("c_k", "channel", ["kir_0"], ("state", "s"), "state_fraction")
    )
    raw["experiment"]["coupling_controls"].append(
        dict(coupling_id="c_k", schedule=[dict(time=0.0, enabled=1)])
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    factors = op.control_factors(state, p, xp=np)
    assert set(factors) == {"junction", "channel"}
    channels = [c.id for c in spec.model.channels]
    k = channels.index("kir_0")
    assert factors["channel"][k] == 0.2
    assert np.all(np.delete(np.asarray(factors["channel"]), k) == 1.0)
    plain = parse_spec(base())
    plain_state, plain_p = get_model(plain.model).initial_values(plain)
    reference = op.control_factors(plain_state, plain_p, xp=np)
    assert np.array_equal(factors["junction"], reference["junction"])


def test_the_half_step_is_the_exact_two_state_solution(bound):
    spec, _, op, state, p = bound
    h = 0.5
    new, valid = op.half_step(state, h, control([1, 1], [0, 0], [0, 0]), p, xp=np)
    assert bool(valid)
    for k, cell in enumerate(("cell_0", "cell_3")):
        u = _hill(_concentration(spec, state, p, "Na", cell), 12.0, 2.0, "hill_activation")
        lam = 5.0 * u + 1.0
        target = 5.0 * u / lam
        expected = target + (0.2 - target) * np.exp(-lam * h)
        np.testing.assert_allclose(new.regulatory_state[k], expected, rtol=1e-14)
        np.testing.assert_allclose(new.regulatory_input_integral[k], u * h, rtol=1e-14)
    # The amounts are read, never written.
    assert np.array_equal(new.amount_increment, state.amount_increment)


def test_zero_rates_select_the_start_state():
    raw = base()
    for entry in block(raw)["states"]:
        entry.update(on_rate_per_s=0.0, off_rate_per_s=0.0)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    new, valid = op.half_step(state, 0.5, control([1, 1], [0, 0], [0, 0]), p, xp=np)
    assert bool(valid)
    assert new.regulatory_state.tobytes() == state.regulatory_state.tobytes()


def test_the_event_map(bound):
    """At a step start: the crossing record from the state before writes and the counter, then a
    due write, the switches copied, the counter advanced; a stale write count refuses the step."""
    _, _, op, state, p = bound
    lifted = state._replace(
        regulatory_state=np.asarray([0.6, 0.2]), coupling_step_count=np.asarray([7])
    )
    new, ok = op.event(lifted, control([0, 1], [0, 1], [0.0, 0.9]), p, xp=np)
    assert bool(ok)
    assert list(new.regulatory_crossing_step) == [7, -1]  # Level 0.5: crossed in cell_0 only.
    assert list(new.regulatory_state) == [0.6, 0.9]  # The write, after the record.
    assert list(new.regulatory_writes_applied) == [0, 1]
    assert list(new.coupling_enabled) == [0.0, 1.0]
    assert list(new.coupling_step_count) == [8]
    again, _ = op.event(new, control([0, 1], [0, 1], [0.0, 0.9]), p, xp=np)
    assert list(again.regulatory_crossing_step) == [7, 8]  # A record is kept once set.
    _, stale = op.event(state, control([1, 1], [0, 2], [0.0, 0.9]), p, xp=np)
    assert not bool(stale)


def test_switched_off_factors_are_exactly_one(bound):
    _, _, op, state, p = bound
    off = state._replace(coupling_enabled=np.zeros(2))
    factors = op.control_factors(off, p, xp=np)
    assert np.all(np.asarray(factors["junction"]) == 1.0)


def test_static_idleness_follows_the_declaration_only():
    for raw, idle in ((rf.with_coupling(rf.sheet()), True), (base(), False)):
        spec = parse_spec(raw)
        model = get_model(spec.model)
        _, p = model.initial_values(spec)
        op = next(o for o in model.operators if o.LAW_ID == LAW)
        assert op.statically_idle(p) is idle
        if idle:
            assert op.control_factors(None, p, xp=np) == {}


def test_the_summary_reports_an_unrecorded_final_crossing(bound):
    """A final row at or above a level with no record (no later step start ran the event map)."""
    spec, _, op, _, _ = bound
    _, declaration, schedule = next(e for e in cs.entries(spec) if e[0].LAW_ID == LAW)
    history = SimpleNamespace(
        regulatory_state=np.asarray([[0.2, 0.2], [0.6, 0.4]]),
        regulatory_crossing_step=np.asarray([[-1, -1], [-1, -1]], dtype=np.int64),
    )
    summary = op.summary(spec, declaration, schedule, history)
    assert summary["coupling_unrecorded_final_crossings"] == [["s", "cell_0"]]
    recorded = history.regulatory_crossing_step.copy()
    recorded[-1, 0] = 1
    history = history.__class__(
        regulatory_state=history.regulatory_state, regulatory_crossing_step=recorded
    )
    assert (
        op.summary(spec, declaration, schedule, history)["coupling_unrecorded_final_crossings"]
        == []
    )


def test_a_non_finite_factor_refuses_the_step(bound):
    _, _, op, state, p = bound
    assert bool(op.domain_valid(state, p, None, xp=np))
    rows = list(p.coupling_route_row)
    lost = np.asarray(state.amount_increment).copy()
    lost[rows[0], p.coupling_route_cell[0]] = (
        -2.0 * np.asarray(p.amount_reference)[rows[0], p.coupling_route_cell[0]]
    )
    with np.errstate(invalid="ignore"):  # The log of a negative amount: the case refused.
        assert not bool(op.domain_valid(state._replace(amount_increment=lost), p, None, xp=np))


def test_a_prior_condition_per_cell_and_by_a_write_at_time_zero():
    """A per-cell s0 binds per slot and round-trips (a number when every cell's is equal); a write
    at time 0 is no schedule change time, its count is in the control at 0, and the first step
    start's event map applies it after the crossing record."""
    raw = base()
    _state(raw).update(initial={"cell_0": 0.7, "cell_3": 0.2})
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    assert list(state.regulatory_state) == [0.7, 0.2]
    assert parse_spec(cs.to_dict(spec)).model.operators == spec.model.operators
    assert block(cs.to_dict(spec))["states"][0]["initial"] == {"cell_0": 0.7, "cell_3": 0.2}
    assert block(cs.to_dict(parse_spec(base())))["states"][0]["initial"] == 0.2

    raw = base()
    raw["experiment"]["regulatory_writes"].append(
        dict(state_id="s", cell_id="cell_0", time=0.0, value=0.7)
    )
    spec = parse_spec(raw)
    state, p = get_model(spec.model).initial_values(spec)
    _, _, schedule = next(e for e in cs.entries(spec) if e[0].LAW_ID == LAW)
    assert 0.0 not in op.schedule_times(schedule)
    c = cs.control_values(spec, [0.0])
    first = control(c.coupling_switch[0], c.regulatory_write_count[0], c.regulatory_write_value[0])
    assert list(first.regulatory_write_count) == [1, 0]
    lifted = state._replace(regulatory_state=np.asarray([0.6, 0.2]))
    new, ok = op.event(lifted, first, p, xp=np)
    assert bool(ok)
    assert list(new.regulatory_state) == [0.7, 0.2]
    assert list(new.regulatory_writes_applied) == [1, 0]
    assert list(new.regulatory_crossing_step) == [0, -1]  # From the state before the write.


def test_a_switch_change_mid_run_cuts_the_coupling():
    """§1.13's cut: a change of c_r's switch at 10 ms is a schedule change time; the control holds 1
    before it and 0 from it; the event map at that step start copies it, after which c_r's route
    gives exactly 1 and c_s's routes are unchanged."""
    raw = base()
    raw["experiment"]["coupling_controls"][0]["schedule"].append(dict(time=0.01, enabled=0))
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == LAW)
    _, _, schedule = next(e for e in cs.entries(spec) if e[0].LAW_ID == LAW)
    assert 0.01 in op.schedule_times(schedule)
    c = cs.control_values(spec, [0.0, 0.009, 0.01, 0.015])
    assert c.coupling_switch.tolist() == [[1, 1], [1, 1], [0, 1], [0, 1]]
    before = sra.route_factors(state, p, xp=np)
    at = control(c.coupling_switch[2], c.regulatory_write_count[2], c.regulatory_write_value[2])
    new, ok = op.event(state, at, p, xp=np)
    assert bool(ok) and list(new.coupling_enabled) == [0.0, 1.0]
    after = sra.route_factors(new, p, xp=np)
    for route, coupling in enumerate(np.asarray(p.coupling_route_coupling)):
        if coupling == 0:
            assert before[route] < 1.0 and after[route] == 1.0
        else:
            assert after[route] == before[route]


# ------------------------------------------------------------------ A7 and A9, at the definition


def _with_idle_operator(raw):
    raw["model"]["operators"].append(dict(law=LAW, species=[], states=[], couplings=[]))
    raw["experiment"]["coupling_controls"] = []
    raw["experiment"]["regulatory_writes"] = []
    return raw


def _lumen(version):
    from tests import membrane_insertion_fixtures as ifx

    raw = ifx.with_operators(ifx.cleft_cell(), ifx.furrow_insertion(onset=0.002))
    lumen = dict(
        law="restricted_cleft_lumen@1",
        lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=2e-6)],
    )
    raw["model"]["operators"].append(lumen)
    if version == 2:
        later = {
            "scheduled_membrane_insertion@1": "scheduled_membrane_insertion@2",
            "restricted_cleft_lumen@1": "restricted_cleft_lumen@2",
        }
        for entry in raw["model"]["operators"]:
            entry["law"] = later.get(entry["law"], entry["law"])
    return _with_idle_operator(raw)


def _replacement_over_water():
    from cells.core.cell_replacement_spec import exact_event_times

    raw = crfx.heredity_sheet(1, 0, dt=1e-3, end_time=0.02)
    raw["experiment"]["observation_times"] = [0.0, 0.02]
    (t,) = exact_event_times((10,), 1e-3)
    template = crfx.template_from_cell(raw, "cell_1", "h")
    return _with_idle_operator(crfx.over_water(raw, [template], ((t, "cell_0", "h", "n1"),)))


WATER_REASON = "reads volume as declared, but ideal_osmosis_linear_compliance_water@1 provides it"
VOLUME_PROVIDERS = {  # A7: a conserved amount with a changing volume, refused with its reason.
    "water": (_watered, WATER_REASON),
    "replacement@2 over water": (_replacement_over_water, WATER_REASON),
    "lumen@1": (
        lambda: _lumen(1),
        "reads extracellular_volume as declared, but restricted_cleft_lumen@1 provides it",
    ),
    "lumen@2": (
        lambda: _lumen(2),
        "reads extracellular_volume as declared, but restricted_cleft_lumen@2 provides it",
    ),
}


@pytest.mark.parametrize("name", sorted(VOLUME_PROVIDERS))
def test_a7_a_changing_volume_is_refused_at_the_definition(name):
    make, reason = VOLUME_PROVIDERS[name]
    with pytest.raises(ConfigError) as error:
        parse_spec(make())
    assert reason in str(error.value), str(error.value)


def test_a9_a_batch_refuses_worlds_of_another_structure():
    from cells.core.batch import BatchSpec, WorldSpec, parse_batch

    def batch(*raws):
        worlds = tuple(WorldSpec(i + 1, parse_spec(r)) for i, r in enumerate(raws))
        return parse_batch(BatchSpec(worlds, len(worlds), 10**6, 2**31).to_dict())

    first = rf.pair_world()
    varied = rf.pair_world(
        on=8.0,
        off=2.0,
        s0=(0.4, 0.1),
        level=0.3,
        half_saturation=2e-3,
        coefficient=2.0,
        basal=0.1,
        write=(0.005, 0.8),
        switch=(0.004, 0.01),
    )
    batch(first, varied)  # Parameters, s0, the level, the switch and the write are data.
    other_side = copy.deepcopy(first)
    block(other_side)["couplings"][0]["target"]["side"] = "second"
    other_law = copy.deepcopy(first)
    block(other_law)["couplings"][1]["law"] = "state_fraction"
    more_species = copy.deepcopy(first)
    block(more_species)["species"].append(dict(id="Na", catalogue=None, evidence=None))
    for other in (other_side, other_law, more_species):
        with pytest.raises(ConfigError, match="matching model array axes"):
            batch(first, other)
