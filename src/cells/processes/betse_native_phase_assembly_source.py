"""Literal SimPhase constructor prefix, ending at the self.sim assignment.

Annotations/decorators and the remaining constructor are outside this selected
body boundary. The driver requires an actual prepared callback argument.
"""

phasecallbacks = None  # Supplied privately by the selected constructor driver.


class PhaseConstructorPrefix:
    def construct(self, kind, p, cells=None, sim=None, callbacks=None):
        from betse.science.cells import Cells
        from betse.science.math.cache.cacheabc import SimPhaseCaches  # noqa: F401
        from betse.science.sim import Simulator
        from betse.science.tissue.tishandler import TissueHandler  # noqa: F401

        if callbacks is None:
            callbacks = phasecallbacks.make_default()
        if cells is None:
            cells = Cells(p=p)
        if sim is None:
            sim = Simulator()

        self.callbacks = callbacks
        self.cells = cells
        self.kind = kind
        self.p = p
        self.sim = sim
