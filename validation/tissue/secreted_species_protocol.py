"""D150 version 1's qualification protocol: its draft from disclosed runs, its guard, its judge.

docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §6, §7 and §12, with the lead's rulings of 13 and 14
November. The protocol (validation/tissue/secreted_species_protocol.json) is PROPOSED: drafted here
from the development runs named beside its numbers and revised after the lead's review with the
advisor (14 November: the controls judged, the scope line, the closed form checked against the PDE,
the step map a tier-2 regression guard outside Q5). Only the lead registers it, and registration
changes its status alone.

* judged_run_refusal / registered: the judge's first call. Before anything is computed or written,
  it refuses an unregistered protocol and a source that is not a clean execution snapshot
  (validation/source_snapshot.py), as S3's and S5's judges do.
* draft DEVELOPMENT_DIR OUTPUT_JSON: the protocol from a development run's analysis.json
  (validation/tissue/secreted_species_analysis.py), every tolerance computed from it.
* judge OUT (python -m validation.tissue.secreted_species_qualification judge OUT): the judged,
  order and control arms, once, from a clean snapshot of main, against the frozen tolerances and
  registered controls; the step map's agreement is reported, not judged. It refuses an existing OUT,
  since every attempt writes its own directory (S5's attempt rule).

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
    "PROPOSED (drafted 14 November 2026 from the development runs named beside its numbers and "
    "revised the same day after the lead's review with the advisor; not registered, and no judged "
    "run is made before the lead registers it)"
)
JUDGED_ARMS = ("dr2.5_dt1", "rk4_dr2.5_dt0.1")
ORDER_ARMS = ("dr5_dt0.5", "dr2.5_dt0.5", "dr1.25_dt0.5", "dr2.5_dt0.25")
TIME_ORDER = ("dr2.5_dt1", "dr2.5_dt0.5", "dr2.5_dt0.25")
CONTROL_ARMS = ("planar_dr2.5_dt1",)  # Q2's judged control (the lead's review).
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
    f"Three step-term definitions compared ({EVIDENCE}/step_term_compare.py: first from the "
    "dirty worktree on the first run's arms, rerun from the clean snapshot of a7e1869 on the "
    f"second's, {EVIDENCE}/qualification-dev-a7e1869/step_term_compare.json, with the same "
    "controls and every fraction within 0.001): per element (S5's form) "
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
    "guard bypassed in-process), first before the lead's review "
    f"({EVIDENCE}/qualification-dev-a7e1869-preview/verdict.json) and again with the judged "
    f"controls after it ({EVIDENCE}/qualification-dev-a7e1869-preview-review/verdict.json): every "
    "item passes, and every control is caught. It is no verdict",
)
REGRESSION_GUARDS = ("tests/unit/test_secreted_species_step_map.py",)  # Tier 2, not judged.
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


def _q1_item(analysis, arm, entry):
    """Q1 for one judged arm: both rules' bounds and their registered controls (k and D)."""
    c = analysis.engine(arm)["concentration"]
    error = np.abs(c - analysis.discrete(arm))
    measures = analysis.q1_measures(c)
    rules = {}
    for rule, measured in (("dt_study", error), ("splitting_term", analysis.norm(error))):
        tolerance = entry[rule]["tolerance_mM"]
        bound = _within(measured, tolerance)
        delta = entry[rule]["control_registered_delta"]
        fractions = analysis.control_fractions(arm, measures[rule], tolerance, delta)
        caught = all(f > 1.0 for f in fractions.values())
        rules[rule] = dict(
            bound=bound,
            control=dict(delta=delta, fractions=fractions, caught=caught),
            passed=bound["passed"] and caught,
        )
    return dict(passed=all(r["passed"] for r in rules.values()), **rules)


def _q2_item(analysis, arms, refused, protocol):
    """Q2: the judged IMEX arm within every tolerance; the planar-face arm, its control, outside
    every quantity's."""
    quantities = protocol["Q2"]["quantities"]
    if "dr2.5_dt1" in refused:
        return dict(passed=False, reason="arm dr2.5_dt1 refused")
    errors = analysis.q2_errors(arms["dr2.5_dt1"])
    bounds = {k: _within(errors[k], v["tolerance"]) for k, v in quantities.items()}
    if "planar_dr2.5_dt1" in refused:
        control = dict(caught=False, reason="arm planar_dr2.5_dt1 refused")
    else:
        planar = analysis.q2_errors(arms["planar_dr2.5_dt1"])
        fractions = {
            k: float(np.max(planar[k] / np.asarray(v["tolerance"], dtype=float)))
            for k, v in quantities.items()
        }
        control = dict(fractions=fractions, caught=all(f > 1.0 for f in fractions.values()))
    passed = all(v["passed"] for v in bounds.values()) and control["caught"]
    return dict(passed=passed, quantities=bounds, planar_control=control)


