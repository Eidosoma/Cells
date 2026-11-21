# Kettner et al. (2003), Fig. 3: the yeast V-ATPase's current-voltage curves (FR-29, D258)

**What this is:** Fig. 3 of Kettner et al. (2003) read as numbers, for FR-29's question of whether
a proton-return mode can work. The figure shows the averaged difference current of the yeast
vacuolar proton pump (V-ATPase) against tonoplast voltage at seven pairs of cytosolic and vacuolar
pH. The values are readings, not the authors' data. Table 2's reversal rows were known before the
reading, so any use is retrospective.

**What Fig. 3 shows** (its legend and the article's Methods):
- **Panel A:** vacuolar (pipette) pH 5.0, with cytosolic (bath) pH 5, 6, 7.5 and 8.5.
- **Panel B:** cytosolic pH 7.5, with vacuolar pH 7.5, 6 and 4.1. It has no vacuolar pH 5.0 curve;
  that pair is panel A's cytosolic pH 7.5 curve.
- **Fuel:** every curve was energized with AAP medium: 5 mM ATP, 5 mM ADP and 10 mM phosphate as
  potassium salts, with 125 mM KCl, 5 mM MgCl2, 0.5 mM EGTA and 5 mM MES titrated with Tris.
- **Each curve is a difference current:**
  - it averages at least three recordings;
  - each recording is the energized ramp minus the non-energized (no ATP) ramp, made as in
    Figs. 1B–C and 2B;
  - the Methods also describe blocking with bafilomycin in ATP and subtracting, citing the authors'
    earlier paper. The legend points to the subtraction without ATP.
- **Units:**
  - current is a density in mA m⁻²: each recording was divided by its membrane area, taken from
    capacitance at 1 µF cm⁻². It is not normalized to a maximum;
  - voltage is cytoplasmic minus vacuolar potential (the Bertl et al. 1992 convention);
  - positive current carries positive charge from the cytosol into the vacuole, the pumping
    direction.
- **Range:** −80 to +60 mV (the ramps ran to +80 mV). No error bars are drawn.
- **Seven of Table 2's eight rows are in Fig. 3.** The row at vacuolar pH 3.1 (reversal above
  +40 mV) comes from Fig. 2.
- **The authors' caveat** (Fig. 1's legend): features of difference curves at positive voltages come
  partly from channel activity in the control recording. The limb above about +20 mV is the least
  reliable part of every curve.

**The files:**
- `kettner2003_fig3_readings.csv`: every curve every 5 mV from −80 to +60 mV, 178 rows.
  - The current, the pixel position, and the number and spread of the columns read.
  - In panel B, from −5 mV up, one row per voltage holds the band where the three curves overlap,
    with the band's lower and upper edges (`band_I_mA_per_m2`).
  - `identity` says how each value is tied to its curve (below).
  - `flags`:
    - `trace_end`: the −80 mV end, where several traces start with a transient;
    - `touching`: no light pixel separates the trace from a neighbour there;
    - `axis`: the trace is near the axis line, so some of its pixels may be cut;
    - `hidden_by_axis`: interpolated between the nearest columns 4 px clear of the axis line.
- `kettner2003_fig3_reversals.csv`: each curve's zero crossing beside Table 2's row.
- `kettner2003_sources.json`:
  - the article's location and licence;
  - the figure image's address, size and SHA-256;
  - each panel's axis calibration;
  - the label boxes left out;
  - the reader's waypoints, so the reading can be repeated from the same image.

**How it was read** (the FR-7 lane, 20 November 2026):
- **The image:** PMC's 400 × 774 px figure, as the article page links it. PMC's Open Access mirror
  holds no files for this article.
- **Resolution:** one pixel is 0.42 mV and 0.41 mA m⁻².
- **Calibration:**
  - voltage comes from a straight line through each axis's eight tick marks, −80 to +60 mV
    (residual SD 0.34 mV);
  - current comes from the ±50 ticks, with zero at the drawn axis line.
- **Reading a trace:**
  - the traces are continuous, averaged ramps, so there are no points to read;
  - the reader set waypoints along each trace;
  - in each pixel column, the reading is the darkness-weighted centre of the trace's pixels within
    5 px of the path. The window stops half way to a neighbouring path, and the axis line, tick
    marks and labels are left out;
  - a sample is the median of the columns within ±1 mV.

**Which curve is which:**
- **The curves are labelled only at −80 mV.** Every zero crossing lies left of its curve's first
  overlap with another, so the reversals come from labelled stretches (`labelled`: followed
  continuously from the label, apart from any other curve).
