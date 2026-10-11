"""Fast corruption and physical-ledger checks; never load a simulator."""

import copy
import importlib
import json
import struct
import zipfile

import artifacts as art
import family_audit as review
import pytest


def npy(shape, numbers, dtype="<f8", fortran=False):
    header = repr(dict(descr=dtype, shape=shape, fortran_order=fortran)).encode() + b"\n"
    code = "d" if dtype == "<f8" else "B"
    return (
        b"\x93NUMPY\x01\x00"
        + struct.pack("<H", len(header))
        + header
        + struct.pack("<" + code * len(numbers), *numbers)
    )


@pytest.fixture(scope="module")
def saved():
    for path in (review.CAPTURE / "family-artifacts").glob("*/comparison.json"):
        if not path.parent.is_symlink() and art.read(path)["case"] == "two_cells_shared_bath":
            arrays = art.decode_npz(path.parent / "run/trajectory.npz")
            definition = art.read(path.parent / "run/resolved_config.json")
            return definition, arrays
    raise AssertionError("Missing shared-bath artifact")


@pytest.mark.parametrize(
    "fortran,numbers", [(False, [1, 2, 3, 4, 5, 6]), (True, [1, 4, 2, 5, 3, 6])]
)
def test_two_array_orders(fortran, numbers):
    assert art.decode_npy(npy((2, 3), numbers, fortran=fortran))["values"] == [[1, 2, 3], [4, 5, 6]]


def test_scalar_and_empty():
    assert art.decode_npy(npy((), [3]))["values"] == 3
    assert art.decode_npy(npy((2, 0), []))["values"] == [[], []]


@pytest.mark.parametrize(
    "bad",
    [
        npy((1,), [float("nan")]),
        npy((1,), [float("inf")]),
        npy((1,), [2], dtype="|b1"),
        npy((2,), [1]),
        npy((1_000_001,), []),
        b"not an array",
    ],
)
def test_corrupt_arrays_rejected(bad):
    with pytest.raises(ValueError):
        art.decode_npy(bad)


@pytest.mark.parametrize("content", ['{"a":1,"a":2}', '{"a":NaN}'])
def test_json_rejects_ambiguous_or_nonfinite(tmp_path, content):
    path = tmp_path / "bad.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        art.read(path)


def test_archive_paths_rejected(tmp_path):
    path = tmp_path / "bad.npz"
    with zipfile.ZipFile(path, "x") as archive:
        archive.writestr("../state.npy", npy((1,), [1]))
    with pytest.raises(ValueError, match="membership"):
        art.decode_npz(path)


def test_capture_authentication():
    r, production = review.authenticated()
    assert len(r["sources_sha256"]) == 601
    assert len(production) == 55


def test_model_imports_blocked_and_fence_restored():
    with review.fence(), pytest.raises(ImportError, match="Forbidden"):
        importlib.import_module("cells")


def test_saved_geometry_and_physics(saved):
    definition, arrays = saved
    review.check_layout(arrays, definition)
    state = review.state_at(arrays, -1)
    review.validate_state(state, 2)
    p = review.physics(definition, state)
    assert p["energy_pJ"] < 2e-8 and p["global_material_fmol"] < 2e-11
    assert p["countercharge_C"] < 1e-20 and p["min_concentration_mM"] > 0


@pytest.mark.parametrize(
    "name,index,new",
    [
        ("owners", 0, 1),
        ("pump_sodium_species", 0, 2),
        ("pump_atp_mM", 0, 2.0),
    ],
)
def test_wrong_layout_rejected(saved, name, index, new):
    definition, arrays = saved
    changed = copy.deepcopy(arrays)
    changed[name]["values"][index] = new
    with pytest.raises(ValueError, match="layout differs"):
        review.check_layout(changed, definition)


def test_bad_padding_rejected(saved):
    _, arrays = saved
    state = review.state_at(copy.deepcopy(arrays), -1)
    state["amount_increment"][0][2] = 1.0
    with pytest.raises(ValueError, match="padding"):
        review.validate_state(state, 2)


def test_false_transfer_breaks_material(saved):
    definition, arrays = saved
    state = review.state_at(copy.deepcopy(arrays), -1)
    state["leak_transferred"][0][0] += 0.1
    assert review.physics(definition, state)["local_material_fmol"] > 0.09


def test_false_work_breaks_energy(saved):
    definition, arrays = saved
    state = review.state_at(copy.deepcopy(arrays), -1)
    state["dissipated_energy_pJ"][0] += 0.1
    assert review.physics(definition, state)["energy_pJ"] > 0.09


def test_depleted_inventory_rejected(saved):
    definition, arrays = saved
    state = review.state_at(copy.deepcopy(arrays), -1)
    state["amount_increment"][0][0] = -10000.0
    with pytest.raises(ValueError, match="depleted"):
        review.physics(definition, state)


def test_identity_changes_detectable(saved):
    definition, _ = saved
    changed = json.loads(json.dumps(definition))
    changed["model"]["cells"][0]["membrane"]["pump"]["metabolism"]["atp_mM"] *= 2
    assert art.digest(changed) != art.digest(definition)


def test_numeric_mismatch_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        art.near([1.0], [1.1])
