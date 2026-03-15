"""Data classes for factory assumptions and item inputs."""
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class FactoryAssumptions:
    """Parameters that define a manufacturing location's cost profile.

    Attributes:
        name:          Display name for the factory / location.
        country:       Country where the factory is located (used for lead-time lookup).
        va_ratio:      Scales base Variable & Fixed VA to this location's cost level.
                       ``None`` for the base case (implicitly 1.0×).
        ps_index:      Multiplier applied to Standard Cost to derive Price Standard.
        mcl_pct:       Manufacturing Cost Load as a percentage (e.g. 101.5 = 1.5 % load).
        sa_pct:        Selling & Admin as a fraction of Net Sales (e.g. 0.035 = 3.5 %).
        tpl:           Tax / duty base percentage (typically 100).
        tariff_pct:    Tariff rate applied to ``(TPL / 100) × PS``.
        duties_pct:    Duties rate applied to ``(TPL / 100) × PS``.
        transport_pct: Transportation cost as a fraction of PS.
    """
    name: str = ""
    country: str = ""
    va_ratio: Optional[float] = None
    ps_index: float = 1.0
    mcl_pct: float = 100.0
    sa_pct: float = 0.0
    tpl: float = 100.0
    tariff_pct: float = 0.0
    duties_pct: float = 0.0
    transport_pct: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class ItemInputs:
    """Per-item cost data supplied by the user.

    Attributes:
        item_number:      Unique identifier for the item.
        designation:      Human-readable item description.
        currency:         Reporting currency code.
        destination:      Target market or region.
        date:             Analysis date (informational).
        comment:          Free-text scope / reason.
        net_sales_value:  Year 1 (base year) annual revenue — used for item comparisons.
        net_sales_qty:    Year 1 (base year) annual units — used for item comparisons.
        material:         Direct material cost per unit (base case).
        variable_va:      Variable value-added cost per unit (base case).
        fixed_va:         Fixed value-added cost per unit (base case).
        sales_projection: Multi-year sales projection as list of
                          ``{"year": int, "value": float, "qty": int}`` dicts.
                          Year 1 must match net_sales_value / net_sales_qty.
                          Used by the investment case to model volume/price growth.
    """
    item_number: str = ""
    designation: str = ""
    currency: str = "SEK"
    destination: str = ""
    date: str = ""
    comment: str = ""
    net_sales_value: float = 0.0
    net_sales_qty: int = 0
    material: float = 0.0
    variable_va: float = 0.0
    fixed_va: float = 0.0
    sales_projection: list = field(default_factory=list)

    @property
    def net_sales_per_unit(self) -> float:
        """Net sales value divided by quantity, or 0 if quantity is zero."""
        return self.net_sales_value / self.net_sales_qty if self.net_sales_qty else 0.0

    def get_projection_for_year(self, year: int) -> tuple[float, int]:
        """Return (net_sales_value, net_sales_qty) for a given projection year.

        Falls back to the last available projection year, or base-year values
        if no projection exists.
        """
        if not self.sales_projection:
            return self.net_sales_value, self.net_sales_qty
        # Find exact year
        for p in self.sales_projection:
            if p["year"] == year:
                return float(p["value"]), int(p["qty"])
        # Beyond projection: use last year
        last = self.sales_projection[-1]
        return float(last["value"]), int(last["qty"])

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        if self.net_sales_qty < 0:
            errors.append("Net sales quantity must be non-negative.")
        if self.net_sales_value < 0:
            errors.append("Net sales value must be non-negative.")
        if self.material < 0:
            errors.append("Material cost must be non-negative.")
        if self.variable_va < 0:
            errors.append("Variable VA must be non-negative.")
        if self.fixed_va < 0:
            errors.append("Fixed VA must be non-negative.")
        return errors
