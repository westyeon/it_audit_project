"""
AI 기반 IT감사 사전 통제 점검 시스템 - Dash 대시보드
"""
import os, glob, re, subprocess, sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
import dash_bootstrap_components as dbc

# ── 경로 ──────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data", "processed")
DB_DIR    = os.path.join(DATA_DIR, "virtual_db")
SRC_DIR   = os.path.join(BASE_DIR, "src")

DOMAIN_COLORS = {"접근통제":"#6366f1","변경관리":"#f59e0b","운영통제":"#10b981"}
SEV_COLORS    = {"HIGH":"#ef4444","MEDIUM":"#f59e0b","LOW":"#10b981"}
SYS_MAP       = {"CRED":"신용평가시스템","PORTAL":"고객포털",
                 "ERP":"경영관리시스템","DW":"데이터웨어하우스","DEVP":"ITSM"}
GRADE_COLORS  = {"Critical":"#7f1d1d","High":"#ef4444","Medium":"#f59e0b",
                 "Low":"#10b981","정상":"#94a3b8"}

# ── 월별 파일 탐지 ─────────────────────────────────────────────
def detect_months():
    files = glob.glob(os.path.join(DATA_DIR, "violations_summary_????-??.csv"))
    months = sorted({re.search(r"(\d{4}-\d{2})", os.path.basename(f)).group(1)
                     for f in files if re.search(r"(\d{4}-\d{2})", f)})
    return months

MONTHS = detect_months()
MONTH_LABELS = {m: datetime.strptime(m,"%Y-%m").strftime("%Y년 %m월") for m in MONTHS}

# ── 데이터 로드 ────────────────────────────────────────────────
def load_summary(month=None):
    if month:
        p = os.path.join(DATA_DIR, f"violations_summary_{month}.csv")
        if os.path.exists(p):
            return pd.read_csv(p, encoding="utf-8-sig")
    p = os.path.join(DATA_DIR, "violations_summary.csv")
    if os.path.exists(p):
        return pd.read_csv(p, encoding="utf-8-sig")
    return None

def load_db(fname):
    p = os.path.join(DB_DIR, fname)
    return pd.read_csv(p, encoding="utf-8-sig") if os.path.exists(p) else pd.DataFrame()

def load_all_dfs():
    dfs = {k: load_db(v) for k,v in {
        "emp":"emp_master.csv","account":"sys_account.csv",
        "access":"access_log.csv","deploy":"deploy_log.csv","backup":"backup_log.csv"
    }.items()}
    for df in [dfs["account"],dfs["access"],dfs["deploy"],dfs["backup"]]:
        if "system_cd" in df.columns:
            df["system_nm"] = df["system_cd"].map(SYS_MAP).fillna(df["system_cd"])
    for col in ["hire_dt","resign_dt"]:
        if col in dfs["emp"].columns:
            dfs["emp"][col] = pd.to_datetime(dfs["emp"][col], errors="coerce")
    for df, cols in [(dfs["account"],["last_review_dt"]),(dfs["access"],["access_dt"]),
                     (dfs["deploy"],["deploy_dt"]),(dfs["backup"],["backup_dt"])]:
        for col in cols:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce")
    return dfs

def risk_score_df(df):
    d = df.copy()
    d["sev_n"] = d["severity"].map({"HIGH":3,"MEDIUM":2,"LOW":1}).fillna(1)
    d["score"] = (d["sev_n"] * np.log1p(d["violation_count"])).round(2)
    d["score"] = d["score"].where(d["yn_violation"]=="Y", 0)
    def grade(s):
        if s>=8:  return "Critical"
        if s>=5:  return "High"
        if s>=2:  return "Medium"
        if s>0:   return "Low"
        return "정상"
    d["grade"] = d["score"].apply(grade)
    d["gcolor"] = d["grade"].map(GRADE_COLORS)
    return d

