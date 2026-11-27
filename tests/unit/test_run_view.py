"""The run view (D154; docs/RUN_VIEW_DESIGN.md; cells/records/run_view.py): write_run, write_batch_run,
the plan, its refusals and the reader's check. The windowed paths: test_run_view_windows.py.

* The shared paths write a view only when asked (view=): without it write_run writes what it
  wrote before; with it, view.json beside the run, before the manifest that covers it.
* The view validates against the run's own files (shapes, time bases, heat monotone), repeats
  byte for byte, holds no host path, and equals the view written afterwards from the saved run.
* Refusals write nothing: an operator without VIEW_LAYERS, a set an operator does not declare,
  geometry for a set the definition fixes, a bad recording subset or run label, a model outside
  version 1, a batch request that misses a world.
* The reader's check refuses malformed views.
* A recording subset keeps the declared fields, elements and cadence, and the view says which.
* A batch writes one view per world, beside its definition; a builder's geometry lands on its set
  (a division: test_run_view_division.py).
* The reader's check opens one file at a time and finds a heat total that falls across files.
* Every field of cells.model.resolved_pump_tissue@3 is described; the operators' missing declarations (the
  requested seams) only shrink.

Declarations an operator does not carry yet are planted for a test's duration only.
"""  # noqa: E501

import json
import os
import resource

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.batch import run_batch
from cells.execution.runner import run
from cells.execution.state import initialise
from cells.models import surface_pump_v3 as tissue3
from cells.operators import OPERATORS
from cells.operators.contract import Operator
from cells.records import run_view
from cells.records.batch_io import write_batch_run
from cells.records.io import write_run
from cells.registry.models import get_model
from tests.batch_fixtures import definition
from tests.run_view_fixtures import (
    EXCHANGE,
    TURNOVER,
    declare_secretion,
    load,
    plant,
    reference_constants,
    secretion,
)


@pytest.fixture
def declared(monkeypatch):
    declare_secretion(monkeypatch)


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """One short run of the example's world, written with a view (twice, for the bytes) and
    without one."""
    with pytest.MonkeyPatch.context() as patch:
        declare_secretion(patch)
        spec = secretion()
        result = run(spec)
        root = tmp_path_factory.mktemp("written")
        request = run_view.Request({"label": "test run"})
        write_run(root / "a", result, view=request)
        write_run(root / "b", result, view=request)
        write_run(root / "plain", result)
        yield spec, result, root


# ------------------------------------------------------------------ write_run


def test_without_a_view_write_run_writes_what_it_wrote(written):
    _, _, root = written
    files = {str(p.relative_to(root / "plain")) for p in (root / "plain").rglob("*") if p.is_file()}
    assert files == {
        "checkpoint_final/manifest.json",
        "checkpoint_final/state.npz",
        "manifest.json",
        "resolved_config.json",
        "summary.json",
        "trajectory.npz",
    }
    a = json.loads((root / "a" / "manifest.json").read_text())["files_sha256"]
    plain = json.loads((root / "plain" / "manifest.json").read_text())["files_sha256"]
    assert set(a) - set(plain) == {"view.json"}
    for name in ("trajectory.npz", "resolved_config.json", "summary.json"):
        assert a[name] == plain[name]


