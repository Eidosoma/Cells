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
  writes without accumulators, B1′'s rate-route declarations); rate routes when a
  composition is built and at the definition (an undeclared control, a source after its target).
* The operators' grid (D283 stage 2): per operator family, an event time within the clock's
  same-instant tolerance of its point k * dt is admitted and its applied copy is the k * dt
  definition; past the tolerance it is refused.
"""

import copy
import math
from types import MappingProxyType

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.batch import BatchSpec, WorldSpec, parse_batch
from cells.execution.grid import EVENT_TIME_KEYS, applied_definition
from cells.execution.schedule import control_values as scheduled_controls
from cells.models import (
    cell_replacement,
    pump_composite,
    surface_pump_v3,
    surface_pump_water,
    surface_pump_water_v2,
)
from cells.models import pump_composite_adapter as pump3
from cells.numerics.clock_instants import on_grid
from cells.operators import OPERATORS
from cells.operators.contract import Operator, Read, check_declarations, factor_reads
from cells.registry.models import get_model
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import secreted_species_fixtures as fx

WATER = "ideal_osmosis_linear_compliance_water@1"
SYMPORT = "k_anion_symport_mass_action@1"
REPLACEMENT = "scheduled_cell_replacement@1"
TURNOVER = "scheduled_species_turnover@1"
REACTIONS = "local_species_reactions@1"


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
    structure = pump3.inner_structure(spec.model)  # I2: one composition per inner structure.
    assert model is pump_composite.implementation("resolved_pump_tissue@3", laws, structure)
    assert model.inner is pump3.for_structure(structure)
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
    with pytest.raises(ConfigError, match=r"requires \S*ideal_osmosis"):
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
    # B1′'s declarations (contract._check_routes), each planted and refused by its words.
    planted = (
        (dict(ROUTABLE_CONTROLS={"not_mine": "rate"}), "maps its own control fields"),
        (dict(ROUTABLE_CONTROLS={"rate_x": "event"}), "maps its own control fields"),
        (dict(RK4="coupled"), "read in exact half-steps only"),
        (dict(PROCESS=True), "read in exact half-steps only"),
        (dict(ROUTABLE_CONTROLS={}, RATE_ROUTES=[(TURNOVER, "turnover_rate")]), "distinct"),
        (dict(ROUTABLE_CONTROLS={}, RATE_ROUTES=((TURNOVER, "x"),) * 2), "distinct"),
        (dict(ROUTABLE_CONTROLS={}, RATE_ROUTES=(("routed@1", "rate_x"),)), "its own controls"),
        (dict(ROUTABLE_CONTROLS={}, RATE_ROUTES=((TURNOVER, "turnover_rate"),)), "rate_factors"),
        (dict(FACTOR_RECORD="nowhere"), "FACTOR_RECORD is an owned state field"),
        (dict(STATE_AXES={"rec": ["one"]}, FACTOR_RECORD="rec"), "with factor_record"),
    )
    for changes, words in planted:
        bad = type("Routed", (Routed,), changes)
        with pytest.raises(ValueError, match=words):
            check_declarations(bad)
    elementless = {
        k: v for k, v in vars(Routed).items() if not k.startswith("__") and k != "routable_elements"
    }
    elementless["LAW_ID"] = "elementless@1"
    with pytest.raises(ValueError, match="defines routable_elements"):
        check_declarations(type("Elementless", (Operator,), elementless))
    check_declarations(Routed)
    check_declarations(RateSource)
    # R2's control-view reads (contract._check_scopes), planted on the coupling's @2: a reader
    # whose three control-view hooks take view=None is admitted; refused by their words, an
    # inner-stage read with no factor and no in-step process, and a hook without view=None.
    reader = dict(
        SCOPED_READS=MappingProxyType({"channel_abundance": Read("current", "inner")}),
        VIEW_READS=("channel_abundance",),
        control_factors=lambda self, state, p, *, xp, view=None: {},
        factor_valid=lambda self, state, p, *, xp, view=None: None,
        factor_record=lambda self, state, p, target, field, *, xp, view=None: None,
    )
    coupling = type(OPERATORS["species_regulated_availability@2"])
    check_declarations(type("Reader", (coupling,), reader))
    # The one registered reader: @2's population source (FR-7's part (b)).
    assert [op.LAW_ID for op in OPERATORS.values() if factor_reads(op)] == [
        "species_regulated_availability@2"
    ]
    for changes, words in (
        (dict(reader, CONTROL_FACTORS=()), "which none of its parts runs at"),
        (
            dict(reader, control_factors=lambda self, state, p, *, xp: {}),
            "its control_factors takes view=None",
        ),
        (
            dict(reader, factor_record=lambda self, state, p, target, field, *, xp, view: None),
            "its factor_record takes view=None",
        ),
    ):
        with pytest.raises(ValueError, match=words):
            check_declarations(type("Reader", (coupling,), changes))
    assert dict(OPERATORS[TURNOVER].ROUTABLE_CONTROLS) == {"turnover_rate": "rate"}
    assert dict(OPERATORS[REACTIONS].ROUTABLE_CONTROLS) == {"reaction_multiplier": "rate"}


class Routed(Operator):
    """A planted routable target (B1′): its own control rate_x, read in exact half-steps."""

    LAW_ID = "routed@1"
    SPLIT = True
    RK4 = "split"
    CONTROL_FIELDS = ("rate_x",)
    ROUTABLE_CONTROLS = MappingProxyType({"rate_x": "rate"})

    def routable_elements(self, declaration, field):
        return ()


class RateSource(Operator):
    """A planted rate-route source (B1′) on the turnover's rates: a definition's declaration is
    the tuple of routes it declares."""

    LAW_ID = "rate_source@1"
    SPLIT = True
    RK4 = "split"
    RATE_ROUTES = (("scheduled_species_turnover@1", "turnover_rate"),)

    def half_step(self, state, h, control, p, *, xp):
        return state, None

    def rate_factors(self, state, p, target, field, *, xp):
        return None

    def declared_rate_routes(self, declaration):
        return declaration


def test_rate_routes_are_checked_when_a_composition_is_built():
    """B1′ (docs/INVENTORY_COUPLING_DESIGN.md §2.1): a source's routes go to routable controls of
    their targets, and the composite wires each target's routes in declared order. A route the
    definition declares has its source before its target, in the composition. Planted, each
    refused: a route to a control the target does not declare routable (at the structure); and a
    declared route to a target before its source, to a law the composition lacks, and outside the
    source's routes (at the definition). A source that declares no route keeps any order."""
    turnover, source = OPERATORS[TURNOVER], RateSource()
    assert pump_composite.structure_errors(pump3, (source, turnover)) == []
    assert pump_composite.rate_routes((source, turnover)) == {
        turnover: ((source, "turnover_rate"),)
    }
    assert pump_composite.rate_routes((turnover,)) == {}
    assert pump_composite.structure_errors(pump3, (source,)) == []  # No target: idle.
    assert pump_composite.structure_errors(pump3, (turnover, source)) == []  # Nothing declared.
    stray = type("Stray", (RateSource,), dict(LAW_ID="stray@1", RATE_ROUTES=((TURNOVER, "x"),)))
    (error,) = pump_composite.structure_errors(pump3, (stray(), turnover))
    assert error == (
        f"stray@1 routes a rate factor to {TURNOVER}'s x, which is not one of its routable "
        "controls (ROUTABLE_CONTROLS)"
    )
    route = ((TURNOVER, "turnover_rate"),)
    check = pump_composite.rate_route_definition_errors
    assert check([(source, route), (turnover, None)]) == []
    assert check([(turnover, None), (source, ())]) == []
    assert check([(turnover, None), (source, route)]) == [
        f"rate_source@1 routes a rate factor to {TURNOVER}, which precedes it: a route's source "
        "runs before its target, so the split's halves are symmetric about it"
    ]
    assert check([(source, route)]) == [
        f"rate_source@1 routes a rate factor to {TURNOVER}, which the composition does not hold"
    ]
    assert check([(source, ((TURNOVER, "x"),)), (turnover, None)]) == [
        f"rate_source@1 declares a route to {TURNOVER}'s x, not one it routes"
    ]


