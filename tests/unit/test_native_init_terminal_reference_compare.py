"""Stdlib-only synthetic saved-data controls; no source trial or live owner."""

import ast
import copy
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from validation.betse import native_init_terminal_reference_compare as compare
from validation.betse import native_init_terminal_reference_compare_software as software

if TYPE_CHECKING:
    # Snapshot the actual partial-context producer for a read-only AST assertion.
    from cells.processes import betse_native_init_terminal  # noqa: F401


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit stdlib-only blocked comparison software required")
    with software.blocked(tmp_path):
        yield


def _array(raw=None, shape=None, strides=None, dtype="<f8"):
    raw = struct.pack("<2d", -0.0, 1.0) if raw is None else raw
    shape = [2] if shape is None else shape
    layout = dict(
        dtype=dtype,
        shape=shape,
        strides_bytes=[8] if strides is None else strides,
        C_contiguous=True,
        F_contiguous=True,
    )
    return dict(
        kind="array",
        layout=layout,
        bytes=dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw)),
    )


def _view(count=3, *, complete=True, matched_rng=False):
    values = []
    for ordinal in range(count):
        values.append(
            dict(
                ordinal=ordinal,
                epoch=compare.EPOCH,
                source_time_bits=struct.pack("!d", ordinal * 0.125).hex(),
                sampled=ordinal % 2 == 0,
                dt_bits=struct.pack("!d", 0.125).hex(),
                fields={
                    name: _array(struct.pack("<2d", float(ordinal), -0.0))
                    for name in compare.FIELDS
                },
            )
        )
    source = {"betse/science/sim.py": "a" * 64, "betse/science/chemistry/networks.py": "b" * 64}
    rng = (
        dict(
            available=True,
            epoch="same_declared_initial_epoch",
            state=dict(numpy="full typed synthetic witness", python="full synthetic witness"),
        )
        if matched_rng
        else dict(available=False, reason="no_common_epoch", retained_epoch="before_SEED")
    )
    return dict(
        authenticated=True,
        complete=complete,
        mode="original",
        rows=values,
        selected_input_files={"sim_config.yaml": "c" * 64},
        configuration_profile="headless",
        native_inventory=source,
        shared_native_sources=source,
        initial_rng=rng,
    )


def _node(kind, value):
    if kind == "float":
        return dict(type=kind, bits=struct.pack("<d", value).hex())
    return dict(type=kind, value=value)


def _wire_array(raw=None, shape=None, dtype="<f8", strides=None):
    raw = struct.pack("<2d", 0.0, -0.0) if raw is None else raw
    layout = dict(
        dtype=dtype,
        shape=[2] if shape is None else shape,
        strides_bytes=[8] if strides is None else strides,
        C_contiguous=True,
        F_contiguous=True,
    )
    if strides == [-8]:
        layout.update(C_contiguous=False, F_contiguous=False)
    return dict(
        tree=dict(
            type="array",
            layout=layout,
            column="native_000000",
            sha256=hashlib.sha256(raw).hexdigest(),
        ),
        columns={
            "native_000000": dict(dtype=dtype, shape=layout["shape"], raw_bytes_hex=raw.hex())
        },
    )


def _dict_wire(values, columns=None):
    return dict(
        tree=dict(
            type="dict", values=[[_node("str", key), value] for key, value in values.items()]
        ),
        columns={} if columns is None else columns,
    )


def test_reference_compare_source_plan_is_forensic_only():
    plan = compare.source_plan()
    assert plan["stdlib_readers_only"] and plan["no_NumPy_model_RNG_or_owner_imports"]
    assert plan["current_common_initial_rng_witness_available"] is False
    assert plan["tolerance"] is None and plan["epochs"]["searched_shift"] is False
    assert plan["scientific_physical_checkpoint_or_solver_repair_credit"] == 0


@pytest.mark.parametrize("count", [1, 3, 500, 512])
def test_reference_compare_complete_original_calendar_counts(count):
    left, right = _view(count, matched_rng=True), _view(count, matched_rng=True)
    result = compare.compare_views(left, right)
    assert result["paired_source_complete"] and result["compared_epochs"] == count
    assert result["aligned_observations_equal"] is True
    assert result["exact_execution_parity"]["available"] is True
    assert result["exact_execution_parity"]["equal"] is True
    assert result["scientific_physical_checkpoint_credit"] == 0


@pytest.mark.parametrize("case", ["missing", "different", "different_epoch"])
def test_reference_compare_unmatched_rng_is_unavailable_not_numerical_mismatch(case):
    left, right = _view(matched_rng=True), _view(matched_rng=True)
    if case == "missing":
        right["initial_rng"] = dict(available=False)
    elif case == "different":
        right["initial_rng"]["state"]["numpy"] = "different exact bits"
    else:
        right["initial_rng"]["epoch"] = "after_seed_not_before_seed"
    right["rows"][0]["fields"]["vm"] = _array(struct.pack("<2d", 7.0, 8.0))
    result = compare.compare_views(left, right)
    assert result["exact_execution_parity"]["available"] is False
    assert result["exact_execution_parity"]["equal"] is None
    assert result["aligned_observations_equal"] is False
    assert "mismatch" not in result["status"]


@pytest.mark.parametrize("field", ["source_time_bits", "sampled", "dt_bits", "epoch", "ordinal"])
def test_reference_compare_no_silent_time_shift_or_epoch_relabel(field):
    left, right = _view(), _view()
    if field == "sampled":
        right["rows"][1][field] = not right["rows"][1][field]
    elif field == "ordinal":
        right["rows"][1][field] += 1
    elif field == "epoch":
        right["rows"][1][field] = "before_body"
    else:
        right["rows"][1][field] = struct.pack("!d", 0.25).hex()
    if field in ("epoch", "ordinal"):
        with pytest.raises(ValueError):
            compare.compare_views(left, right)
    else:
        result = compare.compare_views(left, right)
        assert result["observations"][1]["status"] == "different_explicit_time_epoch"
        assert result["observations"][1]["fields"] == {}


@pytest.mark.parametrize(
    "field", ["mode", "selected_input_files", "configuration_profile", "native_inventory"]
)
def test_reference_compare_input_flux_source_provenance_cannot_drift(field):
    left, right = _view(), _view()
    if field == "native_inventory":
        left[field]["betse/science/sim.py"] = "d" * 64
    elif field == "selected_input_files":
        right[field]["sim_config.yaml"] = "d" * 64
    else:
        right[field] = "different"
    result = compare.compare_views(left, right)
    assert result["status"] == "incompatible_provenance" and result["observations"] == []


