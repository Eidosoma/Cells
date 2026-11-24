# FR-49's judge: erratum 1, 24 November 2026

This erratum is to the judge of `fr49-compartment-compositions-v1`, `validation/fr49/judge_l.py`,
tagged `fr49-compartment-compositions-v1-judge-2026-11-24`.

**What changed.** `LABELS_ONLY`, the judge's explicit list of the label owner's fields, gains one
name: `label_outside_removed_fmol`.
- FR-44 (D327) added this owner field: the record of what left outside nodes at liquid exchanges,
  by label.
- It is zero-size in a world without a wash, as World L is.
- Without the name, L2's check that the labelled run's extra fields are the label owner's alone
  failed at FR-44's head, although the physics comparison found no difference.

**What did not change:**
- **L2's intent:** every field, observation and diagnostic of the unlabelled twin is bit for bit
  in the labelled run, which adds the label owner's fields alone.
- **Everything else in the judge:** no criterion, bound or plant is changed. The list stays
  explicit and independent of the engine's declarations.
- **World L's registered verdict (D331),** judged before this change, stands.

FR-49's later judged runs (World B, C1 and C2) use the judge with this list.
