"""The static model table and the registries that load from it (docs/CORE_SEAMS_DESIGN.md §8.4,
§15; seam F).

Each claim with a planted error it must catch (D187):
- every module under src/cells that registers a piece is one of the table's homes, or a module
  that a home package's __init__ imports (planted: an unlisted module that registers a law, and a
  home package that does not import its registering module); and every inert law module, which
  declares its LAW and registers nothing itself (the lead's R1), is a home (planted: an unlisted
  one, beside a registering module that also binds LAW);
- the loader registers an inert home's LAW with that module as its declarer, and importing the
  module registers nothing (planted: the same module imported but not a home, which a fresh
  manifest then lacks);
- the table's models are the ones core/specs.parse_spec dispatches itself, each with the module
  its branch parses with, and any other ID is refused by its name (planted: a dispatch with one
  more model, and an ID that the table does not list);
- the registries load every home, so a fresh process lists every home's pieces and the manifest's
  bytes do not depend on what was imported first (planted: a loader that misses a home, whose
  pieces a fresh manifest then lacks);
- the cells interface set is the law template's five, each held to its type, and those the
  table's families declare (planted: a law and a family operator claiming an undeclared cells
  interface, and a family operator claiming the composite's contract);
- a family's operators are a section apart: OPERATORS keeps its keys and order, a composite
  definition naming one is refused and the composition cache is untouched (planted: a family
  operator under a composite operator's ID, and a cells one held outside BUILTIN);
- the table's runners and compositions are the code's (planted: a table row with another runner
  and one with its operators reordered);
- every law interface, the five and the families', has its one family word, and no word stands
  without its interface (registry/ids.py; planted: an interface without a word);
- the table's keys and its compositions are full IDs, and no file in the rename's scope holds an old
  spelling outside its exclusions, by the rename tool's own rule (D345; planted: a bare key, and a
  file with an old spelling).
"""

import ast
import copy
import dataclasses
import importlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import cells
from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions import specs
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models.assembly_lineages import model as lineage_model
from cells.models.assembly_lineages_v2 import model as assembly_model
from cells.operators import OPERATORS
from cells.registry import declarations, ids, model_table
from cells.registry import laws as law_registry
from cells.registry import operators as operator_registry
from cells.registry.model_table import MODELS
from tests.unit.test_pump_composite_contract import frozen_worlds

SRC = Path(cells.__file__).resolve().parent
ROOT = SRC.parents[1]
LINEAGES = "cells.model.assembly_lineages@1"
ASSEMBLIES = "cells.model.assembly_lineages@2"
HOMES = {home for m in MODELS.values() for home in (*m.law_homes, *m.operator_homes)}


# ------------------------------------------------------------------ the static scan


def _module_of(root, path):
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join([root.name, *parts])


def _registers(tree):
    """Whether a module calls `register` on a registry's BUILTIN (`BUILTIN.register(...)`, in any
    attribute chain): the one registration call of laws, kinds and operators."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
        ):
            receiver = node.func.value
            name = receiver.attr if isinstance(receiver, ast.Attribute) else None
            name = receiver.id if isinstance(receiver, ast.Name) else name
            if name == "BUILTIN":
                return True
    return False


def _imports(tree, package, leaf):
    """Whether a package's __init__ imports its module `leaf`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module == package and node.level == 0) or (
                node.level == 1 and node.module is None
            ):
                if any(alias.name == leaf for alias in node.names):
                    return True
            if node.level == 0 and node.module == f"{package}.{leaf}":
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name == f"{package}.{leaf}" for alias in node.names):
                return True
    return False


def unlisted(root, homes):
    """The modules under `root` (a package directory) that register a piece but are neither a
    home nor a module that a home package's __init__ imports."""
    out = []
    for path in sorted(root.rglob("*.py")):
        if not _registers(ast.parse(path.read_text())):
            continue
        module = _module_of(root, path)
        package, _, leaf = module.rpartition(".")
        init = root.joinpath(*package.split(".")[1:], "__init__.py")
        listed = package in homes and init.exists()
        if module in homes or (listed and _imports(ast.parse(init.read_text()), package, leaf)):
            continue
        out.append(module)
    return out


def unlisted_inert(root, homes):
    """The inert law modules under `root` (each binds a module-level LAW to a call and registers
    nothing itself) that are not homes: the loader would never register their laws. None is held:
    the Kv1 pilot's five, held until @3's parser read its channel table from the law registry (the
    lead's ruling 3, 18 November), are homes since the Kv1 trigger."""
    out = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text())
        binds = any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "LAW" for t in node.targets)
            and isinstance(node.value, ast.Call)
            for node in tree.body
        )
        module = _module_of(root, path)
        if binds and not _registers(tree) and module not in homes:
            out.append(module)
    return out


