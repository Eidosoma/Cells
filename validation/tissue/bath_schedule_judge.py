"""fr10-dose-schedule-v1's judge: it reads records and never runs (FR-10, D216).

The protocol is validation/tissue/bath_schedule_protocol.json. The judge reads the generator's
records (validation/tissue/bath_schedule_qualification: one results.json per unit), merges the
units (each part in exactly one, all from one source: MG0c's form), derives the metrics below
under the protocol's `judge.derivation`, and evaluates its machine criteria (`judge.criteria`)
with MG0c's evaluator (validation/morphogenesis/mg0a_gradient.evaluate: a missing metric fails its
criterion) into OUT_DIR/verdict.json.

**The arithmetic is FR-4's and FR-5's,** imported read-only from validation/tissue/
compartment_ph_judge.py (the lead's ruling of 17 November 2026; that judge serves two registered
protocols and is never edited): the classes rule for orders with each difference's floor
N eps max|q|, the ladder, the Richardson error (4/3) D(dt, dt/2) at the nominal p = 2, the energy
residual over the integrated flows and its ladder, max-norm differences on shared records,
admission, the merge and its refusals, and compare. That judge keys records by round(t), integer
seconds; FR-10 records every 10 ms, so its parts are passed with their record times in units of
RECORD_UNIT_S (on_record_grid), which leaves every difference, floor and order unchanged.

The FR-10 derivations, fixed before any run:
* **Budgets** (declared first, the lead's ruling): W1's node amounts within B1 = 1e-3 of the step's
  amount (V_node |delta c_b|); W2's V_m within B2 = 1e-3 of |E_K(after) - E_K(before)| at the
  bath's K; W2's cytosol K within C B2 / F, B2 through the owner's capacitor (its charge moves with
  its K alone). Each control differs from its arm's reference by at least 10 x the arm's budget.
* **W3's segments:** each ledger's ratio (|balance| / bound, ratio_LEDGER) before the event
  (t < t_e), at it (the first record at or after t_e) and after it.
* **Records against R-records:** at each event of W1, W2 and W3, the dose's change and the
  free-energy record's change across the event (from the last record before it to the first after
  it) against R-records' dose and delta_G_b, the dose in units of N eps |dose| (rounding) and
  delta_G_b relative.
* **The compensation charge** at rounding of zero at every record of every engine part
  (compensation).
* **K against R-records:** W3's reconciliation term against R-records' K from W3's supply series,
  within the reservoir-work ledger's bound at every record (k_against_reference).
* **Comparisons** (W4, W5): the generator's bit-for-bit results, read as 1 (equal) or 0.
* **Refusals:** a class passes (1) when every representative is refused with the check the
  protocol's refusal_classes names, and every neighbour is admitted and runs.
* **Undefined values are None, never NaN;** a None fails its criterion.

The references part (parts["references"], the FR references agent's, through its adapter) holds
worlds: W1 and W1_floor (record_s and series amount_S_ecs_0, amount_S_ecs_1), W2 and W2_floor
(record_s and series V_wall_cell_0, amount_K_cell_0, amount_Na_cell_0, amount_Cl_cell_0), and
records: {W1, W2, W3: [{time_s, dose_fmol: {species: value}, free_energy_pJ}]}, and K_W3:
{record_s (W3's), series: {K_pJ}}.

Usage:
  python -m validation.tissue.bath_schedule_judge dev PROTOCOL OUT_DIR RESULTS [RESULTS ...]
  python -m validation.tissue.bath_schedule_judge judged PROTOCOL OUT_DIR RESULTS [RESULTS ...]
  python -m validation.tissue.bath_schedule_judge compare RESULTS_A RESULTS_B OUT_JSON
"""

import json
import sys
from pathlib import Path

from validation.morphogenesis.mg0a_gradient import evaluate
from validation.tissue import compartment_ph_judge as base

RECORD_UNIT_S = 0.01
EPS = base.EPS
FARADAY_C_PER_MOL = 6.02214076e23 * 1.602176634e-19  # N_A e, exact SI


def on_record_grid(part):
    """The part with its record times in units of RECORD_UNIT_S (the base arithmetic's keys)."""
    if not isinstance(part, dict) or "record_s" not in part:
        return part
    return dict(part, record_s=[t / RECORD_UNIT_S for t in part["record_s"]])


def flag(value):
    return None if value is None else int(bool(value))


def max_or_none(values):
    return base.max_or_none(list(values))


def _series(part, name):
    return base.series(part, name) if isinstance(part, dict) else None


