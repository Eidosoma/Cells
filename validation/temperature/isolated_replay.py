"""Fresh import-denied replay of finite saved columns, never native bodies."""

import json
import os
from pathlib import Path

from validation.temperature import runtime_capture  # Installs import guard first.


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main():
    from validation.temperature import checks

    root = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    protocol = json.loads(Path(__file__).with_name("protocol.json").read_text())
    rows, diagnostics, scalar_points, batches = [], [], 0, 0
    for path in sorted((root / "native-temperature").glob("*.json")):
        record = json.loads(path.read_text())
        kind = record["kind"]
        if kind == "channel":
            proofs = []
            for row in record["rows"]:
                proof = checks.channel(row["actual"], protocol)
                assert canonical(proof) == canonical(row["reference"]), path.name
                proofs.append(proof["maximum_error_fraction"])
                scalar_points += proof["independent_scalar_points"]
                batches += 1
            assert len(proofs) == 20
            maximum = max(proofs)
        elif kind in ("transport", "pumps", "legacy", "junction", "reactions"):
            proof = getattr(checks, kind)(record["actual"], protocol)
            assert canonical(proof) == canonical(record["reference"]), path.name
            maximum = proof["maximum_error_fraction"]
            batches += 1
            if kind == "junction":
                proof = checks.junction(record["changed_configured"], protocol)
                assert canonical(proof) == canonical(record["changed_configured_reference"])
                maximum = max(maximum, proof["maximum_error_fraction"])
                batches += 1
        else:
            diagnostics.append(dict(case=path.name, kind=kind, finite_equivalence_credit=False))
            continue
        assert maximum <= 1, (path.name, maximum)
        rows.append(dict(case=path.name, kind=kind, maximum_error_fraction=maximum))
    assert (len(rows), len(diagnostics), scalar_points, batches) == (115, 7, 3300, 1170)
    runtime = runtime_capture.capture(0)
    answer = dict(
        kind="cells.native_active_temperature_independent_replay@1",
        records=rows,
        case_count=len(rows),
        reference_batches=batches,
        scalar_channel_points=scalar_points,
        diagnostics=diagnostics,
        runtime=runtime,
        native_execution=False,
        active_guard_relaxation=False,
        thermal_transition=False,
    )
    (root / "independence.json").write_text(json.dumps(answer, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(reference_cases=len(rows), reference_batches=batches, independent=True)))


if __name__ == "__main__":
    main()
