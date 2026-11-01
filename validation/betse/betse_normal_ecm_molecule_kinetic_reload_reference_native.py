"""Private original-BETSE reload compilation and closed data-graph copying.

No Cells numerical implementation is imported here. Compilation defines pinned
original methods; it does not call a constructor, formatter or warm method.
Graph utilities are plumbing, never INIT/owner admission or native persistence.
Unknown objects, callbacks, shared array views and unsupported layouts refuse.
"""

import ast
import copy
import hashlib
import math
from collections import OrderedDict
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np

from validation.betse import betse_normal_catalog_join_native_helpers as catalog

ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PINS = {
    "exceptions.py": "c78612e009270a8d054ea6c52e9e7014ce22e0131a929530e7c3ddc318765971",
    "science/chemistry/molecules.py": (
        "69e50cbca8281d7ececc12d6136846244a0fe273e43b3d1dfaf793ea19cc2926"
    ),
    "science/chemistry/gene.py": "949657c9282b9109123fabb8380ee9fc05941ecef0d085f196154fa1b6bd87d1",
    "science/chemistry/networks.py": (
        "e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177"
    ),
}
PREFIX = "<original BETSE kinetic reload: "
ROOTS = ("sim", "cells", "p", "phase", "raw", "ion_ids", "enabled", "definitions", "catalogs")
MAX_NODES, MAX_ARRAY_BYTES = 25000, 64 * 2**20
SCALAR_TYPES = frozenset(
    t for t in np.sctypeDict.values() if isinstance(t, type) and issubclass(t, np.generic)
)
WARM = {
    "MasterOfMolecules": {"reinitialize"},
    "MasterOfGenes": {"reinitialize"},
    "MasterOfNetworks": {
        "tissue_init",
        "default_zones",
        "write_growth_and_decay",
        "get_influencers",
        "bal_charge",
        "read_reactions",
        "write_reactions",
        "create_reaction_matrix",
        "write_reactions_env",
        "create_reaction_matrix_env",
        "read_transporters",
        "write_transporters",
        "read_channels",
        "read_modulators",
    },
    "Molecule": {"init_growth"},
    "Reaction": {"__init__"},
    "Transporter": {"__init__", "init_reaction"},
    "Channel": {"__init__", "init_channel"},
    "Modulator": {"__init__", "init_modulator"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _class(tree, name):
    rows = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name]
    require(len(rows) == 1, "Missing unique original class: " + name)
    return copy.deepcopy(rows[0])


class Executable(ast.NodeTransformer):
    """Remove only type-check decorators/annotations; preserve original bodies."""

    def visit_FunctionDef(self, node):
        require(
            all(ast.unparse(d) == "type_check" for d in node.decorator_list),
            "Undeclared original decorator",
        )
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                require(
                    isinstance(default, (ast.Constant, ast.UnaryOp)),
                    "Original method default would execute during compilation",
                )
                ast.literal_eval(default)
        return self.generic_visit(node)


def source_plan(root=ROOT):
    root = Path(root).resolve(strict=True)
    trees, sources = {}, {}
    for name, pin in PINS.items():
        path = root / name
        require(
            not path.is_symlink()
            and path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest() == pin,
            "Changed pinned original kinetic source: " + name,
        )
        trees[name] = ast.parse(path.read_bytes())
        sources[name] = dict(path=str(path), sha256=pin)
    classes = [
        _class(trees["science/chemistry/molecules.py"], "MasterOfMolecules"),
        _class(trees["science/chemistry/gene.py"], "MasterOfGenes"),
        *(
            _class(trees["science/chemistry/networks.py"], n)
            for n in (
                "MasterOfNetworks",
                "Molecule",
                "Reaction",
                "Transporter",
                "Channel",
                "Modulator",
            )
        ),
    ]
    exception_nodes = [
        _class(trees["exceptions.py"], name)
        for name in (
            "BetseException",
            "BetseSimException",
            "BetseSimConfException",
            "BetseSimUnstableException",
        )
    ]
    for node in classes:
        wanted = WARM[node.name]
        methods = {n.name: n for n in node.body if isinstance(n, ast.FunctionDef)}
        require(wanted <= set(methods), "Missing original warm method")
        # Verify transitive direct-self calls rather than silently dropping a
        # newly required helper. Cold/optimizer/export/timestep bodies stay out.
        for name in wanted:
            for called in ast.walk(methods[name]):
                if isinstance(called, ast.Call) and isinstance(called.func, ast.Attribute):
                    obj = called.func.value
                    if (
                        isinstance(obj, ast.Name)
                        and obj.id == "self"
                        and called.func.attr in methods
                    ):
                        require(
                            called.func.attr in wanted,
                            "Unselected original warm dependency: " + called.func.attr,
                        )
        node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    nodes = [Executable().visit(n) for n in exception_nodes + classes]
    formatter = next(
        n
        for n in trees["science/chemistry/networks.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "tex_val"
    )
    nodes.append(Executable().visit(copy.deepcopy(formatter)))
    sites = {}
    for node in nodes:
        members = node.body if isinstance(node, ast.ClassDef) else [node]
        for member in members:
            if isinstance(member, ast.FunctionDef):
                name = (node.name + "." + member.name) if member is not node else node.name
                sites[name] = dict(
                    line=member.lineno,
                    end_line=member.end_lineno,
                    executable_AST_sha256=hashlib.sha256(
                        ast.dump(member, include_attributes=False).encode()
                    ).hexdigest(),
                )
    return dict(
        sources=sources,
        sites=sites,
        compiled=False,
        source_calls=0,
        scope=(
            "complete selected original warm method bodies and tex_val; "
            "type-check wrappers/annotations excluded"
        ),
    ), nodes


def compile_original(root=ROOT):
    """Define a fresh namespace. No native class/helper body is called."""
    plan, nodes = source_plan(root)
    # This existing independent builder compiles original channel classes and
    # DynamicValue aliases. It has no Cells imports or model construction.
    namespace, dependency_sites, pins = catalog.authenticated()
    require(
        (Path(pins["checkout"]) / "betse").resolve() == Path(root).resolve(),
        "Original dependency root differs from kinetic source root",
    )
    namespace = dict(
        namespace,
        np=np,
        math=math,
        OrderedDict=OrderedDict,
        __name__="original_betse_kinetic_reload",
    )
    logs = []
    namespace["logs"] = SimpleNamespace(
        log_info=lambda *v: logs.append(("info", v)),
        log_warning=lambda *v: logs.append(("warning", v)),
    )
    # The existing headless source phase uses these literal labels. This is
    # explicitly a conditional source facade, never a native SimPhase owner.
    namespace["SimPhaseKind"].INIT = "INIT"
    namespace["SimPhaseKind"].SIM = "SIM"
    for node in nodes:
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                PREFIX + node.name + ">",
                "exec",
            ),
            namespace,
        )
    require(namespace["tex_val"] is not str, "Original formatter must not become str")
    classes = {name: obj for name, obj in namespace.items() if isinstance(obj, type)}
    return SimpleNamespace(
        namespace=namespace,
        classes=classes,
        logs=logs,
        plan=dict(
            plan,
            compiled=True,
            source_calls=0,
            dependency_sites=dependency_sites,
            dependency_pins=pins["source_sha256"],
            actual_constructor_calls=0,
        ),
    )


