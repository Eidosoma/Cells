"""FR-63: each preparation's pH shift on Kv1.5's activation, and a development check of it (D399).

**What FR-63 is** (docs/FEATURE_REQUESTS.md, logged by the user; D356, D399, D418). It is a
declared pH shift on the m gate of a `cells.channel.kv1p5_mh@1` population, in FR-64's mechanism
(src/cells/laws/channels/voltage_shift.py). The gate reads V_r = V - dV, with
dV = sigma (pH - pH_ref) at the outside node's free protons, and no law changes. Each
preparation's sigma is the two-point secant through its own control and acid midpoints, as the
Lean track transcribed them (PREPARATIONS; docs/FR63_CALIBRATION_REPORT.md §1).

**The check is circular by construction and calibrates nothing.**
- sigma is set from the preparation's two midpoints, so the engine's midpoint shift between them
  is the measured shift by construction.
- The check shows only that the engine applies the declared shift. At each preparation's two pH
  levels, the voltage at which the engine's steady-state activation target crosses one half
  moves by the declared dV, within rounding. It is not a comparison with the measurements.
- It runs at the six calibration pH levels only. Each declaration's window is the closed interval
  between its preparation's two levels: a pH outside it is refused, and inside it the engine
  applies the line, with nothing claimed between the two points.

**The steady-state midpoint only** (the lead's tightening of 27 November). The engine's kinetics
at the calibration levels are candidate held-out readouts, so the check records and reports the
steady-state activation midpoint and nothing else.
- It saves voltages and steady-state activation targets only: no time constant, time course,
  tail current or current trace.
- No world is stepped. The run view's readouts form each gate's time constant beside its target,
  and the driver never reads it.

**The world** (world()). It follows FR-50 phase 2's World 1 (validation/fr50/engine.world_1),
with FR-64's H row (validation/fr64/worlds.pair_world), and is `cells.model.resolved_pump_tissue@3`
alone:
- one 1 pL cell on the held bath through its wall patch, at 298.15 K, the law's fixed
  temperature;
- the bath at the preparation's external K and at the level's pH. The H row has valence +1, is
  impermeant and has no buffer, so the shift reads the bath's stored row;
- one Kv1.5 population with the preparation's declaration (declaration()), held closed
  (availability 0), so its readout current is zero;
- the cell's potential set by its charge anchor, V = Q/C. Its other contents are the fixture's
  (validation/tissue/secreted_species_fixtures), and nothing here reads them.

**The engine's midpoint** (midpoint()) is read through the run view.
- For an anchor voltage V_a (Q = C V_a), the definition is parsed and @3's initial state formed.
- The implementation's observe_history, which the runner calls at every observed row, gives that
  state's membrane_voltage_V and channel_targets (gate m).
- Bisection on V_a brackets the crossing of one half between adjacent anchors. The engine's
  midpoint is the mean of the bracket's two voltage readouts.

**Criteria, fixed before the first run** (check-01; unchanged since).
- MIDPOINT_TOLERANCE_V = 1e-15 V. The rounding it allows is the pH's round trip (|sigma| times a
  few ulps of the pH, under 1e-16 V for these sigmas) and the bracket's width (an ulp or two of
  V, about 1e-18 V).
- **1.** Each preparation's engine midpoint shift equals the declared shift dV(acid) -
  dV(control) within the tolerance. dV is validation/fr64/closed_forms.ph_shift, in 50-digit
  decimals at the bath's own binary64 h.
- **2.** Each engine midpoint equals the law's -6.0 mV plus its level's dV within the tolerance.

Run from the checkout, with the gate environment (PYTHONPATH=src JAX_ENABLE_X64=1
JAX_PLATFORMS=cpu): `python -m validation.fr63.calibration_check OUT_DIR`, where OUT_DIR must not
exist. It writes run_inputs.json first (the revision and the checkout's status and diff,
validation/executed_sources.checkout), then declarations.json and results.json, or FAILURE.json.
"""

import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path

import numpy as np

from cells.definitions.specs import parse_spec
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.registry.models import get_model
from validation import executed_sources
from validation.fr64 import closed_forms
from validation.tissue import secreted_species_fixtures as fx

