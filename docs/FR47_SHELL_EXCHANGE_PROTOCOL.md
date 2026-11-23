# FR-47's qualification: shell exchange, washes and switching gates in the deterministic representation (registration)

**Status: drafted for the lead's tag, 23 November 2026,** before FR-47's build and before any engine
run (D323). Docs and validation only, with no src change. Branch `fr47-protocol` from main ea7ab9a1.
The proposed tag, once at the final head, after the references agent's work, is
`fr47-protocol-registered-2026-11-2x`.

**What it registers:**
- this document;
- the reference spec, `validation/assembly_lineages_v2/fr47_spec/SPEC.md`;
- the criteria, bands and plants, `validation/assembly_lineages_v2/fr47_spec/CRITERIA.md`;
- the pair rule, `validation/assembly_lineages_v2/agreement.py`, shared with Protocol D's
  re-registration;
- at the tag, the code-blind references' code and files.

## 1. The claim

- **The representation.** FR-47 extends `cells.rate_equations@1`, (d), with:
  - the prescribed shell's limits;
  - full and fractional washes (`cells.pool_replacement@1`, `cells.pool_withdrawal@1`), with
    their means and bookings;
  - E2, true zeros for first-order tracer places through the difference form;
  - autonomous switching gates: forms interconverting by a wall step.
- **The qualification shows,** against a code-blind reference and an exact-event ensemble:
  - **in the linear worlds (W1, W1Δ):** (d)'s means equal the reference within its integrator's
    bound. The exact process's law matches the reference in mean and spread. Each stop's removed
    amounts and mixing heat match, and both representations' books close;
  - **in the gated world (W2):**
    - the exact ensemble matches the gate-conditioned reference;
    - (d) matches the mean-field reference;
    - the representation gap is the reference's own prediction. It is measured only where 128
      replicas resolve it, and reported elsewhere.
- **Version 1 refuses by name, in (d):**
  - site binding in shell worlds;
  - gates driven by bound states;
  - FR-46's inner face.
- **min_count 10** is the run setting only, not a qualified n_min (D318, D323).

## 2. Why the reference is exact (S)

- **Every tracer molecule moves independently** (SPEC.md §1, from the registered formulas).
  - The shell's per-molecule rates are constants. A withdrawal at a dyadic f removes each pool
    molecule with probability exactly f, and a replacement removes every pool molecule.
  - So every count is a sum of independent indicators. Its mean, variance and fourth moment follow
    from one molecule's law, since cumulants of independent terms add.
  - The first moments obey the rate equations exactly, with each stop's mean map. So in W1, (d)'s
    error is its integrator's alone, at any count.
- **In W2,** the tracer's rates are linear given the open count K, and K's switching ignores the
  tracer. So the moments E[n^j·1{K = k}], j ≤ 4, obey a closed linear system: an exact mean,
  variance and fourth moment.
  - The mean field differs from the exact mean by O(1/N_g).
- **Probed before writing this spec** (host rates on made-up worlds of W1's and W2's shape, no run):
  - the engine's own κ_in = P_s·A_sh/V_out and κ_out = P_s·A_sh·e^Δ/V_in, to 10⁻¹⁵;
  - the gate's per-copy switching rates, as SPEC.md states them;
  - the gated crossings, carrying exactly g(K).

## 3. The rule at zero uncertainty (D323)

- **Each pair is classified from the reference before the run,** as `constant`, `derived` or
  `spread` (CRITERIA.md; `agreement.py`).
  - Where the reference predicts a constant, every replica must match it, and one wrong replica
    fails.
  - Where it predicts spread, identical replicas still face the spread test.
  - A tolerance exists only where it is derived: here, the tracer moiety's sum in (d).
- **No pair is excluded after a run.**
- **The same module serves Protocol D's re-registration,** whose excluded pairs must be justified
  from the model, not from the replicas.

## 4. Seeds

The seeds are fresh and disjoint from every probe and smoke seed used so far. The probes and smokes
used 1, 3, 5, 7, 23 and 20261123; Protocol D used 1–256 and 100001–100256. Each exact replica runs
at its seed, with environment 0, lineage 0 and branch 0.

| Worlds | First seeds | Retry seeds |
| --- | --- | --- |
| W1 | 470001–470128 | 970001–970128 |
| W1Δ | 470201–470328 | 970201–970328 |
| W2, at N_g = 64, 256, 1,024 and 4,096 | 470401–470528, 470601–470728, 470801–470928 and 471001–471128 | the same plus 500,000 |
| The exact-side plants: P7 on W1Δ, P8 on W1 | 471201–471328 and 471401–471528 | — |

The tag's message names these ranges.

## 5. The run

**The checker** is an independent agent the lead assigns: not FR-47's builder, not this protocol's
author, and not the references agent.

**The checker's order, fixed now:**
1. **The judge's first read.** The checker's judge reads the file the references' own writer wrote
   on invented inputs (SPEC.md §5), and must reproduce every pair, stop and interval it holds,
   before any engine run (D323; FR-30's lesson).
2. **The regeneration check.** The references' files regenerate bitwise under two other hash seeds.
   The references agent shows this before its head, and the checker repeats it.
3. **The runs:**
   - W1, W1Δ and W2's four rungs, in exact events: 128 replicas each, on §4's seeds;
   - (d) once per world, deterministic;
   - the plants, each in its own process.

   All runs are cold, with no JAX compilation cache, and on the light CPUs. They run after
   Protocol D's re-registration, or on other CPUs.
4. **The judgement:** CRITERIA.md's criteria, with `agreement.py` for the statistical ones.
5. **The retry:** once, for inconclusive worlds only, on the retry seeds. Its bands then fail.

**Verdicts:**
- **A world** passes when every criterion that applies passes. It fails when one fails, and is
  inconclusive otherwise.
- **A plant** is caught or not caught.
- **The protocol** passes when every world passes and every plant is caught, and fails when a world
  fails or a plant is not caught.

**The cost** (the design note's §9.5, from a measured W1-sized replica of 14,399 events in 7.4 s
plus 6 s of compile): about 3 CPU-hours, and up to about 6 with the retry.

## 6. FR-43 part 2's lessons, carried

- **Units.** SPEC.md §0 states the unit of every declared count: molecules in one place.
- **Regeneration.** The references show bitwise regeneration under other hash seeds before their
  head.
- **One tag,** at the final head.

## 7. What it does not claim

- **Not claimed:**
  - the relaxation time's dependence on Δ beyond the law's convention;
  - (d) away from the envelope's run setting, except at E2's first-order places;
  - bimolecular site binding, inner-face binding, or gates driven by bound states in (d).
- **Disclosed: what had been seen.**
  - The design note (`/mnt/workspaces/Cells/fr46-48-design-20261123/DESIGN.md`) holds the author's
    own numpy sketch of a W1-shaped reference, with made-up numbers and no engine import, used to
    size the plants' teeth.
  - It also holds made-up-world probes of the engine:
    - the factored flux at zero;
    - the derivative of exp(safe_log) at zero, which is 0;
    - a one-slot shell with washes, which ran and closed its books.
  - None of these is a protocol world, and the references agent does not read the note.
