# Amendment 1, 24 November 2026: the references agent's four questions, and its readings

**Answered by the registration's author, at the lead's request, before any reference value or
registered engine run exists.**
- **Inputs.** No input changes.
- **Bands.** One wording correction has a band effect, in family D only (item 7). The questions
  exposed it, and it is disclosed there. Every other band stands.
- **Precedence.** Where this amendment and the earlier files of this folder differ, this amendment
  governs.
- **Layout.** The file's layout (sidecars, extra keys, precision) is the lead's and is answered
  separately.

## The four questions

**1. Route 2's place in the file.** Accepted as proposed.
- **Each run with releases** carries a run-level list `route2`, with one entry per fate and sample
  time: fate, `ts_s`, class, value, accuracy and scale.
- **The value** is the `win` class at that sample time: the same value as the `win` series' entry
  there, with the same accuracy.
- **The scale** is the maximum over the outputs of that fate's release counter (READOUTS.md §3).
  The accuracy requirement for a route-2 entry is against this scale. Where the `win` entry meets
  its own requirement but not this one, refine (SPEC.md §3).
- **At an idle fate,** the entry is `constant` +0.0 with null accuracy.
  - The engine side's known-rate form, applied to a release counter that is +0.0 at every output,
    sums +0.0 terms, so it is +0.0 bit for bit.
  - The judge never reads a scale for a constant entry.
- **The blank carries no `route2` list** (item 3).

**2. `released_present_gross_<fate>`.** Accepted as proposed. It goes in `series`.
- It is `constant` +0.0 where all three summands (`pre`, `win` and `post`) are constant +0.0 by
  SPEC.md §4: at every output of an idle fate, at every output of the blank, and at t = 0.
- It is `stepped` everywhere else. This is how CRITERIA.md's P1″ reads it.
- Its scale is its row's (READOUTS.md §3).

**3. Survival at an idle fate, and what the blank carries.**
- **Keep the idle fate's survival entries; do not omit them.**
  - Both counts, `alive_t2` and `alive_ts`, are +0.0 constants with null accuracy. They are the
    `win` class at those times.
  - `"ratio": null` stands for undefined. FR-38's survival readout defines a zero denominator as an
    undefined fraction, and the engine side's route-1 readout reports it as undefined (None).
  - The judge scores these entries under C1:
    - the engine's two counts must be +0.0 bit for bit;
    - its ratio must be reported as undefined;
    - a ratio reported as 0, NaN or infinity fails.

  This keeps the readout's fail-closed rule under test.
- **The blank carries `series` and `checks` only.** It has no `excess_over_blank` (it is the
  blank), no `survival` and no `route2` (it releases nothing), and no `not_compared`.

**4. P8's excess over the blank.**
- **Pair the planted run with its own matched blank.** That blank is the planted world with
  H(0) = 0 and k_I = 0, the store's forward rate × 1.01 included. This is how erratum I, item 5
  defines a matched blank: every other declaration equal.
- **Compare its excess with the honest excess,** the honest run minus the honest blank. Size it the
  same way (SPEC.md §6).
- **On the engine side,** the planted blank is one more world-data run at h, in P8's own process.
- **P8's catch does not depend on this choice:** its criteria also include `n_M` and `n_Mx`.
- No other plant's criteria include the excess, so no other plant needs a planted blank.

## The readings

**5. RT: confirmed.**
- R = fl(N_A · k_B) in J mol⁻¹ K⁻¹, and RT = fl(R · 310.15) in J/mol, divided by 1000 for kJ/mol.
  This is the engine's double path; its `R` is that double product.
- The engine side's G export forms R · T/1000 in 60-digit decimal arithmetic from the exact SI
  values instead.
- The two differ by less than one unit in the last place, far below every accuracy requirement.
  State which you use.

**6. The residue potentials in B: confirmed, and the rule is general.**
- Everywhere, a chain's residue potential is its product row's declared potential divided by the
  chain's L, formed in doubles as the engine forms it, fl(μ°_row/L). At this model's c° of 1000 mM
  no standard-state shift enters.
- So in B: transcription's residues are fl(μ°_R/1200), and translation's (`tl` and `tl_s`, which
  both make P) are fl(μ°_P/400).
- The same rule gives the residues in transit and the hold's standard term in every family.
- **A precision note.** In AN, C and D that quotient, fl(−12442.6668/1200), is the double
  −10.368889000000001 (its `repr`). That is one unit in the last place from SPEC.md §1.1's
  −10.368889. In AF the quotient equals SPEC.md's 8.599269797012601 exactly.
  - Use the quotient.
  - The difference lies about 10⁻¹⁶ relative, far below every accuracy requirement.

**7. Family D: K and Y count in G's scale. Confirmed, and the wording is corrected (disclosed).**
- READOUTS.md §3 sums G's scale over "the rows whose amount moves". That was written for fixed
  volumes.
- In family D the cell's volume moves, so every species row's term
  n_r [μ°_r + ln(n_r/(V c°)) − 1] moves with it. That includes K and Y, whose amounts are constant
  and whose dilution terms make up most of G's change there.
- **The correction.** "The rows whose amount moves" reads "the rows whose term in G moves":
  - in A, B and C, the rows whose amount moves, as before;
  - in D, every species row, K and Y included.
- **Its effect.**
  - It widens family D's G rounding term (CRITERIA.md C2) and your accuracy requirement for D's G
    by the K and Y terms' share.
  - It follows READOUTS.md §3's own principle: the scale is the magnitude of the terms a quantity
    is formed from.
  - No reference value or registered engine run exists, so nothing was fitted.
  - Family D does not decide FR-38's verdict.

**8. P9's G − G(0): confirmed.**
- P9 changes only how the gene unit reads the volume. G remains LAWS.md §5's state function,
  evaluated on the planted run's own state at its current volume V, as the engine side's export
  evaluates it.
- The planted bookings still enter the planted run's heats.

**9. B's `tl_s` readout names: confirmed.** They are `C_tl_s_1` … `C_tl_s_8`, `E_tl_s`, `W_tl_s`,
`int_J_I_tl_s`, `int_S_tl_s` and `int_Q_tl_s`: the engine side's pattern, with the chain's ID
`tl_s` in place of `<chain>`.
