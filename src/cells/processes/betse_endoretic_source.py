"""Literal EndoRetic state and update with explicitly owned all-ion arrays.

Static preparation only. Raw source negatives and nonfinite returns remain
observable; finite publication is checked separately. No explicit buffer or
finite-fuel chemistry is introduced.
"""

import copy
from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_normal_ion_join as ions

FIELDS = (
    "cc_er",
    "er_vol",
    "er_sa",
    "Ver",
    "Q",
    "cm_er",
    "Dm_er",
    "Dm_er_base",
    "Dm_channels",
    "zer",
)
PARAMETERS = (
    "serca_max",
    "max_er",
    "act_Km_Ca",
    "act_n_Ca",
    "inh_Km_Ca",
    "inh_n_Ca",
    "act_Km_IP3",
    "act_n_IP3",
)


def _pumpCaER(cCai, cCao, Vm, T, p):
    deltaGATP_o = p.deltaGATP
    cATP = p.cATP
    cADP = p.cADP
    cPi = p.cPi
    Qnumo = cADP * cPi * cCai
    p._observe("quotient_numerator", Qnumo)
    Qdenomo = cATP * cCao
    p._observe("quotient_denominator_raw", Qdenomo)
    inds_Z = (Qdenomo == 0.0).nonzero()
    Qdenomo[inds_Z] = 1e-16
    p._observe("quotient_denominator_used", Qdenomo)
    Q = Qnumo / Qdenomo
    p._observe("quotient", Q)
    Keq = np.exp(-deltaGATP_o / (p.R * T) - 2 * (p.F * Vm / (p.R * T)))
    p._observe("equilibrium", Keq)
    numo_E = cCao / p.KmCa_Ca * (cATP / p.KmCa_ATP)
    denomo_E = (1 + cCao / p.KmCa_Ca) * (1 + cATP / p.KmCa_ATP)
    frwd = numo_E / denomo_E
    p._observe("forward", frwd)
    numo_Eb = cCai / p.KmCa_Ca
    denomo_Eb = 1 + cCai / p.KmCa_Ca
    bkwrd = numo_Eb / denomo_Eb
    p._observe("backward_unused", bkwrd)
    f_Ca = p.serca_max * frwd * (1 - Q / Keq)
    p._observe("serca_flux_mol_m2_s", f_Ca)
    return f_Ca


def _electroflux(cA, cB, Dc, d, zc, vBA, T, p, rho=1):
    FLOAT_NONCE = 1e-25
    vBA += FLOAT_NONCE
    zc += FLOAT_NONCE
    alpha = zc * vBA * p.F / (p.R * T)
    exp_alpha = np.exp(-alpha)
    deno = -np.expm1(-alpha)
    flux = -(Dc * alpha / d) * ((cB - cA * exp_alpha) / deno) * rho
    return flux


