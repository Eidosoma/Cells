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


@pytest.fixture
def headless(tmp_path, monkeypatch):
    from validation.betse import betse_native_parameter_world_ready_qualification as parameter

    monkeypatch.setattr(stage, "BASE", tmp_path)
    monkeypatch.setattr(parameter, "BASE", tmp_path)
    # Actual metadata function and immutable producer, never a successful owner stand-in.
    assert stage.PARAMETER_METADATA_SHA256 == stage.snapshot.digest(Path(parameter.__file__))
    return NS(output=tmp_path / "headless-pair", parameter=parameter)


def test_inputs_headless_exact_two_switches_preserve_all_other_source_bytes():
    raw = (stage.NATIVE / "sim_config.yaml").read_bytes()
    changed = stage.profiles.transform(raw)
    different = [
        (i, before, after)
        for i, (before, after) in enumerate(
            zip(raw.splitlines(), changed.splitlines(), strict=True), 1
        )
        if before != after
    ]
    assert [row[0] for row in different] == [795, 796]
    assert all(before.replace(b": True ", b": False ") == after for _, before, after in different)
    assert hashlib.sha256(changed).hexdigest() == stage.profiles.HEADLESS_SHA256
    assert hashlib.sha256(raw).hexdigest() == stage.CORE["sim_config.yaml"]


@pytest.mark.parametrize("mutation", ["extra", "transport", "missing", "duplicate", "already"])
def test_inputs_headless_transform_refuses_any_unpinned_origin(mutation):
    raw = (stage.NATIVE / "sim_config.yaml").read_bytes()
    if mutation == "extra":
        raw += b"\n"
    elif mutation == "transport":
        raw = raw.replace(b"True", b"False", 1)
    elif mutation == "missing":
        raw = raw.replace(stage.profiles._BEFORE, b"", 1)
    elif mutation == "duplicate":
        raw += stage.profiles._BEFORE
    else:
        raw = stage.profiles.transform(raw)
    with pytest.raises(ValueError):
        stage.profiles.transform(raw)


def test_inputs_headless_pair_uses_actual_parameter_metadata_and_independent_complete_inputs(
    headless,
):
    before = stage.inventory(stage.NATIVE)
    value = stage.prepare(headless.output, profile="headless")
    assert value["kind"] == stage.HEADLESS_KIND
    assert value["configuration_changes"] == stage.profiles.changes()
    assert value["raw_configuration_and_images_unchanged"] is False
    assert value["source_inventory"] == before
    selected = stage.profiles.selected_inventory(value)
    assert [
        name for name in before["files"] if before["files"][name] != selected["files"][name]
    ] == ["sim_config.yaml"]
    seen = set()
    for mode in stage.MODES:
        row = value["modes"][mode]
        checked = headless.parameter.input_program(row["program"]["path"], row["program"]["sha256"])
        assert checked["input_profile"] == "headless"
        assert checked["configuration_changes"] == stage.profiles.changes()
        for name in selected["files"]:
            path = Path(row["config"]) / name
            info = path.stat()
            assert info.st_nlink == 1 and not info.st_mode & 0o222
            assert (info.st_dev, info.st_ino) not in seen
            seen.add((info.st_dev, info.st_ino))
    pin = stage.snapshot.digest(headless.output / "inputs.json")
    assert stage.verify(headless.output, pin) == value
    # A selected unused sibling remains inspectable after native output on the other side.
    used = headless.output / "original/config/INITS/new-native-output"
    used.parent.mkdir(exist_ok=True)
    used.write_bytes(b"test-only consumed directory epoch")
    assert stage.verify(headless.output, pin, mode="disabled") == value
    with pytest.raises(ValueError):
        stage.verify(headless.output, pin, mode="original")
    assert stage.inventory(stage.NATIVE) == before


def test_inputs_headless_profile_does_not_change_original_default_program(headless):
    value = stage.prepare(headless.output)
    assert value["kind"] == stage.KIND and value["raw_configuration_and_images_unchanged"]
    assert "configuration_profile" not in value and "input_inventory" not in value
    for row in value["modes"].values():
        checked = headless.parameter.input_program(row["program"]["path"], row["program"]["sha256"])
        assert "input_profile" not in checked and "configuration_changes" not in checked
        assert checked["files"]["sim_config.yaml"]["sha256"] == stage.CORE["sim_config.yaml"]