def segments(part, name, event_s):
    """The largest of a series before an event, at its first record at or after it, and after."""
    s = _series(part, name)
    if s is None:
        return dict(before=None, at=None, after=None)
    t = part["record_s"]
    before = [v for v, x in zip(s, t, strict=True) if x < event_s - 1e-12]
    rest = [(x, v) for v, x in zip(s, t, strict=True) if x >= event_s - 1e-12]
    return dict(before=max(before) if before else None,
                at=rest[0][1] if rest else None,
                after=max(v for _, v in rest[1:]) if len(rest) > 1 else None)


def ledger_maxima(part):
    """Each ledger's largest ratio over the part's records."""
    if not isinstance(part, dict) or part.get("completed") is not True:
        return None
    return {k[len("ratio_"):]: max(v) for k, v in part.get("series", {}).items()
            if k.startswith("ratio_")}


def event_changes(part, event_times, species):
    """At each event: the change of the dose and of the free-energy record across it, from the last
    record before t_e to the first after it. The held content is constant between events, so this
    holds whichever side of the event a record at t_e shows (the engine's shows the content before
    it: the event applies at the start of the step that starts at t_e, after that record)."""
    if not isinstance(part, dict) or part.get("completed") is not True:
        return None
    t, s, out = part["record_s"], part["series"], []
    for te in event_times:
        before = [k for k, x in enumerate(t) if x < te - 1e-12]
        after = [k for k, x in enumerate(t) if x > te + 1e-12]
        if not before or not after:
            return None
        h, i = before[-1], after[0]
        out.append(dict(
            time_s=te,
            dose_fmol={sp: s[f"bath_dose_{sp}_fmol"][i] - s[f"bath_dose_{sp}_fmol"][h]
                       for sp in species},
            free_energy_pJ=s["bath_dose_free_energy_pJ"][i] - s["bath_dose_free_energy_pJ"][h]))
    return out


def records_against(engine, reference, steps):
    """The dose in units of N eps |dose| (N the run's steps) and delta_G_b relative, the largest
    over the events and species; None without either side."""
    if engine is None or reference is None or len(engine) != len(reference):
        return dict(dose_over_rounding=None, free_energy_relative=None)
    dose, free = [], []
    for e, r in zip(engine, reference, strict=True):
        for sp, value in r["dose_fmol"].items():
            scale = max(1, steps) * EPS * max(abs(value), 1e-300)
            dose.append(abs(e["dose_fmol"].get(sp, 0.0) - value) / scale)
        g = r["free_energy_pJ"]
        free.append(abs(e["free_energy_pJ"] - g) / max(abs(g), 1e-300))
    return dict(dose_over_rounding=max(dose) if dose else None,
                free_energy_relative=max(free) if free else None)


def compensation(part):
    """The compensation-charge record q = -F sum_s z_s dose_s against the rounding of that sum:
    |q| over (n + 2) eps F 1e-15 times the dose's charge magnitude so far (the running sum over
    records of sum_s |z_s| |change of dose_s|), n the species. 0 where q is 0; None where q is not 0
    but no charged dose has moved (a charge from nothing fails), and for an incomplete part."""
    if not isinstance(part, dict) or part.get("completed") is not True:
        return None
    s, z = part["series"], part.get("valences")
    q = s.get("bath_compensation_charge_C")
    if q is None or not z:
        return None
    worst, magnitude = 0.0, 0.0
    for k, value in enumerate(q):
        if k:
            magnitude += sum(abs(v) * abs(s[f"bath_dose_{sp}_fmol"][k]
                                          - s[f"bath_dose_{sp}_fmol"][k - 1])
                             for sp, v in z.items())
        if value == 0.0:
            continue
        scale = (len(z) + 2) * EPS * FARADAY_C_PER_MOL * 1e-15 * magnitude
        if scale == 0.0:
            return None
        worst = max(worst, abs(value) / scale)
    return worst


def k_against_reference(part, reference):
    """W3: the operator's reconciliation term K (bath_reconciliation_pJ: the reservoir-work ledger
    without the term less with it) against R-records' K from W3's own supply series, over the
    reservoir-work ledger's bound, the largest over the records; None without either side or when
    their record times differ."""
    if not isinstance(part, dict) or part.get("completed") is not True or not reference:
        return None
    s, t = part["series"], part["record_s"]
    k, bound = s.get("bath_reconciliation_pJ"), s.get("reservoir_work_bound_pJ")
    k_ref = (reference.get("series") or {}).get("K_pJ")
    if k is None or bound is None or k_ref is None or reference.get("record_s") != t:
        return None
    ratios = [abs(a - b) / c if c > 0 else None for a, b, c in zip(k, k_ref, bound, strict=True)]
    return max_or_none(ratios)


def refusal_class(rows, expected):
    if not rows:
        return None
    refused = all(r["refused"] and r["check"] == expected for r in rows["refused"])
    admitted = all(r["admitted"] and r["ran"] is True for r in rows["admitted"])
    return int(refused and admitted)


