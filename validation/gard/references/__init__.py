"""Independent component references for the GARD law set and its general machinery.

Each module is one row of the claims table in ``docs/GARD_DESIGN.md`` §6.1. It is
written from the public sources and from derivations given in its docstring:

- the preprint, *Plastic heredity* v5.0 (Zenodo record 22799362,
  doi:10.5281/zenodo.22799362), p. 10 and Appendix F;
- Segrè, Ben-Eli and Lancet 2000, PNAS 97:4112 (PMC18166), Eqs. 2 and 4;
- Gross, Fouxon, Lancet and Markovitch 2014, BMC Evol Biol 14:265 (PMC4357159), Eq. 2;
- Lancet, Zidovetzki and Markovitch 2018, J R Soc Interface 15:20180159 (PMC6073634).

Nothing here imports ``cells`` or reads the engine's code. The modules use NumPy,
SciPy and exact ``fractions`` arithmetic only. ``harness.py`` runs every reference
against an engine run's saved records and fails loudly when a record is missing.
"""
