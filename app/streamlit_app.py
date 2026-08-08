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
   - a scroll-reactive hero (the cup drains as you read down the page)
   - KPI cards: spend, revenue, blended ROAS, click-to-purchase conversion
   - the marketing funnel with drop-off
   - revenue by channel with a first/last/linear attribution selector
   - the email A/B test result with its significance verdict
   - RFM + k-means customer segments

 The look is an editorial cafe menu: warm paper, torn-paper section edges,
 a Fraunces display serif, and plum/mocha ink. Everything scroll-driven is
 handled by one small engine injected at the bottom of the file.
============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Make the sibling analysis/ package importable, then reuse its logic so the
# dashboard never re-implements analysis that already exists.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import ab_test, attribution, funnel, segmentation  # noqa: E402

# ---------------------------------------------------------------------------
# PALETTE  (the whole brand identity in one place)
# ---------------------------------------------------------------------------
INK = "#2A1026"        # deep plum-espresso, all body ink
PLUM = "#4B1B4E"
GRAPE = "#6E2E7C"
ORCHID = "#9A4FAF"
BLOSSOM = "#C77CC0"
CARAMEL = "#C98B54"

CARD_TINTS = ["#F5DFE5", "#EADDF5", "#F6E8D6", "#E7E0F2"]
CARD_BARS = [BLOSSOM, ORCHID, CARAMEL, GRAPE]
FUNNEL_GRADS = [(PLUM, GRAPE), (GRAPE, ORCHID), (ORCHID, BLOSSOM), (BLOSSOM, CARAMEL)]
CHANNEL_COLORS = {
    "Email": ORCHID,
    "Instagram": BLOSSOM,
    "Paid Search": GRAPE,
    "Referral": CARAMEL,
}
SEGMENT_COLORS = {
    "Champions": PLUM,
    "Loyal": ORCHID,
    "At risk": CARAMEL,
    "New": BLOSSOM,
}

# ---------------------------------------------------------------------------
# SVG LINE ICONS  (simple, hand-drawn marks - no emoji anywhere)
# ---------------------------------------------------------------------------
CUP_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8z"/>
 <path d="M17 9h2.5a2.5 2.5 0 0 1 0 5H17"/><path d="M8 3c-.5 1 .5 1.5 0 2.5M12 3c-.5 1 .5 1.5 0 2.5"/></svg>"""
COIN_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/>
 <path d="M12 8v8M9.5 9.5c0-1 1-1.5 2.5-1.5s2.5.5 2.5 1.5-1 1.3-2.5 1.5-2.5.5-2.5 1.5 1 1.5 2.5 1.5 2.5-.5 2.5-1.5"/></svg>"""
TREND_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M4 18l5-6 4 3 6-8"/><path d="M16 7h4v4"/></svg>"""
RETURN_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 1 3 6.2"/><path d="M4 20v-5h5"/></svg>"""
FUNNEL_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M3 5h18l-7 8v6l-4 2v-8L3 5z"/></svg>"""
BEAN_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="12" rx="9" ry="6"
 transform="rotate(-30 12 12)"/><path d="M6.8 15.6C9 13 12 12 17.2 8.4"/></svg>"""
FLASK_ICON = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
 stroke-linecap="round" stroke-linejoin="round"><path d="M10 3h4M11 3v6.2L5.4 18A2 2 0 0 0 7.1 21h9.8a2 2 0 0 0 1.7-3L13 9.2V3"/>
 <path d="M8 16h8"/></svg>"""

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
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,600;1,9..144,400;1,9..144,500&family=Inter:wght@400;500;600;700&display=swap');

:root{
  --ink:#2A1026; --plum:#4B1B4E; --grape:#6E2E7C; --orchid:#9A4FAF; --blossom:#C77CC0;
  --mocha:#8A6470; --mocha-d:#5E3F4B; --caramel:#C98B54;
  --cream:#FAF3E9; --paper:#FDF9F2; --blush:#F5DFE5; --lilac:#EADDF5; --sand:#F6E8D6;
  --muted:#8B6C86; --line:rgba(74,27,78,.10);
  --serif:'Fraunces', Georgia, serif; --sans:'Inter', system-ui, sans-serif;
}

html, body, [class*="css"] { font-family: var(--sans); }

/* Streamlit ships its own rules for bare h1-h4 inside markdown, and they beat a
   plain class selector - so every heading we draw is re-declared at a higher
   specificity here. Nothing below is decorative duplication; remove it and the
   display type silently falls back to Source Sans. */
[data-testid="stMarkdownContainer"] h1.pc-display,
[data-testid="stMarkdownContainer"] .pc-sec h2,
[data-testid="stMarkdownContainer"] .pc-mini h3,
[data-testid="stMarkdownContainer"] .pc-footer h4{
  font-family:var(--serif); padding:0; margin:0;
}
[data-testid="stMarkdownContainer"] h1.pc-display{
  font-weight:500; color:#FFF8F3; font-size:clamp(46px, 6.2vw, 88px); line-height:.94;
  letter-spacing:-.022em; margin:20px 0 0; text-shadow:0 14px 34px rgba(42,16,38,.28);
}
[data-testid="stMarkdownContainer"] .pc-sec h2{
  font-weight:500; font-size:clamp(28px, 3.4vw, 42px); line-height:1.06;
  letter-spacing:-.015em; color:var(--plum);
}
[data-testid="stMarkdownContainer"] .pc-mini h3{
  font-weight:500; font-size:20px; color:var(--plum); letter-spacing:-.01em;
}
[data-testid="stMarkdownContainer"] .pc-footer h4{
  font-weight:500; font-size:30px; color:#FFF5EE; margin:0 0 14px; letter-spacing:-.01em;
}

