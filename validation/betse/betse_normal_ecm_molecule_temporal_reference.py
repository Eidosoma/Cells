"""Held paired selected-source probe, not a complete native Parameters/SIM run.

Metadata reads pinned ASTs only. The numerical route requires an actual owned
SIM parent and both existing releases. It executes the selected original store
statements on one reference p/_conf, then original factories in literal order.
The reference p is an isolated source probe, never a lifecycle parent.
"""

import ast
import copy
import hashlib
import inspect
import math
import os
import sys
from pathlib import Path
from types import FunctionType, SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ecm_event_join_source as literal
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_periodic_authority as periodic
from cells.processes import betse_normal_ecm_molecule_sweep_authority as sweep
from cells.processes import betse_normal_ecm_molecule_temporal_config as temporal
from cells.processes import betse_time_modulation as laws
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.perturbations import time_modulation_native as native
from validation.perturbations import time_modulation_reference as independent

NATIVE_ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")
RELEASES = ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED")
require = temporal.require


def released():
    require(
        all(os.environ.get(name) == "1" for name in RELEASES),
        "Paired temporal source comparison remains held behind both releases",
    )


def _function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def callback_abi():
    """Inspect, never evaluate, the producer's actual callback return access."""
    function = _function(ast.parse(Path(literal.__file__).read_bytes()), "prepared_callback")
    access = {}
    for branch in function.body:
        if not isinstance(branch, ast.If) or not isinstance(branch.test, ast.Compare):
            continue
        kind = branch.test.comparators[0]
        if not isinstance(kind, ast.Constant) or kind.value not in ("periodic", "sweep"):
            continue
        returned = [n.value for n in branch.body if isinstance(n, ast.Return)]
        require(
            len(returned) == 1
            and isinstance(returned[0], ast.Lambda)
            and isinstance(returned[0].body, ast.Attribute),
            "Unrecognized temporal callback return ABI",
        )
        access[kind.value] = returned[0].body.attr
    fields = tuple(laws.Values._fields)
    declared = next(
        n
        for n in ast.parse(Path(laws.__file__).read_bytes()).body
        if isinstance(n, ast.ClassDef) and n.name == "Values"
    )
    require(
        fields == tuple(n.target.id for n in declared.body if isinstance(n, ast.AnnAssign)),
        "Loaded time-law result type differs from its source declaration",
    )
    missing = [kind for kind in ("periodic", "sweep") if access.get(kind) not in fields]
    return dict(
        callback_access=access,
        result_fields=fields,
        compatible=not missing,
        missing_fields=missing,
        evaluated=False,
        callback_source_sha256=hashlib.sha256(Path(literal.__file__).read_bytes()).hexdigest(),
        time_law_source_sha256=hashlib.sha256(Path(laws.__file__).read_bytes()).hexdigest(),
    )


def _selected_statements(tree):
    names = ("self.periodic_properties", "self.f_scan_properties")
    return sorted(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(
                ast.unparse(t) in names or any(ast.unparse(t).startswith(k + "[") for k in names)
                for t in n.targets
            )
        ),
        key=lambda n: n.lineno,
    )


def factory_correspondence(original, adopted, name):
    """Only declared non-executing adoption differences may be normalized."""
    before, after = copy.deepcopy(original), copy.deepcopy(adopted)
    original_doc, adopted_doc = (
        ast.get_docstring(before, clean=False),
        ast.get_docstring(after, clean=False),
    )
    require(
        type(original_doc) is str
        and type(adopted_doc) is str
        and inspect.cleandoc(original_doc) == inspect.cleandoc(adopted_doc),
        "Factory source documentation content differs: " + name,
    )
    old_annotation = None if before.returns is None else ast.unparse(before.returns)
    new_annotation = None if after.returns is None else ast.unparse(after.returns)
    require(
        (old_annotation, new_annotation) == (None, None)
        or (name == "f_sweep" and (old_annotation, new_annotation) == ("tuple", None)),
        "Unexpected factory annotation correspondence: " + name,
    )
    before.returns = after.returns = None
    before.body, after.body = before.body[1:], after.body[1:]
    require(
        ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False),
        "Owned factory operational AST differs from original source: " + name,
    )
    return dict(
        operational_AST_equal=True,
        docstring_content_equal=True,
        docstring_whitespace_equal=original_doc == adopted_doc,
        original_return_annotation=old_annotation,
        owned_return_annotation=new_annotation,
    )


