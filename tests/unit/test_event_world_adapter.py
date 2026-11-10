"""Parity rung P3 event tooling (no BETSE; synthetic extractions).

default_world_adapter.betse_world's opt-in ``events`` keyword, event_world_adapter's
reading of BETSE's event parameters and target record, the emulator's event drive
(emulator/events.py, BETSE's pulse and order), and the resolved_pump_tissue@3 event
definitions, including the leak-population equivalence the Na/K mem mapping rests on.
"""

import copy
import hashlib
import json
import math

import jax
import numpy as np
import pytest

from tests.unit.test_default_world_adapter import AREA, MAMMAL, PROTOCOL, ROOT, write_case
from validation.betse import betse_reference_extract as ex
from validation.betse import cells_betse_compare as cmp
from validation.betse import default_world_adapter as adapter
from validation.betse import event_world_adapter as ewa
from validation.betse.emulator import events as ev
from validation.betse.emulator import junction, laws

TM = 7.5e-9  # write_case's membrane thickness
SPOT = [0]  # cell 0: membranes 0, 1, 2
SHARP = 1e-9  # change rate: exact 0/1 pulse values on the synthetic SIM labels
SIM_STEPS, SIM_DT = 3, 1e-4
MEM_PERMS = dict(zip(MAMMAL["species"], MAMMAL["dm"].tolist(), strict=True))


def options(**events):
    """BETSE global_options / scheduled_options with the given events on."""
    g = {k: 0 for k in ("Cl_env", "K_env", "NaKATP_block", "Na_env", "T_change", "gj_block")}
    s = {k: 0 for k in ("Ca_mem", "Cl_mem", "K_mem", "Na_mem", "ecmJ", "pressure")}
    for name, value in events.items():
        (g if name in g else s)[name] = value
    return {"global_options": g, "scheduled_options": s, "mem_perms": MEM_PERMS}


ON = ewa.aligned_time(1, SIM_STEPS, SIM_DT)  # effective from SIM update 1
NA_MEM = [ON, 1.0, SHARP, 9.0, ["Spot"], "None"]


def add_sim_arrays(extract, **arrays):
    """Rewrite sim_final.npz with extra arrays (e.g. Dm_base); the manifest stays valid."""
    manifest = json.loads((extract / "manifest.json").read_text())
    with np.load(extract / "sim_final.npz") as data:
        final = {k: data[k] for k in data.files} | arrays
    (extract / "sim_final.npz").unlink()
    manifest["files"]["sim_final.npz"] = ex.write_npz(
        extract / "sim_final.npz", {k: (v, {"units": "x"}) for k, v in final.items()}
    )
    (extract / "manifest.json").write_text(json.dumps(manifest))


def event_case(root, name="case", *, spot=SPOT, yaml_cells=None, **events):
    case = root / name
    case.mkdir()
    dm = np.repeat(MAMMAL["dm"][:, None], AREA.size, axis=1)
    extract = write_case(case / "extract", ions=MAMMAL, params=options(**events))
    add_sim_arrays(extract, Dm_base=dm)
    (case / "inputs" / "config").mkdir(parents=True)
    listed = spot if yaml_cells is None else yaml_cells
    (case / "inputs" / "config" / "sim_config.yaml").write_text(
        f"        cell targets:\n          type: indices\n          indices: {json.dumps(listed)}\n"
    )
    record = {"kind": ewa.TARGETS_KIND, "profiles": {"Spot": spot}, "sim_steps": SIM_STEPS,
              "sim_dt_s": SIM_DT}  # fmt: skip
    (case / "inputs" / ewa.TARGETS_FILE).write_text(json.dumps(record))
    return case


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    jax.config.update("jax_enable_x64", True)
    root = tmp_path_factory.mktemp("events")
    return {
        "plain": write_case(root / "plain", ions=MAMMAL),
        "na": event_case(root, "na", Na_mem=NA_MEM),
        "pump": event_case(root, "pump", NaKATP_block=[ON, 1.0, SHARP]),
        "both": event_case(
            root,
            "both",
            Na_mem=NA_MEM,
            NaKATP_block=[ON, 1.0, SHARP],
            gj_block=[ON, 1.0, SHARP, 100],
        ),
    }


