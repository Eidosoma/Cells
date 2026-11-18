"""Writes FR-10's registered reference design and values (``designs/``) from the inputs.

    python -m validation.fr10.references.design            # (re)write both files
    python -m validation.fr10.references.design --check    # compare the committed files

``fr10_reference_design.json`` holds the claims, their tolerance basis, every planted control's
deviation on the registered dt ladder (the power), the zero-power cases and the readings.
``fr10_reference_values.json`` holds the references' outputs on the registered inputs, with their
floors. Both are written before any engine output exists; ``--check`` regenerates them and
compares numbers to a relative 1e-12 and everything else exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import localcontext
from itertools import pairwise

import numpy as np

from . import controls, faces, ion, records, schemes
from .common import (
    DESIGNS,
    DIGITS,
    INPUTS_PATH,
    MIN_MARGIN,
    constants_from_block,
    dec,
    jsonable,
    load_inputs,
)

DESIGN_FILE = DESIGNS / "fr10_reference_design.json"
VALUES_FILE = DESIGNS / "fr10_reference_values.json"
REGISTERED = "2026-11-17"
INPUTS_SOURCE = ("branch fr10-protocol, commit cbe4f27d, "
                 "validation/bath_schedule/reference_inputs.json (copied byte for byte)")


def git_blob_id(path) -> str:
    """Git's blob id of a file, computed at run time (no hash literal is kept in the code)."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _orders(errors: list) -> list:
    return [float(np.log2(a / b)) if a > 0 and b > 0 else None
            for a, b in pairwise(errors)]


def _ladder(kind: str, world, ref, ladder, ctrl) -> dict:
    rows = []
    errs = {s: [] for s in schemes.SCHEMES}
    for dt in ladder:
        row = {"dt_s": dt, "stand_in": {}}
        for sc in schemes.SCHEMES:
            if kind == "faces":
                a = schemes.run_faces(world, dt, sc)
                e = {"amount_fmol": float(np.max(np.abs(a - ref["amount_fmol"])))}
                key = "amount_fmol"
            else:
                a = schemes.run_ion(world, dt, sc)
                p = world.permeant[0]
                e = {"V_m_V": float(np.max(np.abs(a["V_m_V"] - ref["V_m_V"]))),
                     "amount_fmol": float(np.max(np.abs(a["amount_fmol"] -
                                                        ref["amount_fmol"][p])))}
                key = "V_m_V"
            row["stand_in"][sc] = e
            errs[sc].append(e[key])
        timing = {c: ctrl[f"{c}@{dt:g}"] for c in ("late", "early", "half")}
        row["controls"] = timing
        units = ("amount_fmol",) if kind == "faces" else ("V_m_V", "amount_fmol")
        row["ceiling"] = {}
        row["honest_margin"] = {}
        for u in units:
            devs = [timing[c][u] for c in timing] + \
                [ctrl[c][u] for c in ("null", "accumulate") if ctrl[c][u] > 0]
            ceiling = min(devs) / MIN_MARGIN
            honest = max(row["stand_in"]["ars_implicit"][u], row["stand_in"]["ars_explicit"][u])
            row["ceiling"][u] = ceiling
            row["honest_margin"][u] = ceiling / honest
        rows.append(row)
    return {"per_dt": rows,
            "observed_order": {sc: _orders(errs[sc]) for sc in schemes.SCHEMES},
            "dt_free_controls": {c: ctrl[c] for c in ("null", "accumulate")}}


