"""The planted legacy runs of Part 2's rehearsal, from the frozen snapshot.

    plant_driver2.py plan ORIGIN PLAN            the plan: every planted run and every control
    plant_driver2.py all PLAN OUT --cpus 12,13   run the plan, one process at a time on each CPU
    plant_driver2.py some PLAN I,J,... OUT       some runs, in this process (what `all` starts)
    plant_driver2.py manifest PLAN OUT F         F: plants_manifest_rehearsal_part2.json

A planted run is the honest legacy definition of a world at the captured h (PART2.md section 7.2)
with one declared change of the definition (`modify`), or with one host-side patch of an imported
module of the snapshot (`patch`), never a change of the snapshot's tree. A control is the same run
with neither, and its arrays equal the honest run's bit for bit (reference2.py). The patch texts are
the ones that spec/plants_manifest_part2.json holds. The numbers of SC12, SC13 and the two refused
runs are this rehearsal's. `patch_source` is Part 1's driver's, and `no_ledgers` is written here for
the calcium models: legacy's own ledgers off, its domain checks on.

A patched run has a process of its own. The runs of one world that change the definition alone run
one after another in one process, which compiles once, with the world's control first (and for the
four children a second control last).
"""

import argparse
import json
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "rehearsal"))
sys.path.insert(0, str(HERE))
import plant_driver as part1  # noqa: E402

PYTHON, SNAPSHOT, TOOL = part1.PYTHON, part1.SNAPSHOT, part1.TOOL
utc, sha256, write_json, changed = part1.utc, part1.sha256, part1.write_json, part1.changed
in_checkout, environment = part1.in_checkout, part1.environment

# ------------------------------------------------------------------ the changes (PART2.md 7.2, 7.3)