def same_world(a, b):
    assert set(a) == set(b)
    for key in a:
        if isinstance(a[key], dict) and key not in ("time",):
            assert set(a[key]) == set(b[key])
            for k in a[key]:
                assert np.array_equal(np.asarray(a[key][k]), np.asarray(b[key][k])), (key, k)
        elif isinstance(a[key], np.ndarray):
            assert np.array_equal(a[key], b[key]), key
        else:
            assert a[key] == b[key], key


def test_events_keyword_is_off_by_default_and_changes_nothing_without_events(cases):
    plain = cases["plain"]
    for blind in (False, True):
        same_world(
            adapter.betse_world(plain, blind=blind),
            adapter.betse_world(plain, blind=blind, events=True),
        )
    with pytest.raises(adapter.AdapterError, match=r"BETSE events \['Na_mem'\] are on"):
        adapter.betse_world(cases["na"] / "extract")
    with pytest.raises(adapter.AdapterError, match="NaKATP_block"):
        adapter.betse_world(cases["both"] / "extract", blind=True)


def test_events_keyword_takes_betse_base_permeability_in_sim(cases, tmp_path):
    world = adapter.betse_world(cases["na"] / "extract", events=True)
    base = MAMMAL["dm"][:, None] / TM
    for phase in adapter.PHASES:
        np.testing.assert_array_equal(
            world["membrane_permeability_m_s"][phase], np.broadcast_to(base, (6, AREA.size))
        )
    other = event_case(tmp_path, Na_mem=NA_MEM)
    add_sim_arrays(
        other / "extract", Dm_base=2 * np.repeat(MAMMAL["dm"][:, None], AREA.size, axis=1)
    )
    with pytest.raises(adapter.AdapterError, match="Dm_base differs"):
        adapter.betse_world(other / "extract", events=True)


def betse_pulse(t, t_on, t_off, t_change):
    """betse/science/math/toolbox.py pulse, verbatim."""
    g = (1 / t_change) * 10
    y1 = 1 / (1 + (np.exp(-g * (t - t_on))))
    y2 = 1 / (1 + (np.exp(-g * (t - t_off))))
    return y1 - y2


def test_pulse_is_betses_and_aligned_sharp_edges_are_exact_steps():
    t = np.linspace(0, 350 * 1e-4, 350)
    for args in ((0.005, 0.02, 1e-3), (0.0101, 0.03, 2.5e-4)):
        assert np.array_equal(ev.pulse(t, *args), betse_pulse(t, *args))
    on, off = ewa.aligned_time(50, 350, 1e-4), ewa.aligned_time(250, 350, 1e-4)
    v = ev.pulse(t, on, off, 1e-7)
    assert np.array_equal(v, (np.arange(350) >= 50) & (np.arange(350) < 250))
    assert t[49] < on < t[50] and t[249] < off < t[250]
    with pytest.raises(ewa.EventError):
        ewa.aligned_time(0, 350, 1e-4)


def test_event_world_reads_betse_parameters_and_the_target_record(cases):
    world = ewa.event_world(cases["both"])
    rows = {row["name"]: row for row in world["events"]}
    assert set(rows) == {"NaKATP_block", "gj_block", "Na_mem"}
    na = rows["Na_mem"]
    assert na["membranes"] == [0, 1, 2] and na["cells"] == SPOT and na["multiplier"] == 9.0
    assert na["dm_default_m2_s"] == MEM_PERMS["Na"] and na["species"] == 0
    assert rows["gj_block"]["membranes"] == list(range(AREA.size))
    values = ewa.event_values(world, "sim")
    assert np.array_equal(values, np.repeat([[0.0], [1.0], [1.0]], 3, axis=1))
    assert not ewa.event_values(world, "init").any()
    nominal = ewa.event_values(world, "sim", clock="nominal")
    assert nominal.shape == values.shape
    shifted = ewa.event_values(world, "sim", shift=1)
    assert np.array_equal(shifted[:, 0], [0.0, 0.0, 1.0])
    blind = ewa.event_world(cases["both"], blind=True)
    assert blind["events"] == world["events"]


