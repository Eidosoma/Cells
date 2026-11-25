"""The builder's side of the ensemble's re-expression: definitions, clocks and tables.

Parse only, and fabricated records: no row compiles or runs a world. The records are made by the
driver's own code around numbered arrays, so that every slot of every array differs and a swapped
index, a turned sign or a shifted clock changes a number that a row holds. The 49 rows take about
25 s on the shared CPUs, most of it the engine's parse of definitions.
"""

import ast
import copy
import dataclasses
import json
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.assembly.spec import AssemblyError
from cells.assembly_pool import observables
from cells.assembly_pool.engine import initial_state
from cells.assembly_pool.kernel import PoolState
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.models.surface_pump import DISSIPATION_MESSAGE, LEDGER_MESSAGE
from cells.models.surface_pump_v3 import STATE_AXES
from cells.registry.models import get_model
from validation.ensemble_reexpression import definitions, labels, refusals, sample, worlds
from validation.ensemble_reexpression import run as driver
from validation.ensemble_reexpression import table as exporter
from validation.ensemble_reexpression.inputs import (
    REGISTERED,
    Inputs,
    InputsError,
    OffGridChange,
    grid_index,
    require_on_grid,
    steps_of,
)

SPEC = REGISTERED.parent


@pytest.fixture(autouse=True)
def _one_revision(monkeypatch):
    """Where the driver would ask Git, which of these rows none is about."""
    monkeypatch.setattr(driver, "revision", lambda: ("0" * 40, False, "none", "0" * 64))


@pytest.fixture(scope="module")
def registered():
    return Inputs()


@pytest.fixture(scope="module")
def invented(tmp_path_factory):
    """The sample's inputs, as a file."""
    path = tmp_path_factory.mktemp("inputs") / "inputs_sample.json"
    path.write_text(json.dumps(sample.invented()))
    return Inputs(path)


# ------------------------------------------------------------------ definitions


ONE_OF_EACH = (
    "jupiter_baseline h=2.5e-05",
    "jupiter_pump_release h=6.25e-06",
    "jupiter_baseline plant channel",
    "integrated h=0.0001",
    "cell s1 pool",
    "cell s1 w3 h=1.25e-05",
    "base s2 w7 h=6.25e-06",
    "base plant swapped",
)


def test_one_run_of_each_kind_parses_to_its_registered_block(registered):
    """The checks of every run (`definitions check`, 36 s) on one of each; the counts are SPEC §4's.
    The registered blocks are held to SPEC §2.5's literal ones inside the check."""
    runs = [registered.run(name) for name in ONE_OF_EACH]
    faults, counts = definitions.check(registered, runs=runs)
    assert faults == []
    assert counts["ionic definitions"] == 4 and counts["composed files"] == 4
    by = {}
    for run in registered.runs.values():
        key = (run.consumer, run.role, run.kind)
        by[key] = by.get(key, 0) + 1
    assert by == {
        ("jupiter", "judged", "ionic"): 6,
        ("jupiter", "support", "ionic"): 1,
        ("jupiter", "plant", "ionic"): 1,
        ("integrated", "judged", "ionic"): 3,
        ("cell", "judged", "pool"): 4,
        ("cell", "judged", "driven"): 96,
        ("cell", "support", "pool"): 1,
        ("base", "judged", "pool"): 4,
        ("base", "judged", "driven"): 96,
        ("base", "support", "pool"): 1,
        ("base", "plant", "driven"): 1,
    }


def test_a_definition_says_the_blocks_names_in_the_engines_words(registered):
    """SPEC §2.1, read from the raw definition and not through worlds.read, so that a pair of turned
    names, one in the writing and one in the reading, is seen."""
    block = registered.worlds["jupiter_pump_release"].block
    raw = definitions.ionic(registered.worlds["jupiter_pump_release"], 2.5e-05)
    model, experiment = raw["model"], raw["experiment"]
    (junction,) = model["junctions"]
    assert (junction["sender"], junction["receiver"]) == ("cell_0", "cell_1")
    own = block["junctions"]["junction"]
    assert (own["from_cell"], own["to_cell"]) == ("cell_0", "cell_1")
    assert junction["gate"]["initial_gate"] == own["gate"]["initial_gate"] == 0.6
    for m in model["membranes"]:
        kept = block["membranes"][m["id"]]
        assert (m["inside"], m["outside"]) == (kept["inside"], kept["outside"])
        assert m["pump"]["capacity_fmol_per_s"] == kept["pump"]["capacity_fmol_per_s"]
        assert m["pump"]["stoichiometry"] == {"Na": -3, "K": 2} and m["calcium_pump"] is None
    for f in model["faces"]:
        kept = block["faces"][f["id"]]
        assert (f["sender"], f["receiver"]) == (kept["sender"], kept["receiver"])
    for c in model["channels"]:
        kept = block["channels"][c["id"]]
        assert (
            c["initial_gate"]
            == [kept["initial_gate"]["m"], kept["initial_gate"]["h"]]
            == [0.2, 0.7]
        )
        assert c["permeant_ions"] == [{"species_id": "K", "relative_permeability": 1.0}]
    assert [r["id"] for r in model["extracellular"]] == ["local", "near", "far"]
    assert not any(r["reservoir"] or r["boundary_potential_V"] for r in model["extracellular"])
    assert model["closure"]["gauge_reference"] == "local"
    off = [{"time": t, "availability": a} for t, a in ((0.0, 1.0), (0.005, 0.0), (0.01, 1.0))]
    assert experiment["pump_controls"] == [
        {"pump_id": m["pump"]["id"], "schedule": off} for m in model["membranes"]
    ]
    one = [{"time": 0.0, "availability": 1.0}]
    for key, name, ids in (
        ("membrane_controls", "membrane_id", ["membrane_0", "membrane_1"]),
        ("channel_controls", "channel_id", ["channel_0", "channel_1"]),
        ("junction_controls", "junction_id", ["junction"]),
    ):
        assert experiment[key] == [{name: i, "schedule": one} for i in ids]
    assert experiment["observation_times"] == [0.0, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02]
    execution = raw["execution"]
    assert (execution["dt"], experiment["end_time"], execution["backend"]) == (2.5e-05, 0.02, "cpu")
    assert (execution["solver"], execution["precision"]) == ("rk4", "float64")
    assert execution["field_solver"] == labels.LABELS["field_solver_floor"]
    sheet = definitions.ionic(registered.worlds["integrated"], 1e-4)
    closed = [(0.0, 1.0), (0.005, 0.5), (0.01, 0.0), (0.015, 1.0)]
    assert [g["junction_id"] for g in sheet["experiment"]["junction_controls"]] == [
        f"junction_{k}" for k in range(12)
    ]
    for group in sheet["experiment"]["junction_controls"]:
        assert [(c["time"], c["availability"]) for c in group["schedule"]] == closed
    assert sheet["experiment"]["pump_controls"] == [] == sheet["experiment"]["channel_controls"]
    assert sheet["execution"]["field_solver"] == labels.LABELS["field_solver"]


def _raw(registered):
    return definitions.ionic(registered.worlds["jupiter_baseline"], 2.5e-05)