# ── 공통 스타일 ────────────────────────────────────────────────
CARD = {
    "background":"white","borderRadius":"16px",
    "padding":"1.25rem 1.4rem",
    "boxShadow":"0 1px 4px rgba(0,0,0,0.04),0 6px 20px rgba(0,0,0,0.06)",
    "border":"1px solid #f1f5f9","marginBottom":"1rem",
}
SIDEBAR = {
    "position":"fixed","top":0,"left":0,"bottom":0,"width":"220px",
    "padding":"1.4rem 0.9rem","background":"white",
    "borderRight":"1px solid #e2e8f0","overflowY":"auto","zIndex":200,
}
CONTENT = {
    "marginLeft":"220px","padding":"1.4rem",
    "background":"#f1f5f9","minHeight":"100vh",
}
def chart_base(h=300, legend=False, bg="white"):
    return dict(
        height=h, showlegend=legend,
        margin=dict(l=10,r=55,t=10,b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=bg,
        font=dict(family="Inter,sans-serif",color="#64748b",size=11),
        xaxis=dict(gridcolor="#f8fafc",linecolor="#e2e8f0",tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#f8fafc",linecolor="#e2e8f0",tickfont=dict(size=10)),
    )
def card_title(txt):
    return html.P(txt, style={
        "fontSize":"0.76rem","fontWeight":"700","color":"#94a3b8",
        "textTransform":"uppercase","letterSpacing":"0.08em",
        "marginBottom":"0.9rem","paddingBottom":"0.5rem",
        "borderBottom":"1px solid #f1f5f9",
    })
def badge(text, color):
    bg = {"red":"#fef2f2","orange":"#fff7ed","green":"#f0fdf4",
          "blue":"#eff6ff","purple":"#f5f3ff","gray":"#f8fafc"}
    fg = {"red":"#ef4444","orange":"#f59e0b","green":"#10b981",
          "blue":"#3b82f6","purple":"#6366f1","gray":"#94a3b8"}
    return html.Span(text, style={
        "background":bg.get(color,"#f1f5f9"),"color":fg.get(color,"#64748b"),
        "borderRadius":"999px","padding":"0.2rem 0.6rem",
        "fontSize":"0.72rem","fontWeight":"700","letterSpacing":"0.04em",
    })

def kpi(value, label, color, delta=None):
    return html.Div([
        html.Div(str(value), style={
            "fontSize":"2.1rem","fontWeight":"900","color":color,
            "lineHeight":"1.1","fontFamily":"Inter,sans-serif",
        }),
        html.Div(label, style={
            "fontSize":"0.72rem","color":"#94a3b8","fontWeight":"600",
            "textTransform":"uppercase","letterSpacing":"0.05em","marginTop":"0.3rem",
        }),
        html.Div(delta, style={"fontSize":"0.72rem","color":"#94a3b8","marginTop":"0.15rem"}) if delta else None,
    ], style={**CARD,"borderLeft":f"4px solid {color}","padding":"1rem 1.2rem","cursor":"default"})

def hero(month, df):
    total = len(df); viol = int((df["yn_violation"]=="Y").sum())
    high = int(((df["severity"]=="HIGH")&(df["yn_violation"]=="Y")).sum())
    rate = round(viol/total*100) if total else 0
    mlabel = MONTH_LABELS.get(month, month) if month else "-"
    stats = [
        (str(total),"점검 규칙","white"),
        (str(viol),"위반 탐지","#fca5a5"),
        (str(high),"HIGH 위반","#fde68a"),
        (f"{rate}%","위반율","#6ee7b7"),
    ]
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H3("IT감사 통제 점검", style={
                    "fontWeight":"900","color":"white","marginBottom":"0.25rem",
                    "fontFamily":"Inter,sans-serif","fontSize":"1.6rem",
                }),
                html.P(f"{mlabel} 기준  ·  AI Rule 엔진 자동 탐지",
                       style={"color":"rgba(255,255,255,0.78)","fontSize":"0.88rem","marginBottom":0}),
            ], width=5, style={"display":"flex","flexDirection":"column","justifyContent":"center"}),
            dbc.Col([
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Div(v, style={"fontSize":"1.9rem","fontWeight":"900","color":c,"lineHeight":"1"}),
                        html.Div(l, style={"fontSize":"0.72rem","color":"rgba(255,255,255,0.7)","marginTop":"0.2rem"}),
                    ], style={"textAlign":"center"}))
                    for v,l,c in stats
                ], className="g-2"),
            ], width=7),
        ])
    ], style={
        "background":"linear-gradient(135deg,#4f46e5 0%,#3b82f6 55%,#0891b2 100%)",
        "borderRadius":"20px","padding":"1.6rem 2rem","marginBottom":"1.2rem",
        "boxShadow":"0 8px 30px rgba(99,102,241,0.25)",
    })

# ── Dash 앱 ───────────────────────────────────────────────────
app = Dash(__name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap",
    ],
    suppress_callback_exceptions=True,
)
app.title = "AI IT감사 점검 시스템"

NAV_PAGES = [
    ("overview","전체 개요"),("access","접근통제"),("change","변경관리"),
    ("ops","운영통제"),("analysis","심화 분석"),("scan","점검 실행"),("report","보고서"),
]

