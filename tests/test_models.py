"""Tests for data models."""
import pytest
from landed_cost.models import FactoryAssumptions, ItemInputs


class TestItemInputs:

    def test_net_sales_per_unit(self):
        item = ItemInputs(net_sales_value=100_000.0, net_sales_qty=1000)
        assert item.net_sales_per_unit == 100.0

    def test_net_sales_per_unit_zero_qty(self):
        item = ItemInputs(net_sales_value=100_000.0, net_sales_qty=0)
        assert item.net_sales_per_unit == 0.0

    def test_validate_valid(self):
        item = ItemInputs(
            net_sales_value=1000.0, net_sales_qty=10,
            material=5.0, variable_va=1.0, fixed_va=1.0,
        )
        assert item.validate() == []

    def test_validate_negative_qty(self):
        item = ItemInputs(net_sales_qty=-1)
        errors = item.validate()
        assert any("quantity" in e.lower() for e in errors)

    def test_validate_negative_material(self):
        item = ItemInputs(material=-5.0)
        errors = item.validate()
        assert any("material" in e.lower() for e in errors)

    def test_sales_projection_default_empty(self):
        item = ItemInputs()
        assert item.sales_projection == []

    def test_get_projection_for_year(self):
        proj = [
            {"year": 1, "value": 100_000.0, "qty": 1000},
            {"year": 2, "value": 120_000.0, "qty": 1100},
            {"year": 3, "value": 140_000.0, "qty": 1200},
        ]
        item = ItemInputs(net_sales_value=100_000.0, net_sales_qty=1000,
                          sales_projection=proj)
        assert item.get_projection_for_year(1) == (100_000.0, 1000)
        assert item.get_projection_for_year(2) == (120_000.0, 1100)
        assert item.get_projection_for_year(3) == (140_000.0, 1200)

    def test_get_projection_beyond_range(self):
        """Years beyond projection use last available year."""
        proj = [
            {"year": 1, "value": 100_000.0, "qty": 1000},
            {"year": 2, "value": 120_000.0, "qty": 1100},
        ]
        item = ItemInputs(net_sales_value=100_000.0, net_sales_qty=1000,
                          sales_projection=proj)
        assert item.get_projection_for_year(5) == (120_000.0, 1100)

    def test_get_projection_no_projection(self):
        """Falls back to base year values if no projection."""
        item = ItemInputs(net_sales_value=100_000.0, net_sales_qty=1000)
        assert item.get_projection_for_year(1) == (100_000.0, 1000)


class TestFactoryAssumptions:

    def test_to_dict(self):
        f = FactoryAssumptions(name="Test", country="Sweden", ps_index=1.05)
        d = f.to_dict()
        assert d["name"] == "Test"
        assert d["ps_index"] == 1.05

    def test_defaults(self):
        f = FactoryAssumptions()
        assert f.ps_index == 1.0
        assert f.mcl_pct == 100.0
        assert f.va_ratio is None
