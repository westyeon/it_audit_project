"""
AI 기반 IT감사 사전 통제 점검 시스템 v4
"""

import os, sys, subprocess, json, glob, re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

# ── 경로 ──────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, "data", "processed")
DB_DIR       = os.path.join(DATA_DIR, "virtual_db")
SRC_DIR      = os.path.join(BASE_DIR, "src")
SUMMARY_PATH = os.path.join(DATA_DIR, "violations_summary.csv")
REPORT_DIR   = os.path.join(DATA_DIR, "report")

DOMAIN_ORDER  = ["접근통제", "변경관리", "운영통제"]
DOMAIN_COLORS = {"접근통제": "#3b82f6", "변경관리": "#f59e0b", "운영통제": "#10b981"}
DOMAIN_ICON   = {"접근통제": "🔐", "변경관리": "🔄", "운영통제": "⚙️"}
DOMAIN_LOG_MAP = {"접근통제": "access_log.csv", "변경관리": "deploy_log.csv",
                  "운영통제": "backup_log.csv"}
SEV_COLORS    = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}

def _detect_months():
    files  = glob.glob(os.path.join(DATA_DIR, "violations_summary_????-??.csv"))
    months = sorted({re.search(r"(\d{4}-\d{2})", os.path.basename(f)).group(1)
                     for f in files if re.search(r"(\d{4}-\d{2})", f)})
    return months if months else ["2025-11"]

AVAILABLE_MONTHS = _detect_months()
MONTH_LABELS     = {m: datetime.strptime(m, "%Y-%m").strftime("%Y년 %m월")
                    for m in AVAILABLE_MONTHS}

# ── 페이지 설정 ────────────────────────────────────────────────
st.set_page_config(
    page_title="AI IT감사 점검 시스템",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── 사이드바: 다크 네이비 ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
}
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span {
    color: rgba(255,255,255,0.85) !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div > div,
section[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: rgba(255,255,255,0.08) !important;
    border-color: rgba(255,255,255,0.2) !important;
    color: white !important;
}
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12); }

/* ── 메인 영역 배경 ── */
.main .block-container {
    padding: 0.7rem 1.1rem 0.8rem !important;
    max-width: 100% !important;
}

/* ── 카드 ── */
.dash-card {
    background: white;
    border-radius: 12px;
    padding: 0.85rem 1rem 0.6rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    margin-bottom: 0.55rem;
}
.card-title {
    font-size: 0.8rem; font-weight: 700; color: #475569;
    text-transform: uppercase; letter-spacing: 0.06em;
    margin-bottom: 0.5rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid #e2e8f0;
}