@pytest.mark.parametrize(
    "events, message",
    [
        ({"K_env": [ON, 1.0, SHARP, 20]}, "K_env"),
        ({"gj_block": [ON, 1.0, SHARP, 50]}, "100%"),
        ({"Na_mem": [ON, 1.0, SHARP, -0.5, ["Spot"], "None"]}, "negative"),
        ({"Na_mem": [ON, 1.0, SHARP, 9.0, ["Spot"], "gradient_x"]}, "modulator"),
        ({"Na_mem": [ON, 1.0, SHARP, 9.0, ["Zone"], "None"]}, "Zone"),
    ],
)
def test_unmapped_events_are_refused(tmp_path, events, message):
    with pytest.raises(ewa.EventError, match=message):
        ewa.event_world(event_case(tmp_path, **events))


def test_target_record_must_match_the_prepared_yaml(tmp_path):
    with pytest.raises(ewa.EventError, match="not found in the prepared YAML"):
        ewa.event_world(event_case(tmp_path, yaml_cells=[1], Na_mem=NA_MEM))


def test_emulator_drive_follows_betse_order(cases):
    world = ewa.event_world(cases["both"])
    drive = ewa.emulator_drive(world, "sim")
    base = np.repeat(MAMMAL["dm"][:, None], AREA.size, axis=1)
    assert np.array_equal(drive.pump, np.repeat([[1.0], [0.0], [0.0]], AREA.size, axis=1))
    assert np.array_equal(drive.junction, drive.pump)
    expect = base[None].repeat(3, axis=0)
    expect[1:, 0, :3] = 9.0 * 1.0 * MEM_PERMS["Na"] + base[0, :3]
    assert np.array_equal(drive.permeability, expect / TM)
    init = ewa.emulator_drive(world, "init")
    assert np.all(init.pump == 1) and np.all(init.junction == 1)
    assert np.array_equal(init.permeability[0], base / TM)


def test_constant_drive_is_the_plain_emulator_step(cases):
    world = ewa.event_world(cases["na"])
    variant = laws.default_world("betse")
    start = adapter.phase_start(world, "sim")
    state, p, _ = adapter.emulator_inputs(world, "sim", start, variant)
    drive = ewa.emulator_drive(world, "sim")
    control = junction.Control(*(np.ones(AREA.size) for _ in junction.Control._fields))
    plain = junction.step(state, p, SIM_DT, control, xp=np, variant=variant)
    first = ev.step(state, p, SIM_DT, jax.tree.map(lambda v: v[0], drive), xp=np, variant=variant)
    for a, b in zip(jax.tree.leaves(plain), jax.tree.leaves(first), strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b))
    second = ev.step(state, p, SIM_DT, jax.tree.map(lambda v: v[1], drive), xp=np, variant=variant)
    rates = second[1].active.ordinary.membrane_inward_fmol_s
    assert not np.allclose(rates[0, :3], plain[1].active.ordinary.membrane_inward_fmol_s[0, :3])
    np.testing.assert_array_equal(rates[1:], plain[1].active.ordinary.membrane_inward_fmol_s[1:])


def test_emulator_shares_init_and_runs_sim_per_case(cases, tmp_path):
    records = ewa.run_event_emulator(
        [cases["na"], cases["pump"]], PROTOCOL, tmp_path / "emu", constants="betse",
        device_kind="cpu", sim_start="chained",
    )  # fmt: skip
    assert set(records) == {"na", "pump"} and all(r["valid"] for r in records.values())
    a, b = (np.load(tmp_path / "emu" / n / "init_history.npz") for n in ("na", "pump"))
    assert all(np.array_equal(a[k], b[k]) for k in a.files)
    a, b = (np.load(tmp_path / "emu" / n / "sim_history.npz") for n in ("na", "pump"))
    assert not np.array_equal(a["vm_time"], b["vm_time"])
    assert records["na"]["phases"]["sim"]["event_values"][0]["first_update_nonzero"] == 1
    other = event_case(tmp_path, "other", Na_mem=NA_MEM)
    world = ewa.event_world(other)
    world["initial_cell_mM"] = world["initial_cell_mM"] * 1.01
    with pytest.raises(ewa.EventError, match="INIT inputs differ"):
        ewa._shared_init([ewa.event_world(cases["na"]), world])