KINETICS = part1.KINETICS
CAV_KINETICS = """from cells.legacy.models import gated_calcium as gm
orig = gm.gates.kinetics
def kinetics(v, *, xp):
    targets, tau = orig(v, xp=xp)
    return targets, 1.01 * tau
gm.gates.kinetics = kinetics
"""
SC1 = """from cells.legacy.models import er_calcium as er
er.processes.release_open = lambda ca, *a, xp, **k: xp.ones_like(ca)
"""
SC2 = """from cells.legacy.models import ip3_calcium as ip3
ip3.process.open_fraction = lambda c, *a, xp, **k: xp.ones_like(c)
"""
SC3 = """from cells.legacy.models import er_calcium as er, spatial_calcium as sp
orig = er.voltage
er.voltage = lambda state, p, *, xp: -orig(state, p, xp=xp)
no_ledgers(sp, er)
"""
SC3B = """from cells.legacy.models import er_calcium as er, spatial_calcium as sp
orig = er.ghk_leak
def ghk_leak(ci, co, voltage, valence, *a, **k):
    if isinstance(valence, int): return orig(ci, co, -voltage, valence, *a, **k)
    flip = np.ones(valence.shape[-1]); flip[1] = -1.0
    return orig(ci, co, voltage * flip, valence, *a, **k)
er.ghk_leak = ghk_leak
no_ledgers(sp, er)
"""
SC4 = """from cells.legacy.models import er_calcium as er, spatial_calcium as sp
orig = er.processes.pump_rates
def pump_rates(cytosol, store, voltage, temperature, p, availability, *, xp):
    rate, energy, drive = orig(store, cytosol, -voltage, temperature, p, availability, xp=xp)
    return -rate, -energy, drive
er.processes.pump_rates = pump_rates
no_ledgers(sp, er)
"""
SC5 = """from cells.legacy.models import er_calcium as er, spatial_calcium as sp
orig = er.ghk_leak
def ghk_leak(ci, co, voltage, valence, *a, **k):
    if isinstance(valence, int): valence = 1
    elif isinstance(valence, np.ndarray):
        valence = valence.copy(); valence[1] = 1.0
    else: valence = valence.at[1].set(1.0)
    return orig(ci, co, voltage, valence, *a, **k)
er.ghk_leak = ghk_leak
no_ledgers(sp, er)
"""
SC6 = """from cells.legacy.models import compartment_reactions as ch, er_calcium as er, spatial_calcium as sp
orig = ch.reversible_flux
def reversible_flux(activity, reactants, products, delta_mu_RT, scale, *, xp):
    if isinstance(reactants, np.ndarray):
        r = reactants.copy(); r[1, 0] += 1.0
    else: r = reactants.at[1, 0].add(1.0)
    return orig(activity, r, products, delta_mu_RT, scale, xp=xp)
ch.reversible_flux = reversible_flux
no_ledgers(ch, er, sp)
"""  # noqa: E501
SC7 = """from cells.laws.reactions import plasma_calcium as lp
patch_source(lp, "exchange_rates", [("3 * lni, 3 * lno", "2 * lni, 2 * lno"), ("3 * lno + lci", "2 * lno + lci")])
from cells.legacy.models import plasma_calcium as pl, spatial_calcium as sp
no_ledgers(pl, sp)
"""  # noqa: E501
SC8 = """from cells.laws.reactions import plasma_calcium as lp
from cells.legacy.models import plasma_calcium as pl, spatial_calcium as sp
orig = lp.er_calcium.pump_rates
def pump_rates(ci, co, voltage, temperature, p, availability, *, xp):
    rate, energy, drive = orig(co, ci, voltage, temperature, p, availability, xp=xp)
    return -rate, -energy, drive
lp.pump_rates = pump_rates
no_ledgers(pl, sp)
"""
SC9 = """from cells.legacy.models import gated_calcium as gm
gm.gates.open_probability = lambda g: g[..., 0, :] ** 2
"""
SC10 = """from cells.legacy.models import gated_calcium as gm
gm.gates.open_probability = lambda g: g[..., 0, :] * g[..., 1, :]
"""
SC11 = """from cells.legacy.assembly_cluster import kernel
orig = kernel.modulate
def modulate(control, opening, owners):
    out = orig(control, opening, owners)
    n = out.calcium_channel.shape[-1]
    cell = jnp.minimum(jnp.arange(n), opening.shape[0] - 1)
    return out._replace(calcium_channel=out.calcium_channel * opening[cell])
kernel.modulate = modulate
"""
SC14 = part1.ST6

mul = part1.mul


def power_plants(world):
    """{plant: (modify, patch)} of a world, by its kind (PART2.md section 7.2)."""
    ionic, store = "/model/ionic", "/model/stores/*/model"
    membrane, plasma = f"{store}/membrane", "/model/plasma_transport/membranes/*"
    leak = f"{ionic}/cells/*/membrane/passive/permeability_m_per_s"
    out = dict(
        leak=[mul(f"{leak}/*")],
        channel=[mul(f"{ionic}/cells/*/channel/max_permeability_m_per_s")],
        pump=[mul(f"{ionic}/cells/*/membrane/pump/capacity_fmol_per_s")],
        junction=[mul(f"{ionic}/junctions/*/permeability_m_per_s/*")],
        jgate=[mul(f"{ionic}/junctions/*/gate/threshold_voltage_V")],
        face=[mul(f"{ionic}/faces/*/diffusivity_m2_per_s/*")],
        faceK=[mul(f"{ionic}/faces/*/diffusivity_m2_per_s/K")],
        kinetics=KINETICS,
        leakCa=[mul(f"{leak}/Ca")],
        junctionCa=[mul(f"{ionic}/junctions/*/permeability_m_per_s/Ca")],
        faceCa=[mul(f"{ionic}/faces/*/diffusivity_m2_per_s/Ca")],
        storeleakCa=[mul(f"{membrane}/permeability_m_per_s/Ca")],
        storeleakK=[mul(f"{membrane}/permeability_m_per_s/K")],
        storepump=[mul(f"{membrane}/pump/capacity_fmol_per_s")],
        release=[mul(f"{membrane}/release/permeability_m_per_s")],
        activation=[mul(f"{membrane}/release/activation_mM")],
        inhibition=[mul(f"{membrane}/release/inhibition_mM")],
        bind0a=[mul(f"{store}/reactions/0/forward_rate_per_s")],
        bind0b=[mul(f"{store}/reactions/1/forward_rate_per_s")],
        bind1a=[mul(f"{store}/reactions/2/forward_rate_per_s")],
        bind1b=[mul(f"{store}/reactions/3/forward_rate_per_s")],
        storecap=[mul(f"{membrane}/specific_capacitance_F_per_m2")],
    )
    if not world["junctions"]:
        out = {k: v for k, v in out.items() if k not in ("junction", "jgate", "junctionCa")}
    if "plasma" in world:
        out |= dict(
            pmca=[mul(f"{plasma}/pump/capacity_fmol_per_s")],
            ncx=[mul(f"{plasma}/exchanger/capacity_fmol_per_s")],
            ncxkm=[mul(f"{plasma}/exchanger/km_na_mM")],
        )
    if "cav" in world:
        out |= dict(
            cav=[mul("/model/calcium_channels/*/max_permeability_m_per_s")],
            cavkinetics=CAV_KINETICS,
        )
    if "ip3" in world:
        out |= dict(
            ip3activation=[mul("/model/ip3_release/*/activation_mM")],
            ip3binding=[mul(f"{store}/reactions/4/forward_rate_per_s")],
        )
    return {k: ([], v) if isinstance(v, str) else (v, None) for k, v in out.items()}


