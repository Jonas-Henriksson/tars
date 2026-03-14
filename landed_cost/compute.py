"""Core computation engine for landed-cost analysis.

The cost build-up:
  1. Base costs -> Standard Cost (SC) = Material + Variable VA + Fixed VA
  2. VA Ratio scales Variable & Fixed VA to each location's cost level
  3. Price Standard (PS) = SC x PS Index
  4. Actual Cost = PS x (MCL % / 100)  [informational - not used in OP]
  5. S&A = Net Sales per Unit x S&A %
  6. Tariff = (TPL / 100) x PS x Tariff %
  7. Duties = (TPL / 100) x PS x Duties %
  8. Transportation = PS x Transport %
  9. Operating Profit = Net Sales - PS - S&A - Tariff - Duties - Transport
 10. Operating Margin = Operating Profit / Net Sales

NWC (Net Working Capital) impact:
 11. Goods-in-Transit (GIT) = (PS x Qty / 365) x Transit Days
 12. Safety Stock = (PS x Qty / 365) x Safety Stock Days
 13. Cycle Stock = (PS x Qty / 365) x Cycle Stock Days
 14. Payables (DPO) = (PS x Qty / 365) x Payment Terms Days  [reduces NWC]
 15. Total NWC = GIT + Safety Stock + Cycle Stock - Payables
 16. Delta NWC = NWC(location) - NWC(base)
 17. NWC Carrying Cost (annual) = Delta NWC x Total Carrying Cost %
     Total Carrying Cost % = Capital Cost (WACC) + Risk Cost + Storage & Handling + Service Cost
 18. NWC Carrying Cost (per unit) = annual NWC cost / Qty
 19. Adjusted OP = OP - NWC carrying cost per unit
"""
from __future__ import annotations
from typing import Optional
from landed_cost.models import FactoryAssumptions, ItemInputs


