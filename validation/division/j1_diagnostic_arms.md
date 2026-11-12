# J1 diagnostic arms on R-full: rationale (draft for registration)

Drafted on 12 November 2026, after J1 failed on the reference
([verdict](/mnt/workspaces/Cells/cell-division-s0b-20261111-01/rfull-band-01/results/j1_verdict.json):
the band −14.58 to −11.32 mV misses −21.9 to −18.7 mV by 4.1 mV). The machine-readable file is
[`j1_diagnostic_arms.json`](j1_diagnostic_arms.json). No arm has been run.

**J1 is now a selection datum.** Nothing here is a prediction of record, and no parameter is ever
picked from Em. One Rm (488 kΩ) admits readings from −12.8 mV (restricted lumen) to about −40 mV
(bath-exposed patch), so a match alone proves nothing. Arms are therefore also compared on the
0–35 min shape of Em and Rm and, if adopted, on check C1: Em at J1 in eggs cleaving in higher-K
media (dL74 p9–11; −17.1 mV in Steinberg and −12.3 mV in solution B, in dL74's own series).

## Counting parameters

Rm2 fixes one unknown, the access A/L (or its scale κ). An arm that adds an unknown with no
measurement of its own becomes a curve at fixed Rm2. An arm whose new quantities are measured or
geometric gets single values.

| Arm | Change | Added unknowns | Kind |
| --- | --- | --- | --- |
| A1 | Fraction f of new membrane faces the bath | f | Curve to the point where A/L reaches 0 (the parallel reading, f ≈ 0.10) |
| A2 | Extra old-membrane conductance beside the furrow (K83) | G_z | Curve to the point where A/L reaches 0 (≈ 0.88 µS) |
| A3 | Lumen as an annular slit in N fixed rings, growing inward, filled in place with bath fluid (N = 1 is the registered lumen) | none (geometry declared; w and bridge area measured) | Single, ranged over w and bridge area; plus an uncalibrated geometric access as a check |
| A4 | Old-membrane P_Cl (K83; bounded by dL74's null) | x = P_Cl/P_K ≤ 0.12 | Curve |
| A5 | Ca²⁺ | – | Out of scope: no permeability, buffering or extrusion sourced |
| A6 | New-membrane rules from each exposed arm alone; self-consistent fits | none (2 data fix 2 unknowns per arm) | Single, with ranges from each arm's SEs |
| A7 | Access changing with furrow depth; late apposition | α; β | Curves |
| A8 | Cation-selective seal, constant-field access, 0.5-µm gap | – | Computed, not rerun |

## What the sources fix

- **K83 does not fix A2's zone in R-full's frame.** Its 4–30× current ratio (p1760) and decay
  (to 0.66 at 200 µm and 0.42 at 300 µm of the 100-µm value, p1755) were measured in 5% De Boer's.
  Read as conductance in an isopotential bath, they add 1.3–12.8 µS. Rm1 → Rm2 allows 0.88 µS in
  all. Much of K83's pattern may be the extracellular return path, which R-full cannot represent.
- **dL74 bounds A4.** Replacing Cl⁻ by SO4²⁻ (solution G, Table 5, rendered) had no significant
  effect in the uncleaved egg (p8–9), nor did changes in external Cl⁻ in cleaving eggs (p9). A
  2-mV detection limit, which the paper does not state, gives P_Cl/P_K ≤ 0.12 (1 mV gives 0.06).
- **A3's geometry** follows from the bridge (0.26 mm²) and the new-membrane area. The slit mouth
  then sits 99 µm below the surface, beside BdL73's 100–150-µm groove. The slit alone gives
  68–113 kΩ, so a rim restriction remains.
- **The time-course targets** are dLB74's description (p531, V) and Fig. 2 (one egg, F). Em falls
  gradually by about 12 mV over 6–15 min, then depolarises about 3 mV. Rm falls over 6–13.5 min,
  then rises late. R-full steps to −15 mV within about 1 min of onset.

## Rules

R-full only, with no engine runs. No DFS74 or J2 quantity is computed for any model until a revised
model is frozen. Arms are run one at a time. Compute is about 2.5–5 CPU-hours at about 1.5 GB per
process; A3 is untimed, so one synthetic N = 10 pulsed run is timed first. Runs go in three
detached jobs through `scripts/run_detached.sh … 3G --oom-first --cpus 5`. Seven choices await the
lead (`lead_decisions` in the JSON).
