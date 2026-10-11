# Next bounded BETSE gates after recording closure

2026-09-17, D130. Readiness snapshot frozen with R1-S0; current execution status
lives in `PROGRESS.md`. This is not a claim of full BETSE coverage.

## Pump–leak: R1-S0 first

R0's saved live outputs and expected window receipts are independently closed.
Next run the separately registered **18-solve 10 ms reference/domain study**.
This answers whether the original equations, reference settings, domains and
accounting remain suitable, and reports endpoint drift without claiming equilibrium.
It does not yet run either simulator or certify the proposed native step ladder.

After its review, measure an explicit native timestep/resource probe and design
the full six-control native/Cells comparison, including restart and physical-prefix
checks. Keep scientific limits fixed. Retain finer-step alternatives as prospective
choices, not automatic retries after a failure. Longer relaxation and recovery
are later scientific experiments, not consequences of elapsed simulation time.

## Gap junctions: useful next capability, not inferred from the pump cluster

The existing accepted preparation establishes **seven cells and thirty membrane
faces**, membrane owners, areas and bath geometry. Its saved geometry does **not**
contain the reciprocal face-neighbour/physical-edge map needed to select and
audit junctions. It is not evidence of active junction transport.

The next J0 deliverable is a supported native preparation that records neighbour
maps, reciprocal pairs, distances, areas, boundary masks and species-specific
transport coefficients. Select actual edges from that evidence. Start held-open,
with disconnected, zero-drive, sign-reversal and single-transfer controls; count
each physical exchange once with opposite endpoint ownership. Then test coupled
transport and only afterward native gate initialization/update/block semantics.
No arbitrary two-cell seed, invented adjacency, or copying of suspected repeated
gate advances into Cells' physical model. No junction capture launches here.

## Biology: provenance work can proceed without simulator parity

The existing Xenopus/Costa candidate remains **non-runnable and unvalidated**.
It records original-abstract versus BETSE-table permeability differences, unknown
uncertainty definitions and unresolved chloride/preparation assumptions. No
original full methods or tables were newly reviewed in this step.

The next data-readiness deliverable should obtain and review the original methods
and tables, establish units/conditions and uncertainty definitions, and explicitly
separate measured inputs, initialized values, fitted quantities and held-out
outcomes. Decide a justified chloride mechanism or non-steady-state scope before
choosing biological tolerances. Do not turn the historical simulated bath/endpoints
into experimental inputs or validate against initialized target concentrations.

## Architecture implications

No production or physics change is needed for this reference-scoping step.
Preserve pure array laws, complete numerical state, explicit transfer ownership,
and separate observation/I/O policy. GPU qualification and conservative fine/coarse
coupling remain independent gates. Windowing bounds retained output; it is not
multirate integration or whole-BETSE constant-memory execution. Organ identity
remains data, with multi-organ coupling a later implementation and validation task.