DRIFTS = {
    "one unit in the last place of an area": lambda raw: raw["model"]["membranes"][1].update(
        area_m2=np.nextafter(raw["model"]["membranes"][1]["area_m2"], 1.0)
    ),
    "the junction turned round": lambda raw: raw["model"]["junctions"][0].update(
        sender="cell_1", receiver="cell_0"
    ),
    "the gates exchanged": lambda raw: raw["model"]["channels"][0]["initial_gate"].reverse(),
    "a pump left out": lambda raw: (
        raw["model"]["membranes"][0].update(pump=None),
        raw["experiment"]["pump_controls"].pop(0),
    ),
    "two faces' ends exchanged": lambda raw: raw["model"]["faces"][0].update(
        sender="near", receiver="local"
    ),
    "a pump switched": lambda raw: raw["experiment"]["pump_controls"][1]["schedule"].append(
        {"time": 0.01, "availability": 0.0}
    ),
    "a held bath": lambda raw: (
        raw["model"]["closure"].update(gauge_reference=None),
        raw["model"]["extracellular"][0].update(reservoir=True),
    ),
    "a tolerance": lambda raw: raw["execution"]["material_balance_atol_fmol"].update(K=1e-11),
    "the species' order is no drift": None,
}


@pytest.mark.parametrize("drift", DRIFTS)
def test_a_definition_that_drifts_from_its_block_is_found(registered, drift):
    """Plants: each changed definition parses, and its block departs from the registered one."""
    world, raw = registered.worlds["jupiter_baseline"], _raw(registered)
    if DRIFTS[drift] is None:
        raw["model"]["species"].reverse()
    else:
        DRIFTS[drift](raw)
    found = worlds.read(parse_spec(raw).to_dict())
    faults = definitions.block_faults(found, world.block, "run", driven=False)
    assert bool(faults) is (DRIFTS[drift] is not None), faults


def test_the_echo_reads_defaults_by_the_spec_and_hides_no_field(registered):
    """SPEC §2.4: an omitted default refuses nothing. A field of a definition that a block has no
    name for is read back under its own name, and a block's field that a definition has no place
    for is refused."""
    block = registered.worlds["integrated"].block
    short = copy.deepcopy(block)
    del short["channels"], short["faces"], short["controls"]["leak"], short["controls"]["pump"]
    for membrane in short["membranes"].values():
        del membrane["pump"]
    assert worlds.departures(short, block) == [] == worlds.departures(block, short)
    assert worlds.departures(block | {"end_s": 0.02 * (1 + 2e-12)}, block) != []
    assert worlds.departures(block | {"end_s": 0.02 * (1 + 5e-13)}, block) == []
    for moved, departs in ((1e-25, False), (1e-24, True)):  # 1e-12 of the charges that face it.
        charged = copy.deepcopy(block)
        charged["outside"]["outside"]["initial_charge_C"] += moved
        assert bool(worlds.departures(charged, block)) is departs
    # A default written out for an entity that is not there (the rehearsal's pump schedules of
    # membranes without a pump) says nothing; any other schedule of one is the engine's to refuse.
    told = copy.deepcopy(block)
    told["controls"]["pump"] = {m: [[0.0, 1.0]] for m in told["membranes"]}
    told["controls"]["channel"] = {"no_channel": [[0.0, 1.0]]}
    asked = dict(step=1e-4, observation_times=[0.0], solver="rk4", field_solver="none")
    assert worlds.write(told, **asked) == worlds.write(block, **asked)
    assert worlds.departures(told, block) == [] == worlds.departures(block, told)
    told["controls"]["pump"]["membrane_3"] = [[0.0, 1.0], [0.005, 0.0]]
    (group,) = worlds.write(told, **asked)["experiment"]["pump_controls"]
    assert group["pump_id"] == "pump_membrane_3" and len(group["schedule"]) == 2
    assert worlds.departures(block, told) != []
    raw = definitions.ionic(registered.worlds["cell"], 2.5e-05)
    raw["model"]["extracellular"][0]["reservoir"] = True
    assert worlds.read(raw)["outside"]["outside"]["reservoir"] is True
    for path in (("stores",), ("cells", "cell_0", "colour")):
        wider = copy.deepcopy(block)
        target = wider
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = 1
        with pytest.raises(worlds.NoSection, match=path[-1]):
            worlds.write(
                wider, step=1e-4, observation_times=[0.0], solver="rk4", field_solver="none"
            )


def test_the_declared_changes_and_the_integrators_are_the_leads(registered, invented):
    """EP1, EP2, `declared_change` and p: the lead's answers of 25 November."""
    plant = registered.run("jupiter_baseline plant channel")
    block = registered.worlds["jupiter_baseline"].block
    changed = definitions.changed_block(block, definitions.declared_change(registered, plant))
    for name, channel in block["channels"].items():
        was = channel["max_permeability_m_per_s"]
        assert changed["channels"][name]["max_permeability_m_per_s"] == was * 1.01
    assert [path[:2] for path, _, _ in worlds.departures(changed, block)] == [
        ("channels", "channel_0"),
        ("channels", "channel_1"),
    ]
    swap = definitions.declared_change(registered, registered.run("base plant swapped"))
    base = registered.worlds["base"]
    honest = definitions.composed(base, 0, 6.25e-06)
    swapped = definitions.composed(base, 0, 6.25e-06, swap)
    assert [p["channels"] for p in swapped["pools"]] == [["channel_1"], ["channel_0"]]
    for pool, other in zip(honest["pools"], swapped["pools"], strict=True):
        assert pool | {"channels": None} == other | {"channels": None}
    assert swapped["ionic"] == honest["ionic"]
    assert [p["levels"] for p in honest["pools"]] == [{"true": 1.0, "false": 0.0}] * 2
    assert [p["pool"]["seed"] for p in honest["pools"]] == [20260925, 20260926]
    assert definitions.first_step(registered, registered.run("base s3 pool")) == 2.5e-05
    assert definitions.declared_change(registered, registered.run("base s0 w2 h=6.25e-06")) == []
    entry = invented.run("inv_sample_cluster plant channel")
    found = definitions.definition(invented, entry)
    assert [c["max_permeability_m_per_s"] for c in found["model"]["channels"]] == [5e-10, 4e-10]
    for wrong in ({"path": ["channels"]}, [{"path": ["no_such"], "value": 1}], [{"times": 2}]):
        run = dataclasses.replace(entry, declared_change=wrong)
        with pytest.raises(InputsError):
            definitions.definition(invented, run)
    assert labels.integrator(4) == "rk4" and labels.integrator(2) == labels.LABELS["imex"]
    with pytest.raises(labels.UnknownOrder, match="unknown_order: p = 3"):
        labels.integrator(3)


def test_a_definition_the_engine_refuses_to_parse_is_submitted_as_declared(invented):
    """The floor solver is declared by the block's own count where no parse can give one."""
    cold = invented.worlds["inv_sample_cold"]
    factored = labels.LABELS["field_solver"]
    assert definitions.submitted(cold, 4e-05)["execution"]["field_solver"] == factored
    block = copy.deepcopy(invented.worlds["inv_sample_cluster"].raw)
    block["ionic"]["temperature_K"] = 150.0
    world = type(cold)("inv_cold_cluster", "jupiter", block)
    raw = definitions.submitted(world, 2e-05)
    assert raw["execution"]["field_solver"] == labels.LABELS["field_solver_floor"]
    with pytest.raises(ConfigError, match="200-400 K"):
        parse_spec(raw)
    assert definitions.floating(block["ionic"]) == 2
    lone = copy.deepcopy(invented.worlds["inv_sample_lone"].raw)
    lone["ionic"]["temperature_K"] = 150.0
    moved = copy.copy(invented)
    moved.worlds = invented.worlds | {
        "inv_sample_lone": type(cold)("inv_sample_lone", "cell", lone)
    }
    for name in ("inv_sample_lone s1 w2 h=2e-05", "inv_sample_lone s1 pool"):
        composed = definitions.definition(moved, moved.run(name))
        assert composed["ionic"]["model"]["temperature_K"] == 150.0
        assert [p["pool"]["seed"] for p in composed["pools"]] == [612]


