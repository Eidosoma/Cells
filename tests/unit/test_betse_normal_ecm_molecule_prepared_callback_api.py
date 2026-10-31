"""Narrow released NumPy callback API check; no lifecycle/native qualification.

Only actual prepared_callback and the existing NumPy time-law helper may do
numeric work here. Each scalar helper/callback invocation is counted as work.
No original factory, independent reference, event firing or parent is created.
"""

import ast
import hashlib
import importlib.abc
import json
import os
import sys
from collections import Counter
from pathlib import Path
from types import CodeType

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_event_join_source as literal
from cells.processes import betse_time_modulation as laws
from validation.betse import betse_normal_ecm_molecule_periodic_checkpoint as periodic
from validation.betse import betse_normal_ecm_molecule_sweep_checkpoint as sweep

PARENT = Path(
    "/mnt/workspaces/Cells/molecule-temporal-paired-continuity-preparation-20261031-01/source-final-02"
)
SOURCE = "src/cells/processes/betse_normal_ecm_event_join_source.py"
TIMES = (0.0, 0.125, 0.5)


@pytest.fixture(autouse=True)
def api_only(monkeypatch, tmp_path):
    counts, forbidden = Counter(), []
    data = dict(scalar_times=[], callback_results=[], primary_failure=None)
    callbacks = {c for c in literal.prepared_callback.__code__.co_consts if type(c) is CodeType}
    allowed = {
        "periodic_program",
        "sweep_program",
        "evaluate",
        "periodic",
        "sweep",
        "validate",
        "record",
        "_float",
        "_provenance",
        "_digest",
        "_arrays",
        "__init__",
        "<genexpr>",
        "<listcomp>",
        "<dictcomp>",
    }
    for name in ("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED", "CELLS_ECM_MOLECULE_EVENTS_RELEASED"):
        monkeypatch.delenv(name, raising=False)

    class NoNative(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                forbidden.append(fullname)
                raise AssertionError("Native import forbidden in callback API check")

    finder = NoNative()
    sys.meta_path.insert(0, finder)
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event not in ("call", "c_call"):
            return
        module = (
            frame.f_globals.get("__name__", "")
            if event == "call"
            else getattr(arg, "__module__", "") or ""
        )
        name = frame.f_code.co_name if event == "call" else getattr(arg, "__name__", "?")
        if module == "random" or module.startswith("numpy.random"):
            forbidden.append(module + "." + name)
            raise AssertionError("RNG forbidden")
        if (
            module.startswith("validation.perturbations.time_modulation")
            or module.endswith("betse_normal_ecm_molecule_temporal_reference")
            and name in {"paired_compare", "_original_parameters"}
        ):
            forbidden.append(module + "." + name)
            raise AssertionError("Native/original/reference route forbidden")
        if event == "call" and module.startswith("cells."):
            if frame.f_code is literal.prepared_callback.__code__:
                counts["prepared_callback_requests"] += 1
            elif frame.f_code in callbacks:
                counts["actual_callback_scalar_entries"] += 1
            elif module == laws.__name__ and name in allowed:
                counts["time_law." + name] += 1
                if name in {"evaluate", "periodic", "sweep", "_arrays"}:
                    assert frame.f_locals["xp"] is np, "Only NumPy helper execution released"
                if name == "evaluate":
                    value = frame.f_locals["time_s"]
                    assert type(value) is np.float64 and float(value) in TIMES
                    data["scalar_times"].append(float(value))
            else:
                forbidden.append(module + "." + name)
                raise AssertionError(
                    "Actual model/factory/checkpoint outside API release: " + forbidden[-1]
                )

    sys.setprofile(profile)
    try:
        yield counts, data
        assert forbidden == []
    finally:
        sys.setprofile(previous)
        sys.meta_path.remove(finder)
        (tmp_path / "callback-api-work.json").write_text(
            json.dumps(
                dict(
                    kind="cells.narrow_NumPy_prepared_callback_API_work@1",
                    counts=dict(counts),
                    scalar_helper_evaluations=counts["time_law.evaluate"],
                    scalar_callback_entries=counts["actual_callback_scalar_entries"],
                    forbidden_entries=forbidden,
                    data=data,
                    cpu_affinity=sorted(os.sched_getaffinity(0)),
                    source_sha256=hashlib.sha256(Path(literal.__file__).read_bytes()).hexdigest(),
                    time_law_sha256=hashlib.sha256(Path(laws.__file__).read_bytes()).hexdigest(),
                    independent_biological_cases=0,
                    lifecycle_or_parent_admission=False,
                )
            )
        )


def declaration(kind):
    return (
        dict(
            kind="periodic",
            frequency=0.25,
            phase=0.125,
            provenance="Declared small NumPy API control",
        )
        if kind == "periodic"
        else dict(
            kind="sweep", start=0.25, slope=0.5, provenance="Declared small NumPy API control"
        )
    )


@pytest.mark.parametrize("kind", ["periodic", "sweep"])
def test_actual_scalar_callback_returns_existing_qualified_factor(kind, api_only):
    counts, data = api_only
    row = declaration(kind)
    try:
        callback = literal.prepared_callback(row)
        program = (
            laws.periodic_program(
                frequency_Hz=row["frequency"], phase_rad=row["phase"], provenance=row["provenance"]
            )
            if kind == "periodic"
            else laws.sweep_program(
                start_Hz=row["start"],
                slope_Hz_s=row["slope"],
                run_sim=True,
                provenance=row["provenance"],
            )
        )
        before = laws.record(program)
        for t in TIMES:
            actual = callback(np.float64(t))
            expected = laws.evaluate(program, np.float64(t), xp=np).factor
            assert type(actual) is type(expected) is np.float64
            assert (
                actual.dtype == expected.dtype == np.dtype("float64")
                and actual.shape == expected.shape == ()
            )
            assert bool(np.isfinite(actual)) and bool(np.array_equal(actual, expected))
            data["callback_results"].append(
                dict(
                    time=t,
                    value=float(actual),
                    hex=float(actual).hex(),
                    dtype=actual.dtype.str,
                    shape=list(actual.shape),
                )
            )
        assert laws.record(program) == before
        assert (
            counts["prepared_callback_requests"] == 1
            and counts["actual_callback_scalar_entries"] == 3
        )
        assert counts["time_law.evaluate"] == 6
        assert counts["time_law." + kind] == 6
        assert not hasattr(laws.Values, "value") and laws.Values._fields == (
            "factor",
            "phase_rad",
            "finite",
        )
    except BaseException as error:
        data["primary_failure"] = dict(type=type(error).__name__, message=str(error))
        raise


def test_only_two_callback_result_attributes_change_from_frozen_parent():
    before = ast.parse((PARENT / SOURCE).read_bytes())
    after = ast.parse(Path(literal.__file__).read_bytes())
    count = 0
    for node in ast.walk(before):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "value"
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "time_laws.evaluate"
        ):
            node.attr = "factor"
            count += 1
    assert count == 2 and ast.dump(before, include_attributes=False) == ast.dump(
        after, include_attributes=False
    )


@pytest.mark.parametrize("observer", [periodic, sweep], ids=["periodic", "sweep"])
def test_observer_binds_factor_callback_and_refuses_frozen_malformed_source(observer):
    current = observer.source_order(literal.__file__)
    assert current["sha256"] == hashlib.sha256(Path(literal.__file__).read_bytes()).hexdigest()
    assert current["sha256"] != hashlib.sha256((PARENT / SOURCE).read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="Changed qualified"):
        observer.source_order(PARENT / SOURCE)


@pytest.mark.parametrize("kind", ["periodic", "sweep"])
def test_missing_callback_parameter_refuses_without_numeric_evaluation(kind, api_only):
    counts, _ = api_only
    row = declaration(kind)
    del row["phase" if kind == "periodic" else "slope"]
    with pytest.raises(KeyError):
        literal.prepared_callback(row)
    assert counts["time_law.evaluate"] == 0 and counts["actual_callback_scalar_entries"] == 0
