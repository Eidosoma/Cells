"""S5a's qualification protocol, PROPOSED and not registered: its draft from disclosed runs.

docs/CELL_DIVISION_S5_DESIGN.md §8.3, with the lead's rulings of 13 and 14 November. Every
tolerance number in the draft is computed here from a development run named beside it
(DEVELOPMENT); the rules are stated with them. The lead registers the protocol, after review
with the advisor: registration changes the status. Judged runs use a fresh clean snapshot of
main, and every S5 judge entry (q2_rops_comparison, q3_tissue_comparison, q5_order,
egg_division_world) starts with registered(), which refuses, before anything is computed, an
unregistered protocol and a run outside a clean execution snapshot, as S3's judge does
(cleft_egg_engine.judged_run_refusal).

Usage: python -m validation.division.s5_protocol draft OUTPUT_JSON
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation/division/s5_protocol.json"


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged run may not start (None: it may): an unregistered protocol, or a source that
    is not a clean execution snapshot (validation/source_snapshot.py), as S3's judge refuses
    them."""
    status = protocol.get("status")
    if not (isinstance(status, str) and status.startswith("registered")):
        return "the S5 protocol is not registered (its status does not begin 'registered')"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot of main, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def registered(item, protocol_path=PROTOCOL, root=ROOT):
    """(protocol, its item): the judge entries' first call. Raises SystemExit("Refused: ...")
    unless the protocol is registered and the source a clean execution snapshot."""
    protocol = json.loads(Path(protocol_path).read_text())
    refusal = judged_run_refusal(protocol, root)
    if refusal:
        raise SystemExit("Refused: " + refusal)
    return protocol, protocol[item]


EVIDENCE = Path("/mnt/workspaces/Cells/cell-division-s5-20261113-01")
DEVELOPMENT = dict(
    q2=EVIDENCE / "protocol-dev-s5a20/q2_rops_comparison/q2_rops.json",
    q3=EVIDENCE / "protocol-dev-s5a21/q3_tissue_comparison/q3_tissue.json",
    q4_tests=EVIDENCE / "protocol-dev-s5a21/test_division_limits_runs.log",
    q4_measure=EVIDENCE / "protocol-dev-s5a21/q4_limits_measure.json",
    q5=EVIDENCE / "comparisons-s5a9/q5_order/q5_order.json",
    q10_dt=EVIDENCE / "gaps-s5a13/q10_sensitivity_dt0.25ms/q10_sensitivity.json",
    q10_half=EVIDENCE / "q10-s5a14-dt0.000125/q10_sensitivity.json",
    egg=EVIDENCE / "egg-s5a8/egg_division.json",
    q2_probe=EVIDENCE / "protocol-dev-s5a21/q2_domain_probe.json",
    q2_cause=EVIDENCE / "protocol-dev-s5a21/q2_rounding_cause.json",
    q2_out_of_domain=EVIDENCE / "comparisons-s5a9/q2_rops_comparison/q2_rops.json",
    regression=EVIDENCE / "regression-s5a9/results.txt",
)
SNAPSHOTS = {
    "protocol-dev-s5a21": "67b22b0",
    "protocol-dev-s5a20": "5e6f9cb",
    "head-s5a18": "1691dc2",
    "probe-q2-s5a16": "cbbe55b",
    "q10-s5a14-dt0.000125": "e448687",
    "gaps-s5a13": "0ae7bef",
    "comparisons-s5a9": "6c2b118",
    "regression-s5a9": "6c2b118",
    "egg-s5a8": "c37ffa2",
}
# Runs from before main's merge of the volume ledger (08c6a10). S5's own crossrev set is
# identical across the merge (crossrev-s5a10-division), but it covers the nine compact worlds
# only; the egg-scale world and Q5's worlds are outside it.
PRE_MERGE = {"comparisons-s5a9", "regression-s5a9", "egg-s5a8"}
EPS = float(np.finfo(float).eps)
FLOOR_K = 64  # Q3's rounding floor: k eps x the quantity's scale, with k = 64 (as Q5's).
ORDER_BAND = (1.8, 2.3)  # Q5's observed-order band (proposed).
STATUS = (
    "PROPOSED, not registered: drafted 14 November 2026 for the lead's review with the "
    "advisor. No judged run has been made. Q2's scale is pending in R-ops (Appendix A.8, the "
    "increment form's term): Q2's frozen draws were fixed before it lands."
)


def load(name):
    return json.loads(DEVELOPMENT[name].read_text())


