# The engine's output format for a lumen standard potential (`cells.model.assembly_lineages@2`; FR-48)

FR-48 (D323). This page adds to `FORMAT.md` and `FORMAT_OL2.md` what a world writes when a species
declares a lumen standard potential. A world that declares none writes exactly what those pages
describe: no key, row or record entry below appears in it.

## The world

- **The declaration** is a third key in the species' potentials, an absolute value beside the
  solution one:

  ```json
  {"id": "S", "moieties": {"s": 1},
   "standard_mu_RT": {"solution": 0.7, "lumen": 1.393147},
   "catalogue": null, "evidence": null}
  ```

- **`lumen`** is μ°/RT at c0 in the lumen.
  - It replaces the solution potential at the species' lumen place alone, so the pool keeps the
    solution potential.
  - Δ = μ°_lumen − μ°_solution is a reversible free-energy difference across the shell. Every
    step reads it through the place's μ° (`mu0`): F, the heat per crossing, and each step's
    reverse ratio Σνμ°.
  - Undeclared, the lumen takes the solution potential, as before.
- **The shell law keeps all of Δ on the exit:** k⁻ = P_s·exp(Σνμ°), with the entry unchanged.
- **What it gives at equal volumes:** the inside count is Binomial(N, 1/(1 + e^Δ)) at equilibrium.
  The relaxation time follows the law's rate convention and is not a claim.
- **The world's dict** writes `lumen` only when it is declared. A world without it keeps its id
  and its programs (D148).

## Version 1's refusals, each by name

- a lumen potential in a world whose geometry is not `cells.assembly_geometry.prescribed_shell@1`. A bilayer's
  osmotic lumen, its lysis returns and its division would each read it;
- on a species with no lumen place;
- without a solution potential, since the records report Δ;
- in `cells.assembly_representation.rate_equations@1`, until FR-47's qualification.

## The records

- **The places table** (run.json's `places`): a lumen place whose species declares a lumen
  potential gains `lumen_offset_RT`, which is Δ = μ°_lumen − μ°_solution.
  - Its `standard_mu_RT` is μ°_lumen.
  - Every other row is unchanged, and the key is absent from every row of a world that declares no
    lumen potential.
