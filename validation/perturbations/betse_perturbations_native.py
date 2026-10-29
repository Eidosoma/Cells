"""Actual source RNG sites, call-order/state receipts and isolated native updates."""

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import traceback
import warnings
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.perturbations.betse_perturbations_fixtures import cases, distribution, limitations

PROTOCOL = Path(__file__).with_name("betse_perturbations_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def write(path, value):
    path.write_text(json.dumps(serial(value), indent=2, allow_nan=False) + "\n")


def state_digest(state):
    return hashlib.sha256(json.dumps(serial(state), separators=(",", ":")).encode()).hexdigest()


class RandomRecorder:
    def __init__(self):
        self.calls = []
        self.compact = False

    def call(self, family, *args, **kwargs):
        before = np.random.get_state()
        clone = np.random.RandomState()
        clone.set_state(before)
        result = getattr(np.random, family)(*args, **kwargs)
        after = np.random.get_state()
        row = dict(
            family=family,
            args=serial(args),
            kwargs=serial(kwargs),
            values=serial(result),
            before_sha256=state_digest(before),
            after_sha256=state_digest(after),
        )
        if family == "normal":
            row["standard_normal"] = serial(
                clone.normal(loc=0.0, scale=1.0, size=kwargs.get("size"))
            )
            assert state_digest(clone.get_state()) == state_digest(after)
        elif family == "choice":
            row["occurrence"] = int(clone.choice(len(args[0])))
            assert args[0][row["occurrence"]] == result
            assert state_digest(clone.get_state()) == state_digest(after)
        if not self.compact:
            row["state_before"] = serial(before)
            row["state_after"] = serial(after)
            self.calls.append(row)
        return result

    def random(self, *args, **kwargs):
        return self.call("random", *args, **kwargs)

    def choice(self, *args, **kwargs):
        return self.call("choice", *args, **kwargs)

    def normal(self, *args, **kwargs):
        return self.call("normal", *args, **kwargs)


class NumpyProxy:
    def __init__(self, random):
        self.random = random

    def __getattr__(self, name):
        return getattr(np, name)


class PhaseKind(Enum):
    INIT = 1
    SIM = 2


def executable(node):
    node = copy.deepcopy(node)
    for item in ast.walk(node):
        if isinstance(item, ast.FunctionDef):
            item.decorator_list = []
            item.returns = None
            for arg in (*item.args.posonlyargs, *item.args.args, *item.args.kwonlyargs):
                arg.annotation = None
    return node


def wrapper(name, args, body):
    fn = ast.parse("def " + name + "(" + args + "):\n    pass\n").body[0]
    fn.body = [copy.deepcopy(n) for n in body]
    return fn


def compile_source(trees, manifest, recorder):
    sim_cls = next(
        n
        for n in trees["betse/science/sim.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    methods = {n.name: n for n in sim_cls.body if isinstance(n, ast.FunctionDef)}
    init = methods["init_dynamics"]
    first = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "Dm_cellsA" for t in n.targets)
    )
    last = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.Dm_cells[self.iK]" for t in n.targets)
    )
    static = init.body[first : last + 1]
    dynamic = [
        n
        for n in ast.walk(methods["_run_sim_core_loop"])
        if isinstance(n, ast.If) and ast.unparse(n.test).startswith("p.dynamic_noise == 1")
    ]
    assert len(dynamic) == 1
    bodies = [
        wrapper("static_init", "self,cells,p", static),
        wrapper("dynamic", "self,phase,cells,p", dynamic),
    ]
    for label in ("normal", "fast"):
        method = methods["_run_sim_core_loop" if label == "normal" else "_run_fast_sim_core_loop"]
        sites = [
            n
            for n in ast.walk(method)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "phase.kind is SimPhaseKind.SIM"
            and any(
                isinstance(k, ast.Call) and ast.unparse(k.func) == "phase.dyna.fire_events"
                for k in ast.walk(n)
            )
        ]
        assert len(sites) == 1
        bodies.append(wrapper("events_" + label, "self,phase,t", sites))
    fast = methods["_run_fast_sim_core_loop"]
    assert not any(
        isinstance(n, ast.Call) and ast.unparse(n.func).startswith("np.random.")
        for n in ast.walk(fast)
    )
    assert not any(
        isinstance(n, ast.Call) and ast.unparse(n.func).endswith("update_mtubes")
        for method in methods.values()
        for n in ast.walk(method)
    )
    manifest["sites"] = dict(
        static=[dict(first_line=static[0].lineno, last_line=static[-1].end_lineno)],
        dynamic=[dict(first_line=dynamic[0].lineno, last_line=dynamic[0].end_lineno)],
        fast_dynamic_rng_sites=[],
        microtubules_integrated=False,
    )
    bodies.append(
        ast.ClassDef(
            name="CapturedSimulator",
            bases=[],
            keywords=[],
            decorator_list=[],
            body=[executable(methods["update_all_concs"])],
        )
    )
    for relative, original, name, names in (
        (
            "betse/science/organelles/microtubules.py",
            "Mtubes",
            "CapturedMtubes",
            ("__init__", "_init_scalars", "_init_scalars_drag", "update_mtubes", "mtubes_to_cell"),
        ),
        ("betse/science/cells.py", "Cells", "CapturedCells", ("div", "single_cell_div_free")),
        (
            "betse/science/tissue/tishandler.py",
            "TissueHandler",
            "CapturedHandler",
            ("fire_events", "makeAllChanges"),
        ),
    ):
        cls = next(
            n for n in trees[relative].body if isinstance(n, ast.ClassDef) and n.name == original
        )
        selected = [
            executable(n) for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names
        ]
        assert len(selected) == len(names)
        bodies.append(
            ast.ClassDef(name=name, bases=[], keywords=[], decorator_list=[], body=selected)
        )
        manifest.setdefault("executed_bodies", {})[original] = dict(
            source=relative, methods=list(names)
        )
    for relative, names in (
        ("betse/science/sim_toolbox.py", ("update_Co", "div_env", "no_negs")),
        ("betse/science/math/modulate.py", ("single_cell",)),
    ):
        selected = [
            executable(n)
            for n in trees[relative].body
            if isinstance(n, ast.FunctionDef) and n.name in names
        ]
        assert len(selected) == len(names)
        bodies.extend(selected)
        for node in selected:
            manifest.setdefault("executed_bodies", {})[node.name] = dict(
                source=relative, first_line=node.lineno, last_line=node.end_lineno
            )
    # Exact normal assignment, used as a distribution probe with prescribed sd.
    mt = next(
        n
        for n in trees["betse/science/organelles/microtubules.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Mtubes"
    )
    assignment = next(
        n
        for n in ast.walk(mt)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "noise" for t in n.targets)
    )
    bodies.append(
        wrapper("normal_distribution", "sim,stdev", [assignment, ast.parse("return noise").body[0]])
    )
    namespace = dict(
        np=NumpyProxy(recorder),
        copy=copy,
        SimPhaseKind=PhaseKind,
        BetseSimUnstableException=ValueError,
        logs=SimpleNamespace(log_info=lambda *_: None),
        modulate=SimpleNamespace(),
    )
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[executable(n) for n in bodies], type_ignores=[])
            ),
            str(PROTOCOL),
            "exec",
        ),
        namespace,
    )
    namespace["stb"] = SimpleNamespace(
        **{k: namespace[k] for k in ("update_Co", "div_env", "no_negs")}
    )
    return namespace


