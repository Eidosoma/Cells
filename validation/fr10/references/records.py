"""R-records: the dose, the bath's free-energy change and the step's charge at each event
(Appendix A.4 and §2.2), and the reservoir-work reconciliation K(t) (A.5 and §2.3).

**The bath (A.1).** A held bath b has a declared volume V_b (pL) and declared composition c^0
(mM). Its composition is piecewise constant, c^e from the e-th event on (right-continuous). The
inputs give each event's composition absolutely, so every epoch's c^e is read, never accumulated.

**The dose (A.4).** At an event that changes the composition from c to c',
dn_s = V_b (c'_s - c_s) fmol, computed in exact rationals from the inputs' doubles.

**The free-energy change (§2.2).** The bath's content n_s = V_b c_s at its declared volume has the
ideal free energy G = 1e-3 RT sum_s n_s (ln(n_s/V_b) - 1) pJ (RT in J/mol, ln of the mM number,
so the standard state is 1 mM). With a_s the content before the event,

    dG_b = 1e-3 RT sum_s [dn_s (ln(a_s/V_b) - 1) + (a_s + dn_s) log1p(dn_s/a_s)]
         = G(a + dn) - G(a).

It is evaluated per species (never as the difference of the two endpoint sums, which cancels
against the 150 mM ions) in 50-digit decimal arithmetic. The second evaluation is the same
expression in float64; their difference is the floor.

**The step's charge (A.4).** q = F 1e-15 sum_s z_s dn_s (C). It is exactly zero for a neutral
step; it is computed in rationals, so a neutral step gives 0.0 exactly.

**K (A.5, §2.3).** With mu_s^e = RT ln c_s^e + z_s F phi_b the bath's potential in epoch e and
S_s(t) the cumulative supply (fmol, positive out of the bath into the tissue),
W_res(t) = 1e-3 sum_e sum_s mu_s^e dS_s^e, and K = W_res - 1e-3 sum_s mu_s^0 S_s, so

    K(t) = 1e-3 sum_{e >= 1, t_e <= t} sum_s (mu_s^e - mu_s^0) (S_s(min(t, t_{e+1})) - S_s(t_e)).

The electrical parts z F phi_b cancel in mu^e - mu^0 = RT ln(c^e/c^0), so phi_b never enters. K
needs S at every event time, so every event time must be one of the record times (to 1e-12 s);
otherwise the call is refused, never interpolated. The primary evaluation is this epoch sum in
50-digit decimals from the supplied doubles. The second is the operator's own form (§2.3),
K = B + 1e-3 sum_s (mu_s^now - mu_s^0) S_s with B <- B + 1e-3 sum_s (mu_s^old - mu_s^new) S_s(t_e)
at each event, in float64; their difference is the floor.

**What K's reference can and cannot catch.** Given the engine's own S, it checks the
reconciliation's arithmetic: a dropped, sign-flipped or mis-epoched term. It has no power against
a wrong S. A K computed from the reference trajectories' supply (``faces`` and ``ion``) does.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import pairwise

import numpy as np

from .common import DIGITS, Constants, constants_from_block, dec, exact

EVENT_TIME_ATOL_S = 1e-12


def valences(world: dict) -> dict:
    """The world's valences, under ``valence`` (R_records) or ``species`` (R_ion)."""
    v = world.get("valence", world.get("species"))
    if not isinstance(v, dict):
        raise ValueError("world declares no valences ('valence' or 'species')")
    out = {}
    for s, z in v.items():
        if int(z) != z:
            raise ValueError(f"valence of {s} is not an integer: {z!r}")
        out[s] = int(z)
    return out


def bath_epochs(bath: dict) -> list:
    """[(t_start, {species: c (Fraction, mM)})], epoch 0 being the declared composition at t = 0.

    Refused: an event at or before t = 0, times that do not increase strictly, a composition
    whose species differ from the declared ones, and any concentration that is not positive
    (D150's trace rule).
    """
    declared = {s: exact(c) for s, c in bath["declared_mM"].items()}
    epochs = [(Fraction(0), declared)]
    for ev in bath.get("events", []):
        t = exact(ev["time_s"])
        if t <= epochs[-1][0]:
            raise ValueError(f"event at {float(t)} s does not follow {float(epochs[-1][0])} s")
        comp = {s: exact(c) for s, c in ev["concentration_mM"].items()}
        if set(comp) != set(declared):
            raise ValueError(f"event at {float(t)} s names species {sorted(comp)}, "
                             f"declared {sorted(declared)}")
        epochs.append((t, comp))
    for t, comp in epochs:
        for s, c in comp.items():
            if c <= 0:
                raise ValueError(f"{s} at {float(t)} s is not positive ({float(c)} mM)")
    return epochs


