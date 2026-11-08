"""Real pinned beartype machinery on synthetic packages; all BETSE entries blocked."""

import ast
import copy
import importlib
import os
import sys
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pytest

from validation.betse import native_init_terminal_reference as initial
from validation.betse import native_init_terminal_reference_compare as init_compare
from validation.betse import native_reference_imports as loader
from validation.betse import native_reference_imports_software as software
from validation.betse import native_sim_reference as sim
from validation.betse import native_sim_reference_compare as sim_compare
from validation.betse import native_sim_reference_source as sim_source

NAMESPACE = "cells_reference_synthetic"
ROOT_BODY = b"from beartype.claw import beartype_this_package\nbeartype_this_package()\n"
MODULE_BODY = b"""entered = []
def checked(value: int) -> int:
    entered.append(value)
    local: int = value
    return local
class API:
    def checked(self, value: int) -> int:
        return checked(value)
"""


@pytest.fixture(autouse=True)
def blockade(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit immutable reference-loader blocked-software release required")
    with software.blocked(tmp_path):
        yield


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(loader.BEARTYPE_ROOT.parent))
    runtime = loader.Runtime()
    state = runtime.state
    hooks, importer_cache = list(sys.path_hooks), dict(sys.path_importer_cache)
    old_hook = state.beartype_pathhook
    whitelist = state.packages_trie_whitelist
    old_packages = dict(whitelist)
    confs = state.module_name_to_beartype_conf
    old_confs = dict(confs)
    runtime_root = tmp_path / "packages"
    package_root = runtime_root / NAMESPACE
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_bytes(ROOT_BODY)
    (package_root / "model.py").write_bytes(MODULE_BODY)

    def selected(relative, raw, mode):
        assert mode == "original"
        return raw, []

    def factory(root_body=None, module_body=None, selector=None):
        if root_body is not None:
            (package_root / "__init__.py").write_bytes(root_body)
        if module_body is not None:
            (package_root / "model.py").write_bytes(module_body)
        inventory = {}
        for path in package_root.rglob("*.py"):
            raw = path.read_bytes()
            inventory[str(path.relative_to(runtime_root))] = dict(
                sha256=loader.hashlib.sha256(raw).hexdigest(), bytes=len(raw)
            )
        return loader.Package(
            runtime_root,
            inventory,
            "original",
            selector or selected,
            namespace=NAMESPACE,
        )

    yield SimpleNamespace(factory=factory, root=runtime_root, package_root=package_root)
    # This only retires the synthetic test namespace and restores original hook
    # objects. No real model registry/state is ever present or reset here.
    monkeypatch.undo()
    for name in tuple(sys.modules):
        if name == NAMESPACE or name.startswith(NAMESPACE + "."):
            del sys.modules[name]
    whitelist.clear()
    whitelist.update(old_packages)
    confs.clear()
    confs.update(old_confs)
    state.beartype_pathhook = old_hook
    sys.path_hooks[:] = hooks
    sys.path_importer_cache.clear()
    sys.path_importer_cache.update(importer_cache)


def _import(fixture, **kwargs):
    package = fixture.factory(**kwargs)
    with package:
        module = importlib.import_module(NAMESPACE + ".model")
    package.verify()
    return package, module


@pytest.mark.parametrize("mode", initial.MODES)
@pytest.mark.parametrize(
    "relative", ("betse/science/sim.py", "betse/science/cells.py", "betse/science/parameters.py")
)
def test_reference_import_selected_bytes_preserve_exact_AST_and_lines(mode, relative):
    raw = (initial.NATIVE_ROOT / relative).read_bytes()
    selected, changes = initial.selected_source(relative, raw, mode)
    tree, expected = initial.selected_tree(relative, raw, mode)
    assert changes == expected
    assert ast.dump(ast.parse(selected)) == ast.dump(tree)
    assert len(selected) == len(raw) and selected.count(b"\n") == raw.count(b"\n")
    if not changes:
        assert selected == raw
    else:
        assert selected != raw