def test_write_run_writes_a_valid_deterministic_view(written, tmp_path):
    spec, result, root = written
    view = load(root / "a")
    run_view.validate(view, root / "a")
    data = (root / "a" / "view.json").read_bytes()
    assert data == (root / "b" / "view.json").read_bytes()
    assert str(root).encode() not in data and b"/mnt/" not in data
    model = get_model(spec.model)
    assert view["run"]["engine_models"] == [
        "cells.model.resolved_pump_composite@1",
        "cells.model.resolved_pump_tissue@3",
        TURNOVER,
        EXCHANGE,
    ]
    assert view["run"]["definition_sha256"] == spec.fingerprint
    assert view["run"]["label"] == "test run"
    records = {r["id"]: r for r in view["records"]}
    assert len(records) == len(model.STATE_AXES) + len(model.OBSERVATION_FIELDS) - 1
    sets = {s["id"]: s for s in view["sets"]}
    assert sets["species"]["ids"] == ["Na", "K", "Cl", "S"]
    assert sets["species"]["species"][3]["identity"]["source"] == TURNOVER
    assert sets["membrane"]["outside"]["index"] == [0, 1]
    assert sets["exchange_route"]["ids"] == ["secrete", "sink"]
    assert sets["exchange_route"]["geometry"] == {"kind": "on", "set": "membrane", "index": [1, 1]}
    # Each route's species, declared direction and roles; turnover's routes, where each acts.
    assert sets["exchange_route"]["carries"] == ["S", "S"]
    assert sets["exchange_route"]["direction"] == ["export", "import"]
    assert set(sets["exchange_route"]["roles"]) == {"inside", "outside"}
    assert sets["turnover_route"]["ids"] == ["produce", "clear"]
    assert sets["turnover_route"]["carries"] == ["S", "S"]
    assert sets["turnover_route"]["kinds"] == ["production", "clearance"]
    assert sets["turnover_route"]["at"] == [{"cell": "cell_0"}, {"outside": "ecs_0"}]
    assert set(sets["membrane"]["roles"]) == {"inside", "outside"}
    assert records["observed_membrane_transferred"]["sign"]["from"] == "inside"
    assert records["observed_reservoir_supplied"]["sign"]["to"] == "node"
    assert records["observed_exchange_moved_fmol"]["layer"] == "exchange"
    assert records["observed_exchange_work_pJ"]["kind"] == "cumulative"  # A declared work field.
    moved = records["observed_exchange_moved_fmol"]
    assert moved["kind"] == "cumulative" and (moved["sign"]["from"], moved["sign"]["to"]) == (
        "inside",
        "outside",
    )
    for name in ("produced", "cleared", "outside_cleared", "energy_magnitude"):
        assert (
            records[f"turnover_{name}_fmol" if "energy" not in name else f"turnover_{name}_pJ"][
                "kind"
            ]
            == "cumulative"
        )
    with np.load(root / "a" / "trajectory.npz") as saved:  # Export positive, import negative.
        totals = saved["exchange_moved_fmol"]
    assert np.all(totals[:, 0] >= 0) and np.all(totals[:, 1] <= 0) and totals[-1].all()
    # Voltages are differences: plus less minus, by the set's roles.
    voltage = records["observed_membrane_voltage_V"]["difference"]
    assert (voltage["plus"], voltage["minus"]) == ("inside", "outside") and "sign" not in voltage
    junction = records["observed_junction_voltage_V"]["difference"]
    assert (junction["plus"], junction["minus"]) == ("sender", "receiver")
    assert "the passive membrane routes only" in records["membrane_transferred"]["note"]
    assert records["face_dissipated_energy_pJ"]["monotone"] == "non-decreasing"
    assert "resets" not in records["face_dissipated_energy_pJ"]  # Nothing retires here.
    # Nothing here changes a view field: every one is a constant, and no merged view is saved;
    # an increment's fixed reference that no view field states is one more (RECORD_REFERENCES).
    constants = {c["id"] for c in view["constants"]}
    assert constants == set(run_view.VIEW_FIELD_AXES) | reference_constants()
    with np.load(root / "a" / "trajectory.npz") as saved:
        assert not [k for k in saved.files if k.startswith(run_view.VIEW_PREFIX)]
    unstated = {(u["id"], u["what"]) for u in view["unstated"]}
    assert ("geometry", "geometry") in unstated and ("source", "engine source") in unstated
    assert not {u for u in unstated if u[1] == "kind"}  # D150's two declare every kind.
    assert view["events"] == [] and view["space"] is None
    end = {"status": "complete", "time": float(result.final.time), "step": 10}
    assert view["run"]["end"] == end and result.final.step_index == 10
    # The same view, written afterwards from the saved run, but for the engine that ran it.
    out = tmp_path / "later"
    run_view.write_view(root / "plain", out=out, run={"label": "test run"})
    later = load(out)
    ((why,),) = [[u["why"] for u in later["unstated"] if u["id"] == "source"]]
    assert why == "the view is written for a run already on disk"
    for each in (view, later):
        each["unstated"] = [u for u in each["unstated"] if u["id"] != "source"]
    assert later == view


def test_a_recording_subset_keeps_the_declared_fields_elements_and_cadence(
    written, declared, tmp_path
):
    spec, result, _ = written
    keep = run_view.Recording(
        fields=("membrane_voltage_V", "amount", "exchange_moved_fmol"),
        elements={"species": ("S",), "membrane": ("contact_0",)},
        every=2,
    )
    write_run(tmp_path / "r", result, view=run_view.Request(recording=keep))
    view = load(tmp_path / "r")
    run_view.validate(view, tmp_path / "r")
    sets = {s["id"]: s for s in view["sets"]}
    assert sets["species"]["recorded"] == [3] and sets["membrane"]["recorded"] == [1]
    assert {r["field"] for r in view["records"]} == set(keep.fields)
    assert view["recording"]["subset"]["every"] == 2
    with np.load(tmp_path / "r" / "trajectory.npz") as saved:
        times = spec.experiment.observation_times
        np.testing.assert_array_equal(saved["observation_times"], times[::2])
        assert saved["observed_amount"].shape == (len(times[::2]), 1, 1)
        assert saved["observed_membrane_voltage_V"].shape == (len(times[::2]), 1)
        assert "membrane_transferred" not in saved.files and "exchange_moved_fmol" in saved.files
        assert len(saved["exchange_moved_fmol"]) == len(saved["accepted_times"])
        assert "volume" in saved.files  # The layout is not a record: kept whole.