def judge(out, protocol_path=PROTOCOL, root=ROOT):
    """The judged run (module docstring): refused first; then the judged, order and control arms,
    once."""
    protocol = registered(protocol_path, root)
    out = Path(out)
    if out.exists():
        raise SystemExit(
            "Refused: the output directory exists; every attempt writes its own (the attempt rule)"
        )
    from validation.tissue import secreted_species_analysis as analysis
    from validation.tissue import secreted_species_qualification as qualification

    qualification.develop(out, (*JUDGED_ARMS, *ORDER_ARMS, *CONTROL_ARMS))
    arms = analysis.load(out)
    refused = sorted(k for k, v in arms.items() if "refused" in v)
    items, reported = {}, {}
    for key, arm, _ in analysis.Q1_ARMS:
        if arm in refused:
            items[key] = dict(passed=False, reason=f"arm {arm} refused")
            continue
        items[key] = _q1_item(analysis, arms[arm], protocol["Q1"]["arms"][arm])
        reported[f"{key}_step_map"] = analysis.step_map_agreement(arms[arm])
    items["Q2"] = _q2_item(analysis, arms, refused, protocol)
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
        reported_not_judged=reported,
        q5="judged separately: the guard tests at the judged snapshot (Q5's judge entry)",
    )
    (out / "verdict.json").write_text(json.dumps(verdict, indent=1, default=float) + "\n")
    print(json.dumps({k: v["passed"] for k, v in items.items()} | {"passed": verdict["passed"]}))
    return verdict


# ------------------------------------------------------------------ the draft


