"""Independent 80-digit scalar calcium/finite-pool oracle; standard library only."""

from decimal import Decimal, localcontext
from numbers import Real

R = Decimal("8.31446261815324")
F = Decimal("96485.3321233100184")


def _d(v, *, positive=False, nonnegative=False):
    if isinstance(v, bool) or not isinstance(v, (Real, Decimal)):
        raise ValueError("Require a real numeric scalar")
    v = Decimal(str(v))
    if not v.is_finite() or (positive and v <= 0) or (nonnegative and v < 0):
        raise ValueError("Invalid scalar domain")
    return v


def rates(
    source,
    destination,
    voltage,
    amount,
    volume,
    temperature,
    delta_1M,
    capacity,
    km_ca,
    km_atp,
    availability,
    *,
    kind,
):
    with localcontext() as context:
        context.prec = 80
        if kind not in ("pmca", "er") or len(amount) != 3:
            raise ValueError("Require declared pump kind and ATP/ADP/Pi order")
        ci, co, v = _d(source, positive=True), _d(destination, positive=True), _d(voltage)
        t, vol = _d(temperature, positive=True), _d(volume, positive=True)
        if not 200 <= t <= 400 or abs(v) > Decimal("0.15"):
            raise ValueError("Temperature/voltage outside component domain")
        n = [_d(a, positive=True) for a in amount]
        atp, adp, pi = [a / vol for a in n]
        d = _d(delta_1M)
        cap, kc, ka, a = (
            _d(capacity, nonnegative=True),
            _d(km_ca, positive=True),
            _d(km_atp, positive=True),
            _d(availability, nonnegative=True),
        )
        if a > 1:
            raise ValueError("Invalid availability")
        rt = R * t
        drive = d + rt * (adp * pi / (1000 * atp)).ln()
        transport = rt * (co / ci).ln() + 2 * F * (v if kind == "er" else -v)
        reaction = drive + transport
        if abs(reaction / rt) > 80:
            raise ValueError("Affinity outside numeric domain")
        saturation = ci / (kc + ci) * atp / (ka + atp)
        cycles = cap * a * saturation * (1 - (reaction / rt).exp())
        mu = [-d + rt * (atp / 1000).ln(), rt * (adp / 1000).ln(), rt * (pi / 1000).ln()]
        values = dict(
            cycles_fmol_s=cycles,
            reaction_free_energy_J_mol=reaction,
            hydrolysis_free_energy_J_mol=drive,
            transport_free_energy_J_mol=transport,
            dissipated_power_pJ_s=-cycles * reaction / 1000,
            pool_chemical_power_pJ_s=cycles * drive / 1000,
            transport_power_pJ_s=cycles * transport / 1000,
            legacy_delta_g0_J_mol=d - rt * Decimal(1000).ln(),
            free_energy_pJ=sum(ni * (u - rt) for ni, u in zip(n, mu, strict=True)) / 1000,
        )
        return {k: float(v) for k, v in values.items()}


def exchange(cycles, owners, owner_count):
    """One Ca transfer and one signed ATP reaction per declared route, once."""
    with localcontext() as context:
        context.prec = 80
        totals = [Decimal(0) for _ in range(owner_count)]
        calcium = []
        for value, owner in zip(cycles, owners, strict=True):
            if type(owner) is not int or not 0 <= owner < owner_count:
                raise ValueError("Invalid owner")
            j = _d(value)
            totals[owner] += j
            calcium.append([-float(j), float(j)])
        return dict(
            amount_fmol_s=[[float(s * j) for j in totals] for s in (-1, 1, 1)],
            calcium_source_destination_fmol_s=calcium,
            signed_hydrolysis_fmol_s=[float(j) for j in totals],
        )


def manufactured_path(steps, depletion_seconds, recovery_seconds):
    """Independent extent integration for the documented equal-Ca manufactured path.

    For delta1M=RT ln1000, V=0, Ca=KmCa=volume=1, ATP+ADP=1,
    ADP=Pi, the source law reduces to .05*(A-(1-A)^2)/(.5+A).
    Recovery blocks the pump and supplies RT ln16 at capacity .05, so
    dA/dt=.05*(16*(1-A)^2-A)/(16*(1-A)^2+A). No production helpers.
    """
    if type(steps) is not int or steps <= 0:
        raise ValueError("Require a positive integer step count")
    with localcontext() as context:
        context.prec = 80
        a = Decimal("0.8")
        outputs = []
        for phase, seconds in enumerate((depletion_seconds, recovery_seconds)):
            h = _d(seconds, positive=True) / steps

            def derivative(atp, phase=phase):
                product = (1 - atp) ** 2
                if phase == 0:
                    return -Decimal("0.05") * (atp - product) / (Decimal("0.5") + atp)
                return Decimal("0.05") * (16 * product - atp) / (16 * product + atp)

            for _ in range(steps):
                k1 = derivative(a)
                k2 = derivative(a + h * k1 / 2)
                k3 = derivative(a + h * k2 / 2)
                k4 = derivative(a + h * k3)
                a += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            outputs.append(float(a))
        return outputs
