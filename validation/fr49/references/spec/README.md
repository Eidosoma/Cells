# FR-49: the references' spec (compartment compositions)

This is the spec for an independent, code-blind reference of FR-49's registered protocol,
`fr49-compartment-compositions-v1` (`validation/fr49/REGISTRATION.md`).

**What is being modelled.** A cell owns a closed compartment, a well-mixed node of fixed volume
behind the cell's own membrane.
- **World L:** a neutral species is produced in the cell, carried into the compartment by a passive
  route, and cleared there. Production during a pulse carries a label, which follows the material
  and never changes it.
- **World B:** a ligand in the compartment binds finite sites that face it, with depletion. A well
  elsewhere in the world is washed while this happens.
- **C1:** a washed well's labels, beside World L.
- **C2:** two ligands competing for one site pool in a compartment.

**This folder holds declared values and protocol only**, so no engine value is in it.
- Do not read engine code (`src/cells/`), the engine's tests, or any engine output or record.
- The pass criteria are in `validation/fr49/REGISTRATION.md`, fixed before any reference exists.
  You need not read them.

## The files

- `LAWS.md`: the equations, complete.
- `cases.json`: the worlds' declared values, their units and the requested outputs.

## What to compute

1. **World L** (LAWS.md §2): the exact solution at every sample time, by matrix exponentials of the
   augmented linear system on each interval between t = 0, t₁, t₂ and the sample times.
   - Cross-check it by an ODE integration at tight tolerance, for example Radau at rtol 1e-12 with
     its steps stopped at t₁ and t₂.
   - Report the largest relative difference.
2. **World B** (LAWS.md §3): the equilibrium root and the exact transient at every sample time, at
   30 significant digits (Python's `decimal` with a 50-digit context has `exp`, `ln` and `sqrt`).
   - Cross-check both by an ODE integration.
3. **C1** (LAWS.md §4): the wash's arithmetic, at 30 digits.
4. **C2** (LAWS.md §5): the transient by ODE integration (Radau at rtol 1e-12, checked by DOP853 or
   a second tolerance), and the equilibrium root at 30 digits.
   - Check that the transient's end approaches the root.

**The declared accuracy:**
- 1e-20 relative for the 30-digit quantities (World B, C1, C2's root);
- 1e-10 relative for the ODE integrations;
- 1e-13 relative for World L's matrix exponentials.

## What to produce

- **One JSON file per world,** `validation/fr49/references/results/<world>.json`, holding:
  - the sample times;
  - every requested quantity under its name in `cases.json`, in the stated units;
  - `method`: the precision, the second method and the largest difference;
  - `provenance`: the git revision, any dirty paths, and the Python, NumPy and SciPy versions.
- **The code** under `validation/fr49/references/`, with its own README and a self-check test that
  compiles no world.
- **A short `NOTES.md`**: every reading you had to make, and any declared value you found
  inconsistent.

The spec gives no time step and no splitting. Both belong to the engine, and its step-halving
studies measure them.
