# Fixed merged-B09 constructor input

The initial mesh campaign's merged-square case was refused by the physical
geometry adapter before constructor comparison. This new, separate adapter
authenticates only the original fixed B09 constructor input. The original
failed campaign and physical bridge remain unchanged.

The single admitted case has nine explicit seed occurrences. The loader checks
the fixed reviewed receipt, its case and source-manifest hashes, revision,
NumPy version, exact captured constructor points and original IDs. It retains
the full before-RNG state and verifies the recorded explicit-point constructor
did not advance it. There is no seed replay or new RNG qualification claim.
No caller coordinates, constructor overrides, new receipt authority or native
lattice relabel is accepted. Constructor metadata and numeric evidence are
immutable, with validation against the fixed capture.

The flags `allow_merging=True`, `mesh_type='quad'` and
`make_all_operators=True` remain literal. Loading this input builds neither a
constructor, a mesh nor operators. A future source constructor/pre_mesh path
must be explicitly qualified. The output has a distinct constructor-input
kind and supplies no physical geometry bridge or topology admission. The old
geometry adapter still rejects merging; a prepared check verifies that guard.

Fourteen checks are prepared for fixed input content, physical guard refusal,
resealed tampering, unknown case names, immutable ownership, forged receipts
and global RNG preservation. Only AST/source checks and Ruff have run; the
loader, tests and scientific modules were not executed during preparation.
There is no numerical retry, tolerance change or reclassification of the prior
mesh failure. Chief coordinates review and any future integration/launch.