class QuantityOwner(Operator):
    """A planted owner of a readable quantity (R3): level, a constant 0.25 per cell."""

    LAW_ID = "quantity_owner@1"
    SPLIT = True
    RK4 = "split"
    QUANTITIES = MappingProxyType({"level": ("cell_slot", "1")})

    def half_step(self, state, h, control, p, *, xp):
        return state, None

    def quantities(self, state, p, *, xp):
        return {"level": xp.full(p.volume.shape, 0.25)}


class QuantityReader(Operator):
    """A planted reader (R3) of the owner's level, a factor operator on @3's junctions that records
    what its hooks receive; a definition's declaration is the tuple of reads it declares."""

    LAW_ID = "quantity_reader@1"
    SPLIT = True
    RK4 = "split"
    CONTROL_FACTORS = ("junction",)
    QUANTITY_READS = MappingProxyType({"quantity_owner@1": ("level",)})
    seen = {}

    def half_step(self, state, h, control, p, *, xp):
        return state, None

    def control_factors(self, state, p, *, xp, quantities=None):
        self.seen["control_factors"] = None if quantities is None else quantities(state)
        return {"junction": xp.ones(p.junction_sender.shape)}

    def factor_valid(self, state, p, *, xp, quantities=None):
        self.seen["factor_valid"] = None if quantities is None else quantities(state)
        return None

    def declared_quantity_reads(self, declaration):
        return declaration


