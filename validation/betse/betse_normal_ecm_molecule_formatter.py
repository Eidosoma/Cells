"""Pinned original formatter AST and declared source-alias binding checks.

No original source function, warm method, model or RNG executes here. Private
function construction does not alter live owners or activate a continuation.
"""

import ast
import copy
import hashlib
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_formatter as formatter
from validation import source_snapshot as snapshot

NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/chemistry/networks.py")
PIN = "e32741a04c08812342461d18c80676153a6316bbd6bb958861defb23cb321177"
OWNED = (
    "src/cells/processes/betse_normal_ecm_molecule_formatter_source.py",
    "src/cells/processes/betse_normal_ecm_molecule_formatter.py",
    "validation/betse/betse_normal_ecm_molecule_formatter.py",
    "tests/unit/test_betse_normal_ecm_molecule_formatter.py",
    "src/cells/processes/betse_normal_network_join_source.py",
    "src/cells/processes/betse_ecm_grn_source.py",
    "src/cells/processes/betse_normal_ecm_molecule_lifecycle_source.py",
)
PREVIOUS_AST = {
    formatter.network.__name__: "2d4b393dd8d5a5518d5daf6976735d02c25508b8b2a9d2550cf56548a26e1321",
    formatter.environment.__name__: (
        "2052ed647c8331c42cabc5ec17b66ad6c196a9649ecfaea2a6f85dd09e95af19"
    ),
    formatter.lifecycle.__name__: (
        "b7fb4b331af30fce432327d0787d56830c1d772f23c140231a65554a5dff7128"
    ),
}
require = formatter.require


def check_declaration_delta(module_name, tree):
    """Data-only AST check: exactly one import and one formatter alias delta."""
    tree = copy.deepcopy(tree)
    imports = [
        n
        for n in tree.body
        if isinstance(n, ast.ImportFrom)
        and n.module == "cells.processes"
        and any(a.name == "betse_normal_ecm_molecule_formatter_source" for a in n.names)
    ]
    require(
        len(imports) == 1
        and len(imports[0].names) == 1
        and imports[0].level == 0
        and imports[0].names[0].asname == "formatter_source",
        "Require the single declared formatter source import",
    )
    tree.body.remove(imports[0])
    aliases = [
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "tex_val"
    ]
    require(
        len(aliases) == 1
        and ast.dump(aliases[0].value, include_attributes=False)
        == ast.dump(
            ast.Attribute(ast.Name("formatter_source", ast.Load()), "tex_val", ast.Load()),
            include_attributes=False,
        ),
        "Require the exact declared formatter source alias",
    )
    aliases[0].value = ast.Name("str", ast.Load())
    require(
        hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
        == PREVIOUS_AST[module_name],
        "Source changed beyond formatter import/alias; method and owner AST must stay exact",
    )
    return dict(
        module=module_name,
        original_module_AST_sha256=PREVIOUS_AST[module_name],
        only_added_import_and_replaced_formatter_alias=True,
        complete_remaining_module_AST_equal=True,
    )


def _function(path):
    matches = [
        n
        for n in ast.parse(Path(path).read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "tex_val"
    ]
    require(len(matches) == 1, "Missing unique formatter function")
    result = copy.deepcopy(matches[0])
    if (
        isinstance(result.body[0], ast.Expr)
        and isinstance(result.body[0].value, ast.Constant)
        and type(result.body[0].value.value) is str
    ):
        result.body.pop(0)
    return result


def source_plan(native=NATIVE):
    """Compare every executable statement/argument, not formatted projections."""
    native = Path(native)
    require(
        not native.is_symlink() and native.is_file() and snapshot.digest(native) == PIN,
        "Changed pinned original formatter source",
    )
    original = _function(native)
    adopted = _function(formatter.source.__file__)
    original_AST = ast.dump(original, include_attributes=False)
    require(
        original_AST == ast.dump(adopted, include_attributes=False),
        "Complete original formatter executable AST differs",
    )
    loaded_names = {
        n.id for n in ast.walk(original) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    locals_ = {a.arg for a in original.args.args} | {
        n.id for n in ast.walk(original) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }
    require(
        loaded_names - locals_ == {"type", "float", "int", "math", "abs", "str", "np"},
        "Changed original formatter dependency vocabulary",
    )
    formatter.check_helper()
    declarations = [
        check_declaration_delta(module.__name__, ast.parse(Path(module.__file__).read_bytes()))
        for module in (formatter.network, formatter.environment, formatter.lifecycle)
    ]
    association = require_adopted_binding()
    candidate = formatter.prepare()
    return dict(
        original=dict(path=str(native.resolve()), sha256=PIN, line=original.lineno),
        adopted=dict(
            path=str(Path(formatter.source.__file__).resolve()),
            sha256=snapshot.digest(formatter.source.__file__),
        ),
        entire_executable_function_AST_equal=True,
        excluded="docstring/source positions only; no executable normalization",
        no_closure_defaults_or_decorators=True,
        exact_dependencies=["type", "float", "int", "math.log10", "abs", "str", "np.mean"],
        raw_failures_and_float_category_retained=True,
        private_preparation=formatter.describe(candidate),
        source_declarations=declarations,
        actual_method_association=association,
        original_function_compiled_or_called=False,
        warm_native_INIT_RNG_execution=0,
        complete_cached_text_comparison_unchanged=True,
        live_bindings_installed=True,
        scientific_acceptance=False,
    )


def require_adopted_binding():
    """Require the real declared source aliases without admitting any parent.

    This accepts no caller-supplied class/record and cannot promote a private
    copy to live INIT/owner authority. Both roles need an explicit fresh source
    binding; the old reference's str prerequisite remains frozen separately.
    """
    originals = formatter.originals()
    require(
        all(f.__globals__["tex_val"] is formatter.check_helper() for f in originals),
        "Actual warm consumers lack the declared native formatter binding",
    )
    methods = {name: f for (_, _, name), f in zip(formatter.SPECS, originals, strict=True)}
    roles = {}
    for role, cls in (
        ("molecules", formatter.lifecycle.MasterOfNetworks),
        ("grn", formatter.lifecycle.qualified.MasterOfNetworks),
    ):
        rows = []
        for name, original in methods.items():
            actual = getattr(cls, name, None)
            if actual is None and role == "grn" and name == "write_transporters":
                continue
            require(
                actual is original and actual.__globals__["tex_val"] is formatter.check_helper(),
                "Foreign actual owner/MRO formatter consumer: " + role + "." + name,
            )
            rows.append(name)
        roles[role] = dict(
            class_name=cls.__module__ + "." + cls.__qualname__, formatter_methods=rows
        )
    require(
        formatter.lifecycle.MasterOfGenes is formatter.lifecycle.qualified.MasterOfGenes
        and formatter.lifecycle.MasterOfNetworks.__bases__
        == (formatter.lifecycle.qualified.MasterOfNetworks,),
        "Actual retained owner classes may not be replaced for formatting",
    )
    return dict(formatter_bound=True, roles=roles, INIT_or_native_owner_admission=False)
