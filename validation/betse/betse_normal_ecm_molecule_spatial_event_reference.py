"""Held spatial-factory to membrane-assignment source probe.

The supplied geometry/properties/stores are a declared source probe, never a
native finalized owner, configuration parser, phase or INIT/SIM parent. The
numerical route compares original BETSE factories and event bodies to existing
Cells kernels/bodies, and reuses the independent spatial Decimal oracle. It
does not admit spatial callbacks into the molecule lifecycle or checkpoint.
"""

import ast
import copy
import hashlib
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ecm_event_join_source as literal
from cells.processes import betse_spatial_modulation as spatial
from validation.betse import betse_normal_current_native as archives
from validation.betse import betse_normal_ecm_event_join_native_events as event_native
from validation.betse import betse_normal_ecm_init_phase_capture as capture
from validation.betse import betse_normal_ecm_molecule_failure_checks as failures
from validation.perturbations import spatial_modulation_native as native
from validation.perturbations import spatial_modulation_reference as independent

NATIVE_ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")
RELEASES = ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED")
PINS = {
    "betse/science/math/modulate.py": (
        "c29f4ae27930f00780736e075183e61f44263dd0caa9d7c2f9a30971f616bff7"
    ),
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
}
IONS = ("Na", "K", "Cl", "Ca")
SUFFIXES = ("Namem", "Kmem", "Clmem", "Camem")
STORES = ("Dm_base", "Dm_scheduled", "Dm_cells", "P_base", "P_mod", "P_cells")
SCOPE = "declared spatial factory/event source probe; no native phase or parent admission"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def released():
    require(all(os.environ.get(k) == "1" for k in RELEASES), "Spatial source probe remains held")


def _function(tree, name):
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(nodes) == 1, "Require exactly one original source function: " + name)
    return nodes[0]


def _body(node):
    return ast.dump(event_native.Clean().visit(copy.deepcopy(node)), include_attributes=False)


