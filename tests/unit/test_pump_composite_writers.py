"""The composite's admission of operators' in-step writers beside declared kinds.

docs/INNER_MODEL_V4_DESIGN.md §7.4 (k) gap 8 and §7.5 version 1; the lead's rulings (15 November):
the core's binding refuses inner movers by node and leaves the operators' writers to the
composite. An operator's in-step process declares its writers by node kind (the contract's
moves_in_step), so it is taken to move its species at every node of that kind.
- Gap 8, one writer: an operator that writes a row a kind holds is refused, naming the kind, the
  row and the operator; on the other node kind or another species it is admitted.
- §7.5 version 1: an operator that writes a row an exact-booked passive route moves (the bound
  passive_exact, the kind's own fixpoint) is refused, naming the operator, the route and the row;
  on a tableau-booked route's row or an unrelated row it is admitted. (Marking such a route
  tableau-booked instead needs a core seam, queued after the landing.)
- Without a declared kind, or without an in-step process, neither check is made.

The planted operator `tests.operator.writer@1` is an in-step process that moves nothing and declares the
rows it writes; it is registered for each test only.
"""

import dataclasses
import re
from typing import NamedTuple

import jax
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes
from cells.models import pump_composite
from cells.models.surface_pump_v3 import MembraneProcess
from cells.operators import OPERATORS, contract
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import secreted_species_fixtures as fx

WRITER = "tests.operator.writer@1"
HELD = "F"  # The planted kind's held species: moved by nothing in the inner step at a cell.
P = 100.0 / (1e15 * fx.CONTACT_AREA_M2 * 2.0)  # The closed pair's route, k = 100/s.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


class Declared(NamedTuple):
    law: str
    rows: tuple  # ((species, "cell" | "outside"), ...): the rows it declares it writes.


class Writer(contract.Operator):
    """An in-step process that moves nothing and declares the rows it writes."""

    LAW_ID = WRITER
    PROCESS = True

    def parse(self, raw, base, inner_model):
        return Declared(self.LAW_ID, tuple((row["species"], row["kind"]) for row in raw["rows"]))

    def to_dict(self, declaration, base):
        rows = [dict(species=s, kind=k) for s, k in declaration.rows]
        return dict(law=self.LAW_ID, rows=rows)

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return {}, {}

    def moves_in_step(self, spec, declaration):
        return declaration.rows

    def process(self, control, p):
        def none(ci, co, volume, voltage, *, xp):
            return MembraneProcess(xp.zeros_like(ci), xp.zeros_like(voltage), True)

        return none


class Event(contract.Operator):
    """Not an in-step process: its moves_in_step is never read."""

    LAW_ID = "tests.operator.event_writer@1"
    EVENT = True

    def moves_in_step(self, spec, declaration):
        return declaration.rows


def declared(*rows):
    return Declared(WRITER, tuple(rows))


@pytest.fixture
def writer(monkeypatch):
    monkeypatch.setitem(OPERATORS, WRITER, Writer())


def with_writer(raw, *rows):
    """A composite definition of raw (@3 or composite) with the planted writer declared last."""
    out = cs.frozen_definition(raw) if raw["model"]["id"] != cs.MODEL_ID else dict(raw)
    out["model"] = dict(out["model"])
    out["model"]["operators"] = [
        *out["model"]["operators"],
        dict(law=WRITER, rows=[dict(species=s, kind=k) for s, k in rows]),
    ]
    return out


# ------------------------------------------------------------------ gap 8: held rows

HOLDING = dataclasses.replace(kf.EXCHANGE, held_rows=lambda declaration: ((HELD, declaration[1]),))


def holding_registry():
    out = kind_registry.KindRegistry()
    out.register(HOLDING)
    return out


def holding_world():
    """The core's seam world (heredity cell D with B, which the exchange kind moves) with F, which
    the planted kind holds at its cell (cell_0)."""
    raw = wfx.heredity_cell("D", end_time=0.004)
    for species in ("B", HELD):
        raw = add_inventory_species(
            raw, species, trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
        )
    return kf.declare(raw, rate=1e-3)


def test_an_operator_writing_a_held_row_is_refused(writer):
    with kind_registry.scope(holding_registry()):
        parse_spec(cs.frozen_definition(holding_world()))  # The kind alone holds F at cell_0.
        message = (
            f"Kind {kf.KIND_ID} holds F at cell_0, which {WRITER} moves in the step (its in-step "
            "process moves F at every cell node); a held row is moved by nothing in the step "
            "(one writer)"
        )
        with pytest.raises(ConfigError, match=re.escape(message)):
            parse_spec(with_writer(holding_world(), (HELD, "cell")))


@pytest.mark.parametrize("row", [(HELD, "outside"), ("B", "cell")], ids=("outside", "species"))
def test_the_writer_on_another_node_kind_or_species_is_admitted(writer, row):
    with kind_registry.scope(holding_registry()):
        spec = parse_spec(with_writer(holding_world(), row))
        pairs = [(op, d) for op, d, _ in cs.entries(spec)]
        assert pump_composite.held_row_errors(pairs, spec) == []
        assert pump_composite.operator_writers(pairs, spec)  # The writer is read, and admitted.


