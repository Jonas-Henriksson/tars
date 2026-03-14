"""Lead-time lookup with fallback estimation.

The matrix stores (origin_country, destination_country) → transit days.
When a pair is missing, ``estimate_lead_time`` uses a region-based heuristic.
"""
from __future__ import annotations
from typing import Optional

# ── REGION CLASSIFICATION ─────────────────────────────────
_REGIONS: dict[str, str] = {
    "Sweden": "europe", "Germany": "europe", "France": "europe",
    "Italy": "europe", "Austria": "europe", "Poland": "europe",
    "Czech Republic": "europe", "Spain": "europe", "Netherlands": "europe",
    "UK": "europe", "Turkey": "europe",
    "USA": "americas", "Mexico": "americas", "Brazil": "americas",
    "Canada": "americas", "Argentina": "americas",
    "China": "asia", "India": "asia", "Japan": "asia",
    "South Korea": "asia", "Thailand": "asia", "Vietnam": "asia",
    "Malaysia": "asia", "Indonesia": "asia",
    "South Africa": "africa", "Australia": "oceania",
}

# Typical transit-day ranges between regions (mid-point estimates)
_INTER_REGION_DAYS: dict[tuple[str, str], int] = {
    ("europe", "europe"): 4,
    ("europe", "americas"): 25,
    ("europe", "asia"): 33,
    ("europe", "africa"): 22,
    ("europe", "oceania"): 38,
    ("americas", "americas"): 8,
    ("americas", "asia"): 28,
    ("americas", "africa"): 30,
    ("americas", "oceania"): 32,
    ("asia", "asia"): 10,
    ("asia", "africa"): 25,
    ("asia", "oceania"): 18,
    ("africa", "africa"): 10,
    ("africa", "oceania"): 30,
    ("oceania", "oceania"): 5,
}
_DOMESTIC_DAYS = 3  # same-country default


