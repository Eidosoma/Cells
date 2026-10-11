"""Build bounded composition examples and independently audit their saved payloads.

Run from Cells with its CPU development environment. Output must be a new path.
The matrix oracle is independent of Cells' model, local process, and coupler.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import GraphContactChange, load_spec, read_json  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run  # noqa: E402
from tests.reference_reaction_transport import reference  # noqa: E402

REFERENCE_TOLERANCE = 4e-8
ACCOUNTING_TOLERANCE = 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reference_errors(spec, times, history):
    count, edges = len(spec.model.cell_ids), len(spec.model.contacts)
    expected = reference(spec, times)
    actual = (
        history.amount[..., :count],
        history.transferred[..., :edges],
        history.converted[..., :count],
    )
    return {
        name: float(np.max(np.abs(a - b), initial=0.0))
        for name, a, b in zip(("amount", "transferred", "converted"), actual, expected, strict=True)
    }


def inspect_run(path):
    manifest = read_json(path / "manifest.json")
    require(manifest["status"] == "complete", f"Incomplete run: {path}")
    require(manifest["source_hashes"] == source_hashes(), f"Source changed: {path}")
    require(manifest["runtime"] == runtime_identity(), f"Runtime changed: {path}")
    for name, digest in manifest["files_sha256"].items():
        file = (path / name).resolve()
        require(file.is_relative_to(path.resolve()), "Artifact path escapes its run")
        require(hashlib.sha256(file.read_bytes()).hexdigest() == digest, f"Corrupt payload: {file}")
    spec = load_spec(path / "resolved_config.json")
    require(spec.fingerprint == manifest["definition_sha256"], "Definition mismatch")
    snapshot = load_snapshot(path / "checkpoint_final")
    with np.load(path / "trajectory.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    history = type(snapshot.checkpoint.state)(
        *(data[name] for name in snapshot.checkpoint.state._fields)
    )
    for field, final in zip(history, snapshot.checkpoint.state, strict=True):
        np.testing.assert_array_equal(field[-1], final)
    errors = reference_errors(spec, data["accepted_times"], history)
    require(max(errors.values()) < REFERENCE_TOLERANCE, f"Matrix-reference error: {path}")
    total = np.asarray(spec.model.initial_amounts).sum()
    balance = float(np.max(np.abs(history.amount.sum(axis=(-2, -1)) - total)))
    # Reconstruct local accounting directly from identities and signed ledgers.
    delta = history.amount - np.asarray(spec.model.initial_amounts)
    for e, contact in enumerate(spec.model.contacts):
        a, b = (spec.model.cell_ids.index(v) for v in (contact.from_cell_id, contact.to_cell_id))
        delta[:, :, a] += history.transferred[:, :, e]
        delta[:, :, b] -= history.transferred[:, :, e]
    first, second = (
        spec.model.species.index(s) for s in (spec.model.from_species, spec.model.to_species)
    )
    delta[:, first] += history.converted
    delta[:, second] -= history.converted
    process_error = float(np.max(np.abs(delta)))
    require(max(balance, process_error) < ACCOUNTING_TOLERANCE, f"Accounting: {path}")
    return data, {
        "manifest_sha256": hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
        "definition_sha256": spec.fingerprint,
        "max_reference_errors_fmol": errors,
        "max_total_amount_error_fmol": balance,
        "max_process_accounting_error_fmol": process_error,
        "final_amounts_fmol": history.amount[-1].tolist(),
        "final_species_totals_fmol": history.amount[-1].sum(axis=-1).tolist(),
        "steps": len(data["accepted_times"]) - 1,
        "timings": manifest["timings"],
    }


def verify(output):
    if output.exists():
        raise ValueError("Output already exists; choose a new path")
    chain = load_spec(ROOT / "configs/reaction_transport_chain.json")
    blocked = replace(
        chain,
        experiment=replace(
            chain.experiment,
            contact=tuple(GraphContactChange(p.time, (0, 0)) for p in chain.experiment.contact),
        ),
    )
    disconnected = replace(
        chain,
        experiment=replace(
            chain.experiment,
            contact=tuple(GraphContactChange(p.time, (1, 0)) for p in chain.experiment.contact),
        ),
    )
    transport = replace(
        chain, model=replace(chain.model, forward_rate=(0, 0, 0), reverse_rate=(0, 0, 0))
    )
    cases = {
        "single": load_spec(ROOT / "configs/reaction_transport_single.json"),
        "pair": load_spec(ROOT / "configs/reaction_transport_pair.json"),
        "chain": chain,
        "blocked": blocked,
        "disconnected": disconnected,
        "transport_only": transport,
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, spec in cases.items():
        print(f"Running composition fixture: {name}", flush=True)
        write_run(output / name, run(spec), checkpoint_times=(6.0,))
    parent = load_snapshot(output / "chain/snapshots/step-000122")
    release_spec = load_spec(ROOT / "configs/reaction_transport_release.json")
    for name, spec, checkpoint in (
        ("resumed", chain, parent.checkpoint),
        ("released", release_spec, branch_checkpoint(chain, parent.checkpoint, release_spec)),
    ):
        write_run(
            output / name,
            run(spec, checkpoint),
            provenance={
                "operation": "resume" if name == "resumed" else "branch",
                "parent_snapshot_sha256": parent.fingerprint,
                "parent_definition_sha256": chain.fingerprint,
                "branch_time": 6.0,
            },
        )
    inspected = {name: inspect_run(output / name) for name in (*cases, "resumed", "released")}
    a, b, c = (inspected[name][0] for name in ("chain", "resumed", "released"))
    suffix = a["accepted_times"] >= 6
    np.testing.assert_array_equal(a["accepted_times"][suffix], b["accepted_times"])
    for field in ("amount", "transferred", "converted"):
        np.testing.assert_array_equal(a[field][suffix], b[field])
        np.testing.assert_array_equal(b[field][0], c[field][0])
    np.testing.assert_array_equal(
        c["transferred"], np.broadcast_to(c["transferred"][0], c["transferred"].shape)
    )
    require(np.max(np.abs(c["amount"][-1] - c["amount"][0])) > 0.1, "Release stopped reactions")
    require(np.all(inspected["blocked"][0]["transferred"] == 0), "Blocked contacts transferred")
    require(
        np.all(inspected["disconnected"][0]["transferred"][:, :, 1] == 0),
        "Isolated route transferred",
    )
    require(
        np.all(inspected["transport_only"][0]["converted"] == 0), "Disabled reactions converted"
    )
    for field in (
        "cell_ids",
        "volume",
        "senders",
        "receivers",
        "contact_ids",
        "contact_active",
        "permeability",
    ):
        np.testing.assert_array_equal(a[field], inspected["blocked"][0][field])
    # Independently assembled oracle measures transient refinement on fixed data.
    short = replace(
        chain,
        experiment=replace(
            chain.experiment,
            end_time=2,
            observation_times=(0, 2),
            contact=(GraphContactChange(0, (1, 0.5)),),
        ),
    )
    errors = []
    for dt in (0.4, 0.2, 0.1):
        result = run(replace(short, execution=replace(short.execution, dt=dt)))
        errors.append(max(reference_errors(result.spec, result.times, result.history).values()))
    ratios = [a / b for a, b in zip(errors, errors[1:], strict=False)]
    require(all(14 < value < 20 for value in ratios), "Refinement outside declared range")
    receipt = {
        "status": "pass",
        "scope": "CORE-003 engineering composition, not source bioelectric validation",
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime_identity(),
        "source_hashes": source_hashes(),
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "oracle_sha256": hashlib.sha256(
            (ROOT / "tests/reference_reaction_transport.py").read_bytes()
        ).hexdigest(),
        "reference_tolerance_fmol": REFERENCE_TOLERANCE,
        "accounting_tolerance_fmol": ACCOUNTING_TOLERANCE,
        "refinement_dt": [0.4, 0.2, 0.1],
        "refinement_errors_fmol": errors,
        "refinement_ratios": ratios,
        "all_artifact_hashes_valid": True,
        "replay_exact_suffix": True,
        "release_stops_transport_not_reactions": True,
        "runs": {name: detail for name, (_, detail) in inspected.items()},
    }
    with (output / "verification.json").open("x") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
