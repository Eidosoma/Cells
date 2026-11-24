# FR-50: the references' spec (absolute one-way fluxes and records)

This is the spec for an independent, code-blind reference of FR-50's registered protocol,
`fr50-one-way-records-v1` (`validation/fr50/REGISTRATION.md`).

**What is being modelled.** Every transfer route has a net record, the cumulative amount it moved,
which can stay at zero while equal amounts cross both ways. FR-50 adds opt-in one-way records,
the cumulative amount each way.

**What the reference gives.** For each declared case, the absolute one-way fluxes and their records
at declared times, from LAWS.md's laws alone. Each of the engine's two directions is then checked
against these absolute values, not only against their difference.

**This folder holds declared values and protocol only**, so no engine value is in it.
- Do not read engine code (`src/cells/`), the engine's tests, or any engine output or record.
- The pass criteria are in `validation/fr50/REGISTRATION.md`, fixed before any reference exists.
  You need not read them.

## The files

- `LAWS.md`: the equations, complete.
- `cases.json`: the cases' declared values, their units and the requested quantities.

## What to compute

For each case in `cases.json`, its `requested` quantities, from LAWS.md:
- **Steady cases** (K1, K4, E1–E4): the constant one-way fluxes, and the records at the record
  times (flux × t).
  - For K4, also report ΔG_cyc/(R T) at the declared state. It should be 0, so report its value as
    computed.
  - For E1 and E4, V is E_K, formed to 50 digits from the declared concentrations.
  - For E4, u at V = E_K.
- **K2:** the closed-form trajectory and records of LAWS.md §5.
- **Host evaluations** (K3, K4h, E6): the fluxes or rates at the declared voltages or state, and the
  ratio between directions.

**Accuracy:** at least 30 significant digits, for example Python's `decimal` with a 50-digit
context.
- **Cross-check:**
  - for the steady cases, recompute each flux from Ussing's ratio and the net, and report the
    difference;
  - for K2, integrate its ODE (for example Radau at rtol 1e-12) and compare the records.
- **The declared accuracy** is 1e-20 relative for the closed forms, and 1e-10 relative for the
  integration.

## What to produce

- **One JSON file per case,** `validation/fr50/references/results/<case id>.json`, holding:
  - every requested quantity, at the case's times or voltages, as decimal strings;
  - `method`: the precision, the second route and the largest difference;
  - `provenance`: the git revision, any dirty paths, and the Python version.
- **The code** under `validation/fr50/references/`, with its own README and a self-check test that
  compiles no world.
- **A short `NOTES.md`**: every reading you had to make, and any declared value you found
  inconsistent.

The spec gives no time step. The engine's step and its rule for each step's one-way amounts are
the engine's own, and its step-halving study measures them.

## Amendment 1 (24 November 2026): the cross-check where a case sits exactly at zero net

**The point.** The references agent asked about the cross-check under "Accuracy": recompute each
flux from Ussing's ratio and the net. In a steady case exactly at zero net, that route is 0/0. The
cases are K1 (a neutral route at equal concentrations), E2 (a neutral junction at equal
concentrations and potentials), E3 (an uncharged face at equal concentrations) and K4 (the
transporter at ΔG_cyc = 0, by Hill's ratio).

**The agent's reading is confirmed.** In those four cases the reference:
1. reports the ratio-and-net route as degenerate;
2. checks independently that the ratio is exactly 1 and the net exactly 0;
3. recomputes each one-way flux by an independent route, in exact rationals with its own exp and ln.

**E1 and E4 are not degenerate.** Their V is E_K formed to 50 digits, so the ratio differs from 1 at
that precision. Their cross-check through Ussing's ratio and the net runs at high precision, as
written.

**Nothing else changes:** no declared value, no criterion of REGISTRATION.md, no requested output
and no declared accuracy.