# ------------------------------------------------------------------ the grid rule


def test_the_grid_rule_takes_a_rounding_and_refuses_the_rest_by_name(registered):
    """SPEC §4: within 2 eps t of k h. The registered change at 0.015 s misses its k h by one unit
    in the last place; a change between two grid points is refused by name."""
    for step in (1e-4, 5e-5, 2.5e-5, 1.25e-5, 6.25e-6, 3.125e-6):
        assert grid_index(0.015, step) == round(0.015 / step)
    assert 150 * 1e-4 != 0.015  # The one unit in the last place that the rule is for.
    assert grid_index(0.015 * (1 + 3e-16), 1e-4) == 150
    assert grid_index(0.015 * (1 + 2e-15), 1e-4) is None
    with pytest.raises(OffGridChange, match="off_grid_change: the change declares 0.00503"):
        require_on_grid([0.005, 0.00503], 1e-4, "the change")
    assert steps_of(0.02, 6.25e-06) == 3200
    with pytest.raises(OffGridChange):
        steps_of(0.02, 3e-05)
    run = registered.run("integrated h=0.0001")
    assert definitions.grid_faults(registered, run) is None
    entry = copy.deepcopy(registered.raw)
    entry["worlds"]["integrated"]["ionic"]["controls"]["junction"]["junction_3"][1][0] = 0.00503
    moved = copy.copy(registered)
    moved.worlds = {
        name: type(w)(name, w.consumer, entry["worlds"][name])
        for name, w in registered.worlds.items()
    }
    fault = definitions.grid_faults(moved, run)
    assert fault.startswith("off_grid_change: controls.junction junction_3 declares 0.00503 s")


def test_a_retry_is_its_familys_by_rule_and_a_restart_names_its_run(registered, tmp_path):
    run = registered.run("base s0 w2 h=3.125e-06 retry")
    assert (run.world, run.seed_index, run.world_id, run.step_s) == ("base", 0, 2, 6.25e-06 / 2)
    assert run.retry and run.kind == "driven" and definitions.grid_faults(registered, run) is None
    for name in ("base s0 w2 h=6.25e-06 retry", "base s9 w2 h=3.125e-06 retry"):
        with pytest.raises(InputsError):
            registered.run(name)
    note = {"kind": "ensemble-reexpression retry owed, version 1", "part": 1, "why": {}}
    path = tmp_path / "retry_owed.json"
    path.write_text(json.dumps(note | {"runs": ["integrated h=1.25e-05 retry"]}))
    assert [r.step_s for r in registered.owed(path)] == [1.25e-05]
    restart = registered.run("jupiter_baseline h=2.5e-05 restart")
    assert (restart.restart_time, restart.judged_name) == (0.01, "jupiter_baseline h=2.5e-05")
    (tmp_path / "twice.json").write_text('{"schema": 1, "schema": 2}')
    with pytest.raises(InputsError, match="given twice"):
        Inputs(tmp_path / "twice.json")


# ------------------------------------------------------------------ fabricated records


def _numbered(name, shape):
    """An array whose every element differs, and differs from every other array's."""
    base = sum(ord(c) * 7.0 for c in name) + 1.0
    return base + 1e-3 * np.arange(float(np.prod(shape))).reshape(shape)


SIZES = {
    "species": lambda d: len(d["model"]["species"]),
    "cell_slot": lambda d: len(d["model"]["cells"]),
    "extracellular_slot": lambda d: len(d["model"]["extracellular"]),
    "membrane_slot": lambda d: len(d["model"]["membranes"]),
    "edge_slot": lambda d: len(d["model"]["junctions"]),
    "face_slot": lambda d: len(d["model"]["faces"]),
    "channel_slot": lambda d: len(d["model"]["channels"]),
    "gate": lambda d: 2,
}


def arrays(definition, times, observed):
    """A run's recorded arrays, as trajectory.npz names them."""
    out = {"accepted_times": np.asarray(times), "observation_times": np.asarray(observed)}
    for name, axes in STATE_AXES.items():
        out[name] = _numbered(name, (len(times), *(SIZES[a](definition) for a in axes)))
    membranes, regions = SIZES["membrane_slot"], SIZES["extracellular_slot"]
    out["observed_membrane_voltage_V"] = _numbered("V", (len(observed), membranes(definition)))
    out["observed_extracellular_potential_V"] = _numbered(
        "phi", (len(observed), regions(definition))
    )
    return out


def attempted(tmp_path, inputs, run, submitted, *, parsed=None, saved=None, **outcome):
    """A run's record, made by the driver's own code around these files."""
    folders = driver.Folders(tmp_path)
    attempt = driver.next_attempt(folders.run(run))
    driver.write_json(attempt / "job.json", {"started_utc": "then"})
    driver.write_json(attempt / "submitted.json", submitted)
    if parsed is not None:
        driver.write_json(attempt / "parsed.json", parsed)
    for name, values in (saved or {}).items():
        path = attempt / name
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, **values)
    facts = {"definition": {}, "resolution": None, "restart": None, "timings": {}}
    facts |= outcome.pop("facts", {})
    outcome = {"status": "completed", "refusal": None, "source": SOURCE, "facts": facts} | outcome
    driver.write_json(attempt / "outcome.json", outcome)
    record = driver.made(inputs, run, attempt, None, tag=None, off_grid=False)
    driver.write_json(folders.run(run) / driver.RECORD, record)
    return folders, attempt


SOURCE = {
    "engine_revision": "0" * 40,
    "checkout_dirty": False,
    "snapshot": "none",
    "snapshot_patch_sha256": "0" * 64,
    "python": "3",
    "numpy": "2",
    "jax": "0",
    "jaxlib": "0",
    "cpu_model": "a model",
    "blas_threads": 1,
}


def ionic_record(tmp_path, inputs, name, times, observed, **more):
    run = inputs.run(name)
    raw = definitions.definition(inputs, run)
    parsed = parse_spec(raw).to_dict()
    found = arrays(parsed, times, observed)
    saved = {more.pop("file", "output/trajectory.npz"): found}
    folders, _ = attempted(tmp_path, inputs, run, raw, parsed=parsed, saved=saved, **more)
    return exporter.entry(inputs, run, folders), found, run


