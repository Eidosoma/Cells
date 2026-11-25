# FR-43 part 3, the co-writers: the code-blind references

Written from `../spec/` (the criteria tag `fr43-part3-cowriters-criteria-2026-11-25`) and, of
`docs/TEMPLATED_POLYMERISATION_LAWS.md`, §§0, 1.1, 1.2, 2, 3.1, 3.4 (its lines on `tx` and `deg_R`), 4.1 to 4.4, 4.7
and 4.8 alone. No engine code, output, test or record was read, and nothing here imports or runs the engine.

## Files

| File | What it is |
| --- | --- |
| `write_references.py` | The writer: the invented set first, then one file per registered world |
| `cowriter_refs/` | `declared` (the inputs as exact numbers, the planted changes), `draws` (Threefry-2x32), `taylor` (method A), `extrapolation` (method B), `split` (the sizing model), `pooled` (CRITERIA 3.3), `build` (tasks, scales, sizing, margins), `checks` (SPEC 9), `layout` (SPEC 7), `invented` (SPEC 8) |
| `self_check.py` | Reads the written files as C0 does and tests them with code of its own (it imports nothing above) |
| `out/` | `inputs_invented.json`, `draws_invented.json`, `reference_invented.json`, `reference_W5.json`, `reference_W5-exact.json`, `reference_W6.json`, and the sidecar `run_times.json` |

To regenerate and to check (Python 3 with NumPy and SciPy; `-I` works, the writer adds its own folder to the path):

```
python -I write_references.py --out DIR --workers 4
python -I self_check.py --out DIR
```

The number of workers changes nothing in the files. `--revision` gives the code's commit where the folder is not a
Git checkout. `run_times.json` alone holds times and the machine.

## Method

Everything that enters a file is computed in Python's `decimal`, whose operations are exactly rounded, so the bytes
depend on no mathematical library. A declared real is the exact value of its nearest double. A time of the grid is
the declared decimal, so that a horizon is a whole number of steps.

- **Draws.** Threefry-2x32 (20 rounds) in integers, from LAWS §6. Random123's published answers and every entry of
  `draws.json` are met. E_k = −ln u1_k to 60 digits.
- **Method A** (`taylor.py`), the published values. Taylor series of order 40 at 50 digits, from recurrences on the
  coefficients of the rows, the books and the hazard (the quotients and the power n_R^(1 − 1/L) by their own
  recurrences). The step is where the last two coefficients fall to 10⁻⁴⁰ of each component's weight. A sample is read
  from the expansion. An event is the root of the hazard's polynomial (safeguarded Newton, to 10⁻⁴⁴ of the step). The
  books are integrated from their own rates, never formed from rows.
