# Prospective requested junction increment

This packet adds the read-only diagnostic
`junction_requested_outward_increment_mol_m3`, with ion × cell axes. It records
the signed outward concentration operand requested by the gap update, before
that operand is added to the binary64 bulk store and before clipping:

```
dg = owner_sum @ (-junction_flux * membrane_area) / cell_volume
requested_outward_increment = -(dt * dg)
```

The existing `cell += dt * dg`, membrane cache, clipping operation, ledgers and
`membrane_bulk_difference_mol_m3 = membrane - cell[:, owner]` remain unchanged.
Stationary and uncommitted ions retain a zero requested increment. A clipped
bulk concentration does not change the requested increment. Binding and state
identities are unchanged; a trial identity includes diagnostics and can change.

The original forty-check ECM panel remains **failed: 39/40**. Its original
high-pump `signed_environment` raw-lag assertion remains failed, with its fixed
`3e-13 + 6e-12 * abs(reference)` budget. This prospective quantity is different
from the stored endpoint difference. The new checks neither rerun nor
reclassify that original assertion. The original checker, test, fixtures,
protocol and native capture are pinned without modification.

The concrete risk addressed by this separate protocol is loss of a small gap
operand during a much larger rounded bulk addition, followed by subtraction
of the stored endpoints. The retained-data diagnosis and its unchanged failed
evidence are linked by the preparation plan. Adding an accurate operand cannot
make the old raw lag more accurate. It also cannot remove the independent
paired-path material imbalance already present in the supplied native inputs.
No path averaging, membrane refresh, conservation fix or energy claim is made.

Ten exact retained contexts cover the failing high-pump case, slow transport,
clipping, stationary ions, stationary pump roles, reversed moving order, cache
lag, fast duplicate sites, permutation and zero transport. No fixture constructor
is invoked during preparation. Their original metadata and typed NPZ inputs,
outputs and projected references are copied into a hash-pinned retained corpus.

Seventeen proposed producer checks and twenty-six fresh worker units are
declared by AST without pytest collection. Each returned trial, failed returned
trial, complete native proof and typed array is saved before comparisons. Every
legacy numerical column must remain identical in shape, dtype and binary64
bytes, including signed zero, to the original retained baselines. Every native
column is also compared with an unchanged native capture in a fresh process.

The independent reference imports only the standard library. It derives its
geometry, source chronology and scalar owner sums independently at the existing
100/160-digit settings. Its optional observer receives a deep copy of the full
raw result before binary64 projection. New mandatory retention saves complete
typed Decimal trees, every coefficient digit/exponent/signed zero, source nonce
binary64 bits, metadata, geometry, stage buffers, candidates, ledgers and the
conservative oracle. Binary64 projections are saved separately. Fresh workers
deny Cells, BETSE and every scientific package, reproduce both full raw trees
and projections, then compare the new quantity with the original fixed budget
and reference resolution fraction of 0.1.

Additional checks reconstruct the exact bulk update from its recorded requested
operand, preserve clipping and stationary state, verify the unchanged raw
endpoint subtraction and reject wrong sign, wrong cell axis, stationary nonzero,
clipped raw lag and rounded state-difference substitutions. A typed-codec case
preserves long decimals, container types and binary64 signs; an observer case
mutates its deep copy and requires the returned full reference to stay intact.

This preparation executes only source parsing, AST normalization, compilation
of code objects, Ruff, hashing and copying. It does not import scientific code,
construct fixtures, collect tests, execute either solver or reference, poll an
active job or edit central `PROGRESS.md`. The immutable packet has a closed
numerical launch gate. Chief owns preflight, a launcher, the finalizer and any
later authorization or scientific qualification. A later runner must set
`CELLS_ECM_REQUESTED_INCREMENT_CORPUS_ROOT` to the packet's `retained_corpus`,
use its frozen source/native tree, include `dependencies/pillow` in `PYTHONPATH`
and use the distinct `betse-ecm-requested-increment-declared-units.json`.