def _q1_arm(x, arms, name):
    width, dt, solver, faces, end = arms[name]
    d, s, p = x["dt_study"], x["splitting_term"], x["predictions"]

    def control(rule):
        return dict(
            control_registered_delta=rule["control_registered_delta"],
            development_control_fractions_at_registered_delta=rule[
                "control_fractions_at_registered_delta"
            ],
            development_control_smallest_relative_error_caught=rule[
                "control_smallest_relative_error_caught"
            ],
        )

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
            **control(d),
        ),
        splitting_term=dict(
            formula_first_shell_mM=s["formula_first_shell_mM"],
            tolerance_mM=s["tolerance_mM"],
            development_fraction_max=s["fraction_max"],
            development_fraction_by_record=s["fraction_by_record"],
            **control(s),
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
    for key in ("Q1_imex", "Q1_rk4"):
        for rule in ("dt_study", "splitting_term"):
            caught = a[key][rule]["control_fractions_at_registered_delta"]
            if caught is None or min(caught.values()) <= 1.0:
                raise SystemExit(f"Refused: {key}'s {rule} control is not caught in development")
    planar = [v.get("planar_control_fraction_max") for v in a["Q2"]["quantities"].values()]
    if None in planar or min(planar) <= 1.0:
        raise SystemExit("Refused: the planar control does not fail every Q2 quantity")
    fixed = {
        k: a[k]["predictions"]["fixed_point_over_first_shell_error_minus_1_by_record"]
        for k in ("Q1_imex", "Q1_rk4")
    }
    maps = {k: a[k]["predictions"]["step_map_agreement"] for k in ("Q1_imex", "Q1_rk4")}
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
        scope=(
            "the lead's review: the judged arms run resolved_pump_tissue@3's faces with exact "
            "radial conductances (4 pi r_a r_b over r_b - r_a between the points each face joins) "
            "and scheduled_species_turnover@1's first-order clearance at every shell, with a "
            "held-bath source (the source bath at c0) and an outer bath at the trace, in "
            "resolved_pump_composite@1. scheduled_species_exchange@1, turnover's production and "
            "the occupant rule enter only through Q5's guard test files. This is design §6's first "
            "acceptance (the held sphere with decay, the finite-domain steady state, the exact "
            "finite-volume solution), so no arm is missing; a qualified statement from this "
            "protocol carries this scope"
        ),
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
                "tests/unit/test_secreted_species_closed_forms.py checks it against the PDE itself "
                "without the builder (the residual of u_t = D lap u - k u by fourth-order "
                "differences, both boundary conditions over time, the start and the steady state "
                "against their sinh forms), against quadrature and against its own mass balance"
            ),
            "independence": (
                "both NumPy, written from the design's Appendix A, never from engine code; neither "
                "takes measured data or fits anything (D151)"
            ),
            "common_mode": (
                "R-discrete shares the builder's declared system, so a builder error would be "
                "common-mode in Q1; Q2 against R-continuum covers it, as its planar control shows "
                "(the lead's review)"
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
            control_arms=list(CONTROL_ARMS),
            development_only_arms=["rk4_dr2.5_dt0.05"],
            disclosures=[
                "dr1.25_dt0.5 runs at dt K_ii 0.384, beyond the probed 0.30; it passed every host "
                "check in development and carries Q2's spatial term and Q3's spatial order "
                "(accepted at the lead's review, with this disclosure)",
            ],
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
                "The engine's time integration of the declared finite-volume system is bounded a "
                "priori by the splitting's leading term (within 3 x it at every record), and lies "
                "within 3 x its own step term (S5's dt study): the judged arms (2.5 um; IMEX at "
                "1 ms, RK4 at 0.1 ms) against R-discrete"
            ),
            what_the_rules_show=(
                "the lead's review: the dt-study rule detects bias, not order. For a second-order "
                "error against an exact reference, 3 x the halving difference puts the pass "
                "fraction near 4/9 (development: "
                f"{a['Q1_imex']['dt_study']['fraction_max']:.3f} IMEX, "
                f"{a['Q1_rk4']['dt_study']['fraction_max']:.3f} RK4); a first-order scheme would "
                "give about 2/3 and still pass, so order is Q3's. The splitting-term rule is the "
                "one judged bound not scaled from the engine's own runs; it is one-sided, so it "
                "bounds the step term and does not identify it. The identification is reported: "
                "the step map's fixed point matches the first shell's error to "
                f"{abs(fixed['Q1_imex'][0]):.1e} (IMEX) and {abs(fixed['Q1_rk4'][0]):.1e} (RK4) "
                f"at the first record, and to {abs(fixed['Q1_imex'][-1]):.1e} and "
                f"{abs(fixed['Q1_rk4'][-1]):.1e} at the last (relative). The judged controls show "
                "that each rule can fail"
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
            verdict_rule=(
                "pass when, for both arms, both rules hold at every record and both rules catch "
                "their registered controls for k and for D"
            ),
            predictions=(
                "reported, not judged: the step map's exact fixed point (the steady bias in full) "
                "and the step map iterated in NumPy (ARS's explicit stages or RK4's polynomial, "
                "the clearance's exact half-steps around them), whose distance from R-discrete "
                "predicts the engine's error at every shell and record. The map's agreement with "
                "the engine is a tier-2 regression guard (regression_guards), not a judged item: "
                "one author wrote both sides"
            ),
            controls=(
                "judged (the lead's review, S5's form): the judged arm's output against R-discrete "
                "with the clearance, and separately the diffusivity, x (1 + delta), at each rule's "
                "and arm's registered delta: 10 x the larger of the smallest deltas that rule "
                "caught for k and for D in development (a 1-2-5 grid from 1e-14 to 0.5; where, as "
                "[record, shell] or [record]). Each rule must catch both: its measure exceeds its "
                "tolerance somewhere"
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
            verdict_rule=(
                "pass when every element's |engine - R-continuum| is within its tolerance and the "
                "planar control fails every quantity's"
            ),
            what_the_rule_shows=(
                "as with Q1's dt study, a pass fraction near 4/9 is structural for second-order "
                "errors (development: 0.44 to 0.47), so the tolerance's power is its judged "
                f"control's: the probes' planar faces exceed it {min(planar):.0f} to "
                f"{max(planar):.0f} times in development"
            ),
            control=(
                "judged (the lead's review): the planar-face arm (planar_dr2.5_dt1: the probes' "
                "faces, area 4 pi r^2 at the edge, otherwise the judged arm) against R-continuum "
                "must fail every quantity's tolerance (its largest fraction above 1)"
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
                "reported only, under the resolved-start rule (rules.resolved_start; the lead's "
                "ruling 5, confirmed at the lead's review): a switch-on cannot pass the host "
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
                "R-continuum's independence check (the lead's review; "
                "test_secreted_species_closed_forms): the closed form against the PDE itself, "
                "without the builder: the residual of u_t = D lap u - k u in spherical form by "
                "fourth-order differences at sample points in r and t, both boundary conditions "
                "over time, the start and the steady state against their independent sinh forms; "
                "and the judged-run refusal",
            ],
            verdict_rule="pass when every test in these files passes",
        ),
        regression_guards=dict(
            judged=False,
            tests=list(REGRESSION_GUARDS),
            step_map=(
                "the step map's agreement with the engine (tests/unit/"
                "test_secreted_species_step_map.py, tier 2): the judged configuration shortened to "
                "500 steps per solver, through the runner, max |engine - map| <= n_steps x eps x "
                "the scale (the largest concentration over the records), the rounding rule fixed "
                "at the lead's review before any judged run. A regression guard for the landing "
                "gates, outside Q5's judged list (the lead, 14 November): one author wrote both "
                "sides, so it carries no qualification verdict, and at its 3 x margin on RK4 a "
                "rounding-level platform change would fail the qualification for the wrong "
                f"reason ({EVIDENCE}/tests/m3-stepmap-af2d2b4/step_map_guard_record.json: 0.041 "
                "(IMEX) and 0.32 (RK4) of the bound at 500 steps). The judged run reports the "
                "full judged arms' ratios, not judged (development: "
                f"{maps['Q1_imex']['fraction_of_bound']:.2g} (IMEX, "
                f"{maps['Q1_imex']['n_steps']} steps) and "
                f"{maps['Q1_rk4']['fraction_of_bound']:.2g} (RK4, {maps['Q1_rk4']['n_steps']} "
                "steps) of the bound)"
            ),
        ),
        review=dict(
            by="the lead with the advisor, 14 November 2026, on the PROPOSED draft at 392c633",
            rulings=[
                "1. Q1 keeps both rules; its claim reads 'bounded a priori by the splitting's "
                "leading term', and the identification is reported (Q1.what_the_rules_show)",
                "2. The RK4 arm is judged, in Q1",
                "3. Q4 (Danckwerts) is reported only, under the resolved-start rule",
                "4. The 1.25 um arm at dt K_ii 0.384 is accepted, with the disclosure "
                "(world.disclosures)",
                "5. Q3's max norm is accepted, with the per-element count reported; both rule "
                "changes stay disclosed (development_findings)",
                "6. The step map's agreement is no judged item (one author wrote both sides): a "
                "guard test with a rounding rule fixed now, reported in the judged run; after the "
                "round, a tier-2 regression guard outside Q5's judged list (regression_guards)",
            ],
            changes=[
                "(a) the controls judged, as S5 did: Q1's k and D controls at a registered delta "
                "per rule and arm; the planar-face arm as Q2's judged control",
                "(b) the scope line (scope)",
                "(c) an independence check on R-continuum: the closed form against the PDE itself "
                "(Q5; test_secreted_species_closed_forms)",
            ],
            after_the_round=[
                "the lead, 14 November, on the review round at 1d96232: the step-map guard out of "
                "Q5's judged list, kept as a tier-2 regression guard so the landing gates catch "
                "drift (regression_guards); the judged run reports the full-arm ratios, not judged",
                "the controls judged at +delta only, one delta per rule and arm: confirmed",
                "the five existing crossrev sets argued unaffected for landing (src/ unchanged); "
                "the rehearsal on main reruns all five and the species set from the clean "
                "snapshot before registration, as S5 did",
            ],
            order_after=(
                "S5's: land on main as PROPOSED, rehearse on main, dry-run every judge entry, "
                "register, then one judged run from a clean snapshot"
            ),
        ),
        reported_in_the_judged_run=dict(
            step_map=(
                "each judged arm's engine against the step map iterated in NumPy: the largest "
                "|engine - map| over the rounding bound n_steps x eps x the scale, and the "
                "engine's distance from R-discrete over the same bound"
            ),
            orders="Q3's observed orders, beside its judged stop rules",
        ),
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