def sidebar(active):
    links = []
    for key, label in NAV_PAGES:
        is_active = key == active
        links.append(html.Div(label, id=f"nav-{key}", n_clicks=0, style={
            "padding":"0.55rem 0.85rem","borderRadius":"10px","marginBottom":"3px",
            "fontSize":"0.87rem","fontWeight":"700" if is_active else "500",
            "cursor":"pointer","color":"#3b82f6" if is_active else "#64748b",
            "background":"#eff6ff" if is_active else "transparent",
            "borderLeft":f"3px solid #6366f1" if is_active else "3px solid transparent",
            "transition":"all 0.15s",
        }))

    month_opts = [{"label":MONTH_LABELS.get(m,m),"value":m} for m in MONTHS]
    default_m  = MONTHS[-1] if MONTHS else None

    return html.Div([
        html.Div([
            html.Span("IT", style={"color":"#6366f1","fontWeight":"900","fontSize":"1.2rem"}),
            html.Span("감사", style={"color":"#1e293b","fontWeight":"900","fontSize":"1.2rem"}),
        ], style={"marginBottom":"0.2rem","fontFamily":"Inter,sans-serif"}),
        html.P("AI-Powered Audit Control",
               style={"color":"#94a3b8","fontSize":"0.7rem","marginBottom":"1.2rem"}),
        html.Hr(style={"borderColor":"#e2e8f0","margin":"0 0 1rem"}),

        html.P("분석 월", style={"color":"#94a3b8","fontSize":"0.7rem","fontWeight":"700",
                                "letterSpacing":"0.08em","marginBottom":"0.35rem"}),
        dcc.Dropdown(id="month-dd", options=month_opts, value=default_m,
                     clearable=False,
                     style={"fontSize":"0.84rem","marginBottom":"1.1rem",
                            "borderRadius":"10px"}),
        html.Hr(style={"borderColor":"#e2e8f0","margin":"0 0 0.8rem"}),
        html.P("MENU", style={"color":"#cbd5e1","fontSize":"0.68rem","fontWeight":"700",
                              "letterSpacing":"0.1em","marginBottom":"0.5rem"}),
        *links,
        html.Hr(style={"borderColor":"#e2e8f0","margin":"1rem 0 0.5rem"}),
        html.Div(id="sidebar-scan-time",
                 style={"color":"#94a3b8","fontSize":"0.7rem","lineHeight":"1.5"}),
    ], style=SIDEBAR)

DEFAULT_MONTH = MONTHS[-1] if MONTHS else None

def make_layout():
    month_opts = [{"label": MONTH_LABELS.get(m,m), "value": m} for m in MONTHS]
    nav_links = []
    for key, label in NAV_PAGES:
        is_active = key == "scan"
        nav_links.append(html.Div(label, id=f"nav-{key}", n_clicks=0, style={
            "padding":"0.55rem 0.85rem","borderRadius":"10px","marginBottom":"3px",
            "fontSize":"0.87rem","fontWeight":"700" if is_active else "500",
            "cursor":"pointer","color":"#3b82f6" if is_active else "#64748b",
            "background":"#eff6ff" if is_active else "transparent",
            "borderLeft":"3px solid #6366f1" if is_active else "3px solid transparent",
        }))
    sidebar_el = html.Div([
        html.Div([
            html.Span("IT", style={"color":"#6366f1","fontWeight":"900","fontSize":"1.2rem"}),
            html.Span("감사", style={"color":"#1e293b","fontWeight":"900","fontSize":"1.2rem"}),
        ], style={"marginBottom":"0.2rem","fontFamily":"Inter,sans-serif"}),
        html.P("AI-Powered Audit Control",
               style={"color":"#94a3b8","fontSize":"0.7rem","marginBottom":"1.2rem"}),
        html.Hr(style={"borderColor":"#e2e8f0","margin":"0 0 1rem"}),
        html.P("분석 월", style={"color":"#94a3b8","fontSize":"0.7rem","fontWeight":"700",
                                "letterSpacing":"0.08em","marginBottom":"0.35rem"}),
        dcc.Dropdown(id="month-dd", options=month_opts, value=DEFAULT_MONTH,
                     clearable=False,
                     style={"fontSize":"0.84rem","marginBottom":"1.1rem","borderRadius":"10px"}),
        html.Hr(style={"borderColor":"#e2e8f0","margin":"0 0 0.8rem"}),
        html.P("MENU", style={"color":"#cbd5e1","fontSize":"0.68rem","fontWeight":"700",
                              "letterSpacing":"0.1em","marginBottom":"0.5rem"}),
        *nav_links,
    ], style=SIDEBAR)
    return html.Div([
        dcc.Store(id="page-store", data="scan"),
        sidebar_el,
        html.Div(id="main-content", style=CONTENT),
    ], style={"fontFamily":"Inter,sans-serif"})

app.layout = make_layout

# ── 네비 스타일 업데이트 ──────────────────────────────────────
@app.callback(
    [Output(f"nav-{k}","style") for k,_ in NAV_PAGES],
    Input("page-store","data"),
)
def update_nav(page):
    page = page or "scan"
    styles = []
    for key, _ in NAV_PAGES:
        active = key == page
        styles.append({
            "padding":"0.55rem 0.85rem","borderRadius":"10px","marginBottom":"3px",
            "fontSize":"0.87rem","fontWeight":"700" if active else "500",
            "cursor":"pointer","color":"#3b82f6" if active else "#64748b",
            "background":"#eff6ff" if active else "transparent",
            "borderLeft":"3px solid #6366f1" if active else "3px solid transparent",
        })
    return styles

# ── 라우팅 ────────────────────────────────────────────────────
@app.callback(
    Output("page-store","data"),
    [Input(f"nav-{k}","n_clicks") for k,_ in NAV_PAGES],
    prevent_initial_call=True,
)
def route(*_):
    ctx = callback_context
    if not ctx.triggered: return no_update
    return ctx.triggered[0]["prop_id"].split(".")[0].replace("nav-","")

