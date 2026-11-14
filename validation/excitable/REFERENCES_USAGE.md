# Using the excitable-tissue references (interface only)

How to run the independent references for Track E's excitable-tissue probe and read their
outputs without reading their source. They were written from the equations appendix
`docs/EXCITABLE_TISSUE_EQUATIONS.md` (draft of 14 November 2026). That file was read from Track
E's branch, first at db488771, then the revision 99fddc35, which added §8.5 and §8.6. Their
author never read `src/cells`, the probe driver `validation/tissue/excitable_probe.py` or the
probe's records. Readings of the appendix are listed under [Readings](#readings-of-the-appendix-taken-here);
disagreements go to the lead.

| Module | What it gives |
| --- | --- |
| `validation/excitable/excitable_reference.py` | The model of §2–§6 (cells, chain, laws, pump, junctions, stimuli, kicks), the integrator, and the observables of a run (crossings, peaks, the largest dV/dt, junction voltages, excursions) |
| `validation/excitable/excitable_limits.py` | The linearised discrete passive cable and the strong-coupling (lumped-cell) limit |
| `validation/excitable/excitable_protocols.py` | §8.1–§8.6 as functions, and the driver that computes their numbers (`--out DIR`; about 1.5 hours on one loaded core) |

Self-tests: `tests/unit/test_excitable_references.py` (16 tests, tier 1, 14 s). They check:
- the laws against the appendix's rate forms;
- the fast right-hand side against the appendix's readable form, to 1e-10 relative;
- conservation through the junctions;
- the rests and the kick;
- the observables against brute force;
- the passive chain against the linear cable;
- the strong-coupling limit, and activation in order.

They also check independence: nothing here imports `cells`, `validation.tissue` (the probe) or
`validation.division`. The one import from another reference is
`validation.coupling.piecewise_ode`, the shared segment-by-segment integrator.

## Conventions

- **Units:** SI, with amounts in fmol, volumes in pL, concentrations in mM (= mol/m³), V in volts
  and t in seconds. The species are in the appendix's order, (Na, K, M, P), with z = (+1, +1, −1, −1).
- **Constants are inputs:** `er.Constants(faraday_C_per_mol, gas_J_per_mol_K, temperature_K)`.
  `er.appendix_constants(T=310.0)` gives §1's exact SI products, N_A e and N_A k_B; pass 298.15 for
  the catalogue cross-check.
- **The appendix's cells:** `er.appendix_tissue(point, n=1, s_c=0.0, **changes)` builds §2, §3,
  §5, §6 and §7.1 at a point.
  - The points (`er.POINTS`) are `"heredity"` and `"point2"` (§7.2), and §8.6's `"A"` (the
    generic cell) and `"B"` (its fallback).
  - `**changes` overrides any `Tissue` field, for example `availability_NaV=0.0`, `stimuli=…` or
    `pump_on=False`.
- **Per-cell and per-junction arrays.** `c_m_F_per_m2`, `P_NaV_m_s`, `P_Kir_m_s`, `P_Kv_m_s` and
  the three availabilities are scalars or arrays over cells. `s_c` is a scalar or an array over
  the n − 1 junctions, junction i joining cells i and i + 1.
  - A junction's availability multiplies its flux, so it is declared as s_c × r_gj on that
    junction.
  - This is how §8.5's segment is built (`ep.segment_chain`).
- **The start:** `er.Start(V, gates_at_V, kick_V=0.0)`.
  - V(0) is V, and the charge follows: q = C V(0).
  - The gates start at their steady state at `gates_at_V`.
  - The composition is the tissue's `initial_mM` (§7.1's H).
  - A kick raises the initial Na amount by C·ΔV/F, so V(0) = V + ΔV with the gates unchanged
    (§6).
- **Stimuli:** `er.stimulus(cells, P, (t_on, t_off), ...)` adds a Na and a K leak of
  permeability P, on for t in each window [t_on, t_off). Every window edge is an integration
  breakpoint.
- **The state:** per cell, the charge q/(F·1e-15), N_Na, N_K and the six gates (NaV m h, Kir m h,
  Kv m h). M follows from the charge, and P is constant.

## Running and reading a run