def test_a_batch_writes_one_view_per_world(declared, tmp_path):
    specs = [secretion(produce=1e-4), secretion(produce=2e-4)]
    result = run_batch(definition(specs))
    requests = {10: run_view.Request({"seed": 1}), 11: run_view.Request({"seed": 2})}
    write_batch_run(tmp_path / "b", result, view=requests)
    for world, spec in zip((10, 11), specs, strict=True):
        folder = tmp_path / "b" / "worlds" / f"world-{world}"
        view = load(folder)
        run_view.validate(view, folder)
        assert view["run"]["definition_sha256"] == spec.fingerprint
        assert view["run"]["seed"] == world - 9
        manifest = json.loads((folder / "manifest.json").read_text())
        assert "view.json" in manifest["files_sha256"]
    bad = {10: requests[10], 11: run_view.Request({"seed": "2"})}
    with pytest.raises(run_view.ViewRefused, match="run label 'seed'"):
        write_batch_run(tmp_path / "refused", result, view=bad)
    assert not (tmp_path / "refused").exists()  # Every world checked before any output.


# ------------------------------------------------------------------ refusals


def test_an_undeclared_operator_is_refused_and_nothing_is_written(written, monkeypatch, tmp_path):
    _, result, _ = written
    plant(monkeypatch, EXCHANGE, VIEW_LAYERS=None)
    with pytest.raises(run_view.ViewRefused, match=f"{EXCHANGE} declares no VIEW_LAYERS"):
        write_run(tmp_path / "out", result, view=run_view.Request())
    assert not (tmp_path / "out").exists()


def test_an_operator_axis_without_a_set_is_refused(written, monkeypatch):
    spec, result, _ = written
    monkeypatch.delattr(type(OPERATORS[EXCHANGE]), "view_sets", raising=False)
    with pytest.raises(run_view.ViewRefused, match="no set for its axis exchange_route"):
        run_view.prepare(spec, run_view.Request(), layout=result.final.layout)


@pytest.mark.parametrize(
    "request_, message",
    [
        (dict(run={"seed": "1"}), "run label 'seed'"),
        (dict(run={"host": "x"}), "run label 'host'"),
        (dict(recording=run_view.Recording(fields=("no_such_field",))), "unknown or no fields"),
        (dict(recording=run_view.Recording(every=0)), "every is an integer"),
        (dict(recording=run_view.Recording(elements={"cell": ("cell_9",)})), "distinct declared"),
        (
            dict(geometry=run_view.Geometry("um", 2, {"membrane": {"kind": "points"}}, "builder")),
            "only cell and outside",
        ),
        (dict(geometry=run_view.Geometry("px", 2, {}, "builder")), "is not one of"),
        (
            dict(
                geometry=run_view.Geometry(
                    "um", 2, {"cell": {"kind": "points", "centres": [[0, 0], [1, 1]]}}, "builder"
                )
            ),
            "1 finite 2-vectors",
        ),
    ],
)
def test_bad_caller_inputs_are_refused(written, declared, request_, message):
    spec, result, _ = written
    with pytest.raises(run_view.ViewRefused, match=message):
        run_view.prepare(spec, run_view.Request(**request_), layout=result.final.layout)


def test_a_model_outside_version_1_is_refused():
    from tests.batch_fixtures import synthetic_pair

    spec = synthetic_pair().worlds[0].simulation
    with pytest.raises(run_view.ViewRefused, match="No view declarations"):
        run_view.prepare(spec, run_view.Request(), layout=None)


def test_a_time_base_without_rows_is_left_out(tmp_path):
    assert run_view.single_file_bases([0.0, 0.1], []) == {"accepted": [("trajectory.npz", 2)]}
    (tmp_path / "windows.jsonl").write_text(
        json.dumps(
            dict(kind="window", path="chunks/w0.npz", accepted_records=0, observation_records=2)
        )
        + "\n"
        + json.dumps(dict(kind="window", path=None, accepted_records=0, observation_records=0))
        + "\n"
    )
    assert run_view.window_bases(tmp_path / "windows.jsonl") == {
        "observation": [("chunks/w0.npz", 2)]
    }


