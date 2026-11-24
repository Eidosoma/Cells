# FR-38's second registered comparison: gross and net read apart (registration)

**Status: registered by the user's decision of 24 November 2026 (D334).** This document was written
by the protocol's author for the lead's tags, and that author does not judge, check or write the
references. Docs and validation only, with no `src/` change. Branch `fr38-registration`, from main
3ec603f0.

**What it registers.**
- This document.
- **The sheet's erratum I** (`docs/TEMPLATED_POLYMERISATION_LAWS.md` §9.22), committed first and
  tagged before the rule (proposed tag `gr1-sheet-fr38-erratum-i-2026-11-24`).
- **The references' spec folder,** `validation/gene_regulation/fr38_v2/spec/`: README.md, SPEC.md,
  LAWS.md, READOUTS.md and CRITERIA.md. With this document it fixes the criteria, bands and plants
  before any reference exists (proposed tag `fr38-v2-criteria-2026-11-24`).
- **At the final tag** (`fr38-v2-registered-2026-11-2x`), before any engine run:
  - the references, written afresh by a new code-blind agent;
  - the engine-side worlds and readout extensions;
  - the plants' world data and patches;
  - the judge's reader, with its first read of the references' invented file.

## 1. Why a second comparison

**The first comparison failed as registered (D313).** Its verdict stands, and this comparison is
recorded beside it, never in its place.

**R1 failed on three clauses, all definitional (D316):**
- **Route 1.** The engine's cohort leaves at the degradation's gross one-way rate k, which is
  erratum F's definition. The references' blank-subtracted class row fell at the net rate
  k(1 − e^y). Their difference, about k·e^y·(mean age), sat just above a declared floor of 10⁻⁹ of
  scale.
- **The zero-rate survivors.** At an idle fate, "the released molecules still present", a
  membership count, is exactly zero. "Row minus blank", a pool difference, is not, because the
  other fate's returned monomers change the idle row's loss. A ruling equated the two.
- **The blank's G.** A floor declared as a fraction of a tiny scale sat below the rounding of G's
  large terms.

**R2 was inconclusive on C_tx_3's observed order.** C_tx_3 is an A1 transcription stage; its order
was 3.94, then 3.69 and 3.67 after the retry, against the cap of 3.5. Gross against net did not
cause it: it explains R1's failure (D334's correction of D316's reading). In R2 the mismatch sat
in route 2, hidden below route 2's grid-error tolerance.

**What this registration changes:**
1. **One name per quantity,** defined by its law, with gross or net in the name (erratum I). The
   five membership classes of a fate row are read in one run, by FR-42's share labels.
2. **A world where gross and net differ grossly.** This is AN, a declared numerical-discrimination
   world. There the confusion of the first comparison falls many orders above every band.
3. **Tolerances built from stated terms:** the engine's step estimate, the reference's stated
   accuracy and the arithmetic's rounding. Never a floor declared as a fraction of a scale.
4. **Every entry classed before the run** by the reference's own structure, with FR-47's
   `agreement.py`. No ruling assigns a class.
5. **The step estimate takes the larger of the two step-halving pairs,** inside D271's window. In
   arm A, transcription's stage complexes are reported, not judged.

## 2. The claim

**What it shows.** `templated_polymerisation@1` with §9's release, labelled by
`neutral_arrival_labels@1`, gives:
- the physical state and books;
- every membership class of erratum I, and so FR-38's window cohort and its survival readout;
- the excess over the matched blank.

Each agrees with code-blind references within CRITERIA.md's tolerances. It holds:
- with chains completing into the hold throughout;
- under a scheduled p;
- with each machine option;
- at the sheet's own potentials (AF);
- in AN, where gross and net differ by percent to order one;
- in A1 with the release (arm B).

**Beside it, with their own verdicts,** families C and D show the same with:
- the monomer pool co-written by a D152 network (FR-43 part 2A);
- a swelling cell (FR-43 part 2B).

**What it does not claim:**
- any biology: τ, p, the fates' rates and AN's potentials are declared (§9.11);
- export, producer identity across replacement, a routed p, or the observation layer;
- the request's first-order limit, which stays release_check's acceptance;
- arm A's stage complexes and arm B's own A1 readouts, which are reported.

The machine options remain declared choices. The one wet-lab figure on record (polymerase retained
after release in 87 of 100 selected traces, Harden et al. 2020) is one study's indication, not a
validation.

**Its standing.** It is a second registration after a definitional failure. Its author had read the
diagnosis (§9). So it is weaker evidence than a first-time pass would have been (D316).

## 3. The engine models it runs

