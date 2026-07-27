"""
============================================================================
 The Purple Cup - Marketing Analytics Dashboard
============================================================================
 SIMULATED / SYNTHETIC DATA - PORTFOLIO PROJECT.
 The Purple Cup is a fictional specialty-drink brand. All data shown here is
 synthetic, generated for demonstration. The analytical work is real.
 Author: Erica Mathias
----------------------------------------------------------------------------
 This dashboard reads data/brewmetrics.db and reuses the analysis modules
 from Phases 3-6 (funnel, attribution, A/B test, segmentation). It presents:
   - KPI cards: spend, revenue, blended ROAS, click-to-purchase conversion
   - the marketing funnel with drop-off
   - revenue by channel with a first/last/linear attribution selector
   - the email A/B test result with its significance verdict
   - RFM + k-means customer segments
============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

# Make the sibling analysis/ package importable, then reuse its logic so the
# dashboard never re-implements analysis that already exists.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import ab_test, attribution, funnel, segmentation  # noqa: E402

# ---------------------------------------------------------------------------
# PALETTE  (the whole brand identity in one place)
# ---------------------------------------------------------------------------
DEEP = "#3B0A5C"
VIOLET = "#5B21B6"
PURPLE = "#7A1FA2"
ACCENT = "#9333EA"
MAGENTA = "#C026D3"
INK = "#2C0645"

CARD_TINTS = ["#EEDCF9", "#E4D3F5", "#F3E0EF", "#EADCF7"]
FUNNEL_COLORS = [DEEP, VIOLET, ACCENT, MAGENTA]
CHANNEL_COLORS = {
    "Email": ACCENT,
    "Instagram": MAGENTA,
    "Paid Search": PURPLE,
    "Referral": VIOLET,
}
SEGMENT_COLORS = {
    "Champions": VIOLET,
    "Loyal": PURPLE,
    "At risk": MAGENTA,
    "New": ACCENT,
}

# ---------------------------------------------------------------------------
# SVG LINE ICONS  (simple, hand-drawn marks - no emoji anywhere)
# ---------------------------------------------------------------------------
CUP_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8z"/>
 <path d="M17 9h2.5a2.5 2.5 0 0 1 0 5H17"/><path d="M8 3c-.5 1 .5 1.5 0 2.5M12 3c-.5 1 .5 1.5 0 2.5"/></svg>"""
LEAF_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M5 19c0-8 6-13 14-14 1 9-4 15-12 15a6 6 0 0 1-2-1z"/>
 <path d="M5 19C8 14 12 11 17 9"/></svg>"""
COIN_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/>
 <path d="M12 8v8M9.5 9.5c0-1 1-1.5 2.5-1.5s2.5.5 2.5 1.5-1 1.3-2.5 1.5-2.5.5-2.5 1.5 1 1.5 2.5 1.5 2.5-.5 2.5-1.5"/></svg>"""
TREND_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M4 18l5-6 4 3 6-8"/><path d="M16 7h4v4"/></svg>"""
RETURN_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 1 3 6.2"/><path d="M4 20v-5h5"/></svg>"""
FUNNEL_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18l-7 8v6l-4 2v-8L3 5z"/></svg>"""

KPI_ICONS = [COIN_ICON, TREND_ICON, RETURN_ICON, FUNNEL_ICON]