def source_plan(root=NATIVE_ROOT):
    """Pin original source and independent references without compiling/calling."""
    root = Path(root).resolve(strict=True)
    sources = {}
    for name, expected in periodic.NATIVE_PINS.items():
        path = root / name
        require(not path.is_symlink() and path.is_file(), "Regular original source required")
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == expected,
            "Original temporal source pin changed: " + name,
        )
        sources[name] = dict(path=str(path), sha256=expected)
    tree = ast.parse((root / "betse/science/parameters.py").read_bytes())
    selected = _selected_statements(tree)
    adopted = _function(ast.parse(Path(temporal.source.__file__).read_bytes()), "populate").body
    require(
        len(selected) == 7
        and [ast.dump(n, include_attributes=False) for n in selected]
        == [ast.dump(n, include_attributes=False) for n in adopted],
        "Selected native store order/body differs from owned source",
    )
    original = ast.parse((root / "betse/science/math/modulate.py").read_bytes())
    current = ast.parse(Path(periodic.source.__file__).read_bytes())
    factories = {
        name: factory_correspondence(_function(original, name), _function(current, name), name)
        for name in ("periodic", "f_sweep")
    }
    return dict(
        native_sources=sources,
        selected_statements_AST_sha256=hashlib.sha256(
            "\n".join(ast.dump(n, include_attributes=False) for n in selected).encode()
        ).hexdigest(),
        selected_statement_count=7,
        factory_correspondence=factories,
        temporal_lookup_defaults=False,
        reference_files={
            str(Path(m.__file__).resolve()): hashlib.sha256(
                Path(m.__file__).read_bytes()
            ).hexdigest()
            for m in (native, independent)
        },
        callback_abi=callback_abi(),
        compiled_or_executed=False,
        scope="normalized temporal projection and original factory/time-law slice; "
        "not complete Parameters/YAML/native setup or a physiological comparison",
    )


def require_abi():
    value = callback_abi()
    require(
        value["compatible"],
        "Temporal callback result ABI prerequisite: actual callback reads "
        + repr(value["callback_access"])
        + "; time-law fields are "
        + repr(value["result_fields"]),
    )
    return value


def _original_parameters(root):
    """Compile original selected statements only in the released source probe."""
    source_plan(root)
    selected = _selected_statements(
        ast.parse((Path(root) / "betse/science/parameters.py").read_bytes())
    )
    wrapper = ast.parse("def original_selected_parameters(self):\n    pass\n")
    wrapper.body[0].body = copy.deepcopy(selected)
    namespace = {"__name__": __name__ + ".original_parameters"}
    exec(
        compile(
            ast.fix_missing_locations(wrapper), "<original selected Parameters stores>", "exec"
        ),
        namespace,
    )
    return namespace["original_selected_parameters"]


def stamp(value):
    require(
        type(value) in (np.float64, np.ndarray),
        "Temporal value needs actual binary64 scalar/0D output",
    )
    require(
        value.shape == () and value.dtype == np.dtype("float64"),
        "Temporal value axes/dtype changed",
    )
    number = float(value)
    require(math.isfinite(number), "Nonfinite temporal source result")
    return dict(
        value=number,
        hex=number.hex(),
        shape=[],
        dtype=value.dtype.str,
        category="array" if type(value) is np.ndarray else "numpy_scalar",
    )


def compare_factor(original, candidate, oracle):
    """No new tolerance: exact source equality plus the existing Decimal budget."""
    for value in (original, candidate):
        require(
            value["shape"] == []
            and value["dtype"] == "<f8"
            and value["category"] in ("array", "numpy_scalar")
            and type(value["value"]) is float
            and math.isfinite(value["value"])
            and value["hex"] == value["value"].hex(),
            "Changed temporal value record",
        )
    require(original["hex"] == candidate["hex"], "Candidate differs from original source factor")
    require(
        type(oracle["factor_budget"]) is float
        and math.isfinite(oracle["factor_budget"])
        and oracle["factor_budget"] > 0
        and math.isfinite(oracle["factor"]),
        "Missing existing independent reference budget",
    )
    require(
        abs(original["value"] - oracle["factor"]) <= oracle["factor_budget"],
        "Original/candidate factor exceeds existing independent reference budget",
    )
    return dict(exact_original_match=True, within_existing_reference_budget=True)


