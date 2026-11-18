"""Independent component references for the origin-of-life engine's laws (OL5).

Each module serves rows of the claims tables in ``docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md``
§7.1-7.2, for the milestones OL1-OL4. It is written from the design's equations and the cited
public sources, with every formula re-derived in its docstring.

Nothing here imports ``cells`` or reads the engine's code. The modules use NumPy, SciPy and
exact ``fractions`` arithmetic only. ``harness.py`` runs every reference against an engine
run's saved records and fails loudly when a record or a declared convention is missing.
"""
