"""Independent temperature/standard-state algebra and existing scalar gate laws.

No Cells, JAX or BETSE imports. Native constants and SI-matched constants remain
different inputs. Finite raw probes, source failures and proposed policies are
kept separate; no new coupled physics is executed here.
"""

from decimal import Decimal, localcontext

from validation.channels import (
    calcium_catalog_extra_reference as extra_ca,
)
from validation.channels import (
    hcn_extra_reference as extra_hcn,
)
from validation.channels import (
    leak_channels_reference as leak,
)
from validation.channels import (
    morris_lecar_channels_reference as ml,
)
from validation.channels import (
    potassium_catalog_reference as extra_k,
)
from validation.channels import (
    sodium_catalog_reference as extra_na,
)
from validation.tissue import cav_reference as cav
from validation.tissue import hcn_reference as hcn
from validation.tissue import kir_reference as kir
from validation.tissue import kv1_reference as kv1
from validation.tissue import sodium_reference as sodium


def d(value):
    return Decimal(str(float(value)))


def channel_kinetics(name, voltage):
    if name in ml.CLASSES:
        values = ml.kinetics(voltage, name)
        return [values["target"]], [values["tau_s"]]
    if name.startswith("Kv1p"):
        target, tau = kv1.kinetics(voltage, int(name[-1]))
    elif name == "Kir2p1":
        target, tau = kir.kinetics(voltage)
    elif name == "Nav1p2":
        target, tau = sodium.kinetics(voltage)
    elif name in extra_na.CLASSES:
        values = extra_na.kinetics(voltage, name)
        target, tau = values["target"], values["tau_s"]
    elif name in extra_k.CLASSES:
        values = extra_k.kinetics(voltage, name)
        target, tau = values["target"], values["tau_s"]
    elif name in cav.LAWS.values():
        target, tau = cav.kinetics(voltage, name)
    elif name in extra_ca.CLASSES:
        values = extra_ca.kinetics(voltage, name)
        target, tau = values["target"], values["tau_s"]
    elif name in ("HCN1", "HCN2", "HCN4"):
        target, tau = hcn.kinetics(voltage, int(name[-1]))
    elif name in extra_hcn.CLASSES:
        target, tau = extra_hcn.kinetics(voltage, name)
    elif name in leak.CLASSES:
        values = leak.kinetics(voltage, name)
        target, tau = values["target"], values["tau_s"]
    else:
        raise ValueError("Unmapped independent catalog class: " + name)
    return [float(value) for value in target], [float(value) for value in tau]


def channel_step(name, voltage, dt_s, initial=(0.23, 0.68)):
    target, tau = channel_kinetics(name, voltage)
    if name in ml.CLASSES:
        state = [ml.native_update(initial[0], voltage, name, dt_s)]
        opened = ml.opening(state[0] if name in ml.KINETIC else 0.0, voltage, name)
        return dict(target=target, tau_s=tau, gates=state, opening=opened)
    with localcontext() as precision:
        precision.prec = 80
        state = [
            float((d(t) * d(g) + d(dt_s) * d(a)) / (d(t) + d(dt_s)))
            for t, g, a in zip(tau, initial, target, strict=True)
        ]
    if name.startswith("Kv1p"):
        opened = float(kv1.opening(state, int(name[-1])))
    elif name == "Kir2p1":
        opened = float(kir.opening(state))
    elif name == "Nav1p2":
        opened = float(sodium.opening(state))
    elif name in extra_na.CLASSES:
        opened = extra_na.opening(state, name)
    elif name in extra_k.CLASSES:
        opened = extra_k.opening(state, name)
    elif name in cav.LAWS.values():
        opened = float(cav.opening(state, name))
    elif name in extra_ca.CLASSES:
        opened = extra_ca.opening(state, name)
    elif name in ("HCN1", "HCN2", "HCN4"):
        opened = float(hcn.opening(state))
    elif name in extra_hcn.CLASSES:
        opened = extra_hcn.opening(state, name)
    else:
        opened = leak.opening(state, name)
    return dict(target=target, tau_s=tau, gates=state, opening=float(opened))


def electroflux(ca, cb, diffusion, length, z, voltage, temperature, constants):
    with localcontext() as precision:
        precision.prec = 100
        ca, cb, diffusion, length, z, v, t = map(
            d, (ca, cb, diffusion, length, z, voltage, temperature)
        )
        f, r = d(constants["F"]), d(constants["R"])
        # Retain the native input nonce, separately from physical regularization.
        x = (z + Decimal("1e-25")) * (v + Decimal("1e-25")) * f / (r * t)
        return float(-diffusion / length * x * (cb - ca * (-x).exp()) / (1 - (-x).exp()))