def test_resolved_definition_maps_events_to_controls_and_leaks(cases):
    from cells.core.specs import parse_spec

    world = ewa.event_world(cases["both"], blind=True)
    sim = ewa.resolved_event_definition(
        world, "sim", adapter.phase_start(world, "init"), dt=SIM_DT / 2
    )
    model, experiment = sim["model"], sim["experiment"]
    assert model["id"] == "resolved_pump_tissue@3" and sim["execution"]["channel_capacity"] == 3
    for c, j in zip(model["channels"], [0, 1, 2], strict=True):
        assert c["membrane_id"] == f"mem-{j}" and c["kinetic_law"] == "naleak_always_open@1"
        assert c["max_permeability_m_per_s"] == 9.0 * MEM_PERMS["Na"] / TM
    change = 2 * (SIM_DT / 2)  # update 1 at integer * Cells dt
    for group in experiment["channel_controls"]:
        assert group["schedule"] == [
            {"time": 0.0, "availability": 0.0},
            {"time": change, "availability": 1.0},
        ]
    for group in experiment["pump_controls"] + experiment["junction_controls"]:
        assert group["schedule"] == [
            {"time": 0.0, "availability": 1.0},
            {"time": change, "availability": 0.0},
        ]
    assert all(
        g["schedule"] == [{"time": 0.0, "availability": 1.0}]
        for g in experiment["calcium_pump_controls"]
    )
    parse_spec(sim)
    init = ewa.resolved_event_definition(world, "init", adapter.phase_start(world, "init"), dt=1e-3)
    assert init["model"]["channels"] == [] and init["experiment"]["channel_controls"] == []
    assert all(len(g["schedule"]) == 1 for g in init["experiment"]["pump_controls"])
    parse_spec(init)


def test_resolved_definition_refuses_what_cells_cannot_express(tmp_path):
    released = ewa.event_world(
        event_case(tmp_path, "rel", gj_block=[ON, ewa.aligned_time(2, 3, SIM_DT), SHARP, 100]),
        blind=True,
    )
    start = adapter.phase_start(released, "init")
    with pytest.raises(ewa.EventError, match="held to the end"):
        ewa.resolved_event_definition(released, "sim", start, dt=SIM_DT)
    chloride = ewa.event_world(
        event_case(tmp_path, "cl", Cl_mem=[ON, 1.0, SHARP, 9.0, ["Spot"], "None"]), blind=True
    )
    assert (
        ewa.emulator_drive(chloride, "sim").permeability[1, 2, 0]
        > ewa.emulator_drive(chloride, "sim").permeability[0, 2, 0]
    )
    with pytest.raises(ewa.EventError, match="no Cl leak law"):
        ewa.resolved_event_definition(chloride, "sim", start, dt=SIM_DT)
    with pytest.raises(ewa.EventError, match="divide"):
        ewa.control_times(chloride, "sim", 3e-5)


def test_leak_population_equals_the_added_passive_permeability(cases):
    """The Na/K mem mapping: passive P plus an always-open leak m P is passive (1 + m) P."""
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    world = ewa.event_world(cases["na"], blind=True)
    start = adapter.phase_start(world, "init")
    leak = ewa.resolved_event_definition(world, "sim", start, dt=SIM_DT)
    for group in leak["experiment"]["channel_controls"]:
        group["schedule"] = [{"time": 0.0, "availability": 1.0}]
    passive = copy.deepcopy(leak)
    passive["model"]["channels"], passive["experiment"]["channel_controls"] = [], []
    passive["execution"]["channel_capacity"] = 0
    for j in (0, 1, 2):
        row = passive["model"]["membranes"][j]["permeability_m_per_s"]
        row["Na"] = row["Na"] + 9.0 * MEM_PERMS["Na"] / TM
    a, b = (run(parse_spec(d)) for d in (leak, passive))
    for name in ("amount", "extracellular_amount", "membrane_voltage_V"):
        x, y = (np.asarray(getattr(r.observations, name)) for r in (a, b))
        scale = np.abs(y).max()
        assert np.abs(x - y).max() <= 1e-12 * scale, name
    moved = np.asarray(a.observations.amount)[-1] - np.asarray(a.observations.amount)[0]
    assert np.abs(moved[0]).max() > 0  # the Na leak moved material
    assert math.isfinite(float(np.asarray(a.observations.membrane_voltage_V).max()))


