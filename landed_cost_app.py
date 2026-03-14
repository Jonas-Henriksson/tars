"""
Landed Cost Comparison Model - v6.0
Multi-Item Project-Based Production Cost & Profitability Analysis
Author: Jonas Henriksson — Head of Strategic Planning & Intelligent Hub
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import json
import base64
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import date, datetime
from fpdf import FPDF

# Import from extracted library modules
from landed_cost.models import FactoryAssumptions, ItemInputs
from landed_cost.compute import compute_location, compute_sensitivity
from landed_cost.investment import compute_investment_case
from landed_cost.lead_times import get_lead_time, estimate_lead_time, LEAD_TIME_MATRIX
from landed_cost.formatters import fn, fp, fi, dc
from landed_cost.constants import (
    NAVY, DARK_TEXT, GREY_TEXT, ACCENT_BLUE, BASE_CASE_BG, BORDER,
    GREEN, RED, MUTED, INPUT_BLUE, CURRENCIES, COUNTRIES,
)

# Constants, models, compute engine, formatters, and lead times
# are imported from the landed_cost package (see landed_cost/ directory).


# ── PAGE CONFIG ───────────────────────────────────────────
st.set_page_config(page_title="Landed Cost Comparison Model", layout="wide", initial_sidebar_state="expanded")

# ── BLUE INPUT BORDER CSS HELPER ──────────────────────────
# Builds CSS rules for key-based targeting (.st-key-{key})
# Fixed keys from main() in A5, dynamic item keys matched via attribute selectors
INPUT_EDITOR_KEYS = [
    "proj_name", "proj_ccy", "proj_tm", "proj_dt",
    "fc_editor", "bf_editor", "coc_editor", "country_editor", "assumption_matrix", "nwc_matrix",
]
_blue_border = f"border-left: 3px solid {INPUT_BLUE} !important; padding-left: 2px;"
_fixed_rules = "\n".join(f"    .st-key-{k} {{ {_blue_border} }}" for k in INPUT_EDITOR_KEYS)
# Dynamic item keys: i0_txt, i1_ns, i2_ov, etc. — use attribute selectors
_dynamic_rules = """    [class*="st-key-"][class*="_txt"] { %(bb)s }
    [class*="st-key-"][class*="_ns"] { %(bb)s }
    [class*="st-key-"][class*="_ov"] { %(bb)s }
    [class*="st-key-"][class*="_inv_matrix"] { %(bb)s }
    [class*="st-key-"][class*="_inv_hz"] { %(bb)s }""" % {"bb": _blue_border}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp {{ font-family: 'Inter', -apple-system, sans-serif; background-color: #ffffff; }}
    .block-container {{ padding: 1.5rem 2.5rem; max-width: 1400px; }}
    #MainMenu, footer {{visibility: hidden;}}
    header {{background: transparent !important;}}
    header [data-testid="stDecoration"] {{display: none;}}
    [data-testid="collapsedControl"] {{background: {NAVY}; border-radius: 4px; padding: 0.25rem;}}
    [data-testid="collapsedControl"] svg {{fill: white !important; color: white !important;}}
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {{
        border-radius: 1px !important; font-size: 0.76rem !important;
        font-family: 'Inter', sans-serif !important; padding: 0.25rem 0.45rem !important;
        border: 1px solid #ccc !important; height: auto !important; min-height: 0 !important;
    }}
    .stNumberInput > div > div {{ border-radius: 1px !important; }}
    .stNumberInput button {{ border-radius: 0 !important; padding: 0 !important; }}
    .stTextInput label, .stNumberInput label, .stSelectbox label {{
        font-size: 0.68rem !important; font-weight: 600 !important; color: {GREY_TEXT} !important;
        letter-spacing: 0.03em; margin-bottom: 0.1rem !important; font-family: 'Inter', sans-serif !important;
        text-transform: uppercase;
    }}
    .stTextInput, .stNumberInput, .stSelectbox {{ margin-bottom: -0.2rem !important; }}
    div[data-testid="stVerticalBlock"] > div {{ gap: 0.25rem; }}

    /* ── IB Header ── */
    .ib-header {{
        background: linear-gradient(135deg, {NAVY} 0%, #001540 100%);
        color: white; padding: 1.1rem 1.8rem 0.9rem; margin: -1.5rem -2.5rem 1.5rem -2.5rem;
        display: flex; align-items: center; justify-content: space-between;
    }}
    .ib-header-left {{ display: flex; flex-direction: column; }}
    .ib-header h1 {{ font-family: 'Inter', sans-serif; font-size: 1.2rem; font-weight: 700; margin: 0 0 0.1rem 0; letter-spacing: -0.01em; }}
    .ib-header .sub {{ font-size: 0.72rem; opacity: 0.75; letter-spacing: 0.04em; }}
    .ib-header .skf-logo {{ height: 32px; opacity: 0.95; }}

    /* ── Sections ── */
    .sec {{ font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 700; color: {NAVY};
        text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 2px solid {NAVY};
        padding-bottom: 0.25rem; margin: 1.6rem 0 0.7rem 0; }}
    .sec-sm {{ font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: {GREY_TEXT};
        text-transform: uppercase; letter-spacing: 0.08em; margin: 0.7rem 0 0.35rem 0; }}

    /* ── IB Tables ── */
    .ib-table {{ width: 100%; border-collapse: collapse; font-size: 0.76rem; font-family: 'Inter', sans-serif; }}
    .ib-table th {{ background: {NAVY}; color: white; font-weight: 600; font-size: 0.67rem;
        text-transform: uppercase; letter-spacing: 0.04em; padding: 0.4rem 0.65rem;
        text-align: right; border-bottom: 2px solid {NAVY}; white-space: nowrap; }}
    .ib-table th:first-child {{ text-align: left; padding-left: 0.7rem; }}
    .ib-table td {{ padding: 0.3rem 0.65rem; text-align: right; border-bottom: 1px solid #eef0f2;
        color: {DARK_TEXT}; font-variant-numeric: tabular-nums; }}
    .ib-table td:first-child {{ text-align: left; font-weight: 500; padding-left: 0.7rem; }}
    .ib-table tr:last-child td {{ border-bottom: none; }}
    .ib-table tr:nth-child(even) td {{ background: #fcfcfd; }}
    .ib-table .row-bold td {{ font-weight: 700; border-top: 1px solid #bbb; background: transparent; }}
    .ib-table .row-subtotal td {{ font-weight: 600; border-top: 1px solid #ddd; background: transparent; }}
    .ib-table .row-separator td {{ border-bottom: none; padding: 0.08rem; background: transparent; }}
    .ib-table .row-double-top td {{ border-top: 3px double #333; font-weight: 700; background: transparent; }}
    .ib-table .indent td:first-child {{ padding-left: 1.4rem; font-weight: 400; color: {GREY_TEXT}; font-size: 0.73rem; }}
    .ib-table .base-case {{ background: {BASE_CASE_BG} !important; }}

    /* ── KPI Cards ── */
    .kpi {{ background: #fafafa; border: 1px solid {BORDER}; border-radius: 1px; padding: 0.7rem 0.9rem; text-align: center; }}
    .kpi .lbl {{ font-size: 0.62rem; color: {GREY_TEXT}; text-transform: uppercase; letter-spacing: 0.06em;
        font-weight: 600; margin-bottom: 0.15rem; }}
    .kpi .val {{ font-size: 1.1rem; font-weight: 700; color: {DARK_TEXT}; font-variant-numeric: tabular-nums; }}
    .kpi .det {{ font-size: 0.65rem; color: {MUTED}; margin-top: 0.1rem; }}

    /* ── Delta Colors ── */
    .delta-pos {{ color: {GREEN} !important; font-weight: 600; }}
    .delta-neg {{ color: #b71c1c !important; font-weight: 600; }}
    .ib-table td.delta-pos {{ color: {GREEN} !important; font-weight: 600; }}
    .ib-table td.delta-neg {{ color: #b71c1c !important; font-weight: 600; }}

    /* ── Callouts ── */
    .callout {{ border-left: 3px solid {NAVY}; padding: 0.5rem 0.9rem; font-size: 0.73rem;
        color: {GREY_TEXT}; background: #fafbfc; margin: 0.5rem 0; line-height: 1.4; }}
    .callout strong {{ color: {DARK_TEXT}; }}

    /* ── Executive Summary ── */
    .exec-summary {{ background: #f8f9fb; border: 1px solid {BORDER}; border-left: 4px solid {NAVY};
        padding: 0.8rem 1.1rem; margin: 0.6rem 0; font-size: 0.76rem; line-height: 1.55;
        font-family: 'Inter', sans-serif; color: {DARK_TEXT}; }}
    .exec-summary .es-title {{ font-size: 0.67rem; font-weight: 700; color: {NAVY}; text-transform: uppercase;
        letter-spacing: 0.08em; margin-bottom: 0.4rem; }}

    /* ── User Guide ── */
    .guide {{ font-family: 'Inter', sans-serif; font-size: 0.8rem; color: {DARK_TEXT}; line-height: 1.75; }}
    .guide h2 {{ font-size: 0.92rem; font-weight: 700; color: {NAVY}; margin: 1.4rem 0 0.4rem 0;
        border-bottom: 1px solid {BORDER}; padding-bottom: 0.25rem; text-transform: uppercase;
        letter-spacing: 0.05em; }}
    .guide h3 {{ font-size: 0.84rem; font-weight: 600; color: {DARK_TEXT}; margin: 0.9rem 0 0.3rem 0; }}
    .guide p {{ margin: 0.3rem 0 0.6rem 0; }}
    .guide .tip {{ background: #e8f4fd; border-left: 3px solid {ACCENT_BLUE}; padding: 0.45rem 0.8rem;
        margin: 0.4rem 0; font-size: 0.76rem; border-radius: 0 2px 2px 0; }}
    .guide .tip strong {{ color: {NAVY}; }}
    .guide .warn {{ background: #fff8e6; border-left: 3px solid #e6a817; padding: 0.45rem 0.8rem;
        margin: 0.4rem 0; font-size: 0.76rem; border-radius: 0 2px 2px 0; }}
    .guide .example {{ background: #f0faf3; border-left: 3px solid {GREEN}; padding: 0.45rem 0.8rem;
        margin: 0.4rem 0; font-size: 0.76rem; border-radius: 0 2px 2px 0; }}
    .guide .term {{ display: inline-block; background: #f0f2f5; padding: 0.08rem 0.4rem;
        border-radius: 2px; font-weight: 600; font-size: 0.76rem; color: {NAVY}; margin: 0.05rem 0; }}
    .guide table {{ width: 100%; border-collapse: collapse; font-size: 0.76rem; margin: 0.4rem 0 0.8rem 0; }}
    .guide table th {{ background: {NAVY}; color: white; font-weight: 600; padding: 0.35rem 0.6rem;
        text-align: left; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.03em; }}
    .guide table td {{ padding: 0.3rem 0.6rem; border-bottom: 1px solid #eef0f2; vertical-align: top; }}
    .guide table tr:nth-child(even) td {{ background: #fcfcfd; }}
    .guide ol, .guide ul {{ margin: 0.2rem 0 0.5rem 1.4rem; padding: 0; }}
    .guide li {{ margin-bottom: 0.25rem; }}

    /* ── Confidentiality Footer ── */
    .conf-footer {{ font-size: 0.6rem; color: {MUTED}; text-align: center; padding: 0.5rem 0; margin-top: 0.5rem;
        border-top: 1px solid #eee; letter-spacing: 0.02em; font-style: italic; }}

    .stCheckbox label span {{ font-size: 0.76rem !important; font-family: 'Inter', sans-serif !important; }}
    div[data-testid="stDataEditor"] td:last-child {{
        background-color: #f8f9fa !important; color: #6c757d !important;
        font-style: italic !important; font-size: 0.73rem !important;
    }}
    div[data-testid="stDataEditor"] th:last-child {{
        background-color: #e9ecef !important; color: #6c757d !important;
    }}
    /* IB Convention: Blue left border on editable data editors via key-based CSS classes */
{_fixed_rules}
{_dynamic_rules}
    .stTabs [data-baseweb="tab-list"] {{ gap: 0px; border-bottom: 2px solid {NAVY}; }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'Inter', sans-serif; font-size: 0.74rem; font-weight: 500;
        padding: 0.45rem 1.1rem; border-radius: 0; text-transform: uppercase;
        letter-spacing: 0.03em;
    }}
    /* ── Sidebar Nav Buttons ── */
    .nav-sep {{
        font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700;
        color: {GREY_TEXT}; text-transform: uppercase; letter-spacing: 0.08em;
        padding: 0.6rem 0 0.2rem 0; margin-top: 0.15rem;
    }}
    section[data-testid="stSidebar"] .stButton {{
        margin-bottom: -0.35rem !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        font-family: 'Inter', sans-serif !important; font-size: 0.76rem !important;
        font-weight: 400 !important; text-align: left !important;
        padding: 0.3rem 0.6rem !important; border-radius: 3px !important;
        letter-spacing: 0.01em !important; justify-content: flex-start !important;
        border: none !important; transition: background 0.15s !important;
        line-height: 1.4 !important; min-height: 0 !important; height: auto !important;
    }}
    section[data-testid="stSidebar"] .stButton > button * {{
        text-align: left !important; justify-content: flex-start !important;
        display: block !important; width: 100% !important;
        font-family: 'Inter', sans-serif !important; font-size: 0.76rem !important;
        font-weight: inherit !important;
    }}
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {{
        background: transparent !important; color: {DARK_TEXT} !important;
    }}
    section[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {{
        background: #f0f2f5 !important;
    }}
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background: #e8edf4 !important; color: {NAVY} !important;
        font-weight: 600 !important; border-left: 3px solid {NAVY} !important;
    }}
    /* Sidebar sub-navigation links */
    .nav-sub {{
        display: block; font-family: 'Inter', sans-serif; font-size: 0.72rem;
        color: {GREY_TEXT}; text-decoration: none; padding: 0.2rem 0 0.2rem 1.2rem;
        line-height: 1.4; transition: color 0.15s;
    }}
    .nav-sub:hover {{ color: {NAVY}; }}

    /* Print optimizations */
    @media print {{
        .stApp {{ background: white !important; }}
        .ib-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        .ib-table th {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    }}
</style>
""", unsafe_allow_html=True)



# Data classes (FactoryAssumptions, ItemInputs), compute engine
# (compute_location, compute_sensitivity), and formatting helpers
# (fn, fp, fi, dc) are imported from landed_cost package.


# ── TABLE BUILDERS ────────────────────────────────────────
def build_cost_table(results, ccy, target_market=None):
    if not results: return ""
    hdr = "".join(f'<th>{r["name"]}</th>' for r in results)
    def row(lbl, key, fmt, cls="", indent=False):
        c = f'class="{cls} {"indent" if indent else ""}"'
        cells = "".join(f'<td class="{"base-case" if i==0 else ""}">{fmt(r[key])}</td>' for i, r in enumerate(results))
        return f'<tr {c}><td>{lbl}</td>{cells}</tr>'
    def delta_row(lbl, key, fmt, cls="", invert=False):
        """Row with conditional red/green formatting comparing each cell vs base."""
        c = f'class="{cls}"'
        base_v = results[0].get(key, 0)
        cells = ""
        for i, r in enumerate(results):
            v = r.get(key, 0)
            if i == 0:
                cells += f'<td class="base-case">{fmt(v)}</td>'
            else:
                diff = v - base_v
                color_diff = -diff if invert else diff
                cell_cls = dc(color_diff) if color_diff != 0 else ""
                cells += f'<td class="{cell_cls}">{fmt(v)}</td>'
        return f'<tr {c}><td>{lbl}</td>{cells}</tr>'
    def sep():
        return f'<tr class="row-separator">{"<td></td>" * (len(results)+1)}</tr>'
    f2 = lambda v: fn(v, 2, dz=False)
    html = f'<table class="ib-table"><thead><tr><th>Per Unit ({ccy})</th>{hdr}</tr></thead><tbody>'
    html += row("Material","material",f2) + row("Variable VA","variable_va",f2) + row("Fixed VA","fixed_va",f2)
    html += row("Standard Cost (SC)","sc",f2,"row-subtotal") + row("Price Standard (PS)","ps",f2)
    html += row("Actual Cost","actual_cost",f2) + sep()
    html += row("Net Sales (Per Unit)","ns_per_unit",f2,"row-subtotal")
    html += row("S&A","sa",lambda v: fn(v,2,acct=True),"",True)
    html += row("Tariff","tariff",lambda v: fn(v,2,acct=True,dz=True),"",True)
    html += row("Duties","duties",lambda v: fn(v,2,acct=True,dz=True),"",True)
    html += row("Transportation","transport",lambda v: fn(v,2,acct=True,dz=True),"",True) + sep()
    html += delta_row("Operating Profit","op",lambda v: fn(v,2,acct=True,dz=True),"row-double-top")
    html += delta_row("Operating Margin","om",lambda v: fp(v,1,dz=False),"row-bold")
    bom = results[0]["om"]
    dash = "\u2013"
    dc_cells = ''.join(f'<td class="{"base-case" if i==0 else dc(r["om"]-bom)}">{dash if i==0 else fp(r["om"]-bom,1,acct=True)}</td>' for i, r in enumerate(results))
    html += f'<tr class="row-bold"><td><em>Delta Margin vs. Base</em></td>{dc_cells}</tr>'
    # NWC impact rows
    has_lt = any(r.get("lead_time_days") is not None for r in results)
    has_ext_nwc = any(r.get("safety_stock_days", 0) > 0 or r.get("cycle_stock_days", 0) > 0 or r.get("payment_terms_days", 0) > 0 for r in results)
    has_any_nwc = has_lt or has_ext_nwc
    if has_any_nwc:
        html += sep()
        html += f'<tr class="row-subtotal"><td colspan="{len(results)+1}" style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.06em;padding-top:0.5rem;">Net Working Capital Impact</td></tr>'
        if has_ext_nwc:
            # Show component breakdown when extended NWC inputs are used
            html += row("GIT (Transit)","delta_git",lambda v: fn(v,0,acct=True,dz=True),"",True)
            html += row("Safety Stock","delta_safety_stock",lambda v: fn(v,0,acct=True,dz=True),"",True)
            html += row("Cycle Stock","delta_cycle_stock",lambda v: fn(v,0,acct=True,dz=True),"",True)
            html += row("Payment Terms (DPO)","delta_payables",lambda v: fn(-v,0,acct=True,dz=True),"",True)
            html += delta_row("Total Delta NWC","delta_nwc",lambda v: fn(v,0,acct=True),"row-subtotal",invert=True)
        html += delta_row("NWC Carrying Cost / Unit","nwc_carrying_cost_per_unit",lambda v: fn(v,2,acct=True),"indent",invert=True)
        html += delta_row("Adj. Operating Profit","adj_op",lambda v: fn(v,2,acct=True,dz=True),"row-bold")
        html += delta_row("Adj. Operating Margin","adj_om",lambda v: fp(v,1,dz=False),"row-bold")
        adj_bom = results[0]["adj_om"]
        adj_dc_cells = ''.join(f'<td class="{"base-case" if i==0 else dc(r["adj_om"]-adj_bom)}">{dash if i==0 else fp(r["adj_om"]-adj_bom,1,acct=True)}</td>' for i, r in enumerate(results))
        html += f'<tr class="row-bold"><td><em>Adj. Delta Margin vs. Base</em></td>{adj_dc_cells}</tr>'
    # Lead time row
    if target_market:
        base_lt = estimate_lead_time(results[0].get("country",""), target_market)
        lt_cells = ""
        for i, r in enumerate(results):
            lt = estimate_lead_time(r.get("country",""), target_market)
            if lt is not None:
                if i == 0:
                    lt_cells += f'<td class="base-case">{lt} days</td>'
                else:
                    delta = lt - base_lt if base_lt is not None else None
                    d_str = ""
                    if delta is not None and delta != 0:
                        sign = "+" if delta > 0 else ""
                        cls = "delta-neg" if delta > 0 else "delta-pos"
                        d_str = f' <span class="{cls}">({sign}{delta}d)</span>'
                    lt_cells += f'<td>{lt} days{d_str}</td>'
            else:
                lt_cells += f'<td class="{"base-case" if i==0 else ""}">{dash}</td>'
        html += f'<tr class="row-bold"><td>Lead Time to {target_market}</td>{lt_cells}</tr>'
    html += '</tbody></table>'
    return html

