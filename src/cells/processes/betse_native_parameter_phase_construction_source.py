# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821
"""Complete original phase tail/time bodies; definitions only, never a fake phase.

Actual phase, kind, Cells, Simulator and callback authority belong to a separately
authenticated source consumer. Only annotations are omitted in this proof.
"""


class PhaseParameterTail:
    def _init_kludge(self):
        """
        Initialize all **kludges** (i.e., inelegant short-term workarounds
        intended to be replaced by actual long-term solutions) required by this
        simulation phase.
        """
        self.sim.dyna = self.dyna
        self.p._run_sim = self.kind is SimPhaseKind.SIM
        self._init_kludge_time()

    def _init_kludge_time(self):
        """
        Initialize all time-specific kludges required by this simulation phase.
        """
        if self.kind is SimPhaseKind.SEED:
            return
        if self.kind is SimPhaseKind.INIT:
            self.p.dt = self.p.init_time_step
            self.p.resample = self.p.init_time_sampling
            self.p.total_time = self.p.init_time_total
        elif self.kind is SimPhaseKind.SIM:
            self.p.dt = self.p.sim_time_step
            self.p.resample = self.p.sim_time_sampling
            self.p.total_time = self.p.sim_time_total
        else:
            raise BetseSimPhaseException(
                'Simulation phase "{}" unsupported.'.format(self.kind.name)
            )
        self.p.t_resample = self.p.resample / self.p.dt