/* ── KPI 카드 ── */
.kpi-row { display: flex; gap: 0.55rem; margin-bottom: 0.55rem; }
.kpi-box {
    flex: 1; background: white; border-radius: 12px;
    padding: 0.9rem 1rem 0.7rem;
    box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    border-top: 3px solid var(--accent);
}
.kpi-box .val { font-size: 2.1rem; font-weight: 900; color: var(--accent); line-height: 1; }
.kpi-box .lbl { font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; font-weight: 600; }
.kpi-box .dl  { font-size: 0.72rem; margin-top: 0.15rem; }
.kpi-box .dl.up   { color: #10b981; }
.kpi-box .dl.down { color: #ef4444; }

/* ── 사이드바 네비 버튼 ── */
.nav-item {
    display: block; padding: 0.45rem 0.75rem;
    border-radius: 8px; margin: 2px 0;
    font-size: 0.85rem; font-weight: 500;
    color: rgba(255,255,255,0.65) !important;
    cursor: pointer; transition: all 0.15s;
}
.nav-item:hover  { background: rgba(255,255,255,0.08); color: white !important; }
.nav-item.active { background: rgba(59,130,246,0.35) !important;
                   color: white !important; font-weight: 700;
                   border-left: 3px solid #3b82f6; }

/* ── 섹션 헤더 ── */
.view-header {
    font-size: 1.1rem; font-weight: 800; color: #0f172a;
    margin-bottom: 0.5rem; letter-spacing: -0.02em;
}
.view-sub { font-size: 0.8rem; color: #94a3b8; margin-top: -0.3rem; margin-bottom: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────
_defaults = {
    "view":           "overview",
    "selected_month": AVAILABLE_MONTHS[-1],
    "filter_domains": DOMAIN_ORDER,
    "filter_sevs":    ["HIGH", "MEDIUM", "LOW"],
    "scan_state":     "idle",
    "last_scan":      None,
    "ai_insights":    None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ════════════════════════════════════════════════════════════════
# 데이터 함수
# ════════════════════════════════════════════════════════════════
@st.cache_data(ttl=30)
def load_summary(month=None):
    path = (os.path.join(DATA_DIR, f"violations_summary_{month}.csv") if month
            else SUMMARY_PATH)
    return pd.read_csv(path, encoding="utf-8-sig") if os.path.exists(path) else None

@st.cache_data
def load_all_monthly():
    frames = []
    for m in AVAILABLE_MONTHS:
        path = os.path.join(DATA_DIR, f"violations_summary_{m}.csv")
        if os.path.exists(path):
            d = pd.read_csv(path, encoding="utf-8-sig")
            d["month"] = m; d["month_label"] = MONTH_LABELS[m]
            frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else None

@st.cache_data
def load_db(fname):
    p = os.path.join(DB_DIR, fname)
    return pd.read_csv(p, encoding="utf-8-sig") if os.path.exists(p) else pd.DataFrame()

@st.cache_data
def get_log_range():
    df = load_db("access_log.csv")
    if df.empty: return "-", "-"
    df["access_dt"] = pd.to_datetime(df["access_dt"], errors="coerce")
    return df["access_dt"].min().strftime("%Y.%m.%d"), df["access_dt"].max().strftime("%Y.%m.%d")

@st.cache_data
def get_rules_count():
    p = os.path.join(DATA_DIR, "rules.json")
    if not os.path.exists(p): return 0
    with open(p, encoding="utf-8") as f: return len(json.load(f))

def calc_scores(df):
    s = {}
    for d in DOMAIN_ORDER:
        sub = df[df["audit_domain"] == d]
        mx = sub["severity_score"].sum(); ac = sub["risk_deduction"].sum()
        s[d] = round(100 * (1 - ac / mx)) if mx else 100
    return s

def grade(sc):
    if sc < 60:   return "고위험", "#ef4444"
    elif sc < 80: return "주의",   "#f59e0b"
    else:         return "정상",   "#10b981"

def calc_matrix(df):
    rows = []
    for d in DOMAIN_ORDER:
        sub   = df[df["audit_domain"] == d]; total = len(sub)
        pass_ = (sub["yn_violation"] == "N").sum()
        design = round(pass_ / total * 100, 1) if total else 0
        log_df = load_db(DOMAIN_LOG_MAP.get(d, "")); tl = len(log_df)
        vl     = int(sub["violation_count"].sum())
        ops    = round(max(0, (1 - vl / tl) * 100), 1) if tl > 0 else 100.0
        rows.append({"도메인": d, "설계적합성": design, "운영유효성": ops,
                     "위반규칙": total - pass_, "전체규칙": total, "위반건수": vl})
    return pd.DataFrame(rows)

def apply_filters(df, domains, sevs):
    return df[df["audit_domain"].isin(domains) & df["severity"].isin(sevs)]

def monthly_score(trend_df, m, domains):
    sub = trend_df[trend_df["month"] == m]
    if sub.empty: return None
    sub = sub[sub["audit_domain"].isin(domains)]
    sc = {}
    for d in domains:
        ds = sub[sub["audit_domain"] == d]
        mx = ds["severity_score"].sum(); ac = ds["risk_deduction"].sum()
        sc[d] = round(100 * (1 - ac / mx)) if mx else 100
    return round(sum(sc.values()) / len(sc)) if sc else None

def hex_rgba(h, a=0.12):
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return f"rgba({r},{g},{b},{a})"


# ════════════════════════════════════════════════════════════════
# 공통 차트 헬퍼
# ════════════════════════════════════════════════════════════════
def gauge_fig(scores, height=220):
    fig = go.Figure()
    for i, d in enumerate(DOMAIN_ORDER):
        s = scores.get(d, 100)
        _, gc = grade(s)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=s,
            title={"text": f"<b>{d}</b>", "font": {"size": 12}},
            number={"suffix": "점", "font": {"size": 26, "color": gc}},
            gauge={
                "axis": {"range": [0, 100], "tickvals": [0, 60, 80, 100]},
                "bar": {"color": gc, "thickness": 0.28},
                "bgcolor": "white", "borderwidth": 0,
                "steps": [{"range": [0, 60],  "color": "#fef2f2"},
                           {"range": [60, 80], "color": "#fffbeb"},
                           {"range": [80, 100],"color": "#f0fdf4"}],
            },
            domain={"x": [i / 3 + 0.01, (i + 1) / 3 - 0.01], "y": [0, 1]},
        ))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=5),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig

def trend_fig(trend_df, domains, height=240):
    rows = []
    for m in AVAILABLE_MONTHS:
        sub = trend_df[trend_df["month"] == m]
        if sub.empty: continue
        for d in domains:
            ds = sub[sub["audit_domain"] == d]
            mx = ds["severity_score"].sum(); ac = ds["risk_deduction"].sum()
            sc = round(100 * (1 - ac / mx)) if mx else 100
            rows.append({"월": MONTH_LABELS[m], "도메인": d, "점수": sc})
    if not rows:
        return go.Figure()
    df_t = pd.DataFrame(rows)
    fig  = go.Figure()
    for d in domains:
        sub = df_t[df_t["도메인"] == d]
        col = DOMAIN_COLORS.get(d, "#666")
        fig.add_trace(go.Scatter(
            x=sub["월"], y=sub["점수"], name=d,
            mode="lines+markers",
            line=dict(color=col, width=2.5, shape="spline"),
            marker=dict(size=7, color="white", line=dict(color=col, width=2.5)),
            fill="tozeroy", fillcolor=hex_rgba(col, 0.06),
            hovertemplate=f"<b>{d}</b>: %{{y}}점<extra></extra>",
        ))
    fig.add_hrect(y0=0,  y1=60, fillcolor="rgba(239,68,68,0.05)",  line_width=0)
    fig.add_hrect(y0=60, y1=80, fillcolor="rgba(245,158,11,0.05)", line_width=0)
    fig.add_hline(y=80, line_dash="dot", line_color="#f59e0b", line_width=1,
                  annotation_text="80", annotation_font_color="#f59e0b",
                  annotation_position="left")
    fig.add_hline(y=60, line_dash="dot", line_color="#ef4444", line_width=1,
                  annotation_text="60", annotation_font_color="#ef4444",
                  annotation_position="left")
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=15, t=10, b=10),
        legend=dict(orientation="h", y=1.12, font=dict(size=11),
                    bgcolor="rgba(0,0,0,0)"),
        yaxis=dict(range=[50, 105], showgrid=True, gridcolor="#f1f5f9",
                   tickfont=dict(size=10)),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig

def heatmap_fig(df, height=200):
    heat = (df[df["yn_violation"] == "Y"]
            .groupby(["audit_domain", "severity"]).size()
            .reset_index(name="건수"))
    pivot = (heat.pivot(index="severity", columns="audit_domain", values="건수")
             .reindex(["HIGH", "MEDIUM", "LOW"])
             .reindex(columns=DOMAIN_ORDER, fill_value=0).fillna(0))
    fig = px.imshow(pivot, color_continuous_scale="Blues",
                    text_auto=True, aspect="auto", height=height)
    fig.update_traces(textfont_size=15, textfont_color="white")
    fig.update_layout(margin=dict(l=0, r=0, t=5, b=0),
                      coloraxis_showscale=False,
                      plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(tickfont=dict(size=11)),
                      yaxis=dict(tickfont=dict(size=11)))
    return fig

def top_bar_fig(df, n=8, height=230):
    top = (df[df["yn_violation"] == "Y"]
           .nlargest(n, "violation_count")
           [["rule_nm", "severity", "violation_count"]])
    fig = go.Figure()
    for sev in ["HIGH", "MEDIUM", "LOW"]:
        sub = top[top["severity"] == sev]
        if sub.empty: continue
        fig.add_trace(go.Bar(
            x=sub["violation_count"], y=sub["rule_nm"],
            orientation="h", name=sev,
            marker_color=SEV_COLORS[sev],
            text=sub["violation_count"],
            textposition="outside", textfont=dict(size=10),
        ))
    fig.update_layout(
        barmode="overlay", height=height,
        margin=dict(l=0, r=40, t=5, b=5),
        legend=dict(orientation="h", y=1.1, traceorder="reversed",
                    font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed", tickfont=dict(size=9)),
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
    )
    return fig

def domain_bar_fig(df, height=200):
    ddf = (df.groupby("audit_domain")
           .agg(위반=("yn_violation", lambda x: (x == "Y").sum()),
                이상없음=("yn_violation", lambda x: (x == "N").sum()))
           .reindex(DOMAIN_ORDER).reset_index())
    fig = go.Figure()
    fig.add_bar(name="이상없음", x=ddf["audit_domain"], y=ddf["이상없음"],
                marker_color="#bfdbfe", text=ddf["이상없음"],
                textposition="inside", textfont=dict(color="#1e3a5f", size=12))
    fig.add_bar(name="위반", x=ddf["audit_domain"], y=ddf["위반"],
                marker_color="#ef4444", text=ddf["위반"],
                textposition="inside", textfont=dict(color="white", size=12))
    fig.update_traces(texttemplate="%{text}개")
    fig.update_layout(
        barmode="stack", height=height,
        margin=dict(l=0, r=0, t=5, b=5),
        legend=dict(orientation="h", y=1.12, font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=10)),
        xaxis=dict(tickfont=dict(size=11)),
    )
    return fig

def scatter_matrix_fig(matrix, scores, height=220):
    fig = go.Figure()
    for (x0,x1,y0,y1,col,lbl) in [
        (0,50,0,50,"#fef2f2","구조적 문제"), (50,100,0,50,"#fffbeb","운영 실패"),
        (0,50,50,100,"#eff6ff","Rule 보완"), (50,100,50,100,"#f0fdf4","정상")]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=col, line_width=0, layer="below")
        fig.add_annotation(x=(x0+x1)/2, y=(y0+y1)/2, text=f"<b>{lbl}</b>",
                           showarrow=False, font=dict(size=9, color="#aaa"))
    for _, row in matrix.iterrows():
        col = DOMAIN_COLORS.get(row["도메인"], "#666")
        fig.add_trace(go.Scatter(
            x=[row["설계적합성"]], y=[row["운영유효성"]],
            mode="markers+text",
            marker=dict(size=28, color=col, opacity=0.9,
                        line=dict(width=2, color="white")),
            text=[row["도메인"]], textposition="top center",
            textfont=dict(size=10, color=col), name=row["도메인"],
            hovertemplate=(f"<b>{row['도메인']}</b><br>"
                           f"설계: {row['설계적합성']}% / 운영: {row['운영유효성']}%"
                           f"<extra></extra>"),
        ))
    fig.add_vline(x=50, line_dash="dash", line_color="#cbd5e1", line_width=1)
    fig.add_hline(y=50, line_dash="dash", line_color="#cbd5e1", line_width=1)
    fig.update_layout(
        height=height,
        xaxis=dict(title="설계 적합성 (%)", range=[0, 105],
                   showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=10)),
        yaxis=dict(title="운영 유효성 (%)", range=[0, 105],
                   showgrid=True, gridcolor="#f1f5f9", tickfont=dict(size=10)),
        showlegend=False,
        margin=dict(l=40, r=10, t=5, b=30),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ════════════════════════════════════════════════════════════════
