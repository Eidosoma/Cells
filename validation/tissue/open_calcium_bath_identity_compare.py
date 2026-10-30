"""Versioned, post hoc bath comparison; never run or alter a trajectory.

The v1 comparator still writes all original arrays, metrics and failures.
Policy v2 changes only temporal-order acceptance of one algebraic identity.
Pinned original receipts remain the evidence for domain and stage validation;
this reader also rechecks their saved physical bounds, without new equations.
"""

import argparse
import json
import math
from pathlib import Path

from validation.tissue import open_calcium_bath_trajectory_common as artifact
from validation.tissue import open_calcium_bath_trajectory_compare as original

IDENTITY = "observer__energy_balance_pJ_s"
POLICY_KIND = "cells.open_calcium_bath_comparison_policy@2"
PROTOCOL_SHA256 = "8eea432dbf4ed3b230c2eb433e0a3766349fd47853e39776477079230a84b305"
INVARIANTS = frozenset(
    "local_material_fmol outside_material_fmol chemical_ledger_fmol ionic_ownership_fmol "
    "nonionic_moiety_fmol ionic_global_fmol pool_material_fmol adenylate_fmol phosphorus_fmol "
    "capacitor_charge_C electrode_charge_C global_charge_C reservoir_work_pJ electrode_work_pJ "
    "energy_residual_pJ pool_energy_pJ program_energy_pJ".split()
)


def load_policy(path, protocol):
    policy = artifact.read_json(path)
    # Compare the entire versioned declaration, not just a user-selected channel.
    declared = artifact.read_json(
        Path(__file__).with_name("open_calcium_bath_identity_policy.json")
    )
    if (
        policy != declared
        or policy["kind"] != POLICY_KIND
        or policy["temporal_order_exempt_channels"] != [IDENTITY]
        or policy["new_numerical_tolerances"] != {}
        or policy["integration_protocol_sha256"] != PROTOCOL_SHA256
        or artifact.digest(protocol) != PROTOCOL_SHA256
        or protocol["kind"] != policy["integration_protocol_kind"]
    ):
        raise ValueError("Changed comparison policy or original integration protocol")
    return policy


