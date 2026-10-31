# ruff: noqa: E501
"""Pinned native INIT->SIM boundary audit; AST/text/hash only, no science execution."""

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
INIT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01")
SIM = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(path, name, owner):
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


def evidence(path, name, owner):
    node = function(path, name, owner)
    writes = []
    for n in ast.walk(node):
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            writes.extend(
                dict(target=ast.unparse(t), expression=ast.unparse(n.value), line=n.lineno)
                for t in targets
            )
    return dict(
        path=str(path),
        sha256=sha(path),
        owner=owner,
        function=name,
        first_line=node.lineno,
        last_line=node.end_lineno,
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        writes=writes,
        calls=[
            dict(callee=ast.unparse(n.func), line=n.lineno)
            for n in ast.walk(node)
            if isinstance(n, ast.Call)
        ],
    )


def audit():
    methods = {}
    for relative, owner, names in (
        ("betse/science/simrunner.py", "SimRunner", ("sim", "init", "_die_if_seed_differs")),
        (
            "betse/science/phase/phasecls.py",
            "SimPhase",
            ("__init__", "_init_kludge", "_init_kludge_time"),
        ),
        (
            "betse/science/sim.py",
            "Simulator",
            (
                "init_dynamics",
                "clear_storage",
                "run_sim_core",
                "_pickle_phase",
                "ca_handler",
                "_run_sim_core_loop",
            ),
        ),
        ("betse/science/chemistry/gene.py", "MasterOfGenes", ("reinitialize", "read_gene_config")),
        (
            "betse/science/chemistry/networks.py",
            "MasterOfNetworks",
            ("tissue_init", "read_channels", "run_loop_channels", "clear_cache"),
        ),
        (
            "betse/science/tissue/tishandler.py",
            "TissueHandler",
            ("init_profiles", "_finalize_events_global", "_finalize_events_tissue"),
        ),
    ):
        for name in names:
            methods[owner + "." + name] = evidence(NATIVE / relative, name, owner)
    sim = function(NATIVE / "betse/science/simrunner.py", "sim", "SimRunner")
    text = ast.unparse(sim)
    assert text.index("fh.loadSim(") < text.index("SimPhase(") < text.index("sim.run_sim_core(")
    assert "sim.init_core(" not in text
    reinit = function(NATIVE / "betse/science/chemistry/gene.py", "reinitialize", "MasterOfGenes")
    assert "read_substances(" not in ast.unparse(reinit) and ".tissue_init(" in ast.unparse(reinit)
    channels = function(
        NATIVE / "betse/science/chemistry/networks.py", "read_channels", "MasterOfNetworks"
    )
    assert "self.channels = OrderedDict({})" in ast.unparse(channels)
    assert "obj.init_active = chan_dic.get('init active', True)" in ast.unparse(channels)
    core = function(NATIVE / "betse/science/sim.py", "run_sim_core", "Simulator")
    text = ast.unparse(core)
    assert (
        text.index("self.init_dynamics(")
        < text.index("self.clear_storage(")
        < text.index("self.update_V(")
        < text.index("self._plot_loop(")
    )
    clear = ast.unparse(function(NATIVE / "betse/science/sim.py", "clear_storage", "Simulator"))
    assert "self.rate_CaATP =" not in clear and "self.rate_NaKATP =" not in clear
    pickle = ast.unparse(function(NATIVE / "betse/science/sim.py", "_pickle_phase", "Simulator"))
    assert pickle.index("fh.saveSim(") < pickle.index("self.vm_time[-1]")
    pins = {}
    for path in sorted((NATIVE / "betse").rglob("*.py")):
        name = str(path.relative_to(NATIVE))
        assert sha(path) == sha(INSTALLED / name), name
        pins[name] = sha(path)
    assert len(pins) == 332
    inherited = SIM / "source/src/cells/processes/betse_normal_ecm_event_mechanics.py"
    sim_tree = ast.parse(inherited.read_text())
    warm = next(
        n for n in sim_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_advance_events"
    )
    assert "binding.calcium['alpha_Ca'] > 0 and index > 0" in ast.unparse(warm)
    assert not any(
        k.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for k in sys.modules
    )
    return dict(
        kind="cells.pinned_INIT_SIM_source_boundary@1",
        status="audited_source_only",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        native_source_sha256=pins,
        source_methods=methods,
        authoritative_dependencies=dict(
            INIT_manifest=dict(
                path=str(INIT / "MANIFEST.json"), sha256=sha(INIT / "MANIFEST.json")
            ),
            SIM_inputs=dict(path=str(SIM / "inputs.json"), sha256=sha(SIM / "inputs.json")),
        ),
        transition_rules=[
            "SimRunner.sim loads Simulator/cells, checks seed compatibility, constructs a new SIM phase using new parameters, and does not rerun init_core.",
            "SimPhase replaces sim.dyna with the new tissue/event owner, sets _run_sim=True, selects SIM dt/total/sampling and derives a fresh phase clock.",
            "init_dynamics reruns initDenv, optional c_env_bound overrides, supplied tissue target/profile assignments, base/scheduled Dm and pressure setup, unconditional static_K RNG draw, GJ/NaK/Ca blocks and ER-disabled None.",
            "Existing GRN owner/core/molecule objects are reinitialized; read_substances and fresh MasterOfGenes are skipped. tissue_init refreshes configuration while preserving current molecular concentrations.",
            "tissue_init can balance primary charge if the existing charge_has_been_balanced flag is false and the new publication flag is true; unconditional ionic byte-carry is therefore invalid.",
            "A non-None channel configuration reconstructs the channel dictionary and all gates at carried pre-bootstrap Vm; SIM ignores init_active when warming them.",
            "A None channel configuration disables the owner flag but does not clear a preexisting channel dictionary. Empty list instead rebuilds an empty enabled dictionary. Latent cache retention needs explicit handling or refusal.",
            "Mechanical entry stores/tools are initialized again under source flags; rho_pump/rho_channel are then reset to scalar1. Event finalization can consume Python shuffle and SIM f_sweep computes an unspecified slope using SIM total.",
            "Rate_CaATP and rate_NaKATP attributes survive phase setup and clear_storage. First SIM NaK alpha0 writes zeros; CaATP alpha0 leaves its retained cache unchanged.",
            "clear_storage resets flux_mem/flux_gj and storage caches; GRN clear_cache clears output histories, not current molecular concentrations. Bootstrap update_V then runs without the loop check_v.",
            "The new SIM cursor/material dt/mechanics counter and headless journal begin at0; primary concentrations and stale gap bookkeeping retain their actual reached values except explicit source setup writers.",
            "RNG states are process globals, not members of the pickle datadump [sim,cells,p]. Separate-process SIM RNG must be supplied; same-process stream continuity requires an explicit no-unowned-draw seam.",
            "Native instability is saved then reraised; unexpected exceptions bypass _pickle_phase. saveSim occurs before final vm_time[-1] reporting, so a zero-sample report failure can follow a written pickle.",
        ],
        implementation_constraints=[
            "Never invoke existing cold initialize() to manufacture a transition; restore the retained GRN then execute its real reinitialize body.",
            "The existing SIM _advance_events index0 CaATP-absence guard conflicts with retained native rates; use a private first-phase cache adapter without shared edits.",
            "Whole seed/load/pickle/profile picking/physical initializer and full run_sim_core remain outside a supplied in-memory headless handoff.",
            "Prepared complete-headless and failed-prefix artifacts must be different types. No automatic failed/paused/capped prefix promotion to complete.",
        ],
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_reference_model_evaluations=0,
        pytest_collection=0,
        numerical_runs=0,
        active_job_queries=0,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                native_files=len(result["native_source_sha256"]),
                methods=len(result["source_methods"]),
                rules=len(result["transition_rules"]),
            )
        )
    )


if __name__ == "__main__":
    main()
