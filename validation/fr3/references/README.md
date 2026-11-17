# FR-3's independent references: site occupancy (desk forms)

**Desk forms, 17 November 2026. Not yet registered.** These are the reference forms of
`docs/SITE_OCCUPANCY_DESIGN.md` Appendix A (A.1–A.5), for §8.3's items Q1–Q5:
- R-ode (`kinetics.py`): Radau, cross-checked by DOP853, with the heat and work integrals carried
  as states in a form that stays regular at B = 0 and at R = 0;
- R-closed and R-qss (`closed.py`);
- R-eq (`equilibrium.py`);
- R-dG (`energy.py`).

The registered design follows the FR lane's inputs file and comes before any engine output. FR-1
takes priority over FR-3 (the lead, 17 November 2026). Following the lead's scope ruling, no world
here combines site occupancy with a bath schedule.

**Written without the engine:** nothing imports `cells` or reads `src/cells/`, the operator's tests
or fixtures, or the FR owner's branch. Read: the design's Appendix A, §2, §3.3–§3.4, §4.1 and
§4.3–§4.4, and §8. Not blind: §4.4 and §8.3 report prototype and engine measurements, such as
the heat-sign table and the prototype's orders. They inform nothing here.

**Readings to settle with the inputs:**
1. R-qss's order in ε is measured on the uptake's relative error, with S varied at fixed V (§8.3's
   sweep). Normalised by n₀ with V varied, the same runs show order 2.
2. RT is 1e-3 R T pJ/fmol with the exact SI R, unless the inputs give the engine's RT.

**Tests:** `tests/unit/test_fr3_references_forms.py`, 9 tests with planted controls. They take
about 25 s on a loaded machine, and are to be trimmed below tier 1's 20 s before the tier rows.
