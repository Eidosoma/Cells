"""Independent-review corruption tests; no simulator imports or integration."""

import copy
import importlib
import struct

import evidence as e
import pytest
import review


@pytest.fixture(scope="module")
def captured():
    return e.read(e.CAPTURE / "registration.json")["protocol"], e.read(e.CAPTURE / "betse.json")[
        "rows"
    ]


def test_authenticated_capture():
    assert len(e.authenticate()["sources_sha256"]) == 613


@pytest.mark.parametrize("index", range(6))
def test_each_native_variant(captured, index):
    p, rows = captured
    variant = p["variants"][index]
    ledger = e.Ledger()
    result = review.review_row(p, variant, rows[variant["id"] + "/observed"], ledger)
    assert result["observed_steps"] == 8 and ledger.count > 1000


@pytest.mark.parametrize(
    "kind",
    [
        "pump_flux",
        "passive_flux",
        "label",
        "density",
        "chronology",
        "chemistry",
        "mask",
        "history",
        "voltage",
        "geometry",
        "fixture",
        "species",
    ],
)
def test_corrupt_native_records_fail(captured, kind):
    p, rows = captured
    variant = p["variants"][0]
    row = copy.deepcopy(rows["pump_leak/observed"])
    raw = row["trace"]["raw_steps"][0]
    step = row["trace"]["steps"][0]
    if kind == "pump_flux":
        raw["calls"][0]["returned"][0][0] *= 2
    elif kind == "passive_flux":
        raw["calls"][1]["returned"][0] *= 2
    elif kind == "label":
        step["before_ordinary"]["reported_NaK_rate"][0] /= 3
    elif kind == "density":
        step["before_ordinary"]["physical"]["ordinary_density_mol_per_m2_s"][0][0] *= 2
    elif kind == "chronology":
        step["after_elapsed_s"] = step["raw_label_s"]
    elif kind == "chemistry":
        step["after_voltage"]["physical"]["inside_mM"][0][0] += 1.0
    elif kind == "mask":
        variant = copy.deepcopy(p["variants"][-1])
        row = copy.deepcopy(rows["closed_boundary/observed"])
        row["geometry"]["boundary_faces"] = []
    elif kind == "history":
        row["histories"]["vm_time"]["values"][0][0] = 1.0
    elif kind == "voltage":
        raw["calls"][0]["inputs"]["Vm"][0] = 0.01
    elif kind == "geometry":
        row["geometry"]["effective_bath_volume_m3"] /= 30
    elif kind == "fixture":
        row["fixture"]["after"]["physical"]["inside_mM"][0][0] += 1.0
    else:
        row["metadata"]["valence"][0] = -1
    with pytest.raises(ValueError):
        review.review_row(p, variant, row, e.Ledger())


@pytest.mark.parametrize("payload", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'])
def test_strict_json(tmp_path, payload):
    path = tmp_path / "bad.json"
    path.write_text(payload)
    with pytest.raises(ValueError):
        e.read(path)


def test_array_bit_identity_distinguishes_negative_zero():
    import hashlib

    r = dict(
        dtype="<f8",
        shape=[1],
        values=[-0.0],
        bytes_sha256=hashlib.sha256(struct.pack("<d", -0.0)).hexdigest(),
    )
    assert e.array(r) == [-0.0]
    r["values"] = [0.0]
    with pytest.raises(ValueError, match="checksum"):
        e.array(r)


def test_import_fence_restores():
    with e.model_fence(), pytest.raises(ImportError, match="Forbidden"):
        importlib.import_module("pump_check")


def test_comparison_rejects_nonfinite():
    with pytest.raises(ValueError):
        e.Ledger().compare("bad", float("nan"), 0.0, 1e-8)


def test_zero_voltage_diffusive_limit():
    p = dict(
        T=298.15, rho=1.0, cA=[145.0], cB=[12.0], Dc=[7.5e-18], d=[7.5e-9], zc=[1.0], vBA=[0.0]
    )
    assert abs(review.passive_density(p)[0] - 1.33e-7) < 1e-22