def make_cells(raw, namespace):
    n, m, e = len(raw["cell_ids"]), len(raw["membrane_ids"]), len(raw["environment_ids"])
    cells = namespace["CapturedCells"]()
    owner = np.asarray(raw["owner"], int)
    area = np.asarray(raw["membrane_area_m2"])
    sums = np.zeros((n, m))
    sums[owner, np.arange(m)] = 1
    scatter = np.zeros((e, m))
    scatter[np.asarray(raw["environment_owner"]), np.arange(m)] = area
    cells.__dict__.update(
        mem_i=np.arange(m),
        cell_i=np.arange(n),
        mem_to_cells=owner,
        M_sum_mems=sums,
        M_sum_mems_inv=np.linalg.pinv(sums),
        mem_sa=area,
        cell_vol=np.asarray(raw["cell_volume_m3"]),
        mem_vol=np.full(m, 1e-17),
        cell_sa=sums @ area,
        map_mem2ecm=np.asarray(raw["environment_owner"], int),
        M_divmap_mem2ecm=scatter,
        memSa_per_envSquare=scatter.sum(axis=1),
        xypts=np.zeros((e, 2)),
        ecm_vol=raw["environment_volume_m3"],
        delta=raw["delta_m"],
        bflags_cells=np.asarray(raw["boundary_cells"], int),
        bflags_mems=np.array([0, 1], int),
        R_rads=np.ones(m) * 1e-6,
    )
    p = raw["micro"]
    normals = np.asarray(p["normal"])
    cells.mem_vects_flat = np.column_stack(
        (np.zeros((m, 2)), normals, np.column_stack((-normals[:, 1], normals[:, 0])))
    )
    cells.nn_i = np.asarray(p["partner"])
    cells.nn_len = np.asarray(p["neighbor_length_m"])
    cells.nn_tx = normals[:, 0]
    cells.nn_ty = normals[:, 1]
    cells.num_mems = sums.sum(axis=1)
    return cells


