"""Stdlib-only lifecycle/ownership audit; reads source, never imports science."""

import ast
import hashlib
import json
from pathlib import Path

NATIVE_FILES = (
    "betse/science/simrunner.py",
    "betse/science/sim.py",
    "betse/science/cells.py",
    "betse/science/filehandling.py",
    "betse/science/parameters.py",
    "betse/science/phase/phasecls.py",
    "betse/science/tissue/tishandler.py",
    "betse/science/chemistry/gene.py",
    "betse/science/chemistry/networks.py",
    "betse/science/physics/ion_current.py",
    "betse/science/physics/pressures.py",
    "betse/science/physics/deform.py",
    "betse/lib/yaml/yamlalias.py",
    "betse/util/type/descriptor/expralias.py",
)
CORE = "src/cells/processes/betse_normal_ecm_initialization.py"
COMPONENTS = (
    "src/cells/processes/betse_normal_ecm_field_join.py",
    "src/cells/processes/betse_normal_ecm_calcium_join.py",
    "src/cells/processes/betse_normal_ecm_mechanics_join.py",
    "src/cells/processes/betse_ecm_grn_source.py",
    "src/cells/processes/betse_ecm_grn_join.py",
    "src/cells/processes/betse_mechanics_join.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return ast.parse(Path(path).read_bytes())


def function(module, name, cls=None):
    body = module.body
    if cls:
        body = next(n.body for n in body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name)


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def calls(node, expression):
    return sorted(
        (
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == expression
        ),
        key=lambda n: n.lineno,
    )


def targets(node):
    if isinstance(node, ast.Assign):
        return node.targets
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return [node.target]
    return []


def assignments(node, target):
    def unpack(value):
        if isinstance(value, (ast.Tuple, ast.List)):
            return [item for child in value.elts for item in unpack(child)]
        return [value]

    return sorted(
        (
            n
            for n in ast.walk(node)
            if any(ast.unparse(t) == target for root in targets(n) for t in unpack(root))
        ),
        key=lambda n: n.lineno,
    )


def attribute_inventory(node, receivers):
    result = {}
    for receiver in receivers:
        rows = {}
        for n in ast.walk(node):
            if (
                isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id == receiver
            ):
                row = rows.setdefault(n.attr, dict(read_lines=[], write_lines=[]))
                row["write_lines" if isinstance(n.ctx, ast.Store) else "read_lines"].append(
                    n.lineno
                )
        result[receiver] = {
            name: {k: sorted(set(v)) for k, v in row.items()} for name, row in sorted(rows.items())
        }
    return result


def one_call(node, name, path):
    found = calls(node, name)
    assert len(found) == 1, (name, len(found))
    return site(path, found[0]) | dict(expression=ast.unparse(found[0]))


def audit(checkout, project):
    """Return source facts and explicit missing seams, with AST witnesses."""
    checkout, project = Path(checkout), Path(project)
    parsed = {path: tree(checkout / path) for path in NATIVE_FILES}
    runner_path, sim_path = "betse/science/simrunner.py", "betse/science/sim.py"
    runner, sim = parsed[runner_path], parsed[sim_path]
    methods = {
        name: function(runner, name, "SimRunner")
        for name in ("seed", "init", "sim", "_die_if_seed_differs")
    }
    simulator = {
        name: function(sim, name, "Simulator")
        for name in (
            "init_core",
            "init_dynamics",
            "initDenv",
            "run_sim_core",
            "clear_storage",
            "update_V",
            "update_gj",
            "ca_handler",
            "_run_sim_core_loop",
            "_pickle_phase",
            "_plot_loop",
        )
    }
    seed_calls = [
        one_call(methods["seed"], expr, runner_path)
        for expr in (
            "phase.cells.make_world",
            "phase.sim.init_core",
            "phase.dyna.init_profiles",
            "phase.cells.redo_gj",
            "phase.cells.graphLaplacian",
            "phase.cells.save_cluster",
        )
    ]
    assert [r["first_line"] for r in seed_calls] == sorted(r["first_line"] for r in seed_calls)
    graph_call = calls(methods["seed"], "phase.cells.graphLaplacian")[0]
    assert any(isinstance(n, ast.Expr) and n.value is graph_call for n in methods["seed"].body)
    init_calls = [
        one_call(methods["init"], expr, runner_path)
        for expr in (
            "fh.loadWorld",
            "self._die_if_seed_differs",
            "phase.sim.init_core",
            "phase.sim.run_sim_core",
        )
    ]
    sim_calls = [
        one_call(methods["sim"], expr, runner_path)
        for expr in (
            "fh.loadSim",
            "self._die_if_seed_differs",
            "sim.run_sim_core",
        )
    ]
    assert not calls(methods["sim"], "sim.init_core") and not calls(
        methods["sim"], "phase.sim.init_core"
    )
    run_calls = [
        one_call(simulator["run_sim_core"], expr, sim_path)
        for expr in (
            "self.init_dynamics",
            "self.clear_storage",
            "self.update_V",
            "self._plot_loop",
        )
    ]
    assert [r["first_line"] for r in run_calls] == sorted(r["first_line"] for r in run_calls)
    dynamics = simulator["init_dynamics"]
    hot_call = one_call(dynamics, "self.grn.reinitialize", sim_path)
    cold_call = one_call(dynamics, "self.grn.read_gene_config", sim_path)
    noisy_call = one_call(dynamics, "np.random.random", sim_path)
    assert any(
        isinstance(n, ast.Assign)
        and any(c is calls(dynamics, "np.random.random")[0] for c in ast.walk(n.value))
        for n in dynamics.body
    )
    stored_keys = (
        "P_mod",
        "P_base",
        "Dm_base",
        "Dm_scheduled",
        "CaATP_block",
        "rho_pump",
        "div_u_osmo",
        "sigma",
        "ko_env",
    )
    dynamics_stores = {}
    for key in stored_keys:
        nodes = assignments(dynamics, "self." + key)
        assert nodes, key
        dynamics_stores[key] = [site(sim_path, n) | dict(statement=ast.unparse(n)) for n in nodes]
    assert not assignments(simulator["init_core"], "self.Egj")
    assert len(assignments(simulator["update_gj"], "self.Egj")) == 1
    assert not assignments(simulator["init_core"], "self.rate_CaATP")
    assert not assignments(dynamics, "self.rate_CaATP")
    assert not any(
        isinstance(n, ast.Delete) and "self.rate_CaATP" in ast.unparse(n) for n in ast.walk(sim)
    )
    mechanical_missing = (
        "osmo_P_cell",
        "osmo_P_env",
        "osmo_P_delta",
        "u_osmo",
        "PP",
        "gPxc",
        "gPyc",
    )
    for key in mechanical_missing:
        assert not assignments(simulator["init_core"], "self." + key)
        assert not assignments(dynamics, "self." + key)
    pickle = simulator["_pickle_phase"]
    replacement = assignments(pickle, "phase.cells")
    assert (
        len(replacement) == 1 and ast.unparse(replacement[0].value) == "copy.deepcopy(self.cellso)"
    )
    clear_display = assignments(pickle, "self.cellso")
    assert len(clear_display) == 1 and ast.unparse(clear_display[0].value) == "None"
    dump = assignments(pickle, "datadump")
    assert len(dump) == 1 and ast.unparse(dump[0].value) == "[self, phase.cells, phase.p]"
    assert replacement[0].lineno < clear_display[0].lineno < dump[0].lineno
    gene_path = "betse/science/chemistry/gene.py"
    hot_gene = function(parsed[gene_path], "reinitialize", "MasterOfGenes")
    read_channels = one_call(hot_gene, "self.core.read_channels", gene_path)
    read_tissues = one_call(hot_gene, "self.core.tissue_init", gene_path)
    source_facts = []
    selected = [(runner_path, node, ("self",)) for node in methods.values()] + [
        (sim_path, node, ("self", "cells", "p")) for node in simulator.values()
    ]
    for path, name, cls, receivers in (
        ("betse/science/cells.py", "make_world", "Cells", ("self", "p")),
        ("betse/science/cells.py", "graphLaplacian", "Cells", ("self", "p")),
        ("betse/science/cells.py", "cellMatrices", "Cells", ("self", "p")),
        (
            "betse/science/tissue/tishandler.py",
            "init_profiles",
            "TissueHandler",
            ("self", "sim", "cells", "p"),
        ),
        (
            "betse/science/tissue/tishandler.py",
            "init_events",
            "TissueHandler",
            ("self", "sim", "cells", "p"),
        ),
        (gene_path, "reinitialize", "MasterOfGenes", ("self", "sim", "cells", "p")),
        (gene_path, "read_gene_config", "MasterOfGenes", ("self", "sim", "cells", "p")),
        (
            "betse/science/chemistry/networks.py",
            "tissue_init",
            "MasterOfNetworks",
            ("self", "sim", "cells", "p"),
        ),
        (
            "betse/science/chemistry/networks.py",
            "read_channels",
            "MasterOfNetworks",
            ("self", "sim", "cells", "p"),
        ),
        ("betse/science/physics/ion_current.py", "get_current", None, ("sim", "cells", "p")),
        ("betse/science/physics/pressures.py", "osmotic_P", None, ("sim", "cells", "p")),
        ("betse/science/physics/deform.py", "getDeformation", None, ("sim", "cells", "p")),
        ("betse/science/filehandling.py", "loadWorld", None, ()),
        ("betse/science/filehandling.py", "loadSim", None, ()),
    ):
        selected.append((path, function(parsed[path], name, cls), receivers))
    for path, node, receivers in selected:
        source_facts.append(
            site(path, node)
            | dict(
                name=node.name,
                attributes=attribute_inventory(node, receivers),
                call_sites=[
                    site(path, n) | dict(expression=ast.unparse(n.func))
                    for n in ast.walk(node)
                    if isinstance(n, ast.Call)
                ],
            )
        )
    component = {path: tree(project / path) for path in COMPONENTS}
    core_tree = tree(project / CORE)

    def core_literal(name):
        return ast.literal_eval(
            next(
                n.value
                for n in core_tree.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
            )
        )

    for name, (qualified, pin) in core_literal("NATIVE_TYPES").items():
        path = qualified.rsplit(".", 1)[0].replace(".", "/") + ".py"
        assert sha(checkout / path) == pin, name
    for path, pin in core_literal("NATIVE_DESCRIPTOR_SOURCES").items():
        assert path in NATIVE_FILES and sha(checkout / path) == pin, path
    alias_names = ast.literal_eval(
        next(
            n.value
            for n in core_tree.body
            if isinstance(n, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "NATIVE_PARAMETER_ALIASES" for t in n.targets
            )
        )
    )
    parameter_class = next(
        n
        for n in parsed["betse/science/parameters.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Parameters"
    )
    aliases = {
        n.targets[0].id: n
        for n in parameter_class.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) in ("yaml_alias", "yaml_enum_alias")
        and n.targets[0].id in alias_names
    }
    assert set(aliases) == set(alias_names)
    handoff = function(core_tree, "handoff")
    assert len(calls(handoff, "source.restore")) == 1
    assert len(calls(handoff, "field.reconstruct")) == 1
    forbidden = {
        "source.cold",
        "field.initialize",
        "calcium.initialize",
        "mechanical_field.initialize",
    }
    assert not any(calls(core_tree, name) for name in forbidden)
    for path in COMPONENTS[:3]:
        initializer = function(component[path], "initialize")
        assert calls(initializer, "source.cold") or calls(initializer, "field.initialize")
    initializers = {
        path: site(path, function(component[path], "initialize")) for path in COMPONENTS[:3]
    }
    preserve = dict(
        stable_initial_mesh=dict(
            status="reviewed_failure",
            complete_meshes="0/9",
            checks="23/32 plus 11/11 conditional source",
            review="/mnt/workspaces/Cells/stable-initial-mesh-preparation-20261030-01/root-review-01/REVIEW.json",
        ),
        native_mesh_lifecycle=dict(
            status="separate reviewed conditional lifecycle",
            checks=39,
            review="/mnt/workspaces/Cells/betse-mesh-lifecycle-preparation-20261030-01/root-review-01/REVIEW.json",
        ),
        original_ecm_material=dict(status="failed", checks="39/40", tolerance_unchanged=True),
    )
    return dict(
        kind="cells.normal_ecm_initialization_source_audit@1",
        native_source_sha256={path: sha(checkout / path) for path in NATIVE_FILES},
        component_sha256={path: sha(project / path) for path in COMPONENTS},
        lifecycle=dict(
            seed=seed_calls,
            init=init_calls,
            sim=sim_calls,
            phase_prefix=run_calls,
            seed_graph_unconditional=True,
            SIM_calls_init_core=False,
            handoff_boundary="after init_dynamics and clear_storage, before bootstrap update_V",
            snapshot_cannot_establish_caller_history=True,
        ),
        dynamics=dict(
            cold_owner=cold_call,
            hot_owner=hot_call,
            unconditional_noise_draw=noisy_call,
            rebuilt_stores=dynamics_stores,
            hot_reinitialize_reads_tissues=read_tissues,
            hot_reinitialize_recreates_channels=read_channels,
            primary_concentrations_not_reset_by_init_core_in_SIM=True,
        ),
        parameter_yaml_aliases={
            name: site("betse/science/parameters.py", node)
            | dict(expression=ast.unparse(node.value))
            for name, node in aliases.items()
        },
        serialization=dict(
            display_replaces_saved_cells=site(sim_path, replacement[0]),
            display_owner_cleared=site(sim_path, clear_display[0]),
            saved_tuple=site(sim_path, dump[0]),
            source_geometry_refresh_inferred=False,
        ),
        owner_source_facts=source_facts,
        component_cold_initializers=initializers,
        admission=dict(
            source_restore=one_call(handoff, "source.restore", CORE),
            bootstrap=one_call(handoff, "field.reconstruct", CORE),
            cold_calls=0,
            numerical_equations_copied=False,
            native_initializer_executed=False,
            classification="complete compatible supplied-owner boundary only",
        ),
        missing_seams=[
            dict(
                id="complete-native-geometry",
                reason=(
                    "Stable initial mesh has 0/9 complete meshes; conditional lifecycle "
                    "operators do not establish make_world"
                ),
                policy="preserve failure; no inferred geometry",
            ),
            dict(
                id="actual-init-load-chain",
                reason=(
                    "No complete seed, INIT trajectory, serialization/load and compatibility "
                    "receipt is supplied"
                ),
                policy="native initialization claim refused",
            ),
            dict(
                id="fresh-Egj",
                reason="init_core does not create Egj; update_gj first writes it",
                policy="retain absence and refuse complete material admission",
            ),
            dict(
                id="hot-GRN",
                reason=(
                    "SIM init_dynamics runs existing-owner reinitialize, including tissue "
                    "and channel reader reconstruction"
                ),
                policy=(
                    "admit actual supplied complete X/Y cache; "
                    "gates/transporters/mitochondria refused"
                ),
            ),
            dict(
                id="CaATP-rate",
                reason=(
                    "INIT-written rate_CaATP persists across init_dynamics; "
                    "existing calcium call-zero contract requires absence"
                ),
                policy="refuse persisted rate; never delete or cold-reset it",
            ),
            dict(
                id="unwritten-mechanics",
                reason=(
                    "Osmotic/pressure-gradient/PP stores are not all created "
                    "in core/dynamics initialization"
                ),
                policy="capture presence; complete mechanics only if every required store exists",
            ),
            dict(
                id="disabled-flow-representation",
                reason=(
                    "init_core stores u_env as scalar 0; the frozen composed mechanics input "
                    "requires matching grid arrays"
                ),
                policy="no silent shape expansion",
            ),
            dict(
                id="scalar-control-representation",
                reason=(
                    "Native disabled blockers may be scalar 1; frozen drive schema requires "
                    "complete membrane rows"
                ),
                policy="refuse incompatible scalar owners; no inferred broadcast",
            ),
            dict(
                id="deformation-pickle-geometry",
                reason=(
                    "_pickle_phase replaces saved cells with the display copy "
                    "when deformation is enabled"
                ),
                policy="validate supplied centres/maps/operators; no geometry repair",
            ),
            dict(
                id="events-pumps-clock",
                reason=(
                    "The supplied loop drives and bounded phase clock do not establish "
                    "tissue event or native pump histories"
                ),
                policy="explicit conditional input ownership only",
            ),
        ],
        retained_evidence=preserve,
        scope=dict(
            native_science_imported=False,
            fixtures_constructed=False,
            tests_collected=False,
            numerical_evaluations=False,
            active_jobs_polled=False,
            PROGRESS_edited=False,
            qualification_inherited=False,
            scientific_launch_gate=False,
        ),
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.checkout, args.project)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