```python
from validation.excitable import excitable_reference as er, excitable_protocols as ep
tissue = er.appendix_tissue("point2", n=20, s_c=1000.0,
                            stimuli=(er.stimulus((0, 1, 2), 1e-6, (0.002, 0.003)),))
run = er.simulate(tissue, er.Start(V=V_rest, gates_at_V=V_rest), 0.05, record=(0.01, 0.05))
run.at[0.01]["V"]                       # every cell's V (V) at a record: an integration end
run.V(0.0123)                            # anywhere, by re-integration from the stored steps
run.crossing(5, -0.03)                   # first upward crossing of -30 mV by cell 5 (s), or None
run.crossing(5, level, direction=-1, t_from=t_peak)  # downward
run.extremum(5, 0.0, 0.05)               # (t, V) of cell 5's peak
run.extremum(5, 0.0, 0.05, quantity="dVdt")  # (t, largest dV/dt)
run.junction_voltage_max(15)             # (t, V_15 - V_16) at the largest |V_15 - V_16|
run.excursions()                         # V_min, V_max, the largest |V_i - V_i+1| and two flags
```

- **`simulate(tissue, start, t_end, record=(), rtol=1e-10, atol=None, method="Radau")`.**
  Radau uses the block-tridiagonal Jacobian sparsity from four cells up. `er.ATOL` gives 1e-14 fmol
  for the charge (6e-14 V), 1e-12 fmol for the amounts and 1e-12 for the gates; a partial dict
  overrides it.
- **Refining observables.**
  - Crossings, peaks, junction maxima and the largest dV/dt are located on the cubic Hermite
    interpolant of the stored steps (V with dV/dt from the right-hand side).
  - They are then refined by Newton's method on re-integrations from the bracketing step.
  - Measured against brute force (fine records of independent runs): the peak to 2e-16 V, the
    largest dV/dt to 4e-14 V/s, a crossing to 3e-17 s.
- **`excursions()`** reports what §4 and §6 ask to be reported:
  - the smallest and largest V of any cell at the stored steps;
  - the largest |V_i − V_{i+1}|;
  - `outside_gate_domain` (V outside [−0.120, 0.060] V);
  - `junction_over_limit` (above 0.120 V).

  The reference evaluates the laws outside their domain without refusing; the engine refuses.

## The protocols (`excitable_protocols`, `ep`)

| Function | Gives |
| --- | --- |
| `ep.rest_potential(point)` | §8.1: V_H at heredity; otherwise V(2 s) from H at V_H |
| `ep.single(point, V_rest, kick=, nav=, kir=, kv=, stimuli=, t_end=0.08)` | One cell from its rest (a Run) |
| `ep.ap_measures(run, V_rest)` | §8.2's measures: peak V, time to peak, largest dV/dt and its time, APD50 and APD90, the return within 5 mV and its time, V at 80 ms, overshoot, excursions |
| `ep.kick_threshold(point, V_rest, tol=1e-7)` | §8.2's threshold as a bisection bracket {threshold, lo, hi, runs} |
| `ep.single_panel(point, V_rest, threshold)` | §8.2's six runs |
| `ep.stimulus_threshold(point, V_rest, rel_tol=1e-6)` | §8.3's P_stim threshold (bisection in log P) |
| `ep.s1s2(point, V_rest, P, deltas)` and `ep.s2_response(run, t2)` | §8.3's S1–S2 and its response rule |
| `ep.chain(V_rest, n, s_c, P_stim=None, windows=, point="point2", nav=, kir=, kv=, t_end=0.15)` | §8.4's chain; P_stim defaults to 1e-6 (c_m/0.05) |
| `ep.activation_times(run)`, `ep.sampled_activation(run, cell, t, dt)` | Exact activation times, and the engine's linear interpolation on rows every dt |
| `ep.conduction_velocity(times, n)`, `ep.range_cv(times, lo, hi)` | CV (cells/s) over N/3 ≤ i ≤ 2N/3, or over cells lo..hi |
| `ep.chain_measures(run)` | Activation times, peaks by cell (the end cell included), propagation, CV, excursions |
| `ep.segment_chain(V_rest, point, r_na=, r_gj=)` and `ep.segment_measures(run)` | §8.5: the segment's case and its report, including the largest abs(ΔV) of each segment junction, at the refined maximum and at the stored steps |
| `ep.cm001_part(point, V_rest, ...)` | §8.6 for candidates A and B |
| `el.passive_linearisation`, `el.linear_cable_response`, `el.neumann_modes`, `el.space_constant_cells`, `el.lumped_cell` | The limits |

