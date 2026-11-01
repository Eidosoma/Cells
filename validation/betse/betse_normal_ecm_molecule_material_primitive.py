"""Source/refactor and held standalone material-primitive preparation.

Correspondence here is to the exact prior Cells source body, not a new native
reference execution. The closed graph output is diagnostic data, never a codec
that restores/admits an extended Execution or State.
"""

import ast
import copy
import hashlib
import sys
from pathlib import Path

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_material_primitive as primitive
from validation import source_snapshot as snapshot
from validation.betse.betse_normal_channel_join_runtime import inventory
from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import identity

OWNED = (
    "src/cells/processes/betse_ecm_transport.py",
    "src/cells/processes/betse_normal_ecm_molecule_material_primitive.py",
    "validation/betse/betse_normal_ecm_molecule_material_primitive.py",
    "tests/unit/test_betse_normal_ecm_molecule_material_primitive.py",
)
PARENT_SHA256 = "05c909a59a760c763a05e30e36dd2630ce5959262519b58fde9e19f121500541"
require = primitive.require


def _function(tree, name):
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(nodes) == 1, "Unique source function required: " + name)
    return nodes[0]


def _ast(value):
    if isinstance(value, list):
        value = ast.Module(body=value, type_ignores=[])
    return ast.dump(value, include_attributes=False)


def _header(function):
    value = copy.copy(function)
    value.body = []
    return _ast(value)


def correspondence(original, current):
    """Compare the complete extraction, guards, handlers and untouched module AST."""
    require(
        hashlib.sha256(original).hexdigest() == PARENT_SHA256, "Unpinned legacy arithmetic source"
    )
    before, after = ast.parse(original), ast.parse(current)
    state, step = _function(before, "state"), _function(before, "step")
    new_state, new_step = _function(after, "state"), _function(after, "step")
    state_values, source = _function(after, "_state_values"), _function(after, "_step_source")
    expected_values = ast.parse("def _state_values(binding, raw, *, step_index): pass").body[0]
    require(
        _header(new_state) == _header(state), "Public state constructor header/decorators changed"
    )
    require(
        _header(state_values) == _header(expected_values),
        "Private state constructor header/decorators changed",
    )
    require(_ast(state.body[:1]) == _ast(new_state.body[:1]), "Legacy state guard changed")
    require(_ast(state.body[1:]) == _ast(state_values.body), "State payload construction changed")
    require(
        _ast(new_state.body[1:])
        == _ast(ast.parse("return _state_values(binding, raw, step_index=step_index)").body),
        "Legacy state extraction dispatch changed",
    )
    require(len(step.body) == 2 and isinstance(step.body[1], ast.Try), "Original step boundary")
    old_try, new_try, source_try = step.body[1], new_step.body[1], source.body[1]
    start = next(
        i
        for i, n in enumerate(old_try.body)
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Tuple)
        and tuple(getattr(e, "id", None) for e in n.targets[0].elts) == ("gb", "k")
    )
    require(
        _ast(old_try.body[:start]) == _ast(new_try.body), "Legacy step entry/validation changed"
    )
    require(
        _ast(old_try.body[start:]) == _ast(source_try.body),
        "Extracted arithmetic/frame/diagnostic order changed",
    )
    for name, trial in (("legacy", new_try), ("private", source_try)):
        require(
            _ast(
                ast.Try(
                    body=[],
                    handlers=old_try.handlers,
                    orelse=old_try.orelse,
                    finalbody=old_try.finalbody,
                )
            )
            == _ast(
                ast.Try(
                    body=[], handlers=trial.handlers, orelse=trial.orelse, finalbody=trial.finalbody
                )
            ),
            "Original exception/partial behavior changed: " + name,
        )
    require(
        _ast(step.body[:1]) == _ast(new_step.body[:1]) == _ast(source.body[:1]),
        "Trial initialization changed",
    )
    require(
        _ast(step.args) == _ast(new_step.args) == _ast(source.args)
        and _ast(state.args) == _ast(new_state.args),
        "Legacy/shared source call signature changed",
    )
    require(
        _ast(new_step.body[2:])
        == _ast(ast.parse("return _step_source(binding, parent, forcing)").body),
        "Legacy arithmetic dispatch changed",
    )
    require(
        _ast(ast.Module(body=step.decorator_list, type_ignores=[]))
        == _ast(ast.Module(body=new_step.decorator_list, type_ignores=[]))
        == _ast(ast.Module(body=source.decorator_list, type_ignores=[])),
        "Original NumPy errstate changed",
    )
    old_rest = [
        n
        for n in before.body
        if not isinstance(n, ast.FunctionDef) or n.name not in {"state", "step"}
    ]
    new_rest = [
        n
        for n in after.body
        if not isinstance(n, ast.FunctionDef)
        or n.name not in {"state", "step", "_state_values", "_step_source"}
    ]
    require(
        _ast(old_rest) == _ast(new_rest),
        "Unrelated legacy source/constants/identity functions changed",
    )
    require(
        not any(isinstance(n, ast.Name) and n.id == "MAX_STEPS" for n in ast.walk(source)),
        "Extended arithmetic still reaches the legacy cap",
    )
    return dict(
        original_sha256=PARENT_SHA256,
        current_sha256=hashlib.sha256(current).hexdigest(),
        arithmetic_AST_sha256=hashlib.sha256(_ast(source_try.body).encode()).hexdigest(),
        legacy_state_guard_exact=True,
        public_state_header_and_decorators_exact=True,
        private_state_header_and_decorators_exact=True,
        legacy_step_guard_exact=True,
        original_handlers_frames_diagnostics_and_error_order_exact=True,
        unchanged_other_module_AST=True,
        shared_arithmetic_implementations=1,
        extended_arithmetic_has_legacy_cap=False,
        native_or_numerical_correspondence=False,
    )


