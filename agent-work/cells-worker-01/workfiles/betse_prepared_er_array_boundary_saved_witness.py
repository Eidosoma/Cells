"""Authenticate saved JSON/NPZ types and bits using only the standard library."""

import ast
import copy
import hashlib
import json
import struct
import zipfile
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
BASE = Path(
    "/mnt/workspaces/Cells/betse-prepared-er-tests-20261030-01/run-context/evidence/prepared-er-join"
)
FIELDS = (
    "cc_er",
    "er_vol",
    "er_sa",
    "Ver",
    "Q",
    "cm_er",
    "Dm_er",
    "Dm_er_base",
    "Dm_channels",
    "zer",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archive(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["complete"] and set(manifest["files"]) == {"data.json", "arrays.npz"}
    for name, digest in manifest["files"].items():
        assert sha(directory / name) == digest, (directory, name)

    def decode(node):
        if not isinstance(node, dict):
            return node
        if "array" in node:
            return dict(
                array=node["array"],
                dtype=node["dtype"],
                shape=node["shape"],
                archive=str(directory),
            )
        if "mapping" in node:
            return {key: decode(value) for key, value in node["mapping"]}
        if "sequence" in node:
            return [decode(value) for value in node["sequence"]]
        if "float64_bits" in node:
            return struct.unpack("<d", bytes.fromhex(node["float64_bits"]))[0]
        raise ValueError("Unknown saved archive node")

    return decode(json.loads((directory / "data.json").read_text()))


def array_bytes(node):
    with zipfile.ZipFile(Path(node["archive"]) / "arrays.npz") as stream:
        raw = stream.read(node["array"] + ".npy")
    assert raw[:6] == b"\x93NUMPY"
    version = tuple(raw[6:8])
    size = 2 if version == (1, 0) else 4
    length = struct.unpack("<H" if size == 2 else "<I", raw[8 : 8 + size])[0]
    header = ast.literal_eval(raw[8 + size : 8 + size + length].decode("latin1").strip())
    assert header["descr"] == node["dtype"] == "<f8" and not header["fortran_order"]
    assert list(header["shape"]) == node["shape"]
    data = raw[8 + size + length :]
    total = 1
    for value in node["shape"]:
        total *= value
    assert len(data) == 8 * total
    return data


def shape(node):
    if isinstance(node, dict) and "array" in node:
        return node["shape"]
    if not isinstance(node, list):
        return []
    assert node
    child = shape(node[0])
    assert all(shape(value) == child for value in node)
    return [len(node), *child]


def payload(node):
    if isinstance(node, dict) and "array" in node:
        return array_bytes(node)
    if isinstance(node, list):
        return b"".join(payload(value) for value in node)
    return struct.pack("<d", float(node))


artifacts, rows = {}, []
inputs = sorted(BASE.glob("isolated-*/inputs.json"))
assert len(inputs) == 6
for path in inputs:
    case = path.parent.name.removeprefix("isolated-")
    raw = json.loads(path.read_text())
    fields = raw["prepared_er_input"]["fields"]
    producer = BASE / (case + "-prepared-return")
    native = path.parent / "native"
    produced = archive(producer)["packet"]["endoretic_state"]["fields"]
    captured = archive(native)["history"][0]["material"]
    trace = captured["channel_capture"]["endoretic"]
    assert captured["failure"]["type"] == "TypeError"
    initial = trace["initial_state"]
    n = len(raw["ion_definition"]["geometry"]["cell_ids"])
    count = len(raw["ion_definition"]["ions"]["ids"])
    witness = {}
    for name in FIELDS:
        expected = (
            []
            if name == "cm_er"
            else [count, n]
            if name in ("cc_er", "Dm_er", "Dm_er_base", "Dm_channels", "zer")
            else [n]
        )
        assert shape(fields[name]) == shape(produced[name]) == shape(initial[name]) == expected
        data = payload(fields[name])
        assert data == payload(produced[name]) == payload(initial[name]), (case, name)
        if name != "cm_er":
            assert isinstance(produced[name], dict) and produced[name]["dtype"] == "<f8"
            assert (
                isinstance(initial[name], dict)
                if name == "cc_er"
                else isinstance(initial[name], list)
            )
        witness[name] = dict(
            shape=expected,
            producer_type="float64 ndarray" if name != "cm_er" else "float64 scalar",
            JSON_type=type(fields[name]).__name__,
            failed_native_initial_type="float64 ndarray"
            if isinstance(initial[name], dict)
            else type(initial[name]).__name__,
            payload_sha256=hashlib.sha256(data).hexdigest(),
            payload_bits_preserved=True,
            planned_restored_type="float64 ndarray" if name != "cm_er" else "float64 scalar",
        )
    after_channels = next(frame for frame in trace["frames"] if frame["stage"] == "channels")[
        "fields"
    ]
    assert shape(after_channels["Dm_er"]) == [2 * count, n]
    rows.append(
        dict(
            case=case,
            fields=witness,
            observed_failure_type=captured["failure"]["type"],
            observed_Ver_type="list",
            observed_after_channels_Dm_er_shape=[2 * count, n],
            expected_Dm_er_shape=[count, n],
            classification=(
                "Boundary list restoration error; no observed ER physical instability diagnosis"
            ),
        )
    )
    artifacts[str(path)] = sha(path)
    for folder in (producer, native):
        for name in ("manifest.json", "data.json", "arrays.npz"):
            artifacts[str(folder / name)] = sha(folder / name)
old = ROOT / "validation/betse/betse_prepared_er_join_native.py"
frozen = Path(
    "/mnt/workspaces/Cells/betse-prepared-er-prepared-20261030-01/source/validation/betse/betse_prepared_er_join_native.py"
)


def functions(path):
    return {
        node.name: node
        for node in ast.parse(path.read_text()).body
        if isinstance(node, ast.FunctionDef)
    }


a, b = functions(frozen), functions(old)
assert set(b) == set(a) | {"restore_supplied_fields"}
changed = []
for name, node in a.items():
    replacement = copy.deepcopy(b[name])
    if name == "_whole_join":
        for item in ast.walk(replacement):
            if (
                isinstance(item, ast.Assign)
                and ast.unparse(item.targets[0]) == "er_state_cache"
                and ast.unparse(item.value)
                == "restore_supplied_fields(inputs['prepared_er_input']['fields'])"
            ):
                item.value = (
                    ast.parse("copy.deepcopy(inputs['prepared_er_input']['fields'])").body[0].value
                )
                changed.append(name)
    if name == "_er_only":
        for item in ast.walk(replacement):
            if isinstance(item, ast.Call) and ast.unparse(item.func) == "er_native.setup":
                assert (
                    ast.unparse(item.args[-1])
                    == "restore_supplied_fields(before['er_state']['fields'])"
                )
                item.args[-1] = ast.parse("before['er_state']['fields']").body[0].value
                changed.append(name)
    assert ast.dump(node, include_attributes=False) == ast.dump(
        replacement, include_attributes=False
    ), name
assert sorted(changed) == ["_er_only", "_whole_join"]
result = dict(
    kind="cells.prepared_ER_array_boundary_saved_witness@1",
    scope=(
        "Read existing saved artifacts only; "
        "no scientific import or new decoder/native/model/reference execution"
    ),
    cases=rows,
    artifact_sha256=artifacts,
    old_native_sha256=sha(frozen),
    new_native_sha256=sha(old),
    nine_arrays_and_one_scalar=True,
    all_JSON_numbers_equal_producer_and_failed_initial_payloads=True,
    inverse_AST_only_two_boundary_calls_changed=True,
    all_other_existing_native_functions_AST_unchanged=True,
    added_function="restore_supplied_fields",
    equations_helpers_fixtures_tolerances_changed=False,
    old_failed_run_preserved=True,
    numerical_runs=0,
    scientific_imports=0,
    pytest_collection_runs=0,
    automatic_retry=False,
)
output = WORK / "betse_prepared_er_array_boundary_saved_witness_01.json"
with output.open("x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
print(
    json.dumps(
        dict(
            witness=str(output),
            sha256=sha(output),
            cases=6,
            fields=60,
            artifact_files=len(artifacts),
            numeric_execution=0,
        )
    )
)
