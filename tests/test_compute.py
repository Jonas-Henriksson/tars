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


# ── NWC / Goods-in-Transit Impact ────────────────────────
class TestNWCImpact:

    def test_no_lead_time_means_zero_nwc(self, base_inputs, base_factory):
        """Without lead time data, all NWC fields should be zero."""
        r = compute_location(base_inputs, base_factory, is_base=True)
        assert r["git_value"] == 0.0
        assert r["delta_git"] == 0.0
        assert r["nwc_carrying_cost_annual"] == 0.0
        assert r["nwc_carrying_cost_per_unit"] == 0.0
        assert r["adj_op"] == r["op"]
        assert r["adj_om"] == r["om"]

    def test_base_case_zero_delta(self, base_inputs, base_factory):
        """Base case with lead time: GIT exists but delta is zero."""
        r = compute_location(base_inputs, base_factory, is_base=True,
                             lead_time_days=5, base_lead_time_days=5, cost_of_capital=0.08)
        ps = r["ps"]  # 25.0
        qty = 2_000_000
        expected_git = (ps * qty / 365.0) * 5
        assert r["git_value"] == pytest.approx(expected_git)
        assert r["delta_lead_time"] == 0
        assert r["delta_git"] == pytest.approx(0.0)
        assert r["nwc_carrying_cost_annual"] == pytest.approx(0.0)
        assert r["adj_op"] == pytest.approx(r["op"])

    def test_longer_lead_time_increases_nwc_cost(self, base_inputs, alt_factory):
        """Longer transit = more GIT = NWC carrying cost reduces adj_op."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=35, base_lead_time_days=5,
                             cost_of_capital=0.08)
        ps = r["ps"]
        qty = 2_000_000
        delta_days = 30  # 35 - 5
        assert r["delta_lead_time"] == 30

        expected_delta_git = (ps * qty / 365.0) * delta_days
        assert r["delta_git"] == pytest.approx(expected_delta_git)

        expected_annual_cost = expected_delta_git * 0.08
        assert r["nwc_carrying_cost_annual"] == pytest.approx(expected_annual_cost)

        expected_per_unit = expected_annual_cost / qty
        assert r["nwc_carrying_cost_per_unit"] == pytest.approx(expected_per_unit)

        assert r["adj_op"] == pytest.approx(r["op"] - expected_per_unit)
        assert r["adj_op"] < r["op"]  # NWC cost reduces profit
        assert r["annual_adj_op"] == pytest.approx(r["adj_op"] * qty)

    def test_shorter_lead_time_reduces_nwc_cost(self, base_inputs, alt_factory):
        """Shorter transit = NWC benefit (negative carrying cost)."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=3, base_lead_time_days=10,
                             cost_of_capital=0.10)
        assert r["delta_lead_time"] == -7
        assert r["delta_git"] < 0  # Negative = capital released
        assert r["nwc_carrying_cost_annual"] < 0  # Benefit
        assert r["adj_op"] > r["op"]  # NWC benefit increases profit

    def test_zero_cost_of_capital_no_carrying_cost(self, base_inputs, alt_factory):
        """With 0% CoC, delta GIT exists but carrying cost is zero."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=35, base_lead_time_days=5,
                             cost_of_capital=0.0)
        assert r["delta_lead_time"] == 30
        assert r["delta_git"] > 0
        assert r["nwc_carrying_cost_annual"] == 0.0
        assert r["adj_op"] == r["op"]

    def test_git_value_formula(self, base_inputs, alt_factory):
        """Verify GIT = (PS x Qty / 365) x transit_days."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=20, base_lead_time_days=5)
        ps = r["ps"]
        qty = 2_000_000
        expected = (ps * qty / 365.0) * 20
        assert r["git_value"] == pytest.approx(expected)

    def test_safety_stock_increases_nwc(self, base_inputs, alt_factory):
        """Higher safety stock at alt vs base increases NWC carrying cost."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=10, base_lead_time_days=10,
                             safety_stock_days=20, base_safety_stock_days=5,
                             cost_of_capital=0.08)
        ps = r["ps"]
        qty = 2_000_000
        daily = ps * qty / 365.0
        # GIT delta is 0 (same lead time), but safety stock delta = 15 days
        assert r["delta_git"] == pytest.approx(0.0)
        assert r["delta_safety_stock"] == pytest.approx(daily * 15)
        assert r["delta_nwc"] == pytest.approx(daily * 15)
        assert r["nwc_carrying_cost_annual"] == pytest.approx(daily * 15 * 0.08)
        assert r["adj_op"] < r["op"]

    def test_cycle_stock_delta(self, base_inputs, alt_factory):
        """Cycle stock difference flows through to NWC delta."""
        r = compute_location(base_inputs, alt_factory,
                             cycle_stock_days=30, base_cycle_stock_days=10,
                             cost_of_capital=0.10)
        ps = r["ps"]
        qty = 2_000_000
        daily = ps * qty / 365.0
        assert r["delta_cycle_stock"] == pytest.approx(daily * 20)
        assert r["nwc_carrying_cost_annual"] == pytest.approx(daily * 20 * 0.10)

    def test_payment_terms_reduce_nwc(self, base_inputs, alt_factory):
        """Longer DPO at alt vs base reduces NWC (benefit)."""
        r = compute_location(base_inputs, alt_factory,
                             payment_terms_days=60, base_payment_terms_days=30,
                             cost_of_capital=0.08)
        ps = r["ps"]
        qty = 2_000_000
        daily = ps * qty / 365.0
        # Longer DPO = more payables = less NWC needed
        assert r["delta_payables"] == pytest.approx(daily * 30)
        # Delta NWC is negative (benefit) because payables increase offsets
        assert r["delta_nwc"] == pytest.approx(-daily * 30)
        assert r["nwc_carrying_cost_annual"] < 0  # Benefit
        assert r["adj_op"] > r["op"]  # Improves profit

    def test_combined_nwc_components(self, base_inputs, alt_factory):
        """All NWC components aggregate correctly."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=35, base_lead_time_days=5,
                             safety_stock_days=15, base_safety_stock_days=10,
                             cycle_stock_days=20, base_cycle_stock_days=15,
                             payment_terms_days=45, base_payment_terms_days=30,
                             cost_of_capital=0.08)
        ps = r["ps"]
        qty = 2_000_000
        daily = ps * qty / 365.0
        # delta_git = daily * 30, delta_ss = daily * 5, delta_cs = daily * 5
        # delta_pt = daily * 15 (subtracted)
        expected_delta_nwc = daily * (30 + 5 + 5 - 15)
        assert r["delta_nwc"] == pytest.approx(expected_delta_nwc)
        assert r["nwc_carrying_cost_annual"] == pytest.approx(expected_delta_nwc * 0.08)
        # total_nwc = git + ss + cs - pt
        expected_total = daily * (35 + 15 + 20 - 45)
        assert r["total_nwc"] == pytest.approx(expected_total)

    def test_nwc_components_default_zero(self, base_inputs, alt_factory):
        """Without optional NWC params, only GIT contributes."""
        r = compute_location(base_inputs, alt_factory,
                             lead_time_days=20, base_lead_time_days=10,
                             cost_of_capital=0.08)
        assert r["safety_stock_value"] == 0.0
        assert r["cycle_stock_value"] == 0.0
        assert r["payables_value"] == 0.0
        assert r["delta_nwc"] == pytest.approx(r["delta_git"])


