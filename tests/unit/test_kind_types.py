"""Schema A's per-structure types and the kind registry (INNER_MODEL_V4_DESIGN.md §7.4 (j), (k)).

- Today's structures keep the module's own classes, by identity.
- A registered kind that a definition does not declare changes nothing: the same classes,
  compile key (the world's part of compile_window's key) and snapshot layout.
- Declared kinds append their fields in canonical order (the sorted namespaced ID), whatever the
  declaration order: the same classes, compile key and snapshot layout either way.
- A kind's state fields are observation columns right after today's state fields, and its
  readouts follow today's (rule (b)).
- The spec round-trips a declared kind through its model key.
"""

import copy
import dataclasses

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.state import initialise
from cells.execution.vector_windows import spec_world_key
from cells.models import surface_pump_v3
from cells.records.io import write_snapshot
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures

TYPE_NAMES = surface_pump_v3.KindTypes._fields


def planted(name, key):
    """A planted kind with one state field, one layout field, one control and one column."""

    def parse(entries, base):
        return tuple(sorted((str(k), float(v)) for k, v in entries.items()))

    return kind_registry.Kind(
        kind_id="tests.planted_kind@1".replace("planted_kind", name),
        model_key=key,
        state_axes=((f"{name}_moved_fmol", ("cell_slot",)),),
        layout_fields=(f"{name}_rate_fmol_s",),
        control_fields=(f"{name}_availability",),
        readout_columns=(f"{name}_rate_column",),
        parse=parse,
        to_dict=lambda declaration: dict(declaration),
        structure_entry=lambda declaration: (),
        control_values=lambda spec, declaration, times: {
            f"{name}_availability": np.ones(len(times))
        },
        initial=lambda spec, declaration, layout: (
            {f"{name}_moved_fmol": np.zeros(len(spec.model.cells))},
            {f"{name}_rate_fmol_s": np.asarray([dict(declaration)["rate"]])},
        ),
    )


def registry(*kinds):
    out = kind_registry.KindRegistry()
    for kind in kinds:
        out.register(kind)
    return out


def heredity():
    return water_fixtures.heredity_cell("D", end_time=0.01)


def declaring(raw, *keys):
    raw = copy.deepcopy(raw)
    for key in keys:
        raw["model"][key] = {"rate": 1.0}
    return raw


def test_todays_structures_keep_todays_classes():
    impl = get_model(parse_spec(heredity()).model)
    assert impl.structure.kinds == ()
    for name in TYPE_NAMES:
        assert getattr(impl, name) is getattr(surface_pump_v3, name), name


def snapshot_keys(path, spec):
    """The npz keys, in order, of a snapshot of the definition's initial checkpoint."""
    with np.load(write_snapshot(path, spec, initialise(spec)) / "state.npz") as archive:
        return list(archive.files)


def compile_key(model, spec):
    """The world's part of vector_windows.compile_window's key (the packed planner's)."""
    return spec_world_key(model, spec, initialise(spec))


def test_a_registered_but_undeclared_kind_changes_nothing(tmp_path):
    spec = parse_spec(heredity())
    impl = get_model(spec.model)
    today = snapshot_keys(tmp_path / "today", spec)
    assert today == [*surface_pump_v3.STATE_TYPE._fields, *surface_pump_v3.LAYOUT_TYPE._fields]
    key = compile_key(impl, spec)
    with kind_registry.scope(registry(planted("alpha", "alpha_block"))):
        again = parse_spec(heredity())
        built = surface_pump_v3.model_for(again.model)
        assert again == spec and again.to_dict() == spec.to_dict()
        assert built.structure_key == impl.structure_key
        assert built is impl  # The same object: the same bound functions, so the compile key.
        for name in TYPE_NAMES:
            assert getattr(built, name) is getattr(surface_pump_v3, name), name
        assert compile_key(built, again) == key
        assert snapshot_keys(tmp_path / "registered", again) == today


def test_kinds_append_in_canonical_order_whatever_the_declaration_order(tmp_path):
    kinds = registry(planted("beta", "beta_block"), planted("alpha", "alpha_block"))
    with kind_registry.scope(kinds):
        one = parse_spec(declaring(heredity(), "beta_block", "alpha_block"))
        two = parse_spec(declaring(heredity(), "alpha_block", "beta_block"))
        assert [k for k, _ in one.model.kinds] == ["tests.alpha@1", "tests.beta@1"]
        assert one.model.kinds == two.model.kinds
        a, b = surface_pump_v3.model_for(one.model), surface_pump_v3.model_for(two.model)
        assert a.structure_key == b.structure_key
        for name in ("STATE_TYPE", "LAYOUT_TYPE", "FLOOR_LAYOUT_TYPE", "Control", "Observations"):
            assert getattr(a, name) is getattr(b, name), name
        assert compile_key(a, one) == compile_key(b, two)  # One executable for both.
        layout = snapshot_keys(tmp_path / "one", one)
        assert layout == snapshot_keys(tmp_path / "two", two)  # One snapshot layout.
        assert layout == [*a.STATE_TYPE._fields, *a.LAYOUT_TYPE._fields]
        today = surface_pump_v3
        assert a.STATE_TYPE._fields == (
            *today.STATE_TYPE._fields,
            "alpha_moved_fmol",
            "beta_moved_fmol",
        )
        assert a.LAYOUT_TYPE._fields == (
            *today.LAYOUT_TYPE._fields,
            "alpha_rate_fmol_s",
            "beta_rate_fmol_s",
        )
        assert a.Control._fields == (
            *today.Control._fields,
            "alpha_availability",
            "beta_availability",
        )
        n = len(today.STATE_TYPE._fields) + 1
        assert a.OBSERVATION_FIELDS == (
            *today.OBSERVATION_FIELDS[:n],
            "alpha_moved_fmol",
            "beta_moved_fmol",
            *today.OBSERVATION_FIELDS[n:],
            "alpha_rate_column",
            "beta_rate_column",
        )
        assert parse_spec(one.to_dict()) == one  # The kinds' model keys round-trip.


def test_namespaces_and_duplicates():
    for kind_id in ("cells.kind.transporter@1", "tests.kind.alpha@1"):
        assert kind_registry.qualified(kind_id) == kind_id
    for short in ("one_part@1", "tests.two_parts@1"):  # Never given a namespace or a family.
        with pytest.raises(ValueError, match=f"^{short} is not namespace.family.name@major"):
            kind_registry.qualified(short)
    with pytest.raises(ValueError, match="a kind's ID is tests.kind.<name>@major"):
        kind_registry.KindRegistry().register(
            dataclasses.replace(planted("alpha", "alpha_block"), kind_id="tests.channel.alpha@1")
        )
    kinds = registry(planted("alpha", "alpha_block"))
    with pytest.raises(ValueError, match="already registered"):
        kinds.register(planted("alpha", "other_block"))
    with pytest.raises(ValueError, match="model key"):
        kinds.register(planted("gamma", "alpha_block"))
    two = ("cells.kind.a@1", "tests.kind.b@1")
    assert kind_registry.KindRegistry.canonical(two[::-1]) == two