class PlainFactor(QuantityReader):
    """A factor operator that reads no quantity: its hooks take no quantities keyword."""

    LAW_ID = "plain_factor@1"
    QUANTITY_READS = MappingProxyType({})

    def control_factors(self, state, p, *, xp):
        self.seen["plain"] = True
        return {"junction": xp.ones(p.junction_sender.shape)}

    def factor_valid(self, state, p, *, xp):
        return None


def test_quantity_reads_are_checked_recorded_and_passed_to_readers_only():
    """R3 (FR-24; docs/OPERATOR_FEATURES_FR23_24_26_DESIGN.md §3.3): an owner declares its readable
    quantities and computes them, a reader declares what it may read. Refused: malformed
    declarations, an owner without quantities, a read of its own law; a read of a quantity the
    composed owner does not declare (at the structure); and a declared read that is not one of the
    reader's, of an owner the composition lacks, or in a route's target's half-steps with the owner
    after that target (at the definition). The field map records the reads only where reader and
    owner are composed; the composite passes the reader, alone, a function of state giving its
    owners' quantities, in its factor hooks (NumPy, no world compiled)."""
    owner, reader, plain = QuantityOwner(), QuantityReader(), PlainFactor()
    for planted in (QuantityOwner, QuantityReader, PlainFactor):
        check_declarations(planted)
    malformed = (
        (dict(QUANTITIES={"level": "cell_slot"}), "QUANTITIES maps names to"),
        (dict(QUANTITY_READS={"quantity_owner@1": "level"}), "QUANTITY_READS maps owner laws"),
        (dict(QUANTITY_READS={"quantity_reader@9": ("level",)}, LAW_ID="quantity_reader@9"),
         "reads no quantity of its own law"),
    )  # fmt: skip
    for attributes, message in malformed:
        with pytest.raises(ValueError, match=message):
            check_declarations(type("M", (QuantityReader,), attributes))
    bare = dict(LAW_ID="bare@1", SPLIT=True, RK4="split", QUANTITIES={"x": ("cell_slot", "1")})
    with pytest.raises(ValueError, match="defines quantities"):
        check_declarations(type("B", (Operator,), bare))
    assert pump_composite.structure_errors(pump3, (owner, reader)) == []
    assert pump_composite.structure_errors(pump3, (reader,)) == []  # No owner: nothing to read.
    reads = {"quantity_owner@1": ("level", "depth")}
    stray = type("Stray", (QuantityReader,), dict(LAW_ID="stray_reader@1", QUANTITY_READS=reads))
    assert pump_composite.structure_errors(pump3, (owner, stray())) == [
        "stray_reader@1 reads quantity_owner@1's depth, which it does not declare among its "
        "quantities"
    ]
    assert pump_composite.quantity_readers((owner, reader, plain)) == {reader: (owner,)}
    check = pump_composite.quantity_read_definition_errors
    level, target = ("quantity_owner@1", "level"), Routed()
    assert check([(owner, None), (reader, ((*level, None),))]) == []
    assert check([(reader, ((*level, None),)), (owner, None)]) == []  # Control view: any order.
    assert check([(owner, None), (target, None), (reader, ((*level, "routed@1"),))]) == []
    assert check([(target, None), (owner, None), (reader, ((*level, "routed@1"),))]) == [
        "quantity_reader@1 reads quantity_owner@1's level in routed@1's half-steps, but "
        "quantity_owner@1 follows routed@1: an owner whose quantity a route reads precedes the "
        "route's target, so both of its halves read the quantity after the owner's first half"
    ]
    assert check([(reader, ((*level, None),))]) == [
        "quantity_reader@1 reads quantity_owner@1's level, which the composition does not hold"
    ]
    assert check([(owner, None), (reader, (("quantity_owner@1", "depth", None),))]) == [
        "quantity_reader@1 declares a read of quantity_owner@1's depth, not one it reads"
    ]
    assert pump_composite.field_map(pump3, (owner, reader))["quantities"] == {
        "quantity_owner@1": {
            "quantities": {"level": ["cell_slot", "1"]},
            "readers": [reader.LAW_ID],
        }
    }
    for alone in ((owner,), (reader,), (owner, plain)):
        assert "quantities" not in pump_composite.field_map(pump3, alone)
    spec = parse_spec(fx.world())
    state, p = get_model(spec.model).initial_values(spec)
    control = get_model(spec.model).CONTROL_TYPE(*(v[0] for v in cs.control_values(spec, [0.0])))
    composition = pump_composite.Composition(pump3, (owner, reader, plain))
    assert composition.quantity_reader(owner, p, xp=np) is None
    assert composition.quantity_reader(plain, p, xp=np) is None
    QuantityReader.seen.clear()
    composition.control_view(control, state, p, xp=np)
    composition._control_factor_checks(state, p, xp=np)
    expected = {"quantity_owner@1": {"level": np.full(p.volume.shape, 0.25)}}
    for hook in ("control_factors", "factor_valid"):
        got = QuantityReader.seen[hook]
        assert got.keys() == expected.keys()
        assert (
            got["quantity_owner@1"]["level"].tobytes()
            == expected["quantity_owner@1"]["level"].tobytes()
        )
    assert QuantityReader.seen["plain"] is True  # Called without the keyword.