# ---------------------------------------------------------------------------
# DATA  (compute everything once, cached; the app just renders the results)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Brewing the numbers...")
def load_data() -> dict:
    conn = funnel.get_connection()

    # --- headline KPIs ---
    spend = conn.execute("SELECT SUM(spend) FROM campaigns").fetchone()[0]
    impressions = conn.execute("SELECT SUM(impressions) FROM campaigns").fetchone()[0]
    counts = dict(conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type").fetchall())
    revenue = conn.execute("SELECT SUM(revenue) FROM events WHERE event_type='purchase'").fetchone()[0]
    clicks, purchases = counts.get("click", 0), counts.get("purchase", 0)

    # --- funnel + biggest leak + opportunity ---
    funnel_df = funnel.compute_funnel(conn)
    leak = funnel.identify_biggest_leak(funnel_df)
    opp = funnel.opportunity_scenario(conn, funnel_df, leak)

    # --- attribution (all three models) ---
    attr = attribution.attribute(attribution.load_events(conn))
    attr_table = attribution.comparison_table(conn, attr)

    # --- segmentation ---
    rfm, n_prospects, snapshot = segmentation.compute_rfm(conn)
    rfm = segmentation.label_clusters(segmentation.run_kmeans(rfm))
    seg_summary = segmentation.summarize(rfm).reset_index()

    conn.close()

    # --- A/B test (self-contained simulated experiment) ---
    exp = ab_test.run_experiment()
    ab = ab_test.two_proportion_ztest(exp["x_a"], exp["n_a"], exp["x_b"], exp["n_b"])
    ab.update(exp)

    return {
        "spend": spend, "revenue": revenue, "impressions": impressions,
        "clicks": clicks, "purchases": purchases,
        "roas": revenue / spend, "click_to_buy": purchases / clicks,
        "funnel": funnel_df, "leak": leak, "opp": opp,
        "attr_table": attr_table, "attr_stats": attr,
        "rfm": rfm, "seg_summary": seg_summary,
        "n_prospects": n_prospects, "snapshot": snapshot,
        "ab": ab,
    }


# ---------------------------------------------------------------------------
# STYLING
# ---------------------------------------------------------------------------
st.set_page_config(page_title="The Purple Cup - Marketing Analytics",
                   layout="wide", initial_sidebar_state="collapsed")

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1200px; }
#MainMenu, header, footer { visibility: hidden; }