def bounded(value, limit, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= limit:
        raise ValueError("Invalid or out-of-budget saved physical check: " + label)
    return value


def invariant(proof, protocol):
    if set(proof) != INVARIANTS:
        raise ValueError("Missing or extra independent invariant")
    for name, value in proof.items():
        bounded(value, math.inf, name)
    return artifact.check_proof(proof, protocol)


def log_rows(path):
    with Path(path).open() as stream:
        for line in stream:
            yield json.loads(line)


def physical_evidence(dataset, protocol, plan, sources, loaded):
    """Recheck complete saved proofs; these are not independent new runs."""
    import numpy as np

    ids = plan["datasets"][dataset]
    rate_limit = protocol["tolerances"]["rate_energy_atol_pJ_s"]
    result = {}
    for name in ids["integrations"]:
        receipt, job = sources[name], plan["jobs"][name]
        record, folder = receipt["record"], Path(receipt["data"])
        times = loaded[name]["times"]
        rate = bounded(record["max_rate_energy_error_pJ_s"], rate_limit, name)
        maxima = dict.fromkeys(INVARIANTS, 0.0)

        def add_proof(proof, maxima=maxima):
            for key, value in invariant(proof, protocol).items():
                maxima[key] = max(maxima[key], value)

        if job["role"] == "oracle":
            proofs = artifact.read_json(folder / "invariants.json")
            if len(proofs) != len(times):
                raise ValueError("Incomplete independent accepted-state proofs")
            for proof in proofs:
                add_proof(proof)
            stages = None
        else:
            accepted, stages, stage_rate = 0, 0, 0.0
            for row in log_rows(folder / "progress.jsonl"):
                if row.get("stage") == "accepted_state":
                    i = accepted
                    if (
                        i >= len(times)
                        or row["sample_index"] != i
                        or row["physical_time_s"] != times[i]
                        or row["total_rk_stages"] != 4 * i
                        or stages != 4 * i
                    ):
                        raise ValueError("Accepted-state proof lost its original clock/stages")
                    add_proof(row["independent_invariants"])
                    current = bounded(row["max_rate_energy_error_pJ_s"], rate, name)
                    if current < stage_rate:
                        raise ValueError("Accepted energy maximum omits an RK stage")
                    stage_rate = current
                    accepted += 1
                else:
                    step, substep = divmod(stages, 4)
                    if (
                        accepted != step + 1
                        or step + 1 >= len(times)
                        or row["step"] != step
                        or row["rk_stage"] != substep + 1
                        or row["step_left_s"] != times[step]
                        or row["step_right_s"] != times[step + 1]
                        or row["step_s"] != times[step + 1] - times[step]
                        or row["held_control_time_s"] != times[step]
                        or row["physical_time_s"]
                        != times[step] + (0.0, 0.5, 0.5, 1.0)[substep] * row["step_s"]
                    ):
                        raise ValueError("Incomplete or shifted original RK4 stage evidence")
                    stage_rate = max(stage_rate, bounded(row["rate_energy_error_pJ_s"], rate, name))
                    stages += 1
            if accepted != len(times) or stages != record["rk_stages"] or stage_rate != rate:
                raise ValueError("Incomplete stage/endpoint physical evidence")
            residual = loaded[name][IDENTITY]
            if residual.dtype.kind != "f" or not np.isfinite(residual).all():
                raise ValueError("Invalid instantaneous identity channel")
            bounded(float(np.max(np.abs(residual))), rate_limit, name + " absolute identity")
        result[name] = dict(
            accepted_proofs=len(times),
            rk_stage_proofs=stages,
            max_rate_energy_error_pJ_s=rate,
            invariant_maxima=maxima,
        )

    projection = sources[ids["projection"]]
    expected = projection["record"]["independent_physical_observer_max_errors"]
    if not expected:
        raise ValueError("Missing independent physical observer checks")
    for name, value in expected.items():
        bounded(value, 1.0, name)
    maxima = dict.fromkeys(expected, 0.0)
    seen = {variant: {} for variant in ids["oracles"]}
    for row in log_rows(Path(projection["data"]) / "progress.jsonl"):
        variant, i = row["variant"], row["sample_index"]
        times = loaded[ids["oracles"][variant]]["times"]
        if type(i) is not int or not 0 <= i < len(times) or row["physical_time_s"] != times[i]:
            raise ValueError("Independent observer proof lost its original clock")
        if i in seen[variant] and seen[variant][i] != row:
            raise ValueError("Overlapping independent observer proofs disagree")
        seen[variant][i] = row
        invariant(row["independent_invariants"], protocol)
        errors = row["independent_observer_errors"]
        if set(errors) != set(expected):
            raise ValueError("Independent physical observer check inventory changed")
        for name, value in errors.items():
            maxima[name] = max(maxima[name], bounded(value, 1.0, name))
    for variant, name in ids["oracles"].items():
        if set(seen[variant]) != set(range(len(loaded[name]["times"]))):
            raise ValueError("Incomplete independent physical observer proofs")
        projected = artifact.read_chunks(Path(projection["data"]) / variant)
        residual = projected[IDENTITY]
        if residual.dtype.kind != "f" or not np.isfinite(residual).all():
            raise ValueError("Invalid projected instantaneous identity channel")
        bounded(float(np.max(np.abs(residual))), rate_limit, variant + " absolute identity")
    if maxima != expected:
        raise ValueError("Independent physical observer maxima disagree with full-grid logs")
    result[ids["projection"]] = dict(
        unique_proofs={variant: len(rows) for variant, rows in seen.items()},
        independent_physical_observer_max_errors=maxima,
    )
    return result


def decision(record, protocol):
    """Keep v1 intact and construct an explicit second acceptance decision."""
    channels = set(record["refinement"])
    observers = {"observer__" + key for key in record["observer_fields"]}
    states = {key for key in channels if key.startswith("state__")}
    if (
        IDENTITY not in channels
        or channels != states | observers | {"potential_V"}
        or len(states) != record["complete_fields"]
        or set(record["oracle_uncertainty_fraction"]) != channels
        or set(record["accuracy"]) != {str(d) for d in protocol["dt_divisors"]}
        or any(set(row) != channels for row in record["accuracy"].values())
    ):
        raise ValueError("Missing or mismatched complete comparison channel inventory")
    for row in (record["oracle_uncertainty_fraction"], *record["accuracy"].values()):
        for key, value in row.items():
            bounded(value, math.inf, key)
    for key, row in record["refinement"].items():
        first = bounded(row["coarse_middle_over_budget"], math.inf, key)
        second = bounded(row["middle_fine_over_budget"], math.inf, key)
        if row != original.refinement(
            first, second, protocol["refinement"]["roundoff_resolution_fraction"]
        ):
            raise ValueError("Original raw refinement metric is inconsistent")
    gates = dict(
        reference_uncertainty=all(
            value <= protocol["tolerances"]["oracle_tightening_max_fraction_of_budget"]
            for value in record["oracle_uncertainty_fraction"].values()
        ),
        all_channel_accuracy=all(
            value <= 1.0 for row in record["accuracy"].values() for value in row.values()
        ),
        other_channel_temporal_refinement=all(
            row["passed"] for key, row in record["refinement"].items() if key != IDENTITY
        ),
    )
    expected_v1_violations = []
    if not gates["reference_uncertainty"]:
        expected_v1_violations.append("oracle tightening exceeds its fixed uncertainty share")
    if not gates["all_channel_accuracy"]:
        expected_v1_violations.append(
            "production full state/observer trajectory exceeds fixed accuracy budget"
        )
    if any(not row["passed"] for row in record["refinement"].values()):
        expected_v1_violations.append(
            "resolved state/observer differences fail fixed refinement criterion"
        )
    if record["violations"] != expected_v1_violations:
        raise ValueError("Original violations disagree with complete raw metrics")
    return dict(
        policy=POLICY_KIND,
        passed=all(gates.values()),
        gates=gates,
        violations=[key for key, passed in gates.items() if not passed],
        temporal_order_exempt_channels=[IDENTITY],
        identity_refinement_diagnostic=record["refinement"][IDENTITY],
        original_v1_passed=not record["violations"],
        scope="Requires separately verified physical evidence and exact original lineage.",
    )


def pinned_json(path, checksum):
    if artifact.sha(path) != checksum:
        raise ValueError("Pinned original evidence changed: " + str(path))
    return artifact.read_json(path)


def original_comparisons(summary, campaign_failure):
    """Pin failures as well as successful parents; never relabel either."""
    failure = pinned_json(campaign_failure, summary["original_campaign_failure_sha256"])
    if failure["status"] != "failed" or summary["original_campaign_status"] != "failed":
        raise ValueError("Original campaign failure identity changed")
    old, failures = (
        {},
        {
            "campaign": dict(
                path=str(Path(campaign_failure).resolve()),
                sha256=summary["original_campaign_failure_sha256"],
            )
        },
    )
    for name, pin in summary["comparisons"].items():
        comparison_path = Path(pin["comparison_path"])
        old[name] = pinned_json(comparison_path, pin["comparison_sha256"])
        if old[name]["violations"] != pin["violations"]:
            raise ValueError("Original comparison violations changed")
        if pin["violations"]:
            # Reconciliation pins the supervisor failure, above its data folder.
            path = comparison_path.parent.parent / "failure.json"
            failed = pinned_json(path, pin["failure_sha256"])
            if failed["status"] != "failed":
                raise ValueError("Original comparison failure identity changed")
            failures[name] = dict(path=str(path), sha256=pin["failure_sha256"])
    return old, failures


def run(bundle, summary_path, summary_sha256, policy_path, output, campaign_failure):
    """Reanalyse all six datasets and four comparisons from pinned receipts."""
    import numpy as np

    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    last = {}
    try:
        summary = pinned_json(summary_path, summary_sha256)
        if artifact.sha(bundle / "manifest.json") != summary["bundle_manifest_sha256"]:
            raise ValueError("Original bundle changed")
        artifact.verify_bundle(bundle)
        protocol = artifact.read_json(bundle / "protocol.json")
        policy = load_policy(policy_path, protocol)
        plan = artifact.read_json(bundle / "plan.json")
        old, failures = original_comparisons(summary, campaign_failure)
        parents = {}
        for comparison in old.values():
            parents.update(comparison["dependencies"])
        needed = {name for name, job in plan["jobs"].items() if job["role"] != "compare"}
        if set(parents) != needed:
            raise ValueError("Incomplete original integration/projection dependency inventory")
        for name, receipt in parents.items():
            pin = summary["verified_role_receipts"][name]
            if (
                Path(receipt["directory"]) / "result.json" != Path(pin["path"])
                or receipt["result_sha256"] != pin["sha256"]
            ):
                raise ValueError("Original parent receipt identity changed")
            pinned_json(pin["path"], pin["sha256"])
        dependency_path = output / "dependency-runs.json"
        artifact.write_json(
            dependency_path, {name: row["directory"] for name, row in parents.items()}
        )
        sources = artifact.dependencies(bundle, dict(requires=sorted(needed)), dependency_path)
        phases, trajectories, records = {}, {}, {}
        v1 = output / "original-v1"
        v1.mkdir()
        for dataset in plan["datasets"]:
            last = dict(stage="full_grid_reanalysis", dataset=dataset)
            record, loaded, receipts = original.phase_comparison(
                bundle, dataset, protocol, plan, sources, v1
            )
            previous = [row for row in old.values() if dataset in row["phase_comparisons"]]
            if len(previous) != 1 or record != previous[0]["phase_comparisons"][dataset]:
                raise ValueError("Reanalysis changed original raw comparison metrics")
            original_path = next(
                Path(summary["comparisons"][name]["comparison_path"]).parent
                for name, row in old.items()
                if row is previous[0]
            )
            filename = dataset + "-comparison.npz"
            with np.load(original_path / filename, allow_pickle=False) as before:
                with np.load(v1 / filename, allow_pickle=False) as after:
                    if set(before.files) != set(after.files) or any(
                        before[key].dtype != after[key].dtype
                        or not np.array_equal(before[key], after[key])
                        for key in before.files
                    ):
                        raise ValueError("Reanalysis changed original raw comparison arrays")
            proof = physical_evidence(dataset, protocol, plan, sources, loaded)
            phases[dataset] = dict(
                v1=record, v2=decision(record, protocol), physical_evidence=proof
            )
            trajectories.update(loaded)
            records.update(receipts)
        carries = {}
        for name, prior in old.items():
            job = plan["jobs"][name]
            carry = (
                original.check_carry(plan, job["dataset"], sources, trajectories, records, protocol)
                if job["is_epoch"]
                else {}
            )
            if carry != prior["actual_INIT_carry"]:
                raise ValueError("Original INIT lineage changed")
            carries[name] = carry
        record = dict(
            kind="cells.open_calcium_bath_saved_reanalysis@2",
            comparison_policy=policy,
            policy_sha256=artifact.sha(policy_path),
            original_protocol_sha256=artifact.digest(protocol),
            original_summary_path=str(Path(summary_path).resolve()),
            original_summary_sha256=summary_sha256,
            original_comparisons=summary["comparisons"],
            original_failures=failures,
            bundle_manifest_sha256=summary["bundle_manifest_sha256"],
            dependencies={
                name: {k: v for k, v in row.items() if k != "record"}
                for name, row in sources.items()
            },
            phases=phases,
            actual_INIT_carry=carries,
            all_original_metrics_and_arrays_exact=True,
            new_trajectory_count=0,
            claim=policy["scope"],
        )
        artifact.write_json(output / "reanalysis.json", record)
        if any(not row["v2"]["passed"] for row in phases.values()):
            raise ValueError("Saved-data comparison failed its separate v2 policy")
        artifact.success(output, record)
    except BaseException as error:
        artifact.failure(output, error, context=last)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "summary", "policy", "output", "campaign-failure"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    args = parser.parse_args()
    run(
        args.bundle,
        args.summary,
        args.summary_sha256,
        args.policy,
        args.output,
        args.campaign_failure,
    )


if __name__ == "__main__":
    main()
