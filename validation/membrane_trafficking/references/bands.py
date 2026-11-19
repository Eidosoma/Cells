"""FR-2's comparison bands: every compared row's band, and every plant's row and band, exported
from the registered design and values into ``interface/comparison_bands.json`` (the user's choice
(b), 19 November 2026).

    python -m validation.membrane_trafficking.references.design            # writes it too
    python -m validation.membrane_trafficking.references.design --check    # and checks it

The engine-side comparison reads this file, the values file, ``reference_inputs.json`` and
REFERENCES_USAGE.md, never the design file. Nothing in it is new: each band is max(the test's
tolerance, 10 × the floor) under the selected models of the dated note of 06:08 UTC
(``increment_storage`` for the potentials, ``stable_change`` for ΔG_chem), each plant's size is its
registered deviation, and ``build`` asserts both against the design.

**A row passes** when |engine − reference| ≤ band, in the row's unit. **A plant must be refused**
at its row when its size exceeds the row's band by ``MIN_MARGIN``; a plant below that is listed
with ``must_refuse`` false and its zero-power reason.
"""

from __future__ import annotations

from decimal import Decimal

from . import network as N

FILE = "interface/comparison_bands.json"
FLOOR_FACTOR = 10
MIN_MARGIN = 10.0
U = float(N.UNIT_ROUNDOFF)
K_OPS = N.K_OPS

MODELS = {
    "increment_storage": {
        "what": ("a node's float64 charge formed as its anchor plus F Σ z (n − n0), from stored "
                 "increments; the rounding acts on potentials through K⁻¹"),
        "parameters": {"unit_roundoff": U, "charge": ("u [|anchor| + (S + 1) CHARGE_PER_FMOL "
                                                      "Σ_s |z_s (n_s − n0_s)| + Σ_h |K_nh φ_h|]"),
                       "solve": "u × 4 × (free nodes) × max|φ|", "K_OPS": K_OPS,
                       "held_node_transfer": (
                           "erratum of 2026-11-19 (README): a held node's transfer is the change "
                           "of its plate charge Q_h = Σ_p s_p C_p V_p over the patches p touching "
                           "h, formed in each stage from that stage's two solves, so per "
                           "half-step floor(ΔQ_h) = n_stages × 2 [max(F_b, F_a) + u K_OPS "
                           "max(A_b, A_a)], F = Σ_p C_p f(V_p) with f the registered voltage "
                           "floors and A = Σ_p |C_p V_p|, before (b) and after (a) the "
                           "half-step; W_elec's is |φ_h| × that (in pJ) + u K_OPS |W_elec|; the "
                           "image charge's is the transfer's")},
        "selected": "dated note, 2026-11-19 06:08 UTC (the builder's statement of the engine)"},
    "stable_change": {
        "what": ("ΔG_chem as the move's change computed stably (log1p), to a few roundings of its "
                 "own size; the capacitor energies as a difference"),
        "parameters": {"unit_roundoff": U, "K_OPS": K_OPS,
                       "residual": ("u K_OPS (|ΔG_chem| + U0 + U1 + |H| + |W_res| + |W_elec| + "
                                    "|held RT ln c share|)"),
                       "W_carriers": "u K_OPS (|ΔG_chem| + |held RT ln c share|)"},
        "selected": "dated note, 2026-11-19 06:08 UTC (the builder's statement of the engine)"},
    "stages": {
        "what": "a few roundings per stage, accumulated over the stages a quantity has passed",
        "parameters": {"unit_roundoff": U, "per_stage": f"{K_OPS} u"}},
    "products": {
        "what": "a few roundings of a product or a sum of products",
        "parameters": {"unit_roundoff": U, "factor": f"{K_OPS} u × (terms + 1)"}},
}


def D(x) -> Decimal:
    return Decimal(str(x))


def band(tol: float, floor: float) -> float:
    return max(tol, FLOOR_FACTOR * floor)