/* gradient header banner */
.pc-header {
  background: linear-gradient(120deg, #3B0A5C 0%, #7A1FA2 55%, #C026D3 100%);
  border-radius: 22px; padding: 30px 36px; color: #fff; margin-bottom: 26px;
  box-shadow: 0 12px 30px rgba(59,10,92,.22);
}
.pc-header .mark { display:flex; align-items:center; gap:14px; }
.pc-header .mark svg { width: 40px; height: 40px; color:#F3E0EF; }
.pc-wordmark { font-family:'Fraunces',serif; font-weight:600; font-size:40px; letter-spacing:.3px; line-height:1; }
.pc-tag { margin-top:10px; font-size:12.5px; letter-spacing:2.4px; text-transform:uppercase; color:#F0D9FA; }
.pc-sub { margin-top:2px; font-size:14px; color:#EADCF7; opacity:.92; }

/* KPI cards */
.kpi { border:1px solid rgba(123,31,162,.16); border-radius:18px; padding:18px 20px 16px;
  position:relative; height:100%; }
.kpi-icon { position:absolute; top:16px; right:16px; width:26px; height:26px; color:#7A1FA2; opacity:.75; }
.kpi-label { font-size:11.5px; letter-spacing:1.3px; text-transform:uppercase; color:#6B3A8E; font-weight:600; }
.kpi-value { font-family:'Fraunces',serif; font-size:33px; font-weight:600; color:#2C0645; margin-top:6px; line-height:1; }
.kpi-sub { font-size:12.5px; color:#7A5A93; margin-top:7px; }

/* section titles */
.pc-section { display:flex; align-items:center; gap:10px; margin:14px 0 4px; }
.pc-section svg { width:22px; height:22px; color:#9333EA; }
.pc-section h3 { font-family:'Fraunces',serif; font-weight:600; color:#3B0A5C; font-size:22px; margin:0; }
.pc-note { font-size:13.5px; color:#5b3a72; margin:2px 0 10px; }

/* insight + a/b cards */
.pc-insight { background:#F7EEFD; border-left:4px solid #9333EA; border-radius:10px;
  padding:12px 16px; font-size:14px; color:#3B0A5C; margin-top:6px; }
.ab-metric { border:1px solid rgba(123,31,162,.16); border-radius:16px; padding:16px 18px; text-align:center; }
.ab-metric .lab { font-size:12px; letter-spacing:.6px; color:#6B3A8E; text-transform:uppercase; }
.ab-metric .val { font-family:'Fraunces',serif; font-size:30px; color:#2C0645; margin-top:4px; }
.pill { display:inline-block; padding:7px 16px; border-radius:999px; font-weight:600; font-size:14px;
  background:#5B21B6; color:#fff; letter-spacing:.3px; }
.pill.warn { background:#B08AD1; }
.pc-foot { margin-top:34px; padding-top:14px; border-top:1px solid #EADCF7; font-size:12.5px; color:#8A6AA6; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor="#EFE3FA", zeroline=False)
    fig.update_yaxes(gridcolor="#EFE3FA", zeroline=False)
    return fig


def section(icon: str, title: str) -> None:
    st.markdown(f'<div class="pc-section">{icon}<h3>{title}</h3></div>', unsafe_allow_html=True)


# ===========================================================================
# RENDER
# ===========================================================================
d = load_data()

# --- header ----------------------------------------------------------------
st.markdown(f"""
<div class="pc-header">
  <div class="mark">{CUP_ICON}{LEAF_ICON}
    <span class="pc-wordmark">The Purple Cup</span>
  </div>
  <div class="pc-tag">simulated data &middot; portfolio project</div>
  <div class="pc-sub">Marketing analytics for a fictional small-batch matcha, ube &amp; coffee brand</div>
</div>
""", unsafe_allow_html=True)

# --- KPI row ---------------------------------------------------------------
kpis = [
    ("Ad spend", f"${d['spend']:,.0f}", "across 5 campaigns, 6 months"),
    ("Revenue", f"${d['revenue']:,.0f}", f"{d['purchases']:,} purchases"),
    ("Blended ROAS", f"{d['roas']:.2f}x", f"${d['roas']:.2f} back per $1 spent"),
    ("Click to purchase", f"{d['click_to_buy']:.1%}", f"{d['clicks']:,} clicks converted"),
]
cols = st.columns(4)
for col, (label, value, sub), tint, icon in zip(cols, kpis, CARD_TINTS, KPI_ICONS):
    col.markdown(f"""
    <div class="kpi" style="background:{tint};">
      <div class="kpi-icon">{icon}</div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

st.write("")

# --- funnel + attribution (two-up) -----------------------------------------
left, right = st.columns([1, 1], gap="large")

with left:
    section(FUNNEL_ICON, "The marketing funnel")
    f = d["funnel"]
    fig = go.Figure(go.Funnel(
        y=f["stage"], x=f["count"],
        textposition="inside", textinfo="value+percent previous",
        marker=dict(color=FUNNEL_COLORS),
        connector=dict(line=dict(color="#E4D3F5", width=1)),
    ))
    st.plotly_chart(style_fig(fig, 360), width='stretch', config={"displayModeBar": False})
    leak, opp = d["leak"], d["opp"]
    st.markdown(f"""<div class="pc-insight">
      <b>Biggest fixable leak:</b> {leak['fixable_step']} loses {leak['fixable_drop_pct']:.0f}% of the prior stage.
      Lifting it {opp['uplift_points']:.0f} points is worth about
      <b>${opp['extra_revenue']:,.0f}</b> in added revenue.</div>""", unsafe_allow_html=True)

with right:
    section(RETURN_ICON, "Revenue by channel")
    model = st.radio("Attribution model", ["Last touch", "First touch", "Linear"],
                     horizontal=True, label_visibility="collapsed")
    col_key = {"First touch": "first_touch", "Last touch": "last_touch", "Linear": "linear"}[model]
    t = d["attr_table"].sort_values(f"{col_key}_rev", ascending=True)
    fig = go.Figure(go.Bar(
        x=t[f"{col_key}_rev"], y=t["channel"], orientation="h",
        marker=dict(color=[CHANNEL_COLORS[c] for c in t["channel"]]),
        text=[f"${v:,.0f}" for v in t[f"{col_key}_rev"]], textposition="outside",
        cliponaxis=False,
    ))
    fig.update_xaxes(title_text=f"Revenue credited ({model.lower()})")
    st.plotly_chart(style_fig(fig, 300), width='stretch', config={"displayModeBar": False})
    stats = d["attr_stats"]
    st.markdown(f"""<div class="pc-insight">
      {stats['n_cross_channel']/stats['n_conversions']:.0%} of purchases were cross-channel journeys.
      Flip between <b>last</b> and <b>first</b> touch to watch <b>Instagram</b> jump - it starts journeys
      it rarely closes, so the ad-platform default undervalues it.</div>""", unsafe_allow_html=True)

st.write("")

# --- A/B test --------------------------------------------------------------
section(LEAF_ICON, "Email A/B test - subject line")
ab = d["ab"]
significant = ab["p_value"] < 0.05
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
c1.markdown(f'<div class="ab-metric"><div class="lab">Variant A rate</div>'
            f'<div class="val">{ab["p_a"]:.2%}</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="ab-metric"><div class="lab">Variant B rate</div>'
            f'<div class="val">{ab["p_b"]:.2%}</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="ab-metric"><div class="lab">Relative lift</div>'
            f'<div class="val">{ab["rel_lift"]:+.0%}</div></div>', unsafe_allow_html=True)
pill = "pill" if significant else "pill warn"
verdict = "Significant at 95%" if significant else "Not significant"
c4.markdown(f"""<div class="ab-metric">
  <div class="lab">Two-proportion z-test</div>
  <div style="margin-top:8px;"><span class="{pill}">{verdict}</span></div>
  <div style="font-size:12.5px;color:#7A5A93;margin-top:8px;">p = {ab['p_value']:.4f} &nbsp;|&nbsp; z = {ab['z']:.2f}</div>
</div>""", unsafe_allow_html=True)
st.markdown(f"""<div class="pc-insight">
  Variant B (&ldquo;A little purple surprise inside&rdquo;) lifted conversion from {ab['p_a']:.1%} to {ab['p_b']:.1%},
  a {ab['rel_lift']:.0%} relative increase (p = {ab['p_value']:.3f}). The 95% CI for the lift is
  [{ab['ci_low']*100:+.2f}, {ab['ci_high']*100:+.2f}] points - real, though the low end is modest.</div>""",
  unsafe_allow_html=True)

st.write("")

# --- segments (two-up) -----------------------------------------------------
left2, right2 = st.columns([1, 1], gap="large")
seg = d["seg_summary"]

with left2:
    section(COIN_ICON, "Customer value by segment")
    fig = go.Figure(go.Bar(
        x=seg["segment"], y=seg["total_revenue"],
        marker=dict(color=[SEGMENT_COLORS[s] for s in seg["segment"]]),
        text=[f"${v:,.0f}<br>{n:,} buyers" for v, n in zip(seg["total_revenue"], seg["customers"])],
        textposition="outside", cliponaxis=False,
    ))
    fig.update_yaxes(title_text="Total revenue")
    st.plotly_chart(style_fig(fig, 330), width='stretch', config={"displayModeBar": False})
    champ = seg[seg["segment"] == "Champions"].iloc[0]
    st.markdown(f"""<div class="pc-insight">
      <b>Champions</b> are {champ['pct_of_customers']:.0f}% of buyers but
      {champ['pct_of_revenue']:.0f}% of revenue. <b>At risk</b> customers went quiet ~4 months ago -
      the highest-ROI win-back target.</div>""", unsafe_allow_html=True)

with right2:
    section(LEAF_ICON, "How the segments cluster (RFM)")
    rfm = d["rfm"]
    fig = go.Figure()
    for s in ["Champions", "Loyal", "At risk", "New"]:
        part = rfm[rfm["segment"] == s]
        fig.add_trace(go.Scatter(
            x=part["recency"], y=part["monetary"], mode="markers", name=s,
            marker=dict(color=SEGMENT_COLORS[s], size=6, opacity=0.55,
                        line=dict(width=0)),
        ))
    fig.update_xaxes(title_text="Recency (days since last order)")
    fig.update_yaxes(title_text="Monetary (total spend $)")
    st.plotly_chart(style_fig(fig, 330), width='stretch', config={"displayModeBar": False})
    st.markdown(f"""<div class="pc-insight">
      Each dot is one of {len(rfm):,} purchasing customers; {d['n_prospects']:,} never-purchased prospects
      are held out. k-means grouped these by similarity - notice At risk drifting right (gone quiet).</div>""",
      unsafe_allow_html=True)

# --- footer ----------------------------------------------------------------
st.markdown(f"""<div class="pc-foot">
  <b>The Purple Cup</b> is a fictional brand and every figure here is simulated data built for a portfolio
  project - it is not real customer data. Analysis: SQL, funnel &amp; conversion, first/last/linear attribution,
  a two-proportion z-test, and RFM + k-means segmentation. Recency snapshot: {d['snapshot']}.
  Built by Erica Mathias.</div>""", unsafe_allow_html=True)