def source_plan(repository, original):
    repo = Path(repository).resolve(strict=True)
    original = Path(original).resolve(strict=True)
    plan = correspondence(original.read_bytes(), (repo / OWNED[0]).read_bytes())
    return dict(
        plan,
        original=dict(path=str(original), sha256=snapshot.digest(original)),
        owned_files={name: snapshot.digest(repo / name) for name in OWNED},
        kind=primitive.KIND,
        numerical_qualification=False,
        coupled_routes_available=False,
        original_three_call_defaults_unchanged=True,
    )


def evidence(execution, error=None):
    return dict(
        kind=primitive.KIND,
        domain=primitive.domain_record(execution.domain),
        binding=None if execution.binding is None else primitive.binding_record(execution.binding),
        current=None if execution.current is None else primitive.state_record(execution.current),
        original_definition=execution.definition,
        original_initial=execution.initial,
        original_input_fingerprint=execution.input_fingerprint,
        journal=execution.journal,
        attempts=execution.attempts,
        work=dict(
            requests=execution.requests,
            material_attempts=execution.material_attempts,
            owner_verifications=execution.owner_verifications,
            source_requests=execution.source_requests,
            actual_source_entries=execution.source_entries,
            nested_Cells_Python_calls_in_source_operations=execution.nested_source_calls,
            retained_bytes=execution.retained_bytes,
        ),
        failure=None if error is None else checkpoint._exception_record(error),
        failed_trial=None if error is None else getattr(error, "trial", None),
        recovery_errors=[
            dict(stage=r["stage"], failure=checkpoint._exception_record(r["error"]))
            for r in execution.recovery_errors
        ],
        failed=execution.failed,
        standalone_only=True,
        source_input_native_derivation_attested=False,
        extended_checkpoint_or_coupled_admission=False,
        scientific_acceptance=False,
    )


def retain(directory, execution, error=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    encoder = primitive.codec.Encoder()
    tree = encoder.capture(evidence(execution, error))
    encoder.write(directory, tree)
    snapshot.write_json(
        directory / "manifest.json",
        dict(
            kind="cells.standalone_material_primitive_diagnostic@1",
            fingerprint=encoder.seal(tree),
            files={
                name: dict(
                    sha256=snapshot.digest(directory / name),
                    bytes=(directory / name).stat().st_size,
                )
                for name in ("state.json", "arrays.npz")
            },
            live_owner_admission=False,
        ),
    )
    primitive.codec._sync_directory(directory)
    return directory


def prepare(repository, directory, *, original):
    repo, directory = Path(repository).resolve(strict=True), Path(directory).resolve()
    require(Path(__file__).resolve() == repo / OWNED[2], "Prepare current Git source only")
    require(
        not directory.is_relative_to(repo) and not repo.is_relative_to(directory),
        "Separate output directory required",
    )
    directory.mkdir(parents=True, exist_ok=False)
    plan = source_plan(repo, original)
    names = dict.fromkeys(OWNED)
    names.update({"pyproject.toml": None, "tests/__init__.py": None})
    require(
        callable(inventory) and callable(identity), "Existing runtime inventory helpers required"
    )
    for name, module in tuple(sys.modules.items()):
        if name.startswith(("cells", "validation")) and getattr(module, "__file__", None):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(repo), "Foreign source regime: " + name)
            names[str(path.relative_to(repo))] = None
    producer = checkpoint.producer_identity()
    for name in producer["source_hashes"]:
        names["src/cells/" + name] = None
    frozen = snapshot.freeze(repo, directory / "source", {n: n for n in names})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            kind=primitive.KIND,
            held=True,
            automatic_launch=False,
            source_manifest_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
            original_source=plan["original"],
            producer=producer,
            actual_source_entries=0,
            independent_biological_cases=0,
            remaining=[
                "Root standalone numerical release/resources",
                "genuine declared source inputs and forcing",
                "independent native/source numerical comparison",
            ],
            coupled_routes_available=False,
        ),
    )
    return dict(
        files=len(frozen["files"]),
        source_manifest_sha256=snapshot.digest(directory / "source/SNAPSHOT.json"),
        inputs_sha256=snapshot.digest(directory / "inputs.json"),
        held=True,
    )