| Model | Where |
| --- | --- |
| `resolved_pump_composite@1` over `resolved_pump_tissue@3`, which moves no ion here | Every world |
| `templated_polymerisation@1`, §9's release (amendment R, errata A–I) | Every world |
| `neutral_arrival_labels@1` (FR-42) | Every labelled run |
| `scheduled_species_turnover@1`, `species_regulated_availability@2` | Arm B (A1's regulator and its factor) |
| `local_species_reactions@1` with `ideal_detailed_balance_mass_action@1` | Family C |
| `ideal_osmosis_linear_compliance_water@1` | Family D |

## 4. The worlds

**All inputs are in `validation/gene_regulation/fr38_v2/spec/SPEC.md`.** Every value that defines a
release, a fate, a window or a pool is new. What is reused:
- A1's chain constants, A1's N and Pi, and in AF A1's M;
- the numeric test instance;
- Mx's start, from FR-43's fixtures.

**Arm A, which decides.** A hold with chains completing into it, two regimes:
- **AF:** the sheet's numeric test instance, where e^(y_f) is about 10⁻⁸.
- **AN:** a declared synthetic residue potential (μ°_res/RT = −10.368889, outside §3.3's range) and
  M at 4 µM. Its initial e^(y_f) is about 0.13.
  - An analytic worst case bounds it: even if every molecule of RNA ever present degraded,
    e^(y_f) ≤ 0.190, inside §9.6's domain.
  - **What a miss in AN means is stated in CRITERIA.md §5,** before any run: a miss in AN fails the
    comparison as registered.
- **The runs.**
  - AF runs p = 0, p = 1 and a scheduled p, each with both machine options.
  - AN runs p = 0 and p = 1 with `returned`, and the scheduled p with both.
  - Each family has a matched blank (H(0) = 0 and k_I = 0, erratum I, item 5) and an unlabelled
    twin. AN also has a restart.

**Arm B, which decides.** A1 with the release, labelled; both machine options with their twins.
- It judges FR-38's quantities and reports A1's own (READOUTS.md §4).
- A parse probe admitted the labelled world.

**Families C and D, beside.**
- **C** adds a D152 passive store M ⇌ Mx, which draws the monomer pool down during the chase.
- **D** puts the hold world in a swelling cell, which crosses about 2 V₀ inside the window. That
  figure is a hand estimate, which the builder confirms with water's own conversion.
- Parse probes admitted both with labelled fate rows. Both were refused before FR-43.
- **A1 in a swelling cell is refused,** because its turnover and factor read the declared volume.
  That engine gap is logged and not built (D334).

## 5. The roles

**Each role is a different agent.**

| Role | Who | Writes | Reads |
| --- | --- | --- | --- |
| Protocol author | The author of this document | This document, erratum I, the spec folder | – (barred from the roles below) |
| References | A new code-blind agent | `validation/gene_regulation/fr38_v2/references/`, afresh | The spec folder and the sheet sections LAWS.md names; nothing else (spec README) |
| Builder | The gene-regulation lane | The worlds (suggested `validation/gene_regulation/fr38_v2/worlds.py`), from SPEC.md; `engine_run.py`'s exports for families C and D (`n_Mx`, `H_store`, `V`, `H_water`, `W_bath`, and G over their rows); the restart; the plants' world data and host-side patches; release_check's net-agreement sub-check scoped to e^(y_f) ≪ 1, since it fails by design in AN | The spec folder; its own code. It runs no registered world before the tag; parse checks and made-up probes only |
| Judge | A new agent, blind to the first comparison | Its reader and mapping, from SPEC.md §7 and the invented file, using `agreement.py`; a synthetic end-to-end check on invented records | This document, the spec folder, its own code. Not the first comparison's references, rule, erratum, records or diagnosis |
| Checker | An independent agent | Its own recomputation of the verdict | The hashed table, the reference files and the judge's record |

**What the checker does.**
- It repeats C0 and the references' regeneration.
- It recomputes every verdict with its own code.
- It scores every plant.

## 6. The order of work

1. **Erratum I** is committed and tagged (`gr1-sheet-fr38-erratum-i-2026-11-24`).
2. **This document and the spec folder** are committed and tagged before the references agent
   starts (`fr38-v2-criteria-2026-11-24`). The bands are fixed from here.
3. **The references,** with their invented file and the regeneration check under two other hash
   seeds.
   - If their sizing (SPEC.md §6) puts a must-catch plant below its 10× (CRITERIA.md §6), a dated
     amendment enlarges or replaces it now.
4. **The builder's worlds and exports,** checked by parse only.
5. **The judge's reader:**
   - its first read of `reference_invented.json`;
   - C0 on the real files, before any engine run;
   - a synthetic end-to-end check on invented records.
6. **The registration tag** `fr38-v2-registered-2026-11-2x`, at the final head, before any engine
   run.
7. **The fresh runs:**
   - from a clean frozen snapshot (`scripts/gates/freeze_snapshot.py --scope full
     --require-clean`);
   - detached (`scripts/run_detached.sh`), on the light CPUs, one thread each;
   - cold, with no compilation cache;
   - the plants in their own processes.

   They queue behind Protocol D's re-registration and FR-47's ensemble (D334).
8. **The table,** built from the engine runs alone and hashed before any reference value is read.
9. **The judge,** from a clean frozen snapshot of the registration tag. Then the one retry, if any
   run is owed it, with its table hashed the same way.
10. **The checker.** Then the record, and a decision entry beside D313.

## 7. What it costs

| Work | Who | Agent-days |
| --- | --- | --- |
| Erratum I, this document and the spec folder | Protocol author | done |
| The worlds, the exports for C and D, the restart, the plants' data and patches, release_check's scoping | Builder | 1.5–2 |
| The references, afresh: the full ODEs in deviation form with the classes; paired blanks; A1 for arm B; the store; water; second methods; closed-form checks; plant sizing; the invented file; regeneration | References agent | 2.5–3.5 |
| Reader, C0, the synthetic end-to-end check, plant scoring, the verdict | Judge | 1–1.5 |
| The recomputation, regeneration and plants | Checker | 0.5–0.75 |
| **Total** | | **about 5.5–7.75** |

**CPU-hours: about 8 to 12** (one thread per run, light CPUs).
- About 85 engine runs, at about 3 minutes each at h over 14,400 s, after a compile of 30–45 s per
  world family.
- Up to about 2.5 CPU-hours more for the retry, if one is owed.
- 1.5 to 3 CPU-hours for the references with their regenerations.
- About 3 to 4 hours of wall time on two light CPUs.

## 8. Left to later registrations

- Export (amendment T, with erratum H's two-pool route 2).
- Producer identity across replacement (amendment G).
- A routed p (B1′).
- The observation layer.
- No engine counters are added for the degradation's one-way parts (D334).

## 9. Disclosures: what this registration's author has seen

- **The first comparison's figures** in D313, D316, the diagnosis record and the verdict notes.
  These include its gaps, its G figures (0.85 and 1.0 ulp), its zero-rate values, R2's orders
  (3.94, 3.69, 3.67) and FR-25's (3.94, 3.69, 1.49).
- **The first rule and its erratum 1** in full.
- **The tagged first references' README,** its method, regeneration and release-section opening.
  Not their code or interface files.
- **The first comparison's engine records,** only for zero flags and sign bits, and whether its two
  blanks were equal (they were, on all 39 readouts).
- **D306's checker scripts,** for the near-edge precedent.
- **Probes on made-up worlds only,** on light CPUs (6, 7 and 22; a few seconds-long arithmetic
  scripts ran unpinned). Their files are in `/mnt/workspaces/Cells/fr38-next-20261124/probe/`:
  - parse checks;
  - three 600 s runs of the five labels;
  - a probe of arm A's shape at 2, 1 and 0.5 s, with k_I 2.0 × 10³, H(0) 140, pools 18 and 9,
    τ 2000 s, p 0.6 then 0.3, k = 1/7000 and 1/1000, W = [300, 600), E_pd 9.5 RT and M 3 µM;
  - a desk sizing from the laws alone, on neighbouring values, with its small-pool rerun;
  - an order-rule scan.
- **What the arm-A probe showed.** Every resolved order inside its window:
  - the stage complexes 2.70 to 3.36;
  - the amounts 3.00;
  - the labels 2.00 to 2.74.

  It also gave the engine-only tolerances that CRITERIA.md §6 uses to size the plants.
- **Two desk calculations used registered inputs:** AN's analytic domain bound, and family D's hand
  estimate of the swelling time scale. No trajectory of a registered quantity was sketched, and no
  engine has run a registered world.
- **The design record** is `/mnt/workspaces/Cells/fr38-next-20261124/REGISTRATION_DRAFT.md`
  (sha256 4b7a361dfa06d34f7bea4aec2b55810caff89eb60edde53a2b480557f5989c9a), as the user approved it
  with the advisor's changes (D334). Where this registration differs from it, D334 governs:
  - the stage complexes are reported in arm A;
  - the references are written afresh;
  - the AN miss rule is stated.

## 10. Decisions

D313, D316, D317, D328 and D334. The judge's pair rule is FR-47's (D323).
