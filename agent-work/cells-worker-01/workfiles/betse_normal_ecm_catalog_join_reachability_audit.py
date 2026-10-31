"""Whole pinned-source modern-channel audit; no model imports or execution."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0")
INSTALLED = Path("/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def functions(node):
    return {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}


def classes(node):
    return {n.name: n for n in node.body if isinstance(n, ast.ClassDef)}


def audit():
    inventory = json.loads(
        (ROOT / "validation/betse/betse_normal_catalog_join_inventory.json").read_text()
    )
    assert inventory["class_count"] == 55
    assert sha(ROOT / inventory["generated_module"]) == inventory["generated_sha256"]
    trees, source_sha = {}, {}
    legacy_calls = []
    for p in sorted((PIN / "betse").rglob("*.py")):
        relative = str(p.relative_to(PIN))
        assert p.read_bytes() == (INSTALLED / relative).read_bytes(), relative
        source_sha[relative] = sha(p)
        tree = ast.parse(p.read_text())
        trees[relative] = tree
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and (
                (isinstance(n.func, ast.Name) and n.func.id == "cagPotassium")
                or isinstance(n.func, ast.Attribute)
                and n.func.attr == "cagPotassium"
            ):
                legacy_calls.append(dict(path=relative, line=n.lineno, expression=ast.unparse(n)))
    assert len(trees) == 332 and not legacy_calls
    network = classes(trees["betse/science/chemistry/networks.py"])
    master = functions(network["MasterOfNetworks"])
    factory = functions(network["Channel"])["init_channel"]
    reader = master["read_channels"]
    assert "self.channels = OrderedDict({})" in ast.unparse(reader)
    runner = master["run_loop_channels"]
    gene = functions(classes(trees["betse/science/chemistry/gene.py"])["MasterOfGenes"])[
        "read_gene_config"
    ]
    sim = functions(classes(trees["betse/science/sim.py"])["Simulator"])
    loop = next(n for n in sim["_run_sim_core_loop"].body if isinstance(n, ast.For))
    ca = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.ions_dict['Ca'] == 1"
    )
    grn = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.grn_enabled"
    )
    commit = next(
        i
        for i, n in enumerate(loop.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "self.update_all_concs(cells, p)"
    )
    assert ca < grn < commit
    text = ast.unparse(loop.body[grn])
    assert (
        text.index("clear_run_loop(")
        < text.index("run_loop_channels(")
        < text.index("run_loop_modulators(")
        < text.index("run_loop(phase=phase, t=t)")
    )
    pop = next(
        n
        for n in ast.walk(runner)
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "enumerate(self.channels)"
    )
    poptext = ast.unparse(pop)
    assert (
        poptext.index("eval(chan.alpha_eval_string")
        < poptext.index("chan.channel_core.run(sim.vm, p)")
        < poptext.index("for ion, rel_perm")
    )
    for needed in (
        "cenv[cells.map_mem2ecm]",
        "cmem = self.cell_concs[ion][cells.mem_to_cells]",
        "sim.vm, sim.T, p",
        "rho=sim.rho_channel",
        "ignoreECM=True",
        "self.extra_J_mem += -f_ED * p.F * zzz",
        "chan.channel_core.chan_flux = f_ED",
        "chan.channel_core.DChan = DChan",
    ):
        assert needed in poptext, needed
    assert "sim.fluxes_mem[" not in poptext
    assert "phase.kind is SimPhaseKind.INIT and chan.init_active is False" in poptext
    assert "self.core.read_channels(channels_config, phase)" in ast.unparse(gene)
    assert "self.channels = True" in ast.unparse(gene)
    assert "self.channel_core.init(sim.vm, cells, p, targets=targets)" in ast.unparse(factory)
    assert "sim.dyna.tissue_target_inds[profile]" in ast.unparse(factory)
    assert "p.expression_data[self.name]" in ast.unparse(factory)
    expected_families = {
        "Na": "vgna",
        "K": "vgk",
        "Cl": "vgcl",
        "Ca": "vgca",
        "Fun": "vgfun",
        "Cat": "vgcat",
        "ML": "vgml",
    }
    for family, module in expected_families.items():
        branch = next(
            n
            for n in ast.walk(factory)
            if isinstance(n, ast.If) and ast.unparse(n.test) == f"ion_string == '{family}'"
        )
        assert ast.unparse(branch.body[0]) == f"class_string = {module}"
    proof = {}
    p_attributes = set()
    routed_ca = 0
    for name, row in inventory["classes"].items():
        assert row["family"] in expected_families
        original = classes(trees[row["source"]])
        assert name in original and row["original_base"] in original
        methods = functions(original[name])
        assert {"_init_state", "_calculate_state"} <= methods.keys()
        relevant = [original[name], original[row["original_base"]]]
        for node in relevant:
            assert not any(isinstance(n, ast.Name) and n.id == "sim" for n in ast.walk(node)), name
            p_attributes |= {
                n.attr
                for n in ast.walk(node)
                if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name)
                and n.value.id == "p"
            }
        routed_ca += any(ion == "Ca" for ion, weight in row["routes"])
        proof[name] = dict(
            family=row["family"],
            source=row["source"],
            source_sha256=source_sha[row["source"]],
            original_base=row["original_base"],
            routes=row["routes"],
            factory_reachable=True,
            constructor_and_gate_methods={
                k: hashlib.sha256(
                    ast.dump(methods[k], include_attributes=False).encode()
                ).hexdigest()
                for k in ("_init_state", "_calculate_state")
            },
        )
    clock = classes(trees["betse/science/channels/channelsabc.py"])["ChannelsABC"]
    p_attributes |= {
        n.attr
        for n in ast.walk(clock)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "p"
    }
    assert p_attributes == {"dt"} and routed_ca == 23
    current = functions(
        ast.parse((ROOT / "src/cells/processes/betse_ecm_grn_source.py").read_text())
    )
    assert "channels" not in ast.literal_eval(
        next(
            n
            for n in ast.walk(current["validate_definition"])
            if isinstance(n, ast.Set)
            and any(isinstance(x, ast.Constant) and x.value == "biomolecules" for x in n.elts)
        )
    )
    restore = ast.unparse(current["restore"])
    assert "net.channels" in restore and "OrderedDict()" in restore
    inherited_ref = (ROOT / "validation/betse/betse_ecm_grn_reference.py").read_text()
    assert 'inputs["incoming_channel_current_A_m2"]' in inherited_ref
    influencers = ast.unparse(master["get_influencers"])
    assert "self.mem_concs" in influencers and "cells.map_mem2ecm" in influencers
    return dict(
        kind="cells.normal_ecm_modern_catalog_reachability@1",
        Python_files=332,
        installed_exact=True,
        original_source_sha256=source_sha,
        catalog_inventory_sha256=sha(
            ROOT / "validation/betse/betse_normal_catalog_join_inventory.json"
        ),
        unchanged_catalog_port_sha256=inventory["generated_sha256"],
        class_count=55,
        families=expected_families,
        Ca_routing_classes=23,
        gate_p_parameter_reads=sorted(p_attributes),
        implicit_free_Ca_class_gating=False,
        modern_class_proof=proof,
        modern_numeric_methods=110,
        source_order=(
            "ordinary refresh -> CaATP -> GRN clear -> channels -> modulators -> "
            "chemistry -> deferred commit -> full fields"
        ),
        read_time=(
            "Cold init uses prepared initial Vm before bootstrap. Population gates use "
            "current Vm once; ordered routes gather current bulk by owner, mapped full grid, "
            "Vm/runtime T/rho and write aliases immediately"
        ),
        explicit_Ca_modulators=(
            "Native read_channels/get_influencers may read membrane Ca or "
            "mapped environmental Ca; no implicit class free-Ca input"
        ),
        route_policy=(
            "No ordinary fluxes_mem write; core extra_J_mem carries channel current "
            "into later chemistry/publication. Last-route chan_flux/DChan retained; "
            "zero-weight Ca route still executes and increments nonce"
        ),
        cold_flag=(
            "Original MasterOfGenes.read_gene_config reads actual channel config and "
            "sets owner.channels; no injected true flag"
        ),
        required_new_seams=[
            "Own extended literal reader/factory/scientific namespace",
            "Own complete channel/core cache, gate-memory and hot restoration",
            "Actual before-channels and post-channels/pre-modulator conditional checkpoints",
            "Explicit original tissue-index preparation for named profile targets",
        ],
        existing_GRN_adapter_accepts_channels=False,
        existing_GRN_cache_contains_channel_state=False,
        old_whole_catalog_join_reused_as_ECM_or_active_CaATP=False,
        scoped_refusals=[
            "Expression/tissue-map lifecycle beyond explicit profile preparation",
            "Legacy cagPotassium has no built-in runtime caller and is not a modern factory class",
            "Forced INIT execution/skip in normal SIM",
            "Unsupported ion roles/families and missing or changed owner/cache",
        ],
        legacy_cagPotassium_runtime_calls=legacy_calls,
        old_Cav_G_failed_nominal_reclassified=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / "betse_normal_ecm_catalog_join_reachability_01.json"
    with path.open("x") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(
        json.dumps(
            dict(
                status="native_modern_catalog_reachable_with_explicit_new_bridges",
                classes=55,
                Ca_routes=23,
                source_files=332,
                witness=str(path),
                sha256=sha(path),
                scientific_imports=0,
                numerical_runs=0,
            )
        )
    )
