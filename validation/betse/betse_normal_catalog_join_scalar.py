"""Authenticated existing independent equations with explicit precision context.

Only function names and the pre-existing 80-digit context parameter change.
"""

from decimal import Decimal, localcontext


def kv1_kinetics(voltage, family, *, precision=90):
    with localcontext() as context:
        context.prec = precision
        v = Decimal(str(voltage)) * 1000

        def sigmoid(midpoint, slope):
            return 1 / (1 + ((v - Decimal(midpoint)) / Decimal(slope)).exp())

        if family == 1:
            target = (sigmoid("-30.5", "-11.3943"), sigmoid("-30", "27.3943"))
            tau = (30 * sigmoid("-76.56", "26.1479"), 15000 * sigmoid("-160.56", "-100"))
        elif family == 2:
            target = (sigmoid("-21", "-11.3943"), sigmoid("-22", "11.3943"))
            tau = (150 * sigmoid("-67.56", "34.1479"), 15000 * sigmoid("-46.56", "-44.1479"))
        elif family == 3:
            target = (sigmoid("-14.1", "-10.3"), sigmoid("-33", "3.7"))
            tau = (
                Decimal("19.16") - Decimal("0.284") * v,
                Decimal("1162.4") - Decimal("13.76") * v,
            )
        elif family == 4:
            target = (sigmoid("-21.7", "-16.9"), sigmoid("-73.6", "12.8"))
            tau = (Decimal(3), Decimal(119))
        elif family == 5:
            target = (sigmoid("-6", "-6.4"), sigmoid("-25.3", "3.5"))
            tau = (Decimal("8.33") - Decimal("0.1163") * v, Decimal(1620) - Decimal("15.5") * v)
        elif family == 6:
            target = (sigmoid("-20.8", "-8.1"), sigmoid("-22", "11.39"))
            tau = (30 * sigmoid("-46.56", "44.14"), 5000 * sigmoid("-46.56", "-44.14"))
        else:
            raise ValueError("Unsupported Kv1 family")
        return (target, tuple((value / 1000 for value in tau)))


def hcn_kinetics(voltage, family, *, precision=90):
    with localcontext() as context:
        context.prec = precision
        v = Decimal(str(voltage)) * 1000
        midpoint, slope, tau, shift = {
            1: ("-94", "8.1", "30", "0"),
            2: ("-99", "6.2", "184", "-10"),
            4: ("-100", "9.6", "461", "-10"),
        }[family]
        argument = (v + Decimal(shift) - Decimal(midpoint)) / Decimal(slope)
        return ((1 / (1 + argument.exp()), Decimal(1)), (Decimal(tau) / 1000, Decimal("0.001")))


def cav_kinetics(voltage, family, *, precision=90):
    with localcontext() as context:
        context.prec = precision
        v = Decimal(str(voltage)) * 1000
        D = Decimal

        def sigmoid(midpoint, slope):
            return 1 / (1 + ((v - D(midpoint)) / D(slope)).exp())

        if family in ("Cav1p2", "Cav1p3"):
            if family == "Cav1p2":
                v -= 10
            target = (sigmoid("-30", "-6"), sigmoid("-80", "6.4"))
            tau = (5 + 20 * sigmoid("-25", "5"), 20 + 50 * sigmoid("-40", "7"))
        elif family == "Cav2p1":
            a, b = (D("8.5") * sigmoid("8", "-12.5"), 35 * sigmoid("-74", "14.5"))
            target, tau = ((a / (a + b), D(1)), (1 / (a + b), D(1)))
        elif family == "Cav2p2":
            delta = v - 20
            a = D(1) if delta == 0 else D("0.1") * delta / (1 - (-delta / 10).exp())
            b = D("0.4") * (-(v + 25) / 18).exp()
            c = D("0.01") * (-(v + 50) / 10).exp()
            d = D("0.1") * sigmoid("-17", "-17")
            target, tau = ((a / (a + b), c / (c + d)), (1 / (a + b), 1 / (c + d)))
        elif family == "Cav2p3":
            a, b = (D("2.6") * sigmoid("-7", "-8"), D("0.18") * sigmoid("-26", "4"))
            c, d = (D("0.0025") * sigmoid("-32", "8"), D("0.19") * sigmoid("-42", "-10"))
            target, tau = ((a / (a + b), c / (c + d)), (1 / (a + b), 1 / (c + d)))
        elif family == "Cav3p1":
            target = (sigmoid("-42.921064", "-5.163208"), sigmoid("-72.907420", "4.575763"))
            tm = (
                D(1)
                if v >= D("-0.01")
                else D("-0.855809") + D("1.493527") * (-v / D("27.414182")).exp()
            )
            tau = (tm, D("9.987873") + D("0.002883") * (-v / D("5.598574")).exp())
        elif family == "Cav3p3":
            target = (sigmoid("-45.454426", "-5.073015"), sigmoid("-74.031965", "8.416382"))
            tau = (
                D("3.394938") + D("54.187616") * sigmoid("-40.040397", "4.110392"),
                D("109.701136") + D("0.003816") * (-v / D("4.781719")).exp(),
            )
        else:
            raise ValueError("Unsupported independent CaV law")
        return (target, tuple((t / 1000 for t in tau)))