# ── Sensitivity analysis ─────────────────────────────────
class TestSensitivity:

    def test_vary_va_ratio(self, base_inputs, alt_factory):
        steps = [0.5, 0.7, 0.9, 1.1]
        results = compute_sensitivity(base_inputs, alt_factory, "va_ratio", steps)
        assert len(results) == 4
        # Lower VA ratio -> lower cost -> higher OP
        assert results[0]["op"] > results[-1]["op"]

    def test_vary_material(self, base_inputs, base_factory):
        steps = [15.0, 20.0, 25.0]
        results = compute_sensitivity(base_inputs, base_factory, "material", steps, is_base=True)
        assert len(results) == 3
        # Lower material -> higher OP
        assert results[0]["op"] > results[-1]["op"]

    def test_invalid_parameter(self, base_inputs, base_factory):
        with pytest.raises(ValueError, match="Unknown parameter"):
            compute_sensitivity(base_inputs, base_factory, "invalid_param", [1.0])

    def test_result_contains_param_metadata(self, base_inputs, alt_factory):
        results = compute_sensitivity(base_inputs, alt_factory, "transport_pct", [0.01, 0.05])
        assert results[0]["param_name"] == "transport_pct"
        assert results[0]["param_value"] == 0.01
        assert results[1]["param_value"] == 0.05
