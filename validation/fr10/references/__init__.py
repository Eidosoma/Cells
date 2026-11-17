"""Independent references for FR-10, the scheduled bath composition (D166, D169, D216).

Written from ``docs/BATH_SCHEDULE_DESIGN.md`` (§2.2, §2.3, §4, §7-§8 and Appendix A) and the
FR lane's registered inputs (``reference_inputs.json``, copied unchanged). Nothing here imports
``cells`` or reads the engine's code, its tests or its fixtures. The modules use NumPy, SciPy and
exact ``fractions`` and ``decimal`` arithmetic only.

- ``faces``: R-faces, a neutral species on a face chain with a stepped held bath (A.2), solved
  exactly per epoch.
- ``ion``: R-ion, a passive cell whose held bath is stepped (A.3): the constant-field flux and the
  capacitor.
- ``records``: R-records, the dose, the bath's free-energy change and the step's charge at each
  event (A.4, §2.2), and the reservoir-work reconciliation K(t) (A.5, §2.3).
- ``controls``: the planted controls and their margins (the design's power).
- ``schemes``: honest and first-order stand-in steppers on the registered dt ladder.
- ``design``: writes the registered design files under ``designs/``.
"""