MODEL = "cells.model.resolved_pump_tissue@3"
LAW = "cells.channel.kv1p5_mh@1"
CELL, BATH = "cell_0", "bath"
WALL = f"wall_{CELL}"
POPULATION = "kv15"
TEMPERATURE_K = 298.15  # The law's fixed temperature (kv1p5_mh.TEMPERATURE_K); room temperature.
CELL_PH = 7.3  # The cell's H row, read by nothing: every shift here reads the outside.
# cells.channel.kv1p5_mh@1's m target is the sigmoid of (V_r + 6.0 mV)/6.4 mV (SPEC-006): its midpoint.
LAW_MIDPOINT_V = D("-0.0060")
MIDPOINT_TOLERANCE_V = D("1e-15")
BRACKET_V = 1e-3  # The bisection starts 1 mV either side of the declared midpoint.
PRECISION = 50

# Each preparation's two calibration levels, control first, as the Lean track transcribed them
# (decimal strings as printed). Errors are each source's: SEM for Trapani and Korn and for
# Longobardo et al.; "as printed" for Kehl et al. (the report's §1 and §6).
PREPARATIONS = {
    "trapani2003": dict(
        study="Trapani and Korn (2003), HEK293",
        doi="10.1016/S0006-3495(03)74842-5",
        source="lean/checks/data/trapani2003_kv15_ph.json: trapani2003_kv15_ph, panel_F (Fig. 1F)",
        ph=("7.3", "6.8"),
        midpoint_mV=("-15.3", "-3.6"),
        error_mV=("0.8", "2.4"),
        error_kind="SEM",
        n=(5, 3),
        external_K_mM="10",
    ),
    "longobardo2001": dict(
        study="Longobardo et al. (2001), Ltk-",
        doi="10.1038/sj.bjp.0704251",
        source="lean/checks/data/paired_calibration_measurements.json: "
        "longobardo2001_kv15_controls@1 (Fig. 1, drug-free controls)",
        ph=("7.4", "6.5"),
        midpoint_mV=("-14.2", "3.1"),
        error_mV=("2.1", "0.7"),
        error_kind="SEM",
        n=(38, 27),
        external_K_mM="4",
    ),
    "kehl2002": dict(
        study="Kehl et al. (2002), HEK293",
        doi="10.1113/jphysiol.2001.014456",
        source="lean/checks/data/paired_calibration_measurements.json: "
        "kehl2002_kv15_potassium@1 (Fig. 2, 3.5 mM external K)",
        ph=("7.4", "6.4"),
        midpoint_mV=("-18.3", "-10.5"),
        error_mV=("1.9", "1.2"),
        error_kind="as printed (SEM, or SD of a fit)",
        n=None,  # None given for the midpoints; FR-63's 6 is the 3.5 mM gmax group's.
        external_K_mM="3.5",
    ),
}
LEVELS = ("control", "acid")


def _text(value):
    """A binary64 as its shortest round-trip string, a Decimal as written."""
    return repr(float(value)) if isinstance(value, float) else str(value)


def calibration(key):
    """The secant and its uncertainty (mV, mV per pH unit), in 50-digit decimals. The shift's
    standard error is the two reported errors in quadrature, the groups taken as independent and
    the pH as exact; sigma's is that over |delta pH|. offset_mV is the law's control midpoint less
    the preparation's: the declaration moves the law's curve and does not align it (FR-64 note
    §8)."""
    prep = PREPARATIONS[key]
    with localcontext() as ctx:
        ctx.prec = PRECISION
        (p0, p1), (m0, m1), (e0, e1) = (
            tuple(D(x) for x in prep[k]) for k in ("ph", "midpoint_mV", "error_mV")
        )
        shift, shift_se = m1 - m0, (e0 * e0 + e1 * e1).sqrt()
        sigma, sigma_se = shift / (p1 - p0), shift_se / abs(p1 - p0)
        offset = LAW_MIDPOINT_V * 1000 - m0
        sigma_V = float(sigma / 1000)
    return dict(
        shift_mV=str(shift),
        shift_se_mV=str(shift_se),
        sigma_mV_per_ph=str(sigma),
        sigma_se_mV_per_ph=str(sigma_se),
        offset_mV=str(offset),
        shift_V_per_ph=sigma_V,
    )


