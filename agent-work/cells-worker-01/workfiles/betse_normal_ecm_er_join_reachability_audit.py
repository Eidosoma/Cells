"""Pinned-source ER reachability/order/ownership audit; no scientific module execution."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_er_join"
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")
REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
PARAMETERS = (
    "serca_max",
    "max_er",
    "act_Km_Ca",
    "act_n_Ca",
    "inh_Km_Ca",
    "inh_n_Ca",
    "act_Km_IP3",
    "act_n_IP3",
)
FIELDS = (
    "cc_er",
    "er_vol",
    "er_sa",
    "Ver",
    "Q",
    "cm_er",
    "Dm_er",
    "Dm_er_base",
    "Dm_channels",
    "zer",
)
REVIEW = Path(
    "/mnt/workspaces/Cells/betse-prepared-er-tests-20261030-02/root-review-01/REVIEW.json"
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def site(path, node):
    return dict(
        path=path,
        line=node.lineno,
        end_line=node.end_lineno,
        source=ast.unparse(node),
        AST_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def root_attribute(node):
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id, node.attr
    return None


def names(path, variable):
    tree = ast.parse(Path(path).read_text())
    assignment = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == variable
    )
    return ast.literal_eval(assignment.value)


def audit():
    prior_path = WORK / "betse_normal_ecm_calcium_join_reachability_01.json"
    prior = json.loads(prior_path.read_text())
    assert prior["source_revision"] == REVISION
    trees, hashes, flag_writes, flag_reads, lookups, kinetics, constructors = (
        {},
        {},
        [],
        [],
        [],
        {k: [] for k in PARAMETERS},
        [],
    )
    for path in sorted((NATIVE / "betse").rglob("*.py")):
        relative = str(path.relative_to(NATIVE))
        digest = sha(path)
        assert (
            digest == prior["source_inventory"][relative]["sha256"] == sha(INSTALLED / relative)
        ), relative
        hashes[relative] = digest
        tree = ast.parse(path.read_bytes())
        trees[relative] = tree
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for attr in ast.walk(target):
                        if isinstance(attr, ast.Attribute) and isinstance(attr.ctx, ast.Store):
                            if attr.attr == "Ca_dyn":
                                flag_writes.append(site(relative, node))
                            if attr.attr in kinetics:
                                kinetics[attr.attr].append(site(relative, node))
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "Ca_dyn"
                and isinstance(node.ctx, ast.Load)
            ):
                flag_reads.append(site(relative, node))
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in ("setattr", "getattr", "hasattr", "delattr")
                    and len(node.args) > 1
                    and isinstance(node.args[1], ast.Constant)
                ):
                    key = node.args[1].value
                    if key == "Ca_dyn":
                        lookups.append(site(relative, node))
                    if key in kinetics and node.func.id == "setattr":
                        kinetics[key].append(site(relative, node))
                if isinstance(node.func, ast.Name) and node.func.id == "EndoRetic":
                    constructors.append(site(relative, node))
    assert len(trees) == len(prior["source_inventory"]) == 332
    assert len(flag_writes) == 1 and flag_writes[0]["source"] == "self.Ca_dyn = False"
    assert not lookups and all(not value for value in kinetics.values())
    simtree = trees["betse/science/sim.py"]
    simulator = next(
        n for n in simtree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    methods = {n.name: n for n in simulator.body if isinstance(n, ast.FunctionDef)}
    constructor_guard = next(
        n
        for n in methods["init_dynamics"].body
        if isinstance(n, ast.If) and "p.Ca_dyn" in ast.unparse(n.test)
    )
    assert ast.unparse(constructor_guard.test) == "p.ions_dict['Ca'] == 1 and p.Ca_dyn"
    assert ast.unparse(constructor_guard.body[0]) == "self.endo_retic = EndoRetic(self, cells, p)"
    assert ast.unparse(constructor_guard.orelse[0]) == "self.endo_retic = None"
    assert len(constructors) == 1
    handler = methods["ca_handler"]
    er_guard = next(
        n for n in handler.body if isinstance(n, ast.If) and "p.Ca_dyn" in ast.unparse(n.test)
    )
    assert ast.unparse(er_guard.test) == "p.Ca_dyn == 1"
    assert ast.unparse(er_guard.body[0]) == "self.endo_retic.update(self, cells, p)"
    assert ast.unparse(handler.body[0].test) == "p.alpha_Ca > 0.0"
    assert handler.body.index(er_guard) > 0
    clear = next(
        n
        for n in methods["clear_storage"].body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.Ca_dyn"
    )
    sampled = next(
        n
        for n in methods["write2storage"].body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "p.Ca_dyn == 1 and p.ions_dict['Ca'] == 1"
    )
    start = ast.unparse(methods["run_sim_core"])
    assert (
        start.index("self.init_dynamics(phase)")
        < start.index("self.clear_storage(")
        < start.index("self.update_V(")
    )
    loop = next(n for n in methods["_run_sim_core_loop"].body if isinstance(n, ast.For))
    looptext = ast.unparse(loop)
    order = (
        "self.update_intra(",
        "self.ca_handler(",
        "self.molecules.core.run_loop(",
        "self.grn.core.run_loop(",
        "self.protein_noise_flux =",
        "osmotic_P(",
        "self.update_all_concs(",
        "self.update_V(",
        "stb.check_v(",
        "self.write2storage(",
    )
    offsets = [looptext.index(key) for key in order]
    assert offsets == sorted(offsets)
    assert not any(
        isinstance(n, ast.Call) and ast.unparse(n.func) == "self.ca_handler"
        for n in ast.walk(methods["_run_fast_sim_core_loop"])
    )
    erclass = next(
        n
        for n in trees["betse/science/organelles/endo_retic.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "EndoRetic"
    )
    ermethods = {n.name: n for n in erclass.body if isinstance(n, ast.FunctionDef)}
    pump = next(
        n
        for n in trees["betse/science/sim_toolbox.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "pumpCaER"
    )
    flux = next(
        n
        for n in trees["betse/science/sim_toolbox.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "electroflux"
    )
    contracts = {}
    for name in ("__init__", "channels", "update", "get_v", "clear_cache", "write_cache"):
        node = ermethods[name]
        reads = {
            owner: sorted(
                {
                    n.attr
                    for n in ast.walk(node)
                    if isinstance(n, ast.Attribute)
                    and isinstance(n.ctx, ast.Load)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == owner
                }
            )
            for owner in ("self", "sim", "cells", "p")
        }
        writes = {owner: set() for owner in ("self", "sim", "cells", "p")}
        for n in ast.walk(node):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for target in targets:
                    if (address := root_attribute(target)) and address[0] in writes:
                        writes[address[0]].add(address[1])
        contracts[name] = dict(
            site=site("betse/science/organelles/endo_retic.py", node),
            reads=reads,
            direct_or_indexed_writes={key: sorted(value) for key, value in writes.items()},
            alias_mutations_are_also_preserved_in_exact_AST=True,
        )
    update_text = ast.unparse(ermethods["update"])
    update_order = (
        "self.channels(",
        "stb.pumpCaER(",
        "sim.cc_cells[sim.iCa] =",
        "sim.cc_er[sim.iCa] =",
        "for i in sim.movingIons:",
        "stb.electroflux(",
        "self.get_v(",
    )
    indices = [update_text.index(key) for key in update_order]
    assert indices == sorted(indices)
    assert "cc_at_mem" not in contracts["update"]["direct_or_indexed_writes"]["sim"]
    assert contracts["update"]["direct_or_indexed_writes"]["sim"] == ["cc_cells", "cc_er"]
    for key in ("fluxes_mem", "fluxes_gj", "fluxes_env_x", "fluxes_env_y"):
        assert key not in contracts["update"]["direct_or_indexed_writes"]["sim"]
    channels = ast.unparse(ermethods["channels"])
    for fragment in (
        "sim.molecules.molecules",
        "sim.molecules.cell_concs['IP3']",
        "sim.metabo.core.cell_concs",
        "sim.grn.core.cell_concs",
    ):
        assert fragment in channels, fragment
    assert names(ROOT / "src/cells/processes/betse_endoretic_source.py", "FIELDS") == FIELDS
    assert names(ROOT / "src/cells/processes/betse_endoretic_source.py", "PARAMETERS") == PARAMETERS
    review = json.loads(REVIEW.read_text())
    assert (
        review["status"]
        == "accepted_scoped_prepared_state_native_correspondence_and_conditional_ER_checks"
        and not review["blockers"]
    )
    assert (
        review["counts"]["fresh_unique_pytest_passes"] == 23
        and review["counts"]["conditional_ER_points_including_diagnostics"] == 83
    )
    for path, expected in review["owned_sha256"].items():
        assert sha(ROOT / path) == expected, path
    binding = ast.unparse(
        next(
            n
            for n in ast.parse(
                (ROOT / "src/cells/processes/betse_normal_er_join.py").read_text()
            ).body
            if isinstance(n, ast.FunctionDef) and n.name == "bind"
        )
    )
    assert "explicit Ca_dyn1 and complete owned ER state" in binding
    native_sources = json.loads(
        (ROOT / "validation/betse/betse_prepared_er_join_protocol.json").read_text()
    )["native_source"]
    assert native_sources["revision"] == REVISION
    for name, expected in native_sources["source_sha256"].items():
        assert sha(NATIVE / name) == sha(INSTALLED / name) == expected, name
    own = Path(__file__)
    compile(own.read_text(), str(own), "exec")
    return dict(
        kind="cells.normal_ecm_er_ordinary_source_reachability_boundary@1",
        status="ordinary_route_blocked_by_native_loader_policy",
        source_revision=REVISION,
        checkout=str(NATIVE),
        installed_package=str(INSTALLED / "betse"),
        source_inventory_sha256=hashes,
        Python_files=332,
        all_installed_sources_exact=True,
        native_source_sha256={
            p: hashes[p]
            for p in (
                "betse/science/parameters.py",
                "betse/science/sim.py",
                "betse/science/sim_toolbox.py",
                "betse/science/organelles/endo_retic.py",
            )
        },
        prior_reachability_binding=dict(path=str(prior_path), sha256=sha(prior_path)),
        reachability_assumption=(
            "Ordinary Parameters.load-produced runtime without external flag, kinetic "
            "or ER-state injection"
        ),
        Ca_dyn_writes=flag_writes,
        Ca_dyn_reads=flag_reads,
        literal_flag_lookup_or_setter_calls=lookups,
        sole_Ca_dyn_value=False,
        ER_constructor_calls=constructors,
        constructor_guard=site("betse/science/sim.py", constructor_guard),
        update_guard=site("betse/science/sim.py", er_guard),
        clear_cache_guard=site("betse/science/sim.py", clear),
        sample_cache_guard=site("betse/science/sim.py", sampled),
        ordinary_outer_order=list(order),
        hypothetical_enabled_ER_inner_order=list(update_order),
        plasma_CaATP_independent_of_disabled_ER=True,
        ordinary_ER_owner=None,
        ordinary_ER_calls_reachable=False,
        source_loader_false_branch_discards_prior_ER_owner=True,
        FAST_has_no_ER_handler_call=True,
        ER_kinetic_native_producers=kinetics,
        missing_native_ER_kinetic_producers=list(PARAMETERS),
        required_ER_fields={
            key: (
                "scalar"
                if key == "cm_er"
                else "[ions,cells]"
                if key in ("cc_er", "Dm_er", "Dm_er_base", "Dm_channels", "zer")
                else "[cells]"
            )
            for key in FIELDS
        },
        required_owner_context=dict(
            required_presence_attributes=["sim.molecules", "sim.metabo", "sim.grn"],
            lookup_precedence=[
                "molecules.molecules + molecules.cell_concs[IP3]",
                "metabo.core.cell_concs[IP3]",
                "grn.core.cell_concs[IP3]",
            ],
            no_owner="Ca-only Hill modulation",
            owner_present_without_IP3="Zero IP3 multiplier",
            actual_modern_ECM_owner_alias_compatibility_not_qualified_here=True,
        ),
        required_shared_state=dict(
            ion_and_cell_owner_axes=True,
            Ca_valence=2,
            moving_ion_indices=True,
            cytosol_and_ER_all_ion_rows=True,
            cell_volume_and_surface_area=True,
            ER_volume_area_capacitance=True,
            runtime_temperature_and_phase_dt=True,
            maintained_pools_and_native_pump_constants=True,
            cell_count_before_literal_constructor=True,
            history_lists=["ver_time", "Ca_er_time"],
        ),
        source_contracts=contracts,
        SERCA_source=site("betse/science/sim_toolbox.py", pump),
        electroflux_source=site("betse/science/sim_toolbox.py", flux),
        material_charge_boundary=dict(
            direct_bulk_cytosol_and_ER_transfer=True,
            membrane_buffer_not_refreshed=True,
            no_ER_flux_written_to_outer_membrane_or_grid_flux_arrays=True,
            Q_and_Ver_recomputed_from_all_ER_ion_rows=True,
            no_new_activity_or_balance_evidence_from_this_static_audit=True,
        ),
        qualified_component_review=dict(
            path=str(REVIEW),
            sha256=sha(REVIEW),
            status=review["status"],
            counts=review["counts"],
            scope_limits=review["scope_limits"],
            owned_sha256=review["owned_sha256"],
        ),
        qualified_component_requires_explicit_Ca_dyn1_and_supplied_ER=True,
        existing_component_qualification_not_ordinary_reachability=True,
        native_initialization_restart_or_whole_solver_credit=False,
        new_ordinary_ER_accuracy_or_history_credit=0,
        ER_enabled_or_missing_defaults_injected=False,
        alternative_composition_implemented=False,
        all_old_source_guards_packets_and_failures_unchanged=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        active_job_queries=0,
        automatic_followup=False,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / (PREFIX + "_source_boundary_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                source_files=result["Python_files"],
                source_revision=REVISION,
                sha256=sha(path),
                missing_ER_kinetics=len(result["missing_native_ER_kinetic_producers"]),
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )
