"""
AI 기반 IT감사 사전 통제 점검 시스템
Dash + Bootstrap 대시보드
"""

import os, glob, re, json, subprocess, sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from dash import Dash, html, dcc, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc

# ── 경로 ──────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(BASE_DIR, "data", "processed")
DB_DIR       = os.path.join(DATA_DIR, "virtual_db")
SRC_DIR      = os.path.join(BASE_DIR, "src")
SUMMARY_PATH = os.path.join(DATA_DIR, "violations_summary.csv")

# ── 상수 ──────────────────────────────────────────────────────
DOMAIN_COLORS = {"접근통제": "#6366f1", "변경관리": "#f59e0b", "운영통제": "#10b981"}
SEV_COLORS    = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}
SYS_MAP       = {"CRED":"신용평가시스템","PORTAL":"고객포털",
                 "ERP":"경영관리시스템","DW":"데이터웨어하우스","DEVP":"ITSM"}

def detect_months():
    files = glob.glob(os.path.join(DATA_DIR, "violations_summary_????-??.csv"))
    months = sorted({re.search(r"(\d{4}-\d{2})", os.path.basename(f)).group(1)
                     for f in files if re.search(r"(\d{4}-\d{2})", f)})
    return months if months else []

AVAILABLE_MONTHS = detect_months()
MONTH_LABELS = {m: datetime.strptime(m, "%Y-%m").strftime("%Y년 %m월")
                for m in AVAILABLE_MONTHS}

# ── 데이터 로드 ────────────────────────────────────────────────
def load_summary(month=None):
    if month:
        path = os.path.join(DATA_DIR, f"violations_summary_{month}.csv")
        if os.path.exists(path):
            return pd.read_csv(path, encoding="utf-8-sig")
    if os.path.exists(SUMMARY_PATH):
        return pd.read_csv(SUMMARY_PATH, encoding="utf-8-sig")
    return None

def load_db(fname):
    path = os.path.join(DB_DIR, fname)
    if os.path.exists(path):
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()

def load_all_db():
    dfs = {k: load_db(v) for k, v in {
        "emp": "emp_master.csv", "account": "sys_account.csv",
        "access": "access_log.csv", "deploy": "deploy_log.csv",
        "backup": "backup_log.csv", "itsm": "itsm_req.csv"
    }.items()}
    for df in [dfs["account"], dfs["access"], dfs["deploy"], dfs["backup"]]:
        if "system_cd" in df.columns:
            df["system_nm"] = df["system_cd"].map(SYS_MAP).fillna(df["system_cd"])
    for col in ["hire_dt","resign_dt"]:
        if col in dfs["emp"].columns:
            dfs["emp"][col] = pd.to_datetime(dfs["emp"][col], errors="coerce")
    for df, cols in [(dfs["account"],["last_review_dt"]),(dfs["access"],["access_dt"]),
                     (dfs["deploy"],["deploy_dt"]),(dfs["backup"],["backup_dt"])]:
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
    return dfs

def calc_risk_score(df):
    sev = {"HIGH":3,"MEDIUM":2,"LOW":1}
    df = df.copy()
    df["sev_score"] = df["severity"].map(sev).fillna(1)
    df["risk_score"] = (df["sev_score"] * np.log1p(df["violation_count"])).round(2)
    df["risk_score"] = df["risk_score"].where(df["yn_violation"]=="Y", 0)
    def grade(s):
        if s>=8: return "Critical","#8B0000"
        elif s>=5: return "High","#ef4444"
        elif s>=2: return "Medium","#f59e0b"
        elif s>0: return "Low","#10b981"
        return "정상","#94a3b8"
    df[["risk_grade","risk_color"]] = df["risk_score"].apply(lambda s: pd.Series(grade(s)))
    return df

# ── Dash 앱 초기화 ─────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap",
    ],
    suppress_callback_exceptions=True,
)
app.title = "AI IT감사 점검 시스템"

