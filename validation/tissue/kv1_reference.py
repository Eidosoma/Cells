"""Independent Decimal Kv1 equations in BETSE's millivolts and milliseconds.

No Cells/JAX imports. Source gate powers and equations are evaluated at 80
decimal digits; native initialization and its discrete clock are checked
separately by executing the unchanged pinned implementation.
"""

from decimal import Decimal, localcontext

LAWS = {f"betse_kv1p{i}_mh{'2' if i == 1 else ''}@1": i for i in range(1, 7)}


def kinetics(voltage, family):
    with localcontext() as context:
        context.prec = 80
        v = Decimal(str(voltage)) * 1000

        def sigmoid(midpoint, slope):
            return 1 / (1 + ((v - Decimal(midpoint)) / Decimal(slope)).exp())

        if family == 1:
            target = sigmoid("-30.5", "-11.3943"), sigmoid("-30", "27.3943")
            tau = 30 * sigmoid("-76.56", "26.1479"), 15000 * sigmoid("-160.56", "-100")
        elif family == 2:
            target = sigmoid("-21", "-11.3943"), sigmoid("-22", "11.3943")
            tau = 150 * sigmoid("-67.56", "34.1479"), 15000 * sigmoid("-46.56", "-44.1479")
        elif family == 3:
            target = sigmoid("-14.1", "-10.3"), sigmoid("-33", "3.7")
            tau = Decimal("19.16") - Decimal("0.284") * v, Decimal("1162.4") - Decimal("13.76") * v
        elif family == 4:
            target = sigmoid("-21.7", "-16.9"), sigmoid("-73.6", "12.8")
            tau = Decimal(3), Decimal(119)
        elif family == 5:
            target = sigmoid("-6", "-6.4"), sigmoid("-25.3", "3.5")
            tau = Decimal("8.33") - Decimal("0.1163") * v, Decimal(1620) - Decimal("15.5") * v
        elif family == 6:
            target = sigmoid("-20.8", "-8.1"), sigmoid("-22", "11.39")
            tau = 30 * sigmoid("-46.56", "44.14"), 5000 * sigmoid("-46.56", "-44.14")
        else:
            raise ValueError("Unsupported Kv1 family")
        return target, tuple(value / 1000 for value in tau)


def opening(gates, family):
    with localcontext() as context:
        context.prec = 80
        return Decimal(str(gates[0])) * Decimal(str(gates[1])) ** (2 if family == 1 else 1)