def derive(parts, protocol):
    """The protocol's derived metrics (module docstring)."""
    d = protocol["judge"]["derivation"]
    g = {name: on_record_grid(part) for name, part in parts.items()}
    worlds = (parts.get("references") or {}).get("worlds", {})
    ref = {k: on_record_grid(v) for k, v in worlds.items()}
    out = dict(admission=base.admission(parts, d["run_parts"]))
    out["orders"], out["state_error"], out["reference"] = {}, {}, {}
    budgets = {}
    for world in ("W1", "W2"):
        w = d[world]
        rungs, declared, half = w["ladder_parts"], w["declared_part"], w["half_part"]
        for x in w["observables"]:
            out["orders"][f"{world}_{x}"] = base.ladder(g, rungs, x, d["band"])
    b1 = d["W1"]["budget_fmol"]
    budgets["W1"] = {x: b1 for x in d["W1"]["observables"]}
    budgets["W2"] = {d["W2"]["v_observable"]: d["W2"]["budget_V"],
                     d["W2"]["k_observable"]: d["W2"]["k_budget_fmol"]}
    for world in ("W1", "W2"):
        w = d[world]
        declared, half = w["declared_part"], w["half_part"]
        for x in w["observables"]:
            out["state_error"][f"{world}_{x}"] = base.ratio(
                base.richardson(g, declared, half, x), budgets[world][x])
            out["reference"][f"{world}_{x}"] = base.ratio(
                base.max_abs_difference(g.get(declared), ref.get(world), x), budgets[world][x])
            out["reference"][f"{world}_{x}_row0"] = base.ratio(
                base.row0(g.get(declared), ref.get(world), x), budgets[world][x])
            out["reference"][f"{world}_{x}_floor"] = base.ratio(
                base.max_abs_difference(ref.get(world), ref.get(f"{world}_floor"), x),
                budgets[world][x])
    out["state_error"]["max"] = max_or_none(
        v for k, v in out["state_error"].items() if k != "max")
    out["reference"]["max"] = max_or_none(
        v for k, v in out["reference"].items()
        if not k.endswith(("_floor", "_row0")) and k != "max")
    out["reference"]["row0_max"] = max_or_none(
        v for k, v in out["reference"].items() if k.endswith("_row0"))
    out["energy"] = {}
    for world in ("W1", "W2"):
        w = d[world]
        out["energy"][world] = dict(
            over_flows_at_declared=base.energy_over_flows(parts.get(w["declared_part"]) or {}),
            ladder=base.energy_ladder(parts, w["ladder_parts"], d["energy_order_low"]))
    w3 = parts.get(d["W3"]["part"])
    out["W3"] = {name: segments(w3, f"ratio_{name}", d["W3"]["event_s"])
                 for name in d["W3"]["ledgers"]}
    own = None
    if w3 and w3.get("completed") is True:
        s, t = w3["series"], w3["record_s"]
        own = [abs(a) / b if b > 0 else None
               for a, b in zip(s["reservoir_work_own_pJ"], s["reservoir_work_bound_pJ"],
                               strict=True)]
        own = dict(record_s=t, series=dict(own=own))
    k3 = segments(own, "own", d["W3"]["event_s"]) if own else dict(before=None, at=None,
                                                                    after=None)
    after_rows = None
    if own:
        after_rows = [v for v, x in zip(own["series"]["own"], own["record_s"], strict=True)
                      if x > d["W3"]["event_s"] + 1e-12]
    out["ledgers"] = {name: (ledger_maxima(parts.get(name)) or {}) for name in d["run_parts"]
                      if (parts.get(name) or {}).get("kind") == "engine"}
    out["ledger_max"] = {
        "records": max_or_none(v.get(k) for v in out["ledgers"].values()
                               for k in d["record_ledgers"]) if out["ledgers"] else None,
        "charge": max_or_none(v.get(k) for v in out["ledgers"].values()
                              for k in d["charge_ledgers"]) if out["ledgers"] else None,
        "water": max_or_none((ledger_maxima(parts.get(d["W6_part"])) or {}).values()
                             or [None]),
    }
    reference_records = (parts.get("references") or {}).get("records", {})
    out["records"] = {}
    for world, spec in d["records"].items():
        engine = event_changes(parts.get(spec["part"]), spec["event_s"], spec["species"])
        steps = (parts.get(spec["part"]) or {}).get("steps") or 0
        out["records"][world] = records_against(engine, reference_records.get(world), steps)
    out["records"]["dose_over_rounding_max"] = max_or_none(
        v["dose_over_rounding"] for k, v in out["records"].items() if isinstance(v, dict))
    out["records"]["free_energy_relative_max"] = max_or_none(
        v["free_energy_relative"] for k, v in out["records"].items() if isinstance(v, dict))
    engine_parts = [name for name in d["run_parts"] if name in d["compensation_parts"]]
    out["compensation"] = {name: compensation(parts.get(name)) for name in engine_parts}
    out["compensation"]["max"] = max_or_none(out["compensation"][n] for n in engine_parts)
    out["K_reference"] = dict(max_over_bound=k_against_reference(
        parts.get(d["W3"]["part"]), (parts.get("references") or {}).get("K_W3")))
    w4, w5, wb = parts.get("W4_idle") or {}, parts.get("W5_restart") or {}, parts.get("W5_batch")
    out["idle"] = flag((w4.get("idle") or {}).get("equal")) if w4.get("completed") else None
    restarts = w5.get("restarts") or {}
    out["restart"] = (int(len(restarts) == len(d["restart_times_s"])
                          and all(r["equal"] for r in restarts.values()))
                      if w5.get("completed") else None)
    batch = (wb or {}).get("worlds") or {}
    out["batch"] = (int(len(batch) == d["batch_worlds"] and all(r["equal"] for r in batch.values()))
                    if (wb or {}).get("completed") else None)
    classes = (parts.get("refusals") or {}).get("classes", {})
    expected = d["refusal_checks"]
    out["refusals"] = {cls: refusal_class(classes.get(cls), check)
                       for cls, check in expected.items()}
    r12 = (classes.get("R12_beyond_the_explicit_bound") or {}).get("declared_alone_at_1ms")
    out["refusals"]["R12_declared_alone_admitted"] = None if r12 is None else flag(r12["admitted"])
    out["refusals"]["all"] = (None if any(v is None for v in out["refusals"].values())
                              else int(all(out["refusals"].values())))
    out["staircase"] = flag(all((parts.get(n) or {}).get("completed") is True
                                for n in d["W7_parts"]))
    w6 = parts.get(d["W6_part"]) or {}
    out["water"] = flag(w6.get("completed") is True)
    k1 = max_or_none(base.ratio(base.max_abs_difference(g.get(d["W1"]["control_part"]),
                                                        ref.get("W1"), x), budgets["W1"][x])
                     for x in d["W1"]["observables"])
    k2 = base.ratio(base.max_abs_difference(g.get(d["W2"]["control_part"]), ref.get("W2"),
                                            d["W2"]["v_observable"]),
                    budgets["W2"][d["W2"]["v_observable"]])
    out["controls"] = dict(
        K1_over_budget=k1, K2_over_budget=k2,
        K3_before=k3["before"], K3_after_min=min(after_rows) if after_rows else None,
        K4_planted_differs=(flag(not (w4.get("planted") or {}).get("equal", True))
                            if w4.get("completed") else None),
        K5_moved_event_differs=(flag(not (w5.get("planted") or {}).get("equal", True))
                                if w5.get("completed") and w5.get("planted") else None))
    return out