def protein_state(sim, index):
    env = sim.cc_env[index]
    return dict(
        cell=serial(sim.cc_cells[index]),
        membrane=serial(sim.cc_at_mem[index]),
        environment=serial(np.atleast_1d(env)),
    )


def capture_case(raw, output, ns, rng, limited=False):
    rng.calls = []
    rng.compact = False
    np.random.seed(raw["seed"])
    record = dict(
        name=raw["name"], input=raw, status="prepared", rng_before=serial(np.random.get_state())
    )
    trace = []
    path = output / (raw["name"] + ".json")
    write(path, record)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            cells = make_cells(raw, ns)
            m, n = len(cells.mem_i), len(cells.cell_i)
            p = SimpleNamespace(
                channel_noise_level=raw["static_level"],
                dynamic_noise=raw["dynamic_enabled"],
                dynamic_noise_level=raw["dynamic_level"],
                ions_dict=dict(P=int(raw["protein_enabled"])),
                dt=raw["dt_s"],
                is_ecm=raw["is_ecm"],
                fast_update_ecm=raw["fast_update_ecm"],
                vol_env=raw["bath_parameter_volume_m3"],
                cell_height=raw["height_m"],
                mod_single_cell_offset=raw["modulator_offset"],
                cluster_open=raw["cluster_open"],
            )
            sim = ns["CapturedSimulator"]()
            initial = np.asarray(raw["initial_diffusion_m2_s"], float)
            sim.Dm_cells = [v.copy() for v in initial] if raw["static_as_list"] else initial.copy()
            sim.P_cells = np.zeros(n)
            sim.mdl = m
            sim.cdl = n
            for i, ion in enumerate(raw["ion_ids"]):
                setattr(sim, "i" + ion, i)
            record["stage"] = "static_init"
            ns["static_init"](sim, cells, p)
            record["static"] = serial(
                dict(
                    uniform=sim.channel_noise_factor,
                    Dm_cells=sim.Dm_cells,
                    Dm_base=sim.Dm_base,
                    Dm_scheduled=sim.Dm_scheduled,
                )
            )
            record["stage"] = "boundary_choice"
            mask, dynamics = ns["single_cell"](np.arange(raw["target_count"]), cells, p)
            record["boundary"] = dict(
                mask=serial(mask),
                chosen_cell_index=int(raw["boundary_cells"][rng.calls[-1]["occurrence"]]),
                occurrence=rng.calls[-1]["occurrence"],
                dynamics=[dynamics(t) for t in raw["times_s"]],
            )
            protein = raw["ion_ids"].index("P")
            ions = len(raw["ion_ids"])
            sim.cc_cells = [
                np.asarray(raw["initial_cell_mol_m3"], float).copy() for _ in range(ions)
            ]
            sim.cc_at_mem = [
                np.asarray(raw["initial_membrane_mol_m3"], float).copy() for _ in range(ions)
            ]
            env = np.asarray(raw["initial_environment_mol_m3"], float)
            if not raw["is_ecm"] and len(env) == 1:
                env = float(env[0])
            sim.cc_env = [copy.deepcopy(env) for _ in range(ions)]
            sim.fluxes_mem = np.zeros((ions, m))
            sim.fluxes_gj = np.zeros((ions, m))
            sim.movingIons = [protein] if raw["protein_enabled"] else []
            handler = ns["CapturedHandler"]()
            handler._fire_events_global = lambda **_: trace.append("global_events_noop")
            handler._fire_events_tissue = lambda **_: trace.append("tissue_events_noop")
            phase = SimpleNamespace(
                sim=sim, p=p, cells=cells, dyna=handler, kind=PhaseKind[raw["phase"]]
            )
            records = []
            for tick, t in enumerate(raw["times_s"]):
                record["stage"] = "tick"
                start = len(rng.calls)
                ns["events_" + raw["solver"]](sim, phase, t)
                before = protein_state(sim, protein)
                if raw["solver"] == "normal":
                    ns["dynamic"](sim, phase, cells, p)
                after = protein_state(sim, protein)
                flux = (
                    serial(sim.protein_noise_flux) if hasattr(sim, "protein_noise_flux") else None
                )
                if raw["solver"] == "normal":
                    sim.update_all_concs(cells, p)
                records.append(
                    dict(
                        tick=tick,
                        time_s=t,
                        draw_calls=len(rng.calls) - start,
                        before=before,
                        after_noise=after,
                        after_bulk=protein_state(sim, protein),
                        flux=flux,
                        Dm_cells=serial(sim.Dm_cells),
                    )
                )
            record["records"] = records
            if raw.get("micro_init_failure"):
                record["stage"] = "micro_init"
                if raw["micro_init_failure"] == "drag":
                    p.__dict__.update(
                        mt_radius=15e-9,
                        length_charge=-360.0,
                        q=1.6e-19,
                        tubulin_dipole=1750.0,
                        tubulin_polar=50.0,
                        cytoplasm_viscocity=1e-2,
                        kb=1.38e-23,
                        T=300.0,
                        mt_space_density=None,
                    )
                tube = ns["CapturedMtubes"](sim, cells, p)
                record["micro_initializer"] = serial(tube.__dict__)
            if raw["run_microtubule"]:
                record["stage"] = "disabled_microtubule"
                config = raw["micro"]
                tube = object.__new__(ns["CapturedMtubes"])
                p.__dict__.update(
                    kb=config["kb"],
                    T=config["T"],
                    dilate_mtube_dt=config["dilation"],
                    tethered_tubule=config["tethered"],
                )
                tube.__dict__.update(
                    mt_theta=np.asarray(config["theta"]),
                    L=np.asarray(config["length_m"]),
                    drag_r=np.asarray(config["drag_native"]),
                    charge_mtube=np.asarray(config["charge_C"]),
                    uxmt=np.asarray(config["ux"]),
                    uymt=np.asarray(config["uy"]),
                    modulator=np.asarray(config["modulator"]),
                    mt_density=1.0,
                )
                if raw.get("micro_failure") == "missing-correlation":
                    del tube.uxmt
                sim.E_cell_x = np.asarray(config["E_x"])
                sim.E_cell_y = np.asarray(config["E_y"])
                sim.T = config["sim_T"]
                start = len(rng.calls)
                tube.update_mtubes(cells, sim, p)
                record["micro"] = serial(
                    dict(
                        theta=tube.mt_theta,
                        draw_calls=len(rng.calls) - start,
                        vectors_x=getattr(tube, "mtubes_x", None),
                        vectors_y=getattr(tube, "mtubes_y", None),
                    )
                )
            record["status"] = "captured_limitation" if limited else "passed"
        except Exception as error:
            record.update(
                status="captured_failure" if limited else "unexpected_failure",
                failure_type=type(error).__name__,
                failure=str(error),
                traceback=traceback.format_exc(),
            )
    record.update(
        rng_after=serial(np.random.get_state()),
        draws=rng.calls,
        dispatch_trace=trace,
        warnings=[dict(category=w.category.__name__, message=str(w.message)) for w in caught],
    )
    write(path, record)
    if not limited:
        assert record["status"] == "passed", (raw["name"], record.get("failure"))
    return dict(name=raw["name"], status=record["status"], path=str(path))


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    source = json.loads(PROTOCOL.read_text())["native_source"]
    checkout = Path(source["checkout"])
    installed = Path(source["installed_package"]).parent
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest = dict(
        status="capturing",
        revision=revision,
        version=source["version"],
        files={},
        records=[],
        full_simulator=False,
        versions={n: importlib.metadata.version(n) for n in ("numpy", "scipy")},
    )
    write(output / "source-manifest.json", manifest)
    trees = {}
    for relative, sha in source["source_sha256"].items():
        content = (installed / relative).read_bytes()
        target = output / "upstream" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, target)
        assert (
            content == (checkout / relative).read_bytes()
            and hashlib.sha256(content).hexdigest() == sha
        )
        manifest["files"][relative] = dict(sha256=sha, checkout_match=True)
        if relative.endswith(".py"):
            trees[relative] = ast.parse(content.decode())
    rng = RandomRecorder()
    ns = compile_source(trees, manifest, rng)
    for raw, limited in [(v, False) for v in cases()] + [(v, True) for v in limitations()]:
        manifest["records"].append(capture_case(raw, output, ns, rng, limited))
        write(output / "source-manifest.json", manifest)
    raw = distribution()
    rng.compact = True
    np.random.seed(raw["seed"])
    before = serial(np.random.get_state())
    count = raw["samples"]
    sim = SimpleNamespace(mdl=count, cdl=1, Dm_cells=np.ones((1, count)), iK=0, P_cells=np.zeros(1))
    ns["static_init"](
        sim, SimpleNamespace(), SimpleNamespace(channel_noise_level=raw["static_level"])
    )
    uniform = sim.channel_noise_factor.copy()
    normal = ns["normal_distribution"](sim, np.ones(count))
    cell = make_cells(raw, ns)
    p = SimpleNamespace(mod_single_cell_offset=raw["modulator_offset"])
    chosen = []
    for _ in range(raw["choice_samples"]):
        mask, _ = ns["single_cell"](np.arange(len(raw["cell_ids"])), cell, p)
        chosen.append(int(np.argmax(mask)))
    write(
        output / "native-distributions.json",
        dict(
            status="passed",
            input=raw,
            rng_before=before,
            rng_after=serial(np.random.get_state()),
            uniform=uniform,
            standard_normal=normal,
            chosen_cells=chosen,
        ),
    )
    manifest.update(
        status="passed",
        component_cases=len(cases()),
        limitations=len(limitations()),
        distribution_samples=count,
        boundary_choice_samples=raw["choice_samples"],
        production_cells_imported=any(k == "cells" or k.startswith("cells.") for k in sys.modules),
        jax_imported=any(k == "jax" or k.startswith("jax.") for k in sys.modules),
        microtubules_enabled=False,
        geometry_or_full_physiology=False,
    )
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    write(output / "source-manifest.json", manifest)
    print(json.dumps(dict(status="passed", cases=len(cases()), limitations=len(limitations()))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    capture(parser.parse_args().output)
