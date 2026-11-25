"""The planted legacy runs of the rehearsal, each in its own process, from the frozen snapshot.

    plant_driver.py plan ORIGIN[:ORIGIN] PLAN   the plan: every planted run and every control
    plant_driver.py all PLAN OUT --cpus 6,7     run the plan, one process per run, one per CPU
    plant_driver.py one PLAN INDEX OUT          one run, in this process (what `all` starts)
    plant_driver.py manifest PLAN OUT POOLS F   F: plants_manifest_rehearsal.json, from the records

A planted run is the honest legacy definition of a world at the captured h/4 with one declared
change of the definition (`modify`), or with one host-side patch of an imported module of the
snapshot (`patch`, text of PLANTS.md's kind), never a change of the snapshot's tree. A control is
the same run with neither, and its arrays equal the honest run's bit for bit (reference.py). The
patch texts of the structural plants are the ones that spec/plants_manifest.json holds;
`patch_source` and `no_ledgers`, which they call, are written here anew.
"""

import argparse
import copy
import hashlib
import inspect
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parents[1] / "legacy_port" / "capture_worlds.py"
PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"
SNAPSHOT = Path("/mnt/workspaces/Cells/legacy-captures-20261125/snapshot-76a498ae")
# ------------------------------------------------------------------ the changes (PLANTS.md section
# 3 and 4)

KINETICS = """from cells.legacy.models import finite_extracellular as fin
orig = fin.kinetics
def kinetics(v, *, xp):
    targets, tau = orig(v, xp=xp)
    return targets, 1.01 * tau
fin.kinetics = kinetics
"""
ST1 = """from cells.legacy.models import junction_finite_extracellular as clu
orig = clu.initial_values
def initial_values(spec):
    state, layout = orig(spec)
    return state, layout._replace(stoichiometry=-layout.stoichiometry)
clu.initial_values = initial_values
"""
NO_LEDGERS = """
from cells.legacy.models import spatial_junction as spa, junction_finite_extracellular as clu2
from cells.legacy.models import finite_extracellular as fin2, kinetic_finite_extracellular as kin2
no_ledgers(spa, clu2, fin2, kin2)
"""
ST2 = """from cells.legacy.models import finite_extracellular as fin
orig = fin.ghk_leak
def ghk_leak(ci, co, voltage, valence, *a, **k):
    if getattr(valence, "ndim", 0) == 2:
        if isinstance(valence, np.ndarray):
            valence = valence.copy(); valence[2] = 1
        else:
            valence = valence.at[2].set(1)
    return orig(ci, co, voltage, valence, *a, **k)
fin.ghk_leak = ghk_leak
"""
ST3 = """from cells.legacy.models import finite_extracellular as fin, kinetic_finite_extracellular as kin
from cells.legacy.models import junction_finite_extracellular as clu, spatial_junction as spa
patch_source(fin, "channel_readouts", [("gate[..., 0, :] * gate[..., 1, :]", "gate[..., 0, :]")],
             aliases=(kin, clu, spa))
"""  # noqa: E501
ST4 = """from cells.legacy.models import finite_extracellular as fin
patch_source(fin, "junction_readouts", [(
    "        dv[..., None, :],\\n        layout.valence,",
    "        -dv[..., None, :],\\n        layout.valence,")])
"""
ST6 = """from cells.legacy.assembly_cluster import engine
orig = engine.channel_owners
def channel_owners(spec):
    r = orig(spec).copy()
    r[0], r[1] = r[1], r[0]
    return r
engine.channel_owners = channel_owners
"""
ST7 = """from cells.legacy.assembly_cell import kernel
def availability(pool, levels):
    cyclic = jax.lax.population_count(pool.bonds) >= jax.lax.population_count(pool.occupied)
    return jnp.where(cyclic, levels[0], levels[1])
kernel.availability = availability
"""
HELD = """from cells.legacy.%s import kernel
patch_source(kernel, "one_tick", [
    ("    target = (state.tick + jnp.uint32(1)).astype(jnp.float64) * dt\\n",
     "    target = (state.tick + jnp.uint32(1)).astype(jnp.float64) * dt\\n"
     "    held_opening = availability(state.pool, levels)\\n"),
    ("opening = availability(current.pool, levels)", "opening = held_opening")])
"""


def mul(path, factor=1.01):
    return {"path": path, "mul": factor}


