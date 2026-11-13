"""resolved_pump_composite@1: definitions, dispatch and the operator contract (no long runs).

* Definitions round trip; frozen @3, water@1, water@2 and replacement@1
  definitions rewrite as compositions with the frozen state, layout and control
  fields in the frozen order; get_model returns one cached implementation per
  ordered operator list, and the run identity enters the batch signature.
* Contract refusals, at parse and when a composition is built: unknown laws, a
  law twice, a required operator missing or after its dependant, a view field
  read as declared by one operator and provided by another, two providers of one
  view field, two in-step processes, an undeclared experiment key; operator
  classes that break the declarations (heat or work suffixes, RK4 modes, entity
  writes without accumulators).
"""

import copy

import jax
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.schedule import control_values as scheduled_controls
from cells.core.specs import ConfigError, parse_spec
from cells.models import (
    cell_replacement,
    pump_composite,
    surface_pump_v3,
    surface_pump_water,
    surface_pump_water_v2,
)
from cells.models import pump_composite_adapter as pump3
from cells.models.operators import OPERATORS
from cells.models.operators.contract import Operator, check_declarations
from cells.models.registry import get_model
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import pump_water_fixtures as wfx

WATER = "ideal_osmosis_linear_compliance_water@1"
SYMPORT = "k_anion_symport_mass_action@1"
REPLACEMENT = "scheduled_cell_replacement@1"


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cell(end=0.01):
    raw = wfx.heredity_cell("H", end_time=end)
    raw["experiment"]["observation_times"] = [0.0, end]
    return raw


def frozen_worlds():
    raw = cell()
    water = wfx.with_water(raw, pf_m_s=5e-4)
    sheet = rfx.heredity_sheet(1, 0, end_time=0.01)
    sheet["experiment"]["observation_times"] = [0.0, 0.01]
    t1 = 0.005
    replaced = rfx.with_replacement(
        sheet, [rfx.template_from_cell(sheet, "cell_1", "h")], [(t1, "cell_0", "h", "n1")]
    )
    return dict(
        inner=(raw, surface_pump_v3, ()),
        water=(water, surface_pump_water, (WATER,)),
        symport=(wfx.with_symport(water), surface_pump_water_v2, (WATER, SYMPORT)),
        replacement=(replaced, cell_replacement, (REPLACEMENT,)),
    )


@pytest.mark.parametrize("kind", ("inner", "water", "symport", "replacement"))
def test_frozen_definitions_rewrite_with_the_frozen_fields(kind):
    raw, frozen, laws = frozen_worlds()[kind]
    spec = parse_spec(cs.frozen_definition(raw))
    assert type(spec.model) is cs.CompositeModel
    assert cs.operator_laws(spec.model) == laws
    assert parse_spec(spec.to_dict()) == spec
    model = get_model(spec.model)
    assert model is pump_composite.implementation("resolved_pump_tissue@3", laws)
    assert model.STATE_TYPE._fields == frozen.STATE_TYPE._fields
    state, layout = model.initial_values(spec)
    frozen_spec = parse_spec(raw)
    frozen_state, frozen_layout = frozen.initial_values(frozen_spec)
    assert type(layout)._fields == type(frozen_layout)._fields
    for name in frozen.STATE_TYPE._fields:
        a, b = getattr(state, name), getattr(frozen_state, name)
        assert a.dtype == b.dtype and (a == b).all(), name
    for name in type(frozen_layout)._fields:
        a, b = getattr(layout, name), getattr(frozen_layout, name)
        assert (a == b).all() if hasattr(a, "shape") else a == b, name
    controls = cs.control_values(spec, [0.0, 0.005, 0.01])
    reference = scheduled_controls(frozen_spec, [0.0, 0.005, 0.01])
    assert controls._fields == reference._fields
    for a, b in zip(controls, reference, strict=True):
        assert a.dtype == b.dtype and (a == b).all()
    assert [c.time for c in spec.experiment.changes] == [
        c.time for c in frozen_spec.experiment.changes
    ]
    identity = model.composition_identity(spec)
    assert identity == dict(
        model="resolved_pump_composite@1",
        inner_model="resolved_pump_tissue@3",
        operators=list(laws),
    )
    assert model.batch_signature(spec.model)[:3] == (
        "resolved_pump_composite@1",
        "resolved_pump_tissue@3",
        laws,
    )


