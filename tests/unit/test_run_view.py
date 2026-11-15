"""The run view (D154; docs/RUN_VIEW_DESIGN.md; cells/run_view.py): write_run, write_batch_run,
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
* Every field of resolved_pump_tissue@3 is described; the operators' missing declarations (the
  requested seams) only shrink.

Declarations an operator does not carry yet are planted for a test's duration only.
"""

import json
import os
import resource

import numpy as np
import pytest

from cells import run_view
from cells.batch_io import write_batch_run
from cells.core.batch import run_batch
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.state import initialise
from cells.io import write_run
from cells.models import surface_pump_v3 as tissue3
from cells.models.operators import OPERATORS
from cells.models.operators.contract import Operator
from cells.models.registry import get_model
from tests.batch_fixtures import definition
from tests.run_view_fixtures import (
    EXCHANGE,
    TURNOVER,
    declare_secretion,
    load,
    plant,
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
    spec, _, root = written
    view = load(root / "a")
    run_view.validate(view, root / "a")
    data = (root / "a" / "view.json").read_bytes()
    assert data == (root / "b" / "view.json").read_bytes()
    assert str(root).encode() not in data and b"/mnt/" not in data
    model = get_model(spec.model)
    assert view["run"]["engine_models"] == [
        "resolved_pump_composite@1",
        "resolved_pump_tissue@3",
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
    assert records["observed_membrane_transferred"]["sign"]["from"] == "inside"
    assert records["observed_reservoir_supplied"]["sign"]["to"] == "node"
    assert records["observed_exchange_moved_fmol"]["layer"] == "exchange"
    assert records["observed_exchange_work_pJ"]["kind"] == "cumulative"  # A declared work field.
    # Its kind and sign are the owner's to declare: an accumulator may be a retirement record.
    assert {"kind", "sign"}.isdisjoint(records["observed_exchange_moved_fmol"])
    assert records["face_dissipated_energy_pJ"]["monotone"] == "non-decreasing"
    assert "resets" not in records["face_dissipated_energy_pJ"]  # Nothing retires here.
    assert {c["id"] for c in view["constants"]} >= {"temperature", "valence", "volume"}
    assert {(u["id"], u["what"]) for u in view["unstated"]} >= {
        ("exchange_moved_fmol", "kind"),
        ("turnover_energy_magnitude_pJ", "kind"),
        ("geometry", "geometry"),
    }
    assert view["events"] == [] and view["space"] is None
    # The same view, written afterwards from the saved run.
    out = tmp_path / "later"
    run_view.write_view(root / "plain", out=out, run={"label": "test run"})
    assert (out / "view.json").read_bytes() == data


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
    assert view["run"]["engine_models"] == ["resolved_pump_tissue@3"]
    assert view["run"]["composition"] is None
    assert {r["owner"] for r in view["records"]} == {"resolved_pump_tissue@3"}
    sets = {s["id"]: s for s in view["sets"]}
    laws = [law for law in sets["channel"]["laws"] if law is not None]
    assert laws and all(
        law["provenance"] == inner_laws.CHANNEL_LAWS[law["law_id"]].provenance for law in laws
    )
    assert sets["gate"]["ids"] == ["gate_0", "gate_1"]
    gated = [law for law in laws if law["gates"]]
    assert gated and all(law["gates"] == ["m", "h"] for law in gated)
    assert not any(sets["membrane"]["pumps"])  # The fixture removes the parent's pump.
    assert {c["id"] for c in view["constants"]} == set(run_view.VIEW_FIELD_AXES)


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


def test_every_field_of_the_inner_model_is_described():
    fields = {*tissue3.STATE_AXES, *(k for k in tissue3.OBSERVATION_FIELDS if k != "times")}
    assert set(run_view.TISSUE_3) == fields
    layer_ids = {layer["id"] for layer in run_view.TISSUE_3_LAYERS}
    for name, (axes, unit, kind, layer, _) in run_view.TISSUE_3.items():
        assert (axes is None) == (name in tissue3.STATE_AXES), name
        assert all(a in run_view.AXIS_SETS for a in axes or tissue3.STATE_AXES[name]), name
        assert unit or run_view._suffix_unit(name), name
        assert kind in run_view.KINDS and layer in layer_ids, name
        if name.endswith(run_view.HEAT_SUFFIX):
            assert kind == "cumulative"


# The operators' declarations the run view reads by getattr and that are not declared yet (the
# requested contract seams): only shrink, as each owner declares them.
PENDING_UNITS = frozenset(
    {
        ("ideal_osmosis_linear_compliance_water@1", "water_availability"),
        ("isopotential_partition@1", "division_applied"),
        ("isopotential_partition@1", "partition_slot_phase"),
        ("isopotential_partition@1", "partition_units_moved"),
        ("k_anion_symport_mass_action@1", "symport_availability"),
        ("k_anion_symport_mass_action@1", "symport_volume_factor"),
        ("local_species_reactions@1", "reaction_affinity_RT"),
        ("membrane_entity_state@1", "population_abundance_increment"),
        ("membrane_entity_state@1", "population_units"),
        ("scheduled_cell_replacement@1", "generation"),
        ("scheduled_cell_replacement@1", "junction_abundance"),
        ("scheduled_cell_replacement@1", "junction_abundance_deficit"),
        ("scheduled_cell_replacement@1", "occupant_template"),
        ("scheduled_cell_replacement@2", "generation"),
        ("scheduled_cell_replacement@2", "junction_abundance"),
        ("scheduled_cell_replacement@2", "junction_abundance_deficit"),
        ("scheduled_cell_replacement@2", "occupant_template"),
        ("scheduled_membrane_insertion@1", "inserted_units"),
        ("scheduled_membrane_insertion@1", "insertion_opened"),
        ("scheduled_membrane_insertion@2", "inserted_units"),
        ("scheduled_membrane_insertion@2", "insertion_opened"),
        ("site_occupancy@1", "site_occupancy"),
        ("species_regulated_availability@1", "coupling_enabled"),
        ("species_regulated_availability@1", "coupling_factor"),
        ("species_regulated_availability@1", "coupling_step_count"),
        ("species_regulated_availability@1", "regulatory_crossing_step"),
        ("species_regulated_availability@1", "regulatory_input_integral"),
        ("species_regulated_availability@1", "regulatory_state"),
        ("species_regulated_availability@1", "regulatory_writes_applied"),
    }
)
# Operators' own axes without a declared set (view_sets).
PENDING_SETS = frozenset(
    {
        ("isopotential_partition@1", "division_slot"),
        ("local_species_reactions@1", "reaction_route"),
        ("site_occupancy@1", "site_population"),
        ("species_regulated_availability@1", "coupling"),
        ("species_regulated_availability@1", "one"),
        ("species_regulated_availability@1", "regulatory_slot"),
        (EXCHANGE, "exchange_route"),  # Until its declaration commit lands.
    }
)


def _pending():
    units, axes, sets = set(), set(), set()
    for law, op in OPERATORS.items():
        for name in (*op.STATE_AXES, *op.READOUT_COLUMNS):
            if not (getattr(op, "UNITS", {}).get(name) or run_view._suffix_unit(name)):
                units.add((law, name))
        for name in op.READOUT_COLUMNS:
            if name not in getattr(op, "OBSERVATION_AXES", {}):
                axes.add((law, name))
        own = {a for v in op.STATE_AXES.values() for a in v if a not in run_view.AXIS_SETS}
        if own and getattr(op, "view_sets", None) is None:
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