def test_an_ionic_entry_is_the_contracts_and_every_readout_is_its_own_slot(invented, tmp_path):
    """READOUTS §2 on numbered arrays: the two flipped signs, the index of every entity, the
    compared times among every accepted row, and the potentials at theirs."""
    times = [k * 2e-05 for k in range(11)]
    observed = [0.0, 4e-05, 0.00012, 0.0002]
    entry, found, run = ionic_record(
        tmp_path, invented, "inv_sample_cluster h=2e-05", times, observed
    )
    assert exporter.entry_faults(run.name, entry) == []
    assert (entry["steps"], entry["restart"], entry["refusal"]) == (10, None, None)
    assert "off_grid" not in entry
    rows = [0, 2, 4, 6, 8, 10]  # Every 40 us of the accepted rows.
    assert entry["t"] == [times[k] for k in rows]
    assert entry["potential_t"] == observed
    expected = {
        "n_cell_K": ("amount_increment", (1, 1), 1, "c_b"),
        "n_out_Cl": ("extracellular_amount_increment", (2, 2), 1, "rim"),
        "leak_Na": ("membrane_transferred", (0, 1), -1, "m_b"),
        "channel_K": ("channel_transferred", (1, 0), -1, "k_a"),
        "junction_K": ("junction_transferred", (1, 0), 1, "j_ab"),
        "face_Na": ("face_transferred", (0, 2), 1, "f_2"),
        "pump": ("pump_cycles", (1,), 1, "m_b"),
        "gate_m": ("channel_gate", (0, 1), 1, "k_b"),
        "gate_h": ("channel_gate", (1, 1), 1, "k_b"),
        "junction_gate": ("junction_gate", (0,), 1, "j_ab"),
        "heat_leak": ("membrane_dissipated_energy_pJ", (0,), 1, "m_a"),
        "heat_pump": ("pump_dissipated_energy_pJ", (1,), 1, "m_b"),
        "heat_junction": ("junction_dissipated_energy_pJ", (0,), 1, "j_ab"),
        "heat_face": ("face_dissipated_energy_pJ", (1,), 1, "f_1"),
        "work_pump": ("metabolic_work_pJ", (0,), 1, "m_a"),
    }
    for name, (array, slot, sign, entity) in expected.items():
        values = [sign * found[array][(k, *slot)] for k in rows]
        assert entry["rows"][name][entity] == values, name
    heat = found["channel_dissipated_energy_pJ"][:, :, 1].sum(axis=1)
    assert entry["rows"]["heat_channel"]["k_b"] == [heat[k] for k in rows]
    three = {
        f"{n}_{x}" for n in ("n_cell", "n_out", "leak", "junction", "face") for x in sample.VALENCE
    }
    assert set(entry["rows"]) == three | set(expected) | {"heat_channel"}
    voltage = found["observed_membrane_voltage_V"]
    phi = found["observed_extracellular_potential_V"]
    assert entry["potentials"] == {
        "voltage": {"m_a": voltage[:, 0].tolist(), "m_b": voltage[:, 1].tolist()},
        "phi_out": {"shell": phi[:, 1].tolist(), "rim": phi[:, 2].tolist()},
    }
    block = invented.worlds[run.world].block
    assert worlds.departures(entry["inputs"], block) == []
    assert set(entry["strings"]) == definitions._labels(invented, run)
    assert entry["declared_strings"] == sorted(entry["strings"].values())
    assert json.loads(json.dumps(entry)) == entry


def test_a_world_without_a_route_has_no_series_of_it(invented, tmp_path):
    """READOUTS §2, `integrated`: no pump, leak, channel or face series, and no phi_out."""
    times = [k * 4e-05 for k in range(6)]
    entry, _, run = ionic_record(
        tmp_path, invented, "inv_sample_sheet h=4e-05", times, [0.0, 8e-05, 0.00016]
    )
    assert exporter.entry_faults(run.name, entry) == []
    species = {f"{n}_{x}" for n in ("n_cell", "n_out", "junction") for x in sample.VALENCE}
    assert set(entry["rows"]) == species | {"junction_gate", "heat_junction"}
    assert set(entry["potentials"]) == {"voltage"}


def test_a_restarts_clock_continues_its_judged_runs(invented, tmp_path):
    """TABLE §3: the first row at the checkpoint's time and none before it, the steps counted after
    it, the potentials after it alone."""
    times = [k * 2e-05 for k in range(6, 11)]
    name = "inv_sample_cluster h=2e-05 restart"
    restart = {"time_s": times[0], "step_index": 6, "through": "file"}
    entry, found, run = ionic_record(
        tmp_path, invented, name, times, [0.00012, 0.0002], facts={"restart": restart}
    )
    assert exporter.entry_faults(name, entry) == []
    assert entry["t"] == [times[0], times[2], times[4]] and entry["steps"] == 4
    assert entry["rows"]["pump"]["m_a"] == [found["pump_cycles"][k, 0] for k in (0, 2, 4)]
    assert entry["potential_t"] == [0.0002]
    assert entry["potentials"]["voltage"]["m_b"] == [found["observed_membrane_voltage_V"][1, 1]]
    assert entry["restart"] == restart
    # A restart that lost its last row is no entry: the exporter refuses it, by name.
    lost, _, _ = ionic_record(
        tmp_path / "lost", invented, name, times[:-1], [0.00012, 0.0002], facts={"restart": restart}
    )
    assert lost["status"] == "refused" and lost["refusal"]["kind"] == "harness"
    assert "has no row at 0.0002 s" in lost["refusal"]["message"]


def test_a_refused_runs_entry_keeps_what_it_has(invented, tmp_path):
    """TABLE §4: at parse nothing but the submitted declaration; at a check the rows before it, and
    the time of the row that failed; a crash, the record alone."""
    run = invented.run("inv_sample_cold h=4e-05")
    raw = definitions.definition(invented, run)
    with pytest.raises(ConfigError) as error:
        parse_spec(raw)
    refusal = refusals.refusal(error.value, stage="parse")
    folders, _ = attempted(tmp_path, invented, run, raw, status="refused", refusal=refusal)
    entry = exporter.entry(invented, run, folders)
    assert exporter.entry_faults(run.name, entry) == []
    assert (entry["t"], entry["rows"], entry["potentials"], entry["steps"]) == ([], {}, {}, 0)
    assert entry["refusal"]["kind"] == "domain" and entry["refusal"]["time_s"] is None
    assert worlds.departures(entry["inputs"], invented.worlds[run.world].block) == []
    assert entry["definition"]["ionic"] == raw and "rk4" in entry["strings"].values()

    stop = {"kind": "check", "message": LEDGER_MESSAGE + "energy", "time_s": 0.00012}
    entry, _, run = ionic_record(
        tmp_path / "check",
        invented,
        "inv_sample_tight h=4e-05",
        [0.0, 4e-05, 8e-05],
        [0.0, 4e-05],
        file="partial.npz",
        status="refused",
        refusal=stop,
    )
    assert exporter.entry_faults(run.name, entry) == []
    assert entry["t"] == [0.0, 4e-05, 8e-05] and entry["steps"] == 2
    assert entry["potential_t"] == [0.0, 4e-05] and entry["refusal"] == stop
    folders = driver.Folders(tmp_path / "check")  # The record holds the hash of those rows' file.
    record, partial = folders.record(run), folders.attempt(run) / "partial.npz"
    assert record["files_sha256"]["partial.npz"] == driver.digest(partial)
    partial.write_bytes(partial.read_bytes() + b" ")
    changed = exporter.entry(invented, run, folders)
    assert "partial.npz is not what its record lists" in changed["refusal"]["message"]

    run = invented.run("inv_sample_slow h=4e-05")
    crash = driver.Folders(tmp_path / "crash")
    attempt = driver.next_attempt(crash.run(run))
    driver.write_json(attempt / "job.json", {"started_utc": "then"})
    record = driver.made(invented, run, attempt, "ended by signal 9", tag=None, off_grid=False)
    driver.write_json(crash.run(run) / driver.RECORD, record)
    entry = exporter.entry(invented, run, crash)
    assert exporter.entry_faults(run.name, entry) == []
    assert entry["refusal"] == {"kind": "harness", "message": "ended by signal 9", "time_s": None}