@pytest.mark.parametrize("complete_a,complete_b", [(False, True), (True, False), (False, False)])
def test_reference_compare_partial_failed_source_never_becomes_complete(complete_a, complete_b):
    result = compare.compare_views(
        _view(2, complete=complete_a, matched_rng=True),
        _view(3, complete=complete_b, matched_rng=True),
    )
    assert result["status"] == "compared_partial_failed_sources"
    assert result["paired_source_complete"] is False
    assert result["observations"][-1]["status"] == "missing_observation"
    assert result["exact_execution_parity"]["equal"] is None


def test_reference_compare_missing_field_is_unavailable_not_zero():
    left, right = _view(matched_rng=True), _view(matched_rng=True)
    del right["rows"][1]["fields"]["fluxes_env_x"]
    result = compare.compare_views(left, right)
    assert result["observations"][1]["fields"]["fluxes_env_x"] == dict(available=False, equal=None)
    assert result["unavailable_observations"] == 1
    assert result["exact_execution_parity"]["available"] is False


@pytest.mark.parametrize("defect", ["dtype", "strides", "shape", "nan_payload", "signed_zero"])
def test_reference_compare_exact_typed_bits_and_layout(defect):
    left, right = _view(matched_rng=True), _view(matched_rng=True)
    node = right["rows"][0]["fields"]["vm"]
    if defect in ("dtype", "strides", "shape"):
        node["layout"][{"dtype": "dtype", "strides": "strides_bytes", "shape": "shape"}[defect]] = {
            "dtype": ">f8",
            "strides": [-8],
            "shape": [1, 2],
        }[defect]
    else:
        raw = (
            bytes.fromhex("010000000000f87f0000000000000000")
            if defect == "nan_payload"
            else struct.pack("<2d", 0.0, 0.0)
        )
        node["bytes"]["sha256"] = hashlib.sha256(raw).hexdigest()
    result = compare.compare_views(left, right)
    assert result["observations"][0]["fields"]["vm"]["equal"] is False


def test_reference_compare_capacity_refuses_513_without_truncation():
    with pytest.raises(ValueError, match="bound"):
        compare.compare_views(_view(513), _view(513))