class Rows:
    """The compared rows. Each check's constant parts (its test, engine reading, tolerance rule and
    source, floor model) are kept once in ``checks``; a row holds its own quantity, unit,
    reference, tolerance, floor, floor model and band. A drive's rows give ``reference_path``
    within ``values.drives[drive]``; the others give it from the values file's root."""

    def __init__(self):
        self.rows, self.index, self.checks, self.aliases = [], {}, {}, {}

    def alias(self, drive: str) -> str:
        if drive not in self.aliases:
            self.aliases[drive] = f"d{len(self.aliases) + 1:02d}"
        return self.aliases[drive]

    def add(self, rid, test, check, quantity, reading, unit, reference, path, tol, tol_rule,
            tol_source, floor, model, **where):
        spec = {"test": test, "engine_reading": reading, "tolerance_rule": tol_rule,
                "tolerance_source": tol_source, "floor_model": model}
        if check in self.checks:
            assert self.checks[check] == spec, (check, spec, self.checks[check])
        else:
            self.checks[check] = spec
        if "drive" in where:
            head = f"drives.{where['drive']}."
            if path.startswith(head):
                path = path[len(head):]
            rid = rid.replace(f"|{where['drive']}|", f"|{self.alias(where['drive'])}|")
        assert rid not in self.index, rid
        row = {"id": rid, "check": check, **where, "quantity": quantity, "unit": unit,
               "reference": reference, "reference_path": path, "tolerance": tol,
               "floor": floor, "floor_model": model,
               "band": band(tol if tol is not None else 0.0, floor)}
        self.index[rid] = row
        self.rows.append(row)
        return row

    def rid(self, rid: str) -> str:
        """A long row id (with its drive key) as stored."""
        for drive, a in self.aliases.items():
            rid = rid.replace(f"|{drive}|", f"|{a}|")
        return rid


def _f(x) -> float:
    return float(D(x))