# ── 스타일 ────────────────────────────────────────────────────
CARD_STYLE = {
    "background": "white",
    "borderRadius": "16px",
    "padding": "1.2rem",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.06)",
    "border": "1px solid #f1f5f9",
    "marginBottom": "1rem",
}
SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0,
    "width": "230px", "padding": "1.5rem 1rem",
    "background": "white",
    "borderRight": "1px solid #e2e8f0",
    "overflowY": "auto", "zIndex": 100,
}
CONTENT_STYLE = {
    "marginLeft": "230px",
    "padding": "1.5rem",
    "background": "#f1f5f9",
    "minHeight": "100vh",
}
NAV_LINK_STYLE = {
    "display": "block", "padding": "0.55rem 0.9rem",
    "borderRadius": "10px", "marginBottom": "4px",
    "color": "#64748b", "textDecoration": "none",
    "fontSize": "0.88rem", "fontWeight": "500",
    "cursor": "pointer", "transition": "all 0.15s",
    "fontFamily": "Inter, sans-serif",
}
NAV_ACTIVE_STYLE = {
    **NAV_LINK_STYLE,
    "background": "#eff6ff", "color": "#3b82f6",
    "fontWeight": "700", "borderLeft": "3px solid #6366f1",
}

def kpi_card(value, label, color, sub=None):
    return html.Div([
        html.Div(str(value), style={
            "fontSize": "2.2rem", "fontWeight": "900",
            "color": color, "lineHeight": "1.1",
            "fontFamily": "Inter, sans-serif",
        }),
        html.Div(label, style={
            "fontSize": "0.75rem", "color": "#64748b",
            "fontWeight": "600", "textTransform": "uppercase",
            "letterSpacing": "0.05em", "marginTop": "0.3rem",
        }),
        html.Div(sub, style={"fontSize":"0.72rem","color":"#94a3b8","marginTop":"0.2rem"}) if sub else None,
    ], style={
        **CARD_STYLE,
        "borderLeft": f"4px solid {color}",
        "padding": "1rem 1.2rem",
    })

def section_header(title, sub=None):
    return html.Div([
        html.H4(title, style={
            "fontWeight": "800", "color": "#0f172a",
            "letterSpacing": "-0.03em", "marginBottom": "0.2rem",
            "fontFamily": "Inter, sans-serif",
        }),
        html.P(sub, style={"color":"#94a3b8","fontSize":"0.83rem","marginBottom":"1rem"}) if sub else None,
    ])

def hero_banner(month, df):
    total = len(df)
    viol  = int((df["yn_violation"]=="Y").sum())
    high  = int(((df["severity"]=="HIGH")&(df["yn_violation"]=="Y")).sum())
    rate  = round(viol/total*100) if total else 0
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H3("IT감사 통제 점검 현황", style={
                    "fontWeight":"900","color":"white","marginBottom":"0.3rem",
                    "fontFamily":"Inter, sans-serif",
                }),
                html.P(f"{MONTH_LABELS.get(month, month)} 기준  ·  AI 기반 자동 탐지",
                       style={"color":"rgba(255,255,255,0.8)","fontSize":"0.9rem"}),
            ], width=6),
            dbc.Col([
                dbc.Row([
                    dbc.Col(html.Div([
                        html.Div(str(total), style={"fontSize":"2rem","fontWeight":"900","color":"white"}),
                        html.Div("점검 규칙", style={"fontSize":"0.75rem","color":"rgba(255,255,255,0.75)"}),
                    ], style={"textAlign":"center"})),
                    dbc.Col(html.Div([
                        html.Div(str(viol), style={"fontSize":"2rem","fontWeight":"900","color":"#fca5a5"}),
                        html.Div("위반 탐지", style={"fontSize":"0.75rem","color":"rgba(255,255,255,0.75)"}),
                    ], style={"textAlign":"center"})),
                    dbc.Col(html.Div([
                        html.Div(str(high), style={"fontSize":"2rem","fontWeight":"900","color":"#fde68a"}),
                        html.Div("HIGH 위반", style={"fontSize":"0.75rem","color":"rgba(255,255,255,0.75)"}),
                    ], style={"textAlign":"center"})),
                    dbc.Col(html.Div([
                        html.Div(f"{rate}%", style={"fontSize":"2rem","fontWeight":"900","color":"#6ee7b7"}),
                        html.Div("위반율", style={"fontSize":"0.75rem","color":"rgba(255,255,255,0.75)"}),
                    ], style={"textAlign":"center"})),
                ])
            ], width=6),
        ])
    ], style={
        "background": "linear-gradient(135deg, #6366f1 0%, #3b82f6 60%, #06b6d4 100%)",
        "borderRadius": "20px", "padding": "1.8rem 2rem", "marginBottom": "1.2rem",
    })