# ── 메인 콘텐츠 ───────────────────────────────────────────────
@app.callback(
    Output("main-content","children"),
    Input("page-store","data"),
    Input("month-dd","value"),
)
def render(page, month):
    page = page or "scan"
    month = month or DEFAULT_MONTH
    df = load_summary(month)
    if page=="overview":  return pg_overview(df, month)
    if page=="access":    return pg_domain(df, month, "접근통제")
    if page=="change":    return pg_domain(df, month, "변경관리")
    if page=="ops":       return pg_domain(df, month, "운영통제")
    if page=="analysis":  return pg_analysis(df, month)
    if page=="scan":      return pg_scan(month)
    if page=="report":    return pg_report(df, month)
    return html.Div("페이지 없음")

# ══════════════════════════════════════════════════════════════
# 전체 개요
# ══════════════════════════════════════════════════════════════
def pg_overview(df, month):
    if df is None:
        return dbc.Alert("점검 실행 메뉴에서 먼저 점검을 실행해주세요.", color="warning",
                         style={"borderRadius":"12px"})

    total = len(df); viol = int((df["yn_violation"]=="Y").sum())
    high  = int(((df["severity"]=="HIGH")&(df["yn_violation"]=="Y")).sum())
    clean = total - viol

    # ── 도메인별 위반 현황 (가로 막대) ──────────────────────────
    dom = df.groupby("audit_domain").agg(
        전체=("rule_id","count"),
        위반=("yn_violation",lambda x:(x=="Y").sum()),
        건수=("violation_count","sum"),
    ).reset_index()
    dom["준수율"] = ((dom["전체"]-dom["위반"])/dom["전체"]*100).round(1)

    fig_dom = go.Figure()
    for _, r in dom.iterrows():
        c = DOMAIN_COLORS.get(r["audit_domain"],"#6366f1")
        fig_dom.add_trace(go.Bar(
            name=r["audit_domain"], x=[r["위반"]], y=[r["audit_domain"]],
            orientation="h", marker_color=c, marker_opacity=0.9,
            text=f"  {r['위반']}개 위반 / 준수율 {r['준수율']}%",
            textposition="outside", insidetextanchor="start",
            hovertemplate=f"{r['audit_domain']}<br>위반: {r['위반']}개<br>총 위반 건수: {r['건수']:,}<extra></extra>",
        ))
    fig_dom.update_layout(**chart_base(h=180, legend=False))
    fig_dom.update_xaxis(title="위반 규칙 수", range=[0, dom["위반"].max()*1.6])
    fig_dom.update_yaxis(categoryorder="array", categoryarray=list(DOMAIN_COLORS.keys()))

    # ── 심각도 도넛 ──────────────────────────────────────────────
    sv = (df[df["yn_violation"]=="Y"].groupby("severity")["rule_id"].count()
          .reindex(["HIGH","MEDIUM","LOW"]).fillna(0).reset_index())
    fig_sev = go.Figure(go.Pie(
        labels=sv["severity"], values=sv["rule_id"], hole=0.65,
        marker_colors=[SEV_COLORS.get(s,"#ccc") for s in sv["severity"]],
        textinfo="label+percent", textfont=dict(size=11),
        hovertemplate="%{label}: %{value}개<extra></extra>",
    ))
    fig_sev.update_layout(**chart_base(h=220, legend=False))
    fig_sev.add_annotation(text=f"<b>{viol}</b><br><span style='font-size:10px'>위반</span>",
                           x=0.5, y=0.5, showarrow=False,
                           font=dict(size=18,color="#1e293b"))

    # ── TOP 10 위반 ───────────────────────────────────────────────
    top = df[df["yn_violation"]=="Y"].nlargest(10,"violation_count")
    fig_top = go.Figure(go.Bar(
        x=top["violation_count"][::-1],
        y=[f"{n[:14]}" for n in top["rule_nm"][::-1]],
        orientation="h",
        marker_color=[DOMAIN_COLORS.get(d,"#94a3b8") for d in top["audit_domain"][::-1]],
        marker_opacity=0.85,
        text=top["violation_count"][::-1].apply(lambda v: f"{v:,}"),
        textposition="outside",
        hovertemplate="%{y}<br>%{x:,}건<extra></extra>",
    ))
    fig_top.update_layout(**chart_base(h=300, legend=False))
    fig_top.update_xaxis(title="위반 건수")

    # ── 월별 트렌드 ───────────────────────────────────────────────
    trend_rows = []
    for m in MONTHS:
        d = load_summary(m)
        if d is not None:
            trend_rows.append({
                "월": MONTH_LABELS.get(m,m),
                "접근통제": int((d[d["audit_domain"]=="접근통제"]["yn_violation"]=="Y").sum()),
                "변경관리": int((d[d["audit_domain"]=="변경관리"]["yn_violation"]=="Y").sum()),
                "운영통제": int((d[d["audit_domain"]=="운영통제"]["yn_violation"]=="Y").sum()),
            })
    trend_df = pd.DataFrame(trend_rows)
    fig_trend = go.Figure()
    if len(trend_df) > 0:
        for domain, color in DOMAIN_COLORS.items():
            if domain in trend_df.columns:
                fig_trend.add_trace(go.Scatter(
                    x=trend_df["월"], y=trend_df[domain],
                    name=domain, mode="lines+markers",
                    line=dict(color=color, width=2.5),
                    marker=dict(size=7, color=color),
                    hovertemplate=f"{domain}<br>%{{x}}: %{{y}}개<extra></extra>",
                ))
    fig_trend.update_layout(**chart_base(h=220, legend=True, bg="rgba(0,0,0,0)"))
    fig_trend.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(size=11),
    ))

    # ── 위험 등급 분포 ────────────────────────────────────────────
    dr = risk_score_df(df)
    grade_order = ["Critical","High","Medium","Low","정상"]
    gc = dr.groupby("grade").size().reindex(grade_order,fill_value=0).reset_index()
    gc.columns = ["등급","수"]
    fig_grade = go.Figure(go.Bar(
        x=gc["등급"], y=gc["수"],
        marker_color=[GRADE_COLORS.get(g,"#ccc") for g in gc["등급"]],
        marker_opacity=0.9,
        text=gc["수"], textposition="outside",
        hovertemplate="%{x}: %{y}개<extra></extra>",
    ))
    fig_grade.update_layout(**chart_base(h=200, legend=False))

    return html.Div([
        hero(month, df),

        # KPI 행
        dbc.Row([
            dbc.Col(kpi(f"{total}개","총 점검 규칙","#6366f1"), md=3),
            dbc.Col(kpi(f"{viol}개","위반 탐지","#ef4444",f"전체의 {round(viol/total*100)}%"), md=3),
            dbc.Col(kpi(f"{high}개","HIGH 위반","#f59e0b","즉각 조치 필요"), md=3),
            dbc.Col(kpi(f"{clean}개","이상 없음","#10b981",f"준수율 {round(clean/total*100)}%"), md=3),
        ], className="g-3 mb-2"),

        # 차트 행 1
        dbc.Row([
            dbc.Col(html.Div([
                card_title("도메인별 위반 현황"),
                dcc.Graph(figure=fig_dom, config={"displayModeBar":False}),
            ], style=CARD), md=4),
            dbc.Col(html.Div([
                card_title("심각도별 위반 비율"),
                dcc.Graph(figure=fig_sev, config={"displayModeBar":False}),
            ], style=CARD), md=3),
            dbc.Col(html.Div([
                card_title("위험 등급 분포 (리스크 점수 기준)"),
                dcc.Graph(figure=fig_grade, config={"displayModeBar":False}),
            ], style=CARD), md=5),
        ], className="g-3 mb-2"),

        # 차트 행 2
        dbc.Row([
            dbc.Col(html.Div([
                card_title("월별 위반 규칙 수 트렌드"),
                dcc.Graph(figure=fig_trend, config={"displayModeBar":False}),
            ], style=CARD), md=5),
            dbc.Col(html.Div([
                card_title("위반 건수 TOP 10"),
                dcc.Graph(figure=fig_top, config={"displayModeBar":False}),
            ], style=CARD), md=7),
        ], className="g-3"),
    ])

