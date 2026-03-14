"""
Landed Cost Comparison Model - v5.0
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
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import date, datetime
from fpdf import FPDF

# Import from extracted library modules
from landed_cost.models import FactoryAssumptions, ItemInputs
from landed_cost.compute import compute_location, compute_sensitivity
from landed_cost.lead_times import get_lead_time, estimate_lead_time, LEAD_TIME_MATRIX
from landed_cost.formatters import fn, fp, fi, dc
from landed_cost.constants import (
    NAVY, DARK_TEXT, GREY_TEXT, ACCENT_BLUE, BASE_CASE_BG, BORDER,
    GREEN, RED, MUTED, INPUT_BLUE, CURRENCIES, COUNTRIES,
)

# Constants, models, compute engine, formatters, and lead times
# are imported from the landed_cost package (see landed_cost/ directory).


# ── PAGE CONFIG ───────────────────────────────────────────
st.set_page_config(page_title="Landed Cost Comparison Model", layout="wide", initial_sidebar_state="collapsed")

# ── BLUE INPUT BORDER CSS HELPER ──────────────────────────
# Builds CSS rules for key-based targeting (.st-key-{key})
# Fixed keys from main() in A5, dynamic item keys matched via attribute selectors
INPUT_EDITOR_KEYS = [
    "proj_name", "proj_ccy", "proj_tm", "proj_dt",
    "fc_editor", "bf_editor", "country_editor", "assumption_matrix",
]
_blue_border = f"border-left: 3px solid {INPUT_BLUE} !important; padding-left: 2px;"
_fixed_rules = "\n".join(f"    .st-key-{k} {{ {_blue_border} }}" for k in INPUT_EDITOR_KEYS)
# Dynamic item keys: i0_txt, i1_ns, i2_ov, etc. — use attribute selectors
_dynamic_rules = """    [class*="st-key-"][class*="_txt"] { %(bb)s }
    [class*="st-key-"][class*="_ns"] { %(bb)s }
    [class*="st-key-"][class*="_ov"] { %(bb)s }""" % {"bb": _blue_border}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp {{ font-family: 'Inter', -apple-system, sans-serif; background-color: #ffffff; }}
    .block-container {{ padding: 1.5rem 2.5rem; max-width: 1400px; }}
    #MainMenu, footer, header {{visibility: hidden;}}
    [data-testid="stSidebar"] {{ display: none; }}
    [data-testid="collapsedControl"] {{ display: none; }}
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {{
        border-radius: 2px !important; font-size: 0.78rem !important;
        font-family: 'Inter', sans-serif !important; padding: 0.3rem 0.5rem !important;
        border: 1px solid #ccc !important; height: auto !important; min-height: 0 !important;
    }}
    .stNumberInput > div > div {{ border-radius: 2px !important; }}
    .stNumberInput button {{ border-radius: 0 !important; padding: 0 !important; }}
    .stTextInput label, .stNumberInput label, .stSelectbox label {{
        font-size: 0.72rem !important; font-weight: 600 !important; color: {GREY_TEXT} !important;
        letter-spacing: 0.02em; margin-bottom: 0.15rem !important; font-family: 'Inter', sans-serif !important;
    }}
    .stTextInput, .stNumberInput, .stSelectbox {{ margin-bottom: -0.2rem !important; }}
    div[data-testid="stVerticalBlock"] > div {{ gap: 0.3rem; }}
    .ib-header {{ background: {NAVY}; color: white; padding: 1.2rem 1.8rem 1rem; margin: -1.5rem -2.5rem 1.5rem -2.5rem; }}
    .ib-header h1 {{ font-family: 'Inter', sans-serif; font-size: 1.25rem; font-weight: 700; margin: 0 0 0.15rem 0; }}
    .ib-header .sub {{ font-size: 0.78rem; opacity: 0.8; }}
    .sec {{ font-family: 'Inter', sans-serif; font-size: 0.73rem; font-weight: 700; color: {NAVY};
        text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 2px solid {NAVY};
        padding-bottom: 0.3rem; margin: 1.8rem 0 0.8rem 0; }}
    .sec-sm {{ font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 600; color: {GREY_TEXT};
        text-transform: uppercase; letter-spacing: 0.06em; margin: 0.8rem 0 0.4rem 0; }}
    .ib-table {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; font-family: 'Inter', sans-serif; }}
    .ib-table th {{ background: {NAVY}; color: white; font-weight: 600; font-size: 0.7rem;
        text-transform: uppercase; letter-spacing: 0.03em; padding: 0.45rem 0.7rem;
        text-align: center; border-bottom: 2px solid {NAVY}; }}
    .ib-table th:first-child {{ text-align: left; padding-left: 0.8rem; }}
    .ib-table td {{ padding: 0.35rem 0.7rem; text-align: center; border-bottom: 1px solid #eef0f2; color: {DARK_TEXT}; }}
    .ib-table td:first-child {{ text-align: left; font-weight: 500; padding-left: 0.8rem; }}
    .ib-table tr:last-child td {{ border-bottom: none; }}
    .ib-table .row-bold td {{ font-weight: 700; border-top: 1px solid #bbb; }}
    .ib-table .row-subtotal td {{ font-weight: 600; border-top: 1px solid #ddd; }}
    .ib-table .row-separator td {{ border-bottom: none; padding: 0.1rem; }}
    .ib-table .row-double-top td {{ border-top: 3px double #333; font-weight: 700; }}
    .ib-table .indent td:first-child {{ padding-left: 1.6rem; font-weight: 400; color: {GREY_TEXT}; }}
    .ib-table .base-case {{ background: {BASE_CASE_BG}; }}
    .kpi {{ background: #fafafa; border: 1px solid {BORDER}; border-radius: 2px; padding: 0.8rem 1rem; text-align: center; }}
    .kpi .lbl {{ font-size: 0.65rem; color: {GREY_TEXT}; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 0.2rem; }}
    .kpi .val {{ font-size: 1.15rem; font-weight: 700; color: {DARK_TEXT}; }}
    .kpi .det {{ font-size: 0.68rem; color: {MUTED}; margin-top: 0.1rem; }}
    .delta-pos {{ color: {GREEN}; }}
    .delta-neg {{ color: {RED}; }}
    .callout {{ border-left: 3px solid {NAVY}; padding: 0.6rem 1rem; font-size: 0.75rem;
        color: {GREY_TEXT}; background: #fafafa; margin: 0.6rem 0; line-height: 1.45; }}
    .callout strong {{ color: {DARK_TEXT}; }}
    .stCheckbox label span {{ font-size: 0.78rem !important; font-family: 'Inter', sans-serif !important; }}
    div[data-testid="stDataEditor"] td:last-child {{
        background-color: #f8f9fa !important; color: #6c757d !important;
        font-style: italic !important; font-size: 0.75rem !important;
    }}
    div[data-testid="stDataEditor"] th:last-child {{
        background-color: #e9ecef !important; color: #6c757d !important;
    }}
    /* IB Convention: Blue left border on editable data editors via key-based CSS classes */
    /* Streamlit assigns .st-key-{{key}} class to widget containers based on their key= param */
    /* Fixed editor keys (Project Setup, Factory Config) */
{_fixed_rules}
    /* Dynamic item editor keys (i0_txt, i1_ns, i2_ov, etc.) via attribute selectors */
{_dynamic_rules}
    .stTabs [data-baseweb="tab-list"] {{ gap: 0px; }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'Inter', sans-serif; font-size: 0.78rem; font-weight: 500;
        padding: 0.5rem 1.2rem; border-radius: 0;
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
    html += row("Operating Profit","op",lambda v: fn(v,2,acct=True,dz=True),"row-double-top")
    html += row("Operating Margin","om",lambda v: fp(v,1,dz=False),"row-bold")
    bom = results[0]["om"]
    dash = "\u2013"
    dc_cells = ''.join(f'<td class="{"base-case" if i==0 else dc(r["om"]-bom)}">{dash if i==0 else fp(r["om"]-bom,1,acct=True)}</td>' for i, r in enumerate(results))
    html += f'<tr class="row-bold"><td><em>Delta Margin vs. Base</em></td>{dc_cells}</tr>'
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
    html = f'<table class="ib-table"><thead><tr><th>Full Year ({ccy})</th>{hdr}</tr></thead><tbody>'
    html += row("Annual Revenue","annual_rev",lambda v: fi(v,dz=False))
    html += row("Annual Total Cost","annual_cost",lambda v: fi(v,dz=False))
    html += row("Annual Operating Profit","annual_op",lambda v: fi(v,acct=True,dz=True),"row-bold")
    html += row("Operating Margin","om",lambda v: fp(v,1,dz=False),"row-bold")
    dash = "\u2013"
    dc_cells = ''.join(f'<td class="{"base-case" if i==0 else dc(r["annual_op"]-bop)}">{dash if i==0 else fi(r["annual_op"]-bop,acct=True)}</td>' for i, r in enumerate(results))
    html += f'<tr class="row-double-top"><td><em>Delta vs. Base Case (Annual)</em></td>{dc_cells}</tr></tbody></table>'
    return html

def build_charts(results, ccy):
    names = [r["name"] for r in results]
    oms = [r["om"]*100 for r in results]
    ops = [r["annual_op"] for r in results]
    colors = [NAVY if i==0 else ACCENT_BLUE for i in range(len(results))]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Operating Margin by Location", f"Annual Operating Profit ({ccy})"), horizontal_spacing=0.12)
    fig.add_trace(go.Bar(x=names, y=oms, marker_color=colors, text=[f"{v:.1f}%" for v in oms],
        textposition="outside", textfont=dict(size=11, family="Inter", color=DARK_TEXT),
        hovertemplate="%{x}<br>OM: %{y:.1f}%<extra></extra>", showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=names, y=ops, marker_color=colors, text=[fi(v,dz=False) for v in ops],
        textposition="outside", textfont=dict(size=10, family="Inter", color=DARK_TEXT),
        hovertemplate="%{x}<br>OP: %{y:,.0f}<extra></extra>", showlegend=False), row=1, col=2)
    fig.update_layout(height=400, margin=dict(l=40,r=40,t=45,b=60), paper_bgcolor="white",
        plot_bgcolor="white", font=dict(family="Inter", size=10, color=DARK_TEXT))
    for ax in ["yaxis","yaxis2"]:
        fig.update_layout(**{ax: dict(showgrid=True, gridcolor="#eee", zeroline=True, zerolinecolor="#ccc")})
    fig.update_xaxes(tickangle=0, tickfont=dict(size=11, family="Inter", color=DARK_TEXT))
    fig.update_yaxes(title_text="Margin (%)", row=1, col=1, ticksuffix="%", title_font=dict(size=10))
    fig.update_yaxes(title_text=ccy, row=1, col=2, title_font=dict(size=10))
    return fig


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
        title=dict(text=f"Sensitivity: Operating Margin vs. {param_label}", font=dict(size=12, family="Inter")),
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
            ws.merge_range(1,0,1,n,f"{inputs['currency']} | Destination: {inputs['destination']}",sf)
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
def export_pdf_project(all_results, ccy, project_name):
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    navy_r, navy_g, navy_b = 0, 32, 96
    white_r, white_g, white_b = 255, 255, 255
    grey_r, grey_g, grey_b = 108, 117, 125
    dark_r, dark_g, dark_b = 26, 26, 46
    base_bg_r, base_bg_g, base_bg_b = 242, 242, 242

    def add_header(pdf, title, subtitle=""):
        pdf.set_fill_color(navy_r, navy_g, navy_b)
        pdf.set_text_color(white_r, white_g, white_b)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, title, ln=True, fill=True)
        if subtitle:
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, subtitle, ln=True, fill=True)
        pdf.set_text_color(dark_r, dark_g, dark_b)
        pdf.ln(4)

    def add_table(pdf, headers, rows, col_widths, bold_rows=None, base_col=0):
        bold_rows = bold_rows or []
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(navy_r, navy_g, navy_b)
        pdf.set_text_color(white_r, white_g, white_b)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 6, h, border=1, align="L" if i == 0 else "C", fill=True)
        pdf.ln()
        pdf.set_text_color(dark_r, dark_g, dark_b)
        for ri, row in enumerate(rows):
            is_bold = ri in bold_rows
            pdf.set_font("Helvetica", "B" if is_bold else "", 7)
            for ci, val in enumerate(row):
                if ci == base_col and ci > 0:
                    pdf.set_fill_color(base_bg_r, base_bg_g, base_bg_b)
                    pdf.cell(col_widths[ci], 5, str(val), border=0, align="L" if ci == 0 else "C", fill=True)
                elif ci == 1:
                    pdf.set_fill_color(base_bg_r, base_bg_g, base_bg_b)
                    pdf.cell(col_widths[ci], 5, str(val), border=0, align="C", fill=True)
                else:
                    pdf.cell(col_widths[ci], 5, str(val), border=0, align="L" if ci == 0 else "C")
            pdf.ln()

    for item in all_results:
        pdf.add_page()
        inp = item["inputs"]
        results = item["results"]
        add_header(pdf, f"{inp['item_number']} - {inp['designation']}", f"{ccy} | Destination: {inp.get('destination','')}")

        n = len(results)
        lw = 50
        cw = int((297 - 20 - lw) / n) if n else 40
        col_widths = [lw] + [cw] * n
        headers = [f"Per Unit ({ccy})"] + [r["name"] for r in results]

        f2 = lambda v: f"{v:,.2f}" if v is not None else "-"
        fp_ = lambda v: f"{v*100:.1f}%" if v is not None else "-"
        fi_ = lambda v: f"{v:,.0f}" if v is not None else "-"

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
        add_table(pdf, headers, cost_rows, col_widths, bold_rows=[3,7,13,14,15])

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
        add_table(pdf, annual_headers, annual_rows, col_widths, bold_rows=[2,3,4])

    # Portfolio summary page
    if len(all_results) > 1:
        pdf.add_page()
        add_header(pdf, "Portfolio Summary", f"{ccy} | {project_name}")
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
        lw = 60
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
        add_table(pdf, headers, rows, col_widths, bold_rows=[len(all_results), len(all_results)+1, len(all_results)+2])

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
def render_portfolio_summary(all_results, ccy):
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
            title=dict(text=f"Total Annual OP by Location ({ccy})", font=dict(size=12, family="Inter")),
            height=400, margin=dict(l=40,r=40,t=50,b=60),
            paper_bgcolor="white", plot_bgcolor="white",
            font=dict(family="Inter", size=10, color=DARK_TEXT),
            yaxis=dict(showgrid=True, gridcolor="#eee"),
        )
        fig.update_xaxes(tickangle=0, tickfont=dict(size=11, family="Inter", color=DARK_TEXT))
        fig.update_yaxes(title_text=ccy, title_font=dict(size=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


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

    st.markdown("""<div class="ib-header" style="position:relative;"><h1>Landed Cost Comparison Model</h1>
        <div class="sub">Multi-Item Project-Based Production Cost & Profitability Analysis &middot; v5.0</div></div>""", unsafe_allow_html=True)

    with st.expander("About this model", expanded=False):
        st.markdown(f"""