# ── 레이아웃 ──────────────────────────────────────────────────
def make_sidebar(active_page):
    nav_items = [
        ("overview",  "전체 개요"),
        ("access",    "접근통제"),
        ("change",    "변경관리"),
        ("ops",       "운영통제"),
        ("analysis",  "심화 분석"),
        ("scan",      "점검 실행"),
        ("report",    "보고서 생성"),
    ]
    nav_links = []
    for page, label in nav_items:
        style = NAV_ACTIVE_STYLE if page == active_page else NAV_LINK_STYLE
        nav_links.append(
            html.Div(label, id=f"nav-{page}", n_clicks=0, style=style)
        )

    month_opts = [{"label": MONTH_LABELS.get(m, m), "value": m} for m in AVAILABLE_MONTHS]
    default_month = AVAILABLE_MONTHS[-1] if AVAILABLE_MONTHS else None

    return html.Div([
        # 로고
        html.Div([
            html.Span("IT", style={"color":"#6366f1","fontWeight":"900"}),
            html.Span("감사 시스템", style={"color":"#1e293b","fontWeight":"900"}),
        ], style={"fontSize":"1.25rem","fontFamily":"Inter, sans-serif","marginBottom":"0.3rem"}),
        html.P("AI-Powered Audit Control",
               style={"color":"#94a3b8","fontSize":"0.72rem","marginBottom":"1.5rem"}),
        html.Hr(style={"borderColor":"#e2e8f0","marginBottom":"1.2rem"}),

        # 분석 월
        html.P("분석 월", style={"color":"#94a3b8","fontSize":"0.72rem",
                                "fontWeight":"700","letterSpacing":"0.08em","marginBottom":"0.4rem"}),
        dcc.Dropdown(
            id="month-selector",
            options=month_opts,
            value=default_month,
            clearable=False,
            style={"fontSize":"0.85rem","marginBottom":"1rem"},
        ),

        html.Hr(style={"borderColor":"#e2e8f0","margin":"1rem 0"}),

        # 내비게이션
        html.P("MENU", style={"color":"#94a3b8","fontSize":"0.7rem",
                              "fontWeight":"700","letterSpacing":"0.1em","marginBottom":"0.5rem"}),
        *nav_links,

        html.Hr(style={"borderColor":"#e2e8f0","margin":"1rem 0"}),
        html.Div(id="last-scan-info", style={"color":"#94a3b8","fontSize":"0.72rem"}),
    ], style=SIDEBAR_STYLE)

app.layout = html.Div([
    dcc.Store(id="current-page", data="overview"),
    dcc.Store(id="last-scan-time", data=None),
    dcc.Interval(id="scan-interval", interval=2000, disabled=True),

    html.Div(id="sidebar-container"),
    html.Div(id="page-content", style=CONTENT_STYLE),
])

# ── 콜백: 사이드바 렌더 ────────────────────────────────────────
@app.callback(
    Output("sidebar-container", "children"),
    Input("current-page", "data"),
)
def render_sidebar(page):
    return make_sidebar(page or "overview")

# ── 콜백: 페이지 라우팅 ────────────────────────────────────────
@app.callback(
    Output("current-page", "data"),
    [Input(f"nav-{p}", "n_clicks") for p in
     ["overview","access","change","ops","analysis","scan","report"]],
    State("current-page", "data"),
    prevent_initial_call=True,
)
def route(*args):
    ctx = callback_context
    if not ctx.triggered: return no_update
    btn_id = ctx.triggered[0]["prop_id"].split(".")[0]
    page = btn_id.replace("nav-","")
    return page

# ── 콜백: 페이지 콘텐츠 ───────────────────────────────────────
@app.callback(
    Output("page-content", "children"),
    Input("current-page", "data"),
    Input("month-selector", "value"),
)
def render_page(page, month):
    page = page or "overview"
    df = load_summary(month)

    if page == "overview":   return page_overview(df, month)
    if page == "access":     return page_domain(df, month, "접근통제")
    if page == "change":     return page_domain(df, month, "변경관리")
    if page == "ops":        return page_domain(df, month, "운영통제")
    if page == "analysis":   return page_analysis(df, month)
    if page == "scan":       return page_scan(month)
    if page == "report":     return page_report(df, month)
    return html.Div("페이지를 찾을 수 없습니다.")