# ------------------------------------------------------------------ pools and driven runs


def _pool_run(folder, definition, events, counts):
    """A pool's finished folder: its registration, its recorded events and its checkpoint.

    events: [(world, time, occupied, bonds), ...] in order."""
    worlds_, rows = definition.worlds, len(events)
    trace = {
        "time_s": np.zeros((rows, worlds_)),
        "occupied": np.zeros((rows, worlds_), np.uint32),
        "bonds": np.zeros((rows, worlds_), np.uint32),
        "free": np.zeros((rows, worlds_), np.int64),
        "event": np.full((rows, worlds_), -1, np.int32),
    }
    for k, (world, time, occupied, bonds) in enumerate(events):
        trace["time_s"][k, world] = time
        trace["occupied"][k, world], trace["bonds"][k, world] = occupied, bonds
        trace["event"][k, world] = 3
    folder.mkdir(parents=True)
    for k, part in enumerate(np.array_split(np.arange(rows), 2)):  # Two chunks, in order.
        np.savez(folder / f"events-{k + 1:07}.npz", **{n: v[part] for n, v in trace.items()})
    driver.write_json(folder / "registration.json", {"definition": definition.to_dict()})
    driver.write_json(folder / "result.json", {"status": "completed"})
    _checkpoint(folder / "checkpoint", definition, counts)


def _checkpoint(folder, definition, counts):
    state = initial_state(definition)
    values = {n: _filled(v) for n, v in state._asdict().items()}
    values["event_count"] = np.asarray(counts, np.uint32)
    folder.mkdir(parents=True)
    np.savez(folder / "state.npz", **values)
    driver.write_json(
        folder / "manifest.json", {"state_sha256": driver.digest(folder / "state.npz")}
    )


def _filled(value):
    if value.dtype == bool:
        return np.arange(value.size).reshape(value.shape) % 2 == 0
    return (np.arange(value.size).reshape(value.shape) + 1).astype(value.dtype)


RING = 0b11111  # Five sites; five bonds make a ring of them.


def test_a_pool_entry_has_the_19_arrays_and_its_own_path(invented, tmp_path):
    """TABLE §3 and READOUTS §4: the arrays by cell, the path by world ID with the availability
    after each committed event, `channel` and `stream_id` from the composed file, and a restart's
    path from its second leg alone."""
    names = (SPEC / "READOUTS.md").read_text().split("in the world order of the seeds' IDs:")[1]
    nineteen = [n for n in names.split("`")[1::2][:19]]
    assert list(PoolState._fields) == nineteen
    for name, restarted in (
        ("inv_sample_pair s0 pool", False),
        ("inv_sample_pair s0 pool restart", True),
    ):
        run = invented.run(name)
        composed = definitions.definition(invented, run)
        facts = {"restart": {"time_s": 0.0001, "step_index": None, "through": "file"}}
        folders, attempt = attempted(
            tmp_path / name, invented, run, composed, facts=facts if restarted else {}
        )
        from cells.assembly_pool.spec import parse_spec as parse_pool

        for k, entry in enumerate(composed["pools"]):
            spec = parse_pool(entry["pool"])
            events = [(0, 1e-05, RING, 0b1111), (2, 2e-05, RING, RING), (0, 3e-05, RING, RING)]
            counts = [2, 0, 1]
            if restarted:
                counts = [2 + 4, 5, 1 + 6]
                first = attempt / f"output/first-leg-{k:03}/checkpoint"
                _checkpoint(first, spec, [4, 5, 6])
            _pool_run(attempt / f"output/pools/pool-{k:03}", spec, events, counts)
        record = driver.made(invented, run, attempt, None, tag=None, off_grid=False)
        (folders.run(run) / driver.RECORD).unlink()
        driver.write_json(folders.run(run) / driver.RECORD, record)
        entry = exporter.entry(invented, run, folders)
        assert exporter.entry_faults(name, entry) == [] and entry["refusal"] is None
        assert entry["steps"] is None and entry["step_s"] is None
        assert entry["path"]["c_b"] == {
            "0": [[1e-05, 0], [3e-05, 1]],
            "1": [],
            "2": [[2e-05, 1]],
        }
        for k, cell in enumerate(("c_a", "c_b")):
            held = entry["pool"][cell]
            assert (held["seed"], held["stream_id"]) == ([711, 721][k], k)
            assert (
                len(held["arrays"]["fragments"]) == 3 and len(held["arrays"]["fragments"][0]) == 21
            )
            assert held["arrays"]["pending_valid"] == [True, False, True]
            own = invented.worlds[run.world].pools[cell]
            shown = {"channel": own["channel"], "stream_id": k, "seed": [711, 721][k]}
            assert entry["inputs"][cell] == shown | {"pool": own["pool"]}
        pool_strings = {"pool_model", "pool_topology", "assembly_observable"}
        assert set(entry["strings"]) == pool_strings
        assert entry["declared_strings"] == sorted(labels.LABELS[n] for n in pool_strings)
        noted = labels.note_entry(entry["declared_strings"])
        assert (noted["model"], noted["observable"]) == ("pool_model", "assembly_observable")
        assert noted["solver"] is None and noted["field_solver"] is None
    # An event that the checkpoint does not count is a fault of the record, and no entry.
    driver.write_json(attempt / "output/pools/pool-000/x.json", {})
    assert exporter.entry(invented, run, folders)["status"] == "completed"
    (attempt / "output/pools/pool-000/events-0000001.npz").unlink()
    assert (
        "not what its record lists" in exporter.entry(invented, run, folders)["refusal"]["message"]
    )