<div style="font-family:Inter,sans-serif;font-size:0.82rem;color:{DARK_TEXT};line-height:1.7;">

<strong style="font-size:0.9rem;">Purpose</strong><br>
The Landed Cost Comparison Model enables strategic evaluation of manufacturing location alternatives.
It compares the full cost-to-serve across multiple production sites, accounting for material costs,
value-added processing, tariffs, duties, transportation, and selling & administrative expenses.
The model calculates operating profit and margin impact at both per-unit and full-year levels.

<br><br><strong style="font-size:0.9rem;">Methodology</strong><br>
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

<br><strong style="font-size:0.9rem;">How to Use</strong><br>
<strong>1.</strong> Configure shared factory assumptions in the matrix (applies to all items)<br>
<strong>2.</strong> Add items using the Item tabs &mdash; enter item details, net sales, and base costs<br>
<strong>3.</strong> Optionally override specific costs per factory in the Cost Overrides grid<br>
<strong>4.</strong> Review results: KPI cards, per-unit tables, full-year impact, and charts<br>
<strong>5.</strong> Use the Portfolio Summary tab to compare across all items<br>
<strong>6.</strong> Export to Excel or PDF for distribution<br>
<strong>7.</strong> Save/Load projects as JSON to resume later

<br><br><strong style="font-size:0.9rem;">Changelog</strong><br>
<span style="color:{GREY_TEXT};">v5.0</span> &mdash; Extracted core logic into testable library modules; added sensitivity analysis; expanded lead-time matrix with region-based fallback estimation; added input validation; added 48 unit tests<br>
<span style="color:{GREY_TEXT};">v4.5</span> &mdash; Fixed CSS class prefix: .st-key- (hyphen) not .stkey_ (underscore); blue input borders now render correctly<br>
<span style="color:{GREY_TEXT};">v4.4</span> &mdash; Key-based CSS targeting (.stkey_) for blue input borders; selective styling of editable vs read-only editors<br>
<span style="color:{GREY_TEXT};">v4.3</span> &mdash; Fixed blue input border rendering (global CSS targeting stDataEditor)<br>
<span style="color:{GREY_TEXT};">v4.2</span> &mdash; IB blue input formatting concept, color legend<br>
<span style="color:{GREY_TEXT};">v4.1</span> &mdash; Lead time comparison by country pair, factory country assignment<br>
<span style="color:{GREY_TEXT};">v4.0</span> &mdash; Multi-item project mode, portfolio summary, PDF export, save/load projects<br>
<span style="color:{GREY_TEXT};">v3.0</span> &mdash; Cost overrides per factory, base factory naming<br>
<span style="color:{GREY_TEXT};">v2.0</span> &mdash; Matrix input UX, sequential flow, IB styling overhaul<br>
<span style="color:{GREY_TEXT};">v1.0</span> &mdash; Initial release with core cost comparison engine