def declaration(key):
    """The population's FR-64 declaration for one preparation: its m gate on the outside pH, the
    secant as sigma (V per pH unit), its control as the reference, and the interval between its
    two levels as the window. Sources are the world's registration's (D361), so it carries no
    source key."""
    control, acid = (float(D(x)) for x in PREPARATIONS[key]["ph"])
    return {
        "ph": {
            "side": "outside",
            "shift_V_per_ph": calibration(key)["shift_V_per_ph"],
            "reference_ph": control,
            "ph_window": [acid, control],
        }
    }


def h_mM(ph):
    """The free proton concentration (mM) of a pH, in binary64 (the convention of
    rapid_proton_buffer.PH_REFERENCE_mM: pH = -log10(h / 1000 mM))."""
    return 1000.0 * 10.0**-ph


def level_ph(key, level):
    return float(D(PREPARATIONS[key]["ph"][LEVELS.index(level)]))


def declared_shift(key, level):
    """dV (V) at the level's bath, 50-digit closed form at the bath's own binary64 h."""
    shift = declaration(key)["ph"]
    return closed_forms.ph_shift(
        h_mM(level_ph(key, level)), shift["shift_V_per_ph"], shift["reference_ph"]
    )


def world(key, level, anchor_V):
    """The check's world (module docstring) for one preparation and level, the cell's potential
    anchored at anchor_V (V). It is parsed and observed, never stepped."""
    prep = PREPARATIONS[key]
    raw = fx.world(cells=((CELL, 1.0),), nodes=(), contacts=(), faces=())
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = m.pop("inner_model")  # @3 alone: the composite fixture's inner, no operator.
    m.pop("operators", None)
    if m["id"] != MODEL:
        raise RuntimeError(f"the fixture's inner model is {m['id']}, not {MODEL}")
    m["temperature_K"] = TEMPERATURE_K
    m["species"].append(dict(id="H", valence=1))
    cell = m["cells"][0]
    bath = next(n for n in m["extracellular"] if n["id"] == BATH)
    wall = next(p for p in m["membranes"] if p["id"] == WALL)
    bath["initial_amount_fmol"]["K"] = float(D(prep["external_K_mM"])) * bath["volume_pL"]
    bath["initial_amount_fmol"]["H"] = h_mM(level_ph(key, level)) * bath["volume_pL"]
    cell["initial_amount_fmol"]["H"] = h_mM(CELL_PH) * cell["volume_pL"]
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["H"] = 0.0
    x["material_balance_atol_fmol"]["H"] = 1e-10
    valence = {s["id"]: s["valence"] for s in m["species"]}

    def ions(node):
        return math.fsum(valence[s] * a for s, a in node["initial_amount_fmol"].items())

    bath["fixed_charge_equivalent_fmol"] = -ions(bath)
    charge = wall["capacitance_F"] * anchor_V  # World 1's charge anchor.
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - ions(cell)
    m["channels"] = [
        dict(
            id=POPULATION, membrane_id=WALL, kinetic_law=LAW, max_permeability_m_per_s=1e-9,
            abundance=1.0, initial_gate=[0.01, 0.9],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
            voltage_shift={"gates": {"m": declaration(key)}},
        )
    ]  # fmt: skip
    e["channel_controls"] = [
        dict(channel_id=POPULATION, schedule=[dict(time=0.0, availability=0.0)])
    ]
    x["channel_capacity"] = 1
    return raw


def observe(key, level, anchor_V):
    """(V, m target) of the world's initial state, through the run view (module docstring)."""
    spec = parse_spec(world(key, level, anchor_V))
    impl = get_model(spec.model)
    state, layout = impl.initial_values(spec)
    history = type(state)(*(np.asarray(v)[None] for v in state))
    seen = impl.observe_history(np.zeros(1), history, layout, [0.0], spec)
    voltage = float(np.asarray(seen.membrane_voltage_V)[0, 0])
    return voltage, float(np.asarray(seen.channel_targets)[0, 0, 0])


