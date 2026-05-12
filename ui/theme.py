# ui/theme.py
# Application colour themes — injected once per page render via apply_theme().
#
# Dark  (default): no CSS injected — page-level CSS already uses dark styles.
# Dark Slate / Light: !important overrides applied on top of page-level CSS.
#
# Usage:
#   from ui.theme import apply_theme
#   apply_theme()   # call once near the top of each page, after apply_auth_gate()
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Theme registry
# ─────────────────────────────────────────────────────────────────────────────

THEME_OPTIONS: dict[str, str] = {
    "dark":       "🌙 Dark",
    "dark_slate": "🌑 Dark Slate",
    "light":      "☀️ Light",
}

DEFAULT_THEME = "dark"

# ─────────────────────────────────────────────────────────────────────────────
# Palette definitions
# ─────────────────────────────────────────────────────────────────────────────

_P: dict[str, dict] = {
    "dark": {
        # Dark is the default — no override CSS needed.
        # Page-level CSS already defines these values.
    },
    "dark_slate": {
        "bg0":         "#0d0d1a",
        "bg1":         "#1a1a2e",
        "bg2":         "#16213e",
        "bg3":         "#0f1726",
        "border":      "#2d2d4e",
        "border2":     "#3d3d6e",
        "text0":       "#e8e8f0",
        "text1":       "#9898b8",
        "text2":       "#7878a8",
        "text3":       "#6060a0",
        "accent":      "#6366f1",
        "accent_hex":  "99,102,241",
        "accent_soft": "rgba(99,102,241,.15)",
        "num_bg":      "#2d2d4e",
        "footer":      "#2d2d5e",
        "grad_a":      "#0d0d1a",
        "grad_b":      "#16213e",
        "grad_c":      "#1a1a2e",
    },
    "light": {
        "bg0":         "#f8fafc",
        "bg1":         "#ffffff",
        "bg2":         "#f1f5f9",
        "bg3":         "#e9f0f8",
        "border":      "#e2e8f0",
        "border2":     "#cbd5e1",
        "text0":       "#1e293b",
        "text1":       "#475569",
        "text2":       "#64748b",
        "text3":       "#94a3b8",
        "accent":      "#C97B1A",
        "accent_hex":  "201,123,26",
        "accent_soft": "rgba(201,123,26,.10)",
        "num_bg":      "#e2e8f0",
        "footer":      "#94a3b8",
        "grad_a":      "#e9f0f8",
        "grad_b":      "#f1f5f9",
        "grad_c":      "#ffffff",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CSS builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_css(p: dict) -> str:
    return f"""
<style>
/* ═══════════════════════════════════════════════════════════
   PROCESS2DIAGRAM THEME OVERRIDE
   ═══════════════════════════════════════════════════════════ */

/* ── Streamlit app shell ─────────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
.main .block-container {{
    background-color: {p["bg0"]} !important;
}}
[data-testid="stSidebar"] {{
    background-color: {p["bg1"]} !important;
    border-right: 1px solid {p["border"]} !important;
}}
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span:not(.role-badge),
[data-testid="stSidebar"] p {{
    color: {p["text0"]} !important;
}}
[data-testid="stHeader"] {{
    background-color: {p["bg0"]} !important;
}}

/* ── Global text ─────────────────────────────────────────── */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
h1, h2, h3 {{
    color: {p["text0"]} !important;
}}
.stMarkdown p, .stMarkdown li {{
    color: {p["text1"]} !important;
}}
.stMarkdown a {{
    color: {p["accent"]} !important;
}}
label, .stCheckbox span, .stRadio span {{
    color: {p["text1"]} !important;
}}
.stCaption, small {{
    color: {p["text2"]} !important;
}}

/* ── Inputs ──────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {{
    background-color: {p["bg1"]} !important;
    color: {p["text0"]} !important;
    border-color: {p["border"]} !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: {p["accent"]} !important;
    box-shadow: 0 0 0 2px rgba({p["accent_hex"]},.2) !important;
}}

/* ── Selectbox ───────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {{
    background-color: {p["bg1"]} !important;
    border-color: {p["border"]} !important;
}}
[data-baseweb="select"] span,
[data-baseweb="select"] div {{
    color: {p["text0"]} !important;
}}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="menu"] {{
    background-color: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
}}
[data-baseweb="menu"] li,
[data-baseweb="menu"] li span {{
    color: {p["text0"]} !important;
}}
[data-baseweb="menu"] li:hover {{
    background-color: {p["bg2"]} !important;
}}

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {{
    background-color: {p["bg2"]} !important;
    color: {p["text0"]} !important;
    border: 1px solid {p["border"]} !important;
}}
.stButton > button:hover {{
    border-color: {p["accent"]} !important;
    color: {p["accent"]} !important;
}}

/* ── Expanders ───────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background-color: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
}}
.streamlit-expanderHeader,
[data-testid="stExpanderToggleIcon"] {{
    color: {p["text0"]} !important;
    background-color: {p["bg1"]} !important;
}}

/* ── Tabs ────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {{
    background-color: {p["bg0"]} !important;
    border-bottom: 1px solid {p["border"]} !important;
}}
[data-baseweb="tab"] {{
    color: {p["text2"]} !important;
    background-color: transparent !important;
}}
[aria-selected="true"][data-baseweb="tab"] {{
    color: {p["accent"]} !important;
}}
[data-baseweb="tab-highlight"] {{
    background-color: {p["accent"]} !important;
}}

/* ── Metrics ─────────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background-color: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    border-radius: 10px !important;
}}
[data-testid="stMetricLabel"] span {{
    color: {p["text2"]} !important;
}}
[data-testid="stMetricValue"] div {{
    color: {p["text0"]} !important;
}}

/* ── Dataframe ───────────────────────────────────────────── */
[data-testid="stDataFrame"],
.stDataFrame {{
    background-color: {p["bg1"]} !important;
}}

/* ── Info / Warning / Success boxes ─────────────────────── */
[data-testid="stInfo"],
[data-testid="stWarning"],
[data-testid="stSuccess"],
[data-testid="stError"] {{
    background-color: {p["bg1"]} !important;
    border-color: {p["border"]} !important;
}}

/* ══════════════════════════════════════════════════════════
   OUR CUSTOM HTML COMPONENTS
   ══════════════════════════════════════════════════════════ */

/* ── Home: header ────────────────────────────────────────── */
.home-header {{
    background: linear-gradient(135deg, {p["grad_a"]} 0%, {p["grad_b"]} 55%, {p["grad_c"]} 100%) !important;
    border-bottom: 2px solid {p["accent"]} !important;
}}
.home-header .greeting {{ color: {p["text0"]} !important; }}
.home-header .sub       {{ color: {p["text2"]} !important; }}
.home-header .brand-badge {{ color: {p["accent"]} !important; }}

/* ── Home: KPI cards ─────────────────────────────────────── */
.kpi-card {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.08) !important;
}}
.kpi-card .kpi-num {{ color: {p["text0"]} !important; }}
.kpi-card .kpi-lbl {{ color: {p["text2"]} !important; }}

/* ── Home: section header ────────────────────────────────── */
.section-hdr {{
    color: {p["text2"]} !important;
}}
.section-hdr::after {{
    background: linear-gradient(90deg, {p["border"]} 0%, transparent 100%) !important;
}}

/* ── Home: flow steps ────────────────────────────────────── */
.flow-step {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.06) !important;
}}
.flow-step .step-title {{ color: {p["text0"]} !important; }}
.flow-step .step-desc  {{ color: {p["text2"]} !important; }}
.flow-arrow            {{ color: {p["accent"]} !important; }}

/* ── Home: area cards ────────────────────────────────────── */
.area-card {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.06) !important;
}}
.area-card .area-title {{
    color: {p["accent"]} !important;
}}
.area-card .area-title::after {{
    background: {p["border"]} !important;
}}

/* ── Home: meeting cards ─────────────────────────────────── */
.mtg-card {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    border-left: 3px solid {p["border2"]} !important;
    box-shadow: 0 2px 8px rgba(0,0,0,.06) !important;
}}
.mtg-card:hover {{ border-left-color: {p["accent"]} !important; }}
.mtg-card .mtg-num   {{ color: {p["accent"]} !important; }}
.mtg-card .mtg-title {{ color: {p["text0"]} !important; }}
.mtg-card .mtg-meta  {{ color: {p["text2"]} !important; }}

/* ── Home: footer ────────────────────────────────────────── */
.home-footer {{
    border-top: 1px solid {p["border"]} !important;
    color: {p["footer"]} !important;
}}

/* ── ComoIniciar: guide header ───────────────────────────── */
.guide-header {{
    background: linear-gradient(135deg, {p["grad_a"]} 0%, {p["grad_b"]} 55%, {p["grad_c"]} 100%) !important;
    border-bottom: 3px solid {p["accent"]} !important;
    box-shadow: 0 4px 24px rgba(0,0,0,.12) !important;
}}
.guide-header .gh-title {{ color: {p["text0"]} !important; }}
.guide-header .gh-sub   {{ color: {p["text2"]} !important; }}

/* ── ComoIniciar: section header ─────────────────────────── */
.g-section-hdr {{ color: {p["text2"]} !important; }}
.g-section-hdr::after {{
    background: linear-gradient(90deg, {p["border"]} 0%, transparent 100%) !important;
}}

/* ── ComoIniciar: feature pills ──────────────────────────── */
.feat-pill {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    color: {p["text0"]} !important;
}}

/* ── ComoIniciar: step cards ─────────────────────────────── */
.step-card {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    box-shadow: 0 2px 10px rgba(0,0,0,.06) !important;
}}
.step-card .sc-title {{ color: {p["text0"]} !important; }}
.step-card .sc-body  {{ color: {p["text1"]} !important; }}
.step-card .sc-tip {{
    background: {p["accent_soft"]} !important;
    border-left-color: {p["accent"]} !important;
    color: {p["text1"]} !important;
}}

/* ── ComoIniciar: page grid items ────────────────────────── */
.page-item {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
    box-shadow: 0 2px 8px rgba(0,0,0,.06) !important;
}}
.page-item .pi-name  {{ color: {p["text0"]} !important; }}
.page-item .pi-desc  {{ color: {p["text2"]} !important; }}
.page-item .pi-group {{
    color: {p["accent"]} !important;
    background: {p["accent_soft"]} !important;
}}

/* ── ComoIniciar: info boxes ─────────────────────────────── */
.info-box {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
}}
.info-box .ib-title {{ color: {p["accent"]} !important; }}

/* ── ComoIniciar: tip rows ───────────────────────────────── */
.tip-row {{
    background: {p["bg1"]} !important;
    border: 1px solid {p["border"]} !important;
}}
.tip-row .tip-num {{
    background: {p["num_bg"]} !important;
    color: {p["accent"]} !important;
}}
.tip-row .tip-txt {{ color: {p["text1"]} !important; }}

</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# CSS cache (built once per theme per process)
# ─────────────────────────────────────────────────────────────────────────────

_CSS_CACHE: dict[str, str] = {}


def _get_css(theme: str) -> str:
    if theme not in _CSS_CACHE:
        palette = _P.get(theme)
        _CSS_CACHE[theme] = _build_css(palette) if palette else ""
    return _CSS_CACHE[theme]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def apply_theme() -> None:
    """Inject theme CSS into the current page.
    Call once per page render, after apply_auth_gate().
    For the default 'dark' theme no CSS is injected (page CSS already handles it).
    """
    import streamlit as st
    theme = st.session_state.get("app_theme", DEFAULT_THEME)
    css = _get_css(theme)
    if css:
        st.markdown(css, unsafe_allow_html=True)
