# Next feature: conservative electroneutral cotransport

Start after handing off the finite-energy tissue implementation and its initial
checks. The coordinator owns that qualification and the subsequent water/energy
composition; this assignment gives the worker an independent new capability.

## Scope and ownership

Own these new files, plus the existing worker log and workfiles:

- `src/cells/processes/cotransport.py`
- `tests/unit/test_cotransport.py`
- `validation/transport/cotransport_reference.py`
- `validation/transport/cotransport_protocol.json`, if useful for the component
- `docs/COTRANSPORT.md`

Do not edit existing models, shared schema/registry/schedule files, PROGRESS.md,
finite-energy or water files, or frozen evidence. Report a concrete bug before
changing a delivered file. All generated captures, logs, references and check
outputs belong under `/mnt/workspaces/Cells`.

## Establish the physical and source contract first

Review electroneutral K/Cl and Na/K/2Cl cotransport as the first named routes.
Inspect pinned BETSE v1.5.0, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, including generic transporter/network
configuration. A readable installed source is available at
`/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/betse`.
Bind any executable source comparison to captured version and file hashes.
Use primary literature or authoritative source documentation when researching
the transport laws. Do not assume BETSE has a runnable named KCC/NKCC law.
Do not copy upstream implementation into the repository.

Send the coordinator a short contract identifying stoichiometry, positive-cycle
direction, units, thermodynamic affinity, kinetic choice, parameters and source
correspondence before implementing it. A manufactured reversible law may be
appropriate for a first physical component; name and label it explicitly rather
than claiming a fitted transporter or native BETSE equivalence. Preserve a
source-specific law separately if its semantics differ.

## Implement the component through initial verification

Use explicit species/route ownership and pure NumPy/JAX-compatible calculations.
Retain signed forward/reverse cycles and matched material transfer on both sides
of every route. Account for free-energy changes and nonnegative dissipation.
Electroneutral stoichiometry must cancel direct transported charge; voltage can
still change later through altered shared ionic concentrations. Do not invent
ATP consumption for these secondary transporters.

Define strict positive-concentration and parameter domains, availability,
inactive padding and leading independent-world axes. Reject invalid active
substrates even when a route is blocked; do not use concentration floors or
silently reset ionic stores. Keep geometry and integration outside this process
kernel. Document how an eventual tissue model should accumulate signed cycles,
per-species transport and dissipation exactly once.

Include an independently implemented scalar/Decimal reference and meaningful
contracts: equilibrium/stall, forward and reversed gradients, stoichiometry,
charge cancellation, chemical-energy/heat balance, independent route controls,
padding/owner identity and actual leading-world broadcasting. A small CPU JAX
eager/JIT check is useful after the host contracts pass. Native source cases and
manufactured numerical cases must remain separately labelled.

Use the established bounded check runner, CPU7, single-thread BLAS, <=1 GiB
charged memory and >=8 GiB host reserve. Begin with host/reference checks; ask the
coordinator for the resource handoff before compiled checks. No GPU, large sweep,
long qualification or polling of another job. Preserve all failures and exact
inputs. The handoff should provide code, equations/source distinctions, API,
test outcomes and delivered source hashes; the coordinator owns later tissue
composition and full CPU/L4 qualification.