def test_reference_import_real_registration_transform_and_typed_wrapper(synthetic):
    package, module = _import(synthetic)
    assert loader.owner_of(module) is package
    actual = module.__loader__
    assert actual._original_base is package.runtime.loader_type
    assert type(actual._original_native) is package.runtime.loader_type
    assert actual._module_conf is package._registration[0]
    assert actual._original_base.source_to_code is package.runtime.loader_type.source_to_code
    assert package.loaded[NAMESPACE]["native_beartype"] is False
    assert package.loaded[module.__name__]["native_beartype"] is True
    fn = package.export(module.__name__, "checked")
    body = fn.__wrapped__
    assert package.code_for(module.__name__, "checked") is body.__code__
    # Annotated local checks are genuinely inserted in the native AST compiler.
    raw_unit = compile(MODULE_BODY, module.__file__, "exec", dont_inherit=True)
    assert body.__code__ != loader._codes(raw_unit)["checked"][0]
    assert module.checked(7) == 7 and module.entered == [7]
    with pytest.raises(Exception) as error:
        module.checked("bad")
    assert type(error.value).__module__.startswith("beartype.")
    assert module.entered == [7]
    package.export(module.__name__, "API.checked")
    assert module.API.__sizeof__.__wrapped__ is object.__sizeof__
    assert package.loaded[module.__name__]["export_code_witnesses"]["API.__sizeof__"][-1] == dict(
        kind="builtin_terminal",
        module="builtins",
        qualified="object.__sizeof__",
        descriptor_type="builtins.method_descriptor",
    )
    package.verify()


def test_reference_import_rejects_missing_real_registration_before_child_body(synthetic):
    package = synthetic.factory(root_body=b"root_body = True\n")
    with pytest.raises(loader.ImportRejected, match="registration"):
        with package:
            importlib.import_module(NAMESPACE + ".model")
    assert NAMESPACE + ".model" not in sys.modules
    assert NAMESPACE + ".model" not in package._loaders


def test_reference_import_disables_bytecode_reads_and_preserves_real_compiler(synthetic):
    cache = synthetic.package_root / "__pycache__"
    cache.mkdir()
    (cache / "model.cpython-313.pyc").write_bytes(b"untrusted cached module")
    package, module = _import(synthetic)
    actual = module.__loader__
    with pytest.raises(OSError, match="cache"):
        actual.get_data(str(cache / "model.cpython-313.pyc"))
    with pytest.raises(loader.ImportRejected, match="writes"):
        actual.set_data(str(cache / "anything.pyc"), b"no")
    assert package.loaded[module.__name__]["bytecode_cache_used"] is False
    assert list(cache.iterdir()) == [cache / "model.cpython-313.pyc"]


@pytest.mark.parametrize(
    "defect",
    (
        "source",
        "spec",
        "loader",
        "delegate",
        "selector_code",
        "wrapper_code",
        "body_code",
        "holder",
        "export",
        "kwdefault",
        "compiler_code",
        "registration",
        "mode",
        "inventory",
        "loader_class",
        "native_delegate_path",
        "namespace_path",
        "compiler_global",
        "AST_flag",
        "builtin_terminal",
    ),
)
def test_reference_import_live_authority_retargets_refuse(synthetic, monkeypatch, defect):
    package, module = _import(synthetic)
    before = list(module.entered)
    actual = module.__loader__
    function = module.checked
    if defect == "source":
        Path(module.__file__).write_bytes(MODULE_BODY + b"\nchanged = True\n")
    elif defect == "spec":
        monkeypatch.setattr(module.__spec__, "loader", object())
    elif defect == "loader":
        monkeypatch.setattr(module, "__loader__", object())
    elif defect == "delegate":
        actual._original_native = type(actual._original_native)(module.__name__, module.__file__)
    elif defect == "selector_code":
        monkeypatch.setattr(package.select, "__code__", (lambda *a: (MODULE_BODY, [])).__code__)
    elif defect in ("wrapper_code", "body_code"):
        target = function if defect == "wrapper_code" else function.__wrapped__
        monkeypatch.setattr(target, "__code__", target.__code__.replace(co_firstlineno=999))
    elif defect == "holder":
        monkeypatch.setattr(module, "API", type("API", (), {"checked": module.API.checked}))
    elif defect == "export":
        monkeypatch.setattr(
            module, "checked", FunctionType(function.__code__, function.__globals__)
        )
    elif defect == "kwdefault":
        value = dict(function.__kwdefaults__ or {})
        value["hidden_delegate"] = lambda: None
        monkeypatch.setattr(function, "__kwdefaults__", value)
    elif defect == "compiler_code":
        target = package.runtime.loader_type.source_to_code
        monkeypatch.setattr(target, "__code__", target.__code__.replace(co_firstlineno=999))
    elif defect == "registration":
        monkeypatch.setattr(package.runtime.state, "beartype_pathhook", object())
    elif defect == "mode":
        package.mode = "disabled"
    elif defect == "inventory":
        package.inventory[next(iter(package.inventory))]["sha256"] = "0" * 64
    elif defect == "loader_class":
        monkeypatch.setattr(type(actual), "get_data", lambda *a: MODULE_BODY)
    elif defect == "native_delegate_path":
        actual._original_native.path += ".changed"
    elif defect == "namespace_path":
        namespace = sys.modules["beartype._data.claw"]
        monkeypatch.setattr(namespace, "__path__", ["/tmp/unissued-namespace"])
    elif defect == "compiler_global":
        monkeypatch.setattr(
            package.runtime.loader_module, "compile", lambda *a, **k: None, raising=False
        )
    elif defect == "AST_flag":
        monkeypatch.setattr(package.runtime.loader_module, "PyCF_ONLY_AST", 0)
    else:
        monkeypatch.setattr(module.API.__sizeof__, "__wrapped__", str.__sizeof__)
    with pytest.raises(loader.ImportRejected):
        package.verify()
        qualified = {"holder": "API.checked", "builtin_terminal": "API.__sizeof__"}.get(
            defect, "checked"
        )
        package.export(module.__name__, qualified)
    assert module.entered == before


