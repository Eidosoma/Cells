"""Source-only preparation; software workers require a separate Root release."""

import argparse
import ast
import copy
import hashlib
import itertools
import json
import marshal
import os
import resource
import runpy
import secrets
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from types import FunctionType, SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import betse_native_phase_callbacks_software as callbacks
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_parameter_load_remainder_software.py"
TEST = "tests/unit/test_betse_native_parameter_load_remainder.py"
OWNED = ("src/cells/processes/betse_native_parameter_load_remainder.py", FILE, TEST)
SOFTWARE_RELEASE = "CELLS_NATIVE_PARAMETER_LOAD_REMAINDER_SOFTWARE_RELEASED"
WORLD_FILE = "validation/betse/betse_native_parameter_world_construction_software.py"
ENTRY_CONFIG = {
    FILE: (TEST, OWNED[0], SOFTWARE_RELEASE),
    WORLD_FILE: (
        "tests/unit/test_betse_native_parameter_world_construction.py",
        "src/cells/processes/betse_native_parameter_world_construction.py",
        "CELLS_NATIVE_PARAMETER_WORLD_CONSTRUCTION_SOFTWARE_RELEASED",
    ),
}
CM_GUARD_TEST = "tests/unit/test_betse_native_parameter_colormap_load.py"
CM_GUARD_SHA256 = "577460cd94e1204b1248db07b3a0cfe20f6b028f7b943f2f9cba797641601a2e"
# Current reviewed fixture for the package-wrapper repair. Historical cleanup
# banks retain their original constant and are never rebound to these bytes.
WRAPPER_GUARD_SHA256 = "0b274dc8084cc26119bb11d0c0c1deeedeaf13d71bc25e72b07e320c5ccd8666"
CM_GUARD_LEGACY_SHA256 = "442f17dd8f8187c43966ccf6c26715b7c5c929aa7dfd697d81de3a465d7d3460"
CM_CONTEXT_TEST = "tests/unit/test_betse_native_parameter_colormaps.py"
CM_CONTEXT_SHA256 = "04a2e766779826524d10daaf5f233feb9572067e08cf68af183d4f8e40505ea4"
AUTH_FILE = "worker-authorization.json"
RESOURCES = dict(
    cpu=0,
    threads=1,
    metadata_bytes=512 * 2**20,
    software_bytes=2**30,
    wall_seconds=480,
    host_reserve_bytes=8 * 2**30,
)


class WorkerEvidenceRejected(RuntimeError):
    def __init__(self, reason, context):
        super().__init__(reason)
        self.world_ready_worker = context


def prepare_sources(repository, directory, *, file, owned, plan):
    repo = Path(repository).resolve(strict=True)
    caller = Path(file)
    if not (repo / caller).is_file():
        raise ValueError("Actual owned runner/source checkout required")
    directory = inherited.separate(directory, repo, Path("/mnt/workspaces/Cells/betse-v1.5.0"))
    directory.mkdir(parents=True, exist_ok=False)
    files = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"](repo, list(owned))
    fixture_sha = snapshot.digest(repo / CM_GUARD_TEST)
    if fixture_sha not in (CM_GUARD_SHA256, WRAPPER_GUARD_SHA256):
        raise ValueError("Explicit reviewed blocked fixture version required")
    for name in ("pyproject.toml", "tests/__init__.py", inherited.CLOSURE_TOOL):
        files[name] = snapshot.digest(repo / name)
    manifest = snapshot.freeze(repo, directory / "source", {name: name for name in files})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            law=plan["law"],
            source_only=True,
            held=True,
            automatic_launch=False,
            repository=str(repo),
            git_revision=manifest["git_revision"],
            snapshot=inherited.ref(directory / "source/SNAPSHOT.json"),
            source_plan=inherited.ref(directory / "source-plan.json"),
            owned_files={name: manifest["files"][name]["sha256"] for name in owned},
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
            actual_source_native_parser_RNG_phase_or_science_release=False,
            software_executed=False,
            source_or_API_adoption_inferred=False,
            software_entry=dict(
                file=file,
                test=ENTRY_CONFIG[file][0],
                release=ENTRY_CONFIG[file][2],
                native_release=False,
            ),
            fixture_producer=dict(path=CM_GUARD_TEST, sha256=fixture_sha),
            resources=dict(
                cpu=0,
                threads=1,
                metadata_bytes=512 * 2**20,
                software_bytes=2**30,
                wall_seconds=480,
                host_reserve_bytes=8 * 2**30,
            ),
        ),
    )
    return dict(
        inputs=inherited.ref(directory / "inputs.json"),
        source_files=len(manifest["files"]),
        held=True,
    )


def prepare(repository, directory):
    from cells.processes import betse_native_parameter_load_remainder as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare the actual single editable checkout only")
    return prepare_sources(repo, directory, file=FILE, owned=OWNED, plan=stage.source_plan())


def _image(packet, file):
    packet = Path(packet).resolve(strict=True)
    inputs = json.loads((packet / "inputs.json").read_text())
    source = packet / "source"
    manifest = snapshot.verify(source, manifest_sha256=inputs["snapshot"]["sha256"])
    test, production, release = ENTRY_CONFIG[file]
    fixture = inputs.get("fixture_producer")
    if (
        inputs["software_entry"]
        != dict(file=file, test=test, release=release, native_release=False)
        or inputs["resources"] != RESOURCES
        or inputs.get("actual_source_native_parser_RNG_phase_or_science_release") is not False
        or type(fixture) is not dict
        or set(fixture) != {"path", "sha256"}
        or fixture["path"] != CM_GUARD_TEST
        or fixture["sha256"] not in (CM_GUARD_SHA256, WRAPPER_GUARD_SHA256)
        or manifest["files"][CM_GUARD_TEST]["sha256"] != fixture["sha256"]
        or snapshot.digest(packet / "source-plan.json") != inputs["source_plan"]["sha256"]
    ):
        raise ValueError("Exact held software image/resources/fixture required")
    for name in (file, test, production):
        if inputs["owned_files"].get(name) != manifest["files"][name]["sha256"]:
            raise ValueError("Selected software producer changed")
    return packet, inputs, source, manifest


def _authorization(output, authorization, authorization_sha256, *, file, entry_path, target=None):
    if authorization is None or type(authorization_sha256) is not str:
        raise ValueError("Direct software child entry is unreleased")
    output = Path(output).resolve(strict=True)
    raw_path = Path(authorization)
    path = raw_path.resolve(strict=True)
    if (
        path != output / AUTH_FILE
        or raw_path.is_symlink()
        or snapshot.digest(path) != authorization_sha256
    ):
        raise ValueError("Foreign/changed worker authorization")
    grant = json.loads(path.read_text())
    if (
        grant.get("kind") != "cells.world_ready_software_worker_authorization@1"
        or grant.get("native_release") is not False
        or grant.get("file") != file
        or grant.get("target") != target
        or grant.get("output") != str(output)
        or grant.get("parent_pid") != os.getppid()
        or type(grant.get("nonce")) is not str
        or len(grant["nonce"]) != 64
    ):
        raise ValueError("Unissued/stale software worker authorization")
    packet, inputs, source, manifest = _image(grant["packet"], file)
    if (
        snapshot.digest(packet / "inputs.json") != grant["inputs_sha256"]
        or inputs["snapshot"]["sha256"] != grant["snapshot_sha256"]
        or Path(entry_path).resolve(strict=True) != source / file
        or snapshot.digest(entry_path) != manifest["files"][file]["sha256"]
        or sorted(os.sched_getaffinity(0)) != [RESOURCES["cpu"]]
    ):
        raise ValueError("Actual frozen child/parent/resource binding changed")
    inherited.separate(
        output,
        packet,
        Path(manifest["repository"]).resolve(),
        Path("/mnt/workspaces/Cells/betse-v1.5.0"),
    )
    if any(
        value not in ("0", "") for name, value in os.environ.items() if name.startswith("CELLS_")
    ):
        raise ValueError("Native/application release leaked into blocked software worker")
    snapshot.write_json(
        output / "worker-authorization.claim.json",
        dict(
            nonce=grant["nonce"],
            authorization=authorization_sha256,
            pid=os.getpid(),
            parent_pid=os.getppid(),
        ),
    )
    return dict(grant=grant, source=source, manifest=manifest, inputs=inputs)