def test_a_batch_request_names_every_world_once():
    request = run_view.Request()
    assert run_view.requests_for(None, [10, 11]) == {}
    assert run_view.requests_for(request, [10, 11]) == {10: request, 11: request}
    with pytest.raises(run_view.ViewRefused, match="name every world once"):
        run_view.requests_for({10: request}, [10, 11])


# ------------------------------------------------------------------ the engine's source

ENGINE_SOURCE = run_view._engine_source  # The real one: the fixtures plant None.


def test_the_engine_source_comes_from_the_execution_snapshot(written, monkeypatch, tmp_path):
    assert ENGINE_SOURCE(root=tmp_path) is None  # A checkout: no SNAPSHOT.json.
    record = {"git_revision": "abc123", "selected_status_porcelain_v1_z": ""}
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(record))
    clean = ENGINE_SOURCE(root=tmp_path)
    assert clean == {
        "revision": "abc123",
        "dirty": False,
        "from": "the execution snapshot's record (SNAPSHOT.json)",
    }
    (tmp_path / "SNAPSHOT.json").write_text(json.dumps(record | {"dirty": True}))
    assert ENGINE_SOURCE(root=tmp_path)["dirty"] is True
    spec, result, _ = written
    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: clean)
    plan = run_view.prepare(spec, run_view.Request(), layout=result.final.layout)
    view = plan.view({}, "prepared")
    run_view.validate(view)
    assert view["run"]["source"] == clean
    assert "source" not in {u["id"] for u in view["unstated"]}
    later = run_view.prepare(spec, run_view.Request(), layout=result.final.layout, recompute=False)
    assert "source" not in later.view({}, "prepared")["run"]  # A run on disk: not this engine.


# ------------------------------------------------------------------ the reader's check


def _mutations():
    def record(view, **change):
        view["records"][0].update(change)

    def drop_unit(view):
        del view["records"][0]["unit"]

    def null_representation(view):
        view["layers"][0]["representation"] = None

    def unknown_event(view):
        view["events"].append(
            dict(time=0.0, kind="birth", layer="turnover", at={"cell": "cell_9"}, label="")
        )

    def gap(view):
        view["time"]["bases"][0]["files"][0]["rows"][0] = 1

    def duplicate(view):
        view["records"].append(dict(view["records"][0]))

    def bad_sign(view):
        rec = next(r for r in view["records"] if r.get("sign"))
        rec["sign"] = dict(rec["sign"], to="sender")

    def bad_difference(view):
        rec = next(r for r in view["records"] if r.get("difference"))
        rec["difference"] = dict(rec["difference"], minus=rec["difference"]["plus"])

    def roleless_set(view):  # A sign whose set states no roles names no role.
        rec = next(r for r in view["records"] if r.get("sign") and r["set"] == "exchange_route")
        next(s for s in view["sets"] if s["id"] == rec["set"]).pop("roles")

    def foreign_cargo(view):
        next(s for s in view["sets"] if s["id"] == "exchange_route")["carries"][0] = "Xe"

    def bad_end(view):
        view["run"]["end"]["step"] = 1.5

    def host_path(view):
        view["time"]["bases"][0]["files"][0]["file"] = "/tmp/trajectory.npz"

    return [
        ("format", lambda v: v.update(format="cells.run_view@0")),
        ("unit", drop_unit),
        ("axis", lambda v: record(v, axes=["time", "species", "no_such_set"])),
        ("representation", null_representation),
        ("event", unknown_event),
        ("rows", gap),
        ("duplicate", duplicate),
        ("sign", bad_sign),
        ("difference", bad_difference),
        ("roles", roleless_set),
        ("carries", foreign_cargo),
        ("end", bad_end),
        ("path", host_path),
        ("extra key", lambda v: v.update(viewer_hint=1)),
    ]


@pytest.mark.parametrize("name, mutate", _mutations(), ids=[m[0] for m in _mutations()])
def test_the_readers_check_refuses_a_malformed_view(written, name, mutate):
    _, _, root = written
    view = load(root / "a")
    mutate(view)
    with pytest.raises(run_view.ViewInvalid):
        run_view.validate(view, root / "a")


@pytest.mark.parametrize(
    "change",
    [
        dict(array="no_such_array"),
        dict(axes=["time", "cell"], set="cell"),  # amount_increment is [species, cell].
    ],
)
def test_the_readers_check_opens_the_files(written, change):
    _, _, root = written
    view = load(root / "a")
    view["records"][0].update(change)
    run_view.validate(view)  # Well formed on its own ...
    with pytest.raises(run_view.ViewInvalid):
        run_view.validate(view, root / "a")  # ... but not the run's files.


