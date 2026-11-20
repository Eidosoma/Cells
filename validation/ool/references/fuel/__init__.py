"""Independent references for fuel, option (d) of the OL4 fuel design (OL5's side).

Written from one source only: ``docs/ORIGIN_OF_LIFE_FUEL_DESIGN.md`` at the git tag
``ol4-fuel-note-2026-11-20``. The engine design note at that tag and OL5's earlier references in
the parent package were read for conventions. Nothing here imports ``cells`` or reads the engine's
code, the builders' validation code, the note author's desk probe or any engine output.

Option (d) is a fuel-to-waste cycle: in the pool F + S -> B + W recharges a spent building block
S into an activated block B; B joins membranes; inside a membrane B + L_i -> 2 L_i, catalysed by
its own product L_i (the transition-state factor, beta > 0); L_i decays to S, uncatalysed, and S
leaves for the pool. The modules:

- ``registered``: the registered worlds, probe states, cycles, runs and refusals (``designs/``);
- ``law``: the exact law of the worlds without geometry (OL1's ``laws.Law``, unchanged) with the
  fuel's planted forms, and the fuel parser's extra refusal;
- ``kernel``: the pair identity with fuel and the cycle's drive on kernel tables (rows OL4-1, OL4-2);
- ``ledger``: closure with fuel, the payers' split and the moieties (rows OL4-3, OL4-4);
- ``stationary``: the true-equilibrium control, the driven steady state, its flux and heat, the
  modality and the mean switching time (rows OL4-5 to OL4-7);
- ``bistability``: §2.3's reduced model in closed form, exactly, with its nulls (row OL4-8);
- ``vesicle``: the fuel law in vesicle worlds (V1), with the geometry of OL2;
- ``harness``, ``standin``, ``design``: the rows against saved records, honest and planted record
  sets, and the machine-readable design.
"""