def paired_compare(
    directory,
    source_binding,
    source_entry,
    *,
    expected_binding_identity,
    expected_entry_identity,
    labels,
    root=NATIVE_ROOT,
):
    """Actual gated slice comparison on a verified retained SIM result.

    Original factories execute on an isolated reference p, not a fake native
    phase. pc/cells are unused by these exact pinned bodies. Every construction,
    factory/evaluation and nested candidate verification is recorded as work.
    """
    released()
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    attempts = []
    take = preparation._retainer(directory, attempts)
    p = None
    try:

        def parent():
            require(
                type(source_binding) is lifecycle.Binding
                and type(source_entry) is lifecycle.SimPhase,
                "Missing actual retained SIM parent for original-source comparison",
            )
            require(
                type(expected_binding_identity) is str
                and bool(expected_binding_identity)
                and type(expected_entry_identity) is str
                and bool(expected_entry_identity)
                and source_binding.identity == expected_binding_identity
                and source_entry.identity == expected_entry_identity
                and source_entry.binding_identity == source_binding.identity,
                "Foreign actual SIM parent/source identity",
            )
            require(
                type(labels) in (tuple, list)
                and len(labels) == 3
                and all(type(t) is float and math.isfinite(t) for t in labels),
                "Three original finite SIM labels required",
            )
            require(
                tuple(labels) == tuple(float(t) for t in source_entry.active.clock.source_times_s),
                "Original-source comparison clock was rebased",
            )

        take(
            "required-retained-SIM",
            parent,
            source_binding=source_binding,
            source_entry=source_entry,
        )
        take("required-callback-result-ABI", require_abi)
        take("actual-SIM-ownership", lambda: lifecycle.verify(source_binding, source_entry))
        published = take(
            "actual-SIM-publication", lambda: bridge.resolve(source_binding, source_entry)
        )
        fields = published.event_finalized
        saved = take(
            "actual-selected-store-receipt",
            lambda: temporal.validate_receipt(
                source_binding, fields, completed=source_entry.source_init
            ),
        )
        require(saved is not None, "Original-source route requires selected configuration mode")
        plan = take("pinned-original-source-plan", lambda: source_plan(root))
        configured_root = Path(os.environ.get("CELLS_BETSE_SOURCE", str(NATIVE_ROOT))).resolve(
            strict=True
        )
        require(
            configured_root == Path(root).resolve(strict=True),
            "Original helper root differs from source plan",
        )
        conf = lifecycle.ions.data(saved["configuration"]["projection"])
        duration = source_binding.inputs["sim_phase"]["time_profile"]["sim_total_s"]
        p = SimpleNamespace(_conf=conf, _run_sim=fields["legacy_run_sim"], sim_time_total=duration)
        populate = None

        def capture_parameters():
            nonlocal populate
            populate = _original_parameters(root)
            return dict(captured_original_selected_statements=7, executed=False)

        take("capture-original-selected-store-source", capture_parameters)

        # Keep callables ephemeral: the retainer receives data only.
        def stores():
            populate(p)
            return dict(
                periodic=copy.deepcopy(p.periodic_properties),
                f_sweep=copy.deepcopy(p.f_scan_properties),
            )

        initial = take(
            "actual-original-selected-store-assignments", stores, original_parameter_fields=vars(p)
        )
        require(
            temporal.same(initial, saved["initial"]),
            "Original selected stores differ from actual issued stores",
        )
        functions = None

        def capture_factories():
            nonlocal functions
            functions = native.capture()
            expected = {"np": np}
            tree = ast.parse((Path(root) / "betse/science/math/modulate.py").read_bytes())
            nodes = [
                copy.deepcopy(n)
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name in ("periodic", "f_sweep")
            ]
            exec(
                compile(
                    ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                    "<pinned BETSE time modulators>",
                    "exec",
                ),
                expected,
            )
            require(
                functions.get("np") is np
                and all(
                    type(functions.get(name)) is FunctionType
                    and functions[name].__globals__ is functions
                    and functions[name].__code__ == expected[name].__code__
                    and functions[name].__defaults__ is None
                    and functions[name].__closure__ is None
                    for name in ("periodic", "f_sweep")
                ),
                "Changed cached original modulation functions",
            )
            return dict(original_modulation_capture_requests=1, AST_code_checks=2, factory_calls=0)

        take("capture-original-modulation-functions", capture_factories)
        family = saved["configuration"]["family"]
        result = []
        for key, suffix in sweep.MEMBRANE_KEYS.items():
            row = published.owner["scheduled_options"][key]
            if row == 0 or row[5] != family:
                continue
            original_callback = candidate_callback = None
            before = copy.deepcopy(
                p.periodic_properties if family == "periodic" else p.f_scan_properties
            )
            targets = list(published.owner["handler_fields"]["targets_" + suffix])

            def factory(targets=targets, before=before):
                nonlocal original_callback
                scalar, original_callback = functions[family](targets, None, p)
                require(
                    type(scalar) is int and scalar == 1 and type(original_callback) is FunctionType,
                    "Original factory scalar/callback changed",
                )
                require(
                    p._conf is conf, "Original factories replaced issued reference configuration"
                )
                return dict(
                    scalar=scalar,
                    before=before,
                    after=copy.deepcopy(
                        p.periodic_properties if family == "periodic" else p.f_scan_properties
                    ),
                    closure_p_retained=any(
                        cell.cell_contents is p for cell in original_callback.__closure__
                    ),
                )

            observed = take(
                "original-factory-" + suffix, factory, original_parameter_fields=vars(p)
            )
            actual = fields[
                ("periodic" if family == "periodic" else "sweep") + "_callback_authority"
            ][suffix]
            require(
                temporal.same(observed["before"], actual["before"])
                and temporal.same(observed["after"], actual["after"])
                and list(actual["targets"]) == targets
                and observed["closure_p_retained"],
                "Original factory mutation/target/parameter association differs",
            )
            dynamic = lifecycle.ions.data(published.owner["callbacks"][suffix]["dynamic"])

            def recreate(dynamic=dynamic):
                nonlocal candidate_callback
                candidate_callback = literal.prepared_callback(dynamic)
                return dict(kind=dynamic["kind"], recreated=True, callable_instance_persisted=False)

            take("actual-candidate-recreation-" + suffix, recreate, dynamic=dynamic)
            program = (
                dict(
                    kind="periodic",
                    frequency_Hz=observed["after"]["frequency"],
                    phase_rad=observed["after"]["phase"],
                    automatic_slope=False,
                    slope_Hz_s=0.0,
                    requested_stop_Hz=None,
                    original_duration_s=None,
                )
                if family == "periodic"
                else dict(
                    kind="sweep",
                    frequency_Hz=observed["after"]["f start"],
                    phase_rad=0.0,
                    automatic_slope=True,
                    slope_Hz_s=observed["after"]["f slope"],
                    requested_stop_Hz=initial["f_sweep"]["f stop"],
                    original_duration_s=duration,
                )
            )
            if family == "f_sweep":
                slope = take(
                    "independent-source-slope-" + suffix,
                    lambda program=program: independent.resolved_slope(program),
                )
                require(
                    slope == observed["after"]["f slope"],
                    "Original automatic slope differs from independent source rounding",
                )
            samples = []
            for index, time in enumerate(labels):
                original = take(
                    f"original-value-{suffix}-{index}",
                    lambda callback=original_callback, time=time: stamp(callback(np.float64(time))),
                )
                candidate = take(
                    f"candidate-value-{suffix}-{index}",
                    lambda callback=candidate_callback, time=time: stamp(
                        callback(np.float64(time))
                    ),
                )
                oracle = take(
                    f"independent-value-{suffix}-{index}",
                    lambda program=program, time=time: independent.evaluate(program, time),
                )
                checked = compare_factor(original, candidate, oracle)
                samples.append(
                    dict(
                        label=time,
                        original=original,
                        candidate=candidate,
                        oracle=oracle,
                        comparison=checked,
                    )
                )
            result.append(
                dict(key=key, suffix=suffix, targets=targets, factory=observed, samples=samples)
            )
        require(
            temporal.same(
                dict(periodic=p.periodic_properties, f_sweep=p.f_scan_properties), saved["after"]
            ),
            "Original final temporal stores differ from retained actual result",
        )
        result = dict(
            source_plan=plan,
            source_binding=source_binding.identity,
            source_entry=source_entry.identity,
            selected_store_identity=saved["identity"],
            family=family,
            labels=list(labels),
            rows=result,
            work=dict(
                original_store_constructions=1,
                ordered_store_statements=7,
                original_factory_calls=len(result),
                original_callback_evaluations=3 * len(result),
                candidate_recreations=len(result),
                candidate_callback_evaluations=3 * len(result),
                independent_evaluations=3 * len(result),
            ),
            independent_biological_cases=0,
            complete_native_Parameters_or_physiology_claim=False,
        )
        preparation.checkpoint.codec._write_json(directory / "result.json", result)
        return result
    except BaseException as error:
        from validation.betse.betse_normal_ecm_init_phase_capture import record_failure

        record_failure(
            error,
            stage="paired-original-temporal-source",
            readers={
                "source_binding": lambda: source_binding,
                "source_entry": lambda: source_entry,
                "original_parameter_fields": lambda: None if p is None else vars(p),
                "attempts": lambda: attempts,
            },
            retain=lambda v: preparation.archives.write_archive(
                directory / "failure", lifecycle.ions.data(v)
            ),
        )
        raise
    finally:
        primary = sys.exception()
        try:
            preparation.checkpoint.codec._write_json(
                directory / "attempts.json", dict(attempts=attempts, independent_cases=0)
            )
        except BaseException as secondary:
            if primary is None:
                raise
            primary.add_note("Temporal reference attempt retention also failed: " + repr(secondary))