@pytest.mark.parametrize("method", ("get_data", "get_code", "source_to_code", "exec_module"))
def test_reference_import_raw_post_execution_entries_refuse(synthetic, method):
    package, module = _import(synthetic)
    actual = module.__loader__
    args = {
        "get_data": (module.__file__,),
        "get_code": (module.__name__,),
        "source_to_code": (MODULE_BODY, module.__file__),
        "exec_module": (module,),
    }
    with pytest.raises(loader.ImportRejected):
        getattr(actual, method)(*args[method])
    assert module.entered == []
    package.verify()


def test_reference_import_declaration_global_delegate_retarget_refuses(synthetic, monkeypatch):
    def target(raw):
        return raw

    namespace = dict(target=target)
    code = compile(
        "def selected(relative, raw, mode):\n    return target(raw), []\n",
        "<synthetic-selector>",
        "exec",
    )
    selected = FunctionType(loader._codes(code)["selected"][0], namespace)
    package, module = _import(synthetic, selector=selected)
    monkeypatch.setitem(namespace, "target", lambda raw: raw)
    with pytest.raises(loader.ImportRejected, match="selection authority"):
        package.verify()
    assert module.entered == []


def _SIM_unit():
    return ast.parse(
        "def _retained_init_sim_reference(\n"
        "    self: int, sim: int, cells: int, p_old: int\n"
        ") -> int:\n"
        "    entered.append(sim)\n"
        "    return sim + cells + p_old\n"
    )


@pytest.mark.parametrize("defect", (None, "code", "wrapper", "export", "duplicate"))
def test_reference_import_selected_SIM_uses_same_native_compiler(synthetic, monkeypatch, defect):
    package, module = _import(synthetic)
    old = dict(vars(module))
    function = package._bind_SIM_caller(module, _SIM_unit())
    assert all(vars(module)[key] is value for key, value in old.items())
    assert function.__wrapped__.__globals__ is vars(module)
    assert package.program_code(module.__name__, loader.SIM_ENTRY) is function.__wrapped__.__code__
    if defect == "code":
        target = function.__wrapped__
        monkeypatch.setattr(target, "__code__", target.__code__.replace(co_firstlineno=999))
    elif defect == "wrapper":
        monkeypatch.setattr(function, "__code__", function.__code__.replace(co_firstlineno=999))
    elif defect == "export":
        monkeypatch.setattr(module, loader.SIM_ENTRY, lambda *a: 0)
    elif defect == "duplicate":
        with pytest.raises(loader.ImportRejected):
            package._bind_SIM_caller(module, _SIM_unit())
        assert module.entered == []
        return
    if defect is not None:
        with pytest.raises(loader.ImportRejected):
            package.program_export(module.__name__, loader.SIM_ENTRY)
        assert module.entered == []
    else:
        assert function(0, 1, 2, 3) == 6
        with pytest.raises(Exception) as error:
            function(0, "bad", 2, 3)
        assert type(error.value).__module__.startswith("beartype.")
        assert module.entered == [1]
        package.verify()
        record = package.record()
        assert len(record["programs"]) == 1
        assert loader.validate_record(
            record,
            package.loaded,
            package.inventory,
            package.root,
            namespace=NAMESPACE,
            mode="original",
            selections={},
        )


