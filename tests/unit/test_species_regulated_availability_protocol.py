"""The coupling operator's qualification tools, on the host: the judge, the drafter, the controls.

docs/INVENTORY_COUPLING_DESIGN.md §10. No compile and no reference run: synthetic records with
known orders exercise the judge's resolution rule, its band and its control verdict; the drafter's
1-2-5 rounding; the controls' registration and their parsing.
* A second-order record is in band; a first-order one is caught; a record under 100 floors, or
  under its rounding scale, is reported, not judged; a pair whose error is zero is not resolved.
* The generator refuses a judged run of an unregistered protocol before writing anything.
* Registration takes the record's status and keeps every other leaf (MG0c's form); every
  protocol world has no free field offsets (D147).
* A control law exists only inside its `registered` block, and the registry is restored after
  the block whether it ends normally, raises or exits.
"""

import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.operators import OPERATORS
from cells.registry.models import get_model
from validation.tissue import regulated_availability_controls as controls
from validation.tissue import regulated_availability_dt_study as generator
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import regulated_availability_judge as judge
from validation.tissue import regulated_availability_protocol as drafter

LADDER = (1e-3, 5e-4, 2.5e-4, 1.25e-4)
PROTOCOL = dict(
    band=[1.7, 2.3],
    resolution=dict(floor_factor=100.0, rounding={"s": 1e-13, "U": "steps_eps_max"}),
    observables=["V", "s", "U"],
)


def arm(errors_by_observable, floor=None, magnitudes=None):
    runs = []
    for i, dt in enumerate(LADDER):
        runs.append(
            dict(
                dt=dt,
                steps=round(2.0 / dt),
                gate_held_at_1=True,
                row0_V_difference=0.0,
                errors={x: [e[i]] for x, e in errors_by_observable.items()},
            )
        )
    return dict(
        runs=runs,
        floor=floor or dict(V=1e-16, s=1e-14, U=1e-16),
        magnitudes=magnitudes or dict(V=0.06, s=1.0, U=1.0),
    )


def second(e0):
    return [e0 / 4**i for i in range(4)]


def first(e0):
    return [e0 / 2**i for i in range(4)]


def test_a_second_order_record_is_in_band_and_a_first_order_one_is_not():
    metrics = judge.derive_arm(
        arm(dict(V=second(1e-8), s=first(1e-6), U=second(1e-9))), PROTOCOL, ["V", "s", "U"]
    )
    assert metrics["V"]["in_band"] == 1 and metrics["V"]["resolved"] == 3
    assert metrics["s"]["in_band"] == 0 and metrics["s"]["resolved"] == 3
    assert [round(p["order"], 12) for p in metrics["V"]["pairs"]] == [2.0, 2.0, 2.0]


def test_pairs_under_the_floor_or_rounding_are_reported_not_judged():
    """V: the finest error under 100 floors; s: under 1e-13; U: under N eps max|U|."""
    metrics = judge.derive_arm(
        arm(
            dict(V=second(1.6e-12), s=second(1.2e-12), U=[4e-12, 1e-12, 2.6e-13, 1e-13]),
            floor=dict(V=2e-15, s=1e-16, U=1e-16),  # V needs 2e-13; s 1e-13 (rounding).
        ),
        PROTOCOL,
        ["V", "s", "U"],
    )
    assert [p["resolved"] for p in metrics["V"]["pairs"]] == [True, False, False]
    assert [p["resolved"] for p in metrics["s"]["pairs"]] == [True, False, False]
    # U's rounding scale at the finer dt: steps x eps x 1.0, 8.9e-13 at 0.25 ms, 1.8e-12 at 0.125.
    assert [p["resolved"] for p in metrics["U"]["pairs"]] == [True, False, False]
    for x in ("V", "s", "U"):
        assert metrics[x]["in_band"] == 1  # Only resolved pairs are judged.


def test_a_zero_error_is_never_a_resolved_pair():
    metrics = judge.derive_arm(arm(dict(V=[0.0] * 4, s=[0.0] * 4, U=[0.0] * 4)), PROTOCOL, [])
    assert all(metrics[x]["resolved"] == 0 for x in ("V", "s", "U"))


def test_a_control_is_caught_when_a_judged_observable_leaves_the_band():
    protocol = dict(
        PROTOCOL,
        judged_observables={"a4.coupled": ["V", "U"]},
        control_arms={"plateau": "a4.coupled"},
    )
    plateau = [1e-8 + 2e-9, 2.5e-9 + 2e-9, 6.25e-10 + 2e-9, 1.6e-10 + 2e-9]
    results = dict(
        parts=dict(
            a4=dict(coupled=arm(dict(V=second(1e-8), s=second(1e-6), U=second(1e-9)))),
            controls=dict(plateau=arm(dict(V=plateau, s=second(1e-6), U=second(1e-9)))),
        )
    )
    derived = judge.derive(results, protocol)
    assert derived["controls"]["plateau"]["caught"] == 1
    assert derived["a4"]["coupled"]["V"]["in_band"] == 1


