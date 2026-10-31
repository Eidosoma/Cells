"""Audit native INIT/SIM ownership, clocks and retained transporter semantics."""
# ruff: noqa: E501 -- Complete source findings, not evaluated model statements.

import ast
import hashlib
import json
import sys
from pathlib import Path

BASE = Path("/mnt/workspaces/Cells")
NATIVE = BASE / "betse-v1.5.0/betse"
INSTALLED = BASE / "venv-betse/lib/python3.13/site-packages/betse"
WORK = Path(__file__).parent
PARENTS = {
    "dispatch01": (
        "betse-normal-ecm-molecule-dispatch-prepared-20261031-01",
        "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922",
    ),
    "transport01": (
        "betse-normal-ecm-molecule-transport-prepared-20261031-01",
        "166e53330a63866f42897029daafde64b3b957bb1ec1771191e46b8c458b5ba6",
    ),
    "transition02": (
        "betse-normal-ecm-init-sim-transition-prepared-20261031-02",
        "fab41871bfaf8e457141bd76a491926577f1a84d16a6052aee2538e0e5eec312",
    ),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fn(relative, name, owner):
    tree = ast.parse((NATIVE / relative).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


def main():
    methods = {}
    for relative, owner, names in (
        ("science/phase/phasecls.py", "SimPhase", ("__init__", "_init_kludge_time")),
        ("science/parameters.py", "Parameters", ("load",)),
        (
            "science/sim.py",
            "Simulator",
            (
                "init_core",
                "init_dynamics",
                "run_sim_core",
                "_plot_loop",
                "_run_sim_core_loop",
                "clear_storage",
            ),
        ),
        (
            "science/chemistry/molecules.py",
            "MasterOfMolecules",
            ("__init__", "read_mol_config", "reinitialize"),
        ),
        (
            "science/chemistry/gene.py",
            "MasterOfGenes",
            ("__init__", "read_gene_config", "reinitialize"),
        ),
        (
            "science/chemistry/networks.py",
            "MasterOfNetworks",
            (
                "__init__",
                "read_substances",
                "tissue_init",
                "read_transporters",
                "write_transporters",
                "run_loop_transporters",
                "read_channels",
                "run_loop_channels",
                "create_reaction_matrix",
                "clear_run_loop",
                "run_loop",
                "clear_cache",
            ),
        ),
    ):
        for name in names:
            node = fn(relative, name, owner)
            methods[owner + "." + name] = dict(
                path=relative,
                line=node.lineno,
                end_line=node.end_lineno,
                source_sha256=sha(NATIVE / relative),
                AST_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
            )
    for owner, relative in (
        ("MasterOfMolecules", "science/chemistry/molecules.py"),
        ("MasterOfGenes", "science/chemistry/gene.py"),
    ):
        reinit = fn(relative, "reinitialize", owner)
        calls = {ast.unparse(n.func) for n in ast.walk(reinit) if isinstance(n, ast.Call)}
        assert "self.core.tissue_init" in calls and "self.core.read_substances" not in calls
        assert "self.core.read_transporters" in calls and "self.core.read_channels" in calls
        for node in reinit.body:
            if not isinstance(node, ast.If):
                continue
            if ast.unparse(node.test) in (
                "transporters_config is not None",
                "channels_config is not None",
            ):
                assert all(
                    not isinstance(n, ast.Assign)
                    or ast.unparse(n.targets[0]).startswith("self.")
                    and not ast.unparse(n.targets[0]).startswith("self.core.")
                    for n in node.orelse
                )
    source = ast.unparse(fn("science/sim.py", "init_dynamics", "Simulator"))
    assert (
        source.index("if p.molecules_enabled:")
        < source.index("if p.grn_enabled:")
        < source.index("self.rho_pump = 1")
    )
    assert "self.molecules = None" not in source and "self.grn = None" not in source
    loop = next(
        n
        for n in fn("science/sim.py", "_run_sim_core_loop", "Simulator").body
        if isinstance(n, ast.For)
    )
    guards = [
        n
        for n in loop.body
        if isinstance(n, ast.If) and ast.unparse(n.test) in ("p.molecules_enabled", "p.grn_enabled")
    ]
    assert [ast.unparse(n.test) for n in guards] == ["p.molecules_enabled", "p.grn_enabled"]
    for guard in guards:
        text = ast.unparse(guard)
        assert (
            text.index(".clear_run_loop(")
            < text.index(".run_loop_transporters(")
            < text.index(".run_loop_channels(")
            < text.index(".run_loop_modulators(")
            < text.index(".run_loop(")
        )
    channels = ast.unparse(
        fn("science/chemistry/networks.py", "run_loop_channels", "MasterOfNetworks")
    )
    assert "phase.kind is SimPhaseKind.INIT and chan.init_active is False" in channels
    clear = ast.unparse(fn("science/sim.py", "clear_storage", "Simulator"))
    assert "if p.molecules_enabled:" in clear and "if p.grn_enabled:" in clear
    cc = fn("science/chemistry/networks.py", "clear_cache", "MasterOfNetworks")
    fields = {
        n.attr
        for n in ast.walk(cc)
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
    }
    assert "flux_time" in fields and "flux" not in fields
    tissue = ast.unparse(fn("science/chemistry/networks.py", "tissue_init", "MasterOfNetworks"))
    assert "p.substances_affect_charge and self.charge_has_been_balanced is False" in tissue
    assert "mol.c_cello" in tissue and "mol.c_envo" in tissue
    core = ast.unparse(fn("science/chemistry/networks.py", "run_loop", "MasterOfNetworks"))
    assert "for rn in self.reactions" in core
    hashes = {}
    for path in sorted(NATIVE.rglob("*.py")):
        name = str(path.relative_to(NATIVE))
        assert sha(path) == sha(INSTALLED / name), name
        hashes[name] = sha(path)
    assert len(hashes) == 332
    parents = {}
    for key, (name, pin) in PARENTS.items():
        path = BASE / name
        assert sha(path / "MANIFEST.json") == pin, key
        parents[key] = dict(
            path=str(path), manifest_sha256=pin, inputs_sha256=sha(path / "inputs.json")
        )
    findings = [
        "SimPhase sets _run_sim from kind and chooses phase dt/resample/total before the core loop; source labels are linspace(0,N*dt,N), distinct from accumulated material dt.",
        "Both INIT and SIM FULL loops dispatch general then GRN, each clear/transporters/channels/modulators/run_loop, without a SIM-only transporter guard.",
        "INIT skips channels whose init_active is False; SIM runs them. Constructor and hot-call histories must remain phase-specific.",
        "Enabled owner with no object takes the real cold reader; enabled existing owner takes real reinitialize. Disabled flags do not delete existing objects.",
        "Reinitialize retains core and molecule objects and skips read_substances; tissue_init updates parameters and generated expressions.",
        "tissue_init may conditionally balance primary charge when publication becomes enabled and that owner has not balanced before; it uses saved c_cello/c_envo values, not an assumed live amount.",
        "Non-null transporter configuration rebuilds its ordered objects and resets flux to constructor None. A null configuration only clears the owner dispatch flag and retains old transporter objects/fluxes.",
        "Channel and modulator null configurations likewise retain old dictionaries. Reaction null configuration can retain old reactions used by core.run_loop despite the owner flag being false.",
        "clear_storage calls clear_cache only on enabled owners. clear_cache resets time-storage lists, not transporter flux or molecular concentration state.",
        "CaATP/NaK cache attributes are not blanket-cleared by source clear_storage; phase journal, clock, bootstrap field and dynamic block stores have separate reset/carry rules.",
        "sim_eosmosis and Ca_dyn remain source-disabled; missing-general-section molecules_enabled obstruction remains. No whole physical initializer or parser is attested.",
    ]
    result = dict(
        kind="cells.general_molecule_active_transport_phase_boundary@1",
        status="native_phase_boundary_audited_reference_dependency_held",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        methods=methods,
        native_python_sha256=hashes,
        dependencies=parents,
        INIT04=dict(
            status="awaiting_exact_Chief_receipt",
            reference_adoption_authorized=False,
            reason="Chief is freezing reviewed scalar-owner event reference fix; no requiring reference is adopted before exact receipt.",
        ),
        source_findings=findings,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
    )
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    output = WORK / "betse_normal_ecm_molecule_lifecycle_boundary_01.json"
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                output=str(output),
                sha256=sha(output),
                native_methods=len(methods),
                native_files=len(hashes),
            )
        )
    )


if __name__ == "__main__":
    main()
