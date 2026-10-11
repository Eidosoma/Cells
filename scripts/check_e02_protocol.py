"""Audit the SPEC-004 freeze and expand its case inventory; never integrate.

This is a deliberately frozen reference protocol, not a second production config
parser. Any input change needs a new named revision and independently reviewed
hash. --audit-workspace additionally checks the *current* 0.10.0/source review;
that option is historical after a later intentional production/source change.
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/reference/e02_switching_protocol_v1.json"
PROTOCOL_SHA256 = "7e828792a61695e57f78da5ebdb02318ab927b82470f39b63aca9772bf0bece8"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_json(path, expected):
    # Parse the very bytes that were hashed; do not reopen a mutable input.
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Frozen input changed: {path}")
    return json.loads(raw)


def load_protocol(path=PROTOCOL):
    return pinned_json(path, PROTOCOL_SHA256)


def _expand_cases(protocol):
    """Input is already hash-checked. Labels refer to future full-state packets."""
    experiment = protocol["experiment"]
    equations = protocol["equations"]
    result = []
    for direction in experiment["directions"]:
        for condition in experiment["conditions"]:
            donors = experiment["donor_ids"][: condition["donors"]]
            cells = [experiment["recipient_id"], *donors]
            labels = [direction["recipient"]] + [direction[condition["donor_state"]]] * len(donors)
            result.append(
                {
                    "id": f"{direction['id']}/{condition['id']}",
                    "role": condition["role"],
                    "model_contract": protocol["model_contract"],
                    "cell_ids": cells,
                    "prepared_labels": labels,
                    "target_label": direction["target"],
                    "edge_ids": experiment["edge_ids"][: len(donors)],
                    "edges": [[experiment["recipient_id"], donor] for donor in donors],
                    "ion_contact": [condition["ion_contact"]] * len(donors),
                    "mirna_contact": [condition["mirna_contact"]] * len(donors),
                    "membrane_diffusion": [
                        [value] * len(cells) for value in equations["membrane_diffusion_per_cell"]
                    ],
                    "ionic_diffusion": [
                        [value] * len(donors) for value in equations["ionic_diffusion_per_edge"]
                    ],
                    "mirna_diffusion": [equations["mirna_diffusion_per_edge"]] * len(donors),
                    "start_time": experiment["start_time"],
                    "end_time": experiment["end_time"],
                    "reference_coordinate_count": 13 * len(cells) + 4 * len(donors),
                    "prepared_packet_status": protocol["preparation"]["packet_status"],
                }
            )
    return result


def case_inventory(path=PROTOCOL):
    return _expand_cases(load_protocol(path))


def observation_times(path=PROTOCOL):
    protocol = load_protocol(path)
    observer = protocol["observer"]
    step = observer["regular_interval"]
    count = int(protocol["experiment"]["end_time"] / step)
    return sorted({i * step for i in range(count + 1)} | set(observer["irregular_times"]))


def verify(path=PROTOCOL, *, audit_workspace=False):
    protocol = load_protocol(path)
    equations = protocol["equations"]
    provenance = protocol["provenance"]
    panel = pinned_json(ROOT / equations["panel"], equations["panel_sha256"])
    fixture = pinned_json(ROOT / provenance["native_fixture"], provenance["native_fixture_sha256"])
    if not (protocol["source_revision"] == panel["source_revision"] == fixture["revision"]):
        raise ValueError("Source identity differs")
    inherited = {name: panel[name] for name in equations["inherit"]}
    cases = _expand_cases(protocol)
    times = observation_times(path)
    lo, hi = protocol["observer"]["terminal_window"]
    result = {
        "status": "pass",
        "scope": "protocol_freeze_and_inventory_only",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha(path),
        "source_revision": protocol["source_revision"],
        "equation_panel_sha256": equations["panel_sha256"],
        "native_fixture_sha256": provenance["native_fixture_sha256"],
        "inherited_equation_fields": list(inherited),
        "preparations": len(protocol["preparation"]["initial_regulation"]),
        "conditions": len(cases),
        "primary_conditions": sum(case["role"] == "primary" for case in cases),
        "cells_across_independent_conditions": sum(len(case["cell_ids"]) for case in cases),
        "edges_across_independent_conditions": sum(len(case["edges"]) for case in cases),
        "observations_per_condition": len(times),
        "terminal_window_observations": sum(lo <= time <= hi for time in times),
        "preparation_packets": "not_generated",
        "trajectory_qualification": "not_run",
        "production_graph_implementation": "not_implemented",
        "switching_outcomes": "not_measured",
        "case_inventory": cases,
    }
    if audit_workspace:
        baseline = pinned_json(
            ROOT / provenance["production_audit"], provenance["production_audit_sha256"]
        )
        current = {
            str(p.relative_to(ROOT / "src/cells")): sha(p)
            for p in sorted((ROOT / "src/cells").rglob("*.py"))
        }
        if current != baseline["source_hashes"]:
            raise ValueError("Production differs from accepted 0.10.0; no implicit rebaseline")
        for name, expected in fixture["source_hashes"].items():
            if sha(ROOT / "upstream/bitsey" / name) != expected:
                raise ValueError(f"Pinned native source changed: {name}")
        for name, expected in provenance["reviewed_documents"].items():
            if sha(ROOT / provenance["reviewed_exploration_root"] / name) != expected:
                raise ValueError(f"Reviewed document changed: {name}; review separately")
        result["workspace_audit"] = {
            "production_sources_unchanged": len(current),
            "production_audit_sha256": provenance["production_audit_sha256"],
            "native_source_hashes_checked": fixture["source_hashes"],
            "reviewed_document_hashes_checked": provenance["reviewed_documents"],
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--audit-workspace", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol, audit_workspace=args.audit_workspace), indent=2))


if __name__ == "__main__":
    main()
