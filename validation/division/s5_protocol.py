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
    q2=EVIDENCE / "protocol-dev-s5a34/q2_rops_comparison/q2_rops.json",  # The third amendment's.
    q2_merge=EVIDENCE / "protocol-dev-s5a32/q2_rops_comparison/q2_rops.json",  # The merged head's.
    # s5a28's: at s5a32 the probe called R-ops at its new default (new_scale_findings).
    q2_near_zero=EVIDENCE / "protocol-dev-s5a28/near_zero_set.json",
    q2_second_amendment=EVIDENCE / "protocol-dev-s5a28/q2_rops_comparison/q2_rops.json",
    q2_first_amendment=EVIDENCE / "protocol-dev-s5a25/q2_rops_comparison/q2_rops.json",
    q2_frozen=EVIDENCE / "protocol-dev-s5a23/q2_rops_comparison/q2_rops.json",  # The freeze's.
    q3=EVIDENCE / "protocol-dev-s5a21/q3_tissue_comparison/q3_tissue.json",
    q4_tests=EVIDENCE / "protocol-dev-s5a21/test_division_limits_runs.log",
    q4_measure=EVIDENCE / "protocol-dev-s5a21/q4_limits_measure.json",
    q5=EVIDENCE / "protocol-dev-s5a22/q5_order/q5_order.json",
    q5_bridge_coupling=EVIDENCE / "bridge-coupling-order.json",
    q7a=EVIDENCE / "protocol-dev-s5a22/test_division_idle_sheet_runs.log",
    refusal=EVIDENCE / "rehearsal-s5a36/test_s5_judged_refusal.log",  # The rehearsal's.
    q10_dt=EVIDENCE / "protocol-dev-s5a22/q10_dt0.25ms/q10_sensitivity.json",
    q10_half=EVIDENCE / "protocol-dev-s5a22/q10_dt0.125ms/q10_sensitivity.json",
    egg=EVIDENCE / "egg-s5a8/egg_division.json",
    q2_probe=EVIDENCE / "protocol-dev-s5a21/q2_domain_probe.json",
    q2_cause=EVIDENCE / "protocol-dev-s5a21/q2_rounding_cause.json",
    q2_out_of_domain=EVIDENCE / "comparisons-s5a9/q2_rops_comparison/q2_rops.json",
    q2_before_freeze=EVIDENCE / "protocol-dev-s5a20/q2_rops_comparison/q2_rops.json",
    a8_ratios=Path(
        "/mnt/workspaces/Cells/cell-division-s5-references-20261113-01/a8-ratios/a8_ratios.json"
    ),
    regression=EVIDENCE / "regression-s5a9/results.txt",
)
SNAPSHOTS = {
    "rehearsal-s5a36": "198492d",
    "protocol-dev-s5a34": "1b2cfd6",
    "protocol-dev-s5a32": "d8a0979",
    "protocol-dev-s5a28": "4487d0a",
    "protocol-dev-s5a25": "3c3f190",
    "protocol-dev-s5a23": "0c7e2ac",
    "protocol-dev-s5a22": "1e73543",
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
    "advisor; the lead's rulings of 14 November written in. No judged run has been made. Q2's "
    "judged seeds and its negative controls are frozen together in this commit, before R-ops' "
    "amended magnitudes (Appendix A.8, the increment form's term, pending in R-ops) land."
)
# Q2's judged sets: fresh seeds, assigned by the lead (14 November). Read only by
# q2_rops_comparison.judge, behind its guard; nobody runs them before the judged run.
JUDGED_SEEDS = {
    "symmetric neighbour world": {
        "spread 0.1": 867424677,
        "spread 1": 731592983,
        "spread 3": 186581497,
    },
    "asymmetric neighbour world (f 0.75, a 0.6, three carriers)": {
        "spread 0.1": 336021742,
        "spread 1": 1277804744,
        "spread 3": 1727379153,
    },
}


def load(name):
    return json.loads(DEVELOPMENT[name].read_text())


def where(name):
    """A development run's path and its snapshot's revision."""
    path = DEVELOPMENT[name]
    if path is None:
        return dict(path=None, pending="the observations-only commit after the freeze")
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
        floors = {q: tolerance(s, 0.0, scales[q])[0] for q, s in steps.items()}
        changes = {}
        for label, change in world["changes"].items():
            changes[label] = {
                q: dict(
                    max_abs_change=c["max_abs_change"],
                    noise_floor=floors[q],
                    within_noise=c["max_abs_change"] <= floors[q],
                )
                for q, c in change.items()
                if q != "against"
            }
        worlds[name] = dict(
            nominal_step_term=steps, noise_floor=floors, development_changes=changes
        )
    return worlds