# ══════════════════════════════════════════════════════════════
# PAGE: 전체 개요
# ══════════════════════════════════════════════════════════════
def page_overview(df, month):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다. 점검 실행 메뉴에서 먼저 점검을 실행해주세요.",
                         color="warning")

    total = len(df)
    viol  = int((df["yn_violation"]=="Y").sum())
    high  = int(((df["severity"]=="HIGH")&(df["yn_violation"]=="Y")).sum())
    clean = total - viol

    domain_sum = df.groupby("audit_domain").agg(
        전체=("rule_id","count"),
        위반=("yn_violation", lambda x: (x=="Y").sum()),
        총건수=("violation_count","sum"),
    ).reset_index()
    domain_sum["위반율"] = (domain_sum["위반"]/domain_sum["전체"]*100).round(1)

    # 도메인별 막대
    fig_domain = go.Figure()
    for _, row in domain_sum.iterrows():
        color = DOMAIN_COLORS.get(row["audit_domain"], "#94a3b8")
        fig_domain.add_trace(go.Bar(
            name=row["audit_domain"], x=[row["audit_domain"]],
            y=[row["위반"]], marker_color=color,
            text=[f"{row['위반']}개"], textposition="outside",
        ))
    fig_domain.update_layout(**chart_layout(height=280, showlegend=False))
    fig_domain.update_yaxis(title="위반 규칙 수")

    # 심각도 도넛
    sev_data = (df[df["yn_violation"]=="Y"]
                .groupby("severity")["rule_id"].count()
                .reindex(["HIGH","MEDIUM","LOW"]).fillna(0).reset_index())
    fig_sev = go.Figure(go.Pie(
        labels=sev_data["severity"], values=sev_data["rule_id"],
        hole=0.62,
        marker_colors=[SEV_COLORS.get(s,"#ccc") for s in sev_data["severity"]],
        textinfo="label+percent", textfont=dict(size=12),
    ))
    fig_sev.update_layout(**chart_layout(height=280, showlegend=False))
    fig_sev.add_annotation(text=f"<b>{viol}</b><br>위반", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=16, color="#1e293b"))

    # 위반 TOP 10
    top10 = df[df["yn_violation"]=="Y"].nlargest(10,"violation_count")
    fig_top = go.Figure(go.Bar(
        x=top10["violation_count"][::-1],
        y=[f"{r} {n[:12]}" for r,n in zip(top10["rule_id"][::-1], top10["rule_nm"][::-1])],
        orientation="h",
        marker_color=[DOMAIN_COLORS.get(d,"#94a3b8") for d in top10["audit_domain"][::-1]],
        text=top10["violation_count"][::-1], textposition="outside",
    ))
    fig_top.update_layout(**chart_layout(height=320))
    fig_top.update_xaxis(title="위반 건수")

    return html.Div([
        hero_banner(month, df),

        # KPI 행
        dbc.Row([
            dbc.Col(kpi_card(f"{total}개", "총 점검 규칙", "#6366f1"), md=3),
            dbc.Col(kpi_card(f"{viol}개", "위반 탐지", "#ef4444",
                             f"전체의 {round(viol/total*100)}%"), md=3),
            dbc.Col(kpi_card(f"{high}개", "HIGH 위반", "#f59e0b",
                             "즉각 조치 필요"), md=3),
            dbc.Col(kpi_card(f"{clean}개", "이상 없음", "#10b981",
                             f"준수율 {round(clean/total*100)}%"), md=3),
        ], className="g-3 mb-3"),

        # 차트 행
        dbc.Row([
            dbc.Col(html.Div([
                html.P("도메인별 위반 규칙 수", style=card_title_style()),
                dcc.Graph(figure=fig_domain, config={"displayModeBar":False}),
            ], style=CARD_STYLE), md=4),
            dbc.Col(html.Div([
                html.P("심각도별 위반 비율", style=card_title_style()),
                dcc.Graph(figure=fig_sev, config={"displayModeBar":False}),
            ], style=CARD_STYLE), md=3),
            dbc.Col(html.Div([
                html.P("위반 건수 TOP 10", style=card_title_style()),
                dcc.Graph(figure=fig_top, config={"displayModeBar":False}),
            ], style=CARD_STYLE), md=5),
        ], className="g-3"),

        # 도메인 요약 테이블
        html.Div([
            html.P("도메인별 위반 현황 요약", style=card_title_style()),
            dbc.Table.from_dataframe(
                domain_sum.rename(columns={
                    "audit_domain":"감사 도메인","전체":"전체 규칙","위반":"위반 규칙",
                    "총건수":"총 위반 건수","위반율":"위반율(%)"
                }),
                striped=True, hover=True, responsive=True,
                style={"fontSize":"0.88rem"},
            ),
        ], style=CARD_STYLE),
    ])

# ══════════════════════════════════════════════════════════════
# PAGE: 도메인 상세
# ══════════════════════════════════════════════════════════════
def page_domain(df, month, domain):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다.", color="warning")

    sub = df[df["audit_domain"]==domain].copy()
    viol = sub[sub["yn_violation"]=="Y"]
    total = len(sub)
    viol_cnt = len(viol)
    pass_rate = round((total-viol_cnt)/total*100) if total else 0
    color = DOMAIN_COLORS.get(domain, "#6366f1")

    # 심각도 파이
    sev_data = (viol.groupby("severity")["rule_id"].count()
                .reindex(["HIGH","MEDIUM","LOW"]).fillna(0).reset_index())
    fig_pie = go.Figure(go.Pie(
        labels=sev_data["severity"], values=sev_data["rule_id"],
        hole=0.6, marker_colors=[SEV_COLORS.get(s,"#ccc") for s in sev_data["severity"]],
        textinfo="label+percent",
    ))
    fig_pie.update_layout(**chart_layout(height=260, showlegend=False))
    fig_pie.add_annotation(text=f"<b>{viol_cnt}</b><br>위반", x=0.5, y=0.5,
                           showarrow=False, font=dict(size=14))

    # 위반 건수 바
    if len(viol) > 0:
        top_viol = viol.nlargest(min(8,len(viol)),"violation_count")
        fig_bar = go.Figure(go.Bar(
            x=top_viol["violation_count"][::-1],
            y=[f"{r}\n{n[:10]}" for r,n in zip(top_viol["rule_id"][::-1],top_viol["rule_nm"][::-1])],
            orientation="h",
            marker_color=color, opacity=0.85,
            text=top_viol["violation_count"][::-1], textposition="outside",
        ))
        fig_bar.update_layout(**chart_layout(height=260))
    else:
        fig_bar = go.Figure()
        fig_bar.update_layout(**chart_layout(height=260))

    # 위반 규칙 테이블
    tbl_df = (viol.sort_values("violation_count", ascending=False)
              [["rule_id","rule_nm","severity","violation_count","remediation"]]
              .rename(columns={"rule_id":"ID","rule_nm":"규칙명","severity":"심각도",
                               "violation_count":"위반 건수","remediation":"시정조치"}))

    return html.Div([
        section_header(f"{domain} 상세",
                       f"{MONTH_LABELS.get(month,month)} 기준"),
        dbc.Row([
            dbc.Col(kpi_card(f"{total}개", "점검 규칙", color), md=3),
            dbc.Col(kpi_card(f"{viol_cnt}개", "위반 탐지", "#ef4444"), md=3),
            dbc.Col(kpi_card(f"{total-viol_cnt}개", "이상 없음", "#10b981"), md=3),
            dbc.Col(kpi_card(f"{pass_rate}%", "준수율", "#6366f1"), md=3),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(html.Div([
                html.P("심각도별 위반 비율", style=card_title_style()),
                dcc.Graph(figure=fig_pie, config={"displayModeBar":False}),
            ], style=CARD_STYLE), md=4),
            dbc.Col(html.Div([
                html.P("위반 건수 TOP 8", style=card_title_style()),
                dcc.Graph(figure=fig_bar, config={"displayModeBar":False}),
            ], style=CARD_STYLE), md=8),
        ], className="g-3 mb-3"),
        html.Div([
            html.P("위반 규칙 상세 목록", style=card_title_style()),
            dbc.Table.from_dataframe(tbl_df, striped=True, hover=True,
                                     responsive=True, style={"fontSize":"0.85rem"}),
        ], style=CARD_STYLE),
    ])