<br><br><strong style="font-size:0.9rem;">Contact</strong><br>
For questions, feedback, or feature requests:<br>
<strong>Jonas Henriksson</strong> &mdash; Head of Strategic Planning & Intelligent Hub<br>
<a href="mailto:jonas.henriksson@skf.com" style="color:{ACCENT_BLUE};text-decoration:none;">jonas.henriksson@skf.com</a>

</div>
""", unsafe_allow_html=True)

    st.markdown(f'<div class="callout" style="font-size:0.72rem;"><span style="border-left:3px solid {INPUT_BLUE};padding-left:0.35rem;font-weight:600;color:{INPUT_BLUE};">Blue border</span> = editable input fields &nbsp;&middot;&nbsp; <span style="font-weight:600;color:{DARK_TEXT};">Output tables</span> = calculated results (read-only) &nbsp;&middot;&nbsp; <span style="color:{GREY_TEXT};font-style:italic;">Grey italic</span> = guidance notes</div>', unsafe_allow_html=True)

    ex = st.checkbox("Load example data", value=st.session_state.ex)
    st.session_state.ex = ex

    # ── PROJECT HEADER ────────────────────────────────────────
    st.markdown('<div class="sec">Project Setup</div>', unsafe_allow_html=True)

    pc1, pc2, pc3, pc4, pc5 = st.columns([2, 1, 1, 1, 2])
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

    with pc5:
        sc1, sc2 = st.columns(2)
        with sc1:
            save_data = save_project_json()
            st.download_button("Save Project", data=save_data,
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
    st.markdown('<div class="sec">Shared Factory Configuration</div>', unsafe_allow_html=True)

    fc_data = {"Comparison Factories": [4 if ex else st.session_state.get("num_fac", 2)]}
    fc_df = pd.DataFrame(fc_data)
    edited_fc = st.data_editor(
        fc_df, use_container_width=False, num_rows="fixed", key="fc_editor", hide_index=True,
        column_config={"Comparison Factories": st.column_config.NumberColumn(
            "Comparison Factories", min_value=1, max_value=6, step=1, format="%d", width=180)})
    num_factories = max(1, min(6, int(edited_fc.loc[0, "Comparison Factories"])))
    st.session_state["num_fac"] = num_factories

    # Base factory name
    bf_df = pd.DataFrame({"Base Factory Name": [EX_BASE.name if ex else "Base Case"]})
    edited_bf = st.data_editor(bf_df, use_container_width=False, num_rows="fixed",
        key="bf_editor", hide_index=True,
        column_config={"Base Factory Name": st.column_config.TextColumn("Base Factory Name", width=250)})
    base_factory_name = str(edited_bf.loc[0, "Base Factory Name"] or "Base Case")

    # Factory country assignment
    st.markdown('<div class="sec-sm">Factory Locations</div>', unsafe_allow_html=True)
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

    st.markdown('<div class="sec-sm">Assumptions Matrix</div>', unsafe_allow_html=True)
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
        st.markdown(f'<div class="sec-sm">Lead Time to {target_market}</div>', unsafe_allow_html=True)
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
        days_cells = "".join(f'<td class="{"base-case" if i==0 else ""}">{r["Transit Days"] if r["Transit Days"] is not None else "\u2013"}</td>' for i, r in enumerate(lt_data))
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
    st.markdown('<div class="sec">Item Analysis</div>', unsafe_allow_html=True)

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

                results = []
                br = compute_location(inputs, base, is_base=True)
                if br: results.append(br)
                for f in factories:
                    if f.name:
                        ov = get_ov(f.name)
                        r = compute_location(inputs, f, overrides=ov)
                        if r: results.append(r)

                if results:
                    # Executive summary KPIs
                    bom = results[0]["om"]
                    ranked = sorted(results[1:], key=lambda r: r["om"], reverse=True)
                    labels = ["Best Location", "2nd Best", "3rd Best"]
                    ncards = min(len(ranked), 3) + 1
                    cols = st.columns(ncards)
                    cols[0].markdown(f'<div style="background:{BASE_CASE_BG};border:1px solid {BORDER};border-radius:2px;padding:0.8rem 1rem;text-align:center;"><div style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.2rem;">Base Case OM</div><div style="font-size:1.15rem;font-weight:700;color:{DARK_TEXT};">{fp(bom,1,dz=False)}</div><div style="font-size:0.82rem;font-weight:600;color:{DARK_TEXT};margin-top:0.15rem;">{results[0]["name"]}</div></div>', unsafe_allow_html=True)
                    for i, r in enumerate(ranked[:3]):
                        delta_pp = (r["om"] - bom) * 100
                        is_better = delta_pp > 0.05
                        is_worse = delta_pp < -0.05
                        bdr = f"border-left:3px solid {GREEN};" if is_better else (f"border-left:3px solid {RED};" if is_worse else f"border-left:3px solid {BORDER};")
                        d_sign = "+" if delta_pp > 0 else ""
                        d_cls = f"color:{GREEN};font-weight:600;" if is_better else (f"color:{RED};font-weight:600;" if is_worse else f"color:{MUTED};")
                        cols[i+1].markdown(f'<div style="background:#fafafa;border:1px solid {BORDER};{bdr}border-radius:2px;padding:0.8rem 1rem;text-align:center;"><div style="font-size:0.65rem;color:{GREY_TEXT};text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-bottom:0.2rem;">{labels[i]}</div><div style="font-size:1.15rem;font-weight:700;color:{DARK_TEXT};">{fp(r["om"],1,dz=False)}</div><div style="font-size:0.82rem;font-weight:600;color:{DARK_TEXT};margin-top:0.15rem;">{r["name"]}</div><div style="font-size:0.7rem;{d_cls}margin-top:0.15rem;">{d_sign}{delta_pp:.1f}pp vs base</div></div>', unsafe_allow_html=True)

                    st.markdown(f'<div class="sec-sm">Per Unit Cost Comparison ({currency})</div>', unsafe_allow_html=True)
                    st.markdown(build_cost_table(results, currency, target_market), unsafe_allow_html=True)

                    st.markdown(f'<div class="sec-sm">Full Year Impact ({currency})</div>', unsafe_allow_html=True)
                    st.markdown(build_annual_table(results, currency), unsafe_allow_html=True)

                    if len(results) >= 2:
                        st.plotly_chart(build_charts(results, currency), use_container_width=True, config={"displayModeBar": False})

                    # Sensitivity analysis
                    with st.expander("Sensitivity Analysis", expanded=False):
                        st.markdown(f'<div class="callout">Explore how changes in a single parameter affect operating margin across all factories.</div>', unsafe_allow_html=True)
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

                        # Build sensible default range based on current values
                        if param_key in ("va_ratio",):
                            steps = [round(v, 2) for v in np.arange(0.4, 1.61, 0.1)]
                        elif is_pct:
                            steps = [round(v, 3) for v in np.arange(0.0, 0.121, 0.01)]
                        else:
                            # Material cost: +-50% around current
                            base_val = getattr(inputs, param_key, 20.0) or 20.0
                            steps = [round(base_val * m, 2) for m in np.arange(0.5, 1.55, 0.1)]

                        fig_sa = build_sensitivity_chart(
                            inputs, factories, base, param_key, sa_choice, steps, currency, is_pct=is_pct
                        )
                        st.plotly_chart(fig_sa, use_container_width=True, config={"displayModeBar": False})

                    all_results.append({
                        "inputs": {"item_number": inputs.item_number, "designation": inputs.designation,
                                   "currency": currency, "destination": inputs.destination},
                        "results": results,
                    })

    # Portfolio Summary tab
    with tabs[-1]:
        render_portfolio_summary(all_results, currency)

    # ── FOOTER ────────────────────────────────────────────────
    st.markdown("---")
    c1,c2,c3 = st.columns([4,1,1])
    c1.markdown(f"<span style='font-size:0.7rem;color:{MUTED};'>Landed Cost Comparison v5.0 &middot; {st.session_state.project_name} &middot; {len(st.session_state.project_items)} items &middot; {currency} &middot; Market: {target_market}</span>", unsafe_allow_html=True)
    if all_results:
        c2.download_button("Export Excel", data=export_excel_project(all_results),
            file_name=f"Landed_Cost_{st.session_state.project_name.replace(' ','_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        c3.download_button("Export PDF", data=export_pdf_project(all_results, currency, st.session_state.project_name),
            file_name=f"Landed_Cost_{st.session_state.project_name.replace(' ','_')}.pdf",
            mime="application/pdf")


if __name__ == "__main__":
    main()
