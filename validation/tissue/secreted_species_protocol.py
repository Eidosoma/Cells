"""D150 version 1's qualification protocol: its draft from disclosed runs, its guard, its judge.

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §6, §7 and §12, with the lead's rulings of 13 and 14
November. The protocol (validation/tissue/secreted_species_protocol.json) is PROPOSED: drafted here
from the development runs named beside its numbers, for the lead's review with the advisor. Only
the lead registers it, and registration changes its status alone.

* judged_run_refusal / registered: the judge's first call. Before anything is computed or written,
  it refuses an unregistered protocol and a source that is not a clean execution snapshot
  (validation/source_snapshot.py), as S3's and S5's judges do.
* draft DEVELOPMENT_DIR OUTPUT_JSON: the protocol from a development run's analysis.json
  (validation/tissue/secreted_species_analysis.py), every tolerance computed from it.
* judge OUT (python -m validation.tissue.secreted_species_qualification judge OUT): the judged and
  order arms, once, from a clean snapshot of main, against the frozen tolerances. It refuses an
  existing OUT, since every attempt writes its own directory (S5's attempt rule).

Usage: python -m validation.tissue.secreted_species_protocol draft DEVELOPMENT_DIR OUTPUT_JSON
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "validation/tissue/secreted_species_protocol.json"
STATUS = (
    "PROPOSED (drafted 14 November 2026 from the development runs named beside its numbers, for "
    "the lead's review with the advisor; not registered, and no judged run is made before the "
    "lead registers it)"
)
JUDGED_ARMS = ("dr2.5_dt1", "rk4_dr2.5_dt0.1")
ORDER_ARMS = ("dr5_dt0.5", "dr2.5_dt0.5", "dr1.25_dt0.5", "dr2.5_dt0.25")
TIME_ORDER = ("dr2.5_dt1", "dr2.5_dt0.5", "dr2.5_dt0.25")
EVIDENCE = "/mnt/workspaces/Cells/secreted-species-v1-20261114-01"
FINDINGS = (  # Disclosed with the draft: what the development runs showed before any registration.
    "Two development runs. The first (qualification-dev-dc2e494, the arms from the clean snapshot "
    "of dc2e494) and the second (qualification-dev-a7e1869, after the radial builder's exact "
    "areas were restored bitwise; the tolerances here are the second's) agree: every fraction of "
    "tolerance within 0.001; the dt study's tolerances within 1.2e-5 (IMEX) and 1.3e-3 (RK4, at "
    "step terms of 5e-18 mM, about 1e3 times their own rounding) relative, Q2's within 1.4e-9, "
    "the splitting term's identical",
    "The species crossrev from the clean snapshot of 8d94451 found the radial world's bindings "
    "changed against its first record (b102da4): face factors by up to 2 ulp and anchors by up "
    "to 5, from a regrouping of 4 pi r_a r_b at dc2e494. Restored at a7e1869: 24/24 jaxpr texts, "
    "24/24 constants and 8/8 bindings identical, its check holding "
    f"({EVIDENCE}/crossrev/species/compare-a7e1869-vs-b102da4.txt)",
    "Three step-term definitions compared on the first run's arms "
    f"({EVIDENCE}/qualification-dev-dc2e494/step_term_compare.json): per element (S5's form) "
    "the controls catch k and D in error by 5e-10 and 5e-9 (IMEX), 1e-12 and 1e-11 (RK4); in the "
    "max norm per record 1e-3 (IMEX) and 5e-6 (RK4); the splitting term as the step term (max "
    "norm) 1e-3 and 2e-3, 5e-6 and 1e-5. The step map's exact fixed point used per element is no "
    "step term: the far field is transient (180 times its tolerance at 0.5 s)",
    "The first analysis judged Q3's stop rule on the errors against R-continuum "
    f"({EVIDENCE}/qualification-dev-dc2e494/analysis-v1-per-element.json): the clearance's "
    "error changes sign from 5 to 2.5 um at 0.25 s and grows there. Successive differences "
    "element by element then failed at one coarse shell of 120, where the spatial error changes "
    "sign; hence successive differences in the max norm (Q3.why_the_max_norm)",
    "A preview verdict (S5's precedent: the judge's code on copies of the development arms, the "
    f"guard bypassed in-process; {EVIDENCE}/qualification-dev-a7e1869-preview/verdict.json): "
    "every item passes. It is no verdict",
)
GUARD_TESTS = (
    "tests/unit/test_species_turnover.py",
    "tests/unit/test_species_exchange.py",
    "tests/unit/test_secreted_species.py",
    "tests/unit/test_secreted_species_closed_forms.py",
    "tests/unit/test_secreted_species_judged_refusal.py",
    "tests/unit/test_secreted_species_runs.py",
    "tests/unit/test_secreted_species_ions.py",
    "tests/unit/test_secreted_species_guards.py",
)


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged run may not start (None: it may): an unregistered protocol, or a source that is
    not a clean execution snapshot, as S3's and S5's judges refuse them."""
    status = protocol.get("status")
    if not (isinstance(status, str) and status.startswith("registered")):
        return "the D150 v1 protocol is not registered (its status does not begin 'registered')"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot of main, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def registered(protocol_path=PROTOCOL, root=ROOT):
    """The protocol, or SystemExit("Refused: ...") unless it is registered and the source clean."""
    protocol = json.loads(Path(protocol_path).read_text())
    refusal = judged_run_refusal(protocol, root)
    if refusal:
        raise SystemExit("Refused: " + refusal)
    return protocol