def build_annual_table(results, ccy):
    if not results: return ""
    hdr = "".join(f'<th>{r["name"]}</th>' for r in results)
    bop = results[0]["annual_op"]
    def row(lbl, key, fmt, cls=""):
        c = f'class="{cls}"'
        cells = "".join(f'<td class="{"base-case" if i==0 else ""}">{fmt(r[key])}</td>' for i, r in enumerate(results))
        return f'<tr {c}><td>{lbl}</td>{cells}</tr>'
    def delta_row(lbl, key, fmt, cls="", invert=False):
        c = f'class="{cls}"'
        base_v = results[0].get(key, 0)
        cells = ""
        for i, r in enumerate(results):
            v = r.get(key, 0)
            if i == 0:
                cells += f'<td class="base-case">{fmt(v)}</td>'
            else:
                diff = v - base_v
                color_diff = -diff if invert else diff
                cell_cls = dc(color_diff) if color_diff != 0 else ""
                cells += f'<td class="{cell_cls}">{fmt(v)}</td>'
        return f'<tr {c}><td>{lbl}</td>{cells}</tr>'
    html = f'<table class="ib-table"><thead><tr><th>Full Year ({ccy})</th>{hdr}</tr></thead><tbody>'
    html += row("Annual Revenue","annual_rev",lambda v: fi(v,dz=False))
    html += row("Annual Total Cost","annual_cost",lambda v: fi(v,dz=False))
    html += delta_row("Annual Operating Profit","annual_op",lambda v: fi(v,acct=True,dz=True),"row-bold")
    html += row("Operating Margin","om",lambda v: fp(v,1,dz=False),"row-bold")
    dash = "\u2013"
    dc_cells = ''.join(f'<td class="{"base-case" if i==0 else dc(r["annual_op"]-bop)}">{dash if i==0 else fi(r["annual_op"]-bop,acct=True)}</td>' for i, r in enumerate(results))
    html += f'<tr class="row-double-top"><td><em>Delta vs. Base Case (Annual)</em></td>{dc_cells}</tr>'
    # NWC annual impact
    has_lt = any(r.get("lead_time_days") is not None for r in results)
    has_ext_nwc = any(r.get("safety_stock_days", 0) > 0 or r.get("cycle_stock_days", 0) > 0 or r.get("payment_terms_days", 0) > 0 for r in results)
    has_any_nwc = has_lt or has_ext_nwc
    if has_any_nwc:
        def sep():
            return f'<tr class="row-separator">{"<td></td>" * (len(results)+1)}</tr>'
        html += sep()
        html += f'<tr class="row-subtotal"><td colspan="{len(results)+1}" style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.06em;padding-top:0.5rem;">Net Working Capital</td></tr>'
        html += row("Goods in Transit (GIT)","git_value",lambda v: fi(v,dz=False))
        if has_ext_nwc:
            html += row("Safety Stock","safety_stock_value",lambda v: fi(v,dz=False))
            html += row("Cycle Stock","cycle_stock_value",lambda v: fi(v,dz=False))
            html += row("Payables (DPO)","payables_value",lambda v: fi(-v,dz=False))
        html += row("Total NWC","total_nwc",lambda v: fi(v,dz=False),"row-subtotal")
        base_nwc_total = results[0].get("total_nwc", 0)
        delta_nwc_cells = ''.join(
            f'<td class="{"base-case" if i==0 else dc(-(r.get("delta_nwc",0)))}">{dash if i==0 else fi(r.get("delta_nwc",0),acct=True)}</td>'
            for i, r in enumerate(results))
        html += f'<tr class="indent"><td>Delta NWC vs. Base</td>{delta_nwc_cells}</tr>'
        html += delta_row("NWC Carrying Cost (Annual)","annual_nwc_cost",lambda v: fi(v,acct=True),"",invert=True)
        html += delta_row("Adj. Annual OP","annual_adj_op",lambda v: fi(v,acct=True,dz=True),"row-bold")
        html += delta_row("Adj. Operating Margin","adj_om",lambda v: fp(v,1,dz=False),"row-bold")
        base_adj_op = results[0].get("annual_adj_op", 0)
        adj_dc_cells = ''.join(
            f'<td class="{"base-case" if i==0 else dc(r.get("annual_adj_op",0)-base_adj_op)}">{dash if i==0 else fi(r.get("annual_adj_op",0)-base_adj_op,acct=True)}</td>'
            for i, r in enumerate(results))
        html += f'<tr class="row-double-top"><td><em>Adj. Delta vs. Base (Annual)</em></td>{adj_dc_cells}</tr>'
    html += '</tbody></table>'
    return html