def where(name):
    """A development run's path and its snapshot's revision."""
    path = DEVELOPMENT[name]
    run = next((k for k in SNAPSHOTS if k in str(path)), None)
    return dict(path=str(path), snapshot_revision=SNAPSHOTS.get(run), pre_merge=run in PRE_MERGE)


def tolerance(step, reference, scale):
    """3 x (step + reference); the floor k eps x scale serves only where both terms fall below
    it."""
    floor = FLOOR_K * EPS * scale
    if step < floor and reference < floor:
        return max(3.0 * (step + reference), floor), True
    return 3.0 * (step + reference), False


def q3():
    report = load("q3")
    worlds = {}
    for name, world in report["worlds"].items():
        quantities = {}
        for q, scale in world["scale"].items():
            if scale == 0.0:  # Absent in this world (no lumen, bridge or contact).
                continue
            rows = {}
            for t, row in world["per_record"].items():
                if not row["live"][q]:  # Not live at this record: nothing is compared.
                    continue
                step, ref = row["engine_step_term"][q], row["reference_term"][q]
                value, floored = tolerance(step, ref, scale)
                seen = row["engine_minus_reference"][q]
                rows[t] = dict(
                    tolerance=value,
                    floor_applies=floored,
                    engine_step_term=step,
                    reference_term=ref,
                    development_engine_minus_reference=seen,
                    development_fraction_of_tolerance=seen / value,
                )
            quantities[q] = dict(scale=scale, floor=FLOOR_K * EPS * scale, records=rows)
        worlds[name] = dict(records_s=world["records_s"], quantities=quantities)
    return worlds


def q10():
    dt, half = load("q10_dt"), load("q10_half")
    worlds = {}
    for name, world in dt["worlds"].items():
        steps = {
            q: float(np.max(np.abs(np.asarray(v) - np.asarray(half["worlds"][name]["nominal"][q]))))
            for q, v in world["nominal"].items()
        }
        scales = {q: float(np.max(np.abs(np.asarray(v)))) for q, v in world["nominal"].items()}
        # As Q3's: the floor serves only where the step term falls below it.
        tolerances = {q: tolerance(s, 0.0, scales[q])[0] for q, s in steps.items()}
        changes = {}
        for label, change in world["changes"].items():
            changes[label] = {
                q: dict(
                    max_abs_change=c["max_abs_change"],
                    tolerance=tolerances[q],
                    within=c["max_abs_change"] <= tolerances[q],
                )
                for q, c in change.items()
                if q != "against"
            }
        worlds[name] = dict(
            nominal_step_term=steps, tolerance=tolerances, development_changes=changes
        )
    return worlds


def q2():
    report = load("q2")
    return dict(
        fixed_cases={k: v["worst"] for k, v in report["cases"].items()},
        simultaneous={
            k: {o: e["worst"] for o, e in v.items()} for k, v in report["simultaneous"].items()
        },
        frozen_draws={
            w: {
                s: {k: v[k] for k in ("seed", "spread", "draws", "admitted", "worst", "worst_key")}
                for s, v in e.items()
            }
            for w, e in report["random"].items()
        },
        negative_controls={
            label: {
                kind: (v["smallest_defect_caught"] if kind != "baseline" else v)
                for kind, v in entry.items()
            }
            for label, entry in report["negative_controls"].items()
        },
    )


def q4():
    log = DEVELOPMENT["q4_tests"].read_text()
    summary = re.findall(r"^(\d+ passed.*|.*failed.*)$", log, re.M)
    return dict(tests=summary[-1] if summary else None, measure=load("q4_measure"))


def q5():
    report = load("q5")
    out = {}
    for world, quantities in report["worlds"].items():
        for q, v in quantities.items():
            out[f"{world} {q}"] = {
                k: v[k]
                for k in (
                    "measurable",
                    "rounding_only",
                    "every_step_term_decreases",
                    "order_min",
                    "order_max",
                )
            }
    return dict(steps_s=report["steps_s"], records_s=report["records_s"], quantities=out)