def test_event_times_off_the_dt_grid_are_refused_for_any_event_operator():
    from dataclasses import replace

    raw, _, _ = frozen_worlds()["replacement"]
    spec = parse_spec(cs.frozen_definition(raw))
    (schedule,) = spec.experiment.operators
    (event,) = schedule.data
    shifted = cs.OperatorSchedule(schedule.law, (replace(event, time=event.time + 1e-4),))
    bad = replace(spec, experiment=replace(spec.experiment, operators=(shifted,)))
    with pytest.raises(ConfigError, match="on the clock's grid"):
        get_model(spec.model).check_definition(bad)


# ---------------------------------------------------------------- the operators' grid (D283)


def _appended(raw, schedule, time, **fields):
    """(raw with a change at `time` appended to the schedule list schedule(raw), time)."""
    schedule(raw).append(dict(time=time, **fields))
    return raw, time


def _bath():
    from tests.unit import test_bath_schedule as t

    return t.definition(), t.EVENT  # 10 ms on the 1 ms clock.


def _wash():
    from tests.unit import test_wash_schedule as t

    return t.washed(), t.T_E  # 1 s on the 10 ms clock (a power of two: ulps differ either side).


def _injection():
    from tests.unit import test_current_injection_runs as t

    return t.definition([(0, 1e-12), (2, 0.0)]), 2 * t.DT


def _trafficking():
    from tests.unit import test_membrane_trafficking as t

    raw = t.one_route()
    return _appended(raw, lambda r: r["experiment"]["trafficking_controls"][0]["recycling"],
                     2e-3, rate_m2_per_s=0.0)  # fmt: skip


def _unit_turnover():
    from tests.unit import test_population_unit_turnover as t

    raw = t.definition(*t.base_routes())
    return _appended(raw, lambda r: r["experiment"]["unit_turnover_controls"][0]["schedule"],
                     2e-3, assembly_rate_per_s=1.0, removal_rate_per_s=1.0)  # fmt: skip


def _sites():
    from tests.unit import test_site_occupancy as t

    raw = t.world()
    return _appended(raw, lambda r: r["experiment"]["site_controls"][0]["schedule"], 2e-3,
                     multiplier=1.0)  # fmt: skip


def _exchange():
    from tests.unit import test_species_exchange as t

    raw = t.definition()
    return _appended(raw, lambda r: r["experiment"]["exchange_controls"][1]["schedule"], 2e-3,
                     rate=0.1)  # fmt: skip


def _turnover():
    from tests.unit import test_species_turnover as t

    raw = t.definition()
    return _appended(raw, lambda r: r["experiment"]["turnover_controls"][1]["schedule"], 2e-3,
                     rate=0.1)  # fmt: skip


def _reactions():
    from tests.unit import test_species_reactions_refusals as t
    from validation.tissue import species_reactions_fixtures as reactions

    raw = reactions.enzyme_network()
    return _appended(raw, lambda r: t.controls(r, "supply")["schedule"], 2e-3, multiplier=1.0)


def _regulated():
    from tests.unit import test_species_regulated_availability as t

    raw = t.base()
    return _appended(raw, lambda r: r["experiment"]["coupling_controls"][0]["schedule"], 2e-3,
                     enabled=0)  # fmt: skip