# ══════════════════════════════════════════════════════════════
# 도메인 상세
# ══════════════════════════════════════════════════════════════
def pg_domain(df, month, domain):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다.", color="warning", style={"borderRadius":"12px"})

    sub  = df[df["audit_domain"]==domain].copy()
    viol = sub[sub["yn_violation"]=="Y"]
    total = len(sub); vc = len(viol)
    pass_rate = round((total-vc)/total*100) if total else 0
    color = DOMAIN_COLORS.get(domain,"#6366f1")

    # 심각도 파이
    sv = (viol.groupby("severity")["rule_id"].count()
          .reindex(["HIGH","MEDIUM","LOW"]).fillna(0).reset_index())
    fig_pie = go.Figure(go.Pie(
        labels=sv["severity"], values=sv["rule_id"], hole=0.62,
        marker_colors=[SEV_COLORS.get(s,"#ccc") for s in sv["severity"]],
        textinfo="label+percent", textfont=dict(size=11),
    ))
    fig_pie.update_layout(**chart_base(h=240, legend=False))
    fig_pie.add_annotation(text=f"<b>{vc}</b><br>위반",x=0.5,y=0.5,
                           showarrow=False,font=dict(size=16,color="#1e293b"))

    # 위반 규칙 바
    if vc > 0:
        top_v = viol.nlargest(min(8,vc),"violation_count")
        fig_bar = go.Figure(go.Bar(
            x=top_v["violation_count"][::-1],
            y=[n[:16] for n in top_v["rule_nm"][::-1]],
            orientation="h", marker_color=color, marker_opacity=0.85,
            text=top_v["violation_count"][::-1].apply(lambda v: f"{v:,}"),
            textposition="outside",
        ))
        fig_bar.update_layout(**chart_base(h=260, legend=False))
    else:
        fig_bar = go.Figure()
        fig_bar.update_layout(**chart_base(h=260))

    # 월별 트렌드 (이 도메인만)
    trend_rows = []
    for m in MONTHS:
        d = load_summary(m)
        if d is not None:
            sub_m = d[d["audit_domain"]==domain]
            trend_rows.append({
                "월": MONTH_LABELS.get(m,m),
                "위반": int((sub_m["yn_violation"]=="Y").sum()),
                "준수율": round((len(sub_m)-(sub_m["yn_violation"]=="Y").sum())/len(sub_m)*100) if len(sub_m) else 100,
            })
    trend_df = pd.DataFrame(trend_rows)
    fig_trend = go.Figure()
    if len(trend_df) > 0:
        fig_trend.add_trace(go.Scatter(
            x=trend_df["월"], y=trend_df["위반"],
            mode="lines+markers", name="위반 규칙 수",
            line=dict(color=color, width=2.5),
            marker=dict(size=8, color=color),
            fill="tozeroy", fillcolor=f"rgba{tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))+(0.08,)}",
        ))
    fig_trend.update_layout(**chart_base(h=200, legend=False, bg="rgba(0,0,0,0)"))
    fig_trend.update_yaxis(title="위반 규칙 수")

    # 위반 목록 테이블
    tbl = (viol.sort_values("violation_count",ascending=False)
           [["rule_id","rule_nm","severity","violation_count","remediation"]]
           .rename(columns={"rule_id":"ID","rule_nm":"규칙명","severity":"심각도",
                            "violation_count":"위반 건수","remediation":"시정조치"}))

    return html.Div([
        html.H4(f"{domain} 상세", style={
            "fontWeight":"800","color":"#0f172a","letterSpacing":"-0.03em","marginBottom":"0.2rem",
        }),
        html.P(f"{MONTH_LABELS.get(month,month)} 기준",
               style={"color":"#94a3b8","fontSize":"0.83rem","marginBottom":"1rem"}),

        dbc.Row([
            dbc.Col(kpi(f"{total}개","점검 규칙",color), md=3),
            dbc.Col(kpi(f"{vc}개","위반 탐지","#ef4444"), md=3),
            dbc.Col(kpi(f"{total-vc}개","이상 없음","#10b981"), md=3),
            dbc.Col(kpi(f"{pass_rate}%","준수율","#6366f1"), md=3),
        ], className="g-3 mb-2"),

        dbc.Row([
            dbc.Col(html.Div([
                card_title("심각도별 위반 비율"),
                dcc.Graph(figure=fig_pie, config={"displayModeBar":False}),
            ], style=CARD), md=3),
            dbc.Col(html.Div([
                card_title("위반 건수 TOP 8"),
                dcc.Graph(figure=fig_bar, config={"displayModeBar":False}),
            ], style=CARD), md=5),
            dbc.Col(html.Div([
                card_title("월별 위반 추이"),
                dcc.Graph(figure=fig_trend, config={"displayModeBar":False}),
            ], style=CARD), md=4),
        ], className="g-3 mb-2"),

        html.Div([
            card_title("위반 규칙 상세 목록"),
            dbc.Table.from_dataframe(tbl, striped=True, hover=True,
                                     responsive=True, style={"fontSize":"0.85rem"}),
        ], style=CARD),
    ])

