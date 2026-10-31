"""PROSPECTIVE, UNRUN: separate ECM computational-domain controls.

These scalar checks do not replace fresh pinned-native probes or the unchanged
whole ECM conditional comparisons. High-voltage samples have no biology credit.
"""

import ast
import hashlib
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from validation.betse import betse_ecm_cal2_reference as cal2
from validation.betse import betse_ecm_sodium_reference as sodium_ecm
from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.channels import calcium_catalog_extra_reference as calcium_original
from validation.channels import sodium_catalog_reference as sodium_original

ROOT = Path(__file__).resolve().parents[2]
CLASSES = sodium_ecm.CLASSES + ("Ca_L2",)
ORDINARY = ("-0.120", "-0.080", "-0.065", "-0.020", "0.000", "0.060")
EXTENDED = (
    "0.060001",
    "0.100",
    "0.1503399220882436",
    "0.16211604721528552",
    "0.20880985372727817",
    "0.2468703954988288",
    "0.300",
    "0.38043109406702724",
    "0.400",
)


def adapter(name):
    return cal2 if name == "Ca_L2" else sodium_ecm


def record(path, value):
    def tree(item):
        if isinstance(item, Decimal):
            return {"decimal": str(item)}
        if isinstance(item, dict):
            return {k: tree(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [tree(v) for v in item]
        return item

    with path.open("x") as stream:
        json.dump(tree(value), stream, indent=2, allow_nan=False)
        stream.write("\n")


def captured(path, function, **request):
    try:
        value = function()
    except Exception as error:
        record(
            path,
            dict(request=request, refused=True, error_type=type(error).__name__, error=str(error)),
        )
        raise
    record(path, dict(request=request, returned=value, numerical_extrapolation_only=True))
    return value


@pytest.mark.parametrize("name", CLASSES)
def test_original_domain_equations_are_exactly_retained(tmp_path, name):
    original = calcium_original if name == "Ca_L2" else sodium_original
    for i, text in enumerate(ORDINARY):
        for precision in (100, 160):
            voltage = Decimal(text)
            actual = captured(
                tmp_path / f"actual-{i}-{precision}.json",
                lambda voltage=voltage, precision=precision: adapter(name).kinetics(
                    voltage, name, precision=precision
                ),
                name=name,
                voltage_V=voltage,
                precision=precision,
                group="ordinary-domain",
            )
            with localcontext() as context:
                context.prec = precision
                expected = original._kinetics(voltage, name)
            record(tmp_path / f"original-{i}-{precision}.json", dict(expected=expected))
            assert actual == expected


@pytest.mark.parametrize("name", CLASSES)
def test_new_domain_is_only_numerical_and_precision_checked(tmp_path, name):
    # Reuse the existing independent component floors; no new budget is fitted.
    protocol_name = (
        "calcium_catalog_extra_protocol.json" if name == "Ca_L2" else "sodium_catalog_protocol.json"
    )
    limits = json.loads((ROOT / "validation/channels" / protocol_name).read_text())["tolerances"]
    for i, text in enumerate(EXTENDED):
        voltage = Decimal(text)
        low = captured(
            tmp_path / f"reference100-{i}.json",
            lambda voltage=voltage: adapter(name).kinetics(voltage, name, precision=100),
            name=name,
            voltage_V=voltage,
            precision=100,
            group="new-computational-domain",
        )
        high = captured(
            tmp_path / f"reference160-{i}.json",
            lambda voltage=voltage: adapter(name).kinetics(voltage, name, precision=160),
            name=name,
            voltage_V=voltage,
            precision=160,
            group="new-computational-domain",
        )
        for field, floor in ((0, "gate_atol"), (1, "tau_atol_s")):
            for a, b in zip(low[field], high[field], strict=True):
                assert a.is_finite() and b.is_finite()
                budget = Decimal(str(limits[floor])) + Decimal(str(limits["relative"])) * abs(b)
                assert abs(a - b) <= Decimal("0.1") * budget
                assert (0 <= b <= 1) if field == 0 else b > 0


@pytest.mark.parametrize("name", CLASSES)
def test_nominal_and_exact_binary64_endpoints_and_adjacent_refusals(tmp_path, name):
    for i, voltage in enumerate(
        (
            Decimal("-.120"),
            -0.120,
            Decimal.from_float(-0.120),
            Decimal(".400"),
            0.400,
            Decimal.from_float(0.400),
        )
    ):
        target, tau = captured(
            tmp_path / f"endpoint-{i}.json",
            lambda voltage=voltage: adapter(name).kinetics(voltage, name, precision=100),
            name=name,
            voltage_V=str(voltage),
        )
        assert all(x.is_finite() for x in target + tau)
    outside = (math.nextafter(-0.120, -math.inf), math.nextafter(0.400, math.inf), -1.0, 5.0, 1e300)
    for i, voltage in enumerate(outside):
        with pytest.raises(ValueError, match="outside declared ECM"):
            captured(
                tmp_path / f"outside-{i}.json",
                lambda voltage=voltage: adapter(name).kinetics(
                    Decimal.from_float(voltage), name, precision=100
                ),
                name=name,
                voltage_V=voltage,
                group="domain-and-overflow-refusal",
            )


@pytest.mark.parametrize(
    "name", tuple(name for name in sodium_ecm.CLASSES if sodium_original.SINGULAR_V[name])
)
def test_sodium_removable_limits_are_not_native_finite_claims(tmp_path, name):
    for i, value in enumerate(sodium_original.SINGULAR_V[name]):
        point = Decimal(str(value))
        samples = (
            point,
            point - Decimal("1e-12"),
            point + Decimal("1e-12"),
            Decimal.from_float(math.nextafter(value, -math.inf)),
            Decimal.from_float(math.nextafter(value, math.inf)),
        )
        for j, sample in enumerate(samples):
            actual = captured(
                tmp_path / f"analytic-limit-{i}-{j}.json",
                lambda sample=sample: sodium_ecm.kinetics(sample, name, precision=100),
                name=name,
                voltage_V=sample,
                literal_native_finite_claim=False,
            )
            with localcontext() as context:
                context.prec = 100
                old = sodium_original._kinetics(sample, name)
            record(tmp_path / f"original-limit-{i}-{j}.json", dict(expected=old))
            assert actual == old


@pytest.mark.parametrize("name", CLASSES)
def test_standalone_domain_is_still_the_original_contract(tmp_path, name):
    original = calcium_original if name == "Ca_L2" else sodium_original
    for i, voltage in enumerate((Decimal("-.120001"), Decimal(".060001"), Decimal(".400"))):
        with pytest.raises(ValueError, match="outside"):
            captured(
                tmp_path / f"standalone-refusal-{i}.json",
                lambda voltage=voltage: original._kinetics(voltage, name),
                name=name,
                voltage_V=voltage,
            )


@pytest.mark.parametrize(
    "bad", (True, False, "0.1", None, 1j, float("nan"), float("inf"), Decimal("NaN"))
)
def test_real_finite_type_guards_still_apply(bad):
    with pytest.raises(ValueError):
        sodium_ecm.kinetics(bad, "Nav1p2", precision=100)
    with pytest.raises(ValueError):
        cal2.kinetics(bad, "Ca_L2", precision=100)


@pytest.mark.parametrize("precision", (True, False, 80, 101, 100.0, None))
def test_only_original_two_precision_levels_are_admitted(precision):
    with pytest.raises(ValueError, match="precision100 or160"):
        sodium_ecm.kinetics(0.0, "Nav1p2", precision=precision)
    with pytest.raises(ValueError, match="precision100 or160"):
        cal2.kinetics(0.0, "Ca_L2", precision=precision)


def test_no_constant_leak_or_other_calcium_domain_inheritance():
    with pytest.raises(ValueError, match="voltage-dependent ECM sodium"):
        sodium_ecm.kinetics(0.2, "NaLeak", precision=100)
    for name in ("Ca_L3", "Cav_G", "CaLeak"):
        with pytest.raises(ValueError, match="separately declared ECM Ca_L2"):
            cal2.kinetics(0.2, name, precision=100)
        with pytest.raises(ValueError, match="outside computational domain"):
            catalog.kinetics(name, Decimal(".2"), 1)
    assert catalog.kinetics("NaLeak", Decimal("1e1000"), 1) == ([Decimal(1)] * 2, [Decimal(1)] * 2)


def test_catalog_budget_table_is_unchanged():
    protocol = json.loads(
        (ROOT / "validation/betse/betse_normal_ecm_catalog_join_protocol.json").read_text()
    )
    for name in CLASSES:
        expected = (5e-14, 5e-12) if name == "Nav1p6" else (1e-12, 5e-11)
        actual = protocol["catalog_budgets"][name]
        assert (actual["absolute"], actual["relative"]) == expected


def test_sodium_equation_tail_is_original_AST_without_its_domain_or_leak_branch():
    old = ast.parse(Path(sodium_original.__file__).read_text())
    new = ast.parse(Path(sodium_ecm.__file__).read_text())

    def function(tree):
        return next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_kinetics"
        )

    body = function(old).body[3:]
    body = [
        n for n in body if not (isinstance(n, ast.If) and ast.unparse(n.test) == "name == 'NaLeak'")
    ]
    expected = ast.Module(body=body, type_ignores=[])
    actual = ast.Module(body=function(new).body[3:], type_ignores=[])
    assert ast.dump(actual, include_attributes=False) == ast.dump(
        expected, include_attributes=False
    )
    # Module hashes are pinned by the prospective source packet, independently
    # of this local AST assertion. This test executes no native channel law.
    assert hashlib.sha256(Path(sodium_original.__file__).read_bytes()).hexdigest() == (
        "27bd6662889eb3cd84a52c3239518b29e03b37d92183d76c32dc1c47c7a980bf"
    )