def build(inputs_path=INPUTS_PATH) -> tuple:
    inputs = load_inputs(inputs_path)
    const = constants_from_block(inputs["constants"])
    rec_worlds = inputs["R_records"]["worlds"]

    fw = faces.parse(inputs["R_faces"])
    fref = faces.solve(fw)
    fdec = faces.solve_decimal(fw)
    f_ladder = inputs["R_faces"]["dt_ladder_s"]
    fctrl = controls.faces_controls(fw, f_ladder, fref)

    iw = ion.parse(inputs["R_ion"], const)
    iref = ion.solve(iw)
    i_ladder = inputs["R_ion"]["dt_ladder_s"]
    ictrl = controls.ion_controls(iw, i_ladder, iref)
    rounded = controls.ion_rounded_constants(inputs["R_ion"], iref)

    ev = records.records_summary(inputs)
    rctrl = {w: controls.records_controls(world, const) for w, world in rec_worlds.items()}
    K1 = records.reconciliation_K(rec_worlds["W1"], fref["times_s"], {"S": fref["supply_fmol"]},
                                  const)
    K2 = records.reconciliation_K(rec_worlds["W2"], iref["times_s"], iref["supply_fmol"], const)
    Kc = {"W1": controls.K_controls(K1, {"S": fref["supply_fmol"]}, rec_worlds["W1"], const),
          "W2": controls.K_controls(K2, iref["supply_fmol"], rec_worlds["W2"], const)}

    with localcontext() as ctx:
        ctx.prec = DIGITS
        const_block = {
            "faraday_C_per_mol": str(dec(const.faraday)),
            "gas_constant_J_per_mol_K": str(dec(const.gas_constant)),
            "RT_J_per_mol_at_310K": str(dec(const.RT(310))),
            "thermal_voltage_V_at_310K": str(dec(const.thermal_voltage(310))),
        }

    f_table = _ladder("faces", fw, fref, f_ladder, fctrl)
    i_table = _ladder("ion", iw, iref, i_ladder, ictrl)
    i_table["rounded_constants"] = rounded
    i_table["rounded_constants_needs_tolerance_V"] = rounded["V_m_V"] / MIN_MARGIN

    p = iw.permeant[0]
    design = {
        "kind": "fr10-references design@1",
        "registered": REGISTERED,
        "status": "registered before any engine output; the references are code-blind",
        "inputs": {"path": "validation/fr10/references/reference_inputs.json",
                   "source": INPUTS_SOURCE, "git_blob": git_blob_id(inputs_path)},
        "constants": const_block,
        "min_margin": MIN_MARGIN,
        "readings": [
            "Inputs are the exact values of the file's doubles; constants are the exact SI values "
            "the file states (F = N_A e, R = N_A k_B), never Appendix A's rounded RT and F.",
            "Events are right-continuous: the bath's composition at t_e is the new one; amounts "
            "and V_m are continuous, so a record at t_e has one value.",
            "dG_b's ln(a_s/V_b) is the log of the mM number (standard state 1 mM). A different "
            "standard state or a dropped -1 shifts dG_b by a multiple of sum_s dn_s, so W2 "
            "(sum_s dn_s = 0) has no power against either; W1 and W3 do.",
            "K(t) needs S_s at every event time: every event time must be a record time (to "
            "1e-12 s), else the call is refused; nothing is interpolated.",
            "K from the engine's own supply checks the reconciliation's arithmetic only; it has "
            "no power against a wrong supply. K from the reference supply (R-faces, R-ion) does.",
            "R-ion's zero-current potential after the step has two readings: (a) at the cytosol's "
            "composition at t_e with the new bath (the Nernst potential), and (b) the epoch's "
            "own limit, where the charge that depolarises the wall has also moved K into the "
            "cytosol. They differ by about 1.2e-7 V; both are returned, labelled.",
            "W1's supply is the finite nodes' gain, S(t) = sum_i (n_i(t) - n_i(0)); W2's is the "
            "cell's gain, S_s(t) = n_s(t) - n_s(0); both are positive out of the bath.",
        ],
        "claims": {
            "R-faces (B1, A.2)": {
                "quantity": "S amount (fmol) at each finite node at each record time; the "
                            "supply S(t)",
                "reference": "exact per epoch: symmetrised eigendecomposition of the deviation "
                             "from the epoch's steady state c_b",
                "second_method": "scipy expm of the augmented generator, chained independently; "
                                 "a 50-digit Sylvester form for two nodes (tests)",
                "floor_max_fmol": float(np.max(fref["floor_fmol"])),
                "decimal_vs_primary_max_fmol": float(np.max(np.abs(fdec - fref["amount_fmol"]))),
                "tolerance_basis": "pinned by the protocol from its dt study, with power at a dt "
                                   "only when tau(dt) <= ceiling(dt) (the smallest control "
                                   "deviation / min_margin) and tau(dt) >= min_margin x floor; "
                                   "an honest second-order engine is expected near the "
                                   "stand-ins' bracket (power.W1)",
                "order": "an honest second-order engine's error falls about 4x per halving of "
                         "dt; the late, early and half-step controls and implicit Euler fall 2x",
            },
            "R-ion (B2, A.3)": {
                "quantity": "V_m (V) and the cytosol's Na, K and Cl (fmol) at each record time; "
                            "the zero-current potential after the step, readings (a) and (b)",
                "reference": "the scalar equation on the charge invariant, DOP853 at rtol 3e-14, "
                             "epoch by epoch",
                "second_method": "Radau on the full state (rtol 1e-12) and QUADPACK's time "
                                 "residual |f(V) (T(V) - t)|; the floor is the larger",
                "floor_max_V": float(np.max(iref["floor"]["V_m_V"])),
                "floor_max_fmol": float(max(np.max(v) for v in
                                            iref["floor"]["amount_fmol"].values())),
                "impermeant_species": "Na, Cl and S are constant: P = 0, so any change fails",
                "tolerance_basis": "as R-faces, per dt (power.W2). Appendix A's rounded constants "
                                   "would move V_m by power.W2.rounded_constants; a V_m tolerance "
                                   "has power against them only below "
                                   "rounded_constants_needs_tolerance_V",
                "relaxation_left_at_end_V": float(iref["V_m_V"][-1] - iref["limit_V"][0]),
            },
            "R-records (B4, A.4, A.5, §2.2, §2.3)": {
                "quantity": "per event: dose per species (fmol), dG_b (pJ), the step's charge "
                            "(C); K(t) (pJ) from a supply series",
                "reference": "exact rationals for the dose and charge; dG_b and K in 50-digit "
                             "decimals",
                "second_method": "float64 evaluations of the same forms (K in the operator's B "
                                 "form)",
                "tolerance_basis": "dG_b within 1e-12 relative (the protocol's criterion; the "
                                   "floor is below 1e-15 relative); dose and K at rounding "
                                   "(a few ulps of their magnitudes); a neutral step's charge "
                                   "is exactly 0 in rationals",
                "floor_max_relative_dG_b": float(max(e["floor"]["dG_b_pJ"] / abs(e["dG_b_pJ"])
                                                     for evs in ev.values() for e in evs)),
            },
        },
        "power": {
            "W1": f_table,
            "W2": i_table,
            "records": rctrl,
            "K": {**Kc, "W3": "the supply is the engine's, at run time: K_dropped's deviation "
                             "is max|K| and K_without_B's is |1e-3 sum_s dmu_s S_s(t_e)|"},
        },
        "zero_power": [
            {"control": "dose_in_mM (a dose or held content booked in mM, missing V_b)",
             "worlds": ["W1", "W2", "W3"], "why": "every bath volume is 1 pL",
             "remedy": "a bath of another volume, such as 25 pL"},
            {"control": "n against c in the faces' view or volumes", "worlds": ["W1"],
             "why": "both finite nodes are 1 pL", "remedy": "unequal node volumes"},
            {"control": "accumulate (offsets added to the previous epoch)",
             "worlds": ["W2", "W3"], "why": "a single event",
             "remedy": "W1 has power (its return to the declared composition); for ions, a "
                       "two-stair schedule such as K 5 -> 15 -> 50 mM"},
            {"control": "dG_no_minus_one, dG_one_molar", "worlds": ["W2"],
             "why": "sum_s dn_s = 0 for a substitution", "remedy": "W1 and W3 have power"},
            {"control": "the view of Na and Cl at the membrane", "worlds": ["W2"],
             "why": "K is the only permeant species",
             "remedy": "an arm with Na and Cl leaks (then the zero-current potential is the "
                       "GHK voltage equation's, which ion.zero_current evaluates)"},
            {"control": "K booked with z F phi_b uncancelled", "worlds": ["W1", "W2", "W3"],
             "why": "phi_b = 0 (and z = 0 in W1 and W3)", "remedy": "none planned"},
            {"control": "K_without_B", "worlds": ["W2"],
             "why": "the supply before the event is zero (the cell is at rest)",
             "remedy": "W1 has power (its second event)"},
            {"control": "charge_dropped_counterion", "worlds": ["W1", "W3"],
             "why": "a neutral species alone", "remedy": "W2 has power"},
        ],
        "notes": {
            "W1_kappa_pL_per_s": faces.kappas(fw),
            "W1_rates_per_s": [float(x) for x in fref["rates_per_s"]],
            "W2_V0_V": iref["V0_V"],
            "W2_rest_V_at_declared": iref["rest_V_declared"],
            "W2_permeant": p,
        },
    }
    values = {
        "kind": "fr10-references values@1",
        "registered": REGISTERED,
        "R_faces": {
            "nodes": fref["nodes"], "species": fref["species"],
            "times_s": fref["times_s"], "amount_fmol": fref["amount_fmol"],
            "floor_fmol": fref["floor_fmol"], "supply_fmol": fref["supply_fmol"],
            "supply_floor_fmol": fref["supply_floor_fmol"],
        },
        "R_ion": {
            "times_s": iref["times_s"], "V_m_V": iref["V_m_V"],
            "amount_fmol": iref["amount_fmol"], "floor": iref["floor"],
            "supply_fmol": iref["supply_fmol"],
            "event_times_s": iref["event_times_s"],
            "zero_current_V_at_event_composition": iref["zero_current_V"],
            "zero_current_floor_V": iref["zero_current_floor_V"],
            "limit_V": iref["limit_V"], "limit_floor_V": iref["limit_floor_V"],
        },
        "R_records": {
            "events": ev,
            "K_from_reference_supply": {
                "W1": {"times_s": K1["times_s"], "K_pJ": K1["K_pJ"], "floor_pJ": K1["floor_pJ"]},
                "W2": {"times_s": K2["times_s"], "K_pJ": K2["K_pJ"], "floor_pJ": K2["floor_pJ"]},
            },
        },
    }
    return jsonable(design), jsonable(values)


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=False) + "\n"