def test_the_readers_check_finds_falling_heat(written, tmp_path):
    _, _, root = written
    view = load(root / "a")
    heat = next(r for r in view["records"] if r["field"] == "membrane_dissipated_energy_pJ")
    with np.load(root / "a" / "trajectory.npz") as saved:
        arrays = {k: saved[k] for k in saved.files}
    arrays[heat["array"]] = -np.abs(arrays[heat["array"]]) - 1.0
    np.savez(tmp_path / "trajectory.npz", **arrays)
    with pytest.raises(run_view.ViewInvalid, match="never falling"):
        run_view.validate(view, tmp_path)


def test_the_readers_check_holds_one_file_open_at_a_time(written, tmp_path):
    """A run cut into one file per row (as a windowed run of one step per window would be) is
    checked under an open-file limit far below its file count, heat carried across files."""
    _, _, root = written
    view = load(root / "a")
    with np.load(root / "a" / "trajectory.npz") as saved:
        arrays = {k: saved[k] for k in saved.files}
    (tmp_path / "chunks").mkdir()
    for base in view["time"]["bases"]:
        names = [base["array"], *(r["array"] for r in view["records"] if r["base"] == base["id"])]
        base["files"] = []
        for i in range(len(arrays[base["array"]])):
            name = f"chunks/{base['id']}-{i:03d}.npz"
            np.savez(tmp_path / name, **{a: arrays[a][i : i + 1] for a in names})
            base["files"].append({"file": name, "rows": [i, i + 1]})
    files = sum(len(b["files"]) for b in view["time"]["bases"])
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (len(os.listdir("/proc/self/fd")) + 6, hard))
    try:
        run_view.validate(view, tmp_path)
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    assert files > 6
    heat = next(r for r in view["records"] if r["field"] == "face_dissipated_energy_pJ")
    first = next(f for b in view["time"]["bases"] if b["id"] == heat["base"] for f in b["files"])
    with np.load(tmp_path / first["file"]) as saved:
        changed = {k: saved[k] for k in saved.files}
    np.savez(tmp_path / first["file"], **(changed | {heat["array"]: changed[heat["array"]] + 1}))
    with pytest.raises(run_view.ViewInvalid, match="never falling"):
        run_view.validate(view, tmp_path)  # A fall between two files is found.


# ------------------------------------------------------------------ geometry and a division


def test_a_builders_geometry_is_placed_on_its_set(declared):
    spec = secretion(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
    )
    geometry = run_view.Geometry(
        "um",
        2,
        {"cell": {"kind": "points", "centres": [[0.0, 0.0], [12.0, 0.0]], "radius": 6.0}},
        "a test builder: two cells 12 um apart",
    )
    plan = run_view.prepare(
        spec, run_view.Request(geometry=geometry), layout=initialise(spec).layout
    )
    view = plan.view({}, "write_run")
    run_view.validate(view)
    cell = next(s for s in view["sets"] if s["id"] == "cell")
    assert cell["geometry"] == {
        "kind": "points",
        "centres": [[0.0, 0.0], [12.0, 0.0]],
        "radius": 6.0,
    }
    assert view["space"] == {
        "unit": "um",
        "dimensions": 2,
        "representation": "prescribed",
        "source": "a test builder: two cells 12 um apart",
    }
    assert "geometry" not in {u["id"] for u in view["unstated"]}
    bad = run_view.Geometry("um", 2, {"cell": {"kind": "points", "centres": [[0, 0]]}}, "b")
    with pytest.raises(run_view.ViewRefused, match="2 finite 2-vectors"):
        run_view.prepare(spec, run_view.Request(geometry=bad), layout=initialise(spec).layout)


def test_the_inner_model_alone_carries_its_laws_and_gate_rows():
    """@3 alone (the heredity cell, with Kir2.1 and NaV1.2 populations): every record is @3's,
    each population carries its law with its provenance, and its gate rows name the set gate."""
    from cells.models import inner_laws
    from tests import partition_fixtures as pf

    spec = parse_spec(pf.parent())
    plan = run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
    view = plan.view({"observation": [("trajectory.npz", 2)]}, "write_run")
    run_view.validate(view)
    assert view["run"]["engine_models"] == ["cells.model.resolved_pump_tissue@3"]
    assert view["run"]["composition"] is None
    assert {r["owner"] for r in view["records"]} == {"cells.model.resolved_pump_tissue@3"}
    sets = {s["id"]: s for s in view["sets"]}
    laws = [law for law in sets["channel"]["laws"] if law is not None]
    assert laws and all(
        law["provenance"] == inner_laws.CHANNEL_LAWS[law["law_id"]].provenance for law in laws
    )
    assert sets["gate"]["ids"] == ["gate_0", "gate_1"]
    gated = [law for law in laws if law["gates"]]
    assert gated and all(law["gates"] == ["m", "h"] for law in gated)
    assert not any(sets["membrane"]["pumps"])  # The fixture removes the parent's pump.
    constants = {c["id"] for c in view["constants"]}
    assert constants == set(run_view.VIEW_FIELD_AXES) | reference_constants()