def _baths(world: dict) -> dict:
    if "baths" in world:
        return world["baths"]
    if "bath" in world:
        return {"bath": world["bath"]}
    raise ValueError("world declares no bath")


def delta_G_exact(before: dict, after: dict, V_b: Fraction, RT: Fraction) -> Decimal:
    """§2.2's dG_b (pJ) in 50-digit decimals, per species."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        total = Decimal(0)
        for s in sorted(before):
            dn = V_b * (after[s] - before[s])
            if dn == 0:
                continue
            ln_c = dec(before[s]).ln()
            ln_ratio = dec(after[s] / before[s]).ln()
            total += dec(dn) * (ln_c - 1) + dec(V_b * after[s]) * ln_ratio
        return dec(RT) * total / 1000


def delta_G_float(before: dict, after: dict, V_b: float, RT: float) -> float:
    """§2.2's expression evaluated literally in float64 (the second evaluation)."""
    total = 0.0
    for s in sorted(before):
        a = V_b * float(before[s])
        dn = V_b * float(after[s]) - a
        if dn == 0.0:
            continue
        total += dn * (np.log(a / V_b) - 1.0) + (a + dn) * np.log1p(dn / a)
    return 1e-3 * RT * total


def content_free_energy_exact(comp: dict, V_b: Fraction, RT: Fraction) -> Decimal:
    """G = 1e-3 RT sum_s n_s (ln(n_s/V_b) - 1) (pJ) of a content n = V_b c, in decimals."""
    with localcontext() as ctx:
        ctx.prec = DIGITS
        total = Decimal(0)
        for s in sorted(comp):
            n = V_b * comp[s]
            total += dec(n) * (dec(comp[s]).ln() - 1)
        return dec(RT) * total / 1000


def event_records(world: dict, constants=None) -> list:
    """Every event's records, bath by bath and in time order.

    ``world`` is one of R_records' worlds (``temperature_K``, ``valence``, ``baths``); an R_ion
    block also works. Each item holds ``bath``, ``time_s``, ``dose_fmol`` {species: float},
    ``dG_b_pJ``, ``charge_C``, the exact ``dose_exact`` (str fractions), the cumulative dose and
    dG_b, and ``floor`` (the float64 evaluation's difference for dG_b; half an ulp for the
    rounded rationals).
    """
    const = constants if isinstance(constants, Constants) else constants_from_block(constants)
    T = world.get("temperature_K")
    if T is None:
        raise ValueError("world declares no temperature_K")
    RT = const.RT(T)
    z = valences(world)
    F = const.faraday
    out = []
    for name, bath in _baths(world).items():
        V_b = exact(bath["volume_pL"])
        epochs = bath_epochs(bath)
        missing = set(epochs[0][1]) - set(z)
        if missing:
            raise ValueError(f"no valence for {sorted(missing)}")
        dG_cum = Decimal(0)
        for (_, before), (t_e, after) in pairwise(epochs):
            dose = {s: V_b * (after[s] - before[s]) for s in sorted(before)}
            dG = delta_G_exact(before, after, V_b, RT)
            dG_f = delta_G_float(before, after, float(V_b), float(RT))
            charge = F * sum(z[s] * dose[s] for s in dose) / 10 ** 15
            with localcontext() as ctx:
                ctx.prec = DIGITS
                dG_cum = dG_cum + dG
                G_end = content_free_energy_exact(after, V_b, RT) - \
                    content_free_energy_exact(epochs[0][1], V_b, RT)
            out.append({
                "bath": name,
                "time_s": float(t_e),
                "dose_fmol": {s: float(v) for s, v in dose.items()},
                "dose_exact": {s: str(v) for s, v in dose.items()},
                "dG_b_pJ": float(dG),
                "charge_C": float(charge),
                "charge_exact": str(charge),
                "neutral": charge == 0,
                "cumulative_dose_fmol": {s: float(V_b * (after[s] - epochs[0][1][s]))
                                         for s in dose},
                "cumulative_dG_b_pJ": float(dG_cum),
                "endpoint_dG_b_pJ": float(G_end),
                "floor": {
                    "dG_b_pJ": abs(float(dG) - dG_f) + 0.5 * np.spacing(abs(float(dG))),
                    "dose_fmol": {s: 0.5 * float(np.spacing(abs(float(v)))) for s, v in
                                  dose.items()},
                    "charge_C": 0.5 * float(np.spacing(abs(float(charge)))),
                },
            })
    return out


