"""Independent 80-digit CaV source equations in millivolts/milliseconds.

No Cells/JAX imports. CaV2.2 includes the analytic removable-zero limit;
CaV3.1 retains the literal source branch at -0.01 mV.
"""

from decimal import Decimal, localcontext

LAWS = {
    "betse_cav1p2_m2h@1": "Cav1p2",
    "betse_cav1p3_m2h@1": "Cav1p3",
    "betse_cav2p1_m@1": "Cav2p1",
    "betse_cav2p2_m2h_regularized@1": "Cav2p2",
    "betse_cav2p3_mh@1": "Cav2p3",
    "betse_cav3p1_mh_source_branch@1": "Cav3p1",
    "betse_cav3p3_mh@1": "Cav3p3",
}
POWERS = {
    name: (2, 1)
    if name in ("Cav1p2", "Cav1p3", "Cav2p2")
    else (1, 0)
    if name == "Cav2p1"
    else (1, 1)
    for name in LAWS.values()
}


def kinetics(voltage, family):
    with localcontext() as context:
        context.prec = 80
        v = Decimal(str(voltage)) * 1000
        D = Decimal

        def sigmoid(midpoint, slope):
            return 1 / (1 + ((v - D(midpoint)) / D(slope)).exp())

        if family in ("Cav1p2", "Cav1p3"):
            if family == "Cav1p2":
                v -= 10
            target = sigmoid("-30", "-6"), sigmoid("-80", "6.4")
            tau = 5 + 20 * sigmoid("-25", "5"), 20 + 50 * sigmoid("-40", "7")
        elif family == "Cav2p1":
            a, b = D("8.5") * sigmoid("8", "-12.5"), 35 * sigmoid("-74", "14.5")
            target, tau = (a / (a + b), D(1)), (1 / (a + b), D(1))
        elif family == "Cav2p2":
            delta = v - 20
            a = D(1) if delta == 0 else D("0.1") * delta / (1 - (-delta / 10).exp())
            b = D("0.4") * (-(v + 25) / 18).exp()
            c = D("0.01") * (-(v + 50) / 10).exp()
            d = D("0.1") * sigmoid("-17", "-17")
            target, tau = (a / (a + b), c / (c + d)), (1 / (a + b), 1 / (c + d))
        elif family == "Cav2p3":
            a, b = D("2.6") * sigmoid("-7", "-8"), D("0.18") * sigmoid("-26", "4")
            c, d = D("0.0025") * sigmoid("-32", "8"), D("0.19") * sigmoid("-42", "-10")
            target, tau = (a / (a + b), c / (c + d)), (1 / (a + b), 1 / (c + d))
        elif family == "Cav3p1":
            target = sigmoid("-42.921064", "-5.163208"), sigmoid("-72.907420", "4.575763")
            tm = (
                D(1)
                if v >= D("-0.01")
                else D("-0.855809") + D("1.493527") * (-v / D("27.414182")).exp()
            )
            tau = tm, D("9.987873") + D("0.002883") * (-v / D("5.598574")).exp()
        elif family == "Cav3p3":
            target = sigmoid("-45.454426", "-5.073015"), sigmoid("-74.031965", "8.416382")
            tau = (
                D("3.394938") + D("54.187616") * sigmoid("-40.040397", "4.110392"),
                D("109.701136") + D("0.003816") * (-v / D("4.781719")).exp(),
            )
        else:
            raise ValueError("Unsupported independent CaV law")
        return target, tuple(t / 1000 for t in tau)


def opening(gates, family):
    with localcontext() as context:
        context.prec = 80
        m, h = (Decimal(str(v)) for v in gates)
        a, b = POWERS[family]
        return m**a * (h**b if b else 1)
