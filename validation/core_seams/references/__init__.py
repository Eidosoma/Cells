"""Independent references for the core-seams pass: seam A (membrane cycles) and seam C (binding).

Written from CORE_SEAMS_DESIGN §3, §5, §16, §17, §18 and the lead's rulings in §19, and from
CORE_SEAMS_STEP0 §1.1 and §7 (their claims, not their scripts). Nothing here imports ``cells`` or
reads the engine's code, its laws, kinds, operators or @3. Standard-library ``decimal`` and
``fractions`` arithmetic, with NumPy for the registered random draws.

- ``exact``: exact SI constants, 60-digit decimals and forward-mode duals.
- ``diagrams``: kinetic diagrams, Hill's cycles by spanning trees and by the matrix-tree minors,
  the master equation's steady state, and Wegscheider's residual, exact and affine.
- ``cycles``: cycle laws on a population (diagram, factored version-1 and net-flow kinds), rows,
  heat, work, charge, exact slopes and the parse-time checks.
- ``binding``: the multi-ligand closure's speciation, conservation, charge, G* and P1's node.
- ``worlds``: the registered inputs; ``design``: the registered values and design; ``api``: the
  entry points.
"""