def compute_location(
    inputs: ItemInputs,
    factory: FactoryAssumptions,
    is_base: bool = False,
    overrides: Optional[dict] = None,
    lead_time_days: Optional[int] = None,
    base_lead_time_days: Optional[int] = None,
    cost_of_capital: float = 0.0,
    safety_stock_days: float = 0.0,
    base_safety_stock_days: float = 0.0,
    cycle_stock_days: float = 0.0,
    base_cycle_stock_days: float = 0.0,
    payment_terms_days: float = 0.0,
    base_payment_terms_days: float = 0.0,
) -> Optional[dict]:
    """Compute the full landed-cost breakdown for one item x one factory.

    Args:
        inputs:                  Per-item cost data.
        factory:                 Factory cost assumptions.
        is_base:                 True for the base-case factory.
        overrides:               Optional per-factory cost overrides.
        lead_time_days:          Transit days from this factory to target market.
        base_lead_time_days:     Transit days from base factory (for delta calc).
        cost_of_capital:         Total annual carrying cost rate as a decimal (e.g. 0.18 = 18%).
        safety_stock_days:       Days of safety stock held for this factory.
        base_safety_stock_days:  Days of safety stock for the base factory.
        cycle_stock_days:        Average production cycle stock in days.
        base_cycle_stock_days:   Cycle stock days for the base factory.
        payment_terms_days:      Supplier payment terms (DPO) in days.
        base_payment_terms_days: DPO for the base factory.

    Returns a dict with all per-unit metrics, annual metrics, NWC impact,
    and metadata, or ``None`` when the factory's VA ratio is missing.
    """
    ns = inputs.net_sales_per_unit

    if is_base:
        mat = inputs.material
        vva = inputs.variable_va
        fva = inputs.fixed_va
    else:
        if factory.va_ratio is None:
            return None
        ov = overrides or {}
        mat = ov.get("material", inputs.material)
        vva = ov.get("variable_va", inputs.variable_va * factory.va_ratio)
        fva = ov.get("fixed_va", inputs.fixed_va * factory.va_ratio)

    sc = mat + vva + fva
    ps = sc * factory.ps_index

    # Actual Cost is an informational metric — it shows the full manufacturing
    # cost after MCL loading but is NOT subtracted in the OP formula, which
    # uses PS (Price Standard) as the cost baseline instead.
    ac = ps * (factory.mcl_pct / 100)

    sa = ns * factory.sa_pct
    tar = (factory.tpl / 100) * ps * factory.tariff_pct
    dut = (factory.tpl / 100) * ps * factory.duties_pct
    trn = ps * factory.transport_pct

    op = ns - ps - sa - tar - dut - trn
    om = op / ns if ns else 0

    qty = inputs.net_sales_qty

    # ── NWC (Net Working Capital) Impact ────────────────────
    # All inventory components valued at PS (transfer price).
    # Daily cost flow = PS x Qty / 365
    lt = lead_time_days
    base_lt = base_lead_time_days
    daily_flow = (ps * qty / 365.0) if qty > 0 else 0.0

    # 1. Goods-in-Transit
    git_value = daily_flow * lt if lt is not None else 0.0
    delta_lt = (lt - base_lt) if (lt is not None and base_lt is not None) else 0
    delta_git = daily_flow * delta_lt

    # 2. Safety Stock (optional)
    ss_value = daily_flow * safety_stock_days
    delta_ss = daily_flow * (safety_stock_days - base_safety_stock_days)

    # 3. Cycle Stock (optional)
    cs_value = daily_flow * cycle_stock_days
    delta_cs = daily_flow * (cycle_stock_days - base_cycle_stock_days)

    # 4. Payment Terms / DPO (optional) — reduces NWC (longer DPO = benefit)
    pt_value = daily_flow * payment_terms_days
    delta_pt = daily_flow * (payment_terms_days - base_payment_terms_days)

    # Total NWC = GIT + Safety Stock + Cycle Stock - Payables
    total_nwc = git_value + ss_value + cs_value - pt_value
    # Delta NWC vs base (payables delta subtracted: higher DPO = lower NWC)
    delta_nwc = delta_git + delta_ss + delta_cs - delta_pt

    # Annual carrying cost of the incremental working capital
    nwc_carrying_cost_annual = delta_nwc * cost_of_capital

    # Per-unit NWC carrying cost
    nwc_carrying_cost_per_unit = nwc_carrying_cost_annual / qty if qty > 0 else 0.0

    # Adjusted operating profit (includes NWC cost)
    adj_op = op - nwc_carrying_cost_per_unit
    adj_om = adj_op / ns if ns else 0

    return {
        "name": factory.name,
        "country": factory.country,
        # Per-unit cost components
        "material": mat,
        "variable_va": vva,
        "fixed_va": fva,
        "sc": sc,
        "ps": ps,
        "actual_cost": ac,
        "ns_per_unit": ns,
        "sa": sa,
        "tariff": tar,
        "duties": dut,
        "transport": trn,
        "op": op,
        "om": om,
        # NWC impact
        "lead_time_days": lt,
        "delta_lead_time": delta_lt,
        "git_value": git_value,
        "delta_git": delta_git,
        "safety_stock_days": safety_stock_days,
        "safety_stock_value": ss_value,
        "delta_safety_stock": delta_ss,
        "cycle_stock_days": cycle_stock_days,
        "cycle_stock_value": cs_value,
        "delta_cycle_stock": delta_cs,
        "payment_terms_days": payment_terms_days,
        "payables_value": pt_value,
        "delta_payables": delta_pt,
        "total_nwc": total_nwc,
        "delta_nwc": delta_nwc,
        "nwc_carrying_cost_annual": nwc_carrying_cost_annual,
        "nwc_carrying_cost_per_unit": nwc_carrying_cost_per_unit,
        "adj_op": adj_op,
        "adj_om": adj_om,
        # Annual aggregates
        "annual_rev": ns * qty,
        "annual_cost": (ps + sa + tar + dut + trn) * qty,
        "annual_op": op * qty,
        "annual_adj_op": adj_op * qty,
        "annual_nwc_cost": nwc_carrying_cost_annual,
    }


def compute_sensitivity(
    inputs: ItemInputs,
    factory: FactoryAssumptions,
    parameter: str,
    steps: list[float],
    is_base: bool = False,
    overrides: Optional[dict] = None,
) -> list[dict]:
    """Run compute_location across a range of values for *parameter*.

    ``parameter`` must be an attribute of FactoryAssumptions (e.g. "va_ratio",
    "transport_pct") or one of the ItemInputs cost fields ("material",
    "variable_va", "fixed_va", "net_sales_value").

    ``steps`` is a list of absolute values for the parameter.

    Returns a list of result dicts (one per step), each augmented with
    ``"param_name"`` and ``"param_value"`` keys.
    """
    results: list[dict] = []
    factory_attrs = {
        "va_ratio", "ps_index", "mcl_pct", "sa_pct",
        "tpl", "tariff_pct", "duties_pct", "transport_pct",
    }
    input_attrs = {"material", "variable_va", "fixed_va", "net_sales_value"}

    if parameter not in factory_attrs and parameter not in input_attrs:
        raise ValueError(
            f"Unknown parameter '{parameter}'. "
            f"Must be one of {sorted(factory_attrs | input_attrs)}."
        )

    for step_val in steps:
        if parameter in factory_attrs:
            from dataclasses import replace
            tweaked_factory = replace(factory, **{parameter: step_val})
            r = compute_location(inputs, tweaked_factory, is_base=is_base, overrides=overrides)
        else:
            from dataclasses import replace
            tweaked_inputs = replace(inputs, **{parameter: step_val})
            r = compute_location(tweaked_inputs, factory, is_base=is_base, overrides=overrides)

        if r is not None:
            r["param_name"] = parameter
            r["param_value"] = step_val
            results.append(r)

    return results