def plan(origin):
    """Every planted run and control, at the captured h."""
    import make_inputs2 as m
    import rules

    origin, out = Path(origin), []

    def entry(name, world, modify=(), patch=None, plant=None, seed=None):
        base = (
            f"science/assembly/{world}/h-s{seed}.json"
            if world in m.CLUSTERS
            else f"science/ionic/{world}/h.json"
        )
        out.append(
            dict(
                name=name, kind="assembly" if world in m.CLUSTERS else "ionic",
                command="assembly-cluster" if world in m.CLUSTERS else None, world=world,
                plant=plant, seed=seed, base=str(origin / base), modify=list(modify), patch=patch,
            )
        )  # fmt: skip

    for world, w in m.WORLDS.items():
        entry(f"control {world} h", world, plant="control")
        for plant, (modify, patch) in power_plants(w).items():
            entry(f"P-{plant} {world}", world, modify, patch, plant)
    s, p, g, i = "inv_spatial", "inv_plasma", "inv_gated", "inv_ip3"
    for name, world, patch in (
        ("SC1 release calcium factor left out", s, SC1),
        ("SC2 IP3 factor left out", i, SC2),
        ("SC3 store voltage sign reversed", s, SC3),
        ("SC3b store voltage sign reversed in the calcium routes", s, SC3B),
        ("SC4 store pump direction reversed", s, SC4),
        ("SC5 calcium valence one in the store leak and release", s, SC5),
        ("SC6 first buffer second order in calcium", s, SC6),
        ("SC7 exchanger sodium terms squared", p, SC7),
        ("SC8 plasma calcium pump reversed", p, SC8),
        ("SC9 calcium channel inactivation left out", g, SC9),
        ("SC10 calcium channel m not squared", g, SC10),
    ):
        entry(name, world, patch=patch, plant=name.split()[0])
    entry(
        "SC6-stoichiometry the first buffer binds two calcium", s,
        [{"path": "/model/stores/*/model/reactions/0/reactants/Ca", "set": 2}],
        plant="SC6-stoichiometry",
    )  # fmt: skip
    for name, world, path in (
        (
            "SC12 the plasma pump's standard free energy left at the mM one", p,
            "/model/plasma_transport/membranes/*/pump/delta_g0_J_per_mol",
        ),
        (
            "SC13 the store pump's standard free energy left at the mM one", s,
            "/model/stores/*/model/membrane/pump/delta_g0_J_per_mol",
        ),
    ):  # fmt: skip
        g0 = next(iter(m.WORLDS[world]["stores"].values()))["pump"]["dg0"]
        wrong = g0 - rules.R * 298.15 * math.log(1000)
        entry(name, world, [{"path": path, "set": wrong}], plant=name.split()[0])
    c = "inv_cluster_gated"
    for seed in range(m.SEEDS):
        entry(f"control {c} s{seed} h", c, plant="control", seed=seed)
    for world in m.CLUSTERS:
        if world != c:
            entry(f"control {world} s0 h", world, plant="control", seed=0)
    entry("SC11 availability on the calcium channel too, seed 1", c, patch=SC11, plant="SC11",
          seed=1)  # fmt: skip
    entry("SC14 availability on the other cell's channel", c, patch=SC14, plant="SC14", seed=1)
    for world in (s, p, g, i):
        entry(f"control {world} h again", world, plant="control again")
    return out