def source_plan(root=NATIVE_ROOT):
    """Authenticate complete original files and copied event ASTs; no compilation."""
    root = Path(root).resolve(strict=True)
    trees = {}
    for name, expected in PINS.items():
        path = root / name
        require(path.is_file() and not path.is_symlink(), "Regular original source required")
        data = path.read_bytes()
        require(
            hashlib.sha256(data).hexdigest() == expected, "Original source pin changed: " + name
        )
        trees[name] = ast.parse(data)
    original = next(
        n
        for n in trees["betse/science/tissue/tishandler.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    owned_tree = ast.parse(Path(literal.__file__).read_bytes())
    owned = next(
        n for n in owned_tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    matched = {}
    for name in ("_fire_events_tissue", "makeAllChanges"):
        require(
            _body(_function(original, name)) == _body(_function(owned, name)),
            "Event operational source differs: " + name,
        )
        matched[name] = True
    require(
        _body(_function(trees["betse/science/math/toolbox.py"], "pulse"))
        == _body(_function(owned_tree, "pulse")),
        "Pulse operational source differs",
    )
    factories = trees["betse/science/math/modulate.py"]
    return dict(
        scope=SCOPE,
        native_sources=dict(PINS),
        factory_AST_sha256={
            name: hashlib.sha256(_body(_function(factories, name)).encode()).hexdigest()
            for name in ("gradient_x", "gradient_y", "gradient_r")
        },
        original_event_AST_equal=matched,
        pulse_AST_equal=True,
        dependencies={
            str(Path(module.__file__).resolve()): hashlib.sha256(
                Path(module.__file__).read_bytes()
            ).hexdigest()
            for module in (literal, spatial, native, independent, event_native)
        },
        compiled_or_evaluated=False,
        INIT_SIM_admission=False,
    )


def declaration(programs, *, pulses, defaults, present, labels, stores, provenance):
    """Bound a small explicitly supplied probe; never invent omitted owner values."""
    require(
        type(programs) is dict and bool(programs) and set(programs) <= set(IONS),
        "Declare one or more supported membrane ions",
    )
    require(
        type(provenance) is str and bool(provenance.strip()), "Declare supplied probe provenance"
    )
    require(
        type(present) is tuple
        and present == tuple(k for k in IONS if k in present)
        and {"Na", "K"} <= set(present),
        "Declare ordered ion presence; native Na/K are required",
    )
    require(
        type(labels) is tuple
        and 1 <= len(labels) <= 8
        and all(type(t) is float and math.isfinite(t) for t in labels),
        "Require bounded original finite source labels without rebasing",
    )
    require(
        type(pulses) is dict
        and set(pulses) == set(programs)
        and type(defaults) is dict
        and set(defaults) == set(IONS),
        "Declare complete pulse and default permeability sources",
    )
    require(
        all(type(v) is float and math.isfinite(v) for v in defaults.values()),
        "Explicit finite source default permeabilities required",
    )
    first, records = None, {}
    geometry_keys = (
        "cell_ids",
        "membrane_ids",
        "cell_centres_m",
        "membrane_midpoints_m",
        "centre_m",
    )
    for ion in IONS:
        if ion not in programs:
            continue
        program = spatial.validate(programs[ion])
        require(
            program.target_domain == "membranes",
            "Membrane event probe requires the membrane source branch",
        )
        require(
            0 < len(program.cell_ids) <= 32
            and 0 < len(program.membrane_ids) <= 128
            and len(program.target_ids) <= 256,
            "Source probe geometry exceeds the declared bound",
        )
        saved = spatial.record(program)
        if first is not None:
            require(
                all(saved[k] == first[k] for k in geometry_keys), "Foreign common geometry/axes"
            )
        first = saved
        pulse = pulses[ion]
        require(
            type(pulse) is tuple
            and len(pulse) == 4
            and all(type(v) is float and math.isfinite(v) for v in pulse)
            and pulse[0] <= pulse[1]
            and pulse[2] > 0,
            "Declare original onset/release/ramp/multiplier without new defaults",
        )
        records[ion] = saved
    require(
        type(stores) is dict and set(stores) == set(STORES),
        "Complete supplied source stores required",
    )
    count = len(first["membrane_ids"])
    for name, value in stores.items():
        expected = (4, count) if name.startswith("Dm_") else (count,)
        require(
            type(value) is np.ndarray
            and value.dtype == np.dtype("float64")
            and value.shape == expected
            and np.isfinite(value).all(),
            "Full finite binary64 source store required: " + name,
        )
    return dict(
        scope=SCOPE,
        programs=records,
        pulses=pulses,
        defaults=defaults,
        present=present,
        labels=labels,
        stores=stores,
        provenance=provenance,
        property_authority=(
            "normalized explicit probe projection, not Parameters/YAML/finalized ownership"
        ),
        INIT_SIM_admission=False,
        independent_biological_cases=0,
    )


def _stamp(value):
    require(
        type(value) is np.ndarray and value.dtype == np.dtype("float64") and value.ndim == 1,
        "Preserve complete source factory arrays and binary64 axes",
    )
    return dict(dtype=value.dtype.str, shape=list(value.shape), values=value.copy())


def compare_factory(original, candidate, oracle):
    """Exact source values plus the existing independently fixed Decimal budget."""
    left, right = _stamp(original), _stamp(candidate)
    require(
        left["shape"] == right["shape"] and np.array_equal(original, candidate),
        "Original/candidate complete spatial factory values or axes differ",
    )
    wanted = np.asarray(oracle["factor"], dtype=np.float64)
    budget = oracle["factor_budget"]
    require(
        type(budget) is float
        and math.isfinite(budget)
        and budget > 0
        and wanted.shape == original.shape
        and np.isfinite(wanted).all()
        and np.isfinite(original).all(),
        "Finite independent spatial comparison required",
    )
    errors = np.abs(original - wanted)
    require(bool(np.all(errors <= budget)), "Existing independent spatial budget exceeded")
    return dict(
        exact_original_match=True,
        existing_factor_budget=budget,
        errors=errors,
        complete_shape=left["shape"],
        numerical_cases=0,
    )


def _snapshot(sim):
    return {key: getattr(sim, key).copy() for key in STORES}


def _error(error):
    return dict(
        type=type(error).__name__, message=str(error), chain=failures.exception_chain(error)
    )


def _take(directory, name, operation, *, attempts, work, readers):
    """Reuse complete raw evidence and preserve a source exception if capture fails."""
    row = dict(operation=name, work=work, status="attempted")
    attempts.append(row)
    source_error = None

    def observed():
        nonlocal source_error
        try:
            return operation()
        except Exception as error:
            source_error = error
            raise

    def retain(payload):
        try:
            archives.write_archive(directory / name, payload)
        except Exception as error:
            row["evidence_complete"] = False
            row.setdefault("recovery_errors", []).append(_error(error))
            raise
        row["evidence_complete"] = True

    try:
        result = failures.retained_call(observed, stage=name, readers=readers, retain=retain)
    except Exception as error:
        row.update(
            status="failed",
            failure=_error(error),
            failure_origin="source" if error is source_error else "evidence",
        )
        if error is source_error:
            error.spatial_probe_source_operation = name
            error.spatial_probe_capture_complete = row.get("evidence_complete", False)
        raise
    row["status"] = "returned"
    return result


def _original_events(root):
    """Compile only the pinned original pulse and two complete event methods."""
    source_plan(root)
    tree = ast.parse((Path(root) / "betse/science/tissue/tishandler.py").read_bytes())
    handler = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    cls = ast.ClassDef(
        name="OriginalSourceProbeEvents",
        bases=[],
        keywords=[],
        body=[
            event_native.Clean().visit(copy.deepcopy(_function(handler, name)))
            for name in ("_fire_events_tissue", "makeAllChanges")
        ],
        decorator_list=[],
    )
    pulse = event_native.Clean().visit(
        copy.deepcopy(
            _function(
                ast.parse((Path(root) / "betse/science/math/toolbox.py").read_bytes()), "pulse"
            )
        )
    )
    namespace = dict(np=np)
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[pulse, cls], type_ignores=[])),
            "<pinned original spatial membrane-event source probe>",
            "exec",
        ),
        namespace,
    )
    namespace["tb"] = SimpleNamespace(pulse=namespace["pulse"])
    return namespace["OriginalSourceProbeEvents"]


