"""Installed-exact native cutting lifecycle source/capability audit; no science."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_native_cut_lifecycle"
SOURCE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def method(path, cls, name):
    tree = ast.parse((SOURCE / path).read_text())
    parent = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in parent.body if isinstance(n, ast.FunctionDef) and n.name == name)


def record(path, cls, name):
    node = method(path, cls, name)
    calls = sorted(
        (n for n in ast.walk(node) if isinstance(n, ast.Call)),
        key=lambda n: (n.lineno, n.col_offset),
    )
    writes = sorted(
        (
            n
            for n in ast.walk(node)
            if isinstance(n, (ast.Attribute, ast.Subscript)) and isinstance(n.ctx, ast.Store)
        ),
        key=lambda n: (n.lineno, n.col_offset),
    )
    return dict(
        path=path,
        cls=cls,
        name=name,
        first_line=node.lineno,
        last_line=node.end_lineno,
        AST_sha256=sha(ast.dump(node, include_attributes=False).encode()),
        calls=[dict(line=n.lineno, function=ast.unparse(n.func)) for n in calls],
        writes=[dict(line=n.lineno, target=ast.unparse(n)) for n in writes],
    )


def audit():
    hashes = {}
    for path in sorted((SOURCE / "betse").rglob("*.py")):
        relative = str(path.relative_to(SOURCE))
        data = path.read_bytes()
        assert data == (INSTALLED / relative).read_bytes(), relative
        hashes[relative] = sha(data)
    assert len(hashes) == 332
    tissue = "betse/science/tissue/tishandler.py"
    chemistry = "betse/science/chemistry/networks.py"
    selected = {
        tissue: (
            "TissueHandler",
            (
                "_cut_cells",
                "fire_events",
                "_fire_events_tissue",
                "init_profiles",
                "init_events",
                "_finalize_events_global",
                "_finalize_events_tissue",
                "makeAllChanges",
            ),
        ),
        "betse/science/cells.py": (
            "Cells",
            (
                "cellVerts",
                "cellMatrices",
                "intra_updater",
                "cell_vols",
                "mem_processing",
                "near_neigh",
                "calc_gj_vects",
                "environment",
                "make_maskM",
                "graphLaplacian",
                "redo_gj",
                "deform_tools",
            ),
        ),
        "betse/science/math/mesh.py": (
            "DECMesh",
            ("cut_mesh", "create_tri_map", "create_mappings", "create_core_operators"),
        ),
        "betse/science/sim.py": (
            "Simulator",
            ("initDenv", "fast_sim_init", "init_dynamics", "_run_sim_core_loop"),
        ),
        chemistry: ("MasterOfNetworks", ("mod_after_cut_event", "redefine_dynamic_dics")),
    }
    methods = {}
    for path, (cls, names) in selected.items():
        for name in names:
            methods[cls + "." + name] = record(path, cls, name)
    tree = ast.parse((SOURCE / chemistry).read_text())
    molecule = next(
        cls
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        and any(isinstance(n, ast.FunctionDef) and n.name == "remove_cells" for n in cls.body)
    )
    methods[molecule.name + ".remove_cells"] = record(chemistry, molecule.name, "remove_cells")
    methods[molecule.name + ".init_growth"] = record(chemistry, molecule.name, "init_growth")
    cut = method(tissue, "TissueHandler", "_cut_cells")
    body = ast.unparse(cut)
    first_geom = next(
        i
        for i, n in enumerate(cut.body)
        if isinstance(n, ast.Assign) and "cells.mesh.cut_mesh" in ast.unparse(n)
    )
    prefix = cut.body[:first_geom]
    calls = [n["function"] for n in methods["TissueHandler._cut_cells"]["calls"]]
    required = [
        "tissue_picker.pick_cells_and_mems",
        "cells.mesh.cut_mesh",
        "cells.cellVerts",
        "cells.cellMatrices",
        "cells.intra_updater",
        "cells.cell_vols",
        "cells.mem_processing",
        "cells.near_neigh",
        "cells.calc_gj_vects",
        "cells.environment",
        "cells.make_maskM",
        "cells.graphLaplacian",
        "sim.grn.core.mod_after_cut_event",
        "sim.initDenv",
        "self.init_profiles",
        "cells.redo_gj",
    ]
    positions = [calls.index(name) for name in required]
    assert positions == sorted(positions)
    assert "sim.__dict__.keys()" in body and "np.delete(data, target_inds_cell)" in body
    assert "specials_list.remove('cc_env')" in body
    assert body.index("if len(data) == len(cells.cell_i)") < body.index(
        "elif len(data) == len(cells.mem_i)"
    )
    assert "del data[index]" in body and "data2.append(data[index])" in body
    assert "sim.initDenv(cells, p)" in body
    assert "sim.sigma_env =" not in body and "sim.ko_env =" not in body
    network = ast.unparse(method(chemistry, "MasterOfNetworks", "mod_after_cut_event"))
    assert (
        network.index("obj.remove_cells(")
        < network.index("obj.update_transporter(")
        < network.index("obj.init_channel(")
    )
    molecule_body = ast.unparse(method(chemistry, molecule.name, "remove_cells"))
    assert "self.cc_grad_x = cgx2[:]" in molecule_body and "self.flux_intra =" not in molecule_body
    assert "phase.dyna.init_profiles(phase)" in molecule_body
    outer = ast.unparse(method(tissue, "TissueHandler", "_fire_events_tissue"))
    assert (
        outer.index("self._cut_cells(")
        < outer.index("self.init_profiles(phase)")
        < outer.index("self.init_events(phase)")
        < outer.index("self.event_cut.fire(")
    )
    return dict(
        kind="cells.native_cut_lifecycle_source_capability_audit@1",
        installed_exact=True,
        Python_files=332,
        original_source_sha256=hashes,
        methods=methods,
        prefix_boundary=dict(
            statement_index=first_geom,
            line=cut.body[first_geom].lineno,
            statement=ast.unparse(cut.body[first_geom]),
            preceding_statement_count=len(prefix),
            first_unowned_capability="DEC_mesh_cut_and_core_rebuild",
            prefix_AST_sha256=sha(
                ast.dump(
                    ast.Module(body=prefix, type_ignores=[]), include_attributes=False
                ).encode()
            ),
        ),
        direct_cut_order=required,
        outer_order=[
            "for each named cut: native _cut_cells",
            "data_length refresh",
            "init_profiles again",
            "redo_gj again",
            "init_events/global+tissue finalization",
            "event_cut.fire only after all successful",
            "voltage event",
            "outer makeAllChanges",
        ],
        profile_reinitialization=(
            "Each molecule.remove_cells invokes init_profiles before its own "
            "init_growth; inner _cut_cells invokes it again; outer cut dispatch "
            "invokes it again after all cuts. Repeated pickers and RNG sites remain "
            "separate actual calls."
        ),
        owner_semantics=dict(
            native=(
                "Hardcoded nested-name set and cell-first length heuristics; "
                "np.delete defaults to flattening without axis; arbitrary simulator "
                "attributes and histories are scanned."
            ),
            Cells=(
                "Existing betse_tissue_cut explicit owner-domain/axis/stable-ID maps "
                "are a separate conservative policy, not native deletion equivalence."
            ),
            empty=(
                "Original call still rebuilds mesh/profiles/diffusion for an empty "
                "typed selection; cannot treat native no-op as stable CutPlan.changed"
                " False."
            ),
            sequential=(
                "Multiple cut profiles select against each newly changed world; no "
                "pre-union of initial indices."
            ),
            aliases=(
                "Lists mutate in place and then retain only data[index]; data2 may be"
                " stale/unbound for unmatched nested rows. Capture full available "
                "parent/partial and original exception."
            ),
        ),
        cache_semantics=dict(
            diffusion=(
                "initDenv resets "
                "D_env,D_env_weight,D_env_weight_base,TJ_modulator,TJ_targets,Chi; no"
                " reinitialization of D_env_base shown in _cut_cells."
            ),
            profiles=(
                "init_profiles writes current Dm_cells; outer makeAllChanges later "
                "overwrites it from retained/deleted Dm_base+Dm_scheduled, not newly "
                "fabricated bases."
            ),
            fields=(
                "Geometry/graph operators rebuilt; sigma_env/ko_env and other "
                "initializer caches are not explicitly refreshed here; shape "
                "coincidences cannot authorize cache reuse."
            ),
            molecules=(
                "remove_cells deletes cell/membrane concentrations, refreshes "
                "profiles/growth, preserves ECM arrays; flux_intra deletion is "
                "assigned to cc_grad_x while old flux_intra persists."
            ),
            channels=(
                "Actual init_channel is called again after molecules/transporters, "
                "resetting gate/route/core state; no hot gate remap or constructor "
                "skipping."
            ),
            rate_RNG=(
                "Source dynamic/cache clocks and complete local RNG/repeated "
                "picker/finalizer epochs need explicit records. Source cut does not "
                "supply a sealed full ordinary checkpoint."
            ),
        ),
        findings=[
            (
                "ECM cc_env is excluded from special nesting but still enters generic"
                " length classification; species count equal cell/membrane count can "
                "corrupt a global grid array."
            ),
            (
                "Scalar NumPy arrays can fail len; nested unknown lengths can reuse "
                "stale data2 or raise; list deletion can fail after partial mutation."
            ),
            (
                "DEC cut_mesh documentation promises restructure edge indices but "
                "returns removed edges; dangling geometry/operator limitations remain"
                " unqualified."
            ),
            (
                "ATP/cell-content release and sigma recomputation are commented out, "
                "not native material/energy mechanisms."
            ),
            (
                "Native source repeats profile mapping and callback/finalizer "
                "construction; RNG consumption cannot be replaced by one old owner "
                "map or one seed."
            ),
        ],
        admissible_implementation=dict(
            prefix=(
                "Literal native deletion/hurt/ECM-target/vertex prefix up to the "
                "first mesh call, preserving all actual arrays/alias mutations and "
                "failure partials. No mesh or source numerical evaluation during "
                "preparation."
            ),
            explicit_owner_sidecar=(
                "Reuse existing stable CutPlan/OwnedField removal ledgers separately "
                "from native arrays, recording disagreement instead of repairing "
                "source."
            ),
            lifecycle=(
                "Ordered capability and epoch/invalidation gate for source "
                "continuation; require explicit changing geometry, operators, "
                "diffusion, profile/callback/RNG, GRN/channel and typed checkpoint "
                "owners."
            ),
            refusal=(
                "Current frozen ordinary event state cannot be resumed after cut. "
                "Missing/unqualified geometry or owner/rebind evidence is a "
                "deliberate prerequisite refusal, retaining prefix return and source "
                "failure evidence."
            ),
            credit=(
                "Source conditional prefix/capability preparation only; zero "
                "physical-mesh, complete native-cut, whole-loop or "
                "conservation/biological credit."
            ),
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        active_job_queries=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / (PREFIX + "_source_witness_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status="static_source_capability_audit_passed",
                methods=len(result["methods"]),
                Python_files=332,
                prefix_boundary=result["prefix_boundary"],
                numerical_runs=0,
            ),
            sort_keys=True,
        )
    )
