"""
Manufacturing Location Analyzer - v6.0
Multi-Item Project-Based Production Cost & Profitability Analysis
Author: Jonas Henriksson — Head of Strategic Planning & Intelligent Hub
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
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
from landed_cost.formatters import fn, fp, fi, fa, dc
from landed_cost.constants import (
    NAVY, DARK_TEXT, GREY_TEXT, ACCENT_BLUE, BASE_CASE_BG, BORDER,
    GREEN, RED, MUTED, INPUT_BLUE, CURRENCIES, COUNTRIES,
)

# Constants, models, compute engine, formatters, and lead times
# are imported from the landed_cost package (see landed_cost/ directory).

# ── PLOTLY GLOBAL FONT ────────────────────────────────────
# Set default font for all Plotly charts to match the app typography.
_plotly_template = go.layout.Template()
_plotly_template.layout.font = dict(family="Inter, Arial, Helvetica, sans-serif")
pio.templates["ib"] = _plotly_template
pio.templates.default = "plotly+ib"


# ── PAGE CONFIG ───────────────────────────────────────────
st.set_page_config(page_title="Manufacturing Location Analyzer", layout="wide", initial_sidebar_state="expanded")

# ── BLUE INPUT BORDER CSS HELPER ──────────────────────────
# Builds CSS rules for key-based targeting (.st-key-{key})
# Fixed keys from main() in A5, dynamic item keys matched via attribute selectors
INPUT_EDITOR_KEYS = [
    "proj_name", "proj_ccy", "proj_tm", "proj_dt",
    "fc_editor", "country_editor", "assumption_matrix", "nwc_matrix",
    "wacc_editor", "target_pb_editor", "target_om_editor", "coc_editor",
    # Governance template inputs
    "ps_dep_editor", "ps_timeline_editor",
    "prop_risks_editor", "prop_fin_editor",
    "td_base_editor", "td_commercial_editor", "td_supply_editor", "td_financial_editor",
]
_blue_border = f"border-left: 3px solid {INPUT_BLUE} !important; padding-left: 2px;"
_fixed_rules = "\n".join(f"    .st-key-{k} {{ {_blue_border} }}" for k in INPUT_EDITOR_KEYS)
# Dynamic item keys: i0_txt, i1_ns, i2_ov, etc. — use attribute selectors
_dynamic_rules = """    [class*="st-key-"][class*="_txt"] { %(bb)s }
    [class*="st-key-"][class*="_ns"] { %(bb)s }
    [class*="st-key-"][class*="_ov"] { %(bb)s }
    [class*="st-key-"][class*="_inv_matrix"] { %(bb)s }
    [class*="st-key-"][class*="_inv_hz"] { %(bb)s }
    [class*="st-key-ps_"] { %(bb)s }
    [class*="st-key-prop_"] { %(bb)s }
    [class*="st-key-td_"] { %(bb)s }""" % {"bb": _blue_border}

st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)
# Inject Inter font into Plotly iframes (Streamlit renders charts in iframes
# that don't inherit the parent document's stylesheets).
# We render charts via components.html() with Inter loaded directly in the HTML.
def plotly_chart(fig, *, config=None, height=None):
    """Render a Plotly figure with Inter font via components.html()."""
    if config is None:
        config = {"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False}
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config=config,
    )
    # Determine chart height from layout or default
    h = height or fig.layout.height or 420
    full = f"""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>* {{ font-family: Inter, -apple-system, BlinkMacSystemFont, sans-serif !important; }}</style>
    {html}
    """
    components.html(full, height=h + 20, scrolling=False)
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp {{ font-family: 'Inter', -apple-system, sans-serif; background-color: #ffffff; }}
    .block-container {{ padding: 1.5rem 2.5rem; max-width: 1400px; }}
    #MainMenu, footer {{visibility: hidden;}}
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] div:last-child {{
        display: none !important;
    }}
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] *,
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploaderDropzoneInstructions"],
    [data-testid="stFileUploaderDropzoneInstructions"] div,
    [data-testid="stFileUploaderDropzoneInstructions"] span {{
        font-family: 'Inter', sans-serif !important;
        font-size: 0.72rem !important;
    }}
    [data-testid="stFileUploader"] button,
    [data-testid="stFileUploader"] button * {{
        font-family: 'Inter', sans-serif !important;
        font-size: 0.72rem !important;
    }}
    .stDownloadButton button,
    [data-testid="stDownloadButton"] button {{
        font-family: 'Inter', sans-serif !important;
        font-size: 0.76rem !important;
        font-weight: 500 !important;
        border-radius: 1px !important;
        border: 1px solid #ccc !important;
        padding: 0.3rem 0.9rem !important;
        min-height: 0 !important;
        height: auto !important;
    }}
    .stDownloadButton button *,
    .stDownloadButton button p,
    .stDownloadButton button span,
    [data-testid="stDownloadButton"] button * {{
        font-family: 'Inter', sans-serif !important;
        font-size: 0.76rem !important;
        font-weight: 500 !important;
    }}
    /* Main-area buttons (Add Item, Remove Last, etc.) */
    .main .stButton > button,
    .main [data-testid="stButton"] > button,
    .main button[kind="secondary"],
    .main .stButton button,
    [data-testid="stMainBlockContainer"] button {{
        font-family: 'Inter', sans-serif !important;
        font-size: 0.76rem !important;
        font-weight: 500 !important;
        border-radius: 1px !important;
        border: 1px solid #ccc !important;
        padding: 0.3rem 0.9rem !important;
        min-height: 0 !important;
        height: auto !important;
    }}
    .stCheckbox label,
    [data-testid="stCheckbox"] label {{
        display: flex !important;
        align-items: center !important;
        gap: 0.4rem !important;
    }}
    .stCheckbox label span,
    .stCheckbox label p,
    [data-testid="stCheckbox"] label span,
    [data-testid="stCheckbox"] label p {{
        font-family: 'Inter', sans-serif !important;
        font-size: 0.76rem !important;
        line-height: 1 !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    /* Square checkbox */
    .stCheckbox svg,
    [data-testid="stCheckbox"] svg,
    .stCheckbox label > div:first-child,
    [data-testid="stCheckbox"] label > div:first-child,
    [data-testid="stCheckbox"] label > div:first-child > div,
    [data-baseweb="checkbox"] div[data-testid="stMarkdownContainer"],
    [data-baseweb="checkbox"] > div {{
        border-radius: 1px !important;
    }}
    header {{background: transparent !important; height: 0 !important; min-height: 0 !important; padding: 0 !important;}}
    header [data-testid="stDecoration"] {{display: none;}}
    /* Sidebar toggle — navy button with white arrow, fixed top-left */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] {{position: fixed; top: 0.5rem; left: 0.5rem; z-index: 999; background: {NAVY}; border-radius: 4px; padding: 0.25rem;}}
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg {{fill: white !important; color: white !important; stroke: white !important;}}
    [data-testid="stSidebarCollapseButton"] button {{background: transparent !important; border: none !important; color: white !important;}}
    /* Close button inside expanded sidebar */
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {{position: static; background: {NAVY}; border-radius: 4px; padding: 0.25rem;}}
    section[data-testid="stSidebar"] button[kind="header"] {{color: white !important; background: {NAVY} !important; border: none !important;}}
    section[data-testid="stSidebar"] {{
        min-width: 21rem !important; max-width: 21rem !important;
        background: #f0f2f6 !important;
    }}
    section[data-testid="stSidebar"] > div {{
        background: #f0f2f6 !important;
    }}
    .stMainBlockContainer {{ padding-top: 0 !important; }}
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

    /* ── IB Header (fixed) ── */
    .ib-header {{
        background: #f0f2f6;
        color: {NAVY}; padding: 0.8rem 1.8rem 0.7rem;
        display: flex; align-items: center; justify-content: space-between;
        border-bottom: 1px solid #d4d8e0;
        position: fixed; top: 0; left: 21rem; right: 0; z-index: 999;
    }}
    .ib-header-spacer {{ height: 4.2rem; }}
    .ib-header-left {{ display: flex; flex-direction: column; }}
    .ib-header h1 {{ font-family: 'Inter', sans-serif; font-size: 1.1rem; font-weight: 700; margin: 0 0 0.1rem 0; letter-spacing: -0.01em; color: {NAVY}; }}
    .ib-header .sub {{ font-size: 0.68rem; color: {GREY_TEXT}; letter-spacing: 0.04em; }}
    .ib-header .skf-logo {{ height: 28px; }}

    /* ── Sections ── */
    .sec {{ font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 700; color: {NAVY};
        text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 2px solid {NAVY};
        padding-bottom: 0.25rem; margin: 1.6rem 0 0.7rem 0; scroll-margin-top: 6rem; }}
    .sec-sm {{ font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: {GREY_TEXT};
        text-transform: uppercase; letter-spacing: 0.08em; margin: 0.7rem 0 0.35rem 0; scroll-margin-top: 6rem; }}

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
        .ib-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; position: static !important; }}
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
        textposition="outside", textfont=dict(size=10, family="Inter, sans-serif", color=DARK_TEXT),
        hovertemplate="%{x}<br>OM: %{y:.1f}%<extra></extra>", showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=names, y=ops, marker_color=colors, text=[fa(v) for v in ops],
        textposition="outside", textfont=dict(size=10, family="Inter, sans-serif", color=DARK_TEXT),
        hovertemplate="%{x}<br>OP: %{y:,.0f}<extra></extra>", showlegend=False), row=1, col=2)
    fig.update_layout(height=400, margin=dict(l=40,r=40,t=45,b=60), paper_bgcolor="white",
        plot_bgcolor="white", font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT))
    # Style subplot titles to match model typography
    for ann in fig.layout.annotations:
        ann.update(font=dict(family="Inter, sans-serif", size=11, color=DARK_TEXT))
    for ax in ["yaxis","yaxis2"]:
        fig.update_layout(**{ax: dict(showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc")})
    fig.update_xaxes(tickangle=0, tickfont=dict(size=10, family="Inter, sans-serif", color=DARK_TEXT))
    fig.update_yaxes(title_text="Margin (%)", row=1, col=1, ticksuffix="%", title_font=dict(size=10, family="Inter, sans-serif"))
    fig.update_yaxes(title_text=ccy, row=1, col=2, title_font=dict(size=10, family="Inter, sans-serif"))
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
        text=[fa(abs(v)) for v in values],
        textfont=dict(size=9, family="Inter, sans-serif", color=DARK_TEXT),
    ))
    fig.update_layout(
        title=dict(text=""),
        height=340, margin=dict(l=40, r=30, t=20, b=50),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=9, color=DARK_TEXT),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title=f"{ccy} per unit", title_font=dict(size=9, family="Inter, sans-serif")),
        xaxis=dict(tickfont=dict(size=9, family="Inter, sans-serif")),
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
            font=dict(size=8, family="Inter, sans-serif", color=left_color),
        )
        fig.add_annotation(
            x=right_v, y=label, text=f"{right_lbl}: {right_v:+.1f}pp",
            showarrow=False, xanchor="left", xshift=4,
            font=dict(size=8, family="Inter, sans-serif", color=right_color),
        )

    fig.update_layout(
        title=dict(text=f"Tornado: OM Sensitivity to ±20% Parameter Changes ({factory.name})<br><span style='font-size:9px;color:#666;font-weight:normal'>Each bar shows the impact on Operating Margin when a single cost parameter is changed by ±20% from its current value</span>", font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT)),
        height=max(250, 50 * len(bars) + 80), barmode="overlay",
        margin=dict(l=120, r=60, t=60, b=40),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
        xaxis=dict(title="Change in OM (percentage points)", showgrid=True, gridcolor="#f0f0f0", zeroline=False, ticksuffix="pp",
                   title_font=dict(size=10, family="Inter, sans-serif"), tickfont=dict(size=10, family="Inter, sans-serif")),
        yaxis=dict(showgrid=False, tickfont=dict(size=10, family="Inter, sans-serif")),
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
        title=dict(text=f"Sensitivity: Operating Margin vs. {param_label}", font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT)),
        height=380, margin=dict(l=50, r=30, t=50, b=50),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
        xaxis=dict(title=f"{param_label}{' (%)' if is_pct else ''}", showgrid=True, gridcolor="#eee"),
        yaxis=dict(title="Operating Margin (%)", showgrid=True, gridcolor="#eee", ticksuffix="%"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ── PORTFOLIO WATERFALL (COST BRIDGE) ─────────────────────────
def build_portfolio_waterfall(all_results, factory_name, ccy):
    """Build a waterfall chart aggregating annual cost components across all items for one factory."""
    total_rev = 0.0
    total_ps = 0.0
    total_sa = 0.0
    total_tar = 0.0
    total_dut = 0.0
    total_trn = 0.0
    total_nwc = 0.0
    total_op = 0.0

    for item in all_results:
        for r in item["results"]:
            if r["name"] == factory_name:
                qty = r["annual_rev"] / r["ns_per_unit"] if r["ns_per_unit"] else 0
                total_rev += r["annual_rev"]
                total_ps += r["ps"] * qty
                total_sa += r["sa"] * qty
                total_tar += r["tariff"] * qty
                total_dut += r["duties"] * qty
                total_trn += r["transport"] * qty
                total_nwc += r.get("nwc_carrying_cost_annual", 0)
                total_op += r["annual_op"]

    labels = ["Net Sales", "Price Std.", "S&A", "Tariff", "Duties", "Transport", "NWC Cost", "Op. Profit"]
    values = [total_rev, -total_ps, -total_sa, -total_tar, -total_dut, -total_trn, -total_nwc, total_op]
    measures = ["absolute", "relative", "relative", "relative", "relative", "relative", "relative", "total"]

    filtered = [(l, v, m) for l, v, m in zip(labels, values, measures) if abs(v) > 0.005 or m in ("absolute", "total")]
    labels, values, measures = zip(*filtered) if filtered else (labels, values, measures)

    fig = go.Figure(go.Waterfall(
        x=list(labels), y=list(values), measure=list(measures),
        connector=dict(line=dict(color="#ccc", width=1)),
        increasing=dict(marker=dict(color="#e8f5e9", line=dict(color=GREEN, width=1))),
        decreasing=dict(marker=dict(color="#ffebee", line=dict(color=RED, width=1))),
        totals=dict(marker=dict(color=NAVY if total_op >= 0 else RED, line=dict(color=NAVY if total_op >= 0 else RED, width=1))),
        textposition="outside",
        text=[fa(abs(v)) for v in values],
        textfont=dict(size=9, family="Inter, sans-serif", color=DARK_TEXT),
    ))
    fig.update_layout(
        title=dict(text=""),
        height=340, margin=dict(l=40, r=30, t=20, b=50),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=9, color=DARK_TEXT),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title=f"{ccy} (annual)", title_font=dict(size=9, family="Inter, sans-serif")),
        xaxis=dict(tickfont=dict(size=9, family="Inter, sans-serif")),
        showlegend=False,
    )
    return fig


# ── PORTFOLIO TORNADO CHART ──────────────────────────────────
def build_portfolio_tornado(all_results, all_fnames, ccy):
    """Build a tornado chart showing how ±20% parameter changes affect total portfolio OM."""
    from dataclasses import replace
    factory_attrs = {"va_ratio", "ps_index", "mcl_pct", "sa_pct", "tpl", "tariff_pct", "duties_pct", "transport_pct"}

    # Compute base portfolio OM (all factories, all items)
    base_rev = sum(r["annual_rev"] for item in all_results for r in item["results"])
    base_op = sum(r["annual_op"] for item in all_results for r in item["results"])
    if base_rev == 0:
        return None
    base_om = base_op / base_rev * 100

    params = [
        ("VA Ratio", "va_ratio", False),
        ("PS Index", "ps_index", False),
        ("S&A %", "sa_pct", True),
        ("Transport %", "transport_pct", True),
        ("Tariff %", "tariff_pct", True),
        ("Duties %", "duties_pct", True),
    ]

    bars = []
    for label, param, is_pct in params:
        # Check if any factory has a non-zero value for this param
        has_value = False
        for item in all_results:
            base_f = item.get("_base_factory")
            facs = item.get("_factories", [])
            for f in ([base_f] if base_f else []) + list(facs):
                if f and getattr(f, param, None) not in (None, 0):
                    has_value = True
                    break
            if has_value:
                break
        if not has_value:
            continue

        # Recompute entire portfolio with ±20% on this param across ALL factories
        om_low = _portfolio_om_all_tweaked(all_results, all_fnames, param, 0.8, factory_attrs)
        om_high = _portfolio_om_all_tweaked(all_results, all_fnames, param, 1.2, factory_attrs)
        if om_low is None or om_high is None:
            continue

        d_low = om_low - base_om
        d_high = om_high - base_om
        spread = abs(d_high - d_low)
        if spread < 0.001:
            continue
        bars.append((label, d_low, d_high, spread))

    if not bars:
        return None

    bars.sort(key=lambda x: x[3])
    labels = [b[0] for b in bars]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=[min(b[1], b[2]) for b in bars],
        orientation="h", marker=dict(color="#e8f5e9", line=dict(color=GREEN, width=1)),
        name="-20%", hovertemplate="%{y}: %{x:+.2f}pp<extra>-20%</extra>",
    ))
    fig.add_trace(go.Bar(
        y=labels, x=[max(b[1], b[2]) - min(b[1], b[2]) for b in bars],
        orientation="h", marker=dict(color="#ffebee", line=dict(color=RED, width=1)),
        name="+20%", base=[min(b[1], b[2]) for b in bars],
        hovertemplate="%{y}: %{x:+.2f}pp<extra>+20%</extra>",
    ))
    fig.add_vline(x=0, line=dict(color=NAVY, width=1.5, dash="dot"))

    for i, (lbl, low, high, _) in enumerate(bars):
        left_v = min(low, high)
        right_v = max(low, high)
        left_is_low = (left_v == low)
        left_lbl = "\u221220%" if left_is_low else "+20%"
        right_lbl = "+20%" if left_is_low else "\u221220%"
        left_color = GREEN if left_v > 0 else RED if left_v < 0 else GREY_TEXT
        right_color = GREEN if right_v > 0 else RED if right_v < 0 else GREY_TEXT
        fig.add_annotation(x=left_v, y=lbl, text=f"{left_lbl}: {left_v:+.1f}pp",
            showarrow=False, xanchor="right", xshift=-4, font=dict(size=8, family="Inter, sans-serif", color=left_color))
        fig.add_annotation(x=right_v, y=lbl, text=f"{right_lbl}: {right_v:+.1f}pp",
            showarrow=False, xanchor="left", xshift=4, font=dict(size=8, family="Inter, sans-serif", color=right_color))

    fig.update_layout(
        title=dict(text=f"Portfolio Tornado: OM Sensitivity to \u00b120%<br><span style='font-size:9px;color:#666;font-weight:normal'>Impact on total portfolio Operating Margin when each shared parameter is changed by \u00b120% across all factories</span>", font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT)),
        height=max(250, 50 * len(bars) + 80), barmode="overlay",
        margin=dict(l=120, r=60, t=60, b=40),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
        xaxis=dict(title="Change in OM (percentage points)", showgrid=True, gridcolor="#f0f0f0", zeroline=False, ticksuffix="pp",
                   title_font=dict(size=10, family="Inter, sans-serif"), tickfont=dict(size=10, family="Inter, sans-serif")),
        yaxis=dict(showgrid=False, tickfont=dict(size=10, family="Inter, sans-serif")),
        showlegend=False, dragmode=False,
    )
    return fig


def _portfolio_om_all_tweaked(all_results, all_fnames, param, multiplier, factory_attrs):
    """Recompute total portfolio OM with one parameter scaled by multiplier across ALL factories."""
    from dataclasses import replace
    total_rev = 0.0
    total_op = 0.0
    for item in all_results:
        dc_inputs = item.get("_inputs_dc")
        base_f = item.get("_base_factory")
        facs = item.get("_factories", [])
        get_ov = item.get("_get_ov")
        if not dc_inputs:
            continue
        for fn_ in all_fnames:
            is_base = (base_f and base_f.name == fn_)
            target_f = base_f if is_base else next((f for f in facs if f.name == fn_), None)
            if not target_f:
                continue
            current = getattr(target_f, param, None) if param in factory_attrs else getattr(dc_inputs, param, None)
            if current is None:
                # No tweak possible, use original
                r = compute_location(dc_inputs, target_f, is_base=is_base, overrides=get_ov(fn_) if get_ov else None)
            elif param in factory_attrs:
                tweaked_f = replace(target_f, **{param: current * multiplier})
                r = compute_location(dc_inputs, tweaked_f, is_base=is_base, overrides=get_ov(fn_) if get_ov else None)
            else:
                tweaked_inputs = replace(dc_inputs, **{param: current * multiplier})
                r = compute_location(tweaked_inputs, target_f, is_base=is_base, overrides=get_ov(fn_) if get_ov else None)
            if r:
                total_rev += r["annual_rev"]
                total_op += r["annual_op"]
    return (total_op / total_rev * 100) if total_rev else None


# ── PORTFOLIO SENSITIVITY SWEEP ──────────────────────────────
def build_portfolio_sensitivity_chart(all_results, all_fnames, param_name, param_label, steps, ccy, is_pct=False):
    """Build a line chart showing how portfolio OM changes as param varies across all factories."""
    from dataclasses import replace
    factory_attrs = {"va_ratio", "ps_index", "mcl_pct", "sa_pct", "tpl", "tariff_pct", "duties_pct", "transport_pct"}
    fig = go.Figure()
    colors_cycle = [NAVY, ACCENT_BLUE, GREEN, RED, "#e67e22", "#8e44ad"]

    for idx, fn_ in enumerate(all_fnames):
        x_vals = []
        y_vals = []
        for step_val in steps:
            total_rev = 0.0
            total_op = 0.0
            for item in all_results:
                dc_inputs = item.get("_inputs_dc")
                base_f = item.get("_base_factory")
                facs = item.get("_factories", [])
                get_ov = item.get("_get_ov")
                if not dc_inputs:
                    continue

                is_base = (base_f and base_f.name == fn_)
                target_f = base_f if is_base else next((f for f in facs if f.name == fn_), None)
                if not target_f:
                    continue

                if param_name in factory_attrs:
                    tweaked_f = replace(target_f, **{param_name: step_val})
                    r = compute_location(dc_inputs, tweaked_f, is_base=is_base, overrides=get_ov(fn_) if get_ov else None)
                else:
                    tweaked_inputs = replace(dc_inputs, **{param_name: step_val})
                    r = compute_location(tweaked_inputs, target_f, is_base=is_base, overrides=get_ov(fn_) if get_ov else None)
                if r:
                    total_rev += r["annual_rev"]
                    total_op += r["annual_op"]

            om = (total_op / total_rev * 100) if total_rev else 0
            x_vals.append(step_val * 100 if is_pct else step_val)
            y_vals.append(om)

        color = colors_cycle[idx % len(colors_cycle)]
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode="lines+markers", name=fn_,
            line=dict(color=color, width=3 if idx == 0 else 2),
            marker=dict(size=5),
            hovertemplate=f"{fn_}<br>{param_label}: %{{x:.1f}}{'%' if is_pct else ''}<br>OM: %{{y:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text=f"Portfolio Sensitivity: Operating Margin vs. {param_label}", font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT)),
        height=380, margin=dict(l=50, r=30, t=50, b=50),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
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
                ws.write(r,0,"Required Investments",hl)
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

        # ── GOVERNANCE SHEETS ────────────────────────────────
        # Pre-study sheet
        ws = wb.add_worksheet("Pre-study")
        w.sheets["Pre-study"] = ws
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 50)
        ws.merge_range(0, 0, 0, 1, f"Pre-study | {st.session_state.get('project_name', '')}", tf)
        r = 2
        for label, key in [("Strategic Rationale", "ps_strategic_rationale"),
                           ("Purpose & Objective", "ps_purpose"),
                           ("Background & Current Set-up", "ps_background"),
                           ("Reason to Change", "ps_reason"),
                           ("Risk of Inaction", "ps_risk_of_inaction"),
                           ("Key Risks & Mitigations", "ps_key_risks"),
                           ("Key Questions", "ps_questions")]:
            ws.write(r, 0, label, hl)
            ws.write(r, 1, st.session_state.get(key, ""), lf)
            r += 1
        r += 1
        ws.write(r, 0, "Team", hl); ws.write(r, 1, "", hl); r += 1
        for label, key in [("Initiative Sponsor", "ps_sponsor"), ("Initiative Lead", "ps_lead"),
                           ("Main Entity(s)", "ps_main_entity"), ("Impact on Other Entities", "ps_impact_entities"),
                           ("Pre-study Team", "ps_team")]:
            ws.write(r, 0, label, lf)
            ws.write(r, 1, st.session_state.get(key, ""), lf)
            r += 1
        r += 1
        ws.write(r, 0, "Time Plan", hl); ws.write(r, 1, "", hl); r += 1
        for ms, dt in st.session_state.get("ps_timeline", {}).items():
            ws.write(r, 0, ms, lf); ws.write(r, 1, str(dt), lf); r += 1

        # Proposal sheet
        ws = wb.add_worksheet("Proposal")
        w.sheets["Proposal"] = ws
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 50)
        ws.merge_range(0, 0, 0, 1, f"Proposal | {st.session_state.get('project_name', '')}", tf)
        r = 2
        for label, key in [("Direction", "prop_direction"), ("Benefits & Key Details", "prop_benefits"),
                           ("Time Plan", "prop_timeplan")]:
            ws.write(r, 0, label, hl)
            ws.write(r, 1, st.session_state.get(key, ""), lf)
            r += 1
        r += 1
        ws.write(r, 0, "Team", hl); ws.write(r, 1, "", hl); r += 1
        for label, key in [("Initiative Sponsor", "ps_sponsor"), ("Initiative Lead", "ps_lead"),
                           ("Main Entity(s)", "ps_main_entity"), ("Pre-study Team", "ps_team")]:
            ws.write(r, 0, label, lf); ws.write(r, 1, st.session_state.get(key, ""), lf); r += 1

        # Transfer Details sheet
        ws = wb.add_worksheet("Transfer Details")
        w.sheets["Transfer Details"] = ws
        ws.set_column(0, 0, 34)
        ws.set_column(1, 6, 18)
        ws.merge_range(0, 0, 0, 6, f"Transfer Details | {st.session_state.get('project_name', '')}", tf)
        r = 2
        for label, key in [("Transfer From", "td_transfer_from"), ("Transfer To", "td_transfer_to"),
                           ("Product Line", "td_product_line"), ("Material Family", "td_material_family"),
                           ("Transfer Volume", "td_transfer_volume"), ("Indicative Timing", "td_indicative_timing")]:
            ws.write(r, 0, label, lb); ws.write(r, 1, st.session_state.get(key, ""), lf); r += 1
        r += 1
        td_reqs = st.session_state.get("td_requirements", {})
        td_cols = ["Requirement", "Value", "Follow-up", "Follow-up Answer", "Approver", "Date", "Status", "Required Documents"]
        for section, rows in td_reqs.items():
            ws.merge_range(r, 0, r, 6, section, sf) if 6 > 0 else ws.write(r, 0, section, sf)
            r += 1
            for ci, col in enumerate(td_cols):
                ws.write(r, ci, col, hf)
            r += 1
            for row in rows:
                for ci, col in enumerate(td_cols):
                    ws.write(r, ci, str(row.get(col, "")), lf)
                r += 1
            r += 1

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

    # ── GOVERNANCE PAGES ────────────────────────────────────
    def _safe(txt):
        return (txt or "").encode("latin-1", "replace").decode("latin-1")

    # Pre-study page
    ps_strat = st.session_state.get("ps_strategic_rationale", "")
    ps_purpose = st.session_state.get("ps_purpose", "")
    ps_bg = st.session_state.get("ps_background", "")
    ps_reason = st.session_state.get("ps_reason", "")
    ps_inaction = st.session_state.get("ps_risk_of_inaction", "")
    ps_risks = st.session_state.get("ps_key_risks", "")
    ps_questions = st.session_state.get("ps_questions", "")
    ps_all = (ps_strat, ps_purpose, ps_bg, ps_reason, ps_inaction, ps_risks, ps_questions)
    if any(s.strip() for s in ps_all):
        pdf.add_page()
        add_page_header(pdf, f"Pre-study | {project_name}", f"{ccy}")
        for label, txt in [("Strategic Rationale", ps_strat),
                           ("Purpose & Objective", ps_purpose),
                           ("Background & Current Set-up", ps_bg),
                           ("Reason to Change", ps_reason),
                           ("Risk of Inaction", ps_inaction),
                           ("Key Risks & Mitigations", ps_risks),
                           ("Key Questions to Review", ps_questions)]:
            if txt.strip():
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(navy_r, navy_g, navy_b)
                pdf.set_text_color(white_r, white_g, white_b)
                pdf.cell(0, 5.5, label, ln=True, fill=True)
                pdf.set_text_color(dark_r, dark_g, dark_b)
                pdf.set_font("Helvetica", "", 7)
                pdf.multi_cell(0, 4, _safe(txt))
                pdf.ln(2)
        # Team
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(navy_r, navy_g, navy_b)
        pdf.set_text_color(white_r, white_g, white_b)
        pdf.cell(0, 5.5, "Team", ln=True, fill=True)
        pdf.set_text_color(dark_r, dark_g, dark_b)
        pdf.set_font("Helvetica", "", 7)
        for label, key in [("Initiative Sponsor", "ps_sponsor"), ("Initiative Lead", "ps_lead"),
                           ("Main Entity(s)", "ps_main_entity"), ("Pre-study Team", "ps_team")]:
            val = st.session_state.get(key, "")
            if val.strip():
                pdf.set_font("Helvetica", "B", 6.5)
                pdf.cell(45, 4.5, label, border=0)
                pdf.set_font("Helvetica", "", 6.5)
                pdf.cell(0, 4.5, _safe(val), ln=True)

    # Proposal page
    prop_dir = st.session_state.get("prop_direction", "")
    prop_ben = st.session_state.get("prop_benefits", "")
    if any(s.strip() for s in (prop_dir, prop_ben)):
        pdf.add_page()
        add_page_header(pdf, f"Proposal | {project_name}", f"{ccy}")
        for label, key in [("Direction", "prop_direction"), ("Benefits & Key Details", "prop_benefits")]:
            txt = st.session_state.get(key, "")
            if txt.strip():
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_fill_color(navy_r, navy_g, navy_b)
                pdf.set_text_color(white_r, white_g, white_b)
                pdf.cell(0, 5.5, label, ln=True, fill=True)
                pdf.set_text_color(dark_r, dark_g, dark_b)
                pdf.set_font("Helvetica", "", 7)
                pdf.multi_cell(0, 4, _safe(txt))
                pdf.ln(2)

    # Transfer Details page
    td_reqs = st.session_state.get("td_requirements", {})
    has_td = any(r.get("Value", "").strip() or r.get("Status", "") != "Pending"
                 for rows in td_reqs.values() for r in rows)
    if has_td:
        pdf.add_page("L")  # Landscape for the wide table
        add_page_header(pdf, f"Transfer Details | {project_name}", f"{ccy}")
        # Header fields
        pdf.set_font("Helvetica", "B", 7)
        for label, key in [("Transfer From", "td_transfer_from"), ("Transfer To", "td_transfer_to"),
                           ("Product Line", "td_product_line"), ("Transfer Volume", "td_transfer_volume")]:
            pdf.cell(30, 4.5, label + ":", border=0)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(40, 4.5, _safe(st.session_state.get(key, "")), border=0)
            pdf.set_font("Helvetica", "B", 7)
        pdf.ln(6)
        # Requirements tables
        td_col_w = [65, 35, 30, 22, 22, 30]
        td_hdrs = ["Requirement", "Value / Answer", "Approver", "Date", "Status", "Req. Documents"]
        td_keys = ["Requirement", "Value", "Approver", "Date", "Status", "Required Documents"]
        for section, rows in td_reqs.items():
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_fill_color(navy_r, navy_g, navy_b)
            pdf.set_text_color(white_r, white_g, white_b)
            pdf.cell(sum(td_col_w), 5, section, ln=True, fill=True)
            pdf.set_text_color(dark_r, dark_g, dark_b)
            pdf.set_font("Helvetica", "B", 6)
            for ci, h in enumerate(td_hdrs):
                pdf.cell(td_col_w[ci], 4.5, h, border=1)
            pdf.ln()
            pdf.set_font("Helvetica", "", 6)
            for row in rows:
                for ci, col in enumerate(td_keys):
                    pdf.cell(td_col_w[ci], 4.5, _safe(str(row.get(col, ""))), border=1)
                pdf.ln()
                # Follow-up row if applicable
                follow_up = row.get("Follow-up", "")
                follow_up_ans = row.get("Follow-up Answer", "")
                cond = row.get("Condition", "")
                if follow_up and (cond != "if_no" or (row.get("Value", "").strip().lower() in ("no", "n", "false", "0"))):
                    prefix = "If no: " if cond == "if_no" else ""
                    pdf.set_font("Helvetica", "I", 6)
                    pdf.cell(td_col_w[0], 4.5, _safe(f"  > {prefix}{follow_up}"), border=1)
                    pdf.set_font("Helvetica", "", 6)
                    pdf.cell(td_col_w[1], 4.5, _safe(follow_up_ans), border=1)
                    for ci in range(2, len(td_col_w)):
                        pdf.cell(td_col_w[ci], 4.5, "", border=1)
                    pdf.ln()
            pdf.ln(2)

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
     "material":18.96,"variable_va":2.26,"fixed_va":2.57,
     "sales_projection":[
         {"year":1,"value":121280000.0,"qty":2570000},
         {"year":2,"value":125720000.0,"qty":2660000},
         {"year":3,"value":130400000.0,"qty":2760000},
         {"year":4,"value":135200000.0,"qty":2850000},
         {"year":5,"value":140400000.0,"qty":2950000},
     ]},
    {"item_number":"2045","designation":"Seal Kit HT-500","destination":"Northern Europe",
     "comment":"New product launch evaluation","net_sales_value":45600000.0,"net_sales_qty":1200000,
     "material":12.50,"variable_va":1.80,"fixed_va":1.95,
     "sales_projection":[
         {"year":1,"value":45600000.0,"qty":1200000},
         {"year":2,"value":49400000.0,"qty":1300000},
         {"year":3,"value":53200000.0,"qty":1400000},
         {"year":4,"value":57000000.0,"qty":1500000},
         {"year":5,"value":60800000.0,"qty":1600000},
     ]},
]


# ── GOVERNANCE TEMPLATE HELPERS ─────────────────────────────────
# Transfer Details requirements:
# Each tuple: (main_question, follow_up_question_or_None, follow_up_condition, required_docs)
# follow_up_condition: "if_no" means only show follow-up when main answer is No/no;
#                      None means always show the follow-up (stacked below main).
_TD_BASE_REQS = [
    ("Tail-end threshold (Q)", "Transfer volume (Q)", None, ""),
    ("Factory strategy (Flexible/volume)", "Transfer volume type (Flexible/volume)", None, ""),
    ("Established skills and capabilities (yes/no)", "Approved plan to establish capability?", "if_no", "High-level plan"),
    ("Macro stability (yes/no)", "Approval to move ahead?", "if_no", "Risk assessment"),
    ("Remaining capacity (Q)", "Expected demand Y+5 (Q)", None, ""),
]
_TD_COMMERCIAL_REQS = [
    ("Confirmed acceptance rate (yes/no)", "Comment", None, ""),
    ("Customer approval (yes/no)", "Comment", None, ""),
    ("Current market demand in region (Q)", "Expected 5-year CAGR", None, ""),
    ("Technology relevancy confirmed (yes/no)", "Comment", None, ""),
]
_TD_SUPPLY_REQS = [
    ("Aligned with Global product line manager", "Comment", None, ""),
    ("Established supply chain (yes/no)", "Approved plan to establish supply?", "if_no", "High-level plan"),
]
_TD_FINANCIAL_REQS = [
    ("Business case for both units in place", "Expected investment (Both units, MSEK)", None, "Business case"),
    ("Payback period (Both units, Years)", "Expected total IRR (Both units, %)", None, ""),
    ("NWC impact assessed (yes/no)", "Expected delta NWC vs. base (MSEK)", None, ""),
]


def _default_td_requirements():
    """Build the default transfer details requirements structure."""
    sections = {
        "Base Requirements": _TD_BASE_REQS,
        "Commercial Requirements": _TD_COMMERCIAL_REQS,
        "Product Line & Supply Chain Requirements": _TD_SUPPLY_REQS,
        "Financial Requirements": _TD_FINANCIAL_REQS,
    }
    result = {}
    for section, rows in sections.items():
        result[section] = []
        for main_q, follow_up_q, condition, support_doc in rows:
            result[section].append({
                "Requirement": main_q,
                "Value": "",
                "Follow-up": follow_up_q or "",
                "Follow-up Answer": "",
                "Condition": condition or "",
                "Approver": "",
                "Date": "",
                "Status": "Pending",
                "Required Documents": support_doc,
            })
    return result


# ── SESSION STATE INIT ──────────────────────────────────────────
def init_state():
    if "project_name" not in st.session_state:
        st.session_state.project_name = "New Analysis"
    if "project_items" not in st.session_state:
        st.session_state.project_items = [{"id": 0}]
    if "next_id" not in st.session_state:
        st.session_state.next_id = 1
    if "ex" not in st.session_state:
        st.session_state.ex = False
    if "active_page" not in st.session_state:
        st.session_state.active_page = "model"
    # ── GOVERNANCE TEMPLATE DEFAULTS ─────────────────────────
    if "ps_strategic_rationale" not in st.session_state:
        st.session_state.ps_strategic_rationale = ""
    if "ps_purpose" not in st.session_state:
        st.session_state.ps_purpose = ""
    if "ps_risk_of_inaction" not in st.session_state:
        st.session_state.ps_risk_of_inaction = ""
    if "ps_key_risks" not in st.session_state:
        st.session_state.ps_key_risks = ""
    if "ps_background" not in st.session_state:
        st.session_state.ps_background = ""
    if "ps_reason" not in st.session_state:
        st.session_state.ps_reason = ""
    if "ps_questions" not in st.session_state:
        st.session_state.ps_questions = ""
    if "ps_dependencies" not in st.session_state:
        st.session_state.ps_dependencies = [{"Dependency": "", "How to Manage": ""}]
    if "ps_sponsor" not in st.session_state:
        st.session_state.ps_sponsor = ""
    if "ps_lead" not in st.session_state:
        st.session_state.ps_lead = ""
    if "ps_main_entity" not in st.session_state:
        st.session_state.ps_main_entity = ""
    if "ps_impact_entities" not in st.session_state:
        st.session_state.ps_impact_entities = ""
    if "ps_team" not in st.session_state:
        st.session_state.ps_team = ""
    if "ps_timeline" not in st.session_state:
        st.session_state.ps_timeline = {
            "Pre-study Finalized": "", "Pre-study to FC": "",
            "IRE Submission": "", "IRE to IC": "", "Project Execution Start": "",
        }
    if "prop_direction" not in st.session_state:
        st.session_state.prop_direction = ""
    if "prop_benefits" not in st.session_state:
        st.session_state.prop_benefits = ""
    if "prop_total_investment" not in st.session_state:
        st.session_state.prop_total_investment = None
    if "prop_cash_out" not in st.session_state:
        st.session_state.prop_cash_out = None
    if "prop_timeplan" not in st.session_state:
        st.session_state.prop_timeplan = ""
    if "prop_risks" not in st.session_state:
        st.session_state.prop_risks = [{"Risk": "", "Mitigation": ""}]
    # prop_sponsor, prop_lead, prop_team removed — Proposal reads from Pre-study team
    if "td_transfer_to" not in st.session_state:
        st.session_state.td_transfer_to = ""
    if "td_transfer_from" not in st.session_state:
        st.session_state.td_transfer_from = ""
    if "td_product_line" not in st.session_state:
        st.session_state.td_product_line = ""
    if "td_material_family" not in st.session_state:
        st.session_state.td_material_family = ""
    if "td_transfer_volume" not in st.session_state:
        st.session_state.td_transfer_volume = ""
    if "td_indicative_timing" not in st.session_state:
        st.session_state.td_indicative_timing = ""
    if "td_requirements" not in st.session_state:
        st.session_state.td_requirements = _default_td_requirements()


# ── ITEM ANALYSIS RENDERER ───────────────────────────────────────
def render_item(idx, item_id, base_factory_name_shared, factory_col_names_shared, num_factories, ex):
    pfx = f"i{item_id}_"
    today = date.today()

    # Item header — batch data overrides example data
    batch = st.session_state.get(f"{pfx}batch_data")
    ex_item = EXAMPLE_ITEMS[idx] if ex and idx < len(EXAMPLE_ITEMS) else None
    if batch:
        ex_item = batch  # batch upload data takes priority

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

    # Sales projection (3-5 year)
    st.markdown('<div class="sec-sm">Sales Projection</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.65rem;color:{GREY_TEXT};margin:-0.3rem 0 0.4rem 0;font-style:italic;">Year 1 (base year) is used for item cost comparisons. Full projection feeds the investment case.</div>', unsafe_allow_html=True)

    n_proj_years = st.session_state.get(f"{pfx}n_proj_years", 5)
    n_proj_years = st.selectbox("Projection years", [3, 4, 5], index=[3, 4, 5].index(n_proj_years), key=f"{pfx}n_proj_years_sel")
    st.session_state[f"{pfx}n_proj_years"] = n_proj_years

    # Build projection table
    ex_proj = ex_item.get("sales_projection", []) if ex_item else []
    proj_data = {"Year": [f"Y{y}" for y in range(1, n_proj_years + 1)]}
    proj_vals = []
    proj_qtys = []
    for y in range(1, n_proj_years + 1):
        ex_row = next((p for p in ex_proj if p["year"] == y), None) if ex_proj else None
        if ex_row:
            proj_vals.append(float(ex_row["value"]))
            proj_qtys.append(float(ex_row["qty"]))
        elif y == 1 and ex_item:
            proj_vals.append(float(ex_item["net_sales_value"]))
            proj_qtys.append(float(ex_item["net_sales_qty"]))
        else:
            proj_vals.append(0.0)
            proj_qtys.append(0.0)
    proj_data["Net Sales (Value)"] = proj_vals
    proj_data["Net Sales (Qty)"] = proj_qtys
    proj_df = pd.DataFrame(proj_data).set_index("Year")

    edited_proj = st.data_editor(
        proj_df, use_container_width=True, num_rows="fixed", key=f"{pfx}proj",
        column_config={
            "Net Sales (Value)": st.column_config.NumberColumn("Net Sales (Value)", format="%,.0f", width=200),
            "Net Sales (Qty)": st.column_config.NumberColumn("Net Sales (Qty)", format="%,.0f", width=200),
        },
    )

    # Extract projection and base year values
    sales_projection = []
    for y in range(1, n_proj_years + 1):
        row_label = f"Y{y}"
        v = float(edited_proj.loc[row_label, "Net Sales (Value)"] or 0)
        q = int(edited_proj.loc[row_label, "Net Sales (Qty)"] or 0)
        sales_projection.append({"year": y, "value": v, "qty": q})

    net_sales_value = sales_projection[0]["value"] if sales_projection else 0.0
    net_sales_qty = sales_projection[0]["qty"] if sales_projection else 0

    # CAGR details
    if len(sales_projection) >= 2 and net_sales_value > 0 and net_sales_qty > 0:
        last_p = sales_projection[-1]
        n_years = len(sales_projection) - 1
        val_y1, val_yn = net_sales_value, last_p["value"]
        qty_y1, qty_yn = net_sales_qty, last_p["qty"]
        val_cagr = ((val_yn / val_y1) ** (1 / n_years) - 1) * 100 if val_y1 > 0 and val_yn > 0 else 0.0
        qty_cagr = ((qty_yn / qty_y1) ** (1 / n_years) - 1) * 100 if qty_y1 > 0 and qty_yn > 0 else 0.0
        price_y1 = val_y1 / qty_y1 if qty_y1 else 0
        price_yn = val_yn / qty_yn if qty_yn else 0
        price_cagr = ((price_yn / price_y1) ** (1 / n_years) - 1) * 100 if price_y1 > 0 and price_yn > 0 else 0.0
        cagr_html = (
            f'<div style="font-family:Inter,sans-serif;font-size:0.68rem;color:{GREY_TEXT};margin:0.2rem 0 0.5rem 0;">'
            f'CAGR (Y1\u2013Y{n_proj_years}): '
            f'Revenue <strong>{val_cagr:+.1f}%</strong> &nbsp;\u00b7&nbsp; '
            f'Volume <strong>{qty_cagr:+.1f}%</strong> &nbsp;\u00b7&nbsp; '
            f'Price/Unit <strong>{price_cagr:+.1f}%</strong>'
            f'</div>'
        )
        st.markdown(cagr_html, unsafe_allow_html=True)

    # Base costs (per unit)
    _base_fn_display = base_factory_name_shared or "Base Factory"
    st.markdown(f'<div class="sec-sm">Base Costs (Per Unit) — {_base_fn_display}</div>', unsafe_allow_html=True)

    bc_data = {
        "Field": ["Material", "Variable VA", "Fixed VA"],
        "Value": [
            ex_item["material"] if ex_item else 0.0,
            ex_item["variable_va"] if ex_item else 0.0,
            ex_item["fixed_va"] if ex_item else 0.0,
        ],
        "Guide": [
            f"Direct material cost per unit at {_base_fn_display}",
            f"Variable VA cost per unit at {_base_fn_display}",
            f"Fixed VA cost per unit at {_base_fn_display}",
        ]
    }
    bc_df = pd.DataFrame(bc_data).set_index("Field")

    edited_bc = st.data_editor(
        bc_df, use_container_width=True, num_rows="fixed", key=f"{pfx}bc",
        column_config={
            "Value": st.column_config.NumberColumn("Value", format="%,.2f", width=200),
            "Guide": st.column_config.TextColumn("Guide", width=300, disabled=True),
        },
        disabled=["Guide"],
    )

    material = float(edited_bc.loc["Material", "Value"] or 0)
    variable_va = float(edited_bc.loc["Variable VA", "Value"] or 0)
    fixed_va = float(edited_bc.loc["Fixed VA", "Value"] or 0)

    inputs = ItemInputs(item_number, designation, st.session_state.get("currency","SEK"),
                        destination, "", comment, net_sales_value, net_sales_qty,
                        material, variable_va, fixed_va, sales_projection)

    if inputs.net_sales_qty == 0 or inputs.net_sales_value == 0:
        st.markdown('<div class="callout">Enter Year 1 Net Sales values to see results.</div>', unsafe_allow_html=True)
        return None

    # Cost overrides
    st.markdown('<div class="sec-sm">Cost Overrides (Optional)</div>', unsafe_allow_html=True)
    OV_ROWS = ["Material", "Variable VA", "Fixed VA"]
    ov_cols = {cn: [None, None, None] for cn in factory_col_names_shared}
    # Pre-populate from batch overrides if available
    batch_ovs = st.session_state.get(f"{pfx}batch_overrides", [])
    for bov in batch_ovs:
        fn_ov = bov.get("factory_name", "")
        if fn_ov in ov_cols:
            ov_cols[fn_ov] = [
                bov.get("material"),
                bov.get("variable_va"),
                bov.get("fixed_va"),
            ]
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
        if cn not in edited_ov.columns:
            return None
        ov = {}
        try:
            for key, row_name in [("material","Material"),("variable_va","Variable VA"),("fixed_va","Fixed VA")]:
                v = edited_ov.loc[row_name, cn]
                if v is not None and not pd.isna(v):
                    ov[key] = float(v)
        except KeyError:
            return None
        return ov if ov else None

    return {"inputs": inputs, "get_ov": get_ov}


# ── PORTFOLIO SUMMARY ─────────────────────────────────────────
def render_portfolio_summary(all_results, ccy, company_wacc=0.08, target_payback=3, target_om=0.20):
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
            text=[fa(totals[fn_]) for fn_ in all_fnames],
            textposition="outside",
            textfont=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT),
        ))
        fig.update_layout(
            title=dict(text=f"Total Annual OP by Location ({ccy})", font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT)),
            height=400, margin=dict(l=40,r=40,t=50,b=60),
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
            yaxis=dict(showgrid=True, gridcolor="#eee"),
        )
        fig.update_xaxes(tickangle=0, tickfont=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT))
        fig.update_yaxes(title_text=ccy, title_font=dict(size=10))
        plotly_chart(fig)

    # ── PORTFOLIO COST BRIDGE & SENSITIVITY (same layout as item-level) ──
    if len(all_fnames) >= 2:
        sub_tab_labels = ["Cost Bridge", "Sensitivity Analysis"]
        sub_tabs = st.tabs(sub_tab_labels)

        plotly_cfg = {"displayModeBar": True, "modeBarButtonsToRemove": ["lasso2d", "select2d", "sendDataToCloud"], "displaylogo": False}

        with sub_tabs[0]:
            st.markdown(f'<div class="callout">Waterfall from Net Sales to Operating Profit aggregated across all items. Shows top {min(len(all_fnames), 3)} locations.</div>', unsafe_allow_html=True)
            n_wf = min(len(all_fnames), 3)
            wf_cols = st.columns(n_wf)
            for wi, fn_ in enumerate(all_fnames[:n_wf]):
                with wf_cols[wi]:
                    st.markdown(f'<div style="font-size:0.7rem;font-family:Inter,sans-serif;font-weight:600;color:{DARK_TEXT};margin-bottom:0.2rem;">Cost Bridge: {fn_} ({ccy}/year)</div>', unsafe_allow_html=True)
                    plotly_chart(build_portfolio_waterfall(all_results, fn_, ccy), config=plotly_cfg)
            if len(all_fnames) > 3:
                st.markdown(f'<div style="font-size:0.7rem;color:{GREY_TEXT};margin-top:0.3rem;">Showing top 3 of {len(all_fnames)} locations.</div>', unsafe_allow_html=True)

        with sub_tabs[1]:
            st.markdown(f'<div class="callout">Explore how changes in a single parameter affect portfolio-level operating margin. The <strong>tornado chart</strong> shows the impact on OM when each cost parameter is individually changed by \u00b120%. The <strong>line chart</strong> below sweeps a single parameter across all factories.</div>', unsafe_allow_html=True)

            # Tornado chart (portfolio-wide, all factories)
            tornado_fig = build_portfolio_tornado(all_results, all_fnames, ccy)
            if tornado_fig:
                plotly_chart(tornado_fig, config=plotly_cfg)

            # Parameter sweep
            sa_params = {
                "VA Ratio": ("va_ratio", False),
                "Transport %": ("transport_pct", True),
                "Tariff %": ("tariff_pct", True),
                "Duties %": ("duties_pct", True),
                "S&A %": ("sa_pct", True),
            }
            sa_col1, sa_col2 = st.columns([1, 3])
            with sa_col1:
                sa_choice = st.selectbox("Parameter", list(sa_params.keys()), key="portfolio_sa_param")
            param_key, is_pct = sa_params[sa_choice]

            if param_key in ("va_ratio",):
                steps = [round(v, 2) for v in np.arange(0.4, 1.61, 0.1)]
            elif is_pct:
                steps = [round(v, 3) for v in np.arange(0.0, 0.121, 0.01)]
            else:
                steps = [round(v, 2) for v in np.arange(0.5, 1.55, 0.1)]

            fig_sa = build_portfolio_sensitivity_chart(all_results, all_fnames, param_key, sa_choice, steps, ccy, is_pct=is_pct)
            plotly_chart(fig_sa, config=plotly_cfg)

    # ── INVESTMENT SUMMARY (Portfolio) ────────────────────────
    has_inv = any(
        ic.get("total_investment", 0) > 0
        for item in all_results
        for ic in item.get("investment", [])
    )
    if has_inv:
        st.markdown(f'<div class="sec-sm">Required Investments Summary</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="callout">Aggregated investment metrics across all items by receiving factory ({ccy}).</div>', unsafe_allow_html=True)

        # Collect alt factory names (exclude base)
        alt_fnames = [fn_ for fn_ in all_fnames if fn_ != base_fn]
        if alt_fnames:
            # Aggregate: total investment, year-by-year savings, combined NPV
            agg_inv = {fn_: 0.0 for fn_ in alt_fnames}
            agg_savings_by_year = {fn_: [] for fn_ in alt_fnames}
            agg_capex = {fn_: 0.0 for fn_ in alt_fnames}
            agg_opex = {fn_: 0.0 for fn_ in alt_fnames}
            agg_restr = {fn_: 0.0 for fn_ in alt_fnames}
            for item in all_results:
                for ic in item.get("investment", []):
                    fn_ = ic.get("factory_name", "")
                    if fn_ in alt_fnames:
                        agg_inv[fn_] += ic.get("total_investment", 0)
                        agg_capex[fn_] += ic.get("capex", 0)
                        agg_opex[fn_] += ic.get("opex", 0)
                        agg_restr[fn_] += ic.get("restructuring", 0)
                        yr_savings = ic.get("annual_savings_by_year", [ic.get("annual_savings", 0)])
                        # Sum year-by-year savings across items
                        for yi, sv in enumerate(yr_savings):
                            if yi < len(agg_savings_by_year[fn_]):
                                agg_savings_by_year[fn_][yi] += sv
                            else:
                                agg_savings_by_year[fn_].append(sv)
            agg_savings = {fn_: (sum(v) / len(v) if v else 0.0) for fn_, v in agg_savings_by_year.items()}

            # Compute portfolio-level NPV, IRR, payback using aggregated flows
            agg_cases = {}
            for fn_ in alt_fnames:
                savings_input = agg_savings_by_year[fn_] if agg_savings_by_year[fn_] else agg_savings[fn_]
                agg_cases[fn_] = compute_investment_case(
                    annual_savings=savings_input,
                    capex=agg_capex[fn_], opex=agg_opex[fn_], restructuring=agg_restr[fn_],
                    discount_rate=company_wacc,
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
                    cls = "delta-pos" if irr > company_wacc else "delta-neg"
                    irr_cells += f'<td class="{cls}"><strong>{irr*100:.1f}%</strong></td>'
                else:
                    irr_cells += f'<td>{dash}</td>'
            inv_p_html += f'<tr class="row-bold"><td><strong>IRR</strong></td>{irr_cells}</tr>'

            # Payback
            pb_cells = ""
            for fn_ in alt_fnames:
                pb = agg_cases[fn_]["simple_payback"]
                if pb is not None:
                    cls = "delta-pos" if pb <= target_payback else "delta-neg"
                    pb_cells += f'<td class="{cls}">{pb:.1f} years</td>'
                else:
                    pb_cells += f'<td>{dash}</td>'
            inv_p_html += f'<tr class="row-bold"><td>Simple Payback (target &le; {target_payback}yr)</td>{pb_cells}</tr>'

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


# ── COUNTRY COORDINATES (for executive summary map) ──────────
_COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "Sweden": (62.0, 15.0), "Germany": (51.2, 10.4), "France": (46.6, 2.2),
    "Italy": (42.5, 12.5), "Austria": (47.5, 14.6), "Poland": (51.9, 19.1),
    "Czech Republic": (49.8, 15.5), "Spain": (40.5, -3.7), "Netherlands": (52.1, 5.3),
    "UK": (55.4, -3.4), "Turkey": (39.9, 32.9),
    "USA": (39.8, -98.6), "Mexico": (23.6, -102.6), "Brazil": (-14.2, -51.9),
    "Canada": (56.1, -106.3), "Argentina": (-38.4, -63.6),
    "China": (35.9, 104.2), "India": (20.6, 79.0), "Japan": (36.2, 138.3),
    "South Korea": (35.9, 127.8), "Thailand": (15.9, 100.9),
    "Vietnam": (14.1, 108.3), "Malaysia": (4.2, 101.9), "Indonesia": (-0.8, 113.9),
    "South Africa": (-30.6, 22.9), "Australia": (-25.3, 133.8),
}


# ── EXECUTIVE SUMMARY PAGE ────────────────────────────────────
def render_executive_summary_page():
    """Render the Executive Summary page — a CEO-level overview of the full case."""
    all_results = st.session_state.get("_all_results", [])
    company_wacc = st.session_state.get("_company_wacc", 0.08)
    target_payback = st.session_state.get("target_payback", 3)
    target_om = st.session_state.get("target_om", 0.20)
    factory_countries = st.session_state.get("_factory_countries", {})
    currency = st.session_state.get("currency", "SEK")
    project_name = st.session_state.get("project_name", "New Analysis")
    target_market = st.session_state.get("target_market", "")
    data_classification = st.session_state.get("data_classification", "C3 - Confidential")
    carrying_cost_rates = st.session_state.get("_carrying_cost_rates", {})

    if not all_results:
        st.markdown('<div class="callout" style="font-size:0.76rem;">No analysis results available yet. Open <strong>Landed Cost Analysis</strong> first to configure the project and compute results.</div>', unsafe_allow_html=True)
        return

    st.markdown(f'<div class="sec">Executive Summary — {project_name}</div>', unsafe_allow_html=True)

    # IB-style project metadata strip
    n_items = len(all_results)
    analysis_date = date.today().strftime("%d %B %Y")
    st.markdown(f'''<div style="display:flex;gap:2rem;flex-wrap:wrap;font-family:Inter,sans-serif;font-size:0.7rem;color:{GREY_TEXT};margin:0.2rem 0 0.6rem 0;padding:0.5rem 0.9rem;background:#fafbfc;border:1px solid {BORDER};border-radius:2px;">
        <div><span style="font-weight:600;color:{NAVY};text-transform:uppercase;letter-spacing:0.06em;font-size:0.62rem;">Project</span><br>{project_name}</div>
        <div><span style="font-weight:600;color:{NAVY};text-transform:uppercase;letter-spacing:0.06em;font-size:0.62rem;">Date</span><br>{analysis_date}</div>
        <div><span style="font-weight:600;color:{NAVY};text-transform:uppercase;letter-spacing:0.06em;font-size:0.62rem;">Currency</span><br>{currency}</div>
        <div><span style="font-weight:600;color:{NAVY};text-transform:uppercase;letter-spacing:0.06em;font-size:0.62rem;">Target Market</span><br>{target_market or "N/A"}</div>
        <div><span style="font-weight:600;color:{NAVY};text-transform:uppercase;letter-spacing:0.06em;font-size:0.62rem;">Items Analysed</span><br>{n_items}</div>
        <div><span style="font-weight:600;color:{NAVY};text-transform:uppercase;letter-spacing:0.06em;font-size:0.62rem;">Classification</span><br>{data_classification}</div>
    </div>''', unsafe_allow_html=True)

    # ── SOURCING MAP ─────────────────────────────────────────
    st.markdown(f'<div class="sec-sm">Global Sourcing & Manufacturing Footprint</div>', unsafe_allow_html=True)

    # Gather location data
    all_fnames = []
    for item in all_results:
        for r in item["results"]:
            if r["name"] not in all_fnames:
                all_fnames.append(r["name"])

    base_fn = all_fnames[0] if all_fnames else None
    alt_fnames = [fn_ for fn_ in all_fnames if fn_ != base_fn]

    # Build coordinate lists
    map_lats, map_lons, map_labels, map_colors, map_sizes, map_symbols = [], [], [], [], [], []

    # Target market marker
    if target_market and target_market in _COUNTRY_COORDS:
        lat, lon = _COUNTRY_COORDS[target_market]
        map_lats.append(lat)
        map_lons.append(lon)
        map_labels.append(f"Target Market: {target_market}")
        map_colors.append("#e67e22")
        map_sizes.append(18)
        map_symbols.append("star")

    # Base factory
    base_country = factory_countries.get(base_fn, "")
    if base_country and base_country in _COUNTRY_COORDS:
        lat, lon = _COUNTRY_COORDS[base_country]
        map_lats.append(lat)
        map_lons.append(lon)
        map_labels.append(f"Current: {base_fn} ({base_country})")
        map_colors.append(NAVY)
        map_sizes.append(16)
        map_symbols.append("circle")

    # Alt factories
    for fn_ in alt_fnames:
        ctry = factory_countries.get(fn_, "")
        if ctry and ctry in _COUNTRY_COORDS:
            lat, lon = _COUNTRY_COORDS[ctry]
            map_lats.append(lat)
            map_lons.append(lon)
            map_labels.append(f"Alternative: {fn_} ({ctry})")
            map_colors.append(ACCENT_BLUE)
            map_sizes.append(14)
            map_symbols.append("diamond")

    fig_map = go.Figure()

    # Draw flow arrows — current sourcing (base → target market)
    if base_country and base_country in _COUNTRY_COORDS and target_market and target_market in _COUNTRY_COORDS:
        b_lat, b_lon = _COUNTRY_COORDS[base_country]
        t_lat, t_lon = _COUNTRY_COORDS[target_market]
        fig_map.add_trace(go.Scattergeo(
            lat=[b_lat, t_lat], lon=[b_lon, t_lon],
            mode="lines", name="Current sourcing",
            line=dict(width=3, color=NAVY, dash="solid"),
            showlegend=True,
            hoverinfo="skip",
        ))

    # Draw flow arrows — potential alternative sourcing (alt → target market)
    # Find the best alternative by OM
    best_alt_fn = None
    if alt_fnames:
        totals = {fn_: 0.0 for fn_ in all_fnames}
        for item in all_results:
            for r in item["results"]:
                totals[r["name"]] += r.get("annual_adj_op", r["annual_op"])
        ranked_alts = sorted(alt_fnames, key=lambda fn_: totals.get(fn_, 0), reverse=True)
        best_alt_fn = ranked_alts[0] if ranked_alts else None

    for fn_ in alt_fnames:
        ctry = factory_countries.get(fn_, "")
        if ctry and ctry in _COUNTRY_COORDS and target_market and target_market in _COUNTRY_COORDS:
            a_lat, a_lon = _COUNTRY_COORDS[ctry]
            t_lat, t_lon = _COUNTRY_COORDS[target_market]
            is_best = (fn_ == best_alt_fn)
            fig_map.add_trace(go.Scattergeo(
                lat=[a_lat, t_lat], lon=[a_lon, t_lon],
                mode="lines",
                name=f"Potential: {fn_}" if is_best else f"Alternative: {fn_}",
                line=dict(width=2.5 if is_best else 1.5,
                          color=GREEN if is_best else ACCENT_BLUE,
                          dash="solid" if is_best else "dot"),
                showlegend=True,
                hoverinfo="skip",
            ))

    # Location markers
    fig_map.add_trace(go.Scattergeo(
        lat=map_lats, lon=map_lons,
        mode="markers+text",
        text=map_labels,
        textposition="top center",
        textfont=dict(size=9, family="Inter, sans-serif", color=DARK_TEXT),
        marker=dict(size=map_sizes, color=map_colors, symbol=map_symbols,
                    line=dict(width=1, color="white")),
        showlegend=False,
        hovertemplate="%{text}<extra></extra>",
    ))

    fig_map.update_geos(
        showcountries=True, countrycolor="#d4d8e0",
        showcoastlines=True, coastlinecolor="#b0b8c4",
        showland=True, landcolor="#f7f8fa",
        showocean=True, oceancolor="#eaf2fb",
        showlakes=False,
        projection_type="natural earth",
        lataxis_range=[-55, 75],
        lonaxis_range=[-140, 170],
    )
    fig_map.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
        legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5,
                    font=dict(size=10)),
        title=dict(
            text=f"Manufacturing Footprint — Sourcing to {target_market}" if target_market else "Manufacturing Footprint",
            font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT),
            x=0.5,
        ),
    )
    plotly_chart(fig_map)

    # Map legend explanation
    legend_parts = [
        f'<span style="color:{NAVY};font-weight:700;">\u25cf</span> Current factory (base case)',
        f'<span style="color:{ACCENT_BLUE};font-weight:700;">\u25c6</span> Alternative factory',
        f'<span style="color:#e67e22;font-weight:700;">\u2605</span> Target market',
        f'<span style="color:{NAVY};">\u2500\u2500</span> Current sourcing flow',
        f'<span style="color:{GREEN};">\u2500\u2500</span> Recommended alternative',
        f'<span style="color:{ACCENT_BLUE};">\u00b7\u00b7\u00b7\u00b7</span> Other alternatives',
    ]
    st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.7rem;color:{GREY_TEXT};text-align:center;margin:-0.5rem 0 1rem 0;">{"&emsp;|&emsp;".join(legend_parts)}</div>', unsafe_allow_html=True)

    # ── KEY FINANCIAL METRICS ────────────────────────────────
    st.markdown(f'<div class="sec-sm">Key Financial Metrics</div>', unsafe_allow_html=True)

    totals = {fn_: 0.0 for fn_ in all_fnames}
    total_rev = {fn_: 0.0 for fn_ in all_fnames}
    adj_totals = {fn_: 0.0 for fn_ in all_fnames}
    for item in all_results:
        for r in item["results"]:
            totals[r["name"]] += r["annual_op"]
            total_rev[r["name"]] += r["annual_rev"]
            adj_totals[r["name"]] += r.get("annual_adj_op", r["annual_op"])

    # IB-style recommendation verdict box
    base_adj_op = adj_totals.get(base_fn, 0)
    base_rev_tot = total_rev.get(base_fn, 0)
    ranked_for_verdict = sorted(alt_fnames, key=lambda fn_: adj_totals.get(fn_, 0), reverse=True)
    if ranked_for_verdict:
        v_best = ranked_for_verdict[0]
        v_delta = adj_totals[v_best] - base_adj_op
        v_best_om = adj_totals[v_best] / total_rev[v_best] * 100 if total_rev[v_best] else 0
        v_base_om = base_adj_op / base_rev_tot * 100 if base_rev_tot else 0
        v_delta_pp = v_best_om - v_base_om
        if v_delta > 0:
            verdict_color = GREEN
            verdict_icon = "\u2714"
            verdict_text = f"Transfer to <strong>{v_best}</strong> is financially attractive, delivering <strong>+{fi(v_delta, dz=False)} {currency}</strong> annual OP uplift ({v_delta_pp:+.1f}pp margin improvement vs. {base_fn})."
        elif abs(v_delta_pp) < 0.5:
            verdict_color = "#e6a817"
            verdict_icon = "\u25cf"
            verdict_text = f"All locations deliver comparable profitability. No material cost advantage exists between {base_fn} and {v_best} ({v_delta_pp:+.1f}pp). Decision should be driven by strategic factors."
        else:
            verdict_color = RED
            verdict_icon = "\u2716"
            verdict_text = f"Current sourcing from <strong>{base_fn}</strong> remains optimal. Best alternative ({v_best}) trails by <strong>{fi(abs(v_delta), dz=False)} {currency}</strong> ({v_delta_pp:+.1f}pp)."

        st.markdown(f'''<div style="background:#f8f9fb;border:1px solid {BORDER};border-left:4px solid {verdict_color};padding:0.8rem 1.1rem;margin:0.5rem 0 0.8rem 0;font-family:Inter,sans-serif;">
            <div style="font-size:0.67rem;font-weight:700;color:{NAVY};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.3rem;">{verdict_icon} Recommendation</div>
            <div style="font-size:0.78rem;color:{DARK_TEXT};line-height:1.55;">{verdict_text}</div>
        </div>''', unsafe_allow_html=True)

    base_op = totals.get(base_fn, 0)
    base_rev = total_rev.get(base_fn, 0)
    base_om = base_op / base_rev * 100 if base_rev else 0

    ranked = sorted(alt_fnames, key=lambda fn_: adj_totals.get(fn_, 0), reverse=True)
    best_fn = ranked[0] if ranked else None
    best_op = adj_totals.get(best_fn, 0)
    best_rev = total_rev.get(best_fn, 0)
    best_om = best_op / best_rev * 100 if best_rev else 0
    delta_op = best_op - adj_totals.get(base_fn, 0)

    # KPI cards
    ncards = min(len(ranked), 3) + 1
    cols = st.columns(ncards)
    cols[0].markdown(f'''<div style="background:{BASE_CASE_BG};border:1px solid {BORDER};border-radius:2px;padding:0.8rem 1rem;text-align:center;">
        <div style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.2rem;">Base Case (Current)</div>
        <div style="font-size:1.15rem;font-weight:700;color:{DARK_TEXT};">{fi(base_op, dz=False)} {currency}</div>
        <div style="font-size:0.82rem;font-weight:600;color:{DARK_TEXT};margin-top:0.15rem;">{base_fn}</div>
        <div style="font-size:0.7rem;color:{MUTED};margin-top:0.1rem;">OM {base_om:.1f}%</div>
    </div>''', unsafe_allow_html=True)

    labels = ["Best Alternative", "2nd Best", "3rd Best"]
    for i, fn_ in enumerate(ranked[:3]):
        delta = adj_totals[fn_] - adj_totals.get(base_fn, 0)
        is_better = delta > 0
        bdr = f"border-left:3px solid {GREEN};" if is_better else f"border-left:3px solid {RED};"
        d_sign = "+" if delta > 0 else ""
        d_cls = f"color:{GREEN};font-weight:600;" if is_better else f"color:{RED};font-weight:600;"
        fn_om = adj_totals[fn_] / total_rev[fn_] * 100 if total_rev[fn_] else 0
        cols[i+1].markdown(f'''<div style="background:#fafafa;border:1px solid {BORDER};{bdr}border-radius:2px;padding:0.8rem 1rem;text-align:center;">
            <div style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.2rem;">{labels[i]}</div>
            <div style="font-size:1.15rem;font-weight:700;color:{DARK_TEXT};">{fi(adj_totals[fn_], dz=False)} {currency}</div>
            <div style="font-size:0.82rem;font-weight:600;color:{DARK_TEXT};margin-top:0.15rem;">{fn_}</div>
            <div style="font-size:0.7rem;{d_cls}margin-top:0.1rem;">{d_sign}{fi(delta, acct=True)} vs base | OM {fn_om:.1f}%</div>
        </div>''', unsafe_allow_html=True)

    # ── PORTFOLIO HEATMAP ────────────────────────────────────
    # Visual matrix: items (rows) x factories (columns) — scalable for 20-30+ items
    if len(all_results) >= 2 and len(all_fnames) >= 2:
        st.markdown(f'<div class="sec-sm">Portfolio Profitability Matrix</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.7rem;color:{GREY_TEXT};margin:-0.2rem 0 0.4rem 0;">Operating margin (%) by item and factory. Green = above target ({target_om*100:.0f}%), red = below. Hover for detail.</div>', unsafe_allow_html=True)

        # Build the matrix data
        item_labels = []
        om_matrix = []
        op_matrix = []
        rev_matrix = []
        annot_matrix = []
        for item in all_results:
            inp = item["inputs"]
            lbl = inp.get("item_number", "")
            if inp.get("designation"):
                lbl = f"{lbl} {inp['designation']}" if lbl else inp["designation"]
            lbl = lbl[:40] if len(lbl) > 40 else lbl
            item_labels.append(lbl or f"Item {len(item_labels)+1}")

            om_row = []
            op_row = []
            rev_row = []
            annot_row = []
            for fn_ in all_fnames:
                match = [r for r in item["results"] if r["name"] == fn_]
                if match:
                    r = match[0]
                    om_val = r.get("adj_om", r["om"]) * 100
                    op_val = r.get("annual_adj_op", r["annual_op"])
                    rev_val = r["annual_rev"]
                    om_row.append(om_val)
                    op_row.append(op_val)
                    rev_row.append(rev_val)
                    annot_row.append(f"{om_val:.1f}%")
                else:
                    om_row.append(None)
                    op_row.append(None)
                    rev_row.append(None)
                    annot_row.append("")
            om_matrix.append(om_row)
            op_matrix.append(op_row)
            rev_matrix.append(rev_row)
            annot_matrix.append(annot_row)

        # Custom hover text
        hover_text = []
        for i, item_lbl in enumerate(item_labels):
            hover_row = []
            for j, fn_ in enumerate(all_fnames):
                if om_matrix[i][j] is not None:
                    hover_row.append(
                        f"<b>{item_lbl}</b><br>"
                        f"Factory: {fn_}<br>"
                        f"OM: {om_matrix[i][j]:.1f}%<br>"
                        f"Annual OP: {fi(op_matrix[i][j], dz=False)}<br>"
                        f"Revenue: {fi(rev_matrix[i][j], dz=False)}"
                    )
                else:
                    hover_row.append("")
            hover_text.append(hover_row)

        # Build heatmap — green above target OM, red below
        target_om_pct = target_om * 100
        fig_hm = go.Figure(data=go.Heatmap(
            z=om_matrix,
            x=all_fnames,
            y=item_labels,
            text=annot_matrix,
            texttemplate="%{text}",
            textfont=dict(size=10, family="Inter, sans-serif"),
            hovertext=hover_text,
            hovertemplate="%{hovertext}<extra></extra>",
            colorscale=[
                [0.0, "#c62828"],
                [0.35, "#ef9a9a"],
                [0.5, "#fff9c4"],
                [0.65, "#a5d6a7"],
                [1.0, "#2e7d32"],
            ],
            zmid=target_om_pct,
            colorbar=dict(
                title=dict(text="OM %", font=dict(size=10)),
                tickfont=dict(size=9),
                thickness=12,
                len=0.8,
            ),
        ))

        # Mark best factory per item with a star overlay
        best_x, best_y, best_text = [], [], []
        for i, item_lbl in enumerate(item_labels):
            valid = [(j, om_matrix[i][j]) for j in range(len(all_fnames)) if om_matrix[i][j] is not None]
            if valid:
                best_j = max(valid, key=lambda x: x[1])[0]
                best_x.append(all_fnames[best_j])
                best_y.append(item_lbl)
                best_text.append("\u2605")

        fig_hm.add_trace(go.Scatter(
            x=best_x, y=best_y, mode="text",
            text=best_text,
            textfont=dict(size=14, color="white"),
            showlegend=False, hoverinfo="skip",
        ))

        hm_height = max(300, min(800, 50 + len(item_labels) * 28))
        fig_hm.update_layout(
            height=hm_height,
            margin=dict(l=10, r=10, t=30, b=40),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
            xaxis=dict(side="top", tickangle=0, tickfont=dict(size=10)),
            yaxis=dict(autorange="reversed", tickfont=dict(size=9)),
        )
        plotly_chart(fig_hm)

        st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.66rem;color:{GREY_TEXT};text-align:center;margin:-0.3rem 0 0.5rem 0;">\u2605 = Best location per item &nbsp;|&nbsp; Values show NWC-adjusted operating margin where available</div>', unsafe_allow_html=True)

    # ── PORTFOLIO ITEM RANKING TABLE ─────────────────────────
    # Condensed table showing each item, its best factory, delta, and verdict
    if len(all_results) >= 2:
        st.markdown(f'<div class="sec-sm">Item Transfer Ranking</div>', unsafe_allow_html=True)
        rank_html = f'<table class="ib-table"><thead><tr><th>#</th><th>Item</th><th>Revenue ({currency})</th><th>Current OM</th><th>Best Alternative</th><th>Best OM</th><th>OM Delta</th><th>Annual OP Uplift</th><th>Verdict</th></tr></thead><tbody>'
        item_rank_data = []
        for item in all_results:
            inp = item["inputs"]
            results_i = item["results"]
            if len(results_i) < 2:
                continue
            lbl = inp.get("item_number", "")
            if inp.get("designation"):
                lbl = f"{lbl} {inp['designation']}" if lbl else inp["designation"]
            base_r = results_i[0]
            base_om_i = base_r.get("adj_om", base_r["om"]) * 100
            base_op_i = base_r.get("annual_adj_op", base_r["annual_op"])
            best_alt = max(results_i[1:], key=lambda r: r.get("annual_adj_op", r["annual_op"]))
            best_om_i = best_alt.get("adj_om", best_alt["om"]) * 100
            best_op_i = best_alt.get("annual_adj_op", best_alt["annual_op"])
            delta_om = best_om_i - base_om_i
            delta_op = best_op_i - base_op_i
            item_rank_data.append((lbl, base_r["annual_rev"], base_om_i, best_alt["name"], best_om_i, delta_om, delta_op))

        # Sort by OP uplift descending
        item_rank_data.sort(key=lambda x: x[6], reverse=True)
        for rank_i, (lbl, rev, b_om, best_name, best_om_v, d_om, d_op) in enumerate(item_rank_data, 1):
            if d_op > 0:
                verdict = f'<span style="color:{GREEN};font-weight:600;">Transfer</span>'
            elif abs(d_om) < 0.5:
                verdict = f'<span style="color:#e6a817;font-weight:600;">Neutral</span>'
            else:
                verdict = f'<span style="color:{RED};font-weight:600;">Keep</span>'
            d_cls = dc(d_op)
            rank_html += f'<tr><td>{rank_i}</td><td style="text-align:left;">{lbl}</td><td>{fi(rev, dz=False)}</td><td>{b_om:.1f}%</td><td>{best_name}</td><td>{best_om_v:.1f}%</td><td class="{d_cls}">{d_om:+.1f}pp</td><td class="{d_cls}">{fi(d_op, acct=True)}</td><td>{verdict}</td></tr>'
        rank_html += '</tbody></table>'
        st.markdown(rank_html, unsafe_allow_html=True)

    # ── EXECUTIVE NARRATIVE (collapsible for large portfolios) ──
    narrative_items = [item for item in all_results if len(item["results"]) >= 2]
    if narrative_items:
        use_expander = len(narrative_items) > 5
        if use_expander:
            narrative_container = st.expander(f"Item-Level Executive Narratives ({len(narrative_items)} items)", expanded=False)
        else:
            narrative_container = st  # render directly

        with narrative_container:
            for item in narrative_items:
                results_n = item["results"]
                inp_data = item["inputs"]
                from landed_cost.models import ItemInputs
                inp_obj = ItemInputs(
                    item_number=inp_data.get("item_number", ""),
                    designation=inp_data.get("designation", ""),
                    net_sales_value=0, net_sales_qty=0,
                    material=0, variable_va=0, fixed_va=0,
                )
                summary_html = build_exec_summary(results_n, inp_obj, currency)
                if summary_html:
                    st.markdown(summary_html, unsafe_allow_html=True)

    # ── LANDED COST COMPARISON TABLE ─────────────────────────
    st.markdown(f'<div class="sec-sm">Landed Cost Comparison — All Items</div>', unsafe_allow_html=True)

    hdr = "".join(f'<th>{fn_}</th>' for fn_ in all_fnames)
    tbl = f'<table class="ib-table"><thead><tr><th>Metric</th>{hdr}</tr></thead><tbody>'

    # Revenue
    rev_cells = "".join(f'<td class="{"base-case" if fn_==base_fn else ""}">{fi(total_rev[fn_], dz=False)}</td>' for fn_ in all_fnames)
    tbl += f'<tr><td>Total Annual Revenue</td>{rev_cells}</tr>'

    # Operating profit
    op_cells = "".join(f'<td class="{"base-case" if fn_==base_fn else ""}">{fi(totals[fn_], dz=False)}</td>' for fn_ in all_fnames)
    tbl += f'<tr class="row-bold"><td><strong>Total Annual OP</strong></td>{op_cells}</tr>'

    # OM
    om_cells = "".join(
        f'<td class="{"base-case" if fn_==base_fn else ""}">{totals[fn_]/total_rev[fn_]*100:.1f}%</td>' if total_rev[fn_] else '<td>\u2013</td>'
        for fn_ in all_fnames
    )
    tbl += f'<tr class="row-bold"><td><strong>Operating Margin</strong></td>{om_cells}</tr>'

    # NWC-adjusted OP
    has_nwc = any(r.get("lead_time_days") is not None for item in all_results for r in item["results"])
    if has_nwc:
        base_adj = adj_totals.get(base_fn, 0)
        adj_op_cells = "".join(f'<td class="{"base-case" if fn_==base_fn else ""}">{fi(adj_totals[fn_], dz=False)}</td>' for fn_ in all_fnames)
        tbl += f'<tr class="row-bold"><td><strong>NWC-Adjusted OP</strong></td>{adj_op_cells}</tr>'

        adj_om_cells = "".join(
            f'<td class="{"base-case" if fn_==base_fn else ""}">{adj_totals[fn_]/total_rev[fn_]*100:.1f}%</td>' if total_rev[fn_] else '<td>\u2013</td>'
            for fn_ in all_fnames
        )
        tbl += f'<tr class="row-bold"><td><strong>Adj. Operating Margin</strong></td>{adj_om_cells}</tr>'

    # Delta vs base
    dash = "\u2013"
    delta_cells = "".join(
        f'<td class="{"base-case" if fn_==base_fn else dc(adj_totals[fn_]-adj_totals.get(base_fn,0))}">{dash if fn_==base_fn else fi(adj_totals[fn_]-adj_totals.get(base_fn,0), acct=True)}</td>'
        for fn_ in all_fnames
    )
    tbl += f'<tr class="row-bold"><td><em>Delta vs. Base</em></td>{delta_cells}</tr>'
    tbl += '</tbody></table>'
    st.markdown(tbl, unsafe_allow_html=True)

    # ── INVESTMENT SUMMARY ───────────────────────────────────
    has_inv = any(
        ic.get("total_investment", 0) > 0
        for item in all_results
        for ic in item.get("investment", [])
    )
    if has_inv:
        st.markdown(f'<div class="sec-sm">Investment Requirements</div>', unsafe_allow_html=True)

        agg_inv = {fn_: 0.0 for fn_ in alt_fnames}
        agg_savings = {fn_: 0.0 for fn_ in alt_fnames}
        agg_count = {fn_: 0 for fn_ in alt_fnames}
        for item in all_results:
            for ic in item.get("investment", []):
                fn_ = ic.get("factory_name", "")
                if fn_ in alt_fnames:
                    agg_inv[fn_] += ic.get("total_investment", 0)
                    agg_savings[fn_] += ic.get("annual_savings", 0)
                    agg_count[fn_] += 1

        # Recompute NPV/IRR/payback at portfolio level
        agg_capex = {fn_: 0.0 for fn_ in alt_fnames}
        agg_opex = {fn_: 0.0 for fn_ in alt_fnames}
        agg_restr = {fn_: 0.0 for fn_ in alt_fnames}
        agg_savings_by_year = {fn_: [] for fn_ in alt_fnames}
        for item in all_results:
            for ic in item.get("investment", []):
                fn_ = ic.get("factory_name", "")
                if fn_ in alt_fnames:
                    agg_capex[fn_] += ic.get("capex", 0)
                    agg_opex[fn_] += ic.get("opex", 0)
                    agg_restr[fn_] += ic.get("restructuring", 0)
                    yr_savings = ic.get("annual_savings_by_year", [ic.get("annual_savings", 0)])
                    for yi, sv in enumerate(yr_savings):
                        if yi < len(agg_savings_by_year[fn_]):
                            agg_savings_by_year[fn_][yi] += sv
                        else:
                            agg_savings_by_year[fn_].append(sv)

        agg_avg_savings = {fn_: (sum(v) / len(v) if v else 0.0) for fn_, v in agg_savings_by_year.items()}
        agg_cases = {}
        for fn_ in alt_fnames:
            savings_input = agg_savings_by_year[fn_] if agg_savings_by_year[fn_] else agg_avg_savings[fn_]
            agg_cases[fn_] = compute_investment_case(
                annual_savings=savings_input,
                capex=agg_capex[fn_], opex=agg_opex[fn_], restructuring=agg_restr[fn_],
                discount_rate=company_wacc, horizon_years=10,
            )

        inv_hdr = "".join(f'<th>{fn_}</th>' for fn_ in alt_fnames)
        inv_tbl = f'<table class="ib-table"><thead><tr><th>Investment Metric</th>{inv_hdr}</tr></thead><tbody>'

        inv_tbl += f'<tr><td>Total Investment</td>{"".join(f"<td>{fi(agg_inv[fn_], dz=False)}</td>" for fn_ in alt_fnames)}</tr>'
        inv_tbl += f'<tr><td>Avg. Annual Savings</td>{"".join(f"<td>{fi(agg_avg_savings[fn_], acct=True, dz=False)}</td>" for fn_ in alt_fnames)}</tr>'

        npv_cells = ""
        for fn_ in alt_fnames:
            v = agg_cases[fn_]["npv"]
            cls = "delta-pos" if v > 0 else ("delta-neg" if v < 0 else "")
            npv_cells += f'<td class="{cls}"><strong>{fi(v, acct=True, dz=False)}</strong></td>'
        inv_tbl += f'<tr class="row-bold"><td><strong>NPV (10yr)</strong></td>{npv_cells}</tr>'

        irr_cells = ""
        for fn_ in alt_fnames:
            irr = agg_cases[fn_]["irr"]
            if irr is not None:
                cls = "delta-pos" if irr > company_wacc else "delta-neg"
                irr_cells += f'<td class="{cls}"><strong>{irr*100:.1f}%</strong></td>'
            else:
                irr_cells += f'<td>{dash}</td>'
        inv_tbl += f'<tr class="row-bold"><td><strong>IRR</strong></td>{irr_cells}</tr>'

        pb_cells = ""
        for fn_ in alt_fnames:
            pb = agg_cases[fn_]["simple_payback"]
            if pb is not None:
                cls = "delta-pos" if pb <= target_payback else "delta-neg"
                pb_cells += f'<td class="{cls}">{pb:.1f} years</td>'
            else:
                pb_cells += f'<td>{dash}</td>'
        inv_tbl += f'<tr class="row-bold"><td>Simple Payback (target \u2264 {target_payback}yr)</td>{pb_cells}</tr>'

        inv_tbl += '</tbody></table>'
        st.markdown(inv_tbl, unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{GREY_TEXT};margin:0.6rem 0;">No investment data entered. Configure investments on the <strong>Required Investments</strong> page.</div>', unsafe_allow_html=True)

    # ── STRATEGIC CONTEXT ────────────────────────────────────
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

    # ── FINANCIAL CONFIGURATION APPLIED ──────────────────────
    st.markdown(f'<div class="sec-sm">Financial Configuration Applied</div>', unsafe_allow_html=True)

    dash = "\u2013"
    tm_display = target_market or dash
    fin_tbl = f'''<table class="ib-table"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>
        <tr><td>Company WACC</td><td>{company_wacc*100:.1f}%</td></tr>
        <tr><td>Target Payback Period</td><td>{target_payback} years</td></tr>
        <tr><td>Target Operating Margin</td><td>{target_om*100:.1f}%</td></tr>
        <tr><td>Currency</td><td>{currency}</td></tr>
        <tr><td>Target Market</td><td>{tm_display}</td></tr>
        <tr><td>Data Classification</td><td>{data_classification}</td></tr>
    </tbody></table>'''
    st.markdown(fin_tbl, unsafe_allow_html=True)

    # Carrying cost rates per factory
    if carrying_cost_rates:
        cc_hdr = "".join(f'<th>{fn_}</th>' for fn_ in all_fnames if fn_ in carrying_cost_rates)
        cc_cells = "".join(f'<td>{carrying_cost_rates[fn_]*100:.1f}%</td>' for fn_ in all_fnames if fn_ in carrying_cost_rates)
        cc_tbl = f'<table class="ib-table" style="margin-top:0.5rem;"><thead><tr><th>Carrying Cost Rate</th>{cc_hdr}</tr></thead><tbody><tr><td>Annual Rate</td>{cc_cells}</tr></tbody></table>'
        st.markdown(cc_tbl, unsafe_allow_html=True)

    # ── APPENDIX / ITEM DETAILS ──────────────────────────────
    st.markdown(f'<div class="sec-sm">Appendix — Item-Level Detail</div>', unsafe_allow_html=True)

    for item_idx, item in enumerate(all_results):
        inp = item["inputs"]
        results = item["results"]
        item_label = f"{inp.get('item_number', '')} {inp.get('designation', '')}".strip() or f"Item {item_idx + 1}"
        st.markdown(f'<div style="font-weight:600;font-size:0.8rem;color:{NAVY};margin:0.8rem 0 0.3rem 0;">{item_label}</div>', unsafe_allow_html=True)

        if len(results) >= 2:
            i_hdr = "".join(f'<th>{r["name"]}</th>' for r in results)
            i_tbl = f'<table class="ib-table"><thead><tr><th>Per-Unit Metric ({currency})</th>{i_hdr}</tr></thead><tbody>'

            rows = [
                ("Net Sales / Unit", "ns"),
                ("Material", "material"),
                ("Variable VA", "variable_va"),
                ("Fixed VA", "fixed_va"),
                ("Total COGS / Unit", "cogs"),
                ("Gross Profit / Unit", "gp"),
                ("S&A / Unit", "sa"),
                ("Tariffs & Duties / Unit", "tariff_duty"),
                ("Transport / Unit", "transport"),
                ("Operating Profit / Unit", "op"),
            ]
            for label, key in rows:
                cls = "row-bold" if key in ("cogs", "gp", "op") else ""
                cells = "".join(
                    f'<td class="{"base-case" if ri==0 else ""}">{fn(r.get(key, 0), 2)}</td>'
                    for ri, r in enumerate(results)
                )
                i_tbl += f'<tr class="{cls}"><td>{"<strong>"+label+"</strong>" if cls else label}</td>{cells}</tr>'

            # OM row
            om_cells = "".join(
                f'<td class="{"base-case" if ri==0 else ""}">{r["om"]*100:.1f}%</td>'
                for ri, r in enumerate(results)
            )
            i_tbl += f'<tr class="row-bold"><td><strong>Operating Margin</strong></td>{om_cells}</tr>'

            # Annual OP row
            aop_cells = "".join(
                f'<td class="{"base-case" if ri==0 else ""}">{fi(r["annual_op"], dz=False)}</td>'
                for ri, r in enumerate(results)
            )
            i_tbl += f'<tr class="row-bold"><td><strong>Annual OP</strong></td>{aop_cells}</tr>'

            i_tbl += '</tbody></table>'
            st.markdown(i_tbl, unsafe_allow_html=True)

    # Footer
    st.markdown(f'<div style="margin-top:1.5rem;padding-top:0.5rem;border-top:1px solid {BORDER};font-family:Inter,sans-serif;font-size:0.65rem;color:{GREY_TEXT};text-align:center;">{data_classification} | {project_name} | Generated by Manufacturing Location Analyzer</div>', unsafe_allow_html=True)


# ── SAVE / LOAD ───────────────────────────────────────────────
def save_project_json():
    """Collect all session state into a JSON-serializable dict."""
    return json.dumps({
        "version": "4.5",
        "project_name": st.session_state.get("project_name", ""),
        "project_items": st.session_state.get("project_items", []),
        "next_id": st.session_state.get("next_id", 1),
        # Governance — Pre-study
        "ps_strategic_rationale": st.session_state.get("ps_strategic_rationale", ""),
        "ps_purpose": st.session_state.get("ps_purpose", ""),
        "ps_risk_of_inaction": st.session_state.get("ps_risk_of_inaction", ""),
        "ps_key_risks": st.session_state.get("ps_key_risks", ""),
        "ps_background": st.session_state.get("ps_background", ""),
        "ps_reason": st.session_state.get("ps_reason", ""),
        "ps_questions": st.session_state.get("ps_questions", ""),
        "ps_dependencies": st.session_state.get("ps_dependencies", []),
        "ps_sponsor": st.session_state.get("ps_sponsor", ""),
        "ps_lead": st.session_state.get("ps_lead", ""),
        "ps_main_entity": st.session_state.get("ps_main_entity", ""),
        "ps_impact_entities": st.session_state.get("ps_impact_entities", ""),
        "ps_team": st.session_state.get("ps_team", ""),
        "ps_timeline": st.session_state.get("ps_timeline", {}),
        # Governance — Proposal
        "prop_direction": st.session_state.get("prop_direction", ""),
        "prop_benefits": st.session_state.get("prop_benefits", ""),
        "prop_total_investment": st.session_state.get("prop_total_investment"),
        "prop_cash_out": st.session_state.get("prop_cash_out"),
        "prop_timeplan": st.session_state.get("prop_timeplan", ""),
        "prop_risks": st.session_state.get("prop_risks", []),
        # Governance — Transfer Details
        "td_transfer_to": st.session_state.get("td_transfer_to", ""),
        "td_transfer_from": st.session_state.get("td_transfer_from", ""),
        "td_product_line": st.session_state.get("td_product_line", ""),
        "td_material_family": st.session_state.get("td_material_family", ""),
        "td_transfer_volume": st.session_state.get("td_transfer_volume", ""),
        "td_indicative_timing": st.session_state.get("td_indicative_timing", ""),
        "td_requirements": st.session_state.get("td_requirements", {}),
    }, indent=2)


# ── BATCH EXCEL UPLOAD ────────────────────────────────────────

def _generate_batch_template(factory_names: list[str], currency: str) -> bytes:
    """Generate an Excel template for batch item upload."""
    import xlsxwriter
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})

    # Styles
    hdr_fmt = wb.add_format({"bold": True, "bg_color": "#1a2332", "font_color": "white",
                             "font_size": 9, "font_name": "Arial", "border": 1})
    guide_fmt = wb.add_format({"italic": True, "font_color": "#6c757d", "font_size": 9,
                               "font_name": "Arial", "text_wrap": True, "border": 1})
    cell_fmt = wb.add_format({"font_size": 10, "font_name": "Arial", "border": 1})
    num_fmt = wb.add_format({"font_size": 10, "font_name": "Arial", "border": 1, "num_format": "#,##0.00"})
    int_fmt = wb.add_format({"font_size": 10, "font_name": "Arial", "border": 1, "num_format": "#,##0"})
    sec_fmt = wb.add_format({"bold": True, "bg_color": "#e8ecf0", "font_size": 9,
                             "font_name": "Arial", "border": 1})

    # ── Items sheet ──
    ws = wb.add_worksheet("Items")
    ws.set_column("A:A", 18)
    ws.set_column("B:B", 28)

    # Headers
    cols = ["Item Number", "Designation", "Destination", "Comment",
            f"Material ({currency}/unit)", f"Variable VA ({currency}/unit)", f"Fixed VA ({currency}/unit)",
            "Y1 Revenue", "Y1 Qty", "Y2 Revenue", "Y2 Qty",
            "Y3 Revenue", "Y3 Qty", "Y4 Revenue", "Y4 Qty",
            "Y5 Revenue", "Y5 Qty"]
    for c, col in enumerate(cols):
        ws.write(0, c, col, hdr_fmt)
        ws.set_column(c, c, max(14, len(col) + 2))

    # Guide row
    guides = ["Unique ID", "Item description", "Target market", "Scope/reason",
              "Direct material cost at base factory", "Variable value-added at base factory",
              "Fixed value-added at base factory",
              "Year 1 net sales value", "Year 1 net sales qty",
              "Year 2 net sales value", "Year 2 net sales qty",
              "Year 3 net sales value", "Year 3 net sales qty",
              "Year 4 net sales value (optional)", "Year 4 net sales qty (optional)",
              "Year 5 net sales value (optional)", "Year 5 net sales qty (optional)"]
    for c, g in enumerate(guides):
        ws.write(1, c, g, guide_fmt)

    # Example row
    ws.write(2, 0, "1001", cell_fmt)
    ws.write(2, 1, "Bearing Assembly XR-200", cell_fmt)
    ws.write(2, 2, "USA", cell_fmt)
    ws.write(2, 3, "Annual sourcing review", cell_fmt)
    ws.write(2, 4, 18.50, num_fmt)
    ws.write(2, 5, 14.20, num_fmt)
    ws.write(2, 6, 7.80, num_fmt)
    ws.write(2, 7, 121280000, int_fmt)
    ws.write(2, 8, 2570000, int_fmt)

    # ── Cost Overrides sheet (optional) ──
    ws2 = wb.add_worksheet("Cost Overrides")
    ov_cols = ["Item Number", "Factory Name", f"Material ({currency}/unit)",
               f"Variable VA ({currency}/unit)", f"Fixed VA ({currency}/unit)"]
    for c, col in enumerate(ov_cols):
        ws2.write(0, c, col, hdr_fmt)
        ws2.set_column(c, c, max(16, len(col) + 2))
    ov_guides = ["Must match Items sheet", "Must match a factory name from the model",
                 "Override material (blank = use base)", "Override variable VA (blank = use VA ratio)",
                 "Override fixed VA (blank = use VA ratio)"]
    for c, g in enumerate(ov_guides):
        ws2.write(1, c, g, guide_fmt)

    # ── Investment Inputs sheet (optional) ──
    ws3 = wb.add_worksheet("Investments")
    inv_cols = ["Item Number", "Factory Name",
                f"CAPEX ({currency})", f"OPEX ({currency})", f"Restructuring ({currency})",
                "Analysis Horizon (Years)"]
    for c, col in enumerate(inv_cols):
        ws3.write(0, c, col, hdr_fmt)
        ws3.set_column(c, c, max(16, len(col) + 2))
    inv_guides = ["Must match Items sheet", "Receiving factory name",
                  "Capital expenditure for tooling/equipment", "One-time project/transfer costs",
                  "Restructuring/severance at sending site", "Default: 10 years"]
    for c, g in enumerate(inv_guides):
        ws3.write(1, c, g, guide_fmt)

    # ── Instructions sheet ──
    ws4 = wb.add_worksheet("Instructions")
    ws4.set_column("A:A", 80)
    instructions = [
        "BATCH ITEM UPLOAD — INSTRUCTIONS",
        "",
        "1. Fill in the 'Items' sheet with one row per item (starting at row 3).",
        "2. Required fields: Item Number, Designation, Material, Variable VA, Fixed VA, Y1 Revenue, Y1 Qty.",
        "3. Y4-Y5 projections are optional — leave blank if only 3-year projection is needed.",
        "4. 'Cost Overrides' sheet is optional — only fill if specific factories need per-unit cost overrides.",
        "5. 'Investments' sheet is optional — fill to pre-populate investment analysis inputs.",
        "",
        "IMPORTANT:",
        "- Factory names in 'Cost Overrides' and 'Investments' must exactly match the factory names configured in the model.",
        f"- All monetary values should be in {currency}.",
        "- Row 2 (guide row) will be ignored during import.",
        f"- Configured factories: {', '.join(factory_names)}" if factory_names else "",
    ]
    for r, line in enumerate(instructions):
        ws4.write(r, 0, line, sec_fmt if r == 0 else cell_fmt)

    wb.close()
    output.seek(0)
    return output.getvalue()


def _parse_batch_upload(uploaded_file, currency: str) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """Parse a batch upload Excel file. Returns (items, overrides, investments, warnings)."""
    warnings = []
    items = []
    overrides = []
    investments = []

    try:
        xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
    except Exception as e:
        return [], [], [], [f"Could not read Excel file: {e}"]

    # ── Parse Items sheet ──
    if "Items" in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name="Items", header=0, skiprows=[1])  # skip guide row
        for idx, row in df.iterrows():
            item_number = str(row.get("Item Number", "") or "").strip()
            designation = str(row.get("Designation", "") or "").strip()
            if not item_number and not designation:
                continue  # skip empty rows

            material = float(row.get(f"Material ({currency}/unit)", 0) or 0)
            variable_va = float(row.get(f"Variable VA ({currency}/unit)", 0) or 0)
            fixed_va = float(row.get(f"Fixed VA ({currency}/unit)", 0) or 0)

            # Sales projection
            projection = []
            for y in range(1, 6):
                rev_col = f"Y{y} Revenue"
                qty_col = f"Y{y} Qty"
                rev = row.get(rev_col)
                qty = row.get(qty_col)
                if rev is not None and not pd.isna(rev) and float(rev) > 0:
                    projection.append({
                        "year": y,
                        "value": float(rev),
                        "qty": int(float(qty)) if qty is not None and not pd.isna(qty) else 0,
                    })

            if not projection:
                warnings.append(f"Item '{item_number or designation}': No sales data found, skipping.")
                continue

            items.append({
                "item_number": item_number,
                "designation": designation,
                "destination": str(row.get("Destination", "") or "").strip(),
                "comment": str(row.get("Comment", "") or "").strip(),
                "material": material,
                "variable_va": variable_va,
                "fixed_va": fixed_va,
                "net_sales_value": projection[0]["value"],
                "net_sales_qty": projection[0]["qty"],
                "sales_projection": projection,
            })
    else:
        warnings.append("No 'Items' sheet found in the uploaded file.")

    # ── Parse Cost Overrides sheet ──
    if "Cost Overrides" in xls.sheet_names:
        df_ov = pd.read_excel(xls, sheet_name="Cost Overrides", header=0, skiprows=[1])
        for _, row in df_ov.iterrows():
            item_num = str(row.get("Item Number", "") or "").strip()
            factory = str(row.get("Factory Name", "") or "").strip()
            if not item_num or not factory:
                continue
            ov_entry = {"item_number": item_num, "factory_name": factory}
            mat = row.get(f"Material ({currency}/unit)")
            vva = row.get(f"Variable VA ({currency}/unit)")
            fva = row.get(f"Fixed VA ({currency}/unit)")
            if mat is not None and not pd.isna(mat):
                ov_entry["material"] = float(mat)
            if vva is not None and not pd.isna(vva):
                ov_entry["variable_va"] = float(vva)
            if fva is not None and not pd.isna(fva):
                ov_entry["fixed_va"] = float(fva)
            overrides.append(ov_entry)

    # ── Parse Investments sheet ──
    if "Investments" in xls.sheet_names:
        df_inv = pd.read_excel(xls, sheet_name="Investments", header=0, skiprows=[1])
        for _, row in df_inv.iterrows():
            item_num = str(row.get("Item Number", "") or "").strip()
            factory = str(row.get("Factory Name", "") or "").strip()
            if not item_num or not factory:
                continue
            inv_entry = {"item_number": item_num, "factory_name": factory}
            capex = row.get(f"CAPEX ({currency})")
            opex = row.get(f"OPEX ({currency})")
            restr = row.get(f"Restructuring ({currency})")
            hz = row.get("Analysis Horizon (Years)")
            if capex is not None and not pd.isna(capex):
                inv_entry["capex"] = float(capex)
            if opex is not None and not pd.isna(opex):
                inv_entry["opex"] = float(opex)
            if restr is not None and not pd.isna(restr):
                inv_entry["restructuring"] = float(restr)
            if hz is not None and not pd.isna(hz):
                inv_entry["horizon_years"] = int(float(hz))
            investments.append(inv_entry)

    if not items:
        warnings.append("No valid items found in the upload.")

    return items, overrides, investments, warnings


def _apply_batch_items(items: list[dict], overrides: list[dict], investments: list[dict]):
    """Apply parsed batch data to session state, creating item entries."""
    # Build item list
    new_items = []
    start_id = st.session_state.get("next_id", 1)

    for i, item in enumerate(items):
        item_id = start_id + i
        new_items.append({"id": item_id})

        # Pre-populate text fields via session state keys that render_item reads
        pfx = f"i{item_id}_"

        # Store batch data for render_item to pick up
        st.session_state[f"{pfx}batch_data"] = item

        # Build override data for this item
        item_ovs = [ov for ov in overrides if ov["item_number"] == item["item_number"]]
        if item_ovs:
            st.session_state[f"{pfx}batch_overrides"] = item_ovs

        # Build investment data for this item
        item_invs = [inv for inv in investments if inv["item_number"] == item["item_number"]]
        if item_invs:
            st.session_state[f"{pfx}batch_investments"] = item_invs

    st.session_state.project_items = new_items
    st.session_state.next_id = start_id + len(items)


# ── MAIN ──────────────────────────────────────────────────────
def main():
    init_state()

    # SKF logo (inline SVG for the wordmark)
    skf_logo_svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2498 587.1" height="28"><path d="m94.4 294.7c-11.5 0-20.7-11.5-20.7-23v-251c0-9.2 9.2-20.7 20.7-20.7h545.6c9.2 0 20.7 11.5 20.7 20.7v103.6c0 11.5-11.5 23-20.7 23h-177.2c-11.5 0-23-11.5-23-23v-36.8c0-6.9-6.9-13.8-13.8-13.8h-117.5c-6.9 0-16.1 6.9-16.1 13.8v117.4c0 6.9 9.2 16.1 16.1 16.1h402.9c16.1 0 23 6.9 23 20.7v324.6c0 11.5-11.5 20.7-23 20.7h-690.7c-11.4.1-20.7-9.1-20.7-20.5 0-.1 0-.1 0-.2v-177.2c0-11.4 9.2-20.7 20.5-20.7h.2 177.3c11.4 0 20.7 9.2 20.7 20.6v.2 110.5c0 6.9 9.2 13.8 16.1 13.8h264.8c6.9 0 13.8-6.9 13.8-13.8v-191.2c0-6.9-6.9-13.8-13.8-13.8zm787.4-59.9v117.4c0 6.9-6.9 11.5-16.1 16.1-13.8 2.3-20.7 9.2-20.7 20.7v177.3c0 11.4 9.2 20.7 20.5 20.7h.2 214.1c11.4 0 20.7-9.2 20.7-20.6 0-.1 0-.1 0-.2v-195.5c0-2.3 4.6-4.6 6.9-2.3l209.5 214.1c4.6 4.6 6.9 4.6 13.8 4.6h262.5c11.5 0 23-9.2 23-20.7v-177.3c0-11.5-11.5-20.7-23-20.7h-191.1c-4.6 0-6.9 0-9.2-4.6l-142.7-140.4c0-2.3-2.3-2.3 0-4.6l69.1-69.1c2.3-2.3 4.6-2.3 9.2-2.3h193.4c9.2 0 20.7-11.5 20.7-23v-103.7c0-9.2-11.5-20.7-20.7-20.7h-191.1c-6.9 0-9.2 2.3-13.8 6.9l-207.2 211.8c-4.6 2.3-9.2 2.3-9.2-2.3v-195.7c0-9.2-9.2-20.7-20.7-20.7h-214.2c-11.5 0-20.7 11.5-20.7 20.7v177.3c0 11.5 6.9 18.4 18.4 20.7 13.8 4.6 18.4 9.2 18.4 16.1zm844.9 331.6c0 11.5 11.5 20.7 23 20.7h211.8c11.5 0 23-9.2 23-20.7v-175c0-11.5-6.9-20.7-20.7-23-11.5-4.6-16.1-6.9-16.1-16.1v-43.7c0-6.9 6.9-13.8 13.8-13.8h80.6c9.2 0 16.1 6.9 16.1 13.8 0 11.5 11.5 23 20.7 23h177.3c11.5 0 23-11.5 23-23v-103.7c0-11.5-11.5-20.7-23-20.7h-177.2c-9.2 0-20.7 9.2-20.7 20.7 0 6.9-6.9 16.1-16.1 16.1h-80.6c-6.9 0-13.8-9.2-13.8-16.1v-117.4c0-6.9 6.9-13.8 13.8-13.8h227.9c6.9 0 16.1 6.9 16.1 13.8v36.8c0 11.5 9.2 23 20.7 23h251c11.5 0 20.7-11.5 20.7-23v-103.6c0-9.2-9.2-20.7-20.7-20.7h-727.5c-11.5 0-23 11.5-23 20.7v177.3c0 11.5 9.2 18.4 20.7 20.7 9.2 2.3 16.1 9.2 16.1 16.1v117.4c0 6.9-4.6 13.8-16.1 16.1-13.8 2.3-20.7 9.2-20.7 20.7z" fill="{NAVY}"/></svg>'
    st.markdown(f"""<div class="ib-header">
        <div class="ib-header-left">
            <h1>Manufacturing Location Analyzer</h1>
            <div class="sub">Multi-Item Production Cost &amp; Profitability Analysis &middot; v9.0</div>
        </div>
        <div>{skf_logo_svg}</div>
    </div>
    <div class="ib-header-spacer"></div>""", unsafe_allow_html=True)

    # ── SIDEBAR ────────────────────────────────────────────────
    st.sidebar.markdown(f"""<div style="padding:0.55rem 1rem 0.4rem 1rem;margin:-1rem -1rem 0.8rem -1rem;border-bottom:2px solid {NAVY};">
        <div style="font-family:Inter,sans-serif;font-size:0.72rem;font-weight:600;color:{NAVY};letter-spacing:0.04em;text-transform:uppercase;">Navigation</div>
    </div>""", unsafe_allow_html=True)

    # Navigation buttons
    nav_pages = [
        ("Landed Cost Analysis", "model"),
        ("Required Investments", "investment"),
        ("Financial Configuration", "financial"),
        ("Executive Summary", "executive"),
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
                ("Analysis Setup", "sec-project-setup"),
                ("Factory Configuration", "sec-factory-config"),
                ("NWC Assumptions", "sec-nwc"),
                ("Item Analysis", "sec-item-analysis"),
            ]
            links_html = "".join(
                f'<a class="nav-sub" href="#{anchor}">{lbl}</a>' for lbl, anchor in sub_sections
            )
            st.sidebar.markdown(links_html, unsafe_allow_html=True)

    # ── GOVERNANCE NAV ──────────────────────────────────────────
    gov_pages = [
        ("Pre-study", "prestudy"),
        ("Proposal", "proposal"),
        ("Transfer Details", "transfer"),
    ]
    st.sidebar.markdown(f'<div class="nav-sep">Governance</div>', unsafe_allow_html=True)
    for label, key in gov_pages:
        if st.sidebar.button(label, key=f"nav_{key}", use_container_width=True,
                             type="primary" if st.session_state.active_page == key else "secondary"):
            st.session_state.active_page = key
            st.rerun()

    st.sidebar.markdown(f'<div class="nav-sep">Reference</div>', unsafe_allow_html=True)
    for label, key in info_pages:
        if st.sidebar.button(label, key=f"nav_{key}", use_container_width=True,
                             type="primary" if st.session_state.active_page == key else "secondary"):
            st.session_state.active_page = key
            st.rerun()

    # Example data toggle at bottom of sidebar
    with st.sidebar:
        ex = st.checkbox("Load example data", value=st.session_state.ex)
        st.session_state.ex = ex

    # Legend at bottom of sidebar
    st.sidebar.markdown(f"""<div style="margin-top:0.5rem;padding:0.6rem 0.8rem;border-top:1px solid #d4d8e0;font-family:Inter,sans-serif;font-size:0.68rem;line-height:1.7;color:{GREY_TEXT};">
        <span style="border-left:3px solid {INPUT_BLUE};padding-left:0.3rem;font-weight:600;color:{INPUT_BLUE};">Blue border</span> = editable input<br>
        <strong style="color:{DARK_TEXT};">Bold</strong> = calculated output<br>
        <span style="font-style:italic;">Grey italic</span> = guidance notes
    </div>""", unsafe_allow_html=True)

    # (Reference page content is rendered in the main window, see below)
    # ── STRATEGIC CONTEXT PAGE ─────────────────────────────────
    # ── FINANCIAL CONFIGURATION PAGE ──────────────────────────
    if st.session_state.active_page == "financial":
        ex = st.session_state.ex
        all_factory_names_cc = st.session_state.get("_all_factory_names", ["Base Case"])
        factory_countries = st.session_state.get("_factory_countries", {})

        st.markdown('<div class="sec">Financial Configuration</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="callout">Company-wide financial parameters for investment analysis and performance benchmarking.</div>', unsafe_allow_html=True)

        fin_col1, fin_col2, fin_col3 = st.columns([1, 1, 1])
        with fin_col1:
            wacc_df = pd.DataFrame({"Company WACC (%)": [st.session_state.get("company_wacc", 0.08) * 100]})
            edited_wacc = st.data_editor(wacc_df, use_container_width=False, num_rows="fixed",
                key="wacc_editor", hide_index=True,
                column_config={"Company WACC (%)": st.column_config.NumberColumn(
                    "Company WACC (%)", min_value=0.0, max_value=30.0, step=0.5, format="%.1f", width=200)})
            company_wacc = float(edited_wacc.loc[0, "Company WACC (%)"] or 0.0) / 100.0
            st.session_state["company_wacc"] = company_wacc
        with fin_col2:
            pb_df = pd.DataFrame({"Target Payback (Years)": [st.session_state.get("target_payback", 3)]})
            edited_pb = st.data_editor(pb_df, use_container_width=False, num_rows="fixed",
                key="target_pb_editor", hide_index=True,
                column_config={"Target Payback (Years)": st.column_config.NumberColumn(
                    "Target Payback (Years)", min_value=1, max_value=15, step=1, format="%d", width=200)})
            target_payback = max(1, int(edited_pb.loc[0, "Target Payback (Years)"] or 3))
            st.session_state["target_payback"] = target_payback
        with fin_col3:
            om_df = pd.DataFrame({"Target Op. Margin (%)": [st.session_state.get("target_om", 0.20) * 100]})
            edited_om = st.data_editor(om_df, use_container_width=False, num_rows="fixed",
                key="target_om_editor", hide_index=True,
                column_config={"Target Op. Margin (%)": st.column_config.NumberColumn(
                    "Target Op. Margin (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f", width=200)})
            target_om = float(edited_om.loc[0, "Target Op. Margin (%)"] or 0.0) / 100.0
            st.session_state["target_om"] = target_om

        # ── Total Carrying Costs
        st.markdown('<div class="sec-sm">Total Carrying Costs</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="callout">Annual carrying cost rate applied to Delta NWC. Typically <strong>15–30%</strong> of inventory value. Use a company-wide rate for simplicity, or per-factory rates to isolate cost differences across the footprint.</div>', unsafe_allow_html=True)

        CC_ROWS = ["Capital Cost (WACC)", "Risk Cost", "Storage & Handling", "Service Cost"]
        CC_GUIDES = [
            "Opportunity cost of tied-up cash — driven by interest rates, tax rates, and network risk profile (typical: 7–15%)",
            "Write-offs, shrinkage, damage, spoilage — divide trailing 12-mo scrap value by avg inventory value (typical: 3–9%)",
            "Warehousing rent/depreciation, utilities, direct labor — divide total warehouse spend by avg inventory value (typical: 2–5%)",
            "Insurance, property taxes, inventory management software (typical: 1–3%)",
        ]
        cc_defaults = [8.0, 5.0, 3.0, 2.0]

        cc_mode = st.radio("Carrying cost mode", ["Company-wide rate", "Per-factory rates"],
                           horizontal=True, key="cc_mode",
                           index=1 if ex else 0)

        if cc_mode == "Company-wide rate":
            cc_data = {
                "Component": CC_ROWS + ["**Total**"],
                "Rate (%)": cc_defaults + [sum(cc_defaults)],
                "Guide": CC_GUIDES + ["Edit to override component sum — components will be ignored"],
            }
            cc_df = pd.DataFrame(cc_data)
            edited_cc = st.data_editor(
                cc_df, use_container_width=True, num_rows="fixed", key="coc_editor", hide_index=True,
                column_config={
                    "Component": st.column_config.TextColumn("Component", width=200, disabled=True),
                    "Rate (%)": st.column_config.NumberColumn("Rate (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f", width=120),
                    "Guide": st.column_config.TextColumn("Guide", disabled=True),
                },
                disabled=["Component", "Guide"])
            # Check if Total was manually overridden
            component_sum = 0.0
            for i, row in edited_cc.iterrows():
                if row["Component"] != "**Total**":
                    v = row["Rate (%)"]
                    if v is not None and not pd.isna(v):
                        component_sum += float(v)
            total_row_val = float(edited_cc.loc[edited_cc["Component"] == "**Total**", "Rate (%)"].values[0] or 0)
            if abs(total_row_val - component_sum) > 0.01:
                global_cc_pct = total_row_val
                st.markdown(f'<div style="font-size:0.72rem;color:{GREY_TEXT};margin-top:0.2rem;">Override active — using <strong>{total_row_val:.1f}%</strong> instead of component sum ({component_sum:.1f}%)</div>', unsafe_allow_html=True)
            else:
                global_cc_pct = component_sum
            global_cc_rate = global_cc_pct / 100.0
            carrying_cost_rates = {fn_: global_cc_rate for fn_ in all_factory_names_cc}
        else:
            cc_cols = {}
            for fn_ in all_factory_names_cc:
                if ex:
                    if "Asia" in fn_ or "China" in str(factory_countries.get(fn_, "")):
                        vals = [9.0, 7.0, 2.5, 1.5]
                    elif "Americas" in fn_ or "USA" in str(factory_countries.get(fn_, "")):
                        vals = [8.5, 4.0, 4.0, 2.5]
                    else:
                        vals = [8.0, 5.0, 3.0, 2.0]
                else:
                    vals = list(cc_defaults)
                cc_cols[fn_] = vals + [sum(vals)]
            cc_cols["Guide"] = CC_GUIDES + ["Edit to override component sum — components will be ignored"]
            cc_rows_with_total = CC_ROWS + ["**Total**"]
            cc_df = pd.DataFrame(cc_cols, index=cc_rows_with_total)

            edited_cc = st.data_editor(
                cc_df, use_container_width=True, num_rows="fixed", key="coc_editor", hide_index=False,
                column_config={
                    **{fn_: st.column_config.NumberColumn(fn_, min_value=0.0, max_value=100.0, step=0.5, format="%.1f") for fn_ in all_factory_names_cc},
                    "Guide": st.column_config.TextColumn("Guide", disabled=True),
                },
                disabled=["Guide"])

            carrying_cost_rates = {}
            overrides = []
            for fn_ in all_factory_names_cc:
                component_sum = 0.0
                for row_name in CC_ROWS:
                    v = edited_cc.loc[row_name, fn_]
                    if v is not None and not pd.isna(v):
                        component_sum += float(v)
                total_val = float(edited_cc.loc["**Total**", fn_] or 0)
                if abs(total_val - component_sum) > 0.01:
                    carrying_cost_rates[fn_] = total_val / 100.0
                    overrides.append(f"{fn_}: {total_val:.1f}% (components: {component_sum:.1f}%)")
                else:
                    carrying_cost_rates[fn_] = component_sum / 100.0
            if overrides:
                st.markdown(f'<div style="font-size:0.72rem;color:{GREY_TEXT};margin-top:0.2rem;">Override active — ' + ", ".join(overrides) + '</div>', unsafe_allow_html=True)

        st.session_state["_carrying_cost_rates"] = carrying_cost_rates

        with st.expander("How to calculate your facility-specific rates"):
            st.markdown(f"""