def _array_layout(value):
    return dict(
        dtype=value.dtype.str,
        shape=list(value.shape),
        strides=list(value.strides),
        C=bool(value.flags.c_contiguous),
        F=bool(value.flags.f_contiguous),
        writable=bool(value.flags.writeable),
    )


class GraphRejected(ValueError):
    def __init__(self, message, partial):
        super().__init__(message)
        self.partial = partial


class Graph:
    """Capture named live roots; optionally copy into closed original classes.

    `types`, `aliases` and `functions` are built by the runtime observer from
    checked live code/owners, never loaded from a supplied archive. There is no
    serialized class import, arbitrary constructor or callback/code decoder.
    """

    def __init__(self, *, types, aliases, functions, api=None):
        self.types, self.aliases, self.functions, self.api = types, aliases, functions, api
        self.nodes, self.seen, self.copies, self.arrays = [], {}, {}, []
        self.array_bytes, self.excluded = 0, []
        self.cloned_aliases, self.cloned_functions = {}, {}

    def refuse(self, message, path):
        raise GraphRejected(
            message + ": " + path,
            dict(nodes=self.nodes, path=path, complete=False, excluded_observers=self.excluded),
        )

    def capture(self, roots):
        require(
            type(roots) is dict and tuple(roots) == ROOTS,
            "Complete ordered runtime roots required; dictionaries alone are not owner authority",
        )
        try:
            root, cloned = self.visit(roots, "$roots")
        except GraphRejected:
            raise
        except Exception as error:
            raise GraphRejected(
                str(error), dict(nodes=self.nodes, complete=False, excluded_observers=self.excluded)
            ) from error
        return dict(
            kind="cells.kinetic_reference_complete_data_graph@1",
            root=root,
            nodes=self.nodes,
            excluded_observers=self.excluded,
            capture_complete=True,
        ), cloned

    def visit(self, value, path):
        if type(value) in (type(None), bool, int, float, str):
            scalar = value.hex() if type(value) is float else value
            return dict(scalar=type(value).__name__, value=scalar), value
        identity = id(value)
        if identity in self.seen:
            require(identity in self.copies, "Unsupported cyclic immutable sequence")
            return dict(ref=self.seen[identity]), self.copies[identity]
        if len(self.nodes) >= MAX_NODES:
            self.refuse("Runtime graph exceeds node bound", path)
        index = len(self.nodes)
        self.seen[identity] = index
        node = {}
        self.nodes.append(node)
        if isinstance(value, np.ndarray):
            if type(value) is not np.ndarray:
                self.refuse("Unowned runtime array category", path)
            if value.dtype.kind not in "biuf" or not (
                value.flags.c_contiguous or value.flags.f_contiguous
            ):
                self.refuse("Unowned/unsupported runtime array layout", path)
            backing = value
            while isinstance(backing, np.ndarray):
                backing = backing.base
            if value.base is not None and not (
                type(backing) is bytes and not value.flags.writeable
            ):
                self.refuse("Runtime array backing/layout authority is unavailable", path)
            for other in self.arrays:
                if np.shares_memory(value, other):
                    self.refuse(
                        "Distinct runtime array views need retained storage authority", path
                    )
            self.arrays.append(value)
            self.array_bytes += value.nbytes
            if self.array_bytes > MAX_ARRAY_BYTES:
                self.refuse("Runtime arrays exceed byte bound", path)
            cloned = value.copy(order="K")
            cloned.setflags(write=value.flags.writeable)
            if _array_layout(cloned) != _array_layout(value):
                self.refuse("Array layout cannot be copied exactly", path)
            node.update(
                kind="array", layout=_array_layout(value), data=value.tobytes(order="A").hex()
            )
        elif isinstance(value, np.generic):
            if type(value) not in SCALAR_TYPES or value.dtype.kind not in "biuf":
                self.refuse("Unowned runtime scalar category/dtype", path)
            cloned = value.copy()
            node.update(kind="numpy_scalar", dtype=value.dtype.str, data=value.tobytes().hex())
        elif type(value) in (dict, OrderedDict):
            cloned = type(value)()
            self.copies[identity] = cloned
            node.update(kind="mapping", ordered=type(value) is OrderedDict, items=[])
            for key, item in value.items():
                require(type(key) in (str, int), "Unsupported runtime mapping key")
                child, copied = self.visit(item, path + "[" + repr(key) + "]")
                node["items"].append([key, child])
                cloned[key] = copied
        elif type(value) in (list, tuple):
            cloned = []
            if type(value) is list:
                self.copies[identity] = cloned
            node.update(kind=type(value).__name__, items=[])
            for i, item in enumerate(value):
                child, copied = self.visit(item, path + "[" + str(i) + "]")
                node["items"].append(child)
                cloned.append(copied)
            if type(value) is tuple:
                cloned = tuple(cloned)
        elif identity in self.aliases:
            tag, entries = self.aliases[identity]
            require(tag == "DynamicValueDict", "Unknown dynamic alias contract")
            node.update(kind="dynamic_aliases", entries=[])
            cloned = object.__new__(self.api.classes[tag]) if self.api else SimpleNamespace()
            self.copies[identity] = cloned
            mapping, copied_entries = OrderedDict(), []
            for name, target, field, offset in entries:
                target_ref, copied_target = self.visit(target, path + ".target[" + name + "]")
                node["entries"].append([name, target_ref, field, offset])
                copied_entries.append((name, copied_target, field, offset))
                if self.api:
                    dynamic = object.__new__(self.api.classes["DynamicValue"])

                    def get(t=copied_target, f=field, i=offset):
                        v = getattr(t, f)
                        return v if i is None else v[i]

                    def put(v, t=copied_target, f=field, i=offset):
                        if i is None:
                            setattr(t, f, v)
                        else:
                            getattr(t, f)[i] = v

                    dynamic.get_value, dynamic.set_value = get, put
                    mapping[name] = dynamic
            if self.api:
                cloned._key_to_dynamic_value = mapping
            self.cloned_aliases[id(cloned)] = (tag, copied_entries)
        elif type(value) is FunctionType and identity in self.functions:
            contract = self.functions[identity]
            require(contract["kind"] == "get_ion", "Unknown scientific callback authority")
            axes_ref, axes = self.visit(contract["ion_ids"], path + ".ion_ids")

            def cloned(name):
                return axes.index(name)

            node.update(kind="get_ion", ion_ids=axes_ref)
            self.cloned_functions[id(cloned)] = dict(contract, ion_ids=axes)
        elif type(value) in self.types:
            tag = self.types[type(value)]
            if tag == "record":
                cls = SimpleNamespace
            elif self.api:
                require(tag in self.api.classes, "Unowned original class: " + tag)
                cls = self.api.classes[tag]
            else:
                cls = SimpleNamespace
            cloned = SimpleNamespace() if cls is SimpleNamespace else object.__new__(cls)
            self.copies[identity] = cloned
            node.update(kind="object", tag=tag, fields=[])
            for name, item in vars(value).items():
                spec = self.functions.get(id(item))
                if type(item) is FunctionType and spec and spec["kind"] == "observer":
                    require(
                        name.startswith("_"), "Scientific callback cannot be excluded as observer"
                    )
                    self.excluded.append(dict(path=path + "." + name, source=spec))
                    continue
                child, copied = self.visit(item, path + "." + name)
                node["fields"].append([name, child])
                setattr(cloned, name, copied)
        else:
            self.refuse(
                "Missing retained class/callback authority for " + type(value).__name__, path
            )
        self.copies[identity] = cloned
        return dict(ref=index), cloned