def _target(file, target):
    test = ENTRY_CONFIG[file][0]
    if target is None:
        return test
    if (
        file != FILE
        or type(target) is not str
        or not target.startswith("test_")
        or any(not (c.isascii() and (c.isalnum() or c == "_")) for c in target)
    ):
        raise ValueError("Choose an exact owned software test function")
    tree = ast.parse((Path(__file__).resolve().parents[2] / test).read_bytes())
    if not any(isinstance(n, ast.FunctionDef) and n.name == target for n in tree.body):
        raise ValueError("Unknown exact owned software test function")
    return test + "::" + target


def _pytest_driver(test):
    """Reuse exact upstream pytest body, replacing only its unsafe evidence finally."""
    if snapshot.digest(inherited.__file__) != callbacks.INHERITED_SHA256:
        raise ValueError("Exact inherited software driver required")
    tree = ast.parse(Path(inherited.__file__).read_bytes())
    node = copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "child")
    )
    body = next(n for n in node.body if isinstance(n, ast.Try))
    if body.handlers or body.orelse or len(body.finalbody) != 1:
        raise ValueError("Inherited child evidence adaptation needs explicit review")
    call = body.finalbody[0].value
    if not (
        isinstance(call, ast.Call)
        and ast.unparse(call.func) == "snapshot.write_json"
        and ast.unparse(call.args[0]) == "directory / 'runtime.json'"
    ):
        raise ValueError("Inherited child finally changed")
    node.body = [n for n in node.body if not isinstance(n, (ast.Try, ast.ImportFrom))]
    # Keep the literal original status assignment, pytest.main arguments and return.
    node.body[-1:-1] = body.body
    code = compile(
        ast.Module(body=[node], type_ignores=[]), inherited.__file__, "exec", dont_inherit=True
    )
    function_code = next(
        c for c in code.co_consts if type(c) is type(code) and c.co_name == "child"
    )
    namespace = dict(inherited.child.__globals__, TEST=test)
    cached = inherited.child.__builtins__
    resolved = namespace["__builtins__"]
    if (resolved if type(resolved) is dict else vars(resolved)) is not cached:
        raise ValueError("Original inherited driver cached builtins changed")
    function = FunctionType(function_code, namespace, "child")
    if function.__builtins__ is not cached:
        raise ValueError("Private pytest driver cached builtins changed")
    return function


def _producers(image, *, selected=None):
    source, manifest = image["source"], image["manifest"]
    for module, expected in (
        (snapshot, "validation/source_snapshot.py"),
        (inherited, "validation/betse/betse_native_simulator_construction_software.py"),
        (callbacks, "validation/betse/betse_native_phase_callbacks_software.py"),
        (sys.modules[__name__], FILE),
    ):
        if Path(vars(module)["__file__"]).resolve() != source / expected:
            raise ValueError("Actual loaded worker framework is outside its frozen image")
    rows, bindings = {}, []
    for module_name, module in sorted(tuple(sys.modules.items())):
        namespace = vars(module) if type(module) is type(sys) else {}
        filename = namespace.get("__file__")
        if type(filename) is not str:
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(source):
            continue
        name = str(path.relative_to(source))
        if selected is not None and module_name not in selected:
            continue
        if (
            name not in manifest["files"]
            or snapshot.digest(path) != manifest["files"][name]["sha256"]
        ):
            raise ValueError("Loaded worker source producer mismatch: " + module_name)
        functions = {}
        for key, value in namespace.items():
            if type(value) is FunctionType and value.__globals__ is namespace:
                resolved = namespace["__builtins__"]
                if (
                    resolved if type(resolved) is dict else vars(resolved)
                ) is not value.__builtins__:
                    raise ValueError("Loaded producer cached builtins mismatch")
                functions[key] = dict(
                    code_sha256=hashlib.sha256(marshal.dumps(value.__code__)).hexdigest(),
                    function_id=id(value),
                    globals_id=id(namespace),
                    builtins_id=id(value.__builtins__),
                )
                bindings.extend(
                    (
                        value,
                        value.__code__,
                        namespace,
                        value.__builtins__,
                        value.__defaults__,
                        value.__kwdefaults__,
                        value.__closure__,
                    )
                )
        rows[module_name] = dict(
            path=str(path), sha256=manifest["files"][name]["sha256"], functions=functions
        )
    return rows, tuple(bindings)


def _identity():
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import identity

    return identity()


def _inventory():
    from validation.betse.betse_normal_channel_join_runtime import inventory

    return inventory()


def _exception(error):
    if error is None:
        return None
    # Read retained exception metadata without dispatching its __getattribute__
    # or a metaclass. String conversion is the final arbitrary callback; the
    # outer guard checks hooks before any later formatter/attachment/writer.
    value = dict(
        type=type.__getattribute__(type(error), "__qualname__"),
        identity=id(error),
        cause_identity=id(BaseException.__cause__.__get__(error, BaseException)),
    )
    value["message"] = str(error)
    return value