# KPI 행 (HTML)
# ════════════════════════════════════════════════════════════════
def render_kpis(df, scores, prev_df=None):
    avg = round(sum(scores.values()) / len(scores))
    viol = int((df["yn_violation"] == "Y").sum())
    high = int(((df["severity"] == "HIGH") & (df["yn_violation"] == "Y")).sum())
    clean = len(df) - viol
    g_lbl, g_col = grade(avg)

    def delta_html(curr, prev_df_col, label=""):
        if prev_df_col is None: return ""
        diff = curr - prev_df_col
        if diff == 0: return f"<div class='dl'>— 전월 동일</div>"
        cls = "up" if diff > 0 else "down"
        sym = "▲" if diff > 0 else "▼"
        return f"<div class='dl {cls}'>{sym} {abs(diff)}{label} 전월 대비</div>"

    prev_avg = prev_viol = prev_high = prev_clean = None
    if prev_df is not None and not prev_df.empty:
        ps = calc_scores(prev_df)
        prev_avg   = round(sum(ps.values()) / len(ps))
        prev_viol  = int((prev_df["yn_violation"] == "Y").sum())
        prev_high  = int(((prev_df["severity"] == "HIGH") & (prev_df["yn_violation"] == "Y")).sum())
        prev_clean = len(prev_df) - prev_viol

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, avg,   "종합 리스크 점수", g_col,    delta_html(avg,   prev_avg,   "점"), "점"),
        (c2, viol,  "위반 탐지 규칙",   "#ef4444", delta_html(viol,  prev_viol,  "개"), "개"),
        (c3, high,  "HIGH 위반",        "#f59e0b", delta_html(high,  prev_high,  "개"), "개"),
        (c4, clean, "이상 없음",         "#10b981", delta_html(clean, prev_clean, "개"), "개"),
    ]
    for col, val, lbl, color, dl_html, suf in cards:
        with col:
            st.markdown(
                f"<div class='kpi-box' style='--accent:{color};'>"
                f"<div class='val'>{val}{suf}</div>"
                f"<div class='lbl'>{lbl}</div>"
                f"{dl_html}"
                f"</div>",
                unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        # 로고
        st.markdown("""
        <div style='padding:0.8rem 0 1rem;'>
          <div style='font-size:1.3rem;font-weight:900;color:white;
                      letter-spacing:-0.03em;'>🛡 IT감사 시스템</div>
          <div style='font-size:0.72rem;color:rgba(255,255,255,0.45);
                      margin-top:2px;'>AI-Powered Audit Control</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<hr style='margin:0 0 0.8rem;'>", unsafe_allow_html=True)

        # 분석 월
        st.markdown("<div style='font-size:0.72rem;color:rgba(255,255,255,0.45);"
                    "font-weight:600;letter-spacing:0.08em;margin-bottom:0.3rem;'>"
                    "📅  분석 월</div>", unsafe_allow_html=True)
        sel_month = st.selectbox(
            "month", AVAILABLE_MONTHS,
            index=AVAILABLE_MONTHS.index(st.session_state.selected_month),
            format_func=lambda m: MONTH_LABELS[m],
            label_visibility="collapsed")
        if sel_month != st.session_state.selected_month:
            st.session_state.selected_month = sel_month
            st.rerun()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # 도메인 필터
        st.markdown("<div style='font-size:0.72rem;color:rgba(255,255,255,0.45);"
                    "font-weight:600;letter-spacing:0.08em;margin-bottom:0.3rem;'>"
                    "🔍  도메인 필터</div>", unsafe_allow_html=True)
        domains = st.multiselect("domains", DOMAIN_ORDER,
                                 default=st.session_state.filter_domains,
                                 label_visibility="collapsed")
        if not domains: domains = DOMAIN_ORDER
        st.session_state.filter_domains = domains

        # 심각도 필터
        st.markdown("<div style='font-size:0.72rem;color:rgba(255,255,255,0.45);"
                    "font-weight:600;letter-spacing:0.08em;"
                    "margin:0.5rem 0 0.3rem;'>⚡  심각도 필터</div>",
                    unsafe_allow_html=True)
        sevs = st.multiselect("sevs", ["HIGH", "MEDIUM", "LOW"],
                              default=st.session_state.filter_sevs,
                              label_visibility="collapsed")
        if not sevs: sevs = ["HIGH", "MEDIUM", "LOW"]
        st.session_state.filter_sevs = sevs

        st.markdown("<hr style='margin:0.8rem 0;'>", unsafe_allow_html=True)

        # 내비게이션
        st.markdown("<div style='font-size:0.72rem;color:rgba(255,255,255,0.45);"
                    "font-weight:600;letter-spacing:0.08em;margin-bottom:0.4rem;'>"
                    "NAVIGATION</div>", unsafe_allow_html=True)

        nav_items = [
            ("overview",  "📊  전체 개요"),
            ("access",    "🔐  접근통제"),
            ("change",    "🔄  변경관리"),
            ("ops",       "⚙️  운영통제"),
            ("analysis",  "🔬  심화 분석"),
            ("scan",      "▶  점검 실행"),
            ("report",    "📄  보고서 생성"),
        ]
        for key, label in nav_items:
            active = "active" if st.session_state.view == key else ""
            if st.button(label, key=f"nav_{key}",
                         use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.view = key
                st.rerun()

        st.markdown("<hr style='margin:0.8rem 0;'>", unsafe_allow_html=True)

        # 마지막 점검
        if st.session_state.last_scan:
            st.markdown(
                f"<div style='font-size:0.7rem;color:rgba(255,255,255,0.35);'>"
                f"마지막 점검<br>"
                f"<b style='color:rgba(255,255,255,0.6);'>{st.session_state.last_scan}</b></div>",
                unsafe_allow_html=True)

    return sel_month, domains, sevs


# ════════════════════════════════════════════════════════════════
# VIEW: 전체 개요
# ════════════════════════════════════════════════════════════════
def view_overview(month, domains, sevs):
    df = load_summary(month)
    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    fdf    = apply_filters(df, domains, sevs)
    scores = calc_scores(df)
    matrix = calc_matrix(df)

    # 이전 월 데이터
    m_idx    = AVAILABLE_MONTHS.index(month)
    prev_df  = load_summary(AVAILABLE_MONTHS[m_idx - 1]) if m_idx > 0 else None

    # 헤더
    st.markdown(f"<div class='view-header'>전체 개요</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>{MONTH_LABELS[month]} 기준 · "
                f"필터: {', '.join(domains)} / {', '.join(sevs)}</div>",
                unsafe_allow_html=True)

    # KPI
    render_kpis(fdf, {d: scores[d] for d in domains if d in scores}, prev_df)
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ROW 2: 트렌드 + 게이지
    c1, c2 = st.columns([1.6, 1])
    trend_df = load_all_monthly()

    with c1:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>월별 리스크 점수 트렌드</div>",
                    unsafe_allow_html=True)
        if trend_df is not None:
            st.plotly_chart(trend_fig(trend_df, domains, height=230),
                            width="stretch",
                            config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>도메인별 리스크 점수</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(gauge_fig({d: scores[d] for d in domains}, height=230),
                        width="stretch",
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ROW 3: 히트맵 + TOP 위반 + 도메인 현황
    c3, c4, c5 = st.columns([1, 1.3, 1])

    with c3:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>도메인 × 심각도 히트맵</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(heatmap_fig(fdf, height=200),
                        width="stretch",
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>위반 건수 TOP 8</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(top_bar_fig(fdf, n=8, height=200),
                        width="stretch",
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c5:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>설계 적합성 vs 운영 유효성</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(scatter_matrix_fig(
            matrix[matrix["도메인"].isin(domains)], scores, height=200),
            width="stretch", config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# VIEW: 도메인 상세 (접근통제 / 변경관리 / 운영통제)
# ════════════════════════════════════════════════════════════════
def view_domain(month, domain, sevs):
    df = load_summary(month)
    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    sub = apply_filters(df, [domain], sevs)
    scores = calc_scores(df)
    score  = scores.get(domain, 100)
    g_lbl, g_col = grade(score)
    violated = int((sub["yn_violation"] == "Y").sum())
    total    = len(sub)
    trend_df = load_all_monthly()

    st.markdown(f"<div class='view-header'>"
                f"{DOMAIN_ICON[domain]} {domain} 상세</div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>{MONTH_LABELS[month]} 기준 · "
                f"심각도 필터: {', '.join(sevs)}</div>", unsafe_allow_html=True)

    # KPI (도메인 전용)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div class='kpi-box' style='--accent:{g_col};'>"
                    f"<div class='val'>{score}점</div>"
                    f"<div class='lbl'>리스크 점수</div>"
                    f"<div class='dl' style='color:{g_col};font-weight:700;'>{g_lbl}</div>"
                    f"</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='kpi-box' style='--accent:#ef4444;'>"
                    f"<div class='val'>{violated}개</div>"
                    f"<div class='lbl'>위반 탐지 규칙</div></div>",
                    unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='kpi-box' style='--accent:#3b82f6;'>"
                    f"<div class='val'>{total}개</div>"
                    f"<div class='lbl'>점검 규칙 수</div></div>",
                    unsafe_allow_html=True)
    with c4:
        pass_rate = round((total - violated) / total * 100) if total else 0
        st.markdown(f"<div class='kpi-box' style='--accent:#10b981;'>"
                    f"<div class='val'>{pass_rate}%</div>"
                    f"<div class='lbl'>준수율</div></div>",
                    unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ROW 2: 트렌드 + 심각도 파이
    c1, c2 = st.columns([1.7, 1])
    with c1:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>월별 리스크 점수 트렌드</div>",
                    unsafe_allow_html=True)
        if trend_df is not None:
            st.plotly_chart(trend_fig(trend_df, [domain], height=230),
                            width="stretch",
                            config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>심각도별 위반 비율</div>",
                    unsafe_allow_html=True)
        pie_data = (sub[sub["yn_violation"] == "Y"]
                    .groupby("severity")["rule_id"].count()
                    .reindex(["HIGH", "MEDIUM", "LOW"]).fillna(0).reset_index())
        pie_data.columns = ["심각도", "건수"]
        total_v = int(pie_data["건수"].sum())
        fig_pie = go.Figure(go.Pie(
            labels=pie_data["심각도"], values=pie_data["건수"],
            hole=0.6,
            marker_colors=[SEV_COLORS.get(s, "#ccc") for s in pie_data["심각도"]],
            textinfo="label+percent", textfont=dict(size=11),
        ))
        fig_pie.update_layout(
            height=230, showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            annotations=[dict(text=f"<b>{total_v}개</b>", x=0.5, y=0.5,
                              font=dict(size=16), showarrow=False)],
        )
        st.plotly_chart(fig_pie, width="stretch",
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ROW 3: TOP 위반 + 규칙 테이블
    c3, c4 = st.columns([1, 1.2])
    with c3:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>위반 건수 TOP 8</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(top_bar_fig(sub, n=8, height=220),
                        width="stretch",
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>위반 규칙 목록</div>",
                    unsafe_allow_html=True)
        tbl = (sub[sub["yn_violation"] == "Y"]
               .sort_values("violation_count", ascending=False)
               [["rule_id", "rule_nm", "severity", "violation_count", "remediation"]]
               .rename(columns={"rule_id": "ID", "rule_nm": "규칙명",
                                 "severity": "등급", "violation_count": "건수",
                                 "remediation": "시정조치"}))
        st.dataframe(tbl, width="stretch", hide_index=True, height=220)
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# VIEW: 심화 분석 (노트북 분석 자동 반영)
# ════════════════════════════════════════════════════════════════
def view_analysis(month):
    import numpy as np

    df_sum  = load_summary(month)
    if df_sum is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    df_emp     = load_db("emp_master.csv")
    df_account = load_db("sys_account.csv")
    df_access  = load_db("access_log.csv")
    df_deploy  = load_db("deploy_log.csv")
    df_backup  = load_db("backup_log.csv")

    for df, cols in [
        (df_emp,     ["hire_dt","resign_dt"]),
        (df_account, ["last_review_dt","last_pw_change_dt"]),
        (df_access,  ["access_dt"]),
        (df_deploy,  ["deploy_dt"]),
        (df_backup,  ["backup_dt"]),
    ]:
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

    SYS_MAP = {"CRED":"신용평가시스템","PORTAL":"고객포털",
               "ERP":"경영관리시스템","DW":"데이터웨어하우스","DEVP":"ITSM"}
    for df in [df_account, df_access, df_deploy, df_backup]:
        if "system_cd" in df.columns:
            df["system_nm"] = df["system_cd"].map(SYS_MAP).fillna(df["system_cd"])

    st.markdown("<div class='view-header'>🔬 심화 분석</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>{MONTH_LABELS[month]} 기준 · DB 데이터 자동 분석</div>",
                unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📍 부서별 위험도", "👤 역할별 분석", "⚖️ 리스크 매트릭스", "📜 법령 준수율"])

    # ── 탭1: 부서별 위험도 히트맵 ────────────────────────────────
    with tab1:
        resigned_ids = set(df_emp[df_emp["yn_employed"]=="N"]["emp_id"])
        active_res = df_account[
            df_account["emp_id"].isin(resigned_ids) &
            (df_account["account_status"]=="active")
        ].merge(df_emp[["emp_id","dept_nm"]], on="emp_id", how="left")

        overdue = df_account[df_account["yn_overdue_review"]=="Y"].merge(
            df_emp[["emp_id","dept_nm"]], on="emp_id", how="left")

        after_h = df_access[df_access["yn_after_hours"]=="Y"].merge(
            df_emp[["emp_id","dept_nm"]], on="emp_id", how="left")

        r1 = active_res.groupby("dept_nm").size().rename("퇴사자계정")
        r2 = overdue.groupby("dept_nm").size().rename("권한검토초과")
        r3 = after_h.groupby("dept_nm").size().rename("시간외접속")

        dept_risk = pd.concat([r1, r2, r3], axis=1).fillna(0).astype(int)
        dept_risk["위험점수"] = dept_risk["퇴사자계정"]*3 + dept_risk["권한검토초과"]*2 + dept_risk["시간외접속"]
        dept_risk = dept_risk.sort_values("위험점수", ascending=False)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='dash-card'><div class='card-title'>부서별 위반 히트맵</div>",
                        unsafe_allow_html=True)
            heat = dept_risk[["퇴사자계정","권한검토초과","시간외접속"]].head(12)
            fig_h = go.Figure(go.Heatmap(
                z=heat.values, x=heat.columns.tolist(), y=heat.index.tolist(),
                colorscale="YlOrRd", text=heat.values,
                texttemplate="%{text}", textfont={"size":11},
                hovertemplate="%{y}<br>%{x}: %{z}건<extra></extra>",
            ))
            fig_h.update_layout(height=350, margin=dict(l=10,r=10,t=10,b=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'>부서별 종합 위험점수 TOP 10</div>",
                        unsafe_allow_html=True)
            top10 = dept_risk.head(10).reset_index()
            fig_b = go.Figure(go.Bar(
                x=top10["위험점수"], y=top10["dept_nm"],
                orientation="h",
                marker_color=["#ef4444" if s>=10 else "#f59e0b" if s>=5 else "#3b82f6"
                              for s in top10["위험점수"]],
                text=top10["위험점수"], textposition="outside",
            ))
            fig_b.update_layout(height=350, margin=dict(l=10,r=10,t=10,b=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                xaxis=dict(color="#94a3b8"),
                                yaxis=dict(color="#e2e8f0", autorange="reversed"),
                                font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'>부서별 위험점수 상세</div>",
                    unsafe_allow_html=True)
        st.dataframe(dept_risk.reset_index().rename(columns={"dept_nm":"부서명"}),
                     use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 탭2: 역할별 분석 ─────────────────────────────────────────
    with tab2:
        roles  = ["developer","operator","security","business"]
        labels = ["개발(developer)","운영(operator)","보안(security)","업무(business)"]

        ah_emp = df_access[df_access["yn_after_hours"]=="Y"][["emp_id"]].drop_duplicates()
        ah_emp = ah_emp.merge(df_emp[["emp_id","role_type"]], on="emp_id", how="left")
        ah_by  = ah_emp.groupby("role_type").size()

        od_emp = df_account[df_account["yn_overdue_review"]=="Y"][["emp_id"]].drop_duplicates()
        od_emp = od_emp.merge(df_emp[["emp_id","role_type"]], on="emp_id", how="left")
        od_by  = od_emp.groupby("role_type").size()

        ar_emp = df_account[
            df_account["emp_id"].isin(resigned_ids) & (df_account["account_status"]=="active")
        ][["emp_id"]].drop_duplicates()
        ar_emp = ar_emp.merge(df_emp[["emp_id","role_type"]], on="emp_id", how="left")
        ar_by  = ar_emp.groupby("role_type").size()

        role_df = pd.DataFrame({
            "시간외접속":   [ah_by.get(r,0) for r in roles],
            "권한검토초과": [od_by.get(r,0) for r in roles],
            "퇴사자계정":   [ar_by.get(r,0) for r in roles],
        }, index=labels)

        role_total = df_emp.groupby("role_type").size().reindex(roles, fill_value=0)
        all_viol   = set(ah_emp["emp_id"].dropna()) | set(od_emp["emp_id"].dropna())
        role_viol  = df_emp[df_emp["emp_id"].isin(all_viol)].groupby("role_type").size().reindex(roles, fill_value=0)
        role_rate  = (role_viol / role_total * 100).fillna(0).round(1)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='dash-card'><div class='card-title'>역할별 접근통제 위반 현황</div>",
                        unsafe_allow_html=True)
            fig_r = go.Figure()
            colors_r = ["#ef4444","#f59e0b","#9b59b6"]
            for i, (col, color) in enumerate(zip(role_df.columns, colors_r)):
                fig_r.add_trace(go.Bar(name=col, x=labels, y=role_df[col], marker_color=color))
            fig_r.update_layout(barmode="group", height=280,
                                margin=dict(l=10,r=10,t=10,b=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                legend=dict(font=dict(color="#e2e8f0")),
                                xaxis=dict(color="#94a3b8"),
                                yaxis=dict(color="#94a3b8"),
                                font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'>역할별 위반 관여 비율</div>",
                        unsafe_allow_html=True)
            fig_rate = go.Figure(go.Bar(
                x=labels, y=role_rate.values,
                marker_color=["#ef4444" if v>20 else "#f59e0b" if v>10 else "#3b82f6"
                              for v in role_rate.values],
                text=[f"{v}%" for v in role_rate.values],
                textposition="outside",
            ))
            fig_rate.update_layout(height=280, margin=dict(l=10,r=10,t=10,b=10),
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)",
                                   xaxis=dict(color="#94a3b8"),
                                   yaxis=dict(color="#94a3b8", title="비율 (%)"),
                                   font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_rate, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'>역할별 요약</div>",
                    unsafe_allow_html=True)
        summary = pd.DataFrame({
            "역할": labels,
            "전체인원": role_total.values,
            "위반관여": role_viol.values,
            "위반율(%)": role_rate.values,
        })
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 탭3: 리스크 점수화 매트릭스 ──────────────────────────────
    with tab3:
        sev_score = {"HIGH":3,"MEDIUM":2,"LOW":1}
        df_r = df_sum.copy()
        df_r["심각도점수"]   = df_r["severity"].map(sev_score).fillna(1)
        df_r["위반건수_log"] = np.log1p(df_r["violation_count"])
        df_r["위험점수"]     = (df_r["심각도점수"] * df_r["위반건수_log"]).round(2)
        df_r["위험점수"]     = df_r["위험점수"].where(df_r["yn_violation"]=="Y", 0)

        def risk_grade(s):
            if s>=8:   return "Critical"
            elif s>=5: return "High"
            elif s>=2: return "Medium"
            elif s>0:  return "Low"
            else:      return "이상없음"
        df_r["위험등급"] = df_r["위험점수"].apply(risk_grade)

        grade_colors = {"Critical":"#8B0000","High":"#ef4444",
                        "Medium":"#f59e0b","Low":"#3b82f6","이상없음":"#64748b"}

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='dash-card'><div class='card-title'>위험 등급별 규칙 분포</div>",
                        unsafe_allow_html=True)
            grade_order = ["Critical","High","Medium","Low","이상없음"]
            gcnt = df_r.groupby("위험등급").size().reindex(grade_order, fill_value=0)
            gcnt_nz = gcnt[gcnt>0]
            fig_pie = go.Figure(go.Pie(
                labels=gcnt_nz.index, values=gcnt_nz.values, hole=0.55,
                marker_colors=[grade_colors[g] for g in gcnt_nz.index],
                textinfo="label+value", textfont=dict(size=11),
            ))
            fig_pie.update_layout(height=280, showlegend=True,
                                  margin=dict(l=10,r=10,t=10,b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  legend=dict(font=dict(color="#e2e8f0")),
                                  font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'>고위험 규칙 TOP 10</div>",
                        unsafe_allow_html=True)
            top10r = df_r[df_r["위험점수"]>0].nlargest(10,"위험점수")
            fig_top = go.Figure(go.Bar(
                x=top10r["위험점수"][::-1],
                y=[f"{r} {n[:10]}" for r,n in zip(top10r["rule_id"][::-1],top10r["rule_nm"][::-1])],
                orientation="h",
                marker_color=[grade_colors[g] for g in top10r["위험등급"][::-1]],
                text=top10r["위험점수"][::-1].round(1), textposition="outside",
            ))
            fig_top.update_layout(height=280, margin=dict(l=10,r=10,t=10,b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)",
                                  xaxis=dict(color="#94a3b8"),
                                  yaxis=dict(color="#e2e8f0"),
                                  font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_top, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'>위험도 산점도 (심각도 × 위반건수)</div>",
                    unsafe_allow_html=True)
        viol_df = df_r[df_r["yn_violation"]=="Y"].copy()
        viol_df["jitter"] = np.random.uniform(-0.15, 0.15, len(viol_df))
        fig_sc = go.Figure(go.Scatter(
            x=viol_df["violation_count"],
            y=viol_df["심각도점수"] + viol_df["jitter"],
            mode="markers",
            marker=dict(
                color=[grade_colors[g] for g in viol_df["위험등급"]],
                size=10, opacity=0.8,
                line=dict(width=1, color="white"),
            ),
            text=viol_df["rule_nm"],
            hovertemplate="<b>%{text}</b><br>위반건수: %{x}<br><extra></extra>",
        ))
        fig_sc.update_layout(
            height=250, margin=dict(l=10,r=10,t=10,b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(type="log", title="위반 건수 (log)", color="#94a3b8",
                       gridcolor="rgba(148,163,184,0.1)"),
            yaxis=dict(tickvals=[1,2,3], ticktext=["LOW","MEDIUM","HIGH"],
                       color="#94a3b8", gridcolor="rgba(148,163,184,0.1)"),
            font=dict(color="#e2e8f0"),
        )
        st.plotly_chart(fig_sc, use_container_width=True, config={"displayModeBar":False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 탭4: 법령 준수율 ─────────────────────────────────────────
    with tab4:
        law_viol = df_sum[df_sum["yn_violation"]=="Y"].copy()
        law_total_cnt = df_sum.groupby("source_law").size()
        law_viol_cnt  = law_viol.groupby("source_law").size()
        law_comp = ((1 - law_viol_cnt/law_total_cnt)*100).round(1).reset_index()
        law_comp.columns = ["법령명","준수율(%)"]
        law_comp = law_comp.sort_values("준수율(%)")

        law_sum = law_viol.groupby("source_law").agg(
            위반규칙수=("rule_id","count"),
            총위반건수=("violation_count","sum"),
            HIGH건수=("severity", lambda x: (x=="HIGH").sum())
        ).reset_index().sort_values("위반규칙수", ascending=False)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='dash-card'><div class='card-title'>법령별 준수율</div>",
                        unsafe_allow_html=True)
            fig_comp = go.Figure(go.Bar(
                x=law_comp["준수율(%)"], y=law_comp["법령명"],
                orientation="h",
                marker_color=["#ef4444" if v<50 else "#f59e0b" if v<75 else "#10b981"
                              for v in law_comp["준수율(%)"]],
                text=[f"{v}%" for v in law_comp["준수율(%)"]],
                textposition="outside",
            ))
            fig_comp.update_layout(height=300, margin=dict(l=10,r=80,t=10,b=10),
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)",
                                   xaxis=dict(range=[0,115], color="#94a3b8"),
                                   yaxis=dict(color="#e2e8f0"),
                                   font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'>법령별 위반 규칙 수</div>",
                        unsafe_allow_html=True)
            fig_law = go.Figure(go.Bar(
                x=law_sum["위반규칙수"], y=law_sum["source_law"],
                orientation="h",
                marker_color=["#ef4444" if h>0 else "#3b82f6" for h in law_sum["HIGH건수"]],
                text=[f"{v}개" + (f" (HIGH {h})" if h>0 else "")
                      for v,h in zip(law_sum["위반규칙수"],law_sum["HIGH건수"])],
                textposition="outside",
            ))
            fig_law.update_layout(height=300, margin=dict(l=10,r=120,t=10,b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)",
                                  xaxis=dict(color="#94a3b8"),
                                  yaxis=dict(color="#e2e8f0"),
                                  font=dict(color="#e2e8f0"))
            st.plotly_chart(fig_law, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'>법령별 위반 현황 상세</div>",
                    unsafe_allow_html=True)
        st.dataframe(law_sum.rename(columns={"source_law":"법령명"}),
                     use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# VIEW: 점검 실행
# ════════════════════════════════════════════════════════════════
def view_scan(month):
    rules_count = get_rules_count()
    dt_from, dt_to = get_log_range()
    df_acc  = load_db("access_log.csv")
    df_dep  = load_db("deploy_log.csv")
    df_bak  = load_db("backup_log.csv")
    df_itsm = load_db("itsm_req.csv")
    total_logs = len(df_acc) + len(df_dep) + len(df_bak) + len(df_itsm)

    st.markdown("<div class='view-header'>▶ 점검 실행</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>분석 기간: {dt_from} ~ {dt_to}</div>",
                unsafe_allow_html=True)

    # 현황
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl, color in [
        (c1, f"{total_logs:,}건", "분석 대상 로그", "#3b82f6"),
        (c2, f"{rules_count}개", "점검 규칙",    "#6366f1"),
        (c3, dt_from,            "시작일",        "#10b981"),
        (c4, dt_to,              "종료일",        "#f59e0b"),
    ]:
        with col:
            st.markdown(f"<div class='kpi-box' style='--accent:{color};'>"
                        f"<div class='val' style='font-size:1.5rem;'>{val}</div>"
                        f"<div class='lbl'>{lbl}</div></div>",
                        unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # 영역 안내
    c1, c2, c3 = st.columns(3)
    c1.info("**🔐 접근통제**\n\n계정·권한·퇴직자 관리")
    c2.info("**🔄 변경관리**\n\nCR·배포·직무분리")
    c3.info("**⚙️ 운영통제**\n\n로그·백업·권한검토")

    # 월 선택
    st.markdown("---")
    sel_col, info_col = st.columns([1, 2])
    with sel_col:
        selected = st.selectbox("분석 월 선택", AVAILABLE_MONTHS,
                                index=AVAILABLE_MONTHS.index(month),
                                format_func=lambda m: MONTH_LABELS[m])
        if selected != st.session_state.selected_month:
            st.session_state.selected_month = selected
            st.session_state.scan_state = "idle"
            st.rerun()
    with info_col:
        already = os.path.exists(
            os.path.join(DATA_DIR, f"violations_summary_{selected}.csv"))
        if already:
            st.success(f"✅ {MONTH_LABELS[selected]} 점검 결과 있음 — 재검사 가능")
        else:
            st.info(f"📋 {MONTH_LABELS[selected]} 점검 결과 없음 — 검사를 실행해주세요")

    if st.session_state.scan_state == "idle":
        st.markdown(f"<p style='text-align:center;color:#64748b;margin:1rem 0;'>"
                    f"<b>{MONTH_LABELS[selected]}</b> 데이터를 점검합니다.</p>",
                    unsafe_allow_html=True)
        _, mid, _ = st.columns([2, 1, 2])
        with mid:
            if st.button("▶ 검사 시작", type="primary", use_container_width=True):
                st.session_state.scan_state = "running"
                st.rerun()

    elif st.session_state.scan_state == "running":
        st.markdown(f"<h4 style='text-align:center;color:#1a237e;'>"
                    f"🔄 {MONTH_LABELS[selected]} 점검 진행 중...</h4>",
                    unsafe_allow_html=True)
        bar = st.progress(0, text="Rule 엔진 초기화 중...")
        logs_box = st.empty(); logs = []
        proc = subprocess.Popen(
            [sys.executable, os.path.join(SRC_DIR, "rule_engine.py"),
             "--month", selected],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        rule_cnt = 0
        import re as _re
        for line in proc.stdout:
            line = line.rstrip()
            if not line: continue
            logs.append(line)
            if _re.search(r'\bR\d{3}\b', line):
                rule_cnt += 1
                pct = min(int(rule_cnt / max(rules_count, 1) * 100), 99)
                bar.progress(pct, text=f"점검 중... ({rule_cnt}/{rules_count}개 규칙)")
            logs_box.code("\n".join(logs[-12:]), language="")
        proc.wait()
        bar.progress(100, text="점검 완료!")
        load_summary.clear(); load_all_monthly.clear()
        st.session_state.scan_state = "done"
        st.session_state.last_scan  = datetime.now().strftime("%Y.%m.%d %H:%M")
        st.rerun()

    elif st.session_state.scan_state == "done":
        df = load_summary()
        violated = (df["yn_violation"] == "Y").sum() if df is not None else 0
        total    = len(df) if df is not None else 0
        st.success(f"✅ 점검 완료 — 총 **{total}개** 규칙 중 **{violated}개** 위반 탐지 "
                   f"({st.session_state.last_scan})")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 재검사", use_container_width=True):
                st.session_state.scan_state = "idle"; st.rerun()
        with c2:
            if st.button("📊 결과 보기", use_container_width=True, type="primary"):
                st.session_state.view = "overview"; st.rerun()


# ════════════════════════════════════════════════════════════════
# VIEW: 보고서
# ════════════════════════════════════════════════════════════════
def view_report(month):
    df = load_summary(month)
    st.markdown("<div class='view-header'>📄 보고서 생성</div>", unsafe_allow_html=True)
    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    scores  = calc_scores(df)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("점검 규칙",  f"{len(df)}개")
    c2.metric("위반 탐지",  f"{(df['yn_violation']=='Y').sum()}개")
    c3.metric("기준일",     datetime.now().strftime("%Y.%m.%d"))
    c4.metric("최저 점수",  f"{min(scores.values())}점")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 📊 Excel 보고서")
        st.markdown("- 규칙별 위반 현황표\n- 도메인별 요약 집계\n- 심각도별 분류")
    with col2:
        st.markdown("##### 📝 Word 보고서")
        st.markdown("- 표지 + 점검 총평\n- 도메인별 상세 분석\n- AI 기반 시정조치 권고")

    st.markdown("---")
    if st.button("📄 보고서 생성", type="primary"):
        with st.spinner("보고서 생성 중... (약 30초)"):
            res = subprocess.run(
                [sys.executable, os.path.join(SRC_DIR, "report_generator.py")],
                capture_output=True, text=True)
        if res.returncode == 0:
            st.success("✅ 보고서 생성 완료!")
        else:
            st.error("❌ 생성 오류")
            with st.expander("오류 내용"): st.code(res.stderr)

    os.makedirs(REPORT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    found = False
    for ext, label, mime in [
        ("xlsx","📥 Excel 다운로드","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("docx","📥 Word 다운로드", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ]:
        fpath = os.path.join(REPORT_DIR, f"IT감사보고서_{today}.{ext}")
        if os.path.exists(fpath):
            found = True
            with open(fpath, "rb") as f:
                st.download_button(label=label, data=f.read(),
                                   file_name=f"IT감사보고서_{today}.{ext}", mime=mime)
    if not found:
        st.info("보고서를 먼저 생성해주세요.")


# ════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════
def main():
    month, domains, sevs = render_sidebar()
    view = st.session_state.view

    if view == "analysis":
        view_analysis(month)
    elif view == "overview":
        view_overview(month, domains, sevs)
    elif view == "access":
        view_domain(month, "접근통제", sevs)
    elif view == "change":
        view_domain(month, "변경관리", sevs)
    elif view == "ops":
        view_domain(month, "운영통제", sevs)
    elif view == "scan":
        view_scan(month)
    elif view == "report":
        view_report(month)

if __name__ == "__main__":
    main()