def write() -> None:
    design, values = build()
    DESIGNS.mkdir(parents=True, exist_ok=True)
    DESIGN_FILE.write_text(_dump(design))
    VALUES_FILE.write_text(_dump(values))


ROUNDING_NOISE = ("floor", "rk4", "decimal_vs_primary", "relaxation_left", "K_without_B",
                  "W2_rest_V", "W2_V0")
"""Paths whose numbers are rounding-level diagnostics. They depend on the BLAS thread count
(``cells`` pins one thread, D190), so they agree when both lie below ``NOISE_CEILING`` or within
a factor of 2."""
NOISE_CEILING = 1e-12


def _same(a, b, path="", rtol=1e-12) -> list:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}: keys {sorted(set(a) ^ set(b))}"]
        return [m for k in a for m in _same(a[k], b[k], f"{path}/{k}", rtol)]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [m for i, (x, y) in enumerate(zip(a, b, strict=True))
                for m in _same(x, y, f"{path}[{i}]", rtol)]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and \
            not isinstance(a, bool) and not isinstance(b, bool):
        if a == b:
            return []
        if any(tag in path for tag in ROUNDING_NOISE):
            ok = max(abs(a), abs(b)) <= NOISE_CEILING or \
                abs(a - b) <= 0.5 * max(abs(a), abs(b))
        else:
            ok = abs(a - b) <= rtol * max(abs(a), abs(b))
        return [] if ok else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def check(rtol: float = 1e-12) -> list:
    """Differences between the committed files and a fresh build (empty when they agree).

    The references' values must agree to ``rtol``; the design's stand-in errors and control
    deviations to 1e-6; rounding-level diagnostics (``ROUNDING_NOISE``) within a factor of 2.
    """
    design, values = build()
    committed_d = json.loads(DESIGN_FILE.read_text())
    committed_v = json.loads(VALUES_FILE.read_text())
    return _same(committed_d, design, "design", rtol=1e-6) + \
        _same(committed_v, values, "values", rtol=rtol)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        diffs = check()
        for d in diffs[:50]:
            print(d)
        return 1 if diffs else 0
    write()
    print(DESIGN_FILE)
    print(VALUES_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