def _supply_table(supply, species, T: int) -> dict:
    if isinstance(supply, dict):
        table = {s: np.asarray(v, dtype=np.float64) for s, v in supply.items()}
    else:
        arr = np.asarray(supply, dtype=np.float64)
        if species is None:
            raise ValueError("an array supply needs its species order")
        if arr.ndim != 2 or arr.shape[1] != len(species):
            raise ValueError("supply must be [time, species] in the given species order")
        table = {s: arr[:, i] for i, s in enumerate(species)}
    for s, v in table.items():
        if v.shape != (T,):
            raise ValueError(f"supply of {s} has shape {v.shape}, expected ({T},)")
        if not np.all(np.isfinite(v)):
            raise ValueError(f"supply of {s} is not finite")
    return table


def event_rows(times, epochs) -> list:
    """The record index of each event time (to EVENT_TIME_ATOL_S); refused when one is absent."""
    times = np.asarray(times, dtype=np.float64)
    if np.any(np.diff(times) < 0):
        raise ValueError("record times must not decrease")
    rows = []
    for t_e, _ in epochs[1:]:
        hit = np.flatnonzero(np.abs(times - float(t_e)) <= EVENT_TIME_ATOL_S)
        if hit.size == 0:
            raise ValueError(f"event time {float(t_e)} s is not among the record times; "
                             "K needs the supply at every event time")
        rows.append(int(hit[0]))
    return rows


def reconciliation_K(world: dict, record_times_s, supply_fmol, constants=None, bath=None,
                     species=None) -> dict:
    """A.5's K(t) (pJ) at every record time, from the cumulative supply at those times.

    ``supply_fmol`` is {species: [T]} or an array [T, S] with ``species`` naming its columns;
    species absent from it have no supply (they contribute nothing). Returns ``times_s``,
    ``K_pJ``, ``floor_pJ`` (decimal epoch sum against the float64 B form), ``event_rows`` and
    ``delta_mu_J_per_mol`` per epoch.
    """
    const = constants if isinstance(constants, Constants) else constants_from_block(constants)
    RT = const.RT(world["temperature_K"])
    baths = _baths(world)
    if bath is None:
        if len(baths) != 1:
            raise ValueError("name the bath: the world has several")
        bath = next(iter(baths))
    epochs = bath_epochs(baths[bath])
    times = np.asarray(record_times_s, dtype=np.float64)
    T = times.size
    table = _supply_table(supply_fmol, species, T)
    unknown = set(table) - set(epochs[0][1])
    if unknown:
        raise ValueError(f"supply names species the bath does not declare: {sorted(unknown)}")
    rows = event_rows(times, epochs)
    c0 = epochs[0][1]
    with localcontext() as ctx:
        ctx.prec = DIGITS
        dmu = [{s: dec(RT) * dec(comp[s] / c0[s]).ln() for s in table}
               for _, comp in epochs]
        S_dec = {s: [dec(exact(x)) for x in v] for s, v in table.items()}
        K = []
        for k in range(T):
            total = Decimal(0)
            for e in range(1, len(epochs)):
                start = rows[e - 1]
                if start > k:
                    break
                end = k if e == len(epochs) - 1 else min(k, rows[e])
                for s in table:
                    total += dmu[e][s] * (S_dec[s][end] - S_dec[s][start])
            K.append(total / 1000)
    K_exact = np.array([float(x) for x in K])
    # The operator's form, in float64.
    dmu_f = [{s: float(d[s]) for s in table} for d in dmu]
    B = 0.0
    epoch = 0
    K_float = np.empty(T)
    for k in range(T):
        while epoch + 1 < len(epochs) and rows[epoch] == k:
            B += 1e-3 * sum((dmu_f[epoch][s] - dmu_f[epoch + 1][s]) * table[s][k] for s in table)
            epoch += 1
        K_float[k] = B + 1e-3 * sum(dmu_f[epoch][s] * table[s][k] for s in table)
    floor = np.abs(K_exact - K_float) + 0.5 * np.spacing(np.abs(K_exact))
    return {
        "times_s": times,
        "K_pJ": K_exact,
        "floor_pJ": floor,
        "K_float64_pJ": K_float,
        "event_rows": rows,
        "delta_mu_J_per_mol": [{s: float(d[s]) for s in table} for d in dmu],
    }


def records_summary(inputs: dict) -> dict:
    """Every event's records for each of R_records' worlds."""
    const = constants_from_block(inputs.get("constants"))
    return {name: event_records(w, const) for name, w in inputs["R_records"]["worlds"].items()}