@pytest.mark.parametrize("plant", (False, True))
def test_a_driven_entry_says_what_its_schedule_came_from(invented, tmp_path, plant):
    """TABLE §3 `inputs.assembly`, and EP2's reading (the lead, 25 November): the switches by the
    channel they drive, the seeds by the pool's position in the composed file."""
    name = "inv_sample_pair plant swapped" if plant else "inv_sample_pair s0 w1 h=2e-05"
    run = invented.run(name)
    composed = definitions.definition(invented, run)
    raw = copy.deepcopy(composed["ionic"])
    driven = [pool["channels"][0] for pool in composed["pools"]]
    assert driven == (["k_b", "k_a"] if plant else ["k_a", "k_b"])
    path = {0: [[3.3e-05, 0.0]], 1: [[5.1e-05, 0.0], [9.7e-05, 1.0]]}
    for k, channel in enumerate(driven):
        (control,) = (
            c for c in raw["experiment"]["channel_controls"] if c["channel_id"] == channel
        )
        control["schedule"] += [{"time": t, "availability": a} for t, a in path[k]]
    parsed = parse_spec(raw).to_dict()
    switches = [
        {"pool": k, "time": t, "level": a, "event": j}
        for k in path
        for j, (t, a) in enumerate(path[k])
    ]
    made_from = {
        "composed_file_sha256": "c" * 64,
        "pools": [
            {"channels": p["channels"], "observable": p["observable"], "seed": p["pool"]["seed"]}
            for p in composed["pools"]
        ],
        "worlds": [
            {"world": 0, "switches": []},
            {"world": 1, "switches": sorted(switches, key=lambda s: s["time"])},
        ],
    }
    times = sorted({*(k * 2e-05 for k in range(11)), 3.3e-05, 5.1e-05, 9.7e-05})
    resolved = tmp_path / "resolutions/one/RESOLUTION.json"
    resolved.parent.mkdir(parents=True)
    resolved.write_text("{}")
    resolution = {"record": "resolutions/one/RESOLUTION.json"}
    resolution["record_sha256"] = driver.digest(resolved)
    folders, attempt = attempted(
        tmp_path, invented, run, composed, parsed=parsed, facts={"resolution": resolution}
    )
    driver.write_json(attempt / "inputs.json", made_from)
    (attempt / "output").mkdir()
    np.savez(attempt / "output/trajectory.npz", **arrays(parsed, times, [0.0, 8e-05, 0.0002]))
    driver.write_json(
        attempt / "output/manifest.json", {"provenance": {"operation": "run", "inputs": made_from}}
    )
    entry = exporter.entry(invented, run, folders)
    assert exporter.entry_faults(name, entry) == [] and entry["refusal"] is None
    assert entry["steps"] == 13 and entry["t"] == [0.0, 8e-05, 0.0002] == entry["potential_t"]
    assert composed["ionic"]["experiment"]["observation_times"] == [0.0, 8e-05, 0.0002]
    assert entry["inputs"]["assembly"] == {
        "assembly_observable": "assembly_observable",
        "composed_file_fingerprint": "c" * 64,
        "pool_seeds": {"c_a": 711, "c_b": 721},
        "switch_list": {driven[0]: path[0], driven[1]: path[1]},
    }
    channel = entry["inputs"]["controls"]["channel"]
    assert channel[driven[1]] == [[0.0, 1.0], *path[1]]
    assert observables.LAW_ID in entry["declared_strings"]
    assert entry["strings"]["assembly_observable"] == observables.LAW_ID
    manifest = attempt / "output/manifest.json"
    manifest.write_text(json.dumps({"definition_sha256": "another"}))
    other = exporter.entry(invented, run, folders)
    assert "is of another definition than the one parsed" in other["refusal"]["message"]
    resolved.write_text("{} ")
    changed = exporter.entry(invented, run, folders)
    assert "its resolution is not what its record lists" in changed["refusal"]["message"]
    # A channel that no pool drives is a key too, with an empty list (Amendment 2, 9.1).
    lone = {"pools": made_from["pools"][:1], "composed_file_sha256": "c" * 64}
    lone["worlds"] = [{"world": 1, "switches": [s for s in switches if s["pool"] == 0]}]
    given = exporter.assembly(parsed, lone, 1)
    assert given["switch_list"] == {driven[0]: path[0], driven[1]: []}
    assert given["pool_seeds"] == {"c_a": 711}
    # Refused before it had a schedule: what its composed file submits, and the engine's own kind.
    refusal = {"kind": "definition", "message": "a near miss", "time_s": None}
    folders, _ = attempted(
        tmp_path / "r", invented, run, composed, status="refused", refusal=refusal
    )
    entry = exporter.entry(invented, run, folders)
    assert exporter.entry_faults(name, entry) == [] and entry["refusal"] == refusal
    given = entry["inputs"]["assembly"]
    assert given["pool_seeds"] == {"c_a": 711, "c_b": 721}
    assert given["switch_list"] == {"k_a": [], "k_b": []}
    assert given["composed_file_fingerprint"] == driver.digest(
        folders.attempt(run) / "submitted.json"
    )


# ------------------------------------------------------------------ strings, refusals, the guard


def test_an_extra_piece_shows_among_the_declared_strings(registered):
    """TABLE §3: an extra operator, kind, law or booking is visible. Plants: each adds one."""
    raw = parse_spec(_raw(registered)).to_dict()
    honest = labels.declared_strings(raw)
    assert set(labels.strings(honest)) == definitions._labels(
        registered, registered.run("jupiter_baseline h=2.5e-05")
    )
    for place in (("model", "heat_bookings"), ("model", "kinds"), ("execution", "fine_windows")):
        wider = copy.deepcopy(raw)
        wider[place[0]][place[1]] = {"own": ["some_piece@3"]}
        assert set(labels.declared_strings(wider)) - set(honest) == {"some_piece@3"}
        keyed = copy.deepcopy(raw)
        keyed[place[0]][place[1]] = {"cells.kind.some_piece@3": {}}
        assert set(labels.declared_strings(keyed)) - set(honest) == {"cells.kind.some_piece@3"}
    note = {"labels": labels.LABELS, "runs": {"r h=2e-05": labels.note_entry(honest)}}
    entry = {"strings": labels.strings(honest), "declared_strings": honest}
    table = {"runs": {"r h=2e-05": entry, "r h=1e-05 retry": entry, "other": entry}}
    assert exporter.string_faults(table, note) == ["other: the note lists no such run"]
    del table["runs"]["other"]
    for strings, declared, text in (
        (entry["strings"], sorted([*honest, "some_piece@3"]), "declared_strings"),
        ({k: v for k, v in entry["strings"].items() if k != "closure"}, honest, "strings"),
    ):
        table["runs"]["r h=2e-05"] = {"strings": strings, "declared_strings": declared}
        (fault,) = exporter.string_faults(table, note)
        assert fault.startswith(f"r h=2e-05: {text}")


THRESHOLD = (
    "Junction gate requires {law}, a threshold in [0, 0.120] V and an initial gate in [minimum, 1]"
)
RELAXATION = labels.LABELS["junction_relaxation"]


@pytest.mark.parametrize(
    "error, stage, gates, kind",
    [
        (NumericalError(LEDGER_MESSAGE + "energy"), "run", (), "check"),
        (NumericalError(DISSIPATION_MESSAGE), "run", (), "check"),
        (NumericalError("rk4 domain failure on [0.0, 0.1]"), "run", (), "domain"),
        (ConfigError("Unsupported resolved transport law"), "parse", (), "definition"),
        (ConfigError("model: missing=['cells'], unknown=[]"), "parse", (), "definition"),
        (ConfigError("Resolved gated channels require RK4 steps <= 25 us"), "run", (), "domain"),
        (ConfigError("volume must be finite and positive"), "parse", (), "domain"),
        (ConfigError("volume must be a finite number"), "parse", (), "definition"),
        (ConfigError(THRESHOLD.format(law=RELAXATION)), "parse", (RELAXATION,), "domain"),
        (ConfigError(THRESHOLD.format(law=RELAXATION)), "parse", ("another",), "definition"),
        (AssemblyError("Finite material conservation failed"), "run", (), "check"),
        (AssemblyError("pool_volume_L must be in [1e-24, 1] litres"), "parse", (), "domain"),
        (
            AssemblyError("Unsupported finite-bond assembly model/topology"),
            "parse",
            (),
            "definition",
        ),
        (KeyError("law"), "parse", (), "definition"),
        (KeyError("law"), "run", (), "harness"),
        (MemoryError("out of memory"), "run", (), "harness"),
        (OSError("No space left on device"), "run", (), "harness"),
    ],
)
def test_what_the_engine_raised_is_mapped_to_a_kind(error, stage, gates, kind):
    found = refusals.refusal(error, stage=stage, gates=gates)
    assert found == {"kind": kind, "message": str(error), "time_s": None}