def test_reference_import_source_failure_keeps_primary_cause_and_partial_module(synthetic):
    raw = b"""cause = ValueError("cause")
primary = RuntimeError("source")
try:
    raise cause
except ValueError:
    raise primary from cause
"""
    package = synthetic.factory(module_body=raw)
    with pytest.raises(RuntimeError) as error:
        with package:
            importlib.import_module(NAMESPACE + ".model")
    actual = package._loaders[NAMESPACE + ".model"]
    retained = actual._original_module
    assert error.value is retained.primary
    assert error.value.__cause__ is retained.cause
    assert actual._original_error is retained.primary
    assert actual._original_code is not None and actual._original_stage == "failed"
    assert package.loaded[retained.__name__]["stage"] == "failed"
    assert retained.__name__ not in sys.modules
    with pytest.raises(loader.ImportRejected):
        loader.owner_of(retained)


@pytest.mark.parametrize("native_failure", (False, True))
def test_reference_import_capture_and_primary_are_separate(synthetic, monkeypatch, native_failure):
    raw = (
        b'cause = ValueError("cause")\n'
        b'primary = RuntimeError("primary")\nraise primary from cause\n'
        if native_failure
        else b"source_completed = True\n"
    )
    package = synthetic.factory(module_body=raw)
    capture = OSError("forensic capture")
    original = package._update if native_failure else package._exports

    def fail(value):
        name = value.name if native_failure else value.__name__
        if name == NAMESPACE + ".model":
            raise capture
        return original(value)

    monkeypatch.setattr(package, "_update" if native_failure else "_exports", fail)
    with pytest.raises((RuntimeError, OSError)) as error:
        with package:
            importlib.import_module(NAMESPACE + ".model")
    actual = package._loaders[NAMESPACE + ".model"]
    retained = actual._original_module
    assert actual._original_captures == [capture]
    if native_failure:
        assert error.value is actual._original_error is retained.primary
        assert error.value.__cause__ is retained.cause
        assert actual._original_source_returned is False
    else:
        assert error.value is capture and actual._original_error is None
        assert actual._original_source_returned is True and retained.source_completed is True
    with pytest.raises(loader.ImportRejected):
        loader.owner_of(retained)