def transport(row):
    constants = row["constants"]
    t = d(row["temperature_K"])
    values = row["electroflux"]
    flux = [
        electroflux(*items, row["temperature_K"], constants)
        for items in zip(
            values["cA"],
            values["cB"],
            values["D"],
            values["d"],
            values["z"],
            values["voltage_V"],
            strict=True,
        )
    ]
    with localcontext() as precision:
        precision.prec = 80
        q, kb = d(constants["q"]), d(constants["kb"])
        alpha = Decimal("1e-9") * q / (kb * t)
        planar = [
            -Decimal("1e-9") * Decimal("1e5")
            - alpha * 100 * 100
            + Decimal("1e-6") * 100
            - Decimal("1e-8") * 100 * 100,
            -Decimal("1e-9") * Decimal("-5e4")
            - alpha * (-200) * 100
            + Decimal("-2e-6") * 100
            - Decimal("1e-8") * 100 * (-200),
        ]
        vector = -Decimal("1e-9") * Decimal("1e5") - alpha * 100 * 100 + Decimal("1e-6") * 100
        special = [
            -Decimal("1e-9") * Decimal("1e5") - alpha * 100 * 100 + Decimal("1e-6") * 100,
            -Decimal("2e-9") * Decimal("-5e4") - 2 * alpha * (-200) * 80 + Decimal("-2e-6") * 80,
        ]
        conductivity = (
            Decimal("1e-9")
            * q
            * d(constants["F"])
            * 100
            / (Decimal("1e-6") * kb * d(row["configured_temperature_K"]))
        )
        physical = (
            Decimal("1e-9")
            * d(constants["F"]) ** 2
            * 100
            / (Decimal("1e-6") * d(constants["R"]) * d(row["configured_temperature_K"]))
        )
    return dict(
        electroflux=flux,
        planar=[float(v) for v in planar],
        vector=float(vector),
        special=[float(v) for v in special],
        conductivity=float(conductivity),
        conductivity_FR_physical=float(physical),
        mixed_constant_relative_difference=float(conductivity / physical - 1),
    )


def pumps(row):
    p = row["parameters"]
    with localcontext() as precision:
        precision.prec = 100
        r, f, t = d(p["R"]), d(p["F"]), d(row["temperature_K"])
        atp, adp, pi = (d(p[key]) for key in ("cATP", "cADP", "cPi"))
        dg_na, dg_ca = d(row["nak_delta_g0_J_mol"]), d(p["deltaGATP"])
        na, k, third, ca, er = [], [], [], [], []
        for voltage in row["voltage_V"]:
            v = d(voltage)
            quotient = adp * pi / (1000 * atp) * (Decimal(145) / 12) ** 3 * (Decimal(140) / 4) ** 2
            ratio = quotient * (dg_na / (r * t) - f * v / (r * t)).exp()
            saturation = (Decimal(12) / d(p["KmNK_Na"])) ** 3 / (
                1 + (Decimal(12) / d(p["KmNK_Na"])) ** 3
            )
            saturation *= (Decimal(4) / d(p["KmNK_K"])) ** 2 / (
                1 + (Decimal(4) / d(p["KmNK_K"])) ** 2
            )
            saturation *= atp / (d(p["KmNK_ATP"]) + atp)
            cycle = d(row["block_fraction"]) * d(p["alpha_NaK"]) * saturation * (1 - ratio)
            na.append(float(-3 * cycle))
            k.append(float(2 * cycle))
            third.append(float(3 * cycle))
            quotient = adp * pi * 2 / (atp * Decimal(".0002"))
            ratio = quotient * (dg_ca / (r * t) - 2 * f * v / (r * t)).exp()
            saturation = (
                Decimal(".0002")
                / (d(p["KmCa_Ca"]) + Decimal(".0002"))
                * atp
                / (d(p["KmCa_ATP"]) + atp)
            )
            # The captured native PMCA body accepts block but does not use it.
            ca.append(float(-d(p["alpha_Ca"]) * saturation * (1 - ratio)))
            quotient = adp * pi * Decimal(".3") / (atp * Decimal(".0002"))
            ratio = quotient * (dg_ca / (r * t) + 2 * f * v / (r * t)).exp()
            er.append(float(d(p["serca_max"]) * saturation * (1 - ratio)))
        literal_hydrolysis = dg_ca + r * t * (adp * pi / atp).ln()
        shared_pool = dg_na + r * t * (adp * pi / (1000 * atp)).ln()
        return dict(
            nak=[na, k, third],
            pmca=ca,
            serca=er,
            calcium_vs_1M_pool_standard_difference_J_mol=float(literal_hydrolysis - shared_pool),
            RT_log_1000_J_mol=float(r * t * Decimal(1000).ln()),
        )


def legacy_opening(voltage, calcium, temperature, constants):
    with localcontext() as precision:
        precision.prec = 100
        v, c, t = map(d, (voltage, calcium, temperature))
        f, r = d(constants["F"]), d(constants["R"])
        ratio = (1 + Decimal("1e6") * c / Decimal("10.22")) / (
            1 + Decimal("1e6") * c / Decimal(".89")
        )
        return float(1 / (1 + 6182 * ratio**4 * (-Decimal("1.64") * f * v / (r * t)).exp()))


def reaction_equilibrium(delta_g0_J_mol, temperature_K, R):
    with localcontext() as precision:
        precision.prec = 100
        return float((-d(delta_g0_J_mol) / (d(R) * d(temperature_K))).exp())