def test_resolved_runs_share_init_and_write_one_layout_per_case(cases, tmp_path):
    runs = ewa.run_resolved_events(
        [cases["na"], cases["pump"]], tmp_path / "res", device_kind="cpu", window_steps=2,
        dt_init=1e-3, dt_sim=SIM_DT,
    )  # fmt: skip
    assert all(r["valid"] for r in runs.values()) and set(runs) == {"na", "pump"}
    for name in runs:
        manifest = json.loads(
            (tmp_path / "res" / name / "layout" / "comparison_manifest.json").read_text()
        )
        assert manifest["protocol_sha256"] is None
        assert runs[name]["phases"]["sim"]["channel_populations"] == (3 if name == "na" else 0)
    a, b = (np.load(tmp_path / "res" / n / "layout" / "init_history.npz") for n in runs)
    assert all(np.array_equal(a[k], b[k]) for k in a.files)
    rows = runs["pump"]["phases"]["sim"]["newton_at_window_ends"]
    assert all(r["converged"] for r in rows)


def test_no_event_case_maps_to_no_events(cases):
    world = ewa.event_world(cases["plain"], blind=True)
    assert world["events"] == [] and world["event_targets"]["path"] is None
    assert not ewa.event_values(world, "sim").size
    drive = ewa.emulator_drive(world, "sim")
    assert np.all(drive.pump == 1) and np.all(drive.junction == 1)
    ewa._shared_init([world, ewa.event_world(cases["na"], blind=True)])


def test_field_propagation_events_runner_is_the_event_emulator(cases, tmp_path):
    from validation.betse import field_propagation as fp

    ewa.run_event_emulator(
        [cases["both"]], PROTOCOL, tmp_path / "emu", constants="betse", device_kind="cpu",
        sim_start="chained",
    )  # fmt: skip
    record = fp.run_propagation(
        cases["both"], PROTOCOL, None, tmp_path / "base", mode="base", runner_name="events"
    )
    assert record["valid"] and record["runner"] == "events"
    for phase in adapter.PHASES:
        a = np.load(tmp_path / "emu" / "both" / f"{phase}_history.npz")
        b = np.load(tmp_path / "base" / f"{phase}_history.npz")
        for name in a.files:
            assert np.array_equal(a[name], b[name]), (phase, name)


def test_judged_runs_name_their_protocols_and_are_judgeable(cases, tmp_path):
    """The judged path: one protocol per case, each layout carries its sha256, the comparator
    accepts it (either verdict: synthetic data), and a mismatched protocol refuses early."""
    template = json.loads(
        (ROOT / "validation/betse/protocols/physical_p4_kleak_dense.json").read_text()
    )
    paths = []
    for name in ("na", "pump"):
        protocol = copy.deepcopy(template) | {"id": f"synthetic-{name}", "betse_case": "synthetic"}
        protocol["cells_run"] |= {
            "model": ewa.RESOLVED_MODEL_ID,
            "field_solver": adapter.RESOLVED_FIELD_SOLVER,
            "dt_init_s": 1e-3,
            "dt_sim_s": SIM_DT,
            "backends": ["cpu"],
        }
        paths.append(tmp_path / f"{name}.json")
        paths[-1].write_text(json.dumps(protocol))
    options = dict(device_kind="cpu", window_steps=2, dt_init=1e-3, protocol_paths=paths)
    runs = ewa.run_resolved_events(
        [cases["na"], cases["pump"]], tmp_path / "judged", dt_sim=SIM_DT, **options
    )
    for name, path in zip(("na", "pump"), paths, strict=True):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        layout = tmp_path / "judged" / name / "layout"
        manifest = json.loads((layout / cmp.LAYOUT_MANIFEST).read_text())
        assert runs[name]["protocol"]["sha256"] == sha == manifest["protocol_sha256"]
        result = cmp.run_comparison(cases[name], layout, path)
        assert not result["refusals"] and result["verdict"] in ("pass", "fail")
    with pytest.raises(adapter.AdapterError, match="dt_sim_s"):
        ewa.run_resolved_events(
            [cases["na"], cases["pump"]], tmp_path / "refused", dt_sim=SIM_DT / 2, **options
        )
    assert not (tmp_path / "refused").exists()