def test_a_declared_changes_gate_law_is_what_its_refusal_is_read_with(invented):
    """The one message that names a law and a range together: a run whose declared change names a
    law that the engine does not have is refused as `definition`, as the rehearsal's is."""
    honest = invented.run("inv_sample_sheet h=4e-05")
    change = [{"path": ["junctions", "j_bc", "gate", "law"], "value": "no_such_law"}]
    message = ConfigError(THRESHOLD.format(law=RELAXATION))
    for run, kind in (
        (honest, "domain"),
        (dataclasses.replace(honest, declared_change=change), "definition"),
        (dataclasses.replace(honest, declared_change=[]), "domain"),
    ):
        worker = object.__new__(driver.Worker)
        worker.inputs, worker.run = invented, run
        assert refusals.kind_of(message, stage="parse", gates=worker.gates()) == kind
    lone = invented.run("inv_sample_lone s1 w2 h=2e-05")
    worker.run = lone
    assert worker.gates() == ()


def test_the_rows_before_a_refusal_and_the_row_that_failed(invented, monkeypatch):
    """A refused run's second pass, on windows that a stand-in yields: adjacent windows share a row,
    and the row that failed is the one after the last accepted window's."""
    raw = definitions.ionic(invented.worlds["inv_sample_sheet"], 4e-05)
    spec = parse_spec(raw)
    fields = get_model(spec.model).STATE_TYPE._fields

    def windows(spec, policy, checkpoint):
        assert (policy.window_steps, policy.recording) == (1, "full")
        for k in range(3):
            if k == 2:
                raise NumericalError(LEDGER_MESSAGE + "energy")
            history = get_model(spec.model).STATE_TYPE(
                *(np.asarray([[k * 10.0 + j], [(k + 1) * 10.0 + j]]) for j in range(len(fields)))
            )
            observed = SimpleNamespace(times=np.asarray([k * 1.0]), voltage=np.asarray([[k * 2.0]]))
            times = np.asarray([k * 4e-05, (k + 1) * 4e-05])
            yield SimpleNamespace(history=history, times=times, observations=observed)

    monkeypatch.setattr(refusals, "iter_windows", windows)
    found, failed = refusals.rows_before(spec)
    assert failed == 3 * 4e-05
    assert found["accepted_times"].tolist() == [0.0, 4e-05, 8e-05]
    for j, name in enumerate(fields):
        assert found[name].ravel().tolist() == [j, 10.0 + j, 20.0 + j]
    assert found["observation_times"].tolist() == [0.0, 1.0]
    assert found["observed_voltage"].ravel().tolist() == [0.0, 2.0]


def test_a_check_that_its_second_pass_does_not_meet_says_so(invented, tmp_path, monkeypatch):
    """The lead's ruling: `second_pass_completed: true` where the one-step pass of a check's refusal
    completes, in the record's refusal and the entry's; absent otherwise, and on no other kind."""
    worker = object.__new__(driver.Worker)
    worker.attempt, worker.facts = tmp_path, {}
    spec = SimpleNamespace(experiment=SimpleNamespace(end_time=0.0002))
    found = {}
    for kind, failed in (("check", None), ("check", 4e-05), ("domain", None), ("domain", 4e-05)):
        monkeypatch.setattr(refusals, "rows_before", lambda *_, at=failed: (None, at))
        refusal = {"kind": kind, "message": LEDGER_MESSAGE + "energy", "time_s": None}
        worker.kept(spec, None, refusal)
        assert worker.facts["refused_row_found"] is (failed is not None)
        told = {"window_steps": 1, "rows": None, "completed": failed is None}
        assert worker.facts["second_pass"] == told
        found[kind, failed] = refusal
    rows = {"accepted_times": np.zeros(2)}
    monkeypatch.setattr(refusals, "rows_before", lambda *_: (rows, 4e-05))
    worker.kept(spec, None, {"kind": "check", "message": "", "time_s": None})
    assert worker.facts["second_pass"]["rows"] == "partial.npz"
    assert (tmp_path / "partial.npz").is_file()
    said = {"time_s": 0.0002, "second_pass_completed": True}
    assert found["check", None] == found["domain", None] | {"kind": "check"} | said
    assert found["check", 4e-05] == found["domain", None] | {"kind": "check", "time_s": 4e-05}
    assert found["domain", 4e-05] == found["domain", None]
    entry, _, run = ionic_record(
        tmp_path / "entry",
        invented,
        "inv_sample_tight h=4e-05",
        [0.0, 4e-05, 8e-05],
        [0.0, 4e-05],
        file="partial.npz",
        status="refused",
        refusal=found["check", None],
    )
    assert entry["refusal"] == found["check", None]
    assert exporter.entry_faults(run.name, entry) == []
    for wrong in ({"second_pass_completed": False}, {"kind": "domain", "time_s": None}):
        faults = exporter.entry_faults(run.name, entry | {"refusal": entry["refusal"] | wrong})
        assert faults == [f"{run.name}: refusal's second_pass_completed"]


def test_a_judged_run_writes_the_checkpoint_that_its_restart_resumes(invented, tmp_path):
    worker = object.__new__(driver.Worker)
    worker.inputs = invented
    worker.run = invented.run("inv_sample_cluster h=2e-05")
    times = [k * 2e-05 for k in range(11)]
    assert worker.checkpoints(times) == (times[6],) and times[6] != 0.00012
    with pytest.raises(RuntimeError, match="No accepted row at 0.00012 s"):
        worker.checkpoints(times[:6])
    worker.run = invented.run("inv_sample_sheet h=4e-05")
    assert worker.checkpoints(times) == ()
    for k in (2, 6):
        folder = tmp_path / f"output/snapshots/step-{k:06}"
        folder.mkdir(parents=True)
        driver.write_json(folder / "manifest.json", {"clock": {"time": times[k]}})
    assert driver.checkpoint_folder(tmp_path, 0.00012).name == "step-000006"
    with pytest.raises(RuntimeError, match="no checkpoint at 0.0001 s"):
        driver.checkpoint_folder(tmp_path, 0.0001)


def test_a_registered_run_is_made_from_a_clean_snapshot_of_the_named_tag_alone(
    registered, invented, tmp_path, monkeypatch
):
    run = registered.run("integrated h=0.0001")
    driver.guard(invented, invented.run("inv_sample_sheet h=4e-05"), None)
    with pytest.raises(driver.Guarded, match="not here"):
        driver.one(registered, run, tmp_path / "runs", tag="some-tag")
    assert not (tmp_path / "runs").exists()
    value = {
        "selected_status_porcelain_v1_z": "",
        "patch_sha256": driver.EMPTY,
        "git_revision": "a" * 40,
        "repository": "/nowhere",
    }
    (tmp_path / driver.SNAPSHOT).write_text("{}")
    own = tmp_path / REGISTERED.relative_to(driver.ROOT)
    own.parent.mkdir(parents=True)
    own.write_bytes(REGISTERED.read_bytes())
    inputs = Inputs(own)
    monkeypatch.setattr("validation.source_snapshot.verify", lambda root: value)
    tags = {"refs/tags/the-tag^{commit}": b"a" * 40, "refs/tags/other^{commit}": b"b" * 40}
    monkeypatch.setattr(driver, "_git", lambda root, *args: tags[args[-1]] + b"\n")
    driver.guard(inputs, run, "the-tag", tmp_path)
    for tag, text in ((None, "name the registration tag"), ("other", "is not the tag")):
        with pytest.raises(driver.Guarded, match=text):
            driver.guard(inputs, run, tag, tmp_path)
    with pytest.raises(driver.Guarded, match="not the snapshot's own inputs"):
        driver.guard(registered, run, "the-tag", tmp_path)
    value["selected_status_porcelain_v1_z"] = " M src/cells/__init__.py"
    with pytest.raises(driver.Guarded, match="not clean"):
        driver.guard(inputs, run, "the-tag", tmp_path)
    with pytest.raises(driver.Guarded, match="outside the tree"):
        driver.Folders(driver.ROOT / "runs")