def draft():
    egg = load("egg")
    regression = DEVELOPMENT["regression"].read_text().splitlines()
    return {
        "kind": "cells.cell_division_s5_protocol@1",
        "id": "s5a-partition-bridge-insertion2-lumen2",
        "title": (
            "S5a: isopotential_partition@1, cytoplasmic_bridge_closure@1, "
            "scheduled_membrane_insertion@2 and restricted_cleft_lumen@2 against R-ops, "
            "R-tissue and the analytic limits"
        ),
        "status": STATUS,
        "engine_models": [
            "resolved_pump_composite@1",
            "resolved_pump_tissue@3",
            "membrane_entity_state@1",
            "isopotential_partition@1",
            "cytoplasmic_bridge_closure@1",
            "scheduled_membrane_insertion@2",
            "restricted_cleft_lumen@2",
            "electrode_current_injection@1",
        ],
        "references": {
            "R-ops": "validation/division/partition_reference.py (run, not read)",
            "R-tissue": "validation/division/cleft_tissue_reference.py (run, not read)",
            "interface": "validation/division/REFERENCES_USAGE.md; the adapters are built from "
            "it alone",
        },
        "rules": {
            "tolerances": "Every tolerance number is computed from a development run named "
            "beside it (validation/division/s5_protocol.py draft); development runs are not "
            "judged.",
            "judged_run": "once per item, after registration, from a fresh clean execution "
            "snapshot of main (validation/source_snapshot.py, no dirty patch). Each judged "
            "driver refuses an unregistered protocol and a run outside a clean snapshot (to be "
            "added at registration). A failure is recorded and diagnosed, never retuned.",
            "development_runs": {k: where(k) for k in DEVELOPMENT},
            "pre_merge": "runs marked pre_merge ran before main's merge of the volume ledger "
            "(08c6a10). S5's own crossrev set is identical across the merge "
            "(crossrev-s5a10-division against crossrev-s5a11), but it covers the nine compact "
            "worlds only; the egg-scale world and Q5's worlds are outside it, and the only merged "
            "source they execute (current_injection.py) changed by a declaration "
            "(CONFLICTS_VIEW volume).",
        },
        "Q1": {
            "claim": "Every @3 and operator ledger closes on host and device across partitions, "
            "with insertion, lumen, bridge and injection.",
            "worlds": "compact 1 -> 2 and 1 -> 2 -> 4 (tests/partition_fixtures), and the "
            "egg-scale world (validation/division/egg_division_world.py) at full scale",
            "pass": "no ledger, domain or dissipation check fails on any row, host and device",
            "as_built": [
                "tests/unit/test_partition_runs.py",
                "tests/unit/test_cleft_division_runs.py",
                "validation/division/egg_division_world.py (windowed, device checks on every "
                "row, then the host replay)",
            ],
            "judged_run": "the egg-scale world once, at 0.25 ms, with a 6G memory cap; the "
            "compact worlds through their test files at the judged snapshot",
            "development": dict(
                egg=where("egg"),
                egg_diagnostics=egg["diagnostics"],
                egg_rows_replayed=egg["rows_replayed"],
                regression=dict(where("regression"), files_passed=len(regression) - 1),
            ),
        },
        "Q2": {
            "claim": "The engine's event map equals R-ops'.",
            "cases": [
                "each world's events: the compact symmetric and asymmetric worlds, the "
                "neighbour contact, the bridge world's first and second divisions, the "
                "asymmetric furrow world with a bridge, the second-onset world's first division",
                "the simultaneous second divisions as the engine applies them (bridge world, "
                "second-onset world), against R-ops applying them one after the other, in both "
                "orders",
                "the frozen draws (below)",
            ],
            "frozen_draws": {
                "worlds": [
                    "symmetric neighbour world: tests/partition_fixtures.divided(neighbour=True)",
                    "asymmetric neighbour world: divided(neighbour=True, f=0.75, "
                    "area_fraction=0.6, carriers={Na: 0.3, K: 0.5, M: 0.2})",
                ],
                "spreads_declared_charges": [0.1, 1.0, 3.0],
                "draws_per_world_and_spread": 200,
                "seed": "numpy default_rng(20261113), fresh per world and spread",
                "sampler": "validation/division/q2_rops_comparison.perturbed",
                "rule": "every draw the composite's control domain check admits, with the "
                "control at the event, is compared; no other bound applies, and no draw is "
                "redrawn",
                "open_question": "one seed feeds all six sets: both worlds draw the same "
                "stream (so their admitted counts match, 200, 148 and 59), and the three spreads "
                "differ only in the net-charge term. These are q2_domain_probe's draws, whose "
                "old-scale results are known (9.06, 860.56, 152.62). Distinct seeds per world "
                "and spread would be independent sets. The lead's choice, before R-ops' "
                "amended magnitudes land.",
            },
            "tolerance": "64 eps x R-ops' own magnitude per compared quantity (the lead's "
            "ruling). For a cell's node charge, input and daughters alike, R-ops' magnitude "
            "adds |Q| + 1e-15 F sum |z dn|, the increment form's term, carried through its own "
            "solve (Appendix A.8, pending in R-ops); clefts unchanged. A key without an R-ops "
            "magnitude compares at 64 eps x (|engine| + |R-ops|).",
            "negative_controls": {
                "cases": "the asymmetric neighbour world's bound state and its admitted "
                "spread-1 draw whose daughter sits nearest 0 V after the event; the asymmetric "
                "furrow world",
                "defects": "R-ops given a_k + delta for membrane_0 (potentials cannot show it: "
                "a patch's charge and capacitance split together), and the parent's node charge "
                "+ delta |Q_P|; delta from 1e-16 to 1e-2 in quarter decades",
                "report": "the smallest delta caught (ratio above 64) on the daughters' charges, "
                "on the potentials and on any key, under the old and the new scales",
                "proposed_pass": "where the case's undefected ratio passes, a_k + 1e-9 is caught "
                "on the charges, and the parent's charge + 1e-9 |Q_P| on the charges and the "
                "potentials (for the lead to set)",
            },
            "judged_run": "q2_rops_comparison once at the judged snapshot, with R-ops' amended "
            "magnitudes; every case reported under both the old and the new scale",
            "development_old_scale": dict(where("q2"), **q2()),
            "disclosed_runs": {
                "out_of_domain_94.7": dict(
                    where("q2_out_of_domain"),
                    note="uncompensated increments; the states pass @3's bare domain check but "
                    "fail the composite's control domain check in 197 of 200 (the gating laws' "
                    "voltage domains) and the dropped 10% band in all 200. Cause: the engine "
                    "forms charges in increment form, and its rounding scales with the "
                    "increments' ionic content.",
                ),
                "domain_probe": where("q2_probe"),
                "rounding_cause": dict(
                    where("q2_cause"),
                    note="|engine - R-ops| scales with the increments' ionic content at fixed "
                    "net charge: median ratio 9.3-10.0 at 10x and 96-112 at 100x (asymmetric "
                    "world); A.1's whole content is about 1,370 times the increments'.",
                ),
            },
        },
        "Q3": {
            "claim": "Trajectories after partition agree with R-tissue.",
            "worlds": "quartered furrow (cleft_quartered, passive, 1 pA into d1) and neighbour "
            "contact (asymmetric f 0.75, a 0.6, three mismatch carriers, the contact's gate "
            "fixed open, 1 pA into d1); validation/division/q3_tissue_comparison.py",
            "records": "strictly after each division instant and off the onset instants",
            "quantities": "each live cell's Vm; each lumen's volume and composition; the "
            "bridge current; each contact's current in R-tissue's direction",
            "judged_dt_s": 2.5e-4,
            "engine_step_term_rule": "|Q(0.25 ms) - Q(0.125 ms)| per quantity and record",
            "reference_term_rule": "|R-tissue(SMALL atol) - R-tissue(SMALL x 1e-3)| per quantity "
            "and record",
            "tolerance_rule": f"3 x (step + reference) per quantity and record; where both "
            f"terms fall below it, the floor {FLOOR_K} eps x the quantity's scale (its largest "
            f"|value| over the world's records, the engine's at the judged step) serves instead",
            "verdict_rule": "pass when every |engine - R-tissue| at each record is within its "
            "tolerance",
            "tolerances": dict(where("q3"), worlds=q3()),
        },
        "Q4": {
            "claim": "The analytic limits (design §7.3) hold, each to its stated tolerance.",
            "limits": [
                "symmetric division at the event: daughters bitwise half the parent, moved "
                "transfers and the chemical work exact zeros, the capacitor term within 1e-14 "
                "of 1/2 C (0.1 V)^2 (test_partition.py)",
                "symmetric trajectories: every field and potential of d1 and d2 within 64 eps "
                "of its scale for 50 ms (test_division_limits_runs.py)",
                "asymmetric division: increments to 1e-12, Q_D1 = a q to 1e-12, the unmixing "
                "work RT sum delta^2 / (2 n f (1 - f)) to 1e-3 and >= 0 (test_partition.py)",
                "isopotential split: the daughters at the parent's potential to 1e-12 "
                "(test_partition.py)",
                "open bridge: its conductance 2 a sigma_cyt to 1e-3, and 1 - V2/V1 = R_b / (Rm + "
                "R_b) to 1% at 0.25 ms (test_bridge_closure_runs.py)",
                "closed bridge (a = 0): the trans-cleft T-network's coupling, cleft ratio and "
                "input resistance to 1%, and the bridge-free world's response to 1e-9 "
                "(test_division_limits_runs.py)",
                "sealed cleft (A/L = 0): R_j = 1/G_f1 + 1/G_f2 = 2 r_new / A_face to 1%, the "
                "coupling to 1% (test_division_limits_runs.py)",
            ],
            "development": dict(where("q4_tests"), **q4()),
        },
        "Q5": {
            "claim": "The observed order is about 2 after partitions.",
            "driver": "validation/division/q5_order.py at 0.5, 0.25 and 0.125 ms",
            "rule": "each measurable component's observed order log2(e1 / e2) lies in the band "
            f"{list(ORDER_BAND)} (proposed); components whose change is within 64 eps of the "
            "quantity's scale are rounding and counted apart",
            "stop_condition": "stop and report if any measurable component's step term fails to "
            "decrease from the (0.5, 0.25 ms) pair to the (0.25, 0.125 ms) pair (S3's)",
            "development": dict(where("q5"), **q5()),
        },
        "Q6": {
            "claim": "Restarts and batches (design §8.3's items).",
            "as_built": [
                "restart at t_e - dt, t_e and t_e + dt, and from a checkpoint written after a "
                "partition, bitwise (test_partition_runs.py)",
                "a vector-window batch mixing worlds by value equals each scalar run within "
                "1e-12 of each field's scale, bitwise against itself reversed; a batch mixing "
                "static structures is refused (test_partition_runs.py, "
                "test_cleft_division_runs.py)",
                "E_ref, q_ref and partition_birth_gate are bindings, never compiled in "
                "(validation/division/division_crossrev.py check)",
            ],
        },
        "Q7": {
            "claim": "Idle and unchanged (the lead's ruling).",
            "items": [
                "an idle partition and an idle bridge are bitwise the composition without them "
                "(test_partition.py, test_partition_runs.py, test_bridge_closure.py): built",
                "the 19-cell sheet at the 64-node cap with idle division operators, bitwise: "
                "not built",
                "S3's cleft egg on insertion@2 and lumen@2 under a registered operator variant "
                "of S3's protocol (S3's tolerances unchanged; its judge gains the variant's "
                "acceptance); the comparison with S3's judged run reported: not built",
                "crossrev: every existing set identical, S5's own set recorded "
                "(crossrev-s5a11, crossrev-s5a10-division): built",
            ],
        },
        "Q8": {"claim": "Each refusal, with its message.", "as_built": "the S5 tier-1 files"},
        "Q9": {
            "claim": "Closed slots are @3 padding at the view; the lumen's padded-slot test.",
            "as_built": "test_partition.py, test_restricted_lumen_v2.py",
        },
        "Q10": {
            "claim": "Sensitivity to the partition time and to a_0 (design §4.2).",
            "driver": "validation/division/q10_sensitivity.py",
            "judged_dt_s": 2.5e-4,
            "tolerance_rule": "per world and quantity, 3 x the nominal run's step term "
            "|Q(0.25 ms) - Q(0.125 ms)|, with Q3's floor (64 eps x the quantity's largest "
            "|value|) where the step term falls below it (proposed); a change within it is "
            "insensitive, otherwise t_p and a_0 enter that quantity's band",
            "note": "the nominal bridge exchange is exactly 0 (the bridge closes at 3 ms, before "
            "the current starts), so its tolerance is 0 and any exchange a variant opens is a "
            "change; without injection every arm's change is exactly 0",
            "tolerances": dict(
                quarter=where("q10_dt"),
                eighth=where("q10_half"),
                worlds=q10(),
            ),
        },
        "Q11": {
            "claim": "The retirement record is state wherever state goes.",
            "as_built": [
                "history rows, checkpoints, host replays and the summary carry the record; the "
                "negative control (record zeroed) fails the local and outside ledgers "
                "(test_partition_runs.py)",
                "at egg scale: the windowed run's rows replay with identical diagnostics; the "
                "negative control fails (egg_division_world.py)",
            ],
            "development": dict(
                where("egg"),
                negative_control=egg["negative_control"],
                record_after_first_partition_pJ=egg["record_after_first_partition_pJ"],
            ),
        },
    }


if __name__ == "__main__":
    if sys.argv[1:2] != ["draft"]:
        raise SystemExit("Usage: python -m validation.division.s5_protocol draft OUTPUT_JSON")
    Path(sys.argv[2]).write_text(json.dumps(draft(), indent=1) + "\n")