# ------------------------------------------------------------------ one run


def no_ledgers(*modules):
    """Legacy's material, charge, energy and dissipation ledgers off; its domain checks stay on."""
    from cells.execution.errors import NumericalError

    names = (
        "max_balance_error_fmol", "max_ownership_error_fmol", "max_global_ion_balance_error_fmol",
        "max_countercharge_error_C", "max_energy_balance_error_pJ", "max_current_normalized",
        "max_process_accounting_error_fmol", "max_global_moiety_error_fmol",
        "max_charge_balance_error_equivalent_fmol",
    )  # fmt: skip

    def domain_only(m):
        spatial = hasattr(m, "ionic_model")

        def check_values(state, spec, **_):
            import numpy as np

            _, p = m.initial_values(spec)
            with np.errstate(all="ignore"):
                if spatial:
                    valid = m.domain_valid(state, p, p.active, xp=np, ionic=m.ionic_model(spec))
                elif hasattr(m, "base"):
                    ionic = m.base.ionic_model(spec)
                    valid = m.domain_valid(state, p, p.active, xp=np, ionic=ionic)
                else:
                    valid = m.domain_valid(state, p, p.active)
            if not valid:
                raise NumericalError("Invalid state or domain; no repair")
            return dict.fromkeys(names, 0.0)

        return check_values

    for m in modules:
        m.check_values = domain_only(m)


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
        name=entry["name"], kind=entry["kind"], world=entry["world"], plant=entry["plant"],
        seed=entry["seed"], base=entry["base"], base_sha256=sha256(entry["base"]),
        modify=entry["modify"], modified_leaves=leaves, patch=entry["patch"],
        command=[sys.executable, "-B", *sys.argv],
        environment={
            k: os.environ.get(k)
            for k in (
                "PYTHONPATH", "JAX_PLATFORMS", "JAX_ENABLE_X64", "JAX_ENABLE_COMPILATION_CACHE",
                "CUDA_VISIBLE_DEVICES", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
            )
        },
        affinity=sorted(os.sched_getaffinity(0)), started=started,
    )  # fmt: skip
    outcome = "completed"
    try:
        if entry["patch"] is not None:
            import jax
            import jax.numpy as jnp
            import numpy as np

            exec(
                compile(entry["patch"], f"<patch {entry['name']}>", "exec"),
                dict(
                    np=np, jax=jax, jnp=jnp, patch_source=part1.patch_source, no_ledgers=no_ledgers
                ),
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
                    entry["command"], "run", str(folder / "definition.json"), "--output",
                    str(folder / "run"), "--backend", "cpu",
                ]
            )  # fmt: skip
            failure = folder / "run" / "failure.json"
            if failure.exists():
                outcome = f"refused: {json.loads(failure.read_text())['error']}"[:300]
            elif code or not (folder / "run" / "completion.json").exists():
                outcome = "failed: incomplete"
            tool.drop_source_copy(SNAPSHOT, folder / "run")
    except Exception as error:  # The planted run's own refusal is an output: its type and message.
        outcome = f"refused: {type(error).__name__}: {error}"[:300]
    record.update(
        finished=utc(), seconds=time.monotonic() - began, outcome=outcome,
        definition_sha256=sha256(folder / "definition.json"), driver_sha256=sha256(__file__),
        part1_driver_sha256=sha256(part1.__file__), capture_tool_sha256=sha256(TOOL),
        outputs_sha256={
            str(p.relative_to(folder)): sha256(p)
            for p in sorted(folder.rglob("*"))
            if p.is_file() and p.name != "plant.json"
        },
        output_folder=str(folder),
    )  # fmt: skip
    write_json(folder / "plant.json", record)
    print(f"{utc()} {entry['name']}: {outcome}", flush=True)