# ══════════════════════════════════════════════════════════════
# 심화 분석
# ══════════════════════════════════════════════════════════════
def pg_analysis(df, month):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다.", color="warning", style={"borderRadius":"12px"})

    dfs = load_all_dfs()
    emp=dfs["emp"]; account=dfs["account"]; access=dfs["access"]
    deploy=dfs["deploy"]; backup=dfs["backup"]

    resigned = set(emp[emp["yn_employed"]=="N"]["emp_id"])
    active_res = account[
        account["emp_id"].isin(resigned)&(account["account_status"]=="active")
    ].merge(emp[["emp_id","dept_nm"]],on="emp_id",how="left")
    overdue = account[account["yn_overdue_review"]=="Y"].merge(emp[["emp_id","dept_nm"]],on="emp_id",how="left")
    after_h = access[access["yn_after_hours"]=="Y"].merge(emp[["emp_id","dept_nm"]],on="emp_id",how="left")

    dept_risk = pd.concat([
        active_res.groupby("dept_nm").size().rename("퇴사자계정"),
        overdue.groupby("dept_nm").size().rename("권한검토초과"),
        after_h.groupby("dept_nm").size().rename("시간외접속"),
    ],axis=1).fillna(0).astype(int)
    dept_risk["위험점수"] = dept_risk["퇴사자계정"]*3+dept_risk["권한검토초과"]*2+dept_risk["시간외접속"]
    dept_risk = dept_risk.sort_values("위험점수",ascending=False)

    # 히트맵
    hd = dept_risk[["퇴사자계정","권한검토초과","시간외접속"]].head(12)
    fig_heat = go.Figure(go.Heatmap(
        z=hd.values, x=hd.columns.tolist(), y=hd.index.tolist(),
        colorscale="YlOrRd", texttemplate="%{z}",
        hovertemplate="%{y}<br>%{x}: %{z}건<extra></extra>",
    ))
    fig_heat.update_layout(**chart_base(h=340, legend=False, bg="white"))

    # 위험점수 바
    td = dept_risk.head(10).reset_index()
    fig_dept = go.Figure(go.Bar(
        x=td["위험점수"], y=td["dept_nm"],
        orientation="h",
        marker_color=["#ef4444" if s>=10 else "#f59e0b" if s>=5 else "#6366f1" for s in td["위험점수"]],
        text=td["위험점수"], textposition="outside",
    ))
    fig_dept.update_layout(**chart_base(h=300, legend=False))
    fig_dept.update_yaxis(autorange="reversed")

    # 리스크 매트릭스
    dr = risk_score_df(df)
    grade_order = ["Critical","High","Medium","Low","정상"]
    gc = dr.groupby("grade").size().reindex(grade_order,fill_value=0).reset_index()
    gc.columns=["등급","수"]
    fig_grade = go.Figure(go.Bar(
        x=gc["등급"], y=gc["수"],
        marker_color=[GRADE_COLORS.get(g,"#ccc") for g in gc["등급"]],
        text=gc["수"], textposition="outside",
    ))
    fig_grade.update_layout(**chart_base(h=230, legend=False))

    top_r = dr[dr["score"]>0].nlargest(10,"score")
    fig_risk = go.Figure(go.Bar(
        x=top_r["score"][::-1],
        y=[f"{r} {n[:12]}" for r,n in zip(top_r["rule_id"][::-1],top_r["rule_nm"][::-1])],
        orientation="h",
        marker_color=[GRADE_COLORS.get(g,"#ccc") for g in top_r["grade"][::-1]],
        text=top_r["score"][::-1].round(1), textposition="outside",
    ))
    fig_risk.update_layout(**chart_base(h=300, legend=False))

    # 법령 준수율
    law_total = df.groupby("source_law").size()
    law_viol  = df[df["yn_violation"]=="Y"].groupby("source_law").size()
    law_comp  = ((1-law_viol/law_total)*100).round(1).reset_index()
    law_comp.columns=["법령명","준수율(%)"]
    law_comp = law_comp.sort_values("준수율(%)")
    fig_law = go.Figure(go.Bar(
        x=law_comp["준수율(%)"], y=law_comp["법령명"],
        orientation="h",
        marker_color=["#ef4444" if v<50 else "#f59e0b" if v<75 else "#10b981" for v in law_comp["준수율(%)"]],
        text=[f"{v}%" for v in law_comp["준수율(%)"]],
        textposition="outside",
    ))
    fig_law.update_layout(**chart_base(h=280, legend=False))
    fig_law.update_xaxis(range=[0,115])

    return html.Div([
        html.H4("심화 분석", style={"fontWeight":"800","color":"#0f172a","letterSpacing":"-0.03em","marginBottom":"0.2rem"}),
        html.P(f"{MONTH_LABELS.get(month,month)} 기준 · DB 데이터 자동 분석",
               style={"color":"#94a3b8","fontSize":"0.83rem","marginBottom":"1rem"}),

        dbc.Tabs([
            dbc.Tab(label="부서별 위험도", tab_id="dept", children=[
                html.Div(style={"height":"0.8rem"}),
                dbc.Row([
                    dbc.Col(html.Div([card_title("부서별 위반 히트맵"),
                                     dcc.Graph(figure=fig_heat, config={"displayModeBar":False})],style=CARD),md=6),
                    dbc.Col(html.Div([card_title("부서별 종합 위험점수 TOP 10"),
                                     dcc.Graph(figure=fig_dept, config={"displayModeBar":False})],style=CARD),md=6),
                ],className="g-3"),
            ]),
            dbc.Tab(label="리스크 점수화", tab_id="risk", children=[
                html.Div(style={"height":"0.8rem"}),
                dbc.Row([
                    dbc.Col(html.Div([card_title("위험 등급 분포"),
                                     dcc.Graph(figure=fig_grade, config={"displayModeBar":False})],style=CARD),md=4),
                    dbc.Col(html.Div([card_title("고위험 규칙 TOP 10"),
                                     dcc.Graph(figure=fig_risk, config={"displayModeBar":False})],style=CARD),md=8),
                ],className="g-3"),
            ]),
            dbc.Tab(label="법령 준수율", tab_id="law", children=[
                html.Div(style={"height":"0.8rem"}),
                html.Div([card_title("법령별 규칙 준수율"),
                          dcc.Graph(figure=fig_law, config={"displayModeBar":False})],style=CARD),
            ]),
        ], active_tab="dept"),
    ])