def test_pumps_are_membrane_columns_with_their_rows_per_cycle():
    """Requirement 6: each pump's law, provenance and rows per cycle by role (inward-positive),
    from its law's declaration, on its membrane's entry."""
    from cells.models import inner_laws
    from validation.tissue import pump_water_fixtures as wfx

    spec = parse_spec(wfx.heredity_cell("H", dt=1e-3, end_time=0.004))
    plan = run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
    pumps = [p for p in plan.sets["membrane"]["pumps"] if p is not None]
    assert pumps
    for pump in pumps:
        law = inner_laws.PUMP_LAWS[pump["law_id"]]
        assert [(m["role"], m["count"]) for m in pump["per_cycle"]] == list(law.moves)
        assert [m["species"] for m in pump["per_cycle"]] == ["Na", "K"]
        assert pump["per_cycle_sign"] == "inward-positive"
        assert pump["provenance"] == law.provenance
    cycles = plan.fields["pump_cycles"]
    assert cycles.sign["from"] == "outside" and cycles.sign["to"] == "inside"


# ------------------------------------------------------------------ declarations


def test_the_inner_models_own_declarations_describe_every_field(written):
    """The writer keeps no table of the inner model's fields: every record of
    cells.model.resolved_pump_tissue@3's fields takes its unit, kind, layer and orientation (a flow's sign or
    a difference's ends, with who confirmed it) from @3's own declarations (models/surface_pump_v3),
    and @3's layers are its VIEW_LAYERS."""
    _, _, root = written
    view = load(root / "a")
    assert not hasattr(run_view, "TISSUE_3") and not hasattr(run_view, "INNER_TABLES")
    fields = {*tissue3.STATE_AXES, *(k for k in tissue3.OBSERVATION_FIELDS if k != "times")}
    records = [r for r in view["records"] if r["owner"] == tissue3.MODEL_ID]
    assert {r["field"] for r in records} == fields
    for record in records:
        name = record["field"]
        declared = (tissue3.UNITS[name], tissue3.RECORD_KINDS[name], tissue3.RECORD_LAYERS[name])
        assert (record["unit"], record["kind"], record["layer"]) == declared, record["id"]
        sign = tissue3.ORIENTATION.get(name)
        key = "difference" if sign is not None and "plus" in sign else "sign"
        assert record.get(key) == (None if sign is None else dict(sign)), record["id"]
    layers = [x for x in view["layers"] if x["owner"] == tissue3.MODEL_ID]
    assert [{k: x[k] for k in ("id", "label", "representation")} for x in layers] == [
        dict(x) for x in tissue3.VIEW_LAYERS
    ]


def test_a_kind_worlds_sets_and_records_come_from_its_kinds(monkeypatch):
    """A kind world (FR-4's development world without its transporter, as
    test_inner_view_declarations' kind test; host only, no run): the passive routes' own set (their
    view_sets: roles, carried species, law, host), the proton buffer's node axis on the view's node
    set (VIEW_AXIS_SETS), and every field of the structure described by its kinds' declarations
    folded into @3's."""
    from validation.compartment_ph_engine import definitions as defs

    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    raw = defs.development_world(defs.fr4_world())
    raw["model"].pop("transporters")
    spec = parse_spec(raw)
    _, layout = get_model(spec.model).initial_values(spec)
    plan = run_view.prepare(spec, layout=layout)
    view = plan.view(run_view.single_file_bases([0.0, 1.0], [0.0, 1.0]), "write_run")
    run_view.validate(view)
    sets = {s["id"]: s for s in view["sets"]}
    routes = sets["passive_route"]
    assert routes["owner"] == tissue3.MODEL_ID and set(routes["roles"]) == {"inside", "outside"}
    assert routes["ids"] == [r["id"] for r in raw["model"]["passive_routes"]]
    laws = [r["law"] for r in raw["model"]["passive_routes"]]
    assert [law["law_id"] for law in routes["laws"]] == laws  # The law IDs pass through...
    assert all(isinstance(k, str) and "@" not in k for k in routes["kinds"])  # ...kinds are words.
    records = {r["id"]: r for r in view["records"]}
    moved = records["passive_transferred"]
    assert (moved["set"], moved["kind"], moved["unit"]) == ("passive_route", "cumulative", "fmol")
    assert (moved["sign"]["from"], moved["sign"]["to"]) == ("outside", "inside")
    assert (records["observed_pH"]["set"], records["observed_pH"]["unit"]) == ("node", "pH")