def _child(output, authorization, authorization_sha256, *, file, entry_path, target=None):
    selected = _target(file, target)
    image = _authorization(
        output, authorization, authorization_sha256, file=file, entry_path=entry_path, target=target
    )
    output = Path(output)
    before, bindings = None, None
    original_profile, original_trace = object(), object()
    originals_known = False
    hook_api = dict(
        get_profile=sys.getprofile,
        get_trace=sys.gettrace,
        set_profile=sys.setprofile,
        set_trace=sys.settrace,
    )
    context = SimpleNamespace(
        primary=None,
        pytest_status=None,
        errors=[],
        values={},
        writes={},
        image=image,
        metadata_stopped=False,
        callback_calls=[],
        proof_samples=[],
        raw_results={},
    )
    refusal = WorkerEvidenceRejected("Worker evidence incomplete; no success receipt", context)
    try:
        original_profile, original_trace = hook_api["get_profile"](), hook_api["get_trace"]()
        originals_known = True
    except BaseException as error:
        context.primary = error
        context.metadata_stopped = True

    def checkpoint(label):
        if context.metadata_stopped:
            return False
        for name, expected in (("profile", original_profile), ("trace", original_trace)):
            try:
                actual = hook_api["get_" + name]()
                context.proof_samples.append((label, name, actual, expected))
                if actual is not expected:
                    raise ValueError("Required worker hook changed")
            except BaseException as error:
                context.errors.append((label + "_" + name, error))
                context.metadata_stopped = True
        return not context.metadata_stopped

    def perform(name, function, *args, primary=False, **kwargs):
        if not checkpoint("before_" + name):
            return False, None
        context.callback_calls.append(name)
        try:
            value = function(*args, **kwargs)
            context.raw_results[name] = value
            return True, value
        except BaseException as error:
            if primary and context.primary is None:
                context.primary = error
            else:
                context.errors.append((name, error))
            return False, None
        finally:
            checkpoint("after_" + name)

    try:
        ok, initial = perform("initial_producers", _producers, image, primary=True)
        if ok:
            before, bindings = initial
            ok, driver = perform("pytest_driver", _pytest_driver, selected, primary=True)
            if ok:
                _, context.pytest_status = perform("pytest", driver, output, primary=True)
        if context.primary is not None and not context.metadata_stopped:
            perform(
                "primary_context_attachment",
                setattr,
                context.primary,
                "world_ready_worker",
                context,
            )
        for name, function in (("identity", _identity), ("inventory", _inventory)):
            if context.metadata_stopped:
                break
            ok, value = perform(name, function)
            if ok:
                context.values[name] = value
                written, _ = perform(
                    name + "_write", snapshot.write_json, output / (name + ".json"), value
                )
                context.writes[name] = written
        if before is not None and not context.metadata_stopped:
            ok, compared = perform("producers", _producers, image, selected=before)
            if ok:
                after, current = compared
                if (
                    after != before
                    or len(current) != len(bindings)
                    or any(x is not y for x, y in zip(current, bindings, strict=True))
                ):
                    context.errors.append(
                        ("producers", ValueError("Actual producer identity changed"))
                    )
                else:
                    ok, all_loaded = perform("producer_inventory", _producers, image)
                    if ok:
                        context.values["producers"] = dict(before=before, after=all_loaded[0])
                        written, _ = perform(
                            "producers_write",
                            snapshot.write_json,
                            output / "producers.json",
                            context.values["producers"],
                        )
                        context.writes["producers"] = written
        if checkpoint("before_hooks_evidence"):
            value = dict(
                profile=id(original_profile),
                trace=id(original_trace),
                expected_profile=id(original_profile),
                expected_trace=id(original_trace),
                restored=True,
                sample_scope="before_later_worker_writers_not_final",
                final_restoration_requires_terminal=True,
            )
            context.values["hook_identities"] = context.values["hooks"] = value
            written, _ = perform("hooks_write", snapshot.write_json, output / "hooks.json", value)
            context.writes["hooks"] = written
        for filename in ("runtime.json", "worker-evidence.json"):
            if context.metadata_stopped:
                break
            ok, primary_document = perform("format_primary", _exception, context.primary)
            errors_document = []
            for name, error in tuple(context.errors):
                if context.metadata_stopped:
                    break
                formatted, document = perform("format_secondary", _exception, error)
                if formatted:
                    errors_document.append((name, document))
            if ok and not context.metadata_stopped:
                payload = dict(
                    child=context.values.get("identity"),
                    loaded=context.values.get("inventory"),
                    pytest_status=context.pytest_status,
                    primary=primary_document,
                    errors=errors_document,
                    available=context.values,
                    writes=context.writes,
                    evidence_operations_so_far_complete=context.primary is None
                    and not context.errors,
                    pytest_returned_zero=context.pytest_status == 0,
                    final_worker_success_requires_terminal=True,
                    final_hook_sample_after_all_writers_pending=True,
                    authorization_sha256=authorization_sha256,
                    native_or_scientific_admission=False,
                )
                written, _ = perform(
                    filename + "_write", snapshot.write_json, output / filename, payload
                )
                context.writes[filename] = written
    except BaseException as error:
        # Includes checkpoint/perform entry rejection before their protection.
        context.errors.append(("metadata_entry", error))
        context.metadata_stopped = True

    # Recovery is independent and cannot rearm any callback above. Preserve all
    # raw outcomes and primary/cause even if a hook helper/setter refuses entry.
    cleanup_errors, samples = [], []
    current = dict(profile=object(), trace=object())
    for attempt in range(4):
        if attempt and originals_known:
            for name, expected in (("profile", original_profile), ("trace", original_trace)):
                try:
                    hook_api["set_" + name](expected)
                except BaseException as error:
                    cleanup_errors += [("final_" + name + "_restore_" + str(attempt), error)]
        for name in ("profile", "trace"):
            try:
                current[name] = hook_api["get_" + name]()
                samples += [(attempt, name, current[name])]
            except BaseException as error:
                current[name] = object()
                cleanup_errors += [("final_" + name + "_sample_" + str(attempt), error)]
        if (
            originals_known
            and current["profile"] is original_profile
            and current["trace"] is original_trace
        ):
            break
        cleanup_errors += [
            (
                "final_hook_identity_" + str(attempt),
                ValueError("Worker hooks changed after callbacks"),
            )
        ]
        if not originals_known:
            break
    restored = (
        originals_known
        and current["profile"] is original_profile
        and current["trace"] is original_trace
    )
    context.hook_recovery = dict(
        originals_known=originals_known,
        samples=tuple(samples),
        errors=tuple(cleanup_errors),
        final_profile=current["profile"],
        final_trace=current["trace"],
        expected_profile=original_profile,
        expected_trace=original_trace,
        identities_match=restored,
        clean=restored and not cleanup_errors and not context.metadata_stopped,
    )
    context.values["final_hook_identities"] = dict(
        profile=id(current["profile"]),
        trace=id(current["trace"]),
        expected_profile=id(original_profile),
        expected_trace=id(original_trace),
        restored=restored,
        clean=context.hook_recovery["clean"],
        sample_scope="after_all_worker_writers_and_primary_attachment",
    )
    context.errors += cleanup_errors
    if cleanup_errors:
        context.metadata_stopped = True
    if context.primary is not None:
        raise context.primary
    if context.errors or context.metadata_stopped:
        raise refusal
    return context.pytest_status


def child(output, *, authorization=None, authorization_sha256=None, target=None):
    return _child(
        output, authorization, authorization_sha256, file=FILE, entry_path=__file__, target=target
    )


def software(packet, output, *, target=None):
    return _software(packet, output, file=FILE, target=target)


def _software(packet, output, *, file, target=None):
    if os.environ.get(ENTRY_CONFIG[file][2]) != "1":
        raise ValueError("Software execution remains held for Root; source preparation only")
    _target(file, target)
    packet, inputs, source, manifest = _image(packet, file)
    parent_root = Path(__file__).resolve().parents[2]
    for name in {FILE, file}:
        if snapshot.digest(parent_root / name) != manifest["files"][name]["sha256"]:
            raise ValueError("Actual parent software producer differs from frozen worker")
    directory = inherited.separate(
        output,
        packet,
        Path(manifest["repository"]).resolve(),
        Path("/mnt/workspaces/Cells/betse-v1.5.0"),
    )

    def bounded(command, **kwargs):
        expected = [
            sys.executable,
            "-B",
            "-m",
            file[:-3].replace("/", "."),
            "--child",
            str(directory),
        ]
        if command != expected or Path(kwargs["cwd"]).resolve() != source:
            raise ValueError("Unexpected inherited child command/source")
        grant = dict(
            kind="cells.world_ready_software_worker_authorization@1",
            file=file,
            packet=str(packet),
            output=str(directory),
            inputs_sha256=snapshot.digest(packet / "inputs.json"),
            snapshot_sha256=inputs["snapshot"]["sha256"],
            parent_pid=os.getpid(),
            nonce=secrets.token_hex(32),
            native_release=False,
            target=target,
        )
        path = directory / AUTH_FILE
        snapshot.write_json(path, grant)
        path.chmod(0o600)
        # Authorization travels in explicit arguments; inherited env deliberately
        # strips all CELLS_* releases and that behavior remains unchanged.
        return inherited.guard.run_bounded(
            [
                *command,
                "--authorization",
                str(path),
                "--authorization-sha256",
                snapshot.digest(path),
                *(["--target", target] if target is not None else []),
            ],
            **kwargs,
        )

    return callbacks.delegate(
        inherited.software, FILE=file, guard=SimpleNamespace(run_bounded=bounded)
    )(packet, directory)


