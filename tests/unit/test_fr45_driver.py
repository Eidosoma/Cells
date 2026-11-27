"""FR-45's driver and exporter (validation/fr45/driver.py, exporter.py) on two invented worlds, each run in its own
process as the judged run runs them: a W2-shaped world through its wash, and a W5-shaped world refused by the stage
condition at its first step. The judge then finds no fault of §11.1 in either run (but the checkout's own state),
both variants of the wash's map leave every site amount unchanged (C6), and the refusal meets C7.

Seconds and reason (D224): about 40 s on two cores, two engine runs in their own processes, each compiled once.
The driver is the only path from a world to the table, and the dress rehearsal is too long to gate on.
"""

import copy
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RT = 6.02214076e23 * 1.380649e-23 * 301.5 * 1e-3


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def world(name, node, volume, amounts, set_, populations, dt, times, wash=None):
    """An invented world in TABLE §4.1's shape, in the bath form (host entities named as §4.1 names them)."""
    ligands = list(amounts)
    nodes = [
        (node, "node", volume, True),
        ("bath", "node", 140.0, False),
        ("host_cell", "cell", 0.007, False),
    ]
    return dict(
        world=f"INVENTED-{name}",
        constants=dict(sites_per_fmol=602214076.0, temperature_K=301.5, RT_pJ_per_fmol=RT),
        nodes=[dict(id=i, kind=k, volume_pL=v, registered=r) for i, k, v, r in nodes],
        patches=[dict(id="host_wall", inside="host_cell", outside="bath"),
                 dict(id="host_contact", inside="host_cell", outside=node)],
        ligands=ligands,
        free_amounts=[dict(ligand=lig, node=node, n_fmol=n, declared=True) for lig, n in amounts.items()]
        + [dict(ligand=lig, node=i, n_fmol=1e-12 * v, declared=False) for lig in ligands for i, _, v, r in nodes
           if not r],
        sets=[dict(id=set_[0], shared=True, owner=node, face=None, faces=node, copies=set_[1], sites_per_copy=set_[2],
                   accessible_fraction=set_[3])],
        populations=[dict(id=f"{set_[0]}_{lig}", set=set_[0], ligand=lig, k_on=k_on, k_off=k_off,
                          initial_occupancy=theta) for lig, (k_on, k_off, theta) in populations.items()],
        wash=wash,
        permeabilities=[dict(patch=p, ligand=lig, value=0.0) for p in ("host_wall", "host_contact") for lig in ligands],
        ion_permeabilities={p: {"IA": 0.0, "IB": 0.0} for p in ("host_wall", "host_contact")},
        multipliers=[dict(of=f"{set_[0]}_{lig}", name="site_binding_multiplier", value=1.0) for lig in populations],
        charges={lig: 0 for lig in ligands},
        capacitor_components=[dict(members=["bath", "host_cell", node], held_by="bath")],
        host_values=dict(areas=dict(host_wall=21.8, host_contact=14.3), capacitances=dict(host_wall=0.218,
                         host_contact=0.143), ion_amounts={c: dict(IA=0.03, IB=0.003) for c in (node, "bath",
                         "host_cell")}),
        dt_s=dt, observation_times_s=times, horizon_s=times[-1] if times else 1.0,
    )  # fmt: skip


W2 = world("W2", "pool", 2.0, dict(X1=0.004, X2=0.003), ("lattice", 2.0e6, 4, 0.5),
           dict(X1=(800.0, 0.4, 0.1), X2=(500.0, 0.2, 0.05)), 0.01, [0.04, 0.08, 0.09, 0.12],
           wash=dict(time_s=0.08, node="pool", fraction=0.3, buffer_mM=dict(X1=1e-12, X2=0.0002)))  # fmt: skip
W5 = world("W5", "cup", 1.25, dict(X1=0.00153, X2=0.0013), ("seat", 777.0, 9, 0.93),
           dict(X1=(6700.0, 0.19, 0.0043), X2=(6600.0, 0.23, 0.006)), 0.1, [])  # fmt: skip