def test_every_module_that_registers_a_piece_is_a_home_of_the_table(tmp_path):
    assert unlisted(SRC, HOMES) == []
    for home in HOMES:  # Each home exists, as a module or a package.
        assert importlib.util.find_spec(home) is not None, home
    # Planted: an unlisted module that registers a law, and a home package whose __init__ does
    # not import its registering module.
    tree = tmp_path / "planted"
    (tree / "family").mkdir(parents=True)
    (tree / "__init__.py").write_text("")
    (tree / "stray.py").write_text(
        "from cells.registry import laws as law_registry\n"
        "LAW = law_registry.BUILTIN.register(object())\n"
    )
    (tree / "family" / "__init__.py").write_text("from planted.family import listed\n")
    for leaf in ("listed", "forgotten"):
        (tree / "family" / f"{leaf}.py").write_text("BUILTIN.register(object())\n")
    assert unlisted(tree, {"planted.family"}) == ["planted.family.forgotten", "planted.stray"]
    # Inert law modules: each is a home. Planted: an unlisted one; a registering module that also
    # binds LAW is the registering scan's, not this one's.
    assert unlisted_inert(SRC, HOMES) == []
    (tree / "family" / "inert.py").write_text("LAW = RouteLaw('tests.route.x@1', ('membrane',), 'x')\n")
    (tree / "family" / "both.py").write_text("LAW = BUILTIN.register(RouteLaw('tests.route.y@1'))\n")
    assert unlisted_inert(tree, {"planted.family"}) == ["planted.family.inert"]
    assert unlisted_inert(tree, {"planted.family", "planted.family.inert"}) == []


# ------------------------------------------------------------------ the table and the dispatch


def dispatched(source, namespace):
    """{model ID: the module its branch parses with} of parse_spec's own dispatch: each comparison
    of data['model'].get('id') with a literal or a name of `namespace`, and the module its branch
    imports parse from (definitions/specs.py itself for an inline branch). Any other form refuses."""  # noqa: E501
    out = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.If):
            continue
        for test in ast.walk(node.test):
            if not (
                isinstance(test, ast.Compare)
                and ast.unparse(test.left) == "data['model'].get('id')"
            ):
                continue
            (item,) = test.comparators
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                model_id = item.value
            elif isinstance(item, ast.Name) and isinstance(namespace.get(item.id), str):
                model_id = namespace[item.id]
            else:
                raise ValueError(f"An unread model-ID form: {ast.unparse(item)}")
            imports = [n.module for n in node.body if isinstance(n, ast.ImportFrom)]
            out[model_id] = imports[0] if imports else specs.__name__
    return out


def test_the_table_s_models_are_parse_spec_s_own_dispatch():
    source = inspect.getsource(specs.parse_spec)
    table = {key: model.module for key, model in MODELS.items()}
    assert dispatched(source, vars(specs)) == table  # Keyed as definitions write the IDs.
    assert all(m.type in model_table.TYPES for m in MODELS.values())
    # Planted: a dispatch with one more model, which the table does not list.
    marker = '    if not isinstance(data["model"], dict):'
    planted = source.replace(
        marker,
        '    if isinstance(data["model"], dict) and data["model"].get("id") == "planted@1":\n'
        "        from cells.planted_spec import parse\n\n"
        "        return parse(data)\n" + marker,
    )
    assert planted != source
    extra = dispatched(planted, vars(specs))
    assert extra != table and extra["planted@1"] == "cells.planted_spec"
    # An ID that the table does not list, a family's other major among them, is refused by its
    # name, before its fields are read.
    for unknown in ("planted@1", "resolved_tissue@3"):
        definition = dict(schema_version=1, model=dict(id=unknown), experiment={}, execution={})
        with pytest.raises(ConfigError, match=f"^Unknown model: '{unknown}'; available: ") as no:
            parse_spec(definition)
        assert str(no.value).endswith(", ".join(MODELS))


# ------------------------------------------------------------------ loading


