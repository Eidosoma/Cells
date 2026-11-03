"""Metadata-only complete bundle/independence/failure controls."""

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo_inputs as stage
from validation.betse import native_seed_demo_inputs_software as software

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit blocked input-preparation software release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.base.reuse.reuse))
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    fn = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(fn)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    root = tmp_path / "original-data"
    rows = {
        "sim_config.yaml": b"unchanged scalar: 0.0\n",
        "extra_configs/expression_data.yaml": b"literal expression\n",
        "extra_configs/grn_basic.yaml": b"literal grn\n",
        "geo/circle/circle_base.png": b"\x89PNG\x00\xff\x80raw\x00",
        "geo/circle/spot_2.png": b"\xff\x00different image bits",
        "geo/example.svg": b"<svg>original</svg>\n",
    }
    for name, value in rows.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (root / "empty-original-directory").mkdir()
    core = {name: hashlib.sha256(rows[name]).hexdigest() for name in stage.CORE}
    monkeypatch.setattr(stage, "NATIVE", root)
    monkeypatch.setattr(stage, "BASE", tmp_path)
    monkeypatch.setattr(stage, "CORE", core)
    monkeypatch.setattr(stage, "BUNDLE_SHA256", stage._digest(stage.inventory(root)))

    def input_program(path, pin):
        assert stage.snapshot.digest(path) == pin
        value = json.loads(path.read_text())
        config = Path(value["files"]["sim_config.yaml"]["input"]["path"]).parent
        assert value == stage._program(config)
        for name, expected in core.items():
            assert stage.snapshot.digest(config / name) == expected
            assert not (config / name).stat().st_mode & 0o222
        return dict(
            root=str(config),
            directories=[
                str(config / p)
                for p in ("INITS", "SIMS", "RESULTS/init_1", "RESULTS/sim_1", "RESULTS/GRN")
            ],
        )

    monkeypatch.setattr(stage, "_parameter_metadata", lambda: NS(input_program=input_program))
    return NS(root=root, rows=rows, output=tmp_path / "paired", tmp=tmp_path)


def test_inputs_full_pair_keeps_all_original_bytes_paths_and_independent_inodes(bundle):
    result = stage.prepare(bundle.output)
    assert result["held"] and not result["native_execution"]
    assert result["source_tree_sha256"] == stage.BUNDLE_SHA256
    assert tuple(result["modes"]) == ("original", "disabled")
    seen = set()
    for mode in stage.MODES:
        config = bundle.output / mode / "config"
        for name, value in bundle.rows.items():
            target = config / name
            assert target.read_bytes() == value
            info = target.stat()
            assert info.st_nlink == 1 and not info.st_mode & 0o222
            assert (info.st_dev, info.st_ino) not in seen
            seen.add((info.st_dev, info.st_ino))
        assert (config / "empty-original-directory").is_dir()
        assert not (config / "INITS").exists() and not (config / "RESULTS").exists()
    pin = stage.snapshot.digest(bundle.output / "inputs.json")
    assert stage.verify(bundle.output, pin) == result


@pytest.mark.parametrize("mutation", ["change", "missing", "added", "symlink"])
def test_inputs_changed_original_bundle_refuses_before_output(bundle, mutation):
    path = bundle.root / "geo/circle/spot_2.png"
    if mutation == "change":
        path.write_bytes(b"changed")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "added":
        (bundle.root / "new-data").write_bytes(b"new")
    else:
        path.unlink()
        path.symlink_to(bundle.root / "sim_config.yaml")
    with pytest.raises(ValueError):
        stage.prepare(bundle.output)
    assert not bundle.output.exists()


@pytest.mark.parametrize("mutation", ["bits", "writable", "shared_inode", "new_file", "outputs"])
def test_inputs_modified_or_used_copy_refuses_without_repair(bundle, mutation):
    stage.prepare(bundle.output)
    pin = stage.snapshot.digest(bundle.output / "inputs.json")
    config = bundle.output / "disabled/config"
    path = config / "geo/circle/circle_base.png"
    if mutation == "bits":
        path.chmod(0o644)
        path.write_bytes(b"changed image")
        path.chmod(0o444)
    elif mutation == "writable":
        path.chmod(0o644)
    elif mutation == "shared_inode":
        path.unlink()
        os.link(bundle.output / "original/config/geo/circle/circle_base.png", path)
    elif mutation == "new_file":
        (config / "unexpected").write_bytes(b"extra")
    else:
        (config / "INITS").mkdir()
    with pytest.raises(ValueError):
        stage.verify(bundle.output, pin)
    assert stage.snapshot.digest(bundle.output / "inputs.json") == pin


