"""Independent references for FR-6's A5'' (D162, D216): a channel population driven through a
regulatory state with a per-cell prior.

Two cells start in different conditions (s0) and receive the same regulator dose. Their K-leak
populations' availability follows the state, F = b + (1 - b) s. The references reuse the coupling
operator's independent references unchanged (``validation/coupling``):
- R-cell's world classes and its integrator (``cells_reference``: ``World``, ``Cell``, ``Patch``,
  ``Population``, ``Regulator``, ``State``, ``Input``, ``Coupling``, ``simulate``, ``floor``,
  ``compare``);
- R-state's turnover regulator and closed forms (``state_reference``).

What is new here:
- the registered worlds (``worlds.py``, ``reference_inputs.json``);
- the planted controls that tell the two cells apart (``controls.py``);
- an honest second-order stand-in on the dt ladder (``schemes.py``);
- the registered design and values (``design.py``, ``designs/``).

Nothing here imports ``cells`` or reads the operator's code, its tests or its fixtures.
"""