@pytest.mark.parametrize("profile", [None, True, "other", 1])
def test_inputs_headless_unknown_profile_refuses_before_output(headless, profile):
    with pytest.raises(ValueError):
        stage.prepare(headless.output, profile=profile)
    assert not headless.output.exists()


@pytest.mark.parametrize("profile", [None, "original", "other", True])
def test_inputs_headless_bytes_require_exact_explicit_program_profile(headless, profile):
    value = stage.prepare(headless.output, profile="headless")
    program = value["modes"]["original"]["program"]
    raw = json.loads(Path(program["path"]).read_bytes())
    if profile is None:
        raw.pop("input_profile")
    else:
        raw["input_profile"] = profile
    path = headless.output / "incorrect-profile.json"
    stage.snapshot.write_json(path, raw)
    with pytest.raises(ValueError):
        headless.parameter.input_program(path, stage.snapshot.digest(path))


@pytest.mark.parametrize("mutation", ["extra_file", "wrong_hash", "lost_label", "wrong_changes"])
def test_inputs_headless_inventory_refuses_rehashed_variant_metadata(headless, mutation):
    value = stage.prepare(headless.output, profile="headless")
    if mutation == "extra_file":
        value["input_inventory"]["files"]["foreign"] = dict(sha256="0" * 64, size_bytes=1)
    elif mutation == "wrong_hash":
        value["input_inventory"]["files"]["sim_config.yaml"]["sha256"] = "0" * 64
    elif mutation == "lost_label":
        value.pop("configuration_profile")
    else:
        value["configuration_changes"][0]["after"] = True
    with pytest.raises(ValueError):
        stage.profiles.selected_inventory(value)


@pytest.mark.parametrize(
    "name",
    [
        "extra_configs/grn_basic.yaml",
        "extra_configs/expression_data.yaml",
        "geo/circle/circle_base.png",
    ],
)
def test_inputs_headless_other_files_cannot_be_modified_or_relabelled(headless, name):
    value = stage.prepare(headless.output, profile="headless")
    path = Path(value["modes"]["original"]["config"]) / name
    assert path.is_file()
    path.chmod(0o644)
    path.write_bytes(path.read_bytes() + b"\n")
    path.chmod(0o444)
    with pytest.raises(ValueError):
        stage.verify(headless.output, stage.snapshot.digest(headless.output / "inputs.json"))


def test_inputs_headless_transform_failure_preserves_partial_copy_and_original_cause(
    headless, monkeypatch
):
    primary, cause = OSError("transform output"), LookupError("same cause")
    primary.__cause__ = cause

    def failed(*args):
        raise primary

    monkeypatch.setattr(stage, "_copy_headless", failed)
    with pytest.raises(OSError) as caught:
        stage.prepare(headless.output, profile="headless")
    assert caught.value is primary and caught.value.__cause__ is cause
    assert (headless.output / "failure.json").is_file()
    assert list((headless.output / "original/config").rglob("*.png"))
    assert not (headless.output / "disabled").exists()


@pytest.mark.parametrize(
    ("profile", "changed_lines"),
    [("original", []), ("headless", [795, 796]), ("headless_core", [387, 501, 795, 796])],
)
def test_inputs_core_profiles_preserve_every_other_original_byte(profile, changed_lines):
    raw = (stage.NATIVE / "sim_config.yaml").read_bytes()
    value = stage.profiles.transform(raw, profile)
    difference = [
        (index, before, after)
        for index, (before, after) in enumerate(
            zip(raw.splitlines(True), value.splitlines(True), strict=True), 1
        )
        if before != after
    ]
    assert [index for index, _, _ in difference] == changed_lines
    assert all(before.replace(b": True ", b": False ") == after for _, before, after in difference)
    assert dict(
        sha256=hashlib.sha256(value).hexdigest(), size_bytes=len(value)
    ) == stage.profiles.main_file(profile)
    # Exact byte comparison covers both original calendars, all numerical settings,
    # custom channel definitions and all inactive event definitions as well.
    assert len(difference) == len(stage.profiles.changes(profile))
    if profile == "headless_core":
        assert stage.profiles.changes(profile)[2:] == [
            dict(path=["cutting event", "event happens"], before=True, after=False),
            dict(path=["general network", "implement network"], before=True, after=False),
        ]