# ══════════════════════════════════════════════════════════════
# PAGE: 심화 분석
# ══════════════════════════════════════════════════════════════
def page_analysis(df, month):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다.", color="warning")

    dfs = load_all_db()
    emp = dfs["emp"]; account = dfs["account"]; access = dfs["access"]
    deploy = dfs["deploy"]; backup = dfs["backup"]

    # 부서별 위험도
    resigned = set(emp[emp["yn_employed"]=="N"]["emp_id"])
    active_res = account[account["emp_id"].isin(resigned) &
                         (account["account_status"]=="active")
                        ].merge(emp[["emp_id","dept_nm"]], on="emp_id", how="left")
    overdue = account[account["yn_overdue_review"]=="Y"].merge(
        emp[["emp_id","dept_nm"]], on="emp_id", how="left")
    after_h = access[access["yn_after_hours"]=="Y"].merge(
        emp[["emp_id","dept_nm"]], on="emp_id", how="left")

    dept_risk = pd.concat([
        active_res.groupby("dept_nm").size().rename("퇴사자계정"),
        overdue.groupby("dept_nm").size().rename("권한검토초과"),
        after_h.groupby("dept_nm").size().rename("시간외접속"),
    ], axis=1).fillna(0).astype(int)
    dept_risk["위험점수"] = dept_risk["퇴사자계정"]*3 + dept_risk["권한검토초과"]*2 + dept_risk["시간외접속"]
    dept_risk = dept_risk.sort_values("위험점수", ascending=False)

    fig_heat = go.Figure(go.Heatmap(
        z=dept_risk[["퇴사자계정","권한검토초과","시간외접속"]].head(12).values,
        x=["퇴사자계정","권한검토초과","시간외접속"],
        y=dept_risk.head(12).index.tolist(),
        colorscale="YlOrRd", texttemplate="%{z}",
        hovertemplate="%{y}<br>%{x}: %{z}건<extra></extra>",
    ))
    fig_heat.update_layout(**chart_layout(height=350))

    top_dept = dept_risk.head(10).reset_index()
    fig_dept = go.Figure(go.Bar(
        x=top_dept["위험점수"], y=top_dept["dept_nm"],
        orientation="h",
        marker_color=["#ef4444" if s>=10 else "#f59e0b" if s>=5 else "#6366f1"
                      for s in top_dept["위험점수"]],
        text=top_dept["위험점수"], textposition="outside",
    ))
    fig_dept.update_layout(**chart_layout(height=320))
    fig_dept.update_yaxis(autorange="reversed")

    # 리스크 점수화
    df_r = calc_risk_score(df)
    grade_cnt = df_r.groupby("risk_grade").size().reset_index()
    grade_cnt.columns = ["등급","건수"]
    grade_order = ["Critical","High","Medium","Low","정상"]
    grade_colors_map = {"Critical":"#8B0000","High":"#ef4444","Medium":"#f59e0b",
                        "Low":"#10b981","정상":"#94a3b8"}
    grade_cnt["등급"] = pd.Categorical(grade_cnt["등급"], categories=grade_order, ordered=True)
    grade_cnt = grade_cnt.sort_values("등급")

    fig_grade = go.Figure(go.Pie(
        labels=grade_cnt["등급"], values=grade_cnt["건수"], hole=0.55,
        marker_colors=[grade_colors_map.get(g,"#ccc") for g in grade_cnt["등급"]],
        textinfo="label+value",
    ))
    fig_grade.update_layout(**chart_layout(height=280, showlegend=False))

    top_risk = df_r[df_r["risk_score"]>0].nlargest(10,"risk_score")
    fig_risk = go.Figure(go.Bar(
        x=top_risk["risk_score"][::-1],
        y=[f"{r} {n[:10]}" for r,n in zip(top_risk["rule_id"][::-1],top_risk["rule_nm"][::-1])],
        orientation="h",
        marker_color=[grade_colors_map.get(g,"#ccc") for g in top_risk["risk_grade"][::-1]],
        text=top_risk["risk_score"][::-1].round(1), textposition="outside",
    ))
    fig_risk.update_layout(**chart_layout(height=280))

    # 법령 준수율
    law_total = df.groupby("source_law").size()
    law_viol  = df[df["yn_violation"]=="Y"].groupby("source_law").size()
    law_comp  = ((1 - law_viol/law_total)*100).round(1).reset_index()
    law_comp.columns = ["법령명","준수율(%)"]
    law_comp = law_comp.sort_values("준수율(%)")
    fig_law = go.Figure(go.Bar(
        x=law_comp["준수율(%)"], y=law_comp["법령명"],
        orientation="h",
        marker_color=["#ef4444" if v<50 else "#f59e0b" if v<75 else "#10b981"
                      for v in law_comp["준수율(%)"]],
        text=[f"{v}%" for v in law_comp["준수율(%)"]],
        textposition="outside",
    ))
    fig_law.update_layout(**chart_layout(height=300))
    fig_law.update_xaxis(range=[0,115])

    return html.Div([
        section_header("심화 분석", f"{MONTH_LABELS.get(month,month)} 기준 · DB 데이터 자동 분석"),

        dbc.Tabs([
            dbc.Tab(label="부서별 위험도", children=[
                html.Div(style={"height":"1rem"}),
                dbc.Row([
                    dbc.Col(html.Div([
                        html.P("부서별 위반 히트맵", style=card_title_style()),
                        dcc.Graph(figure=fig_heat, config={"displayModeBar":False}),
                    ], style=CARD_STYLE), md=6),
                    dbc.Col(html.Div([
                        html.P("부서별 종합 위험점수 TOP 10", style=card_title_style()),
                        dcc.Graph(figure=fig_dept, config={"displayModeBar":False}),
                    ], style=CARD_STYLE), md=6),
                ], className="g-3"),
            ]),
            dbc.Tab(label="리스크 점수화", children=[
                html.Div(style={"height":"1rem"}),
                dbc.Row([
                    dbc.Col(html.Div([
                        html.P("위험 등급 분포", style=card_title_style()),
                        dcc.Graph(figure=fig_grade, config={"displayModeBar":False}),
                    ], style=CARD_STYLE), md=4),
                    dbc.Col(html.Div([
                        html.P("고위험 규칙 TOP 10", style=card_title_style()),
                        dcc.Graph(figure=fig_risk, config={"displayModeBar":False}),
                    ], style=CARD_STYLE), md=8),
                ], className="g-3"),
            ]),
            dbc.Tab(label="법령 준수율", children=[
                html.Div(style={"height":"1rem"}),
                html.Div([
                    html.P("법령별 규칙 준수율", style=card_title_style()),
                    dcc.Graph(figure=fig_law, config={"displayModeBar":False}),
                ], style=CARD_STYLE),
            ]),
        ], style={"marginBottom":"1rem"}),
    ])

