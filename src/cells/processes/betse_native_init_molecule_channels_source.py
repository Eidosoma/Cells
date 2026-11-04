"""Pinned original default general-network channel code; compile, never run.

Nav1p3/Kv1p5 initialization and the active INIT KLeak path retain the original
base-class dispatch. No catalogue/component object replaces a native channel.
"""

import ast
import hashlib
from types import CodeType

from cells.processes import betse_native_init_molecule_network_source as network

NATIVE = network.NATIVE
PINS = {
    "betse/science/chemistry/networks.py": network.PINS["betse/science/chemistry/networks.py"],
    "betse/science/channels/channelsabc.py": (
        "ed3e6395ec844108be7b585fd1007a9e22e899ff13df964fc1a3b14e5bf944d4"
    ),
    "betse/science/channels/vg_na.py": (
        "6faa67bdc4bfd0ee35dc1cc0fd8dcd73a703ff58120d1b1968da94dac1fe8831"
    ),
    "betse/science/channels/vg_k.py": (
        "89412aff6163dfe4ccf61afb82418a788ff8e10fbe2ec8cda24c498316b4842f"
    ),
}
CLASSES = {
    "Channel": "betse/science/chemistry/networks.py",
    "ChannelsABC": "betse/science/channels/channelsabc.py",
    "VgNaABC": "betse/science/channels/vg_na.py",
    "Nav1p3": "betse/science/channels/vg_na.py",
    "VgKABC": "betse/science/channels/vg_k.py",
    "Kv1p5": "betse/science/channels/vg_k.py",
    "KLeak": "betse/science/channels/vg_k.py",
}
METHODS = {
    "Channel": ("__init__", "init_channel"),
    "ChannelsABC": ("update_mh",),
    "VgNaABC": ("init", "run", "_implement_state"),
    "Nav1p3": ("_init_state", "_calculate_state"),
    "VgKABC": ("init", "run", "_implement_state"),
    "Kv1p5": ("_init_state", "_calculate_state"),
    "KLeak": ("_init_state", "_calculate_state"),
}
SITES = {(role, name): CLASSES[role] for role, names in METHODS.items() for name in names}
DEFAULT_TYPES = (("Na", "Nav1p3"), ("K", "Kv1p5"), ("K", "KLeak"))


def tree(relative):
    path = NATIVE / relative
    if (
        relative not in PINS
        or path.is_symlink()
        or hashlib.sha256(path.read_bytes()).hexdigest() != PINS[relative]
    ):
        raise ValueError("Pinned original native channel source required")
    return ast.parse(path.read_bytes(), filename=str(path))


def node(role, name):
    owner = next(
        item
        for item in tree(SITES[(role, name)]).body
        if isinstance(item, ast.ClassDef) and item.name == role
    )
    return next(
        item for item in owner.body if isinstance(item, ast.FunctionDef) and item.name == name
    )


def code(role, name):
    relative = SITES[(role, name)]
    full = compile(tree(relative), str(NATIVE / relative), "exec", dont_inherit=True)
    owner = next(item for item in full.co_consts if type(item) is CodeType and item.co_name == role)
    return next(item for item in owner.co_consts if type(item) is CodeType and item.co_name == name)


def defaults(role, name):
    arguments = node(role, name).args
    return (
        tuple(ast.literal_eval(value) for value in arguments.defaults) or None,
        {
            argument.arg: ast.literal_eval(value)
            for argument, value in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
            if value is not None
        }
        or None,
    )


def plan():
    return dict(
        source=PINS,
        methods={
            role + "." + name: (node(role, name).lineno, node(role, name).end_lineno)
            for role, name in SITES
        },
        default_types=DEFAULT_TYPES,
        unchanged_native_base_dispatch=True,
        no_catalogue_owner_substitution=True,
        no_numerical_factory_native_or_reference_release=True,
    )


def effects(method, receiver):
    """Original stores/list updates at an exact receiver expression."""
    result = set()
    for item in ast.walk(method):
        if isinstance(item, (ast.Assign, ast.Delete)):
            targets = item.targets
        elif isinstance(item, (ast.AnnAssign, ast.AugAssign)):
            targets = (item.target,)
        elif isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
            targets = (item.func.value,) if item.func.attr in ("append", "extend", "clear") else ()
        else:
            continue
        for target in targets:
            for value in ast.walk(target):
                if isinstance(value, ast.Attribute) and ast.unparse(value.value) == receiver:
                    result.add(value.attr)
    return frozenset(result)
