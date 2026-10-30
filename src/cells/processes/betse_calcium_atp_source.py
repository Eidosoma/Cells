# ruff: noqa: E501
"""Literal maintained-pool native CaATP helper; STATIC, NOT QUALIFIED.

The block and met arguments are source-unused. Negative calcium clipping,
zero-product substitution and unused backward arithmetic remain literal.
Original equations: BETSE1.5.0, Alexis Pietak and Cecil Curry.
"""

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions


class BetseSimUnstableException(ValueError):
    pass


class CalciumSourceRefused(ValueError):
    def __init__(self, reason, partial):
        super().__init__(str(reason))
        self.partial = partial


@dataclass(frozen=True, slots=True)
class Trial:
    incoming_membrane_mM: object
    incoming_bath_mM: object
    membrane_after_mM: object
    bath_after_mM: object
    voltage_V: object
    runtime_temperature_K: float
    parameters: object
    block_unused: object
    met_unused: object
    arithmetic: object
    flux_mol_m2_s: object
    source_completed: bool
    finite: bool
    failure: object


def evaluate(*, membrane_mM, bath_mM, voltage_V, runtime_temperature_K, parameters, block, met):
    # Explicit container shape is preserved, including the scalar refusal probe.
    ci = np.array(membrane_mM, dtype=np.float64, copy=True)
    co = np.array(bath_mM, dtype=np.float64, copy=True)
    vm = np.array(voltage_V, dtype=np.float64, copy=True)
    old_ci, old_co = ci.copy(), co.copy()
    observations = {}
    flux = None
    failure = None

    def observe(name, value):
        observations[name] = ions.freeze(np.asarray(value))

    try:
        with np.errstate(all="ignore"):
            flux = _equations(
                ci,
                co,
                vm,
                runtime_temperature_K,
                SimpleNamespace(**parameters),
                block,
                met=met,
                observe=observe,
            )
    except Exception as error:
        failure = dict(type=type(error).__name__, message=str(error))
    finite = all(np.isfinite(value).all() for value in (ci, co, vm, *observations.values()))
    trial = Trial(
        ions.freeze(old_ci),
        ions.freeze(old_co),
        ions.freeze(ci),
        ions.freeze(co),
        ions.freeze(vm),
        float(runtime_temperature_K),
        ions.freeze(parameters),
        ions.freeze(np.asarray(block)),
        ions.freeze(met),
        ions.freeze(observations),
        ions.freeze(flux),
        failure is None,
        bool(finite),
        ions.freeze(failure),
    )
    if failure:
        raise CalciumSourceRefused(failure["message"], trial)
    return trial


def _no_negs(data):
    """
    This function screens an (concentration) array to
    ensure there are no NaNs and no negative values,
    crashing with an instability message if it finds any.
    """
    inds_nan = np.isnan(data).nonzero()
    inds_neg = (data < 0.0).nonzero()
    if len(inds_neg[0]) > 0:
        data[inds_neg] = 0.0
    if len(inds_nan[0]) > 0:
        raise BetseSimUnstableException(
            "Your simulation has become unstable. Please try a smaller time step,reduce gap junction radius, and/or reduce rate coefficients."
        )
    return data


def _equations(cCai, cCao, Vm, T, p, block, met=None, *, observe):
    """
    Parameters
    ----------
    cCai            Concentration of Ca2+ inside the cell
    cCao            Concentration of Ca2+ outside the cell
    voli            Volume of the cell [m3]
    volo            Volume outside the cell [m3]
    Vm              Voltage across cell membrane [V]
    p               An instance of Parameters object


    Returns
    -------
    cCai2           Updated Ca2+ inside cell
    cCao2           Updated Ca2+ outside cell
    f_Ca            Ca2+ flux (into cell +)
    """
    deltaGATP_o = p.deltaGATP
    observe("before_no_negs_membrane", cCai)
    _no_negs(cCai)
    observe("after_no_negs_membrane", cCai)
    observe("before_no_negs_bath", cCao)
    _no_negs(cCao)
    observe("after_no_negs_bath", cCao)
    cATP = p.cATP
    cADP = p.cADP
    cPi = p.cPi
    Qnumo = cADP * cPi * cCao
    observe("quotient_numerator", Qnumo)
    Qdenomo = cATP * cCai
    observe("quotient_denominator_raw", Qdenomo)
    inds_Z = (Qdenomo == 0.0).nonzero()
    observe("zero_denominator_indices", inds_Z[0])
    Qdenomo[inds_Z] = 1e-16
    observe("quotient_denominator_used", Qdenomo)
    Q = Qnumo / Qdenomo
    observe("quotient", Q)
    Keq = np.exp(-(deltaGATP_o / (p.R * T) - 2 * (p.F * Vm / (p.R * T))))
    observe("equilibrium", Keq)
    numo_E = cCai / p.KmCa_Ca * (cATP / p.KmCa_ATP)
    observe("forward_numerator", numo_E)
    denomo_E = (1 + cCai / p.KmCa_Ca) * (1 + cATP / p.KmCa_ATP)
    observe("forward_denominator", denomo_E)
    frwd = numo_E / denomo_E
    observe("forward", frwd)
    numo_Eb = cCao / p.KmCa_Ca
    observe("backward_numerator_unused", numo_Eb)
    denomo_Eb = 1 + cCao / p.KmCa_Ca
    observe("backward_denominator_unused", denomo_Eb)
    bkwrd = numo_Eb / denomo_Eb
    observe("backward_unused", bkwrd)
    f_Ca = -p.alpha_Ca * frwd * (1 - Q / Keq)
    observe("raw_flux_mol_m2_s", f_Ca)
    return f_Ca
