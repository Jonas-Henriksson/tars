"""Tests for formatting helpers."""
import pytest
from landed_cost.formatters import (
    format_number, format_percent, format_integer, delta_class,
    fn, fp, fi, dc,
)


class TestFormatNumber:

    def test_basic(self):
        assert format_number(1234.5678, decimals=2) == "1,234.57"

    def test_none(self):
        assert format_number(None) == "\u2013"

    def test_dash_zero(self):
        assert format_number(0.001, decimals=2) == "\u2013"
        assert format_number(0.001, decimals=2, dash_zero=False) == "0.00"

    def test_accounting_negative(self):
        assert format_number(-100.0, accounting=True) == "(100.00)"

    def test_suffix(self):
        assert format_number(42.0, suffix=" SEK", dash_zero=False) == "42.00 SEK"


class TestFormatPercent:

    def test_basic(self):
        assert format_percent(0.123) == "12.3%"

    def test_none(self):
        assert format_percent(None) == "\u2013"

    def test_accounting(self):
        assert format_percent(-0.05, accounting=True) == "(5.0%)"


class TestFormatInteger:

    def test_basic(self):
        assert format_integer(123456) == "123,456"

    def test_dash_zero(self):
        assert format_integer(0) == "\u2013"
        assert format_integer(0, dash_zero=False) == "0"


class TestDeltaClass:

    def test_positive(self):
        assert delta_class(0.5) == "delta-pos"

    def test_negative(self):
        assert delta_class(-0.5) == "delta-neg"

    def test_zero(self):
        assert delta_class(0) == ""

    def test_none(self):
        assert delta_class(None) == ""


class TestAliases:
    """Ensure the short aliases delegate to full-name helpers."""

    def test_fn(self):
        assert fn(1234.5) == format_number(1234.5)

    def test_fp(self):
        assert fp(0.123) == format_percent(0.123)

    def test_fi(self):
        assert fi(12345) == format_integer(12345)

    def test_dc(self):
        assert dc(1.0) == delta_class(1.0)
