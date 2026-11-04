"""Pinned original fresh molecule-network setup; compile only, never import BETSE.

The runtime adapter reuses these original methods. This module contains no
replacement arithmetic or parser, owner construction, or execution release.
"""

import ast
import hashlib
from pathlib import Path
from types import CodeType

NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0")
PINS = {
    "betse/science/chemistry/molecules.py": (
        "69e50cbca8281d7ececc12d6136846244a0fe273e43b3d1dfaf793ea19cc2926"
    ),
    "betse/science/chemistry/networks.py": (
        "e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177"
    ),
    "betse/util/type/iterable/mapping/mapcls.py": (
        "15a88829cbb5fc9fc9d60c0a8b4e7ea120f86d06ceb7e1876d55862ee060ad58"
    ),
    "betse/science/chemistry/netplot.py": (
        "205f3fe2f01da21c2f5d263e9161ae6b4f8f9632d5ca5bf3dc21587b697dce6f"
    ),
}
MOLECULE_METHODS = ("__init__", "read_mol_config")
NETWORK_METHODS = (
    "__init__",
    "read_substances",
    "tissue_init",
    "default_zones",
    "get_influencers",
    "write_growth_and_decay",
    "read_reactions",
    "write_reactions",
    "write_reactions_env",
    "create_reaction_matrix",
    "create_reaction_matrix_env",
    "read_transporters",
    "write_transporters",
    "read_channels",
    "read_modulators",
    "bal_charge",
)
RUNTIME_NETWORK_METHODS = (
    "clear_cache",
    "clear_run_loop",
    "run_loop_transporters",
    "run_loop_channels",
    "run_loop_modulators",
    "run_loop",
    "energy_charge",
    "write_data",
    "report",
)
RUNTIME_MOLECULE_METHODS = ("update_intra", "transport")
RUNTIME_SITES = (
    *(("MasterOfNetworks", name) for name in RUNTIME_NETWORK_METHODS),
    *(("Molecule", name) for name in RUNTIME_MOLECULE_METHODS),
)
SITES = {
    **{
        ("MasterOfMolecules", name): "betse/science/chemistry/molecules.py"
        for name in MOLECULE_METHODS
    },
    **{
        ("MasterOfNetworks", name): "betse/science/chemistry/networks.py"
        for name in (*NETWORK_METHODS, *RUNTIME_NETWORK_METHODS)
    },
    **{
        ("Molecule", name): "betse/science/chemistry/networks.py"
        for name in RUNTIME_MOLECULE_METHODS
    },
    ("Molecule", "__init__"): "betse/science/chemistry/networks.py",
    ("Molecule", "init_growth"): "betse/science/chemistry/networks.py",
    ("Reaction", "__init__"): "betse/science/chemistry/networks.py",
    ("Transporter", "__init__"): "betse/science/chemistry/networks.py",
    ("Transporter", "init_reaction"): "betse/science/chemistry/networks.py",
    ("DynamicValue", "__init__"): "betse/util/type/iterable/mapping/mapcls.py",
    ("DynamicValueDict", "__init__"): "betse/util/type/iterable/mapping/mapcls.py",
    ("DynamicValueDict", "__getitem__"): "betse/util/type/iterable/mapping/mapcls.py",
    ("DynamicValueDict", "__setitem__"): "betse/util/type/iterable/mapping/mapcls.py",
    ("DynamicValueDict", "__len__"): "betse/util/type/iterable/mapping/mapcls.py",
    ("DynamicValueDict", "__iter__"): "betse/util/type/iterable/mapping/mapcls.py",
    (None, "set_net_opts"): "betse/science/chemistry/netplot.py",
}


def tree(relative):
    path = NATIVE / relative
    if (
        relative not in PINS
        or path.is_symlink()
        or hashlib.sha256(path.read_bytes()).hexdigest() != PINS[relative]
    ):
        raise ValueError("Exact pinned original molecule-network source required")
    return ast.parse(path.read_bytes(), filename=str(path))


def node(role, name):
    relative = SITES[(role, name)]
    if role is None:
        return next(
            value
            for value in tree(relative).body
            if isinstance(value, ast.FunctionDef) and value.name == name
        )
    owner = next(
        value
        for value in tree(relative).body
        if isinstance(value, ast.ClassDef) and value.name == role
    )
    return next(
        value for value in owner.body if isinstance(value, ast.FunctionDef) and value.name == name
    )


def code(role, name):
    """Full ORIGINAL module/class compilation context; no eval/module execution."""
    relative = SITES[(role, name)]
    root = compile(tree(relative), str(NATIVE / relative), "exec", dont_inherit=True)
    if role is None:
        return next(
            value for value in root.co_consts if type(value) is CodeType and value.co_name == name
        )
    owner = next(
        value for value in root.co_consts if type(value) is CodeType and value.co_name == role
    )
    return next(
        value for value in owner.co_consts if type(value) is CodeType and value.co_name == name
    )


def defaults(role, name):
    """Literal declared defaults only; no factory/helper or annotation lookup."""
    method = node(role, name)
    return (
        tuple(ast.literal_eval(value) for value in method.args.defaults) or None,
        {
            key.arg: ast.literal_eval(value)
            for key, value in zip(method.args.kwonlyargs, method.args.kw_defaults, strict=True)
            if value is not None
        }
        or None,
    )


def plan():
    reader = node("MasterOfMolecules", "read_mol_config")
    calls = tuple(
        (value.lineno, ast.unparse(value.func))
        for value in sorted(
            (value for value in ast.walk(reader) if isinstance(value, ast.Call)),
            key=lambda value: (value.lineno, value.col_offset),
        )
    )
    return dict(
        pins=PINS,
        methods={
            ("module" if role is None else role) + "." + name: (
                node(role, name).lineno,
                node(role, name).end_lineno,
            )
            for role, name in SITES
        },
        original_reader_calls=calls,
        whole_module_context=True,
        constructor_order=(
            "MasterOfMolecules(p)",
            "read_mol_config(phase)",
            "MasterOfNetworks(sim,cells,substances,p)",
        ),
        source_path_join_not_filesystem_creation=True,
        native_default_mit_enabled=False,
        no_reinitialize_or_existing_owner_promotion=True,
        no_replacement_equations=True,
        native_or_numeric_or_parser_or_RNG_release=False,
    )