# ------------------------------------------------------------------ the judge


def _within(error, tolerance):
    error, tolerance = np.asarray(error, dtype=float), np.asarray(tolerance, dtype=float)
    if error.shape != tolerance.shape:
        raise SystemExit(f"Refused: records {error.shape} do not match the protocol's")
    return dict(passed=bool(np.all(error <= tolerance)), worst=float(np.max(error / tolerance)))


def judge(out, protocol_path=PROTOCOL, root=ROOT):
    """The judged run (module docstring): refused first; then the judged and order arms, once."""
    protocol = registered(protocol_path, root)
    out = Path(out)
    if out.exists():
        raise SystemExit(
            "Refused: the output directory exists; every attempt writes its own (the attempt rule)"
        )
    from validation.tissue import secreted_species_analysis as analysis
    from validation.tissue import secreted_species_qualification as qualification

    qualification.develop(out, (*JUDGED_ARMS, *ORDER_ARMS))
    arms = analysis.load(out)
    refused = sorted(k for k, v in arms.items() if "refused" in v)
    items = {}
    for key, arm, _ in analysis.Q1_ARMS:
        if arm in refused:
            items[key] = dict(passed=False, reason=f"arm {arm} refused")
            continue
        entry = protocol["Q1"]["arms"][arm]
        error = analysis.q1_errors(arms[arm])
        dt_study = _within(error, entry["dt_study"]["tolerance_mM"])
        split = _within(analysis.norm(error), entry["splitting_term"]["tolerance_mM"])
        items[key] = dict(
            passed=dt_study["passed"] and split["passed"],
            dt_study=dt_study,
            splitting_term=split,
            error_max_norm_mM=analysis.norm(error).tolist(),
        )
    if "dr2.5_dt1" in refused:
        items["Q2"] = dict(passed=False, reason="arm dr2.5_dt1 refused")
    else:
        errors = analysis.q2_errors(arms["dr2.5_dt1"])
        q2 = {
            k: _within(errors[k], v["tolerance"]) for k, v in protocol["Q2"]["quantities"].items()
        }
        items["Q2"] = dict(passed=all(v["passed"] for v in q2.values()), quantities=q2)
    orders = analysis.orders(arms)
    stops = [v["every_difference_decreases"] for part in orders.values() for v in part.values()]
    items["Q3"] = dict(
        passed=len(stops) == protocol["Q3"]["stop_rule_count"] and all(stops),
        orders=orders,
        note="the orders reported; the stop rules on successive differences judged",
    )
    verdict = dict(
        protocol_id=protocol["id"],
        protocol_status=protocol["status"],
        source=qualification.source_identity(),
        refused_arms=refused,
        items=items,
        passed=not refused and all(v["passed"] for v in items.values()),
        q5="judged separately: the guard tests at the judged snapshot (Q5's judge entry)",
    )
    (out / "verdict.json").write_text(json.dumps(verdict, indent=1, default=float) + "\n")
    print(json.dumps({k: v["passed"] for k, v in items.items()} | {"passed": verdict["passed"]}))
    return verdict


# ------------------------------------------------------------------ the draft


