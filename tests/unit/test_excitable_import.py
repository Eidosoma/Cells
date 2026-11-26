"""Track E's conduction-assay importer (validation/tissue/excitable_import.py; D153 rule (b), D170).

A synthetic checkpoint of a small held-bath chain of cells.model.resolved_pump_tissue@3 (the probe's own
definition, no engine execution): amounts and charges are carried with the source's fixed
background; gates are carried and the junction gates pinned open, each junction's effective
availability frozen; the floor refuses a junction below s * r_gj = 20, closed ones included;
water and composites are refused; the booking is the trapezoid; the record names the source's
digest and claims no continuity; the assay definition parses.
"""

import copy
import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from validation.tissue import excitable_import as imp
from validation.tissue import excitable_probe as probe


def chain(n=4, s=500.0, gated=True):
    probe.set_point(1e-6, 1e-8, 0.01)
    raw = probe.definition(n, dt=1e-3, end_time=1.0, kv_m_s=3e-7, s=s, gated=gated)
    raw["model"].pop("junction_heat_booking", None)
    return raw


def write_checkpoint(folder, raw, *, time_s=0.6, scale_gate=0.9, increment=1e-3):
    m = raw["model"]
    species = [s["id"] for s in m["species"]]
    ne, nx = len(m["junctions"]), len(m["extracellular"])
    ref = np.asarray([[c["initial_amount_fmol"][s] for c in m["cells"]] for s in species])
    xref = np.asarray([[c["initial_amount_fmol"][s] for c in m["extracellular"]] for s in species])
    inc = np.full_like(ref, increment)
    nc = len(m["channels"])
    state = dict(
        amount_reference=ref,
        amount_increment=inc,
        extracellular_amount_reference=xref,
        extracellular_amount_increment=np.zeros_like(xref),
        channel_gate=np.full((2, nc), 0.25),
        junction_gate=np.full(ne, scale_gate),
        volume=np.asarray([c["volume_pL"] for c in m["cells"]]),
        valence=np.asarray([[s["valence"]] for s in m["species"]], dtype=float),
    )
    world = folder / "world-1"
    world.mkdir(parents=True)
    np.savez(world / "state.npz", **state)
    manifest = dict(
        kind=imp.CHECKPOINT_KIND,
        spec=raw,
        clock=dict(time=time_s, step_index=600, event_index=0),
        manifest_sha256="source-recorded-digest",
        spec_sha256="spec-digest",
        state_sha256="state-digest",
        runtime=dict(cells_version="test"),
    )
    (world / "manifest.json").write_text(json.dumps(manifest))
    assert nx == len(m["extracellular"])
    return world, state


def test_amounts_charges_gates_and_effective_availability(tmp_path):
    raw = chain()
    world, state = write_checkpoint(tmp_path, raw)
    assay, record = imp.assay_definition(world, dt=5e-6, end_time=0.05)
    m = assay["model"]
    species = [s["id"] for s in m["species"]]
    valence = [s["valence"] for s in m["species"]]
    for i, cell in enumerate(m["cells"]):
        a = state["amount_reference"][:, i] + state["amount_increment"][:, i]
        assert [cell["initial_amount_fmol"][s] for s in species] == pytest.approx(a, rel=1e-15)
        q = CHARGE_PER_FMOL * (sum(v * x for v, x in zip(valence, a, strict=True))
                               + cell["fixed_charge_equivalent_fmol"])  # fmt: skip
        assert cell["initial_charge_C"] == pytest.approx(q, rel=1e-12)
    for c in m["channels"]:
        assert all(g == 0.25 for g in c["initial_gate"])
    for j, row in zip(m["junctions"], assay["experiment"]["junction_controls"], strict=True):
        assert j["gate"]["minimum_open_fraction"] == 1.0 and j["gate"]["initial_gate"] == 1.0
        assert row["schedule"] == [dict(time=0.0, availability=pytest.approx(0.9))]
    carried = record["junction_carriage"][0]
    assert carried["gate"] == 0.9 and carried["effective_availability"] == pytest.approx(0.9)
    assert carried["s_times_r_gj"] == pytest.approx(500.0 * 0.9, rel=1e-9)
    assert m["junction_heat_booking"] == imp.TRAPEZOID
    assert record["source"]["manifest_sha256"] == "source-recorded-digest"
    assert len(record["source"]["manifest_file_sha256"]) == 64
    assert "claims no continuity" in record["rule"]
    assert record["assay"]["free_field_offsets"] == 0
    parse_spec(assay)  # a valid @3 definition