# ══════════════════════════════════════════════════════════════
# 점검 실행
# ══════════════════════════════════════════════════════════════
def pg_scan(month):
    mlabel = MONTH_LABELS.get(month,month) if month else "-"
    return html.Div([
        html.H4("점검 실행", style={"fontWeight":"800","color":"#0f172a","marginBottom":"0.2rem"}),
        html.P("Rule 엔진을 실행하여 위반 사항을 자동 탐지합니다",
               style={"color":"#94a3b8","fontSize":"0.83rem","marginBottom":"1rem"}),
        dbc.Row([
            dbc.Col(kpi("70개","점검 규칙","#6366f1"),md=3),
            dbc.Col(kpi("3개","점검 도메인","#3b82f6"),md=3),
            dbc.Col(kpi("6개","분석 테이블","#10b981"),md=3),
            dbc.Col(kpi(mlabel,"선택 월","#f59e0b"),md=3),
        ],className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("접근통제",className="fw-bold"),
                html.P("계정·권한·퇴직자 관리",className="text-muted small mb-0"),
            ])],outline=True,color="primary"),md=4),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("변경관리",className="fw-bold"),
                html.P("CR·배포·직무분리",className="text-muted small mb-0"),
            ])],outline=True,color="warning"),md=4),
            dbc.Col(dbc.Card([dbc.CardBody([
                html.H6("운영통제",className="fw-bold"),
                html.P("로그·백업·권한검토",className="text-muted small mb-0"),
            ])],outline=True,color="success"),md=4),
        ],className="g-3 mb-3"),
        html.Div([
            dbc.Button("점검 실행", id="scan-btn", color="primary", size="lg",
                       style={"borderRadius":"12px","fontWeight":"700","padding":"0.75rem 3rem"}),
            html.Div(id="scan-result",style={"marginTop":"1rem"}),
        ],style={**CARD,"textAlign":"center","padding":"2rem"}),
    ])

