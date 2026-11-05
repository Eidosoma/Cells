"""Synthetic saved histories and real codecs; no model, NumPy, RNG or live owner."""

import ast
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from validation.betse import native_sim_reference_compare as compare
from validation.betse import native_sim_reference_compare_software as software

_SYNTHETIC_ADAPTER_ATTEMPTS = []

if TYPE_CHECKING:
    # Read-only metadata fixture code, compiled but never module-executed.
    from tests.unit import (
        test_native_init_terminal_reference_compare,  # noqa:F401
        test_native_seed_demo_report,  # noqa:F401
    )


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit immutable stdlib-only SIM comparison software required")
    with software.blocked(tmp_path):
        yield


def _node(kind, value):
    if kind == "float":
        return dict(kind=kind, bits=struct.pack("<d", value).hex())
    return dict(kind=kind, value=value)


def _array(raw=None, *, words=False):
    raw = (
        struct.pack("<624I", *range(624))
        if words
        else struct.pack("<2d", -0.0, 1.0)
        if raw is None
        else raw
    )
    return dict(
        kind="array",
        layout=dict(
            dtype="<u4" if words else "<f8",
            shape=[624] if words else [len(raw) // 8],
            strides_bytes=[4] if words else [8],
            C_contiguous=True,
            F_contiguous=True,
        ),
        bytes=dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
    )


def _rng():
    return dict(
        numpy=dict(
            kind="tuple",
            items=[
                _node("str", "MT19937"),
                _array(words=True),
                _node("int", 624),
                _node("int", 0),
                _node("float", -0.0),
            ],
        ),
        python=dict(
            kind="tuple",
            items=[
                _node("int", 3),
                dict(
                    kind="tuple", items=[*[_node("int", i) for i in range(624)], _node("int", 624)]
                ),
                _node("NoneType", None),
            ],
        ),
    )


def _view(count=3, *, complete=True):
    random_state = _rng()
    rows = []
    for i in range(count):
        time = struct.pack("!d", i * 0.125).hex()
        dt, sampled = struct.pack("!d", 0.125).hex(), i % 2 == 0
        groups = {name: dict(saved_typed_observation=_array()) for name in compare.GROUPS}
        groups.update(
            clock=dict(source_time_bits=time, dt_bits=dt, sampled=sampled), rng=random_state
        )
        rows.append(
            dict(
                ordinal=i,
                epoch=compare.EPOCH,
                source_time_bits=time,
                dt_bits=dt,
                sampled=sampled,
                groups=groups,
            )
        )
    return dict(
        authenticated=True,
        files_bound=True,
        endpoint_complete=complete,
        rows=rows,
        calendar=[row["source_time_bits"] for row in rows] if rows else None,
        mode="original",
        inputs={"sim_config.yaml": "a" * 64},
        configuration_profile="headless",
        original_sources="b" * 64,
        lineage={name: True for name in compare.LINEAGE},
        initial_rng=dict(
            available=True,
            epoch=compare.INITIAL_EPOCH,
            common_binding=dict(input_inventory_sha256="c" * 64, mode="original"),
            full_state=random_state,
        ),
        reader=compare.report.Reader(),
        failure=None,
    )


def _save(path, value):
    compare.snapshot.write_json(path, value)
    return dict(path=str(path), sha256=compare.snapshot.digest(path))


def _replace(pin, value):
    Path(pin["path"]).write_text(json.dumps(value, allow_nan=False))
    pin["sha256"] = compare.snapshot.digest(Path(pin["path"]))


def _wire(node, columns):
    kind = node["kind"]
    if kind == "array":
        raw = (
            struct.pack("<624I", *range(624))
            if node["layout"]["dtype"] == "<u4"
            else struct.pack("<2d", -0.0, 1.0)
        )
        name = f"column_{len(columns):06d}"
        columns[name] = dict(
            dtype=node["layout"]["dtype"], shape=node["layout"]["shape"], raw_bytes_hex=raw.hex()
        )
        return dict(
            type=kind, layout=node["layout"], column=name, sha256=hashlib.sha256(raw).hexdigest()
        )
    if kind == "tuple":
        return dict(type=kind, values=[_wire(value, columns) for value in node["items"]])
    if kind == "float":
        return dict(type=kind, bits=node["bits"])
    return dict(type=kind, value=node["value"])


def _row_wire(index, *, rich=False):
    state, columns = _rng(), {}
    fields = dict(
        type="dict",
        values=[
            [dict(type="str", value=name), _wire(_array(), columns)]
            for name in compare.codec.FIELDS
        ],
    )
    values = dict(
        ordinal=dict(type="int", value=index + 1),
        source_time=dict(type="float", bits=struct.pack("<d", index * 0.125).hex()),
        sampled=dict(type="bool", value=index % 2 == 0),
        configured_dt=dict(type="float", bits=struct.pack("<d", 0.125).hex()),
        fields=fields,
        numpy_random=_wire(state["numpy"], columns),
        python_random=_wire(state["python"], columns),
    )
    if rich:

        def mapping(values):
            return dict(
                type="dict",
                values=[[dict(type="str", value=key), value] for key, value in values.items()],
            )

        absent = mapping(dict(present=dict(type="bool", value=False)))
        values.update(
            observation_contract=dict(type="str", value=compare.OBSERVATION_KIND),
            gates=mapping(
                dict(
                    gap_junction=mapping({name: absent for name in ("gjopen", "gj_block", "vgj")}),
                    gap_junction_core=mapping(
                        {name: absent for name in ("alpha", "beta", "gjopen")}
                    ),
                    molecules=mapping(
                        dict(
                            enabled=dict(type="bool", value=False),
                            source_branch=dict(type="str", value="disabled"),
                        )
                    ),
                    grn=mapping(
                        dict(
                            enabled=dict(type="bool", value=False),
                            source_branch=dict(type="str", value="disabled"),
                        )
                    ),
                )
            ),
            electric_fields=mapping(
                {
                    name: absent
                    for name in (
                        "E_cell_x",
                        "E_cell_y",
                        "E_env_x",
                        "E_env_y",
                        "Emc",
                        "Eme",
                        "v_env",
                        "Phi_b",
                    )
                }
            ),
            events=mapping(
                dict(
                    calls=dict(type="list", values=[]),
                    global_options=mapping({}),
                    scheduled_options=mapping({}),
                    event_cut=absent,
                    voltage_event=absent,
                )
            ),
        )
    return dict(
        tree=dict(
            type="dict",
            values=[[dict(type="str", value=name), value] for name, value in values.items()],
        ),
        columns=columns,
    )


def _saved_reference(tmp_path, count=2):
    """Known reference file grammar, always forensic-only, never source execution."""
    source, output, inputs = tmp_path / "source", tmp_path / "worker", tmp_path / "inputs"
    source.mkdir()
    output.mkdir()
    inputs.mkdir()
    files = {}
    for name, expected in compare.REF_PRODUCERS.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((software.ROOT / name).read_bytes())
        assert compare.snapshot.digest(path) == expected
        path.chmod(0o444)
        files[name] = dict(
            checkout_path=name,
            sha256=expected,
            observation=dict(size=path.stat().st_size),
            snapshot_mode=0o444,
        )
    (source / "checkout.patch").write_bytes(b"")
    (source / "checkout.patch").chmod(0o444)
    _save(
        source / "SNAPSHOT.json",
        dict(
            kind="cells.checkout_source_snapshot@1",
            status="complete",
            immutable=True,
            files=files,
            patch_sha256=compare.snapshot.digest(source / "checkout.patch"),
        ),
    )
    for path in source.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    _save(inputs / "sim_config.yaml", dict(synthetic_immutable_input=True))
    execution_source = dict(
        root=str(source),
        snapshot_sha256=compare.snapshot.digest(source / "SNAPSHOT.json"),
        owned_files=compare.REF_PRODUCERS,
    )
    parent = _save(
        tmp_path / "INIT-prepared.json",
        dict(
            execution_source=execution_source,
            source_plan=dict(input_profile="headless"),
            native_inventory_sha256="d" * 64,
            inputs=dict(
                mode="original",
                root=str(inputs),
                inventory=dict(
                    files={
                        "sim_config.yaml": dict(
                            sha256=compare.snapshot.digest(inputs / "sim_config.yaml")
                        )
                    }
                ),
            ),
        ),
    )
    parent_result = dict(kind=compare.codec.REFERENCE_KIND, status="completed", synthetic=True)
    _save(output / "result.json", parent_result)
    prepared = _save(
        tmp_path / "prepared.json",
        dict(
            kind=compare.REF_KIND,
            held=True,
            execution_source=execution_source,
            INIT_prepared=parent,
        ),
    )
    release = _save(
        tmp_path / "release.json",
        dict(
            kind="cells.original_SIM_reference_execution_release@1",
            prepared_sha256=prepared["sha256"],
            worker_output=str(output),
        ),
    )
    captures, iterations = [], []
    folder = output / "SIM-reference/captures"
    folder.mkdir(parents=True)
    for i in range(count):
        label = f"SIM.iteration_{i + 1:04d}"
        pins = compare.codec.evidence.write(
            folder / f"{i}.json", _row_wire(i, rich=True), label=label
        )
        captures.append(dict(label=label, status="saved", files=pins))
        iterations.append(pins[0])
    captures.append(
        dict(
            label=f"SIM.iteration_{count + 1:04d}",
            status="capture_failed",
            error=dict(type="OSError", message="retained original capture failure"),
        )
    )
    worker = _save(
        output / "SIM-reference-result.json",
        dict(
            kind=compare.REF_KIND,
            status="failed",
            stage="SIM",
            INIT_result=parent_result,
            primary=dict(identity=123, cause=dict(identity=122)),
            capture_errors=[],
            SIM_capture_errors=[dict(stage="iteration_capture", identity=124)],
            SIM_captures=captures,
            SIM_iterations=iterations,
        ),
    )
    controller = _save(
        tmp_path / "result.json", dict(status="failed", synthetic_metadata_only=True)
    )
    return dict(prepared=prepared, release=release, controller=controller, worker=worker)


def test_sim_compare_plan_retains_prerequisites_and_scope():
    plan = compare.source_plan()
    assert plan["tolerance"] is None and plan["searched_epoch_shift"] is False
    assert plan["issued_SIM_producer_kind"] is None
    assert plan["live_owner_or_checkpoint_hydration"] is False
    assert plan["numerical_physical_or_restart_credit"] == 0
    assert "numpy" not in sys.modules


@pytest.mark.parametrize("count", [1, 3, 500, 512])
def test_sim_compare_complete_history_and_declared_groups(tmp_path, count):
    result = compare.compare_views(_view(count), _view(count))
    assert result["endpoint_complete"] and result["all_requested_groups_available"]
    assert result["available_observations_equal"] is True
    assert result["numerical_parity"] == dict(
        available=True,
        equal=True,
        scope="exact declared saved SIM groups/epochs only; no physical/restart qualification",
        reason=None,
    )
    assert result["numerical_physical_or_restart_credit"] == 0
    _save(tmp_path / "comparison.json", result)


@pytest.mark.parametrize("group", compare.GROUPS)
def test_sim_compare_missing_group_never_becomes_zero_or_equality(group):
    left, right = _view(), _view()
    right["rows"][1]["groups"][group] = None
    result = compare.compare_views(left, right)
    assert result["endpoint_complete"] and not result["all_requested_groups_available"]
    assert result["observations"][1]["groups"][group] == dict(available=False, equal=None)
    assert result["numerical_parity"]["available"] is False


@pytest.mark.parametrize("field", ["ordinal", "epoch", "source_time_bits", "dt_bits", "sampled"])
def test_sim_compare_no_time_search_relabelling_or_missing_clock(field):
    left, right = _view(), _view()
    row = right["rows"][1]
    if field == "ordinal":
        row[field] += 1
    elif field == "epoch":
        row[field] = "original_full_INIT_body_end_before_next_FOR_ITER"
    elif field == "sampled":
        row[field] = not row[field]
        row["groups"]["clock"][field] = row[field]
    else:
        row[field] = struct.pack("!d", 7.0).hex()
        row["groups"]["clock"][field] = row[field]
        if field == "source_time_bits":
            right["calendar"][1] = row[field]
    if field in ("ordinal", "epoch"):
        with pytest.raises(ValueError):
            compare.compare_views(left, right)
    else:
        result = compare.compare_views(left, right)
        assert result["observations"][1]["status"] == "different_explicit_SIM_clock"
        assert result["observations"][1]["groups"] == {}
        assert not result["all_requested_groups_available"]
        assert not result["numerical_parity"]["available"]


@pytest.mark.parametrize("key", ["mode", "inputs", "original_sources", "configuration_profile"])
def test_sim_compare_provenance_original_and_omitted_flux_are_distinct(key):
    left, right = _view(), _view()
    right[key] = "disabled" if key == "mode" else "changed"
    result = compare.compare_views(left, right)
    assert result["status"] == "incompatible_provenance" and result["observations"] == []


@pytest.mark.parametrize("field", compare.LINEAGE)
def test_sim_compare_missing_or_changed_old_new_p_and_sim_cells_lineage(field):
    left, right = _view(), _view()
    right["lineage"][field] = False
    result = compare.compare_views(left, right)
    assert result["endpoint_complete"] and result["available_observations_equal"]
    assert not result["lineage_verified"] and not result["numerical_parity"]["available"]


@pytest.mark.parametrize("defect", ["missing", "epoch", "binding", "MT_word", "Gaussian_bits"])
def test_sim_compare_mismatched_initial_rng_refuses_numerical_parity(defect):
    left, right = _view(), _view()
    state = right["initial_rng"]
    if defect == "missing":
        state["available"] = False
    elif defect == "epoch":
        state["epoch"] = "after_INIT_not_pre_SEED"
    elif defect == "binding":
        state["common_binding"]["input_inventory_sha256"] = "e" * 64
    elif defect == "MT_word":
        state["full_state"]["python"]["items"][1]["items"][17]["value"] += 1
    else:
        state["full_state"]["numpy"]["items"][-1]["bits"] = "010000000000f87f"
    result = compare.compare_views(left, right)
    assert result["endpoint_complete"] and not result["numerical_parity"]["available"]
    assert result["numerical_parity"]["equal"] is None


@pytest.mark.parametrize("defect", ["dtype", "shape", "stride", "signed_zero", "NaN_payload"])
def test_sim_compare_exact_array_bits_dtype_shape_layout(defect):
    left, right = _view(), _view()
    node = right["rows"][0]["groups"]["voltage"]["saved_typed_observation"]
    if defect == "dtype":
        node["layout"]["dtype"] = ">f8"
    elif defect == "shape":
        node["layout"]["shape"] = [1, 2]
    elif defect == "stride":
        node["layout"].update(strides_bytes=[-8], C_contiguous=False, F_contiguous=False)
    else:
        raw = (
            struct.pack("<2d", 0.0, 1.0)
            if defect == "signed_zero"
            else bytes.fromhex("010000000000f87f000000000000f03f")
        )
        node["bytes"]["sha256"] = hashlib.sha256(raw).hexdigest()
    result = compare.compare_views(left, right)
    assert result["numerical_parity"]["available"] and result["numerical_parity"]["equal"] is False
    assert result["observations"][0]["groups"]["voltage"]["equal"] is False


def test_sim_compare_partial_failures_preserve_prefix_primary_capture(tmp_path):
    left, right = _view(2, complete=False), _view(3)
    left["failure"] = dict(
        primary=dict(identity=10, cause=dict(identity=9)), capture_errors=[dict(identity=11)]
    )
    result = compare.compare_views(left, right)
    assert (
        result["endpoint_complete"] is False and result["failures"]["reference"] is left["failure"]
    )
    assert result["observations"][-1]["status"] == "missing_completed_prefix_observation"
    assert not result["numerical_parity"]["available"]
    _save(tmp_path / "failed-prefix-report.json", result)


@pytest.mark.parametrize("defect", ["empty", "short", "513", "clock_group", "RNG_empty"])
def test_sim_compare_incomplete_or_malformed_history_cannot_claim_completion(defect):
    left, right = _view(), _view()
    if defect == "empty":
        right = _view(0)
    elif defect == "short":
        right["rows"].pop()
    elif defect == "513":
        right = _view(513)
    elif defect == "clock_group":
        right["rows"][0]["groups"]["clock"]["sampled"] = False
    else:
        right["rows"][0]["groups"]["rng"]["numpy"]["items"] = []
    with pytest.raises(ValueError):
        compare.compare_views(left, right)


def test_sim_compare_actual_wire_roster_has_explicit_missing_channels(tmp_path):
    path = tmp_path / "iteration.json"
    pins = compare.codec.evidence.write(path, _row_wire(0), label="synthetic")
    row = compare._read_row(compare.report.Reader(), pins[0], 0)
    assert row["ordinal"] == 0 and row["epoch"] == compare.EPOCH
    assert row["groups"]["gates"] is row["groups"]["fields"] is row["groups"]["events"] is None
    assert row["groups"]["rng"] == _rng()
    assert row["groups"]["concentrations"]["cc_cells"]["layout"]["shape"] == [2]


def test_sim_compare_known_reference_failure_is_forensic_not_authenticated(tmp_path):
    pins = _saved_reference(tmp_path)
    side = compare.reference_side(pins)
    assert side["error"] is None, side["error"]
    assert side["files_bound"] and not side["authenticated"] and not side["endpoint_complete"]
    assert len(side["rows"]) == 2 and side["failure"]["primary"]["identity"] == 123
    result = compare.compare_saved(pins, dict(held_preparation=True))
    assert result["status"] == "unverified_evidence" and not result["endpoint_complete"]
    assert result["sides"]["reference"]["retained_completed_rows"] == 2
    assert result["errors"]["issued"]["type"] == "ProducerPrerequisiteUnavailable"


@pytest.mark.parametrize(
    "defect", ["primary_file", "sidecar", "extra_iteration", "input_drift", "parent", "snapshot"]
)
def test_sim_compare_known_file_graph_defects_preserve_primary_and_refuse(tmp_path, defect):
    pins = _saved_reference(tmp_path)
    worker = json.loads(Path(pins["worker"]["path"]).read_text())
    if defect == "primary_file":
        worker["SIM_iterations"][0] = dict(path="not-actual-primary", sha256="0" * 64)
    elif defect == "sidecar":
        Path(worker["SIM_iterations"][0]["path"]).unlink()
    elif defect == "extra_iteration":
        worker["SIM_iterations"].pop()
    elif defect == "input_drift":
        (tmp_path / "inputs/sim_config.yaml").write_text("changed")
    elif defect == "parent":
        worker["INIT_result"]["status"] = "failed"
    else:
        source = tmp_path / "source/SNAPSHOT.json"
        source.chmod(0o644)
        source.write_text("{}")
    _replace(pins["worker"], worker)
    side = compare.reference_side(pins)
    assert side["error"] is not None and not side["files_bound"]
    assert side["failure"]["primary"]["identity"] == 123
    assert not side["authenticated"] and not side["endpoint_complete"]


@pytest.mark.parametrize("target", ["reference", "issued", "both"])
def test_sim_compare_final_rebind_revokes_all_success_flags(tmp_path, monkeypatch, target):
    left, right = _view(), _view()
    paths = []
    for index, side in enumerate((left, right)):
        path = tmp_path / f"data-{index}.json"
        pin = _save(path, dict(unchanged=True))
        side["reader"].bound(pin)
        paths.append(path)
    monkeypatch.setattr(compare, "reference_side", lambda request: left)

    def issued(request):
        for name, path in zip(("reference", "issued"), paths, strict=True):
            if target in (name, "both"):
                path.write_text("{}")
        return right

    monkeypatch.setattr(compare, "issued_side", issued)
    result = compare.compare_saved({}, {})
    assert result["status"] == "evidence_changed_during_comparison"
    assert result["observations"] == [] and result["endpoint_complete"] is False
    assert result["all_requested_groups_available"] is False
    assert result["available_observations_equal"] is None
    assert result["numerical_parity"]["available"] is False
    assert result["unverified_forensics"]["endpoint_complete"] is True


@pytest.mark.parametrize("drift", [False, True])
def test_sim_compare_CLI_request_is_bound_after_comparison(tmp_path, monkeypatch, drift):
    request = _save(tmp_path / "request.json", dict(reference={}, issued={}))
    output = tmp_path / "report.json"

    def compare_request(*args):
        result = compare.compare_views(_view(), _view())
        if drift:
            Path(request["path"]).write_text("{}")
        return result

    monkeypatch.setattr(compare, "compare_saved", compare_request)
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
    assert result["endpoint_complete"] is (not drift)
    if drift:
        assert result["status"] == "request_changed_during_comparison"
        assert result["unverified_forensics"]["endpoint_complete"]


def _starting_records():
    raw = _row_wire(0)
    values = {key["value"]: value for key, value in raw["tree"]["values"]}
    mt, py = values["numpy_random"], values["python_random"]
    array = mt["values"][1]
    column = raw["columns"][array["column"]]
    ref = dict(
        tree=dict(
            type="dict",
            values=[
                [dict(type="str", value=name), value]
                for name, value in dict(
                    numpy_random=mt,
                    python_random=py,
                    initial_random_reset_or_replacement=dict(type="bool", value=False),
                ).items()
            ],
        ),
        columns={array["column"]: column},
    )
    demo = dict(
        numpy_random=[
            "MT19937",
            dict(
                __ndarray__=True,
                dtype="<u4",
                shape=[624],
                strides=[4],
                raw_bytes_hex=column["raw_bytes_hex"],
            ),
            624,
            0,
            dict(float64_bits=mt["values"][4]["bits"]),
        ],
        python_random=[3, [item["value"] for item in py["values"][1]["values"]], None],
        initial_random_reset_or_replacement=False,
    )
    common = dict(
        input_inventory_sha256="a" * 64,
        mode="original",
        profile="headless",
        runtime=dict(python="synthetic"),
    )
    witnesses = []
    for state, boundary, source_name in (
        (demo, "after_issued_WorldReady_before_geometry_phase_construction", "demo"),
        (ref, "after_original_Parameters.make_and_SimRunner_before_runner.seed", "reference"),
    ):
        witnesses.append(
            dict(
                kind="cells.common_initial_rng_observation@1",
                epoch=compare.INITIAL_EPOCH,
                state=json.loads(json.dumps(state)),
                common_binding=json.loads(json.dumps(common)),
                source=dict(synthetic_producer=source_name),
                order=dict(boundary=boundary, same_parameter=True, seed_entered=False),
                observed_states_equalized=False,
                common_starting_authority_established=False,
            )
        )
    return demo, ref, witnesses


def _fixture_functions(path, names, namespace):
    """Reuse only named inert fixture constructors, with no imports/exec."""
    tree = ast.parse(path.read_bytes())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    require_names = {n.name for n in nodes}
    assert require_names == set(names)
    compiled = compile(
        ast.Module(body=nodes, type_ignores=[]), str(path), "exec", dont_inherit=True
    )
    codes = {c.co_name: c for c in compiled.co_consts if type(c) is CodeType}
    for node in nodes:
        defaults = tuple(ast.literal_eval(value) for value in node.args.defaults)
        fn = FunctionType(codes[node.name], namespace, node.name, defaults or None)
        fn.__kwdefaults__ = {
            arg.arg: ast.literal_eval(value)
            for arg, value in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
            if value is not None
        } or None
        namespace[node.name] = fn
    return namespace


def _demo_rng_files(tmp_path, *, mode="original"):
    import copy
    import zipfile

    path = software.ROOT / "tests/unit/test_native_seed_demo_report.py"
    tree = ast.parse(path.read_bytes())
    names = [
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and not n.name.startswith("test_")
        and not n.decorator_list
    ]
    ns = dict(
        report=compare.report,
        hashlib=hashlib,
        json=json,
        struct=struct,
        copy=copy,
        os=os,
        zipfile=zipfile,
        NS=SimpleNamespace,
        __name__="tests.synthetic_saved_fixture",
    )
    functions = _fixture_functions(path, names, ns)
    value = functions["fixture"](tmp_path, mode=mode, version=12)
    return dict(
        plan=functions["pin"](value.plan),
        outcome=functions["pin"](value.worker / "demo/outcome.json"),
    ), value


def _typed(value, columns):
    if type(value) is dict:
        if value.get("__ndarray__") is True:
            name = f"rng_{len(columns)}"
            raw = bytes.fromhex(value["raw_bytes_hex"])
            columns[name] = dict(
                dtype=value["dtype"], shape=value["shape"], raw_bytes_hex=raw.hex()
            )
            return dict(
                type="array",
                layout=dict(
                    dtype=value["dtype"],
                    shape=value["shape"],
                    strides_bytes=value["strides"],
                    C_contiguous=True,
                    F_contiguous=True,
                ),
                column=name,
                sha256=hashlib.sha256(raw).hexdigest(),
            )
        if set(value) == {"float64_bits"}:
            return dict(type="float", bits=value["float64_bits"])
        return dict(
            type="dict",
            values=[
                [dict(type="str", value=key), _typed(item, columns)] for key, item in value.items()
            ],
        )
    if type(value) in (list, tuple):
        return dict(type=type(value).__name__, values=[_typed(item, columns) for item in value])
    return dict(type=type(value).__name__, value=value)


def _reference_rng_files(tmp_path, *, saved_state=None):
    path = software.ROOT / "tests/unit/test_native_init_terminal_reference_compare.py"
    private = SimpleNamespace(**vars(compare.codec))
    private._reference_source = FunctionType(
        compare.codec._reference_source.__code__,
        dict(vars(compare.codec), REFERENCE_AST_SHA256=compare.REFERENCE_RNG_AST_SHA256),
    )
    ns = dict(
        compare=private,
        software=software,
        ast=ast,
        hashlib=hashlib,
        json=json,
        struct=struct,
        Path=Path,
        __name__="tests.synthetic_saved_fixture",
    )
    funcs = _fixture_functions(
        path, ("_saved_reference", "_write", "_node", "_wire_array", "_dict_wire"), ns
    )
    request = funcs["_saved_reference"](tmp_path, count=1)
    plan = json.loads(Path(request["prepared"]["path"]).read_text())
    worker = json.loads(Path(request["worker"]["path"]).read_text())
    output = Path(request["worker"]["path"]).parent
    runtime = json.loads((output / "runtime.json").read_text())
    executable = _save(tmp_path / "executable.fixture", dict(inert=True))
    origins = {
        name: _save(tmp_path / (name + ".fixture"), dict(inert=name))
        for name in compare.RNG_MODULES
    }
    runtime.update(python="3.13.synthetic", executable=executable)
    runtime["loaded_files"].update(origins)
    _replace(dict(path=str(output / "runtime.json")), runtime)
    root = Path(plan["inputs"]["root"])
    plan["inputs"]["inventory"] = compare.input_files.inventory(root)
    _replace(request["prepared"], plan)
    release = json.loads(Path(request["release"]["path"]).read_text())
    release["prepared_sha256"] = request["prepared"]["sha256"]
    _replace(request["release"], release)
    process_path = tmp_path / "process/process-inputs.json"
    process = json.loads(process_path.read_text())
    for flag, value in (
        ("--prepared-sha256", request["prepared"]["sha256"]),
        ("--release-sha256", request["release"]["sha256"]),
    ):
        process["command"][process["command"].index(flag) + 1] = value
    _replace(dict(path=str(process_path)), process)
    state, _, _ = _starting_records()
    if saved_state is not None:
        state = json.loads(json.dumps(saved_state))
    state = dict(
        state,
        numpy_random=tuple(state["numpy_random"]),
        python_random=(
            state["python_random"][0],
            tuple(state["python_random"][1]),
            state["python_random"][2],
        ),
    )
    order = dict(
        boundary="after_original_Parameters.make_and_SimRunner_before_runner.seed",
        stage="original_runner",
        parameter_identity=31,
        runner_identity=32,
        same_parameter=True,
        seed_entered=False,
        selected_boundaries=[],
        native_sites=[
            dict(
                site=["betse.science.parameters", "load", 479, "original_parameters"],
                counts=[1, 1, 10, 10],
            ),
            dict(
                site=["betse.science.simrunner", "__init__", 50, "original_runner"],
                counts=[1, 1, 20, 20],
            ),
        ],
    )
    witness = dict(
        kind="cells.common_initial_rng_observation@1",
        epoch=compare.INITIAL_EPOCH,
        common_binding=dict(
            input_inventory_sha256=compare.codec.saved._seal(plan["inputs"]["inventory"]),
            mode=plan["inputs"]["mode"],
            profile=plan["source_plan"]["input_profile"],
            runtime=dict(
                python=runtime["python"],
                executable=executable,
                numpy_version="synthetic",
                files=origins,
            ),
        ),
        state=state,
        source=dict(
            reference_sha256=plan["execution_source"]["owned_files"][compare.codec.REF_SOURCE],
            snapshot_sha256=plan["execution_source"]["snapshot_sha256"],
            native_inventory_sha256=plan["native_inventory_sha256"],
            original_critical_pins=plan["source_plan"]["critical_source_pins"],
        ),
        order=order,
        observed_states_equalized=False,
        common_starting_authority_established=False,
        scientific_physical_checkpoint_credit=0,
    )
    captures = []
    for label, value in (("before_seed_random_states", state), ("pre_seed_rng_witness", witness)):
        columns = {}
        raw = dict(tree=_typed(value, columns), columns=columns)
        files = compare.codec.evidence.write(
            output / "captures" / (label + ".json"), raw, label=label
        )
        captures.append(dict(label=label, status="saved", files=files))
    worker["captures"] = captures + worker["captures"]
    worker["initial_rng_observation"] = captures[1]["files"][0]
    worker["work_sites"] = order["native_sites"]
    worker["status"] = "failed"
    worker["primary"] = [dict(type="synthetic.later_source_failure", identity=90)]
    _replace(request["worker"], worker)
    controller = json.loads(Path(request["controller"]["path"]).read_text())
    controller["worker_result_sha256"] = request["worker"]["sha256"]
    _replace(request["controller"], controller)
    return request


@pytest.mark.parametrize("mode", ["original", "disabled"])
def test_sim_compare_rng_saved_demo_authenticates_real_grammar_without_SIM(mode, tmp_path):
    request, _ = _demo_rng_files(tmp_path, mode=mode)
    side = compare.demo_starting_rng(request)
    assert side["authenticated"] and side["available"], side["error"]
    assert side["witness"]["common_binding"]["mode"] == mode
    assert side["complete_SIM"] is False and side["common_starting_authority_established"] is False
    assert side["numerical_parity_available"] is False
    _save(
        tmp_path / "demo-starting-authentication.json",
        dict(
            authenticated=side["authenticated"],
            available=side["available"],
            error=side["error"],
            observed_file_pins=side["reader"].pins,
            scientific_credit=0,
        ),
    )


def test_sim_compare_rng_saved_reference_authenticates_failed_prefix(tmp_path):
    request = _reference_rng_files(tmp_path)
    side = compare.reference_starting_rng(request)
    assert side["authenticated"] and side["available"], side["error"]
    assert side["failure"]["status"] == "failed" and side["failure"]["primary"][0]["identity"] == 90
    assert side["complete_SIM"] is False and side["common_starting_authority_established"] is False
    _save(
        tmp_path / "reference-starting-authentication.json",
        dict(
            authenticated=side["authenticated"],
            available=side["available"],
            error=side["error"],
            observed_file_pins=side["reader"].pins,
            scientific_credit=0,
        ),
    )


def _demo_capture_edit(request, label, action):
    outcome = json.loads(Path(request["outcome"]["path"]).read_text())
    row = next(row for row in outcome["captures"] if row["label"] == label)
    path = Path(request["outcome"]["path"]).parent / row["path"]
    value = json.loads(path.read_text())
    action(value)
    _replace(dict(path=str(path)), value)
    row["sha256"] = compare.snapshot.digest(path)
    if label == "pre_seed_rng_witness":
        outcome["initial_rng_observation"] = dict(row)
    _replace(request["outcome"], outcome)


@pytest.mark.parametrize(
    "defect",
    [
        "epoch",
        "boundary",
        "same_parameter",
        "seed_entered",
        "state",
        "snapshot",
        "parameter_packet",
        "runtime_missing",
        "runtime_retarget",
        "mode",
        "profile",
        "inventory",
        "input_extra",
        "input_changed",
        "capture_order",
        "capture_pin",
        "guard",
        "loaded_origin",
    ],
)
def test_sim_compare_rng_demo_rejects_resealed_drift(tmp_path, defect):
    request, value = _demo_rng_files(tmp_path)

    def change(w):
        if defect == "epoch":
            w["epoch"] = "after_INIT"
        elif defect == "boundary":
            w["order"]["boundary"] = "original_SimRunner"
        elif defect == "same_parameter":
            w["order"]["same_parameter"] = False
        elif defect == "seed_entered":
            w["order"]["seed_entered"] = True
        elif defect == "state":
            w["state"]["numpy_random"][2] = 17
        elif defect == "snapshot":
            w["source"]["snapshot_sha256"] = "0" * 64
        elif defect == "parameter_packet":
            w["source"]["parameter_packet_sha256"] = "0" * 64
        elif defect == "runtime_missing":
            w["common_binding"]["runtime"]["files"].pop("random")
        elif defect == "runtime_retarget":
            w["common_binding"]["runtime"]["files"]["random"] = w["common_binding"]["runtime"][
                "files"
            ]["_random"]
        elif defect == "mode":
            w["common_binding"]["mode"] = "disabled"
        elif defect == "profile":
            w["common_binding"]["profile"] = "headless"
        elif defect == "inventory":
            w["common_binding"]["input_inventory_sha256"] = "0" * 64

    if defect in ("input_extra", "input_changed"):
        root = Path(json.loads(value.plan.read_text())["parameter_inputs"]["path"])
        root = Path(json.loads(root.read_text())["program"]["root"])
        (root / ("extra.dat" if defect == "input_extra" else "original.yaml")).write_bytes(
            b"changed bytes"
        )
    elif defect in ("capture_order", "capture_pin"):
        outcome = json.loads(Path(request["outcome"]["path"]).read_text())
        if defect == "capture_order":
            outcome["captures"][0:2] = reversed(outcome["captures"][0:2])
        else:
            outcome["initial_rng_observation"]["sha256"] = "0" * 64
        _replace(request["outcome"], outcome)
    elif defect == "guard":
        path = value.output / "process/result.json"
        row = json.loads(path.read_text())
        row["sampled_peak_process_tree_rss_bytes"] = 2**31
        _replace(dict(path=str(path)), row)
    elif defect == "loaded_origin":
        path = value.worker / "runtime-after.json"
        row = json.loads(path.read_text())
        row["loaded_files"]["random"] = row["loaded_files"]["_random"]
        _replace(dict(path=str(path)), row)
    else:
        _demo_capture_edit(request, "pre_seed_rng_witness", change)
    side = compare.demo_starting_rng(request)
    assert not side["authenticated"] and not side["available"] and side["error"] is not None
    assert side["numerical_parity_available"] is False
    _save(tmp_path / "refusal.json", dict(error=side["error"], failure=side["failure"], credit=0))


def _reference_capture_edit(request, label, action):
    worker = json.loads(Path(request["worker"]["path"]).read_text())
    row = next(row for row in worker["captures"] if row["label"] == label)
    raw = compare.codec.evidence.read(
        row["files"][0]["path"], expand=True, expected_sha256=row["files"][0]["sha256"]
    )
    action(raw)
    folder = Path(request["worker"]["path"]).parent / "captures"
    fresh = folder / (label + ".repaired-fixture.json")
    row["files"] = compare.codec.evidence.write(fresh, raw, label=label)
    if label == "pre_seed_rng_witness":
        worker["initial_rng_observation"] = row["files"][0]
    _replace(request["worker"], worker)


@pytest.mark.parametrize(
    "defect",
    [
        "epoch",
        "state",
        "inventory",
        "mode",
        "profile",
        "source",
        "order",
        "same_parameter",
        "seed_entered",
        "roots_alias",
        "native_site",
        "runtime_missing",
        "runtime_retarget",
        "input_extra",
        "capture_order",
        "capture_pin",
        "guard",
        "source_producer",
    ],
)
def test_sim_compare_rng_reference_rejects_resealed_drift(tmp_path, defect):
    request = _reference_rng_files(tmp_path)
    if defect in ("input_extra", "guard", "source_producer"):
        if defect == "input_extra":
            (tmp_path / "prepared-config/extra.dat").write_bytes(b"undeclared")
        elif defect == "guard":
            p = tmp_path / "process/result.json"
            v = json.loads(p.read_text())
            v["elapsed_seconds"] = 8000
            _replace(dict(path=str(p)), v)
        else:
            p = tmp_path / "source" / compare.codec.REF_SOURCE
            p.chmod(0o644)
            p.write_text(p.read_text() + "\n# changed\n")
    elif defect in ("capture_order", "capture_pin"):
        worker = json.loads(Path(request["worker"]["path"]).read_text())
        if defect == "capture_order":
            worker["captures"][0:2] = reversed(worker["captures"][0:2])
        else:
            worker["initial_rng_observation"] = worker["captures"][0]["files"][0]
        _replace(request["worker"], worker)
    else:

        def change(raw):
            top = {k["value"]: v for k, v in raw["tree"]["values"]}
            common = {k["value"]: v for k, v in top["common_binding"]["values"]}
            order = {k["value"]: v for k, v in top["order"]["values"]}
            if defect == "epoch":
                top["epoch"]["value"] = "after_SIM"
            elif defect == "state":
                states = {k["value"]: v for k, v in top["state"]["values"]}
                states["numpy_random"]["values"][2]["value"] = 17
            elif defect in ("mode", "profile", "inventory"):
                key = {"mode": "mode", "profile": "profile", "inventory": "input_inventory_sha256"}[
                    defect
                ]
                common[key]["value"] = "changed"
            elif defect == "source":
                source = {k["value"]: v for k, v in top["source"]["values"]}
                source["reference_sha256"]["value"] = "0" * 64
            elif defect == "order":
                order["boundary"]["value"] = (
                    "after_issued_WorldReady_before_geometry_phase_construction"
                )
            elif defect in ("same_parameter", "seed_entered"):
                order[defect]["value"] = defect == "seed_entered"
            elif defect == "roots_alias":
                order["runner_identity"]["value"] = order["parameter_identity"]["value"]
            elif defect == "native_site":
                order["native_sites"]["values"] = [
                    _typed(dict(site=["x", "init", 1, "INIT"], counts=[1, 0, 1, 1]), {})
                ]
            else:
                runtime = {k["value"]: v for k, v in common["runtime"]["values"]}
                files = runtime["files"]["values"]
                if defect == "runtime_missing":
                    files.pop()
                else:
                    files[0][1] = files[1][1]

        _reference_capture_edit(request, "pre_seed_rng_witness", change)
    side = compare.reference_starting_rng(request)
    assert not side["authenticated"] and not side["available"] and side["error"] is not None
    assert side["failure"]["primary"][0]["identity"] == 90
    _save(tmp_path / "refusal.json", dict(error=side["error"], failure=side["failure"], credit=0))


def test_sim_compare_rng_paired_same_bytes_are_not_common_start_or_parity(tmp_path):
    demo_dir, ref_dir = tmp_path / "demo-case", tmp_path / "reference-case"
    demo_dir.mkdir()
    ref_dir.mkdir()
    demo, value = _demo_rng_files(demo_dir)
    outcome = json.loads(Path(demo["outcome"]["path"]).read_text())
    row = next(r for r in outcome["captures"] if r["label"] == "before_seed_random_states")
    state = json.loads((value.worker / "demo" / row["path"]).read_text())
    reference = _reference_rng_files(ref_dir, saved_state=state)
    result = compare.compare_starting_rng_saved(demo, reference)
    assert result["status"] == "starting_observation_files_authenticated", result
    assert result["comparison"]["states_equal"] is True
    assert result["comparison"]["common_binding_equal"] is False
    assert result["observations_match"] is False
    assert result["common_starting_authority_established"] is False
    assert result["numerical_parity_available"] is False
    _save(tmp_path / "paired-observations.json", result)


def test_sim_compare_rng_later_failure_keeps_authenticated_earlier_observation(tmp_path):
    request, _ = _demo_rng_files(tmp_path)
    outcome = json.loads(Path(request["outcome"]["path"]).read_text())
    outcome.update(
        status="failed",
        primary="OriginalLaterFailure",
        secondary=[dict(stage="later", error="CaptureError")],
    )
    _replace(request["outcome"], outcome)
    side = compare.demo_starting_rng(request)
    assert side["authenticated"] and side["available"], side["error"]
    assert side["failure"]["primary"] == "OriginalLaterFailure"
    assert side["failure"]["secondary"] == outcome["secondary"]
    assert side["complete_SIM"] is False


@pytest.mark.parametrize("missing", ["before_seed_random_states", "pre_seed_rng_witness"])
def test_sim_compare_rng_missing_capture_is_unavailable_not_state_inference(tmp_path, missing):
    request, _ = _demo_rng_files(tmp_path)
    value = json.loads(Path(request["outcome"]["path"]).read_text())
    row = next(r for r in value["captures"] if r["label"] == missing)
    (Path(request["outcome"]["path"]).parent / row["path"]).unlink()
    side = compare.demo_starting_rng(request)
    assert not side["authenticated"] and not side["available"]
    assert side["wire"] is None and side["error"] is not None


@pytest.mark.parametrize(
    "defect", ["missing_load", "missing_runner", "unfinished", "reordered", "duplicate"]
)
def test_sim_compare_rng_original_constructor_sites_are_required(tmp_path, defect):
    request = _reference_rng_files(tmp_path)

    def change(raw):
        values = {k["value"]: v for k, v in raw["tree"]["values"]}
        order = {k["value"]: v for k, v in values["order"]["values"]}
        sites = order["native_sites"]["values"]
        if defect.startswith("missing_"):
            sites.pop(0 if defect == "missing_load" else 1)
        elif defect == "duplicate":
            sites.append(sites[0])
        else:
            row = {k["value"]: v for k, v in sites[1]["values"]}
            row["counts"]["values"][1 if defect == "unfinished" else 2]["value"] = 0

    _reference_capture_edit(request, "pre_seed_rng_witness", change)
    side = compare.reference_starting_rng(request)
    assert side["authenticated"] is False and side["error"] is not None
    assert side["failure"]["primary"][0]["identity"] == 90
    _save(tmp_path / "constructor-order-refusal.json", side["error"])


@pytest.mark.parametrize(
    "defect",
    [
        "report_code",
        "report_keyword",
        "reader_constructor",
        "reader_default",
        "reader_type",
        "codec_code",
        "input_code",
        "input_hashing",
    ],
)
def test_sim_compare_rng_readers_refuse_retarget_before_delegation(tmp_path, monkeypatch, defect):
    touched = []

    def replacement(*args, **kwargs):
        _SYNTHETIC_ADAPTER_ATTEMPTS.append("replaced reader entered")

    def foreign_constructor(self):
        _SYNTHETIC_ADAPTER_ATTEMPTS.append("foreign constructor entered")

    check = compare._report_api
    module = compare.report
    if defect == "report_code":
        monkeypatch.setattr(module._plan, "__code__", replacement.__code__)
    elif defect == "report_keyword":
        monkeypatch.setattr(module._short_history_captures, "__kwdefaults__", dict(natural=True))
    elif defect == "reader_constructor":
        monkeypatch.setattr(module.Reader, "__init__", foreign_constructor)
    elif defect == "reader_default":
        monkeypatch.setattr(module.Reader.read, "__defaults__", ("supplied digest",))
    elif defect == "reader_type":
        monkeypatch.setattr(module, "Reader", replacement)
    elif defect == "codec_code":
        module = compare.codec
        monkeypatch.setattr(module._reference, "__code__", replacement.__code__)
        check = compare._reference_reader
    else:
        module = compare.input_files

        def check():
            return compare._source_reader(module, compare.INPUT_READER_SHA256)

        if defect == "input_code":
            monkeypatch.setattr(module.inventory, "__code__", replacement.__code__)
        else:
            monkeypatch.setattr(module, "hashlib", None)
    monkeypatch.setattr(module, "_SYNTHETIC_ADAPTER_ATTEMPTS", touched, raising=False)
    with pytest.raises(ValueError):
        check()
    assert touched == []
    _save(tmp_path / "reader-authority-refusal.json", dict(defect=defect, delegate_calls=touched))


def test_sim_compare_rng_foreign_reader_is_never_constructed_on_failure(tmp_path, monkeypatch):
    touched = []

    def foreign_reader():
        touched.append("constructed")
        raise AssertionError("foreign reader must not enter")

    monkeypatch.setattr(compare.report, "Reader", foreign_reader)
    result = compare.compare_starting_rng_saved({}, {})
    assert result["status"] == "unavailable" and touched == []
    assert all(not side["authenticated"] for side in result["sides"].values())
    assert result["file_pins"] == dict(demo=[], reference=[])
    _save(tmp_path / "foreign-reader-refusal.json", result)


def _rng_pair_files(tmp_path):
    demo_dir, ref_dir = tmp_path / "demo-side", tmp_path / "reference-side"
    demo_dir.mkdir()
    ref_dir.mkdir()
    demo, _ = _demo_rng_files(demo_dir)
    return demo, _reference_rng_files(ref_dir)


@pytest.mark.parametrize("target", ["demo", "reference", "both"])
def test_sim_compare_rng_final_rebind_revokes_authenticated_observations(
    tmp_path, monkeypatch, target
):
    demo, reference = _rng_pair_files(tmp_path)
    delegate = compare.compare_initial_rng_records

    def compare_then_change(*args, **kwargs):
        result = delegate(*args, **kwargs)
        for name, pin in (("demo", demo["outcome"]), ("reference", reference["worker"])):
            if target in (name, "both"):
                Path(pin["path"]).write_text("{}")
        return result

    monkeypatch.setattr(compare, "compare_initial_rng_records", compare_then_change)
    result = compare.compare_starting_rng_saved(demo, reference)
    assert result["status"] == "evidence_changed_during_starting_rng_authentication"
    assert all(not side["authenticated"] for side in result["sides"].values())
    assert result["observations_match"] is None and result["numerical_parity_available"] is False
    previous = result["unverified_forensics"]
    assert previous["status"] == "starting_observation_files_authenticated"
    assert all(side["authenticated"] for side in previous["sides"].values())
    _save(tmp_path / "late-file-drift.json", result)


@pytest.mark.parametrize("drift", [False, True])
def test_sim_compare_rng_CLI_preserves_starting_schema_and_request_binding(
    tmp_path, monkeypatch, drift
):
    demo, reference = _rng_pair_files(tmp_path)
    request = _save(tmp_path / "paired-request.json", dict(demo=demo, reference=reference))
    output = tmp_path / "paired-report.json"
    delegate = compare.compare_starting_rng_saved

    def compare_then_change(*args):
        result = delegate(*args)
        if drift:
            Path(request["path"]).write_text("{}")
        return result

    monkeypatch.setattr(compare, "compare_starting_rng_saved", compare_then_change)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compare",
            "--starting-rng",
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
    assert result["kind"] == compare.STARTING_REPORT_KIND
    assert result["common_starting_authority_established"] is False
    assert result["numerical_parity_available"] is False
    if drift:
        assert result["status"] == "request_changed_during_comparison"
        assert all(not side["authenticated"] for side in result["sides"].values())
        assert (
            result["unverified_forensics"]["status"] == "starting_observation_files_authenticated"
        )
    else:
        assert result["status"] == "starting_observation_files_authenticated"


def test_sim_compare_starting_adapter_is_read_only_and_keeps_distinct_orders(tmp_path):
    demo, ref, witnesses = _starting_records()
    result = compare.compare_initial_rng_records(
        demo, ref, demo_witness=witnesses[0], reference_witness=witnesses[1]
    )
    assert result["states_equal"] and result["common_binding_equal"]
    assert result["input_runtime_epoch_and_producer_authenticated"] is False
    assert result["common_starting_authority_established"] is False
    assert result["numerical_parity_available"] is False
    assert (
        result["retained_source_order"]["demo"]["order"]
        != result["retained_source_order"]["reference"]["order"]
    )
    _save(tmp_path / "starting-RNG-observation.json", result)


@pytest.mark.parametrize("defect", ["epoch", "order", "witness_state", "replacement", "empty_MT"])
def test_sim_compare_starting_adapter_refuses_witness_retarget(defect):
    demo, ref, witnesses = _starting_records()
    if defect == "epoch":
        witnesses[0]["epoch"] = "after_SIM"
    elif defect == "order":
        witnesses[0]["order"]["boundary"] = witnesses[1]["order"]["boundary"]
    elif defect == "witness_state":
        witnesses[0]["state"]["numpy_random"][2] = 17
    elif defect == "replacement":
        demo["initial_random_reset_or_replacement"] = True
    else:
        demo["numpy_random"][1]["raw_bytes_hex"] = "00" * 2496
    with pytest.raises(ValueError):
        compare.compare_initial_rng_records(
            demo, ref, demo_witness=witnesses[0], reference_witness=witnesses[1]
        )


@pytest.mark.parametrize("defect", ["source_pin", "delegate_code", "constant", "hash_global"])
def test_sim_compare_starting_adapter_checks_source_and_callables_before_use(monkeypatch, defect):
    touched = []

    def replacement(*args):
        _SYNTHETIC_ADAPTER_ATTEMPTS.append(True)

    if defect == "source_pin":
        monkeypatch.setattr(compare, "RNG_ADAPTER_SHA256", "0" * 64)
    elif defect == "delegate_code":
        monkeypatch.setattr(
            compare.rng_adapter, "_SYNTHETIC_ADAPTER_ATTEMPTS", touched, raising=False
        )
        monkeypatch.setattr(compare.rng_adapter.compare_states, "__code__", replacement.__code__)
    elif defect == "constant":
        monkeypatch.setattr(compare.rng_adapter, "KIND", "supplied replacement")
    else:
        monkeypatch.setattr(compare.rng_adapter, "hashlib", None)
    with pytest.raises(ValueError):
        compare._rng_api()
    assert touched == []


def test_sim_compare_rich_observations_keep_native_absence_without_zero_fill(tmp_path):
    pins = compare.codec.evidence.write(
        tmp_path / "rich.json", _row_wire(0, rich=True), label="synthetic"
    )
    row = compare._read_row(compare.report.Reader(), pins[0], 0, required_observation=True)
    assert row["groups"]["gates"] is not None and row["groups"]["events"] is not None
    fields = compare.codec._mapping(row["groups"]["fields"])
    assert compare.codec._mapping(fields["E_env_x"])["present"] == dict(kind="bool", value=False)


def test_sim_compare_current_reference_cannot_substitute_legacy_missing_observations(tmp_path):
    pins = compare.codec.evidence.write(tmp_path / "legacy.json", _row_wire(0), label="synthetic")
    with pytest.raises(ValueError, match="declared observation"):
        compare._read_row(compare.report.Reader(), pins[0], 0, required_observation=True)


def _metadata_wire(value):
    if type(value) is dict:
        return dict(
            type="dict",
            values=[
                [dict(type="str", value=key), _metadata_wire(item)] for key, item in value.items()
            ],
        )
    if type(value) in (list, tuple):
        return dict(type=type(value).__name__, values=[_metadata_wire(item) for item in value])
    return dict(type=type(value).__name__, value=value)


@pytest.mark.parametrize(
    "defect", [None, "aliased_p", "edge", "fact", "source", "hooks", "coverage"]
)
def test_sim_compare_closed_lineage_is_exact_data_not_live_authority(tmp_path, defect):
    value = dict(
        kind="cells.original_SIM_closed_lineage_observation@1",
        epoch="after_original_SIM_core_before_pickle_with_restored_hooks",
        facts={name: True for name in compare.LINEAGE},
        process_local_identities=dict(
            INIT_phase=1, old_parameters=2, SIM_phase=3, current_parameters=4, simulator=5, cells=6
        ),
        actual_edges=[
            ["INIT_phase", "p", "old_parameters"],
            ["INIT_phase", "sim", "simulator"],
            ["INIT_phase", "cells", "cells"],
            ["SIM_phase", "p", "current_parameters"],
            ["SIM_phase", "sim", "simulator"],
            ["SIM_phase", "cells", "cells"],
        ],
        source_returned=True,
        inherited_hooks_restored=True,
        observer_coverage_failed=False,
        live_owner_or_checkpoint_hydration=False,
    )
    if defect == "aliased_p":
        value["process_local_identities"]["current_parameters"] = 2
    elif defect == "edge":
        value["actual_edges"][3][-1] = "old_parameters"
    elif defect == "fact":
        value["facts"]["sim_retained"] = False
    elif defect == "source":
        value["source_returned"] = False
    elif defect == "hooks":
        value["inherited_hooks_restored"] = False
    elif defect == "coverage":
        value["observer_coverage_failed"] = True
    pin = compare.codec.evidence.write(
        tmp_path / "lineage.json",
        dict(tree=_metadata_wire(value), columns={}),
        label="synthetic closed lineage",
    )[0]
    if defect is not None:
        with pytest.raises(ValueError):
            compare._read_lineage(compare.report.Reader(), pin)
    else:
        result = compare._read_lineage(compare.report.Reader(), pin)
        assert result == value and result["live_owner_or_checkpoint_hydration"] is False


def _terminal_saved(tmp_path, monkeypatch):
    """Exact saved-file grammar with explicit synthetic adopted review pins.

    Only metadata is produced. No worker/process, original source body or
    retained owner is constructed, and these fixtures grant no execution.
    """
    from validation.betse import native_sim_reference as producer

    source, output, inputs = tmp_path / "source", tmp_path / "worker", tmp_path / "inputs"
    source.mkdir()
    output.mkdir()
    inputs.mkdir()
    config = _save(inputs / "sim_config.yaml", dict(synthetic_input_only=True))
    inventory = dict(
        directories=[],
        files={
            "sim_config.yaml": dict(
                sha256=config["sha256"], size_bytes=Path(config["path"]).stat().st_size
            )
        },
    )
    native = producer.initial.source_inventory()
    source_plan = producer.source_plan()
    contracts = producer.review_contracts()
    reviews = {
        role: _save(tmp_path / f"review-{role}.json", value) for role, value in contracts.items()
    }
    source_plan["reviews"] = {role: pin["sha256"] for role, pin in reviews.items()}
    file_names = (*compare.REF_PRODUCERS, producer.initial.FILE)
    files, accepted = {}, {}
    for name in file_names:
        raw = (software.ROOT / name).read_bytes()
        if name == producer.FILE:
            tree = ast.parse(raw)
            adopted = {
                "SOURCE_REVIEW_SHA256": reviews["source"]["sha256"],
                "REFERENCE_REVIEW_SHA256": reviews["reference"]["sha256"],
                "EXECUTION_REVIEW_SHA256": reviews["execution"]["sha256"],
            }
            body = []
            for node in tree.body:
                if isinstance(node, ast.Assign) and {
                    getattr(t, "id", None) for t in node.targets
                } == set(adopted):
                    body.extend(
                        ast.Assign(
                            targets=[ast.Name(id=key, ctx=ast.Store())], value=ast.Constant(value)
                        )
                        for key, value in adopted.items()
                    )
                else:
                    body.append(node)
            tree.body = body
            raw = ast.unparse(ast.fix_missing_locations(tree)).encode()
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o444)
        digest = compare.snapshot.digest(path)
        files[name] = dict(
            checkout_path=name, sha256=digest, observation=dict(size=len(raw)), snapshot_mode=0o444
        )
        if name in compare.REF_PRODUCERS:
            accepted[name] = digest
    monkeypatch.setattr(compare, "REF_PRODUCERS", accepted)
    (source / "checkout.patch").write_bytes(b"synthetic metadata snapshot\n")
    (source / "checkout.patch").chmod(0o444)
    _save(
        source / "SNAPSHOT.json",
        dict(
            kind="cells.checkout_source_snapshot@1",
            status="complete",
            immutable=True,
            files=files,
            patch_sha256=compare.snapshot.digest(source / "checkout.patch"),
        ),
    )
    for path in source.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    source.chmod(0o555)
    execution = dict(
        root=str(source),
        snapshot_sha256=compare.snapshot.digest(source / "SNAPSHOT.json"),
        owned_files=accepted,
    )
    parent_plan = dict(
        execution_source=execution,
        source_plan=producer.initial.source_plan(input_profile="headless_core"),
        native_root=str(producer.initial.NATIVE_ROOT),
        native_inventory=native,
        native_inventory_sha256=producer.initial._seal(native),
        inputs=dict(
            root=str(inputs), inventory=inventory, mode="original", profile="headless_core"
        ),
    )
    parent = _save(tmp_path / "INIT-prepared.json", parent_plan)
    parent_result = dict(
        kind=compare.codec.REFERENCE_KIND,
        status="completed",
        source_returned=True,
        inherited_hooks_restored=True,
        observer_coverage_failed=False,
        filesystem_audit_installed=True,
    )
    _save(output / "result.json", parent_result)
    plan = dict(
        kind=compare.REF_KIND,
        held=True,
        execution_source=execution,
        source_plan=source_plan,
        INIT_prepared=parent,
    )
    prepared = _save(tmp_path / "prepared.json", plan)
    init_release = _save(
        tmp_path / "INIT-release.json",
        dict(
            kind="cells.original_INIT_reference_execution_release@1",
            enabled=True,
            prepared_sha256=parent["sha256"],
            snapshot_sha256=execution["snapshot_sha256"],
            worker_output=str(output),
        ),
    )
    release = _save(
        tmp_path / "release.json",
        dict(
            kind="cells.original_SIM_reference_execution_release@1",
            enabled=True,
            prepared_sha256=prepared["sha256"],
            worker_output=str(output),
            reviews=reviews,
            policy=source_plan["resource_policy"],
            init_release=init_release,
        ),
    )
    captures, iterations = [], []
    folder = output / "SIM-reference/captures"
    folder.mkdir(parents=True)

    def capture(label, wire):
        pins = compare.codec.evidence.write(folder / f"{len(captures)}.json", wire, label=label)
        captures.append(dict(label=label, status="saved", files=pins))
        return pins[0]

    for i in range(2):
        iterations.append(capture(f"SIM.iteration_{i + 1:04d}", _row_wire(i, rich=True)))
    columns = {}
    calendar_node = _wire(_array(struct.pack("<2d", 0.0, 0.125)), columns)
    raw_calendar = struct.pack("<2d", 0.0, 0.125)
    columns[calendar_node["column"]]["raw_bytes_hex"] = raw_calendar.hex()
    calendar_node["sha256"] = hashlib.sha256(raw_calendar).hexdigest()
    capture(
        "SIM.original_calendar",
        dict(
            columns=columns,
            tree=dict(
                type="tuple",
                values=[
                    calendar_node,
                    dict(
                        type="set", values=[dict(type="float", bits=struct.pack("<d", 0.0).hex())]
                    ),
                ],
            ),
        ),
    )
    identities = dict(
        INIT_phase=101,
        old_parameters=102,
        SIM_phase=103,
        current_parameters=104,
        simulator=105,
        cells=106,
    )
    lineage = dict(
        kind="cells.original_SIM_closed_lineage_observation@1",
        epoch="after_original_SIM_core_before_pickle_with_restored_hooks",
        facts={name: True for name in compare.LINEAGE},
        process_local_identities=identities,
        actual_edges=[
            [phase, field, root]
            for phase, p in (("INIT_phase", "old_parameters"), ("SIM_phase", "current_parameters"))
            for field, root in (("p", p), ("sim", "simulator"), ("cells", "cells"))
        ],
        source_returned=True,
        inherited_hooks_restored=True,
        observer_coverage_failed=False,
        live_owner_or_checkpoint_hydration=False,
    )
    lineage_pin = capture("SIM.closed_lineage", dict(tree=_metadata_wire(lineage), columns={}))
    terminal = dict(
        kind="cells.original_SIM_terminal_observation@1",
        epoch=compare.EPOCH,
        normal_phase_return=True,
        normal_report_return=True,
        normal_core_prefix_return=True,
        normal_full_loop_return=True,
        normal_context_return=True,
        normal_selected_caller_return=True,
        context_entries=2,
        context_yield=True,
        before_native_pickle=True,
        native_pickle_entered=False,
        configured_iterations=2,
        completed_iterations=2,
        source_time_bits=["0000000000000000", "3fc0000000000000"],
        sampled_time_bits=["0000000000000000"],
        dt_bits="3fc0000000000000",
        selected_source=source_plan["original"]["terminal_observation"],
        events=[
            [i + 1, *event]
            for i, event in enumerate(
                source_plan["original"]["terminal_observation"]["required_events"]
            )
        ],
        actual_frame_identities={
            role: i + 1
            for i, role in enumerate(
                ("phase", "report", "core", "calendar", "loop", "context", "caller")
            )
        },
        lineage_identities=identities,
        physical_checkpoint_or_common_starting_authority=False,
    )
    terminal_pin = capture("SIM.terminal", dict(tree=_metadata_wire(terminal), columns={}))
    copied = dict(
        root=str(output / "config"),
        source_root=str(inputs),
        inventory=inventory,
        files=[
            dict(
                name="sim_config.yaml",
                sha256=config["sha256"],
                status="copied",
                source_inode=[1, 2],
                execution_inode=[1, 3],
            )
        ],
    )
    (output / "config").mkdir()
    (output / "config/sim_config.yaml").write_bytes(Path(config["path"]).read_bytes())
    _save(output / "execution-inputs.json", copied)
    executable = tmp_path / "python"
    executable.write_bytes(b"synthetic process metadata, never executed")
    native_names = (
        "betse",
        "betse.science",
        "betse.science.simrunner",
        "betse.science.sim",
        "betse.science.phase.phasecls",
        "betse.util.type.contexts",
    )
    native_producers = {
        name: dict(
            path=str(
                producer.initial.NATIVE_ROOT
                / (
                    name.replace(".", "/")
                    + ("/__init__.py" if name in ("betse", "betse.science") else ".py")
                )
            ),
            sha256=native[
                name.replace(".", "/")
                + ("/__init__.py" if name in ("betse", "betse.science") else ".py")
            ]["sha256"],
            selections=[],
        )
        for name in native_names
    }
    loaded = {
        name: {key: row[key] for key in ("path", "sha256")}
        for name, row in native_producers.items()
    }
    for name in (producer.FILE, producer.LITERAL, producer.initial.FILE):
        loaded[name[:-3].replace("/", ".")] = dict(
            path=str(source / name), sha256=files[name]["sha256"]
        )
    _save(
        output / "SIM-reference/runtime.json",
        dict(
            python="synthetic-runtime-only",
            executable=dict(path=str(executable), sha256=compare.snapshot.digest(executable)),
            loaded_files=loaded,
        ),
    )
    _save(
        output / "SIM-reference/filesystem.json",
        dict(
            installed=True,
            failures=[],
            first_error=None,
            write_policy=dict(failures=[], first_error=None),
        ),
    )
    _save(
        output / "SIM-reference/source-input-binding.json",
        dict(
            execution_source=execution,
            prepared_inputs=parent_plan["inputs"],
            execution_inputs=copied,
            native_producers=native_producers,
        ),
    )
    policy = source_plan["resource_policy"]
    limits = dict(
        max_wall_seconds=policy["wall_seconds"],
        max_process_tree_rss_bytes=policy["max_rss_bytes"],
        min_available_host_memory_bytes=policy["reserve_bytes"],
    )
    process = dict(
        status="completed",
        returncode=0,
        elapsed_seconds=1.0,
        sampled_peak_process_tree_rss_bytes=1024,
        minimum_available_host_memory_bytes=policy["reserve_bytes"],
        samples=1,
        limits=limits,
    )
    process_root = tmp_path / "process"
    process_root.mkdir()
    _save(process_root / "result.json", process)
    _save(
        process_root / "process-inputs.json",
        dict(
            cwd=str(source),
            limits=limits,
            command=[
                str(executable),
                "-B",
                "-m",
                "validation.betse.native_sim_reference",
                "--prepared",
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
        ),
    )
    controller = _save(
        tmp_path / "result.json",
        dict(
            kind=compare.REF_KIND,
            status="completed",
            prepared_sha256=prepared["sha256"],
            process=process,
        ),
    )
    worker = _save(
        output / "SIM-reference-result.json",
        dict(
            kind=compare.REF_KIND,
            status="completed",
            INIT_result=parent_result,
            INIT_parent_consumed=True,
            SIM_source_returned=True,
            inherited_hooks_restored=True,
            SIM_observer_coverage_failed=False,
            SIM_finalization_complete=True,
            primary=None,
            capture_errors=[],
            SIM_capture_errors=[],
            SIM_captures=captures,
            SIM_iterations=iterations,
            SIM_closed_lineage=lineage_pin,
            SIM_terminal_observation=terminal_pin,
        ),
    )
    return dict(prepared=prepared, release=release, controller=controller, worker=worker)


def test_sim_compare_terminal_authentication_saved_graph_positive_without_common_start(
    tmp_path, monkeypatch
):
    pins = _terminal_saved(tmp_path, monkeypatch)
    side = compare.reference_side(pins)
    assert side["error"] is None, side["error"]
    assert side["authenticated"] and side["endpoint_complete"] and side["files_bound"]
    assert not side["initial_rng"]["available"] and len(side["rows"]) == 2
    assert (
        side["terminal_observation"]["lineage_identities"]
        == side["lineage_forensics"]["process_local_identities"]
    )


@pytest.mark.parametrize(
    "drift",
    [
        None,
        "project_equal_copy",
        "native_module_relabel",
        "native_package_relabel",
        "main_only",
        "main_equal_copy",
    ],
)
def test_sim_compare_terminal_repair_canonical_runtime_origins(tmp_path, monkeypatch, drift):
    pins = _terminal_saved(tmp_path, monkeypatch)
    output = Path(pins["worker"]["path"]).parent
    runtime_path, binding_path = (
        output / "SIM-reference/runtime.json",
        output / "SIM-reference/source-input-binding.json",
    )
    runtime, binding = json.loads(runtime_path.read_text()), json.loads(binding_path.read_text())
    loaded = runtime["loaded_files"]
    project = "validation.betse.native_sim_reference"
    if drift in ("project_equal_copy", "main_equal_copy"):
        original = loaded[project]
        foreign = tmp_path / "equal-byte-foreign-source.py"
        foreign.write_bytes(Path(original["path"]).read_bytes())
        assert compare.snapshot.digest(foreign) == original["sha256"]
        if drift == "project_equal_copy":
            loaded[project] = dict(path=str(foreign), sha256=original["sha256"])
        else:
            loaded.pop(project)
            loaded["__main__"] = dict(path=str(foreign), sha256=original["sha256"])
    elif drift in ("native_module_relabel", "native_package_relabel"):
        name = "betse.science.sim" if drift == "native_module_relabel" else "betse"
        other = "betse.science.simrunner" if drift == "native_module_relabel" else "betse.science"
        loaded[name] = dict(loaded[other])
        binding["native_producers"][name] = dict(binding["native_producers"][other])
    elif drift == "main_only":
        loaded["__main__"] = loaded.pop(project)
    runtime_path.write_text(json.dumps(runtime))
    binding_path.write_text(json.dumps(binding))
    side = compare.reference_side(pins)
    if drift in (None, "main_only"):
        assert side["authenticated"] and side["endpoint_complete"], side["error"]
    else:
        assert not side["authenticated"] and not side["endpoint_complete"]
        assert side["error"] is not None
    assert len(side["rows"]) == 2 and side["failure"]["primary"] is None


@pytest.mark.parametrize("changed", [False, True])
def test_sim_compare_terminal_authentication_current_input_defaults_are_exact(monkeypatch, changed):
    if changed:
        monkeypatch.setattr(compare.input_files._copy_headless, "__defaults__", ("original",))
        with pytest.raises(ValueError, match="callable/code/default"):
            compare._source_reader(compare.input_files, compare.INPUT_READER_SHA256)
    else:
        assert (
            compare._source_reader(compare.input_files, compare.INPUT_READER_SHA256)
            is compare.input_files
        )


@pytest.mark.parametrize("field", ["authenticated", "endpoint_complete", "error"])
def test_sim_compare_terminal_rejected_authentication_never_promotes_matching_rows(field):
    side = _view(2)
    side["files_bound"] = True
    side["input_provenance"] = compare.complete_input_provenance(
        dict(files={"sim_config.yaml": dict(sha256="a" * 64, size_bytes=1)}, directories=[])
    )
    side["error"] = None
    side[field] = {"type": "retained_terminal_rejection"} if field == "error" else False
    result = compare.compare_terminal_views(side, side)
    assert result["exact_observation_comparison_available"] is False
    assert result["exact_observations_equal"] is None
    assert result["numerical_parity_available"] is False
    if field == "error":
        assert result["errors"]["reference"] is side["error"]


@pytest.mark.parametrize("late_drift", [False, True])
def test_sim_compare_terminal_authentication_paired_reader_forwards_independent_anchor(
    tmp_path, monkeypatch, late_drift
):
    pins = _terminal_saved(tmp_path, monkeypatch)
    accepted = "a" * 64
    calls = []

    def issued_metadata(request, *, accepted_observer_sha256=None):
        # This isolated adapter control reuses saved inert observations. It is
        # not a second numerical implementation or an issued owner witness.
        calls.append((request, accepted_observer_sha256))
        side = compare.reference_side(pins)
        assert side["authenticated"], side["error"]
        if late_drift:
            (tmp_path / "inputs/late.yaml").write_text("retained added path")
        return side

    monkeypatch.setattr(compare, "issued_side", issued_metadata)
    result = compare.compare_terminal_saved(
        pins, {"inert_adapter_fixture": True}, accepted_observer_sha256=accepted
    )
    assert calls == [({"inert_adapter_fixture": True}, accepted)]
    assert result["common_starting_authority_established"] is False
    assert result["numerical_parity_available"] is False
    assert result["exact_observation_comparison_available"] is (not late_drift)
    assert result["exact_observations_equal"] is (True if not late_drift else None)


@pytest.mark.parametrize("retarget", [False, True])
def test_sim_compare_terminal_executable_alias_retains_actual_runtime_target(
    tmp_path, monkeypatch, retarget
):
    pins = _terminal_saved(tmp_path, monkeypatch)
    alias = tmp_path / "venv-python"
    alias.symlink_to(tmp_path / "python")
    path = tmp_path / "process/process-inputs.json"
    command = json.loads(path.read_text())
    command["command"][0] = str(alias)
    path.write_text(json.dumps(command))
    side = compare.reference_side(pins)
    assert side["authenticated"], side["error"]

    def issued_metadata(*args, **kwargs):
        if retarget:
            other = tmp_path / "equal-bytes-foreign-python"
            other.write_bytes((tmp_path / "python").read_bytes())
            alias.unlink()
            alias.symlink_to(other)
        return side

    monkeypatch.setattr(compare, "issued_side", issued_metadata)
    result = compare.compare_terminal_saved(pins, {})
    assert result["exact_observation_comparison_available"] is (not retarget)
    if retarget:
        assert result["status"] == "evidence_changed_during_comparison"
    assert result["numerical_parity_available"] is False


@pytest.mark.parametrize(
    "defect",
    [
        "review",
        "release",
        "INIT",
        "hooks",
        "context",
        "loop",
        "calendar",
        "source_order",
        "lineage",
        "frame_alias",
        "runtime",
        "command",
        "process",
        "input_copy",
        "writer",
    ],
)
def test_sim_compare_terminal_authentication_refuses_resealed_semantic_drift(
    tmp_path, monkeypatch, defect
):
    pins = _terminal_saved(tmp_path, monkeypatch)
    worker = json.loads(Path(pins["worker"]["path"]).read_text())
    output = Path(pins["worker"]["path"]).parent
    if defect in ("context", "loop", "calendar", "source_order", "lineage", "frame_alias"):
        pin = worker["SIM_terminal_observation"]
        raw, parts = compare.codec._capture(compare.report.Reader(), pin)
        value = compare._data(compare.codec.wire(raw, parts))
        if defect == "context":
            value["normal_context_return"] = False
        elif defect == "loop":
            value["normal_full_loop_return"] = False
        elif defect == "calendar":
            value["configured_iterations"] = 3
        elif defect == "source_order":
            value["events"][1], value["events"][2] = value["events"][2], value["events"][1]
        elif defect == "lineage":
            value["lineage_identities"]["current_parameters"] = 999
        else:
            value["actual_frame_identities"]["loop"] = value["actual_frame_identities"]["core"]
        new = compare.codec.evidence.write(
            output / "SIM-reference/captures/changed-terminal.json",
            dict(tree=_metadata_wire(value), columns={}),
            label="SIM.terminal",
        )
        next(r for r in worker["SIM_captures"] if r["label"] == "SIM.terminal")["files"] = new
        worker["SIM_terminal_observation"] = new[0]
    elif defect == "INIT":
        worker["INIT_parent_consumed"] = False
    elif defect == "hooks":
        worker["inherited_hooks_restored"] = False
    elif defect in ("review", "release"):
        value = json.loads(Path(pins["release"]["path"]).read_text())
        if defect == "review":
            value["reviews"]["source"]["sha256"] = "0" * 64
        else:
            value["enabled"] = False
        _replace(pins["release"], value)
    else:
        target = {
            "runtime": output / "SIM-reference/runtime.json",
            "command": tmp_path / "process/process-inputs.json",
            "process": tmp_path / "process/result.json",
            "input_copy": output / "execution-inputs.json",
            "writer": output / "SIM-reference/filesystem.json",
        }[defect]
        value = json.loads(target.read_text())
        if defect == "runtime":
            value["loaded_files"].pop("betse.science.sim")
        elif defect == "command":
            value["command"][3] = "unrelated.module"
        elif defect == "process":
            value["returncode"] = 1
        elif defect == "input_copy":
            value["files"][0]["sha256"] = "0" * 64
        else:
            value["write_policy"]["first_error"] = {"retained_failure": True}
        target.write_text(json.dumps(value))
    _replace(pins["worker"], worker)
    side = compare.reference_side(pins)
    assert side["error"] is not None and not side["authenticated"] and not side["endpoint_complete"]
    assert len(side["rows"]) == 2 and side["failure"]["primary"] is None
