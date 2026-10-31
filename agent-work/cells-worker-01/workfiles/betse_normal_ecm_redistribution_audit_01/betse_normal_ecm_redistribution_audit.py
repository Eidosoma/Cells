"""Read pinned sources only; never import or execute scientific modules."""

import ast
import hashlib
import json
from pathlib import Path

BASE = Path("/mnt/workspaces/Cells")
NATIVE = BASE / "betse-v1.5.0/betse"
INSTALLED = BASE / "venv-betse/lib/python3.13/site-packages/betse"
PARENTS = {
    "INIT02": (
        BASE / "betse-normal-ecm-init-phase-prepared-20261031-02",
        "528a1c7d1df0be152919b9dd446f3247676856585652f2c2924d82840c27d36f",
    ),
    "MOLECULE01": (
        BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01",
        "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922",
    ),
}
ATTRS = {
    "rho_pump",
    "rho_channel",
    "Ec",
    "D_membrane",
    "z_channel",
    "z_pump",
    "sim_eosmosis",
    "move_pumps_channels",
}
OUTPUT = Path(__file__).with_name("betse_normal_ecm_redistribution_audit_01.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Inventory(ast.NodeVisitor):
    def __init__(self, path):
        self.path = str(path)
        self.scope = []
        self.attributes = []
        self.writes = []
        self.dynamic = []
        self.movement_names = []

    def record(self, node):
        return dict(path=self.path, scope=".".join(self.scope), line=node.lineno)

    def visit_ClassDef(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_ClassDef
    visit_AsyncFunctionDef = visit_ClassDef

    def visit_Attribute(self, node):
        if node.attr in {"MoveChannel", "move_pumps_channels"}:
            self.movement_names.append(dict(self.record(node), expression=ast.unparse(node)))
        if node.attr in ATTRS:
            self.attributes.append(
                dict(
                    self.record(node),
                    attribute=node.attr,
                    context=type(node.ctx).__name__,
                    expression=ast.unparse(node),
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            for field in ast.walk(target):
                if isinstance(field, ast.Attribute) and field.attr in ATTRS:
                    self.writes.append(
                        dict(
                            self.record(node),
                            attribute=field.attr,
                            target=ast.unparse(target),
                            value=ast.unparse(node.value),
                            operation=type(node).__name__,
                        )
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.visit_Assign(
            ast.copy_location(
                ast.Assign(targets=[node.target], value=node.value or ast.Constant(None)), node
            )
        )

    def visit_AugAssign(self, node):
        for field in ast.walk(node.target):
            if isinstance(field, ast.Attribute) and field.attr in ATTRS:
                self.writes.append(
                    dict(
                        self.record(node),
                        attribute=field.attr,
                        target=ast.unparse(node.target),
                        value=ast.unparse(node.value),
                        operation=type(node).__name__,
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "setattr", "hasattr", "delattr"}
            and len(node.args) > 1
        ):
            key = node.args[1]
            if isinstance(key, ast.Constant) and key.value in ATTRS:
                self.dynamic.append(dict(self.record(node), expression=ast.unparse(node)))
        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id in {"MoveChannel", "move_channels", "move_pumps_channels"}:
            self.movement_names.append(dict(self.record(node), expression=node.id))


def main():
    checks, hashes, inventories, bindings = [], {}, [], []

    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))

    trees = {}
    for path in sorted(NATIVE.rglob("*.py")):
        rel = path.relative_to(NATIVE).as_posix()
        hashes[rel] = sha(path)
        check(
            "installed:" + rel, (INSTALLED / rel).is_file() and hashes[rel] == sha(INSTALLED / rel)
        )
        trees[rel] = ast.parse(path.read_text(), filename=str(path))
        inventory = Inventory(rel)
        inventory.visit(trees[rel])
        inventories.append(inventory)
    check("332 native Python sources", len(hashes) == 332)
    writes = [row for item in inventories for row in item.writes]
    expected = {
        ("science/parameters.py", "Parameters.load", "self.sim_eosmosis", "False"),
        ("science/sim.py", "Simulator.init_core", "self.Ec", "np.zeros(self.mdl)"),
        ("science/sim.py", "Simulator.init_dynamics", "self.rho_pump", "1"),
        ("science/sim.py", "Simulator.init_dynamics", "self.rho_channel", "1"),
        ("science/simrunner.py", "SimRunner.sim_grn", "phase.sim.rho_pump", "1.0"),
        ("science/simrunner.py", "SimRunner.sim_grn", "phase.sim.rho_channel", "1.0"),
        ("science/chemistry/networks.py", "MasterOfNetworks.optimizer", "sim.rho_channel", "1"),
        (
            "science/physics/move_channels.py",
            "MoveChannel.__init__",
            "sim.rho_pump",
            "np.ones(sim.mdl)",
        ),
        (
            "science/physics/move_channels.py",
            "MoveChannel.__init__",
            "sim.rho_channel",
            "np.ones(sim.mdl)",
        ),
        (
            "science/physics/move_channels.py",
            "MoveChannel.update_channel",
            "sim.rho_channel",
            "cpi + cfluxc * (cells.mem_sa / cells.mem_vol) * p.dt",
        ),
        (
            "science/physics/move_channels.py",
            "MoveChannel.update_pump",
            "sim.rho_pump",
            "cpi + cfluxp * (cells.mem_sa / cells.mem_vol) * p.dt",
        ),
    }
    actual = {(r["path"], r["scope"], r["target"], r["value"]) for r in writes}
    check("exhaustive explicit attribute/subscript writer set", actual == expected)
    check("all writes are plain assignments", all(r["operation"] == "Assign" for r in writes))
    check("no tracked literal dynamic attribute access", not any(i.dynamic for i in inventories))
    check("no active MoveChannel symbol usage", not any(i.movement_names for i in inventories))
    check(
        "no active redistribution imports",
        not any(
            isinstance(n, (ast.Import, ast.ImportFrom)) and "move_channels" in ast.unparse(n)
            for tree in trees.values()
            for n in ast.walk(tree)
        ),
    )
    toolbox = trees["science/sim_toolbox.py"]
    check(
        "toolbox has no scalar projector symbol",
        not any(
            getattr(n, "name", None) == "single_cell_div_free"
            or isinstance(n, ast.Name)
            and n.id == "single_cell_div_free"
            or isinstance(n, ast.alias)
            and (n.asname or n.name) == "single_cell_div_free"
            for n in ast.walk(toolbox)
        ),
    )
    cells = trees["science/cells.py"]
    projectors = [
        n
        for n in ast.walk(cells)
        if isinstance(n, ast.FunctionDef) and n.name == "single_cell_div_free"
    ]
    check(
        "Cells projector is a different two-component method",
        len(projectors) == 1 and [a.arg for a in projectors[0].args.args] == ["self", "uxo", "uyo"],
    )
    move = trees["science/physics/move_channels.py"]
    run = next(n for n in ast.walk(move) if isinstance(n, ast.FunctionDef) and n.name == "run")
    check(
        "original channel then pump order",
        [ast.unparse(n) for n in run.body]
        == ["self.update_channel(sim, cells, p)", "self.update_pump(sim, cells, p)"],
    )

    def anchor(origin, path, text):
        root = NATIVE if origin == "native" else PARENTS[origin][0] / "source"
        file = root / path
        data = file.read_text()
        check(origin + ":" + path + ":" + text[:65], text in data)
        if text in data:
            bindings.append(
                dict(
                    origin=origin,
                    path=path,
                    sha256=sha(file),
                    line=data[: data.index(text)].count("\n") + 1,
                    text=text,
                )
            )
        if origin != "native":
            manifest = json.loads((PARENTS[origin][0] / "MANIFEST.json").read_text())
            check("frozen member:" + path, manifest["files"].get("source/" + path) == sha(file))

    for origin, (root, digest) in PARENTS.items():
        check(origin + " manifest identity", sha(root / "MANIFEST.json") == digest)
    p = "src/cells/processes/"
    v = "validation/betse/"
    for origin, path, text in (
        (
            "native",
            "science/sim.py",
            "#     self.move_pumps_channels = MoveChannel(self, cells, p)",
        ),
        ("native", "science/parameters.py", "# self.D_membrane = float("),
        ("native", "science/parameters.py", "# self.z_channel = float("),
        ("native", "science/parameters.py", "# self.z_pump = float("),
        ("native", "science/sim.py", "fNa_NaK = self.rho_pump*fNa_NaK"),
        ("native", "science/sim.py", "fK_NaK = self.rho_pump*fK_NaK"),
        ("native", "science/sim.py", "f_CaATP = self.rho_pump * f_CaATP"),
        ("native", "science/sim.py", "self.rate_CaATP = f_CaATP"),
        ("native", "science/sim.py", "self.fluxes_mem[self.iCa] += self.rho_pump*(f_CaATP)"),
        (
            "INIT02",
            p + "betse_normal_pump_join.py",
            "scaled_na = live.rho_pump * arithmetic.raw_sodium_flux_mol_m2_s",
        ),
        ("INIT02", p + "betse_normal_pump_join.py", "proxy = arithmetic.raw_rate_proxy_mol_m2_s"),
        (
            "INIT02",
            p + "betse_normal_ecm_init_phase_pump.py",
            "flux[na] = packet.rho_pump * arithmetic.raw_sodium_flux_mol_m2_s",
        ),
        (
            "INIT02",
            p + "betse_ecm_transport.py",
            "-((diffusion * alpha) / distance) * "
            "((cb - ca * np.exp(-alpha)) / -np.expm1(-alpha)) * rho",
        ),
        ("INIT02", p + "betse_ecm_transport.py", "forcing.channel_multiplier,"),
        ("INIT02", p + "betse_normal_ecm_catalog_join_source.py", "rho=sim.rho_channel,"),
        ("INIT02", p + "betse_ecm_grn_source.py", "rho=sim.rho_channel,"),
        (
            "INIT02",
            p + "betse_ecm_grn_source.py",
            "Other ECM GRN lifecycle branches require separate state",
        ),
        ("INIT02", p + "betse_normal_ecm_calcium_join.py", "rho_pump=1,"),
        ("INIT02", p + "betse_normal_ecm_calcium_join.py", "fm[i] += 1 * masked"),
        ("INIT02", p + "betse_normal_molecule_source.py", "declared native rho_channel=1 scope"),
        (
            "INIT02",
            p + "betse_normal_transporter_join.py",
            "before the single no-ECM rho multiplication in storage",
        ),
        (
            "INIT02",
            v + "betse_normal_pump_join_fixtures.py",
            'rho_pump=[0.2 + 0.15 * j for j in range(9)] if case == "redistributed" else [1.0] * 9',
        ),
        (
            "INIT02",
            v + "betse_normal_ecm_catalog_join_fixtures.py",
            'call["material"]["channel_multiplier"] = [0.0] * m',
        ),
        (
            "MOLECULE01",
            p + "betse_normal_ecm_molecule_dispatch.py",
            'if item["network"]["configuration"].get("transporters") is not None:',
        ),
    ):
        anchor(origin, path, text)
    result = dict(
        kind="cells.normal_ecm_redistribution_source_correspondence@1",
        status="source_audit_complete_no_enabled_movement_seam"
        if all(c["passed"] for c in checks)
        else "source_audit_failed",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        auditor_sha256=sha(Path(__file__)),
        native_root=str(NATIVE),
        installed_root=str(INSTALLED),
        parents={
            key: dict(path=str(root), manifest_sha256=digest)
            for key, (root, digest) in PARENTS.items()
        },
        native_python_sha256=hashes,
        checks=checks,
        writes=writes,
        attribute_inventory=[row for i in inventories for row in i.attributes],
        source_correspondences=bindings,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
        new_scientific_passes=0,
        limits="Static source correspondence only; no supplied nonunit-rho ECM CaATP claim, "
        "no dynamic projection, membrane population inventory or physical trafficking claim.",
    )
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failures = [c["name"] for c in checks if not c["passed"]]
    print(
        json.dumps(
            dict(
                output=str(OUTPUT),
                sha256=sha(OUTPUT),
                native_files=len(hashes),
                checks=len(checks),
                failures=failures,
            )
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