class _LiteralEndoRetic(object):
    def __init__(self, sim, cells, p):
        self.er_vol = 0.1 * cells.cell_vol
        self.er_sa = 1.0 * cells.cell_sa
        self.Ver = np.zeros(sim.cdl)
        self.Q = np.zeros(sim.cdl)
        self.cm_er = p.cm
        sim.cc_er = copy.deepcopy(sim.cc_cells)
        sim.cc_er[sim.iCa][:] = 0.2
        self.Dm_er = copy.deepcopy(sim.cc_cells)
        for arr in self.Dm_er:
            arr[:] = 1e-18
        self.Dm_er_base = copy.deepcopy(self.Dm_er)
        self.Dm_channels = copy.deepcopy(self.Dm_er)
        self.zer = copy.deepcopy(sim.cc_cells)
        for i, arr in enumerate(self.zer):
            arr[:] = sim.zs[i]

    def get_v(self, sim, p):
        self.Q = np.sum(self.zer * p.F * sim.cc_er, axis=0)
        self.Ver = 1 / self.cm_er * self.Q * (self.er_vol / self.er_sa)

    def update(self, sim, cells, p):
        self.channels(sim, cells, p)
        self._observe("channels", sim, None, None)
        f_CaATP = stb.pumpCaER(sim.cc_er[sim.iCa], sim.cc_cells[sim.iCa], self.Ver, sim.T, p)
        sim.cc_cells[sim.iCa] = (
            sim.cc_cells[sim.iCa] - f_CaATP * (self.er_sa / cells.cell_vol) * p.dt
        )
        sim.cc_er[sim.iCa] = sim.cc_er[sim.iCa] + f_CaATP * (self.er_sa / self.er_vol) * p.dt
        self._observe("serca_commit", sim, sim.iCa, f_CaATP)
        for i in sim.movingIons:
            IdCM = np.ones(sim.cdl)
            f_ED = stb.electroflux(
                sim.cc_cells[i],
                sim.cc_er[i],
                self.Dm_er[i],
                p.tm * IdCM,
                sim.zs[i] * IdCM,
                self.Ver,
                sim.T,
                p,
                rho=1,
            )
            sim.cc_cells[i] = sim.cc_cells[i] - f_ED * (self.er_sa / cells.cell_vol) * p.dt
            sim.cc_er[i] = sim.cc_er[i] + f_ED * (self.er_sa / self.er_vol) * p.dt
            self._observe("er_electroflux_commit", sim, i, f_ED)
        self.get_v(sim, p)
        self._observe("charge_voltage", sim, None, None)

    def channels(self, sim, cells, p):
        cCa_act = (sim.cc_cells[sim.iCa] / p.act_Km_Ca) ** p.act_n_Ca
        cCa_inh = (sim.cc_cells[sim.iCa] / p.inh_Km_Ca) ** p.inh_n_Ca
        Dm_mod_mol = cCa_act / (1 + cCa_act) * (1 / (1 + cCa_inh))
        if sim.molecules is not None or sim.metabo is not None or sim.grn is not None:
            if sim.molecules is not None and "IP3" in sim.molecules.molecules:
                cIP3_act = (sim.molecules.cell_concs["IP3"] / p.act_Km_IP3) ** p.act_n_IP3
            elif sim.metabo is not None and "IP3" in sim.metabo.core.cell_concs:
                cIP3_act = (sim.metabo.core.cell_concs["IP3"] / p.act_Km_IP3) ** p.act_n_IP3
            elif sim.grn is not None and "IP3" in sim.grn.core.cell_concs:
                cIP3_act = (sim.grn.core.cell_concs["IP3"] / p.act_Km_IP3) ** p.act_n_IP3
            else:
                cIP3_act = np.zeros(sim.cdl)
            Dm_mod_mol = cCa_act / (1 + cCa_act) * (1 / (1 + cCa_inh)) * (cIP3_act / (1 + cIP3_act))
        self.Dm_channels[sim.iCa] = p.max_er * Dm_mod_mol
        self.Dm_er = self.Dm_er_base + self.Dm_channels


stb = SimpleNamespace(pumpCaER=_pumpCaER, electroflux=_electroflux)


@dataclass(frozen=True, slots=True)
class OwnedState:
    binding_identity: str
    ion_ids: tuple
    cell_ids: tuple
    fields: object
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    parent: OwnedState
    cytosol_before_mM: object
    cytosol_after_mM: object
    frames: tuple
    arithmetic: object
    raw_candidate: object
    candidate: object
    source_completed: bool
    finite: bool
    failure: object
    amount_change_mol: object
    amount_gross_mol: object


def state(binding_identity, ion_ids, cell_ids, fields):
    fields = ions.data(fields)
    count, n = len(ion_ids), len(cell_ids)
    if set(fields) != set(FIELDS):
        raise ValueError("Require every owned native ER field")
    values = {}
    for key in FIELDS:
        value = np.asarray(fields[key], np.float64)
        shape = (
            ()
            if key == "cm_er"
            else (count, n)
            if key in ("cc_er", "Dm_er", "Dm_er_base", "Dm_channels", "zer")
            else (n,)
        )
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError("Require finite explicitly shaped ER state: " + key)
        if key in ("er_vol", "er_sa", "cm_er") and np.any(value <= 0):
            raise ValueError("Require positive ER geometry/capacitance")
        values[key] = float(value) if key == "cm_er" else ions.freeze(value)
    result = OwnedState(binding_identity, tuple(ion_ids), tuple(cell_ids), ions.freeze(values), "")
    return replace(result, identity=ions.digest(result))


