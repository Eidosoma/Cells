"""The run view's loop block (FR-11; docs/LOOPING_REPLAY_DESIGN.md §2, §3; cells/records/run_view.py).

* Refused before any output: a species or cell type that is not a word, a cell the definition
  does not declare, a period or tolerance not above zero, follows (the cycle's, after its probe),
  a run without its engine source, a recording subset that leaves out a total the loop reader
  differences, a batch's world. A cell type, when given, stands beside the species in the block.
* The declarations a closure reads (the operator contract's RECORD_DIAGNOSTICS and
  RECORD_REFERENCES): a diagnostic's records say so, and a field stored as an increment over a
  fixed reference names it (a constant of the view, or the merged view's record under door S).
  cells.model.resolved_pump_tissue@3 declares its own (models/surface_pump_v3), which the tests read; an
  operator's are planted on its class.
* The closure (loop_closure) on saved files, read one at a time: for each observed record of kind
  level, amount or rate that is not a diagnostic, the largest change from the first row to the
  last over the record's largest magnitude, an increment measured as reference + increment. A
  record identically zero is named, never divided by; diagnostics and cumulative totals are
  named under "not measured" with the reason.
* The shared paths write the block when the observed rows span the period and the closure is
  within the tolerance, with what an independent computation from the design's words gives;
  otherwise the block is left out and the view says why. The reader's check measures it again.

The run: one heredity cell under a biphasic current train (an injection world), observed over its
second period.
"""  # noqa: E501

import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.execution.windows import WindowPolicy
from cells.operators import OPERATORS
from cells.records import run_view
from cells.records.io import write_run
from cells.records.window_io import write_windowed_run
from cells.registry.models import get_model
from tests.run_view_fixtures import DT, INJECTION, injection_world, load

PERIOD, HALF = 0.004, 2  # +1 pA for two steps, then -1 pA for two: one period is 4 ms.
CURRENT = 1e-12
KINDS = ("level", "amount", "rate")  # The design's measured kinds (§2), restated.
SOURCE = {
    "revision": "planted-by-the-test",
    "dirty": False,
    "from": "the execution snapshot's record (SNAPSHOT.json)",
}
# cells.model.resolved_pump_tissue@3's own record roles, restated: the tests check the writer reads them.
DIAGNOSTICS = ("charge_residual_C", "component_current_residual_A", "energy_balance_pJ_s")
REFERENCES = {
    "amount_increment": "amount_reference",
    "extracellular_amount_increment": "extracellular_amount_reference",
}


def periodic(periods=2):
    """The injection world under `periods` periods of the train, observed every step of the
    last period (its first row at t0, its last at t0 + T)."""
    steps = round(PERIOD / DT)
    currents = [(k * HALF, CURRENT if k % 2 == 0 else -CURRENT) for k in range(2 * periods)]
    raw = injection_world(currents, end=periods * PERIOD)
    first = (periods - 1) * steps
    raw["experiment"]["observation_times"] = [(first + j) * DT for j in range(steps + 1)]
    return raw


def plant_source(patch, source=SOURCE):
    patch.setattr(run_view, "_engine_source", lambda root=None: None if source is None else source)


def declare(patch, spec, source=SOURCE):
    """The engine source planted; the inner model's diagnostics and references are @3's own,
    read from the object the writer reads them from."""
    plant_source(patch, source)
    inner = run_view._inner(get_model(spec.model))
    assert tuple(inner.RECORD_DIAGNOSTICS) == DIAGNOSTICS
    assert dict(inner.RECORD_REFERENCES) == REFERENCES


def request(tolerance=2.0, period=PERIOD, cell="cell_0", **loop):
    return run_view.Request(
        {"label": "a loop test"}, loop=run_view.Loop("heredity", cell, period, tolerance, **loop)
    )


def independent_closure(directory, view):
    """The closure from the design's words (§2) and the lead's two rules, computed apart from
    loop_closure on io.write_run's one file: (largest ratio, the first record attaining it, the
    records identically zero, {reason word: records left out})."""
    constants = {c["id"]: np.asarray(c["values"], dtype=float) for c in view["constants"]}
    ratios, zero, left = {}, [], {"diagnostic": [], "cumulative": [], "unstated": []}
    with np.load(directory / "trajectory.npz", allow_pickle=False) as saved:
        for record in view["records"]:
            if record["base"] != "observation":
                continue
            if "diagnostic" in record:
                left["diagnostic"].append(record["id"])
                continue
            if record.get("kind") not in KINDS:
                left["cumulative" if record.get("kind") == "cumulative" else "unstated"].append(
                    record["id"]
                )
                continue
            x = np.asarray(saved[record["array"]], dtype=float)
            if "reference" in record:  # Stored over a fixed reference: the quantity is the sum.
                x = x + constants[record["reference"]["constant"]]
            top = np.max(np.abs(x), initial=0.0)  # A set with no entity holds nothing.
            if top == 0:
                zero.append(record["id"])
                continue
            ratios[record["id"]] = np.max(np.abs(x[-1] - x[0])) / top
    worst = max(ratios, key=ratios.get)
    return float(ratios[worst]), worst, zero, left