RECORDED_KIND_FREE = {  # A kind-free world's name: the field its row reads.
    "FR-51's block without kinds (D402)": "channel_unblocked_fraction",
    "FR-50's own one-way records": "one_way_forward_fmol",
}


def kind_free_world(name):
    """A world that declares no kind but records its own fields: FR-51's run world (a blocked
    population), or FR-50's World 1 (@3's own one-way records, beside its block)."""
    if name.startswith("FR-51"):
        from validation.fr51 import engine as fr51

        return fr51.run_world()
    from validation.fr50 import engine as fr50

    cases = fr50._cases()
    return fr50.world_1(cases["E1"], cases["E4"], dt=1e-4, end=1e-3)


@pytest.mark.parametrize("name", list(RECORDED_KIND_FREE))
def test_a_kind_free_world_s_own_records_are_described(name, monkeypatch):
    """D402 (host, about 1 s each): a world that declares no kind still folds @3's records of what
    it declares into its view declarations, so the view states them: FR-51's unblocked fraction
    (before D402 the writer refused it, "declares no axes, unit or layer", since only a kind world
    folded them), and FR-50's own one-way records, on their pair set with each pair's entity and
    species, forward from origin to destination. Plant: the old fold, kinds only, refuses both."""
    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    spec = parse_spec(kind_free_world(name))
    impl = get_model(spec.model)
    assert not impl.structure.kinds
    _, layout = impl.initial_values(spec)
    plan = run_view.prepare(spec, layout=layout)
    view = plan.view(run_view.single_file_bases([0.0, 1e-3], [0.0, 1e-3]), "write_run")
    run_view.validate(view)
    records, sets = {r["field"]: r for r in view["records"]}, {s["id"]: s for s in view["sets"]}
    field = RECORDED_KIND_FREE[name]
    if name.startswith("FR-51"):
        assert (records[field]["unit"], records[field]["kind"]) == ("1", "level")
    else:
        forward, gap = records[field], records["one_way_gap_relative"]
        assert (forward["set"], forward["unit"], forward["kind"]) == (
            "one_way_pair", "fmol", "cumulative",
        )  # fmt: skip
        assert (forward["sign"]["from"], forward["sign"]["to"]) == ("origin", "destination")
        assert (gap["unit"], gap["kind"]) == ("1", "level")
        pairs = sets["one_way_pair"]
        assert pairs["ids"] == [f"{k}:{e}:{s}" for k, e, s in impl.structure.one_way_records]
        assert pairs["carries"] == ["K", "K"] and pairs["kinds"] == ["channel", "membrane"]
    monkeypatch.setattr(tissue3, "declares_view", lambda structure: bool(structure.kinds))
    before = tissue3.InnerImplementation(impl.structure)  # The plant: the fold before D402,
    monkeypatch.setattr("cells.registry.models.get_model", lambda model: before)  # uncached.
    with pytest.raises(run_view.ViewRefused, match="declares no axes, unit or layer"):
        run_view.prepare(spec, layout=layout)


def test_the_injections_records_layer_and_events(monkeypatch):
    """The writer reads cells.operator.electrode_current_injection@1's own declarations (host only, no run):
    each field's unit (from its name), axes, kind and prescribed layer, and each scheduled current
    as an event at the electrode's cell."""
    from tests.run_view_fixtures import INJECTION, injection_world

    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    spec = parse_spec(injection_world([(0, 1e-12), (2, -1e-12)], end=0.004))
    _, layout = get_model(spec.model).initial_values(spec)
    plan = run_view.prepare(spec, layout=layout)
    view = plan.view(run_view.single_file_bases([0.0, 0.004], [0.0, 0.004]), "write_run")
    run_view.validate(view)
    records = {r["id"]: r for r in view["records"]}
    expected = {
        "injection_supplied_fmol": ("fmol", ["time", "species", "cell"]),
        "injection_removed_fmol": ("fmol", ["time", "species", "cell"]),
        "injection_charge_C": ("C", ["time", "cell"]),
        "injection_image_charge_C": ("C", ["time", "outside"]),
        "injection_work_pJ": ("pJ", ["time", "cell"]),
        "injection_energy_magnitude_pJ": ("pJ", ["time", "cell"]),
    }
    for name, (unit, axes) in expected.items():
        for record_id in (name, f"observed_{name}"):
            record = records[record_id]
            got = tuple(record[k] for k in ("unit", "axes", "kind", "layer", "owner"))
            assert got == (unit, axes, "cumulative", "injection", INJECTION), record_id
    (layer,) = [x for x in view["layers"] if x["owner"] == INJECTION]
    assert (layer["id"], layer["representation"]) == ("injection", "prescribed")
    cell = spec.model.cells[0].id
    assert [(e["time"], e["kind"], e["at"]) for e in view["events"]] == [
        (0.0, "current", {"cell": cell}),
        (0.002, "current", {"cell": cell}),
    ]