def initialize(
    binding_identity,
    ion_ids,
    cell_ids,
    cell_mol_m3,
    cell_volume_m3,
    cell_area_m2,
    valence,
    capacitance_F_m2,
):
    sim = SimpleNamespace(
        cc_cells=np.array(cell_mol_m3, copy=True),
        cdl=len(cell_ids),
        iCa=ion_ids.index("Ca"),
        zs=np.array(valence, copy=True),
    )
    cells = SimpleNamespace(
        cell_vol=np.array(cell_volume_m3, copy=True), cell_sa=np.array(cell_area_m2, copy=True)
    )
    er = _LiteralEndoRetic(sim, cells, SimpleNamespace(cm=capacitance_F_m2))
    fields = {key: copy.deepcopy(getattr(er, key)) for key in FIELDS if key != "cc_er"}
    fields["cc_er"] = sim.cc_er.copy()
    return state(binding_identity, ion_ids, cell_ids, fields)


def context(raw, n):
    if not isinstance(raw, dict) or set(raw) != {"molecules", "metabo", "grn"}:
        raise ValueError("Require explicit presence and IP3 membership for all three source owners")
    result = {}
    for name, row in raw.items():
        if (
            not isinstance(row, dict)
            or set(row) != {"present", "contains_IP3", "IP3_mM"}
            or type(row["present"]) is not bool
            or type(row["contains_IP3"]) is not bool
        ):
            raise ValueError("Require explicit native owner lookup context")
        if not row["present"] and row["contains_IP3"]:
            raise ValueError("Absent owner cannot contain an IP3 entry")
        values = None
        if row["contains_IP3"]:
            values = np.asarray(row["IP3_mM"], np.float64)
            if values.shape != (n,) or not np.isfinite(values).all():
                raise ValueError("Require explicit finite IP3 cell vector")
            values = ions.freeze(values)
        elif row["IP3_mM"] is not None:
            raise ValueError("Absent IP3 must be declared None")
        result[name] = dict(present=row["present"], contains_IP3=row["contains_IP3"], IP3_mM=values)
    return ions.freeze(result)


def _owners(raw):
    result = {}
    for name, row in raw.items():
        if not row["present"]:
            result[name] = None
            continue
        concentrations = {"IP3": np.array(row["IP3_mM"], copy=True)} if row["contains_IP3"] else {}
        result[name] = (
            SimpleNamespace(
                molecules={"IP3": True} if row["contains_IP3"] else {}, cell_concs=concentrations
            )
            if name == "molecules"
            else SimpleNamespace(core=SimpleNamespace(cell_concs=concentrations))
        )
    return result