def t4_t6_t3_rows(R: Rows, vals: dict) -> None:
    for key, dv in vals["drives"].items():
        pools = set(dv["pool_nodes"])
        prev_volt = dv["start"]["voltages_V"]
        prev_patches = dv["start"]["patches"]
        for i, hs in enumerate(dv["half_steps"]):
            n = i + 1
            start_volt = prev_volt
            start_patches = prev_patches
            P = f"drives.{key}.half_steps[{i}]"
            cf = hs["closed_forms"]
            fl = hs["floors"]["increment_storage"]
            maxphi = _f(hs["max_abs_potential_V"])
            w = {"drive": key, "half_step": n}
            # ---- T4 (one-direction, single-route half-steps)
            if cf.get("kind") == "retrieval":
                for node, d in hs["potential_change_V"].items():
                    if node in pools or _f(fl["potential_change_V"][node]) == 0.0:
                        continue                    # the pools move; held nodes are held
                    R.add(f"T4|{key}|{n}|potential_unchanged|{node}", "T4",
                          "potential_unchanged", f"φ_after − φ_before at {node}",
                          "the node's potential after the half-step less before it", "V", d,
                          f"{P}.potential_change_V.{node}", 1e-12 * maxphi,
                          "1e-12 × max|φ| (max|φ| before the half-step)", "§12",
                          _f(fl["potential_change_V"][node]), "increment_storage", node=node, **w)
                b = dv["pool_patch"]
                Vb = _f(cf["V_b_after_V"])
                R.add(f"T4|{key}|{n}|V_b_after|{b}", "T4", "V_b_after",
                      f"V_b′ = φ_in − φ_out of {b} after the half-step",
                      "the pool patch's voltage after the half-step", "V", cf["V_b_after_V"],
                      f"{P}.closed_forms.V_b_after_V", 1e-12 * abs(Vb), "relative 1e-12", "§12",
                      _f(fl["voltage_after_V"][b]), "increment_storage", patch=b, **w)
            if cf.get("kind") == "recycling":
                b, k = dv["pool_patch"], dv["plasma_patch"]
                Vb_after = _f(hs["after"]["voltages_V"][b])
                dVb = D(hs["after"]["voltages_V"][b]) - D(start_volt[b])
                R.add(f"T4|{key}|{n}|V_b_kept|{b}", "T4", "V_b_kept",
                      f"V_b after − V_b before, {b}",
                      "the pool patch's voltage after the half-step less before it", "V",
                      format(dVb, ".49e") if dVb != 0 else "0",
                      f"{P}.after.voltages_V.{b}", 1e-12 * abs(Vb_after),
                      "relative 1e-12 of V_b", "§12",
                      _f(fl["voltage_after_V"][b]) + _f(fl["voltage_before_V"][b]),
                      "increment_storage", patch=b, **w)
                Vk = _f(cf["V_k_after_V"])
                R.add(f"T4|{key}|{n}|V_k_after|{k}", "T4", "V_k_after",
                      f"V_k′ = φ_in − φ_out of {k} after the half-step",
                      "the plasma patch's voltage after the half-step", "V", cf["V_k_after_V"],
                      f"{P}.closed_forms.V_k_after_V", 1e-12 * abs(Vk), "relative 1e-12", "§12",
                      _f(fl["voltage_after_V"][k]), "increment_storage", patch=k, **w)
            if cf.get("kind") in ("retrieval", "recycling"):
                H = _f(cf["heat_pJ"])
                R.add(f"T4|{key}|{n}|heat", "T4", "heat",
                      "the single route's merge heat over the half-step",
                      "the change of trafficking_dissipated_energy_pJ (share 1)", "pJ",
                      cf["heat_pJ"], f"{P}.closed_forms.heat_pJ", 1e-9 * abs(H),
                      "relative 1e-9", "§12", _f(fl["heat_rel"]) * abs(H), "increment_storage",
                      **w)
            prev_volt = hs["after"]["voltages_V"]
            prev_patches = hs["after"]["patches"]
            # ---- T6 (every half-step)
            s = hs["sums"]
            t6 = hs["floors"]["T6"]["stable_change"]
            mt = _f(s["max_term_pJ"])
            fres = _f(t6["residual_pJ"])
            R.add(f"T6|{key}|{n}|residual", "T6", "residual",
                  "ΔG_chem + ΔU_view + H − W_res − W_elec − W_carriers over the half-step",
                  "the engine's six terms over the half-step, summed", "pJ", s["residual_pJ"],
                  f"{P}.sums.residual_pJ", _f(s["residual_band_pJ"]),
                  "1e-9 × max|term| + 1e-18 pJ", "§13", fres, "stable_change", **w)
            for term, path, reading in (
                    ("dG_chem", "dG_chem_pJ", "the chemical free-energy change at the free nodes"),
                    ("dU_view", "dU_view_pJ", "the capacitor energy's change, ½ Σ C V²"),
                    ("heat_total", "heat_closed_pJ", "the stage heats over the half-step")):
                R.add(f"T6|{key}|{n}|{term}", "T6", term, term + " over the half-step", reading,
                      "pJ", s[path], f"{P}.sums.{path}", 1e-9 * mt + 1e-18,
                      "1e-9 × max|term| + 1e-18 pJ, the residual's, per term", "references",
                      fres, "stable_change", **w)
            wc = _f(s["W_carriers_pJ"])
            fw = _f(t6["W_carriers_pJ"])
            R.add(f"T6|{key}|{n}|W_carriers", "T6", "W_carriers",
                  "the carriers' work over the half-step, all routes",
                  "the change of trafficking_work_pJ, summed over routes", "pJ",
                  s["W_carriers_pJ"], f"{P}.sums.W_carriers_pJ",
                  max(1e-6 * abs(wc), 1e-15 * mt), "max(relative 1e-6, 1e-15 × max|term|)",
                  "§13", fw, "stable_change", **w)
            if len(s["W_carriers_by_route_pJ"]) > 1:
                for r, x in s["W_carriers_by_route_pJ"].items():
                    R.add(f"T6|{key}|{n}|W_carriers_route|{r}", "T6", "W_carriers_route",
                          f"route {r}'s carriers' work over the half-step",
                          "the change of trafficking_work_pJ for the route", "pJ", x,
                          f"{P}.sums.W_carriers_by_route_pJ.{r}",
                          max(1e-6 * abs(_f(x)), 1e-15 * mt),
                          "max(relative 1e-6, 1e-15 × max|term|)", "§13", fw, "stable_change",
                          route=r, **w)
                for r, x in s.get("cleft_shares", {}).items():
                    R.add(f"T6|{key}|{n}|cleft_share|{r}", "T6", "cleft_share",
                          f"route {r}'s share of the shared cleft's free-energy change",
                          "|its carrier amount moved| / Σ |amounts|, per carrier row", "1", x,
                          f"{P}.sums.cleft_shares.{r}", 1e-3 * abs(_f(x)), "relative 1e-3",
                          "§13", K_OPS * U * abs(_f(x)), "products", route=r, **w)
            if s["supplied_fmol"]:
                wr = _f(s["W_res_pJ"])
                parts = max(abs(wr), abs(_f(s["W_res_without_phi_pJ"])),
                            abs(wr - _f(s["W_res_without_phi_pJ"])))
                R.add(f"T6|{key}|{n}|W_res", "T6", "W_res",
                      "the reservoir work over the half-step, 1e-3 Σ μ × supplied",
                      "the change of reservoir_work_pJ", "pJ", s["W_res_pJ"],
                      f"{P}.sums.W_res_pJ", 1e-12 * abs(wr), "relative 1e-12", "§13",
                      K_OPS * U * 4 * parts, "products", **w)
            for h, q in s["electrode_closed_C"].items():
                qv = _f(q)
                if qv == 0.0:
                    continue
                we = _f(s["W_elec_closed_pJ"])
                fq = held_transfer_floor(_TOUCH[key][h], fl, start_patches, start_volt,
                                         hs["after"]["patches"], hs["after"]["voltages_V"],
                                         len(hs["stages"]))
                phi_h = abs(_f(hs["after"]["potentials_V"][h]))
                R.add(f"T6|{key}|{n}|W_elec|{h}", "T6", "W_elec",
                      f"the electrode work at {h} over the half-step, φ_h × the transfer",
                      "the change of electrode_work_pJ", "pJ", s["W_elec_closed_pJ"],
                      f"{P}.sums.W_elec_closed_pJ", 1e-14 * abs(we), "relative 1e-14", "§13",
                      phi_h * fq * 1e12 + K_OPS * U * abs(we), "increment_storage", node=h, **w)
                R.add(f"T6|{key}|{n}|electrode_transfer|{h}", "T6", "electrode_transfer",
                      f"the electrode transfer at {h} over the half-step (ΔQ_h, signed)",
                      "the change of electrode_charge_transferred_C", "C", q,
                      f"{P}.sums.electrode_closed_C.{h}", 1e-14 * abs(qv),
                      "relative 1e-14, §13's electrode-work tolerance applied to the transfer",
                      "references", fq, "increment_storage", node=h, **w)
                qa = _f(s["electrode_abs_C"][h])
                R.add(f"T6|{key}|{n}|image_charge|{h}", "T6", "image_charge",
                      f"Σ over stages of |electrode transfer| at {h}",
                      "the change of trafficking_image_charge_C (confirmed, 06:08 UTC)", "C",
                      s["electrode_abs_C"][h], f"{P}.sums.electrode_abs_C.{h}", 1e-14 * qa,
                      "relative 1e-14, as the transfer's", "references", fq,
                      "increment_storage", node=h, **w)
            # ---- T3 (every half-step)
            for p, x in hs["T3"]["N_plus_R_minus_N0_plus_R0"].items():
                m = _f(dv["N0_plus_R0"][p])
                R.add(f"T3|{key}|{n}|N_plus_R|{p}", "T3", "N_plus_R",
                      f"N + R − (N0 + R0) for {p}",
                      "trafficking_units plus the route's internalised units, less N0 + R0",
                      "units", x, f"{P}.T3.N_plus_R_minus_N0_plus_R0.{p}", 1e-14 * m,
                      "relative 1e-14 of N0 + R0 (T5's conservation tolerance; §12 states T3's "
                      "bound only as 'within its bound')", "references (borrowed)",
                      n * _f(hs["floors"]["units_rel"]) * m, "stages", population=p, **w)
            for qty, unit, key2, kpatch in (("dA_sum", "m^2", "dA_sum_by_cell_m2", "area_m2"),
                                            ("dC_sum", "F", "dC_sum_by_cell_F",
                                             "capacitance_F")):
                for cell, x in hs["T3"][key2].items():
                    scale = sum(_f(pp[kpatch]) for pid, pp in hs["after"]["patches"].items()
                                if pid in _INSIDE[key].get(cell, ()))
                    R.add(f"T3|{key}|{n}|{qty}|{cell}", "T3", qty,
                          f"Σ over {cell}'s patches of the half-step's change",
                          "the per-cell ledger of trafficking_area_m2 or trafficking_capacitance_F",
                          unit, x, f"{P}.T3.{key2}.{cell}", None,
                          "none stated: the band is 10 × the floor", "references",
                          n * K_OPS * U * scale, "stages", cell=cell, **w)