def test_reference_compare_wire_scalar_bits_and_columns():
    raw = bytes.fromhex("010000000000f87f0000000000000080")
    value = _wire_array(raw, strides=[-8])
    parsed = compare.wire(value, [])
    assert parsed["layout"]["strides_bytes"] == [-8]
    assert parsed["bytes"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert compare._f64(dict(kind="float", bits="0000000000000080")) == "8000000000000000"


@pytest.mark.parametrize("defect", ["extra_column", "hash", "extent", "dtype", "layout_bool"])
def test_reference_compare_wire_refuses_drift(defect):
    value = _wire_array()
    if defect == "extra_column":
        value["columns"]["unused"] = copy.deepcopy(value["columns"]["native_000000"])
    elif defect == "hash":
        value["tree"]["sha256"] = "0" * 64
    elif defect == "extent":
        value["tree"]["layout"]["shape"] = [3]
    elif defect == "dtype":
        value["columns"]["native_000000"]["dtype"] = ">f8"
    else:
        value["tree"]["layout"]["C_contiguous"] = 1
    with pytest.raises(ValueError):
        compare.wire(value, [])


def test_reference_compare_lossless_sidecar_authentication_and_drift(tmp_path):
    raw = struct.pack("<d", -0.0) * 8192
    value = _wire_array(raw, shape=[8192])
    path = tmp_path / "capture.json"
    compare.evidence.write(path, value, label="synthetic wire")
    pin = dict(path=str(path), sha256=compare.snapshot.digest(path))
    reader = compare.report.Reader()
    restored, pins = compare._capture(reader, pin)
    assert compare.wire(restored, pins)["bytes"]["sha256"] == hashlib.sha256(raw).hexdigest()
    blob = next(Path(row["path"]) for row in pins if row["path"].endswith(".bin"))
    changed = bytearray(blob.read_bytes())
    changed[-1] ^= 1
    blob.write_bytes(changed)
    with pytest.raises(ValueError):
        compare._capture(reader, pin)


def test_reference_compare_exact_reader_pins_refuse_retarget(tmp_path):
    path = tmp_path / "record.json"
    path.write_text('{"value":1}')
    pin = dict(path=str(path), sha256=compare.snapshot.digest(path))
    reader = compare.report.Reader()
    assert reader.bound(pin) == {"value": 1}
    path.write_text('{"value":2}')
    with pytest.raises(ValueError):
        reader.bound(pin)


def test_reference_compare_missing_saved_sides_are_not_partial_success():
    result = compare.compare_saved(None, None)
    assert result["status"] == "unverified_evidence"
    assert result["paired_source_complete"] is False
    assert result["exact_execution_parity"] == dict(available=False, equal=None)


def test_reference_compare_source_adoption_changes_only_declared_four_pins():
    path = software.ROOT / compare.REF_SOURCE
    raw = path.read_bytes()
    constants, pins = compare._reference_source(raw)
    assert constants["KIND"] == compare.REFERENCE_KIND and all(
        value is None for value in pins.values()
    )
    tree = ast.parse(raw)
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(
            isinstance(t, ast.Name) and t.id in compare.REVIEW_NAMES for t in node.targets
        ):
            node.value = ast.Constant("1" * 64)
    _, changed = compare._reference_source(ast.unparse(tree).encode())
    assert all(value == "1" * 64 for value in changed.values())
    tree.body.append(
        ast.Assign(targets=[ast.Name(id="unreviewed", ctx=ast.Store())], value=ast.Constant(True))
    )
    with pytest.raises(ValueError, match="source/epoch revision"):
        compare._reference_source(ast.unparse(ast.fix_missing_locations(tree)).encode())


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    compare.snapshot.write_json(path, value)
    return dict(path=str(path), sha256=compare.snapshot.digest(path))


def _import_lifecycle_fixture(native, inventory, original_files, *, mode="original"):
    """Synthetic saved metadata only: compile pinned library code, never execute it."""
    from validation.betse import native_reference_imports as importer

    files, loaded, components = importer._tree(), {}, {}
    for name, relative, qualified in (
        ("get_code", "claw/_importlib/_clawimpload.py", "BeartypeSourceFileLoader.get_code"),
        (
            "source_to_code",
            "claw/_importlib/_clawimpload.py",
            "BeartypeSourceFileLoader.source_to_code",
        ),
        ("configuration", "claw/_package/clawpkgtrie.py", "get_package_conf_or_none"),
        ("path_hook_factory", "claw/_importlib/clawimpmain.py", "add_beartype_pathhook"),
    ):
        path = importer.BEARTYPE_ROOT / relative
        code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
        components[name] = dict(
            file=str(path),
            qualified=qualified,
            code_sha256=importer.code_sha256(importer._codes(code)[qualified][0]),
        )
        loaded["beartype." + relative[:-3].replace("/", ".")] = dict(
            path=str(path), sha256=files[relative]["sha256"]
        )
    loaded["beartype"] = dict(
        path=str(importer.BEARTYPE_ROOT / "__init__.py"), sha256=files["__init__.py"]["sha256"]
    )
    root = native / "betse/__init__.py"
    root_pin = compare.snapshot.digest(root)
    inventory.setdefault("betse/__init__.py", dict(sha256=root_pin))
    original_files.setdefault("betse", dict(path=str(root), sha256=root_pin))
    selected = importer.expected_selections(native, inventory, mode)
    modules = {
        name: dict(
            **row,
            selected_sha256=row["sha256"],
            selections=[],
            stage="completed",
            loader_base=(
                "_frozen_importlib_external.SourceFileLoader"
                if name == "betse"
                else "beartype.claw._importlib._clawimpload.BeartypeSourceFileLoader"
            ),
            native_beartype=name != "betse",
            module_code_sha256="0" * 64,
            bytecode_cache_used=False,
            capture_errors=[],
            source_returned=True,
            source_error=None,
            export_code_witnesses={},
        )
        for name, row in original_files.items()
    }
    for row in modules.values():
        relative = str(Path(row["path"]).relative_to(native))
        if relative in selected:
            row.update(selected[relative])
    return dict(
        kind=importer.KIND,
        mode=mode,
        policy=importer.specification(),
        modules=modules,
        programs={},
        runtime=dict(
            policy=importer.specification(),
            files=files,
            loaded_modules=loaded,
            compiler_components=components,
            namespace_modules={
                "beartype._data.claw": dict(
                    paths=[str(importer.BEARTYPE_ROOT / "_data/claw")],
                    loader="_frozen_importlib_external.NamespaceLoader",
                    source_tree_sha256=importer.BEARTYPE_TREE_SHA256,
                )
            },
        ),
    )


def _saved_reference(tmp_path, count=3, *, input_count=1):
    """Synthetic saved file graph only: no code, pickle, or source trial runs."""
    source, native = tmp_path / "source", Path("/mnt/workspaces/Cells/betse-v1.5.0")
    output, process = tmp_path / "worker", tmp_path / "process"
    output.mkdir()
    process.mkdir()
    review_pin = _write(tmp_path / "synthetic-reviewed-contract.json", dict(metadata_fixture=True))
    raw = (software.ROOT / compare.REF_SOURCE).read_bytes()
    constants, _ = compare._reference_source(raw)
    tree = ast.parse(raw)
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(
            isinstance(t, ast.Name) and t.id in compare.REVIEW_NAMES for t in node.targets
        ):
            node.value = ast.Constant(review_pin["sha256"])
    producer = source / compare.REF_SOURCE
    producer.parent.mkdir(parents=True)
    producer.write_text(ast.unparse(tree))
    producer.chmod(0o444)
    (source / "checkout.patch").write_bytes(b"")
    (source / "checkout.patch").chmod(0o444)
    source_pin = compare.snapshot.digest(producer)
    importer = source / compare.native_imports.FILE
    importer.write_bytes((software.ROOT / compare.native_imports.FILE).read_bytes())
    importer.chmod(0o444)
    manifest = dict(
        kind="cells.checkout_source_snapshot@1",
        status="complete",
        immutable=True,
        files={
            compare.REF_SOURCE: dict(
                checkout_path=compare.REF_SOURCE,
                sha256=source_pin,
                observation=dict(size=producer.stat().st_size),
                snapshot_mode=0o444,
            ),
            compare.native_imports.FILE: dict(
                checkout_path=compare.native_imports.FILE,
                sha256=compare.snapshot.digest(importer),
                observation=dict(size=importer.stat().st_size),
                snapshot_mode=0o444,
            ),
        },
        patch_sha256=compare.snapshot.digest(source / "checkout.patch"),
    )
    _write(source / "SNAPSHOT.json", manifest)
    for path in source.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    policy = constants["NATIVE_POLICY"]
    inventory = {name: dict(sha256=pin) for name, pin in constants["CRITICAL"].items()}
    originals = {
        name[:-3].replace("/", "."): dict(path=str(native / name), sha256=pin)
        for name, pin in constants["CRITICAL"].items()
        if name.startswith("betse/science/")
    }
    lifecycle = _import_lifecycle_fixture(native, inventory, originals)
    config = tmp_path / "prepared-config"
    config.mkdir()
    (config / "sim_config.yaml").write_bytes(b"synthetic immutable input bytes")
    input_pin = compare.snapshot.digest(config / "sim_config.yaml")
    input_inventory = dict(files={"sim_config.yaml": dict(sha256=input_pin)}, directories=[])
    if input_count == 2:
        (config / "input.csv").write_bytes(b"unchanged synthetic input\n")
        input_inventory["files"]["input.csv"] = dict(
            sha256=compare.snapshot.digest(config / "input.csv")
        )
    plan = dict(
        kind=compare.REFERENCE_KIND,
        held=True,
        native_root=str(native),
        native_inventory=inventory,
        native_inventory_sha256=compare.saved._seal(inventory),
        execution_source=dict(
            root=str(source),
            snapshot_sha256=compare.snapshot.digest(source / "SNAPSHOT.json"),
            owned_files={compare.REF_SOURCE: source_pin},
        ),
        inputs=dict(root=str(config), inventory=input_inventory, mode="original"),
        source_plan=dict(critical_source_pins=constants["CRITICAL"], input_profile="headless"),
        selections={
            path: row["selections"]
            for path, row in compare.native_imports.expected_selections(
                native, inventory, "original"
            ).items()
        },
    )
    prepared = _write(tmp_path / "prepared.json", plan)
    release = _write(
        tmp_path / "release.json",
        dict(
            prepared_sha256=prepared["sha256"],
            snapshot_sha256=plan["execution_source"]["snapshot_sha256"],
            worker_output=str(output),
            policy=policy,
            reviews={name: review_pin for name in ("source", "bootstrap", "writer", "execution")},
        ),
    )
    runtime_files = {}
    for relative, pin in constants["CRITICAL"].items():
        if relative.startswith("betse/science/"):
            module = relative.removesuffix(".py").replace("/", ".")
            runtime_files[module] = dict(path=str(native / relative), sha256=pin)
    runtime_files.update(originals)
    runtime_files.update(lifecycle["runtime"]["loaded_modules"])
    _write(
        output / "runtime.json",
        dict(loaded_files=runtime_files, modules_without_files=["beartype._data.claw"]),
    )
    captures, iterations = [], []

    def capture(label, value):
        path = output / "captures" / (label + ".json")
        path.parent.mkdir(exist_ok=True)
        pins = compare.evidence.write(path, value, label=label)
        captures.append(dict(label=label, status="saved", files=pins))
        return pins[0]

    bits = b"".join(struct.pack("<d", i * 0.125) for i in range(count))
    calendar = _wire_array(bits, shape=[count])
    calendar["tree"] = dict(
        type="tuple",
        values=[
            calendar["tree"],
            dict(
                type="set", values=[_node("float", i * 0.125) for i in range(count) if i % 2 == 0]
            ),
        ],
    )
    capture("original_calendar", calendar)
    capture(
        "final_calendar_configuration",
        _dict_wire(dict(init_tsteps=_node("int", count), dt=_node("float", 0.125))),
    )
    for ordinal in range(1, count + 1):
        values = dict(
            ordinal=_node("int", ordinal),
            source_time=_node("float", (ordinal - 1) * 0.125),
            sampled=_node("bool", (ordinal - 1) % 2 == 0),
            configured_dt=_node("float", 0.125),
            fields=dict(type="dict", values=[]),
            numpy_random=dict(type="tuple", values=[]),
            python_random=dict(type="tuple", values=[]),
        )
        iterations.append(capture(f"iteration_{ordinal:04d}", _dict_wire(values)))
    (output / "config/INITS").mkdir(parents=True)
    copies = []
    for name, entry in input_inventory["files"].items():
        original, copied = config / name, output / "config" / name
        copied.write_bytes(original.read_bytes())
        old, new = original.stat(), copied.stat()
        copies.append(
            dict(
                name=name,
                status="copied",
                sha256=entry["sha256"],
                source_inode=[old.st_dev, old.st_ino],
                execution_inode=[new.st_dev, new.st_ino],
            )
        )
    seed = output / "config/INITS/world_1.betse.gz"
    seed.write_bytes(b"synthetic bytes; never unpickled")
    _write(
        output / "filesystem.json",
        dict(
            installed=True,
            first_error=None,
            failures=[],
            write_policy=dict(first_error=None, failures=[]),
        ),
    )
    _write(
        output / "execution-inputs.json",
        dict(
            root=str(output / "config"),
            source_root=str(config),
            inventory=input_inventory,
            files=copies,
        ),
    )
    worker = _write(
        output / "result.json",
        dict(
            kind=compare.REFERENCE_KIND,
            status="completed",
            primary=None,
            capture_errors=[],
            source_returned=True,
            inherited_hooks_restored=True,
            filesystem_audit_installed=True,
            observer_coverage_failed=False,
            native_producers=lifecycle["modules"],
            native_import_lifecycle=lifecycle,
            captures=captures,
            iterations=iterations,
            seed=dict(
                record=dict(
                    path=str(seed),
                    sha256=compare.snapshot.digest(seed),
                    size_bytes=seed.stat().st_size,
                ),
                attempts=[dict(kind="loadWorld", path=str(seed), admitted=True)],
            ),
        ),
    )
    limits = dict(
        max_wall_seconds=policy["wall_seconds"],
        max_process_tree_rss_bytes=policy["max_rss_bytes"],
        min_available_host_memory_bytes=policy["reserve_bytes"],
    )
    _write(
        process / "process-inputs.json",
        dict(
            command=[
                "python",
                "--worker",
                prepared["path"],
                "--prepared-sha256",
                prepared["sha256"],
                "--release",
                release["path"],
                "--release-sha256",
                release["sha256"],
                "--output",
                str(output),
            ],
            cwd=str(source),
            limits=limits,
        ),
    )
    _write(
        process / "result.json",
        dict(
            limits=limits,
            returncode=0,
            status="completed",
            elapsed_seconds=1,
            sampled_peak_process_tree_rss_bytes=1,
            minimum_available_host_memory_bytes=16 * 2**30,
            samples=1,
        ),
    )
    controller = _write(
        tmp_path / "result.json", dict(status="completed", worker_result_sha256=worker["sha256"])
    )
    return dict(prepared=prepared, release=release, controller=controller, worker=worker)


def test_reference_compare_saved_reference_file_graph_is_authenticated(tmp_path):
    pins = _saved_reference(tmp_path)
    side = compare._reference(pins)
    assert side["authenticated"], side["error"]
    assert side["complete"] and len(side["rows"]) == 3
    assert side["initial_rng"]["available"] is False
    assert (
        side["rows"][0]["ordinal"] == 0
        and side["rows"][-1]["source_time_bits"] == struct.pack("!d", 0.25).hex()
    )


@pytest.mark.parametrize("defect", ["calendar", "command", "runtime", "seed", "controller"])
def test_reference_compare_saved_reference_drift_refuses_before_parity(tmp_path, defect):
    pins = _saved_reference(tmp_path)
    if defect == "seed":
        (tmp_path / "worker/config/INITS/world_1.betse.gz").write_bytes(b"changed")
    else:
        if defect == "calendar":
            path = tmp_path / "worker/captures/original_calendar.json"
        elif defect == "command":
            path = tmp_path / "process/process-inputs.json"
        elif defect == "runtime":
            path = tmp_path / "worker/runtime.json"
        else:
            path = tmp_path / "result.json"
        value = json.loads(path.read_text())
        if defect == "command":
            value["command"][-1] = str(tmp_path / "different")
        elif defect == "runtime":
            value["loaded_files"] = {}
        elif defect == "controller":
            value["worker_result_sha256"] = "0" * 64
        else:
            value["mutated"] = True
        path.write_text(json.dumps(value))
        if defect == "controller":
            pins["controller"]["sha256"] = compare.snapshot.digest(path)
    side = compare._reference(pins)
    assert not side["authenticated"] and side["complete"] is False
    assert side["error"] is not None


@pytest.mark.parametrize(
    "kind,bits,expected",
    [
        ("<f8", "010000000000f87f", "7ff8000000000001"),
        (">f8", "8000000000000000", "8000000000000000"),
    ],
)
def test_reference_compare_float_bit_order_preserves_payloads(kind, bits, expected):
    assert compare._f64(dict(kind="numpy_scalar", dtype=kind, bits=bits)) == expected


def test_reference_compare_reader_imports_are_stdlib_and_saved_readers_only():
    tree = ast.parse(Path(compare.__file__).read_bytes())
    roots = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.extend(item.name.split(".")[0] for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.append(node.module.split(".")[0])
    assert not {"numpy", "cells", "betse", "random"} & set(roots)


def _saved_views(tmp_path):
    sides, paths = [], []
    for name in ("reference", "demo"):
        side = _view(matched_rng=True)
        side["reader"] = compare.report.Reader()
        path = tmp_path / (name + "-saved.json")
        side["reader"].bound(_write(path, dict(authenticated_before_comparison=True)))
        sides.append(side)
        paths.append(path)
    return sides, paths


@pytest.mark.parametrize("target", [0, 1])
def test_reference_compare_repair_late_rebind_revokes_verified_result(
    tmp_path, monkeypatch, target
):
    sides, paths = _saved_views(tmp_path)
    monkeypatch.setattr(compare, "_reference", lambda request: sides[0])

    def demo(request, mode):
        paths[target].write_text('{"changed_after_initial_authentication": true}\n')
        return sides[1]

    monkeypatch.setattr(compare, "_demo", demo)
    result = compare.compare_saved({}, {})
    assert result["status"] == "evidence_changed_during_comparison"
    assert result["paired_source_complete"] is False
    assert result["evidence_authenticated"] is False
    assert result["aligned_observations_equal"] is None and result["observations"] == []
    assert result["dt_dependent_comparison_available"] is False
    assert result["exact_execution_parity"]["available"] is False
    assert result["exact_execution_parity"]["equal"] is None
    forensic = result["unverified_forensics"]
    assert forensic["paired_source_complete"] is True
    assert forensic["aligned_observations_equal"] is True
    assert forensic["exact_execution_parity"]["equal"] is True
    assert len(forensic["observations"]) == 3
    assert ("reference", "demo")[target] in result["errors"]


@pytest.mark.parametrize("drift", [False, True])
def test_reference_compare_repair_cli_requires_final_authentication(tmp_path, monkeypatch, drift):
    sides, paths = _saved_views(tmp_path)
    monkeypatch.setattr(compare, "_reference", lambda request: sides[0])

    def demo(request, mode):
        if drift:
            paths[0].write_text('{"changed_after_initial_authentication": true}\n')
        return sides[1]

    monkeypatch.setattr(compare, "_demo", demo)
    request = _write(tmp_path / "request.json", dict(reference={}, demo={}))
    output = tmp_path / "comparison.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare",
            "--request",
            request["path"],
            "--request-sha256",
            request["sha256"],
            "--output",
            str(output),
        ],
    )
    assert compare.main() == int(drift)
    result = json.loads(output.read_text())
    assert result["paired_source_complete"] is (not drift)
    assert result["evidence_authenticated"] is (not drift)
    assert result["scientific_physical_checkpoint_credit"] == 0