def worked(tmp_path, path, name, monkeypatch, *, off_grid=False):
    """The outcome of a worker whose ionic run is replaced by a mark."""
    attempt = driver.next_attempt(tmp_path / "attempts")
    job = {"run": name, "inputs": str(path), "runs": str(tmp_path / "runs"), "off_grid": off_grid}
    driver.write_json(attempt / "job.json", job)
    monkeypatch.setattr(driver.Worker, "execute", lambda self, *_: self.output.mkdir())
    driver.Worker(attempt).outcome()
    found = {name: (attempt / name).exists() for name in ("output", "submitted.json")}
    return json.loads((attempt / "outcome.json").read_text()), found


def test_the_generators_own_refusals_come_before_any_run(invented, tmp_path, monkeypatch):
    """The lead's answers: a run off its grid is refused by name (`harness`) and made where told,
    with a flag in its record and its entry; a registered run is never made so; a `p` that names no
    integrator is `harness` too."""
    raw = copy.deepcopy(invented.raw)
    raw["worlds"]["inv_sample_sheet"]["ionic"]["controls"]["junction"]["j_ab"][1][0] = 9.1e-05
    raw["worlds"]["inv_sample_slow"]["p"] = 3
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(raw))
    sheet = "inv_sample_sheet h=4e-05"
    outcome, made = worked(tmp_path, path, sheet, monkeypatch)
    assert made == {"output": False, "submitted.json": True}
    assert outcome["refusal"]["kind"] == "harness"
    assert outcome["refusal"]["message"].startswith("off_grid_change: ")
    outcome, made = worked(tmp_path, path, sheet, monkeypatch, off_grid=True)
    assert made["output"] and outcome["status"] == "completed"
    assert outcome["facts"]["off_grid"].startswith("off_grid_change: ")
    outcome, made = worked(tmp_path, path, "inv_sample_slow h=4e-05", monkeypatch)
    assert made == {"output": False, "submitted.json": False}
    assert outcome["refusal"]["kind"] == "harness"
    assert outcome["refusal"]["message"].startswith("unknown_order: p = 3")
    name = "integrated h=0.0001"
    outcome, made = worked(tmp_path, REGISTERED, name, monkeypatch, off_grid=True)
    assert not made["output"] and outcome["refusal"]["kind"] == "harness"
    run = dataclasses.replace(invented.run(sheet), name="sheet h=4e-05")
    folders, attempt = attempted(tmp_path / "told", invented, run, {})
    record = driver.made(invented, run, attempt, None, tag=None, off_grid=True)
    assert record["options"]["off_grid"] is True
    (folders.run(run) / driver.RECORD).unlink()
    driver.write_json(folders.run(run) / driver.RECORD, record)
    entry = exporter.entry(invented, run, folders)
    assert entry["refusal"]["kind"] == "harness" and "off_grid" in entry["refusal"]["message"]
    assert entry["off_grid"] is True and exporter.entry_faults(run.name, entry) == []
    assert (entry["t"], entry["rows"], entry["potentials"]) == ([], {}, {})


def test_a_worker_that_leaves_no_outcome_is_a_harness_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "MODULE", "this")  # A module that ends well and writes nothing.
    for name, limit, text in (
        ("one", None, "the worker ended with exit code 0 and wrote no outcome"),
        ("two", 0.0, "the run took more than 0.0 s"),
    ):
        attempt = tmp_path / name
        attempt.mkdir()
        assert driver.work_apart(attempt, limit) == text


def test_a_campaign_makes_restarts_last_and_its_snapshot_holds_what_its_modules_import(registered):
    runs = driver.ordered(registered)
    assert [r.restart_time is not None for r in runs] == [False] * 211 + [True] * 3
    units = {driver.unit(r) for r in runs}
    assert len(units) == 214 and all(re.fullmatch(r"[A-Za-z0-9._-]+", u) for u in units)
    assert [r.name for r in driver.ordered(registered, consumers=["integrated"])] == [
        f"integrated h={h!r}" for h in (1e-4, 5e-5, 2.5e-5)
    ]
    imported = set()
    for name in driver.DRIVERS:
        path = driver.ROOT / name
        assert path.is_file(), name
        if path.suffix == ".py":
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "validation"
                ):
                    imported |= {f"{node.module}.{a.name}" for a in node.names} | {node.module}
                elif isinstance(node, ast.Import):
                    imported |= {a.name for a in node.names if a.name.startswith("validation")}
    files = {name.replace("/", ".") + ".py" for name in imported}
    needed = {
        p.relative_to(driver.ROOT).as_posix()
        for p in (driver.ROOT / (n[:-3].replace(".", "/") + ".py") for n in files)
        if p.is_file()
    }
    assert needed and needed <= set(driver.DRIVERS)


def test_a_table_lists_what_is_missing_and_a_folders_sums_hold(invented, tmp_path):
    times = [k * 4e-05 for k in range(6)]
    folder = tmp_path / "runs"
    ionic_record(folder, invented, "inv_sample_sheet h=4e-05", times, [0.0, 8e-05, 0.00016])
    found = exporter.tables(invented, driver.Folders(folder))
    assert list(found) == ["jupiter", "cell", "base", "integrated"]
    assert found["integrated"]["missing"] == [sample.OFF_GRID]
    assert list(found["integrated"]["runs"]) == ["inv_sample_sheet h=4e-05"]
    jupiter = [r.name for r in invented.runs.values() if r.consumer == "jupiter"]
    assert found["jupiter"]["missing"] == jupiter and found["jupiter"]["runs"] == {}
    out = tmp_path / "table"
    exporter.write(found, out)
    assert exporter.check(out) == []
    sums = (out / "SHA256SUMS").read_text().splitlines()
    assert len(sums) == 4 and all(len(line.split("  ")) == 2 for line in sums)
    name = sums[0].split("  ")[1]
    (out / name).write_text((out / name).read_text() + " ")
    assert exporter.check(out) == [f"{name}: its sha256 is not in SHA256SUMS"]


# ------------------------------------------------------------------ the format sample


def test_the_committed_format_sample_is_the_contracts_and_no_number_is_a_runs():
    """TABLE §7: what the judge's reader is held to. Every number of it is a placeholder."""
    folder = Path(sample.__file__).parent / "format_sample"
    seen = set()
    for part in ("table", "table-retry"):
        assert exporter.check(folder / part) == []
        for path in (folder / part).glob("table_*.json"):
            for made in json.loads(path.read_text())["runs"].values():
                kind = made["refusal"]["kind"] if made["refusal"] else "completed"
                seen.add((part, kind, made["step_s"] is None, made["restart"] is not None))
                numbers = [v for held in made["rows"].values() for vs in held.values() for v in vs]
                assert set(numbers) <= {0.5}
                seen |= {"off_grid"} & set(made)
    for kind in ("completed", "definition", "domain", "check", "harness"):
        assert ("table", kind, False, False) in seen
    assert {("table", "completed", True, r) for r in (False, True)} <= seen
    assert ("table", "completed", False, True) in seen
    assert ("table-retry", "completed", False, False) in seen and "off_grid" in seen
    listed = (folder / "README.md").read_text().splitlines()
    for path, types in sample.keys(folder / "table").items():
        assert f"{path}: {', '.join(types)}" in listed
