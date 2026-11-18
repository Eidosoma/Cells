"""Independent references for FR-3, site occupancy (D159, D169, D216).

Written from ``docs/SITE_OCCUPANCY_DESIGN.md`` Appendix A (A.1 to A.7), §2, §3.3 and §8, and from
the FR lane's registered inputs once they exist. Nothing here imports ``cells`` or reads the
engine's code, the operator's tests or fixtures. NumPy, SciPy and exact ``fractions`` and
``decimal`` arithmetic only.

- ``kinetics``: R-ode, the declared binding and internalisation network (A.2) integrated by Radau
  and cross-checked by DOP853, with the heat and work integrals carried as states (A.3).
- ``closed``: R-closed, A.4's closed forms, and R-qss, A.5's quasi-steady saturable law.
- ``equilibrium``: R-eq, the equilibrium of populations sharing a closed node, and its heat.
- ``energy``: R-dG, the site and node free energies, the stable increments, and the ledger.
"""