CM_FILE = "validation/betse/betse_native_parameter_colormap_load_software.py"
CLEANUP_GROUPS = (
    ("CM", "test_matplotlib_guard_unchanged_valid_cleanup_requires_evidence_return"),
    ("CM", "test_matplotlib_guard_cleanup_keeps_primary_and_all_independent_attempts"),
    ("CM", "test_guard_failed_recovery_never_enters_attachment_formatting_or_writer"),
    ("CM", "test_guard_attachment_rejection_preserves_exact_primary_and_secondary_failure"),
    ("CM", "test_guard_writer_hook_changes_are_recovered_after_callback_and_never_clean"),
    ("CM", "test_nested_matplotlib_guard_blocks_real_import_attempt_and_retains_primary"),
    ("CM", "test_runner_refuses_missing_or_foreign_target_before_worker"),
    ("CM", "test_runner_forwards_one_declared_target_to_existing_guard_and_child"),
    ("CM", "test_undecorated_outer_body_cannot_hide_behind_canonical_wrapped_helper"),
    ("CM", "test_undecorated_helper_defaults_and_delegates_are_exact"),
    ("CM", "test_named_missing_name_helper_authenticates_before_any_delegate"),
    ("CM", "test_numpy_copy_export_substitution_refuses_without_any_delegate"),
    ("CM", "test_numpy_argument_delegate_requires_actual_direct_owned_edge"),
    ("CM", "test_numpy_actual_implementation_role_is_distinct_from_unordered_gc_membership"),
    ("CM", "test_registry_dispatch_retarget_refuses_before_attribute_or_load_entry"),
    ("CM", "test_source_unwind_hook_loss_and_restore_rejection_preserve_original_primary"),
    ("CM", "test_toy_getter_line_mutation_is_rejected_before_foreign_dispatch_without_owner"),
    ("CM", "test_prepare_shaped_catch_retains_canonical_primary_after_recovery_sentinel"),
    ("WR", "test_cleanup_batch_launch_stays_held_before_snapshot"),
    ("WR", "test_exact_function_selection_refuses_foreign_targets_before_packet"),
    ("WR", "test_direct_child_and_cli_refuse_before_pytest_or_output"),
    ("WR", "test_worker_authorization_binds_parent_image_entry_and_consumes_once"),
    ("WR", "test_parent_authorization_survives_inherited_release_environment_stripping"),
    ("WR", "test_dual_hook_recovery_samples_after_both_actions_and_never_erases_failure"),
    ("WR", "test_final_recovery_helper_entry_refusal_preserves_primary_and_retires_guard"),
    ("WR", "test_observer_bookkeeping_failure_preserves_falsey_primary_and_both_hooks"),
    ("WR", "test_observer_final_samples_follow_mutating_bookkeeping"),
    ("WR", "test_failed_observer_restore_stops_bookkeeping_even_after_recovery"),
    ("WR", "test_real_observer_toy_nested_frames_and_attempts_are_not_cases"),
    ("WR", "test_real_observer_stops_first_safe_boundary_and_preserves_falsey_unwind"),
    ("WR", "test_real_inherited_callback_raw_entry_is_counted_poisoned_and_cannot_be_caught"),
    ("WR", "test_actual_wrong_parent_helper_frame_refuses_before_body_and_stays_poisoned"),
    ("WR", "test_actual_hook_setter_failures_recover_both_without_replacing_source_unwind"),
    ("WR", "test_inherited_callback_cannot_disable_parent_safe_boundaries"),
    ("WR", "test_worker_final_cleanup_accepts_unchanged_conditional_evidence"),
    ("WR", "test_worker_evidence_probes_and_writes_are_independent_of_primary"),
    ("WR", "test_worker_samples_after_every_writer_and_refuses_recovered_hook_drift"),
    ("WR", "test_worker_final_hook_cleanup_is_bounded_independent_and_keeps_primary"),
    ("WR", "test_worker_hook_loss_stops_all_later_metadata_even_after_final_recovery"),
    ("WR", "test_worker_formatter_hook_loss_stops_later_formatters_attachment_and_writers"),
    ("WR", "test_first_group_creates_launcher_before_guard_without_starting_worker"),
    ("WR", "test_worker_formatter_bypasses_custom_cause_and_type_access_before_hook_loss"),
)


REMAINING_SOFTWARE_RELEASE = "CELLS_NATIVE_PARAMETER_CLEANUP_REMAINING_SOFTWARE_RELEASED"
PRIOR_CLEANUP_REFS = {
    "inputs": (
        "/mnt/workspaces/Cells/native-parameter-CM-WR-seam-repair-20261102-01/prepared/batch-inputs.json",
        "54203ff59acd70a5ecf5f407ff79a3d9c8ad6ad10d06438a708ea7733f40a6fd",
    ),
    "terminal": (
        "/mnt/workspaces/Cells/native-parameter-CM-WR-seam-repair-20261102-01/prepared/BATCH-FAILURE.json",
        "48baeaf11946611fd178c8157eed8a1a89475e408699d75a7a24784342857153",
    ),
    "review": (
        "/mnt/workspaces/Cells/native-parameter-CM-WR-seam-repair-20261102-01/root-batch-review.json",
        "9ce6e73baf0045baa11a11c1152dc6194a0844341402dae8862886c1232dbaf1",
    ),
    "fixture_review": (
        "/mnt/workspaces/Cells/native-parameter-CM-api-default-fixture-repair-20261102-01/root-review.json",
        "33a393f7258b8bf7302c4ac5424c8e8fbafa7c3b245d8d683fa1a89010d74c94",
    ),
}
REVIEWED_CLEANUP_REFS = {
    "prior": (
        "/mnt/workspaces/Cells/native-parameter-CM-context-focused73-development-20261102-01/root-review.json",
        "a5b8ef340bc089e595460cb3f18a2d0951cde28f8792388cc7e575858a0628b6",
    ),
    "current": (
        "/mnt/workspaces/Cells/native-parameter-CM-required-helper-repair68-20261102-01/root-review.json",
        "cda13b1ff629d0cc0790d388e5002e53c856e8482fd6959947f053091672ce0f",
    ),
}


def _bound_cleanup_record(reference):
    path = Path(reference["path"])
    if not path.is_absolute() or path.is_symlink() or snapshot.digest(path) != reference["sha256"]:
        raise ValueError("Bound cleanup evidence changed")
    return json.loads(path.read_text())


def _literal_selector(source, test, target):
    """Read this bounded pytest roster without importing tests or evaluating values."""
    tree = ast.parse((Path(source) / test).read_bytes())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == target]
    if len(nodes) != 1:
        raise ValueError("Exactly one declared test function required")
    parameters = []
    # pytest applies the bottom decorator first. These declared modules have __name__ IDs.
    for decorator in reversed(nodes[0].decorator_list):
        if (
            not isinstance(decorator, ast.Call)
            or ast.unparse(decorator.func) != "pytest.mark.parametrize"
            or len(decorator.args) != 2
            or decorator.keywords
            or not isinstance(decorator.args[0], ast.Constant)
            or type(decorator.args[0].value) is not str
            or not isinstance(decorator.args[1], (ast.List, ast.Tuple))
        ):
            raise ValueError("Explicit supported pytest parameter roster required")
        name, values = decorator.args[0].value, decorator.args[1].elts
        if not name.isidentifier() or not values:
            raise ValueError("Single nonempty declared parameter axis required")
        ids = []
        for index, value in enumerate(values):
            if isinstance(value, ast.Constant) and (
                value.value is None or type(value.value) in (str, bool, int)
            ):
                text = str(value.value)
                if not text.isascii() or any(c in text for c in "\\\n\r\t"):
                    raise ValueError("Unambiguous literal pytest parameter ID required")
            elif (
                test == TEST
                and target == "test_direct_child_and_cli_refuse_before_pytest_or_output"
                and name == "entry"
                and isinstance(value, ast.Name)
                and len(values) == 2
                and value.id == ("runner", "world_runner")[index]
            ):
                qualified = "validation.betse.betse_native_parameter_" + (
                    "load_remainder_software"
                    if value.id == "runner"
                    else "world_construction_software"
                )
                aliases = [
                    (n.level, n.module + "." + alias.name)
                    for n in tree.body
                    if isinstance(n, ast.ImportFrom) and n.module is not None
                    for alias in n.names
                    if (alias.asname or alias.name) == value.id
                ]
                shadowed = any(
                    (isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == value.id)
                    or (
                        isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign))
                        and any(
                            isinstance(item, ast.Name)
                            and isinstance(item.ctx, ast.Store)
                            and item.id == value.id
                            for item in ast.walk(n)
                        )
                    )
                    or (
                        isinstance(n, ast.Import)
                        and any((a.asname or a.name.split(".")[0]) == value.id for a in n.names)
                    )
                    for n in tree.body
                )
                if aliases != [(0, qualified)] or shadowed:
                    raise ValueError("Exact unshadowed declared module alias required")
                text = qualified
            else:
                raise ValueError("Undeclared executable parameter value refused")
            ids.append(text)
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate pytest parameter IDs refused")
        parameters.append(ids)
    names = (
        [target]
        if not parameters
        else [target + "[" + "-".join(parts) + "]" for parts in itertools.product(*parameters)]
    )
    nodeids = [test + "::" + name for name in names]
    if len(set(nodeids)) != len(nodeids):
        raise ValueError("Duplicate expanded pytest node IDs refused")
    return dict(
        function_nodeid=test + "::" + target,
        expected_item_names=names,
        expected_nodeids=nodeids,
        expected_cases=len(nodeids),
    )