_INSIDE = {}                    # drive -> cell -> the patches it is inside of (set by build)
_TOUCH = {}                     # drive -> node -> [(patch, +1 inside or −1 outside)] (set by build)


def held_transfer_floor(touch: list, fl: dict, patches_b: dict, volt_b: dict, patches_a: dict,
                        volt_a: dict, n_stages: int) -> float:
    """Erratum (2026-11-19): a held node's transfer over a half-step under increment_storage.

    The transfer is the change of the node's plate charge Q_h = Σ_p s_p C_p V_p over the patches
    p touching h, which each stage forms from its own two solves. Carrying the registered voltage
    floors f (each with its own solve) through Q_h, with a few roundings of its products and sum,
    gives per stage F_1 + F_2 + u K_OPS (A_1 + A_2) for its two states, where F = Σ_p C_p f(V_p)
    and A = Σ_p |C_p V_p|. A stage's states differ from the half-step's two (b, a) by a few percent
    at most, so each is bounded by the larger of those, and the half-step's floor is
    n_stages × 2 [max(F_b, F_a) + u K_OPS max(A_b, A_a)] (C)."""
    F = {"b": 0.0, "a": 0.0}
    A = {"b": 0.0, "a": 0.0}
    for p, _sign in touch:
        Cb, Vb = _f(patches_b[p]["capacitance_F"]), _f(volt_b[p])
        Ca, Va = _f(patches_a[p]["capacitance_F"]), _f(volt_a[p])
        F["b"] += Cb * _f(fl["voltage_before_V"][p])
        F["a"] += Ca * _f(fl["voltage_after_V"][p])
        A["b"] += abs(Cb * Vb)
        A["a"] += abs(Ca * Va)
    return n_stages * 2 * (max(F.values()) + K_OPS * U * max(A.values()))