# ------------------------------------------------------------------ refused before any output


@pytest.fixture(scope="module")
def prepared():
    spec = parse_spec(periodic())
    _, layout = get_model(spec.model).initial_values(spec)
    return spec, layout


@pytest.mark.parametrize(
    "loop, message",
    [
        (dict(species="two words"), "species is a word"),
        (dict(species=""), "species is a word"),
        (dict(cell="cell_9"), "not a declared cell"),
        (dict(period=0.0), "period is a finite number above zero"),
        (dict(period=float("inf")), "period is a finite number above zero"),
        (dict(tolerance=-1.0), "tolerance is a finite number above zero"),
        (dict(tolerance=True), "tolerance is a finite number above zero"),
        (dict(follows=({"time": 0.002, "from": "cell_0", "to": "cell_0"},)), "follows"),
        (dict(cell_type="two words"), "cell_type is a word"),
        (dict(cell_type=""), "cell_type is a word"),
    ],
)
def test_bad_loops_are_refused_before_any_output(prepared, monkeypatch, loop, message):
    spec, layout = prepared
    plant_source(monkeypatch)
    fields = dict(species="heredity", cell="cell_0", period=PERIOD, tolerance=1e-3) | loop
    with pytest.raises(run_view.ViewRefused, match=message):
        run_view.prepare(spec, run_view.Request(loop=run_view.Loop(**fields)), layout=layout)


def test_a_loop_needs_the_engine_source(prepared, monkeypatch):
    spec, layout = prepared
    plant_source(monkeypatch, None)  # A checkout, or an example: no execution snapshot.
    with pytest.raises(run_view.ViewRefused, match="names its engine source"):
        run_view.prepare(spec, request(), layout=layout)
    plant_source(monkeypatch)
    plan = run_view.prepare(spec, request(), layout=layout)
    assert plan.loop == request().loop


def test_a_loop_keeps_the_totals_the_loop_reader_differences(prepared, monkeypatch):
    spec, layout = prepared
    plant_source(monkeypatch)
    kept = ("membrane_voltage_V", "membrane_transferred", "channel_transferred")
    subset = run_view.Request(loop=request().loop, recording=run_view.Recording(fields=kept))
    with pytest.raises(run_view.ViewRefused, match="leaves out pump_cycles"):
        run_view.prepare(spec, subset, layout=layout)
    whole = run_view.Recording(fields=(*kept, "pump_cycles"))
    run_view.prepare(spec, run_view.Request(loop=request().loop, recording=whole), layout=layout)


def test_a_batch_world_is_not_a_loop():
    with pytest.raises(run_view.ViewRefused, match="one run, not a batch"):
        run_view.requests_for(request(), [10, 11])


# ------------------------------------------------------------------ the declarations it reads


def test_diagnostics_and_references_are_read_from_their_owners(prepared, monkeypatch):
    """The inner model's (@3's own) and an operator's RECORD_DIAGNOSTICS mark their records;
    RECORD_REFERENCES names each increment's reference, stated as a constant of the view."""
    spec, layout = prepared
    declare(monkeypatch, spec)
    monkeypatch.setattr(
        type(OPERATORS[INJECTION]), "RECORD_DIAGNOSTICS", ("injection_energy_magnitude_pJ",)
    )
    plan = run_view.prepare(spec, layout=layout)
    view = plan.view(run_view.single_file_bases([0.0, PERIOD], [0.0, PERIOD]), "write_run")
    run_view.validate(view)
    records = {r["id"]: r for r in view["records"]}
    marked = {r["id"] for r in view["records"] if "diagnostic" in r}
    assert marked == {
        *(f"observed_{k}" for k in DIAGNOSTICS),
        "injection_energy_magnitude_pJ",
        "observed_injection_energy_magnitude_pJ",
    }
    for name, reference in REFERENCES.items():
        for record_id in (name, f"observed_{name}"):
            assert records[record_id]["reference"] == {"constant": reference}, record_id
    constants = {c["id"]: c for c in view["constants"]}
    assert np.array_equal(constants["amount_reference"]["values"], layout.amount_reference)
    assert constants["amount_reference"]["axes"] == ["species", "cell"]
    assert "reference" not in records["observed_amount"]  # Not stored over a reference.