<div style="font-size:0.78rem;color:{DARK_TEXT};line-height:1.7;">
<strong>What drives your specific rate</strong><br>
Your actual rate fluctuates based on practical factors: current interest rates (cost of debt feeds directly into WACC),
corporate tax rates (interest on debt is tax-deductible, shifting the effective number), and your network risk profile
(stable, mature supply networks command lower equity premiums vs. volatile sectors).
If your planning teams are using a blanket textbook rate without isolating actual WACC and operational costs per facility,
you are missing clear optimization opportunities across the footprint.

<br><br><strong>Practical approach to isolate per-facility rates</strong>
<ol style="margin:0.3rem 0 0 1.2rem;padding:0;">
<li><strong>Isolate the data</strong> &mdash; Pull 12 months of trailing data for each major node in the network.
Three numbers per facility: average inventory value, total warehousing spend, and total value of written-off or scrapped stock.</li>
<li><strong>Calculate Storage &amp; Handling</strong> &mdash; Total warehousing spend &divide; average inventory value.
Include rent/depreciation, utilities, and direct warehouse labor. This gives you the storage percentage for that specific location.</li>
<li><strong>Calculate Risk Cost</strong> &mdash; Total value of written-off, scrapped, and lost stock &divide; average inventory value.
This provides the local risk percentage.</li>
</ol>
</div>
""", unsafe_allow_html=True)

            st.markdown(f'<div style="font-size:0.78rem;color:{DARK_TEXT};font-weight:600;margin-top:1rem;margin-bottom:0.4rem;">Rate Calculator</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:0.72rem;color:{GREY_TEXT};margin-bottom:0.5rem;">Enter trailing 12-month data for a facility to calculate its Storage &amp; Handling and Risk Cost rates.</div>', unsafe_allow_html=True)

            calc_df = pd.DataFrame({
                "Input": ["Average Inventory Value", "Total Warehousing Spend", "Total Scrap / Write-off Value"],
                "Amount": [None, None, None],
                "Guide": [
                    "Average on-hand inventory value over 12 months",
                    "Rent/depreciation + utilities + direct warehouse labor",
                    "Written-off, scrapped, damaged, and lost stock value",
                ],
            })
            edited_calc = st.data_editor(
                calc_df, use_container_width=False, num_rows="fixed", key="cc_calc", hide_index=True,
                column_config={
                    "Input": st.column_config.TextColumn("Input", width=220, disabled=True),
                    "Amount": st.column_config.NumberColumn("Amount", min_value=0, format="%.0f", width=160),
                    "Guide": st.column_config.TextColumn("Guide", width=320, disabled=True),
                },
                disabled=["Input", "Guide"])

            inv_val = edited_calc.loc[0, "Amount"]
            wh_spend = edited_calc.loc[1, "Amount"]
            scrap_val = edited_calc.loc[2, "Amount"]

            if inv_val and not pd.isna(inv_val) and float(inv_val) > 0:
                inv_v = float(inv_val)
                storage_pct = (float(wh_spend) / inv_v * 100) if (wh_spend and not pd.isna(wh_spend)) else 0.0
                risk_pct = (float(scrap_val) / inv_v * 100) if (scrap_val and not pd.isna(scrap_val)) else 0.0
                st.markdown(f"""<div style="font-size:0.78rem;color:{DARK_TEXT};line-height:1.8;margin-top:0.4rem;padding:0.5rem 0.8rem;background:#f8f9fb;border-radius:4px;">
                    <strong>Results:</strong><br>
                    Storage &amp; Handling Rate: <strong>{storage_pct:.1f}%</strong> &nbsp;(warehousing spend &divide; inventory value)<br>
                    Risk Cost Rate: <strong>{risk_pct:.1f}%</strong> &nbsp;(scrap value &divide; inventory value)<br>
                    Combined: <strong>{storage_pct + risk_pct:.1f}%</strong> &nbsp;&mdash; add WACC and Service Cost for the total carrying cost rate
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>Landed Cost Comparison v9.0 &middot; {st.session_state.project_name} &middot; Financial Configuration</span>", unsafe_allow_html=True)
        return  # Don't render the model page

    # ── REQUIRED INVESTMENTS PAGE ─────────────────────────────
    if st.session_state.active_page == "investment":
        all_results = st.session_state.get("_all_results", [])
        company_wacc = st.session_state.get("_company_wacc", 0.08)
        target_payback = st.session_state.get("target_payback", 3)
        target_om = st.session_state.get("target_om", 0.20)
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
            st.markdown(f'<div class="sec">Required Investments — {item_label}</div>', unsafe_allow_html=True)

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
                st.markdown(f'<div style="font-size:0.72rem;color:{GREY_TEXT};padding-top:0.6rem;">Discount rate uses Company WACC: <strong>{company_wacc*100:.1f}%</strong></div>', unsafe_allow_html=True)

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

            # Compute investment cases with year-by-year savings from projection
            inv_results = []
            dc_inputs = item_data.get("_inputs_dc")
            base_factory = item_data.get("_base_factory")
            factories_list = item_data.get("_factories", [])
            get_ov_fn = item_data.get("_get_ov")

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

                # Build year-by-year savings from sales projection
                alt_factory = next((f for f in factories_list if f.name == an), None)
                projection = dc_inputs.sales_projection if dc_inputs else []
                nwc_all = st.session_state.get("_nwc_assumptions", {})
                cc_rates = st.session_state.get("_carrying_cost_rates", {})
                if projection and dc_inputs and alt_factory and base_factory:
                    from dataclasses import replace
                    savings_by_year = []
                    base_nwc_inv = nwc_all.get(base_factory.name, {})
                    alt_nwc_inv = nwc_all.get(an, {})
                    base_cc = cc_rates.get(base_factory.name, 0.18)
                    alt_cc = cc_rates.get(an, 0.18)
                    base_lt = get_lead_time(factory_countries.get(base_factory.name, ""),
                                            factory_countries.get(base_factory.name, ""))
                    alt_lt = get_lead_time(factory_countries.get(base_factory.name, ""),
                                           factory_countries.get(an, ""))
                    ov = get_ov_fn(an) if get_ov_fn else {}
                    for p in projection:
                        yr_inputs = replace(dc_inputs,
                                               net_sales_value=float(p["value"]),
                                               net_sales_qty=int(p["qty"]))
                        base_r = compute_location(yr_inputs, base_factory, is_base=True,
                                    lead_time_days=base_lt, base_lead_time_days=base_lt,
                                    cost_of_capital=base_cc,
                                    safety_stock_days=base_nwc_inv.get("safety_stock_days", 0),
                                    base_safety_stock_days=base_nwc_inv.get("safety_stock_days", 0),
                                    cycle_stock_days=base_nwc_inv.get("cycle_stock_days", 0),
                                    base_cycle_stock_days=base_nwc_inv.get("cycle_stock_days", 0),
                                    payment_terms_days=base_nwc_inv.get("payment_terms_days", 0),
                                    base_payment_terms_days=base_nwc_inv.get("payment_terms_days", 0))
                        alt_r_yr = compute_location(yr_inputs, alt_factory, overrides=ov,
                                    lead_time_days=alt_lt, base_lead_time_days=base_lt,
                                    cost_of_capital=alt_cc,
                                    safety_stock_days=alt_nwc_inv.get("safety_stock_days", 0),
                                    base_safety_stock_days=base_nwc_inv.get("safety_stock_days", 0),
                                    cycle_stock_days=alt_nwc_inv.get("cycle_stock_days", 0),
                                    base_cycle_stock_days=base_nwc_inv.get("cycle_stock_days", 0),
                                    payment_terms_days=alt_nwc_inv.get("payment_terms_days", 0),
                                    base_payment_terms_days=base_nwc_inv.get("payment_terms_days", 0))
                        if base_r and alt_r_yr:
                            base_op = base_r.get("annual_adj_op", base_r["annual_op"])
                            alt_op = alt_r_yr.get("annual_adj_op", alt_r_yr["annual_op"])
                            savings_by_year.append(alt_op - base_op)
                    annual_savings = savings_by_year if savings_by_year else 0.0
                else:
                    base_adj_annual_op = results[0].get("annual_adj_op", results[0]["annual_op"])
                    annual_savings = alt_r.get("annual_adj_op", alt_r["annual_op"]) - base_adj_annual_op

                inv_case = compute_investment_case(
                    annual_savings=annual_savings,
                    capex=capex, opex=opex, restructuring=restr,
                    discount_rate=company_wacc,
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
                inv_html = f'<table class="ib-table"><thead><tr><th>Required Investments ({currency})</th>{inv_hdr}</tr></thead><tbody>'

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
                        cls = "delta-pos" if ic["irr"] > company_wacc else "delta-neg"
                        irr_cells += f'<td class="{cls}"><strong>{ic["irr"]*100:.1f}%</strong></td>'
                    else:
                        irr_cells += f'<td>{dash}</td>'
                inv_html += f'<tr class="row-bold"><td><strong>IRR</strong></td>{irr_cells}</tr>'

                # Payback (compared against target payback)
                pb_cells = ""
                for ic in inv_results:
                    if ic["simple_payback"] is not None:
                        cls = "delta-pos" if ic["simple_payback"] <= target_payback else "delta-neg"
                        pb_cells += f'<td class="{cls}">{ic["simple_payback"]:.1f} years</td>'
                    else:
                        pb_cells += f'<td>{dash}</td>'
                inv_html += f'<tr class="row-bold"><td>Simple Payback (target &le; {target_payback}yr)</td>{pb_cells}</tr>'

                dpb_cells = ""
                for ic in inv_results:
                    if ic["discounted_payback"] is not None:
                        cls = "delta-pos" if ic["discounted_payback"] <= target_payback else "delta-neg"
                        dpb_cells += f'<td class="{cls}">{ic["discounted_payback"]:.1f} years</td>'
                    else:
                        dpb_cells += f'<td>{dash}</td>'
                inv_html += f'<tr class="row-bold"><td>Discounted Payback (target &le; {target_payback}yr)</td>{dpb_cells}</tr>'

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
                    title=dict(text=f"Cumulative Cash Flow ({currency})", font=dict(size=11, family="Inter, sans-serif", color=DARK_TEXT)),
                    height=350, margin=dict(l=50, r=30, t=50, b=50),
                    paper_bgcolor="white", plot_bgcolor="white",
                    font=dict(family="Inter, sans-serif", size=10, color=DARK_TEXT),
                    xaxis=dict(title="Year", showgrid=True, gridcolor="#eee", dtick=1),
                    yaxis=dict(title=currency, showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                plotly_chart(fig_cf)

        # Footer for investment page
        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>Landed Cost Comparison v9.0 &middot; {st.session_state.project_name} &middot; Required Investments Analysis</span>", unsafe_allow_html=True)
        return

    # ── EXECUTIVE SUMMARY PAGE ────────────────────────────────
    if st.session_state.active_page == "executive":
        render_executive_summary_page()
        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>Landed Cost Comparison v9.0 &middot; {st.session_state.project_name} &middot; Executive Summary</span>", unsafe_allow_html=True)
        return

    # ── Reference pages: render in main window ──
    if st.session_state.active_page == "about":
        st.markdown(f"""
<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};line-height:1.6;max-width:800px;">

<strong style="font-size:0.82rem;">Purpose</strong><br>
The Manufacturing Location Analyzer enables strategic evaluation of manufacturing location alternatives.
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
<li><strong>Payables (DPO)</strong> = (Material x Qty / 365) x Payment Terms Days &mdash; reduces NWC</li>
<li><strong>Total NWC</strong> = GIT + Safety Stock + Cycle Stock - Payables</li>
<li><strong>Delta NWC</strong> = NWC(location) - NWC(base)</li>
<li><strong>NWC Carrying Cost</strong> = Delta NWC x Total Carrying Cost % (per factory: WACC + Risk + Storage + Service)</li>
<li><strong>Adjusted OP</strong> = OP - NWC Carrying Cost per unit</li>
</ul>

<br><strong style="font-size:0.9rem;">Required Investments Analysis</strong><br>
A separate module evaluates the overall investment rationale for each production transfer:
<ul style="margin:0.3rem 0 0.3rem 1.2rem;padding:0;">
<li><strong>Total Investment</strong> = CAPEX + OPEX + Restructuring</li>
<li><strong>Annual Savings</strong> = NWC-Adjusted Annual OP (alternative) - NWC-Adjusted Annual OP (base)</li>
<li><strong>NPV</strong> = -Investment + &Sigma; [Annual Savings / (1+r)<sup>t</sup>] over the analysis horizon</li>
<li><strong>IRR</strong> = Discount rate where NPV = 0 (solved numerically)</li>
<li><strong>Simple Payback</strong> = Total Investment / Annual Savings</li>
<li><strong>Discounted Payback</strong> = First year where cumulative discounted cash flow &ge; 0</li>
</ul>
Investment inputs are per receiving factory and per item. The discount rate defaults to the Company WACC.

</div>
""", unsafe_allow_html=True)
        return

    if st.session_state.active_page == "guide":
        st.markdown(f"""<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};line-height:1.6;max-width:800px;">
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
<strong>1.</strong> Set analysis name, currency, target market<br>
<strong>2.</strong> Configure factory assumptions matrix<br>
<strong>3.</strong> Assign factory countries for lead times<br>
<strong>4.</strong> Set Company WACC, carrying cost rates, and NWC assumptions<br>
<strong>5.</strong> Add items with costs and overrides<br>
<strong>6.</strong> Review results, sensitivity, investment<br>
<strong>7.</strong> Add strategic context per item<br>
<strong>8.</strong> Export PDF or Excel
</div>""", unsafe_allow_html=True)
        return

    if st.session_state.active_page == "changelog":
        st.markdown(f"""
<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};line-height:1.6;max-width:800px;">
<strong style="font-size:0.82rem;">Changelog</strong><br>
<span style="color:{GREY_TEXT};">v9.0</span> &mdash; Qualitative context, Data Classification, sidebar nav<br>
<span style="color:{GREY_TEXT};">v8.0</span> &mdash; Required Investments Analysis (NPV, IRR, payback)<br>
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
        return

    # ── PRE-STUDY PAGE ─────────────────────────────────────────
    if st.session_state.active_page == "prestudy":
        project_name = st.session_state.project_name
        data_classification = st.session_state.get("data_classification", "C3 - Confidential")
        st.markdown(f"""<div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.8rem;">
            <div style="font-family:Inter,sans-serif;font-size:1.1rem;font-weight:700;color:{NAVY};">Pre-study <span style="font-weight:400;color:{DARK_TEXT};">|</span> {project_name}</div>
            <div style="background:{NAVY};color:#fff;font-size:0.62rem;font-weight:600;padding:0.2rem 0.7rem;border-radius:2px;text-transform:uppercase;letter-spacing:0.06em;">Footprint Optimization</div>
        </div>""", unsafe_allow_html=True)
        st.markdown(f'<div class="callout" style="font-size:0.72rem;">Structured evaluation framework for the pre-study phase. Captures strategic rationale, current set-up, key questions, dependencies, and team. Complete this document before submitting a formal proposal to the Factory Council.</div>', unsafe_allow_html=True)

        ps_left, ps_right = st.columns([3, 2])
        with ps_left:
            # Strategic Rationale (merged from Strategic Context page)
            st.markdown(f'<div class="sec-sm">Strategic Rationale</div>', unsafe_allow_html=True)
            st.session_state.ps_strategic_rationale = st.text_area(
                "Strategic Rationale", value=st.session_state.ps_strategic_rationale,
                key="ps_strat_input", height=100, label_visibility="collapsed",
                placeholder="Why is this transfer being considered? What strategic objective does it serve? (e.g. cost competitiveness, capacity, market proximity, risk diversification)")

            st.markdown(f'<div class="sec-sm">Purpose & Objective</div>', unsafe_allow_html=True)
            st.session_state.ps_purpose = st.text_area(
                "Purpose", value=st.session_state.ps_purpose,
                key="ps_purpose_input", height=80, label_visibility="collapsed",
                placeholder="What is the specific goal of this evaluation? (e.g. annual sourcing review, new product launch, capacity constraint resolution)")

            st.markdown(f'<div class="sec-sm">Background & Current Set-up</div>', unsafe_allow_html=True)
            st.session_state.ps_background = st.text_area(
                "Background", value=st.session_state.ps_background,
                key="ps_bg_input", height=100, label_visibility="collapsed",
                placeholder="Describe the current manufacturing set-up, volumes, and relevant context...")

            st.markdown(f'<div class="sec-sm">Reason to Change Current Set-up</div>', unsafe_allow_html=True)
            st.session_state.ps_reason = st.text_area(
                "Reason", value=st.session_state.ps_reason,
                key="ps_reason_input", height=100, label_visibility="collapsed",
                placeholder="Why is a change being considered? What triggers this evaluation?...")

            st.markdown(f'<div class="sec-sm">What Happens If We Don\'t Do This?</div>', unsafe_allow_html=True)
            st.session_state.ps_risk_of_inaction = st.text_area(
                "Risk of Inaction", value=st.session_state.ps_risk_of_inaction,
                key="ps_inaction_input", height=80, label_visibility="collapsed",
                placeholder="Describe the consequence of maintaining the status quo. (e.g. continued margin erosion, capacity bottleneck, single-source risk)")

            st.markdown(f'<div class="sec-sm">Key Risks & Mitigations</div>', unsafe_allow_html=True)
            st.session_state.ps_key_risks = st.text_area(
                "Key Risks", value=st.session_state.ps_key_risks,
                key="ps_risks_input", height=80, label_visibility="collapsed",
                placeholder="What are the main risks? (e.g. quality ramp-up, customer approval timeline, IP concerns, FX exposure, geopolitical risk)")

            st.markdown(f'<div class="sec-sm">Key Questions to Review</div>', unsafe_allow_html=True)
            st.session_state.ps_questions = st.text_area(
                "Questions", value=st.session_state.ps_questions,
                key="ps_questions_input", height=100, label_visibility="collapsed",
                placeholder="List the key questions that need to be answered during the pre-study phase...")

        with ps_right:
            # Cross-functional dependencies
            st.markdown(f'<div class="sec-sm">Cross-functional Dependencies & How to Manage</div>', unsafe_allow_html=True)
            dep_df = pd.DataFrame(st.session_state.ps_dependencies)
            if "Dependency" not in dep_df.columns:
                dep_df = pd.DataFrame([{"Dependency": "", "How to Manage": ""}])
            edited_deps = st.data_editor(
                dep_df, use_container_width=True, num_rows="dynamic", key="ps_dep_editor",
                hide_index=True,
                column_config={
                    "Dependency": st.column_config.TextColumn("Dependency", width=180),
                    "How to Manage": st.column_config.TextColumn("How to Manage", width=260),
                })
            st.session_state.ps_dependencies = edited_deps.to_dict("records")

            # Team
            st.markdown(f'<div class="sec-sm">Team</div>', unsafe_allow_html=True)
            st.session_state.ps_sponsor = st.text_input("Initiative Sponsor", value=st.session_state.ps_sponsor, key="ps_sponsor_input")
            st.session_state.ps_lead = st.text_input("Initiative Lead", value=st.session_state.ps_lead, key="ps_lead_input")
            st.session_state.ps_main_entity = st.text_input("Main Entity(s)", value=st.session_state.ps_main_entity, key="ps_entity_input")
            st.session_state.ps_impact_entities = st.text_input("Impact Assessment on Other Entity(s)", value=st.session_state.ps_impact_entities, key="ps_impact_input")
            st.session_state.ps_team = st.text_area(
                "Pre-study Team", value=st.session_state.ps_team,
                key="ps_team_input", height=80, label_visibility="visible",
                placeholder="Team members and their roles / regions...")

            # Time Plan
            st.markdown(f'<div class="sec-sm">Time Plan</div>', unsafe_allow_html=True)
            tl = st.session_state.ps_timeline
            tl_df = pd.DataFrame({"Milestone": list(tl.keys()), "Target Date": list(tl.values())})
            edited_tl = st.data_editor(
                tl_df, use_container_width=True, num_rows="fixed", key="ps_timeline_editor",
                hide_index=True,
                column_config={
                    "Milestone": st.column_config.TextColumn("Milestone", disabled=True, width=200),
                    "Target Date": st.column_config.TextColumn("Target Date", width=160),
                },
                disabled=["Milestone"])
            st.session_state.ps_timeline = dict(zip(edited_tl["Milestone"], edited_tl["Target Date"].fillna("")))

        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>{data_classification} &middot; {project_name} &middot; Pre-study</span>", unsafe_allow_html=True)
        return

    # ── PROPOSAL PAGE ──────────────────────────────────────────
    if st.session_state.active_page == "proposal":
        project_name = st.session_state.project_name
        data_classification = st.session_state.get("data_classification", "C3 - Confidential")
        currency = st.session_state.get("currency", "SEK")
        all_results = st.session_state.get("_all_results", [])

        st.markdown(f"""<div style="font-family:Inter,sans-serif;font-size:1.1rem;font-weight:700;color:{NAVY};margin-bottom:0.8rem;">
            Proposal <span style="font-weight:400;color:{DARK_TEXT};">|</span> {project_name}
        </div>""", unsafe_allow_html=True)
        st.markdown(f'<div class="callout" style="font-size:0.72rem;">One-page decision summary for the Factory Council. Financial figures are auto-populated from the Required Investments analysis where available.</div>', unsafe_allow_html=True)

        # Auto-generate direction from model results if not already set
        if not st.session_state.prop_direction.strip() and all_results:
            try:
                best_name, best_delta = "", 0.0
                base_om = 0.0
                for item_data in all_results:
                    results = item_data.get("results", [])
                    if len(results) >= 2:
                        base_om = results[0].get("operating_margin_pct", 0)
                        for r in results[1:]:
                            delta = r.get("operating_margin_pct", 0) - base_om
                            if delta > best_delta:
                                best_delta = delta
                                best_name = r.get("name", "")
                if best_name:
                    base_name = all_results[0]["results"][0].get("name", "Base") if all_results[0].get("results") else "Base"
                    st.session_state.prop_direction = (
                        f"Transfer production from {base_name} to {best_name}, "
                        f"achieving {best_delta:+.1f}pp operating margin improvement."
                    )
            except (KeyError, IndexError):
                pass

        prop_left, prop_right = st.columns([2, 3])
        with prop_left:
            st.markdown(f'<div class="sec-sm">Direction</div>', unsafe_allow_html=True)
            st.session_state.prop_direction = st.text_area(
                "Direction", value=st.session_state.prop_direction,
                key="prop_direction_input", height=160, label_visibility="collapsed",
                placeholder="Describe the recommended direction and key rationale...")

        with prop_right:
            # Benefits & Key Details (bundled)
            st.markdown(f'<div class="sec-sm">Benefits & Key Details</div>', unsafe_allow_html=True)
            st.session_state.prop_benefits = st.text_area(
                "Benefits", value=st.session_state.prop_benefits,
                key="prop_benefits_input", height=140, label_visibility="collapsed",
                placeholder="List key benefits and relevant details (use bullet points):\n- Margin improvement of X.Xpp\n  - Lower VA cost at receiving site\n- Risk diversification\n- Relevant technical / market details...")

            # Financials & Time Plan — proper numeric inputs
            st.markdown(f'<div class="sec-sm">Financials & Time Plan</div>', unsafe_allow_html=True)
            # Auto-populate investment total from model
            auto_inv = 0.0
            if all_results:
                for item_data in all_results:
                    for ic in item_data.get("investment_cases", []):
                        auto_inv += ic.get("total_investment", 0)
            auto_inv_m = auto_inv / 1e6 if auto_inv else 0.0

            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                inv_val = st.session_state.prop_total_investment if st.session_state.prop_total_investment is not None else (auto_inv_m if auto_inv_m else None)
                new_inv = st.number_input(
                    f"Total Investment (M{currency})", value=inv_val,
                    min_value=0.0, step=0.5, format="%.1f", key="prop_inv_input")
                st.session_state.prop_total_investment = new_inv
                if auto_inv_m > 0:
                    st.markdown(f'<div style="font-size:0.62rem;color:{GREY_TEXT};margin-top:-0.5rem;font-style:italic;">Auto-calculated: {auto_inv_m:.1f} M{currency}</div>', unsafe_allow_html=True)
            with fc2:
                new_cash = st.number_input(
                    f"Cash Out (M{currency})", value=st.session_state.prop_cash_out or 0.0,
                    min_value=0.0, step=0.5, format="%.1f", key="prop_cash_input")
                st.session_state.prop_cash_out = new_cash
            with fc3:
                st.session_state.prop_timeplan = st.text_input(
                    "Time Plan", value=st.session_state.prop_timeplan,
                    key="prop_timeplan_input",
                    placeholder="e.g. May '25 — Dec '26")

        # Dependencies, Risks & Mitigations (full width)
        st.markdown(f'<div class="sec-sm">Dependencies, Risks & Mitigations</div>', unsafe_allow_html=True)
        risk_df = pd.DataFrame(st.session_state.prop_risks)
        if "Risk" not in risk_df.columns:
            risk_df = pd.DataFrame([{"Risk": "", "Mitigation": ""}])
        edited_risks = st.data_editor(
            risk_df, use_container_width=True, num_rows="dynamic", key="prop_risks_editor",
            hide_index=True,
            column_config={
                "Risk": st.column_config.TextColumn("Risk / Dependency", width=280),
                "Mitigation": st.column_config.TextColumn("Mitigation", width=320),
            })
        st.session_state.prop_risks = edited_risks.to_dict("records")

        # Team — read-only reference from Pre-study
        st.markdown(f'<div class="sec-sm">Team</div>', unsafe_allow_html=True)
        team_data = {
            "Role": ["Initiative Sponsor", "Initiative Lead", "Main Entity(s)", "Pre-study Team"],
            "Name": [
                st.session_state.ps_sponsor or "—",
                st.session_state.ps_lead or "—",
                st.session_state.ps_main_entity or "—",
                st.session_state.ps_team.replace("\n", ", ") if st.session_state.ps_team else "—",
            ],
        }
        has_team = any(v != "—" for v in team_data["Name"])
        if has_team:
            team_html = '<table class="ib-table"><thead><tr><th>Role</th><th>Name</th></tr></thead><tbody>'
            for role, name in zip(team_data["Role"], team_data["Name"]):
                team_html += f'<tr><td>{role}</td><td>{name}</td></tr>'
            team_html += '</tbody></table>'
            st.markdown(team_html, unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="font-size:0.72rem;color:{GREY_TEXT};font-style:italic;">Complete the Team section on the Pre-study page to populate this table.</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>{data_classification} &middot; {project_name} &middot; Proposal</span>", unsafe_allow_html=True)
        return

    # ── TRANSFER DETAILS PAGE ──────────────────────────────────
    if st.session_state.active_page == "transfer":
        project_name = st.session_state.project_name
        data_classification = st.session_state.get("data_classification", "C3 - Confidential")
        all_factory_names = st.session_state.get("_all_factory_names", ["Base Case"])
        factory_countries = st.session_state.get("_factory_countries", {})

        st.markdown(f"""<div style="font-family:Inter,sans-serif;font-size:1.1rem;font-weight:700;color:{NAVY};margin-bottom:0.8rem;">
            Transfer Details <span style="font-weight:400;color:{DARK_TEXT};">|</span> {project_name}
        </div>""", unsafe_allow_html=True)

        # Auto-populate transfer from/to from factory config if empty
        if not st.session_state.td_transfer_from and len(all_factory_names) >= 1:
            st.session_state.td_transfer_from = all_factory_names[0]
        if not st.session_state.td_transfer_to and len(all_factory_names) >= 2:
            st.session_state.td_transfer_to = all_factory_names[1]

        # Auto-fetch transfer volume from analysis results (From factory)
        _all_res = st.session_state.get("_all_results", [])
        _td_total_ps_msek = ""
        _td_total_qty = ""
        if _all_res:
            _from_name = st.session_state.td_transfer_from
            _ps_sum = 0.0
            _qty_sum = 0
            for item in _all_res:
                inp = item.get("_inputs_dc")
                for r in item.get("results", []):
                    if r.get("name") == _from_name:
                        _ps_sum += r["ps"] * (inp.net_sales_qty if inp else 0)
                        _qty_sum += inp.net_sales_qty if inp else 0
            if _ps_sum > 0:
                _td_total_ps_msek = f"{_ps_sum / 1e6:.1f} MSEK"
            if _qty_sum > 0:
                _td_total_qty = f"{_qty_sum:,.0f}"
        # Auto-populate transfer volume if empty
        if not st.session_state.td_transfer_volume and _td_total_ps_msek:
            st.session_state.td_transfer_volume = _td_total_ps_msek

        # Header bar — six key-value pairs in styled boxes (From first, then To)
        st.markdown(f"""<div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:1rem;">
            <div style="flex:1;min-width:200px;background:{NAVY};color:#fff;padding:0.5rem 0.8rem;border-radius:3px;">
                <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.06em;opacity:0.8;">Transfer from</div>
                <div style="font-size:0.8rem;font-weight:600;">{st.session_state.td_transfer_from or '—'}</div>
            </div>
            <div style="flex:1;min-width:200px;background:{NAVY};color:#fff;padding:0.5rem 0.8rem;border-radius:3px;">
                <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.06em;opacity:0.8;">Transfer to</div>
                <div style="font-size:0.8rem;font-weight:600;">{st.session_state.td_transfer_to or '—'}</div>
            </div>
            <div style="flex:1;min-width:150px;background:#e8edf5;padding:0.5rem 0.8rem;border-radius:3px;">
                <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.06em;color:{GREY_TEXT};">Product Line</div>
                <div style="font-size:0.8rem;font-weight:600;color:{DARK_TEXT};">{st.session_state.td_product_line or '—'}</div>
            </div>
            <div style="flex:1;min-width:150px;background:#e8edf5;padding:0.5rem 0.8rem;border-radius:3px;">
                <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.06em;color:{GREY_TEXT};">Material Family</div>
                <div style="font-size:0.8rem;font-weight:600;color:{DARK_TEXT};">{st.session_state.td_material_family or '—'}</div>
            </div>
            <div style="flex:1;min-width:150px;background:{NAVY};color:#fff;padding:0.5rem 0.8rem;border-radius:3px;">
                <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.06em;opacity:0.8;">Transfer Volume</div>
                <div style="font-size:0.8rem;font-weight:600;">{st.session_state.td_transfer_volume or '—'}</div>
            </div>
            <div style="flex:1;min-width:150px;background:#e8edf5;padding:0.5rem 0.8rem;border-radius:3px;">
                <div style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.06em;color:{GREY_TEXT};">Indicative Timing</div>
                <div style="font-size:0.8rem;font-weight:600;color:{DARK_TEXT};">{st.session_state.td_indicative_timing or '—'}</div>
            </div>
        </div>""", unsafe_allow_html=True)

        # Editable header fields
        with st.expander("Edit Transfer Header", expanded=False):
            hc1, hc2, hc3 = st.columns(3)
            with hc1:
                st.session_state.td_transfer_from = st.text_input("Transfer From", value=st.session_state.td_transfer_from, key="td_from_input")
                st.session_state.td_transfer_to = st.text_input("Transfer To", value=st.session_state.td_transfer_to, key="td_to_input")
            with hc2:
                st.session_state.td_product_line = st.text_input("Product Line", value=st.session_state.td_product_line, key="td_pl_input")
                st.session_state.td_material_family = st.text_input("Material Family", value=st.session_state.td_material_family, key="td_mf_input")
            with hc3:
                st.session_state.td_transfer_volume = st.text_input("Transfer Volume", value=st.session_state.td_transfer_volume, key="td_vol_input")
                st.session_state.td_indicative_timing = st.text_input("Indicative Timing", value=st.session_state.td_indicative_timing, key="td_timing_input")

        # Requirements sections — custom-rendered rows with stacked questions & conditional follow-ups
        td_reqs = st.session_state.td_requirements

        _section_styles = {
            "Base Requirements": f"background:{NAVY};color:#fff;",
            "Commercial Requirements": f"background:#4472C4;color:#fff;",
            "Product Line & Supply Chain Requirements": f"background:#7B9CD6;color:#fff;",
            "Financial Requirements": f"background:#A9C0E8;color:{DARK_TEXT};",
        }

        _STATUS_BADGE = {
            "Pending": "background:#FFF3CD;color:#856404;",
            "Approved": "background:#D4EDDA;color:#155724;",
            "Rejected": "background:#F8D7DA;color:#721C24;",
        }

        # Migrate old data format if needed (Related Question -> Follow-up)
        for _sec_name, _sec_rows in td_reqs.items():
            for _row in _sec_rows:
                if "Related Question" in _row and "Follow-up" not in _row:
                    _row["Follow-up"] = _row.pop("Related Question", "")
                    _row["Follow-up Answer"] = _row.pop("Answer", "")
                    _row.setdefault("Condition", "")

        # Column header
        st.markdown(f"""<div style="display:flex;gap:0;font-family:Inter,sans-serif;font-size:0.62rem;font-weight:600;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;padding:0.3rem 0;border-bottom:1px solid #ddd;margin-top:0.5rem;">
            <div style="flex:3;padding-left:0.5rem;">Requirement</div>
            <div style="flex:2;">Value / Answer</div>
            <div style="flex:1.5;">Approver</div>
            <div style="flex:1;">Date</div>
            <div style="flex:1;">Status</div>
            <div style="flex:1.5;">Required Documents</div>
        </div>""", unsafe_allow_html=True)

        for section_name, rows in td_reqs.items():
            style = _section_styles.get(section_name, f"background:{NAVY};color:#fff;")
            st.markdown(f"""<div style="{style}padding:0.45rem 0.8rem;border-radius:3px 3px 0 0;margin-top:1rem;font-family:Inter,sans-serif;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;">
                {section_name}
            </div>""", unsafe_allow_html=True)

            for ri, row in enumerate(rows):
                sec_key = section_name.lower().replace(" ", "_").replace("&", "and")
                req_label = row["Requirement"]
                follow_up = row.get("Follow-up", "")
                condition = row.get("Condition", "")

                # Main question row
                c_req, c_val, c_approver, c_date, c_status, c_docs = st.columns([3, 2, 1.5, 1, 1, 1.5])
                with c_req:
                    st.markdown(f"<div style='font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};padding:0.35rem 0;'>{req_label}</div>", unsafe_allow_html=True)
                with c_val:
                    row["Value"] = st.text_input("val", value=row.get("Value", ""), key=f"td_{sec_key}_{ri}_val", label_visibility="collapsed")
                with c_approver:
                    row["Approver"] = st.text_input("apr", value=row.get("Approver", ""), key=f"td_{sec_key}_{ri}_apr", label_visibility="collapsed")
                with c_date:
                    row["Date"] = st.text_input("dt", value=row.get("Date", ""), key=f"td_{sec_key}_{ri}_dt", label_visibility="collapsed")
                with c_status:
                    _status_opts = ["Pending", "Approved", "Rejected"]
                    _cur_status = row.get("Status", "Pending")
                    _si = _status_opts.index(_cur_status) if _cur_status in _status_opts else 0
                    row["Status"] = st.selectbox("st", _status_opts, index=_si, key=f"td_{sec_key}_{ri}_st", label_visibility="collapsed")
                with c_docs:
                    row["Required Documents"] = st.text_input("doc", value=row.get("Required Documents", ""), key=f"td_{sec_key}_{ri}_doc", label_visibility="collapsed")

                # Follow-up question (stacked below, with conditional logic for "if_no")
                if follow_up:
                    show_follow_up = True
                    if condition == "if_no":
                        main_val = (row.get("Value", "") or "").strip().lower()
                        show_follow_up = main_val in ("no", "n", "false", "0")

                    if show_follow_up:
                        c_fq, c_fa, _, _, _, _ = st.columns([3, 2, 1.5, 1, 1, 1.5])
                        with c_fq:
                            _prefix = "If no: " if condition == "if_no" else ""
                            st.markdown(f"<div style='font-family:Inter,sans-serif;font-size:0.72rem;color:{GREY_TEXT};padding:0 0 0.35rem 1rem;font-style:italic;'>↳ {_prefix}{follow_up}</div>", unsafe_allow_html=True)
                        with c_fa:
                            row["Follow-up Answer"] = st.text_input("fua", value=row.get("Follow-up Answer", ""), key=f"td_{sec_key}_{ri}_fua", label_visibility="collapsed")

                # Separator line between rows
                st.markdown(f"<div style='border-bottom:1px solid #eee;margin:0;'></div>", unsafe_allow_html=True)

        st.session_state.td_requirements = td_reqs

        # Auto-fetch quantity annotation for "Transfer volume (Q)" field
        if _td_total_qty:
            st.markdown(f"<div style='font-family:Inter,sans-serif;font-size:0.68rem;color:{GREY_TEXT};margin-top:0.3rem;'>Auto-fetched from analysis — Transfer quantity: <strong>{_td_total_qty}</strong> units</div>", unsafe_allow_html=True)

        # Approval summary
        total_reqs = sum(len(rows) for rows in td_reqs.values())
        approved = sum(1 for rows in td_reqs.values() for r in rows if r.get("Status") == "Approved")
        pending = sum(1 for rows in td_reqs.values() for r in rows if r.get("Status") == "Pending")
        rejected = sum(1 for rows in td_reqs.values() for r in rows if r.get("Status") == "Rejected")
        st.markdown(f"""<div style="display:flex;gap:1.5rem;margin-top:1rem;font-family:Inter,sans-serif;font-size:0.72rem;">
            <div><span style="display:inline-block;width:10px;height:10px;background:#D4EDDA;border:1px solid #155724;border-radius:2px;margin-right:0.3rem;"></span>Approved: <strong>{approved}</strong>/{total_reqs}</div>
            <div><span style="display:inline-block;width:10px;height:10px;background:#FFF3CD;border:1px solid #856404;border-radius:2px;margin-right:0.3rem;"></span>Pending: <strong>{pending}</strong></div>
            <div><span style="display:inline-block;width:10px;height:10px;background:#F8D7DA;border:1px solid #721C24;border-radius:2px;margin-right:0.3rem;"></span>Rejected: <strong>{rejected}</strong></div>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"<span style='font-size:0.65rem;color:{MUTED};letter-spacing:0.02em;'>{data_classification} &middot; {project_name} &middot; Transfer Details</span>", unsafe_allow_html=True)
        return

    # ── COST MODEL PAGE (active_page == "model") ──

    ex = st.session_state.ex

    # ── PROJECT HEADER ────────────────────────────────────────
    st.markdown('<div class="sec" id="sec-project-setup">Analysis Setup</div>', unsafe_allow_html=True)

    pc1, pc2, pc3, pc4, pc4b, pc5 = st.columns([2, 1, 1, 1, 1, 2])
    with pc1:
        proj_df = pd.DataFrame({"Analysis Name": [st.session_state.project_name]})
        edited_proj = st.data_editor(proj_df, use_container_width=True, num_rows="fixed",
            key="proj_name", hide_index=True,
            column_config={"Analysis Name": st.column_config.TextColumn("Analysis Name", width=280)})
        st.session_state.project_name = str(edited_proj.loc[0, "Analysis Name"] or "New Analysis")

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
            _ = st.download_button("Save Analysis", data=save_data,
                file_name=f"{st.session_state.project_name.replace(' ','_')}.json",
                mime="application/json", help="Download project as JSON to continue later")
            st.markdown(f'<div style="font-size:0.6rem;font-family:Inter,sans-serif;color:{GREY_TEXT};margin-top:-0.5rem;">Save to continue later</div>', unsafe_allow_html=True)
        with sc2:
            st.markdown(f'<div style="font-size:0.6rem;font-family:Inter,sans-serif;color:{GREY_TEXT};margin-bottom:0.2rem;">Load a previously saved project (.json)</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("Load Project", type=["json"], key="load_proj", label_visibility="collapsed")
            if uploaded:
                try:
                    proj = json.load(uploaded)
                    st.session_state.project_name = proj.get("project_name", "Loaded Analysis")
                    st.session_state.project_items = proj.get("project_items", [{"id": 0}])
                    st.session_state.next_id = proj.get("next_id", 1)
                    # Restore governance data
                    for gk in ("ps_strategic_rationale", "ps_purpose", "ps_risk_of_inaction",
                               "ps_key_risks", "ps_background", "ps_reason", "ps_questions", "ps_sponsor",
                               "ps_lead", "ps_main_entity", "ps_impact_entities", "ps_team",
                               "prop_direction", "prop_benefits", "prop_timeplan",
                               "td_transfer_to", "td_transfer_from", "td_product_line",
                               "td_material_family", "td_transfer_volume", "td_indicative_timing"):
                        if gk in proj:
                            st.session_state[gk] = proj[gk]
                    for gk_obj in ("ps_dependencies", "ps_timeline", "prop_risks",
                                   "td_requirements"):
                        if gk_obj in proj:
                            st.session_state[gk_obj] = proj[gk_obj]
                    if "prop_total_investment" in proj:
                        st.session_state.prop_total_investment = proj["prop_total_investment"]
                    if "prop_cash_out" in proj:
                        st.session_state.prop_cash_out = proj["prop_cash_out"]
                    st.rerun()
                except Exception:
                    st.error("Invalid project file.")

    # ── SHARED FACTORY SETUP ──────────────────────────────────────
    st.markdown('<div class="sec" id="sec-factory-config">Shared Factory Configuration</div>', unsafe_allow_html=True)

    # Number of comparison factories
    fc_df = pd.DataFrame({"Comparison Factories": [4 if ex else st.session_state.get("num_fac", 2)]})
    edited_fc = st.data_editor(fc_df, use_container_width=False, num_rows="fixed",
        key="fc_editor", hide_index=True,
        column_config={"Comparison Factories": st.column_config.SelectboxColumn(
            "Comparison Factories", options=list(range(1, 9)), required=True, width=180)})
    num_factories = max(1, int(edited_fc.loc[0, "Comparison Factories"] or 2))
    st.session_state["num_fac"] = num_factories

    # Factory locations — consolidated table (first row = current factory)
    st.markdown(f'<div class="callout">Name each factory and assign its <strong>country</strong>. The first row is your <strong>current factory</strong> (base case). This determines lead time to the target market (<strong>{target_market}</strong>).</div>', unsafe_allow_html=True)

    ex_base_name = EX_BASE.name if ex else "Base Case"
    ex_base_country = "Sweden" if ex else "Sweden"
    ex_factory_countries = ["Germany", "China", "France", "USA"] if ex else []
    country_data = {"Factory": [ex_base_name], "Country": [ex_base_country],
                    "Guide": ["Current factory (base case)"]}
    for i in range(num_factories):
        ex_f = EX_FACTORIES[i] if ex and i < len(EX_FACTORIES) else None
        col_name = ex_f.name if ex_f else f"Factory {i+2}"
        country_data["Factory"].append(col_name)
        country_data["Country"].append(ex_factory_countries[i] if ex and i < len(ex_factory_countries) else "")
        country_data["Guide"].append(f"Comparison factory {i+1}")
    country_df = pd.DataFrame(country_data)

    edited_countries = st.data_editor(
        country_df, use_container_width=False, num_rows="fixed", key="country_editor", hide_index=True,
        column_config={
            "Factory": st.column_config.TextColumn("Factory", width=200),
            "Country": st.column_config.SelectboxColumn("Country", options=COUNTRIES, width=180),
            "Guide": st.column_config.TextColumn("Guide", width=220, disabled=True),
        },
        disabled=["Guide"],
    )
    # Read back edited factory names (user may have renamed them)
    edited_factory_names = list(edited_countries["Factory"])
    base_factory_name = str(edited_factory_names[0] or "Base Case")
    factory_countries = {}
    for _, r in edited_countries.iterrows():
        factory_countries[str(r["Factory"])] = str(r["Country"] or "")
    st.session_state["_factory_countries"] = factory_countries

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
        # Use edited name from country table if available, otherwise default
        col_name = str(edited_factory_names[i + 1]) if (i + 1) < len(edited_factory_names) else (ex_f.name if ex_f else f"Factory {i+2}")
        factory_col_names.append(col_name)
        if ex_f:
            factory_cols[col_name] = [ex_f.va_ratio, ex_f.ps_index, ex_f.mcl_pct, ex_f.sa_pct,
                                      ex_f.tpl, ex_f.tariff_pct, ex_f.duties_pct, ex_f.transport_pct]
        else:
            factory_cols[col_name] = [1.0, 1.0, 100.0, 0.0, 100.0, 0.0, 0.0, 0.0]

    factory_cols["Guide"] = GUIDES
    df_matrix = pd.DataFrame(factory_cols, index=ROWS)
    df_matrix.loc["VA Ratio", base_factory_name] = None
    st.session_state["_all_factory_names"] = [base_factory_name] + factory_col_names

    st.markdown('<div class="sec-sm" id="sec-assumptions">Assumptions Matrix</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="callout">These assumptions apply to <strong>all items</strong> in the project. Current factory (<strong>{base_factory_name}</strong>) VA Ratio is 1.0x (implicit).</div>', unsafe_allow_html=True)

    col_config = {
        base_factory_name: st.column_config.NumberColumn(base_factory_name, format="%.2f"),
        **{cn: st.column_config.NumberColumn(cn, format="%.2f") for cn in factory_col_names},
        "Guide": st.column_config.TextColumn("Guide", width=320, disabled=True),
    }

    edited_df = st.data_editor(
        df_matrix, use_container_width=True, num_rows="fixed", key="assumption_matrix",
        column_config=col_config, disabled=["Guide"])

    # ── NWC ASSUMPTIONS (major section) ──────────────────────
    st.markdown('<div class="sec" id="sec-nwc">NWC Assumptions</div>', unsafe_allow_html=True)

    # Lead time comparison (subsection within NWC)
    if target_market:
        st.markdown(f'<div class="sec-sm" id="sec-lead-times">Lead Time to {target_market}</div>', unsafe_allow_html=True)
        all_factory_names = [base_factory_name] + factory_col_names
        base_country = factory_countries.get(base_factory_name, "")
        base_lt_est = estimate_lead_time(base_country, target_market)

        # Build editable transit days via data_editor (single row, column per factory)
        lt_defaults = {}
        for fn_ in all_factory_names:
            ctry = factory_countries.get(fn_, "")
            est = estimate_lead_time(ctry, target_market)
            lt_defaults[fn_] = {"est": est, "country": ctry}

        lt_edit_data = {}
        for fn_ in all_factory_names:
            ov_key = f"lt_override_{fn_}"
            est = lt_defaults[fn_]["est"]
            lt_edit_data[fn_] = [st.session_state.get(ov_key, est if est is not None else 0)]

        lt_edit_df = pd.DataFrame(lt_edit_data)
        lt_col_config = {fn_: st.column_config.NumberColumn(fn_, min_value=0, step=1, format="%d") for fn_ in all_factory_names}
        edited_lt = st.data_editor(lt_edit_df, column_config=lt_col_config, hide_index=True, use_container_width=True, key="lt_editor")

        # Persist edited values
        for fn_ in all_factory_names:
            ov_key = f"lt_override_{fn_}"
            st.session_state[ov_key] = int(edited_lt[fn_].iloc[0]) if pd.notna(edited_lt[fn_].iloc[0]) else lt_defaults[fn_]["est"]

        # Build display table (Route, Transit Days with override indicator, Delta)
        has_any_override = False
        lt_data_final = []
        base_lt_final = st.session_state.get(f"lt_override_{base_factory_name}", base_lt_est) or base_lt_est
        for fn_ in all_factory_names:
            ctry = lt_defaults[fn_]["country"]
            est = lt_defaults[fn_]["est"]
            lt = st.session_state.get(f"lt_override_{fn_}", est)
            is_overridden = lt is not None and est is not None and lt != est
            if is_overridden:
                has_any_override = True
            delta = (lt - base_lt_final) if (lt is not None and base_lt_final is not None) else None
            lt_data_final.append({"Factory": fn_, "Country": ctry,
                "Route": f"{ctry} \u2192 {target_market}" if ctry else "\u2013",
                "Estimated": est, "Transit Days": lt,
                "Delta vs Base": delta if delta is not None and fn_ != base_factory_name else None,
                "overridden": is_overridden})

        hdr = "".join(f'<th>{r["Factory"]}</th>' for r in lt_data_final)
        route_cells = "".join(f'<td class="{"base-case" if i==0 else ""}">{r["Route"]}</td>' for i, r in enumerate(lt_data_final))
        dash = "\u2013"
        days_cells = ""
        for i, r in enumerate(lt_data_final):
            cls = "base-case" if i == 0 else ""
            val_str = str(r["Transit Days"]) if r["Transit Days"] is not None else dash
            if r["overridden"]:
                val_str = f'<span style="color:{ACCENT_BLUE};font-weight:700;" title="Estimated: {r["Estimated"]} days">{val_str} *</span>'
            days_cells += f'<td class="{cls}">{val_str}</td>'
        delta_cells = ""
        for i, r in enumerate(lt_data_final):
            if i == 0:
                delta_cells += f'<td class="base-case">{dash}</td>'
            else:
                d = r["Delta vs Base"]
                if d is not None and d != 0:
                    sign = "+" if d > 0 else ""
                    cls = "delta-neg" if d > 0 else "delta-pos"
                    delta_cells += f'<td class="{cls}">{sign}{d} days</td>'
                else:
                    delta_cells += f'<td>{dash}</td>'
        lt_html = f'<table class="ib-table"><thead><tr><th>Lead Time</th>{hdr}</tr></thead><tbody>'
        lt_html += f'<tr><td>Route</td>{route_cells}</tr>'
        lt_html += f'<tr class="row-bold"><td>Transit Days</td>{days_cells}</tr>'
        lt_html += f'<tr class="row-bold"><td><em>Delta vs. Base</em></td>{delta_cells}</tr>'
        lt_html += '</tbody></table>'
        if has_any_override:
            lt_html += f'<div style="font-size:0.68rem;color:{ACCENT_BLUE};margin-top:0.3rem;font-style:italic;">* Manual override \u2014 estimated value from lead time matrix has been replaced.</div>'
        st.markdown(lt_html, unsafe_allow_html=True)

    # ── NWC inventory & payment terms ──────────────────────
    all_factory_names_nwc = [base_factory_name] + factory_col_names
    st.markdown(f'<div class="sec-sm">Inventory &amp; Payment Terms</div>', unsafe_allow_html=True)
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

    # ── Read financial configuration from session state ──────
    carrying_cost_rates = st.session_state.get("_carrying_cost_rates", {})
    company_wacc = st.session_state.get("company_wacc", 0.08)
    target_payback = st.session_state.get("target_payback", 3)
    target_om = st.session_state.get("target_om", 0.20)

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

    # Batch upload section
    all_factory_names_batch = [base_factory_name] + factory_col_names
    with st.expander("Batch Upload (Excel)", expanded=False):
        st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.73rem;color:{GREY_TEXT};line-height:1.5;margin-bottom:0.5rem;">Upload an Excel file to import multiple items at once. Download the template first, fill in your data, then upload. Factory configuration (above) must be set up before importing.</div>', unsafe_allow_html=True)

        bu_c1, bu_c2 = st.columns(2)
        with bu_c1:
            try:
                template_data = _generate_batch_template(all_factory_names_batch, currency)
                st.download_button(
                    "Download Template",
                    data=template_data,
                    file_name=f"Batch_Upload_Template_{currency}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="batch_template_dl",
                    use_container_width=True,
                )
            except ImportError:
                st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.72rem;color:{GREY_TEXT};">Template generation requires xlsxwriter.</div>', unsafe_allow_html=True)
        with bu_c2:
            batch_file = st.file_uploader(
                "Upload Items (.xlsx)",
                type=["xlsx"],
                key="batch_upload",
                label_visibility="collapsed",
            )

        if batch_file is not None:
            items_parsed, ovs_parsed, invs_parsed, parse_warnings = _parse_batch_upload(batch_file, currency)

            if parse_warnings:
                for w in parse_warnings:
                    st.warning(w)

            if items_parsed:
                st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:0.76rem;color:{DARK_TEXT};margin:0.3rem 0;"><strong>{len(items_parsed)}</strong> items found &nbsp;|&nbsp; <strong>{len(ovs_parsed)}</strong> cost overrides &nbsp;|&nbsp; <strong>{len(invs_parsed)}</strong> investment entries</div>', unsafe_allow_html=True)

                # Preview table
                preview_df = pd.DataFrame([{
                    "Item": f"{it['item_number']} {it['designation']}".strip(),
                    "Material": it["material"],
                    "Var. VA": it["variable_va"],
                    "Fixed VA": it["fixed_va"],
                    "Y1 Revenue": it["net_sales_value"],
                    "Y1 Qty": it["net_sales_qty"],
                    "Years": len(it.get("sales_projection", [])),
                } for it in items_parsed])
                st.dataframe(preview_df, use_container_width=True, hide_index=True, height=min(200, 35 + len(items_parsed) * 35))

                if st.button("Import Items", key="batch_import_btn", type="primary", use_container_width=True):
                    _apply_batch_items(items_parsed, ovs_parsed, invs_parsed)
                    st.rerun()

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

                # Resolve lead times for NWC calculation (use overrides if set)
                base_country = factory_countries.get(base_factory_name, "")
                base_lt_est = estimate_lead_time(base_country, target_market) if target_market else None
                base_lt = st.session_state.get(f"lt_override_{base_factory_name}", base_lt_est) if target_market else None
                if base_lt is None:
                    base_lt = base_lt_est

                results = []
                base_cc_rate = carrying_cost_rates.get(base_factory_name, 0.18)
                br = compute_location(inputs, base, is_base=True,
                    lead_time_days=base_lt, base_lead_time_days=base_lt,
                    cost_of_capital=base_cc_rate,
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
                        f_lt_est = estimate_lead_time(f.country, target_market) if target_market and f.country else None
                        f_lt = st.session_state.get(f"lt_override_{f.name}", f_lt_est) if target_market else None
                        if f_lt is None:
                            f_lt = f_lt_est
                        f_nwc = nwc_assumptions.get(f.name, {})
                        f_cc_rate = carrying_cost_rates.get(f.name, 0.18)
                        r = compute_location(inputs, f, overrides=ov,
                            lead_time_days=f_lt, base_lead_time_days=base_lt,
                            cost_of_capital=f_cc_rate,
                            safety_stock_days=f_nwc.get("safety_stock_days", 0),
                            base_safety_stock_days=base_nwc.get("safety_stock_days", 0),
                            cycle_stock_days=f_nwc.get("cycle_stock_days", 0),
                            base_cycle_stock_days=base_nwc.get("cycle_stock_days", 0),
                            payment_terms_days=f_nwc.get("payment_terms_days", 0),
                            base_payment_terms_days=base_nwc.get("payment_terms_days", 0))
                        if r: results.append(r)

                if results:
                    # Qualitative data from Pre-study (project-level)
                    qual_from_state = {
                        "strategic_rationale": st.session_state.get("ps_strategic_rationale", ""),
                        "purpose": st.session_state.get("ps_purpose", ""),
                        "risk_of_inaction": st.session_state.get("ps_risk_of_inaction", ""),
                        "risks": st.session_state.get("ps_key_risks", ""),
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
                        plotly_chart(build_charts(results, currency))

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
                                st.markdown(f'<div style="font-size:0.7rem;font-family:Inter,sans-serif;font-weight:600;color:{DARK_TEXT};margin-bottom:0.2rem;">Cost Bridge: {wf_r["name"]} ({currency}/unit)</div>', unsafe_allow_html=True)
                                plotly_chart(build_waterfall_chart(wf_r, currency))
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
                                    plotly_chart(tornado_fig)

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
                        plotly_chart(fig_sa)

                    inv_results = []

                    # ── QUALITATIVE DATA (read from Pre-study, project-level) ──
                    qual = {
                        "strategic_rationale": st.session_state.get("ps_strategic_rationale", ""),
                        "purpose": st.session_state.get("ps_purpose", ""),
                        "risk_of_inaction": st.session_state.get("ps_risk_of_inaction", ""),
                        "risks": st.session_state.get("ps_key_risks", ""),
                    }

                    all_results.append({
                        "inputs": {"item_number": inputs.item_number, "designation": inputs.designation,
                                   "currency": currency, "destination": inputs.destination,
                                   "data_classification": data_classification},
                        "results": results,
                        "investment": inv_results,
                        "qualitative": qual,
                        "_inputs_dc": inputs,
                        "_base_factory": base,
                        "_factories": factories,
                        "_get_ov": get_ov,
                    })

    # Portfolio Summary tab
    with tabs[-1]:
        render_portfolio_summary(all_results, currency, company_wacc=company_wacc,
                                target_payback=target_payback, target_om=target_om)

    # Store results for investment page
    st.session_state["_all_results"] = all_results
    st.session_state["_company_wacc"] = company_wacc
    st.session_state["_factory_countries"] = factory_countries
    st.session_state["_nwc_assumptions"] = nwc_assumptions
    st.session_state["_carrying_cost_rates"] = carrying_cost_rates

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