def t5_rows(R: Rows, vals: dict, criteria: list) -> None:
    t5 = vals["T5"]
    key = next(k for k in vals["drives"] if "cycle_follows" in k)
    units_rel = [_f(h["floors"]["units_rel"]) for h in vals["drives"][key]["half_steps"]]
    for i, row in enumerate(t5["cycle_operator"]["half_steps"]):
        acc = sum(units_rel[: i + 1])
        for p, c in row["closed"].items():
            for qty in ("N", "R"):
                v = _f(c[qty])
                R.add(f"T5|cycle_operator|{i + 1}|{qty}|{p}", "T5", f"cycle_{qty}",
                      f"{qty} of {p} after half-step {i + 1} of the operator-level cycle",
                      ("trafficking_units" if qty == "N" else
                       "trafficking_internalised_units (the route's record)"),
                      "units", c[qty], f"T5.cycle_operator.half_steps[{i}].closed.{p}.{qty}",
                      1e-13 * abs(v), "relative 1e-13", "§12", acc * abs(v), "stages",
                      drive=key, half_step=i + 1, population=p)
    b = t5["both_directions"]
    for p in ("kir_0",):
        rec = b["populations"][p]
        for nn in ("8", "16"):
            v = _f(rec["palindrome"]["N"][nn])
            floor = (3 * int(nn) + 1) * K_OPS * U * abs(v)
            R.add(f"T5|both_directions|{p}|N|n{nn}", "T5", "both_N",
                  f"N of {p} at 4 ms after {nn} palindromic half-steps",
                  "trafficking_units at the end of the run", "units", rec["palindrome"]["N"][nn],
                  f"T5.both_directions.populations.{p}.palindrome.N.{nn}", None,
                  "none stated (the references' own: the scheme's N to its float64 floor)",
                  "references", floor, "stages", population=p, steps=int(nn))
        criteria.extend([
            {"id": f"T5|both_directions|{p}|ratio_8_16", "test": "T5",
             "reference": rec["palindrome"]["ratio"]["8/16"],
             "reference_path": f"T5.both_directions.populations.{p}.palindrome.ratio.8/16",
             "criterion": "3.5 < err(8)/err(16) < 4.5", "source": "§13"},
            {"id": f"T5|both_directions|{p}|err16", "test": "T5",
             "reference": rec["palindrome"]["rel_error"]["16"],
             "reference_path": f"T5.both_directions.populations.{p}.palindrome.rel_error.16",
             "criterion": "err(16) < 1e-4 (relative, against the exact N at 4 ms)",
             "source": "§13"},
            {"id": f"T5|both_directions|{p}|lie_ratio_8_16", "test": "T5",
             "reference": rec["lie"]["ratio"]["8/16"],
             "reference_path": f"T5.both_directions.populations.{p}.lie.ratio.8/16",
             "criterion": "the Lie plant's err(8)/err(16) < 2.5 (it must fail 3.5 < r < 4.5)",
             "source": "§13"}])
    blocks = [("compiled_cycle", t5["compiled_cycle"])] + [
        (f"batch_{r}", blk) for r, blk in t5["batch"].items()]
    for name, blk in blocks:
        for j, ob in enumerate(blk["observations"]):
            stages = 3 * 2 * j                  # two half-steps per 1 ms step, three stages each
            path = (f"T5.{name}.observations[{j}]" if name == "compiled_cycle"
                    else f"T5.batch.{name[6:]}.observations[{j}]")
            items = [(f"{q}|{p}", ob[q][p], f"{path}.{q}.{p}", "units") for q in ("N", "R")
                     for p in ob["N"]]
            items += [(q, ob[q], f"{path}.{q}", u) for q, u in
                      (("A_k", "m^2"), ("A_b", "m^2"), ("C_k_F", "F"), ("C_b_F", "F"))]
            for sub, ref, pth, unit in items:
                v = _f(ref)
                R.add(f"T5|{name}|obs{j}|{sub}", "T5", "compiled",
                      f"{sub} at observation {j} ({_f(ob['t']) * 1e3:g} ms) of {name}",
                      "the run's history at that observation", unit, ref, pth,
                      1e-12 * abs(v), "relative 1e-12", "§12", (stages + 1) * K_OPS * U * abs(v),
                      "stages", block=name, observation=j)