def _polymerisation():
    from validation.gene_regulation import worlds

    raw = worlds.a1()
    schedule = raw["experiment"]["polymerisation_controls"][0]["schedule"]
    return _appended(raw, lambda r: schedule, 4 * 0.5, value=schedule[0]["value"])


def _divided(**kwargs):
    from tests import partition_fixtures as t

    return t.divided(**kwargs), t.EVENT  # 2 ms on the 1 ms clock.


def _insertion():
    from tests import membrane_insertion_fixtures as t

    return t.with_operators(t.cleft_cell(), t.furrow_insertion(onset=2e-3)), 2e-3


def _labels():
    from tests.unit import test_neutral_arrival_labels as t

    return t.labelled(t.world()), t.TS  # A label switch, on the 1/64 s clock.


def _replacement():
    raw, _, _ = frozen_worlds()["replacement"]
    return cs.frozen_definition(raw), 0.005  # 5 ms on the 1 ms clock.


# Per operator family (each with its own grid check, or the composite's check of event operators),
# a valid world with one of the operator's event times at its point k * dt.
ON_GRID_ROWS = {
    "bath_schedule": _bath,
    "wash_schedule": _wash,
    "current_injection": _injection,
    "membrane_trafficking": _trafficking,
    "population_unit_turnover": _unit_turnover,
    "site_occupancy": _sites,
    "species_exchange": _exchange,
    "species_turnover": _turnover,
    "species_reactions": _reactions,
    "species_regulated_availability": _regulated,
    "templated_polymerisation": _polymerisation,
    "partition": _divided,
    "bridge_closure (its start with its division)": lambda: _divided(bridge=("linear", 0.004)),
    "membrane_insertion (its onset with its rate change)": _insertion,
    "cell_replacement": _replacement,
    "species_labels (a label switch)": _labels,
}


def _admitted(raw):
    """The parsed definition, through its composition's checks (where the injection's, the
    bridge's and the event operators' grid checks run)."""
    spec = parse_spec(raw)
    get_model(spec.model).check_definition(spec)
    return spec


def _ulps(time, n):
    """time moved by n ulps (up for n > 0)."""
    for _ in range(abs(n)):
        time = math.nextafter(time, math.copysign(math.inf, n))
    return time


def _retimed(raw, old, new):
    """(a copy of raw with every experiment event time equal to `old` set to `new`, how many): a
    bridge's start moves with its division's time, an insertion's onset with its rate change."""
    out, moved = copy.deepcopy(raw), []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in EVENT_TIME_KEYS and type(item) in (int, float) and item == old:
                    value[key] = new
                    moved.append(key)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(out["experiment"])
    return out, len(moved)


@pytest.mark.parametrize("family", sorted(ON_GRID_ROWS))
def test_an_event_time_within_4_ulps_of_its_point_is_that_point_for_every_operator(family):
    """D283 stage 2: an operator's event time one ulp either side of its point k * dt is admitted
    (on_grid), and the applied copy that the runner runs is the definition declared at k * dt, so
    it runs at k * dt, while the declared fingerprint stays the declared time's. Five ulps off,
    past the tolerance, it is refused in the clock's words. Parse-level (no world compiles)."""
    raw, point = ON_GRID_ROWS[family]()
    assert on_grid(point, raw["execution"]["dt"]) == point  # The row's time is a point exactly.
    exact = _admitted(raw)
    for n in (1, -1):
        near = _ulps(point, n)
        moved, count = _retimed(raw, point, near)
        assert count, "the row moves its operator's event"
        spec = _admitted(moved)
        applied, snaps = applied_definition(spec)
        assert snaps == ((near, point),)
        assert spec.fingerprint != exact.fingerprint
        assert applied.fingerprint == exact.fingerprint
    with pytest.raises(ConfigError, match="on the clock's grid"):
        _admitted(_retimed(raw, point, _ulps(point, 5))[0])


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
    # A current read of a field no operator changes reads its declared value (C1,
    # docs/OPERATOR_COMPOSITION_DESIGN.md §4.1); before a changer at its own stage it is refused
    # (C2), after it admitted.
    assert pump_composite.structure_errors(pump3, (EarlyReader(),)) == []
    errors = pump_composite.structure_errors(pump3, (EarlyReader(), OPERATORS[WATER]))
    assert errors == [
        f"early_reader@1 reads the view volume at stage split before {WATER} changes it there"
    ]
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
