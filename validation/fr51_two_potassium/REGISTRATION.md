# FR-51's two-potassium registration: does the block's reference voltage follow external potassium? (D353, D355, D356)

**Status.** A registration by the lead, 25 November 2026, tagged before the 10 and 20 mM curves of Panama and Lopatin
(2006), Fig. 3E, are read. It is value-silent about them. **It is not blind:** its rule was written by someone who knows
the study's 60 mM result (section 7), and section 5 says what that means.

## 1. What is tested, and on what engine

**The composition** (D356): an always-open potassium population, `kleak_always_open@1`, on `resolved_pump_tissue@3`,
carrying `open_channel_block_weighted_modes@1` with its block referenced to the potassium reversal,
`{"reversal_of": "K"}` (the **reversal arm**), against the same composition with the block referenced to the membrane
voltage (the **absolute-voltage arm**). The observable is the blocked population's current divided by the matched free
population's current.

- **The engine** is pinned to FR-51's landing, 955765ef (tag `fr51-landed-2026-11-24`), before FR-64 changes the
  declaration (D361). The runs, and the scoring code, use a clean frozen snapshot of it, because the scorer imports the
  engine's `reversal_potential`.
- **The calibration is frozen:** the 5.4 mM trace only, in Lean's `lean/checks/data/panama2006_external_k_anchor.json`
  (main 18198688; its sha256 is in section 9). It holds the two-mode block and the half
  crossing, −74.05 mV with bracket [−75, −70], from two independent readings of the 5.4 mM trace on the 5 mV grid;
  internal K 145 mM, 300 K, free spermine 7 µM. Every parameter is held fixed at 10 and 20 mM.
- **What the composition predicts.** A block that depends on voltage through V − E_K only has a half crossing that moves
  exactly with E_K. At fixed internal K, E_K moves by RT/F ln(K_o/5.4): **+15.93 mV at 10 mM and +33.85 mV at 20 mM**.
  With an absolute-voltage reference it moves by 0.

## 2. The engine check, before any extraction is scored

The runner builds the composition at 5.4, 10 and 20 mM in each arm, with the calibration's K(0) rule as Lean states it
(`lean/PROGRESS.md`, section `fr51-panama-holdouts`, at 18198688: K(0) = c_B exp[z (M − E_0) / (1000 R T / F)] for each
mode of midpoint M and valence z, with E_0 the concentration-based K reversal at 5.4 mM in the reversal arm and 0 in the
absolute-voltage arm), so the runner chooses no mapping of its own. It finds the half crossing of the blocked/free ratio by
a root-find on the compiled clamp, not on a grid.
- **Pass, all of:**
  - the two arms' 5.4 mM crossings coincide, as that construction requires, within 1e-6 mV;
  - in the reversal arm the crossings at 10 and 20 mM move from the 5.4 mM crossing by the predicted shifts, and in the
    absolute arm by 0, each within 1e-6 mV.
- **The plants,** each of which must be caught by one of those:
  - the membrane-voltage reference in the reversal arm (its shifts are 0);
  - the reversal's sign flipped (the crossings move the other way);
  - external K of 11 mM for 10 (that shift moves by 2.46 mV);
  - internal K of 150 mM for 145 in the reversal arm (its 5.4 mM crossing moves by 0.88 mV, so the arms no longer
    coincide; the shifts do not move).
- A failure stops the registration: the shifts above are then not the engine's.

## 3. The extraction

- **The source** is the published Fig. 3E (DOI 10.1113/jphysiol.2005.097741), the 10 and 20 mM Kir2.1 traces of total
  normalized current on its logarithmic ordinate.
- **The reader's sheet** is filed, with its sha256, before the first reader starts, as an addition to this registration
  that changes none of it. It is written by an agent who reads only the panel's printed labels and legend, and it holds: the
  image's sha256 and its 654 by 408 raster; the pixel tick table, copied out of the anchor file (the ticks only); and how
  the 5.4, 10 and 20 mM traces are identified in the panel by its own markers. It holds no reading of any curve. If it
  cannot say which traces are which, the registration stops.
- **The window is fixed:** every 5 mV from −100 to 0 mV, 21 samples per trace, inside the tick range. A sample that cannot
  be read is null. Values are relative currents to two decimals.
- **Two fresh readers,** the lead's, each independent of the other, read the image with the reader's sheet only. They are
  barred from: this registration and every prediction in it; the anchor file and its values; the other reader's file; the
  paper's text and abstract; and Lean's replay and records. Neither is the search that saw the figure. No other extraction
  is scored, and no one else's is used.
- **A control, read blind:** each reader also reads the 5.4 mM trace over the same window. The frozen scorer's
  `half_crossing` on those rows must bracket it in [−75, −70] mV; if not, that reader's whole file is void. Two void files,
  or one void and one valid, leave the levels unresolved.
- **No re-read and no third reader.** A file the scorer refuses (an error, or rows outside its rules) counts as unresolved
  at both levels, whatever else is in it.
- **The image** is kept on disk outside the repository with its sha256; it is not committed.
- **Scoring** is by the frozen `lean/checks/panama_holdout_shift.py`, taken from 18198688 and checked against the sha256
  in section 9, unedited, on each reader's file, run on the 955765ef snapshot. Per level it names the closer model:
  concentration reversal, absolute voltage or unresolved. The level's outcome is the common name of the two readers; if
  they differ, the level is unresolved. Both files are kept whatever the outcome, and the larger of two readings is never
  chosen.