def test_the_floor_refuses_weak_and_closed_junctions(tmp_path):
    raw = chain(s=500.0)
    raw["experiment"]["junction_controls"][1]["schedule"] = [
        dict(time=0.0, availability=1.0),
        dict(time=0.5, availability=0.03),  # 500 x 0.03 x 0.9 = 13.5 at the import time
    ]
    world, _ = write_checkpoint(tmp_path / "weak", raw)
    with pytest.raises(imp.ImportRefused, match="below the floor"):
        imp.assay_definition(world, dt=5e-6, end_time=0.05)
    closed = chain(s=500.0)
    closed["experiment"]["junction_controls"][0]["schedule"] = [dict(time=0.0, availability=0.0)]
    world, _ = write_checkpoint(tmp_path / "closed", closed)
    with pytest.raises(imp.ImportRefused, match="below the floor"):
        imp.assay_definition(world, dt=5e-6, end_time=0.05)


def test_water_and_composites_are_refused(tmp_path):
    raw = chain()
    world, state = write_checkpoint(tmp_path / "water", raw)
    changed = dict(np.load(world / "state.npz"))
    changed["volume"] = changed["volume"] * 1.01
    np.savez(world / "state.npz", **changed)
    with pytest.raises(imp.ImportRefused, match="water"):
        imp.assay_definition(world, dt=5e-6, end_time=0.05)
    composite = copy.deepcopy(raw)
    composite["model"]["id"] = "cells.model.resolved_pump_composite@1"
    world, _ = write_checkpoint(tmp_path / "composite", composite)
    with pytest.raises(imp.ImportRefused, match="composite"):
        imp.assay_definition(world, dt=5e-6, end_time=0.05)


def test_the_stimulus_and_the_trapezoid_rule(tmp_path):
    raw = chain()
    world, _ = write_checkpoint(tmp_path, raw)
    assay, _ = imp.assay_definition(
        world, dt=5e-6, end_time=0.05, stimulus=dict(cells=[0], window=(0.002, 0.003), m_s=2e-7)
    )
    ids = [c["id"] for c in assay["model"]["channels"]]
    assert "stimk_0" in ids and "stimna_0" in ids
    assert assay["execution"]["channel_capacity"] == len(ids)
    parse_spec(assay)
    with pytest.raises(imp.ImportRefused, match="unstimulated"):
        imp.rest_check(assay, execute=lambda raw: None)
    tableau = copy.deepcopy(assay)
    tableau["model"]["junction_heat_booking"] = "explicit_tableau"
    with pytest.raises(imp.ImportRefused, match="trapezoid"):
        imp.require_trapezoid(tableau)


def test_rest_check_reads_drift(tmp_path):
    raw = chain()
    world, _ = write_checkpoint(tmp_path, raw)
    assay, _ = imp.assay_definition(world, dt=5e-6, end_time=0.01)
    t = np.linspace(0.0, 0.01, 11)
    flat = dict(times=t, vm=np.full((11, 4), -0.0796), refusal=None)
    assert imp.rest_check(assay, execute=lambda raw: flat)["passes"]
    fired = dict(times=t, vm=np.full((11, 4), -0.0796), refusal=None)
    fired["vm"][5:, 2] = 0.03
    out = imp.rest_check(assay, execute=lambda raw: fired)
    assert not out["passes"] and out["outside"] == [2]