def _case_roster(selector, cases, guards):
    """Require each exact successful item and its own complete post-teardown guard."""
    expected = selector["expected_nodeids"]
    test, target = selector["function_nodeid"].split("::")
    if (
        type(expected) is not list
        or not expected
        or any(type(node) is not str for node in expected)
        or len(expected) != len(set(expected))
        or type(selector["expected_cases"]) is not int
        or selector["expected_cases"] != len(expected)
        or selector["expected_item_names"] != [n.split("::")[1] for n in expected]
        or any(
            n != test + "::" + target and not n.startswith(test + "::" + target + "[")
            for n in expected
        )
    ):
        raise ValueError("Unique exact expected node roster required")
    actual = []
    for case in cases:
        if (
            case.tag != "testcase"
            or case.get("classname") != test[:-3].replace("/", ".")
            or any(c.tag in ("failure", "error", "skipped") for c in case)
        ):
            raise ValueError("Successful exact-module JUnit items required")
        actual.append(test + "::" + case.get("name", ""))
    if actual != expected or len(guards) != len(expected):
        raise ValueError("Exact ordered unique JUnit item/node IDs required")
    by_node = {}
    for guard in guards:
        node = guard.get("nodeid")
        if node not in expected or node in by_node:
            raise ValueError("Exact unique item/guard association required")
        for name in ("attempted", "flattened_attempted", "cleanup_error_stages"):
            if type(guard.get(name)) is not list or guard[name]:
                raise ValueError("Guard attempts or incomplete cleanup refused")
        for name in (
            "fixture_setup_completed",
            "inherited_receipt_complete",
            "inherited_generator_closed",
            "profile_restored",
            "trace_restored",
        ):
            if guard.get(name) is not True:
                raise ValueError("Complete post-teardown guard required")
        for name in (
            "actual_native_numeric_parser_RNG_path_writes",
            "actual_event_source_numeric_parser_RNG_file_entries",
            "final_blocked_attempt_count",
        ):
            if type(guard.get(name)) is not int or guard[name] != 0:
                raise ValueError("Zero actual/attempted work guard required")
        by_node[node] = guard
    return list(actual)


def _reference_contract(record):
    """Shared data contract of the two reviewed full-file fixture producers.

    As in the existing CM reader, persisted False is before the evidence callback;
    this record requires the independently checked successful full pytest teardown.
    """
    if type(record) is not dict:
        raise ValueError("Complete Matplotlib reference receipt required")
    for name in ("attempts", "cleanup_errors"):
        if type(record.get(name)) is not list or record[name]:
            raise ValueError("Matplotlib attempts or cleanup failure refused")
    for name in ("primary_type", "primary_identity", "primary_cause_identity"):
        if name not in record or record[name] is not None:
            raise ValueError("Matplotlib receipt retained a primary failure")
    for kind in ("profile", "trace"):
        actual = record.get("final_" + kind + "_identity")
        expected = record.get("expected_" + kind + "_identity")
        if (
            record.get(kind + "_restored") is not True
            or type(actual) is not int
            or type(expected) is not int
            or actual <= 0
            or actual != expected
        ):
            raise ValueError("Matplotlib hook identity mismatch")
    if (
        type(record.get("actual_import_factory_entries")) is not int
        or record["actual_import_factory_entries"] != 0
    ):
        raise ValueError("Matplotlib actual import/factory entries refused")
    if (
        record.get("clean_guard") is not False
        or record.get("certification") != "Successful cleanup return is also required"
        or record.get("hook_evidence_phase")
        != "Before evidence callback; returned final samples also required"
    ):
        raise ValueError("Exact pre-return Matplotlib receipt phase required")


