"""Independent references for FR-1, the closed compartment (D157, D169, D216).

Written from ``docs/CLOSED_COMPARTMENT_DESIGN.md`` Appendix A (A.1 to A.10) and §6, and from the FR
lane's registered inputs once they exist. Nothing here imports ``cells`` or reads the engine's
code, the operators' tests or fixtures. The modules use NumPy, SciPy and exact ``fractions`` and
``decimal`` arithmetic only.

- ``exact``: decimal and rational helpers, a 50-digit matrix exponential, a rational linear solve.
- ``forms``: the closed forms A.2, A.3 and A.5 to A.8, each with a second method.
- ``stepmap``: A.4, the palindrome's step map, its fixed point and its splitting term.
- ``capacitor``: A.9, a dense capacitor solve of its own.
- ``energy``: A.10, the free energy and each law's work.
"""