- **Method B** (`extrapolation.py`), the check. Gragg-Bulirsch-Stoer extrapolation (twelve columns, 34 digits, 10⁻²³ of
  each component's weight per step) of rates evaluated directly from the laws, in steps that land on every sample. An
  event's time comes from the hazard as the independent variable (dt/dH = 1/a_0), and from the closed form where a_0
  is constant.
- **Closed forms.** W5-exact's published times are the decimal sums of LAWS §4, and method A's own hazard meets them.
  The transfer alone meets its exponential.
- **The sizing model** (`split.py`), LAWS §5 at 28 digits. A is exact: the free site conducts nothing, so the row it
  reads is fixed and the hazard is linear in time, and the active site's propensity is constant while the pools relax
  as an exponential. B is, for the reactions, a Taylor series whose remainder is below 10⁻²⁰ per half-step, and for
  the gene unit one step of SSPRK(3,3) of h/2. Tightened to 40 digits and 10⁻²⁸ it changes by less than 10⁻¹² of the
  split's own error (an invented world of each kind).
- **The statistics** are CRITERIA 3.3's, from the model's and method A's decimals.

## Accuracy

A published `accuracy` is u times the largest value of the readout over the copy's samples (u T for the events), which
holds the rounding to the nearest double, plus ten times the largest difference of the two methods. It is one number per
readout and copy, repeated along its list. The two methods differ by less than 10⁻²⁰ of T or of the scale in every
world, honest and planted, so the double's rounding is what the accuracy says. SPEC §4's limits are met by four
decades (W5-exact's events: by a factor of nine). The weights and the tolerances of both methods are far more than ten
times tighter than the published accuracy.

## Readings

The text governs. Where it left a choice, this is what was read. The first eight were put to the lead and accepted as
defaults on 25 November 2026. The two added keys (`change`, `reason`) can be ignored by a reader that does not know them
(SPEC §7).

1. **`q` where no order is formed.** CRITERIA 3.3: "With at least three used, q is the least-squares slope". It leaves
   open what stands in `q` with fewer. JSON `null` (in `retry` as well).
2. **P8 and P8-W6.** CRITERIA 6.2: "E: the number of entries that differ", and "or the reason for a plant with none (P8,
   `no_margin`)". It leaves open the other two numbers of the entry and where the reason stands. `distance` is the number
   of judged events (k < K_c of copy 0) whose channel or counts differ from the reference's after the edit,
   `expected_tolerance` is 0.0, `margin` is null, and the added key `reason` holds the reason.
3. **The record plants' margins.** CRITERIA 6.2: "its distance from the honest reference (or the honest record), at its
   best entry of the named check, over the expected honest tolerance there", "R: the formula of §3.2"; 6.3: "the honest
   run of copy 0 of the family named, at the world's coarsest rung". It leaves open what the honest record is before any
   run exists. They are formed on the references' own rows and books of copy 0, with S = t/h_1 and s_id of the honest
   terms, at the sample with the largest ratio, one entry per named check, family null. P5's tolerance is e_round with
   S = T/h_1 (LAWS §7: "every registered S is at least 1,000") plus the accuracy, at the judged event the farthest away.
4. **P3's margin.** CRITERIA 6.2: "P3: the pooled RMS between the honest reference and the Lie emulation at its rungs",
   and "at its best entry of the named check"; "S: the sizing model's τ of the family". Its three rungs give three
   distances. The best entry is the largest, the coarsest rung's, over the family's expected τ of `t_events`. All three
   stand under `mutant`.
5. **The invented worlds' names** are the registered ones. SPEC §8: "`reference_invented.json` is one object, world name
   to §7's layout, for the three worlds".
6. **The invented refused and stopped runs.** SPEC §8 asks for "a full set of runs (judged, restart, Lie plant, refused,
   stopped, retry)"; SPEC §2 knows the roles `judged`, `support` and `plant`, "There is no other role". It leaves open
   their role and how their change is written. They are `support` runs of variant `refused` and `stopped`, each with the
   added key `change` in the plants' style. The refused run is W5-exact at a step whose product with the largest
   propensity is above 1 (SPEC §2's placement); it alone does not keep the placement. The stopped run is W6 with another
   start amount of Pi: x of LAWS §3 starts below −1 and crosses it inside the run (the message to the lead said M and y;
   Pi and x cross by more).
7. **The invented retry runs** are listed under `retry.runs`, not in `runs`. SPEC §8: "`inputs_invented.json` lists the
   retry runs of one family"; it leaves open where.
8. **`reported` and `provenance`.** "The number of draws used per copy" is K_all + 1 (the pending event's threshold is
   read too). `provenance.revision` is the commit that last changed the references' code, `out/` left out.

Others:

9. The published accuracy is one number per readout and copy, and e_ref is the largest over the copies (t > 0).
10. A pooled statistic's e_round uses S = T/h_j (CRITERIA §1), the events' and the rows' alike.
11. The planted copies' `K` counts their own events to T − g h_1. The common entries of a margin are k < K_c of the
    honest copy that the planted one also has. An exact process does not depend on the declared order, so both families
    hold the same list.
12. The identities of SPEC §9.4 are summed over the published doubles, and their bound is 10⁻¹¹ times the least
    |coefficient| × scale of their terms.
13. A check passes where its residual is at most its bound; what must exceed something is written as a ratio or
    negated, and its name says so. Copy 0 carries the world's checks beside its own (`world: ...`).
14. W5-exact's families have an empty object under `sizing`, and a world without a Lie plant or a two-rung check has an
    empty `mutant` or `rungs`.

## Checks

`checks` of each copy holds SPEC §9's, and copy 0 holds the world's (the relaxation, the totals, the sizing, the pairs, the
margins). `self_check.py` then reads the files alone and, with code of its own, (1) forms every number C0 reads again from
the published ones, (2) solves the exact process a third time with SciPy's DOP853 in doubles, the affinities from the
laws' logarithms, (3) computes the split's first differences and the pairs again in plain doubles, and (4) checks the
invented set's rules, the shared numbers among them.