# ------------------------------------------------------------------ the batch


def batches(entries, out):
    """The plan's runs that are still to make, as lists of indices that share a process."""
    groups = {}
    for i, e in enumerate(entries):
        if (out / e["name"] / "plant.json").exists():
            continue
        alone = e["patch"] is not None or e["kind"] != "ionic"
        groups.setdefault(i if alone else e["world"], []).append(i)
    return sorted(groups.values(), key=lambda g: -len(g))


def run_all(plan_file, out, cpus, seconds):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    entries = json.loads(Path(plan_file).read_text())
    todo = batches(entries, out)
    lock = threading.Lock()

    def worker(cpu):
        while True:
            with lock:
                if not todo:
                    return
                batch = todo.pop(0)
            log = out / "logs" / f"{batch[0]:03d}.log"
            with log.open("wb") as stream:
                subprocess.run(
                    [
                        "taskset", "-c", str(cpu), "nice", "-n", "10", PYTHON, "-B", __file__,
                        "some", str(plan_file), ",".join(map(str, batch)), str(out),
                    ],
                    env=environment(), stdin=subprocess.DEVNULL, stdout=stream,
                    stderr=subprocess.STDOUT, timeout=seconds,
                )  # fmt: skip
            print(log.read_text(errors="replace").strip().splitlines()[-1:], flush=True)

    threads = [threading.Thread(target=worker, args=(c,)) for c in cpus]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    missing = [e["name"] for e in entries if not (out / e["name"] / "plant.json").exists()]
    (out / "EXIT").write_text(f"{1 if missing else 0} {utc()} missing {missing}\n")


def manifest(plan_file, out, target):
    runs = []
    for e in json.loads(Path(plan_file).read_text()):
        r = json.loads((Path(out) / e["name"] / "plant.json").read_text())
        r["command"] = [in_checkout(v) for v in r["command"]]
        runs.append({k: v for k, v in r.items() if k not in ("plant", "world", "seed")})
    write_json(
        target,
        dict(
            schema="ensemble-reexpression plant manifest, version 1", part=2,
            snapshot="legacy-captures-20261125/snapshot-76a498ae",
            runs=sorted(runs, key=lambda r: r["name"]),
        ),
    )  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action, names in (
        ("plan", ("origin", "plan")),
        ("some", ("plan", "indices", "out")),
        ("manifest", ("plan", "out", "target")),
    ):
        s = sub.add_parser(action)
        for n in names:
            s.add_argument(n)
    s = sub.add_parser("all")
    s.add_argument("plan")
    s.add_argument("out")
    s.add_argument("--cpus", default="12,13,14,15,28,29,30,31")
    s.add_argument("--seconds", type=int, default=7200)
    a = parser.parse_args()
    if a.action == "plan":
        entries = plan(a.origin)
        write_json(a.plan, entries)
        print(f"{len(entries)} runs in {a.plan}")
    elif a.action == "some":
        for index in a.indices.split(","):
            one(a.plan, int(index), a.out)
    elif a.action == "all":
        run_all(a.plan, a.out, [int(c) for c in a.cpus.split(",")], a.seconds)
    else:
        manifest(a.plan, a.out, a.target)
