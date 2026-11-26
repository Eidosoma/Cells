"""The run view's three format items (docs/CORE_SEAMS_DESIGN.md §9; cells/records/run_view.py),
and the view of B1's door.

Each claim with a planted error the check must catch (D187):
- kinds are words: the writer refuses a set whose kind is a versioned ID (an operator's planted
  set), and so does the reader's check; FR-5's world, with cells.kind.ph_condition@1's set, gives its
  kind as a word and its law under laws, and its view is admitted (the old form is refused);
- a reference constant is written only where a written record names it: a recording subset that
  keeps amount_increment states amount_reference, one that drops it does not;
- the door: the channel set states each population's factors, and a factored world's
  channel_availability record says it is the held value; a world without factors states none.
(A field reference's unstated entry, item 3's other half: test_run_view_door_s.py.)
"""

import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.kinds import ph_condition
from cells.models import surface_pump_v3 as tissue3
from cells.operators import OPERATORS
from cells.records import run_view
from cells.records.io import write_run
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests.run_view_fixtures import EXCHANGE, declare_secretion, load, plant, secretion
from tests.unit.test_surface_pump_v3_populations import heredity


@pytest.fixture(scope="module")
def secreted():
    """The worked example's world (test_run_view.py's), run once, with its operators' layers."""
    with pytest.MonkeyPatch.context() as patch:
        declare_secretion(patch)
        spec = secretion()
        yield spec, run(spec)


def prepared(spec):
    impl = get_model(spec.model)
    _, layout = impl.initial_values(spec)
    return run_view.prepare(spec, run_view.Request(), layout=layout)


# ------------------------------------------------------------------ item 1: kinds are words


def test_the_writer_refuses_a_versioned_id_as_a_kind(secreted, monkeypatch, tmp_path):
    spec, result = secreted
    declare_secretion(monkeypatch)
    own = type(OPERATORS[EXCHANGE]).view_sets

    def with_kinds(self, spec, declaration, *, kind):
        sets = own(self, spec, declaration)
        entry = dict(sets["exchange_route"])
        entry["kinds"] = tuple(kind for _ in entry["ids"])
        return {"exchange_route": entry}

    words = lambda self, s, d: with_kinds(self, s, d, kind="secretion")  # noqa: E731
    plant(monkeypatch, EXCHANGE, view_sets=words)
    write_run(tmp_path / "words", result, view=run_view.Request())
    sets = {s["id"]: s for s in load(tmp_path / "words")["sets"]}
    assert set(sets["exchange_route"]["kinds"]) == {"secretion"}
    law_id = lambda self, s, d: with_kinds(self, s, d, kind=EXCHANGE)  # noqa: E731
    plant(monkeypatch, EXCHANGE, view_sets=law_id)  # Plant: the law's versioned ID as a kind.
    with pytest.raises(run_view.ViewRefused, match="versioned ID as a kind"):
        write_run(tmp_path / "ids", result, view=run_view.Request())
    assert not (tmp_path / "ids").exists()


def test_the_readers_check_refuses_a_versioned_id_as_a_kind(secreted, monkeypatch, tmp_path):
    spec, result = secreted
    declare_secretion(monkeypatch)
    write_run(tmp_path / "r", result, view=run_view.Request())
    view = load(tmp_path / "r")
    run_view.validate(view, tmp_path / "r")
    route = next(s for s in view["sets"] if s["id"] == "exchange_route")
    route["kinds"] = ["secretion@1" for _ in route["ids"]]  # Plant.
    with pytest.raises(run_view.ViewInvalid, match="kinds are words"):
        run_view.validate(view)


def test_a_ph_condition_set_gives_its_kind_as_a_word_and_its_law_under_laws(monkeypatch):
    from validation.compartment_ph_engine import definitions as defs
    from validation.compartment_ph_engine.parameters import ARM_R

    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    spec = parse_spec(defs.development_world(defs.fr5_world(ARM_R)))
    plan = prepared(spec)
    entry = plan.sets["ph_condition"]
    assert entry["kinds"] == ["factor"] and entry["laws"] == [{"law_id": ph_condition.LAW_ID}]
    own = ph_condition.view_sets

    def old_form(spec, declaration):  # Plant: the law's ID as the kind, as before §9's item 1.
        sets = own(spec, declaration)
        entry = dict(sets[ph_condition.AXIS])
        entry["kinds"] = [ph_condition.LAW_ID for _ in entry["ids"]]
        return {ph_condition.AXIS: entry}

    registry = kind_registry.KindRegistry()
    for kind_id in dict(spec.model.kinds):
        kind = kind_registry.BUILTIN.lookup(kind_id)
        if kind_id == ph_condition.KIND_ID:
            from dataclasses import replace

            kind = replace(kind, view_sets=old_form)
        registry.register(kind)
    with kind_registry.scope(registry):
        spec = parse_spec(defs.development_world(defs.fr5_world(ARM_R)))
        with pytest.raises(run_view.ViewRefused, match="versioned ID as a kind"):
            prepared(spec)


# ------------------------------------------------------------------ item 3: reference constants


def test_a_reference_constant_is_written_only_where_a_record_names_it(
    secreted, monkeypatch, tmp_path
):
    spec, result = secreted
    declare_secretion(monkeypatch)
    references = set(tissue3.RECORD_REFERENCES.values()) - set(run_view.VIEW_FIELD_AXES)
    assert references == {"amount_reference"}
    for name, fields, stated in (
        ("kept", ("amount_increment", "membrane_voltage_V"), True),
        ("dropped", ("amount", "membrane_voltage_V"), False),  # Plant: no record names it.
    ):
        keep = run_view.Recording(fields=fields)
        write_run(tmp_path / name, result, view=run_view.Request(recording=keep))
        view = load(tmp_path / name)
        run_view.validate(view, tmp_path / name)
        constants = {c["id"] for c in view["constants"]}
        named = {r["reference"]["constant"] for r in view["records"] if "reference" in r}
        assert ("amount_reference" in constants) is stated
        assert named <= constants and (named == {"amount_reference"}) is stated


# ------------------------------------------------------------------ B1's door in the view


def test_the_channel_set_states_each_populations_factors(monkeypatch):
    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    with kind_registry.scope(kf.registry(kf.factor_source())):
        factored = parse_spec(heredity(("f_b", "f_c")))
        plan = prepared(factored)
        channels = plan.sets["channel"]
        assert channels["factors"] == [["f_b", "f_c"], []]
        view = plan.view({"observation": [("trajectory.npz", 2)]}, "full")
        run_view.validate(view)
        (record,) = [r for r in view["records"] if r["field"] == "channel_availability"]
        assert record["note"] == tissue3.ROUTED_CHANNEL_NOTE
        plain = prepared(parse_spec(heredity()))  # Without factors: none stated.
        assert "factors" not in plain.sets["channel"]
        view = plain.view({"observation": [("trajectory.npz", 2)]}, "full")
        (record,) = [r for r in view["records"] if r["field"] == "channel_availability"]
        assert "note" not in record
    broken = dict(channels, factors=[["f_b"]])  # Plant: not one per population.
    view = plan.view({"observation": [("trajectory.npz", 2)]}, "full")
    view["sets"] = [broken if s["id"] == "channel" else s for s in view["sets"]]
    with pytest.raises(run_view.ViewInvalid, match="factors has one per id"):
        run_view.validate(view)