@pytest.mark.parametrize(
    "defect",
    [
        "empty",
        "missing",
        "duplicate",
        "extra",
        "non_list",
        "changed_omitted",
        "copy_status",
        "copy_inode",
    ],
)
def test_reference_compare_repair_execution_roster_exact(tmp_path, defect):
    pins = _saved_reference(tmp_path, input_count=2)
    path = tmp_path / "worker/execution-inputs.json"
    execution = json.loads(path.read_text())
    rows = execution["files"]
    if defect == "empty":
        execution["files"] = []
    elif defect in ("missing", "changed_omitted"):
        omitted = rows.pop()
        if defect == "changed_omitted":
            (tmp_path / "worker/config" / omitted["name"]).write_bytes(b"changed unlisted input")
    elif defect == "duplicate":
        rows[1] = dict(rows[0])
    elif defect == "extra":
        rows.append(dict(rows[0], name="undeclared.csv"))
    elif defect == "non_list":
        execution["files"] = {}
    elif defect == "copy_status":
        rows[0]["status"] = "attempted"
    else:
        rows[0]["execution_inode"][1] += 1
    path.write_text(json.dumps(execution))
    side = compare._reference(pins)
    assert side["authenticated"] is False and side["complete"] is False
    assert side["error"] is not None
    assert "selected_input_files" not in side
    assert "execution copy" in side["error"]["message"].lower()