def _manifest_bytes(tmp_path, name, *, first=(), extra_home=None):
    """The manifest's bytes from a fresh process that imports `first` before it writes them, with
    `extra_home` added to the law registry's homes (a planted family's)."""
    script = (
        "import importlib, sys\n"
        "from cells.registry import laws\n"
        f"extra = {extra_home!r}\n"
        "if extra:\n"
        "    laws.BUILTIN_PACKAGES = (*laws.BUILTIN_PACKAGES, extra)\n"
        f"for name in {list(first)!r}:\n"
        "    importlib.import_module(name)\n"
        "from cells.registry import declarations\n"
        "doc = declarations.manifest()\n"
        "assert declarations.format_errors(doc) == [] and declarations.coverage_errors(doc) == []\n"
        "sys.stdout.write(declarations.dumps(doc))\n"
    )
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join((str(tmp_path), str(SRC.parent), str(ROOT))),
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    (tmp_path / name).write_text(result.stdout)
    return result.stdout


def test_a_fresh_process_lists_every_home_s_pieces_whatever_was_imported_first(tmp_path):
    (tmp_path / "planted_family_home.py").write_text(
        "from cells.registry import laws\n"
        "LAW = laws.BUILTIN.register(laws.RouteLaw('tests.route.planted_home_route@1', ('membrane',),\n"
        "    'a planted family law', host='cells.kind.passive_routes@1'))\n"
    )
    home = "planted_family_home"
    fresh = _manifest_bytes(tmp_path, "fresh.json", extra_home=home)
    everything = [home, *reversed(sorted(HOMES)), "cells.models.assembly_lineages.runner"]
    reordered = _manifest_bytes(tmp_path, "reordered.json", first=everything, extra_home=home)
    assert fresh == reordered  # The same bytes, whatever was imported first.
    ids = {(e["piece"], e["id"]) for e in json.loads(fresh)["pieces"]}
    assert ("law", "tests.route.planted_home_route@1") in ids
    # Every piece the homes register is listed by a fresh process: those of this process, which
    # has loaded every home.
    law_registry.active(), operator_registry.active()
    registered = {("law", key) for key in law_registry.BUILTIN._laws}
    registered |= {("operator", declarations.qualified(o.LAW_ID)) for o in OPERATORS.values()}
    registered |= {
        ("operator", declarations.qualified(d.operator_id))
        for d in operator_registry.BUILTIN.family_operators()
    }
    assert registered <= ids
    # Planted: a loader that misses the family's home. A fresh process then lists none of its
    # pieces, so the bytes would follow whatever imported the home first.
    missed = _manifest_bytes(tmp_path, "missed.json")
    assert ("law", "tests.route.planted_home_route@1") not in {
        (e["piece"], e["id"]) for e in json.loads(missed)["pieces"]
    }
    assert missed != fresh


def test_the_loader_registers_an_inert_law_module_with_it_as_its_declarer(tmp_path):
    (tmp_path / "planted_inert_home.py").write_text(
        "from cells.modules import RouteLaw\n"
        "LAW = RouteLaw('tests.route.planted_inert_route@1', ('membrane',), 'a planted inert law',\n"
        "    host='cells.kind.passive_routes@1')\n"
    )
    home = "planted_inert_home"
    listed = json.loads(_manifest_bytes(tmp_path, "inert.json", extra_home=home))
    (entry,) = (e for e in listed["pieces"] if e["id"] == "tests.route.planted_inert_route@1")
    assert entry["piece"] == "law" and entry["module"] == home
    # Planted: imported first but not a home. Importing it registers nothing, so a fresh
    # manifest lacks it.
    imported = json.loads(_manifest_bytes(tmp_path, "imported.json", first=[home]))
    assert "tests.route.planted_inert_route@1" not in {e["id"] for e in imported["pieces"]}


# ------------------------------------------------------------------ interfaces


@dataclasses.dataclass(frozen=True)
class ExchangeLike(law_registry.Law):
    interface = "cells.exchange_law@1"  # Declared by the assembly lineages' row.


@dataclasses.dataclass(frozen=True)
class LineageOperator(operator_registry.FamilyOperator):
    interface = "cells.lineage_operator@1"
    trigger: str = "a size threshold"