# The operators' declarations the run view reads by getattr and that are not declared yet (the
# requested contract seams): only shrink, as each owner declares them.
PENDING_UNITS = frozenset(
    {
        ("cells.operator.ideal_osmosis_linear_compliance_water@1", "water_availability"),
        ("cells.operator.isopotential_partition@1", "division_applied"),
        ("cells.operator.isopotential_partition@1", "partition_slot_phase"),
        ("cells.operator.isopotential_partition@1", "partition_units_moved"),
        ("cells.operator.k_anion_symport_mass_action@1", "symport_availability"),
        ("cells.operator.k_anion_symport_mass_action@1", "symport_volume_factor"),
        ("cells.operator.membrane_entity_state@1", "population_abundance_increment"),
        ("cells.operator.membrane_entity_state@1", "population_units"),
        ("cells.operator.scheduled_cell_replacement@1", "generation"),
        ("cells.operator.scheduled_cell_replacement@1", "junction_abundance"),
        ("cells.operator.scheduled_cell_replacement@1", "junction_abundance_deficit"),
        ("cells.operator.scheduled_cell_replacement@1", "occupant_template"),
        ("cells.operator.scheduled_cell_replacement@2", "generation"),
        ("cells.operator.scheduled_cell_replacement@2", "junction_abundance"),
        ("cells.operator.scheduled_cell_replacement@2", "junction_abundance_deficit"),
        ("cells.operator.scheduled_cell_replacement@2", "occupant_template"),
        ("cells.operator.scheduled_membrane_insertion@1", "inserted_units"),
        ("cells.operator.scheduled_membrane_insertion@1", "insertion_opened"),
        ("cells.operator.scheduled_membrane_insertion@2", "inserted_units"),
        ("cells.operator.scheduled_membrane_insertion@2", "insertion_opened"),
        ("cells.operator.site_occupancy@1", "site_occupancy"),
        ("cells.operator.species_regulated_availability@1", "coupling_enabled"),
        ("cells.operator.species_regulated_availability@1", "coupling_factor"),
        ("cells.operator.species_regulated_availability@1", "coupling_step_count"),
        ("cells.operator.species_regulated_availability@1", "regulatory_crossing_step"),
        ("cells.operator.species_regulated_availability@1", "regulatory_input_integral"),
        ("cells.operator.species_regulated_availability@1", "regulatory_state"),
        ("cells.operator.species_regulated_availability@1", "regulatory_writes_applied"),
    }
)
# Operators' own axes without a declared set (view_sets).
PENDING_SETS = frozenset(
    {
        ("cells.operator.isopotential_partition@1", "division_slot"),
        ("cells.operator.site_occupancy@1", "site_population"),
        ("cells.operator.species_regulated_availability@1", "coupling"),
        ("cells.operator.species_regulated_availability@1", "one"),
        ("cells.operator.species_regulated_availability@1", "regulatory_slot"),
    }
)


def _pending():
    units, axes, sets = set(), set(), set()
    for law, op in OPERATORS.items():
        for name in (*op.STATE_AXES, *op.READOUT_COLUMNS):
            if not (op.UNITS.get(name) or run_view._suffix_unit(name)):
                units.add((law, name))
        for name in op.READOUT_COLUMNS:
            if name not in op.OBSERVATION_AXES:
                axes.add((law, name))
        own = {a for v in op.STATE_AXES.values() for a in v if a not in run_view.AXIS_SETS}
        if own and type(op).view_sets is Operator.view_sets:  # The contract's default: none.
            sets |= {(law, a) for a in own}
    return units, axes, sets


def test_the_operators_pending_view_declarations_only_shrink():
    """The design's unit test (§3): every field of the composite family resolves to a unit, but
    for the listed ones, whose owners' UNITS are a requested seam; likewise sets for operators'
    own axes (view_sets). Readout columns without OBSERVATION_AXES are every operator's today."""
    units, axes, sets = _pending()
    assert units <= PENDING_UNITS, sorted(units - PENDING_UNITS)
    assert sets <= PENDING_SETS, sorted(sets - PENDING_SETS)
    readouts = {(law, k) for law, op in OPERATORS.items() for k in op.READOUT_COLUMNS}
    assert axes <= readouts
    assert all(issubclass(type(op), Operator) for op in OPERATORS.values())