def test_inputs_core_pair_uses_actual_metadata_and_same_bytes_for_both_flux_modes(headless):
    from validation.betse import native_seed_initial_rng as initial_rng

    source = stage.inventory(stage.NATIVE)
    value = stage.prepare(headless.output, profile="headless_core")
    assert value["kind"] == stage.HEADLESS_CORE_KIND
    assert value["configuration_profile"] == "headless_core"
    assert value["configuration_changes"] == stage.profiles.changes("headless_core")
    assert value["held"] and value["physical_or_scientific_claim"] is False
    assert value["source_inventory"] == source
    expected = stage.profiles.inventory(source, "headless_core")
    assert expected["directories"] == source["directories"]
    assert [
        name for name in source["files"] if source["files"][name] != expected["files"][name]
    ] == [stage.profiles.MAIN]
    inodes = set()
    for mode, row in value["modes"].items():
        assert stage.inventory(Path(row["config"])) == expected
        program = headless.parameter.input_program(row["program"]["path"], row["program"]["sha256"])
        assert program["input_profile"] == "headless_core"
        assert program["configuration_changes"] == value["configuration_changes"]
        assert (
            program["files"][stage.profiles.MAIN]["sha256"] == stage.profiles.HEADLESS_CORE_SHA256
        )
        assert "numerical inputs unchanged" in program["origin"]
        # This is the real immutable input witness, not a parameter/phase stand-in.
        assert mode in stage.MODES
        witness = initial_rng.declaration(program)
        assert initial_rng.validate_declaration(witness) is witness
        assert witness["profile"] == "headless_core" and witness["inventory"] == expected
        for name in expected["files"]:
            info = (Path(row["config"]) / name).stat()
            assert not info.st_mode & 0o222 and info.st_nlink == 1
            assert (info.st_dev, info.st_ino) not in inodes
            inodes.add((info.st_dev, info.st_ino))
    assert (
        stage.verify(headless.output, stage.snapshot.digest(headless.output / "inputs.json"))
        == value
    )
    assert stage.inventory(stage.NATIVE) == source


@pytest.mark.parametrize("profile", [None, "original", "headless"])
def test_inputs_core_cannot_be_relabelled_by_actual_parameter_reader(headless, profile):
    value = stage.prepare(headless.output, profile="headless_core")
    program = value["modes"]["original"]["program"]
    raw = json.loads(Path(program["path"]).read_bytes())
    if profile is None:
        raw.pop("input_profile")
    else:
        raw["input_profile"] = profile
    wrong = headless.output / "wrong-profile.json"
    stage.snapshot.write_json(wrong, raw)
    with pytest.raises(ValueError):
        headless.parameter.input_program(wrong, stage.snapshot.digest(wrong))


@pytest.mark.parametrize(
    "mutation",
    ["label", "kind", "omit_change", "extra_change", "integer_false", "inventory", "numeric_bytes"],
)
def test_inputs_core_provenance_or_numeric_byte_drift_refuses(headless, mutation):
    value = stage.prepare(headless.output, profile="headless_core")
    if mutation == "label":
        value["configuration_profile"] = "headless"
    elif mutation == "kind":
        value["kind"] = stage.HEADLESS_KIND
    elif mutation == "omit_change":
        value["configuration_changes"].pop()
    elif mutation == "extra_change":
        value["configuration_changes"].append(
            dict(path=["world options", "world size"], before=True, after=False)
        )
    elif mutation == "integer_false":
        value["configuration_changes"][-1]["after"] = 0
    elif mutation == "inventory":
        value["input_inventory"]["files"][stage.profiles.MAIN] = stage.profiles.main_file(
            "headless"
        )
    else:
        path = Path(value["modes"]["original"]["config"]) / stage.profiles.MAIN
        path.chmod(0o644)
        path.write_bytes(path.read_bytes() + b"\n# undeclared input byte\n")
        path.chmod(0o444)
    altered = headless.output / "inputs.json"
    altered.chmod(0o644)
    altered.write_text(json.dumps(value))
    altered.chmod(0o444)
    with pytest.raises(ValueError):
        stage.verify(headless.output, stage.snapshot.digest(altered))


@pytest.mark.parametrize("source", ["headless", "headless_core", "changed"])
def test_inputs_core_transformation_requires_original_bytes_not_a_retuned_case(source):
    raw = (stage.NATIVE / stage.profiles.MAIN).read_bytes()
    raw = raw + b"\n" if source == "changed" else stage.profiles.transform(raw, source)
    with pytest.raises(ValueError):
        stage.profiles.transform(raw, "headless_core")
