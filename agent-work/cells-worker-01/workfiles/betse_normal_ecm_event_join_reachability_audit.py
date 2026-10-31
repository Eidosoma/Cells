# ruff: noqa: E501 -- explicit source provenance strings.
"""Static native event/control/noise ownership audit; no scientific imports/calls."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
PREFIX = "betse_normal_ecm_event_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def methods(path, name):
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    return {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def site(node):
    return dict(first_line=node.lineno, last_line=node.end_lineno, AST_sha256=digest(node))


def writes(node):
    result = []
    for value in ast.walk(node):
        targets = (
            value.targets
            if isinstance(value, ast.Assign)
            else [value.target]
            if isinstance(value, (ast.AugAssign, ast.AnnAssign))
            else []
        )
        for target in targets:
            text = ast.unparse(target)
            if text.startswith(("sim.", "self.", "p.", "phase.sim.")):
                result.append(dict(target=text, line=value.lineno, statement=ast.unparse(value)))
    return sorted(result, key=lambda row: row["line"])


def audit():
    originals = {}
    for path in sorted((PIN / "betse").rglob("*.py")):
        relative = str(path.relative_to(PIN))
        data = path.read_bytes()
        assert data == (INSTALLED / relative).read_bytes(), relative
        originals[relative] = hashlib.sha256(data).hexdigest()
    assert len(originals) == 332
    sim = methods(PIN / "betse/science/sim.py", "Simulator")
    handlers = methods(PIN / "betse/science/tissue/tishandler.py", "TissueHandler")
    mod = functions(PIN / "betse/science/math/modulate.py")
    pulse = functions(PIN / "betse/science/math/toolbox.py")["pulse"]
    volt = methods(PIN / "betse/science/tissue/event/tisevevolt.py", "SimEventPulseVoltage")
    loop = next(n for n in sim["_run_sim_core_loop"].body if isinstance(n, ast.For))
    statements = [ast.unparse(n) for n in loop.body]
    reset_mem = statements.index("self.fluxes_mem.fill(0)")
    reset_gj = statements.index("self.fluxes_gj.fill(0)")
    event = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and "phase.dyna.fire_events" in ast.unparse(n)
    )
    moving = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "self.movingIons"
    )
    ca = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and "self.ca_handler(" in ast.unparse(n)
    )
    grn = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.grn_enabled"
    )
    noise = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and "p.dynamic_noise == 1" in ast.unparse(n.test)
    )
    commit = statements.index("self.update_all_concs(cells, p)")
    field = statements.index("self.update_V(cells, p)")
    assert reset_mem < reset_gj < event < moving < ca < grn < noise < commit < field
    assert ast.unparse(loop.body[event].test) == "phase.kind is SimPhaseKind.SIM"
    assert (
        ast.unparse(loop.body[noise].test)
        == "p.dynamic_noise == 1 and p.ions_dict['P'] == 1 and (phase.kind is SimPhaseKind.SIM)"
    )
    fire = [
        ast.unparse(n)
        for n in handlers["fire_events"].body
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
    ]
    assert fire == [
        "self._fire_events_global(phase=phase, t=t)",
        "self._fire_events_tissue(phase=phase, t=t)",
        "self.makeAllChanges(phase.sim)",
    ]
    glob = ast.unparse(handlers["_fire_events_global"])
    tissue = ast.unparse(handlers["_fire_events_tissue"])
    global_keys = [
        ast.literal_eval(n.test.left.slice)
        for n in handlers["_fire_events_global"].body
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and isinstance(n.test.left, ast.Subscript)
    ]
    assert global_keys == [
        "K_env",
        "Na_env",
        "T_change",
        "gj_block",
        "NaKATP_block",
    ]  # Cl has an additional ion guard.
    global_lines = {
        name: next(
            n.lineno
            for n in ast.walk(handlers["_fire_events_global"])
            if isinstance(n, ast.Subscript) and ast.unparse(n) == f"p.global_options[{name!r}]"
        )
        for name in ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block")
    }
    assert list(sorted(global_lines, key=global_lines.get)) == [
        "K_env",
        "Cl_env",
        "Na_env",
        "T_change",
        "gj_block",
        "NaKATP_block",
    ]
    assert "sim.c_env_bound[sim.iM]" in glob
    assert "sim.NaKATP_block = 1.0 - tb.pulse" in glob
    assert "sim.gj_block[self.targets_gj_block]" in glob
    assert (
        "sim.T = self.multT * tb.pulse(t, self.tonT, self.toffT, self.trampT) * p.T + p.T" in glob
    )
    changes = ast.unparse(handlers["makeAllChanges"])
    assert "sim.Dm_cells = sim.Dm_scheduled + sim.Dm_base" in changes
    assert "sim.P_cells = sim.P_mod + sim.P_base" in changes
    assert (
        "sim.D_env_base[i][self.targets_ecmJ]" in tissue
        and "sim.D_env_weight_base[self.targets_ecmJ]" in tissue
    )
    assert "sim.D_env_weight_base = sim.D_env_weight_base.reshape(cells.X.shape)" in tissue
    assert tissue.index("self.event_cut is not None") < tissue.index(
        "self._event_voltage is not None"
    )
    init = ast.unparse(handlers["_finalize_events_global"])
    assert (
        "shuffle(mem_i_copy)" in init and "cells.mem_i[x] for x in range(0, data_fraction)" in init
    )
    assert "mem_i_copy" not in ast.unparse(
        next(
            n
            for n in ast.walk(handlers["_finalize_events_global"])
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.targets_gj_block"
        ).value
    )
    init_dynamic = ast.unparse(sim["init_dynamics"])
    assert init_dynamic.index("self.Dm_base =") < init_dynamic.index("self.channel_noise_factor =")
    assert "np.random.random(self.mdl)" in init_dynamic
    noise_code = ast.unparse(loop.body[noise])
    assert "p.dynamic_noise_level * (np.random.random(self.mdl) - 0.5)" in noise_code
    assert "ignoreECM=False" in noise_code and "self.fluxes_mem" not in noise_code
    moving_init = [
        n
        for n in ast.walk(sim["init_core"])
        if isinstance(n, ast.Expr) and ast.unparse(n) == "self.movingIons.append(vars(self)[str1])"
    ]
    assert len(moving_init) == 1
    random_sites = []
    for name, node in {**mod, **{"handler." + k: v for k, v in handlers.items()}}.items():
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and (
                ast.unparse(call.func).startswith("np.random.")
                or ast.unparse(call.func) == "shuffle"
            ):
                random_sites.append(dict(owner=name, call=ast.unparse(call), line=call.lineno))
    for name in ("gradient_x", "gradient_y", "single_cell"):
        text = ast.unparse(mod[name])
        assert "len(pc) == len(cells.mem_i)" in text and "len(pc) == len(cells.cell_i)" in text
    assert "p.gradient_y_properties['x-offset']" in ast.unparse(mod["gradient_y"])
    assert ast.unparse(mod["gradient_r"]).count("p.gradient_r_properties['x-offset']") == 2
    assert "p._run_sim" in ast.unparse(
        mod["f_sweep"]
    ) and "p.f_scan_properties['f slope'] =" in ast.unparse(mod["f_sweep"])
    # Frozen catalog component admits fixed kernels and independent per-call packets.
    catalog_main = ast.parse(
        (ROOT / "src/cells/processes/betse_normal_ecm_catalog_join.py").read_text()
    )
    catalog_text = ast.unparse(catalog_main)
    assert "runtime_temperature_K" not in ast.unparse(
        next(n for n in catalog_main.body if isinstance(n, ast.ClassDef) and n.name == "Binding")
    )
    assert "source.restore(ctx, parent.network.network_cache)" in catalog_text
    return dict(
        kind="cells.normal_ecm_event_static_reachability@1",
        Python_files=332,
        installed_exact=True,
        original_source_sha256=originals,
        normal_order=[
            "reset_membrane_GJ_ECM_flux",
            "SIM_fire_events",
            "ordinary_pumps",
            "moving_ions",
            "CaATP",
            "GRN_channels_modulators_chemistry",
            "protein_noise",
            "mechanics_if_enabled",
            "deferred_commit",
            "full_fields_check_v",
        ],
        event_order=[
            "global_K_salt",
            "global_Cl_salt",
            "global_Na_salt",
            "runtime_T",
            "GJ_targets",
            "NaKATP_scalar",
            "tissue_Na_K_Cl_Ca",
            "pressure",
            "ECM_diffusion_and_weight",
            "cuts_if_owned",
            "voltage",
            "makeAllChanges",
        ],
        clock="Actual source normal linspace(0,N*dt,N) event labels; transport and noise dt are configured phase dt; calls independent of sampling",
        literal_handler_methods={
            name: site(handlers[name])
            for name in (
                "_finalize_events_global",
                "_finalize_events_tissue",
                "fire_events",
                "_fire_events_global",
                "_fire_events_tissue",
                "makeAllChanges",
            )
        },
        handler_writes={
            name: writes(handlers[name])
            for name in ("_fire_events_global", "_fire_events_tissue", "makeAllChanges")
        },
        original_pulse=site(pulse),
        voltage_fire=site(volt["fire"]),
        modulator_functions={
            name: site(mod[name])
            for name in (
                "periodic",
                "f_sweep",
                "single_cell",
                "gradient_x",
                "gradient_y",
                "gradient_r",
                "gradient_bitmap",
            )
        },
        normal_event_guard=site(loop.body[event]),
        normal_protein_noise_guard_and_body=site(loop.body[noise]),
        RNG_sites=random_sites,
        RNG_ownership=dict(
            preparation="Static K consumes M uniforms even level0; single_cell callback consumes one choice; GJ finalization consumes Python shuffle but selects unshuffled prefix; supplied prepared owner must retain those epochs",
            normal="dynamic==1/P-enabled/SIM consumes one M-uniform vector after GRN including t0 and level0; disabled branch consumes none; full local MT words/position/Gaussian cache/version required",
            stable_owner_RNG="Different convention, no native equivalence",
        ),
        source_defects_preserved=[
            "global salts overlap Na/M boundary setters in fixed K-Cl-Na order",
            "GJ shuffled copy unused",
            "native pump block becomes scalar",
            "static K first-SIM reset by makeAllChanges",
            "gradient/single_cell choose domain by len(pc), not supplied ion domain; full vector is assigned without target gather",
            "gradient_y uses x-offset; radial uses x-offset in both components",
            "f_sweep mutates slope at callback construction when None and _run_sim",
            "protein noise directly updates concentrations, no membrane flux accumulation or sqrt(dt) scaling",
            "all enabled ions appended to movingIons in native init_core, including P despite stale comment",
        ],
        reusable_components={
            p: sha(ROOT / p)
            for p in (
                "src/cells/core/physiology_native_calendar.py",
                "src/cells/processes/betse_global_controls.py",
                "src/cells/processes/betse_tissue_profiles.py",
                "src/cells/processes/betse_time_modulation.py",
                "src/cells/processes/betse_perturbations.py",
            )
        },
        required_new_seams=[
            "explicit supplied tissue/default/callback/geometry owner",
            "persistent live Dm_base/Dm_scheduled/D_env/base/weights/control/bath/T/bound_V stores",
            "scalar native controls retained, explicit broadcasting only at existing vector consumers",
            "real M-1 role and arrays for K/Na salt events",
            "noise callback after GRN snapshot before deferred commit; cache epoch after noise and ordinary commit retained",
        ],
        scoped_refusals=[
            "cut/remesh lifecycle without supplied new geometry ownership",
            "bitmap/expression/unowned callback lifecycle",
            "forced INIT/events-disabled/native full SimRunner equivalence",
            "inferred native cold/restart RNG or tissue profile construction",
        ],
        catalog02_final_static_review_pending=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / f"{PREFIX}_reachability_01.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in (
                    "original_source_sha256",
                    "handler_writes",
                    "RNG_sites",
                    "literal_handler_methods",
                    "modulator_functions",
                )
            },
            sort_keys=True,
        )
    )