# ------------------------------------------------------------------ the closure on saved files


def synthetic(tmp_path, chunks, kinds, *, constants=(), marks=None):
    """A minimal view of observed records over chunk files: chunks [(times, {array: rows})];
    marks: {record name: {key: value}} added to a record (diagnostic, reference)."""
    files = []
    for i, (times, arrays) in enumerate(chunks):
        name = f"chunk-{i}.npz"
        np.savez(tmp_path / name, observation_times=np.asarray(times, dtype=float), **arrays)
        files.append({"file": name, "rows": [0, len(times)]})
    base = {"id": "observation", "array": "observation_times", "files": files}
    records = [
        {
            "id": f"observed_{k}",
            "array": f"observed_{k}",
            "base": "observation",
            "axes": ["time", "thing"],
            "kind": kind,
        }
        | (marks or {}).get(k, {})
        for k, kind in kinds.items()
    ]
    return {
        "time": {"bases": [base]},
        "records": records,
        "sets": [{"id": "thing", "ids": ["a", "b"]}],
        "constants": list(constants),
    }


def test_the_closure_is_the_largest_seam_over_each_records_magnitude(tmp_path):
    kinds = dict(a="level", b="rate", c="amount", d="cumulative", e="level")
    first = {
        "observed_a": np.array([[1.0, -2.0], [1.5, -2.5]]),
        "observed_b": np.array([[0.0, 0.0], [3.0, 0.0]]),
        "observed_c": np.zeros((2, 2)),  # Identically zero: named, never divided by.
        "observed_d": np.array([[0.0, 0.0], [5.0, 0.0]]),  # A total: left out, though it grows.
        "observed_e": np.array([[1e-26, 0.0], [-3e-26, 0.0]]),  # A diagnostic: left out.
    }
    second = {
        "observed_a": np.array([[1.1, -2.0]]),
        "observed_b": np.array([[0.3, 0.0]]),
        "observed_c": np.zeros((1, 2)),
        "observed_d": np.array([[10.0, 0.0]]),
        "observed_e": np.array([[2e-26, 0.0]]),
    }
    marks = {"e": {"diagnostic": run_view.DIAGNOSTIC_NOTE}}
    view = synthetic(tmp_path, [([0.0, 0.5], first), ([1.0], second)], kinds, marks=marks)
    why = dict(run_view.NOT_MEASURED)
    assert run_view.loop_closure(view, tmp_path) == {
        "within": 0.3 / 3.0,
        "record": "observed_b",
        "zero": ["observed_c"],
        "not_measured": [
            {"why": why["diagnostic"], "records": ["observed_e"]},
            {"why": why["cumulative"], "records": ["observed_d"]},
        ],
        "start": 0.0,
        "end": 1.0,
    }
    view["records"] = [r for r in view["records"] if r["id"] == "observed_c"]
    with pytest.raises(run_view.ViewInvalid, match="identically zero"):
        run_view.loop_closure(view, tmp_path)


def test_an_increment_is_measured_over_its_reference(tmp_path):
    """reference + increment against that sum's own magnitude: the reference a constant (at the
    recorded elements), or the merged view's rows."""
    rows = {
        "observed_n": np.array([[0.0, 1.0], [0.5, 1.0], [0.1, 1.0]]),  # Increments.
        "observed_ref": np.array([[100.0, 1.0], [100.0, 1.0], [100.0, 1.0]]),
    }
    constant = {"id": "n_reference", "values": [100.0, 1.0]}
    # The sum's seam over its largest magnitude (the reference record itself is constant: 0).
    expected = ((0.1 + 100.0) - (0.0 + 100.0)) / (0.5 + 100.0)
    for reference in ({"constant": "n_reference"}, {"record": "observed_ref"}):
        view = synthetic(
            tmp_path,
            [([0.0, 0.5, 1.0], rows)],
            dict(n="amount", ref="level"),
            constants=[constant],
            marks={"n": {"reference": reference}},
        )
        closure = run_view.loop_closure(view, tmp_path)
        assert (closure["within"], closure["record"]) == (expected, "observed_n"), reference
    view["records"][0]["reference"] = {"field": "n_reference"}  # A run on disk: not saved.
    with pytest.raises(run_view.ViewInvalid, match="reference is not saved"):
        run_view.loop_closure(view, tmp_path)