def _q1_arm(x, arms, name):
    width, dt, solver, faces, end = arms[name]
    d, s, p = x["dt_study"], x["splitting_term"], x["predictions"]
    return dict(
        grid=dict(width_m=width, dt_s=dt, solver=solver, faces=faces, end_s=end),
        records_s=x["records_s"],
        scale_mM=x["scale_mM"],
        floor_mM=x["floor_mM"],
        dt_study=dict(
            step_term_arm=x["step_arm"],
            tolerance_mM=d["tolerance_mM"],
            elements_at_floor=d["elements_at_floor"],
            development_fraction_max=d["fraction_max"],
            development_fraction_by_record=d["fraction_by_record"],
            control_smallest_relative_error_caught=d["control_smallest_relative_error_caught"],
        ),
        splitting_term=dict(
            formula_first_shell_mM=s["formula_first_shell_mM"],
            tolerance_mM=s["tolerance_mM"],
            development_fraction_max=s["fraction_max"],
            development_fraction_by_record=s["fraction_by_record"],
            control_smallest_relative_error_caught=s["control_smallest_relative_error_caught"],
        ),
        predictions_reported=p,
    )


def draft(development, output):
    """The PROPOSED protocol from a development run's analysis (DEVELOPMENT/analysis.json)."""
    from validation.tissue import secreted_species_qualification as q

    development = Path(development)
    a = json.loads((development / "analysis.json").read_text())
    if a["refused"]:
        raise SystemExit(f"Refused: the development run has refused arms {sorted(a['refused'])}")
    named = dict(
        path=str(development / "analysis.json"),
        arms=str(development),
        arms_snapshot_revision=a["arms_source"]["git_revision"],
        arms_patch_sha256=a["arms_source"]["patch_sha256"],
        analysis_source=a["analysis_source"],
        drafted_by=q.source_identity(),
    )
    stop_rule_count = len(a["Q3"]["space"]) + len(a["Q3"]["time"])
    protocol = dict(
        kind="cells.secreted_species_v1_protocol@1",
        id="d150-v1-held-sphere",
        title=(
            "D150 v1: scheduled_species_turnover@1's clearance with resolved_pump_tissue@3's face "
            "law in resolved_pump_composite@1, against the exact discrete solution and the held "
            "sphere's continuum closed forms"
        ),
        status=STATUS,
        engine_models=[
            "resolved_pump_composite@1",
            "resolved_pump_tissue@3",
            "scheduled_species_turnover@1",
            "scheduled_species_exchange@1 (Q5's guards of record)",
        ],
        references={
            "R-discrete": (
                "validation/tissue/secreted_species_radial.py solution: each arm's own declared "
                "finite-volume system (the same faces, volumes, clearance and baths), solved "
                "exactly by the matrix exponential"
            ),
            "R-continuum": (
                "validation/tissue/secreted_species_closed_forms.py HeldSphere: the finite-domain "
                "solution of the held sphere with first-order decay through v = r u, its steady "
                "state plus a finite sum of sine modes, every quantity an exact integral (the "
                "shells' averages, the amount, the two baths' supplies and the clearance); "
                "tests/unit/test_secreted_species_closed_forms.py checks it against quadrature and "
                "its own mass balance"
            ),
            "independence": (
                "both NumPy, written from the design's Appendix A, never from engine code; neither "
                "takes measured data or fits anything (D151)"
            ),
        },
        world=dict(
            builder="validation/tissue/secreted_species_radial.py world (faces 'exact')",
            driver="validation/tissue/secreted_species_qualification.py (ARMS, arm_world)",
            radius_m=q.R,
            outer_m=q.OUTER,
            diffusivity_m2_per_s=q.D,
            clearance_per_s=q.K,
            lambda_m=(q.D / q.K) ** 0.5,
            c0_mM=q.C0,
            trace_mM=q.TRACE,
            start=(
                "the steady state plus two positive sine modes of v (index, amplitude in mM m): "
                f"{[list(m) for m in q.MODES]}; each shell starts at its exact average"
            ),
            records_s=list(q.RECORDS),
            rk4_records_s=list(q.RK4_RECORDS),
            faces=(
                "each face declared with the exact spherical-shell conductance between the points "
                "it joins, area 4 pi r_a r_b over length r_b - r_a (the lead's requirement on "
                "radial builders, §11.5 item 8)"
            ),
            regime=(
                "kt 0.25 to 4 at the records, R / lambda = 0.5, the medium out to 6 lambda: the "
                "first calibration target's non-dimensional regime (kt below 1, profiles over a "
                "few lambda; §6), compressed in time (k = 1/s; §4.5)"
            ),
            ions=(
                "quiescent: no pump or channel, zero membrane permeability and zero ion face "
                "diffusivity (the species-only world)"
            ),
            arms={
                k: dict(zip(("width_m", "dt_s", "solver", "faces", "end_s"), v, strict=True))
                for k, v in q.ARMS.items()
            },
            judged_arms=list(JUDGED_ARMS),
            order_arms=list(ORDER_ARMS),
            development_only_arms=["rk4_dr2.5_dt0.05", "planar_dr2.5_dt1"],
        ),
        rules=dict(
            tolerances=(
                "every tolerance number is computed from the development run named beside it "
                "(validation/tissue/secreted_species_protocol.py draft); development runs are not "
                "judged"
            ),
            judged_run=(
                "once, after registration, from a fresh clean execution snapshot of main "
                "(validation/source_snapshot.py, no dirty patch), through scripts/run_detached.sh. "
                "A failure is recorded and diagnosed, never retuned"
            ),
            attempts=(
                "an attempt killed by infrastructure before its verdict is written (an "
                "out-of-memory kill, a unit stopped by the slice, a host crash) is not a verdict. "
                "It is recorded with its logs and partial outputs and rerun once from the same "
                "snapshot; each attempt writes its own output directory, since the judge entry "
                "refuses an existing one. A second infrastructure kill goes to the lead, as does "
                "any other ending without a verdict. A run that has written its verdict is final "
                "(S5's rule). An arm the engine refuses is a verdict: its items fail"
            ),
            resolved_start=(
                "every judged arm runs through the runner with every host check, from a pre-formed "
                "profile (the lead's ruling 5) that meets both boundary conditions at t = 0. A "
                "switch-on from the trace is no judged arm: the host energy ledger refuses an "
                "unresolved onset (§11.4). A ramped source is inadmissible until a probe "
                "measures it"
            ),
            guard_world=(
                "the species-only world: the ions quiescent, so the energy bound is the species' "
                "own (§7)"
            ),
            guards_of_record=(
                "energy: RK4 for the face heat and the operators' work (the radial and face-free "
                "worlds, the absolute bound 2e-8 pJ; tests/unit/test_secreted_species_guards.py, "
                "test_secreted_species_runs.py), and a NumPy dG test per law (Decimal, 50 digits; "
                "tests/unit/test_species_turnover.py, test_species_exchange.py). The IMEX bound is "
                "blind to the species' bookings in mixed worlds and coarse in species-only ones, "
                "so it is no guard of record (§12.1)"
            ),
            judge_entries=dict(
                guard=(
                    "validation/tissue/secreted_species_protocol.registered, the judge's first "
                    "call: it refuses an unregistered protocol and a source that is not a clean "
                    "execution snapshot before anything is computed or written; "
                    "tests/unit/test_secreted_species_judged_refusal.py tests it on edited copies"
                ),
                Q1_Q2_Q3="python -m validation.tissue.secreted_species_qualification judge OUT",
                Q5=(
                    "python -m pytest on Q5's test files from the judged snapshot, through "
                    "scripts/run_detached.sh"
                ),
            ),
            development_runs=dict(
                closed_form=named,
                splitting_bias_m2=(
                    "/mnt/workspaces/Cells/secreted-species-v1-20261114-01/splitting_bias.json "
                    "(milestone 2: the formula verified against the step map's fixed point)"
                ),
            ),
        ),
        Q1=dict(
            claim=(
                "The engine integrates the declared finite-volume system in time to its step term, "
                "and that step term is the clearance splitting's: the judged arms against "
                "R-discrete"
            ),
            records="each arm's records after t = 0",
            quantity="each shell's |engine - R-discrete| (mM)",
            dt_study_rule=(
                "S5's form, per shell and record: the step term |q(dt) - q(dt/2)| on the same "
                "grid; tolerance 3 x the step term, or the floor 64 eps x the scale (the largest "
                "concentration over the arm's records, the engine's at the judged step) where that "
                "is larger"
            ),
            splitting_term_rule=(
                "the lead's milestone-3 instruction, per record in the max norm over shells: the "
                "step term dt^2 k (g - k c_ss) / 4 under ARS(2,2,2) and / 12 under RK4 (§12.1), "
                "with g the source face's kappa c0 / V0 and c_ss the declared system's steady "
                "state, at the first shell, which carries the error; tolerance 3 x (|term| + the "
                "floor). The term is the leading order of the composite step's steady bias: the "
                "split scheme's first shell runs low by it"
            ),
            verdict_rule="pass when both rules hold at every record, for both arms",
            predictions=(
                "reported, not judged: the step map's exact fixed point (the steady bias in full) "
                "and the step map iterated in NumPy (ARS's explicit stages or RK4's polynomial, "
                "the clearance's exact half-steps around them), whose distance from R-discrete "
                "predicts the engine's error at every shell and record"
            ),
            controls=(
                "development only: references with the clearance or diffusivity in error by a "
                "relative delta (1e-14 to 0.5); the smallest delta each rule catches, with "
                "[record, shell] or [record] where"
            ),
            development="rules.development_runs.closed_form",
            arms={
                "dr2.5_dt1": _q1_arm(a["Q1_imex"], q.ARMS, "dr2.5_dt1"),
                "rk4_dr2.5_dt0.1": _q1_arm(a["Q1_rk4"], q.ARMS, "rk4_dr2.5_dt0.1"),
            },
        ),
        Q2=dict(
            claim=(
                "The engine solves the held sphere with first-order decay to its spatial and "
                "temporal step terms: the judged IMEX arm (2.5 um, 1 ms) against R-continuum"
            ),
            records_s=a["Q2"]["records_s"],
            quantities_described=dict(
                coarse=(
                    "each 5 um shell's average (24), aggregated exactly from the grid's shells (mM)"
                ),
                amount_fmol="the amount in the medium",
                source_supplied_fmol="the source bath's cumulative supply",
                outer_supplied_fmol="the outer bath's cumulative supply (negative: it absorbs)",
                cleared_fmol="the cumulative clearance",
            ),
            spatial_step_term_rule="|q(2.5 um) - q(1.25 um)| at 0.5 ms, per element and record",
            time_step_term_rule="|q(1 ms) - q(0.5 ms)| at 2.5 um, per element and record",
            reference_term_rule="64 eps x the quantity's scale (the closed form is exact)",
            tolerance_rule="3 x (spatial + time + reference) per element and record",
            verdict_rule="pass when every element's |engine - R-continuum| is within its tolerance",
            control=(
                "development only: the probes' planar faces (arm planar_dr2.5_dt1) against the "
                "same tolerances"
            ),
            development="rules.development_runs.closed_form",
            quantities={
                k: dict(
                    scale=v["scale"],
                    reference_term=v["reference_term"],
                    tolerance=v["tolerance"],
                    development_fraction_max=v["fraction_max"],
                    development_fraction_by_record=v["fraction_by_record"],
                    development_largest_time_over_largest_spatial=v[
                        "largest_time_over_largest_spatial"
                    ],
                    development_planar_control_fraction_max=v.get("planar_control_fraction_max"),
                )
                for k, v in a["Q2"]["quantities"].items()
            },
        ),
        Q3=dict(
            claim="The observed orders are about 2 in space and in time",
            driver="the judge's order arms",
            arms=dict(space=["dr5_dt0.5", "dr2.5_dt0.5", "dr1.25_dt0.5"], time=list(TIME_ORDER)),
            reported_not_banded=(
                "the observed orders are reported (S3's and S5's registered form); only the stop "
                "rules are judged"
            ),
            difference=(
                "per quantity and record, the largest |q(h) - q(h/2)| over the quantity's elements "
                "(the shells or the 24 coarse shells; a scalar is its own)"
            ),
            measurable=(
                "a quantity at a record whose two successive differences both lie above 64 eps x "
                "its scale (the largest |value| over every element, record and arm), defined "
                "before the judged run"
            ),
            stop_rules=[
                "every measurable difference decreases from the (5, 2.5 um) pair to the (2.5, "
                "1.25 um) pair, at 0.5 ms (the coarse shells and the four scalars)",
                "every measurable difference decreases from the (1, 0.5 ms) pair to the (0.5, "
                "0.25 ms) pair, at 2.5 um (the shells and the four scalars)",
                "a quantity that does not converge stops the run for a report",
            ],
            stop_rule_count=stop_rule_count,
            why_the_max_norm=(
                "a development finding: element by element (S5's Q5 wording, written for scalar "
                "components), one of the 120 coarse-shell differences in space does not fall: "
                "coarse shell 19 at 2 s, where the spatial error changes sign (-9.6e-9 to +1.6e-8 "
                "of c0 across shells 18 and 19). There the difference's leading term vanishes and "
                "the next need not fall (its first difference is 1.2e-6 of that record's largest), "
                "while the element's errors against R-continuum fall (2.2e-11, 1.6e-11, 4.6e-12 "
                "mM). A monotonicity test per element of a sign-changing field is ill-posed at the "
                "crossing, so the rule takes the max norm; the per-element count is reported "
                "(development, per_element_reported). Q1's and Q2's tolerances stay per element: "
                "a magnitude bound is not ill-posed there, and every element passes"
            ),
            why_differences=(
                "an error against R-continuum can change sign between grids: the clearance's at "
                "0.25 s does from 5 to 2.5 um, so it grows there while the differences decrease. "
                "The errors' orders against R-continuum are reported beside the stop rules"
            ),
            development=a["Q3"],
        ),
        Q4=dict(
            claim="The switch-on against the Danckwerts form near the source",
            judged=False,
            reason=(
                "pre-formed starts only (the lead's ruling 5): a switch-on cannot pass the host "
                "energy ledger (§11.4), so it would run through the checked step map without the "
                "runner's host checks, and the infinite-medium form differs from the finite "
                "domain's at the outer bath"
            ),
            record=(
                "probe 4 (§11.3 (b)): through the checked step map, 2.5 um, 1 ms, 2,000 steps, no "
                "step refused; 8.6e-7 to 4.2e-9 of c0 from the exact discrete solution at 0.25 to "
                "2 s, and its gap from the Danckwerts form approaches the smooth start's"
            ),
        ),
        Q5=dict(
            claim="The guards of record hold at the judged snapshot",
            tests=list(GUARD_TESTS),
            covers=[
                "the energy guards of record: RK4 for the face heat (test_secreted_species_guards) "
                "and for the operators' work (test_secreted_species_runs), and the NumPy dG test "
                "per law (test_species_turnover, test_species_exchange)",
                "the definition-time refusals, the occupant rule, the donor copies, the species "
                "cap and the stationary refusal (test_species_turnover, test_species_exchange, "
                "test_secreted_species)",
                "the ion rows bitwise with the operators active (test_secreted_species_ions)",
                "the closed forms' own checks and the judged-run refusal",
            ],
            verdict_rule="pass when every test in these files passes",
        ),
        open_questions=[
            "The step term: Q1 judges both the dt study per shell (S5's form, the tolerances "
            "pinned from the dt study) and the splitting term per record (the instruction's). Keep "
            "both, or one? The formula is leading order: 9.4% below the step map's fixed point "
            "under ARS at dt K_ii 0.19, 0.4% under RK4; the fixed point gives the observed "
            "first-shell error to 8e-4 or better (relative). Q2's time term stays the dt study's, "
            "since the formula has no per-element form for the transient far field",
            "The RK4 arm (2.5 um, 0.1 ms, to 0.5 s) as a judged arm of Q1",
            "Q4: the Danckwerts switch-on reported only (probe 4's record), not judged",
            "dr1.25_dt0.5 runs at dt K_ii 0.384, beyond the probed 0.30: it passed every host "
            "check in development; it carries Q2's spatial term and Q3's spatial order",
            "Q3's stop rule in the max norm per quantity and record, where S5's Q5 counted "
            "components (a development finding: per element, one coarse shell of 120, at a sign "
            "change of the spatial error, does not fall)",
            "The step map's agreement with the engine (reported in Q1's predictions) could become "
            "a judged item with a rounding rule (for example n_steps x eps x the scale), decided "
            "before any judged run",
        ],
        development_findings=list(FINDINGS),
    )
    Path(output).write_text(json.dumps(protocol, indent=1, default=float) + "\n")
    print(output)
    return protocol


if __name__ == "__main__":
    action, *args = sys.argv[1:]
    if action == "draft":
        draft(*args)
    else:
        raise SystemExit(f"Unknown action {action!r} (draft)")
