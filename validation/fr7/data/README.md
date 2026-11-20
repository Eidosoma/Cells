# FR-7: public Kir2.1 readings for the measured response (D238 item 4, D241)

**What this is:** a retrospective source for FR-7's measured response, one channel's abundance
against membrane voltage. The user supplied it on 20 November 2026 (D241). It holds group means
and their plotted standard errors, read from published figures.

**The files:**
- `kir21_ambrosini_2014_readings.csv`: 14 group means and their plotted SEMs from Ambrosini et
  al. (2014). The study covers Kir2.1 wild type and K346T in human U251MG cells:
  - Fig. 3E, the membrane-fraction signal;
  - Fig. 3F, the resting membrane voltage;
  - Fig. 3G, the barium-sensitive current density at -100 mV (n = 6);
  - Fig. 4B, total protein remaining at 0, 3, 6 and 12 h of a chase;
  - Supplementary Fig. S2B, the steady-state current density at -140 to -30 mV in 10 mV steps, for
    each variant (a second reader's rows, D254).

  The pixel positions of every mean and error-bar tip are kept. The `reader` column marks who read
  each row: `first_reader` for the user's 12 rows (D241), and `second_reader` for Fig. 3G's two,
  read by the FR-7 lane on 20 November 2026 by the same method from the same image (D249).
- `kir21_public_data_v1.json`: the studies' public locations, sizes and SHA-256 checksums of the
  source files, and each digitized axis's tick coordinates. Qile et al. (2019) gives a 2.6 h
  half-life for wild-type human Kir2.1 protein in HEK293T cells.

**Precision of the readings:**
- one vertical pixel is about 0.34 percentage points in Fig. 3E, 0.094 mV in Fig. 3F, 0.117 pA/pF
  in Fig. 3G, and 0.0023 of the control signal in Fig. 4B;
- a reread of the voltage bars in the journal PDF moved no mean by more than 0.13 mV;
- the authors report a voltage contrast of about -6 mV; the bar edges read -5.45 mV.

**Supplementary Fig. S2B, read from the PDF's embedded image** (page 9, extracted, not rendered):
- **The points sit on the drawn axis at -140 to -30 mV,** exactly the legend's command steps. The
  axis shows no 15 mV junction offset, and the figure doesn't say whether it carries the
  adjustment.
- **Its -100 mV points equal Fig. 3G's means and SEMs,** so its rows are the six-cell means despite
  the legend's "representative"; their n is given as 3G's.
- **Gaps:**
  - wild type at -80 mV is hidden behind K346T's marker and is read from its connecting line;
  - several error bars end inside their markers, and those SEMs are left empty.

**The recording conditions (the article's Methods, for the HEK293 and U251MG patch clamp):**
- bath, mmol/l: NaCl 135, KCl 4.8, CaCl2 1.8, MgCl2 1, glucose 10, HEPES 5; pH 7.4 with NaOH;
- pipette, mmol/l: KAsp 130, KCl 15, MgCl2 1, K2-ATP 2, HEPES 5; pH 7.4 with KOH;
- at room temperature, with no number given;
- IK1 plotted as barium-sensitive currents (1 mmol/l BaCl2 in the bath);
- the data adjusted for a liquid junction potential of 15 mV;
- not stated: the recording configuration, the cells' capacitance, and how Fig. 3F's voltage was
  measured.

**How it may be used (the user's terms, D241):**
- **A retrospective group comparison only.** The group means were visible while the source was
  chosen.
- **Fix the abundance-to-conductance conversion independently of the two voltage means.**
- **What is compared:** the predicted K346T-minus-wild-type voltage contrast against the
  published one.
- **Record which protein pool each model state represents.** Fig. 3E is a relative
  membrane-fraction protein signal, not a count of conducting surface channels. Fig. 4B follows
  total protein.
- **Not supported by these data:**
  - the lifetime of conducting surface units in U251MG cells;
  - persistence after a trigger, which would need voltage measured through recovery and a
    measured trigger-clearance time.
- **The judged run stays pending** until two things are decided: the mapping from measured
  protein to functional surface units, and FR-8's timing.

**The U251 background: Ratto et al. (2019/2020), bare values (D253, D254):**
- **The file:** `u251_background_ratto_2020_values.csv`. It holds the cited numbers the lead read
  from the paper:
  - resting voltage in the IN and OUT cells after a wound assay;
  - membrane resistance and capacitance of the cells with constitutive currents;
  - the capacitance of the cells without currents;
  - the barium-sensitive Kir4.1 maximum conductance and reversal;
  - the junction potential.

  The recording solutions are in the manifest's study entry.
- **Licence:** © Springer, with no CC licence, so only bare cited numbers are recorded. No text or
  figure is reproduced (D227).
- **Not corroboration** of Ambrosini et al. under D248: it comes from a different lab.
- **Comparability with Ambrosini et al.'s recordings:**
  - **Configuration:** whole-cell perforated patch with nystatin, against Ambrosini's presumed
    dialysed whole cell.
    - Nystatin pores pass monovalent ions, chloride included. So Ratto's cytosol moves toward the
      pipette's KCl 140 / NaCl 4 mM, with chloride near 144 mM.
    - Ambrosini's dialysed cytosol has chloride 17 mM and no sodium.
    - **The OUT cells' -34.7 mV is the background's reversal in Ratto's conditions, not in
      Ambrosini's.** A Goldman-Hodgkin-Katz desk estimate (D254) fitted to -34.7 mV puts the same
      background at about -37 mV in Ambrosini's conditions if its non-potassium part is sodium,
      and about -76 mV if it is chloride.
  - **Conductance:** the membrane resistance and capacitance of the cells with constitutive
    currents give a total resting conductance of about 0.046 nS/pF (0.073 at two SEMs).
    - That is an upper bound on the background, since those cells carry Kir4.1 and other currents.
    - There is no lower bound: no membrane resistance is given for the cells without currents.
  - **Other differences:**
    - the cells were polarised by a wound assay;
    - the junction corrections differ, 8.8 mV against 15 mV;
    - both temperatures are unstated;
    - the bath potassium is 5 mM against 4.8 mM.
- **Use:** item 4 stays a consistency check (D254). These values do not make a link able to fail;
  D254 lists what would.

**Many variants: Ross et al. (2025), bare values (CC BY 4.0):**
- **The files:** three of the article's supplementary tables, value for value as printed:
  - `kir21_ross_2025_table_s1.csv` (Table S1), wild type and 71 variants:
    - surface expression by flow cytometry, % of wild type, mean ± SD (n experiments), for 70
      variants, each co-expressed with wild type;
    - "variant only" surface expression for 10 variants, each expressed alone;
    - yeast growth, densitometry relative to wild type, for 20 variants;
    - the authors' surface fitness, the log2 of the surface value;
    - two columns from deep mutational scans: surface fitness scores (MAVEDB, MacDonald et al.
      2023) and function labels the authors read from Coyote-Maestas et al. (2022).
  - `kir21_ross_2025_table_s2.csv` (Table S2): 28 variants in gnomAD v4.1, with ClinVar class,
    frequency and allele count.
  - `kir21_ross_2025_table_s6.csv` (Table S6): current density at -50 and -100 mV, pA/pF,
    mean ± SD (n), for wild type and 13 variants.
- **Surface expression is in Table S1,** and Table S2 holds only gnomAD frequencies. Table S4 (total
  expression by flow cytometry and western blot, and Tagg) is not extracted.
- **The composition mismatch:**
  - the currents come from stable HEK293 lines that each express one variant, so their channels
    are homomeric (the article's Methods as the lead read them; this extraction read only the
    tables);
  - S1's surface column is the variant co-expressed with wild type, so its channels can be
    heteromeric;
  - only D71Y has both a variant-only surface value and a current;
  - across the 10 variants with both surface columns, variant-only over co-expressed runs from
    0.55 (H110Y) to 1.31 (D71Y). Composition moves the surface value by up to about a factor of
    two in this set.
  - **So the co-expressed value is not the abundance of the channels whose current was
    recorded.** A current divided by it mixes composition with per-channel activity.
- **Kept as printed, not corrected:**
  - four surface fitness values are not the log2 of their surface values: R67F and D78G (78 %,
    printed -0.09), N190I (94 %, 0.60) and V295A (78 %, -0.26). The other 65 of the 69 rows with
    both values agree to two decimals. The column's header reads "(% of WT)", and wild type's row
    reads 100;
  - T75R's yeast cell is printed "2.4 ± 0.8 ± (3)*" and D78Y's "1.8 0.8 (3)". Both are recorded
    as SD 0.8 and n 3, with the printed text in the note column;
  - T400M's yeast value is 1 ± 2 (n 3);
  - ClinVar labels differ between S1 and S6 for V123G, S136F, T192I, G206S, P351S and T400M. Each
    file keeps its own table's label;
  - superscript marks have their own columns. W81V's scan score carries a dagger that the caption
    doesn't explain.
- **Not stated in the tables:**
  - the yeast readout's direction. The variants with clear currents read lowest (P351S 0.7, T400M
    1, G206S 1.2), and the near-null ones 1.7 to 2.3. Don't read it as more growth, more function;
  - what S6's n counts;
  - whether S4's totals were measured with the variant alone or co-expressed.
- **Use:** bare values for the user's choice on item 4 (D256). Every value has been seen, so any
  test built on them is retrospective.

**Attribution:**
- Figure readings adapted from Ambrosini et al. (2014), Hum. Mol. Genet.,
  doi:10.1093/hmg/ddu201, (c) the authors, CC BY 4.0
  (https://creativecommons.org/licenses/by/4.0/).
- Qile et al. (2019), Front. Physiol., doi:10.3389/fphys.2019.00863, (c) the authors, CC BY 4.0.
- Ratto et al. (2019/2020), Cell Mol Neurobiol, doi:10.1007/s10571-019-00776-3, (c) Springer, no CC
  licence: bare cited numbers only.
- Values from Ross et al. (2025), J. Biol. Chem. 302(1):110985, doi:10.1016/j.jbc.2025.110985,
  supplementary Tables S1, S2 and S6, (c) the authors, CC BY 4.0.
- No figure images, table images or PDFs are committed.