def build_charts(results, ccy):
    names = [r["name"] for r in results]
    oms = [r["om"]*100 for r in results]
    ops = [r["annual_op"] for r in results]
    colors = [NAVY if i==0 else ACCENT_BLUE for i in range(len(results))]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Operating Margin by Location", f"Annual Operating Profit ({ccy})"), horizontal_spacing=0.12)
    fig.add_trace(go.Bar(x=names, y=oms, marker_color=colors, text=[f"{v:.1f}%" for v in oms],
        textposition="outside", textfont=dict(size=10, family="Inter", color=DARK_TEXT),
        hovertemplate="%{x}<br>OM: %{y:.1f}%<extra></extra>", showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=names, y=ops, marker_color=colors, text=[fi(v,dz=False) for v in ops],
        textposition="outside", textfont=dict(size=10, family="Inter", color=DARK_TEXT),
        hovertemplate="%{x}<br>OP: %{y:,.0f}<extra></extra>", showlegend=False), row=1, col=2)
    fig.update_layout(height=400, margin=dict(l=40,r=40,t=45,b=60), paper_bgcolor="white",
        plot_bgcolor="white", font=dict(family="Inter", size=10, color=DARK_TEXT))
    # Style subplot titles to match model typography
    for ann in fig.layout.annotations:
        ann.update(font=dict(family="Inter", size=11, color=DARK_TEXT))
    for ax in ["yaxis","yaxis2"]:
        fig.update_layout(**{ax: dict(showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc")})
    fig.update_xaxes(tickangle=0, tickfont=dict(size=10, family="Inter", color=DARK_TEXT))
    fig.update_yaxes(title_text="Margin (%)", row=1, col=1, ticksuffix="%", title_font=dict(size=10, family="Inter"))
    fig.update_yaxes(title_text=ccy, row=1, col=2, title_font=dict(size=10, family="Inter"))
    return fig


# ── WATERFALL (COST BRIDGE) CHART ─────────────────────────────
def build_waterfall_chart(result, ccy):
    """Build an IB-style waterfall from Net Sales down to Operating Profit."""
    ns = result["ns_per_unit"]
    ps = result["ps"]
    sa = result["sa"]
    tar = result["tariff"]
    dut = result["duties"]
    trn = result["transport"]
    nwc = result.get("nwc_carrying_cost_per_unit", 0)
    op = result["op"]

    labels = ["Net Sales", "Price Std.", "S&A", "Tariff", "Duties", "Transport", "NWC Cost", "Op. Profit"]
    values = [ns, -ps, -sa, -tar, -dut, -trn, -nwc, op]
    measures = ["absolute", "relative", "relative", "relative", "relative", "relative", "relative", "total"]

    # Filter out zero-value items (but always keep NS and OP)
    filtered = [(l, v, m) for l, v, m in zip(labels, values, measures) if abs(v) > 0.005 or m in ("absolute", "total")]
    labels, values, measures = zip(*filtered) if filtered else (labels, values, measures)

    colors = {
        "increasing": "#e8f5e9",
        "decreasing": "#ffebee",
        "totals": NAVY if op >= 0 else RED,
    }

    fig = go.Figure(go.Waterfall(
        x=list(labels), y=list(values), measure=list(measures),
        connector=dict(line=dict(color="#ccc", width=1)),
        increasing=dict(marker=dict(color="#e8f5e9", line=dict(color=GREEN, width=1))),
        decreasing=dict(marker=dict(color="#ffebee", line=dict(color=RED, width=1))),
        totals=dict(marker=dict(color=NAVY if op >= 0 else RED, line=dict(color=NAVY if op >= 0 else RED, width=1))),
        textposition="outside",
        text=[fn(abs(v), 2, dz=False) for v in values],
        textfont=dict(size=9, family="Inter", color=DARK_TEXT),
    ))
    fig.update_layout(
        title=dict(text=f"Cost Bridge: {result['name']} ({ccy}/unit)", font=dict(size=11, family="Inter", color=DARK_TEXT), y=0.95),
        height=390, margin=dict(l=40, r=30, t=80, b=50),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter", size=9, color=DARK_TEXT),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title=f"{ccy} per unit", title_font=dict(size=9, family="Inter")),
        xaxis=dict(tickfont=dict(size=9, family="Inter")),
        showlegend=False,
    )
    return fig


# ── TORNADO CHART ─────────────────────────────────────────────
def build_tornado_chart(inputs, factory, is_base, ccy, overrides=None):
    """Build a tornado chart showing which parameters have the largest OM impact."""
    base_result = compute_location(inputs, factory, is_base=is_base, overrides=overrides)
    if base_result is None:
        return None
    base_om = base_result["om"] * 100

    params = [
        ("VA Ratio", "va_ratio", False),
        ("PS Index", "ps_index", False),
        ("S&A %", "sa_pct", True),
        ("Transport %", "transport_pct", True),
        ("Tariff %", "tariff_pct", True),
        ("Duties %", "duties_pct", True),
        ("Material", "material", False),
    ]

    bars = []
    for label, param, is_pct in params:
        if param in ("va_ratio",) and is_base:
            continue
        current = getattr(factory, param, None) or getattr(inputs, param, None)
        if current is None or current == 0:
            if param not in ("material",):
                continue
            current = getattr(inputs, param, 0)
            if current == 0:
                continue

        low_val = current * 0.8
        high_val = current * 1.2

        factory_attrs = {"va_ratio", "ps_index", "mcl_pct", "sa_pct", "tpl", "tariff_pct", "duties_pct", "transport_pct"}
        input_attrs = {"material", "variable_va", "fixed_va", "net_sales_value"}

        if param in factory_attrs:
            from dataclasses import replace
            r_low = compute_location(inputs, replace(factory, **{param: low_val}), is_base=is_base, overrides=overrides)
            r_high = compute_location(inputs, replace(factory, **{param: high_val}), is_base=is_base, overrides=overrides)
        else:
            from dataclasses import replace as rep
            r_low = compute_location(rep(inputs, **{param: low_val}), factory, is_base=is_base, overrides=overrides)
            r_high = compute_location(rep(inputs, **{param: high_val}), factory, is_base=is_base, overrides=overrides)

        if r_low and r_high:
            om_low = r_low["om"] * 100 - base_om
            om_high = r_high["om"] * 100 - base_om
            spread = abs(om_high - om_low)
            bars.append((label, om_low, om_high, spread))

    if not bars:
        return None

    # Sort by spread (largest impact at top)
    bars.sort(key=lambda x: x[3])
    labels = [b[0] for b in bars]
    lows = [b[1] for b in bars]
    highs = [b[2] for b in bars]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=[min(l, h) for l, h in zip(lows, highs)],
        orientation="h", marker=dict(color="#e8f5e9", line=dict(color=GREEN, width=1)),
        name="-20%", hovertemplate="%{y}: %{x:+.2f}pp<extra>-20%</extra>",
    ))
    fig.add_trace(go.Bar(
        y=labels, x=[max(l, h) - min(l, h) for l, h in zip(lows, highs)],
        orientation="h", marker=dict(color="#ffebee", line=dict(color=RED, width=1)),
        name="+20%", base=[min(l, h) for l, h in zip(lows, highs)],
        hovertemplate="%{y}: %{x:+.2f}pp<extra>+20%</extra>",
    ))
    fig.add_vline(x=0, line=dict(color=NAVY, width=1.5, dash="dot"))

    # Add data labels at each bar end: show param direction + OM impact
    # low = OM change when param at -20%, high = OM change when param at +20%
    for i, (label, low, high, _) in enumerate(bars):
        left_v = min(low, high)
        right_v = max(low, high)
        # Determine which scenario is on which side
        left_is_low = (left_v == low)  # True if -20% scenario is on the left
        left_lbl = "−20%" if left_is_low else "+20%"
        right_lbl = "+20%" if left_is_low else "−20%"
        # Color based on OM impact direction (positive = good = green)
        left_color = GREEN if left_v > 0 else RED if left_v < 0 else GREY_TEXT
        right_color = GREEN if right_v > 0 else RED if right_v < 0 else GREY_TEXT
        fig.add_annotation(
            x=left_v, y=label, text=f"{left_lbl}: {left_v:+.1f}pp",
            showarrow=False, xanchor="right", xshift=-4,
            font=dict(size=8, family="Inter", color=left_color),
        )
        fig.add_annotation(
            x=right_v, y=label, text=f"{right_lbl}: {right_v:+.1f}pp",
            showarrow=False, xanchor="left", xshift=4,
            font=dict(size=8, family="Inter", color=right_color),
        )

    fig.update_layout(
        title=dict(text=f"Tornado: OM Sensitivity to ±20% Parameter Changes ({factory.name})<br><span style='font-size:9px;color:#666;font-weight:normal'>Each bar shows the impact on Operating Margin when a single cost parameter is changed by ±20% from its current value</span>", font=dict(size=11, family="Inter", color=DARK_TEXT)),
        height=max(250, 50 * len(bars) + 80), barmode="overlay",
        margin=dict(l=120, r=60, t=60, b=40),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter", size=10, color=DARK_TEXT),
        xaxis=dict(title="Change in OM (percentage points)", showgrid=True, gridcolor="#f0f0f0", zeroline=False, ticksuffix="pp",
                   title_font=dict(size=10, family="Inter"), tickfont=dict(size=10, family="Inter")),
        yaxis=dict(showgrid=False, tickfont=dict(size=10, family="Inter")),
        showlegend=False,
        dragmode=False,
    )
    return fig


# ── EXECUTIVE SUMMARY NARRATIVE ──────────────────────────────
def build_qualitative_summary(qualitative):
    """Build HTML block for qualitative strategic context."""
    if not qualitative:
        return ""
    parts = []
    if qualitative.get("strategic_rationale", "").strip():
        parts.append(f'<tr><td style="font-weight:600;color:{NAVY};white-space:nowrap;vertical-align:top;padding:0.3rem 0.8rem 0.3rem 0;">Strategic Rationale</td><td style="padding:0.3rem 0;">{qualitative["strategic_rationale"].strip()}</td></tr>')
    if qualitative.get("purpose", "").strip():
        parts.append(f'<tr><td style="font-weight:600;color:{NAVY};white-space:nowrap;vertical-align:top;padding:0.3rem 0.8rem 0.3rem 0;">Purpose & Objective</td><td style="padding:0.3rem 0;">{qualitative["purpose"].strip()}</td></tr>')
    if qualitative.get("risk_of_inaction", "").strip():
        parts.append(f'<tr><td style="font-weight:600;color:{NAVY};white-space:nowrap;vertical-align:top;padding:0.3rem 0.8rem 0.3rem 0;">Risk of Inaction</td><td style="padding:0.3rem 0;">{qualitative["risk_of_inaction"].strip()}</td></tr>')
    if qualitative.get("risks", "").strip():
        parts.append(f'<tr><td style="font-weight:600;color:{NAVY};white-space:nowrap;vertical-align:top;padding:0.3rem 0.8rem 0.3rem 0;">Key Risks</td><td style="padding:0.3rem 0;">{qualitative["risks"].strip()}</td></tr>')
    if not parts:
        return ""
    return f"""<div style="background:#fafbfc;border:1px solid {BORDER};border-left:3px solid {NAVY};border-radius:2px;padding:0.7rem 1rem;margin:0.5rem 0 0.8rem 0;font-family:Inter,sans-serif;font-size:0.78rem;color:{DARK_TEXT};line-height:1.6;">
<div style="font-weight:700;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;color:{GREY_TEXT};margin-bottom:0.4rem;">Strategic Context</div>
<table style="border-collapse:collapse;width:100%;">{"".join(parts)}</table>
</div>"""


def build_exec_summary(results, inputs, ccy):
    """Generate an auto-written executive summary paragraph for IB-style reports."""
    if len(results) < 2:
        return ""
    base = results[0]
    ranked = sorted(results[1:], key=lambda r: r["om"], reverse=True)
    best = ranked[0]
    delta_pp = (best["om"] - base["om"]) * 100
    delta_annual = best["annual_op"] - base["annual_op"]

    item_desc = f"{inputs.item_number} ({inputs.designation})" if inputs.item_number else inputs.designation or "this item"

    if delta_pp > 0.05:
        verdict = f'<strong style="color:{GREEN};">{best["name"]}</strong> offers the highest operating margin at <strong>{fp(best["om"],1,dz=False)}</strong>, a <strong style="color:{GREEN};">+{delta_pp:.1f}pp</strong> improvement over the base case ({base["name"]}, {fp(base["om"],1,dz=False)})'
        annual_str = f', translating to an annual profit uplift of <strong style="color:{GREEN};">{fi(delta_annual, dz=False)} {ccy}</strong>' if abs(delta_annual) > 0.5 else ""
    elif delta_pp < -0.05:
        verdict = f'The base case <strong>{base["name"]}</strong> remains the optimal location at <strong>{fp(base["om"],1,dz=False)}</strong> OM. The best alternative ({best["name"]}) trails by <strong style="color:{RED};">{delta_pp:.1f}pp</strong>'
        annual_str = ""
    else:
        verdict = f'All locations deliver comparable margins near <strong>{fp(base["om"],1,dz=False)}</strong>. No material cost advantage exists between {base["name"]} and {best["name"]}'
        annual_str = ""

    # NWC / Goods-in-Transit impact narrative
    has_nwc = any(r.get("lead_time_days") is not None for r in results)
    nwc_str = ""
    if has_nwc:
        adj_ranked = sorted(results[1:], key=lambda r: r.get("adj_om", r["om"]), reverse=True)
        adj_best = adj_ranked[0]
        adj_delta_pp = (adj_best.get("adj_om", adj_best["om"]) - base.get("adj_om", base["om"])) * 100
        nwc_cost = adj_best.get("nwc_carrying_cost_annual", 0)
        delta_lt = adj_best.get("delta_lead_time", 0)

        if abs(nwc_cost) > 0.5:
            nwc_dir = "increases" if nwc_cost > 0 else "releases"
            nwc_impact = f"reduces" if nwc_cost > 0 else "improves"
            nwc_str = (
                f' After adjusting for NWC impact from goods-in-transit ({delta_lt:+d} days vs. base), '
                f'incremental inventory {nwc_dir} <strong>{fi(abs(nwc_cost), dz=False)} {ccy}</strong> in annual carrying cost, '
                f'which {nwc_impact} the adjusted margin to <strong>{fp(adj_best.get("adj_om", adj_best["om"]),1,dz=False)}</strong> '
                f'({adj_delta_pp:+.1f}pp vs. base).'
            )
        elif delta_lt != 0:
            nwc_str = f' Lead time differential of {delta_lt:+d} days has negligible NWC impact at current cost of capital.'

    return f"""<div class="exec-summary">
<div class="es-title">Executive Summary</div>
For {item_desc}, {verdict}{annual_str}.{nwc_str}
Analysis covers {len(results)} manufacturing location{"s" if len(results)>1 else ""} with {ccy} reporting.
</div>"""


# ── SENSITIVITY CHART ────────────────────────────────────────
def build_sensitivity_chart(inputs, factories, base_factory, param_name, param_label, steps, ccy, is_pct=False):
    """Build a line chart showing how OM changes as *param_name* varies across factories."""
    fig = go.Figure()
    colors_cycle = [NAVY, ACCENT_BLUE, GREEN, RED, "#e67e22", "#8e44ad"]

    for idx, factory in enumerate([base_factory] + list(factories)):
        is_base = (idx == 0)
        results = compute_sensitivity(inputs, factory, param_name, steps, is_base=is_base)
        if not results:
            continue
        x_vals = [r["param_value"] * 100 if is_pct else r["param_value"] for r in results]
        y_vals = [r["om"] * 100 for r in results]
        color = colors_cycle[idx % len(colors_cycle)]
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode="lines+markers", name=factory.name,
            line=dict(color=color, width=2 if idx > 0 else 3),
            marker=dict(size=5),
            hovertemplate=f"{factory.name}<br>{param_label}: %{{x:.1f}}{'%' if is_pct else ''}<br>OM: %{{y:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text=f"Sensitivity: Operating Margin vs. {param_label}", font=dict(size=11, family="Inter", color=DARK_TEXT)),
        height=380, margin=dict(l=50, r=30, t=50, b=50),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter", size=10, color=DARK_TEXT),
        xaxis=dict(title=f"{param_label}{' (%)' if is_pct else ''}", showgrid=True, gridcolor="#eee"),
        yaxis=dict(title="Operating Margin (%)", showgrid=True, gridcolor="#eee", ticksuffix="%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ── EXCEL EXPORT ──────────────────────────────────────────────
def export_excel_project(project_data):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        wb = w.book
        hf = wb.add_format({"bg_color":NAVY,"font_color":"white","bold":True,"font_name":"Arial","font_size":9,"align":"center","bottom":2})
        hl = wb.add_format({"bg_color":NAVY,"font_color":"white","bold":True,"font_name":"Arial","font_size":9,"bottom":2})
        lf = wb.add_format({"font_name":"Arial","font_size":9,"font_color":DARK_TEXT})
        lb = wb.add_format({"font_name":"Arial","font_size":9,"font_color":DARK_TEXT,"bold":True})
        nf = wb.add_format({"font_name":"Arial","font_size":9,"num_format":"#,##0.00","align":"center"})
        nb = wb.add_format({"font_name":"Arial","font_size":9,"num_format":"#,##0.00","align":"center","bold":True,"top":1})
        pf = wb.add_format({"font_name":"Arial","font_size":9,"num_format":"0.0%","align":"center","bold":True})
        inf_ = wb.add_format({"font_name":"Arial","font_size":9,"num_format":"#,##0","align":"center"})
        inb = wb.add_format({"font_name":"Arial","font_size":9,"num_format":"#,##0","align":"center","bold":True,"top":1})
        tf = wb.add_format({"font_name":"Arial","font_size":14,"bold":True,"font_color":"white","bg_color":NAVY})
        sf = wb.add_format({"font_name":"Arial","font_size":9,"font_color":"white","bg_color":NAVY})

        for item in project_data:
            results = item["results"]
            inputs = item["inputs"]
            sname = f"{inputs['item_number'] or 'Item'}_{inputs['designation'][:20]}"[:31]
            ws = wb.add_worksheet(sname)
            w.sheets[sname] = ws
            n = len(results)
            ws.merge_range(0,0,0,n,f"Landed Cost: {inputs['item_number']} - {inputs['designation']}",tf)
            dc_ = inputs.get("data_classification", "C3 - Confidential")
            ws.merge_range(1,0,1,n,f"{inputs['currency']} | Destination: {inputs['destination']} | {dc_}",sf)
            ws.set_column(0,0,24)
            for c in range(1,n+1): ws.set_column(c,c,16)
            r=3
            ws.write(r,0,f"Per Unit ({inputs['currency']})",hl)
            for c,res in enumerate(results): ws.write(r,c+1,res["name"],hf)
            r+=1
            for lbl_,key_,cf_ in [("Material","material",nf),("Variable VA","variable_va",nf),("Fixed VA","fixed_va",nf),
                ("Standard Cost","sc",nb),("Price Standard","ps",nf),("Actual Cost","actual_cost",nf),(None,None,None),
                ("Net Sales/Unit","ns_per_unit",nb),("  S&A","sa",nf),("  Tariff","tariff",nf),("  Duties","duties",nf),
                ("  Transport","transport",nf),(None,None,None),("Operating Profit","op",nb),("Operating Margin","om",pf)]:
                if lbl_ is None: r+=1; continue
                ws.write(r,0,lbl_,lb if key_ in ("sc","ns_per_unit","op","om") else lf)
                for c,res in enumerate(results): ws.write(r,c+1,res[key_],cf_)
                r+=1
            # NWC per-unit rows
            has_lt = any(res.get("lead_time_days") is not None for res in results)
            has_ext_nwc = any(res.get("safety_stock_days",0)>0 or res.get("cycle_stock_days",0)>0 or res.get("payment_terms_days",0)>0 for res in results)
            if has_lt or has_ext_nwc:
                r+=1
                if has_ext_nwc:
                    ws.write(r,0,"  Delta GIT",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("delta_git",0),nf)
                    r+=1
                    ws.write(r,0,"  Delta Safety Stock",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("delta_safety_stock",0),nf)
                    r+=1
                    ws.write(r,0,"  Delta Cycle Stock",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("delta_cycle_stock",0),nf)
                    r+=1
                    ws.write(r,0,"  Delta Payables (DPO)",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,-res.get("delta_payables",0),nf)
                    r+=1
                    ws.write(r,0,"Total Delta NWC",lb)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("delta_nwc",0),nb)
                    r+=1
                ws.write(r,0,"NWC Carrying Cost/Unit",lf)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("nwc_carrying_cost_per_unit",0),nf)
                r+=1
                ws.write(r,0,"Adj. Operating Profit",lb)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("adj_op",res["op"]),nb)
                r+=1
                ws.write(r,0,"Adj. Operating Margin",lb)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("adj_om",res["om"]),pf)
            r+=1
            ws.write(r,0,f"Full Year ({inputs['currency']})",hl)
            for c,res in enumerate(results): ws.write(r,c+1,res["name"],hf)
            r+=1
            for lbl_,key_,cf_ in [("Annual Revenue","annual_rev",inf_),("Annual Cost","annual_cost",inf_),
                ("Annual OP","annual_op",inb),("Operating Margin","om",pf)]:
                ws.write(r,0,lbl_,lb if "OP" in lbl_ or "Margin" in lbl_ else lf)
                for c,res in enumerate(results): ws.write(r,c+1,res[key_],cf_)
                r+=1
            bop_=results[0]["annual_op"]
            ws.write(r,0,"Delta vs Base",lb)
            for c,res in enumerate(results): ws.write(r,c+1,"\u2013" if c==0 else res["annual_op"]-bop_,inb if c>0 else inf_)
            # NWC annual rows
            if has_lt or has_ext_nwc:
                r+=1; r+=1
                ws.write(r,0,"Goods in Transit (GIT)",lf)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("git_value",0),inf_)
                if has_ext_nwc:
                    r+=1
                    ws.write(r,0,"Safety Stock",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("safety_stock_value",0),inf_)
                    r+=1
                    ws.write(r,0,"Cycle Stock",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("cycle_stock_value",0),inf_)
                    r+=1
                    ws.write(r,0,"Payables (DPO)",lf)
                    for c,res in enumerate(results): ws.write(r,c+1,-res.get("payables_value",0),inf_)
                    r+=1
                    ws.write(r,0,"Total NWC",lb)
                    for c,res in enumerate(results): ws.write(r,c+1,res.get("total_nwc",0),inb)
                r+=1
                delta_key = "delta_nwc" if has_ext_nwc else "delta_git"
                delta_label = "Delta NWC vs Base" if has_ext_nwc else "Delta GIT vs Base"
                ws.write(r,0,delta_label,lf)
                for c,res in enumerate(results): ws.write(r,c+1,"\u2013" if c==0 else res.get(delta_key,0),inf_ if c==0 else inb)
                r+=1
                ws.write(r,0,"NWC Carrying Cost (Annual)",lf)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("annual_nwc_cost",0),inf_)
                r+=1
                ws.write(r,0,"Adj. Annual OP",lb)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("annual_adj_op",res["annual_op"]),inb)
                r+=1
                ws.write(r,0,"Adj. Operating Margin",lb)
                for c,res in enumerate(results): ws.write(r,c+1,res.get("adj_om",res["om"]),pf)
                r+=1
                base_adj_op = results[0].get("annual_adj_op", results[0]["annual_op"])
                ws.write(r,0,"Adj. Delta vs Base",lb)
                for c,res in enumerate(results): ws.write(r,c+1,"\u2013" if c==0 else res.get("annual_adj_op",res["annual_op"])-base_adj_op,inb if c>0 else inf_)

            # Investment analysis rows
            inv_data = item.get("investment", [])
            has_inv_data = any(ic.get("total_investment", 0) > 0 for ic in inv_data)
            if has_inv_data and len(results) >= 2:
                r+=2
                ws.write(r,0,"Transfer Investment",hl)
                for c,res in enumerate(results): ws.write(r,c+1,res["name"] if c>0 else "",hf if c>0 else hl)
                r+=1
                inv_by_name = {ic["factory_name"]: ic for ic in inv_data}
                for lbl_,key_ in [("CAPEX","capex"),("OPEX","opex"),("Restructuring","restructuring"),("Total Investment","total_investment")]:
                    ws.write(r,0,lbl_,lb if "Total" in lbl_ else lf)
                    ws.write(r,1,"\u2013",inf_)
                    for c,res in enumerate(results[1:],2):
                        ic = inv_by_name.get(res["name"],{})
                        ws.write(r,c,ic.get(key_,0),inb if "Total" in lbl_ else inf_)
                    r+=1
                r+=1
                ws.write(r,0,"Annual Savings",lf)
                ws.write(r,1,"\u2013",inf_)
                for c,res in enumerate(results[1:],2):
                    ic = inv_by_name.get(res["name"],{})
                    ws.write(r,c,ic.get("annual_savings",0),inb)
                r+=1
                for lbl_,key_ in [("NPV","npv"),("IRR","irr"),("Simple Payback (yrs)","simple_payback"),("Discounted Payback (yrs)","discounted_payback")]:
                    ws.write(r,0,lbl_,lb)
                    ws.write(r,1,"\u2013",inf_)
                    for c,res in enumerate(results[1:],2):
                        ic = inv_by_name.get(res["name"],{})
                        v = ic.get(key_)
                        if v is not None:
                            if key_ == "irr":
                                ws.write(r,c,v,pf)
                            else:
                                ws.write(r,c,v,inb if key_=="npv" else nf)
                        else:
                            ws.write(r,c,"\u2013",inf_)
                    r+=1

            # Qualitative context
            qual = item.get("qualitative", {})
            has_qual = any(v.strip() for v in qual.values()) if qual else False
            if has_qual:
                r+=2
                wf = wb.add_format({"font_name":"Arial","font_size":9,"text_wrap":True,"font_color":DARK_TEXT,"valign":"top"})
                ws.write(r,0,"Strategic Context",hl)
                ws.merge_range(r,1,r,n,"",hl)
                r+=1
                for q_key, q_label in [("strategic_rationale","Strategic Rationale"),("purpose","Purpose & Objective"),
                    ("risk_of_inaction","Risk of Inaction"),("risks","Key Risks & Mitigations")]:
                    txt = qual.get(q_key, "").strip()
                    if txt:
                        ws.write(r,0,q_label,lb)
                        ws.merge_range(r,1,r,n,txt,wf) if n > 1 else ws.write(r,1,txt,wf)
                        r+=1

        # Summary sheet
        if len(project_data) > 1:
            ws = wb.add_worksheet("Portfolio Summary")
            w.sheets["Portfolio Summary"] = ws
            ws.merge_range(0,0,0,5,"Portfolio Summary",tf)
            ws.set_column(0,0,30)
            ws.set_column(1,5,18)
            r=2
            fnames = set()
            for item in project_data:
                for res in item["results"]:
                    fnames.add(res["name"])
            fnames = sorted(fnames)
            ws.write(r,0,"Item",hl)
            for c,fn_ in enumerate(fnames): ws.write(r,c+1,fn_,hf)
            r+=1
            for item in project_data:
                lbl = f"{item['inputs']['item_number']} - {item['inputs']['designation']}"
                ws.write(r,0,lbl,lf)
                for c,fn_ in enumerate(fnames):
                    match = [res for res in item["results"] if res["name"]==fn_]
                    if match: ws.write(r,c+1,match[0]["annual_op"],inb)
                r+=1
            r+=1
            ws.write(r,0,"Total Annual OP",lb)
            for c,fn_ in enumerate(fnames):
                total = sum(res["annual_op"] for item in project_data for res in item["results"] if res["name"]==fn_)
                ws.write(r,c+1,total,inb)

    buf.seek(0)
    return buf


# ── PDF EXPORT ────────────────────────────────────────────────
class IBPitchPDF(FPDF):
    """Custom FPDF with IB-style headers and footers."""

    def __init__(self, project_name="", ccy="", data_classification="C3 - Confidential", **kwargs):
        super().__init__(orientation="L", unit="mm", format="A4", **kwargs)
        self._project_name = project_name
        self._ccy = ccy
        self._dc = data_classification
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 6)
        self.set_text_color(153, 153, 153)
        self.cell(0, 4, f"SKF  |  Landed Cost Analysis  |  {self._project_name}  |  {self._ccy}", align="L")
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 287, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 287, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "I", 5.5)
        self.set_text_color(153, 153, 153)
        self.cell(0, 4, f"{self._dc}  -  SKF Group  -  Strategic Planning & Intelligent Hub", align="L")
        self.cell(0, 4, f"Page {self.page_no()}", align="R")


