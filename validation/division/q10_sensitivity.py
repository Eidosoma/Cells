"""Q10 development study: S5a's compact worlds' sensitivity to the partition time and the aperture.

docs/CELL_DIVISION_S5_DESIGN.md §4.2 and §8.3 Q10. This is a development study, not a judged
run. No tolerance is registered yet, so every change is reported raw, absolute and relative to
the nominal run, and nothing is called insensitive. Once tolerances are registered, a quantity
whose change exceeds its tolerance takes t_p and a_0 into its band.

Engine models: resolved_pump_composite@1 over resolved_pump_tissue@3, with
membrane_entity_state@1, isopotential_partition@1 and cytoplasmic_bridge_closure@1 (linear
closure over 1 ms); scheduled_membrane_insertion@2 and restricted_cleft_lumen@2 in the furrow
world; electrode_current_injection@1 in the injected variants.

Worlds (tests/partition_fixtures; nominal values around the heredity cell, built from neither J1
input, so the J2 bright line holds):
* 1->2: the compact bridge world, end 6 ms;
* 1->2->4: the daughters divide at 5 ms, after every variant's bridge has closed, end 7 ms;
* furrow 1->2: the furrow world (onset at 1 ms, cleft lumen), end 6 ms.
Each world runs without and with 1 pA into d1. The current flows over one window shared by every
variant, from 3 ms (the latest partition time) until 6 ms, or until d1's own division at 5 ms.
So a change of t_p does not change the injected charge.

Ranges, declared here, one parameter at a time:
* the partition time t_p in {1, 2, 3} ms (exact multiples of dt; the furrow world's {2, 3} ms,
  after its onset), against the nominal 2 ms;
* the aperture a_0 in {0.4, 1, 1.8} x 2 nm. G_b0 = 2 a_0 sigma_cyt then spans the declared
  sigma_cyt band, 0.2 to 0.9 S/m, at the default 0.5 S/m: sigma_cyt enters only through G_b0
  (§4.2). The widest a_0 stays within the 1 ms step bound (0.88 of it in the symmetric worlds).
  This range runs at t_p = 3 ms, against the t_p = 3 ms run. Only there is the bridge open
  while the current flows; at the nominal t_p it has closed first and a_0 cannot act.

Compared at the last two records, after every variant's divisions and closure:
* each live patch's voltage;
* each live cell's amounts;
* the bridge's exchange (its transfer plus its record);
* the furrow world's lumen volume and composition.

Usage: python -m validation.division.q10_sensitivity OUTPUT_DIR (through
scripts/run_detached.sh; about 30 runs, each compiling, about 15 minutes on one core).
"""

import json
import sys
import time
from pathlib import Path

import jax
import numpy as np

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from tests import partition_fixtures as fx

STATUS = "Development study for Q10 (S5a); not judged; no tolerance registered"
TAU = 0.001  # s, linear closure.
APERTURES = (0.4, 1.0, 1.8)  # x fx.APERTURE_M.
INJECTION_A = 1e-12
INJECTION_START = 0.003  # s: the latest partition time, so the window is every variant's.
SECOND = 0.005  # s: the 1->2->4 daughters' division, after every variant's closure.
NOMINAL_TP = 0.002


def world(family, tp, scale, injected):
    """(raw, compare records) of one variant."""
    bridge = ("linear", TAU, scale * fx.APERTURE_M)
    current = INJECTION_A if injected else None
    window = dict(injection=current, injection_start=INJECTION_START)
    if family == "1->2":
        raw = fx.divided(at=tp, end=0.006, bridge=bridge, **window)
        records = [0.005, 0.006]
    elif family == "1->2->4":
        raw = fx.divided(at=tp, end=0.007, second=SECOND, bridge=bridge, **window)
        records = [0.006, 0.007]
    else:
        raw = fx.cleft_divided(at=tp, end=0.006, bridge=bridge, **window)
        records = [0.005, 0.006]
    raw["experiment"]["observation_times"] = [0.0, *records]
    return raw, records