OPERATORS = ["cells.model.resolved_pump_composite@1", "cells.model.resolved_pump_tissue@3",
             "cells.operator.site_occupancy@1"]  # fmt: skip
REGISTRATION = dict(
    runs={"W2": dict(world="W2", plant=None, dt_s=0.01), "W5": dict(world="W5", plant=None, dt_s=0.1)},
    rows={"W2": {"0.01": [[0.0, 0], [0.04, 4], [0.08, 8], [0.09, 9], [0.12, 12]]},
          "W5": {"0.1": [[0.0, 0], [1.0, 10]]}},
    wash={"W2": dict(time_s=0.08)}, maps={"W2": [0.08]}, files={"W2": "W2", "W5": "W5"},
    heat_nodes={"W2": ["pool"], "W5": ["cup"]},
    operators={"W2": [*OPERATORS, "cells.operator.scheduled_compartment_wash@1"], "W5": OPERATORS}, plants=[],
)  # fmt: skip


def _drive(job, folder):
    path = folder / "jobs" / f"{job['run']}.json"
    path.write_text(json.dumps(job))
    env = dict(
        os.environ,
        PYTHONPATH=f"{ROOT / 'src'}{os.pathsep}{ROOT}",
        JAX_ENABLE_X64="1",
        JAX_PLATFORMS="cpu",
    )
    command = [sys.executable, "-B", "-m", "validation.fr45.driver", "run", str(path),
               str(folder / "records" / f"{job['run']}.json")]  # fmt: skip
    return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)


def test_two_invented_runs_through_the_driver_exporter_and_judge(tmp_path):
    (tmp_path / "jobs").mkdir()
    (tmp_path / "records").mkdir()
    jobs = [
        dict(run=w["world"], inputs=w, plant=None, start=None, time_limit_step=None)
        for w in (W2, W5)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        done = list(pool.map(lambda job: _drive(job, tmp_path), jobs))
    assert all(d.returncode == 0 for d in done), [d.stderr[-2000:] for d in done]
    exporter = _load("fr45_exporter_under_test", ROOT / "validation" / "fr45" / "exporter.py")
    table = exporter.export(
        tmp_path / "records", tmp_path / "table", [j["run"] for j in jobs], invented="INVENTED"
    )
    J = _load("fr45_judge_under_test_driver", ROOT / "validation" / "fr45" / "judge.py")
    agreement = J.load_by_path(
        "fr45_agreement_driver", ROOT / "validation" / "assembly_lineages_v2" / "agreement.py"
    )
    env = J.Env(table, {}, J.Registration(REGISTRATION, "INVENTED-"), agreement, None)
    J.identity(env)
    assert [f for f in env.faults if f["item"] != 11] == []
    w2, w5 = table["runs"]["INVENTED-W2"], table["runs"]["INVENTED-W5"]
    assert all(
        r["source"]["jax_enable_x64"] and r["source"]["jax_platforms"] == "cpu" for r in (w2, w5)
    )
    # The echo against the world as an expected-inputs entry holds it: the host values are the host-entity
    # addendum's (the engine's own ions among them), so they are markers here; every ion's permeability is 0.0.
    want = copy.deepcopy(W2)
    markers = dict(volume="addendum", trace="addendum trace", host_values="addendum")
    want["host_values"] = "addendum"
    for node in want["nodes"]:
        node["volume_pL"] = node["volume_pL"] if node["registered"] else "addendum"
    want["ion_permeabilities"] = {patch: {"each_ion": 0.0} for patch in want["ion_permeabilities"]}
    assert J.Echo(markers).compare(w2["inputs"], want).departures == []
    for obs in ("R:lattice", "B:lattice_X1", "B:lattice_X2"):
        c6 = {
            "criterion": "C6",
            "observable": obs,
            "time_s": 0.08,
            "class": "constant",
            "value": "unchanged",
        }
        assert J._value(env, "W2", c6, "W2", w2)["passes"] is True
    assert J._c7(w5)["passes"] is True
    assert J.mapped(w5["refusal"]) == ("stage", None) and w5["step_report"]["verdict"] == "refused"