def test_the_drafters_grid_rounds_up():
    assert drafter.snap_up(1.36e-9) == 2e-9
    assert drafter.snap_up(3.9e-4) == 5e-4
    assert drafter.snap_up(6e-3) == 1e-2
    assert drafter.snap_up(2e-3) == 2e-3


def test_a_judged_run_of_an_unregistered_protocol_is_refused_before_writing(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(dict(id="x", status="PROPOSED (a draft)")))
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="not registered"):
        generator.main(["judged", str(protocol), str(out), "a1"])
    assert not out.exists()


@pytest.mark.parametrize("kind", sorted(controls.CONTROLS))
def test_a_control_law_exists_only_inside_its_block(kind):
    raw = rf.shared_structure(on=("a", "k"), s0=(0.5, 0.5), rates=(5.0, 1.0), end=0.02)
    law = controls.law_of(kind)
    assert law not in OPERATORS
    with controls.registered(kind):
        spec = parse_spec(controls.as_control(raw, kind))
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        op = model.operators[0]
        assert op.LAW_ID == law and type(op) is controls.CONTROLS[kind]
        factors = op.control_factors(state, p, xp=np)
        assert set(factors) == {"junction", "channel"}
    assert law not in OPERATORS


@pytest.mark.parametrize("kind", sorted(controls.CONTROLS))
def test_the_registry_is_restored_after_the_block_even_when_it_raises(kind):
    """The lead's condition for planted defects: the registry after a control block is the
    registry before it, whether the block ends normally, raises, or exits; a second registration
    of the same control inside a block is refused and leaves the outer one in place."""
    law, before = controls.law_of(kind), dict(OPERATORS)
    with pytest.raises(RuntimeError, match="inside the block"):
        with controls.registered(kind):
            assert law in OPERATORS
            raise RuntimeError("inside the block")
    assert OPERATORS == before
    with pytest.raises(SystemExit):
        with controls.registered(kind):
            raise SystemExit(1)
    assert OPERATORS == before
    with controls.registered(kind):
        with pytest.raises(RuntimeError, match="already registered"):
            with controls.registered(kind):
                pass
        assert law in OPERATORS
    assert OPERATORS == before and law not in OPERATORS


def test_the_record_comparison_finds_every_difference_but_run_times(tmp_path):
    """The rehearsal's bitwise check of two runs' records: a changed float, a missing record and a
    δ-control at another δ are reported; run times are not records."""
    base = dict(
        parts=dict(
            a4=dict(coupled=dict(runs=[dict(errors=dict(V=[1e-9, 2e-9]), wall_s=3.0)])),
            controls=dict(delta_basal_a4=dict(delta=2e-5, runs=[]), wall_s=9.0),
        )
    )
    same = json.loads(json.dumps(base))
    same["parts"]["a4"]["coupled"]["runs"][0]["wall_s"] = 7.0
    moved = json.loads(json.dumps(base))
    moved["parts"]["a4"]["coupled"]["runs"][0]["errors"]["V"][1] = np.nextafter(2e-9, 1.0)
    moved["parts"]["controls"]["delta_basal_a4"]["delta"] = 1.8e-5
    paths = {}
    for name, value in dict(base=base, same=same, moved=moved).items():
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(value))
    identical = judge.compare(paths["base"], paths["same"], tmp_path / "c1.json")["parts"]
    assert identical["a4"]["identical"] and identical["controls"]["delta_basal_a4"]["identical"]
    report = judge.compare(paths["base"], paths["moved"], tmp_path / "c2.json")["parts"]
    assert report["a4"]["differences"] == [".coupled.runs[0].errors.V[1]"]
    assert report["controls"]["delta_basal_a4"]["identical"] is None


def test_registration_takes_the_records_status_and_keeps_every_other_leaf(tmp_path):
    """The lead's registration (MG0c's form): refused for a protocol already registered or a
    record whose status does not begin 'registered'; otherwise the status is the record's, the
    record follows it, and every other leaf is as drafted."""
    proposed = dict(id="x", status="PROPOSED (a draft)", criteria=[dict(id="c")], band=[1.7, 2.3])
    path, record = tmp_path / "protocol.json", tmp_path / "record.json"
    path.write_text(json.dumps(proposed))
    record.write_text(json.dumps(dict(status="draft, not a registration")))
    with pytest.raises(SystemExit, match="must begin 'registered'"):
        drafter.register(path, record)
    record.write_text(json.dumps(dict(status="registered 15 November 2026 by the lead", by="x")))
    out = drafter.register(path, record)
    assert list(out) == ["id", "status", "registration", "criteria", "band"]
    assert out["status"] == out["registration"]["status"]
    assert {k: v for k, v in out.items() if k not in ("status", "registration")} == {
        k: v for k, v in proposed.items() if k != "status"
    }
    with pytest.raises(SystemExit, match="only a PROPOSED protocol"):
        drafter.register(path, record)


def test_every_protocol_world_has_no_free_field_offsets():
    """D147, for every world the protocol runs (A4's and A5's arms, the four controls): no free
    field offsets, so the declared field solver (@2) stands and agrees with the automatic choice."""
    facts = drafter.d147_worlds()
    assert len(facts["worlds"]) == 9
    assert facts["max_free_field_offsets"] == 0 and facts["automatic_choice_agrees"]