def _cache_node(node, columns=()):
    descriptor = json.dumps(node, sort_keys=True, separators=(",", ":"))
    return dict(
        descriptor_json=descriptor,
        identity=hashlib.sha256(descriptor.encode()).hexdigest(),
        all_finite=True,
        columns=list(columns),
    )


def _cache_array(raw, size, *, simulator=False):
    node = dict(
        kind="numeric_array",
        column="column_00000",
        sha256=hashlib.sha256(raw).hexdigest(),
        source_layout=dict(
            dtype="<f8", shape=[size], strides_bytes=[8], C_contiguous=True, F_contiguous=True
        ),
    )
    if simulator:
        node = dict(
            kind="tuple",
            items=[
                dict(
                    kind="tuple",
                    items=[
                        dict(kind="str", value="Simulator"),
                        dict(
                            kind="dict",
                            items=[[dict(kind="str", value=name), node] for name in compare.FIELDS],
                        ),
                    ],
                )
            ],
        )
    return _cache_node(
        node,
        [
            dict(
                name="column_00000",
                values=dict(
                    __ndarray__=True,
                    dtype="<f8",
                    shape=[size],
                    strides=[8],
                    raw_bytes_hex=raw.hex(),
                ),
            )
        ],
    )


def _failed_demo_side(
    tmp_path,
    *,
    unavailable=None,
    capture_error=None,
    raw_context=False,
    raw_scalar="numpy_le",
    calendar_dtype="<f8",
    calendar_size=3,
    sidecars=False,
):
    """Real failure label/cache/sidecar grammar; report-authentication seam only."""
    folder = tmp_path / "worker/demo"
    folder.mkdir(parents=True)
    rows, attempts, pins = [], [], []

    def capture(name, value):
        label = "init_terminal.failure." + name
        if name == unavailable or (raw_context and name == "configured_dt"):
            attempts.append(dict(label=label, status="unavailable"))
            return
        if name == capture_error:
            attempts.append(dict(label=label, status="capture_failed", error=dict(type="OSError")))
            return
        path = folder / (name + ".json")
        generated = compare.evidence.write(path, value, label=label)
        pins.extend(generated)
        rows.append(
            dict(label=label, path=path.name, sha256=generated[0]["sha256"], status="saved")
        )
        attempts.append(dict(label=label, status="saved"))

    if raw_context:
        capture(
            "calendar",
            dict(
                __ndarray__=True,
                dtype=calendar_dtype,
                shape=[calendar_size],
                strides=[8],
                raw_bytes_hex=struct.pack(
                    calendar_dtype[0] + str(calendar_size) + "d",
                    *(i * 0.125 for i in range(calendar_size)),
                ).hex(),
            ),
        )
        samples = []
        for index in range(0, calendar_size, 2):
            if raw_scalar == "python":
                samples.append(dict(float64_bits=struct.pack("<d", index * 0.125).hex()))
            else:
                endian = ">" if raw_scalar == "numpy_be" else "<"
                samples.append(
                    dict(
                        numpy_scalar_dtype=endian + "f8",
                        raw_bytes_hex=struct.pack(endian + "d", index * 0.125).hex(),
                    )
                )
        capture("sampled", samples)
    else:
        capture("calendar", _cache_array(struct.pack("<3d", 0, 0.125, 0.25), 3))
        capture(
            "sampled",
            _cache_node(
                dict(
                    kind="tuple",
                    items=[
                        dict(kind="float", bits=struct.pack("<d", value).hex())
                        for value in (0, 0.25)
                    ],
                )
            ),
        )
    capture(
        "configured_dt",
        None
        if raw_context
        else _cache_node(dict(kind="float", bits=struct.pack("<d", 0.125).hex())),
    )
    primary = dict(
        primary=dict(identity=501, type="NativeFailure"),
        cause=dict(identity=502, type="OriginalCause"),
        live_claim_or_frame_serialization=False,
    )
    capture("primary", primary)
    capture("current_iteration", 2)
    capture("completed_iterations", 2)
    capture("last_iteration_raw", None)
    for ordinal in range(2):
        cache = (
            _cache_array(struct.pack("<d", float(ordinal)) * 8192, 8192, simulator=True)
            if sidecars
            else _cache_array(struct.pack("<2d", float(ordinal), -0.0), 2, simulator=True)
        )
        capture(
            f"iteration.{ordinal:04d}.linkage",
            dict(
                ordinal=ordinal,
                source_time_bits=struct.pack("!d", ordinal * 0.125).hex(),
                sampled=ordinal % 2 == 0,
                after_identity=cache["identity"],
                work_end=ordinal + 10,
                callbacks_end=ordinal + 1,
                molecular_record_identity=100 + ordinal,
            ),
        )
        capture(f"iteration.{ordinal:04d}.after", cache)
        capture(f"iteration.{ordinal:04d}.diagnostics", None)
    outcome = dict(
        status="failed",
        endpoint="init_terminal",
        primary="NativeFailure",
        secondary=[dict(stage="failed-third-iteration-observer", error="CaptureFailure")],
        completed_stage_trials=["init_electrical"],
        captures=rows,
        terminal_failure_captures=attempts,
        init_terminal_completed=False,
        init_time_steps_completed=0,
    )
    pins.append(_write(folder / "outcome.json", outcome))
    pins.append(_write(tmp_path / "worker/runtime-after.json", dict(loaded_files={})))
    source = tmp_path / "source"
    source_pins = {}
    originals = {"betse/science/sim.py": "a" * 64, "betse/science/chemistry/networks.py": "b" * 64}
    for relative, name in (
        ("src/cells/processes/betse_native_init_first_step_source.py", "SOURCE_PINS"),
        ("src/cells/processes/betse_native_init_molecule_network_source.py", "PINS"),
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name + " = " + repr(originals) + "\n")
        source_pins[relative] = compare.snapshot.digest(path)
    demo_plan = _write(tmp_path / "demo-plan.json", dict(source_plan=dict(synthetic=True)))
    side = dict(
        authenticated=True,
        complete=False,
        reader=compare.report.Reader(),
        error=None,
        saved=dict(
            endpoint="init_terminal",
            status="failed",
            output=str(tmp_path),
            selected_input_files={"sim_config.yaml": "c" * 64},
            init_native_molecules=True,
            source_files=source_pins,
            configuration_profile="headless",
            demonstration=dict(natural_terminal=None),
            failures=[dict(path="worker/failure.json", failure=dict(primary=primary))],
        ),
        plan=dict(source=str(source), producers={}, demo_plan=demo_plan),
    )
    for pin in pins:
        side["reader"].bind(pin)
    return side, outcome, primary