def t8_rows(R: Rows, vals: dict) -> None:
    for pid, rec in vals["T8"]["populations"].items():
        if not rec["coupled"]:
            continue
        st = _f(rec["start_m2"])
        R.add(f"T8|{pid}|start", "T8", "start", f"the start of {pid}'s conductance factor",
              "F × availability × abundance × area at t = 0 (m²)", "m^2", rec["start_m2"],
              f"T8.populations.{pid}.start_m2", 1e-14 * st, "relative 1e-14", "§12-§13",
              K_OPS * U * st, "products", population=pid)
        for j, ob in enumerate(rec["observations"]):
            v = _f(ob["start_times_A_over_A0_m2"])
            R.add(f"T8|{pid}|obs{j}|factor", "T8", "factor",
                  f"{pid}'s conductance factor at {_f(ob['t_s']) * 1e3:g} ms",
                  "F × availability × abundance × area (abundance = N/(A ρ))", "m^2",
                  ob["start_times_A_over_A0_m2"],
                  f"T8.populations.{pid}.observations[{j}].start_times_A_over_A0_m2",
                  1e-12 * abs(v), "relative 1e-12", "§12-§13",
                  (3 * 2 * j + 1) * K_OPS * U * abs(v), "stages", population=pid, observation=j)


def plants(R: Rows, vals: dict, des: dict, zero_power: list, kinds: dict) -> list:
    out = []
    reasons = {z["what"]: z["why"] for z in zero_power}

    def put(name, rid, planted, size, unit, registered_dev, reason=None):
        rid = R.rid(rid)
        row = R.index[rid]
        margin = size / row["band"] if row["band"] > 0 else float("inf")
        kind = kinds.setdefault(name, {"planted": planted})
        assert kind["planted"] == planted, name
        must = margin >= MIN_MARGIN
        if not must:
            assert reason, (name, rid)
            kind.setdefault("zero_power", reason)
        out.append({"plant": name, "row": rid, "size": size, "unit": unit, "band": row["band"],
                    "margin": margin, "must_refuse": must, "registered_deviation": registered_dev})

    P = des["plants"]
    t4 = {"R1 at a held bath: the owner's potential moves by V_k dC/(C_k - dC)": "owner",
          "R1 at a free node: the outside node's potential moves by -V_k dC/(C_k - dC)":
          "outside", "carriers without their valence (delta = t dq/F)": "argmax"}
    planted = {"owner": "R1: the capacitance moved at fixed charges, no carriers written",
               "outside": "R1: the capacitance moved at fixed charges, no carriers written",
               "argmax": "the carriers moved as δ = t δq/F, their valence dropped"}
    for name, which in t4.items():
        for r in P[name]["rows"]:
            key, n = r["where"].rsplit(" #", 1)
            dv = vals["drives"][key]
            hs = dv["half_steps"][int(n) - 1]
            cf = hs["closed_forms"]
            pools = set(dv["pool_nodes"])
            if which == "argmax":
                nv, pa = cf["no_valence_potentials_V"], hs["after"]["potentials_V"]
                devs = {m: abs(_f(D(nv[m]) - D(pa[m]))) for m in pa if m not in pools}
                size = max(devs.values())
                # the row of the node that moves most; the owner's where nothing moves
                rowed = [m for m in devs
                         if R.rid(f"T4|{key}|{n}|potential_unchanged|{m}") in R.index]
                node = max(rowed, key=devs.get) if size > 0 else dv["owner"]
            else:
                node = dv[which]
                size = abs(_f(cf["R1_potential_change_V"][node]))
            assert abs(size - r["deviation"]) <= 1e-12 * max(abs(size), 1e-300), (name, r)
            rid = f"T4|{key}|{n}|potential_unchanged|{node}"
            assert R.rid(rid) in R.index, rid
            put(name, rid, planted[which], size, "V", r["deviation"],
                reasons.get("a dropped valence or swapped transference numbers, in the "
                            "declared worlds"))
    t6 = {"a merge heat of the wrong sign": "the merge heat booked with the wrong sign",
          "the electrode work with the wrong sign": "the electrode work with the wrong sign",
          "the reservoir work without z F phi_b": "the reservoir work without z F φ_b",
          "the carriers' work with the wrong sign": "the carriers' work with the wrong sign"}
    for name, what in t6.items():
        for r in P[name]["rows"]:
            key, n = r["where"].rsplit(" #", 1)
            put(name, f"T6|{key}|{n}|residual", what, r["deviation"], "pJ", r["deviation"])
    for r in P["the two transference numbers swapped"]["rows"]:
        key, n = r["where"].rsplit(" #", 1)
        put("the two transference numbers swapped", f"T6|{key}|{n}|W_carriers",
            "each route's two transference numbers swapped", r["deviation"], "pJ",
            r["deviation"], reasons.get("a dropped valence or swapped transference numbers, in "
                                        "the declared worlds"))
    for name in ("the whole cleft change on one route (this route takes all)",
                 "the whole cleft change on one route (this route takes none)"):
        for r in P[name]["rows"]:
            head, rest = r["where"].split(" #", 1)
            n, route, *_ = rest.split(" ")
            put(name, f"T6|{head}|{n}|W_carriers_route|{route}",
                "the shared cleft's whole free-energy change booked on one route",
                r["deviation"], "pJ", r["deviation"])
    for r in P["a unit dropped from the record"]["rows"]:
        key, p = r["where"].rsplit(" ", 1)
        put("a unit dropped from the record", f"T3|{key}|1|N_plus_R|{p}",
            "one unit dropped from the route's record", 1.0, "units", r["deviation"])
    for r in P["e (or e_r) off by 1 part in 10^6"]["rows"]:
        _hs, i, p = r["where"].split(" ")
        rows_ = [x for x in vals["T5"]["cycle_operator"]["half_steps"]]
        qty = "N" if p in rows_[int(i) - 1]["plant_e_1e-6_rel"] else "R"
        rid = f"T5|cycle_operator|{i}|{qty}|{p}"
        size = r["deviation"] * abs(_f(R.index[R.rid(rid)]["reference"]))
        put("e (or e_r) off by 1 part in 10^6", rid,
            "e (on retrieval) or e_r (on recycling) off by 1 part in 10^6", size, "units",
            r["deviation"])
    for name in ("T8 without the coupling", "T8 without the retrieval"):
        for r in P[name]["rows"]:
            pid, _at, t, _ms = r["where"].split(" ")
            j = int(t)
            rid = f"T8|{pid}|obs{j}|factor"
            size = r["deviation"] * abs(_f(R.index[R.rid(rid)]["reference"]))
            put(name, rid, ("the coupling's factor F left out" if "coupling" in name
                            else "the retrieval left out"), size, "m^2", r["deviation"],
                "t = 0, before any retrieval" if "retrieval" in name else None)
    return out