def power_plants(ionic_prefix, kind):
    """{plant: (modify, patch)} of one world of a kind (PLANTS.md section 3)."""
    p = ionic_prefix
    leak = [mul(f"{p}/model/cells/*/membrane/passive/permeability_m_per_s/*")]
    channel = [mul(f"{p}/model/cells/*/channel/max_permeability_m_per_s")]
    pump = [mul(f"{p}/model/cells/*/membrane/pump/capacity_fmol_per_s")]
    junction = [mul(f"{p}/model/junctions/*/permeability_m_per_s/*")]
    jgate = [mul(f"{p}/model/junctions/*/gate/threshold_voltage_V")]
    face = [mul(f"{p}/model/faces/*/diffusivity_m2_per_s/*")]
    face_k = [mul(f"{p}/model/faces/*/diffusivity_m2_per_s/K")]
    out = dict(
        leak=(leak, None),
        channel=(channel, None),
        kinetics=([], KINETICS),
        pump=(pump, None),
        junction=(junction, None),
        jgate=(jgate, None),
        face=(face, None),
        faceK=(face_k, None),
    )
    keep = dict(
        jupiter=tuple(out),
        integrated=("junction", "jgate"),
        base=("leak", "channel", "kinetics", "pump", "junction", "jgate", "face"),
        cell=("leak", "channel", "kinetics", "pump"),
    )[kind]
    return {k: out[k] for k in keep}


def plan(origins):
    """Every planted run and control. `origins` is one origin folder, or several separated by `:`,
    of which the first that holds a world's definition is its base."""
    sys.path.insert(0, str(HERE))
    import make_inputs

    origins = [Path(o) for o in origins.split(":")]
    out = []

    def entry(name, world, modify=(), patch=None, plant=None):
        consumer = make_inputs.WORLDS[world]["consumer"]
        assembly = consumer in ("cell", "base")
        base = (
            f"science/assembly/{world}/h4-s0.json" if assembly else f"science/ionic/{world}/h4.json"
        )
        home = next(o for o in origins if (o / base).exists())
        out.append(
            dict(
                name=name,
                kind="assembly" if assembly else "ionic",
                command=dict(cell="assembly-cell", base="assembly-cluster").get(consumer),
                world=world,
                plant=plant,
                base=str(home / base),
                modify=list(modify),
                patch=patch,
            )
        )

    for world, w in make_inputs.WORLDS.items():
        prefix = "/ionic" if w["consumer"] in ("cell", "base") else ""
        entry(f"control {world} h4", world, plant="control")
        for plant, (modify, patch) in power_plants(prefix, w["consumer"]).items():
            entry(f"PW-{plant} {world}", world, modify, patch, plant)
    c = "inv_cluster"
    entry("ST1 pump direction", c, patch=ST1, plant="ST1")
    entry("ST1 pump direction, own ledgers off", c, patch=ST1 + NO_LEDGERS, plant="ST1 off")
    entry("ST2 leak valence of Cl", c, patch=ST2, plant="ST2")
    entry("ST3 inactivation gate left out", c, patch=ST3, plant="ST3")
    entry("ST4 junction voltage sign", c, patch=ST4, plant="ST4")
    entry("ST4 junction voltage sign, own ledgers off", c, patch=ST4 + NO_LEDGERS, plant="ST4 off")
    diff = next(iter(make_inputs.WORLDS[c]["faces"].values()))["diff"]
    entry(
        "ST5 Na and K face diffusivities exchanged",
        c,
        [
            {"path": "/model/faces/*/diffusivity_m2_per_s/Na", "set": diff["K"]},
            {"path": "/model/faces/*/diffusivity_m2_per_s/K", "set": diff["Na"]},
        ],
        plant="ST5",
    )
    entry("ST6 availability on the other cell's channel", "inv_base", patch=ST6, plant="ST6")
    entry("ST7 availability inverted", "inv_cell", patch=ST7, plant="ST7")
    entry(
        "ST8 pump released on one membrane",
        "inv_release",
        [
            {
                "path": "/experiment/membrane_controls/1/pump",
                "set": [{"multiplier": 1.0, "time": 0.0}],
            }
        ],
        plant="ST8",
    )
    entry(
        "ST9 the schedule is not applied",
        "inv_junctions",
        [{"path": "/experiment/junction_controls/*/schedule/*/open_fraction", "set": 1.0}],
        plant="ST9",
    )
    entry(
        "ST10 availability held over the step, base",
        "inv_base",
        patch=HELD % "assembly_cluster",
        plant="ST10",
    )
    entry(
        "ST10 availability held over the step, cell",
        "inv_cell",
        patch=HELD % "assembly_cell",
        plant="ST10",
    )
    return out


# ------------------------------------------------------------------ one run


def utc():
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=1, allow_nan=False) + "\n")


