"""Core computation engine for landed-cost analysis.

The 8-step cost build-up:
  1. Base costs → Standard Cost (SC) = Material + Variable VA + Fixed VA
  2. VA Ratio scales Variable & Fixed VA to each location's cost level
  3. Price Standard (PS) = SC × PS Index
  4. Actual Cost = PS × (MCL % / 100)  [informational — not used in OP]
  5. S&A = Net Sales per Unit × S&A %
  6. Tariff = (TPL / 100) × PS × Tariff %
  7. Duties = (TPL / 100) × PS × Duties %
  8. Transportation = PS × Transport %
  9. Operating Profit = Net Sales − PS − S&A − Tariff − Duties − Transport
 10. Operating Margin = Operating Profit / Net Sales
"""
from __future__ import annotations
from typing import Optional
from landed_cost.models import FactoryAssumptions, ItemInputs


def compute_location(
    inputs: ItemInputs,
    factory: FactoryAssumptions,
    is_base: bool = False,
    overrides: Optional[dict] = None,
) -> Optional[dict]:
    """Compute the full landed-cost breakdown for one item × one factory.

    Returns a dict with all per-unit metrics, annual metrics, and metadata,
    or ``None`` when the factory's VA ratio is missing (non-base, no ratio).
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
        # Annual aggregates
        "annual_rev": ns * qty,
        "annual_cost": (ps + sa + tar + dut + trn) * qty,
        "annual_op": op * qty,
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
