"""The mitochondrial cycle laws' shared source and conventions (docs/MITOCHONDRIA_LAWS_APPENDIX.md
at tag mito-laws-appendix-2026-11-20b, ruled by the user in D236): D. A. Beard's 2005 model of
oxidative phosphorylation and its 2006 correction, both CC BY. It declares no law of its own; each
law is its own inert module, since registry/laws.py's loader takes one LAW per module.

The appendix's conventions (§0, frame B), as the cycle kind runs them:
- N is the matrix and P the intermembrane space. Every row is a base form, and every proton is
  counted.
- x is the kind's, from the species registry's base-form potentials (§9; the named set
  cells.potential_set.beard2005@1), never from a law's constant.
- Activities are a = c/1 M, the monomial form's standard state of 1000 mM.
- The kind's psi = F (phi_N - phi_P)/RT is -u, with u = F Delta psi/RT and
  Delta psi = phi_P - phi_N. So the appendix's e^(k u) is zeta (or eta) = -k.
- A population's capacity carries the law's rate constant X (Table 1, in the column the definition
  chooses) times the mitochondrial volume. That turns mol s^-1 per litre of mitochondria into
  fmol/s.
- Each declared flux is J = S (1 - e^x). A law whose source writes its exponent per electron pair
  has its affinity share: 2 for complex III, 4 for complex IV."""

from cells.modules import Citation, CitedWork

APPENDIX = "docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20b (D236)"
BEARD_2005 = CitedWork(
    ("Beard DA",),
    2005,
    "A biophysical model of the mitochondrial respiratory system and oxidative phosphorylation",
    doi="10.1371/journal.pcbi.0010036",
)
BEARD_2006 = CitedWork(
    ("Beard DA",),
    2006,
    "A biophysical model of the mitochondrial respiratory system and oxidative phosphorylation "
    "(correction, Table 1)",
    doi="10.1371/journal.pcbi.0020008",
)
LICENCE = "CC BY (both works); the constants are Table 1's (the 2006 correction) and Table 2's"


def citation(place, departures=()):
    """A mitochondrial law's Citation: the source as the appendix declares it, at `place`."""
    return Citation(
        f"D. A. Beard's model of oxidative phosphorylation, as declared in {APPENDIX}",
        place,
        LICENCE,
        tuple(departures),
        (BEARD_2005, BEARD_2006),
    )
