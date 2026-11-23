# The engine's output format for binding from a shell's inner face (`cells.assembly_lineages@2`; FR-46)

FR-46 (D323). This page adds to `FORMAT.md` and `FORMAT_OL2.md` what a world writes when a site pair
declares the inner face. A world whose pairs are all outer, FR-21's, writes exactly what those pages
describe: no key below appears in it.

## The world

- **A site pair's face:**

  ```json
  "sites": [{"site": "R", "complex": "XR"},
            {"site": "R", "complex": "XRi", "face": "inner"}]
  ```

  - `face` is `"outer"`, the default, which is never written, or `"inner"`.
  - An outer pair binds from the pool, X@pool + site@membrane → complex@membrane (FR-21).
  - An inner pair binds from the lumen, X@lumen + site@membrane → complex@membrane, in a prescribed
    shell only (version 1).
  - Both are under `cells.stochastic_mass_action@1` with `count_on_m`, declared in that direction.
    The forward is a⁺ = k_f·θ⁺·n_site, with θ⁺ the ligand's own phase's activity. The reverse
    returns the ligand to that phase.
- **A pair binds on its own face only.** The other shape for the same pair is refused by rule 3.

## The face rule

- **One face per complex, propagated by ligand moiety over every wall state.**
  - Each admitted binding seeds its complex with its face, for each moiety of its ligand.
  - Every step wholly in the membrane joins, per moiety, each reactant that holds the moiety with
    each product that holds it. A wall state with no binding pair of its own therefore carries the
    face on.
- **A component that holds both faces is refused by name, listing its wall states.** It would let
  the ligand pass from the pool to the lumen through the wall, a carrier.

## Version 1's refusals, each by name

- inner-face binding outside a prescribed shell (rule 3);
- in `cells.rate_equations@1`;
- a carrier across the wall (the face rule).

**Rule 3's message** now names both admitted shapes. Its prefix, "world: step … crosses phases at
the membrane", is unchanged.

## The records

**world.json's `sites`** writes `"face": "inner"` for an inner pair only. An outer pair's entry is
unchanged.
