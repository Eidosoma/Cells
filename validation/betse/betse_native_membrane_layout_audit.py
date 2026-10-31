"""Static producer/consumer correspondence; never import or execute native code."""

import ast
import hashlib
import json
from pathlib import Path

CORE = "src/cells/processes/betse_native_membrane_layout.py"
INITIALIZATION_CORE = "src/cells/processes/betse_normal_ecm_initialization.py"
INITIALIZATION02 = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-initialization-prepared-20261031-02"
)
INITIALIZATION02_MANIFEST = "f423016aedf458d416b51e2b56640e64f5d36716b84d77efb953d7b2be371909"
NATIVE_PINS = {
    "betse/science/cells.py": ("be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
    "betse/science/chemistry/networks.py": (
        "e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177"
    ),
    "betse/science/organelles/microtubules.py": (
        "775cf740d4c98ddeb247b6da3ccc9115ad1255b18c75b7958b6d96a13346febf"
    ),
    "betse/science/physics/ion_current.py": (
        "a9a82ef377853c3e83466c312e508fdb33cae28237c5310a00fb50df3f56bc9f"
    ),
    "betse/science/pipe/export/plot/pipeexpplotcell.py": (
        "230602b5fbc0ca47db361c23a2de608a6b4f2c6169ab9a2a308f0c4b7fd85290"
    ),
    "betse/science/pipe/export/plot/pipeexpplotcells.py": (
        "4246e2a2a9edce94b1b59d73e747b8ba9ed10754bf78cd0c9d58963bbe9d5097"
    ),
    "betse/science/sim.py": ("02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43"),
    "betse/science/sim_toolbox.py": (
        "d94b50e8c0fdcee28b6b301c493ffa5aaf42b18e87ea4750483e164a3bdcacec"
    ),
    "betse/science/visual/plot/plotutil.py": (
        "52c058f48751d7ebf1d8472629b84aa39bf41b04294a018cd2a04eefd1a2b2eb"
    ),
    "betse/science/wrapper.py": (
        "4f9faa20a1415e3e5e6aced0c4b9664fd723238800ccc8822a18260b9e0ac982"
    ),
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def site(path, node):
    return dict(
        source=path,
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        expression=ast.unparse(node),
    )


def function(tree, name, cls=None):
    body = tree.body
    if cls:
        body = next(
            node.body for node in body if isinstance(node, ast.ClassDef) and node.name == cls
        )
    return next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)


def assigned(node, target):
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Assign)
        and any(ast.unparse(value) == target for value in child.targets)
    ]