def test_the_cells_interface_set_is_the_five_and_the_families_declared_ones():
    declared = set(MODELS[LINEAGES].interfaces)
    assert declared <= law_registry.FAMILY_INTERFACES
    contracts = {declarations.KIND_INTERFACE, operator_registry.COMPOSITE_INTERFACE}
    assert not law_registry.FAMILY_INTERFACES & (set(law_registry.INTERFACES) | contracts)
    registry = law_registry.LawRegistry()
    admitted = ExchangeLike("tests.exchange.planted_exchange@1", host=LINEAGES)
    assert admitted.errors() == [] and registry.register(admitted) is admitted
    section = operator_registry.OperatorRegistry()
    operator = LineageOperator("tests.operator.planted_fission@1", host=LINEAGES)
    assert operator.errors() == [] and section.register(operator) is operator

    # Planted: undeclared cells interfaces, and the composite's contract claimed by a family.
    @dataclasses.dataclass(frozen=True)
    class Undeclared(law_registry.Law):
        interface = "cells.undeclared_law@1"

    with pytest.raises(ValueError, match="nor one a family declares in the model table"):
        registry.register(Undeclared("tests.exchange.undeclared@1", host=LINEAGES))
    for interface in ("cells.undeclared_operator@1", operator_registry.COMPOSITE_INTERFACE):
        claimant = type("Claimant", (LineageOperator,), {"interface": interface})
        with pytest.raises(ValueError, match="is not a family's interface"):
            section.register(claimant("tests.operator.claimant@1", host=LINEAGES))
    with pytest.raises(ValueError, match="a cited operator gives its source as a Citation"):
        section.register(LineageOperator("tests.operator.uncited@1", host=LINEAGES, provenance="cited"))
    assert [d.operator_id for d in section.family_operators()] == ["tests.operator.planted_fission@1"]


def wordless(interfaces):
    """The law interfaces among `interfaces` with no family word: a family operator's takes the
    operators' own."""
    operators = {type(d).interface for d in operator_registry.active().family_operators()}
    return sorted(set(interfaces) - operators - set(ids.LAW_FAMILIES))


def test_every_law_interface_has_its_family_word():
    declared = {*law_registry.INTERFACES, *law_registry.FAMILY_INTERFACES}
    assert wordless(declared) == [] and set(ids.LAW_FAMILIES) <= declared
    assert {type(law).interface for law in law_registry.active()._laws.values()} <= declared
    words = [*ids.FIXED_FAMILIES, *set(ids.LAW_FAMILIES.values()), *ids.SUBLAW_FAMILIES]
    assert len(words) == len(set(words))
    # Planted: an interface without a word.
    assert wordless({*declared, "cells.undeclared_law@1"}) == ["cells.undeclared_law@1"]


# ------------------------------------------------------------------ one spelling (D345)


def partial_ids(models):
    """The table's IDs that are not a piece's of their family: its keys, and its compositions'."""
    stated = [(key, "model") for key in models]
    for model in models.values():
        inner, operators = model.composition or (None, ())
        stated += [(inner, "model")] * (inner is not None) + [(o, "operator") for o in operators]
    return [value for value, family in stated if not ids.piece(value, family=family)]


def test_the_table_s_keys_and_compositions_are_full_ids():
    assert partial_ids(MODELS) == []
    assert partial_ids({"planted_tissue@1": next(iter(MODELS.values()))}) == ["planted_tissue@1"]


def left_over(tool, renames, root):
    """Every old spelling in the rename's scope under `root` outside its exclusions, by the rename
    tool's rule."""
    out = []
    for folder in renames.scope["dirs"]:
        for file in sorted((root / folder).rglob("*")):
            path = file.relative_to(root).as_posix()
            if file.is_file() and renames.excluded(path) is None:
                out += tool.leftovers({path: (None, file.read_bytes())}, renames)
    return out


def test_no_old_spelling_is_left_in_scope(tmp_path):
    """Seconds and reason (D224): about 2 s, every file in scope read once; a branch that merges
    after the rename brings old spellings back, and no parse reads most of them."""
    location = ROOT / "scripts" / "id_moves.py"
    spec = importlib.util.spec_from_file_location("id_moves", location)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    choices = tool.load_choices(ROOT / tool.CHOICES)
    frozen = tool.frozen_list(ROOT, ROOT / tool.FROZEN, choices)
    renames = tool.load_map(ROOT / tool.MAP, frozen)
    assert left_over(tool, renames, ROOT) == []
    planted = tmp_path / "src" / "planted.py"
    planted.parent.mkdir()
    planted.write_text(f'LAW_ID = "{next(iter(ids.RENAMED))}"\n')
    assert [found[:2] for found in left_over(tool, renames, tmp_path)] == [("src/planted.py", 1)]


# ------------------------------------------------------------------ a family's operators