def step(
    parent,
    *,
    binding_identity,
    cytosol_mM,
    cell_volume_m3,
    moving_indices,
    valence,
    runtime_temperature_K,
    parameters,
    owner_context,
):
    checked = state(parent.binding_identity, parent.ion_ids, parent.cell_ids, parent.fields)
    if parent.binding_identity != binding_identity or checked.identity != parent.identity:
        raise ValueError("Changed ER state/binding association")
    if any(isinstance(v, np.ndarray) and v.flags.writeable for v in parent.fields.values()):
        raise ValueError("Require immutable owned ER buffers")
    live_context = context(ions.data(owner_context), len(parent.cell_ids))
    sim = SimpleNamespace(
        cc_cells=np.array(cytosol_mM, copy=True),
        cc_er=np.array(parent.fields["cc_er"], copy=True),
        cdl=len(parent.cell_ids),
        iCa=parent.ion_ids.index("Ca"),
        zs=np.array(valence, copy=True),
        movingIons=tuple(moving_indices),
        T=runtime_temperature_K,
        **_owners(live_context),
    )
    cells = SimpleNamespace(cell_vol=np.array(cell_volume_m3, copy=True))
    er = object.__new__(_LiteralEndoRetic)
    for key in FIELDS:
        if key != "cc_er":
            setattr(er, key, copy.deepcopy(parent.fields[key]))
    frames, arithmetic = [], {}

    def raw_fields():
        return {
            key: copy.deepcopy(sim.cc_er if key == "cc_er" else getattr(er, key)) for key in FIELDS
        }

    def observe(stage, actual, index, flux):
        frames.append(
            ions.freeze(
                dict(
                    stage=stage,
                    ion_id=None if index is None else parent.ion_ids[index],
                    cytosol_mM=actual.cc_cells.copy(),
                    fields=raw_fields(),
                    flux_mol_m2_s=None if flux is None else flux.copy(),
                )
            )
        )

    er._observe = observe
    p = SimpleNamespace(
        **parameters,
        _observe=lambda name, value: arithmetic.__setitem__(
            name, ions.freeze(np.array(value, copy=True))
        ),
    )
    observe("initial", sim, None, None)
    completed, failure = True, None
    with np.errstate(all="ignore"):
        try:
            er.update(sim, cells, p)
        except Exception as error:
            import traceback

            completed = False
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
    raw = raw_fields()
    finite = (
        all(np.isfinite(np.asarray(value)).all() for value in raw.values())
        and np.isfinite(sim.cc_cells).all()
        and all(np.isfinite(np.asarray(value)).all() for value in arithmetic.values())
    )
    candidate = (
        state(binding_identity, parent.ion_ids, parent.cell_ids, raw)
        if completed and finite
        else None
    )
    before_cytosol = np.array(cytosol_mM, copy=True)
    vol = np.asarray(cell_volume_m3)
    before_amount = before_cytosol * vol + parent.fields["cc_er"] * parent.fields["er_vol"]
    after_amount = sim.cc_cells * vol + sim.cc_er * er.er_vol
    return Trial(
        parent,
        ions.freeze(before_cytosol),
        ions.freeze(sim.cc_cells),
        tuple(frames),
        ions.freeze(arithmetic),
        ions.freeze(raw),
        candidate,
        completed,
        bool(finite),
        ions.freeze(failure),
        ions.freeze(after_amount - before_amount),
        ions.freeze(
            abs(before_cytosol * vol)
            + abs(parent.fields["cc_er"] * parent.fields["er_vol"])
            + abs(sim.cc_cells * vol)
            + abs(sim.cc_er * er.er_vol)
        ),
    )


def probe_pump(inputs):
    """Expose literal helper returns/refusals separately from owned finite state."""
    arithmetic = {}
    parameters = SimpleNamespace(
        **inputs["parameters"],
        _observe=lambda name, value: arithmetic.__setitem__(
            name, ions.freeze(np.array(value, copy=True))
        ),
    )
    cc_er = np.array(inputs["cER_mM"], np.float64)
    cytosol = np.array(inputs["cytosol_mM"], np.float64)
    voltage = np.array(inputs["voltage_V"], np.float64)
    flux = failure = None
    with np.errstate(all="ignore"):
        try:
            flux = _pumpCaER(cc_er, cytosol, voltage, inputs["runtime_temperature_K"], parameters)
        except Exception as error:
            import traceback

            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
    return ions.freeze(
        dict(
            inputs=inputs,
            arithmetic=arithmetic,
            flux_mol_m2_s=flux,
            cER_after_mM=cc_er,
            cytosol_after_mM=cytosol,
            voltage_after_V=voltage,
            source_completed=failure is None,
            failure=failure,
            finite=failure is None
            and np.isfinite(flux).all()
            and all(np.isfinite(value).all() for value in arithmetic.values()),
        )
    )