## 4. What each level can decide

These are the frozen scorer's own decisions on synthetic curves (logistic, with the anchor's slope, read to two decimals),
run on the 955765ef engine. s is the true shift of the half crossing.

| Level | Absolute voltage named | Unresolved | Concentration reversal named |
| --- | --- | --- | --- |
| 10 mM (prediction 15.93) | s < 3.95 mV | 3.95 to 14.20 | s ≥ 14.20 |
| 20 mM (prediction 33.85) | s < 8.95 mV | 8.95 to 24.20 | s ≥ 24.20 |

- **Both point predictions are decided at both levels.** At 10 mM the reversal prediction lies 1.73 mV inside its edge,
  less than a typical reading difference; at 20 mM it lies 9.65 mV inside.
- **An exact 0.50 reading** on a grid sample widens the bracket to 10 mV, so a level can read unresolved at an edge: at
  10 mM a crossing at −60 mV, and at 20 mM at −50 mV.
- **A constant reading error** of up to 0.04 in relative current does not change an outcome away from an edge, and near the
  10 mM edge it can.
- **The 20 mM level is the deciding one; 10 mM is supporting.**

## 5. The verdict

- **The external arm passes** when 20 mM names the concentration reversal and 10 mM does not name absolute voltage.
- **It fails** when 20 mM names absolute voltage.
- **It is undetermined** otherwise: 20 mM unresolved, or a contradiction (20 mM reversal and 10 mM absolute voltage),
  which is reported as such.

**This rule was written with a known result in view.** D355 records this study's 60 mM shift, from Lean's non-blind
replay, as 51.6 mV against a measured reversal shift of 53.2 and a concentration-based 62.3. The ratio of observed to
concentration-based shift there is 0.83. At 0.83 the rule gives 10 mM unresolved and 20 mM reversal, which is a pass. So
a pass is the expected result if the study behaves at 10 and 20 mM as it did at 60 mM, and it is not a test of the size.

- **What a pass cannot show.** It rejects a shift at 20 mM below about seven tenths of the concentration-based one (24.20
  of 33.85 mV). It cannot tell a Nernst shift (ratio 1.0) from a shift that tracks the measured reversal (0.83), which is
  D355's open gap.
- **Reported, unjudged, per level:** the observed shift over the predicted one, against 1.0 and 0.83, and each reader's
  shift and both signed residuals. No measured reversal enters, since no frozen source for it was named.
- **A pass** lifts the composition's development-only label for external-potassium changes only, and the label says:
  direction, and a shift of at least about seven tenths of the concentration-based one at 20 mM; size not judged. It is one
  study's prospective indication, beside the non-blind two-lab replay of D355.
- **A fail or an undetermined result** leaves it development-only, changes no law, and is recorded (D351).

## 6. The internal arm, separate and already seen

Lopatin and Nichols (1996), Fig. 3: raising internal K from 150 to 625 mM moved the half-block voltage by about +5 mV
(about −20 to −15). Lean's replay gives the reversal reference a prediction of −36.3 mV and the membrane-voltage reference
0 (Lean's figure, computed on engine 7ca7c9c1; the same concentration ratio gives −36.9 mV at this registration's 300 K,
so Lean's is consistent with about 295 K, which was not checked).
- **This arm is not blind,** and nothing is extracted for it. The observed +5 mV is close to the absolute-voltage arm and
  not to the reversal arm. It supports the scope line (the reversal reference holds for changes of the ion outside the cell
  only), and decides nothing in section 5.
- Any other internal level in that figure is reserved, and is read only under an amendment to this registration.

## 7. What had been seen, disclosed

- **The lead** has seen Lean's exploratory replay at 5.4 to 60 mM and Ishihara's three levels (D355), the published
  four-level slope of 0.98, the internal endpoints above, and the anchor file, which holds only the 5.4 mM calibration. The
  lead chose the two-model rule, the windows and the thresholds knowing the 60 mM ratio of 0.83. The lead has not opened
  `kir_spermine_potassium.json` and knows no reading of the 10 or 20 mM curves.
- **Lean's search** saw the full figure including the intermediate traces, and had read their reversal voltages and the
  published four-level fit (D356). By its recall it extracted no normalized current at 10 or 20 mM. It is not a reader.
- **Both reserved responses come from one study,** so this is a within-study test, not a second confirmation.

## 8. Roles and changes

- **The engine check** is run by an agent that has seen neither the 10 nor the 20 mM curve, and whose script and result are
  filed before the first reader's file is scored.
- **The sheet's writer** (section 3) is another agent, and reads no curve.
- **The two readers** are fresh agents (section 3).
- **The judge** is the frozen scorer. The lead records the outcome against section 5 and changes nothing after the first
  read.
- Nothing here is edited after the tag except by a dated, disclosed erratum, tagged before it is used.

## 9. Pinned at the tag

| What | Value |
| --- | --- |
| Engine | 955765ef (`fr51-landed-2026-11-24`) |
| Scoring code | `lean/checks/panama_holdout_shift.py`, main 18198688, sha256 `d85181e8b8d8447ab23b4c48c2b109c93873890158d1cc18373c9ea76bd11fd7` |
| Calibration | `lean/checks/data/panama2006_external_k_anchor.json`, main 18198688, sha256 `377f7ab7d18da93e27fa29e5e5c6f9e90f5cc0a6c1dca751fa31e1f8789d4551` |
| Scorer's own decision table | section 4, from a run on the 955765ef snapshot |