# ══════════════════════════════════════════════════════════════
# PAGE: 점검 실행
# ══════════════════════════════════════════════════════════════
def page_scan(month):
    df_acc = load_db("access_log.csv")
    df_dep = load_db("deploy_log.csv")
    df_bak = load_db("backup_log.csv")
    total_logs = len(df_acc) + len(df_dep) + len(df_bak)
    month_label = MONTH_LABELS.get(month, month) if month else "-"

    return html.Div([
        section_header("점검 실행", "Rule 엔진을 실행하여 위반 사항을 자동 탐지합니다"),

        dbc.Row([
            dbc.Col(kpi_card(f"{total_logs:,}건", "분석 대상 로그", "#6366f1"), md=3),
            dbc.Col(kpi_card("70개", "점검 규칙", "#3b82f6"), md=3),
            dbc.Col(kpi_card("3개", "점검 도메인", "#10b981"), md=3),
            dbc.Col(kpi_card(month_label, "선택 월", "#f59e0b"), md=3),
        ], className="g-3 mb-4"),

        dbc.Row([
            dbc.Col(html.Div([
                html.P("점검 영역", style=card_title_style()),
                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardBody([
                            html.H5("접근통제", className="card-title"),
                            html.P("계정·권한·퇴직자 관리", className="card-text text-muted"),
                        ])
                    ], color="primary", outline=True), md=4),
                    dbc.Col(dbc.Card([
                        dbc.CardBody([
                            html.H5("변경관리", className="card-title"),
                            html.P("CR·배포·직무분리", className="card-text text-muted"),
                        ])
                    ], color="warning", outline=True), md=4),
                    dbc.Col(dbc.Card([
                        dbc.CardBody([
                            html.H5("운영통제", className="card-title"),
                            html.P("로그·백업·권한검토", className="card-text text-muted"),
                        ])
                    ], color="success", outline=True), md=4),
                ], className="g-2"),
            ], style=CARD_STYLE)),
        ], className="mb-4"),

        html.Div([
            dbc.Button("점검 실행", id="scan-btn", color="primary", size="lg",
                       style={"borderRadius":"12px","fontWeight":"700",
                              "padding":"0.75rem 2.5rem","fontSize":"1rem"}),
            html.Div(id="scan-status", style={"marginTop":"1rem"}),
        ], style={**CARD_STYLE, "textAlign":"center", "padding":"2rem"}),
    ])