def export_pdf_project(all_results, ccy, project_name):
    dc_label = all_results[0]["inputs"].get("data_classification", "C3 - Confidential") if all_results else "C3 - Confidential"
    pdf = IBPitchPDF(project_name=project_name, ccy=ccy, data_classification=dc_label)
    navy_r, navy_g, navy_b = 0, 32, 96
    white_r, white_g, white_b = 255, 255, 255
    dark_r, dark_g, dark_b = 26, 26, 46
    base_bg_r, base_bg_g, base_bg_b = 242, 242, 242
    green_r, green_g, green_b = 13, 104, 50
    red_r, red_g, red_b = 192, 57, 43

    def add_page_header(pdf, title, subtitle=""):
        pdf.set_fill_color(navy_r, navy_g, navy_b)
        pdf.set_text_color(white_r, white_g, white_b)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, title, ln=True, fill=True)
        if subtitle:
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 5, subtitle, ln=True, fill=True)
        pdf.set_text_color(dark_r, dark_g, dark_b)
        pdf.ln(3)

    def add_table(pdf, headers, rows, col_widths, bold_rows=None, base_col=0):
        bold_rows = bold_rows or []
        pdf.set_font("Helvetica", "B", 6.5)
        pdf.set_fill_color(navy_r, navy_g, navy_b)
        pdf.set_text_color(white_r, white_g, white_b)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 5.5, h, border=0, align="L" if i == 0 else "R", fill=True)
        pdf.ln()
        pdf.set_text_color(dark_r, dark_g, dark_b)
        for ri, row in enumerate(rows):
            is_bold = ri in bold_rows
            pdf.set_font("Helvetica", "B" if is_bold else "", 6.5)
            # Alternating row shading
            if ri % 2 == 0 and ri not in bold_rows:
                pdf.set_fill_color(250, 251, 252)
                fill = True
            else:
                fill = False
            for ci, val in enumerate(row):
                if ci == 1:
                    pdf.set_fill_color(base_bg_r, base_bg_g, base_bg_b)
                    pdf.cell(col_widths[ci], 4.5, str(val), border=0, align="R", fill=True)
                else:
                    pdf.cell(col_widths[ci], 4.5, str(val), border=0, align="L" if ci == 0 else "R", fill=fill and ci > 0)
            pdf.ln()
            # Draw line under bold rows
            if is_bold:
                y = pdf.get_y()
                pdf.set_draw_color(180, 180, 180)
                pdf.line(10, y, sum(col_widths) + 10, y)

    # Cover page
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(navy_r, navy_g, navy_b)
    pdf.cell(0, 14, "Landed Cost Analysis", align="C", ln=True)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(108, 117, 125)
    pdf.cell(0, 8, project_name, align="C", ln=True)
    pdf.ln(6)
    pdf.set_draw_color(navy_r, navy_g, navy_b)
    pdf.set_line_width(0.8)
    pdf.line(100, pdf.get_y(), 197, pdf.get_y())
    pdf.ln(8)
    # Data classification from first item (project-level)
    dc_label = all_results[0]["inputs"].get("data_classification", "C3 - Confidential") if all_results else "C3 - Confidential"

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"{ccy}  |  {len(all_results)} Item{'s' if len(all_results)!=1 else ''}  |  {dc_label}", align="C", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, date.today().strftime("%B %d, %Y"), align="C", ln=True)
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(navy_r, navy_g, navy_b)
    pdf.cell(0, 6, "SKF", align="C", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(108, 117, 125)
    pdf.cell(0, 5, "Strategic Planning & Intelligent Hub", align="C", ln=True)

    # PDF-safe formatters: use ASCII hyphen instead of en-dash (Helvetica can't encode \u2013)
    f2 = lambda v: f"{v:,.2f}" if v is not None else "-"
    fp_ = lambda v: f"{v*100:.1f}%" if v is not None else "-"
    fi_ = lambda v: f"{v:,.0f}" if v is not None else "-"

    for item in all_results:
        pdf.add_page()
        inp = item["inputs"]
        results = item["results"]
        add_page_header(pdf, f"{inp['item_number']} - {inp['designation']}", f"{ccy}  |  Destination: {inp.get('destination','')}")

        n = len(results)
        lw = 48
        cw = int((297 - 20 - lw) / n) if n else 40
        col_widths = [lw] + [cw] * n
        headers = [f"Per Unit ({ccy})"] + [r["name"] for r in results]

        cost_rows = []
        for lbl, key in [("Material","material"),("Variable VA","variable_va"),("Fixed VA","fixed_va"),
            ("Standard Cost","sc"),("Price Standard","ps"),("Actual Cost","actual_cost"),("",""),
            ("Net Sales/Unit","ns_per_unit"),("  S&A","sa"),("  Tariff","tariff"),("  Duties","duties"),
            ("  Transport","transport"),("",""),("Operating Profit","op")]:
            if lbl == "": cost_rows.append([""] * (n+1)); continue
            cost_rows.append([lbl] + [f2(r[key]) for r in results])
        cost_rows.append(["Operating Margin"] + [fp_(r["om"]) for r in results])
        bom = results[0]["om"]
        cost_rows.append(["Delta vs Base"] + ["-"] + [fp_(r["om"]-bom) for r in results[1:]])
        nwc_bold = []
        has_lt = any(r.get("lead_time_days") is not None for r in results)
        has_ext_nwc_pdf = any(r.get("safety_stock_days",0)>0 or r.get("cycle_stock_days",0)>0 or r.get("payment_terms_days",0)>0 for r in results)
        if has_lt or has_ext_nwc_pdf:
            cost_rows.append([""] * (n+1))
            if has_ext_nwc_pdf:
                cost_rows.append(["  Delta GIT"] + [fi_(r.get("delta_git",0)) for r in results])
                cost_rows.append(["  Delta Safety Stock"] + [fi_(r.get("delta_safety_stock",0)) for r in results])
                cost_rows.append(["  Delta Cycle Stock"] + [fi_(r.get("delta_cycle_stock",0)) for r in results])
                cost_rows.append(["  Delta Payables (DPO)"] + [fi_(-r.get("delta_payables",0)) for r in results])
                cost_rows.append(["Total Delta NWC"] + [fi_(r.get("delta_nwc",0)) for r in results])
            cost_rows.append(["NWC Carrying Cost/Unit"] + [f2(r.get("nwc_carrying_cost_per_unit",0)) for r in results])
            cost_rows.append(["Adj. Operating Profit"] + [f2(r.get("adj_op",r["op"])) for r in results])
            cost_rows.append(["Adj. Operating Margin"] + [fp_(r.get("adj_om",r["om"])) for r in results])
            adj_bom = results[0].get("adj_om", results[0]["om"])
            cost_rows.append(["Adj. Delta vs Base"] + ["-"] + [fp_(r.get("adj_om",r["om"])-adj_bom) for r in results[1:]])
            nwc_bold = [len(cost_rows)-3, len(cost_rows)-2, len(cost_rows)-1]
            if has_ext_nwc_pdf:
                nwc_bold.append(len(cost_rows)-5)  # Total Delta NWC row
        add_table(pdf, headers, cost_rows, col_widths, bold_rows=[3,7,13,14,15]+nwc_bold)

        pdf.ln(4)
        annual_headers = [f"Full Year ({ccy})"] + [r["name"] for r in results]
        annual_rows = [
            ["Annual Revenue"] + [fi_(r["annual_rev"]) for r in results],
            ["Annual Cost"] + [fi_(r["annual_cost"]) for r in results],
            ["Annual OP"] + [fi_(r["annual_op"]) for r in results],
            ["Operating Margin"] + [fp_(r["om"]) for r in results],
        ]
        bop = results[0]["annual_op"]
        annual_rows.append(["Delta vs Base"] + ["-"] + [fi_(r["annual_op"]-bop) for r in results[1:]])
        nwc_annual_bold = []
        if has_lt or has_ext_nwc_pdf:
            annual_rows.append([""] * (n+1))
            annual_rows.append(["Goods in Transit (GIT)"] + [fi_(r.get("git_value",0)) for r in results])
            if has_ext_nwc_pdf:
                annual_rows.append(["Safety Stock"] + [fi_(r.get("safety_stock_value",0)) for r in results])
                annual_rows.append(["Cycle Stock"] + [fi_(r.get("cycle_stock_value",0)) for r in results])
                annual_rows.append(["Payables (DPO)"] + [fi_(-r.get("payables_value",0)) for r in results])
                annual_rows.append(["Total NWC"] + [fi_(r.get("total_nwc",0)) for r in results])
            delta_key_pdf = "delta_nwc" if has_ext_nwc_pdf else "delta_git"
            delta_label_pdf = "Delta NWC vs Base" if has_ext_nwc_pdf else "Delta GIT vs Base"
            annual_rows.append([delta_label_pdf] + ["-"] + [fi_(r.get(delta_key_pdf,0)) for r in results[1:]])
            annual_rows.append(["NWC Carrying Cost (Annual)"] + [fi_(r.get("annual_nwc_cost",0)) for r in results])
            annual_rows.append(["Adj. Annual OP"] + [fi_(r.get("annual_adj_op",r["annual_op"])) for r in results])
            annual_rows.append(["Adj. Operating Margin"] + [fp_(r.get("adj_om",r["om"])) for r in results])
            base_adj_op = results[0].get("annual_adj_op", results[0]["annual_op"])
            annual_rows.append(["Adj. Delta vs Base"] + ["-"] + [fi_(r.get("annual_adj_op",r["annual_op"])-base_adj_op) for r in results[1:]])
            nwc_annual_bold = [len(annual_rows)-3, len(annual_rows)-2, len(annual_rows)-1]
            if has_ext_nwc_pdf:
                # Bold the Total NWC row
                total_nwc_idx = len(annual_rows) - 7  # Total NWC is 7 rows back from end
                nwc_annual_bold.append(total_nwc_idx)
        add_table(pdf, annual_headers, annual_rows, col_widths, bold_rows=[2,3,4]+nwc_annual_bold)

        # Investment analysis in PDF
        inv_data = item.get("investment", [])
        has_inv_pdf = any(ic.get("total_investment", 0) > 0 for ic in inv_data)
        if has_inv_pdf and len(results) >= 2:
            pdf.ln(4)
            inv_headers = [f"Investment ({ccy})"] + [r["name"] for r in results]
            inv_rows = []
            inv_by_name = {ic["factory_name"]: ic for ic in inv_data}
            for lbl_, key_ in [("CAPEX","capex"),("OPEX","opex"),("Restructuring","restructuring"),("Total Investment","total_investment")]:
                row_data = [lbl_, "-"]
                for r in results[1:]:
                    ic = inv_by_name.get(r["name"],{})
                    row_data.append(fi_(ic.get(key_,0)))
                inv_rows.append(row_data)
            inv_rows.append([""] * (n+1))
            sav_row = ["Annual Savings", "-"]
            for r in results[1:]:
                ic = inv_by_name.get(r["name"],{})
                sav_row.append(fi_(ic.get("annual_savings",0)))
            inv_rows.append(sav_row)
            inv_rows.append([""] * (n+1))
            # Metrics
            npv_row = ["NPV", "-"]
            irr_row = ["IRR", "-"]
            pb_row = ["Simple Payback", "-"]
            dpb_row = ["Disc. Payback", "-"]
            for r in results[1:]:
                ic = inv_by_name.get(r["name"],{})
                npv_row.append(fi_(ic.get("npv",0)))
                irr_v = ic.get("irr")
                irr_row.append(f"{irr_v*100:.1f}%" if irr_v is not None else "-")
                pb_v = ic.get("simple_payback")
                pb_row.append(f"{pb_v:.1f} yrs" if pb_v is not None else "-")
                dpb_v = ic.get("discounted_payback")
                dpb_row.append(f"{dpb_v:.1f} yrs" if dpb_v is not None else "-")
            inv_rows.extend([npv_row, irr_row, pb_row, dpb_row])
            add_table(pdf, inv_headers, inv_rows, col_widths, bold_rows=[3, 5, 8, 9, 10, 11])

        # Qualitative context in PDF
        qual = item.get("qualitative", {})
        has_qual_pdf = any(v.strip() for v in qual.values()) if qual else False
        if has_qual_pdf:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(navy_r, navy_g, navy_b)
            pdf.set_text_color(white_r, white_g, white_b)
            pdf.cell(0, 5.5, "Strategic Context", ln=True, fill=True)
            pdf.set_text_color(dark_r, dark_g, dark_b)
            for q_key, q_label in [("strategic_rationale","Strategic Rationale"),("purpose","Purpose & Objective"),
                ("risk_of_inaction","Risk of Inaction"),("risks","Key Risks & Mitigations")]:
                txt = qual.get(q_key, "").strip()
                if txt:
                    pdf.set_font("Helvetica", "B", 6.5)
                    pdf.cell(45, 4.5, q_label, border=0)
                    pdf.set_font("Helvetica", "", 6.5)
                    # Multi-cell for wrapping long text
                    x_start = pdf.get_x()
                    y_start = pdf.get_y()
                    safe_txt = txt.encode("latin-1", "replace").decode("latin-1")
                    pdf.multi_cell(0, 4.5, safe_txt, border=0)
                    pdf.ln(0.5)

    # Portfolio summary page
    if len(all_results) > 1:
        pdf.add_page()
        add_page_header(pdf, "Portfolio Summary", f"{ccy}  |  {project_name}")
        all_fnames = []
        for item in all_results:
            for r in item["results"]:
                if r["name"] not in all_fnames: all_fnames.append(r["name"])
        totals = {fn_: 0.0 for fn_ in all_fnames}
        total_rev = {fn_: 0.0 for fn_ in all_fnames}
        for item in all_results:
            for r in item["results"]:
                totals[r["name"]] += r["annual_op"]
                total_rev[r["name"]] += r["annual_rev"]
        n = len(all_fnames)
        lw = 58
        cw = int((297 - 20 - lw) / n) if n else 40
        col_widths = [lw] + [cw] * n
        headers = ["Item"] + all_fnames
        rows = []
        for item in all_results:
            inp = item["inputs"]
            row = [f"{inp['item_number']} - {inp['designation']}"]
            for fn_ in all_fnames:
                match = [r for r in item["results"] if r["name"] == fn_]
                row.append(fi_(match[0]["annual_op"]) if match else "-")
            rows.append(row)
        rows.append(["Total Annual OP"] + [fi_(totals[fn_]) for fn_ in all_fnames])
        rows.append(["Operating Margin"] + [f"{totals[fn_]/total_rev[fn_]*100:.1f}%" if total_rev[fn_] else "-" for fn_ in all_fnames])
        base_op = totals.get(all_fnames[0], 0) if all_fnames else 0
        rows.append(["Delta vs Base"] + ["-"] + [fi_(totals[fn_]-base_op) for fn_ in all_fnames[1:]])
        base_bold = [len(all_results), len(all_results)+1, len(all_results)+2]

        # NWC-adjusted portfolio rows in PDF
        has_nwc_portfolio = any(
            r.get("lead_time_days") is not None
            for item in all_results for r in item["results"]
        )
        nwc_portfolio_bold = []
        if has_nwc_portfolio:
            adj_totals_pdf = {fn_: 0.0 for fn_ in all_fnames}
            nwc_totals_pdf = {fn_: 0.0 for fn_ in all_fnames}
            for item in all_results:
                for r in item["results"]:
                    adj_totals_pdf[r["name"]] += r.get("annual_adj_op", r["annual_op"])
                    nwc_totals_pdf[r["name"]] += r.get("annual_nwc_cost", 0)
            rows.append([""] * (n+1))
            rows.append(["NWC Carrying Cost (Annual)"] + [fi_(nwc_totals_pdf[fn_]) for fn_ in all_fnames])
            rows.append(["Adj. Total Annual OP"] + [fi_(adj_totals_pdf[fn_]) for fn_ in all_fnames])
            adj_pct_pdf = {fn_: (adj_totals_pdf[fn_]/total_rev[fn_]*100 if total_rev[fn_] else 0) for fn_ in all_fnames}
            rows.append(["Adj. Operating Margin"] + [f"{adj_pct_pdf[fn_]:.1f}%" for fn_ in all_fnames])
            base_adj_pdf = adj_totals_pdf.get(all_fnames[0], 0) if all_fnames else 0
            rows.append(["Adj. Delta vs Base"] + ["-"] + [fi_(adj_totals_pdf[fn_]-base_adj_pdf) for fn_ in all_fnames[1:]])
            nwc_portfolio_bold = [len(rows)-3, len(rows)-2, len(rows)-1]

        add_table(pdf, headers, rows, col_widths, bold_rows=base_bold+nwc_portfolio_bold)

    buf = io.BytesIO()
    buf.write(pdf.output())
    buf.seek(0)
    return buf


# ── EXAMPLE DATA ──────────────────────────────────────────────
EX_BASE = FactoryAssumptions(name="Factory A (Europe)", country="Sweden", va_ratio=None, ps_index=1.038, mcl_pct=101.5, sa_pct=0.035, tpl=100.0, tariff_pct=0.0, duties_pct=0.0, transport_pct=0.0)
EX_FACTORIES = [
    FactoryAssumptions(name="Factory B (Europe)", country="Germany", va_ratio=1.05, ps_index=1.038, mcl_pct=102.0, sa_pct=0.035, tpl=100.0, tariff_pct=0.0, duties_pct=0.0, transport_pct=0.0),
    FactoryAssumptions(name="Factory C (Asia)", country="China", va_ratio=0.72, ps_index=1.025, mcl_pct=99.5, sa_pct=0.038, tpl=100.0, tariff_pct=0.045, duties_pct=0.025, transport_pct=0.025),
    FactoryAssumptions(name="Factory D (Europe)", country="France", va_ratio=1.15, ps_index=1.042, mcl_pct=101.0, sa_pct=0.036, tpl=100.0, tariff_pct=0.0, duties_pct=0.0, transport_pct=0.008),
    FactoryAssumptions(name="Factory E (Americas)", country="USA", va_ratio=0.85, ps_index=1.03, mcl_pct=100.5, sa_pct=0.04, tpl=100.0, tariff_pct=0.035, duties_pct=0.015, transport_pct=0.02)]

EXAMPLE_ITEMS = [
    {"item_number":"1001","designation":"Bearing Assembly XR-200","destination":"Northern Europe",
     "comment":"Annual sourcing review","net_sales_value":121280000.0,"net_sales_qty":2570000,
     "material":18.96,"variable_va":2.26,"fixed_va":2.57},
    {"item_number":"2045","designation":"Seal Kit HT-500","destination":"Northern Europe",
     "comment":"New product launch evaluation","net_sales_value":45600000.0,"net_sales_qty":1200000,
     "material":12.50,"variable_va":1.80,"fixed_va":1.95},
]


# ── SESSION STATE INIT ──────────────────────────────────────────
def init_state():
    if "project_name" not in st.session_state:
        st.session_state.project_name = "New Project"
    if "project_items" not in st.session_state:
        st.session_state.project_items = [{"id": 0}]
    if "next_id" not in st.session_state:
        st.session_state.next_id = 1
    if "ex" not in st.session_state:
        st.session_state.ex = False
    if "active_page" not in st.session_state:
        st.session_state.active_page = "model"


# ── ITEM ANALYSIS RENDERER ───────────────────────────────────────
def render_item(idx, item_id, base_factory_name_shared, factory_col_names_shared, num_factories, ex):
    pfx = f"i{item_id}_"
    today = date.today()

    # Item header
    ex_item = EXAMPLE_ITEMS[idx] if ex and idx < len(EXAMPLE_ITEMS) else None

    txt_data = {
        "Field": ["Item Number", "Designation", "Destination", "Comment"],
        "Value": [
            ex_item["item_number"] if ex_item else "",
            ex_item["designation"] if ex_item else "",
            ex_item["destination"] if ex_item else "",
            ex_item["comment"] if ex_item else "",
        ],
        "Guide": [
            "Unique item identifier",
            "Item name or description",
            "Target market or region",
            "Scope or reason for analysis",
        ]
    }
    txt_df = pd.DataFrame(txt_data).set_index("Field")

    edited_txt = st.data_editor(
        txt_df, use_container_width=True, num_rows="fixed", key=f"{pfx}txt",
        column_config={
            "Value": st.column_config.TextColumn("Value", width=280),
            "Guide": st.column_config.TextColumn("Guide", width=300, disabled=True),
        },
        disabled=["Guide"],
    )

    item_number = str(edited_txt.loc["Item Number", "Value"] or "")
    designation = str(edited_txt.loc["Designation", "Value"] or "")
    destination = str(edited_txt.loc["Destination", "Value"] or "")
    comment = str(edited_txt.loc["Comment", "Value"] or "")

    # Net sales + base costs
    st.markdown('<div class="sec-sm">Net Sales & Base Costs (Per Unit)</div>', unsafe_allow_html=True)

    ns_data = {
        "Field": ["Net Sales (Total Value)", "Net Sales (Quantity)", "Material", "Variable VA", "Fixed VA"],
        "Value": [
            ex_item["net_sales_value"] if ex_item else 0.0,
            ex_item["net_sales_qty"] if ex_item else 0.0,
            ex_item["material"] if ex_item else 0.0,
            ex_item["variable_va"] if ex_item else 0.0,
            ex_item["fixed_va"] if ex_item else 0.0,
        ],
        "Guide": [
            "Total annual revenue for this item",
            "Total annual units produced/sold",
            "Direct material cost per unit at base case",
            "Variable VA cost per unit at base case",
            "Fixed VA cost per unit at base case",
        ]
    }
    ns_df = pd.DataFrame(ns_data).set_index("Field")

    edited_ns = st.data_editor(
        ns_df, use_container_width=True, num_rows="fixed", key=f"{pfx}ns",
        column_config={
            "Value": st.column_config.NumberColumn("Value", format="%,.2f", width=200),
            "Guide": st.column_config.TextColumn("Guide", width=300, disabled=True),
        },
        disabled=["Guide"],
    )

    net_sales_value = float(edited_ns.loc["Net Sales (Total Value)", "Value"] or 0)
    net_sales_qty = int(edited_ns.loc["Net Sales (Quantity)", "Value"] or 0)
    material = float(edited_ns.loc["Material", "Value"] or 0)
    variable_va = float(edited_ns.loc["Variable VA", "Value"] or 0)
    fixed_va = float(edited_ns.loc["Fixed VA", "Value"] or 0)

    inputs = ItemInputs(item_number, designation, st.session_state.get("currency","SEK"),
                        destination, "", comment, net_sales_value, net_sales_qty,
                        material, variable_va, fixed_va)

    if inputs.net_sales_qty == 0 or inputs.net_sales_value == 0:
        st.markdown('<div class="callout">Enter Net Sales values to see results.</div>', unsafe_allow_html=True)
        return None

    # Cost overrides
    st.markdown('<div class="sec-sm">Cost Overrides (Optional)</div>', unsafe_allow_html=True)
    OV_ROWS = ["Material", "Variable VA", "Fixed VA"]
    ov_cols = {cn: [None, None, None] for cn in factory_col_names_shared}
    ov_cols["Guide"] = ["Override material (blank = base)", "Override variable VA (blank = VA Ratio)", "Override fixed VA (blank = VA Ratio)"]
    ov_df = pd.DataFrame(ov_cols, index=OV_ROWS)

    edited_ov = st.data_editor(
        ov_df, use_container_width=True, num_rows="fixed", key=f"{pfx}ov",
        column_config={
            **{cn: st.column_config.NumberColumn(cn, format="%.2f") for cn in factory_col_names_shared},
            "Guide": st.column_config.TextColumn("Guide", width=280, disabled=True),
        },
        disabled=["Guide"],
    )

    def get_ov(cn):
        ov = {}
        for key, row_name in [("material","Material"),("variable_va","Variable VA"),("fixed_va","Fixed VA")]:
            v = edited_ov.loc[row_name, cn]
            if v is not None and not pd.isna(v):
                ov[key] = float(v)
        return ov if ov else None

    return {"inputs": inputs, "get_ov": get_ov}


# ── PORTFOLIO SUMMARY ─────────────────────────────────────────
def render_portfolio_summary(all_results, ccy, cost_of_capital=0.08):
    if not all_results:
        st.markdown('<div class="callout">Complete at least one item analysis to see the portfolio summary.</div>', unsafe_allow_html=True)
        return

    st.markdown('<div class="sec">Portfolio Summary</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="callout">Aggregated annual operating profit across all items by factory location ({ccy}).</div>', unsafe_allow_html=True)

    # Collect factory names and totals
    all_fnames = []
    for item in all_results:
        for r in item["results"]:
            if r["name"] not in all_fnames:
                all_fnames.append(r["name"])

    totals = {fn_: 0.0 for fn_ in all_fnames}
    total_rev = {fn_: 0.0 for fn_ in all_fnames}
    for item in all_results:
        for r in item["results"]:
            totals[r["name"]] += r["annual_op"]
            total_rev[r["name"]] += r["annual_rev"]
    op_pct = {fn_: (totals[fn_] / total_rev[fn_] * 100 if total_rev[fn_] else 0) for fn_ in all_fnames}

    # KPI cards
    base_fn = all_fnames[0] if all_fnames else None
    base_op = totals.get(base_fn, 0)
    base_pct = op_pct.get(base_fn, 0)
    ranked = sorted([fn_ for fn_ in all_fnames if fn_ != base_fn], key=lambda fn_: totals[fn_], reverse=True)
    labels = ["Best Location", "2nd Best", "3rd Best"]
    ncards = min(len(ranked), 3) + 1
    cols = st.columns(ncards)
    cols[0].markdown(f'<div style="background:{BASE_CASE_BG};border:1px solid {BORDER};border-radius:2px;padding:0.8rem 1rem;text-align:center;"><div style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.2rem;">Base Case Total OP</div><div style="font-size:1.15rem;font-weight:700;color:{DARK_TEXT};">{fi(base_op, dz=False)}</div><div style="font-size:0.82rem;font-weight:600;color:{DARK_TEXT};margin-top:0.15rem;">{base_fn}</div><div style="font-size:0.7rem;color:{MUTED};margin-top:0.1rem;">OP {base_pct:.1f}%</div></div>', unsafe_allow_html=True)
    for i, fn_ in enumerate(ranked[:3]):
        delta = totals[fn_] - base_op
        is_better = delta > 0
        is_worse = delta < 0
        bdr = f"border-left:3px solid {GREEN};" if is_better else (f"border-left:3px solid {RED};" if is_worse else f"border-left:3px solid {BORDER};")
        d_sign = "+" if delta > 0 else ""
        d_cls = f"color:{GREEN};font-weight:600;" if is_better else (f"color:{RED};font-weight:600;" if is_worse else f"color:{MUTED};")
        cols[i+1].markdown(f'<div style="background:#fafafa;border:1px solid {BORDER};{bdr}border-radius:2px;padding:0.8rem 1rem;text-align:center;"><div style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.2rem;">{labels[i]}</div><div style="font-size:1.15rem;font-weight:700;color:{DARK_TEXT};">{fi(totals[fn_], dz=False)}</div><div style="font-size:0.82rem;font-weight:600;color:{DARK_TEXT};margin-top:0.15rem;">{fn_}</div><div style="font-size:0.7rem;{d_cls}margin-top:0.1rem;">{d_sign}{fi(delta, acct=True)} vs base</div></div>', unsafe_allow_html=True)

    # Summary table with OP %
    hdr = "".join(f'<th>{fn_}</th>' for fn_ in all_fnames)
    html = f'<table class="ib-table"><thead><tr><th>Item</th>{hdr}</tr></thead><tbody>'

    for item in all_results:
        inp = item["inputs"]
        lbl = f"{inp['item_number']} - {inp['designation']}"
        cells = ""
        for fn_ in all_fnames:
            match = [r for r in item["results"] if r["name"] == fn_]
            if match:
                v = match[0]["annual_op"]
                cells += f'<td class="{("base-case" if fn_==all_fnames[0] else "")}">{fi(v, dz=False)}</td>'
            else:
                cells += "<td>\u2013</td>"
        html += f"<tr><td>{lbl}</td>{cells}</tr>"

    tot_cells = "".join(f'<td class="{("base-case" if fn_==all_fnames[0] else "")}">{fi(totals[fn_], dz=False)}</td>' for fn_ in all_fnames)
    html += f'<tr class="row-double-top"><td><strong>Total Annual OP</strong></td>{tot_cells}</tr>'

    pct_cells = "".join(f'<td class="{("base-case" if fn_==all_fnames[0] else "")}">{op_pct[fn_]:.1f}%</td>' for fn_ in all_fnames)
    html += f'<tr class="row-bold"><td><strong>Operating Margin</strong></td>{pct_cells}</tr>'

    dash = "\u2013"
    delta_cells = "".join(
        f'<td class="{("base-case" if fn_==base_fn else dc(totals[fn_]-base_op))}">{dash if fn_==base_fn else fi(totals[fn_]-base_op, acct=True)}</td>'
        for fn_ in all_fnames
    )
    html += f'<tr class="row-bold"><td><em>Delta vs. Base (Total)</em></td>{delta_cells}</tr>'

    # NWC-adjusted portfolio rows
    has_nwc = any(
        r.get("lead_time_days") is not None
        for item in all_results for r in item["results"]
    )
    if has_nwc:
        adj_totals = {fn_: 0.0 for fn_ in all_fnames}
        nwc_totals = {fn_: 0.0 for fn_ in all_fnames}
        for item in all_results:
            for r in item["results"]:
                adj_totals[r["name"]] += r.get("annual_adj_op", r["annual_op"])
                nwc_totals[r["name"]] += r.get("annual_nwc_cost", 0)
        adj_pct = {fn_: (adj_totals[fn_] / total_rev[fn_] * 100 if total_rev[fn_] else 0) for fn_ in all_fnames}
        base_adj = adj_totals.get(base_fn, 0)

        sep_cells = "<td></td>" * (len(all_fnames) + 1)
        html += f'<tr class="row-separator">{sep_cells}</tr>'
        html += f'<tr class="row-subtotal"><td colspan="{len(all_fnames)+1}" style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.06em;padding-top:0.5rem;">NWC Impact (Goods in Transit)</td></tr>'

        nwc_cells = "".join(
            f'<td class="{"base-case" if fn_==base_fn else ""}">{fi(nwc_totals[fn_], acct=True)}</td>'
            for fn_ in all_fnames
        )
        html += f'<tr><td>NWC Carrying Cost (Annual)</td>{nwc_cells}</tr>'

        adj_op_cells = "".join(
            f'<td class="{"base-case" if fn_==base_fn else ""}">{fi(adj_totals[fn_], dz=False)}</td>'
            for fn_ in all_fnames
        )
        html += f'<tr class="row-bold"><td><strong>Adj. Total Annual OP</strong></td>{adj_op_cells}</tr>'

        adj_pct_cells = "".join(
            f'<td class="{"base-case" if fn_==base_fn else ""}">{adj_pct[fn_]:.1f}%</td>'
            for fn_ in all_fnames
        )
        html += f'<tr class="row-bold"><td><strong>Adj. Operating Margin</strong></td>{adj_pct_cells}</tr>'

        adj_delta_cells = "".join(
            f'<td class="{("base-case" if fn_==base_fn else dc(adj_totals[fn_]-base_adj))}">{dash if fn_==base_fn else fi(adj_totals[fn_]-base_adj, acct=True)}</td>'
            for fn_ in all_fnames
        )
        html += f'<tr class="row-bold"><td><em>Adj. Delta vs. Base (Total)</em></td>{adj_delta_cells}</tr>'

    html += "</tbody></table>"

    st.markdown(html, unsafe_allow_html=True)

    # Chart with updated styling
    if len(all_fnames) >= 2:
        colors = [NAVY if i==0 else ACCENT_BLUE for i in range(len(all_fnames))]
        fig = go.Figure(go.Bar(
            x=all_fnames, y=[totals[fn_] for fn_ in all_fnames],
            marker_color=colors,
            text=[fi(totals[fn_], dz=False) for fn_ in all_fnames],
            textposition="outside",
            textfont=dict(size=11, family="Inter", color=DARK_TEXT),
        ))
        fig.update_layout(
            title=dict(text=f"Total Annual OP by Location ({ccy})", font=dict(size=11, family="Inter", color=DARK_TEXT)),
            height=400, margin=dict(l=40,r=40,t=50,b=60),
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="Inter", size=10, color=DARK_TEXT),
            yaxis=dict(showgrid=True, gridcolor="#eee"),
        )
        fig.update_xaxes(tickangle=0, tickfont=dict(size=11, family="Inter", color=DARK_TEXT))
        fig.update_yaxes(title_text=ccy, title_font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False})

    # ── INVESTMENT SUMMARY (Portfolio) ────────────────────────
    has_inv = any(
        ic.get("total_investment", 0) > 0
        for item in all_results
        for ic in item.get("investment", [])
    )
    if has_inv:
        st.markdown(f'<div class="sec-sm">Transfer Investment Summary</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="callout">Aggregated investment metrics across all items by receiving factory ({ccy}).</div>', unsafe_allow_html=True)

        # Collect alt factory names (exclude base)
        alt_fnames = [fn_ for fn_ in all_fnames if fn_ != base_fn]
        if alt_fnames:
            # Aggregate: total investment, total annual savings, combined NPV
            agg_inv = {fn_: 0.0 for fn_ in alt_fnames}
            agg_savings = {fn_: 0.0 for fn_ in alt_fnames}
            agg_capex = {fn_: 0.0 for fn_ in alt_fnames}
            agg_opex = {fn_: 0.0 for fn_ in alt_fnames}
            agg_restr = {fn_: 0.0 for fn_ in alt_fnames}
            for item in all_results:
                for ic in item.get("investment", []):
                    fn_ = ic.get("factory_name", "")
                    if fn_ in alt_fnames:
                        agg_inv[fn_] += ic.get("total_investment", 0)
                        agg_savings[fn_] += ic.get("annual_savings", 0)
                        agg_capex[fn_] += ic.get("capex", 0)
                        agg_opex[fn_] += ic.get("opex", 0)
                        agg_restr[fn_] += ic.get("restructuring", 0)

            # Compute portfolio-level NPV, IRR, payback using aggregated flows
            agg_cases = {}
            for fn_ in alt_fnames:
                agg_cases[fn_] = compute_investment_case(
                    annual_savings=agg_savings[fn_],
                    capex=agg_capex[fn_], opex=agg_opex[fn_], restructuring=agg_restr[fn_],
                    discount_rate=cost_of_capital,
                    horizon_years=10,
                )

            inv_p_hdr = "".join(f'<th>{fn_}</th>' for fn_ in alt_fnames)
            inv_p_html = f'<table class="ib-table"><thead><tr><th>Portfolio Investment ({ccy})</th>{inv_p_hdr}</tr></thead><tbody>'

            def _pr(lbl, vals, cls=""):
                cells = "".join(f'<td>{v}</td>' for v in vals)
                return f'<tr class="{cls}"><td>{lbl}</td>{cells}</tr>'

            inv_p_html += _pr("Total CAPEX", [fi(agg_capex[fn_], dz=True) for fn_ in alt_fnames])
            inv_p_html += _pr("Total OPEX", [fi(agg_opex[fn_], dz=True) for fn_ in alt_fnames])
            inv_p_html += _pr("Total Restructuring", [fi(agg_restr[fn_], dz=True) for fn_ in alt_fnames])
            inv_p_html += _pr("Total Investment", [fi(agg_inv[fn_], dz=False) for fn_ in alt_fnames], "row-subtotal")
            inv_p_html += _pr("Total Annual Savings", [fi(agg_savings[fn_], acct=True, dz=False) for fn_ in alt_fnames])

            sep_cells = "<td></td>" * (len(alt_fnames) + 1)
            inv_p_html += f'<tr class="row-separator">{sep_cells}</tr>'

            # NPV
            npv_cells = ""
            for fn_ in alt_fnames:
                v = agg_cases[fn_]["npv"]
                cls = "delta-pos" if v > 0 else ("delta-neg" if v < 0 else "")
                npv_cells += f'<td class="{cls}"><strong>{fi(v, acct=True, dz=False)}</strong></td>'
            inv_p_html += f'<tr class="row-bold"><td><strong>NPV (10yr)</strong></td>{npv_cells}</tr>'

            # IRR
            irr_cells = ""
            dash = "\u2013"
            for fn_ in alt_fnames:
                irr = agg_cases[fn_]["irr"]
                if irr is not None:
                    cls = "delta-pos" if irr > cost_of_capital else "delta-neg"
                    irr_cells += f'<td class="{cls}"><strong>{irr*100:.1f}%</strong></td>'
                else:
                    irr_cells += f'<td>{dash}</td>'
            inv_p_html += f'<tr class="row-bold"><td><strong>IRR</strong></td>{irr_cells}</tr>'

            # Payback
            pb_cells = ""
            for fn_ in alt_fnames:
                pb = agg_cases[fn_]["simple_payback"]
                if pb is not None:
                    cls = "delta-pos" if pb <= 10 else "delta-neg"
                    pb_cells += f'<td class="{cls}">{pb:.1f} years</td>'
                else:
                    pb_cells += f'<td>{dash}</td>'
            inv_p_html += f'<tr class="row-bold"><td>Simple Payback</td>{pb_cells}</tr>'

            inv_p_html += '</tbody></table>'
            st.markdown(inv_p_html, unsafe_allow_html=True)

    # ── QUALITATIVE CONTEXT (Portfolio) ──────────────────────
    has_qual = any(
        any(v.strip() for v in item.get("qualitative", {}).values())
        for item in all_results
    )
    if has_qual:
        st.markdown(f'<div class="sec-sm">Strategic Context</div>', unsafe_allow_html=True)
        for item in all_results:
            qual = item.get("qualitative", {})
            if not any(v.strip() for v in qual.values()):
                continue
            inp = item["inputs"]
            lbl = f"{inp['item_number']} - {inp['designation']}" if inp.get("item_number") else inp.get("designation", "Item")
            st.markdown(f'<div style="font-weight:600;font-size:0.8rem;color:{NAVY};margin:0.6rem 0 0.2rem 0;">{lbl}</div>', unsafe_allow_html=True)
            st.markdown(build_qualitative_summary(qual), unsafe_allow_html=True)