def test_batches_refuse_two_compositions():
    raw = cell()
    plain = parse_spec(cs.frozen_definition(raw))
    water = parse_spec(cs.frozen_definition(wfx.with_water(raw)))
    with pytest.raises(ConfigError, match="matching model array axes"):
        parse_batch(
            BatchSpec((WorldSpec(1, plain), WorldSpec(2, water)), 2, 10**6, 2**31).to_dict()
        )


def composite(raw, operators):
    raw = copy.deepcopy(raw)
    raw["model"]["operators"] = operators
    return raw


def test_contract_refusals_at_the_definition():
    water = cs.frozen_definition(wfx.with_symport(wfx.with_water(cell())))
    blocks = water["model"]["operators"]
    with pytest.raises(ConfigError, match="registered law"):
        parse_spec(composite(water, [dict(blocks[0], law="ideal_osmosis@0"), blocks[1]]))
    with pytest.raises(ConfigError, match="requires ideal_osmosis"):
        raw = composite(water, [blocks[1]])
        del raw["experiment"]["water_controls"]
        parse_spec(raw)
    with pytest.raises(ConfigError, match="before it"):
        parse_spec(composite(water, [blocks[1], blocks[0]]))
    with pytest.raises(ConfigError, match="same experiment key"):
        parse_spec(composite(water, [blocks[0], blocks[0], blocks[1]]))
    with pytest.raises(ConfigError, match="Declare the operator schedule"):
        raw = copy.deepcopy(water)
        del raw["experiment"]["symport_controls"]
        parse_spec(raw)
    with pytest.raises(ConfigError):  # An operator key without its operator.
        parse_spec(composite(water, [blocks[0]]))
    with pytest.raises(ConfigError, match="inner model"):
        raw = copy.deepcopy(water)
        raw["model"]["inner_model"] = "resolved_pump_tissue@2"
        parse_spec(raw)


def test_replacement_refuses_a_volume_provider():
    sheet = rfx.heredity_sheet(1, 0, end_time=0.01)
    sheet["experiment"]["observation_times"] = [0.0, 0.01]
    replaced = cs.frozen_definition(
        rfx.with_replacement(
            sheet, [rfx.template_from_cell(sheet, "cell_1", "h")], [(0.005, "cell_0", "h", "n1")]
        )
    )
    water = cs.frozen_definition(wfx.with_water(sheet))
    raw = copy.deepcopy(replaced)
    raw["model"]["operators"] = [*water["model"]["operators"], *raw["model"]["operators"]]
    raw["experiment"]["water_controls"] = water["experiment"]["water_controls"]
    with pytest.raises(ConfigError, match="reads volume as declared"):
        parse_spec(raw)


class Dummy(Operator):
    LAW_ID = "dummy_view@1"
    SPLIT = True
    RK4 = "split"
    VIEW_FIELDS = ("pump_capacity",)


class OtherDummy(Dummy):
    LAW_ID = "dummy_view@2"


class ProcessDummy(Operator):
    LAW_ID = "dummy_process@1"
    PROCESS = True


class OtherProcess(ProcessDummy):
    LAW_ID = "dummy_process@2"


def test_structure_refusals_when_a_composition_is_built():
    errors = pump_composite.structure_errors(pump3, (Dummy(), OtherDummy()))
    assert any("two providers of the view field pump_capacity" in e for e in errors)
    errors = pump_composite.structure_errors(pump3, (ProcessDummy(), OtherProcess()))
    assert any("at most one in-step membrane process" in e for e in errors)
    errors = pump_composite.structure_errors(pump3, (OPERATORS[WATER], OPERATORS[WATER]))
    assert any("appears twice" in e for e in errors)
    assert any("two owners of one state field" in e for e in errors)
    errors = pump_composite.structure_errors(pump3, tuple(OPERATORS[k] for k in (WATER, SYMPORT)))
    assert errors == []
    with pytest.raises(ConfigError, match="two providers"):
        pump_composite.Composition(pump3, (Dummy(), OtherDummy()))