@app.callback(
    Output("scan-status", "children"),
    Input("scan-btn", "n_clicks"),
    State("month-selector", "value"),
    prevent_initial_call=True,
)
def run_scan(n, month):
    if not n: return no_update
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SRC_DIR, "rule_engine.py")],
            capture_output=True, text=True, timeout=120,
            cwd=BASE_DIR,
        )
        if result.returncode == 0:
            return dbc.Alert("점검 완료! 좌측 메뉴에서 결과를 확인하세요.", color="success")
        else:
            return dbc.Alert(f"오류 발생: {result.stderr[:200]}", color="danger")
    except Exception as e:
        return dbc.Alert(f"실행 오류: {str(e)}", color="danger")

# ══════════════════════════════════════════════════════════════
# PAGE: 보고서 생성
# ══════════════════════════════════════════════════════════════
def page_report(df, month):
    if df is None:
        return dbc.Alert("점검 결과가 없습니다.", color="warning")

    total = len(df)
    viol  = int((df["yn_violation"]=="Y").sum())

    return html.Div([
        section_header("보고서 생성", "AI 분석이 포함된 Excel·Word 보고서를 자동 생성합니다"),

        dbc.Row([
            dbc.Col(kpi_card(f"{total}개", "점검 규칙", "#6366f1"), md=3),
            dbc.Col(kpi_card(f"{viol}개", "위반 탐지", "#ef4444"), md=3),
            dbc.Col(kpi_card(datetime.now().strftime("%Y.%m.%d"), "기준일", "#10b981"), md=3),
            dbc.Col(kpi_card("Claude AI", "분석 엔진", "#f59e0b"), md=3),
        ], className="g-3 mb-4"),

        dbc.Row([
            dbc.Col(html.Div([
                html.P("Excel 보고서", style=card_title_style()),
                html.Ul([
                    html.Li("규칙별 위반 현황표 (4개 시트)"),
                    html.Li("도메인별 요약 집계"),
                    html.Li("심각도별 분류 및 색상 표시"),
                    html.Li("AI 총평 자동 삽입"),
                ], style={"color":"#475569","fontSize":"0.88rem"}),
            ], style=CARD_STYLE), md=6),
            dbc.Col(html.Div([
                html.P("Word 보고서", style=card_title_style()),
                html.Ul([
                    html.Li("표지 + 점검 개요"),
                    html.Li("AI 기반 자연어 총평"),
                    html.Li("도메인별 상세 분석"),
                    html.Li("우선순위별 시정조치 권고"),
                ], style={"color":"#475569","fontSize":"0.88rem"}),
            ], style=CARD_STYLE), md=6),
        ], className="g-3 mb-4"),

        html.Div([
            dbc.Button("보고서 생성 (AI 분석 포함)", id="report-btn", color="primary", size="lg",
                       style={"borderRadius":"12px","fontWeight":"700",
                              "padding":"0.75rem 2.5rem","fontSize":"1rem"}),
            html.Div(id="report-status", style={"marginTop":"1rem"}),
        ], style={**CARD_STYLE, "textAlign":"center", "padding":"2rem"}),
    ])

@app.callback(
    Output("report-status", "children"),
    Input("report-btn", "n_clicks"),
    prevent_initial_call=True,
)
def run_report(n):
    if not n: return no_update
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SRC_DIR, "report_generator.py")],
            capture_output=True, text=True, timeout=120, cwd=BASE_DIR,
        )
        if result.returncode == 0:
            return dbc.Alert("보고서 생성 완료! data/processed/report/ 폴더를 확인하세요.",
                             color="success")
        else:
            return dbc.Alert(f"오류: {result.stderr[:200]}", color="danger")
    except Exception as e:
        return dbc.Alert(f"실행 오류: {str(e)}", color="danger")

# ── 헬퍼 ──────────────────────────────────────────────────────
def chart_layout(height=300, showlegend=True):
    return dict(
        height=height, showlegend=showlegend,
        margin=dict(l=10, r=60, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color="#475569", size=11),
        xaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0", tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0", tickfont=dict(size=10)),
        legend=dict(font=dict(size=11)),
    )

def card_title_style():
    return {
        "fontSize":"0.78rem","fontWeight":"700","color":"#94a3b8",
        "textTransform":"uppercase","letterSpacing":"0.07em",
        "marginBottom":"0.75rem","paddingBottom":"0.5rem",
        "borderBottom":"1px solid #f1f5f9","fontFamily":"Inter, sans-serif",
    }

if __name__ == "__main__":
    print("=" * 50)
    print("  AI IT감사 대시보드 시작")
    print("  http://localhost:8050")
    print("=" * 50)
    app.run(debug=False, port=8050)
