"""Source-only preparation; software workers require a separate Root release."""

import argparse
import ast
import copy
import hashlib
import json
import marshal
import os
import runpy
import secrets
import sys
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
CM_GUARD_SHA256 = "89a54c30a2c2f7077bcb183c2cacf6855314142781ccac5fa15e625806821945"
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
            fixture_producer=dict(path=CM_GUARD_TEST, sha256=CM_GUARD_SHA256),
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
    if (
        inputs["software_entry"]
        != dict(file=file, test=test, release=release, native_release=False)
        or inputs["resources"] != RESOURCES
        or inputs.get("actual_source_native_parser_RNG_phase_or_science_release") is not False
        or inputs["fixture_producer"] != dict(path=CM_GUARD_TEST, sha256=CM_GUARD_SHA256)
        or manifest["files"][CM_GUARD_TEST]["sha256"] != CM_GUARD_SHA256
        or snapshot.digest(packet / "source-plan.json") != inputs["source_plan"]["sha256"]
    ):
        raise ValueError("Exact held software image/resources/fixture required")
    for name in (file, test, production):
        if inputs["owned_files"].get(name) != manifest["files"][name]["sha256"]:
            raise ValueError("Selected software producer changed")
    return packet, inputs, source, manifest


def _authorization(output, authorization, authorization_sha256, *, file, entry_path):
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
    return (
        None
        if error is None
        else dict(
            type=type(error).__qualname__,
            message=str(error),
            identity=id(error),
            cause_identity=id(error.__cause__),
        )
    )


def _child(output, authorization, authorization_sha256, *, file, entry_path):
    image = _authorization(
        output, authorization, authorization_sha256, file=file, entry_path=entry_path
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
        primary=None, pytest_status=None, errors=[], values={}, writes={}, image=image
    )
    try:
        original_profile, original_trace = hook_api["get_profile"](), hook_api["get_trace"]()
        originals_known = True
        before, bindings = _producers(image)
        context.pytest_status = _pytest_driver(ENTRY_CONFIG[file][0])(output)
    except BaseException as error:
        context.primary = error

    # Every probe and every write is independent. Keep actual surviving values
    # even when their first persistence fails, without masking the pytest error.
    def producers():
        if before is None:
            raise ValueError("Initial producer authentication failed; no tests entered")
        after, current = _producers(image, selected=before)
        if (
            after != before
            or len(current) != len(bindings)
            or any(a is not b for a, b in zip(current, bindings, strict=True))
        ):
            raise ValueError("Actual loaded producer/function identity changed during worker")
        all_loaded, _ = _producers(image)
        return dict(before=before, after=all_loaded)

    def hooks():
        observed, failures = {}, []
        for name in ("profile", "trace"):
            try:
                observed[name] = hook_api["get_" + name]()
            except BaseException as error:
                observed[name] = object()
                failures.append((name, error))
        profile, trace = observed["profile"], observed["trace"]
        result = dict(
            profile=id(profile),
            trace=id(trace),
            expected_profile=id(original_profile),
            expected_trace=id(original_trace),
            restored=originals_known and profile is original_profile and trace is original_trace,
            sample_scope="before_later_worker_writers_not_final",
            final_restoration_requires_terminal=True,
        )
        context.values["hook_identities"] = result
        if failures:
            context.errors.extend(("hook_" + name, error) for name, error in failures)
            raise failures[0][1]
        if not result["restored"]:
            raise ValueError(
                "Worker profile/trace identities changed before later evidence writers"
            )
        return result

    for name, function in (
        ("identity", _identity),
        ("inventory", _inventory),
        ("producers", producers),
        ("hooks", hooks),
    ):
        try:
            context.values[name] = function()
        except BaseException as error:
            context.errors.append((name, error))
        if name in context.values:
            try:
                snapshot.write_json(output / (name + ".json"), context.values[name])
                context.writes[name] = True
            except BaseException as error:
                context.writes[name] = False
                context.errors.append((name + "_write", error))
    for filename in ("runtime.json", "worker-evidence.json"):
        try:
            snapshot.write_json(
                output / filename,
                dict(
                    child=context.values.get("identity"),
                    loaded=context.values.get("inventory"),
                    pytest_status=context.pytest_status,
                    primary=_exception(context.primary),
                    errors=[(name, _exception(error)) for name, error in context.errors],
                    available=context.values,
                    writes=context.writes,
                    evidence_operations_so_far_complete=context.primary is None
                    and not context.errors,
                    pytest_returned_zero=context.pytest_status == 0,
                    final_worker_success_requires_terminal=True,
                    final_hook_sample_after_all_writers_pending=True,
                    authorization_sha256=authorization_sha256,
                    native_or_scientific_admission=False,
                ),
            )
        except BaseException as error:
            context.errors.append((filename + "_write", error))
    if context.primary is not None:
        try:
            context.primary.world_ready_worker = context
        except BaseException as error:
            context.errors.append(("primary_context_attachment", error))

    # All evidence writers and primary attachment above are fallible callbacks.
    # Inline cleanup cannot itself be skipped by a rejected helper call-entry.
    # Persisted hook samples are explicitly preliminary; terminal success is
    # conditional on these final independent samples, with drift sticky even
    # when a bounded restoration succeeds. No further writer runs below.
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
                ValueError("Worker hooks changed after evidence callbacks"),
            )
        ]
        if not originals_known:
            break  # Never install an invented original hook after a failed sample.
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
        clean=restored and not cleanup_errors,
    )
    context.values["final_hook_identities"] = dict(
        profile=id(current["profile"]),
        trace=id(current["trace"]),
        expected_profile=id(original_profile),
        expected_trace=id(original_trace),
        restored=restored,
        clean=restored and not cleanup_errors,
        sample_scope="after_all_worker_writers_and_primary_attachment",
    )
    context.errors += cleanup_errors
    if context.primary is not None:
        raise context.primary
    if context.errors:
        raise WorkerEvidenceRejected("Worker evidence incomplete; no success receipt", context)
    return int(context.pytest_status)


def child(output, *, authorization=None, authorization_sha256=None):
    return _child(output, authorization, authorization_sha256, file=FILE, entry_path=__file__)


def software(packet, output):
    return _software(packet, output, file=FILE)


def _software(packet, output, *, file):
    if os.environ.get(ENTRY_CONFIG[file][2]) != "1":
        raise ValueError("Software execution remains held for Root; source preparation only")
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
            ],
            **kwargs,
        )

    return callbacks.delegate(
        inherited.software, FILE=file, guard=SimpleNamespace(run_bounded=bounded)
    )(packet, directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--software", type=Path)
    mode.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--authorization-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return child(
            args.child,
            authorization=args.authorization,
            authorization_sha256=args.authorization_sha256,
        )
    if args.prepare:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.software and args.output:
        result = software(args.software, args.output)
        print(json.dumps(result))
        return int(result["returncode"])
    parser.error("--software requires --output")


if __name__ == "__main__":
    raise SystemExit(main())
