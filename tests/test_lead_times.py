"""Tests for lead-time lookup and estimation."""
import pytest
from landed_cost.lead_times import get_lead_time, estimate_lead_time


class TestGetLeadTime:

    def test_known_pair(self):
        assert get_lead_time("Sweden", "USA") == 28

    def test_domestic(self):
        assert get_lead_time("Germany", "Germany") == 2

    def test_unknown_pair(self):
        assert get_lead_time("Argentina", "Vietnam") is None

    def test_symmetric_not_guaranteed(self):
        """Matrix is directional — A→B may differ from B→A."""
        ab = get_lead_time("Sweden", "Germany")
        ba = get_lead_time("Germany", "Sweden")
        assert ab is not None and ba is not None
        assert ab == 4 and ba == 4  # happens to be same here


class TestEstimateLeadTime:

    def test_falls_back_to_exact(self):
        assert estimate_lead_time("Sweden", "USA") == 28

    def test_domestic_fallback(self):
        # Argentina → Argentina is not in the matrix, but same-country = 3
        assert estimate_lead_time("Argentina", "Argentina") == 3

    def test_inter_region_estimate(self):
        # Argentina → Vietnam — not in matrix, but americas→asia ~ 28
        result = estimate_lead_time("Argentina", "Vietnam")
        assert result is not None
        assert result > 0

    def test_unknown_country(self):
        assert estimate_lead_time("Narnia", "USA") is None
