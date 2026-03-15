"""Tests for the transfer investment analysis module."""
import pytest
from landed_cost.investment import (
    compute_npv, compute_irr, compute_payback,
    compute_discounted_payback, compute_investment_case,
)


class TestNPV:

    def test_simple_npv(self):
        # -100 upfront, +50 for 3 years at 10%
        cfs = [-100, 50, 50, 50]
        npv = compute_npv(cfs, 0.10)
        # 50/1.1 + 50/1.21 + 50/1.331 = 45.45 + 41.32 + 37.57 = 124.34
        assert npv == pytest.approx(24.34, abs=0.1)

    def test_zero_discount_rate(self):
        cfs = [-100, 30, 30, 30, 30]
        npv = compute_npv(cfs, 0.0)
        assert npv == pytest.approx(20.0)

    def test_single_cashflow(self):
        assert compute_npv([-100], 0.1) == pytest.approx(-100.0)

    def test_high_discount_destroys_value(self):
        cfs = [-1000, 200, 200, 200, 200, 200]
        npv = compute_npv(cfs, 0.50)
        assert npv < 0  # High discount wipes out returns


class TestIRR:

    def test_known_irr(self):
        # -100 upfront, +110 next year => IRR = 10%
        irr = compute_irr([-100, 110])
        assert irr == pytest.approx(0.10, abs=0.001)

    def test_annuity_irr(self):
        # -100 upfront, +50 for 3 years => IRR ~23.4%
        irr = compute_irr([-100, 50, 50, 50])
        assert irr is not None
        assert irr == pytest.approx(0.234, abs=0.01)

    def test_no_positive_returns_none(self):
        irr = compute_irr([-100, -50, -20])
        assert irr is None

    def test_no_investment_returns_none(self):
        irr = compute_irr([100, 50, 50])
        assert irr is None

    def test_empty_returns_none(self):
        assert compute_irr([]) is None
        assert compute_irr([-100]) is None

    def test_high_return(self):
        # -100, +200 => IRR = 100%
        irr = compute_irr([-100, 200])
        assert irr == pytest.approx(1.0, abs=0.01)


class TestPayback:

    def test_simple_payback(self):
        pb = compute_payback(100, 25)
        assert pb == pytest.approx(4.0)

    def test_fractional_payback(self):
        pb = compute_payback(100, 30)
        assert pb == pytest.approx(100 / 30)

    def test_zero_savings_returns_none(self):
        assert compute_payback(100, 0) is None

    def test_negative_savings_returns_none(self):
        assert compute_payback(100, -10) is None

    def test_zero_investment_returns_none(self):
        assert compute_payback(0, 50) is None


class TestDiscountedPayback:

    def test_basic_discounted_payback(self):
        cfs = [-100, 40, 40, 40, 40]
        dpb = compute_discounted_payback(cfs, 0.10)
        assert dpb is not None
        assert dpb > 2.5  # More than simple payback of 2.5
        assert dpb < 4.0

    def test_never_pays_back(self):
        cfs = [-1000, 10, 10, 10]
        dpb = compute_discounted_payback(cfs, 0.10)
        assert dpb is None

    def test_zero_rate_equals_simple(self):
        cfs = [-100, 50, 50, 50]
        dpb = compute_discounted_payback(cfs, 0.0)
        assert dpb == pytest.approx(2.0, abs=0.01)


class TestInvestmentCase:

    def test_full_case(self):
        result = compute_investment_case(
            annual_savings=5_000_000,
            capex=10_000_000,
            opex=2_000_000,
            restructuring=3_000_000,
            discount_rate=0.08,
            horizon_years=10,
        )
        assert result["total_investment"] == 15_000_000
        assert result["annual_savings"] == 5_000_000
        assert result["npv"] > 0  # 5M * ~6.7 annuity factor - 15M > 0
        assert result["irr"] is not None
        assert result["irr"] > 0.20  # High savings vs investment
        assert result["simple_payback"] == pytest.approx(3.0)
        assert result["discounted_payback"] is not None
        assert result["discounted_payback"] > 3.0
        assert len(result["cash_flows"]) == 11  # Year 0 + 10 years
        assert len(result["cumulative_cf"]) == 11

    def test_no_investment_all_upside(self):
        result = compute_investment_case(
            annual_savings=1_000_000,
            capex=0, opex=0, restructuring=0,
            discount_rate=0.08,
            horizon_years=5,
        )
        assert result["total_investment"] == 0
        assert result["npv"] > 0
        assert result["simple_payback"] is None  # No investment to pay back

    def test_negative_savings(self):
        result = compute_investment_case(
            annual_savings=-500_000,
            capex=1_000_000,
            discount_rate=0.08,
            horizon_years=10,
        )
        assert result["npv"] < 0
        assert result["irr"] is None
        assert result["simple_payback"] is None

    def test_cash_flows_structure(self):
        result = compute_investment_case(
            annual_savings=100,
            capex=500, opex=100, restructuring=50,
            horizon_years=5,
        )
        assert result["cash_flows"][0] == -650
        assert all(cf == 100 for cf in result["cash_flows"][1:])
        # Cumulative: -650, -550, -450, -350, -250, -150
        assert result["cumulative_cf"][0] == -650
        assert result["cumulative_cf"][-1] == pytest.approx(-650 + 500)

    def test_horizon_affects_npv(self):
        short = compute_investment_case(annual_savings=1000, capex=5000, horizon_years=3)
        long = compute_investment_case(annual_savings=1000, capex=5000, horizon_years=20)
        assert long["npv"] > short["npv"]

    def test_variable_annual_savings(self):
        """Year-by-year savings from sales projections."""
        savings = [1_000_000, 1_200_000, 1_500_000, 1_800_000, 2_000_000]
        result = compute_investment_case(
            annual_savings=savings,
            capex=5_000_000,
            discount_rate=0.08,
            horizon_years=10,
        )
        # First 5 years use provided values, years 6-10 repeat last value
        assert result["cash_flows"][1] == 1_000_000
        assert result["cash_flows"][5] == 2_000_000
        assert result["cash_flows"][6] == 2_000_000  # extended
        assert len(result["cash_flows"]) == 11
        assert result["annual_savings_by_year"] == savings + [2_000_000] * 5
        # Average savings
        avg = sum(result["annual_savings_by_year"]) / 10
        assert result["annual_savings"] == pytest.approx(avg)
        # NPV should be higher than flat at min savings
        flat_result = compute_investment_case(
            annual_savings=1_000_000, capex=5_000_000, discount_rate=0.08, horizon_years=10)
        assert result["npv"] > flat_result["npv"]

    def test_short_savings_list_extended(self):
        """Savings list shorter than horizon is extended with last value."""
        result = compute_investment_case(
            annual_savings=[100, 200],
            capex=500,
            horizon_years=5,
        )
        assert result["cash_flows"] == [-500, 100, 200, 200, 200, 200]
        assert result["annual_savings_by_year"] == [100, 200, 200, 200, 200]