# ── KNOWN LEAD-TIME MATRIX ───────────────────────────────
LEAD_TIME_MATRIX: dict[tuple[str, str], int] = {
    # Sweden origins
    ("Sweden", "Sweden"): 2, ("Sweden", "Germany"): 4, ("Sweden", "France"): 5,
    ("Sweden", "USA"): 28, ("Sweden", "China"): 35, ("Sweden", "India"): 32,
    ("Sweden", "Brazil"): 35, ("Sweden", "Mexico"): 30, ("Sweden", "Japan"): 38,
    ("Sweden", "South Korea"): 36, ("Sweden", "UK"): 5, ("Sweden", "Italy"): 6,
    ("Sweden", "Poland"): 3, ("Sweden", "Netherlands"): 4, ("Sweden", "Spain"): 6,
    ("Sweden", "Austria"): 5, ("Sweden", "Czech Republic"): 4,
    ("Sweden", "Canada"): 30, ("Sweden", "Thailand"): 36, ("Sweden", "Australia"): 40,
    ("Sweden", "South Africa"): 28, ("Sweden", "Turkey"): 12,
    # Germany origins
    ("Germany", "Germany"): 2, ("Germany", "Sweden"): 4, ("Germany", "France"): 3,
    ("Germany", "USA"): 25, ("Germany", "China"): 33, ("Germany", "India"): 30,
    ("Germany", "Brazil"): 33, ("Germany", "Mexico"): 28, ("Germany", "Japan"): 36,
    ("Germany", "UK"): 4, ("Germany", "Italy"): 4,
    ("Germany", "Poland"): 3, ("Germany", "Netherlands"): 2, ("Germany", "Spain"): 5,
    ("Germany", "Austria"): 2, ("Germany", "Czech Republic"): 2,
    ("Germany", "South Korea"): 35, ("Germany", "Canada"): 27,
    ("Germany", "Thailand"): 34, ("Germany", "Australia"): 38,
    ("Germany", "South Africa"): 25, ("Germany", "Turkey"): 10,
    # France origins
    ("France", "France"): 2, ("France", "Germany"): 3, ("France", "Sweden"): 5,
    ("France", "USA"): 22, ("France", "China"): 34, ("France", "India"): 28,
    ("France", "Brazil"): 30, ("France", "UK"): 3, ("France", "Mexico"): 25,
    ("France", "Italy"): 3,
    ("France", "Spain"): 3, ("France", "Netherlands"): 3, ("France", "Poland"): 5,
    ("France", "Austria"): 4, ("France", "South Africa"): 24,
    # Italy origins
    ("Italy", "Italy"): 2, ("Italy", "Germany"): 4, ("Italy", "France"): 3,
    ("Italy", "USA"): 24, ("Italy", "China"): 32, ("Italy", "India"): 26,
    ("Italy", "Sweden"): 6, ("Italy", "UK"): 5,
    ("Italy", "Spain"): 4, ("Italy", "Turkey"): 8,
    # China origins
    ("China", "China"): 3, ("China", "USA"): 30, ("China", "Germany"): 33,
    ("China", "Sweden"): 35, ("China", "France"): 34, ("China", "India"): 18,
    ("China", "Japan"): 7, ("China", "South Korea"): 5, ("China", "Brazil"): 40,
    ("China", "Mexico"): 32, ("China", "UK"): 34, ("China", "Italy"): 32,
    ("China", "Thailand"): 8, ("China", "Vietnam"): 6, ("China", "Malaysia"): 7,
    ("China", "Indonesia"): 10, ("China", "Australia"): 18,
    ("China", "Canada"): 28, ("China", "South Africa"): 30,
    # India origins
    ("India", "India"): 3, ("India", "USA"): 32, ("India", "Germany"): 30,
    ("India", "Sweden"): 32, ("India", "China"): 18, ("India", "France"): 28,
    ("India", "Brazil"): 38, ("India", "UK"): 28,
    ("India", "Thailand"): 14, ("India", "Australia"): 22,
    ("India", "South Africa"): 18, ("India", "Japan"): 20,
    # USA origins
    ("USA", "USA"): 3, ("USA", "Germany"): 25, ("USA", "Sweden"): 28,
    ("USA", "France"): 22, ("USA", "China"): 30, ("USA", "India"): 32,
    ("USA", "Mexico"): 5, ("USA", "Brazil"): 18, ("USA", "Canada"): 4,
    ("USA", "UK"): 20, ("USA", "Japan"): 22,
    ("USA", "South Korea"): 24, ("USA", "Australia"): 28,
    # Mexico origins
    ("Mexico", "USA"): 5, ("Mexico", "Mexico"): 2, ("Mexico", "Brazil"): 20,
    ("Mexico", "Germany"): 28, ("Mexico", "Sweden"): 30, ("Mexico", "China"): 32,
    ("Mexico", "Canada"): 7,
    # Brazil origins
    ("Brazil", "Brazil"): 3, ("Brazil", "USA"): 18, ("Brazil", "Germany"): 33,
    ("Brazil", "Sweden"): 35, ("Brazil", "China"): 40, ("Brazil", "Mexico"): 20,
    ("Brazil", "Argentina"): 8,
    # Japan origins
    ("Japan", "Japan"): 2, ("Japan", "USA"): 22, ("Japan", "China"): 7,
    ("Japan", "Germany"): 36, ("Japan", "Sweden"): 38, ("Japan", "South Korea"): 3,
    ("Japan", "Thailand"): 10, ("Japan", "India"): 20, ("Japan", "Australia"): 14,
    # South Korea origins
    ("South Korea", "South Korea"): 2, ("South Korea", "USA"): 24,
    ("South Korea", "China"): 5, ("South Korea", "Japan"): 3,
    ("South Korea", "Germany"): 35, ("South Korea", "Sweden"): 36,
    ("South Korea", "Vietnam"): 6, ("South Korea", "Thailand"): 8,
    # UK origins
    ("UK", "UK"): 2, ("UK", "USA"): 20, ("UK", "Germany"): 4,
    ("UK", "France"): 3, ("UK", "Sweden"): 5, ("UK", "China"): 34,
    ("UK", "India"): 28, ("UK", "South Africa"): 22,
    # Poland origins
    ("Poland", "Poland"): 2, ("Poland", "Germany"): 3, ("Poland", "Sweden"): 4,
    ("Poland", "USA"): 27, ("Poland", "France"): 5, ("Poland", "China"): 34,
    ("Poland", "UK"): 5,
    # Thailand origins
    ("Thailand", "Thailand"): 2, ("Thailand", "USA"): 30, ("Thailand", "China"): 10,
    ("Thailand", "Germany"): 34, ("Thailand", "Sweden"): 36, ("Thailand", "Japan"): 12,
    ("Thailand", "India"): 14, ("Thailand", "Australia"): 16,
    # Vietnam origins
    ("Vietnam", "Vietnam"): 2, ("Vietnam", "USA"): 28, ("Vietnam", "China"): 6,
    ("Vietnam", "Japan"): 10, ("Vietnam", "South Korea"): 8,
    ("Vietnam", "Germany"): 34, ("Vietnam", "Australia"): 16,
    # Australia origins
    ("Australia", "Australia"): 3, ("Australia", "USA"): 28,
    ("Australia", "China"): 18, ("Australia", "Japan"): 14,
    ("Australia", "UK"): 36, ("Australia", "India"): 22,
    # Canada origins
    ("Canada", "Canada"): 3, ("Canada", "USA"): 4, ("Canada", "Mexico"): 7,
    ("Canada", "Germany"): 27, ("Canada", "UK"): 22, ("Canada", "China"): 28,
    # Turkey origins
    ("Turkey", "Turkey"): 2, ("Turkey", "Germany"): 10, ("Turkey", "Sweden"): 12,
    ("Turkey", "USA"): 28, ("Turkey", "UK"): 12, ("Turkey", "Italy"): 8,
    # South Africa origins
    ("South Africa", "South Africa"): 3, ("South Africa", "Germany"): 25,
    ("South Africa", "UK"): 22, ("South Africa", "USA"): 28,
    ("South Africa", "India"): 18, ("South Africa", "China"): 30,
}


def get_lead_time(origin: str, destination: str) -> Optional[int]:
    """Look up transit days for a known country pair. Returns None if not found."""
    return LEAD_TIME_MATRIX.get((origin, destination))


def estimate_lead_time(origin: str, destination: str) -> Optional[int]:
    """Estimate transit days using a region-based heuristic when exact data is missing.

    Falls back to the known matrix first, then uses inter-region midpoint estimates.
    Returns None only if one or both countries are not in the region map.
    """
    exact = get_lead_time(origin, destination)
    if exact is not None:
        return exact

    if origin == destination:
        return _DOMESTIC_DAYS

    r1 = _REGIONS.get(origin)
    r2 = _REGIONS.get(destination)
    if r1 is None or r2 is None:
        return None

    key = (r1, r2) if (r1, r2) in _INTER_REGION_DAYS else (r2, r1)
    return _INTER_REGION_DAYS.get(key)
