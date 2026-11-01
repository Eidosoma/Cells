"""Prepare independent original-BETSE ASTs through multi-cell cell_index.

This is source preparation only. It reads the pinned original files and shares
the existing independent AST/helper assembler, never Cells' adopted kernels.
It does not execute a class, parameter store, decoder, RNG, or numerical body.
A future execution driver must independently enforce non-SVG multi-cell inputs,
provide and disclose the normalized parameter/phase boundary, and retain failed
outputs. These ASTs alone do not admit that driver or a successful comparison.
"""

import ast
import copy
import hashlib
from pathlib import Path

from validation.betse import native_single_cell_prefix_native as shared

CELLS_FILE = "betse/science/cells.py"
PARAMETER_FILE = "betse/science/parameters.py"
METHODS = ("__init__", "make_world", "_make_cell_lattice", "make_voronoi", "cell_index")
CLIPPING_PINS = {
    "betse/util/math/geometry/polygon/geopolyconvex.py": (
        "7c02760027be9913dc9e1e4c76352be942a6b2628f8c3b19098b21ca6b594199"
    ),
    "betse/util/type/iterable/iterables.py": (
        "d5568a6a25f1d6c2a6dd0f3babac4eec1b860ee931531c1955dcd8f390ae5403"
    ),
    "betse/util/type/iterable/generators.py": (
        "f6acfb290e2b732e04f81c1a917c2c29915ed568ea49f81b6bfd9228cee3dd01"
    ),
    "betse/util/type/cls/classes.py": (
        "518cf58a45b621fae925595c3e3ed48dcba8c1f71df6718b10ffbe253710aab4"
    ),
    "betse/util/type/numeric/floats.py": (
        "4bc44d057523606dbdea4be47d9b42af5be748d0d4482832bf2695c3632cdb84"
    ),
}
CLIPPING_CONSTANTS = {"betse/util/type/numeric/floats.py": ("PI", "TWO_PI")}
# Keep source-module identity: the two different to_iterable functions must
# never be flattened into one name by a future execution namespace builder.
CLIPPING_FUNCTIONS = {
    "betse/util/math/geometry/geopoint.py": (
        "die_unless_point",
        "is_left_of_vector",
        "intersect_lines",
    ),
    "betse/lib/numpy/nparray.py": ("to_iterable",),
    "betse/util/math/geometry/polygon/geopolyconvex.py": ("clip_counterclockwise",),
    "betse/util/type/iterable/iterables.py": ("to_iterable",),
    "betse/util/type/iterable/generators.py": ("is_generator",),
    "betse/util/type/cls/classes.py": ("get_name_unqualified",),
}
# Original source statements, including both complete configuration branches.
# They run before caller construction in a later, separately released driver.
STORE_LINES = (
    521,
    533,
    534,
    535,
    536,
    544,
    546,
    558,
    560,
    575,
    578,
    582,
    1118,
    1119,
    1122,
    1127,
    1128,
    1129,
    1130,
    1131,
)


def _one(nodes, kind, name):
    matches = [node for node in nodes if isinstance(node, kind) and node.name == name]
    if len(matches) != 1:
        raise ValueError("Require one original source definition: " + name)
    return matches[0]


def pins_for():
    return shared.NATIVE_PINS | CLIPPING_PINS


def _tree(root, relative):
    path = root / relative
    raw = path.read_bytes()
    if path.is_symlink() or hashlib.sha256(raw).hexdigest() != pins_for()[relative]:
        raise ValueError("Changed original source: " + relative)
    return ast.parse(raw, filename=str(path))


def _site(node):
    return dict(
        first_line=node.lineno,
        last_line=node.end_lineno,
        ast_sha256=hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    )


def source_nodes(root):
    """Return fresh AST groups and exact sites without executing those ASTs."""
    root = Path(root)
    groups, _ = shared.source_nodes(root)
    caller = _one(
        [node for file, nodes in groups if file == CELLS_FILE for node in nodes],
        ast.ClassDef,
        "Cells",
    )
    caller.body = [_one(caller.body, ast.FunctionDef, name) for name in METHODS]
    world = _one(caller.body, ast.FunctionDef, "make_world")
    boundaries = [
        index
        for index, node in enumerate(world.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "self"
        and node.value.func.attr == "cell_index"
    ]
    if len(boundaries) != 1:
        raise ValueError("Require one original cell_index boundary")
    world.body = world.body[: boundaries[0] + 1]
    # The enclosing AST range describes only this retained prefix.
    world.end_lineno = world.body[-1].end_lineno
    world.end_col_offset = world.body[-1].end_col_offset

    original = _one(_tree(root, PARAMETER_FILE).body, ast.ClassDef, "Parameters")
    statements = {}
    for node in ast.walk(original):
        if isinstance(node, (ast.Assign, ast.If)) and node.lineno in STORE_LINES:
            if node.lineno in statements:
                raise ValueError("Ambiguous original parameter statement")
            statements[node.lineno] = node
    if set(statements) != set(STORE_LINES):
        raise ValueError("Incomplete original parameter statement roster")
    stores = _one(
        [node for file, nodes in groups if file == PARAMETER_FILE for node in nodes],
        ast.FunctionDef,
        "store_parameters",
    )
    stores.body = [copy.deepcopy(statements[line]) for line in STORE_LINES]
    stores.lineno, stores.end_lineno = stores.body[0].lineno, stores.body[-1].end_lineno
    stores.col_offset, stores.end_col_offset = 0, stores.body[-1].end_col_offset

    for relative, names in CLIPPING_FUNCTIONS.items():
        tree = _tree(root, relative)
        helpers = [copy.deepcopy(_one(tree.body, ast.FunctionDef, name)) for name in names]
        groups.append((relative, helpers))

    for relative, names in CLIPPING_CONSTANTS.items():
        tree = _tree(root, relative)
        constants = []
        for name in names:
            matches = [
                node
                for node in tree.body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            ]
            if len(matches) != 1:
                raise ValueError("Require one original constant: " + name)
            constants.append(copy.deepcopy(matches[0]))
        groups.append((relative, constants))

    sites = {}
    for file, nodes in groups:
        for node in nodes:
            name = getattr(node, "name", "assignment_" + str(node.lineno))
            sites[file + ":" + name] = _site(node)
            if file == CELLS_FILE and isinstance(node, ast.ClassDef):
                for method in node.body:
                    sites[file + ":" + node.name + "." + method.name] = _site(method)
    for node in stores.body:
        sites[PARAMETER_FILE + ":statement_" + str(node.lineno)] = _site(node)
    # A second byte check rejects a source change during assembly. No producer
    # or Cells state is inferred from matching numerical values.
    for relative, expected in pins_for().items():
        path = root / relative
        if path.is_symlink() or shared.digest(path) != expected:
            raise ValueError("Original source changed during preparation: " + relative)
    return groups, sites