## Results (track-e-protocols-01, rtol 1e-10)

The evidence is in `/mnt/workspaces/Cells/independent-references-20261114-01/` (`HANDOFF.md`):
- `track-e-protocols-01/results.json` has every number, run from the frozen snapshot
  `track-e-snapshot-01` of cd622adf;
- `track-e-followup-01/` holds the follow-ups, from `track-e-snapshot-02` of 8898ec99;
- `block-site-A/` holds the blinded comparison.

**§8.1 rests** (2 s from H at V_H):

| Cell | Rest |
| --- | --- |
| heredity | V_H = −79.556260 mV |
| point 2 | −79.558916 mV |
| A | −79.558918 mV |
| B | −79.559338 mV |

**§8.5, candidate A** (N = 40, s_c = 1000, stimulus 2e-7 m/s): block, cell 15 activating without
cell 24, holds from combined r = 0.2 down.

| Case | s_c·r_gj | Block | Segment delay (ms) | CV 6–14 / 16–23 / 25–31 (cells/s) | Entry max abs(V15 − V16) (mV) | Largest V (mV), cell |
| --- | --- | --- | --- | --- | --- | --- |
| control | 1000 | no | 1.087 | 8171 / 8277 / 8354 | 18.134 | 56.626, 39 |
| combined 0.9 | 900 | no | 1.183 | 8231 / 7614 / 8283 | 19.613 | 56.630, 39 |
| combined 0.8 | 800 | no | 1.304 | 8296 / 6920 / 8213 | 21.359 | 56.634, 39 |
| combined 0.7 | 700 | no | 1.461 | 8369 / 6189 / 8146 | 23.454 | 56.639, 39 |
| combined 0.6 | 600 | no | 1.676 | 8452 / 5416 / 8088 | 26.026 | 56.646, 39 |
| combined 0.5 | 500 | no | 1.990 | 8548 / 4590 / 8052 | 29.279 | 56.655, 39 |
| sodium 0.7 | 1000 | no | 1.172 | 8171 / 7627 / 8235 | 18.481 | 56.635, 39 |
| sodium 0.5 | 1000 | no | 1.262 | 8171 / 7052 / 8129 | 18.747 | 56.644, 39 |
| coupling 0.5 | 500 | no | 1.631 | 8548 / 5678 / 8097 | 28.586 (exit 23–24: 30.480) | 56.635, 39 |
| coupling 0.3 | 300 | no | 2.192 | 8801 / 4342 / 7897 | 38.681 (exit: 43.061) | 56.644, 39 |
| combined 0.3 (ladder) | 300 | no | 3.514 | 8801 / 2712 / 8246 | 39.557 | 56.680, 39 |
| combined 0.2 (ladder) | 200 | **yes** | – | 8983 / – / – | 48.818 | 47.792, 13 |
| combined 0.1 (ladder) | 100 | yes | – | 9248 / – / – | 66.306 | 50.096, 13 |
| combined 0.05 (ladder) | 50 | yes | – | 9453 / – / – | 84.506 | 51.983, 14 |
| combined 0.03 (ladder) | 30 | yes | – | 9565 / – / – | 97.122 | 53.227, 14 |
| **combined 0.02** (extension) | **20** | yes | – | 9634 / – / – | **106.012** | 53.972, 14 |
| **combined 0.01** (extension) | **10** | yes | – | 9714 / – / – | **118.079** | 54.923, 15 |
| combined 0.007, 0.005, 0.003, 0.002, 0.001 (ladder) | 7, 5, 3, 2, 1 | yes | – | – | 122.665, 126.069, 129.807, 131.821, 133.943 | 55.392–56.435, 15 |