def test_reference_compare_repair_failed_terminal_keeps_completed_prefix(tmp_path, monkeypatch):
    side, outcome, primary = _failed_demo_side(tmp_path, unavailable="last_iteration_raw")
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert actual["complete"] is False and len(actual["rows"]) == 2
    assert not any(row["label"] == "init_terminal.record" for row in outcome["captures"])
    assert actual["failure_evidence"]["primary_capture"] == primary
    assert actual["failure_evidence"]["secondary"] == outcome["secondary"]
    assert any(
        row["status"] == "unavailable" for row in actual["failure_evidence"]["capture_attempts"]
    )
    compared = compare.compare_views(_view(), actual)
    assert compared["status"] == "compared_partial_failed_sources"
    assert compared["compared_epochs"] == 2
    assert compared["aligned_observations_equal"] is True
    assert compared["observations"][2]["status"] == "missing_observation"
    assert compared["paired_source_complete"] is False
    assert compared["exact_execution_parity"]["available"] is False
    assert compared["source_failures"]["demo"]["primary_capture"] == primary


@pytest.mark.parametrize("defect", ["missing", "altered", "identity", "ordinal", "sample"])
def test_reference_compare_repair_failed_terminal_capture_refuses(tmp_path, monkeypatch, defect):
    side, outcome, primary = _failed_demo_side(tmp_path)
    label = "init_terminal.failure.iteration.0001." + (
        "after" if defect in ("missing", "altered", "identity") else "linkage"
    )
    row = next(row for row in outcome["captures"] if row["label"] == label)
    path = tmp_path / "worker/demo" / row["path"]
    if defect == "missing":
        outcome["captures"].remove(row)
        (tmp_path / "worker/demo/outcome.json").write_text(json.dumps(outcome))
    elif defect == "altered":
        path.write_text('{"altered_saved_bytes": true}\n')
    else:
        value = compare.evidence.read(path)
        if defect == "identity":
            # Authenticated changed data still cannot retarget the retained linkage.
            value = _cache_array(struct.pack("<2d", 9, -0.0), 2, simulator=True)
        elif defect == "ordinal":
            value["ordinal"] = 9
        else:
            value["sampled"] = True
        path.write_text(json.dumps(value))
        row["sha256"] = compare.snapshot.digest(path)
        (tmp_path / "worker/demo/outcome.json").write_text(json.dumps(outcome))
        # Authenticate this deliberately resealed fixture; association must still refuse.
        side["reader"].pins[str(path)] = row["sha256"]
    if defect != "altered":
        path = tmp_path / "worker/demo/outcome.json"
        side["reader"].pins[str(path)] = compare.snapshot.digest(path)
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"] is False and actual["error"] is not None
    assert actual["complete"] is False
    assert actual["failure_evidence"]["primary"] == "NativeFailure"
    assert actual["failure_evidence"]["secondary"] == outcome["secondary"]