def audit(checkout, project):
    checkout, project = Path(checkout), Path(project)
    assert sha(INITIALIZATION02 / "manifest.json") == INITIALIZATION02_MANIFEST
    parent = json.loads((INITIALIZATION02 / "manifest.json").read_text())["file_sha256"]
    assert sha(project / INITIALIZATION_CORE) == parent["source/" + INITIALIZATION_CORE]
    trees = {}
    for path, pin in NATIVE_PINS.items():
        assert sha(checkout / path) == pin, path
        trees[path] = ast.parse((checkout / path).read_bytes())
    cells_path = "betse/science/cells.py"
    cells = trees[cells_path]
    producers = {}
    expected = "np.array([cv_x, cv_y, cv_nx, cv_ny, cv_tx, cv_ty]).T"
    for name in ("cellVerts", "quickVerts", "deformWorld"):
        node = function(cells, name, "Cells")
        writer = assigned(node, "self.mem_vects_flat")
        assert len(writer) == 1 and ast.unparse(writer[0].value) == expected
        for target, expression in (
            ("pt1", "polyc[i - 1]"),
            ("pt2", "polyc[i]"),
            ("mid", "(pt1 + pt2) / 2"),
            ("tang_a", "pt2 - pt1"),
            ("tang", "tang_a / np.linalg.norm(tang_a)"),
            ("normal", "np.array([tang[1], -tang[0]])"),
        ):
            assert any(ast.unparse(a.value) == expression for a in assigned(node, target)), (
                name,
                target,
            )
        assert all(
            any(
                isinstance(child, ast.Call)
                and ast.unparse(child) == name + ".append(" + value + ")"
                for child in ast.walk(node)
            )
            for name, value in (
                ("cv_x", "mid[0]"),
                ("cv_y", "mid[1]"),
                ("cv_nx", "normal[0]"),
                ("cv_ny", "normal[1]"),
                ("cv_tx", "tang[0]"),
                ("cv_ty", "tang[1]"),
            )
        )
        producers[name] = dict(method=site(cells_path, node), writer=site(cells_path, writer[0]))
    reads, writes = [], []
    for path, tree in trees.items():
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr != "mem_vects_flat":
                continue
            if isinstance(node.ctx, ast.Store):
                writes.append(site(path, parents[node]))
            else:
                enclosing = parents[node]
                assert isinstance(enclosing, ast.Subscript)
                assert isinstance(enclosing.slice, ast.Tuple) and len(enclosing.slice.elts) == 2
                column = enclosing.slice.elts[1]
                assert isinstance(column, ast.Constant) and type(column.value) is int
                assert column.value in range(6)
                reads.append(site(path, enclosing) | dict(column=column.value))
    assert len(writes) == 3 and len(reads) == 66
    assert {row["column"] for row in reads} == set(range(6))
    native_cellverts = function(cells, "cellVerts", "Cells")
    owner_writes = {
        target: site(cells_path, assigned(native_cellverts, target)[0])
        for target in ("self.mem_to_cells", "self.cell_to_mems", "self.cell_i", "self.mem_i")
    }
    flatten_path = "betse/science/math/toolbox.py"
    flatten = function(trees[flatten_path], "flatten")
    init = ast.parse((project / INITIALIZATION_CORE).read_bytes())
    four = [
        node
        for node in ast.walk(init)
        if isinstance(node, ast.Compare) and ast.unparse(node) == "vectors.shape != (m, 4)"
    ]
    assert len(four) == 1
    core = ast.parse((project / CORE).read_bytes())
    imports = [node for node in ast.walk(core) if isinstance(node, (ast.Import, ast.ImportFrom))]
    forbidden = {"numpy", "betse", "cells", "scipy", "jax", "jaxlib", "PIL"}
    for node in imports:
        names = (
            [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
        )
        assert not {name.split(".")[0] for name in names} & forbidden
    return dict(
        kind="cells.betse_native_membrane_layout_static_correspondence@1",
        native_source_sha256=NATIVE_PINS,
        producers=producers,
        active_consumers=reads,
        writes=writes,
        native_owner_sites=owner_writes,
        flatten_owner_order=site(flatten_path, flatten),
        columns=["mid_x", "mid_y", "nx", "ny", "tx", "ty"],
        column_units=["m", "m", "1", "1", "1", "1"],
        source_semantics=dict(
            mem_i="contiguous native membrane row axis",
            owner_order="cell-major then local edge(i-1,i)",
            normal="clockwise [ty,-tx] in producer; no geometry qualification here",
            midpoints="same producer mid values as mem_mids_flat",
            consumer_normals="actual column2/3, including ordinary physics",
            plotting="actual midpoint0/1 and tangent4/5 reads exist",
        ),
        held_initialization02=dict(
            manifest_sha256=INITIALIZATION02_MANIFEST,
            core_sha256=sha(project / INITIALIZATION_CORE),
            four_column_gate=site(INITIALIZATION_CORE, four[0]),
            actual_contract="columns2:4 are normals; not normal+tangent",
            changed=False,
            integration_performed=False,
        ),
        conversion_maps=dict(midpoint_normal=[0, 1, 2, 3], normal_tangent=[2, 3, 4, 5]),
        scope=dict(
            scientific_imports=False,
            candidate_evaluation=False,
            fixture_construction=False,
            collection=False,
            numerical_jobs=False,
            physical_geometry_admitted=False,
            native_seed_init_chain_closed=False,
            PROGRESS_edited=False,
        ),
    )