- **The blinded comparison.** The values were recorded at 20:49:52Z, before §8.5's withheld
  engine values were read at 20:50:03Z (`block-site-A/COMPARISON.md`).

  | Quantity | Engine | Reference |
  | --- | --- | --- |
  | s_c·r_gj = 20 | 106 mV | 106.012 mV |
  | s_c·r_gj = 10 | 118.1 mV | 118.079 mV |
  | Largest V over §8.5's cases | +56.65 mV at most | +56.655 mV |

  - The entry maximum crosses the engine's 120 mV junction limit between s_c·r_gj = 10 and 7.
  - At rtol 1e-11 with atol / 100 (the follow-up), the junction maxima move by at most 2.3e-14 V
    (7.5e-15 V at the block sites), the largest V by 3.5e-14 V and the activation times by 9e-16
    s. Every block outcome is unchanged.
- **Peaks by cell in A's control:** interior cells 9–25 peak at 40.39–40.47 mV, and the end
  cell at 56.63 mV, the sealed end. Every propagating case's largest V is the end cell's.
- **Coupling-only rungs** (follow-up, r_Na = 1).
  - Block from s_c·r_gj = 50. The wave crosses the segment and fails at its exit, 23–24.
  - The largest segment junction voltage is 76.061, 95.442, 113.440, **120.643** and 126.069 mV
    at s_c·r_gj = 100, 50, 20, 10 and 5. The value at 10 is at the exit junction.
  - So in this arm the engine's 120 mV limit is exceeded already at 10, while 20 keeps 6.6 mV of
    margin.

**§8.5, point 2** (stimulus 1e-6 m/s): every reduced case blocks, so the combined cases are not
extended. The control propagates.

| Case | Block | Last activated, last above 0 mV | Entry max abs(V15 − V16) (mV) | Largest V (mV), cell |
| --- | --- | --- | --- | --- |
| control | no | 39, 39 | 19.040 | 34.345, 39 |
| combined 0.5 | yes | 20, 16 | 31.615 | 19.727, 0 |
| combined 0.3 | yes | 17, 15 | 42.380 | 20.757, 14 |
| combined 0.2 | yes | 16, 15 | 51.490 | 23.235, 14 |
| combined 0.1 | yes | 16, 15 | 67.350 | 26.562, 14 |
| combined 0.05 | yes | 15, 15 | 82.041 | 28.902, 15 |
| sodium 0.3 | yes | 19, 15 | 19.687 | 19.727, 0 |
| sodium 0.1 | yes | 18, 15 | 19.908 | 19.727, 0 |
| coupling 0.1 | yes | 23, 23 | 67.319 | 26.564, 14 |
| coupling 0.03 | yes | 15, 15 | 91.158 | 30.730, 15 |

- The control's segment delay is 4.239 ms.
- Its CV is 2082, 2124 and 2134 cells/s over cells 6–14, 16–23 and 25–31.

**§8.2 single cell** (kick thresholds by bisection; every run is 80 ms):

| Cell | Kick threshold (mV), bracket |
| --- | --- |
| heredity | 42.59302 (42.59296–42.59302, 22 runs) |
| point 2 | 28.36578 (28.36573–28.36578) |

| Cell, run | Kick (mV) | Peak (mV), at (ms) | Largest dV/dt (V/s) | APD50, APD90 (ms) | Back within 5 mV (ms) | V at 80 ms (mV) |
| --- | --- | --- | --- | --- | --- | --- |
| heredity, twice (capped) | 60.000 | 16.328, 4.545 | 23.215 | –, – | – | 7.465 |
| heredity, twice, NaV off | 60.000 | −19.556, 0 | −0.081 | – | – | −27.009 |
| heredity, twice, all off | 60.000 | −19.556, 0 | −0.035 | – | – | −22.493 |
| heredity, threshold + 0.5 mV | 43.093 | 1.155, 10.047 | 9.817 | –, – | – | −4.877 |
| heredity, threshold − 0.5 mV | 42.093 | −1.273, 11.183 | 8.360 | –, – | – | −6.731 |
| heredity, threshold − 5 mV | 37.593 | −18.303, 80.0 | 1.694 | – | – | −18.303 |
| point 2, twice | 56.732 | 34.818, 1.533 | 81.831 | 3.614, 12.163 | 18.171 | −82.703 |
| point 2, twice, NaV off | 56.732 | −22.827, 0 | −0.095 | – | – | −50.376 |
| point 2, twice, all off | 56.732 | −22.827, 0 | −0.031 | – | – | −25.417 |
| point 2, threshold + 0.5 mV | 28.866 | 4.260, 28.300 | 20.196 | 6.423, 31.248 | – | −74.505 |
| point 2, threshold − 0.5 mV | 27.866 | −5.182, 44.107 | 10.472 | 10.107, – | – | −64.236 |
| point 2, threshold − 5 mV | 23.366 | −56.193, 0 | −0.010 | – | – | −58.614 |