def apply_change(value, segments, item):
    """The number of leaves of `value` at the path that the change touches, changed in place."""
    head, *rest = segments
    if head == "*":
        keys = list(value) if isinstance(value, dict) else range(len(value))
    else:
        keys = [int(head)] if isinstance(value, list) else [head]
    count = 0
    for key in keys:
        if rest:
            count += apply_change(value[key], rest, item)
            continue
        if isinstance(value[key], bool) or (
            "mul" in item and not isinstance(value[key], (int, float))
        ):
            raise ValueError(f"no number at {key!r}")
        value[key] = value[key] * item["mul"] if "mul" in item else copy.deepcopy(item["set"])
        count += 1
    return count


def changed(definition, modify):
    out, leaves = copy.deepcopy(definition), []
    for item in modify:
        leaves.append(apply_change(out, item["path"].strip("/").split("/"), item))
    return out, leaves


def patch_source(module, name, edits, aliases=()):
    """Replace text in the source of a module's function and rebind it there and in the aliases."""
    source = textwrap.dedent(inspect.getsource(getattr(module, name)))
    for old, new in edits:
        if source.count(old) != 1:
            raise ValueError(f"{name}: {source.count(old)} places for {old!r}")
        source = source.replace(old, new)
    exec(compile(source, f"<patched {module.__name__}.{name}>", "exec"), module.__dict__)
    for alias in aliases:
        if hasattr(alias, name):
            setattr(alias, name, module.__dict__[name])


def no_ledgers(*modules):
    """Legacy's material, charge, energy and dissipation ledgers off; its domain checks stay on."""
    import numpy as np

    from cells.execution.errors import NumericalError
    from cells.legacy.models import finite_extracellular as fin

    names = (
        "max_balance_error_fmol",
        "max_extracellular_balance_error_fmol",
        "max_charge_balance_error_V",
        "max_energy_balance_error_pJ",
        "max_global_balance_error_fmol",
        "max_countercharge_error_C",
    )

    def check_accounting(
        state, spec, layout, valid, *, balances=fin.balances, dissipation_fields=()
    ):
        if not valid:
            raise NumericalError("Invalid finite-compartment state/domain; no repair")
        values = balances(state, layout)
        return dict(zip(names, (float(np.max(np.abs(v), initial=0)) for v in values), strict=True))

    for m in (fin, *modules):
        if hasattr(m, "check_accounting"):
            m.check_accounting = check_accounting


def one(plan_file, index, out):
    sys.path.insert(0, str(TOOL.parent))
    import capture_worlds as tool

    entry = json.loads(Path(plan_file).read_text())[index]
    folder = Path(out) / entry["name"]
    folder.mkdir(parents=True, exist_ok=False)
    started, began = utc(), time.monotonic()
    raw = json.loads(Path(entry["base"]).read_text())
    body = raw["definition"] if entry["kind"] == "ionic" else raw
    body, leaves = changed(body, entry["modify"])
    definition = dict(raw, definition=body) if entry["kind"] == "ionic" else body
    write_json(folder / "definition.json", definition)
    record = dict(
        name=entry["name"],
        kind=entry["kind"],
        world=entry["world"],
        plant=entry["plant"],
        base=entry["base"],
        base_sha256=sha256(entry["base"]),
        modify=entry["modify"],
        modified_leaves=leaves,
        patch=entry["patch"],
        command=[sys.executable, "-B", *sys.argv],
        environment={
            k: os.environ.get(k)
            for k in (
                "PYTHONPATH",
                "JAX_PLATFORMS",
                "JAX_ENABLE_X64",
                "JAX_ENABLE_COMPILATION_CACHE",
                "CUDA_VISIBLE_DEVICES",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            )
        },
        affinity=sorted(os.sched_getaffinity(0)),
        started=started,
    )
    outcome = "completed"
    try:
        if entry["patch"] is not None:
            import jax
            import jax.numpy as jnp
            import numpy as np

            exec(
                compile(entry["patch"], f"<patch {entry['name']}>", "exec"),
                dict(np=np, jax=jax, jnp=jnp, patch_source=patch_source, no_ledgers=no_ledgers),
            )
        if entry["kind"] == "ionic":
            code = tool.ionic(folder / "definition.json", folder / "run", tool.WINDOW_STEPS)
            run = json.loads((folder / "run" / "run.json").read_text())
            if "refusal" in run:
                outcome = f"refused: {run['refusal']['type']}: {run['refusal']['message']}"[:300]
            elif code or not run.get("complete"):
                outcome = "failed: incomplete"
        else:
            from cells.__main__ import main as cells_main

            code = cells_main(
                [
                    entry["command"],
                    "run",
                    str(folder / "definition.json"),
                    "--output",
                    str(folder / "run"),
                    "--backend",
                    "cpu",
                ]
            )
            failure = folder / "run" / "failure.json"
            if failure.exists():
                outcome = f"refused: {json.loads(failure.read_text())['error']}"[:300]
            elif code or not (folder / "run" / "completion.json").exists():
                outcome = "failed: incomplete"
            tool.drop_source_copy(SNAPSHOT, folder / "run")
    except Exception as error:  # The planted run's own refusal is an output: its type and message.
        outcome = f"refused: {type(error).__name__}: {error}"[:300]
    record.update(
        finished=utc(),
        seconds=time.monotonic() - began,
        outcome=outcome,
        definition_sha256=sha256(folder / "definition.json"),
        driver_sha256=sha256(__file__),
        capture_tool_sha256=sha256(TOOL),
        outputs_sha256={
            str(p.relative_to(folder)): sha256(p)
            for p in sorted(folder.rglob("*"))
            if p.is_file() and p.name not in ("plant.json",)
        },
        output_folder=str(folder),
    )
    write_json(folder / "plant.json", record)
    print(f"{utc()} {entry['name']}: {outcome}", flush=True)