def _factory(original, program, cells, p, locals_after):
    """Observe only exact factory frames; exception unwinds never replace the cause."""
    pc = np.asarray([program.membrane_ids.index(k) for k in program.target_ids], dtype=np.int64)
    if not original:
        values = spatial.evaluate(program, xp=np)
        locals_after.update(
            complete_factor=values.factor,
            finite=values.finite,
            normalization_m=values.normalization_m,
        )
        return values.factor, literal.prepared_callback(dict(kind="constant"))
    factory = native.capture()[program.kind]
    previous = sys.getprofile()

    def observe(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is factory.__code__ and event == "return":
            # Exclude live callables/p/cells; their supplied inputs and exact source
            # are recorded separately. Arrays retain dtype, shape and all values.
            try:
                for key, value in frame.f_locals.items():
                    if type(value) in (np.ndarray, np.float64, int, float, str, type(None)):
                        locals_after[key] = value.copy() if type(value) is np.ndarray else value
                locals_after["return_or_unwind_type"] = type(arg).__name__
            except Exception as error:
                locals_after.setdefault("capture_errors", []).append(_error(error))

    sys.setprofile(observe)
    try:
        return factory(pc, cells, p)
    finally:
        sys.setprofile(previous)


def _leg(directory, supplied, programs, *, original, attempts, original_events):
    """Execute one isolated probe; retain a failed prefix without calling it success."""
    directory.mkdir(exist_ok=False)
    saved = next(iter(supplied["programs"].values()))
    cells = SimpleNamespace(
        cell_i=np.arange(len(saved["cell_ids"])),
        mem_i=np.arange(len(saved["membrane_ids"])),
        cell_centres=np.asarray(saved["cell_centres_m"], dtype=np.float64),
        mem_mids_flat=np.asarray(saved["membrane_midpoints_m"], dtype=np.float64),
        centre=np.asarray(saved["centre_m"], dtype=np.float64),
    )
    p = SimpleNamespace(
        scheduled_options={key + "_mem": 0 for key in IONS} | dict(pressure=0, ecmJ=0),
        ions_dict={key: int(key in supplied["present"]) for key in IONS},
        is_ecm=True,
    )
    sim = SimpleNamespace(
        **{k: v.copy() for k, v in supplied["stores"].items()},
        **{"i" + ion: i for i, ion in enumerate(IONS)},
    )
    probe = SimpleNamespace(p=p, sim=sim, cells=cells)
    owner = object.__new__(original_events if original else literal.TissueHandler)
    owner.event_cut = owner._event_voltage = None
    owner.tissue_default = SimpleNamespace(
        **{"Dm_" + k: v for k, v in supplied["defaults"].items()}
    )
    returned, frames, callbacks, factory_locals = {}, [], [], {}
    stage = "factory"

    def take(name, operation, work):
        return _take(
            directory,
            name,
            operation,
            attempts=attempts,
            work=work,
            readers=dict(
                stores=lambda: _snapshot(sim),
                factory_locals=lambda: copy.deepcopy(factory_locals),
                callbacks=lambda: copy.deepcopy(callbacks),
            ),
        )

    try:
        for ion, suffix in zip(IONS, SUFFIXES, strict=True):
            if ion not in programs:
                continue
            program = programs[ion]
            properties = dict(
                exponent=program.exponent,
                slope=program.slope,
                **{"x-offset": program.x_offset, "z-offset": program.z_offset},
            )
            setattr(p, program.kind + "_properties", properties)
            factory_locals = {}
            holder = {}

            def construct(program=program, factory_locals=factory_locals, holder=holder):
                scalar, callback = _factory(original, program, cells, p, factory_locals)
                require(callable(callback), "Actual source callback return required")
                holder["callback"] = callback
                return _stamp(scalar)

            stage = "factory-" + ion
            returned[ion] = take(
                stage,
                construct,
                "original_factory"
                if original
                else "candidate_spatial_evaluation_and_callback_recreation",
            )
            targets = [program.membrane_ids.index(k) for k in program.target_ids]
            pulse = supplied["pulses"][ion]
            p.scheduled_options[ion + "_mem"] = list(pulse) + [
                list(program.target_ids),
                program.kind,
            ]
            for key, value in zip(
                ("t_on_", "t_off_", "t_change_", "mem_mult_"), pulse, strict=True
            ):
                setattr(owner, key + suffix, value)
            setattr(owner, "targets_" + suffix, targets)
            setattr(owner, "scalar_" + suffix, returned[ion]["values"])

            def counted(t, callback=holder["callback"], ion=ion):
                event = dict(ion=ion, time=t, status="attempted")
                callbacks.append(event)
                row = dict(
                    operation="callback-" + ion, work="source_dynamic_callback", status="attempted"
                )
                attempts.append(row)
                try:
                    value = callback(t)
                except Exception as error:
                    event.update(status="failed", failure=_error(error))
                    row.update(status="failed", failure=_error(error))
                    raise
                event.update(status="returned", value=value)
                row["status"] = "returned"
                return value

            setattr(owner, "dyna_" + suffix, counted)
        for i, t in enumerate(supplied["labels"]):
            for method in ("_fire_events_tissue", "makeAllChanges"):
                stage = f"label-{i}-" + method
                before = _snapshot(sim)

                def operation(t=t, method=method):
                    if method == "_fire_events_tissue":
                        return owner._fire_events_tissue(probe, t)
                    return owner.makeAllChanges(sim)

                take(
                    stage,
                    operation,
                    "original_event_method" if original else "candidate_event_method",
                )
                frames.append(
                    dict(label=i, time=t, method=method, before=before, after=_snapshot(sim))
                )
    except Exception as error:
        if getattr(error, "spatial_probe_source_operation", None) != stage or not getattr(
            error, "spatial_probe_capture_complete", False
        ):
            raise
        return dict(
            status="source_failed",
            stage=stage,
            failure=_error(error),
            factories=returned,
            frames=frames,
            callbacks=callbacks,
            stores=_snapshot(sim),
            factory_locals=factory_locals,
        )
    return dict(
        status="source_completed",
        factories=returned,
        frames=frames,
        callbacks=callbacks,
        stores=_snapshot(sim),
        factory_locals=factory_locals,
    )


def _exact(left, right):
    if type(left) is np.ndarray:
        require(
            type(right) is np.ndarray
            and left.dtype == right.dtype
            and left.shape == right.shape
            and np.array_equal(left, right),
            "Source array value/dtype/shape differs",
        )
    elif type(left) is dict:
        require(type(right) is dict and set(left) == set(right), "Source record fields differ")
        for key in left:
            _exact(left[key], right[key])
    elif type(left) in (tuple, list):
        require(type(left) is type(right) and len(left) == len(right), "Source sequence differs")
        for a, b in zip(left, right, strict=True):
            _exact(a, b)
    else:
        require(type(left) is type(right) and left == right, "Source scalar category/value differs")


def _trace(result, supplied):
    expected_frames = [
        (i, t, method)
        for i, t in enumerate(supplied["labels"])
        for method in ("_fire_events_tissue", "makeAllChanges")
    ]
    actual_frames = [(f["label"], f["time"], f["method"]) for f in result["frames"]]
    require(
        actual_frames == expected_frames[: len(actual_frames)],
        "Duplicated/omitted event stage or source clock",
    )
    expected_callbacks = [
        (ion, t)
        for t in supplied["labels"]
        for ion in IONS
        if ion in supplied["programs"] and ion in supplied["present"]
    ]
    actual_callbacks = [(f["ion"], f["time"]) for f in result["callbacks"]]
    require(
        actual_callbacks == expected_callbacks[: len(actual_callbacks)],
        "Duplicated/omitted callback or ion order",
    )
    if result["status"] == "source_completed":
        require(
            actual_frames == expected_frames and actual_callbacks == expected_callbacks,
            "Completed source trace is missing event/callback entries",
        )
    for row in result["callbacks"]:
        require(
            row["status"] == "returned" and type(row["value"]) is int and row["value"] == 1,
            "Spatial source constant dynamics changed",
        )


def compare_legs(original, candidate, supplied):
    """Compare all full stores, source order and retained refusal boundaries."""
    require(original["status"] == candidate["status"], "Source completion/refusal differs")
    require(
        original["status"] in ("source_completed", "source_failed"),
        "Unknown source completion status",
    )
    _trace(original, supplied)
    _trace(candidate, supplied)
    for key in ("factories", "frames", "callbacks", "stores"):
        _exact(original[key], candidate[key])
    if original["status"] == "source_failed":
        require(original["stage"] == candidate["stage"], "Source failure stage differs")
        for key in ("type", "message"):
            _exact(original["failure"][key], candidate["failure"][key])
        return dict(status="matching_source_refusal_diagnostic", successful_event_admission=False)
    return dict(status="source_probe_match", successful_event_admission=False)


def paired_probe(
    directory, programs, *, pulses, defaults, present, labels, stores, provenance, root=NATIVE_ROOT
):
    """Held original/candidate comparison, independent of any invented run parent."""
    released()  # Must precede directory creation, compilation and numerical work.
    supplied = declaration(
        programs,
        pulses=pulses,
        defaults=defaults,
        present=present,
        labels=labels,
        stores=stores,
        provenance=provenance,
    )
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    attempts, results = [], {}
    try:
        archives.write_archive(directory / "supplied-probe", supplied)
        results["source_plan"] = source_plan(root)
        require(
            Path(os.environ.get("CELLS_BETSE_SOURCE", str(NATIVE_ROOT))).resolve(strict=True)
            == Path(root).resolve(strict=True),
            "Original factory capture root differs",
        )
        original_events = _original_events(root)
        for name, original in (("original", True), ("candidate", False)):
            results[name] = _leg(
                directory / name,
                supplied,
                programs,
                original=original,
                attempts=attempts,
                original_events=original_events,
            )
            archives.write_archive(directory / (name + "-result"), results[name])
        results["factory_comparisons"] = {}
        for ion, returned in results["original"]["factories"].items():
            oracle = _take(
                directory,
                "independent-factory-" + ion,
                lambda ion=ion: independent.evaluate(supplied["programs"][ion]),
                attempts=attempts,
                work="independent_spatial_Decimal_evaluation",
                readers={},
            )
            results["factory_comparisons"][ion] = compare_factory(
                returned["values"], results["candidate"]["factories"][ion]["values"], oracle
            )
        results["comparison"] = compare_legs(results["original"], results["candidate"], supplied)
        results.update(
            scope=SCOPE,
            attempts=attempts,
            independent_biological_cases=0,
            INIT_SIM_admission=False,
            checkpoint_continuity_admission=False,
        )
        archives.write_archive(directory / "comparison-result", results)
        return results
    except Exception as error:
        capture.record_failure(
            error,
            stage="spatial-event-paired-probe",
            readers=dict(
                supplied=lambda: supplied, results=lambda: results, attempts=lambda: attempts
            ),
            retain=lambda payload: archives.write_archive(directory / "failure", payload),
        )
        raise