- **Panel A, right of the overlaps:** curves are followed by slope continuity (`slope_continuity`).
  - These calls are clear:
    - cytosolic pH 6 crosses pH 5 near −24 mV;
    - pH 7.5 joins pH 5 near −4 mV;
    - pH 8.5 joins pH 5 near +11 mV;
    - each leaves on its own slope.
  - **One call is not clear:** cytosolic pH 6 and 7.5 touch from about +16 to +23 mV, then part
    with the upper line rising more steeply. At this resolution crossing can't be told from
    touching, so those samples are marked `ambiguous_pH_cyt_6_or_7.5`.
    - Read as crossing, at +60 mV pH 7.5 reads about +25 and pH 6 about +20 mA m⁻².
    - Swapped, pH 6 reads about +25 and pH 7.5 about +20.
  - At +60 mV the order from the top is pH 7.5 (or 6), 6 (or 7.5), 8.5, then 5.
- **`overlapping`:** two curves share one dark run. The reading window stops half way between
  the reader's two paths, so the two values there differ because of where the paths were put, not
  because of the image. Read such a pair as one value, give or take half their difference. Seven
  rows in panel A carry it (where pH_cyt 6 meets 5, 6 meets 7.5, and 8.5 meets 5), and six in
  panel B.
- **Panel B:**
  - vacuolar pH 6 and 4.1 join just after their zero crossings, near −17 mV (`overlapping`);
  - all three curves join near −5 mV and can't be separated (`not_separable`). Above −5 mV the
    band they form is 2 to 7 mA m⁻² wide.

**The reversals against Table 2:**

| Cytosolic / vacuolar pH | Fig. 3, read (mV) | Table 2 (mV, mean ± SE, n) | Read minus Table 2 |
| --- | --- | --- | --- |
| 6.0 / 5.0 | −55.1 (−55.7 to −54.5) | −59.8 ± 3 (9) | +4.7 mV, 1.6 SE |
| 7.5 / 5.0 | −30.7 (−31.3 to −30.2) | −34.0 ± 4 (14) | +3.3 mV, 0.8 SE |
| 8.5 / 5.0 | −15.5 (−15.8 to −15.1) | −17.5 ± 5 (6) | +2.0 mV, 0.4 SE |
| 7.5 / 6.0 | −35.8 (−36.9 to −34.7) | −38.6 ± 9 (3) | +2.8 mV, 0.3 SE |
| 7.5 / 4.1 | −23.2 (−23.6 to −22.9) | −25.6 ± 1 (4) | +2.4 mV, 2.4 SE |
| 5.0 / 5.0 | no crossing; lowest reading +4.5 mA m⁻² | below −80 (5) | consistent |
| 7.5 / 7.5 | no crossing; lowest reading +6.2 mA m⁻² | below −80 (4) | consistent |

- **All five crossings lie positive of Table 2's means,** by 2.0 to 4.7 mV, and within 2.4 SE of
  each row.
- **Each gap times its curve's slope at reversal is somewhat steadier than the gaps,** 0.9 to
  1.5 mA m⁻² (2 to 4 px) against 2.0 to 4.7 mV. The method spread alone moves the 7.5 / 6.0 product
  from about 0.5 to 1.3. This is an observation, not a cause.
  - Table 2 gives the mean of single recordings' reversals, while Fig. 3 averages the curves
    themselves.
  - A small current offset in the averaged curves or in the drawing would also give it.
- **The ranges in brackets are spreads between reading methods,** not errors. The methods are a
  bracket between the nearest clear columns and straight-line fits over ±12 and ±25 px, each 3 and
  4 px clear of the axis line.
- **The gaps are small against the spread between recordings.** Table 2's SE times √n puts that
  spread at 9 to 16 mV for four rows and 2 mV for 7.5 / 4.1, so only that row's gap is large against
  it.
- **The choice of zero adds 0.2 to 0.7 mV.** Taking zero from the tick fit instead of the drawn axis
  would move each crossing that much further positive (`zero_row_shift_mV`).

**A check on the units:** the Results give Fig. 1's example as about 4 pA at 0 mV on a vacuole
about 9 µm across (about 250 µm²), which is about 16 mA m⁻². The cytosolic pH 7.5 / vacuolar pH 5.0
curve here reads 12.2 mA m⁻² at 0 mV.

**Attribution:**
- Readings of Fig. 3 of Kettner C, Bertl A, Obermeyer G, Slayman C, Bihler H (2003),
  "Electrophysiological Analysis of the Yeast V-Type Proton Pump: Variable Coupling Ratio and
  Proton Shunt", Biophys. J. 85(6):3730, doi:10.1016/S0006-3495(03)74789-4.
- © 2003 Biophysical Society, free to read at PMC with no CC licence. Only bare cited values are
  recorded (D227); no image or text is reproduced.