def test_reference_compare_repair_failed_terminal_capture_error_is_distinct(tmp_path, monkeypatch):
    side, outcome, primary = _failed_demo_side(tmp_path, capture_error="last_iteration_raw")
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert len(actual["rows"]) == 2 and actual["complete"] is False
    assert actual["failure_evidence"]["primary_capture"] == primary
    assert next(
        row
        for row in actual["failure_evidence"]["capture_attempts"]
        if row["status"] == "capture_failed"
    )["error"] == dict(type="OSError")


@pytest.mark.parametrize("selected_stop", [False, True])
def test_reference_compare_repair_success_grammar_keeps_normal_return_gate(
    tmp_path, monkeypatch, selected_stop
):
    side, outcome, _ = _failed_demo_side(tmp_path)
    folder = tmp_path / "worker/demo"
    retained = {row["label"]: row for row in outcome["captures"]}
    native_rows = []
    for ordinal in range(2):
        label = f"init_terminal.failure.iteration.{ordinal:04d}.after"
        native_rows.append(
            [
                ordinal,
                struct.pack("!d", ordinal * 0.125).hex(),
                ordinal % 2 == 0,
                compare.evidence.read(folder / retained[label]["path"])["identity"],
                ordinal + 10,
                ordinal + 1,
                ordinal + 100,
                None,
            ]
        )
    record = dict(
        iterations=native_rows,
        source_completed=True,
        loop_returned=True,
        context_returned=True,
        selected_stop=selected_stop,
    )
    values = {"record": record}
    for name in ("configured_dt", "iteration.0000.after", "iteration.0001.after"):
        values[name] = compare.evidence.read(
            folder / retained["init_terminal.failure." + name]["path"]
        )
    for name, value in values.items():
        label = "init_terminal." + name
        path = folder / (label + ".json")
        pins = compare.evidence.write(path, value, label=label)
        for pin in pins:
            side["reader"].bind(pin)
        outcome["captures"].append(
            dict(label=label, path=path.name, sha256=pins[0]["sha256"], status="saved")
        )
    outcome.update(status="completed", primary=None, terminal_failure_captures=[])
    path = folder / "outcome.json"
    path.write_text(json.dumps(outcome))
    side["reader"].pins[str(path)] = compare.snapshot.digest(path)
    side["complete"] = True
    side["saved"]["demonstration"]["natural_terminal"] = dict(
        original_time_bits=[row[1] for row in native_rows]
    )
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"] is (not selected_stop), actual.get("error")
    if not selected_stop:
        assert actual["complete"] is True and len(actual["rows"]) == 2
        assert "failure_evidence" not in actual


@pytest.mark.parametrize("raw_scalar", ["python", "numpy_le", "numpy_be"])
@pytest.mark.parametrize("calendar_dtype", ["<f8", ">f8"])
def test_reference_compare_no_trial_retains_raw_prefix_without_dt(
    tmp_path, monkeypatch, raw_scalar, calendar_dtype
):
    side, outcome, primary = _failed_demo_side(
        tmp_path, raw_context=True, raw_scalar=raw_scalar, calendar_dtype=calendar_dtype
    )
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert actual["complete"] is False and len(actual["rows"]) == 2
    assert all(row["dt_bits"] is None and row["dt_available"] is False for row in actual["rows"])
    retained = actual["failure_evidence"]
    assert retained["primary_capture"] == primary
    assert retained["secondary"] == outcome["secondary"]
    assert retained["calendar"]["encoding"] == "raw_context_ndarray"
    assert retained["calendar"]["observation"]["dtype"] == calendar_dtype
    assert retained["sampled"]["encoding"] == "raw_context_scalar_list"
    assert retained["configured_dt"] == dict(
        available=False, bits=None, capture_status="unavailable", inferred=False
    )
    assert not any(row["label"].endswith(".configured_dt") for row in outcome["captures"])
    compared = compare.compare_views(_view(), actual)
    assert compared["evidence_authenticated"] is True
    assert compared["paired_source_complete"] is False
    assert compared["compared_epochs"] == 2
    assert compared["unavailable_timing_observations"] == 2
    assert compared["dt_dependent_comparison_available"] is False
    assert compared["aligned_observations_equal"] is None
    assert compared["exact_execution_parity"]["available"] is False
    for row in compared["observations"][:2]:
        assert row["status"] == "compared_saved_fields_with_unavailable_dt"
        assert row["timing"] == dict(source_time_bits=True, sampled=True, dt_bits=None)
        assert len(row["fields"]) == len(compare.FIELDS)
        assert all(field == dict(available=True, equal=True) for field in row["fields"].values())


def test_reference_compare_no_trial_full512_raw_calendar(tmp_path, monkeypatch):
    side, _, _ = _failed_demo_side(tmp_path, raw_context=True, calendar_size=512)
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert len(actual["calendar"]) == 512 and len(actual["rows"]) == 2
    assert actual["calendar"][-1] == struct.pack("!d", 511 * 0.125).hex()
    assert actual["failure_evidence"]["configured_dt"]["available"] is False


@pytest.mark.parametrize("capture_status", ["unavailable", "capture_failed"])
def test_reference_compare_no_trial_trial_cache_can_also_lack_dt(
    tmp_path, monkeypatch, capture_status
):
    side, _, primary = _failed_demo_side(
        tmp_path,
        unavailable="configured_dt" if capture_status == "unavailable" else None,
        capture_error="configured_dt" if capture_status == "capture_failed" else None,
    )
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert len(actual["rows"]) == 2 and actual["complete"] is False
    assert actual["failure_evidence"]["calendar"]["encoding"] == "sealed_trial_cache"
    assert actual["failure_evidence"]["primary_capture"] == primary
    assert actual["failure_evidence"]["configured_dt"] == dict(
        available=False, bits=None, capture_status=capture_status, inferred=False
    )


