"""Formatting helpers for numbers, percentages, and delta styling."""
from __future__ import annotations
from landed_cost.constants import GREEN, RED


# ── Concise aliases (kept for backward compatibility) ─────
def fn(v, d=2, sfx="", acct=False, dz=True):
    """Format a number with *d* decimals, optional suffix and accounting style."""
    return format_number(v, decimals=d, suffix=sfx, accounting=acct, dash_zero=dz)


def fp(v, d=1, acct=False, dz=True):
    """Format a value as a percentage (0.35 → '35.0%')."""
    return format_percent(v, decimals=d, accounting=acct, dash_zero=dz)


def fi(v, acct=False, dz=True):
    """Format an integer (no decimals)."""
    return format_integer(v, accounting=acct, dash_zero=dz)


def dc(v):
    """Return CSS class name for a delta value."""
    return delta_class(v)


# ── Full-name helpers ─────────────────────────────────────
def format_number(v, decimals: int = 2, suffix: str = "", accounting: bool = False, dash_zero: bool = True) -> str:
    """Format a numeric value with thousands separators.

    Args:
        v:          The value to format (None is safe).
        decimals:   Number of decimal places.
        suffix:     String appended after the number (e.g. " SEK").
        accounting: If True, negative values are wrapped in parentheses.
        dash_zero:  If True, values near zero display as an en-dash (–).
    """
    if v is None:
        return "\u2013"
    threshold = 0.5 * (10 ** -decimals)
    if dash_zero and abs(v) < threshold:
        return "\u2013"
    if accounting and v < 0:
        return f"({abs(v):,.{decimals}f}{suffix})"
    return f"{v:,.{decimals}f}{suffix}"


def format_percent(v, decimals: int = 1, accounting: bool = False, dash_zero: bool = True) -> str:
    """Format a fraction as a percentage (e.g. 0.12 → '12.0%')."""
    if v is None:
        return "\u2013"
    threshold = 0.5 * (10 ** -(decimals + 2))
    if dash_zero and abs(v) < threshold:
        return "\u2013"
    p = v * 100
    if accounting and p < 0:
        return f"({abs(p):,.{decimals}f}%)"
    return f"{p:,.{decimals}f}%"


def format_integer(v, accounting: bool = False, dash_zero: bool = True) -> str:
    """Format a value as an integer with thousands separators."""
    if v is None:
        return "\u2013"
    if dash_zero and abs(v) < 0.5:
        return "\u2013"
    if accounting and v < 0:
        return f"({abs(v):,.0f})"
    return f"{v:,.0f}"


def format_abbreviated(v) -> str:
    """Format a number with K/M suffix to match chart axis labels."""
    if v is None:
        return "\u2013"
    av = abs(v)
    sign = "" if v >= 0 else "-"
    if av >= 1_000_000:
        return f"{sign}{av / 1_000_000:,.1f}M"
    elif av >= 1_000:
        return f"{sign}{av / 1_000:,.0f}K"
    elif av >= 1:
        return f"{sign}{av:,.0f}"
    else:
        return f"{sign}{av:,.2f}"


def fa(v) -> str:
    """Short alias for format_abbreviated."""
    return format_abbreviated(v)


def delta_class(v) -> str:
    """Return a CSS class name ('delta-pos' / 'delta-neg') for coloring deltas."""
    if v is None or abs(v) < 0.0001:
        return ""
    return "delta-pos" if v > 0 else "delta-neg"
