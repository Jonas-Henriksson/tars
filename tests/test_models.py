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