def test_inputs_fresh_sibling_can_be_verified_after_other_modes_native_outputs_exist(bundle):
    stage.prepare(bundle.output)
    pin = stage.snapshot.digest(bundle.output / "inputs.json")
    (bundle.output / "original/config/INITS").mkdir()
    value = stage.verify(bundle.output, pin, mode="disabled")
    assert value["modes"]["disabled"]["config"] == str(bundle.output / "disabled/config")
    with pytest.raises(ValueError):
        stage.verify(bundle.output, pin, mode="original")


def test_inputs_original_distribution_placeholders_are_preserved_with_exact_directory_epoch(
    bundle, monkeypatch
):
    for name in ("INITS/.gitignore", "SIMS/.gitignore", "RESULTS/init_1/.gitignore"):
        path = bundle.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original distribution placeholder\n")
    monkeypatch.setattr(stage, "BUNDLE_SHA256", stage._digest(stage.inventory(bundle.root)))
    result = stage.prepare(bundle.output)
    pin = stage.snapshot.digest(bundle.output / "inputs.json")
    assert stage.verify(bundle.output, pin) == result
    assert result["distribution_output_placeholders_preserved"]
    assert not result["native_simulation_outputs_created"]
    for mode in stage.MODES:
        row = result["modes"][mode]
        assert [state[1:] for state in row["initial_directory_state"]] == [
            [True, True],
            [True, True],
            [True, True],
            [False, False],
            [False, False],
        ]
        assert (bundle.output / mode / "config/INITS/.gitignore").read_bytes() == (
            bundle.root / "INITS/.gitignore"
        ).read_bytes()


@pytest.mark.parametrize("limit", ["MAX_FILES", "MAX_BYTES", "MAX_FILE_BYTES"])
def test_inputs_limits_refuse_before_copy(bundle, limit, monkeypatch):
    monkeypatch.setattr(stage, limit, 1)
    with pytest.raises(ValueError):
        stage.prepare(bundle.output)
    assert not bundle.output.exists()


def test_inputs_failed_copy_keeps_partial_files_and_cause_without_retry(bundle, monkeypatch):
    primary = OSError("same read error")
    cause = LookupError("same cause")
    primary.__cause__ = cause
    original, calls = stage._copy_file, []

    def copy(source, target, row):
        calls.append(target)
        if len(calls) == 3:
            raise primary
        return original(source, target, row)

    monkeypatch.setattr(stage, "_copy_file", copy)
    with pytest.raises(OSError) as caught:
        stage.prepare(bundle.output)
    assert caught.value is primary and primary.__cause__ is cause
    assert len(calls) == 3 and all(path.is_file() for path in calls[:2])
    assert not (bundle.output / "disabled").exists()
    assert not (bundle.output / "inputs.json").exists()
    assert json.loads((bundle.output / "failure.json").read_text())["partial_files_preserved"]


def test_inputs_report_failure_does_not_replace_original_copy_error(bundle, monkeypatch):
    class Falsey(OSError):
        def __bool__(self):
            return False

    primary, secondary = Falsey("copy"), OSError("report")

    def copy(*args):
        raise primary

    def write(*args):
        raise secondary

    with monkeypatch.context() as patch:
        patch.setattr(stage, "_copy_file", copy)
        patch.setattr(stage.snapshot, "write_json", write)
        with pytest.raises(Falsey) as caught:
            stage.prepare(bundle.output)
        assert caught.value is primary and primary.input_preparation_capture_error is secondary


@pytest.mark.parametrize("location", ["source", "existing", "escape", "linked"])
def test_inputs_output_domain_refuses_without_existing_data_edits(bundle, location):
    if location == "source":
        output = bundle.root / "new"
    elif location == "existing":
        output = bundle.root
    elif location == "escape":
        output = bundle.tmp / ".." / "escape"
    else:
        link = bundle.tmp / "link"
        link.symlink_to(bundle.root, target_is_directory=True)
        output = link / "new"
    with pytest.raises(ValueError):
        stage.prepare(output)
    assert (bundle.root / "sim_config.yaml").read_bytes() == bundle.rows["sim_config.yaml"]


def test_inputs_source_plan_does_not_claim_image_or_parameter_execution():
    plan = stage.source_plan()
    assert plan["full_original_geo_and_extra_configs"]
    assert not plan["native_execution"] and not plan["actual_parameter_or_phase_authority"]
    assert (
        plan["bundle_sha256"] == "a46d83ac79195a2e15078feccd5e0fc62804ca1976042cc9516c30a9f859db27"
    )


@pytest.mark.parametrize(
    "roster", [["validation/launcher.py"], ("outputs/launcher.py",), ("../outside.py",)]
)
def test_inputs_execution_snapshot_extension_refuses_mutable_or_outside_roster(roster):
    from validation.betse import native_seed_demo as demo

    with pytest.raises(ValueError):
        demo.prepare(
            None,
            None,
            inputs=None,
            inputs_sha256=None,
            python=None,
            bootstrap=None,
            bootstrap_sha256=None,
            auxiliary_configuration=None,
            flux_operator="original",
            extra_sources=roster,
        )
