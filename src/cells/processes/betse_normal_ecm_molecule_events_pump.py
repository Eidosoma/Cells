"""Unchanged NaK arithmetic with actual SIM source-phase evidence labels."""

from cells.processes import betse_normal_ecm_init_phase_pump as original
from cells.processes import betse_normal_ion_join as ions

finite = original.finite


def produce(binding, parent, stores, incoming_rate, observer=None):

    def reached(value):
        if observer is not None:
            observer(ions.freeze(dict(ions.data(value), source_phase="SIM", legacy_run_sim=True)))

    result, flux, proxy = original.produce(binding, parent, stores, incoming_rate, reached)
    result = dict(ions.data(result))
    result["before"] = dict(result["before"], source_phase="SIM", legacy_run_sim=True)
    return (ions.freeze(result), flux, proxy)