def test_the_closure_refuses_what_it_cannot_measure(tmp_path):
    rows = {"observed_a": np.array([[1.0, 0.0], [np.nan, 0.0], [1.0, 0.0]])}
    view = synthetic(tmp_path, [([0.0, 0.5, 1.0], rows)], dict(a="level"))
    with pytest.raises(run_view.ViewInvalid, match="not finite"):
        run_view.loop_closure(view, tmp_path)  # A NaN between the ends is not lost.
    view["records"][0]["kind"] = "cumulative"
    with pytest.raises(run_view.ViewInvalid, match="no observed record"):
        run_view.loop_closure(view, tmp_path)
    view["time"]["bases"] = []
    with pytest.raises(run_view.ViewInvalid, match="no observed rows"):
        run_view.loop_closure(view, tmp_path)


# ------------------------------------------------------------------ the shared paths


@pytest.fixture(scope="module")
def result():
    return run(parse_spec(periodic()))


def test_a_loop_that_closes_is_written_with_its_measured_closure(result, monkeypatch, tmp_path):
    declare(monkeypatch, result.spec)
    write_run(tmp_path / "a", result, view=request())
    write_run(tmp_path / "b", result, view=request())
    view = load(tmp_path / "a")
    a, b = ((tmp_path / name / run_view.FILE).read_bytes() for name in ("a", "b"))
    assert a == b  # The same bytes.
    within, worst, zero, left = independent_closure(tmp_path / "a", view)
    why = dict(run_view.NOT_MEASURED)
    loop = view[run_view.LOOP_KEY]
    assert loop == {
        "species": "heredity",
        "cell": "cell_0",
        "period": PERIOD,
        "closes": {
            "within": within,
            "says": f"the last observed row meets the first within {within:.2g} relative "
            f"(largest in {worst})",
            "tolerance": 2.0,
            "zero": zero,
        },
        "not_measured": [{"why": why[k], "records": left[k]} for k in left if left[k]],
    }
    assert left["diagnostic"] == [f"observed_{k}" for k in DIAGNOSTICS]
    assert "observed_membrane_transferred" in left["cumulative"]
    assert 0.0 < within <= 2.0
    assert "loop" not in {u["id"] for u in view["unstated"]}
    assert view["run"]["source"] == SOURCE and "revision" not in view["run"]
    run_view.validate(view, tmp_path / "a")  # The reader's check measures it again.
    # A cell type: the caller's label beside the species (absent above: the default cell).
    write_run(tmp_path / "typed", result, view=request(cell_type="resting"))
    typed = load(tmp_path / "typed")
    run_view.validate(typed, tmp_path / "typed")
    assert typed[run_view.LOOP_KEY] == dict(loop, cell_type="resting")
    view[run_view.LOOP_KEY]["closes"]["within"] = within / 2
    with pytest.raises(run_view.ViewInvalid, match="the one measured on its files"):
        run_view.validate(view, tmp_path / "a")


def test_a_run_that_does_not_close_or_span_the_period_is_not_a_loop(result, monkeypatch, tmp_path):
    declare(monkeypatch, result.spec)
    write_run(tmp_path / "measured", result, view=request())
    within = load(tmp_path / "measured")[run_view.LOOP_KEY]["closes"]["within"]
    write_run(tmp_path / "at", result, view=request(tolerance=within))
    assert run_view.LOOP_KEY in load(tmp_path / "at")  # Within the tolerance, at its edge.
    cases = {
        "open": (request(tolerance=within / 2), "above the tolerance"),
        "short": (request(period=PERIOD - DT), "not the period"),
    }
    for name, (asked, reason) in cases.items():
        write_run(tmp_path / name, result, view=asked)
        view = load(tmp_path / name)
        assert run_view.LOOP_KEY not in view, name
        (item,) = [u for u in view["unstated"] if u["id"] == "loop"]
        assert reason in item["why"], name
        run_view.validate(view, tmp_path / name)


def test_the_windowed_path_writes_the_loop(monkeypatch, tmp_path):
    """The replay driver's path: observed rows only (recording "observations")."""
    spec = parse_spec(periodic())
    declare(monkeypatch, spec)
    policy = WindowPolicy(window_steps=3, recording="observations")
    write_windowed_run(tmp_path / "w", spec, policy, view=request())
    view = load(tmp_path / "w")
    assert view[run_view.LOOP_KEY]["closes"]["within"] <= 2.0
    assert [b["id"] for b in view["time"]["bases"]] == ["observation"]
    assert len(view["time"]["bases"][0]["files"]) > 1  # Read across chunks.
    run_view.validate(view, tmp_path / "w")
    manifest = json.loads((tmp_path / "w" / "manifest.json").read_text())
    assert run_view.FILE in manifest["files_sha256"]