def verdict(parts, protocol):
    derived = derive(parts, protocol)
    evaluated = evaluate(dict(criteria=protocol["judge"]["criteria"]),
                         dict(parts=parts, derived=derived))
    return derived, evaluated


def main(argv):
    if argv and argv[0] == "compare":
        return base.compare(*argv[1:])
    if len(argv) < 4 or argv[0] not in ("dev", "judged"):
        raise SystemExit(__doc__)
    mode, protocol_path, out_dir, paths = argv[0], argv[1], Path(argv[2]), argv[3:]
    protocol = json.loads(Path(protocol_path).read_text())
    results_list = [(p, json.loads(Path(p).read_text())) for p in paths]
    if mode == "judged":
        why = base.refusal(protocol, results_list, out_dir)
        if why:
            raise SystemExit("Refused: " + why)
        label = "Judged verdict"
    else:
        if out_dir.exists():
            raise SystemExit("Refused: the output directory exists")
        label = "Development verdict (not a judgement: the protocol is not registered)"
    parts, origin = base.merge(results_list, protocol, judged=mode == "judged")
    derived, evaluated = verdict(parts, protocol)
    record = dict(kind=label, protocol_id=protocol["id"], protocol_status=protocol["status"],
                  results=[str(p) for p in paths], part_sources=origin,
                  source=results_list[0][1].get("source"), passed=evaluated["passed"],
                  criteria=evaluated["criteria"], derived=derived)
    out_dir.mkdir(parents=True)
    (out_dir / "verdict.json").write_text(json.dumps(record, indent=1, allow_nan=False) + "\n")
    failed = [c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"]]
    print(label, "passed" if evaluated["passed"] else f"FAILED: {failed}")
    return record


if __name__ == "__main__":
    main(sys.argv[1:])