class _FalseyCapture(ValueError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("falsey", (False, True))
def test_reference_import_repair_first_capture_survives_later_update(
    synthetic, monkeypatch, falsey
):
    package = synthetic.factory(module_body=b"source_completed = True\n")
    first = (_FalseyCapture if falsey else ValueError)("first capture")
    cause = RuntimeError("original cause")
    first.__cause__ = cause
    second = OSError("later update")
    exports, update = package._exports, package._update

    def failed_exports(module):
        if module.__name__ == NAMESPACE + ".model":
            raise first
        return exports(module)

    def failed_update(actual):
        if actual.name == NAMESPACE + ".model":
            raise second
        return update(actual)

    monkeypatch.setattr(package, "_exports", failed_exports)
    monkeypatch.setattr(package, "_update", failed_update)
    with pytest.raises(ValueError) as error:
        with package:
            importlib.import_module(NAMESPACE + ".model")
    actual = package._loaders[NAMESPACE + ".model"]
    assert error.value is first and error.value.__cause__ is cause
    assert actual._original_error is None and actual._original_source_returned is True
    assert actual._original_module.source_completed is True
    assert actual._original_captures == [first, second]
    assert actual._original_captures[0] is first and actual._original_captures[1] is second
    assert actual._original_stage == "capture_failed"
    with pytest.raises(loader.ImportRejected):
        loader.owner_of(actual._original_module)


@pytest.mark.parametrize("mode", initial.MODES)
def test_reference_import_repair_expected_native_selections_match_producer(mode):
    native = initial.source_inventory()
    selected = loader.expected_selections(initial.NATIVE_ROOT, native, mode)
    assert set(selected) == set(loader.SELECTED_NATIVE_FILES)
    for path, row in selected.items():
        raw = (initial.NATIVE_ROOT / path).read_bytes()
        value, descriptors = initial.selected_source(path, raw, mode)
        assert row == dict(
            selected_sha256=loader.hashlib.sha256(value).hexdigest(), selections=descriptors
        )


@pytest.mark.parametrize("mode", initial.MODES)
@pytest.mark.parametrize(
    "defect",
    (
        None,
        "mode",
        "unchanged_cells",
        "missing",
        "extra",
        "descriptor",
        "hash",
        "unchanged_module",
        "module_role",
    ),
)
def test_reference_import_repair_saved_selection_associations(mode, defect):
    from tests.unit.test_native_init_terminal_reference_compare import _import_lifecycle_fixture

    native = initial.source_inventory()
    originals = {
        "betse.science." + name: dict(
            path=str(initial.NATIVE_ROOT / ("betse/science/" + name + ".py")),
            sha256=native["betse/science/" + name + ".py"]["sha256"],
        )
        for name in ("sim", "cells", "parameters")
    }
    record = _import_lifecycle_fixture(initial.NATIVE_ROOT, native, originals, mode=mode)
    expected = loader.expected_selections(initial.NATIVE_ROOT, native, mode)
    declarations = {path: row["selections"] for path, row in expected.items()}
    rows = record["modules"]
    cells = rows["betse.science.cells"]
    if defect == "mode":
        record["mode"] = "original" if mode == "disabled" else "disabled"
    elif defect == "unchanged_cells":
        if mode == "disabled":
            cells["selected_sha256"], cells["selections"] = cells["sha256"], []
        else:
            other = loader.expected_selections(initial.NATIVE_ROOT, native, "disabled")
            cells.update(other["betse/science/cells.py"])
    elif defect == "missing":
        rows["betse.science.sim"]["selections"] = []
    elif defect == "extra":
        cells["selections"].append(dict(extra="unapproved selection"))
    elif defect == "descriptor":
        rows["betse.science.sim"]["selections"][0]["first_excluded_line"] += 1
    elif defect == "hash":
        rows["betse.science.sim"]["selected_sha256"] = "0" * 64
    elif defect == "unchanged_module":
        rows["betse.science.parameters"]["selections"] = [dict(undeclared=True)]
        rows["betse.science.parameters"]["selected_sha256"] = "0" * 64
    elif defect == "module_role":
        rows["betse.science.parameters"], rows["betse.science.cells"] = (
            cells,
            rows["betse.science.parameters"],
        )
    if defect is None:
        assert loader.validate_record(
            record, rows, native, initial.NATIVE_ROOT, mode=mode, selections=declarations
        )
    else:
        with pytest.raises(loader.ImportRejected):
            loader.validate_record(
                record, rows, native, initial.NATIVE_ROOT, mode=mode, selections=declarations
            )


@pytest.mark.parametrize("role", (None, "configuration", "source_to_code", "path_hook_factory"))
def test_reference_import_repair_compiler_roles_are_not_interchangeable(synthetic, role):
    package, _ = _import(synthetic)
    record = copy.deepcopy(package.record())
    components = record["runtime"]["compiler_components"]
    if role is not None:
        components["get_code"], components[role] = components[role], components["get_code"]
    if role is None:
        assert loader.validate_record(
            record,
            record["modules"],
            package.inventory,
            package.root,
            namespace=NAMESPACE,
            mode="original",
            selections={},
        )
    else:
        with pytest.raises(loader.ImportRejected, match="association"):
            loader.validate_record(
                record,
                record["modules"],
                package.inventory,
                package.root,
                namespace=NAMESPACE,
                mode="original",
                selections={},
            )


def test_reference_import_repair_bootstrap_declares_exact_package_root_once():
    tree = ast.parse(Path(sim.__file__).read_bytes())
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare_pair_frozen"
    )
    assignment = next(
        n
        for n in ast.walk(function)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "read_roots" for t in n.targets)
    )
    expressions = [ast.unparse(n) for n in assignment.value.args[0].args[0].elts]
    assert expressions.count("str(initial.native_imports.BEARTYPE_ROOT)") == 1
    assert expressions.count("str(initial.NATIVE_ROOT)") == 1


@pytest.mark.parametrize(
    "defect",
    (None, "policy", "compiler_tree", "raw_descendant", "code", "capture", "source", "extra"),
)
def test_reference_import_saved_reader_exact_contract_without_runtime(synthetic, defect):
    package, module = _import(synthetic)
    record = copy.deepcopy(package.record())
    producers = record["modules"]
    if defect == "policy":
        record["policy"]["bytecode_cache_reads"] = 0
    elif defect == "compiler_tree":
        next(iter(record["runtime"]["files"].values()))["bytes"] += 1
    elif defect == "raw_descendant":
        producers[module.__name__]["native_beartype"] = False
    elif defect == "code":
        producers[module.__name__]["module_code_sha256"] = None
    elif defect == "capture":
        producers[module.__name__]["capture_errors"] = ["ValueError"]
    elif defect == "source":
        producers[module.__name__]["selected_sha256"] = "0" * 64
    elif defect == "extra":
        record["extra"] = True
    if defect is None:
        assert loader.validate_record(
            record,
            producers,
            package.inventory,
            package.root,
            namespace=NAMESPACE,
            mode="original",
            selections={},
        )
    else:
        with pytest.raises(loader.ImportRejected):
            loader.validate_record(
                record,
                producers,
                package.inventory,
                package.root,
                namespace=NAMESPACE,
                mode="original",
                selections={},
            )