@app.callback(Output("scan-result","children"), Input("scan-btn","n_clicks"),
              prevent_initial_call=True)
def run_scan(n):
    if not n: return no_update
    try:
        r = subprocess.run([sys.executable, os.path.join(SRC_DIR,"rule_engine.py")],
                           capture_output=True, text=True, timeout=120, cwd=BASE_DIR)
        if r.returncode==0:
            return dbc.Alert("점검 완료! 좌측 메뉴에서 결과를 확인하세요.",color="success",style={"borderRadius":"10px"})
        return dbc.Alert(f"오류: {r.stderr[:300]}",color="danger",style={"borderRadius":"10px"})
    except Exception as e:
        return dbc.Alert(str(e),color="danger",style={"borderRadius":"10px"})

# ══════════════════════════════════════════════════════════════
# 보고서
# ══════════════════════════════════════════════════════════════
def pg_report(df, month):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다.", color="warning", style={"borderRadius":"12px"})
    total=len(df); viol=int((df["yn_violation"]=="Y").sum())
    return html.Div([
        html.H4("보고서 생성",style={"fontWeight":"800","color":"#0f172a","marginBottom":"0.2rem"}),
        html.P("AI 분석이 포함된 Excel·Word 보고서를 자동 생성합니다",
               style={"color":"#94a3b8","fontSize":"0.83rem","marginBottom":"1rem"}),
        dbc.Row([
            dbc.Col(kpi(f"{total}개","점검 규칙","#6366f1"),md=3),
            dbc.Col(kpi(f"{viol}개","위반 탐지","#ef4444"),md=3),
            dbc.Col(kpi(datetime.now().strftime("%Y.%m.%d"),"기준일","#10b981"),md=3),
            dbc.Col(kpi("Claude AI","분석 엔진","#f59e0b"),md=3),
        ],className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(html.Div([
                card_title("Excel 보고서"),
                html.Ul([html.Li(t) for t in ["규칙별 위반 현황표 (4개 시트)","도메인별 요약","심각도별 색상 분류","AI 총평 자동 삽입"]],
                        style={"color":"#475569","fontSize":"0.88rem"}),
            ],style=CARD),md=6),
            dbc.Col(html.Div([
                card_title("Word 보고서"),
                html.Ul([html.Li(t) for t in ["표지 + 점검 개요","AI 기반 자연어 총평","도메인별 상세 분석","우선순위별 시정조치 권고"]],
                        style={"color":"#475569","fontSize":"0.88rem"}),
            ],style=CARD),md=6),
        ],className="g-3 mb-3"),
        html.Div([
            dbc.Button("보고서 생성 (AI 분석 포함)", id="report-btn", color="primary", size="lg",
                       style={"borderRadius":"12px","fontWeight":"700","padding":"0.75rem 2.5rem"}),
            html.Div(id="report-result",style={"marginTop":"1rem"}),
        ],style={**CARD,"textAlign":"center","padding":"2rem"}),
    ])

@app.callback(Output("report-result","children"), Input("report-btn","n_clicks"),
              prevent_initial_call=True)
def run_report(n):
    if not n: return no_update
    try:
        r = subprocess.run([sys.executable, os.path.join(SRC_DIR,"report_generator.py")],
                           capture_output=True, text=True, timeout=120, cwd=BASE_DIR)
        if r.returncode==0:
            return dbc.Alert("완료! data/processed/report/ 폴더를 확인하세요.",color="success",style={"borderRadius":"10px"})
        return dbc.Alert(f"오류: {r.stderr[:300]}",color="danger",style={"borderRadius":"10px"})
    except Exception as e:
        return dbc.Alert(str(e),color="danger",style={"borderRadius":"10px"})

if __name__ == "__main__":
    print("="*50)
    print("  AI IT감사 대시보드")
    print("  http://localhost:8050")
    print("="*50)
    app.run(debug=False, port=8050)