def midpoint(key, level):
    """The bracket of the crossing m = 1/2 between adjacent anchors, through the run view."""
    centre = float(LAW_MIDPOINT_V + declared_shift(key, level))
    lo, hi = centre - BRACKET_V, centre + BRACKET_V
    (v_lo, m_lo), (v_hi, m_hi) = observe(key, level, lo), observe(key, level, hi)
    if not m_lo < 0.5 <= m_hi:
        raise RuntimeError(f"{key} {level}: the start bracket does not hold the crossing")
    steps = 2
    while True:
        mid = lo + (hi - lo) / 2
        if not lo < mid < hi:
            break
        v, m = observe(key, level, mid)
        steps += 1
        if m < 0.5:
            lo, v_lo, m_lo = mid, v, m
        else:
            hi, v_hi, m_hi = mid, v, m
    return dict(
        anchor_V=[lo, hi],
        voltage_V=[v_lo, v_hi],
        m_target=[m_lo, m_hi],
        midpoint_V=(v_lo + v_hi) / 2,
        observations=steps,
    )


def judge(key, rows):
    """The criteria (module docstring) for one preparation's two levels."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        dv = {level: declared_shift(key, level) for level in LEVELS}
        expected = {level: LAW_MIDPOINT_V + dv[level] for level in LEVELS}
        declared = dv["acid"] - dv["control"]
        mids = {level: D(rows[level]["midpoint_V"]) for level in LEVELS}
        shift = mids["acid"] - mids["control"]
        shift_misfit = abs(shift - declared)
        misfits = {level: abs(mids[level] - expected[level]) for level in LEVELS}
    out = dict(
        declared_dV_V={level: str(v) for level, v in dv.items()},
        declared_midpoint_shift_V=str(declared),
        midpoint_shift_V=str(shift),
        shift_misfit_V=str(shift_misfit),
        midpoint_misfit_V={level: str(v) for level, v in misfits.items()},
        shift_within=shift_misfit <= MIDPOINT_TOLERANCE_V,
        midpoints_within=all(v <= MIDPOINT_TOLERANCE_V for v in misfits.values()),
    )
    out["passes"] = out["shift_within"] and out["midpoints_within"]
    return out


def _json(value):
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, (float, D)):
        return _text(value)
    return value


def write(path, value):
    with path.open("x") as stream:
        json.dump(_json(value), stream, indent=2, allow_nan=False)
        stream.write("\n")


def provenance(root, argv):
    import jax

    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return dict(
        driver="validation/fr63/calibration_check.py",
        revision=revision,
        checkout=executed_sources.checkout(root),
        argv=argv,
        started_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.version,
        numpy=np.__version__,
        jax=jax.__version__,
        platform=platform.platform(),
        cpus=sorted(os.sched_getaffinity(0)),
        environment={k: os.environ.get(k) for k in ("JAX_ENABLE_X64", "JAX_PLATFORMS")},
        engine_models=[MODEL, LAW],
        criteria=dict(midpoint_tolerance_V=str(MIDPOINT_TOLERANCE_V)),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("out", type=Path, help="the run's folder, which must not exist")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True)
    root = Path(__file__).resolve().parents[2]
    write(args.out / "run_inputs.json", provenance(root, sys.argv))
    try:
        shifts = {
            key: dict(study=prep["study"], voltage_shift={"gates": {"m": declaration(key)}})
            for key, prep in PREPARATIONS.items()
        }
        write(args.out / "declarations.json", shifts)
        results = dict(
            calibration={key: calibration(key) for key in PREPARATIONS},
            sources=PREPARATIONS,
        )
        checks = {}
        for key in PREPARATIONS:
            rows = {}
            for level in LEVELS:
                started = time.perf_counter()
                found = midpoint(key, level)
                seconds = time.perf_counter() - started
                print(
                    f"{key} {level}: midpoint {found['midpoint_V']!r} V "
                    f"({found['observations']} observations, {seconds:.1f} s)",
                    flush=True,
                )
                ph = level_ph(key, level)
                rows[level] = dict(ph=ph, bath_h_mM=h_mM(ph), **found)
            checks[key] = dict(levels=rows, verdict=judge(key, rows))
            print(f"{key}: passes {checks[key]['verdict']['passes']}", flush=True)
        results["checks"] = checks
        results["passes"] = all(c["verdict"]["passes"] for c in checks.values())
        results["finished_utc"] = datetime.now(timezone.utc).isoformat()
        executed_sources.refuse_untracked(root, "FR-63's development check")
        write(args.out / "results.json", results)
        print(f"all pass: {results['passes']}", flush=True)
        return 0 if results["passes"] else 1
    except Exception:
        write(args.out / "FAILURE.json", dict(traceback=traceback.format_exc()))
        raise


if __name__ == "__main__":
    sys.exit(main())