# ── SAVE / LOAD ───────────────────────────────────────────────
def save_project_json():
    """Collect all session state into a JSON-serializable dict."""
    return json.dumps({
        "version": "4.5",
        "project_name": st.session_state.get("project_name", ""),
        "project_items": st.session_state.get("project_items", []),
        "next_id": st.session_state.get("next_id", 1),
    }, indent=2)


# ── MAIN ──────────────────────────────────────────────────────
def main():
    init_state()

    # SKF logo (inline SVG for the wordmark)
    skf_logo_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2498 587.1" height="36"><path d="m94.4 294.7c-11.5 0-20.7-11.5-20.7-23v-251c0-9.2 9.2-20.7 20.7-20.7h545.6c9.2 0 20.7 11.5 20.7 20.7v103.6c0 11.5-11.5 23-20.7 23h-177.2c-11.5 0-23-11.5-23-23v-36.8c0-6.9-6.9-13.8-13.8-13.8h-117.5c-6.9 0-16.1 6.9-16.1 13.8v117.4c0 6.9 9.2 16.1 16.1 16.1h402.9c16.1 0 23 6.9 23 20.7v324.6c0 11.5-11.5 20.7-23 20.7h-690.7c-11.4.1-20.7-9.1-20.7-20.5 0-.1 0-.1 0-.2v-177.2c0-11.4 9.2-20.7 20.5-20.7h.2 177.3c11.4 0 20.7 9.2 20.7 20.6v.2 110.5c0 6.9 9.2 13.8 16.1 13.8h264.8c6.9 0 13.8-6.9 13.8-13.8v-191.2c0-6.9-6.9-13.8-13.8-13.8zm787.4-59.9v117.4c0 6.9-6.9 11.5-16.1 16.1-13.8 2.3-20.7 9.2-20.7 20.7v177.3c0 11.4 9.2 20.7 20.5 20.7h.2 214.1c11.4 0 20.7-9.2 20.7-20.6 0-.1 0-.1 0-.2v-195.5c0-2.3 4.6-4.6 6.9-2.3l209.5 214.1c4.6 4.6 6.9 4.6 13.8 4.6h262.5c11.5 0 23-9.2 23-20.7v-177.3c0-11.5-11.5-20.7-23-20.7h-191.1c-4.6 0-6.9 0-9.2-4.6l-142.7-140.4c0-2.3-2.3-2.3 0-4.6l69.1-69.1c2.3-2.3 4.6-2.3 9.2-2.3h193.4c9.2 0 20.7-11.5 20.7-23v-103.7c0-9.2-11.5-20.7-20.7-20.7h-191.1c-6.9 0-9.2 2.3-13.8 6.9l-207.2 211.8c-4.6 2.3-9.2 2.3-9.2-2.3v-195.7c0-9.2-9.2-20.7-20.7-20.7h-214.2c-11.5 0-20.7 11.5-20.7 20.7v177.3c0 11.5 6.9 18.4 18.4 20.7 13.8 4.6 18.4 9.2 18.4 16.1zm844.9 331.6c0 11.5 11.5 20.7 23 20.7h211.8c11.5 0 23-9.2 23-20.7v-175c0-11.5-6.9-20.7-20.7-23-11.5-4.6-16.1-6.9-16.1-16.1v-43.7c0-6.9 6.9-13.8 13.8-13.8h80.6c9.2 0 16.1 6.9 16.1 13.8 0 11.5 11.5 23 20.7 23h177.3c11.5 0 23-11.5 23-23v-103.7c0-11.5-11.5-20.7-23-20.7h-177.2c-9.2 0-20.7 9.2-20.7 20.7 0 6.9-6.9 16.1-16.1 16.1h-80.6c-6.9 0-13.8-9.2-13.8-16.1v-117.4c0-6.9 6.9-13.8 13.8-13.8h227.9c6.9 0 16.1 6.9 16.1 13.8v36.8c0 11.5 9.2 23 20.7 23h251c11.5 0 20.7-11.5 20.7-23v-103.6c0-9.2-9.2-20.7-20.7-20.7h-727.5c-11.5 0-23 11.5-23 20.7v177.3c0 11.5 9.2 18.4 20.7 20.7 9.2 2.3 16.1 9.2 16.1 16.1v117.4c0 6.9-4.6 13.8-16.1 16.1-13.8 2.3-20.7 9.2-20.7 20.7z" fill="white"/></svg>'
    st.markdown(f"""<div class="ib-header">
        <div class="ib-header-left">
            <h1>Landed Cost Comparison Model</h1>
            <div class="sub">Multi-Item Project-Based Production Cost &amp; Profitability Analysis &middot; v9.0</div>
        </div>
        <div>{skf_logo_svg}</div>
    </div>""", unsafe_allow_html=True)

    # ── SIDEBAR ────────────────────────────────────────────────
    st.sidebar.markdown(f"""<div style="background:{NAVY};padding:0.55rem 1rem;margin:-1rem -1rem 0.8rem -1rem;">
        <div style="font-family:Inter,sans-serif;font-size:0.72rem;font-weight:600;color:white;letter-spacing:0.04em;text-transform:uppercase;">Navigation</div>
    </div>""", unsafe_allow_html=True)

    # Navigation buttons
    nav_pages = [
        ("Landed Cost Analysis", "model"),
        ("Transfer Investment", "investment"),
        ("Strategic Context", "strategic"),
    ]
    info_pages = [
        ("About & Methodology", "about"),
        ("User Guide", "guide"),
        ("Changelog & Contact", "changelog"),
    ]

    st.sidebar.markdown(f'<div class="nav-sep">Analysis</div>', unsafe_allow_html=True)

    # Render nav buttons with sub-section links after active page
    for label, key in nav_pages:
        if st.sidebar.button(label, key=f"nav_{key}", use_container_width=True,
                             type="primary" if st.session_state.active_page == key else "secondary"):
            st.session_state.active_page = key
            st.rerun()
        # Sub-section links appear directly below the active Landed Cost Analysis button
        if key == "model" and st.session_state.active_page == "model":
            sub_sections = [
                ("Project Setup", "sec-project-setup"),
                ("Factory Configuration", "sec-factory-config"),
                ("Factory Locations", "sec-factory-locations"),
                ("Assumptions Matrix", "sec-assumptions"),
                ("Lead Times", "sec-lead-times"),
                ("NWC Assumptions", "sec-nwc"),
                ("Item Analysis", "sec-item-analysis"),
            ]
            links_html = "".join(
                f'<a class="nav-sub" href="#{anchor}">{lbl}</a>' for lbl, anchor in sub_sections
            )
            st.sidebar.markdown(links_html, unsafe_allow_html=True)

    st.sidebar.markdown(f'<div class="nav-sep">Reference</div>', unsafe_allow_html=True)
    for label, key in info_pages:
        if st.sidebar.button(label, key=f"nav_{key}", use_container_width=True,
                             type="primary" if st.session_state.active_page == key else "secondary"):
            st.session_state.active_page = key
            st.rerun()

    # ── SIDEBAR CONTENT (Reference pages) ──
    if st.session_state.active_page == "about":
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"""
<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};line-height:1.6;">

<strong style="font-size:0.82rem;">Purpose</strong><br>
The Landed Cost Comparison Model enables strategic evaluation of manufacturing location alternatives.
It compares the full cost-to-serve across multiple production sites, accounting for material costs,
value-added processing, tariffs, duties, transportation, and selling & administrative expenses.
The model calculates operating profit and margin impact at both per-unit and full-year levels.

<br><br><strong style="font-size:0.82rem;">Methodology</strong><br>
The 8-step cost build-up follows standard industrial cost methodology:
<ol style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;">
<li>Base case costs (Material + Variable VA + Fixed VA) define the Standard Cost (SC)</li>
<li>VA Ratio scales Variable and Fixed VA to each location's cost level</li>
<li>PS Index converts SC to Price Standard (PS)</li>
<li>MCL % determines Actual Cost from PS</li>
<li>S&A is applied as a percentage of Net Sales</li>
<li>Tariffs and Duties are calculated on (TPL/100) x PS</li>
<li>Transportation is applied directly on PS</li>
<li>Operating Profit = Net Sales - PS - S&A - Tariff - Duties - Transport</li>
</ol>

<br><strong style="font-size:0.82rem;">NWC Impact</strong><br>
Net Working Capital impact captures the balance sheet cost of inventory tied up across the supply chain:
<ul style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;">
<li><strong>Goods in Transit (GIT)</strong> = (PS x Qty / 365) x Transit Days</li>
<li><strong>Safety Stock</strong> = (PS x Qty / 365) x Safety Stock Days</li>
<li><strong>Cycle Stock</strong> = (PS x Qty / 365) x Cycle Stock Days</li>
<li><strong>Payables (DPO)</strong> = (PS x Qty / 365) x Payment Terms Days &mdash; reduces NWC</li>
<li><strong>Total NWC</strong> = GIT + Safety Stock + Cycle Stock - Payables</li>
<li><strong>Delta NWC</strong> = NWC(location) - NWC(base)</li>
<li><strong>NWC Carrying Cost</strong> = Delta NWC x Cost of Capital (WACC %)</li>
<li><strong>Adjusted OP</strong> = OP - NWC Carrying Cost per unit</li>
</ul>

<br><strong style="font-size:0.9rem;">Transfer Investment Analysis</strong><br>
A separate module evaluates the overall investment rationale for each production transfer:
<ul style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;">
<li><strong>Total Investment</strong> = CAPEX + OPEX + Restructuring</li>
<li><strong>Annual Savings</strong> = NWC-Adjusted Annual OP (alternative) - NWC-Adjusted Annual OP (base)</li>
<li><strong>NPV</strong> = -Investment + &Sigma; [Annual Savings / (1+r)<sup>t</sup>] over the analysis horizon</li>
<li><strong>IRR</strong> = Discount rate where NPV = 0 (solved numerically)</li>
<li><strong>Simple Payback</strong> = Total Investment / Annual Savings</li>
<li><strong>Discounted Payback</strong> = First year where cumulative discounted cash flow &ge; 0</li>
</ul>
Investment inputs are per receiving factory and per item. The discount rate defaults to the Cost of Capital (WACC).

</div>
""", unsafe_allow_html=True)

    elif st.session_state.active_page == "changelog":
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"""
<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};line-height:1.6;">
<strong style="font-size:0.82rem;">Changelog</strong><br>
<span style="color:{GREY_TEXT};">v9.0</span> &mdash; Qualitative context, Data Classification, sidebar nav<br>
<span style="color:{GREY_TEXT};">v8.0</span> &mdash; Transfer Investment Analysis (NPV, IRR, payback)<br>
<span style="color:{GREY_TEXT};">v7.0</span> &mdash; NWC impact, GIT, adjusted OP/margin<br>
<span style="color:{GREY_TEXT};">v6.0</span> &mdash; IB visual refresh, waterfall, tornado, PDF export<br>
<span style="color:{GREY_TEXT};">v5.0</span> &mdash; Testable modules, sensitivity, lead times<br>
<span style="color:{GREY_TEXT};">v4.0</span> &mdash; Multi-item projects, portfolio summary<br>
<span style="color:{GREY_TEXT};">v1&ndash;3</span> &mdash; Core engine, matrix UX, IB styling<br>

<br><strong style="font-size:0.82rem;">Contact</strong><br>
<strong>Jonas Henriksson</strong><br>Head of Strategic Planning &amp; Intelligent Hub<br>
<a href="mailto:jonas.henriksson@skf.com" style="color:{ACCENT_BLUE};text-decoration:none;">jonas.henriksson@skf.com</a>
</div>
""", unsafe_allow_html=True)

    elif st.session_state.active_page == "guide":
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"""<div style="font-family:Inter,sans-serif;font-size:0.74rem;color:{DARK_TEXT};line-height:1.55;">
<strong style="font-size:0.82rem;">What This Model Does</strong><br>
Compares full cost-to-serve across factory locations, including material, labour, tariffs, shipping, and inventory costs. Shows which location offers the best operating profit.

<br><br><strong style="font-size:0.82rem;">Quick Start</strong><br>
<strong>1.</strong> Tick "Load example data" to see a pre-filled analysis<br>
<strong>2.</strong> Check KPI cards for best margin at a glance<br>
<strong>3.</strong> Review tables for cost breakdown details<br>
<strong>4.</strong> Open Portfolio Summary for combined view

<br><br><strong style="font-size:0.82rem;">Input Legend</strong><br>
<span style="border-left:3px solid {INPUT_BLUE};padding-left:0.3rem;font-weight:600;color:{INPUT_BLUE};">Blue border</span> = editable input<br>
<strong>Bold text</strong> = calculated output<br>
<span style="color:{GREY_TEXT};font-style:italic;">Grey italic</span> = guidance notes

<br><br><strong style="font-size:0.82rem;">Workflow</strong><br>
<strong>1.</strong> Set project name, currency, target market<br>
<strong>2.</strong> Configure factory assumptions matrix<br>
<strong>3.</strong> Assign factory countries for lead times<br>
<strong>4.</strong> Set WACC % and NWC assumptions<br>
<strong>5.</strong> Add items with costs and overrides<br>
<strong>6.</strong> Review results, sensitivity, investment<br>
<strong>7.</strong> Add strategic context per item<br>
<strong>8.</strong> Export PDF or Excel
</div>""", unsafe_allow_html=True)
    # ── STRATEGIC CONTEXT PAGE ─────────────────────────────────
    if st.session_state.active_page == "strategic":
        st.markdown(f'<div class="callout" style="font-size:0.72rem;">Provide strategic context and qualitative rationale for each item\'s transfer decision. These inputs appear in the executive summary, portfolio overview, and exported reports.</div>', unsafe_allow_html=True)
        st.markdown('<div class="sec">Strategic Context & Qualitative Assessment</div>', unsafe_allow_html=True)

        for idx, item_def in enumerate(st.session_state.project_items):
            item_label = f"Item {idx + 1}"
            st.markdown(f'<div class="sec-sm">{item_label}</div>', unsafe_allow_html=True)

            q_labels = [
                ("strategic_rationale", "Strategic Rationale",
                 "Why is this transfer being considered? What strategic objective does it serve? (e.g. cost competitiveness, capacity, market proximity, risk diversification)"),
                ("purpose", "Purpose & Objective",
                 "What is the specific goal of this evaluation? (e.g. annual sourcing review, new product launch, capacity constraint resolution)"),
                ("risk_of_inaction", "What Happens If We Don't Do This?",
                 "Describe the consequence of maintaining the status quo. (e.g. continued margin erosion, capacity bottleneck, single-source risk, inability to serve key market)"),
                ("risks", "Key Risks & Mitigations",
                 "What are the main risks of this transfer? (e.g. quality ramp-up, customer approval timeline, IP concerns, FX exposure, geopolitical risk)"),
            ]
            ex_qual = {}
            if st.session_state.ex:
                ex_qual = {
                    "strategic_rationale": "Diversify manufacturing footprint to reduce single-source risk and improve cost competitiveness in key growth markets. Aligns with Group strategy to establish regional production hubs.",
                    "purpose": "Annual sourcing review — evaluate transfer feasibility for high-volume bearing assembly line as part of the 2026 manufacturing footprint optimisation programme.",
                    "risk_of_inaction": "Continued margin erosion of 2-3pp annually due to rising European labour costs. Single-source risk from Factory A capacity constraints limits growth in Americas and Asia-Pacific markets.",
                    "risks": "Quality ramp-up: 6-12 month qualification period at receiving site. Customer re-approval required for automotive OEM accounts (est. 9 months). FX exposure on CNY/SEK if transferring to Asia. Geopolitical risk for China-based production.",
                }

            col1, col2 = st.columns(2)
            for qi, (key, label, help_text) in enumerate(q_labels):
                with col1 if qi % 2 == 0 else col2:
                    st.markdown(f'<div style="font-size:0.75rem;font-weight:600;color:{DARK_TEXT};margin:0.6rem 0 0.2rem 0;">{label}</div>', unsafe_allow_html=True)
                    st.text_area(
                        label, value=ex_qual.get(key, ""),
                        key=f"i{item_def['id']}_qual_{key}",
                        height=100, label_visibility="collapsed",
                        placeholder=help_text)

        # Footer for strategic context page
        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>Landed Cost Comparison v9.0 &middot; {st.session_state.project_name} &middot; Strategic Context</span>", unsafe_allow_html=True)
        return  # Don't render the model page

    # ── TRANSFER INVESTMENT PAGE ─────────────────────────────
    if st.session_state.active_page == "investment":
        all_results = st.session_state.get("_all_results", [])
        cost_of_capital = st.session_state.get("_cost_of_capital", 0.08)
        factory_countries = st.session_state.get("_factory_countries", {})
        currency = st.session_state.get("currency", "SEK")
        ex = st.session_state.ex

        if not all_results:
            st.markdown(f'<div class="callout" style="font-size:0.76rem;">No item results available yet. Open <strong>Landed Cost Analysis</strong> first to configure the project and compute results.</div>', unsafe_allow_html=True)
            return

        st.markdown(f'<div class="callout">Evaluate the investment rationale for transferring production. Enter one-time costs per receiving factory. Annual savings are derived from the NWC-adjusted OP delta vs. base. Leave blank or zero if no investment is required.</div>', unsafe_allow_html=True)

        for item_idx, item_data in enumerate(all_results):
            results = item_data["results"]
            inp = item_data["inputs"]
            item_id = st.session_state.project_items[item_idx]["id"] if item_idx < len(st.session_state.project_items) else item_idx

            if len(results) < 2:
                continue

            item_label = f"{inp.get('item_number', '')} {inp.get('designation', '')}".strip() or f"Item {item_idx + 1}"
            st.markdown(f'<div class="sec">Transfer Investment — {item_label}</div>', unsafe_allow_html=True)

            inv_c1, inv_c2 = st.columns([1, 1])
            with inv_c1:
                inv_horizon_df = pd.DataFrame({"Analysis Horizon (Years)": [st.session_state.get(f"i{item_id}_inv_hz_val", 10)]})
                edited_hz = st.data_editor(inv_horizon_df, use_container_width=False, num_rows="fixed",
                    key=f"i{item_id}_inv_hz", hide_index=True,
                    column_config={"Analysis Horizon (Years)": st.column_config.NumberColumn(
                        "Analysis Horizon (Years)", min_value=1, max_value=30, step=1, format="%d", width=200)})
                inv_horizon = max(1, min(30, int(edited_hz.loc[0, "Analysis Horizon (Years)"] or 10)))
                st.session_state[f"i{item_id}_inv_hz_val"] = inv_horizon
            with inv_c2:
                st.markdown(f'<div style="font-size:0.72rem;color:{GREY_TEXT};padding-top:0.6rem;">Discount rate uses Cost of Capital (WACC): <strong>{cost_of_capital*100:.1f}%</strong></div>', unsafe_allow_html=True)

            alt_names = [r["name"] for r in results[1:]]
            INV_ROWS = ["CAPEX (Tooling / Equipment)", "OPEX (Project / Qualification)", "Restructuring (Sending Site)"]
            inv_cols = {}
            for an in alt_names:
                if ex:
                    if "Asia" in an or "China" in str(factory_countries.get(an, "")):
                        inv_cols[an] = [8_000_000.0, 2_500_000.0, 1_500_000.0]
                    elif "Americas" in an or "USA" in str(factory_countries.get(an, "")):
                        inv_cols[an] = [5_000_000.0, 1_800_000.0, 1_000_000.0]
                    else:
                        inv_cols[an] = [3_000_000.0, 1_000_000.0, 500_000.0]
                else:
                    inv_cols[an] = [None, None, None]
            inv_cols["Guide"] = [
                f"Capital expenditure for tooling / equipment at receiving site ({currency})",
                f"One-time project, transfer, qualification costs ({currency})",
                f"Restructuring / severance costs at sending site ({currency})",
            ]
            inv_df = pd.DataFrame(inv_cols, index=INV_ROWS)

            edited_inv = st.data_editor(
                inv_df, use_container_width=True, num_rows="fixed",
                key=f"i{item_id}_inv_matrix",
                column_config={
                    **{an: st.column_config.NumberColumn(an, format="%,.0f", min_value=0) for an in alt_names},
                    "Guide": st.column_config.TextColumn("Guide", width=380, disabled=True),
                },
                disabled=["Guide"])

            # Compute investment cases
            inv_results = []
            base_adj_annual_op = results[0].get("annual_adj_op", results[0]["annual_op"])
            for alt_r in results[1:]:
                an = alt_r["name"]
                def _inv_val(row_name, col_name, _df=edited_inv):
                    v = _df.loc[row_name, col_name]
                    if v is not None and not pd.isna(v):
                        return float(v)
                    return 0.0
                capex = _inv_val("CAPEX (Tooling / Equipment)", an)
                opex = _inv_val("OPEX (Project / Qualification)", an)
                restr = _inv_val("Restructuring (Sending Site)", an)
                annual_savings = alt_r.get("annual_adj_op", alt_r["annual_op"]) - base_adj_annual_op

                inv_case = compute_investment_case(
                    annual_savings=annual_savings,
                    capex=capex, opex=opex, restructuring=restr,
                    discount_rate=cost_of_capital,
                    horizon_years=inv_horizon,
                )
                inv_case["factory_name"] = an
                inv_results.append(inv_case)

            # Store investment results back for portfolio/export
            item_data["investment"] = inv_results

            # Display investment results table
            has_any_inv = any(ic["total_investment"] > 0 or ic["annual_savings"] != 0 for ic in inv_results)
            if has_any_inv:
                dash = "\u2013"
                inv_hdr = "".join(f'<th>{ic["factory_name"]}</th>' for ic in inv_results)
                inv_html = f'<table class="ib-table"><thead><tr><th>Transfer Investment ({currency})</th>{inv_hdr}</tr></thead><tbody>'

                def _inv_row(lbl, vals, cls=""):
                    cells = "".join(f'<td>{v}</td>' for v in vals)
                    return f'<tr class="{cls}"><td>{lbl}</td>{cells}</tr>'

                inv_html += _inv_row("CAPEX", [fi(ic["capex"], dz=True) for ic in inv_results])
                inv_html += _inv_row("OPEX", [fi(ic["opex"], dz=True) for ic in inv_results])
                inv_html += _inv_row("Restructuring", [fi(ic["restructuring"], dz=True) for ic in inv_results])
                inv_html += _inv_row("Total Investment", [fi(ic["total_investment"], dz=False) for ic in inv_results], "row-subtotal")

                inv_html += f'<tr class="row-separator">{"<td></td>" * (len(inv_results)+1)}</tr>'
                inv_html += _inv_row("Annual Savings (Adj. OP Delta)", [fi(ic["annual_savings"], acct=True, dz=False) for ic in inv_results])
                inv_html += _inv_row("Analysis Horizon", [f"{ic['horizon_years']} years" for ic in inv_results])
                inv_html += _inv_row("Discount Rate (WACC)", [fp(ic['discount_rate'], 1, dz=False) for ic in inv_results])

                inv_html += f'<tr class="row-separator">{"<td></td>" * (len(inv_results)+1)}</tr>'

                # NPV with color coding
                npv_cells = ""
                for ic in inv_results:
                    cls = "delta-pos" if ic["npv"] > 0 else ("delta-neg" if ic["npv"] < 0 else "")
                    npv_cells += f'<td class="{cls}"><strong>{fi(ic["npv"], acct=True, dz=False)}</strong></td>'
                inv_html += f'<tr class="row-bold"><td><strong>NPV</strong></td>{npv_cells}</tr>'

                # IRR
                irr_cells = ""
                for ic in inv_results:
                    if ic["irr"] is not None:
                        cls = "delta-pos" if ic["irr"] > cost_of_capital else "delta-neg"
                        irr_cells += f'<td class="{cls}"><strong>{ic["irr"]*100:.1f}%</strong></td>'
                    else:
                        irr_cells += f'<td>{dash}</td>'
                inv_html += f'<tr class="row-bold"><td><strong>IRR</strong></td>{irr_cells}</tr>'

                # Payback
                pb_cells = ""
                for ic in inv_results:
                    if ic["simple_payback"] is not None:
                        cls = "delta-pos" if ic["simple_payback"] <= inv_horizon else "delta-neg"
                        pb_cells += f'<td class="{cls}">{ic["simple_payback"]:.1f} years</td>'
                    else:
                        pb_cells += f'<td>{dash}</td>'
                inv_html += f'<tr class="row-bold"><td>Simple Payback</td>{pb_cells}</tr>'

                dpb_cells = ""
                for ic in inv_results:
                    if ic["discounted_payback"] is not None:
                        cls = "delta-pos" if ic["discounted_payback"] <= inv_horizon else "delta-neg"
                        dpb_cells += f'<td class="{cls}">{ic["discounted_payback"]:.1f} years</td>'
                    else:
                        dpb_cells += f'<td>{dash}</td>'
                inv_html += f'<tr class="row-bold"><td>Discounted Payback</td>{dpb_cells}</tr>'

                inv_html += '</tbody></table>'
                st.markdown(inv_html, unsafe_allow_html=True)

                # Cumulative cash flow chart
                fig_cf = go.Figure()
                colors_cycle = [ACCENT_BLUE, GREEN, RED, "#e67e22", "#8e44ad", NAVY]
                for ci, ic in enumerate(inv_results):
                    if ic["total_investment"] > 0 or ic["annual_savings"] != 0:
                        years = list(range(inv_horizon + 1))
                        color = colors_cycle[ci % len(colors_cycle)]
                        fig_cf.add_trace(go.Scatter(
                            x=years, y=ic["cumulative_cf"],
                            mode="lines+markers", name=ic["factory_name"],
                            line=dict(color=color, width=2), marker=dict(size=4),
                            hovertemplate=f"{ic['factory_name']}<br>Year %{{x}}<br>Cumulative: %{{y:,.0f}} {currency}<extra></extra>",
                        ))
                fig_cf.add_hline(y=0, line=dict(color=NAVY, width=1.5, dash="dot"))
                fig_cf.update_layout(
                    title=dict(text=f"Cumulative Cash Flow ({currency})", font=dict(size=11, family="Inter", color=DARK_TEXT)),
                    height=350, margin=dict(l=50, r=30, t=50, b=50),
                    paper_bgcolor="white", plot_bgcolor="white",
                    font=dict(family="Inter", size=10, color=DARK_TEXT),
                    xaxis=dict(title="Year", showgrid=True, gridcolor="#eee", dtick=1),
                    yaxis=dict(title=currency, showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_cf, use_container_width=True, config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False})

        # Footer for investment page
        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>Landed Cost Comparison v9.0 &middot; {st.session_state.project_name} &middot; Transfer Investment Analysis</span>", unsafe_allow_html=True)
        return

    # ── Reference-only pages: show info message ──
    if st.session_state.active_page in ("about", "guide", "changelog"):
        st.markdown(f'<div class="callout" style="font-size:0.76rem;">Reference content is displayed in the sidebar. Select <strong>Landed Cost Analysis</strong> or <strong>Strategic Context</strong> from the sidebar to work with the analysis.</div>', unsafe_allow_html=True)
        return

    # ── COST MODEL PAGE (active_page == "model") ──
    st.markdown(f'<div class="callout" style="font-size:0.72rem;"><span style="border-left:3px solid {INPUT_BLUE};padding-left:0.35rem;font-weight:600;color:{INPUT_BLUE};">Blue border</span> = editable input fields &nbsp;&middot;&nbsp; <span style="font-weight:600;color:{DARK_TEXT};">Output tables</span> = calculated results (read-only) &nbsp;&middot;&nbsp; <span style="color:{GREY_TEXT};font-style:italic;">Grey italic</span> = guidance notes</div>', unsafe_allow_html=True)

    ex = st.checkbox("Load example data", value=st.session_state.ex)
    st.session_state.ex = ex

    # ── PROJECT HEADER ────────────────────────────────────────
    st.markdown('<div class="sec" id="sec-project-setup">Project Setup</div>', unsafe_allow_html=True)

    pc1, pc2, pc3, pc4, pc4b, pc5 = st.columns([2, 1, 1, 1, 1, 2])
    with pc1:
        proj_df = pd.DataFrame({"Project Name": [st.session_state.project_name]})
        edited_proj = st.data_editor(proj_df, use_container_width=True, num_rows="fixed",
            key="proj_name", hide_index=True,
            column_config={"Project Name": st.column_config.TextColumn("Project Name", width=280)})
        st.session_state.project_name = str(edited_proj.loc[0, "Project Name"] or "New Project")

    with pc2:
        ccy_df = pd.DataFrame({"Currency": ["SEK"]})
        edited_ccy = st.data_editor(ccy_df, use_container_width=True, num_rows="fixed",
            key="proj_ccy", hide_index=True,
            column_config={"Currency": st.column_config.SelectboxColumn("Currency", options=CURRENCIES, width=100)})
        st.session_state["currency"] = str(edited_ccy.loc[0, "Currency"] or "SEK")
        currency = st.session_state["currency"]

    with pc3:
        tm_df = pd.DataFrame({"Target Market": ["USA" if ex else "USA"]})
        edited_tm = st.data_editor(tm_df, use_container_width=True, num_rows="fixed",
            key="proj_tm", hide_index=True,
            column_config={"Target Market": st.column_config.SelectboxColumn("Target Market", options=COUNTRIES, width=140)})
        target_market = str(edited_tm.loc[0, "Target Market"] or "")
        st.session_state["target_market"] = target_market

    with pc4:
        dt_df = pd.DataFrame({"Date": [date.today()]})
        edited_dt = st.data_editor(dt_df, use_container_width=True, num_rows="fixed",
            key="proj_dt", hide_index=True,
            column_config={"Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", width=130)})

    with pc4b:
        DATA_CLASSES = ["C1 - Public", "C2 - Internal", "C3 - Confidential", "C4 - Strictly Confidential"]
        dc_df = pd.DataFrame({"Data Classification": ["C3 - Confidential"]})
        edited_dc = st.data_editor(dc_df, use_container_width=True, num_rows="fixed",
            key="proj_dc", hide_index=True,
            column_config={"Data Classification": st.column_config.SelectboxColumn(
                "Data Classification", options=DATA_CLASSES, width=180)})
        data_classification = str(edited_dc.loc[0, "Data Classification"] or "C3 - Confidential")
        st.session_state["data_classification"] = data_classification

    with pc5:
        sc1, sc2 = st.columns(2)
        with sc1:
            save_data = save_project_json()
            _ = st.download_button("Save Project", data=save_data,
                file_name=f"{st.session_state.project_name.replace(' ','_')}.json",
                mime="application/json")
        with sc2:
            uploaded = st.file_uploader("Load Project", type=["json"], key="load_proj", label_visibility="collapsed")
            if uploaded:
                try:
                    proj = json.load(uploaded)
                    st.session_state.project_name = proj.get("project_name", "Loaded Project")
                    st.session_state.project_items = proj.get("project_items", [{"id": 0}])
                    st.session_state.next_id = proj.get("next_id", 1)
                    st.rerun()
                except Exception:
                    st.error("Invalid project file.")

    # ── SHARED FACTORY SETUP ──────────────────────────────────────
    st.markdown('<div class="sec" id="sec-factory-config">Shared Factory Configuration</div>', unsafe_allow_html=True)

    fc_data = {"Comparison Factories": [4 if ex else st.session_state.get("num_fac", 2)]}
    fc_df = pd.DataFrame(fc_data)
    edited_fc = st.data_editor(
        fc_df, use_container_width=False, num_rows="fixed", key="fc_editor", hide_index=True,
        column_config={"Comparison Factories": st.column_config.NumberColumn(
            "Comparison Factories", min_value=1, max_value=6, step=1, format="%d", width=180)})
    num_factories = max(1, min(6, int(edited_fc.loc[0, "Comparison Factories"])))
    st.session_state["num_fac"] = num_factories

    # Base factory name + Cost of Capital
    bf_col1, bf_col2 = st.columns([2, 1])
    with bf_col1:
        bf_df = pd.DataFrame({"Base Factory Name": [EX_BASE.name if ex else "Base Case"]})
        edited_bf = st.data_editor(bf_df, use_container_width=False, num_rows="fixed",
            key="bf_editor", hide_index=True,
            column_config={"Base Factory Name": st.column_config.TextColumn("Base Factory Name", width=250)})
        base_factory_name = str(edited_bf.loc[0, "Base Factory Name"] or "Base Case")
    with bf_col2:
        coc_df = pd.DataFrame({"Cost of Capital (WACC %)": [8.0 if ex else 8.0]})
        edited_coc = st.data_editor(coc_df, use_container_width=False, num_rows="fixed",
            key="coc_editor", hide_index=True,
            column_config={"Cost of Capital (WACC %)": st.column_config.NumberColumn(
                "Cost of Capital (WACC %)", min_value=0.0, max_value=30.0, step=0.5, format="%.1f", width=200)})
        cost_of_capital = float(edited_coc.loc[0, "Cost of Capital (WACC %)"] or 0.0) / 100.0
        st.session_state["cost_of_capital"] = cost_of_capital

    # Factory country assignment
    st.markdown('<div class="sec-sm" id="sec-factory-locations">Factory Locations</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="callout">Assign the <strong>country</strong> where each factory is located. This determines lead time to the target market (<strong>{target_market}</strong>).</div>', unsafe_allow_html=True)

    ex_base_country = "Sweden" if ex else "Sweden"
    ex_factory_countries = ["Germany", "China", "France", "USA"] if ex else []
    country_data = {"Factory": [base_factory_name], "Country": [ex_base_country]}
    for i in range(num_factories):
        ex_f = EX_FACTORIES[i] if ex and i < len(EX_FACTORIES) else None
        col_name = ex_f.name if ex_f else f"Factory {i+2}"
        country_data["Factory"].append(col_name)
        country_data["Country"].append(ex_factory_countries[i] if ex and i < len(ex_factory_countries) else "")
    country_df = pd.DataFrame(country_data)

    edited_countries = st.data_editor(
        country_df, use_container_width=False, num_rows="fixed", key="country_editor", hide_index=True,
        column_config={
            "Factory": st.column_config.TextColumn("Factory", width=200, disabled=True),
            "Country": st.column_config.SelectboxColumn("Country", options=COUNTRIES, width=180),
        },
        disabled=["Factory"],
    )
    factory_countries = {}
    for _, r in edited_countries.iterrows():
        factory_countries[r["Factory"]] = str(r["Country"] or "")

    # Assumptions matrix
    ROWS = ["VA Ratio","PS Index","MCL %","S&A %","TPL","Tariff %","Duties %","Transport %"]
    GUIDES = [
        "Scales base Variable & Fixed VA to location cost level",
        "Multiplied by SC to get Price Standard (PS)",
        "Applied to PS for Actual Cost: PS x (MCL / 100)",
        "Selling & Admin as % of Net Sales, deducted from revenue",
        "Base for Tariff & Duties: (TPL/100) x PS x rate",
        "Tariff cost on (TPL/100) x PS. Set 0 if same region",
        "Duties cost on (TPL/100) x PS. Set 0 if same region",
        "Transport cost on PS. Set 0 if same region",
    ]
    base_defaults = [None, 1.0, 100.0, 0.0, 100.0, 0.0, 0.0, 0.0]
    ex_base_vals = [None, EX_BASE.ps_index, EX_BASE.mcl_pct, EX_BASE.sa_pct, EX_BASE.tpl,
                    EX_BASE.tariff_pct, EX_BASE.duties_pct, EX_BASE.transport_pct]

    factory_cols = {}
    factory_col_names = []
    base_vals = ex_base_vals if ex else base_defaults
    factory_cols[base_factory_name] = [v if v is not None else None for v in base_vals]

    for i in range(num_factories):
        ex_f = EX_FACTORIES[i] if ex and i < len(EX_FACTORIES) else None
        col_name = ex_f.name if ex_f else f"Factory {i+2}"
        factory_col_names.append(col_name)
        if ex_f:
            factory_cols[col_name] = [ex_f.va_ratio, ex_f.ps_index, ex_f.mcl_pct, ex_f.sa_pct,
                                      ex_f.tpl, ex_f.tariff_pct, ex_f.duties_pct, ex_f.transport_pct]
        else:
            factory_cols[col_name] = [1.0, 1.0, 100.0, 0.0, 100.0, 0.0, 0.0, 0.0]

    factory_cols["Guide"] = GUIDES
    df_matrix = pd.DataFrame(factory_cols, index=ROWS)
    df_matrix.loc["VA Ratio", base_factory_name] = None

    st.markdown('<div class="sec-sm" id="sec-assumptions">Assumptions Matrix</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="callout">These assumptions apply to <strong>all items</strong> in the project. Base case (<strong>{base_factory_name}</strong>) VA Ratio is 1.0x (implicit).</div>', unsafe_allow_html=True)

    col_config = {
        base_factory_name: st.column_config.NumberColumn(base_factory_name, format="%.2f"),
        **{cn: st.column_config.NumberColumn(cn, format="%.2f") for cn in factory_col_names},
        "Guide": st.column_config.TextColumn("Guide", width=320, disabled=True),
    }

    edited_df = st.data_editor(
        df_matrix, use_container_width=True, num_rows="fixed", key="assumption_matrix",
        column_config=col_config, disabled=["Guide"])

    # Lead time comparison
    if target_market:
        st.markdown(f'<div class="sec-sm" id="sec-lead-times">Lead Time to {target_market}</div>', unsafe_allow_html=True)
        all_factory_names = [base_factory_name] + factory_col_names
        lt_data = []
        base_country = factory_countries.get(base_factory_name, "")
        base_lt = estimate_lead_time(base_country, target_market)
        for fn_ in all_factory_names:
            ctry = factory_countries.get(fn_, "")
            lt = estimate_lead_time(ctry, target_market)
            delta = (lt - base_lt) if (lt is not None and base_lt is not None) else None
            lt_data.append({"Factory": fn_, "Country": ctry, "Route": f"{ctry} \u2192 {target_market}" if ctry else "\u2013",
                "Transit Days": lt if lt is not None else None,
                "Delta vs Base": delta if delta is not None and fn_ != base_factory_name else None})
        lt_df = pd.DataFrame(lt_data)
        hdr = "".join(f'<th>{r["Factory"]}</th>' for r in lt_data)
        route_cells = "".join(f'<td class="{"base-case" if i==0 else ""}">{r["Route"]}</td>' for i, r in enumerate(lt_data))
        dash = "\u2013"
        days_cells = "".join(f'<td class="{"base-case" if i==0 else ""}">{r["Transit Days"] if r["Transit Days"] is not None else dash}</td>' for i, r in enumerate(lt_data))
        delta_cells = ""
        dash = "\u2013"
        for i, r in enumerate(lt_data):
            if i == 0:
                delta_cells += f'<td class="base-case">{dash}</td>'
            else:
                d = r["Delta vs Base"]
                if d is not None and d != 0:
                    sign = "+" if d > 0 else ""
                    cls = "delta-neg" if d > 0 else "delta-pos"
                    delta_cells += f'<td class="{cls}">{sign}{d} days</td>'
                elif d is not None:
                    delta_cells += f'<td>{dash}</td>'
                else:
                    delta_cells += f'<td>{dash}</td>'
        lt_html = f'<table class="ib-table"><thead><tr><th>Lead Time</th>{hdr}</tr></thead><tbody>'
        lt_html += f'<tr><td>Route</td>{route_cells}</tr>'
        lt_html += f'<tr class="row-bold"><td>Transit Days</td>{days_cells}</tr>'
        lt_html += f'<tr class="row-bold"><td><em>Delta vs. Base</em></td>{delta_cells}</tr>'
        lt_html += '</tbody></table>'
        st.markdown(lt_html, unsafe_allow_html=True)

    # ── NWC ASSUMPTIONS ──────────────────────────────────────
    all_factory_names_nwc = [base_factory_name] + factory_col_names
    st.markdown('<div class="sec-sm" id="sec-nwc">NWC Assumptions</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="callout">Net Working Capital assumptions for inventory and payment terms analysis. Leave blank or zero to exclude. All values in <strong>days</strong>. Applies to all items.</div>', unsafe_allow_html=True)
    NWC_ROWS = ["Safety Stock Days", "Cycle Stock Days", "Payment Terms (DPO) Days"]
    NWC_GUIDES = [
        "Buffer inventory held as safety margin (days of supply)",
        "Average production cycle inventory (days of supply)",
        "Supplier payment terms - longer DPO reduces NWC (days)",
    ]
    nwc_cols = {}
    for fn_ in all_factory_names_nwc:
        if ex:
            # Example data: base has moderate values, others vary
            if fn_ == base_factory_name:
                nwc_cols[fn_] = [14.0, 10.0, 30.0]
            elif "Asia" in fn_ or "China" in str(factory_countries.get(fn_, "")):
                nwc_cols[fn_] = [21.0, 15.0, 45.0]
            elif "Americas" in fn_ or "USA" in str(factory_countries.get(fn_, "")):
                nwc_cols[fn_] = [14.0, 12.0, 35.0]
            else:
                nwc_cols[fn_] = [14.0, 10.0, 30.0]
        else:
            nwc_cols[fn_] = [None, None, None]
    nwc_cols["Guide"] = NWC_GUIDES
    nwc_df = pd.DataFrame(nwc_cols, index=NWC_ROWS)

    edited_nwc = st.data_editor(
        nwc_df, use_container_width=True, num_rows="fixed", key="nwc_matrix",
        column_config={
            **{fn_: st.column_config.NumberColumn(fn_, format="%.0f", min_value=0, max_value=365) for fn_ in all_factory_names_nwc},
            "Guide": st.column_config.TextColumn("Guide", width=320, disabled=True),
        },
        disabled=["Guide"])

    # Extract NWC assumptions per factory
    nwc_assumptions = {}
    for fn_ in all_factory_names_nwc:
        def _nwc_val(row_name, col_name):
            v = edited_nwc.loc[row_name, col_name]
            if v is not None and not pd.isna(v):
                return float(v)
            return 0.0
        nwc_assumptions[fn_] = {
            "safety_stock_days": _nwc_val("Safety Stock Days", fn_),
            "cycle_stock_days": _nwc_val("Cycle Stock Days", fn_),
            "payment_terms_days": _nwc_val("Payment Terms (DPO) Days", fn_),
        }
    base_nwc = nwc_assumptions.get(base_factory_name, {})

    # Build factory objects
    base = FactoryAssumptions(
        name=base_factory_name, country=factory_countries.get(base_factory_name, ""), va_ratio=None,
        ps_index=float(edited_df.loc["PS Index", base_factory_name] or 1.0),
        mcl_pct=float(edited_df.loc["MCL %", base_factory_name] or 100.0),
        sa_pct=float(edited_df.loc["S&A %", base_factory_name] or 0.0),
        tpl=float(edited_df.loc["TPL", base_factory_name] or 100.0),
        tariff_pct=float(edited_df.loc["Tariff %", base_factory_name] or 0.0),
        duties_pct=float(edited_df.loc["Duties %", base_factory_name] or 0.0),
        transport_pct=float(edited_df.loc["Transport %", base_factory_name] or 0.0))

    factories = []
    for cn in factory_col_names:
        va = edited_df.loc["VA Ratio", cn]
        factories.append(FactoryAssumptions(
            name=cn, country=factory_countries.get(cn, ""),
            va_ratio=float(va) if va is not None and not pd.isna(va) else 1.0,
            ps_index=float(edited_df.loc["PS Index", cn] or 1.0),
            mcl_pct=float(edited_df.loc["MCL %", cn] or 100.0),
            sa_pct=float(edited_df.loc["S&A %", cn] or 0.0),
            tpl=float(edited_df.loc["TPL", cn] or 100.0),
            tariff_pct=float(edited_df.loc["Tariff %", cn] or 0.0),
            duties_pct=float(edited_df.loc["Duties %", cn] or 0.0),
            transport_pct=float(edited_df.loc["Transport %", cn] or 0.0)))

    # ── ITEM TABS ─────────────────────────────────────────────
    st.markdown('<div class="sec" id="sec-item-analysis">Item Analysis</div>', unsafe_allow_html=True)

    # Add / remove item buttons
    bc1, bc2, _ = st.columns([1, 1, 6])
    with bc1:
        if st.button("Add Item", key="add_item"):
            st.session_state.project_items.append({"id": st.session_state.next_id})
            st.session_state.next_id += 1
            st.rerun()
    with bc2:
        if len(st.session_state.project_items) > 1:
            if st.button("Remove Last", key="rem_item"):
                st.session_state.project_items.pop()
                st.rerun()

    # Create tabs
    tab_labels = [f"Item {i+1}" for i in range(len(st.session_state.project_items))] + ["Portfolio Summary"]
    tabs = st.tabs(tab_labels)

    all_results = []

    for idx, (tab, item_def) in enumerate(zip(tabs[:-1], st.session_state.project_items)):
        with tab:
            item_data = render_item(idx, item_def["id"], base_factory_name, factory_col_names, num_factories, ex)

            if item_data is not None:
                inputs = item_data["inputs"]
                get_ov = item_data["get_ov"]

                # Resolve lead times for NWC calculation
                base_country = factory_countries.get(base_factory_name, "")
                base_lt = estimate_lead_time(base_country, target_market) if target_market else None

                results = []
                br = compute_location(inputs, base, is_base=True,
                    lead_time_days=base_lt, base_lead_time_days=base_lt,
                    cost_of_capital=cost_of_capital,
                    safety_stock_days=base_nwc.get("safety_stock_days", 0),
                    base_safety_stock_days=base_nwc.get("safety_stock_days", 0),
                    cycle_stock_days=base_nwc.get("cycle_stock_days", 0),
                    base_cycle_stock_days=base_nwc.get("cycle_stock_days", 0),
                    payment_terms_days=base_nwc.get("payment_terms_days", 0),
                    base_payment_terms_days=base_nwc.get("payment_terms_days", 0))
                if br: results.append(br)
                for f in factories:
                    if f.name:
                        ov = get_ov(f.name)
                        f_lt = estimate_lead_time(f.country, target_market) if target_market and f.country else None
                        f_nwc = nwc_assumptions.get(f.name, {})
                        r = compute_location(inputs, f, overrides=ov,
                            lead_time_days=f_lt, base_lead_time_days=base_lt,
                            cost_of_capital=cost_of_capital,
                            safety_stock_days=f_nwc.get("safety_stock_days", 0),
                            base_safety_stock_days=base_nwc.get("safety_stock_days", 0),
                            cycle_stock_days=f_nwc.get("cycle_stock_days", 0),
                            base_cycle_stock_days=base_nwc.get("cycle_stock_days", 0),
                            payment_terms_days=f_nwc.get("payment_terms_days", 0),
                            base_payment_terms_days=base_nwc.get("payment_terms_days", 0))
                        if r: results.append(r)

                if results:
                    # Qualitative data from session state (persisted from text_area widgets)
                    qual_from_state = {
                        key: st.session_state.get(f"i{item_def['id']}_qual_{key}", "")
                        for key in ("strategic_rationale", "purpose", "risk_of_inaction", "risks")
                    }

                    # Executive summary narrative
                    exec_html = build_exec_summary(results, inputs, currency)
                    if exec_html:
                        st.markdown(exec_html, unsafe_allow_html=True)

                    # Strategic context (qualitative inputs)
                    qual_html = build_qualitative_summary(qual_from_state)
                    if qual_html:
                        st.markdown(qual_html, unsafe_allow_html=True)

                    # KPI cards
                    bom = results[0]["om"]
                    ranked = sorted(results[1:], key=lambda r: r["om"], reverse=True)
                    labels = ["Best Location", "2nd Best", "3rd Best"]
                    ncards = min(len(ranked), 3) + 1
                    cols = st.columns(ncards)
                    cols[0].markdown(f'<div style="background:{BASE_CASE_BG};border:1px solid {BORDER};border-radius:1px;padding:0.7rem 0.9rem;text-align:center;"><div style="font-size:0.62rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.06em;font-weight:600;margin-bottom:0.15rem;">Base Case OM</div><div style="font-size:1.1rem;font-weight:700;color:{DARK_TEXT};font-variant-numeric:tabular-nums;">{fp(bom,1,dz=False)}</div><div style="font-size:0.78rem;font-weight:600;color:{DARK_TEXT};margin-top:0.1rem;">{results[0]["name"]}</div></div>', unsafe_allow_html=True)
                    for i, r in enumerate(ranked[:3]):
                        delta_pp = (r["om"] - bom) * 100
                        is_better = delta_pp > 0.05
                        is_worse = delta_pp < -0.05
                        bdr = f"border-left:3px solid {GREEN};" if is_better else (f"border-left:3px solid {RED};" if is_worse else f"border-left:3px solid {BORDER};")
                        d_sign = "+" if delta_pp > 0 else ""
                        d_cls = f"color:{GREEN};font-weight:600;" if is_better else (f"color:{RED};font-weight:600;" if is_worse else f"color:{MUTED};")
                        cols[i+1].markdown(f'<div style="background:#fafafa;border:1px solid {BORDER};{bdr}border-radius:1px;padding:0.7rem 0.9rem;text-align:center;"><div style="font-size:0.62rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.06em;font-weight:600;margin-bottom:0.15rem;">{labels[i]}</div><div style="font-size:1.1rem;font-weight:700;color:{DARK_TEXT};font-variant-numeric:tabular-nums;">{fp(r["om"],1,dz=False)}</div><div style="font-size:0.78rem;font-weight:600;color:{DARK_TEXT};margin-top:0.1rem;">{r["name"]}</div><div style="font-size:0.68rem;{d_cls}margin-top:0.1rem;">{d_sign}{delta_pp:.1f}pp vs base</div></div>', unsafe_allow_html=True)

                    st.markdown(f'<div class="sec-sm">Per Unit Cost Comparison ({currency})</div>', unsafe_allow_html=True)
                    st.markdown(build_cost_table(results, currency, target_market), unsafe_allow_html=True)

                    st.markdown(f'<div class="sec-sm">Full Year Impact ({currency})</div>', unsafe_allow_html=True)
                    st.markdown(build_annual_table(results, currency), unsafe_allow_html=True)

                    if len(results) >= 2:
                        st.plotly_chart(build_charts(results, currency), use_container_width=True, config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False})

                    # ── SUB-TABS: Cost Bridge | Sensitivity ──
                    sub_tab_labels = ["Cost Bridge", "Sensitivity Analysis"]
                    sub_tabs = st.tabs(sub_tab_labels)

                    # ── Cost Bridge tab ──
                    with sub_tabs[0]:
                        st.markdown(f'<div class="callout">Waterfall from Net Sales to Operating Profit for each factory. Shows top {min(len(results), 3)} locations.</div>', unsafe_allow_html=True)
                        n_wf = min(len(results), 3)
                        wf_cols = st.columns(n_wf)
                        for wi, wf_r in enumerate(results[:n_wf]):
                            with wf_cols[wi]:
                                st.plotly_chart(build_waterfall_chart(wf_r, currency), use_container_width=True, config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False})
                        if len(results) > 3:
                            st.markdown(f'<div style="font-size:0.7rem;color:{GREY_TEXT};margin-top:0.3rem;">Showing top 3 of {len(results)} locations. All locations included in tables above.</div>', unsafe_allow_html=True)

                    # ── Sensitivity tab ──
                    with sub_tabs[1]:
                        st.markdown(f'<div class="callout">Explore how changes in a single parameter affect operating margin. The <strong>tornado chart</strong> shows the impact on OM when each cost parameter is individually changed by ±20% from its current value — longer bars indicate higher sensitivity. The <strong>line chart</strong> below lets you sweep a single parameter across all factories.</div>', unsafe_allow_html=True)

                        # Tornado chart with factory selector
                        if len(results) >= 2:
                            tornado_factory_names = [r["name"] for r in results[1:]]
                            tc1, tc2 = st.columns([1, 3])
                            with tc1:
                                tornado_sel = st.selectbox("Tornado Factory", tornado_factory_names, key=f"i{item_def['id']}_tornado_fac")
                            tornado_factory = next((f for f in factories if f.name == tornado_sel), None)
                            if tornado_factory:
                                tornado_fig = build_tornado_chart(inputs, tornado_factory, is_base=False, ccy=currency, overrides=get_ov(tornado_factory.name))
                                if tornado_fig:
                                    st.plotly_chart(tornado_fig, use_container_width=True, config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False})

                        sa_params = {
                            "VA Ratio": ("va_ratio", False),
                            "Transport %": ("transport_pct", True),
                            "Tariff %": ("tariff_pct", True),
                            "Duties %": ("duties_pct", True),
                            "Material Cost": ("material", False),
                            "S&A %": ("sa_pct", True),
                        }
                        sa_col1, sa_col2 = st.columns([1, 3])
                        with sa_col1:
                            sa_choice = st.selectbox("Parameter", list(sa_params.keys()), key=f"i{item_def['id']}_sa_param")
                        param_key, is_pct = sa_params[sa_choice]

                        if param_key in ("va_ratio",):
                            steps = [round(v, 2) for v in np.arange(0.4, 1.61, 0.1)]
                        elif is_pct:
                            steps = [round(v, 3) for v in np.arange(0.0, 0.121, 0.01)]
                        else:
                            base_val = getattr(inputs, param_key, 20.0) or 20.0
                            steps = [round(base_val * m, 2) for m in np.arange(0.5, 1.55, 0.1)]

                        fig_sa = build_sensitivity_chart(
                            inputs, factories, base, param_key, sa_choice, steps, currency, is_pct=is_pct
                        )
                        st.plotly_chart(fig_sa, use_container_width=True, config={"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False})

                    inv_results = []

                    # ── QUALITATIVE DATA (read from session state; edited on Strategic Context page) ──
                    qual = {
                        key: st.session_state.get(f"i{item_def['id']}_qual_{key}", "")
                        for key in ("strategic_rationale", "purpose", "risk_of_inaction", "risks")
                    }

                    all_results.append({
                        "inputs": {"item_number": inputs.item_number, "designation": inputs.designation,
                                   "currency": currency, "destination": inputs.destination,
                                   "data_classification": data_classification},
                        "results": results,
                        "investment": inv_results,
                        "qualitative": qual,
                    })

    # Portfolio Summary tab
    with tabs[-1]:
        render_portfolio_summary(all_results, currency, cost_of_capital=cost_of_capital)

    # Store results for investment page
    st.session_state["_all_results"] = all_results
    st.session_state["_cost_of_capital"] = cost_of_capital
    st.session_state["_factory_countries"] = factory_countries

    # ── FOOTER ────────────────────────────────────────────────
    st.markdown("---")
    c1,c2,c3 = st.columns([4,1,1])
    c1.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>Landed Cost Comparison v9.0 &middot; {st.session_state.project_name} &middot; {len(st.session_state.project_items)} item{'s' if len(st.session_state.project_items)!=1 else ''} &middot; {currency} &middot; Market: {target_market} &middot; {data_classification}</span>", unsafe_allow_html=True)
    if all_results:
        _ = c2.download_button("Export Excel", data=export_excel_project(all_results),
            file_name=f"Landed_Cost_{st.session_state.project_name.replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        _ = c3.download_button("Export PDF", data=export_pdf_project(all_results, currency, st.session_state.project_name),
            file_name=f"Landed_Cost_{st.session_state.project_name.replace(' ','_')}.pdf",
            mime="application/pdf")
    dc_short = data_classification.split(" - ")[0] if " - " in data_classification else data_classification
    st.markdown(f'<div class="conf-footer">{data_classification} &mdash; SKF Group &mdash; Strategic Planning &amp; Intelligent Hub &mdash; {date.today().strftime("%B %Y")}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
