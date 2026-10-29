"""Independent active owner/gate remap, full histories and transient continuation."""

import json
import os
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import active_excision_fixtures as fixtures
from validation.tissue import active_excision_reference as ref


def evidence(name, value, arrays=None):
    if folder := os.environ.get("CELLS_REFERENCE_EVIDENCE"):
        root = Path(folder)
        root.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)
        (root / (name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
        )


def integrate(raw, **kwargs):
    try:
        return ref.integrate(raw, **kwargs)
    except ref.ReferenceIntegrationError as error:
        evidence(
            "failed-integration",
            dict(
                definition=raw,
                arguments=kwargs,
                exception=str(error),
                failed_trial=error.diagnostics,
            ),
        )
        raise


@lru_cache(maxsize=None)
def prefix(refinement=1):
    return integrate(fixtures.definition(), end_time=fixtures.CUT_TIME, refinement=refinement)


def serialized(cut):
    raw = deepcopy(cut["raw"])
    raw["model"] = dict(
        id=ref.MODEL_ID, tissue=raw["model"], excision=dict(source=deepcopy(cut["archive"]))
    )
    return raw


def compare(c, a, b, *, rtol=2e-8, atol=3e-11):
    for name, values in ref.unpack(c, a).items():
        np.testing.assert_allclose(
            values, ref.unpack(c, b)[name], rtol=rtol, atol=3e-25 if name.endswith("_C") else atol
        )


def energy_balance(c, before, after, start, end):
    a, b = ref.unpack(c, before), ref.unpack(c, after)
    heat = sum(np.sum(b[k] - a[k]) for k in c["shapes"] if k.endswith("dissipated_energy_pJ"))
    work = sum(
        np.sum(b[k] - a[k]) for k in ("reservoir_work_pJ", "electrode_work_pJ", "metabolic_work_pJ")
    )
    return (
        ref.snapshot(c, after, end)["stored_energy_pJ"]
        - ref.snapshot(c, before, start)["stored_energy_pJ"]
        + heat
        - work
    )


def local_material(c, state):
    d, m = ref.unpack(c, state), c["raw"]["model"]
    inside, outside = d["amount_increment"].copy(), d["extracellular_amount_increment"].copy()
    cids, oids = [v["id"] for v in m["cells"]], [v["id"] for v in m["extracellular"]]
    species = [v["id"] for v in m["species"]]
    mids = {p["id"]: j for j, p in enumerate(m["membranes"])}
    for j, p in enumerate(m["membranes"]):
        amount = d["membrane_transferred"][:, j].copy()
        for k, channel in enumerate(m["channels"]):
            if mids[channel["membrane_id"]] == j:
                amount += d["channel_transferred"][:, k]
        if p["pump"] is not None:
            amount[species.index(p["pump"]["roles"]["sodium"])] += 3 * d["pump_cycles"][j]
            amount[species.index(p["pump"]["roles"]["potassium"])] -= 2 * d["pump_cycles"][j]
        inside[:, cids.index(p["inside"])] += amount
        outside[:, oids.index(p["outside"])] -= amount
    for family, target, ids in (("junction", inside, cids), ("face", outside, oids)):
        for j, p in enumerate(m[family + "s"]):
            target[:, ids.index(p["sender"])] += d[family + "_transferred"][:, j]
            target[:, ids.index(p["receiver"])] -= d[family + "_transferred"][:, j]
    outside -= d["reservoir_supplied"]
    return max(np.max(abs(inside), initial=0), np.max(abs(outside), initial=0))


@pytest.mark.parametrize("catalog", ["compact", "full"])
@pytest.mark.parametrize("arm", ["open", "clamped", "blocked", "reordered", "empty"])
def test_complete_initial_stage_and_energy_identity(catalog, arm):
    raw = fixtures.definition(arm, catalog=catalog, padded=True)
    c = ref.bind(raw)
    y = ref.initial(c)
    slope, phi, proof = ref.evaluate(c, y, 0.0)
    d = ref.unpack(c, slope)
    assert len(d) == 19 and np.isfinite(slope).all()
    if catalog == "full" and arm != "empty":
        assert len({p["kinetic_law"] for p in raw["model"]["channels"]}) == 56
    vi, vo = c["vi"], c["vo"]
    chemical = (
        0.001
        * ref.R
        * c["layout"]["temperature"]
        * (
            np.sum(np.log(c["ai"] / vi) * d["amount_increment"])
            + np.sum(np.log(c["ao"] / vo) * d["extracellular_amount_increment"])
        )
    )
    z = np.asarray(c["layout"]["valence"])
    qdot = (
        ref.F
        * 1e-15
        * np.sum(z * np.c_[d["amount_increment"], d["extracellular_amount_increment"]], axis=0)
    )
    qdot[len(vi) :] += d["electrode_charge_transferred_C"]
    capacitor = 1e12 * np.dot(phi, qdot)
    heat = sum(np.sum(v) for k, v in d.items() if k.endswith("dissipated_energy_pJ"))
    work = sum(
        np.sum(d[k]) for k in ("reservoir_work_pJ", "electrode_work_pJ", "metabolic_work_pJ")
    )
    assert abs(chemical + capacitor + heat - work) < 3e-10
    assert proof["max_charge_residual_C"] < 3e-25
    assert local_material(c, slope) < 3e-13
    if arm == "blocked":
        for key, value in d.items():
            if key not in ref.GATES:
                np.testing.assert_array_equal(value, 0)
        assert np.any(d["channel_gate"] != 0) and np.any(d["junction_gate"] != 0)
    evidence(
        f"stage-{catalog}-{arm}",
        dict(
            status="passed",
            definition=raw,
            complete_fields=19,
            energy_rate_residual_pJ_s=float(chemical + capacitor + heat - work),
            scope="Instantaneous independent stage; not gate relaxation or native whole tissue",
        ),
    )


@pytest.mark.parametrize("removed", ["cell_0", "cell_1", "cell_2"])
@pytest.mark.parametrize("reordered", [False, True])
def test_all_56_laws_follow_owners_and_zero_one_two_state_memory(removed, reordered):
    raw = fixtures.definition("reordered" if reordered else "open", catalog="full")
    c = ref.bind(raw)
    values = ref.unpack(c, ref.initial(c))
    for j, p in enumerate(raw["model"]["channels"]):
        count = len(p["initial_gate"])
        values["channel_gate"][:count, j] = [0.42, 0.61][:count]
    values["junction_gate"][:] = [0.37, 0.58, 0.83]
    state = ref.flatten(c, values)
    cut = ref.excise(raw, state, [removed], fixtures.CUT_TIME)
    after = cut["raw"]["model"]
    now = ref.unpack(cut["context"], cut["state"])
    old = {p["id"]: j for j, p in enumerate(raw["model"]["channels"])}
    counts = set()
    for j, p in enumerate(after["channels"]):
        count = len(p["initial_gate"])
        counts.add(count)
        np.testing.assert_array_equal(
            now["channel_gate"][:, j], values["channel_gate"][:, old[p["id"]]]
        )
        np.testing.assert_array_equal(
            p["initial_gate"], values["channel_gate"][:count, old[p["id"]]]
        )
    assert counts == {0, 1, 2}
    assert len(after["junctions"]) == 1
    junction = after["junctions"][0]
    oldj = next(j for j, p in enumerate(raw["model"]["junctions"]) if p["id"] == junction["id"])
    assert now["junction_gate"][0] == values["junction_gate"][oldj]
    assert sum(key not in ref.GATES for key in now) == 17
    for key, v in now.items():
        if key not in ref.GATES:
            np.testing.assert_array_equal(v, 0)
    assert len(after["membranes"]) == 4
    assert len(cut["audit"]["removed_pump_ids"]) == 2
    assert set(cut["archive"]["checkpoint"]["state"]) == set(c["shapes"])
    assert after["faces"] == raw["model"]["faces"]
    assert after["extracellular"] == raw["model"]["extracellular"]
    ref.evaluate(cut["context"], cut["state"], fixtures.CUT_TIME)


def test_actual_evolved_prefix_gates_and_all_source_histories_are_preserved():
    raw = fixtures.definition(padded=True)
    c = ref.bind(raw)
    source = prefix()["state"][-1]
    values = ref.unpack(c, source)
    assert (
        np.max(abs(values["channel_gate"] - ref.unpack(c, ref.initial(c))["channel_gate"])) > 1e-5
    )
    assert (
        np.max(abs(values["junction_gate"] - ref.unpack(c, ref.initial(c))["junction_gate"])) > 1e-7
    )
    assert np.any(values["channel_transferred"]) and np.any(values["pump_cycles"])
    assert np.any(values["metabolic_work_pJ"])
    padded = {key: np.pad(v, [(0, 1)] * v.ndim) for key, v in values.items()}
    layout = {key: np.asarray(value) for key, value in c["layout"].items()}
    cut = ref.excise(
        raw,
        padded,
        ["cell_1"],
        fixtures.CUT_TIME,
        step_index=44,
        event_index=4,
        source_layout=layout,
    )
    for key, value in padded.items():
        np.testing.assert_array_equal(cut["archive"]["checkpoint"]["state"][key], value)
    for key, value in layout.items():
        np.testing.assert_array_equal(cut["archive"]["checkpoint"]["layout"][key], value)
    assert cut["archive"]["checkpoint"]["step_index"] == 44
    assert not cut["audit"]["gate_energy_store"] and not cut["audit"]["finite_atp_store"]
    for key, value in ref.unpack(cut["context"], cut["state"]).items():
        if key not in ref.GATES:
            np.testing.assert_array_equal(value, 0)
    evidence(
        "evolved-cut",
        dict(
            status="passed",
            archive=cut["archive"],
            audit=cut["audit"],
            after_definition=cut["raw"],
            source_scope="Actual DOP853 prefix, not fabricated history",
        ),
    )


def test_four_removed_owner_clocks_survive_with_exact_noop_rates():
    raw = fixtures.definition()
    c = ref.bind(raw)
    cut = ref.excise(raw, ref.initial(c), ["cell_1"], fixtures.CUT_TIME)
    assert set(ref.event_times(raw)) <= set(ref.event_times(cut["raw"]))
    for time in (81.1e-6, 88.3e-6, 93.7e-6, 107.9e-6):
        a, phi, _ = ref.evaluate(cut["context"], cut["state"], time - 1e-12)
        b, other, _ = ref.evaluate(cut["context"], cut["state"], time)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(phi, other)


@pytest.mark.parametrize(
    "fault",
    [
        "old_parent",
        "missing_field",
        "nan",
        "stateless_slot",
        "one_state_slot",
        "junction_below_minimum",
        "channel_over_one",
        "unknown",
        "duplicate",
        "off_grid",
        "past",
    ],
)
def test_invalid_source_gate_ownership_and_absolute_cut_clock_rejected(fault):
    raw = fixtures.definition()
    c = ref.bind(raw)
    values = ref.unpack(c, ref.initial(c))
    time, removed = fixtures.CUT_TIME, ["cell_1"]
    if fault == "old_parent":
        raw["model"]["id"] = "resolved_tissue@11"
    elif fault == "missing_field":
        values.pop("metabolic_work_pJ")
    elif fault == "nan":
        values["amount_increment"][0, 0] = np.nan
    elif fault == "stateless_slot":
        values["channel_gate"][0, 1] = 0.1
    elif fault == "one_state_slot":
        values["channel_gate"][1, 0] = 0.1
    elif fault == "junction_below_minimum":
        values["junction_gate"][0] = 0.09
    elif fault == "channel_over_one":
        values["channel_gate"][0, 0] = 1.01
    elif fault == "unknown":
        removed = ["absent"]
    elif fault == "duplicate":
        removed *= 2
    elif fault == "off_grid":
        time = 10.1e-6
    else:
        time = -1e-6
    with pytest.raises(ValueError):
        ref.excise(raw, values, removed, time)


@pytest.mark.parametrize("arm", ["closed", "disconnected"])
def test_invalid_retained_field_archives_complete_19_field_failure(arm):
    raw = fixtures.definition(arm)
    c = ref.bind(raw)
    with pytest.raises(ref.ExcisionError) as caught:
        ref.excise(raw, ref.initial(c), fixtures.cut_plan(arm)[0]["removed_cell_ids"], 0.0)
    assert len(caught.value.archive["checkpoint"]["state"]) == 19
    evidence(
        "expected-rejection-" + arm,
        dict(status="expected_rejection", archive=caught.value.archive, audit=caught.value.audit),
    )


def test_noop_and_terminal_preserve_complete_active_source():
    raw = fixtures.definition()
    c = ref.bind(raw)
    state = prefix()["state"][-1]
    noop = ref.excise(raw, state, [], fixtures.CUT_TIME)
    assert noop["raw"] == raw
    np.testing.assert_array_equal(noop["state"], state)
    terminal = ref.excise(raw, state, [p["id"] for p in raw["model"]["cells"]], fixtures.CUT_TIME)
    assert terminal["raw"] is terminal["state"] is terminal["context"] is None
    assert terminal["audit"]["terminal"]
    assert terminal["archive"]["checkpoint"]["state"] == noop["archive"]["checkpoint"]["state"]
    assert len(ref.unpack(c, state)) == 19


def test_full_19_prefix_cut_suffix_refinement_energy_and_material():
    raw = fixtures.definition()
    before = ref.bind(raw)
    prefixes, suffixes, cuts, residuals = [], [], [], []
    for refinement in (1, 2):
        p = prefix(refinement)
        cut = ref.excise(raw, p["state"][-1], ["cell_1"], fixtures.CUT_TIME)
        suffix = integrate(serialized(cut), refinement=refinement)
        prefixes.append(p)
        suffixes.append(suffix)
        cuts.append(cut)
        residual = []
        for c, start_state, run in (
            (before, ref.initial(before), p),
            (cut["context"], cut["state"], suffix),
        ):
            for time, state in zip(run["times"], run["state"], strict=True):
                assert local_material(c, state) < 3e-13
                residual.append(energy_balance(c, start_state, state, run["times"][0], time))
        assert max(map(abs, residual)) < 3e-9
        residuals.append(residual)
    compare(before, prefixes[0]["state"], prefixes[1]["state"])
    compare(cuts[0]["context"], suffixes[0]["state"], suffixes[1]["state"])
    assert suffixes[0]["times"][0] == fixtures.CUT_TIME
    evidence(
        "full19-transient-refinement",
        dict(
            status="passed",
            fields=19,
            prefix_end_s=fixtures.CUT_TIME,
            suffix_end_s=fixtures.END_TIME,
            prefix_evaluations=[v["evaluations"] for v in prefixes],
            suffix_evaluations=[v["evaluations"] for v in suffixes],
            energy_residuals_pJ=residuals,
            scope=(
                "Gate/history preservation and live coupling; "
                "not slow-gate equilibrium or full native cut parity"
            ),
        ),
        dict(
            prefix_times=np.asarray(prefixes[0]["times"]),
            prefix=prefixes[0]["state"],
            prefix_refined=prefixes[1]["state"],
            suffix_times=np.asarray(suffixes[0]["times"]),
            suffix=suffixes[0]["state"],
            suffix_refined=suffixes[1]["state"],
        ),
    )


def test_sequential_active_cuts_preserve_nested_memory_and_absolute_epoch():
    raw = fixtures.definition()
    first = ref.excise(raw, prefix()["state"][-1], ["cell_1"], fixtures.CUT_TIME)
    first_raw = serialized(first)
    continued = integrate(first_raw, end_time=80 * fixtures.DT)
    second = ref.excise(first_raw, continued["state"][-1], ["cell_0"], 80 * fixtures.DT)
    assert second["archive"]["definition"]["model"]["excision"]["source"] == first["archive"]
    assert [p["id"] for p in second["raw"]["model"]["cells"]] == ["cell_2"]
    assert second["raw"]["model"]["junctions"] == []
    end = integrate(serialized(second))
    assert end["times"][0] == 80 * fixtures.DT
    assert (
        abs(
            energy_balance(
                second["context"],
                second["state"],
                end["state"][-1],
                end["times"][0],
                end["times"][-1],
            )
        )
        < 3e-9
    )
    evidence(
        "sequential-active",
        dict(
            status="passed",
            first=first["archive"],
            second=second["archive"],
            retained_gates=second["raw"]["model"]["channels"],
            final_time=end["times"][-1],
        ),
    )
    assert not any(name == "cells" or name.startswith(("cells.", "jax")) for name in sys.modules)