- **The heredity cell fires but does not repolarise within 80 ms:** at twice threshold V is still
  +7.5 mV at 80 ms. It has no Kv1.5, so APD50 and APD90 are undefined.
- **Point 2 repolarises,** with an APD90 of 12.2 ms at twice threshold.
- **Just below point 2's threshold** a slow regenerative event peaks at −5.2 mV at 44 ms, short
  of an overshoot.
- **"–"** marks a level not reached within the 80 ms window. A threshold means "within the 80 ms
  window".

**§8.3 stimulus and recovery** (1 ms at 2 ms):

| Cell | P_stim threshold (m/s), bracket | S1–S2 at twice it, Δ (ms): 5, 8, 10, 12, 15, 20, 25, 30, 40, 60 |
| --- | --- | --- |
| heredity | 6.999239e-08 (6.999233e-08–6.999239e-08, 25 runs) | no response at any interval: V never falls back below −30 mV |
| point 2 | 4.047999e-08 (4.047996e-08–4.047999e-08) | no, no, no, no, no, yes, yes, yes, yes, yes (S2's peak +4.3 mV at 20 ms, +31.7 mV at 60 ms) |

**§8.4 chain** (point 2, N = 20, cells 0–2 at 1e-6 m/s for [2, 3) ms):

| s_c | Propagates | CV (cells/s) | t(19) (ms) | Peak, cell 10 / end cell (mV) | Largest junction voltage (mV) |
| --- | --- | --- | --- | --- | --- |
| 10 | no: only cells 0–2 activate; cell 3 peaks at −60.9 mV | – | – | −79.2 / −79.6 | 95.3 |
| 30 | no: only cells 0–2 activate; cell 3 peaks at −45.7 mV | – | – | −77.8 / −79.2 | 81.7 |
| 100 | yes | 572.45 | 31.264 | 13.75 / 31.60 | 66.4 |
| 300 | yes | 1112.14 | 16.758 | 10.12 / 33.53 | 51.8 |
| 1000 | yes | 2093.32 | 9.529 | 11.38 / 34.36 | 34.3 |
| 3000 | yes | 3760.17 | 6.128 | 14.73 / 34.65 | 21.0 |
| 1000, NaV off | no (cells 0–3 cross −30 mV electrotonically) | – | – | – / −64.3 | – |
| 1000, passive (NaV, Kv, Kir off) | no (likewise) | – | – | – / −58.5 | – |

- **CV grows a little faster than √s_c:** by 1.94, 1.88 and 1.80 per threefold step.
- **The length check:** N = 40 at s_c = 1000 gives CV 2123.74 cells/s, against 2093.32 at N = 20.
- **The coupling bracket:** block at s_c ≤ 42.090 and propagation at s_c ≥ 42.488, bisected in log
  s_c to 1%. No block appears above it, up to s_c = 1e4.
  - **Its blocking end checked** (`track-e-bracketcheck-02`). At s_c = 42.090 the wave is still
    blocked under `ep.wave_outcome`, the horizon-independent rule: no new activation for 0.148 s
    after the last one, against a required 0.02 s.
  - So the bracket is not an artefact of the 150 ms horizon.
- **The end cell peaks highest,** at the sealed end, as in §8.5.

**§8.4, continued** (s_c = 1000):

| Quantity | Value |
| --- | --- |
| Capture threshold | 1.30717e-07 m/s; bracket 1.30607e-07 (no capture) to 1.30717e-07 (capture), 15 runs. About 3.2 times the single cell's §8.3 threshold. The no-capture end holds under `ep.wave_outcome`: no new activation for 0.147 s (`track-e-bracketcheck-02`) |
| Far-end S1–S2 interval | **Window-dependent.** 27.982 ms (bracket 27.976–27.982 ms, 17 runs) within the driver's window, which ends 30 ms after the first wave's far-end arrival plus S2's onset (about 69.5 ms). With a 300 ms window (`checks-final/`), Δ = 27.976 ms also gives a far-end second wave, a slow one arriving at 155.8 ms. So the long-window interval lies below 27.976 ms; it was not re-bracketed. §8.4 names no window |

**§8.6, the 0.01 F/m² cells** (rests −79.558918 mV for A and −79.559338 mV for B):

| Cell | Kick threshold (mV) | Twice threshold, capped: peak (mV), largest dV/dt (V/s), APD90 (ms) | Kick to −20 mV: peak (mV) | Kick to 0 mV: peak (mV) | Stimulus 2e-7: peak (mV), APD90 (ms) | Chain, s_c 1000: CV (cells/s), peak interior / end (mV) | Largest V: single, chain (mV) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 24.84478 (lower end 24.84472) | 55.610, 247.40, 3.830 | 55.857 | 56.019 | 34.317, 4.876 | 8361.6, 41.26 / 56.62 | 56.019, 56.620 |
| B | 30.85115 (lower end 30.85110) | 35.773 (kick capped at 60 mV), 95.73, 8.108 | 35.725 | 37.643 | 24.571, 9.594 | 5412.0, 19.39 / 36.09 | 37.643, 36.088 |

- Every run's largest V is below +60 mV. A's highest is the chain's end cell, at +56.620 mV.
- **The stimulus rows.** Their largest dV/dt, 864.49 V/s for both A and B, is the stimulus
  onset's, so the APD90 shown runs from 2 ms.
  - Measured from the stimulus end, 3 ms (`checks-final/`): APD50 1.873 and 2.973 ms, APD90 3.876
    and 8.594 ms for A and B.
  - The upstroke merges with the stimulus: after 3 ms, dV/dt is largest at 3 ms itself, 172.9 and
    78.6 V/s.
- **The NaV-off and all-off arms** do not fire. They decay passively from the kick (`ep.single_panel`
  and the follow-up's `cm001_arms`).
- **APD in the main run.** The main run (cd622adf) gave APD values for non-firing arms, measured
  from a "largest dV/dt" that falls after the peak, some of them negative. These are not action
  potentials, and their APD is undefined. Since 868ae4c9 `ap_measures` reports None for them.
  Every APD in the tables above is of a firing run.

**The limits.**
- **The passive cable** (point 2, N = 20, s_c = 1000, NaV, Kv and Kir unavailable; stimulus on
  cells 0–2 for [2, 3) ms):

  | Quantity | Value |
  | --- | --- |
  | g_m | 1.4773e-11 S |
  | g_j | 1.0457e-07 S |
  | Space constant | 84.1 cells |
  | Passive rest current at V_r | −4.83e-13 A (the passive cell drifts from point 2's rest) |

  - The nonlinear chain against the linear discrete cable, as a largest difference and the
    response's size:

    | P_stim | Largest difference | Response |
    | --- | --- | --- |
    | 1e-9 | 1.2e-8 V | 0.76 mV |
    | 2e-9 | 2.6e-8 V | 1.4 mV |
    | 4e-9 | 5.7e-8 V | 2.7 mV |

  - The difference grows with the stimulus: the composition change the linearisation freezes,
    and the linearisation's second order.
- **The strong-coupling limit** (point 2, N = 20, against the lumped cell with the stimulus
  averaged over the chain): the largest difference in V at 5, 10 and 30 ms.

  | s_c | 5 ms | 10 ms | 30 ms |
  | --- | --- | --- | --- |
  | 1e4 | 15.7 mV | 8.87 mV | 1.33 mV |
  | 1e5 | 4.83 mV | 1.30 mV | 0.19 mV |
  | 1e6 | 0.51 mV | 0.13 mV | 0.021 mV |

  - It is first order in 1/s_c from 1e5. At 5 ms, inside the action potential's upstroke, the
    approach is slower.

**§9's convergence check** (rtol 1e-11 with atol / 100, against rtol 1e-10):

| Observable | Difference |
| --- | --- |
| Point 2's rest | 2.8e-14 V |
| Peak (twice-threshold runs) | ≤ 8.9e-15 V |
| Largest dV/dt | ≤ 3.1e-12 V/s |
| Its time | ≤ 5.0e-11 s |
| APD50 and APD90 | ≤ 4.0e-12 s |
| Chain activation times (s_c = 1000) | ≤ 2.4e-16 s |
| Chain peaks | ≤ 1.6e-14 V |
| CV | 7.2e-11 cells/s |

Both kick-threshold brackets hold at the tighter tolerances. With §8.5's block-site check, this
puts the reference's own error at 1e-11 or below on every reported observable. The quoted
threshold brackets, set by the bisection tolerance, are wider than that.

## Readings of the appendix taken here

1. **Peak and overshoot.** A "peak" is the largest V of the run from t = 0, so a kick's own V(0)
   counts. An "overshoot" is a peak above 0 mV.
2. **APD_x** runs from the time of the largest dV/dt to the first time after the peak at which V
   falls to V_peak − (x/100)(V_peak − V_rest).
3. **"Returns within 5 mV of rest within 60 ms":** the first time after the peak at which V falls
   to V_rest + 5 mV is at most 60 ms. The time is reported.
4. **Thresholds** are bisection brackets, with lo failing and hi succeeding. The threshold
   reported is hi.
5. **The chain's activation time** is the first upward crossing of −30 mV, exact.
   `sampled_activation` gives the appendix's "interpolated linearly" reading on rows every dt; the
   appendix names no row interval.
6. **CV** uses the cells N/3 ≤ i ≤ 2N/3: cells 7 to 13 of 20, and 14 to 26 of 40. §8.5's ranges
   (6–14, 16–23, 25–31) are inclusive.
7. **Propagation and block.**
   - In §8.4, a wave propagates when every cell activates; otherwise it is blocked.
   - In §8.5, block is the appendix's own definition: cell 15 activates and cell 24 does not.
8. **The capture threshold and the far-end S1–S2 interval** are taken at s_c = 1000, the
   coupling of §8.4's controls; the appendix does not name one. The far-end interval also
   depends on the observation window, which the appendix does not name (see Results).
   - "Passive" has NaV, Kv and Kir unavailable, in §8.2's wording.
   - The far-end second wave is a second upward crossing of −30 mV by the last cell after S2's
     onset.
9. **The coupling bracket** extends §8.4's scan downwards until block, and probes s_c = 1e4
   above it. Each change of outcome is bisected in log s_c to 1%.
10. **§8.5's "largest |V_i − V_{i+1}| … taken at every step".** The reference gives both the
    continuous maximum, refined between steps, and the maximum at its own stored steps. The
    engine's value at its fixed steps can be no larger than the continuous one.
11. **§8.6's kicks "to −20 mV and to 0 mV"** set V(0) = −20 mV and 0 mV, with ΔV = target − V_rest
    and the gates at rest. §8.2's threshold and panel are computed too. §8.2's NaV-off and
    all-off arms at those two kicks are in the follow-up (`cm001_arms`).
12. **A's coupling ladder.** At the coordinator's request, the reference adds combined cases below
    §8.5's list, down to r = 0.001 (s_c·r_gj = 1). They give the block-site junction voltages
    across s_c·r_gj, including the range below 10 that the engine's junction law refuses.

## Known limits

- **Speed.** The right-hand side is NumPy on small arrays. Under load, a single 80 ms action
  potential takes about 4 s, a 20-cell chain over 0.1 s about 30 s, and a 40-cell segment case
  about 40 s, all at rtol 1e-10.
- **The passive cable** (`el.linear_cable_response`) freezes the composition. The passive chain
  departs from it by a relative 1e-5 per millivolt of response: the ion entry the stimulus
  causes, which the pump senses. Against the passive chain with no stimulus, it holds to 1e-9 V.
- **The strong-coupling limit** is first order in 1/s_c. Measured during the stimulus, the
  difference falls tenfold per decade of s_c.
- **The appendix is a draft**, and the references follow the revision read (99fddc35), the head
  of Track E's branch for that file when this was written.
- **§1's catalogue cross-check at 298.15 K was not run.** The temperature is an input, so
  `er.appendix_constants(298.15)` runs it.
- **`ep.wave_outcome`**, the horizon-independent propagation predicate of the follow-ups, is
  checked by the evidence (`bracket_check`) rather than by a unit test.