# What an engine-side control's development summary keeps besides its catches.
ENGINE_SIDE = ("engine_refuses_from", "refused_by", "event_checks_agree_with_the_event_map")
# And what a NEAR_ZERO_REPORTED control's keeps (the third amendment).
FIRST_ORDER = ("observed_at_threshold", "first_order_at_threshold")


def q2(name="q2", scale="old"):
    """Q2's development observations at one scale from a run's report."""
    if DEVELOPMENT[name] is None:
        return where(name)
    report = load(name)
    report = report["scales"][scale] if "scales" in report else report
    return dict(
        where(name),
        scale=scale,
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
                kind: (
                    v
                    if kind in ("baseline", "construction")
                    else {
                        k: v[k] for k in ("smallest_defect_caught", "targets_caught_at_threshold")
                    }
                    | ({k: v[k] for k in ENGINE_SIDE if k in v} if "refused_by" in v else {})
                    | {k: v[k] for k in FIRST_ORDER if k in v}
                )
                for kind, v in entry.items()
            }
            for label, entry in report["negative_controls"].items()
        },
    )


def q2_previews():
    """The verdict function on the seen sets' development report under the frozen rule and
    under the third amendment's: a preview, not the judged verdict."""
    from validation.division import q2_rops_comparison as q2d  # As draft imports it.

    report = load("q2")
    item = {"negative_controls": {"threshold": q2d.THRESHOLD}}
    out = dict(where("q2"), note="the verdict function on the seen sets: a preview only")
    for name, reported in (("frozen_rule", ()), ("third_amendment", q2d.NEAR_ZERO_REPORTED)):
        v = q2d.verdict(report, item, reported=reported)
        failing = [k for k, ok in v["controls"].items() if not ok]
        out[name] = dict(
            verdict=v["verdict"],
            largest_ratio=v["largest_ratio"],
            failing=failing,
            near_zero_counts=v["near_zero_counts"],
        )
    return out


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
                k: v.get(k)
                for k in (
                    "scale",
                    "floor",
                    "measurable",
                    "rounding_only",
                    "every_step_term_decreases",
                    "order_min",
                    "order_median",
                    "order_max",
                )
            }
    bridge = load("q5_bridge_coupling")
    return dict(
        steps_s=report["steps_s"],
        records_s=report["records_s"],
        quantities=out,
        bridge_coupling_offset=dict(where("q5_bridge_coupling"), report=bridge),
    )


def passed(name):
    """The last summary line of a pytest log."""
    log = DEVELOPMENT[name].read_text()
    summary = re.findall(r"^(\d+ passed.*|.*failed.*)$", log, re.M)
    return dict(where(name), tests=summary[-1] if summary else None)