def test_factor_and_reset_names_are_checked_for_every_operator():
    """Each operator's CONTROL_FACTORS and STATE_RESETS name inner fields, with or without a
    closer, whatever the operator's place (an S5a edit had scoped these checks to the last
    operator of a composition with closers; restored before landing)."""

    class BadFactor(Operator):
        LAW_ID = "bad_factor@1"
        SPLIT = True
        RK4 = "split"
        CONTROL_FACTORS = ("no_such_control",)

    class BadReset(Operator):
        LAW_ID = "bad_reset@1"
        EVENT = True
        STATE_RESETS = ("no_such_state",)

    errors = pump_composite.structure_errors(pump3, (BadFactor(), BadReset(), Dummy()))
    assert any("multiplies no_such_control" in e for e in errors)
    assert any("resets no_such_state" in e for e in errors)


def test_operator_declarations_are_checked():
    class Unbooked(Operator):
        LAW_ID = "unbooked@1"
        SPLIT = True
        RK4 = "split"
        STATE_AXES = {"x_dissipated_energy_pJ": ["cell_slot"]}

    class Unsplit(Operator):
        LAW_ID = "unsplit@1"
        SPLIT = True

    class Writer(Operator):
        LAW_ID = "writer@1"
        EVENT = True
        ENTITY_WRITES = {"amount_increment": ("nothing_owned",)}

    class Nothing(Operator):
        LAW_ID = "nothing@1"

    for bad in (Unbooked, Unsplit, Writer, Nothing):
        with pytest.raises(ValueError):
            check_declarations(bad)
    for op in OPERATORS.values():
        check_declarations(type(op))


def test_event_times_off_the_dt_grid_are_refused_for_any_event_operator():
    from dataclasses import replace

    raw, _, _ = frozen_worlds()["replacement"]
    spec = parse_spec(cs.frozen_definition(raw))
    (schedule,) = spec.experiment.operators
    (event,) = schedule.data
    shifted = cs.OperatorSchedule(schedule.law, (replace(event, time=event.time + 1e-4),))
    bad = replace(spec, experiment=replace(spec.experiment, operators=(shifted,)))
    with pytest.raises(ConfigError, match="exact multiples of dt"):
        get_model(spec.model).check_definition(bad)


# ---------------------------------------------------------------- ownership (v2 §1.2-§1.4)


class Owner(Operator):
    """A test owner: one owned field other operators may write, booked in its ledger."""

    LAW_ID = "test_owner@1"
    SPLIT = True
    RK4 = "split"
    STATE_AXES = {"owned_pL": ["cell_slot"], "owned_meter": ["cell_slot"]}
    LEDGERS = ("owned_balance",)
    LEDGER_DIAGNOSTICS = ("owned_balance_error",)
    ACCEPTS_WRITES = {"owned_pL": ("owned_balance",)}


class OwnerWriter(Operator):
    """A test writer of the owner's field, with its accumulator."""

    LAW_ID = "test_writer@1"
    EVENT = True
    STATE_AXES = {"written_pL": ["cell_slot"]}
    ENTITY_WRITES = {"owned_pL": ("written_pL",)}

    def external_ledger_terms(self, ledgers, row, p, *, xp):
        return {k: v - 1.0 for k, v in ledgers.items()}

    def external_magnitude_terms(self, magnitudes, row, p, *, xp):
        return {k: v + 2.0 for k, v in magnitudes.items()}


class ColumnThief(Operator):
    LAW_ID = "column_thief@1"
    SPLIT = True
    RK4 = "split"
    READOUT_COLUMNS = ("energy_balance_pJ_s",)


class GhostReplacer(Operator):
    LAW_ID = "ghost_replacer@1"
    SPLIT = True
    RK4 = "split"
    REPLACES = {"no_such_column": "test"}


class EarlyReader(Operator):
    LAW_ID = "early_reader@1"
    SPLIT = True
    RK4 = "split"
    VIEW_READS = ("volume",)


def test_ownership_refusals_when_a_composition_is_built():
    errors = pump_composite.structure_errors(pump3, (ColumnThief(),))
    assert any("adds the column energy_balance_pJ_s, which inner owns" in e for e in errors)
    errors = pump_composite.structure_errors(pump3, (GhostReplacer(),))
    assert any("replaces no_such_column" in e for e in errors)
    errors = pump_composite.structure_errors(pump3, (EarlyReader(),))
    assert any("reads the view volume; no earlier operator provides it" in e for e in errors)
    assert pump_composite.structure_errors(pump3, (OPERATORS[WATER], EarlyReader())) == []
    errors = pump_composite.structure_errors(pump3, (OwnerWriter(), Owner()))  # Writer first.
    assert any("writes owned_pL, which is neither inner state nor accepted" in e for e in errors)
    assert pump_composite.structure_errors(pump3, (Owner(), OwnerWriter())) == []


