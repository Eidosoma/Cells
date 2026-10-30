"""Fresh production-denied charged/blocker history and failed-tape replay."""

# ruff: noqa: E402

import builtins
import hashlib
import importlib.abc
import importlib.metadata
import json
import os
import platform
import struct
import sys
from decimal import Decimal
from pathlib import Path

BLOCKED = {"cells", "jax", "jaxlib"}
original_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("Production import denied: " + name)
    return original_import(name, *args, **kwargs)


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Production import denied: " + fullname)


builtins.__import__ = guarded
sys.meta_path.insert(0, Guard())

import numpy as np

from validation.tissue import physiology_protein_block_calendar_reference as reference
from validation.tissue import physiology_protein_packet_provider_reference as packets


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda value: np.asarray(value).tolist(),
    )


def fraction(value, target, budget):
    value, target, budget = np.asarray(value), np.asarray(target), np.asarray(budget)
    delta = abs(value - target)
    assert np.all((budget > 0) | (delta == 0))
    return float(
        np.max(np.divide(delta, budget, out=np.zeros_like(delta), where=budget > 0), initial=0)
    )


def raw_archive(path):
    """Independent complete numeric archive reader; no executable type codec."""
    manifest = json.loads((path / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((path / name).read_bytes()).hexdigest() == expected

    def read(node, archive):
        if not isinstance(node, dict):
            return node
        if "array" in node:
            values = archive[node["array"]]
            assert values.dtype.str == node["dtype"] and list(values.shape) == node["shape"]
            return np.array(values)
        if "mapping" in node:
            return {key: read(value, archive) for key, value in node["mapping"]}
        if "tuple" in node:
            return tuple(read(value, archive) for value in node["tuple"])
        if "float64_bits" in node:
            return struct.unpack("<d", bytes.fromhex(node["float64_bits"]))[0]
        raise ValueError("Unknown independent raw archive node")

    with np.load(path / "arrays.npz", allow_pickle=False) as archive:
        return read(json.loads((path / "data.json").read_text()), archive)


def compare(record, answer):
    maximum = 0.0
    oracle = reference.charged.loop.ionic.local.rates.permeability.ORACLES[
        record["inputs"]["raw"]["model"]["id"]
    ]
    for actual, target, blocked in zip(
        record["actual"], answer["endpoints"], answer["block_calls"], strict=True
    ):
        state = oracle.flatten(target["context"], actual["full_fields"])
        assert np.array_equal(state, actual["state"])
        budget = oracle.flatten(
            target["context"],
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in target["context"]["shapes"].items()
            },
        ) + 3e-10 * abs(target["state"])
        assert np.array_equal(budget, actual["state_budget"])
        maximum = max(maximum, fraction(state, target["state"], budget))
        phi = np.asarray(target["potential_V"])
        maximum = max(maximum, fraction(actual["potential_V"], phi, 3e-13 + 3e-10 * abs(phi)))
        for key, value in actual["protein"].items():
            wanted = np.asarray(target["component"]["protein"][key])
            maximum = max(maximum, fraction(value, wanted, 2e-14 + 5e-13 * abs(wanted)))
        for key, value in actual["work"].items():
            wanted = target["work"][key]
            maximum = max(maximum, abs(value - wanted) / (3e-14 + 3e-10 * abs(wanted)))
        assert canonical(actual["packet"]) == canonical(target["packet"])
        assert canonical(actual["successor_stream"]) == canonical(target["successor_stream"])
        for key in ("external_work_pJ", "dissipated_free_energy_pJ"):
            assert actual["ledger"][key] == target["ledger"][key]
        wanted = float(Decimal(target["ledger"]["clamp_work_pJ"]))
        maximum = max(
            maximum,
            abs(float(Decimal(actual["ledger"]["clamp_work_pJ"])) - wanted)
            / (3e-14 + 3e-10 * abs(wanted)),
        )
        wanted = np.asarray(
            [float(Decimal(value)) for value in target["ledger"]["electrode_charge_C"]]
        )
        actual_charge = np.asarray(
            [float(Decimal(value)) for value in actual["ledger"]["electrode_charge_C"]]
        )
        maximum = max(maximum, fraction(actual_charge, wanted, 3e-25 + 2e-12 * abs(wanted)))
        wanted = target["global_accounting"]["energy_residual_pJ"]
        maximum = max(
            maximum,
            abs(actual["cumulative"]["energy_residual_pJ"] - wanted)
            / (3e-14 + 3e-10 * abs(wanted)),
        )
        assert actual["cumulative"]["valid"] and all(actual["cumulative"]["checks"].values())
        assert target["global_accounting"]["energy_valid"]
        for key, value in actual["block_state"].items():
            wanted = np.asarray(blocked["block_state"][key])
            maximum = max(maximum, fraction(value, wanted, 3e-15 + 3e-14 * abs(wanted)))
        for actual_control, wanted_control in zip(
            actual["interval_controls"], blocked["interval_controls"], strict=True
        ):
            for side in ("base_left", "base_right", "actual_left", "actual_right"):
                for key, value in actual_control[side].items():
                    wanted = np.asarray(wanted_control[side][key])
                    maximum = max(maximum, fraction(value, wanted, 3e-15 + 3e-14 * abs(wanted)))
    assert maximum <= 1, maximum
    return maximum


def main():
    case, expected_count = sys.argv[1], int(sys.argv[2])
    folder = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "tissue-step"
    phase = os.environ["CELLS_PROTEIN_BLOCK_PHASE"]
    affinity = sorted(os.sched_getaffinity(0))
    declared_cpu = int(os.environ.get("CELLS_PROTEIN_BLOCK_CPU", "7"))
    assert affinity == [declared_cpu]
    (folder / ("protein-block-calendar-runtime-" + phase + ".json")).write_text(
        json.dumps(
            dict(
                pid=os.getpid(),
                measured_child_cpu_affinity=affinity,
                python_version=platform.python_version(),
                python_full_version=sys.version,
                numpy_version=np.__version__,
                installed_jax_version=importlib.metadata.version("jax"),
                installed_jaxlib_version=importlib.metadata.version("jaxlib"),
                production_runtime_loaded=False,
            ),
            indent=2,
        )
    )
    rows = []
    if case != "failed":
        record = json.loads(
            (folder / ("protein-block-calendar-reference-" + case + ".json")).read_text()
        )
        assert record["completed"]
        for refinement, name in ((1, "expected_standard"), (2, "expected_tight")):
            answer = reference.integrate(**record["inputs"], refinement=refinement)
            assert canonical(reference.report(answer)) == canonical(record[name])
            maximum = compare(record, answer) if refinement == 2 else 0.0
            rows.append(
                dict(
                    case=case,
                    refinement=refinement,
                    exact_reference_replay=True,
                    complete_ionic_blocker_and_tape_history=True,
                    maximum_error_fraction=maximum,
                )
            )
    else:
        for path in sorted(folder.glob("protein-block-calendar-failed-provider-*.json")):
            record = json.loads(path.read_text())
            answer = packets.provide(**record["inputs"])
            assert canonical(answer) == canonical(record["expected"])
            assert canonical(answer["packet"]) == canonical(record["actual_packet"])
            assert canonical(answer["successor_stream"]) == canonical(record["actual_successor"])
            archive_path = Path(record["actual_failure_archive"])
            assert (
                hashlib.sha256((archive_path / "manifest.json").read_bytes()).hexdigest()
                == record["actual_failure_manifest_sha256"]
            )
            raw = raw_archive(archive_path)
            failure = raw["failure"]["fields"]
            assert len(failure["intervals"]) >= 2
            trial = failure["trial"]["fields"]["protein"]["fields"]
            maximum = 0.0
            for key, value in trial.items():
                wanted = np.asarray(answer["proposal"]["trial"]["protein"][key])
                maximum = max(
                    maximum,
                    fraction(value, wanted, 3e-14 * abs(wanted) + 4 * abs(np.spacing(wanted))),
                )
            assert maximum <= 1
            rows.append(
                dict(
                    case=path.name,
                    exact_reference_replay=True,
                    actual_full_failed_trial_checked=True,
                    maximum_error_fraction=maximum,
                )
            )
    assert len(rows) == expected_count, (case, len(rows), expected_count)
    assert not [name for name in sys.modules if name.split(".")[0] in BLOCKED]
    result = dict(
        case=case,
        actual_reference_forms=len(rows),
        production_imports_denied=True,
        production_imports_loaded=[],
        maximum_error_fraction=max(row["maximum_error_fraction"] for row in rows),
        cases=rows,
    )
    (folder.parent / ("independence-" + case + ".json")).write_text(
        json.dumps(result, indent=2, allow_nan=False)
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("case", "actual_reference_forms", "maximum_error_fraction")
            }
        )
    )


if __name__ == "__main__":
    main()
