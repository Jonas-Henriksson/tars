"""Transfer investment analysis: NPV, IRR, payback period.

Evaluates whether the annual savings from a production transfer justify
the upfront investment (CAPEX, OPEX, restructuring) over a given horizon.

Cash-flow convention:
  Year 0: -CAPEX - OPEX - Restructuring  (total outlay)
  Year 1..N: Annual savings (delta OP vs. base, NWC-adjusted)

Metrics:
  NPV  = Sum of discounted cash flows at the given discount rate
  IRR  = Discount rate that makes NPV = 0  (bisection solver)
  Simple Payback = Total Investment / Annual Savings  (years)
  Discounted Payback = first year where cumulative discounted CF >= 0
"""
from __future__ import annotations
from typing import Optional


def compute_npv(cash_flows: list[float], discount_rate: float) -> float:
    """Net Present Value of a cash-flow series.

    Args:
        cash_flows: [CF_0, CF_1, ..., CF_n] where CF_0 is typically negative.
        discount_rate: Annual rate as decimal (e.g. 0.08 = 8%).

    Returns the NPV.
    """
    npv = 0.0
    for t, cf in enumerate(cash_flows):
        npv += cf / (1 + discount_rate) ** t
    return npv


def compute_irr(
    cash_flows: list[float],
    tol: float = 1e-6,
    max_iter: int = 200,
) -> Optional[float]:
    """Internal Rate of Return via bisection.

    Returns the IRR as a decimal, or None if no solution is found
    (e.g. no sign change, or all cash flows are negative).
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    # Need at least one negative and one positive CF for IRR to exist
    has_neg = any(cf < 0 for cf in cash_flows)
    has_pos = any(cf > 0 for cf in cash_flows)
    if not (has_neg and has_pos):
        return None

    lo, hi = -0.5, 5.0  # -50% to 500%

    npv_lo = compute_npv(cash_flows, lo)
    npv_hi = compute_npv(cash_flows, hi)

    # If NPV doesn't change sign in this range, widen or give up
    if npv_lo * npv_hi > 0:
        # Try wider range
        lo, hi = -0.9, 20.0
        npv_lo = compute_npv(cash_flows, lo)
        npv_hi = compute_npv(cash_flows, hi)
        if npv_lo * npv_hi > 0:
            return None

    for _ in range(max_iter):
        mid = (lo + hi) / 2
        npv_mid = compute_npv(cash_flows, mid)
        if abs(npv_mid) < tol:
            return mid
        if npv_lo * npv_mid < 0:
            hi = mid
            npv_hi = npv_mid
        else:
            lo = mid
            npv_lo = npv_mid

    return (lo + hi) / 2


def compute_payback(total_investment: float, annual_savings: float) -> Optional[float]:
    """Simple payback period in years.

    Returns None if annual_savings <= 0 (never pays back).
    """
    if annual_savings <= 0 or total_investment <= 0:
        return None
    return total_investment / annual_savings


def compute_discounted_payback(
    cash_flows: list[float],
    discount_rate: float,
) -> Optional[float]:
    """Discounted payback: first year where cumulative discounted CF >= 0.

    Returns fractional years, or None if payback never occurs within the horizon.
    """
    cumulative = 0.0
    for t, cf in enumerate(cash_flows):
        dcf = cf / (1 + discount_rate) ** t
        prev_cum = cumulative
        cumulative += dcf
        if cumulative >= 0 and t > 0:
            # Linear interpolation within the year
            if dcf > 0:
                frac = -prev_cum / dcf
                return (t - 1) + frac
            return float(t)
    return None


def compute_investment_case(
    annual_savings: float,
    capex: float = 0.0,
    opex: float = 0.0,
    restructuring: float = 0.0,
    discount_rate: float = 0.08,
    horizon_years: int = 10,
) -> dict:
    """Full investment analysis for a production transfer scenario.

    Args:
        annual_savings:  Annual OP improvement vs. base (NWC-adjusted).
        capex:           Capital expenditure at receiving site (tooling, etc.).
        opex:            One-time operational costs (project, qualification).
        restructuring:   One-time restructuring costs at sending site.
        discount_rate:   Discount rate (decimal). Typically WACC.
        horizon_years:   Analysis horizon in years.

    Returns a dict with all investment metrics.
    """
    total_investment = capex + opex + restructuring
    cash_flows = [-total_investment] + [annual_savings] * horizon_years

    npv = compute_npv(cash_flows, discount_rate)
    irr = compute_irr(cash_flows)
    simple_payback = compute_payback(total_investment, annual_savings)
    disc_payback = compute_discounted_payback(cash_flows, discount_rate)

    # Cumulative undiscounted cash flows per year (for charting)
    cumulative = []
    running = 0.0
    for cf in cash_flows:
        running += cf
        cumulative.append(running)

    return {
        "capex": capex,
        "opex": opex,
        "restructuring": restructuring,
        "total_investment": total_investment,
        "annual_savings": annual_savings,
        "discount_rate": discount_rate,
        "horizon_years": horizon_years,
        "cash_flows": cash_flows,
        "cumulative_cf": cumulative,
        "npv": npv,
        "irr": irr,
        "simple_payback": simple_payback,
        "discounted_payback": disc_payback,
    }