def test_a_family_s_operators_are_a_section_apart_from_the_composite_s():
    keys, values = tuple(OPERATORS), tuple(OPERATORS.values())
    cache = pump_composite._implementation.cache_info()
    planted = LineageOperator("tests.operator.planted_fission@1", host=LINEAGES, test="tests/unit/x.py::y")
    operator_registry.BUILTIN.register(planted)
    try:
        assert tuple(OPERATORS) == keys and tuple(OPERATORS.values()) == values
        assert planted.operator_id not in OPERATORS and planted.operator_id not in (
            operator_registry.BUILTIN
        )
        with pytest.raises(KeyError):
            operator_registry.BUILTIN.lookup(planted.operator_id)
        assert planted in operator_registry.BUILTIN.family_operators(
            "cells.lineage_operator@1", LINEAGES
        )
        # A composite definition that names it is refused at the definition.
        water = composite_spec.frozen_definition(frozen_worlds()["water"][0])
        raw = copy.deepcopy(water)
        raw["model"]["operators"] = [dict(raw["model"]["operators"][0], law=planted.operator_id)]
        with pytest.raises(ConfigError, match="names a registered law"):
            parse_spec(raw)
        # The manifest lists it with its own interface and host.
        (entry,) = (e for e in declarations.manifest()["pieces"] if e["id"] == planted.operator_id)
        assert entry["piece"] == "operator" and entry["interface"] == "cells.lineage_operator@1"
        assert entry["host"] == entry["family"] == LINEAGES and entry["models"] == [LINEAGES]
        assert entry["module"] == __name__ and entry["fields"] == {"trigger": "a size threshold"}
        assert entry["test"] == planted.test and entry["provenance"]["tag"] == "parity"
    finally:
        operator_registry.BUILTIN.unregister(planted.operator_id)
    assert planted not in operator_registry.BUILTIN.family_operators()
    assert pump_composite._implementation.cache_info() == cache  # The compositions' cache.
    # Planted: a family operator under a composite operator's ID, and a cells family operator
    # held outside BUILTIN (one object per cells ID, as for the composite's).
    twin = LineageOperator(declarations.qualified(keys[0]), host=LINEAGES)
    with pytest.raises(ValueError, match="already registered"):
        operator_registry.BUILTIN.extended(twin)
    with pytest.raises(ValueError, match="only as BUILTIN's own"):
        operator_registry.OperatorRegistry().register(
            LineageOperator("cells.operator.planted_lineage@1", host=LINEAGES)
        )
    section = operator_registry.BUILTIN.extended(planted)
    assert section.module(planted.operator_id) == __name__
    assert tuple(op.LAW_ID for op in section.operators()) == keys


# ------------------------------------------------------------------ runners and compositions


def table_errors(models, worlds):
    """Where the table's runners and compositions disagree with the code: a model's declared
    RUNNER (models/assembly_lineages/model.py's form), and the operators and inner model that
    frozen_definition gives a composition's real definition (`worlds`: frozen_worlds())."""
    out = []
    runners = {LINEAGES: lineage_model.RUNNER, ASSEMBLIES: assembly_model.RUNNER}
    for key, model in models.items():
        if model.runner != runners.get(key):
            out.append(f"{key}: runner {model.runner!r}")
    for raw, *_ in worlds.values():
        model_id = raw["model"]["id"]
        if models[model_id].type != "composition":
            continue
        rewritten = composite_spec.frozen_definition(raw)["model"]
        found = (rewritten["inner_model"], tuple(b["law"] for b in rewritten["operators"]))
        if models[model_id].composition != found:
            out.append(f"{model_id}: composition {models[model_id].composition!r}")
    compositions = {k for k, m in models.items() if m.type == "composition"}
    rewritten = {raw["model"]["id"] for raw, *_ in worlds.values()}
    out += [f"{k}: not a frozen composition" for k in sorted(compositions - rewritten)]
    return out


def test_the_table_s_runners_and_compositions_are_the_code_s():
    worlds = frozen_worlds()
    assert table_errors(MODELS, worlds) == []
    for row in MODELS.values():  # A runner's entry exists.
        if row.runner:
            module, _, function = row.runner.partition(":")
            assert callable(getattr(importlib.import_module(module), function))
    # Planted: another runner, and a composition's operators reordered.
    lineages, water = MODELS[LINEAGES], MODELS["cells.model.resolved_pump_water@2"]
    inner, operators = water.composition
    planted = dict(
        MODELS,
        **{
            LINEAGES: lineages._replace(runner="cells.models.assembly_lineages.runner:other"),
            "cells.model.resolved_pump_water@2": water._replace(composition=(inner, operators[::-1])),
        },
    )
    assert table_errors(planted, worlds) == [
        f"{LINEAGES}: runner 'cells.models.assembly_lineages.runner:other'",
        f"cells.model.resolved_pump_water@2: composition {(inner, operators[::-1])!r}",
    ]