/* ---------- page canvas: warm paper with soft mocha + plum glows ---------- */
.stApp{
  background:
    radial-gradient(760px 560px at 6% 2%, rgba(201,139,84,.14) 0%, rgba(201,139,84,0) 58%),
    radial-gradient(820px 600px at 100% 8%, rgba(154,79,175,.13) 0%, rgba(154,79,175,0) 58%),
    radial-gradient(900px 700px at 88% 100%, rgba(138,100,112,.16) 0%, rgba(138,100,112,0) 62%),
    linear-gradient(180deg,#FDF8F1 0%, #FAF2EA 46%, #F6EFF6 100%);
  background-attachment: fixed;
  overflow-x: hidden;
}
[data-testid="stMain"], section.main{ overflow-x: hidden; }

/* paper grain */
.stApp::before{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.045;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

.block-container{ position:relative; z-index:1; padding-top:0 !important; padding-bottom:0 !important;
  max-width:1200px; }
/* the page composes its own vertical rhythm, so drop Streamlit's top-level gap
   and the -1rem markdown compensation that would otherwise overlap our bands */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"]{ gap:0 !important; }
[data-testid="stMarkdownContainer"]{ margin-bottom:0 !important; }

/* full-bleed bands. --vw is the scroller's width (set by the engine); the 100vw
   fallback includes the scrollbar and would overflow by a few pixels. */
.pc-hero, .pc-marquee, .pc-footer{
  width:var(--vw, 100vw);
  margin-left:calc(50% - var(--vw, 100vw) / 2);
  margin-right:calc(50% - var(--vw, 100vw) / 2);
}
#MainMenu, header, footer { visibility: hidden; }
[data-testid="stHeader"]{ display:none; }

/* ============================ TOP NAV ============================ */
.pc-nav{
  position:fixed; top:0; left:0; right:0; z-index:60; height:66px;
  display:flex; align-items:center; justify-content:center;
  transition: background .45s ease, box-shadow .45s ease, height .35s ease,
              backdrop-filter .4s ease, color .16s ease;
}
/* while the bar is transparent it floats over hero artwork, so it carries its
   own scrim - without it the wordmark collides with the hero stat strip */
.pc-nav::before{ content:""; position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(180deg, rgba(48,24,42,.42) 0%, rgba(48,24,42,0) 100%);
  transition:opacity .45s ease; }
.pc-nav.solid::before{ opacity:0; }
.pc-nav .wrap{ position:relative; width:min(1200px, calc(100% - 48px)); display:flex;
  align-items:center; gap:26px; }
.pc-nav .brand{ display:flex; align-items:center; gap:10px; margin-right:auto; }
.pc-nav .brand svg{ width:24px; height:24px; }
.pc-nav .brand b{ font-family:var(--serif); font-weight:600; font-size:21px; letter-spacing:.2px; }
.pc-nav .links{ display:flex; gap:26px; }
/* ink flips faster than the bar fades in, so the labels never sit light-on-light */
.pc-nav .brand b{ transition:color .16s ease; }
.pc-nav a{ font-size:13px; font-weight:500; letter-spacing:.2px; cursor:pointer; opacity:.82;
  position:relative; padding:4px 0; text-decoration:none !important;
  transition:opacity .2s ease, color .16s ease; }
.pc-nav a::after{ content:""; position:absolute; left:0; right:100%; bottom:0; height:1.5px;
  background:currentColor; transition:right .28s cubic-bezier(.22,.8,.25,1); }
.pc-nav a:hover{ opacity:1; } .pc-nav a:hover::after{ right:0; }
.pc-nav a.on{ opacity:1; } .pc-nav a.on::after{ right:0; }
/* over the hero: light ink */
.pc-nav, .pc-nav a, .pc-nav .brand b{ color:#FCF3EC; }
/* after scrolling past the hero: paper bar, dark ink */
.pc-nav.solid{ height:58px; background:rgba(253,248,241,.82); backdrop-filter:blur(14px) saturate(1.2);
  box-shadow:0 1px 0 rgba(74,27,78,.09), 0 12px 30px rgba(74,27,78,.07); }
.pc-nav.solid, .pc-nav.solid a, .pc-nav.solid .brand b{ color:var(--plum); }
.pc-nav .cta{ border:1px solid currentColor; border-radius:999px; padding:8px 16px; font-size:12px;
  letter-spacing:.6px; text-transform:uppercase; opacity:.9; }
.pc-nav .cta::after{ display:none; }
.pc-nav .cta:hover{ background:currentColor; }
.pc-nav .cta:hover span{ color:var(--cream); }
.pc-nav.solid .cta:hover span{ color:var(--paper); }
@media (max-width:860px){ .pc-nav .links, .pc-nav .cta{ display:none; } }

/* ============================ HERO ============================ */
.pc-hero{
  position:relative; min-height:min(94vh, 860px); padding:120px 0 130px; overflow:hidden;
  background:
    radial-gradient(110% 80% at 74% 26%, rgba(255,232,216,.34) 0%, rgba(255,232,216,0) 58%),
    radial-gradient(90% 70% at 6% 96%, rgba(58,26,52,.34) 0%, rgba(58,26,52,0) 62%),
    linear-gradient(152deg, #5B3A48 0%, #7E5665 34%, #A0757F 62%, #6D4361 100%);
  isolation:isolate;
}
.pc-hero::after{  /* soft vignette so the type stays crisp */
  content:""; position:absolute; inset:0; pointer-events:none;
  background:radial-gradient(90% 70% at 20% 40%, rgba(42,16,38,.28) 0%, rgba(42,16,38,0) 70%);
}
.pc-hero-inner{
  position:relative; z-index:2; width:min(1200px, calc(100% - 48px)); margin:0 auto;
  display:grid; grid-template-columns:minmax(0,1.02fr) minmax(0,.98fr); gap:34px; align-items:center;
}
.pc-eyebrow{ font-size:11px; letter-spacing:3.4px; text-transform:uppercase; color:#EFD5DF;
  display:flex; align-items:center; gap:12px; }
.pc-eyebrow::before{ content:""; width:34px; height:1px; background:currentColor; opacity:.7; }
.pc-display{
  font-family:var(--serif); font-weight:500; color:#FFF8F3; margin:20px 0 0;
  font-size:clamp(46px, 6.2vw, 88px); line-height:.94; letter-spacing:-.022em;
  text-shadow:0 14px 34px rgba(42,16,38,.28);
}
.pc-display em{ font-style:italic; font-weight:400; color:#F3D9E6;
  background:linear-gradient(100deg,#F6DCE8 0%, #E9CFEA 50%, #F7E3D2 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
/* the display face has a deep descender on the italic line - keep the lede clear of
   it. Container-prefixed because Streamlit's own `p` rule would win otherwise. */
[data-testid="stMarkdownContainer"] p.pc-lede{
  margin:44px 0 0; max-width:46ch; font-size:15.5px; line-height:1.68; color:#F3E2E4; opacity:.92;
}
.pc-hero-cta{ margin-top:30px; display:flex; align-items:center; gap:18px; flex-wrap:wrap; }
.pc-btn{
  appearance:none; border:0; cursor:pointer; font-family:var(--sans); font-size:12.5px; font-weight:600;
  letter-spacing:1.6px; text-transform:uppercase; color:#43162F;
  background:linear-gradient(135deg,#FFF3E6,#F6DCE6); padding:15px 30px; border-radius:999px;
  box-shadow:0 14px 30px rgba(42,16,38,.30); transition:transform .22s cubic-bezier(.22,.8,.25,1), box-shadow .22s ease;
}
.pc-btn:hover{ transform:translateY(-3px); box-shadow:0 20px 40px rgba(42,16,38,.36); }
.pc-by{ font-size:12.5px; color:#EBD6DC; letter-spacing:.4px; }
.pc-by b{ font-family:var(--serif); font-weight:500; font-size:14px; color:#FFF3EA; }

/* hero stat strip */
.pc-hero-stats{ position:relative; z-index:2; width:min(1200px, calc(100% - 48px)); margin:56px auto 0;
  display:grid; grid-template-columns:repeat(4, 1fr); gap:10px;
  border-top:1px solid rgba(255,240,235,.22); padding-top:22px; }
.pc-hero-stats .s .k{ font-family:var(--serif); font-size:27px; font-weight:500; color:#FFF6EF; }
.pc-hero-stats .s .v{ font-size:10.5px; letter-spacing:2.2px; text-transform:uppercase; color:#E9CFD8; margin-top:5px; }
@media (max-width:860px){
  .pc-hero-inner{ grid-template-columns:1fr; } .pc-hero-art{ order:-1; }
  .pc-hero-stats{ grid-template-columns:repeat(2,1fr); row-gap:20px; }
}

/* ---- the cup ----------------------------------------------------------
   The drink level is driven by --p, page scroll progress, so the cup is a
   true reading meter: full at the top, empty at the footer. --hp (progress
   through the hero) only drives the flight from the hero into the corner
   dock, which the engine positions frame by frame.

   .pc-cup-src is the copy that sits in the hero layout: on desktop it is
   visibility:hidden and exists purely to reserve the slot and give the
   engine a rectangle to fly from. The visible cup is #pc-cup-fly, a fixed
   clone the engine appends to <body> so nothing can scroll or clip it away.
   Below 900px there is no dock - the inline copy is simply made visible. */
.pc-hero-art{ position:relative; display:flex; justify-content:center; }
.pc-cup-src{ position:relative; width:min(100%, 470px); visibility:hidden; }
#pc-cup-fly{ position:fixed; left:0; bottom:0; width:470px; z-index:55; pointer-events:none;
  will-change:transform, width; }
#pc-cup-fly::before{ content:""; position:absolute; inset:-4% -8% -14% -8%; z-index:-1;
  border-radius:50%; opacity:0; transition:opacity .5s ease;
  background:radial-gradient(closest-side, rgba(250,243,233,.60), rgba(250,243,233,0) 76%); }
#pc-cup-fly.docked::before{ opacity:1; }
.pc-cup{ display:block; width:100%; overflow:visible;
  filter:drop-shadow(0 34px 44px rgba(42,16,38,.34)); transition:filter .5s ease; }
#pc-cup-fly.docked .pc-cup{ filter:drop-shadow(0 12px 20px rgba(42,16,38,.22)); }
/* the drink slides down 230 SVG units - top of the glass to the last dregs */
.pc-cup .liquid{ transform:translateY(calc(var(--p,0) * 230px)); }
.pc-cup .surface{ animation:pcWobble 6s ease-in-out infinite; transform-origin:center; }
@keyframes pcWobble{ 0%,100%{ transform:scaleX(1); } 50%{ transform:scaleX(1.012) translateY(1px); } }
.pc-cup .ice{ animation:pcBob 7s ease-in-out infinite; }
@keyframes pcBob{ 0%,100%{ transform:translateY(0) rotate(0deg); }
                  50%{ transform:translateY(-3px) rotate(.5deg); } }
.pc-level{ position:absolute; right:0; bottom:2%; text-align:right; z-index:3;
  transition:font-size .4s ease; }
.pc-level .n{ font-family:var(--serif); font-size:34px; font-weight:500; color:#FFF4EC; line-height:1;
  transition:color .5s ease, font-size .5s cubic-bezier(.22,.8,.25,1); }
.pc-level .l{ font-size:9.5px; letter-spacing:2.4px; text-transform:uppercase; color:#E7CBD6;
  margin-top:6px; transition:opacity .35s ease; }
.pc-level .bar{ margin-top:9px; margin-left:auto; width:64px; height:3px; border-radius:2px;
  background:rgba(255,240,235,.25); overflow:hidden; transition:width .5s ease, background .5s ease; }
.pc-level .bar i{ display:block; height:100%; width:calc((1 - var(--p,0)) * 100%);
  background:linear-gradient(90deg,#F7E0D0,#EBC9DC); transition:background .5s ease; }

/* Docked, the readout sits under the small glass. It travels over cream panels
   *and* the dark footer, so it carries its own paper chip rather than trusting
   the page behind it; the thin meter is dropped (the top bar already has it). */
#pc-cup-fly.docked .pc-level{ left:0; right:0; bottom:-32px; text-align:center; }
#pc-cup-fly.docked .pc-level .n{ display:inline-block; font-size:17px; color:var(--plum);
  background:rgba(252,246,238,.94); border-radius:999px; padding:3px 12px;
  box-shadow:0 5px 14px rgba(42,16,38,.16); }
#pc-cup-fly.docked .pc-level .l, #pc-cup-fly.docked .pc-level .bar{ display:none; }

@media (max-width:900px){
  #pc-cup-fly{ display:none !important; }
  .pc-cup-src{ visibility:visible; }
  .pc-level{ display:none; }
}

/* torn paper edges */
.pc-torn{ position:absolute; left:0; width:100%; height:74px; display:block; z-index:3; }
.pc-torn.bottom{ bottom:-1px; } .pc-torn.top{ top:-1px; transform:scaleY(-1); }

/* ============================ MARQUEE ============================ */
.pc-marquee{ overflow:hidden; padding:16px 0; border-bottom:1px solid var(--line);
  background:linear-gradient(90deg, rgba(234,221,245,.55), rgba(246,232,214,.55), rgba(245,223,229,.55)); }
.pc-marquee .track{ display:flex; gap:0; white-space:nowrap; width:max-content;
  transform:translateX(calc(var(--p,0) * -420px)); animation:pcSlide 38s linear infinite; }
.pc-marquee span{ font-family:var(--serif); font-style:italic; font-size:17px; color:var(--grape);
  opacity:.72; padding:0 26px; }
.pc-marquee span::after{ content:"\\2022"; margin-left:26px; color:var(--caramel); font-style:normal; }
@keyframes pcSlide{ from{ margin-left:0; } to{ margin-left:-50%; } }

/* ============================ SECTION HEADS ============================ */
.pc-anchor{ position:relative; top:-84px; height:0; }
.pc-sec{ margin:66px 0 26px; display:grid; grid-template-columns:auto 1fr; gap:22px; align-items:start; }
.pc-sec .num{ font-family:var(--serif); font-size:13px; font-weight:600; color:var(--caramel);
  letter-spacing:2px; padding-top:12px; }
.pc-sec h2{ font-family:var(--serif); font-weight:500; font-size:clamp(28px,3.4vw,42px); line-height:1.06;
  letter-spacing:-.015em; color:var(--plum); margin:0; }
.pc-sec h2 em{ font-style:italic; color:var(--orchid); }
.pc-sec p{ margin:12px 0 0; max-width:62ch; font-size:14.5px; line-height:1.66; color:var(--muted); }
.pc-sec .rule{ grid-column:1 / -1; height:1px; margin-top:22px;
  background:linear-gradient(90deg, rgba(154,79,175,.28), rgba(201,139,84,.22) 45%, rgba(154,79,175,0)); }

/* ============================ KPI CARDS ============================ */
.kpi{
  position:relative; height:100%; overflow:hidden; background:var(--tint,#F5DFE5);
  border:1px solid rgba(74,27,78,.07); border-radius:26px; padding:22px 24px 24px;
  box-shadow:0 16px 34px rgba(94,63,75,.10);
  transition:transform .3s cubic-bezier(.22,.8,.25,1), box-shadow .3s ease;
}
.kpi::before{ content:""; position:absolute; inset:auto 24px 0 24px; height:3px; opacity:.8;
  border-radius:3px 3px 0 0; background:var(--bar,#9A4FAF); }
.kpi::after{ /* faint cup-ring stain */
  content:""; position:absolute; right:-38px; bottom:-46px; width:150px; height:150px; border-radius:50%;
  border:10px solid rgba(255,255,255,.42); }
.kpi:hover{ transform:translateY(-6px); box-shadow:0 26px 48px rgba(74,27,78,.16); }
.kpi-top{ display:flex; align-items:center; justify-content:space-between; position:relative; z-index:1; }
.kpi-ic{ display:flex; width:38px; height:38px; align-items:center; justify-content:center; border-radius:13px;
  background:rgba(255,255,255,.66); color:var(--bar,#9A4FAF); }
.kpi-ic svg{ width:20px; height:20px; }
.kpi-idx{ font-family:var(--serif); font-size:12px; letter-spacing:2px; color:rgba(74,27,78,.34); }
.kpi-label{ position:relative; z-index:1; margin-top:20px; font-size:10.5px; letter-spacing:2.2px;
  text-transform:uppercase; color:var(--grape); font-weight:600; }
.kpi-value{ position:relative; z-index:1; font-family:var(--serif); font-size:clamp(32px,3.4vw,42px);
  font-weight:500; color:var(--ink); margin-top:10px; line-height:1; font-variant-numeric:tabular-nums; }
.kpi-sub{ position:relative; z-index:1; font-size:12.5px; color:var(--muted); margin-top:10px; line-height:1.5; }

/* ============================ PANELS ============================ */
div[class*="st-key-pcpanel"]{
  background:linear-gradient(180deg, rgba(255,253,250,.94) 0%, rgba(253,247,241,.92) 100%);
  border:1px solid rgba(74,27,78,.08) !important; border-radius:30px !important;
  box-shadow:0 24px 60px rgba(94,63,75,.12); padding:26px 30px 24px !important; margin-bottom:10px;
  backdrop-filter:blur(4px);
}
.pc-mini{ display:flex; align-items:center; gap:11px; margin:2px 0 10px; }
.pc-mini .ic{ display:flex; width:34px; height:34px; align-items:center; justify-content:center;
  border-radius:12px; background:linear-gradient(135deg,var(--lilac),#F7EEFB); color:var(--grape); }
.pc-mini .ic svg{ width:19px; height:19px; }
.pc-mini h3{ font-family:var(--serif); font-weight:500; color:var(--plum); font-size:20px; margin:0;
  letter-spacing:-.01em; }

/* ---- the funnel: centred bars that grow on reveal ---- */
.pcf{ padding:10px 4px 0; }
.pcf .meta{ display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px; }
.pcf .meta .s{ font-size:10.5px; letter-spacing:2.2px; text-transform:uppercase;
  color:var(--grape); font-weight:600; }
.pcf .meta .n{ font-family:var(--serif); font-size:21px; color:var(--ink);
  font-variant-numeric:tabular-nums; }
.pcf .bar{ height:40px; display:flex; justify-content:center; }
.pcf .bar i{ display:block; height:100%; width:0; border-radius:13px; background:var(--c);
  box-shadow:0 10px 22px rgba(74,27,78,.18); transition:width 1.05s cubic-bezier(.22,.8,.25,1),
  filter .2s ease; transition-delay:calc(var(--i, 0) * .11s); }
.pcf[data-in="1"] .bar i{ width:var(--w); }
.pcf .bar i:hover{ filter:brightness(1.07) saturate(1.05); }
.pcf .gap{ display:flex; justify-content:center; padding:11px 0 9px; position:relative; }
.pcf .gap::before{ content:""; position:absolute; top:0; left:50%; width:1px; height:100%;
  background:linear-gradient(180deg, rgba(154,79,175,.30), rgba(154,79,175,0)); }
.pcf .gap span{ position:relative; background:rgba(253,248,241,.9); border-radius:999px;
  padding:3px 12px; font-size:11.5px; color:var(--muted); letter-spacing:.3px; }
.pcf .gap b{ color:var(--caramel); font-weight:600; }
.pcf-note{ margin-top:14px; text-align:center; font-size:11px; letter-spacing:.4px;
  color:var(--muted); opacity:.8; font-style:italic; }

/* insight callouts */
.pc-insight{ background:linear-gradient(100deg, rgba(234,221,245,.62), rgba(246,232,214,.48));
  border:1px solid rgba(154,79,175,.12); border-left:3px solid var(--orchid);
  border-radius:6px 16px 16px 6px; padding:14px 18px; font-size:13.6px; color:var(--plum);
  margin-top:12px; line-height:1.6; }
.pc-insight b{ color:var(--ink); }

/* a/b metric cards + verdict pill */
.ab-metric{ height:100%; border:1px solid rgba(74,27,78,.09); border-radius:20px; padding:18px 18px 20px;
  text-align:center; background:linear-gradient(180deg,#FFFFFF,#FBF4FA);
  box-shadow:0 8px 22px rgba(74,27,78,.07); transition:transform .28s cubic-bezier(.22,.8,.25,1); }
.ab-metric:hover{ transform:translateY(-4px); }
.ab-metric .lab{ font-size:10.5px; letter-spacing:2px; color:var(--grape); text-transform:uppercase; font-weight:600; }
.ab-metric .val{ font-family:var(--serif); font-size:34px; font-weight:500; color:var(--ink); margin-top:8px;
  font-variant-numeric:tabular-nums; }
.ab-metric .verdict{ margin-top:10px; }
.ab-metric .pv{ font-size:12.5px; color:var(--muted); margin-top:9px; }
.pill{ display:inline-block; padding:8px 18px; border-radius:999px; font-weight:600; font-size:12.5px;
  letter-spacing:.6px; background:linear-gradient(135deg,var(--plum),var(--orchid)); color:#FFF6FB;
  box-shadow:0 8px 20px rgba(110,46,124,.34); }
.pill.warn{ background:linear-gradient(135deg,#A98CA8,#C0A3BC); box-shadow:none; }

/* attribution toggle -> pills */
div[role="radiogroup"]{ gap:8px !important; }
div[role="radiogroup"] label{ border:1px solid rgba(74,27,78,.14); border-radius:999px; padding:7px 16px !important;
  background:rgba(255,255,255,.7); transition:all .22s ease; cursor:pointer; }
div[role="radiogroup"] label:hover{ border-color:var(--orchid); background:#fff; }
div[role="radiogroup"] label > div:first-child{ display:none !important; }
div[role="radiogroup"] label p{ font-size:12.5px !important; font-weight:500; color:var(--grape) !important;
  letter-spacing:.3px; }
div[role="radiogroup"] label:has(input:checked){ background:linear-gradient(135deg,var(--plum),var(--grape));
  border-color:transparent; box-shadow:0 8px 18px rgba(74,27,78,.22); }
div[role="radiogroup"] label:has(input:checked) p{ color:#FDF3FA !important; }

/* ============================ FOOTER ============================ */
.pc-footer{ position:relative; margin-top:78px; padding:110px 0 56px;
  background:linear-gradient(150deg,#5E3F4B 0%, #7C5570 48%, #4B1B4E 100%); overflow:hidden; }
.pc-footer .wrap{ position:relative; z-index:2; width:min(1200px, calc(100% - 48px)); margin:0 auto;
  display:grid; grid-template-columns:minmax(0,1.3fr) minmax(0,1fr); gap:40px; }
.pc-footer h4{ font-family:var(--serif); font-weight:500; font-size:30px; color:#FFF5EE; margin:0 0 14px;
  letter-spacing:-.01em; }
.pc-footer p{ font-size:13.4px; line-height:1.72; color:#E9D6DC; opacity:.9; margin:0 0 10px; max-width:60ch; }
.pc-footer .tags{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }
.pc-footer .tags span{ font-size:11px; letter-spacing:1.3px; text-transform:uppercase; color:#F1DCE3;
  border:1px solid rgba(255,240,235,.26); border-radius:999px; padding:6px 13px; }
.pc-footer p.pad{ margin-top:22px; }
.pc-footer .sig{ font-family:var(--serif); font-style:italic; font-size:20px; color:#FFF3EA; margin-top:20px; }
@media (max-width:860px){ .pc-footer .wrap{ grid-template-columns:1fr; } }

/* ============================ SCROLL REVEALS ============================ */
html.pc-js [data-reveal]{ opacity:0; transform:translateY(30px);
  transition:opacity .78s cubic-bezier(.22,.8,.25,1), transform .78s cubic-bezier(.22,.8,.25,1); }
html.pc-js [data-reveal][data-in="1"]{ opacity:1; transform:none; }
html.pc-js [data-reveal][data-d="1"]{ transition-delay:.09s; }
html.pc-js [data-reveal][data-d="2"]{ transition-delay:.18s; }
html.pc-js [data-reveal][data-d="3"]{ transition-delay:.27s; }
/* reduced motion kills the looping decoration; the cup still tracks scroll,
   since its level is information rather than ornament */
@media (prefers-reduced-motion: reduce){
  html.pc-js [data-reveal]{ opacity:1 !important; transform:none !important; }
  .pc-cup .surface, .pc-cup .ice, .pc-marquee .track{ animation:none !important; }
  .pc-marquee .track{ transform:none !important; }
}

/* plotly tidy-up */
.js-plotly-plot .plotly .modebar{ display:none !important; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)


def h(markup: str) -> str:
    """Flatten markup to one line before handing it to st.markdown.

    Streamlit runs our HTML through a Markdown parser first, and any line
    indented four or more spaces would be turned into a literal code block.
    Stripping the indentation and joining with single spaces keeps the markup
    intact without changing how it renders.
    """
    return " ".join(ln.strip() for ln in markup.strip().splitlines() if ln.strip())


def style_fig(fig: go.Figure, height: int = 340) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=6, r=6, t=18, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=INK, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=12)),
        hoverlabel=dict(bgcolor="#FFFDFA", bordercolor="#E7D8EA",
                        font=dict(family="Inter, sans-serif", color=INK)),
    )
    fig.update_xaxes(gridcolor="rgba(74,27,78,.07)", zeroline=False, linecolor="rgba(74,27,78,.12)")
    fig.update_yaxes(gridcolor="rgba(74,27,78,.07)", zeroline=False, linecolor="rgba(74,27,78,.12)")
    return fig


def mini(icon: str, title: str) -> None:
    """Small titled header used inside a panel."""
    st.markdown(h(f'<div class="pc-mini"><span class="ic">{icon}</span><h3>{title}</h3></div>'),
                unsafe_allow_html=True)


def funnel_bars(f) -> None:
    """Draw the funnel as centred bars that grow when the panel scrolls in.

    A Plotly funnel is unusable here: 1.13M impressions against 2.6k purchases
    renders the last three stages as a hairline. Widths therefore use an eased
    scale (count ** 0.32) so every stage stays legible - the printed counts and
    step conversions are exact, and the note under the chart says so.
    """
    top = float(f["count"].iloc[0])
    rows = []
    for i, r in f.iterrows():
        width = max(0.12, (float(r["count"]) / top) ** 0.32) * 100
        c1, c2 = FUNNEL_GRADS[i % len(FUNNEL_GRADS)]
        if i:
            rows.append(
                f'<div class="gap"><span><b>{r["step_conv_pct"]:.1f}%</b> continue '
                f'&middot; {int(r["dropped_count"]):,} lost</span></div>')
        rows.append(
            f'<div class="row" style="--w:{width:.1f}%; --c:linear-gradient(90deg,{c1},{c2}); --i:{i};">'
            f'<div class="meta"><span class="s">{r["stage"]}</span>'
            f'<span class="n">{int(r["count"]):,}</span></div>'
            f'<div class="bar"><i></i></div></div>')
    st.markdown(h(f'<div class="pcf" data-reveal="funnel">{"".join(rows)}'
                  f'<div class="pcf-note">widths use an eased scale so every stage stays '
                  f'visible &mdash; the counts are exact</div></div>'), unsafe_allow_html=True)


def insight(body: str) -> None:
    """The lilac takeaway box that sits under a chart."""
    st.markdown(h(f'<div class="pc-insight">{body}</div>'), unsafe_allow_html=True)


TORN = ('<svg class="pc-torn {cls}" viewBox="0 0 1440 74" preserveAspectRatio="none" '
        'xmlns="http://www.w3.org/2000/svg"><path fill="{fill}" d="M0,74 L0,36 '
        'C58,20 104,45 168,38 C232,31 268,54 332,47 C396,40 436,16 500,25 '
        'C564,34 596,58 660,51 C724,44 762,18 826,27 C890,36 918,60 982,53 '
        'C1046,46 1082,20 1146,29 C1210,38 1244,62 1308,55 C1372,48 1404,24 1440,33 L1440,74 Z"/>'
        '<path fill="{fill}" opacity=".45" d="M0,74 L0,50 C70,40 118,58 190,52 '
        'C262,46 300,62 372,56 C444,50 480,34 552,42 C624,50 660,66 732,60 '
        'C804,54 840,36 912,44 C984,52 1020,68 1092,62 C1164,56 1200,40 1272,48 '
        'C1344,56 1392,66 1440,58 L1440,74 Z"/></svg>')


def section(num: str, anchor: str, label: str, title_html: str, blurb: str) -> None:
    """Editorial section header + a scroll anchor the nav / rail can jump to."""
    st.markdown(h(
        f'<div class="pc-anchor" id="{anchor}" data-label="{label}"></div>'
        f'<div class="pc-sec" data-reveal="sec"><span class="num">{num}</span>'
        f'<div><h2>{title_html}</h2><p>{blurb}</p></div>'
        f'<div class="rule"></div></div>'),
        unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# THE GLASS  (hero art). An iced latte: the .liquid group slides down as --p
# (page scroll progress) goes 0 -> 1, taking the floating ice with it, while
# the ube boba stay settled on the bottom and the straw stays put. Empty glass
# with a few dregs at the footer.
# ---------------------------------------------------------------------------
CUP_SVG = """
<svg class="pc-cup" viewBox="0 0 460 430" xmlns="http://www.w3.org/2000/svg" fill="none">
  <defs>
    <linearGradient id="pcGlass" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity=".55"/>
      <stop offset="26%" stop-color="#FFFFFF" stop-opacity=".10"/>
      <stop offset="74%" stop-color="#FFFFFF" stop-opacity=".10"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity=".45"/>
    </linearGradient>
    <linearGradient id="pcCoaster" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#FFFBF6"/><stop offset="100%" stop-color="#DFCCCE"/>
    </linearGradient>
    <linearGradient id="pcBrew" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3E2015"/><stop offset="18%" stop-color="#5E3520"/>
      <stop offset="48%" stop-color="#95603C"/><stop offset="78%" stop-color="#C89765"/>
      <stop offset="100%" stop-color="#E2C199"/>
    </linearGradient>
    <linearGradient id="pcIce" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity=".72"/>
      <stop offset="55%" stop-color="#E8F3F8" stop-opacity=".44"/>
      <stop offset="100%" stop-color="#B9D6E4" stop-opacity=".34"/>
    </linearGradient>
    <linearGradient id="pcStraw" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#B266C4"/><stop offset="100%" stop-color="#7E3A90"/>
    </linearGradient>
    <clipPath id="pcInner">
      <path d="M141,80 L160,344 A64,11 0 0 0 290,344 L309,80 Z"/>
    </clipPath>
  </defs>

  <!-- shadow + paper coaster -->
  <ellipse cx="225" cy="380" rx="140" ry="20" fill="#2A1026" opacity=".22"/>
  <ellipse cx="225" cy="374" rx="126" ry="21" fill="url(#pcCoaster)"/>
  <ellipse cx="225" cy="369" rx="126" ry="21" fill="#FFFCF7"/>
  <ellipse cx="225" cy="368" rx="92" ry="14" fill="none" stroke="#E7D6D8" stroke-width="1.4"/>

  <!-- the glass, back wall first so the drink sits inside it -->
  <path d="M133,72 L153,348 A72,12 0 0 0 297,348 L317,72 Z" fill="#F2F7F9" opacity=".34"/>

  <!-- the drink: this group slides down as --p grows, taking the ice with it -->
  <g clip-path="url(#pcInner)">
    <g class="liquid">
      <rect x="133" y="104" width="184" height="330" fill="url(#pcBrew)"/>
      <g class="surface">
        <ellipse cx="225" cy="104" rx="86" ry="14" fill="#B98452"/>
        <ellipse cx="225" cy="102" rx="86" ry="14" fill="#D7A874"/>
        <ellipse cx="204" cy="99" rx="26" ry="7" fill="#EBCBA4" opacity=".75"/>
      </g>
      <g class="ice" stroke="#FFFFFF" stroke-opacity=".7" stroke-width="1.6">
        <rect x="160" y="96" width="52" height="46" rx="11" fill="url(#pcIce)" transform="rotate(-13 186 119)"/>
        <rect x="216" y="82" width="46" height="42" rx="10" fill="url(#pcIce)" transform="rotate(9 239 103)"/>
        <rect x="246" y="124" width="48" height="44" rx="10" fill="url(#pcIce)" transform="rotate(-7 270 146)"/>
        <rect x="168" y="156" width="44" height="40" rx="10" fill="url(#pcIce)" transform="rotate(16 190 176)"/>
        <rect x="214" y="184" width="42" height="38" rx="9" fill="url(#pcIce)" transform="rotate(-4 235 203)"/>
      </g>
    </g>
    <!-- ube boba settled on the bottom - they stay put while the level drops -->
    <g class="boba">
      <circle cx="186" cy="336" r="12" fill="#4B1B4E"/><circle cx="212" cy="341" r="12" fill="#5C2460"/>
      <circle cx="238" cy="336" r="12" fill="#4B1B4E"/><circle cx="264" cy="341" r="12" fill="#5C2460"/>
      <circle cx="199" cy="320" r="11" fill="#6E2E7C"/><circle cx="251" cy="320" r="11" fill="#6E2E7C"/>
      <circle cx="225" cy="328" r="11" fill="#5C2460"/>
      <circle cx="196" cy="316" r="3.2" fill="#B98ACB" opacity=".7"/>
      <circle cx="248" cy="316" r="3.2" fill="#B98ACB" opacity=".7"/>
    </g>
  </g>

  <!-- glass front: sheen, walls, rim, condensation -->
  <path d="M133,72 L153,348 A72,12 0 0 0 297,348 L317,72 Z" fill="url(#pcGlass)"/>
  <path d="M133,72 L153,348 A72,12 0 0 0 297,348 L317,72 Z" stroke="#FFFFFF" stroke-opacity=".85"
        stroke-width="3"/>
  <path d="M166,96 L182,330" stroke="#FFFFFF" stroke-opacity=".5" stroke-width="7" stroke-linecap="round"/>
  <path d="M288,110 L276,300" stroke="#FFFFFF" stroke-opacity=".28" stroke-width="5" stroke-linecap="round"/>
  <ellipse cx="225" cy="72" rx="92" ry="16" fill="#FFFFFF" fill-opacity=".22"/>
  <ellipse cx="225" cy="72" rx="92" ry="16" fill="none" stroke="#FFFFFF" stroke-opacity=".9" stroke-width="3.4"/>
  <g fill="#FFFFFF" opacity=".45">
    <ellipse cx="196" cy="164" rx="4" ry="5.5"/><ellipse cx="205" cy="216" rx="3" ry="4"/>
    <ellipse cx="188" cy="258" rx="4.5" ry="6"/><ellipse cx="266" cy="192" rx="3.4" ry="4.6"/>
    <ellipse cx="272" cy="252" rx="4.2" ry="5.6"/><ellipse cx="256" cy="300" rx="3" ry="4"/>
  </g>

  <!-- straw: stays where it is while the drink goes down -->
  <g transform="rotate(11 250 180)">
    <path d="M258,26 L244,296" stroke="url(#pcStraw)" stroke-width="17" stroke-linecap="round"/>
    <path d="M256,42 L254,74" stroke="#F1DCF5" stroke-opacity=".85" stroke-width="17"/>
    <path d="M252,110 L250,142" stroke="#F1DCF5" stroke-opacity=".7" stroke-width="17"/>
    <path d="M261,28 L248,290" stroke="#FFFFFF" stroke-opacity=".35" stroke-width="4"
          stroke-linecap="round"/>
  </g>

  <!-- a couple of beans on the coaster -->
  <g stroke="#6B4433" stroke-width="1.8" fill="#8A5A41" opacity=".85">
    <g transform="translate(112,366) rotate(-24)">
      <ellipse rx="13" ry="8"/><path d="M-9,4 C-4,-2 4,-4 9,-5" fill="none" stroke="#4A2C1E"/>
    </g>
    <g transform="translate(340,370) rotate(18)">
      <ellipse rx="12" ry="7.5"/><path d="M-8,3.5 C-4,-1.5 4,-3.5 8,-4.5" fill="none" stroke="#4A2C1E"/>
    </g>
  </g>
</svg>
"""


# ---------------------------------------------------------------------------
# SCROLL ENGINE
# Streamlit strips <script> from st.markdown, so the interaction layer is
# injected through a zero-height component iframe that reaches into the parent
# document. It owns: scroll progress vars (--p page, --hp hero), the fixed
# chrome (progress bar, section rail, back-to-top, floating beans), reveal-on-
# enter, number count-ups, nav state, and smooth anchor jumps. A
# MutationObserver re-scans after every Streamlit rerun.
# ---------------------------------------------------------------------------
ENGINE = r"""<script>
(function(){
  var W = window.parent, D = W.document, R = D.documentElement;
  var VER = 'pc-engine-11';
  /* Always tear down and re-install. A Streamlit rerun can rebuild this
     component's iframe, which kills the realm the previous engine lived in -
     so its __pcRescan / observers are dead objects. Reusing them would leave
     every reveal stuck at opacity 0. If instead the iframe survives a rerun,
     this script simply does not run again and the live engine keeps working. */
  if (W.__pcKill) { try { W.__pcKill(); } catch(e){} }

  var bound = [];
  function on(t, ev, fn, opt){ t.addEventListener(ev, fn, opt); bound.push([t, ev, fn, opt]); }

  /* ---------------- engine-owned chrome ---------------- */
  var css = D.createElement('style');
  css.id = 'pc-engine-css';
  css.textContent = [
    '#pc-prog{position:fixed;top:0;left:0;right:0;height:3px;z-index:80;pointer-events:none;',
    '  background:rgba(74,27,78,.08);}',
    '#pc-prog i{display:block;height:100%;width:0%;transition:width .12s linear;',
    '  background:linear-gradient(90deg,#4A2418,#8E5A3C 40%,#9A4FAF 78%,#C77CC0);',
    '  box-shadow:0 0 12px rgba(154,79,175,.55);}',
    '#pc-rail{position:fixed;right:22px;top:50%;transform:translateY(-50%);z-index:70;',
    '  display:flex;flex-direction:column;gap:15px;align-items:flex-end;}',
    '#pc-rail button{all:unset;cursor:pointer;display:flex;align-items:center;gap:9px;opacity:.5;',
    '  transition:opacity .25s ease;}',
    '#pc-rail button:hover,#pc-rail button.on{opacity:1;}',
    '#pc-rail .t{font:500 10.5px/1 Inter,sans-serif;letter-spacing:1.6px;text-transform:uppercase;',
    '  color:#6E2E7C;opacity:0;transform:translateX(6px);transition:all .25s ease;white-space:nowrap;}',
    '#pc-rail button:hover .t,#pc-rail button.on .t{opacity:1;transform:none;}',
    '#pc-rail .d{width:8px;height:8px;border-radius:50%;background:#6E2E7C;opacity:.45;',
    '  transition:all .3s cubic-bezier(.22,.8,.25,1);}',
    '#pc-rail button.on .d{opacity:1;width:10px;height:10px;background:#9A4FAF;',
    '  box-shadow:0 0 0 4px rgba(154,79,175,.18);}',
    '#pc-top{position:fixed;right:22px;bottom:26px;z-index:70;width:46px;height:46px;border-radius:50%;',
    '  border:1px solid rgba(74,27,78,.12);background:rgba(253,248,241,.9);color:#4B1B4E;cursor:pointer;',
    '  display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;',
    '  transform:translateY(12px);transition:all .35s cubic-bezier(.22,.8,.25,1);',
    '  box-shadow:0 12px 26px rgba(74,27,78,.16);backdrop-filter:blur(8px);}',
    '#pc-top.show{opacity:1;pointer-events:auto;transform:none;}',
    '#pc-top:hover{transform:translateY(-3px);}',
    '#pc-beans{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden;}',
    '#pc-beans i{position:absolute;display:block;color:#8A6470;opacity:.16;}',
    '#pc-beans svg{width:100%;height:100%;}',
    '@media (max-width:1100px){#pc-rail{display:none;}#pc-beans{display:none;}}',
    '@media (prefers-reduced-motion: reduce){#pc-beans{display:none;}}'
  ].join('');
  D.head.appendChild(css);

  function el(tag, id, html){
    var e = D.createElement(tag); if (id) e.id = id; if (html) e.innerHTML = html;
    D.body.appendChild(e); return e;
  }
  ['pc-prog','pc-rail','pc-top','pc-beans','pc-cup-fly'].forEach(function(id){
    var o = D.getElementById(id); if (o) o.remove();
  });

  var prog = el('div', 'pc-prog', '<i></i>');
  var progFill = prog.firstChild;
  var rail = el('div', 'pc-rail', '');
  var toTop = el('button', 'pc-top',
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M12 19V5M5 12l7-7 7 7"/></svg>');

  /* drifting coffee beans, parallaxed by scroll */
  var beanSVG = '<svg viewBox="0 0 40 26" fill="none" stroke="currentColor" stroke-width="1.6">' +
    '<ellipse cx="20" cy="13" rx="18" ry="11"/><path d="M7 20C12 14 20 10 33 6"/></svg>';
  var beans = el('div', 'pc-beans', '');
  var beanSpec = [
    [4, 16, 46, -0.34, -18], [92, 26, 34, 0.26, 24], [8, 62, 30, 0.42, -12],
    [88, 74, 44, -0.30, 16], [50, 8, 26, 0.20, 8], [70, 46, 22, -0.22, -10],
    [26, 88, 32, 0.36, 14], [96, 52, 26, 0.16, -8]
  ];
  var beanEls = beanSpec.map(function(s){
    var b = D.createElement('i');
    b.style.left = s[0] + '%'; b.style.top = s[1] + '%';
    b.style.width = s[2] + 'px'; b.style.height = (s[2] * 0.65) + 'px';
    b.innerHTML = beanSVG; b.__k = s[3]; b.__r = s[4];
    beans.appendChild(b); return b;
  });

  /* ---------------- the flying cup ----------------
     The visible cup is a clone of the hero's .pc-cup-src living directly on
     <body>, so no scrolling ancestor can take it off screen. Each frame it is
     interpolated between the hero slot's rectangle and a small bottom-left
     dock, anchored bottom-left so no height measurement (and no layout read
     after write) is ever needed. Cloning rather than moving the original
     matters: stealing a node out of a Streamlit container makes React throw
     when it later tries to remove it. */
  var DOCK_W = 148, DOCK_L = 18, DOCK_B = 46, DOCK_MIN_VW = 900;
  var fly = null, cupSrc = null;

  function buildCup(){
    var old = D.getElementById('pc-cup-fly'); if (old) old.remove();
    cupSrc = D.querySelector('.pc-cup-src');
    if (!cupSrc) { fly = null; return; }
    fly = D.createElement('div');
    fly.id = 'pc-cup-fly';
    /* The clone would otherwise duplicate every SVG id in the document, and
       url(#...) resolves to the *first* match - the hidden copy. A clipPath
       inside a visibility:hidden subtree clips to nothing, which silently
       erases the drink. Give the clone its own namespace. */
    fly.innerHTML = cupSrc.innerHTML
      .replace(/id="(pc[A-Za-z]+)"/g, 'id="$1-fly"')
      .replace(/url\(#(pc[A-Za-z]+)\)/g, 'url(#$1-fly)');
    D.body.appendChild(fly);
  }

  function placeCup(t){
    if (!fly) return;
    if (!cupSrc || !cupSrc.isConnected) cupSrc = D.querySelector('.pc-cup-src');
    if (!cupSrc || W.innerWidth < DOCK_MIN_VW) return;
    var r = cupSrc.getBoundingClientRect();
    if (!r.width) return;
    var e = t * t * (3 - 2 * t);                    // smoothstep, softer landing
    var w = r.width + (DOCK_W - r.width) * e;
    var x = r.left + (DOCK_L - r.left) * e;
    var bottom = viewH() - r.bottom;                 // hero slot, measured from the viewport floor
    var b = bottom + (DOCK_B - bottom) * e;
    fly.style.width = w.toFixed(1) + 'px';
    fly.style.transform = 'translate3d(' + x.toFixed(1) + 'px,' + (-b).toFixed(1) + 'px,0)';
    fly.classList.toggle('docked', e > 0.55);
  }

  /* ---------------- scroller ---------------- */
  function pickScroller(){
    var sel = ['[data-testid="stMain"]', 'section.main', '[data-testid="stAppViewContainer"]'];
    for (var i = 0; i < sel.length; i++){
      var e = D.querySelector(sel[i]);
      if (e && e.scrollHeight > e.clientHeight + 20) return e;
    }
    return D.scrollingElement || R;
  }
  var sc = pickScroller();
  function scrollTopOf(){ return sc === R || sc === D.body ? (W.pageYOffset || R.scrollTop) : sc.scrollTop; }
  function viewH(){ return W.innerHeight || R.clientHeight; }

  /* ---------------- per-frame update ---------------- */
  var nav = null, hero = null, anchors = [], railBtns = [], ticking = false, lastPick = 0;

  function update(){
    ticking = false;
    var now = Date.now();
    if (now - lastPick > 800){ lastPick = now; if (sc.scrollHeight <= sc.clientHeight + 20) sc = pickScroller(); }

    var y = scrollTopOf();
    var max = Math.max(1, sc.scrollHeight - sc.clientHeight);
    var p = Math.min(1, Math.max(0, y / max));

    /* --hp is how far the hero has travelled: it flies the cup to its dock.
       The drink level itself follows --p, so the cup empties across the whole
       page and reads 0% exactly at the footer. */
    if (!hero) hero = D.querySelector('.pc-hero');
    var span = hero ? hero.offsetHeight * 0.72 : viewH() * 0.7;
    var hp = Math.min(1, Math.max(0, y / Math.max(1, span)));

    R.style.setProperty('--p', p.toFixed(4));
    R.style.setProperty('--hp', hp.toFixed(4));
    R.style.setProperty('--vw', sc.clientWidth + 'px');
    progFill.style.width = (p * 100).toFixed(2) + '%';

    var pct = Math.round((1 - p) * 100) + '%';
    var lvls = D.querySelectorAll('.pc-level-n');
    for (var n = 0; n < lvls.length; n++) lvls[n].textContent = pct;
    placeCup(hp);

    if (!nav) nav = D.querySelector('.pc-nav');
    /* light nav while it sits over the hero band, paper nav once past it */
    if (nav) nav.classList.toggle('solid',
      hero ? hero.getBoundingClientRect().bottom < 84 : y > viewH() * 0.6);
    toTop.classList.toggle('show', y > viewH() * 0.9);

    for (var i = 0; i < beanEls.length; i++){
      var b = beanEls[i];
      b.style.transform = 'translateY(' + (y * b.__k).toFixed(1) + 'px) rotate(' +
                          (b.__r + p * 90 * (b.__k > 0 ? 1 : -1)).toFixed(1) + 'deg)';
    }

    /* active section on the rail + nav */
    var act = -1, mid = viewH() * 0.42;
    for (var j = 0; j < anchors.length; j++){
      if (anchors[j].getBoundingClientRect().top <= mid) act = j;
    }
    railBtns.forEach(function(b, k){ b.classList.toggle('on', k === act); });
    if (nav) nav.querySelectorAll('a[data-goto]').forEach(function(a){
      a.classList.toggle('on', act >= 0 && a.getAttribute('data-goto') === anchors[act].id);
    });

    checkReveals();
  }
  function onScroll(){ if (!ticking){ ticking = true; W.requestAnimationFrame(update); } }

  /* ---------------- reveal + count-up ---------------- */
  function fmt(v, dec){
    return v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }
  function countUp(node){
    var target = parseFloat(node.getAttribute('data-count'));
    if (!isFinite(target)) return;
    var dec = parseInt(node.getAttribute('data-dec') || '0', 10);
    var pre = node.getAttribute('data-prefix') || '';
    var suf = node.getAttribute('data-suffix') || '';
    var t0 = 0, dur = 1250;
    function step(t){
      if (!t0) t0 = t;
      var k = Math.min(1, (t - t0) / dur);
      var e = 1 - Math.pow(1 - k, 3);
      node.textContent = pre + fmt(target * e, dec) + suf;
      if (k < 1) W.requestAnimationFrame(step);
    }
    W.requestAnimationFrame(step);
  }

  /* Reveals are measured against the real page viewport rather than with an
     IntersectionObserver: this script lives in a zero-height component iframe,
     so an observer created here would use *that* iframe as its root and never
     fire. A rect test per frame over a handful of nodes is cheap and exact. */
  var pending = [];
  function checkReveals(){
    if (!pending.length) return;
    var vh = viewH(), still = [];
    for (var i = 0; i < pending.length; i++){
      var n = pending[i];
      if (n.getBoundingClientRect().top < vh * 0.92){
        n.setAttribute('data-in', '1');
        n.querySelectorAll('[data-count]:not([data-done])').forEach(function(c){
          c.setAttribute('data-done', '1'); countUp(c);
        });
      } else { still.push(n); }
    }
    pending = still;
  }

  function jump(id){
    var t = D.getElementById(id); if (!t) return;
    var offset = 92;
    if (sc === R || sc === D.body){
      W.scrollTo({ top: t.getBoundingClientRect().top + scrollTopOf() - offset, behavior: 'smooth' });
    } else {
      var d = t.getBoundingClientRect().top - sc.getBoundingClientRect().top;
      sc.scrollTo({ top: sc.scrollTop + d - offset, behavior: 'smooth' });
    }
  }

  function buildRail(){
    var found = Array.prototype.slice.call(D.querySelectorAll('.pc-anchor[data-label]'));
    if (found.length === anchors.length &&
        found.every(function(a, i){ return a === anchors[i]; })) return;
    anchors = found; rail.innerHTML = ''; railBtns = [];
    anchors.forEach(function(a){
      var b = D.createElement('button');
      b.innerHTML = '<span class="t">' + a.getAttribute('data-label') + '</span><span class="d"></span>';
      b.onclick = function(){ jump(a.id); };
      rail.appendChild(b); railBtns.push(b);
    });
  }

  function rescan(){
    if (!fly || !fly.isConnected) buildCup();
    /* Streamlit's own panel containers get the reveal treatment too */
    D.querySelectorAll('div[class*="st-key-pcpanel"]').forEach(function(e){
      if (!e.hasAttribute('data-reveal')) e.setAttribute('data-reveal', 'panel');
    });
    pending = Array.prototype.slice.call(D.querySelectorAll('[data-reveal]:not([data-in])'));
    buildRail();
    update();
  }
  W.__pcRescan = rescan;

  on(D, 'click', function(ev){
    var t = ev.target.closest ? ev.target.closest('[data-goto]') : null;
    if (t){ ev.preventDefault(); jump(t.getAttribute('data-goto')); }
  }, true);
  toTop.onclick = function(){
    if (sc === R || sc === D.body) W.scrollTo({ top: 0, behavior: 'smooth' });
    else sc.scrollTo({ top: 0, behavior: 'smooth' });
  };

  var moT = null;
  var mo = new W.MutationObserver(function(){
    clearTimeout(moT); moT = setTimeout(rescan, 110);
  });
  mo.observe(D.body, { childList: true, subtree: true });

  on(W, 'scroll', onScroll, { passive: true, capture: true });
  on(W, 'resize', onScroll);

  R.classList.add('pc-js');
  W.__pcVer = VER;
  W.__pcKill = function(){
    bound.forEach(function(b){ b[0].removeEventListener(b[1], b[2], b[3]); });
    try { mo.disconnect(); } catch(e){}
    ['pc-prog','pc-rail','pc-top','pc-beans','pc-cup-fly','pc-engine-css'].forEach(function(id){
      var o = D.getElementById(id); if (o) o.remove();
    });
    R.classList.remove('pc-js');
    W.__pcVer = null;
  };

  rescan();
  setTimeout(rescan, 400);
  setTimeout(rescan, 1200);
})();
</script>"""


# ===========================================================================
# RENDER
# ===========================================================================
d = load_data()

# --- fixed top navigation --------------------------------------------------
st.markdown(h(f"""
<div class="pc-nav">
  <div class="wrap">
    <div class="brand">{CUP_ICON}<b>The Purple Cup</b></div>
    <div class="links">
      <a data-goto="sec-overview">Overview</a>
      <a data-goto="sec-funnel">Funnel</a>
      <a data-goto="sec-test">Experiment</a>
      <a data-goto="sec-people">Customers</a>
    </div>
    <a class="cta" data-goto="pc-colophon"><span>About</span></a>
  </div>
</div>
"""), unsafe_allow_html=True)

# --- hero ------------------------------------------------------------------
st.markdown(h(f"""
<div class="pc-hero">
  <div class="pc-hero-inner">
    <div class="pc-hero-copy">
      <div class="pc-eyebrow">simulated data &middot; portfolio project</div>
      <h1 class="pc-display">Every Cup<br><em>Tells a Story.</em></h1>
      <p class="pc-lede">Six months of spend, journeys, experiments and customers for
        <b>The Purple Cup</b> &mdash; a fictional small-batch matcha, ube &amp; coffee brand &mdash;
        brewed down into the numbers that actually move the business.</p>
      <div class="pc-hero-cta">
        <button class="pc-btn" data-goto="sec-overview">Pour me a look</button>
        <span class="pc-by">analysis &amp; build by <b>Erica Mathias</b></span>
      </div>
    </div>
    <div class="pc-hero-art">
      <div class="pc-cup-src">
        {CUP_SVG}
        <div class="pc-level">
          <div class="n pc-level-n">100%</div>
          <div class="l">cup remaining</div>
          <div class="bar"><i></i></div>
        </div>
      </div>
    </div>
  </div>
  <div class="pc-hero-stats">
    <div class="s"><div class="k">{d['impressions']:,.0f}</div><div class="v">impressions</div></div>
    <div class="s"><div class="k">{d['clicks']:,}</div><div class="v">clicks</div></div>
    <div class="s"><div class="k">{d['purchases']:,}</div><div class="v">purchases</div></div>
    <div class="s"><div class="k">5</div><div class="v">campaigns</div></div>
  </div>
  {TORN.format(cls="bottom", fill="#FDF8F1")}
</div>
"""), unsafe_allow_html=True)

# --- marquee ---------------------------------------------------------------
MARQUEE_WORDS = ["iced matcha", "ube", "cold brew", "small batch", "oat milk",
                 "single origin", "over ice", "purple hour"]
_ticker = "".join(f"<span>{w}</span>" for w in MARQUEE_WORDS * 3)
st.markdown(h(f'<div class="pc-marquee"><div class="track">{_ticker}</div></div>'),
            unsafe_allow_html=True)

# --- section 01: the headline numbers --------------------------------------
section("01", "sec-overview", "Overview",
        "The six-month <em>pour</em>, in four numbers",
        "What the brand spent, what came back, and how efficiently clicks turned into "
        "orders. Everything below is computed live from the project database.")

kpis = [
    ("Ad spend", d["spend"], 0, "$", "", "across 5 campaigns &middot; 6 months"),
    ("Revenue", d["revenue"], 0, "$", "", f"{d['purchases']:,} purchases"),
    ("Blended ROAS", d["roas"], 2, "", "x", f"${d['roas']:.2f} back per $1 spent"),
    ("Click to purchase", d["click_to_buy"] * 100, 1, "", "%", f"{d['clicks']:,} clicks converted"),
]
cols = st.columns(4, gap="medium")
for i, (col, (label, raw, dec, pre, suf, sub), tint, bar, icon) in enumerate(
        zip(cols, kpis, CARD_TINTS, CARD_BARS, KPI_ICONS)):
    shown = f"{pre}{raw:,.{dec}f}{suf}"
    col.markdown(h(f"""
    <div class="kpi" data-reveal="kpi" data-d="{i % 4}" style="--tint:{tint}; --bar:{bar};">
      <div class="kpi-top"><span class="kpi-ic">{icon}</span><span class="kpi-idx">0{i + 1}</span></div>
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" data-count="{raw:.4f}" data-dec="{dec}"
           data-prefix="{pre}" data-suffix="{suf}">{shown}</div>
      <div class="kpi-sub">{sub}</div>
    </div>"""), unsafe_allow_html=True)

# --- section 02: funnel + attribution --------------------------------------
section("02", "sec-funnel", "Funnel",
        "Where the journey <em>leaks</em>",
        "Impression to click to purchase &mdash; plus who really deserves the credit once "
        "you stop giving it all to the last click.")

with st.container(border=True, key="pcpanel-funnel"):
    left, right = st.columns([1, 1], gap="large")

    with left:
        mini(FUNNEL_ICON, "The marketing funnel")
        funnel_bars(d["funnel"])
        leak, opp = d["leak"], d["opp"]
        insight(f"""
          <b>Biggest fixable leak:</b> {leak['fixable_step']} loses {leak['fixable_drop_pct']:.0f}% of the prior stage.
          Lifting it {opp['uplift_points']:.0f} points is worth about
          <b>${opp['extra_revenue']:,.0f}</b> in added revenue.""")

    with right:
        mini(RETURN_ICON, "Revenue by channel")
        model = st.radio("Attribution model", ["Last touch", "First touch", "Linear"],
                         horizontal=True, label_visibility="collapsed")
        col_key = {"First touch": "first_touch", "Last touch": "last_touch", "Linear": "linear"}[model]
        t = d["attr_table"].sort_values(f"{col_key}_rev", ascending=True)
        fig = go.Figure(go.Bar(
            x=t[f"{col_key}_rev"], y=t["channel"], orientation="h",
            marker=dict(color=[CHANNEL_COLORS[c] for c in t["channel"]], cornerradius=9),
            text=[f"${v:,.0f}" for v in t[f"{col_key}_rev"]], textposition="outside",
            textfont=dict(color=INK, size=12.5), cliponaxis=False,
        ))
        # headroom on the axis so the outside value labels are never clipped
        fig.update_xaxes(title_text=f"Revenue credited ({model.lower()})",
                         range=[0, float(t[f"{col_key}_rev"].max()) * 1.22])
        fig.update_layout(barcornerradius=9)
        st.plotly_chart(style_fig(fig, 320), width="stretch", config={"displayModeBar": False})
        stats = d["attr_stats"]
        insight(f"""
          {stats['n_cross_channel']/stats['n_conversions']:.0%} of purchases were cross-channel journeys.
          Flip between <b>last</b> and <b>first</b> touch to watch <b>Instagram</b> jump &mdash; it starts
          journeys it rarely closes, so the ad-platform default undervalues it.""")

# --- section 03: A/B test --------------------------------------------------
section("03", "sec-test", "Experiment",
        "One subject line, <em>two</em> outcomes",
        "A held-out email test on the subject line, judged by a two-proportion z-test "
        "rather than by whichever variant happened to look nicer.")

with st.container(border=True, key="pcpanel-ab"):
    mini(FLASK_ICON, "Email A/B test &mdash; subject line")
    ab = d["ab"]
    significant = ab["p_value"] < 0.05
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4], gap="medium")
    c1.markdown(h(f'<div class="ab-metric"><div class="lab">Variant A rate</div>'
                  f'<div class="val">{ab["p_a"]:.2%}</div></div>'), unsafe_allow_html=True)
    c2.markdown(h(f'<div class="ab-metric"><div class="lab">Variant B rate</div>'
                  f'<div class="val">{ab["p_b"]:.2%}</div></div>'), unsafe_allow_html=True)
    c3.markdown(h(f'<div class="ab-metric"><div class="lab">Relative lift</div>'
                  f'<div class="val">{ab["rel_lift"]:+.0%}</div></div>'), unsafe_allow_html=True)
    pill = "pill" if significant else "pill warn"
    verdict = "Significant at 95%" if significant else "Not significant"
    c4.markdown(h(f"""<div class="ab-metric">
      <div class="lab">Two-proportion z-test</div>
      <div class="verdict"><span class="{pill}">{verdict}</span></div>
      <div class="pv">p = {ab['p_value']:.4f} &nbsp;|&nbsp; z = {ab['z']:.2f}</div>
    </div>"""), unsafe_allow_html=True)
    insight(f"""
      Variant B (&ldquo;A little purple surprise inside&rdquo;) lifted conversion from {ab['p_a']:.1%}
      to {ab['p_b']:.1%}, a {ab['rel_lift']:.0%} relative increase (p = {ab['p_value']:.3f}). The 95% CI
      for the lift is [{ab['ci_low']*100:+.2f}, {ab['ci_high']*100:+.2f}] points &mdash; real, though the
      low end is modest.""")

# --- section 04: segments --------------------------------------------------
section("04", "sec-people", "Customers",
        "Not one audience &mdash; <em>four</em>",
        "RFM scoring plus k-means splits the buyer base into groups that behave "
        "differently enough to deserve different marketing.")

with st.container(border=True, key="pcpanel-seg"):
    left2, right2 = st.columns([1, 1], gap="large")
    seg = d["seg_summary"]

    with left2:
        mini(COIN_ICON, "Customer value by segment")
        fig = go.Figure(go.Bar(
            x=seg["segment"], y=seg["total_revenue"],
            marker=dict(color=[SEGMENT_COLORS[s] for s in seg["segment"]], cornerradius=9),
            text=[f"${v:,.0f}<br>{n:,} buyers" for v, n in zip(seg["total_revenue"], seg["customers"])],
            textposition="outside", textfont=dict(color=INK, size=12), cliponaxis=False,
        ))
        fig.update_yaxes(title_text="Total revenue",
                         range=[0, float(seg["total_revenue"].max()) * 1.22])
        fig.update_layout(barcornerradius=9)
        st.plotly_chart(style_fig(fig, 330), width="stretch", config={"displayModeBar": False})
        champ = seg[seg["segment"] == "Champions"].iloc[0]
        insight(f"""
          <b>Champions</b> are {champ['pct_of_customers']:.0f}% of buyers but
          {champ['pct_of_revenue']:.0f}% of revenue. <b>At risk</b> customers went quiet ~4 months ago
          &mdash; the highest-ROI win-back target.""")

    with right2:
        mini(BEAN_ICON, "How the segments cluster (RFM)")
        rfm = d["rfm"]
        fig = go.Figure()
        for s in ["Champions", "Loyal", "At risk", "New"]:
            part = rfm[rfm["segment"] == s]
            fig.add_trace(go.Scatter(
                x=part["recency"], y=part["monetary"], mode="markers", name=s,
                marker=dict(color=SEGMENT_COLORS[s], size=7, opacity=0.5, line=dict(width=0)),
            ))
        fig.update_xaxes(title_text="Recency (days since last order)")
        fig.update_yaxes(title_text="Monetary (total spend $)")
        st.plotly_chart(style_fig(fig, 330), width="stretch", config={"displayModeBar": False})
        insight(f"""
          Each dot is one of {len(rfm):,} purchasing customers; {d['n_prospects']:,} never-purchased
          prospects are held out. k-means grouped these by similarity &mdash; notice At risk drifting
          right (gone quiet).""")

# --- footer / colophon -----------------------------------------------------
st.markdown(h(f"""
<div class="pc-anchor" id="pc-colophon" data-label="About"></div>
<div class="pc-footer">
  {TORN.format(cls="top", fill="#F6EFF6")}
  <div class="wrap">
    <div>
      <h4>About this cup</h4>
      <p><b>The Purple Cup</b> is a fictional brand and every figure here is simulated data built for a
        portfolio project &mdash; it is not real customer data. The analysis, though, is the real thing:
        SQL over a normalized SQLite schema, funnel &amp; conversion analysis, first / last / linear
        attribution, a two-proportion z-test, and RFM + k-means segmentation.</p>
      <p style="opacity:.75;">Recency snapshot: {d['snapshot']}.</p>
      <div class="sig">&mdash; Erica Mathias</div>
    </div>
    <div>
      <h4>Brewed with</h4>
      <div class="tags">
        <span>Python</span><span>pandas</span><span>SQLite</span><span>SciPy</span>
        <span>scikit-learn</span><span>Streamlit</span><span>Plotly</span>
      </div>
      <p class="pad">Scroll and the iced coffee empties &mdash; the glass follows you down the page
        as a reading meter, the numbers count up, the sections arrive, and the beans drift.
        All of it is one small scroll engine, no libraries.</p>
    </div>
  </div>
</div>
"""), unsafe_allow_html=True)

# Scroll engine (zero-height iframe so its script can run against the page).
components.html(ENGINE, height=0)