def _group_evidence(row, selector, *, fixture_source):
    saved = _bound_cleanup_record(row["software"])
    runtime = _bound_cleanup_record(row["runtime"])
    junit = Path(row["junit"]["path"])
    if snapshot.digest(junit) != row["junit"]["sha256"] or junit.is_symlink():
        raise ValueError("Bound group JUnit changed")
    if (
        saved["status"] != "completed"
        or type(saved["returncode"]) is not int
        or saved["returncode"] != 0
        or saved["complete_guards"] is not True
        or type(saved["guard_attempts"]) is not int
        or saved["guard_attempts"] != 0
        or type(saved["guard_receipts"]) is not int
        or saved["guard_receipts"] != selector["expected_cases"]
        or type(runtime["pytest_status"]) is not int
        or runtime["pytest_status"] != 0
    ):
        raise ValueError("Successful full group/pytest teardown required")
    paths = sorted((junit.parent / "pytest").rglob("native-blocked.json"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("Original native guard files required")
    guards = [json.loads(p.read_text()) for p in paths]
    nodes = _case_roster(selector, list(ET.parse(junit).iter("testcase")), guards)
    test = selector["function_nodeid"].split("::")[0]
    if test not in (CM_GUARD_TEST, TEST, CM_CONTEXT_TEST):
        raise ValueError("Exact reviewed test/fixture route required")
    reference_installed = test != CM_CONTEXT_TEST
    fixture = Path(fixture_source) / (CM_GUARD_TEST if reference_installed else CM_CONTEXT_TEST)
    fixture_pin = snapshot.digest(fixture)
    allowed = (
        (CM_GUARD_SHA256, CM_GUARD_LEGACY_SHA256) if reference_installed else (CM_CONTEXT_SHA256,)
    )
    if fixture.is_symlink() or fixture_pin not in allowed:
        raise ValueError("Exact reviewed bank fixture producer required")
    references, matched = [], set()
    for path, guard in zip(paths, guards, strict=True) if reference_installed else ():
        sibling = path.with_name("matplotlib-blocked.json")
        if not sibling.is_file() or sibling.is_symlink():
            raise ValueError("Case Matplotlib sibling receipt missing or foreign")
        _reference_contract(json.loads(sibling.read_text()))
        matched.add(sibling)
        references.append(
            dict(
                nodeid=guard["nodeid"],
                reference=inherited.ref(sibling),
                fixture_sha256=fixture_pin,
                persisted_record_is_final_certificate=False,
            )
        )
    # Nested deliberate guard probes are diagnostics, not additional pytest cases.
    extras = [
        inherited.ref(p)
        for p in sorted((junit.parent / "pytest").rglob("matplotlib-blocked.json"))
        if p not in matched
    ]
    return dict(
        nodeids=nodes,
        native_guards=[inherited.ref(p) for p in paths],
        matplotlib_references=references,
        additional_matplotlib_diagnostics=extras,
        fixture_source=dict(path=str(fixture), sha256=fixture_pin),
        reference_fixture_installed=reference_installed,
        software=row["software"],
        runtime=row["runtime"],
        junit=row["junit"],
    )


def _remaining_shape(prior, terminal, review, fixture_review, affected):
    """Data-shape check only; actual entry also authenticates every evidence pin."""
    expected = [list(row) for row in CLEANUP_GROUPS]
    if len(expected) != 42 or prior["groups"] != expected or prior["resources"] != RESOURCES:
        raise ValueError("Exact original cleanup plan/resources required")
    if (
        terminal["status"] != "failed_stopped_no_retry"
        or terminal["inputs_sha256"] != PRIOR_CLEANUP_REFS["inputs"][1]
        or terminal["active"] != dict(index=8, family="CM", target=CLEANUP_GROUPS[8][1])
        or [row["index"] for row in terminal["outcomes"]] != list(range(8))
        or sum(row["cases"] for row in terminal["outcomes"]) != 28
    ):
        raise ValueError("Original eight-complete/one-failed disposition required")
    if (
        review["status"] != "batch_failed_fixture_correction_required"
        or review["batch_inputs"]["sha256"] != PRIOR_CLEANUP_REFS["inputs"][1]
        or review["terminal"]["sha256"] != PRIOR_CLEANUP_REFS["terminal"][1]
        or (review["passed_cases"], review["failed_cases"], review["unrun_cases"]) != (29, 1, 124)
    ):
        raise ValueError("Exact prior Root review required")
    targets = [CLEANUP_GROUPS[i][1] for i in range(8, 11)]
    if (
        fixture_review["status"] != "source_accepted_affected_eight_software_authorized"
        or fixture_review["software_release"]["controls"] != targets
        or fixture_review["software_release"]["cases"] != 8
    ):
        raise ValueError("Exact affected-eight source disposition required")
    fresh = affected["fresh_software"]
    if (
        affected["kind"] != "cells.Root_CM_required_helper68_source_saved_review@1"
        or affected["disposition"]
        != "clear_for_scoped_Git_integration_held_source_and_blocked_software_only"
        or affected["blockers"] != []
        or (fresh["passed"], fresh["failed"], fresh["selected_unique"]) != (68, 0, 68)
        or fresh["by_module"]
        != {CM_GUARD_TEST: 18, "tests/unit/test_betse_native_parameter_colormaps.py": 50}
        or fresh["forbidden_attempts"] != 0
        or fresh["new_scientific_calls"] != 0
    ):
        raise ValueError("Exact reviewed68 disposition required; no synthetic current-source eight")
    return tuple(range(11, 42))


def _remaining_selection(affected_reference):
    reviewed = {
        name: dict(path=path, sha256=pin) for name, (path, pin) in REVIEWED_CLEANUP_REFS.items()
    }
    if affected_reference != reviewed["current"]:
        raise ValueError("Exact Root-reviewed split-source evidence required")
    references = {
        name: dict(path=path, sha256=pin) for name, (path, pin) in PRIOR_CLEANUP_REFS.items()
    }
    records = {name: _bound_cleanup_record(ref) for name, ref in references.items()}
    affected = _bound_cleanup_record(affected_reference)
    indices = _remaining_shape(
        records["inputs"],
        records["terminal"],
        records["review"],
        records["fixture_review"],
        affected,
    )
    earlier = _bound_cleanup_record(reviewed["prior"])
    if (
        earlier["disposition"] != "saved_evidence_verified_terminal_failure_preserved"
        or earlier["integrity_blockers"] != []
    ):
        raise ValueError("Reviewed earlier successes and failed controllers required")
    if affected["historical_scope"]["prior_root_review"] != reviewed["prior"]:
        raise ValueError("Current review must bind original source bank")
    failures = []
    for row in earlier["preserved_failures"]:
        record = _bound_cleanup_record(row["artifact"])
        if record["status"] != "failed_stopped_no_retry":
            raise ValueError("Failed controllers must remain failed")
        failures.append(dict(classification=row["classification"], artifact=row["artifact"]))
    if len(failures) != 2:
        raise ValueError("Both original controller failures required")
    failed = earlier["groups"][2]
    if _bound_cleanup_record(failed["software"])["status"] != "failed":
        raise ValueError("Original missing-helper failed group must remain failed")
    if snapshot.digest(Path(failed["junit"]["path"])) != failed["junit"]["sha256"]:
        raise ValueError("Original failed JUnit must remain bound")
    failures.append(
        dict(
            classification="failed_group_not_recredited",
            artifact=failed["software"],
            junit=failed["junit"],
        )
    )
    failed_processes = [
        row["terminal"] for row in earlier["terminal_outcomes"] if row["status"] == "failed"
    ]
    if len(failed_processes) != 4 or any(
        _bound_cleanup_record(ref)["status"] != "failed" for ref in failed_processes
    ):
        raise ValueError("All four earlier failed process terminals must remain failed")
    bound = affected["bound_evidence"]
    batch = _bound_cleanup_record(bound["batch_result"])
    inputs68 = _bound_cleanup_record(bound["batch_inputs"])
    selected68 = _bound_cleanup_record(bound["selection"])
    # Bind the correction to frozen inherited summary fields, never use those fields as counts.
    _bound_cleanup_record(bound["selection_summary_reconciliation"])
    packet_refs = {
        "earlier": next(
            ref
            for ref in earlier["bound_evidence"]
            if ref["path"] == str(Path(reviewed["prior"]["path"]).parent / "packet/inputs.json")
        ),
        "current": inputs68["packet"],
    }
    banks = {}
    for name, ref in packet_refs.items():
        packet = _bound_cleanup_record(ref)
        manifest = _bound_cleanup_record(packet["snapshot"])
        source = Path(packet["snapshot"]["path"]).parent
        pin = manifest["files"][CM_GUARD_TEST]["sha256"]
        if snapshot.digest(source / CM_GUARD_TEST) != pin:
            raise ValueError("Actual affected test producer changed")
        banks[name] = dict(packet=ref, snapshot=packet["snapshot"], test_sha256=pin)
    if banks["current"]["test_sha256"] != CM_GUARD_SHA256:
        raise ValueError("Explicit current fixture successor required")
    split_groups, all_affected = [], []
    for original, bank_name, actual_index, row in (
        (8, "earlier", 0, earlier["groups"][0]),
        (9, "earlier", 1, earlier["groups"][1]),
        (10, "current", 2, batch["groups"][0]),
    ):
        target = CLEANUP_GROUPS[original][1]
        if row["index"] != actual_index:
            raise ValueError("Retain actual execution indices; no original-index relabel")
        bank = banks[bank_name]
        if _bound_cleanup_record(row["software"])["packet"] != bank["packet"]:
            raise ValueError("Actual execution packet must match its source bank")
        source = Path(bank["snapshot"]["path"]).parent
        selector = _literal_selector(source, CM_GUARD_TEST, target)
        evidence = _group_evidence(row, selector, fixture_source=source)
        all_affected.extend(evidence["nodeids"])
        split_groups.append(
            dict(
                original_index=original,
                execution_index=actual_index,
                bank=bank_name,
                selector=selector,
                evidence=evidence,
            )
        )
    if len(all_affected) != 8 or len(set(all_affected)) != 8:
        raise ValueError("Exactly eight unique affected node identities required")
    current_nodes = []
    current_functions = []
    current_source = Path(banks["current"]["snapshot"]["path"]).parent
    current_manifest = _bound_cleanup_record(banks["current"]["snapshot"])
    for row, group in zip(selected68["selectors"], batch["groups"], strict=True):
        test, target = row["function_nodeid"].split("::")
        if (
            group["target"] != target
            or group["status"] != "completed_reviewed"
            or _bound_cleanup_record(group["software"])["packet"] != banks["current"]["packet"]
            or snapshot.digest(current_source / test) != current_manifest["files"][test]["sha256"]
        ):
            raise ValueError("Current68 group and actual source must match selector")
        exact = {
            key: row[key]
            for key in (
                "function_nodeid",
                "expected_item_names",
                "expected_nodeids",
                "expected_cases",
            )
        }
        evidence = _group_evidence(group, exact, fixture_source=current_source)
        current_functions.append(row["function_nodeid"])
        current_nodes.extend(evidence["nodeids"])
    if (
        len(current_functions) != 18
        or len(set(current_functions)) != 18
        or len(current_nodes) != 68
        or len(set(current_nodes)) != 68
    ):
        raise ValueError("Exact unique current68 roster required")
    counts, selectors, producers, family_counts = {}, {}, {}, dict(CM=0, WR=0)
    prior_root = Path(PRIOR_CLEANUP_REFS["inputs"][0]).parent
    for index in indices:
        family, target = CLEANUP_GROUPS[index]
        test = CM_GUARD_TEST if family == "CM" else TEST
        packet = json.loads((prior_root / (family + "-packet/inputs.json")).read_text())
        if (
            snapshot.digest(prior_root / (family + "-packet/inputs.json"))
            != records["inputs"]["packets"][family]["sha256"]
        ):
            raise ValueError("Original test-producer packet changed")
        source = prior_root / (family + "-packet/source")
        manifest = _bound_cleanup_record(packet["snapshot"])
        if snapshot.digest(source / test) != manifest["files"][test]["sha256"]:
            raise ValueError("Original exact-function source changed")
        selector = _literal_selector(source, test, target)
        checkout = Path(__file__).resolve().parents[2]
        if _literal_selector(checkout, test, target) != selector:
            raise ValueError("Current source must preserve exact original remaining item IDs")
        if selector["function_nodeid"] in current_functions or set(
            selector["expected_nodeids"]
        ) & set(current_nodes):
            raise ValueError("Remaining selectors overlap completed68")
        selectors[str(index)] = selector
        counts[str(index)] = selector["expected_cases"]
        producers[test] = snapshot.digest(checkout / test)
        family_counts[family] += selector["expected_cases"]
    producers[FILE] = snapshot.digest(Path(__file__))
    if producers[CM_GUARD_TEST] != CM_GUARD_SHA256:
        raise ValueError("Current exact CM fixture producer required before preparation")
    remaining_nodes = [node for row in selectors.values() for node in row["expected_nodeids"]]
    if len(remaining_nodes) != len(set(remaining_nodes)):
        raise ValueError("Unique remaining item/node IDs required")
    if sum(counts.values()) != 118 or family_counts != dict(CM=29, WR=89):
        raise ValueError("Original remaining118 case roster changed")
    return dict(
        kind="original_remaining_only",
        indices=list(indices),
        cases=118,
        case_counts=counts,
        selectors=selectors,
        cases_by_family=family_counts,
        functions=len(selectors),
        producers=producers,
        prior=references,
        affected=affected_reference,
        split_affected=dict(
            cases=8,
            earlier_source_cases=5,
            current_source_cases=3,
            single_current_source_run=False,
            banks=banks,
            groups=split_groups,
        ),
        current68=dict(
            review=reviewed["current"],
            selectors=bound["selection"],
            nodeids=current_nodes,
            functions=current_functions,
        ),
        preserved_failures=failures,
        preserved_failed_processes=failed_processes,
        prior_review=reviewed["prior"],
        overlap_with_current68=[],
        held_for_Root_disposition=True,
    )


def _selected_cleanup_groups(inputs):
    selection = inputs.get("selection")
    if selection is None:
        if inputs["groups"] != [list(row) for row in CLEANUP_GROUPS]:
            raise ValueError("Exact legacy cleanup plan required")
        return tuple(enumerate(CLEANUP_GROUPS))
    if selection.get("kind") != "original_remaining_only":
        raise ValueError("Unknown cleanup selection")
    expected = _remaining_selection(selection["affected"])
    if selection != expected or inputs["groups"] != [
        list(CLEANUP_GROUPS[i]) for i in expected["indices"]
    ]:
        raise ValueError("Remaining selection must be exactly original11-41; no prefix replay")
    return tuple((i, CLEANUP_GROUPS[i]) for i in expected["indices"])


def _remaining_release():
    if os.environ.get(REMAINING_SOFTWARE_RELEASE) != "1":
        raise ValueError(
            "Remaining software execution held for affected-eight review and Root disposition"
        )


def prepare_remaining_cleanup(directory, affected_result, affected_sha):
    selection = _remaining_selection(
        dict(path=str(Path(affected_result).resolve(strict=True)), sha256=affected_sha)
    )
    return prepare_cleanup_batch(directory, selection=selection)


def _cleanup_environment(source):
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    environment.update(
        PYTHONPATH=os.pathsep.join(
            [
                str(source / "src"),
                str(source),
                "/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01",
            ]
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        RAYON_NUM_THREADS="1",
    )
    return environment


def prepare_cleanup_batch(directory, *, selection=None):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Cleanup software launch remains held for Root")
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if inherited.guard.memory_available() < 8 * 2**30:
        raise ValueError("Metadata host reserve below 8GiB")
    repo = Path(__file__).resolve().parents[2]
    if repo != Path("/home/robert/Cells") or os.sched_getaffinity(0) != {0}:
        raise ValueError("Actual checkout and CPU0 required for software-only preparation")
    directory = inherited.separate(
        Path(directory), repo, Path("/mnt/workspaces/Cells/betse-v1.5.0")
    )
    rows = (
        _selected_cleanup_groups(
            dict(
                groups=[list(CLEANUP_GROUPS[i]) for i in selection["indices"]], selection=selection
            )
        )
        if selection is not None
        else tuple(enumerate(CLEANUP_GROUPS))
    )
    groups = [row for _, row in rows]
    directory.mkdir(parents=True, exist_ok=False)
    owned = (
        *OWNED,
        CM_FILE,
        CM_GUARD_TEST,
        "src/cells/processes/betse_native_parameter_colormap_load.py",
    )
    selected = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"](repo, list(owned))
    for name in ("pyproject.toml", "tests/__init__.py", inherited.CLOSURE_TOOL):
        selected[name] = snapshot.digest(repo / name)
    for family, file in (("CM", CM_FILE), ("WR", FILE)):
        packet = directory / (family + "-packet")
        packet.mkdir()
        manifest = snapshot.freeze(repo, packet / "source", {name: name for name in selected})
        # This declarative software plan does not call or substitute a missing
        # production source_plan, owner, factory or genuine handoff authority.
        snapshot.write_json(
            packet / "source-plan.json",
            dict(
                law="blocked_CM_WR_cleanup_metadata@1",
                targets=[t for f, t in groups if f == family],
                production_admission=False,
                genuine_source_plan_and_owner_prerequisites_still_required=True,
            ),
        )
        snapshot.write_json(
            packet / "inputs.json",
            dict(
                law="blocked_CM_WR_cleanup_metadata@1",
                repository=str(repo),
                git_revision=manifest["git_revision"],
                held=True,
                snapshot=inherited.ref(packet / "source/SNAPSHOT.json"),
                source_plan=inherited.ref(packet / "source-plan.json"),
                owned_files={name: manifest["files"][name]["sha256"] for name in owned},
                external_runtime_paths=["/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01"],
                resources=RESOURCES,
                software_entry=dict(
                    file=file,
                    test=CM_GUARD_TEST if family == "CM" else TEST,
                    release=None if family == "CM" else SOFTWARE_RELEASE,
                    native_release=False,
                ),
                fixture_producer=dict(path=CM_GUARD_TEST, sha256=CM_GUARD_SHA256),
                actual_source_native_parser_RNG_phase_or_science_release=False,
            ),
        )
    controller = directory / "WR-packet/source"
    for family in ("CM", "WR"):
        snapshot.assert_checkout_unchanged(directory / (family + "-packet/source"))
    inputs = dict(
        groups=groups,
        selection=selection,
        resources=RESOURCES,
        retry=False,
        scientific_release=False,
        packets={f: inherited.ref(directory / (f + "-packet/inputs.json")) for f in ("CM", "WR")},
        controller_manifest=inherited.ref(controller / "SNAPSHOT.json"),
    )
    snapshot.write_json(directory / "batch-inputs.json", inputs)
    return dict(
        status="prepared_held_software_only",
        batch_inputs=inherited.ref(directory / "batch-inputs.json"),
    )


def launch_cleanup_batch(directory):
    prepared = prepare_cleanup_batch(directory)
    return start_prepared_cleanup_batch(directory, prepared["batch_inputs"]["sha256"])


def start_prepared_cleanup_batch(directory, inputs_sha):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Cleanup software launch remains held for Root")
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    repo = Path(__file__).resolve().parents[2]
    if repo != Path("/home/robert/Cells") or os.sched_getaffinity(0) != {0}:
        raise ValueError("Actual checkout and CPU0 required for software-only launch")
    directory = inherited.separate(
        Path(directory), repo, Path("/mnt/workspaces/Cells/betse-v1.5.0")
    )
    if snapshot.digest(directory / "batch-inputs.json") != inputs_sha:
        raise ValueError("Prepared software plan changed")
    inputs = json.loads((directory / "batch-inputs.json").read_text())
    rows = _selected_cleanup_groups(inputs)
    if inputs["resources"] != RESOURCES:
        raise ValueError("Exact current cleanup resources required")
    if inputs.get("selection") is not None:
        _remaining_release()
    for family in ("CM", "WR"):
        if (
            snapshot.digest(directory / (family + "-packet/inputs.json"))
            != inputs["packets"][family]["sha256"]
        ):
            raise ValueError("Prepared software producer changed")
        snapshot.assert_checkout_unchanged(directory / (family + "-packet/source"))
    controller = directory / "WR-packet/source"
    # Metadata preparation is capped separately. The detached software tree
    # inherits its declared 1GiB ceiling and retains the sampled RSS guards.
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    with (
        (directory / "controller.stdout.log").open("x") as stdout,
        (directory / "controller.stderr.log").open("x") as stderr,
    ):
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                FILE[:-3].replace("/", "."),
                "--cleanup-batch-child",
                str(directory),
                "--batch-inputs-sha256",
                snapshot.digest(directory / "batch-inputs.json"),
            ],
            cwd=controller,
            env=dict(
                _cleanup_environment(controller),
                **(
                    {REMAINING_SOFTWARE_RELEASE: "1"} if inputs.get("selection") is not None else {}
                ),
            ),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
    launch = dict(
        status="detached_blocked_software_only",
        pid=process.pid,
        cpu=0,
        groups=len(rows),
        automatic_retry=False,
        batch_inputs=inherited.ref(directory / "batch-inputs.json"),
    )
    snapshot.write_json(directory / "LAUNCH.json", launch)
    return launch


def cleanup_batch_child(directory, inputs_sha):
    directory = Path(directory).resolve(strict=True)
    outcomes, active = [], None
    try:
        if snapshot.digest(directory / "batch-inputs.json") != inputs_sha or os.sched_getaffinity(
            0
        ) != {0}:
            raise ValueError("Frozen cleanup batch authority changed")
        inputs = json.loads((directory / "batch-inputs.json").read_text())
        rows = _selected_cleanup_groups(inputs)
        if inputs["resources"] != RESOURCES:
            raise ValueError("Exact target resources required")
        if inputs.get("selection") is not None:
            _remaining_release()
        source = Path(__file__).resolve().parents[2]
        snapshot.verify(source, manifest_sha256=inputs["controller_manifest"]["sha256"])
        for index, (family, target) in rows:
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > 512 * 2**20:
                raise ValueError("Metadata controller exceeds 512MiB")
            active = dict(index=index, family=family, target=target)
            packet = directory / (family + "-packet")
            if snapshot.digest(packet / "inputs.json") != inputs["packets"][family]["sha256"]:
                raise ValueError("Software packet changed")
            group = directory / (str(index).zfill(2) + "-" + family)
            group.mkdir()
            (group / "launcher").mkdir()
            file = CM_FILE if family == "CM" else FILE
            environment = _cleanup_environment(packet / "source")
            environment[SOFTWARE_RELEASE] = "1"  # Software only; stripped before the child.
            command = [
                sys.executable,
                "-B",
                "-m",
                file[:-3].replace("/", "."),
                "--software",
                str(packet),
                "--output",
                str(group / "software"),
                "--target",
                target,
            ]
            inherited.guard.run_bounded(
                command,
                directory=group / "launcher",
                cwd=packet / "source",
                env=environment,
                timeout=480,
                max_rss_bytes=2**30,
                min_available_bytes=8 * 2**30,
            )
            test = CM_GUARD_TEST if family == "CM" else TEST
            selector = _literal_selector(packet / "source", test, target)
            if (
                inputs.get("selection") is not None
                and selector != inputs["selection"]["selectors"][str(index)]
            ):
                raise ValueError("Original remaining item/node IDs changed")
            evidence = _group_evidence(
                {
                    key: inherited.ref(group / "software" / leaf)
                    for key, leaf in (
                        ("software", "result.json"),
                        ("runtime", "runtime.json"),
                        ("junit", "junit.xml"),
                    )
                },
                selector,
                fixture_source=packet / "source",
            )
            review = dict(
                **active,
                status="completed_reviewed",
                cases=len(evidence["nodeids"]),
                guards=len(evidence["native_guards"]),
                exact_selector=selector,
                evidence=evidence,
                result=inherited.ref(group / "software/result.json"),
                source=inputs["packets"][family],
                actual_source_entries=0,
                biological_credit=0,
            )
            snapshot.write_json(group / "local-review.json", review)
            outcomes.append(review)
            active = None
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > 512 * 2**20:
            raise ValueError("Metadata controller exceeds 512MiB")
        snapshot.write_json(
            directory / "BATCH-RESULT.json",
            dict(
                status="completed",
                outcomes=outcomes,
                inputs_sha256=inputs_sha,
                scientific_credit=0,
                automatic_retry=False,
            ),
        )
        return 0
    except BaseException as error:
        snapshot.write_json(
            directory / "BATCH-FAILURE.json",
            dict(
                status="failed_stopped_no_retry",
                outcomes=outcomes,
                active=active,
                unrun_from=len(outcomes),
                error_type=type(error).__qualname__,
                traceback=traceback.format_exc(),
                inputs_sha256=inputs_sha,
                scientific_credit=0,
                automatic_retry=False,
            ),
        )
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--launch-cleanup-batch", type=Path)
    mode.add_argument("--prepare-cleanup-batch", type=Path)
    mode.add_argument("--prepare-remaining-cleanup", type=Path)
    parser.add_argument("--affected-result", type=Path)
    parser.add_argument("--affected-sha256")
    mode.add_argument("--start-prepared-cleanup-batch", type=Path)
    mode.add_argument("--cleanup-batch-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--batch-inputs-sha256")
    mode.add_argument("--software", type=Path)
    mode.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--authorization-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--target")
    args = parser.parse_args()
    if args.prepare_remaining_cleanup:
        print(
            json.dumps(
                prepare_remaining_cleanup(
                    args.prepare_remaining_cleanup, args.affected_result, args.affected_sha256
                )
            )
        )
        return 0
    if args.prepare_cleanup_batch:
        print(json.dumps(prepare_cleanup_batch(args.prepare_cleanup_batch)))
        return 0
    if args.start_prepared_cleanup_batch:
        print(
            json.dumps(
                start_prepared_cleanup_batch(
                    args.start_prepared_cleanup_batch, args.batch_inputs_sha256
                )
            )
        )
        return 0
    if args.launch_cleanup_batch:
        print(json.dumps(launch_cleanup_batch(args.launch_cleanup_batch)))
        return 0
    if args.cleanup_batch_child:
        return cleanup_batch_child(args.cleanup_batch_child, args.batch_inputs_sha256)
    if args.child:
        return child(
            args.child,
            authorization=args.authorization,
            authorization_sha256=args.authorization_sha256,
            target=args.target,
        )
    if args.prepare:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.software and args.output:
        result = software(args.software, args.output, target=args.target)
        print(json.dumps(result))
        return int(result["returncode"])
    parser.error("--software requires --output")


if __name__ == "__main__":
    raise SystemExit(main())