def test_reference_import_INIT_SIM_contracts_are_closed_and_consistent():
    assert initial.SOURCE_REVIEW_SHA256 is initial.BOOTSTRAP_REVIEW_SHA256 is None
    assert (
        sim.SOURCE_REVIEW_SHA256
        is sim.REFERENCE_REVIEW_SHA256
        is sim.EXECUTION_REVIEW_SHA256
        is None
    )
    assert initial.source_plan()["native_import_lifecycle"] == loader.specification()
    assert sim_source.source_plan()["native_import_lifecycle"] == loader.specification()
    constants, pins = init_compare._reference_source(Path(initial.__file__).read_bytes())
    assert constants["IMPORTS_SHA256"] == initial.IMPORTS_SHA256
    assert pins["SOURCE_REVIEW_SHA256"] is None
    assert sim_compare.REFERENCE_RNG_AST_SHA256 == initial.comparator_ast_sha256(
        Path(initial.__file__).read_bytes()
    )
    assert sim_compare.CODEC_SHA256 == initial.snapshot.digest(Path(init_compare.__file__))
    with pytest.raises(TypeError):
        sim_source.terminal_code("core", "original")
    with pytest.raises(initial.ReferenceRejected):
        sim_source.terminal_code("core", "original", object())


@pytest.mark.parametrize("field", ("co_filename", "co_firstlineno", "co_flags", "constant_bits"))
def test_reference_import_code_witness_preserves_exact_fields_and_bits(field):
    code = compile(
        'value = "a long constant repeated across independently compiled code"',
        "<synthetic-code-witness>",
        "exec",
        dont_inherit=True,
    )
    same = compile(
        'value = "a long constant repeated across independently compiled code"',
        "<synthetic-code-witness>",
        "exec",
        dont_inherit=True,
    )
    assert loader.code_sha256(code) == loader.code_sha256(same)
    if field == "constant_bits":
        a = loader.struct.unpack("!d", bytes.fromhex("7ff8000000000001"))[0]
        b = loader.struct.unpack("!d", bytes.fromhex("7ff8000000000002"))[0]
        assert loader._atom(a) != loader._atom(b)
        code, changed = code.replace(co_consts=(None, a)), code.replace(co_consts=(None, b))
    else:
        values = dict(co_filename="<retargeted>", co_firstlineno=99, co_flags=code.co_flags ^ 1)
        changed = code.replace(**{field: values[field]})
    assert loader.code_sha256(code) != loader.code_sha256(changed)


def test_reference_import_code_witness_refuses_unknown_constant():
    code = compile("value = None", "<synthetic-code-witness>", "exec", dont_inherit=True)
    with pytest.raises(loader.ImportRejected, match="constant type"):
        loader.code_sha256(code.replace(co_consts=(object(),)))


@pytest.mark.parametrize("group", ("init_reader", "sim_reader"))
def test_reference_import_group_keeps_explicit_CPU_and_exact_targets(group):
    target, selection = software._group(group + "::exact_selected_control")
    namespace = software._namespace(group + "::exact_selected_control")
    assert selection == "exact_selected_control"
    assert namespace["SOURCE"] == target.SOURCE and namespace["TEST"] == target.TEST
    assert namespace["POLICY"] == dict(target.POLICY, cpu=6)
    assert namespace["FILE"] == software.FILE and namespace["MODULE"] == software.MODULE
    assert namespace["OWNED"] == (software.FILE, target.SOURCE, target.TEST, software.SOURCE)


@pytest.mark.parametrize("selection", ("bad::selector", "init_reader::", "::selector"))
def test_reference_import_group_unknown_or_empty_target_refuses(selection):
    with pytest.raises(ValueError):
        software._group(selection)


def test_reference_import_group_default_preserves_original_control_route():
    assert software._group("reference_import") == (None, "reference_import")
    namespace = software._namespace()
    for name in ("SOURCE", "TEST", "FILE", "MODULE", "OWNED", "RELEASE", "POLICY"):
        assert namespace[name] == getattr(software, name)
