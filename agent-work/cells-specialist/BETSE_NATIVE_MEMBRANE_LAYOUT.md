# Explicit native six-column membrane layout

This adapter addresses a concrete schema mismatch before any integration with
the held initialization packet. Pinned BETSE `cellVerts`, `quickVerts` and
`deformWorld` write `mem_vects_flat` as `[mid_x,mid_y,nx,ny,tx,ty]`. The first two
columns duplicate `mem_mids_flat` in metres. The remaining four columns are
dimensionless normal and tangent components. A source/AST audit records all
three writers and 66 active consumer slices in ten files, plus the owner-order
flattening helper. Plotting reads midpoints and tangents as well as normals.

The held initialization02 gate expects four columns and compares its last two
columns with normals. A `[nx,ny,tx,ty]` view therefore has a different contract.
The new prefix provides two separately named opt-in conversions:

| Conversion | Selected native columns | Roles | Units |
| --- | --- | --- | --- |
| `native_six_to_midpoint_normal_xy@1` | 0,1,2,3 | mid_x,mid_y,nx,ny | m,m,1,1 |
| `native_six_to_normal_tangent_xy@1` | 2,3,4,5 | nx,ny,tx,ty | 1,1,1,1 |

Both view objects retain their complete six-column parent and explicit column
map. Neither conversion invokes the existing initialization handoff. The
initialization02 core, fixture, runner, source budgets and frozen bundle remain
unchanged. Future integration requires its own reviewed changes after this
feature is qualified.

The production module uses only the standard library. Passive capture reads
named instance stores without native methods, copies their logical row bytes,
and records original dtype, byte order, shape and strides. Numeric snapshots
are immutable `Buffer` objects; consumers can see exactly which bytes and
columns they receive. Fortran, strided and big-endian source arrays are copied
in logical C row order while their original stride metadata remains recorded.
This preserves values and source storage metadata, rather than reproducing a
caller's aliasing or stride layout. No cast or numerical tolerance is used.
Binary64 vector/midpoint arrays and 32/64-bit integer owner buffers are the
supported schema. Unsupported dtypes and unreadable stores remain explicit
capture errors and cannot bind.

The six required owner stores are `cell_i`, `mem_i`, `mem_to_cells`,
`cell_to_mems`, `mem_mids_flat` and `mem_vects_flat`. Native cell and membrane
axes must remain complete and contiguous. The actual inverse owner rows must
flatten to that same membrane axis in cell-major, local-edge order; no sorting
or owner inference is permitted. Object-array owner containers retain their
dtype/shape/stride headers and complete integer contents, including per-row
headers when rows have object dtype. Object pointer addresses are not copied
as numeric data. Local indices correspond to source polygon edge `(i-1,i)`;
the adapter never manufactures physical endpoints from them.

Midpoint duplicate stores must agree bitwise, including signed zero and byte
order. All six columns must be finite binary64. These are schema conditions;
the adapter computes no polygon, midpoint, length, unit-vector correction,
surface measure, volume, boundary relation or inverse operator. A proposed
nonunit-vector specimen intentionally remains admissible as an unqualified
schema, demonstrating that layout acceptance carries no vector-geometry
credit. Source class/hash observations establish which object was read; they
do not establish that `seed`, `init`, loading, deformation or bootstrap ran.

The independent checker receives the complete original snapshot, bound layout
and explicit views. It uses separate stdlib byte decoding and owner scans,
compares original/parent bytes and metadata, checks seals and closed gates,
and reconstructs each named view directly from native byte offsets. It imports
no production or scientific module. The proposed panel contains 43 checks,
14 fresh checker workers and a Root finalizer: 58 units. Six positive cases
are supplied schema specimens, not native generation or scientific cases.
Controls cover missing/four-column/float32/nonfinite stores, midpoint signed
zero and dtype changes, owner disagreement, declarations, resealing, parent
and view corruption, caller buffer independence and continued handoff refusal.

Declarations precede store construction; original stores, capture results,
conversion requests, outputs and checker inputs are persisted before gates.
Failure artifacts retain the full state and any captured original/partial
buffers. Large payloads remain sidecars. Preparation performs source/AST
audits, code-object compilation, Ruff, hashes and immutable copying only.
No adapter, fixture, checker or native evaluation, collection or numerical job
is authorized by this packet. Chief owns review, subsequent launch and
finalization; `PROGRESS.md` remains Root-owned. Every physical, vector geometry,
native seed/init history, integration and ordinary-loop gate stays closed.