# ------------------------------------------------------------------ the batch


def environment():
    env = {k: v for k, v in os.environ.items() if k not in ("XLA_FLAGS", "JAX_DISABLE_JIT")}
    env.update(
        PYTHONPATH=f"{SNAPSHOT}/src:{SNAPSHOT}",
        PYTHONDONTWRITEBYTECODE="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        JAX_ENABLE_COMPILATION_CACHE="false",
        CUDA_VISIBLE_DEVICES="",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    return env


def run_all(plan_file, out, cpus, seconds):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    entries = json.loads(Path(plan_file).read_text())
    todo = [i for i, e in enumerate(entries) if not (out / e["name"] / "plant.json").exists()]
    lock = threading.Lock()

    def worker(cpu):
        while True:
            with lock:
                if not todo:
                    return
                i = todo.pop(0)
            log = out / "logs" / f"{i:03d}.log"
            with log.open("wb") as stream:
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        str(cpu),
                        "nice",
                        "-n",
                        "10",
                        PYTHON,
                        "-B",
                        __file__,
                        "one",
                        str(plan_file),
                        str(i),
                        str(out),
                    ],  # fmt: skip
                    env=environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=seconds,
                )
            print(log.read_text(errors="replace").strip().splitlines()[-1:], flush=True)

    threads = [threading.Thread(target=worker, args=(c,)) for c in cpus]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    missing = [e["name"] for e in entries if not (out / e["name"] / "plant.json").exists()]
    (out / "EXIT").write_text(f"{1 if missing else 0} {utc()} missing {missing}\n")


def in_checkout(item):
    """A path of this checkout, from its top: the committed manifest holds no home path."""
    return item.removeprefix(str(HERE.parents[2]) + "/") if isinstance(item, str) else item


def manifest(plan_file, out, pools, target):
    entries = json.loads(Path(plan_file).read_text())
    runs = []
    for e in entries:
        r = json.loads((Path(out) / e["name"] / "plant.json").read_text())
        r["command"] = [in_checkout(v) for v in r["command"]]
        runs.append({k: v for k, v in r.items() if k not in ("plant", "world")})
    write_json(
        target,
        dict(
            schema="ensemble-reexpression plant manifest, version 1",
            part=1,
            snapshot="legacy-captures-20261125/snapshot-76a498ae",
            runs=runs,
            pool_plants=json.loads(Path(pools).read_text()),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action, names in (
        ("plan", ("origin", "plan")),
        ("one", ("plan", "index", "out")),
        ("manifest", ("plan", "out", "pools", "target")),
    ):
        s = sub.add_parser(action)
        for n in names:
            s.add_argument(n)
    s = sub.add_parser("all")
    s.add_argument("plan")
    s.add_argument("out")
    s.add_argument("--cpus", default="6,7,22,23")
    s.add_argument("--seconds", type=int, default=3600)
    a = parser.parse_args()
    if a.action == "plan":
        entries = plan(a.origin)
        write_json(a.plan, entries)
        print(f"{len(entries)} runs in {a.plan}")
    elif a.action == "one":
        one(a.plan, int(a.index), a.out)
    elif a.action == "all":
        run_all(a.plan, a.out, [int(c) for c in a.cpus.split(",")], a.seconds)
    else:
        manifest(a.plan, a.out, a.pools, a.target)
