# Boundary-voltage adapter

Chief assigned this workstream through thread communications on 30 October 2026.
Owned changes are new `physiology_boundary_voltage*` core, model, independent
reference and test files, plus this directory. Shared CLI, docs and `PROGRESS.md`
remain Chief's responsibility. Key owns the protein-packet provider.

The concrete scientific risk is treating four native side setters as physical
electrodes, or changing clamps while retaining fixed-voltage history identities.
The first interface therefore binds explicit side IDs to actual reservoir IDs,
refuses finite owners/gauges and conflicting corner prescriptions, and evaluates
complete ordinary passive, ionic, calcium and fuel rates with held voltages.
For calcium/fuel the actual reservoir-capable identities are
`resolved_open_calcium@1` and `resolved_open_calcium_energy@1`; the finite-only
`resolved_calcium@11` and `resolved_calcium_energy@5` reject reservoir declarations
and retain their closed-system gauge semantics. Open families retain their
explicit hard ionic-moiety ceilings and complete external closure. The first
frozen attempt preserved this fixture-preflight failure; the scientific domain
is not relaxed to accommodate clamps.
Only temporary `boundary_V` changes. Accepted state, original charge/capacitance
anchors, controls and material/energy ledgers are checked and preserved.

Changing clamp potentials at fixed ion inventories can redistribute capacitor
charge and change stored electrical energy. The endpoint adapter reports these
changes and the conditional work of an ideal linear capacitive ramp at fixed
free charges. This is endpoint algebra, not a transition adopted from BETSE.
The source setter does not specify electrode dynamics or an accepted jump;
ordinary history identities assume fixed clamps. No heat term, accepted stepping,
trajectory, checkpoint migration, timing synchronization or GPU claim is added.

Validation uses pinned BETSE setter bodies separately from independent named
owner/full-node field and full-rate references. Cover four ordinary families,
initial/evolved source-valid states, four sides, shared corners, owner/order and
padding changes, no-event identity, corrupt/stale records, strict parent
preservation and energy/turnover limits. Reuse existing comparison budgets:
rates `3e-12 + 3e-10*abs(reference)` (charge `3e-23` absolute), potentials
`3e-13 + 3e-10*abs(reference)`, stage energy residual `1e-10 pJ/s`, and existing
5% passive/fuel turnover ceilings. Fresh replay denies Cells/JAX imports.

Run on CPU5, one BLAS/XLA thread, process-tree RSS <=1 GiB, host reserve >=8 GiB,
480 seconds per phase. Capture frozen sources, inputs, reference evidence, raw
failed trials and durable success/failure artifacts under `/mnt/workspaces/Cells`.
Longer than ten minutes: detach and return without automatic polling. No follow-up
audit/regression or GPU job is scheduled by this workstream.