def quantities(result, spec):
    """{quantity: array} at the compare records (module docstring)."""
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    h, times = result.history, np.asarray(result.times)
    # The compare records are the last two observation times. The history holds a row at every
    # accepted step (every dt here; each time once, as the report's accepted_times_s shows), so
    # its rows are found by time, and the observations' by position.
    observed = np.asarray(result.observations.times)
    seen = [len(observed) - 2, len(observed) - 1]
    rows = [
        int(np.flatnonzero(np.isclose(times, observed[k], rtol=0, atol=1e-12))[0]) for k in seen
    ]
    e = [j.id for j in spec.model.junctions].index("bridge_1")
    out = {"patch_voltage_V": [], "cell_amount_fmol": [], "bridge_exchange_fmol": []}
    lumen = "lumen_volume_increment_pL" in type(h)._fields
    if lumen:
        out |= {"lumen_volume_pL": [], "lumen_concentration_mM": []}
    for i, k in zip(rows, seen, strict=True):
        state = model.STATE_TYPE(*(np.asarray(v[i]) for v in h))
        q = model.view(p, state, xp=np)
        v = adapter.patch_voltages(adapter.node_potentials(state, q, xp=np), q, xp=np)
        out["patch_voltage_V"].append(np.asarray(v)[np.asarray(q.membrane_active)])
        amounts = np.asarray(p.amount_reference) + np.asarray(state.amount_increment)
        out["cell_amount_fmol"].append(amounts[:, np.asarray(q.active)])
        exchange = (
            np.asarray(state.junction_transferred)[:, e]
            + np.asarray(state.partition_retired_junction_transferred_fmol)[:, e]
        )
        out["bridge_exchange_fmol"].append(exchange)
        if lumen:
            cleft = [c.id for c in spec.model.extracellular].index("cleft")
            out["lumen_volume_pL"].append(np.asarray(result.observations.lumen_volume_pL)[k, cleft])
            out["lumen_concentration_mM"].append(
                np.asarray(result.observations.lumen_concentration_mM)[k, :, cleft]
            )
    return {k: np.asarray(v) for k, v in out.items()}


APERTURE_TP = 0.003  # s: the a_0 range is run here, where the open bridge meets the current.


def variants(family):
    """[(label, t_p, aperture scale, baseline label)], one parameter at a time.

    The t_p range is compared with the nominal (2 ms). The a_0 range runs at t_p = 3 ms and is
    compared with the t_p = 3 ms run: only there is the bridge open (3 to 4 ms) while the
    current flows (from 3 ms), so only there can a_0 act. At the nominal t_p the bridge has
    closed before any asymmetry, and the a_0 arm would read exactly zero.
    """
    times = (0.002, 0.003) if family == "furrow 1->2" else (0.001, 0.002, 0.003)
    rows = [("nominal", NOMINAL_TP, 1.0, None)]
    rows += [(f"t_p={tp * 1e3:g} ms", tp, 1.0, "nominal") for tp in times if tp != NOMINAL_TP]
    base = f"t_p={APERTURE_TP * 1e3:g} ms"
    rows += [(f"a_0={s:g}x at {base}", APERTURE_TP, s, base) for s in APERTURES if s != 1.0]
    return rows


def changes(nominal, other):
    out = {}
    for name, value in nominal.items():
        delta = np.abs(other[name] - value)
        scale = np.max(np.abs(value))
        out[name] = dict(
            max_abs_change=float(np.max(delta)),
            max_relative_change=float(np.max(delta) / scale) if scale > 0 else None,
        )
    return out


def main(output):
    jax.config.update("jax_enable_x64", True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        status=STATUS,
        engine_models=[
            "resolved_pump_composite@1",
            "resolved_pump_tissue@3",
            "membrane_entity_state@1",
            "isopotential_partition@1",
            "cytoplasmic_bridge_closure@1",
            "scheduled_membrane_insertion@2",
            "restricted_cleft_lumen@2",
            "electrode_current_injection@1",
        ],
        ranges=dict(
            aperture_range_at_partition_time_s=APERTURE_TP,
            partition_time_s=[0.001, 0.002, 0.003],
            furrow_partition_time_s=[0.002, 0.003],
            aperture_scale=list(APERTURES),
            nominal_aperture_m=fx.APERTURE_M,
            sigma_cyt_S_per_m=fx.SIGMA_CYT,
            closure="linear",
            closure_time_s=TAU,
            injection_A=INJECTION_A,
            injection_window_s=[INJECTION_START, "end, or d1's division at 5 ms (1->2->4)"],
            second_division_s=SECOND,
        ),
        worlds={},
    )
    for family in ("1->2", "1->2->4", "furrow 1->2"):
        for injected in (False, True):
            key = f"{family}{' + injection' if injected else ''}"
            results, baselines, accepted = {}, {}, {}
            for label, tp, scale, baseline in variants(family):
                raw, records = world(family, tp, scale, injected)
                spec = parse_spec(raw)
                start = time.perf_counter()
                result = run(spec)
                results[label] = quantities(result, spec)
                baselines[label] = baseline
                accepted[label] = np.asarray(result.times).tolist()
                print(f"{key} {label}: {time.perf_counter() - start:.1f} s", flush=True)
            nominal = results["nominal"]
            report["worlds"][key] = dict(
                compared_at_s=records,
                accepted_times_s=accepted,
                nominal={k: v.tolist() for k, v in nominal.items()},
                changes={
                    label: dict(
                        against=baselines[label], **changes(results[baselines[label]], values)
                    )
                    for label, values in results.items()
                    if label != "nominal"
                },
            )
            (output / "q10_sensitivity.json").write_text(json.dumps(report, indent=1) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
