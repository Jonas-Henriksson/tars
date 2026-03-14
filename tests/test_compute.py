"""Tests for the landed-cost computation engine."""
import pytest
from landed_cost.models import FactoryAssumptions, ItemInputs
from landed_cost.compute import compute_location, compute_sensitivity


# ── Fixtures ──────────────────────────────────────────────
@pytest.fixture
def base_inputs():
    return ItemInputs(
        item_number="1001",
        designation="Test Item",
        currency="SEK",
        net_sales_value=100_000_000.0,
        net_sales_qty=2_000_000,
        material=20.0,
        variable_va=3.0,
        fixed_va=2.0,
    )


@pytest.fixture
def base_factory():
    return FactoryAssumptions(
        name="Base", country="Sweden",
        va_ratio=None, ps_index=1.0, mcl_pct=100.0,
        sa_pct=0.0, tpl=100.0,
        tariff_pct=0.0, duties_pct=0.0, transport_pct=0.0,
    )


@pytest.fixture
def alt_factory():
    return FactoryAssumptions(
        name="Alt", country="China",
        va_ratio=0.7, ps_index=1.03, mcl_pct=101.0,
        sa_pct=0.04, tpl=100.0,
        tariff_pct=0.05, duties_pct=0.02, transport_pct=0.03,
    )


# ── Basic computation ────────────────────────────────────
class TestComputeLocation:

    def test_base_case_simple(self, base_inputs, base_factory):
        r = compute_location(base_inputs, base_factory, is_base=True)
        assert r is not None
        assert r["material"] == 20.0
        assert r["variable_va"] == 3.0
        assert r["fixed_va"] == 2.0
        assert r["sc"] == 25.0
        assert r["ps"] == 25.0  # ps_index = 1.0
        assert r["ns_per_unit"] == 50.0
        # OP = NS - PS - S&A - Tar - Dut - Trn = 50 - 25 - 0 - 0 - 0 - 0 = 25
        assert r["op"] == pytest.approx(25.0)
        assert r["om"] == pytest.approx(0.5)

    def test_alternative_with_va_ratio(self, base_inputs, alt_factory):
        r = compute_location(base_inputs, alt_factory)
        assert r is not None
        # VA ratio 0.7 scales variable_va (3*0.7=2.1) and fixed_va (2*0.7=1.4)
        assert r["variable_va"] == pytest.approx(2.1)
        assert r["fixed_va"] == pytest.approx(1.4)
        sc = 20.0 + 2.1 + 1.4  # = 23.5
        assert r["sc"] == pytest.approx(sc)
        ps = sc * 1.03
        assert r["ps"] == pytest.approx(ps)

    def test_alternative_returns_none_without_va_ratio(self, base_inputs):
        factory = FactoryAssumptions(name="NoRatio", va_ratio=None)
        r = compute_location(base_inputs, factory, is_base=False)
        assert r is None

    def test_tariff_and_duties(self, base_inputs, alt_factory):
        r = compute_location(base_inputs, alt_factory)
        ps = r["ps"]
        # tariff = (100/100) * ps * 0.05
        assert r["tariff"] == pytest.approx(ps * 0.05)
        # duties = (100/100) * ps * 0.02
        assert r["duties"] == pytest.approx(ps * 0.02)

    def test_transport(self, base_inputs, alt_factory):
        r = compute_location(base_inputs, alt_factory)
        assert r["transport"] == pytest.approx(r["ps"] * 0.03)

    def test_sa_deduction(self, base_inputs, alt_factory):
        r = compute_location(base_inputs, alt_factory)
        assert r["sa"] == pytest.approx(50.0 * 0.04)

    def test_annual_aggregates(self, base_inputs, base_factory):
        r = compute_location(base_inputs, base_factory, is_base=True)
        assert r["annual_rev"] == pytest.approx(50.0 * 2_000_000)
        assert r["annual_op"] == pytest.approx(25.0 * 2_000_000)

    def test_overrides(self, base_inputs, alt_factory):
        ov = {"material": 15.0, "variable_va": 1.5}
        r = compute_location(base_inputs, alt_factory, overrides=ov)
        assert r["material"] == 15.0
        assert r["variable_va"] == 1.5
        # fixed_va still uses VA ratio
        assert r["fixed_va"] == pytest.approx(2.0 * 0.7)

    def test_zero_quantity(self, base_factory):
        inputs = ItemInputs(net_sales_value=1000.0, net_sales_qty=0, material=10.0)
        r = compute_location(inputs, base_factory, is_base=True)
        assert r is not None
        assert r["ns_per_unit"] == 0.0
        assert r["om"] == 0

    def test_actual_cost_informational(self, base_inputs, alt_factory):
        """Actual cost uses MCL but does not affect OP."""
        r = compute_location(base_inputs, alt_factory)
        assert r["actual_cost"] == pytest.approx(r["ps"] * 1.01)
        # OP should use ps, not actual_cost
        expected_op = (r["ns_per_unit"] - r["ps"] - r["sa"]
                       - r["tariff"] - r["duties"] - r["transport"])
        assert r["op"] == pytest.approx(expected_op)

    def test_op_formula_consistency(self, base_inputs, alt_factory):
        r = compute_location(base_inputs, alt_factory)
        # annual_cost = (ps + sa + tariff + duties + transport) * qty
        per_unit_cost = r["ps"] + r["sa"] + r["tariff"] + r["duties"] + r["transport"]
        assert r["annual_cost"] == pytest.approx(per_unit_cost * 2_000_000)
        assert r["annual_op"] == pytest.approx(r["annual_rev"] - r["annual_cost"])


# ── Sensitivity analysis ─────────────────────────────────
class TestSensitivity:

    def test_vary_va_ratio(self, base_inputs, alt_factory):
        steps = [0.5, 0.7, 0.9, 1.1]
        results = compute_sensitivity(base_inputs, alt_factory, "va_ratio", steps)
        assert len(results) == 4
        # Lower VA ratio → lower cost → higher OP
        assert results[0]["op"] > results[-1]["op"]

    def test_vary_material(self, base_inputs, base_factory):
        steps = [15.0, 20.0, 25.0]
        results = compute_sensitivity(base_inputs, base_factory, "material", steps, is_base=True)
        assert len(results) == 3
        # Lower material → higher OP
        assert results[0]["op"] > results[-1]["op"]

    def test_invalid_parameter(self, base_inputs, base_factory):
        with pytest.raises(ValueError, match="Unknown parameter"):
            compute_sensitivity(base_inputs, base_factory, "invalid_param", [1.0])

    def test_result_contains_param_metadata(self, base_inputs, alt_factory):
        results = compute_sensitivity(base_inputs, alt_factory, "transport_pct", [0.01, 0.05])
        assert results[0]["param_name"] == "transport_pct"
        assert results[0]["param_value"] == 0.01
        assert results[1]["param_value"] == 0.05
