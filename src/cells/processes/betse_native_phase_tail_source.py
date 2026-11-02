# Copyright 2014-2025 Alexis Pietak & Cecil Curry; see licenses/BETSE.txt.
# ruff: noqa: F821
"""Literal remaining SimPhase constructor statements and both kludge bodies.

Only the genuine existing SEED branch may be selected by the consumer.
The INIT/SIM bodies are retained as source, never a new phase authority.
"""


class PhaseConstructorTail:
    def complete(self, kind, p):
        self._init_kludge()

        # FIXME: Isolate exports produced by the "seed" phase to their own
        # directory; for simplicity, these exports currently reuse the same
        # directory as that of the "init" phase.

        # Absolute path of the top-level exports directory for this phase.
        if kind is SimPhaseKind.SEED:
            self.export_dirname = p.init_export_dirname
        elif kind is SimPhaseKind.INIT:
            self.export_dirname = p.init_export_dirname
        elif kind is SimPhaseKind.SIM:
            self.export_dirname = p.sim_export_dirname
        else:
            raise BetseSimPhaseException('Simulation phase "{}" unrecognized.'.format(kind.name))

    def _init_kludge(self) -> None:
        """
        Initialize all **kludges** (i.e., inelegant short-term workarounds
        intended to be replaced by actual long-term solutions) required by this
        simulation phase.
        """

        # FIXME: Eliminate this crude hack by refactoring all references to
        # "sim.dyna" throughout the codebase to "phase.dyna" instead. Naturally,
        # this will require refactoring all methods referencing "sim.dyna" to
        # accept a "phase: SimPhase" parameter. After doing so, remove this line.
        # Praise be to the multifoliate rose!
        # FIXME: O.K.; thanks to intrepid obsessiveness, only one submodule
        # referencing "sim.dyna" exists in the codebase: the
        # "betse.science.chemistry.networks" submodule. There currently exist
        # only 6 references to "sim.dyna" in this submodule. (Make 'em vanish.)
        self.sim.dyna = self.dyna

        # FIXME: Eliminate this crude hack by refactoring all references to
        # "p._run_sim" throughout the codebase to test "phase.kind" instead.
        # Although there only exists one remaining reference, refactoring that
        # reference will be a living nightmare. Why? Because the reference
        # resides in a modulator function -- which are currently called in an
        # extremely dynamic, inscrutable, non-greppable manner. Refactoring this
        # single reference to test "phase.kind" instead will require:
        #
        # * Defining a new high-level
        #  betse.science.math.modulate.make_modulator() function resembling:
        #      def make_modulator(modulator_name: str) -> CallableTypes
        # * Refactoring *ALL* modulator functions to accept a single "phase:
        #  SimPhase" parameter rather than the two "cells, p" parameters
        #  currently accepted by modulator functions.
        # * Refactoring *ALL* calls to modulator functions to instead:
        #  * First call the make_modulator() function. This will ensure that
        #    this *NEVER* happens again, by ensuring that we're able to
        #    reliably manage modulator functions from a single point of
        #    failure.
        #  * Next call the callable returned by that function, passing that
        #    callable the current "phase" object. Of course, this will in turn
        #    necessitate refactoring each callable performing such a call to
        #    transitively accept the current "phase" object. This is Hell.
        # * Refactoring the f_sweep() modulator function to test "phase.kind"
        #  rather than "p._run_sim".
        #
        # To grep for existing calls to modulator functions, grep for both the
        # strings "\bmodulator function\b" and "\bgetattr\(". Our YAML structure
        # appears to reliably refer to the desired modulator function for a
        # given operation via "'modulator function'". *sigh*
        self.p._run_sim = self.kind is SimPhaseKind.SIM

        # Initialize all time-specific kludges required by this phase.
        self._init_kludge_time()

    def _init_kludge_time(self) -> None:
        """
        Initialize all time-specific kludges required by this simulation phase.
        """

        # If this is the seed phase, avoid defining any of the following
        # ad-hoc "Parameters" instance variables.
        if self.kind is SimPhaseKind.SEED:
            return

        # FIXME: Eliminate all of the following crude hacks by:
        #
        # * Defining a new "betse.science.phase.phasetime" submodule.
        # * Defining a new "SimPhaseTime" class in this submodule: e.g.,
        #    class SimPhaseTime(object):
        #        '''
        #        Attributes
        #        ----------
        #        dt : float
        #            Duration in seconds of each time step (including sampled and unsampled)
        #            for the current simulation phase.
        #        t_resample : float
        #            Number of time steps between each sampled time step, including that
        #            sampled time step itself. Notably, if the current time step ``t`` is a
        #            sampled time step:
        #
        #            * ``t + t_resample`` is the next sampled time step (if any).
        #            * ``t - t_resample`` is the prior sampled time step (if any).
        #        total_time : float
        #            Duration in seconds of the current simulation phase *not* modified by
        #            extraneous settings (e.g., gap junction acceleration factor).
        #        '''
        #
        # * Defining a new "time" variable of this "SimPhase" instance in the
        #  above __init__() method: e.g.,
        #      from betse.science.phase.phasetime import SimPhaseTime
        #      self.time = SimPhaseTime()
        # * Shifting all of the following instance variables from being
        #  dynamically defined on the "Parameters" instance here to being
        #  statically (i.e., normally) defined in the SimPhaseTime.__init__()
        #  method instead.
        #
        # Lastly, note that if this is the seed phase, that the "self.time"
        # variable should default to "None" to induce exceptions on any
        # erroneous attempt to access time parameters when seeding.

        # Set temporal attributes specific to the passed simulation phase type.
        # These attributes include:
        #
        # * "dt", the duration in seconds of each time step for this phase.
        # * "total_time", the duration in seconds of this phase.

        # If this phase is an initialization...
        if self.kind is SimPhaseKind.INIT:
            self.p.dt = self.p.init_time_step
            self.p.resample = self.p.init_time_sampling
            self.p.total_time = self.p.init_time_total
        # Else if this phase is a simulation...
        elif self.kind is SimPhaseKind.SIM:
            self.p.dt = self.p.sim_time_step
            self.p.resample = self.p.sim_time_sampling
            self.p.total_time = self.p.sim_time_total
        else:
            raise BetseSimPhaseException(
                'Simulation phase "{}" unsupported.'.format(self.kind.name)
            )

        # Number of time steps (including sampled and unsampled) between each
        # unsampled time step, including that unsampled time step itself.
        self.p.t_resample = self.p.resample / self.p.dt
