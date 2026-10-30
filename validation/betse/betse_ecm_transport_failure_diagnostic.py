"""Recover full reference evidence for a failed ECM comparison, without acceptance.

Run in a fresh worker against the original frozen reference/checker sources.
All complete reference buffers are saved before comparison. This diagnostic
never changes a budget or counts the failed manufactured input as a new case.
"""

import argparse
import hashlib
import importlib.abc
import json
import os
import sys
from pathlib import Path


class DenyProduction(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"cells", "betse", "jax", "jaxlib"}:
            raise ImportError("Production/native import denied: " + fullname)


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def diagnose(directory):
    sys.meta_path.insert(0, DenyProduction())
    import numpy as np

    from validation.betse import betse_ecm_transport_checks as checks
    from validation.betse import betse_ecm_transport_reference as reference

    raw = directory / "evidence/ecm-transport-raw"
    case = json.loads((directory / "inputs.json").read_text())["case"]
    record = json.loads((raw / (case + ".json")).read_text())
    inputs = record["inputs"]
    old = json.loads((directory / "original-case.json").read_text())
    assert inputs == old["inputs"], "The failed scientific input must remain unchanged"
    answers = []
    for factor in (1, 2):
        answer = reference.evaluate(inputs, refinement=factor)
        columns = {
            f"step_{i}." + key: value
            for i, row in enumerate(answer["history"])
            for key, value in checks.columns(row).items()
        }
        # Stored numeric outputs are binary64 projections of the 100/160-digit
        # calculations, not claims that binary64 stores that many digits.
        write(directory / f"fresh-reference-r{factor}.json", answer)
        with (directory / f"fresh-reference-r{factor}.npz").open("xb") as stream:
            np.savez_compressed(stream, **columns)
        answers.append(columns)
    assert answers[0].keys() == answers[1].keys()
    failures, comparisons, resolutions = [], [], []
    with (
        np.load(raw / (case + ".npz"), allow_pickle=False) as actual,
        np.load(raw / (case + "-references.npz"), allow_pickle=False) as prior,
        np.load(directory / "original-case.npz", allow_pickle=False) as original,
    ):
        assert actual.files == original.files
        for key in original.files:
            np.testing.assert_array_equal(actual[key], original[key], err_msg=key)
            assert actual[key].dtype == original[key].dtype
        for key, raw_wanted in answers[0].items():
            name = key.replace(".", "__")
            value = actual["actual__" + name]
            wanted, tight = np.asarray(raw_wanted), np.asarray(answers[1][key])
            assert value.shape == wanted.shape == tight.shape
            np.testing.assert_array_equal(prior["reference__" + name], wanted, err_msg=key)
            np.testing.assert_array_equal(prior["refined__" + name], tight, err_msg=key)
            assert all(np.isfinite(v).all() for v in (value, wanted, tight))
            budget = checks.budget(key, wanted)
            fractions = abs(value - wanted) / budget
            resolution = abs(wanted - tight) / checks.budget(key, tight)
            flat = int(np.argmax(fractions)) if fractions.size else 0
            index = np.unravel_index(flat, fractions.shape) if fractions.size else ()
            row = dict(
                field=key,
                shape=list(value.shape),
                max_error_fraction=float(np.max(fractions, initial=0)),
                max_absolute_error=float(np.max(abs(value - wanted), initial=0)),
                reference_resolution_fraction=float(np.max(resolution, initial=0)),
                worst_index=[int(i) for i in index],
            )
            if fractions.size:
                row.update(
                    actual=float(value[index]),
                    reference=float(wanted[index]),
                    tighter_reference=float(tight[index]),
                    budget_at_worst=float(budget[index]),
                )
            comparisons.append(row)
            resolutions.append(row["reference_resolution_fraction"])
            if row["max_error_fraction"] > 1:
                failures.append(row)
    assert max(resolutions, default=0) <= 0.1, "Original reference self-resolution limit"
    assert failures, "Do not silently reinterpret a changed outcome as the original failure"
    write(
        directory / "comparison.json",
        dict(
            status="diagnostic_completed_original_accuracy_failure_preserved",
            original_qualification_pass=False,
            case=case,
            production_imports_denied=True,
            original_actual_and_native_buffers_exact=True,
            fresh_and_inprocess_references_exact=True,
            full_reference_buffers_saved_before_comparison=True,
            reference_precisions=[100, 160],
            stored_reference_dtype="binary64 projections",
            comparisons=comparisons,
            failed_fields=failures,
            reference_resolution_fraction=max(resolutions, default=0),
            additional_biological_cases=0,
            tolerances_unchanged=True,
            automatic_followup=False,
        ),
    )
    assert not any(
        name.split(".")[0] in {"cells", "betse", "jax", "jaxlib"} for name in sys.modules
    )
    files = {}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            path = Path(name).resolve()
            with path.open("rb") as stream:
                files[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    path = Path(sys.executable).resolve()
    with path.open("rb") as stream:
        files[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    write(
        directory / "runtime-independent.json",
        dict(affinity=sorted(os.sched_getaffinity(0)), files=files, production_imports_denied=True),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    diagnose(parser.parse_args().directory)