def test_ownership_declarations_are_checked():
    class SelfReplacer(Operator):
        LAW_ID = "self_replacer@1"
        EVENT = True
        READOUT_COLUMNS = ("mine",)
        REPLACES = {"mine": "own column"}

    class Unledgered(Owner):
        LAW_ID = "unledgered@1"
        ACCEPTS_WRITES = {"owned_pL": ("not_a_ledger",)}

    class Eventless(Operator):
        LAW_ID = "eventless@1"
        SPLIT = True
        RK4 = "split"
        STATE_AXES = {"a": ["cell_slot"], "b": ["cell_slot"]}
        ENTITY_WRITES = {"amount_increment": ("a",)}
        EVENT_REPLACES = {"amount_increment": ("a", "b")}

    class ReadsAndHolds(Operator):
        LAW_ID = "reads_and_holds@1"
        EVENT = True
        VIEW_READS = ("volume",)
        CONFLICTS_VIEW = ("volume",)

    for bad in (SelfReplacer, Unledgered, Eventless, ReadsAndHolds):
        with pytest.raises(ValueError):
            check_declarations(bad)
    check_declarations(Owner)
    check_declarations(OwnerWriter)


def test_field_map_and_column_chains_of_the_registered_compositions():
    water2 = pump_composite.implementation(pump3.MODEL_ID, (WATER, SYMPORT))
    columns = water2.FIELD_MAP["observations"]
    assert columns["energy_balance_pJ_s"] == ["inner", WATER, SYMPORT]
    assert columns["energy_balance_pJ"] == [WATER, SYMPORT]
    assert water2.FIELD_MAP["state"]["amount_increment"] == {"owner": "inner", "writers": [SYMPORT]}
    assert water2.FIELD_MAP["views"]["volume"] == {"provider": WATER, "readers": []}
    replacement = pump_composite.implementation(pump3.MODEL_ID, (REPLACEMENT,))
    assert replacement.FIELD_MAP["state"]["channel_gate"]["writers"] == [REPLACEMENT]
    for laws in ((), (WATER,), (WATER, SYMPORT), (REPLACEMENT,)):
        assert pump_composite.implementation(pump3.MODEL_ID, laws).writers_of == {}


def test_writers_terms_reach_only_the_owners_accepted_ledgers():
    from types import SimpleNamespace

    owner, writer = Owner(), OwnerWriter()
    writers = pump_composite.accepted_writers((owner, writer))
    assert writers == {Owner.LAW_ID: ((writer, ("owned_balance",)),)}
    host = SimpleNamespace(writers_of=writers)
    values = {"owned_balance": 3.0, "untouched": 5.0}
    out = pump_composite.Composition._with_writers(host, owner, values, None, None, xp=None)
    assert out == {"owned_balance": 2.0, "untouched": 5.0}
    out = pump_composite.Composition._with_writers(
        host, owner, values, None, None, xp=None, magnitudes=True
    )
    assert out == {"owned_balance": 5.0, "untouched": 5.0}


def test_the_energy_role_table_is_the_suffix_selection_for_every_composition():
    """v2 design §1.1: the energy ledger's flow bound reads a declared table (@3's heat and work
    fields from the adapter, each operator's HEAT_FIELDS and WORK_FIELDS, in state order). For
    every registered composition it is today's suffix selection, so the bounds are unchanged."""
    suffixes = ("_dissipated_energy_pJ", "_work_pJ")
    assert set(pump3.HEAT_FIELDS) == {k for k in pump3.STATE_FIELDS if k.endswith(suffixes[0])}
    assert set(pump3.WORK_FIELDS) == {k for k in pump3.STATE_FIELDS if k.endswith(suffixes[1])}
    injection = "electrode_current_injection@1"
    for laws in ((), (WATER,), (WATER, SYMPORT), (REPLACEMENT,), (injection,)):
        model = pump_composite.implementation(pump3.MODEL_ID, laws)
        fields = model.STATE_TYPE._fields
        assert model.ENERGY_FLOW_FIELDS == tuple(k for k in fields if k.endswith(suffixes)), laws