def draft():
    from validation.division import q2_rops_comparison as q2d  # The constants Q2 states.

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
            "snapshot of main (validation/source_snapshot.py, no dirty patch). A failure is "
            "recorded and diagnosed, never retuned.",
            "attempts": "an attempt killed by infrastructure before its verdict is written (an "
            "out-of-memory kill, a unit stopped by the slice, a host crash) is not a verdict. It "
            "is recorded with its logs and partial outputs and rerun once from the same "
            "snapshot; each attempt writes its own output directory, since every judge entry "
            "refuses an existing one. A second infrastructure kill goes to the lead, as does "
            "any other ending without a verdict. A run that has written its verdict is final "
            "(the lead, 14 November)",
            "judge_entries": {
                "guard": "validation/division/s5_protocol.registered, each entry's first call: "
                "it refuses an unregistered protocol and a source that is not a clean execution "
                "snapshot before anything is computed or written (S3's rule); "
                "tests/unit/test_s5_judged_refusal.py tests it on edited copies",
                "Q1 and Q11": "python -m validation.division.egg_division_world OUT --judge",
                "Q2": "python -m validation.division.q2_rops_comparison judge OUT (also refused "
                "until R-ops takes charge_term)",
                "Q3": "python -m validation.division.q3_tissue_comparison judge OUT",
                "Q5": "python -m validation.division.q5_order judge OUT",
                "Q4, Q6-Q9": "the test files at the judged snapshot",
                "Q10": "none: reported, not judged",
                "development": dict(
                    passed("refusal"),
                    note="the pre-registration rehearsal's run (the lead, 14 November). The "
                    "count went from 5 (protocol-dev-s5a22, the earlier pointer) to 6 because "
                    "the freeze (0c7e2ac) added Q2 to test_each_judge_entry_refuses_first's "
                    "parametrization after s5a22",
                ),
            },
            "landing_order": "this protocol's frozen commit lands on main first, then the "
            "amended R-ops; A.8's 'pending in R-ops' is removed in that second landing (the "
            "lead, 14 November)",
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
                "the random sets (below)",
                "the negative controls (below)",
            ],
            "random_sets": {
                "worlds": [
                    "symmetric neighbour world: tests/partition_fixtures.divided(neighbour=True)",
                    "asymmetric neighbour world (f 0.75, a 0.6, three carriers): "
                    "divided(neighbour=True, f=0.75, area_fraction=0.6, carriers={Na: 0.3, "
                    "K: 0.5, M: 0.2})",
                ],
                "spreads_declared_charges": list(q2d.SPREADS),
                "draws_per_set": q2d.RANDOM_STATES,
                "sampler": "validation/division/q2_rops_comparison.perturbed, one fresh numpy "
                "default_rng per world and spread",
                "count_rule": "every draw the composite's control domain check admits, with the "
                "control at the event, is compared; no other bound applies, no draw is redrawn, "
                "and the admitted counts are reported",
                "seen": dict(
                    seed=q2d.SEEN_SEED,
                    role="development evidence (q2_domain_probe's draws; their old-scale "
                    "results were seen). Once the amended R-ops lands they are rerun under both "
                    "scales (apply(..., charge_term=False) for the old) and disclosed",
                ),
                "judged": dict(
                    seeds=JUDGED_SEEDS,
                    role="the judged sets, assigned by the lead; read only by "
                    "q2_rops_comparison.judge behind its guard. Nobody runs them, at either "
                    "scale, before the judged run, nor draws the judged states, inputs "
                    "included (the lead, 14 November)",
                ),
            },
            "tolerance": "64 eps x R-ops' own magnitude per compared quantity (the lead's "
            "ruling). A cell's node charge, input and daughters alike, has R-ops' magnitude "
            "M = |Q| + |Q-bar| + 1e-15 F sum_s |z_s Delta_s|: Q-bar its declared charge anchor "
            "and Delta its increments (an input cell's own; a daughter's split anchor and the "
            "increments the map computes). The added term is the increment form's (the lead's "
            "ruling of 14 November: not A.1's whole content, about 1,370 times larger on these "
            "draws). A daughter's magnitude also carries what enters its charge form: f M_P + "
            "mag(delta q) for D1, M_P plus that for D2. Each cell's term |Q-bar| + 1e-15 F sum "
            "|z Delta| is carried through R-ops' own solve into the potentials and everything "
            "downstream (Appendix A.8; in R-ops since 2a386d4); a cleft's charge keeps |Q_c|. "
            "A key without an R-ops magnitude compares at 64 eps x (|engine| + |R-ops|).",
            "a8_loosening": dict(
                where("a8_ratios"),
                note="the references agent's measure of A.8's loosening (new/old per output "
                "key): every magnitude that depends on a charge or potential (charges, "
                "potentials, image charge, capacitor energy, and through delta q the mismatch, "
                "delta, the increments and moved amounts, the daughters' amounts, the free "
                "energy and W); volumes, backgrounds, anchors, areas and capacitances "
                "unchanged. The factor on Q2's own draws comes from the seen sets' rerun",
            ),
            "negative_controls": {
                "frozen": "with the judged seeds, in one commit (the lead, 14 November)",
                "defects": {
                    "a_k": f"R-ops given {q2d.CONTROL_PATCH}'s share a_k + delta; a patch's "
                    "charge and capacitance split together, so it reaches the charges and never "
                    "the potentials",
                    "parent charge": "R-ops given the parent's node charge Q_P + delta "
                    "|Q_declared| (the snapshot's charge anchor), which does not vanish as Q_P "
                    "nears 0",
                    "f": "R-ops given the volume fraction f + delta",
                    "transference": "R-ops given the first carrier's t + delta and the "
                    "second's t - delta, their sum kept 1",
                    "W": "R-ops' daughters' free energy evaluated at V_D (1 + delta), a booking "
                    "defect in the free-energy volume: W moves by -1e-3 RT N_D ln(1 + delta), "
                    "first order (the amendment; accepted as built). It is applied to R-ops' "
                    "output through the usage note's G(n, V): the engine books free energy "
                    "relative to its anchors, so a volume defect there would touch only the "
                    "increments, about 1e-3 of the effect at the bound state",
                    "mismatch scale": "the engine moves (1 + delta) times the mismatch, its "
                    "carrier fractions scaled in its layout, which breaks isopotentiality at "
                    "first order (an engine-side defect, since R-ops keeps the transference "
                    "numbers summing to 1; the amendment, formerly 'image'); a delta its event "
                    "map refuses is reported",
                    "non-conservation": "D2 takes slightly more than the rest: Delta_D2 -> "
                    "(Delta_P - Delta_D1)(1 + delta), applied to the engine's state after its "
                    "event, its D2 increment and moved amount and the image it books (plates1 "
                    "- plates0, the partition's capacitor_state) (the second amendment). At "
                    "first order it moves the amounts by delta Delta_D2, and the charges and "
                    "the image charge by delta F sum_s z_s Delta_D2,s, which vanishes only "
                    "where D2's increment is electroneutral (the condition, stated by the third "
                    "amendment; each case records D2's net charge increment). The work bookings "
                    "keep the "
                    "engine's undefected values, so its work entries are uninformative. The "
                    "partition's event checks, re-applied to the defective state with its "
                    "constants, report the delta they refuse and the checks that refuse it",
                },
                "construction_checks": "each case records the engine-side controls' "
                "construction against the engine's own event: at delta = 0 the "
                "non-conservation construction reproduces the event in every field; the "
                "re-applied event checks pass the event; and along the mismatch-scale ladder "
                "they agree with the event map's verdict and booked image at every delta. The "
                "verdict requires all three (added with the second amendment, at review "
                "before its development run; accepted by the lead, 14 November: a control "
                "whose construction is not faithful at delta = 0 means nothing)",
                "engine_refusals": "the engine-side controls' refusal sizes and refusing checks "
                "are reported information, not judged. They come from event_checks, a copy in "
                "validation/ of the checks the partition's event_map states inline (calling the "
                "engine's own needs a src change: a follow-up, not made now). So the copy's "
                "limits touch information only: its agreement test exercises the isopotential "
                "check alone on the refusing side (the mismatch scale never trips the plate "
                "charges), and a check the event map gained later would be missed. A wrong copy "
                "could fail the construction checks but cannot change a catch; the image the "
                "non-conservation control books is the partition's own capacitor_state's, "
                "checked bit for bit at delta = 0. test_s5_protocol_binding fails if event_map "
                "gains, loses or changes a check or what the checks read (the lead's staleness "
                "guard, 14 November)",
                "deltas": list(q2d.DEFECTS),
                "families": {k: list(v) for k, v in q2d.CONTROL_GROUPS.items()},
                "targets": {k: list(v) for k, v in q2d.CONTROL_TARGETS.items()},
                "statistic": "per control and family, the smallest delta whose ratio passes 64 "
                "(None if none does; 'baseline above 64' where the undefected case already "
                "fails at that scale)",
                "threshold": q2d.THRESHOLD,
                "pass": "at the new scale each near-zero case passes undefected; every judged "
                "control's target families are caught at or below the threshold; and each "
                "case's construction checks hold. Judged in every case, near-zero included: "
                "the parent charge, non-conservation, f and W. Judged on the fixed cases "
                "only: a_k, the mismatch scale and transference (near_zero_reported), which "
                "on the near-zero cases are reported beside their first-order size (the "
                "third amendment). After registration any control miss is a failed Q2, "
                "never a moved threshold",
                "near_zero_reported": list(q2d.NEAR_ZERO_REPORTED),
                "amendment": {
                    "when": "the lead, 14 November, after the freeze (0c7e2ac) and before any "
                    "new-scale run; the threshold stays 1e-9",
                    "finding": "W is reached by no map defect at 1e-9: f at 1.0-1.8e-5 or "
                    "never, transference at 3.2-5.6e-5, a_k at 1.0-1.8e-5, the parent charge "
                    "at 1-1.8e-4 (old scale, protocol-dev-s5a23)",
                    "reason": "dG is stationary at the correct split: at delta = 0 the "
                    "daughters' concentrations equal the parent's, so d dG / d delta = ln c_D1 "
                    "- ln c_D2 = 0, and any map defect reaches W only at second order. W "
                    "equals dG here, the bath held at 0 V. f -> W was a mis-specified target",
                    "changes": [
                        "W leaves f's targets; f's effect on W is reported as information",
                        "W takes its own first-order control (the daughters' free energy at "
                        "V_D (1 + delta))",
                        "the image charge takes its own control (the mismatch scaled, "
                        "delta -> (1 + delta) delta)",
                    ],
                },
                "second_amendment": {
                    "when": "the lead, 14 November, after the first amendment (3c3f190) and "
                    "before any new-scale run; the threshold stays 1e-9",
                    "finding": "the mismatch-scale control (then 'image') does not reach the "
                    "image charge: it missed in 10 of 12 cases, and its two catches were "
                    "rounding: there the image ratio moves in steps of about 20-40 and does not "
                    "grow with delta (old scale, protocol-dev-s5a25)",
                    "reason": "a held node's plate charge is minus the total charge of the "
                    "patches facing it; a split that conserves charge leaves it unchanged, and "
                    "so does the furrow world's floating cleft, whose charge is fixed. No "
                    "charge-conserving defect can move the image charge",
                    "changes": [
                        "the delta-scaling control, renamed 'mismatch scale', targets the "
                        "charges and potentials, no longer the image charge",
                        "a non-conservation control, the defect class the image charge exists "
                        "to catch: Delta_D2 -> (Delta_P - Delta_D1)(1 + delta), targeting the "
                        "image charge and the charge and material sums",
                        "the W control is accepted as built",
                        "the construction checks (negative_controls.construction_checks), "
                        "required by the verdict",
                    ],
                    "rulings": [
                        "the verdict's requirement of the construction checks: accepted",
                        "the charge and material sums are judged through the per-daughter "
                        "charges and amounts families (compare has no sum key): accepted",
                        "the non-conservation control's work entries: uninformative by "
                        "construction, accepted as stated",
                        "the copied event checks: their refusal sizes are information "
                        "(negative_controls.engine_refusals); a staleness test; the engine's "
                        "own checks a follow-up, since they need a src change",
                    ],
                },
                "third_amendment": {
                    "when": "the lead with the advisor, 14 November, after a new-scale result "
                    "on the seen sets (protocol-dev-s5a32); the last amendment before "
                    "registration: after registration, any control miss is a failed Q2",
                    "finding": "at the new scale one target misses 1e-9: the mismatch scale's "
                    "charges in seen spread 1 draw 35 (63.05 at delta = 1e-9, caught at "
                    "1.78e-9). The frozen rule's preview verdict on the seen sets fails, on "
                    "that entry alone (preview_verdicts)",
                    "cause": "a_k, the mismatch scale and transference move charge in "
                    "proportion to the patch charges (x q_k, x dq, x dq / (z F)), which vanish "
                    "at 0 V, while A.8's term (the anchor and the increments' content) does "
                    "not. On a near-zero case their smallest defect caught therefore measures "
                    "the vanishing effect, not Q2's power: at draw 35 (V_P = -0.63 mV) a_k's "
                    "margin is 6.6, transference's 6.8 and the mismatch scale's charges below 1. "
                    "Shown at first order in all ten near-zero cases before this amendment was "
                    "committed: each observed ratio at 1e-9 is within 0.04% of its first-order "
                    "size (development run q2-dev-15, worktree; first_order)",
                    "first_order": "the charge and amount predictions use R-ops' own values and "
                    "magnitudes alone; the mismatch scale's potential prediction is a linearity "
                    "check, R-ops' carrier displacement through the engine's own field solve "
                    "(corrected before registration: the amendment's first record said R-ops "
                    "alone for all)",
                    "changes": [
                        "the parent charge (charges, potentials), non-conservation (image, "
                        "charges, amounts), f (amounts) and W (work) are judged in every case, "
                        "near-zero included",
                        "a_k, the mismatch scale and transference (near_zero_reported) are "
                        "judged on the fixed cases, every target at 1e-9; on the near-zero "
                        "cases they are reported beside their first-order size at 1e-9 "
                        "(first_order_at_threshold, observed_at_threshold)",
                        "the near-zero cases still pass undefected at the new scale",
                    ],
                    "unchanged": "the defect definitions, the 1e-9 threshold, the statistic, "
                    "the seeds and the comparison rule",
                    "condition": "non-conservation's charge and image effect, delta F sum z "
                    "Delta_D2, vanishes only where D2's increment is electroneutral. Each case "
                    "records D2's net charge increment (construction); no seen case is "
                    "electroneutral (1.9-3.5e-13 C in magnitude)",
                    "judged_states": "nobody draws the judged states before the judged run, "
                    "inputs included",
                },
                "scales": "old and new (R-ops' charge_term)",
                "cases": [
                    "the asymmetric neighbour world's bound state",
                    "the near-zero seen draws (below)",
                    "the asymmetric furrow world after its onset (two patches a cell)",
                ],
                "near_zero": dict(
                    rule=f"the asymmetric world's admitted seen draws whose parent patch lies "
                    f"within {q2d.NEAR_ZERO_V} V of 0 V before the event (a state-only rule)",
                    members=[list(x) for x in q2d.NEAR_ZERO],
                    worst_seen=list(q2d.WORST_SEEN),
                    disclosure="the rule was chosen after the seen states had been seen: a "
                    "1 mV rule kept two draws (spread 1, draws 35 and 77); 5 mV adds seven more "
                    "and the spread-3 worst (draw 32). The driver recomputes the members from "
                    "the rule and asserts them",
                    judged_sets="the rule applies unchanged to the judged sets: at the judged "
                    "run the near-zero cases are the judged sets' admitted draws within the "
                    "same 5 mV (the lead, 14 November)",
                    empty_sets="a judged set with no admitted draw within 5 mV leaves its "
                    "near-zero conditions vacuous for that set, not failed. The verdict reports "
                    "the near-zero count of each of the asymmetric world's sets (the rule draws "
                    "from those alone); if no judged set has a near-zero case it says plainly "
                    "that the near-zero part went untested by the judged sets, tested only on "
                    "the seen sets (the lead, 14 November). The seen sets hold 0, 9 and 1 at "
                    "spreads 0.1, 1 and 3",
                ),
            },
            "judged_run": "q2_rops_comparison judge once at the judged snapshot, with R-ops' "
            "amended magnitudes: the cases, the simultaneous divisions, the judged sets and the "
            "controls under both scales, each passed to R-ops explicitly (charge_term False "
            "for the old, True for the new) and recorded in its scale's report; the verdict "
            "at the new scale, under the third amendment's rule",
            "preview_verdicts": q2_previews(),
            "development_old_scale": q2(),
            "development_new_scale": q2(scale="new"),
            "development_estimate": dict(
                where("q2_near_zero"),
                note="the a_k control at the new scale, estimated before R-ops lands: in every "
                "near-zero member a 1e-9 defect moves at least 1e-23 C of charge against a "
                "threshold of 1.2-4.1e-25 C, so it would be caught (an estimate, not a "
                "new-scale result). The new-scale run catches it on the charges at "
                "1e-13-1.8e-10 in every case (development_new_scale)",
            ),
            "development_at_the_merge": dict(
                where("q2_merge"),
                note="the merged head's new-scale pass: the result the third amendment "
                "followed; protocol-dev-s5a34 reproduces it apart from the first-order records",
            ),
            "development_at_the_second_amendment": dict(
                where("q2_second_amendment"),
                note="the second amendment's controls before R-ops' amendment (old scale); "
                "protocol-dev-s5a32's old scale is bit-identical to it",
            ),
            "development_at_the_freeze": dict(
                where("q2_frozen"),
                note="the frozen controls before the amendment (old scale): their W finding "
                "led to it",
            ),
            "development_at_the_first_amendment": dict(
                where("q2_first_amendment"),
                note="the first amendment's controls (old scale): their image finding led to "
                "the second amendment",
            ),
            "development_findings": [
                "W is reached by no map defect at 1e-9 (old scale, protocol-dev-s5a23): f at "
                "1.0-1.8e-5 or never, transference at 3.2-5.6e-5 or never, a_k at 1.0-1.8e-5, "
                "the parent charge at 1-1.8e-4. dG is stationary at the correct split, so a map "
                "defect reaches W only at second order; the lead removed W from f's targets and "
                "gave W and the image charge their own controls (negative_controls.amendment)",
                "the amended W control is caught on W at 5.6e-13 in all 12 cases (old scale, "
                "protocol-dev-s5a25, unchanged at protocol-dev-s5a28), and f on the amounts at "
                "1.8e-14",
                "a finding for the lead: the image control does not reach the image charge. A "
                "held node's plate charge is minus the total charge of the patches facing it; a "
                "split that conserves charge (the engine's always does, D2 taking the rest) "
                "leaves it unchanged, and so does the floating cleft's fixed charge in the "
                "furrow world. So the image target misses in 10 of 12 cases (never caught, or "
                "the undefected ratio above 64), and the two catches (seen spread 1 draws 35 "
                "and 180, at 1.8e-12 and 5.6e-13) are rounding, not a reach: their undefected "
                "image ratios are 0.0 and 23.6, and along the ladder the ratio moves in steps "
                "of about 20-40 without growing with delta (corrected at protocol-dev-s5a28: "
                "'near 64' was wrong). The image control reaches the potentials at "
                "1.8e-14-1e-13 and the charges at 3.2-5.6e-13 where measurable. The engine's "
                "own event checks refuse it from 3.2e-9 to 1.8e-7. The threshold was not "
                "moved: the lead's second amendment took the image charge from this control's "
                "targets and gave it the non-conservation control "
                "(negative_controls.second_amendment)",
                "the non-conservation control (old scale, protocol-dev-s5a28) is caught on the "
                "image charge at 1.0e-15-5.6e-13 and on the charges at 1.8e-15-5.6e-13, each in "
                "11 of 12 cases, and on the amounts at 1.0-3.2e-13 in all 12. It reaches them "
                "at first order: at delta = 1e-9 their ratios are 1.4e5-3.5e7 in every case, "
                "growing tenfold per decade from 1e-11. The low end is rounding-assisted (draw "
                "35's image reads 71.8 at 1.0e-15, against a first-order 35, in rounding steps "
                "of about 39). Its two misses "
                "are old-scale baselines above 64 (draw 77's image charge, draw 35's charges), "
                "which only the new scale settles. D2's net charge increment is 1.9-3.5e-13 C "
                "in magnitude, so no case is electroneutral. The engine's own event checks "
                "refuse it from 5.6e-11 to 3.2e-9: the plate-charge check in 9 of the 10 "
                "near-zero draws (5.6e-11-3.2e-10), the isopotential check in the two fixed "
                "cases (3.2e-9) and in spread 3 draw 32 (1.0e-10)",
                "the mismatch-scale control (old scale, protocol-dev-s5a28) is caught on the "
                "charges at 3.2-5.6e-13 in 11 of 12 cases and on the potentials at "
                "1.8e-14-1.0e-13 in 5; its misses are old-scale baselines above 64 (draw 35's "
                "charges, seven near-zero draws' potentials). The event map refuses it from "
                "3.2e-9 to 1.8e-7, by its isopotential check in every case",
                "the construction checks hold in all 12 cases (protocol-dev-s5a28): at delta = "
                "0 the non-conservation construction reproduces the engine's event in every "
                "field, bit for bit; the re-applied event checks pass the event; and they "
                "agree with the event map's verdict and booked image at every delta of the "
                "mismatch-scale ladder",
                "the engine does not output delta q or delta separately: the transference "
                "control reaches them through the increments and moved amounts (caught at "
                "1.0-1.8e-13 old scale); free-energy changes are observed only within W",
                "no charge-conserving defect reaches the image charge, zero in exact "
                "arithmetic for an isopotential split: neither the map defects nor the mismatch "
                "scale (above); the non-conservation control does (above)",
                "at the old scale the near-zero cases' undefected potentials (and draw 35's "
                "charges and draw 77's image charge) exceed 64, so those families read "
                "'baseline above 64' there; where "
                "measurable the parent charge is caught on the charges at 3.2e-16-5.6e-15",
            ],
            "new_scale_findings": [
                "both scales from the merged head's snapshot (protocol-dev-s5a32, d8a0979; the "
                "seen sets only, the judged sets not run). The old scale (charge_term=False) is "
                "bit-identical to protocol-dev-s5a28's, before R-ops' amendment",
                "every comparison at the new scale is within 64: the fixed cases 0.25-0.39; "
                "the simultaneous divisions 0.058 and 0.23; the seen sets' worst ratios "
                "symmetric 0.21, 0.23, 0.21 and asymmetric 1.27, 1.40, 1.51 (spreads 0.1, 1, "
                "3; admitted 200, 148, 59). The asymmetric sets' 9.06, 860.56 and 152.62 at the "
                "old scale become 1.27, 1.40 and 1.51",
                "the near-zero cases pass undefected at the new scale (any key 0.59-1.51, "
                "against 10.6-861 at the old), and each fails with every control's defect at "
                "1e-9 in at least one family",
                "the controls at the new scale, smallest defect caught per target over the 12 "
                "cases: a_k charges 1e-13-1.8e-10; parent charge charges 1.8e-13-3.2e-12 and "
                "potentials 5.6e-14-3.2e-13; f amounts 1.8e-14; transference amounts "
                "1.8e-13-1.8e-10; W work 5.6e-13; mismatch scale charges 1e-12-1.8e-9 and "
                "potentials 1.8e-13-1e-10; non-conservation image 1e-12-5.6e-12, charges "
                "1e-12-1e-11 and amounts 1e-13-5.6e-13. The construction checks hold in all 12 "
                "cases; the engine's refusal sizes are the old scale's",
                "a finding for the lead: one target misses 1e-9 at the new scale. The mismatch "
                "scale's charges in seen spread 1 draw 35 read 63.05 at delta = 1e-9 "
                "(charge_D1_C; D2 53.6) and are caught at 1.78e-9; its potentials, also a "
                "target, read 718. Target and threshold unchanged. So the frozen rule's "
                "preview verdict on the seen sets (not the judged verdict) fails, on that "
                "entry alone; the third amendment followed (negative_controls.third_amendment, "
                "preview_verdicts)",
                "the mechanism: on the charges the mismatch scale is the a_k control at "
                "|a - f| = 0.15 strength (their ratio at 1e-9 is 0.1499-0.1501 in all ten "
                "near-zero draws). Both move charge in proportion to the patch charges, which "
                "vanish with the parent potential; A.8's term (the anchor and the increments' "
                "content) does not. In draw 35 (V_P = -0.63 mV, the seen sets' nearest to 0 V) "
                "a 1e-9 defect moves 1.54e-24 C against 64 eps x M_D1 = 1.57e-24 C (M_D1 = "
                "1.10e-10 C, its charge -6.2e-15 C; probe/q2_draw35_keys-s5a32.json). At that "
                "draw a_k's margin is 6.6 and transference's 6.8 (amounts); the parent charge, "
                "scaled by the declared charge, keeps 3.2e4",
                "recurrence: one such draw among the 207 admitted at spreads 1 and 3",
                "the third amendment's snapshot (protocol-dev-s5a34, 1b2cfd6) reproduces "
                "protocol-dev-s5a32 apart from the first-order records, and the worktree run "
                "q2-dev-15 exactly. Its first-order check: in all ten near-zero cases each "
                "target of a_k, the mismatch scale and transference reads 0.99974-1.00040 of "
                "its first-order size at 1e-9, and the fixed cases 1.00000 "
                "(development_new_scale). Its preview verdicts: the frozen rule fails, on draw "
                "35's mismatch-scale charges alone; the third amendment's rule passes "
                "(preview_verdicts)",
                "protocol-dev-s5a32's near_zero_set.json holds new-scale ratios under "
                "old_scale_potential_ratio: the probe (unedited) calls R-ops at its default, "
                "now the new scale. q2_near_zero stays at protocol-dev-s5a28",
            ],
            "before_the_freeze": dict(
                where("q2_before_freeze"),
                note="the same cases and seen sets at the old scale (fixed 0.39; simultaneous "
                "0.088 and 0.33; symmetric 0.81, 0.93, 0.68; asymmetric 9.06, 860.56, 152.62), "
                "with the earlier controls (a_k and |Q_P|-scaled parent charge only)",
            ),
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
            "circuit_world": {
                "accepted": "the lead, 14 November",
                "changes": [
                    "every membrane permeability x 100: each patch keeps its reversal "
                    "potential, and the membrane time constant goes from about 1.5 s to 15 ms, "
                    "so the limit is reached in a short run",
                    "no insertion after the division: the geometry holds still",
                    "the access face's area 1.5e-13 m^2: its resistance comparable with a furrow's",
                ],
                "base": "S5's compact furrow world (cleft_divided, symmetric, passive)",
            },
            "development": dict(where("q4_tests"), **q4()),
        },
        "Q5": {
            "claim": "The observed order is about 2 after partitions.",
            "driver": "validation/division/q5_order.py at 0.5, 0.25 and 0.125 ms",
            "reported_not_banded": "the observed orders are reported (S3's registered form); "
            "only the stop rules are judged (the lead, 14 November)",
            "measurable": "a component whose two step terms, |q(0.5) - q(0.25)| and "
            "|q(0.25) - q(0.125)|, both lie above Q3's floor, 64 eps x the quantity's scale "
            "(its largest |value| over every component, record and step), defined before the "
            "judged run; the lumen volumes fall outside it",
            "stop_rules": [
                "every measurable component's step term decreases from the (0.5, 0.25 ms) "
                "pair to the (0.25, 0.125 ms) pair",
                "a quantity that does not converge stops the run for a report",
            ],
            "dropped_band": "a band of [1.8, 2.3] was proposed after the development orders "
            "(1.99 to 2.06) had been seen, and is dropped",
            "bridge_coupling_offset": "the split injection's offset of the bridge's fast mode "
            "has observed order 2.3 to 2.6 (bridge_coupling_order.py); a higher order is not a "
            "defect, and it is reported as it is",
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
                "(a) the 19-cell heredity sheet padded to the 64-node cap (32 + 32 slots) with "
                "idle division operators, bitwise against the same sheet without them; one slot "
                "past the cap refused (test_division_idle_sheet_runs.py): built",
                "(b) S3's cleft egg on insertion@2 and lumen@2: deferred (design decision 24). "
                "Its gate is a registered operator variant in S3's protocol family, with a J1 "
                "judge entry point whose default is today's path and S3's registered readings "
                "shown bitwise unchanged",
                "crossrev: every existing set identical, S5's own set recorded (crossrev-s5a11, "
                "crossrev-s5a10-division; the lead's renewed baseline of record at the landing "
                "tree covers all five sets): built",
            ],
            "acceptance_list_change": "until (b) passes, insertion@2 and lumen@2 are qualified "
            "in division worlds only, and S3's egg stays on insertion@1 and lumen@1 (the lead "
            "tells the user)",
            "development": dict(q7a=passed("q7a")),
        },
        "Q8": {"claim": "Each refusal, with its message.", "as_built": "the S5 tier-1 files"},
        "Q9": {
            "claim": "Closed slots are @3 padding at the view; the lumen's padded-slot test.",
            "as_built": "test_partition.py, test_restricted_lumen_v2.py",
        },
        "Q10": {
            "claim": "Sensitivity to the partition time and to a_0 (design §4.2).",
            "driver": "validation/division/q10_sensitivity.py",
            "reported_not_judged": "the lead, 14 November",
            "dt_s": 2.5e-4,
            "nominal": "t_p 2 ms, a_0 1x, the bridge closing linearly over 2 ms: it is open "
            "from 2 to 4 ms and the current flows from 3 ms, so the nominal exchange is not "
            "zero against zero; every arm runs one parameter at a time against the nominal",
            "noise_floor": "per world and quantity, 3 x the nominal's step term |Q(0.25 ms) - "
            "Q(0.125 ms)|, or 64 eps x the quantity's largest |value| where that is larger; a "
            "change below it is reported as within noise",
            "development": dict(
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
