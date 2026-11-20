# FR-7: public Kir2.1 readings for the measured response (D238 item 4, D241)

**What this is:** a retrospective source for FR-7's measured response, one channel's abundance
against membrane voltage. The user supplied it on 20 November 2026 (D241). It holds group means
and their plotted standard errors, read from published figures.

**The files:**
- `kir21_ambrosini_2014_readings.csv`: 12 group means and their plotted SEMs from Ambrosini et
  al. (2014). The study covers Kir2.1 wild type and K346T in human U251MG cells:
  - Fig. 3E, the membrane-fraction signal;
  - Fig. 3F, the resting membrane voltage;
  - Fig. 4B, total protein remaining at 0, 3, 6 and 12 h of a chase.

  The pixel positions of every mean and error-bar tip are kept.
- `kir21_public_data_v1.json`: the studies' public locations, sizes and SHA-256 checksums of the
  source files, and each digitized axis's tick coordinates. Qile et al. (2019) gives a 2.6 h
  half-life for wild-type human Kir2.1 protein in HEK293T cells.

**Precision of the readings:**
- one vertical pixel is about 0.34 percentage points in Fig. 3E, 0.094 mV in Fig. 3F, and 0.0023
  of the control signal in Fig. 4B;
- a reread of the voltage bars in the journal PDF moved no mean by more than 0.13 mV;
- the authors report a voltage contrast of about -6 mV; the bar edges read -5.45 mV.

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

**Attribution:**
- Figure readings adapted from Ambrosini et al. (2014), Hum. Mol. Genet.,
  doi:10.1093/hmg/ddu201, (c) the authors, CC BY 4.0
  (https://creativecommons.org/licenses/by/4.0/).
- Qile et al. (2019), Front. Physiol., doi:10.3389/fphys.2019.00863, (c) the authors, CC BY 4.0.
- No figure images are committed.
