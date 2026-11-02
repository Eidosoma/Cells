# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821
"""Literal SimPhase constructor continuation, stopping before _init_kludge.

TissueHandler resolves only to the consumer's genuine new-constructor path.
The five handler bodies are reused from the retained tissue source module.
"""


class PhaseDynaContinuation:
    def attach(self, p):
        self.dyna = TissueHandler(p=p)