def _difference(left, right, path):
    if type(left) is not type(right):
        return dict(
            path=path,
            reason="category",
            original_type=type(left).__name__,
            candidate_type=type(right).__name__,
        )
    if type(left) is dict:
        if list(left) != list(right):
            return dict(
                path=path, reason="mapping keys/order", original=list(left), candidate=list(right)
            )
        for key in left:
            result = _difference(left[key], right[key], path + "[" + repr(key) + "]")
            if result:
                return result
    elif type(left) is list:
        if len(left) != len(right):
            return dict(path=path, reason="length", original=len(left), candidate=len(right))
        for i, (a, b) in enumerate(zip(left, right, strict=True)):
            result = _difference(a, b, path + "[" + str(i) + "]")
            if result:
                return result
    elif left != right:
        return dict(path=path, reason="value", original=left, candidate=right)
    return None


def compare_graphs(original, candidate):
    require(
        original["capture_complete"] is candidate["capture_complete"] is True,
        "Incomplete source graph cannot match",
    )
    # Node IDs express alias topology; arrays include exact bytes, dtype, shape,
    # strides, order and writeability. No scalar-rate projection or tolerance.
    for key in ("kind", "root", "nodes"):
        difference = _difference(original[key], candidate[key], key)
        if difference:
            raise GraphRejected(
                "Complete original/candidate graph differs: " + difference["path"],
                dict(difference=difference, complete_match=False),
            )
    return dict(
        complete_data_graph_equal=True,
        aliases_values_layout_config_equal=True,
        tolerance=None,
        native_parent_admission=False,
        independent_biological_cases=0,
    )