def build(vals: dict, des: dict) -> dict:
    """The interface from the registered values and design (asserting the plants' sizes)."""
    from validation.core_seams.references.exact import context

    with context():
        return _build(vals, des)


def _build(vals: dict, des: dict) -> dict:
    _INSIDE.clear()
    _TOUCH.clear()
    from . import worlds as W
    inp = W.load()
    for key, dv in vals["drives"].items():
        w = W.world_record(inp, dv["world"])
        inside, touch = {}, {}
        for p in w["patches"]:
            inside.setdefault(p["inside"], []).append(p["id"])
            touch.setdefault(p["inside"], []).append((p["id"], 1))
            touch.setdefault(p["outside"], []).append((p["id"], -1))
        _INSIDE[key] = inside
        _TOUCH[key] = touch
    R = Rows()
    criteria = []
    t4_t6_t3_rows(R, vals)
    t5_rows(R, vals, criteria)
    t8_rows(R, vals)
    kinds = {}
    pl = plants(R, vals, des, des["zero_power"], kinds)
    lie = des["plants"]["the Lie split S_ret(h) S_rec(h)"]
    kinds["the Lie split S_ret(h) S_rec(h)"] = {
        "planted": "the half-step run as S_ret(h) S_rec(h) in place of the palindrome",
        "refused_by": ("its criterion row: err(8)/err(16) outside (3.5, 4.5); the test asks the "
                       "plant's ratio to be below 2.5")}
    pl.append({"plant": "the Lie split S_ret(h) S_rec(h)",
               "row": "T5|both_directions|kir_0|lie_ratio_8_16", "size": lie["lie_ratio_8_16"],
               "unit": "1", "band": None, "margin": None, "must_refuse": bool(lie["caught"]),
               "registered_deviation": lie["lie_ratio_8_16"]})
    return {"kind": "cells.fr2_comparison_bands@1",
            "about": ("FR-2's comparison bands: every compared row's quantity, unit, reference, "
                      "tolerance, floor (model and value) and band, and every plant's row, size "
                      "and band; exported from the registered design and values"),
            "generated_from": {"values": "designs/membrane_trafficking_reference_values.json",
                               "design": "designs/membrane_trafficking_reference_design.json",
                               "by": "validation/membrane_trafficking/references/bands.py"},
            "selected_models": {"potentials": "increment_storage",
                                "dG_chem": "stable_change",
                                "note": "README, dated note of 2026-11-19 06:08 UTC"},
            "band_rule": (f"band = max(tolerance, {FLOOR_FACTOR} × floor), absolute, in the row's "
                          "unit; a row passes when |engine − reference| ≤ band; a null tolerance "
                          "means none is stated and the band is the floor's"),
            "plant_rule": (f"a plant must be refused at its row when size ≥ {MIN_MARGIN:g} × band "
                           "(must_refuse); below that it is zero power, with its reason"),
            "models": MODELS, "checks": R.checks, "drives": {a: d for d, a in R.aliases.items()},
            "rows": R.rows, "criteria": criteria, "plant_kinds": kinds, "plants": pl,
            "counts": {"rows": len(R.rows), "criteria": len(criteria), "plants": len(pl),
                       "plants_must_refuse": sum(1 for p in pl if p["must_refuse"])}}