def test_only_an_in_step_process_is_a_writer():
    with kind_registry.scope(holding_registry()):
        spec = parse_spec(cs.frozen_definition(holding_world()))
        pairs = [(Writer(), declared((HELD, "cell"))), (Event(), declared((HELD, "cell")))]
        errors = pump_composite.held_row_errors(pairs, spec)
        assert len(errors) == 1 and errors[0].startswith(f"Kind {kf.KIND_ID} holds F at cell_0")
        assert WRITER in errors[0]  # Only the in-step process: an event part is not a writer.
        assert pump_composite.operator_writers(pairs, spec) == {(HELD, "cell_0"): (WRITER,)}


# ------------------------------------------------------------------ §7.5: exact-booked rows


def route(rid, permeability, *, species=fx.SPECIES):
    """A neutral route on the contact patch (cell_0 to ecs_0), in FR-4's form."""
    return {
        "id": rid,
        "patch": "contact_0",
        "law": passive_routes.LAW_ID,
        "species": species,
        "permeability_m_per_s": permeability,
    }


def pair(*rows, wall_s=0.0, routes=None):
    """The closed pair (FR-1's face-free world W) as a composition with passive routes on its
    contact patch, and the planted writer when rows are given. wall_s: S's permeability on the
    wall patch to the held bath, which then also moves S at cell_0 (the route is tableau-booked)."""
    raw = fx.face_free(end=0.004)
    m = raw["model"]
    if wall_s:
        m["membranes"][0]["permeability_m_per_s"][fx.SPECIES] = wall_s
    m[passive_routes.MODEL_KEY] = routes or [route("leak_S", P)]
    return with_writer(raw, *rows) if rows else raw


def exact_mask(raw):
    spec = parse_spec(raw)
    _, p = get_model(spec.model).initial_values(spec)
    return p.passive_exact.tolist()


def test_the_rule_names_the_passive_kind():
    assert pump_composite.PASSIVE_ROUTES_ID == passive_routes.KIND_ID


@pytest.mark.parametrize("kind, node", [("cell", "cell_0"), ("outside", "ecs_0")])
def test_an_operator_writing_an_exact_routes_row_is_refused(writer, kind, node):
    assert exact_mask(pair()) == [True]
    message = (
        f"{WRITER} moves S at every {kind} node in the step (its in-step process), and the "
        f"passive route leak_S books S at {node} exactly (§7.5); version 1 refuses this "
        "because it cannot yet downgrade the route to tableau booking where an operator writes "
        "its row"
    )
    with pytest.raises(ConfigError, match=re.escape(message)):
        parse_spec(pair((fx.SPECIES, kind)))


@pytest.mark.parametrize("kind", ["cell", "outside"])
def test_the_writer_on_a_tableau_booked_routes_row_is_admitted(writer, kind):
    assert exact_mask(pair(wall_s=1e-9)) == [False]  # The wall patch also moves S at cell_0.
    spec = parse_spec(pair((fx.SPECIES, kind), wall_s=1e-9))
    _, p = get_model(spec.model).initial_values(spec)
    pairs = [(op, d) for op, d, _ in cs.entries(spec)]
    assert pump_composite.exact_row_errors(pairs, spec, p) == []


def test_the_writer_on_an_unrelated_row_is_admitted(writer):
    spec = parse_spec(pair(("K", "cell"), ("K", "outside")))
    _, p = get_model(spec.model).initial_values(spec)
    assert p.passive_exact.tolist() == [True]  # The exact route stays exact.
    pairs = [(op, d) for op, d, _ in cs.entries(spec)]
    assert pump_composite.exact_row_errors(pairs, spec, p) == []


def test_a_route_without_permeability_moves_no_row():
    spec = parse_spec(pair(routes=[route("leak_S", P), route("idle_T", 0.0)]))
    _, p = get_model(spec.model).initial_values(spec)
    errors = pump_composite.exact_row_errors([(Writer(), declared((fx.SPECIES, "cell")))], spec, p)
    assert len(errors) == 1 and "passive route leak_S books S at cell_0" in errors[0]


# ------------------------------------------------------------------ the guard


def test_no_check_is_made_without_a_kind_or_an_in_step_process(monkeypatch):
    def refuse(*args):
        raise AssertionError("an operator-writer check ran")

    monkeypatch.setattr(pump_composite, "held_row_errors", refuse)
    monkeypatch.setattr(pump_composite, "exact_row_errors", refuse)
    # Today's symport composition: an in-step process, no kind.
    parse_spec(cs.frozen_definition(wfx.with_symport(wfx.with_water(wfx.heredity_cell("D")))))
    # A kind without an in-step process.
    parse_spec(pair())
    with kind_registry.scope(holding_registry()):
        parse_spec(cs.frozen_definition(holding_world()))
    spec = parse_spec(pair())
    assert pump_composite.operator_writers([(Event(), declared((fx.SPECIES, "cell")))], spec) == {}
