# FR-51: the references' spec (closed forms of permeation and block)

This is the spec for an independent, code-blind reference of FR-51's registered protocol,
`fr51-channel-block-v1` (`validation/fr51/REGISTRATION.md`).

**What is being modelled.** A population of ion channels on a membrane patch conducts one ion by
constant-field (GHK) permeation. A blocker binds in its open pore, reversibly and instantaneously,
in weighted modes. Each mode has its own dissociation constant at zero voltage and its own
steepness against the membrane voltage, or against the voltage relative to the ion's reversal
potential. The block multiplies the flux by one unblocked fraction u.

**What the reference gives.** For each declared case, the closed-form permeation, the unblocked
fraction and its parts, the blocked current, and the slopes the stability criteria read, all at
declared voltages. Cells' engine results are compared with them afterwards.

**This folder holds declared values and protocol only**, so no engine value is in it.
- Do not read engine code (`src/cells/`), the engine's tests, or any engine output or record.
- The pass criteria are in `validation/fr51/REGISTRATION.md`, fixed before any reference exists.
  You need not read them: they compare the engine with your values and never change those.

## The files

- `LAWS.md`: the equations, complete. No other document is needed.
- `cases.json`: the constants, the voltage grid, the populations, the blocks, the cases and the
  requested outputs, with their units.

## What to compute

For each case in `cases.json`:
1. **The voltages.** Form the grid from its rule in decimal arithmetic (361 voltages from −0.120 V
   in steps of 0.0005 V). Add E_ion, E_ion − 0.0005 V and E_ion + 0.0005 V, with E_ion the case's
   Nernst potential of its population's ion.
2. **The free quantities** at every voltage (LAWS.md §2): J_free, I_free and dI_free/dV.
3. **For a case with a block** (LAWS.md §3–§5), at every voltage:
   - V_ref;
   - each mode's θ_k and 1 − θ_k;
   - u;
   - J_blocked and I_blocked;
   - dI_blocked/dV;
   - ∂J_blocked/∂c_o and ∂J_blocked/∂c_i.

   Also u at V = E_ion (`u_at_reversal`).
4. **For the count cases** (C1, C2; LAWS.md §6), the same quantities, with:
   - C1's abundance 2;
   - C2's abundance N/(A ρ_ref), from its declared units and reference density.

**Accuracy.** Work to at least 30 significant digits (LAWS.md §7), and report decimal strings of at
least 20.
- **A cross-check.** Recompute every u, every I and every slope by a second, independent route.
  Report the largest relative difference between the two. Examples of a second route:
  - for u, the literal 1 − Σ_k w_k θ_k at 50 digits, against the form of LAWS.md §3;
  - for the slopes, central differences at 50 digits (step 1e-12 V or 1e-12 relative), against the
    analytic forms of LAWS.md §2, §4 and §5.
- **The declared accuracy** is 1e-20 relative for u and I, and 1e-15 relative for the slopes,
  where the second route is a difference quotient.

## What to produce

- **One JSON file per case,** `validation/fr51/references/results/<case id>.json`, holding:
  - the voltages used (decimal strings);
  - every requested quantity, as arrays over the voltages under the names in
    `cases.json`'s `requested_outputs`, in the stated units;
  - `u_at_reversal` and `E_ion_V`;
  - `method`: the precision, the second route and the largest difference;
  - `provenance`: the git revision, any dirty paths, and the Python version.
- **The code** under `validation/fr51/references/`, with its own README and a self-check test that
  compiles no world.
- **A short `NOTES.md`**: every reading you had to make of an ambiguous statement, and any declared
  value you found inconsistent.

The lead may name another place.