def _reseal_failure_capture(side, outcome, name, mutate):
    folder = Path(side["saved"]["output"]) / "worker/demo"
    row = next(
        row for row in outcome["captures"] if row["label"] == "init_terminal.failure." + name
    )
    path = folder / row["path"]
    value = compare.evidence.read(path)
    mutate(value)
    path.write_text(json.dumps(value))
    row["sha256"] = compare.snapshot.digest(path)
    side["reader"].pins[str(path)] = row["sha256"]
    path = folder / "outcome.json"
    path.write_text(json.dumps(outcome))
    side["reader"].pins[str(path)] = compare.snapshot.digest(path)


def test_reference_compare_no_trial_retains_raw_calendar_layout(tmp_path, monkeypatch):
    side, outcome, _ = _failed_demo_side(tmp_path, raw_context=True)
    _reseal_failure_capture(side, outcome, "calendar", lambda raw: raw.update(strides=[-8]))
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert actual["failure_evidence"]["calendar"]["observation"]["strides"] == [-8]
    assert actual["calendar"] == [struct.pack("!d", i * 0.125).hex() for i in range(3)]


@pytest.mark.parametrize(
    "defect",
    [
        "calendar_shape",
        "calendar_extent",
        "calendar_stride",
        "sample_dtype",
        "sample_extent",
        "sample_untyped",
    ],
)
def test_reference_compare_no_trial_raw_encoding_drift_refuses(tmp_path, monkeypatch, defect):
    side, outcome, primary = _failed_demo_side(tmp_path, raw_context=True)
    name = "calendar" if defect.startswith("calendar") else "sampled"

    def change(value):
        if defect == "calendar_shape":
            value["shape"] = [1, 3]
            value["strides"] = [24, 8]
        elif defect == "calendar_extent":
            value["shape"] = [4]
        elif defect == "calendar_stride":
            value["strides"] = [True]
        elif defect == "sample_dtype":
            value[0]["numpy_scalar_dtype"] = "<f4"
        elif defect == "sample_extent":
            value[0]["raw_bytes_hex"] = "00"
        else:
            value[0] = 0

    _reseal_failure_capture(side, outcome, name, change)
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"] is False and actual["complete"] is False
    assert actual["error"] is not None
    assert actual["failure_evidence"]["primary_capture"] == primary
    assert actual["failure_evidence"]["secondary"] == outcome["secondary"]


def test_reference_compare_no_trial_large_saved_state_sidecars(tmp_path, monkeypatch):
    side, _, primary = _failed_demo_side(tmp_path, raw_context=True, sidecars=True)
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"], actual.get("error")
    assert actual["failure_evidence"]["primary_capture"] == primary
    assert len(actual["rows"]) == 2 and actual["rows"][1]["dt_bits"] is None
    assert actual["rows"][1]["fields"]["vm"]["layout"]["shape"] == [8192]
    assert (
        actual["rows"][1]["fields"]["vm"]["bytes"]["sha256"]
        == hashlib.sha256(struct.pack("<d", 1.0) * 8192).hexdigest()
    )


@pytest.mark.parametrize("defect", ["missing", "corrupt"])
def test_reference_compare_no_trial_raw_sidecar_loss_refuses(tmp_path, monkeypatch, defect):
    side, outcome, primary = _failed_demo_side(tmp_path, raw_context=True, sidecars=True)
    row = next(
        row
        for row in outcome["captures"]
        if row["label"] == "init_terminal.failure.iteration.0001.after"
    )
    path = tmp_path / "worker/demo" / row["path"]
    blob = next(
        Path(pin["path"]) for pin in compare.evidence.files(path) if pin["path"].endswith(".bin")
    )
    if defect == "missing":
        blob.unlink()
    else:
        data = bytearray(blob.read_bytes())
        data[-1] ^= 1
        blob.write_bytes(data)
    monkeypatch.setattr(compare.saved, "_side", lambda request, mode: side)
    actual = compare._demo({}, "original")
    assert actual["authenticated"] is False and actual["complete"] is False
    assert actual["error"] is not None
    assert len(actual["rows"]) == 1  # Original first completed row remains forensic evidence.
    assert actual["failure_evidence"]["primary_capture"] == primary


@pytest.mark.parametrize("defect", ["undeclared", "complete", "contradictory"])
def test_reference_compare_no_trial_unknown_dt_cannot_gain_timing_authority(defect):
    left, right = _view(complete=False), _view(complete=False)
    row = right["rows"][0]
    row.update(dt_bits=None, dt_available=False)
    if defect == "undeclared":
        del row["dt_available"]
    elif defect == "complete":
        right["complete"] = True
    else:
        row["dt_bits"] = struct.pack("!d", 0.125).hex()
    with pytest.raises(ValueError, match="Exact original float64"):
        compare.compare_views(left, right)


def test_reference_compare_no_trial_two_missing_dts_are_not_equal():
    left, right = _view(complete=False), _view(complete=False)
    for side in (left, right):
        for row in side["rows"]:
            row.update(dt_bits=None, dt_available=False)
    result = compare.compare_views(left, right)
    assert result["aligned_observations_equal"] is None
    assert result["dt_dependent_comparison_available"] is False
    assert result["unavailable_timing_observations"] == 3
    assert all(row["timing"]["dt_bits"] is None for row in result["observations"])


@pytest.mark.parametrize("bits", ["8000000000000000", "7ff8000000000001"])
def test_reference_compare_no_trial_raw_scalar_bits_are_lossless(bits):
    raw = bytes.fromhex(bits)
    assert compare._raw_failure_scalar(dict(float64_bits=raw[::-1].hex()), []) == bits
    for dtype, data in (("<f8", raw[::-1]), (">f8", raw)):
        assert (
            compare._raw_failure_scalar(
                dict(numpy_scalar_dtype=dtype, raw_bytes_hex=data.hex()), []
            )
            == bits
        )


def test_reference_compare_no_trial_fixture_follows_actual_failure_projection():
    path = software.ROOT / "validation/betse/native_seed_demo.py"
    tree = ast.parse(path.read_bytes())
    failure = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_history_failure_evidence"
    )
    text = ast.unparse(failure)
    assert "value('calendar', 'time_steps')" in text
    assert "project('sampled', sampling)" in text
    assert "value('dt')" in text
    terminal = ast.parse(
        (software.ROOT / "src/cells/processes/betse_native_init_terminal.py").read_bytes()
    )
    assert not any(
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "context"
        and node.attr == "dt"
        for node in ast.walk(terminal)
    )
