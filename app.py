"""
AI 기반 IT감사 사전 통제 점검 시스템 v4
"""

import os, sys, subprocess, json, glob, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
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
DOMAIN_COLORS = {"접근통제": "#60a5fa", "변경관리": "#a78bfa", "운영통제": "#22d3ee"}
DOMAIN_ICON   = {"접근통제": "", "변경관리": "", "운영통제": ""}
DOMAIN_LOG_MAP = {"접근통제": "access_log.csv", "변경관리": "deploy_log.csv",
                  "운영통제": "backup_log.csv"}
SEV_COLORS    = {"HIGH": "#fb7185", "MEDIUM": "#fbbf24", "LOW": "#34d399"}

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
    initial_sidebar_state="collapsed",
)

# ── CSS (블루-화이트 글래스모피즘) ─────────────────────────────
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
@import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css');

/* ── CSS 변수 ── */
:root {
    --primary:      #2563eb;
    --primary-lt:   #eff6ff;
    --primary-dk:   #1e40af;
    --sky:          #0ea5e9;
    --blue:         #2563eb;
    --cyan:         #0891b2;
    --bg:           #f7faff;
    --glass:        #ffffff;
    --glass-border: #e6edfb;
    --border:       #e6edfb;
    --text:         #0f172a;
    --text-sub:     #475569;
    --text-muted:   #94a3b8;
}

/* ── Streamlit 기본 헤더/툴바/배지 숨김 ── */
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stToolbar"]   { display: none !important; }
div[data-testid="stDecoration"]{ display: none !important; }
div[data-testid="stStatusWidget"] { display: none !important; }
[class*="viewerBadge"] { display: none !important; }
[data-testid="stAppViewBadge"] { display: none !important; }
a[href^="https://streamlit.io"] { display: none !important; }
a[href*="streamlit.io/cloud"] { display: none !important; }
/* Streamlit Cloud viewer badge (CSS module: _link_/_profileContainer_) */
[class^="_link_"], [class*=" _link_"] { display: none !important; }
[class^="_profileContainer_"], [class*=" _profileContainer_"] { display: none !important; }
[class^="_container_"][class*="_link_"] { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }
.main .block-container { padding-top: 0.8rem !important; }

/* ── 폰트 ── */
html, body, [class*="css"], .stApp, .stApp * {
    font-family: 'Pretendard Variable', Pretendard, 'Inter', -apple-system, sans-serif !important;
    letter-spacing: -0.01em;
}
.fa-solid, .fa-regular, .fa-brands, [class*="fa-"] {
    font-family: 'Font Awesome 6 Free' !important;
}
/* Material 아이콘 폰트 복원 (전역 폰트 강제의 예외) */
span[data-testid="stIconMaterial"],
.material-symbols-rounded, .material-symbols-outlined, .material-icons,
[class*="material-symbols"] {
    font-family: 'Material Symbols Rounded' !important;
    letter-spacing: normal !important;
}

/* ── 전체 배경: 밝은 화이트 + 상단 옅은 글로우 ── */
.stApp {
    background-color: var(--bg) !important;
    background-image:
        radial-gradient(at 50% -5%, rgba(96,165,250,0.12) 0px, transparent 42%),
        radial-gradient(at 95% 2%,  rgba(125,211,252,0.10) 0px, transparent 38%) !important;
    background-attachment: fixed !important;
}
.main .block-container {
    padding: 1.2rem 1.6rem 1.8rem !important;
    max-width: 100% !important;
}

/* ── 사이드바 — 화이트 글래스 ── */
section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.55) !important;
    backdrop-filter: blur(24px) !important;
    -webkit-backdrop-filter: blur(24px) !important;
    border-right: 1px solid rgba(255,255,255,0.9) !important;
    box-shadow: 4px 0 24px rgba(37,99,235,0.06) !important;
}
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span {
    color: var(--text-sub) !important;
}
/* 셀렉트박스 컨테이너 */
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: rgba(255,255,255,0.8) !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}
/* 셀렉트박스 선택된 값 텍스트 */
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] div,
section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span,
section[data-testid="stSidebar"] .stSelectbox input {
    color: var(--text) !important;
    background: transparent !important;
}
/* 멀티셀렉트 입력 영역 */
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] div,
section[data-testid="stSidebar"] .stMultiSelect input {
    color: var(--text) !important;
    background: transparent !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(37,99,235,0.12) !important;
}

/* ── 카드 — 글래스 ── */
.dash-card {
    background: #ffffff;
    border-radius: 18px;
    padding: 1.1rem 1.2rem 1rem;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04), 0 6px 20px rgba(15,23,42,0.06);
    margin-bottom: 0.75rem;
    border: 1px solid var(--border);
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.dash-card:hover {
    box-shadow: 0 4px 12px rgba(15,23,42,0.08), 0 12px 28px rgba(37,99,235,0.10);
    transform: translateY(-1px);
}
.card-title {
    font-size: 0.95rem; font-weight: 800;
    color: #1e293b;
    letter-spacing: -0.01em;
    margin-bottom: 0.7rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(37,99,235,0.10);
}
.card-title i { color: #3b82f6; }

/* ── KPI 카드 ── */
.kpi-box {
    background: #ffffff;
    border-radius: 18px;
    padding: 1rem 1.1rem 0.85rem;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04), 0 6px 20px rgba(15,23,42,0.06);
    border: 1px solid var(--border);
    border-top: 3px solid var(--accent);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    position: relative; overflow: hidden;
}
.kpi-box::after {
    content: '';
    position: absolute; top: 0; right: 0;
    width: 60px; height: 60px;
    background: radial-gradient(circle at top right,
        rgba(37,99,235,0.08), transparent 70%);
}
.kpi-box:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 36px rgba(37,99,235,0.18);
}
.kpi-box .val {
    font-size: 2rem; font-weight: 900;
    color: var(--accent); line-height: 1.1;
}
.kpi-box .lbl {
    font-size: 0.73rem; color: var(--text-sub);
    margin-top: 0.25rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.05em;
}
.kpi-box .dl { font-size: 0.71rem; margin-top: 0.2rem; }
.kpi-box .dl.up   { color: #2563eb; font-weight: 600; }
.kpi-box .dl.down { color: #f43f5e; font-weight: 600; }

/* ── 섹션 레이블 ── */
.section-label {
    font-size: 0.69rem; font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
    display: flex; align-items: center; gap: 6px;
}
.section-label::after {
    content: ''; flex: 1; height: 1px;
    background: rgba(37,99,235,0.12);
}

/* ── 뷰 헤더 ── */
.view-header {
    font-size: 1.35rem; font-weight: 800;
    color: var(--text);
    margin-bottom: 0.2rem; letter-spacing: -0.03em;
}
.view-sub {
    font-size: 0.8rem; color: var(--text-muted);
    margin-bottom: 0.9rem; font-weight: 500;
}

/* ── 네비 버튼 ── */
section[data-testid="stSidebar"] .stButton { margin: 1px 0 !important; }
section[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: none !important;
    border-left: 3px solid transparent !important;
    color: var(--text-sub) !important;
    text-align: left !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    border-radius: 0 12px 12px 0 !important;
    padding: 0.55rem 0.9rem !important;
    transition: all 0.15s ease !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(37,99,235,0.08) !important;
    color: var(--primary) !important;
    border-left-color: rgba(37,99,235,0.4) !important;
}
section[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: rgba(37,99,235,0.10) !important;
    color: var(--primary) !important;
    font-weight: 700 !important;
    border-left-color: var(--primary) !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stButton button[kind="primary"] * {
    color: var(--primary) !important;
}

/* ── 멀티셀렉트 태그 ── */
section[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background-color: rgba(37,99,235,0.12) !important;
    border-color: rgba(37,99,235,0.25) !important;
}
section[data-testid="stSidebar"] span[data-baseweb="tag"] span,
section[data-testid="stSidebar"] span[data-baseweb="tag"] div {
    color: var(--primary-dk) !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] span[data-baseweb="tag"] svg {
    fill: var(--primary) !important;
}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: rgba(255,255,255,0.5);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.8);
    border-radius: 14px;
    padding: 5px 6px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.84rem !important;
    color: var(--text-sub) !important;
    padding: 0.45rem 1.1rem !important;
    white-space: nowrap !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: var(--primary) !important;
    box-shadow: 0 2px 10px rgba(37,99,235,0.15) !important;
}

/* ── 데이터프레임 — 화이트 ── */
.stDataFrame, div[data-testid="stDataFrame"] {
    border-radius: 14px !important;
    overflow: hidden !important;
    border: 1px solid var(--border) !important;
    background: #ffffff !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.05), 0 4px 14px rgba(15,23,42,0.05) !important;
}
.stDataFrame [data-testid="stDataFrameResizable"],
div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {
    background: #ffffff !important;
}
/* expander도 흰 배경 */
div[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04) !important;
}
div[data-testid="stExpander"] summary { font-weight: 600 !important; }

/* ── 버튼: pill 형태 (활성 메뉴 + 액션) ── */
.main .stButton button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    box-shadow: 0 6px 18px rgba(79,70,229,0.32) !important;
    transition: all 0.18s ease !important;
}
.main .stButton button[kind="primary"]:hover {
    box-shadow: 0 8px 24px rgba(79,70,229,0.45) !important;
    transform: translateY(-1px) !important;
}
.main .stButton button[kind="primary"] * { color: #ffffff !important; }

/* ── 버튼: 비활성 메뉴 + 보조 액션 (옅은 pill) ── */
.main .stButton button[kind="secondary"] {
    background: rgba(255,255,255,0.55) !important;
    border: 1px solid transparent !important;
    border-radius: 999px !important;
    color: #64748b !important;
    font-weight: 600 !important;
    box-shadow: none !important;
    transition: all 0.18s ease !important;
}
.main .stButton button[kind="secondary"]:hover {
    background: #eef2ff !important;
    color: #4f46e5 !important;
    border-color: transparent !important;
    transform: translateY(-1px) !important;
}
.main .stButton button[kind="secondary"]:hover * { color: #4f46e5 !important; }

/* ── 상단 메뉴: 책갈피 텍스트 탭 ── */
.st-key-topnav .stButton button {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    border-bottom: 2.5px solid transparent !important;
    padding: 0.5rem 0.2rem !important;
    transition: color 0.15s ease, border-color 0.15s ease !important;
    transform: none !important;
}
.st-key-topnav .stButton button:hover { transform: none !important; }
/* 비선택 탭 — 옅은 회색 */
.st-key-topnav .stButton button[kind="secondary"] {
    color: #94a3b8 !important;
    font-weight: 500 !important;
}
.st-key-topnav .stButton button[kind="secondary"] * { color: #94a3b8 !important; }
.st-key-topnav .stButton button[kind="secondary"]:hover,
.st-key-topnav .stButton button[kind="secondary"]:hover * {
    color: #334155 !important;
    background: transparent !important;
}
/* 선택 탭 — 진한 블루 + 밑줄 */
.st-key-topnav .stButton button[kind="primary"] {
    color: #2563eb !important;
    font-weight: 800 !important;
    background: transparent !important;
    border-bottom: 2.5px solid #2563eb !important;
    box-shadow: none !important;
}
.st-key-topnav .stButton button[kind="primary"] * { color: #2563eb !important; }
/* 메뉴 아이콘 — 칩 제거, 작고 미니멀 */
.st-key-topnav .stButton button span[data-testid="stIconMaterial"] {
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin-right: 4px !important;
    font-size: 17px !important;
    color: inherit !important;
}

/* ── 상단 분석월 셀렉트박스 ── */
.main .stSelectbox > div > div {
    background: rgba(255,255,255,0.85) !important;
    border-radius: 999px !important;
    border: 1px solid var(--border) !important;
}

/* ── 구분선 ── */
hr { border-color: rgba(37,99,235,0.10) !important; }

/* ── 알림 ── */
.stAlert { border-radius: 14px !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--primary) !important; }

/* ── 스크롤바 ── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: rgba(37,99,235,0.25); border-radius: 8px; }
::-webkit-scrollbar-track { background: transparent; }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────
_defaults = {
    "view":           "scan",
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

# 도메인별 로그 파일·날짜 컬럼 매핑
DOMAIN_LOG_DT = {
    "접근통제": ("access_log.csv",  "access_dt"),
    "변경관리": ("deploy_log.csv",  "deploy_dt"),
    "운영통제": ("backup_log.csv",  "backup_dt"),
}

@st.cache_data
def get_monthly_log_counts():
    """도메인 × 월 → 로그 건수 사전 (캐시)"""
    result = {}
    for domain, (fname, dt_col) in DOMAIN_LOG_DT.items():
        df = load_db(fname)
        if df.empty or dt_col not in df.columns:
            result[domain] = {}
            continue
        df[dt_col] = pd.to_datetime(df[dt_col], errors="coerce")
        monthly = (df.groupby([df[dt_col].dt.year, df[dt_col].dt.month])
                     .size().to_dict())
        result[domain] = {f"{y}-{m:02d}": c for (y, m), c in monthly.items()}
    return result

@st.cache_data
def get_rules_count():
    p = os.path.join(DATA_DIR, "rules.json")
    if not os.path.exists(p): return 0
    with open(p, encoding="utf-8") as f: return len(json.load(f))

def calc_scores(df, month=None):
    """
    복합 리스크 점수 (0~100):
      설계 점수 (40%) = 위반 없는 규칙 수 / 전체 규칙 수 × 100
      운영 점수 (60%) = (1 - 해당 월 위반 로그 수 / 전체 로그 수) × 100
    → 규모와 무관하게 실제 위반율을 반영
    """
    monthly_counts = get_monthly_log_counts()
    s = {}
    for d in DOMAIN_ORDER:
        sub         = df[df["audit_domain"] == d]
        total_rules = len(sub)
        pass_rules  = int((sub["yn_violation"] == "N").sum())

        # 설계 점수: 규칙 준수율
        design = round(pass_rules / total_rules * 100) if total_rules else 100

        # 운영 점수: 위반 로그 비율
        m_counts  = monthly_counts.get(d, {})
        total_log = m_counts.get(month, sum(m_counts.values())) if month else sum(m_counts.values())
        viol_log  = int(sub[sub["yn_violation"] == "Y"]["violation_count"].sum())
        if total_log > 0:
            ops = max(round((1 - min(viol_log / total_log, 1.0)) * 100), 0)
        else:
            ops = design  # 로그 없으면 설계 점수로 대체

        s[d] = round(design * 0.4 + ops * 0.6)
    return s

def grade(sc):
    if sc < 60:   return "고위험", "#fb7185"
    elif sc < 80: return "주의",   "#fbbf24"
    else:         return "정상",   "#60a5fa"

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
    sc = calc_scores(sub[sub["audit_domain"].isin(domains)], month=m)
    vals = [sc[d] for d in domains if d in sc]
    return round(sum(vals) / len(vals)) if vals else None

def hex_rgba(h, a=0.12):
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return f"rgba({r},{g},{b},{a})"


def compare_violations(curr_df, prev_df):
    """
    현재월 vs 전월 위반 비교.
    curr_df에 '위반상태' 컬럼 추가:
      반복위반 — 전월에도 위반, 이번에도 위반  (가장 위험)
      신규위반 — 이번 달 처음 발생
      해결됨   — 전월에 위반이었으나 이번 달 정상
      이상없음 — 전월·현재 모두 이상 없음
    Returns (tagged_df, n_repeat, n_new, n_resolved)
    """
    curr = curr_df.copy()

    if prev_df is None or prev_df.empty:
        curr["위반상태"] = curr["yn_violation"].map({"Y": "신규위반", "N": "이상없음"})
        n_new = int((curr["yn_violation"] == "Y").sum())
        return curr, 0, n_new, 0

    prev_viol_ids = set(prev_df[prev_df["yn_violation"] == "Y"]["rule_id"])
    curr_viol_ids = set(curr[curr["yn_violation"] == "Y"]["rule_id"])

    repeat   = curr_viol_ids & prev_viol_ids
    new_viol = curr_viol_ids - prev_viol_ids
    resolved = prev_viol_ids - curr_viol_ids

    def _status(row):
        rid = row["rule_id"]
        if row["yn_violation"] == "Y":
            return "반복위반" if rid in repeat else "신규위반"
        return "해결됨" if rid in resolved else "이상없음"

    curr["위반상태"] = curr.apply(_status, axis=1)
    return curr, len(repeat), len(new_viol), len(resolved)


# ════════════════════════════════════════════════════════════════
# AI 인사이트 (Claude API)
# ════════════════════════════════════════════════════════════════
def build_audit_context(df, month, scores, n_repeat, n_new, n_resolved):
    """Claude에게 전달할 감사 컨텍스트 — 팩트 중심으로 구조화"""
    lines = [
        f"[분석 대상] {MONTH_LABELS.get(month, month)} IT감사 점검 결과",
        "",
        "[도메인별 리스크 점수]",
    ]
    for d in DOMAIN_ORDER:
        sc   = scores.get(d, 100)
        g, _ = grade(sc)
        sub  = df[df["audit_domain"] == d]
        viol = int((sub["yn_violation"] == "Y").sum())
        total = len(sub)
        high  = int(((sub["severity"]=="HIGH") & (sub["yn_violation"]=="Y")).sum())
        lines.append(f"- {d}: {sc}점 / {g} / 전체 {total}개 규칙 중 위반 {viol}개 (HIGH {high}개)")

    lines += [
        "",
        "[전월 대비 위반 추이]",
        f"- 반복 위반(전월 동일): {n_repeat}개 규칙",
        f"- 신규 위반(이번 달 첫 발생): {n_new}개 규칙",
        f"- 해결 완료: {n_resolved}개 규칙",
        "",
        "[HIGH 등급 위반 규칙 전체 목록]",
    ]
    high_viols = (df[(df["severity"] == "HIGH") & (df["yn_violation"] == "Y")]
                  .sort_values("violation_count", ascending=False)
                  [["rule_id","rule_nm","audit_domain","violation_count","remediation"]])
    for _, r in high_viols.iterrows():
        lines.append(
            f"- {r['rule_id']} | {r['rule_nm']} | {r['audit_domain']} "
            f"| 위반 {int(r['violation_count'])}건 | 조치: {r['remediation']}"
        )

    lines += ["", "[MEDIUM 등급 위반 규칙 상위 5개]"]
    med_viols = (df[(df["severity"] == "MEDIUM") & (df["yn_violation"] == "Y")]
                 .nlargest(5, "violation_count")
                 [["rule_id","rule_nm","audit_domain","violation_count"]])
    for _, r in med_viols.iterrows():
        lines.append(
            f"- {r['rule_id']} | {r['rule_nm']} | {r['audit_domain']} "
            f"| 위반 {int(r['violation_count'])}건"
        )

    # 팩트 검증용 수치 요약 (Claude가 참조)
    total_viol = int((df["yn_violation"] == "Y").sum())
    total_rules = len(df)
    lines += [
        "",
        "[팩트 기준값 — 분석 내용은 반드시 이 수치와 일치해야 함]",
        f"- 전체 점검 규칙: {total_rules}개",
        f"- 위반 탐지 규칙: {total_viol}개 ({round(total_viol/total_rules*100)}%)",
        f"- HIGH 위반: {int(((df['severity']=='HIGH')&(df['yn_violation']=='Y')).sum())}개",
        f"- 반복 위반: {n_repeat}개 / 신규: {n_new}개 / 해결: {n_resolved}개",
    ]
    return "\n".join(lines)


def _get_api_key():
    """API 키 우선순위: Streamlit Secrets → .env 파일 → 환경변수"""
    # 1) Streamlit Cloud 배포 시
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    # 2) 로컬 .env 파일
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY"):
                    return line.split("=", 1)[-1].strip()
    # 3) OS 환경변수
    return os.environ.get("ANTHROPIC_API_KEY", "")


def verify_ai_response(response: str, df, scores, n_repeat, n_new) -> list[str]:
    """
    AI 응답에서 숫자를 추출해 실제 데이터와 대조.
    불일치 항목 리스트 반환 (없으면 빈 리스트).
    """
    import re
    warnings = []
    # 응답 내 rule_id 언급 확인
    mentioned_ids = set(re.findall(r'R\d{3}', response))
    actual_viol_ids = set(df[df["yn_violation"]=="Y"]["rule_id"].tolist())
    wrong_ids = mentioned_ids - actual_viol_ids
    if wrong_ids:
        warnings.append(f"실제 위반 목록에 없는 규칙 ID 언급: {', '.join(sorted(wrong_ids))}")
    # 반복 위반 건수 검증
    repeat_match = re.search(r'반복\s*위반[^\d]*(\d+)', response)
    if repeat_match:
        mentioned_cnt = int(repeat_match.group(1))
        if abs(mentioned_cnt - n_repeat) > 2:
            warnings.append(f"반복 위반 건수 불일치: 응답 {mentioned_cnt}개 ≠ 실제 {n_repeat}개")
    return warnings


def stream_ai_insights(context: str):
    """Claude API 스트리밍 호출 — generator 반환"""
    try:
        import anthropic as _ant
        client = _ant.Anthropic(api_key=_get_api_key())

        system_prompt = """당신은 금융권 IT 통제 점검 전문가로서 내부 통제 점검 보고서를 작성합니다.

[필수 준수 사항]
1. 제공된 데이터의 수치만 사용하고, 임의로 수치를 변경하거나 추정하지 마십시오.
2. 언급하는 모든 규칙은 반드시 제공된 목록의 rule_id(예: R002)를 명시하십시오.
3. 점검 보고서에 적합한 공식 용어를 사용하십시오.
   - 사용 가능: 통제 미흡, 시정 필요, 개선 권고, 취약점 식별, 위반 탐지, 즉시 조치 필요
   - 사용 금지: 붕괴, 심각한 문제, 위기, 마비, 위험천만 등 과장된 표현
4. 각 항목은 사실(위반 건수, rule_id)을 먼저 서술하고, 해석·권고를 후술하십시오.
5. 불확실한 원인 추정은 "~로 추정됨", "~가능성 있음" 등 단정 표현을 피하십시오."""

        prompt = f"""아래 IT감사 점검 결과를 분석하십시오.

{context}

---

가독성을 위해 **간결하게** 작성하십시오. 각 항목은 1~2줄을 넘기지 마십시오.
맨 처음 줄은 반드시 아래 형식으로 시작하십시오.

핵심 요약: (이번 달 IT통제 상태의 가장 중요한 결론을 한 문장으로. 예: 변경관리 도메인에서 HIGH 위반 11건이 집중되어 즉시 조치가 필요함)

그 다음 빈 줄을 두고 아래 세 섹션을 작성하십시오.

## 위반 패턴 분석
- 도메인별 위반 현황을 핵심 수치 중심으로 3~4개 bullet로 기술. 각 bullet은 한 줄.
- 반복 위반 규칙은 rule_id와 건수를 인용하되 장황한 설명은 생략.

## 우선 조치 항목
- HIGH·반복 위반 기준 5개를 선정.
- 형식: **[P1] R002 미승인 운영배포** — 조치: (한 줄 조치 방법)
- 조치 방법은 한 줄로 핵심만.

## 점검 총평
- 2문장 이내. 종합 점수·주요 취약 도메인·개선 방향만 포함. 공식 보고서 문체(~임, ~함, ~필요)."""

        with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    except Exception as e:
        yield f"\n\n⚠ AI 분석 오류: {str(e)}"


def render_ai_result(text, warnings=None):
    """AI 응답을 핵심 요약 카드 + 섹션 탭으로 표시."""
    import re
    # 핵심 요약 추출
    summary = ""
    m = re.search(r'핵심\s*요약\s*[:：]\s*(.+)', text)
    if m:
        summary = m.group(1).strip().split("\n")[0]

    # ## 헤더 기준 섹션 분리
    blocks = re.split(r'\n#{2,3}\s+', "\n" + text)
    sections = []
    for b in blocks[1:]:
        parts = b.split("\n", 1)
        title = parts[0].strip()
        body  = parts[1].strip() if len(parts) > 1 else ""
        if title:
            sections.append((title, body))

    # 핵심 요약 카드
    if summary:
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#eff6ff,#f0f9ff);"
            f"border:1px solid #bfdbfe;border-left:4px solid #3b82f6;"
            f"border-radius:14px;padding:0.95rem 1.2rem;margin-bottom:0.8rem;'>"
            f"<div style='font-size:0.7rem;font-weight:700;color:#2563eb;"
            f"letter-spacing:0.08em;text-transform:uppercase;margin-bottom:0.35rem;'>"
            f"<i class='fa-solid fa-lightbulb'></i>&nbsp; 핵심 요약</div>"
            f"<div style='font-size:0.98rem;font-weight:600;color:#1e293b;"
            f"line-height:1.55;'>{summary}</div></div>",
            unsafe_allow_html=True)

    # 섹션 탭
    if sections:
        ICONS = {"위반 패턴 분석": "🔍", "우선 조치 항목": "✅",
                 "점검 총평": "📝"}
        tab_labels = []
        for t, _ in sections:
            ic = next((v for k, v in ICONS.items() if k in t), "•")
            tab_labels.append(f"{ic}  {t}")
        tabs = st.tabs(tab_labels)
        for tab, (title, body) in zip(tabs, sections):
            with tab:
                st.markdown("<div style='height:0.4rem'></div>",
                            unsafe_allow_html=True)
                st.markdown(body)
    else:
        st.markdown(text)

    # 팩트 검증
    if warnings:
        with st.expander("⚠ 팩트 검증 — 확인 필요 항목", expanded=False):
            for w in warnings:
                st.warning(w)
    else:
        st.caption("✓ 팩트 검증 통과 — 응답 내 수치가 실제 데이터와 일치합니다.")


STATUS_COLOR = {
    "반복위반": "#fb7185",
    "신규위반": "#fbbf24",
    "해결됨":   "#34d399",
    "이상없음": "#94a3b8",
}
STATUS_BADGE_CSS = {
    "반복위반": "background:#fff1f2;color:#f43f5e;",
    "신규위반": "background:#fffbeb;color:#d97706;",
    "해결됨":   "background:#f0fdf4;color:#059669;",
    "이상없음": "background:#f8fafc;color:#94a3b8;",
}


# ════════════════════════════════════════════════════════════════
# 공통 차트 헬퍼
# ════════════════════════════════════════════════════════════════
def domain_score_fig(scores, df, height=250):
    """도메인별 리스크 점수 — 수평 진행 막대"""
    fig = go.Figure()
    # 필터에서 선택된 도메인만 표시 (scores에 있는 것만)
    active_domains = [d for d in DOMAIN_ORDER[::-1] if d in scores]
    for d in active_domains:
        sc  = scores[d]
        _, col = grade(sc)
        sub = df[df["audit_domain"] == d]
        viol = int((sub["yn_violation"] == "Y").sum())
        total = len(sub)
        g_lbl, _ = grade(sc)
        # 배경 트랙
        fig.add_trace(go.Bar(
            x=[100], y=[d], orientation="h",
            marker=dict(color="#f1f5f9", line=dict(width=0)),
            showlegend=False, hoverinfo="skip",
        ))
        # 점수 막대
        fig.add_trace(go.Bar(
            x=[sc], y=[d], orientation="h",
            marker=dict(color=col, opacity=0.88, line=dict(width=0)),
            text=f"<b>{sc}점</b>  {g_lbl}",
            textposition="inside" if sc > 25 else "outside",
            textfont=dict(size=13, color="white" if sc > 25 else col),
            showlegend=False,
            hovertemplate=(f"<b>{d}</b><br>리스크 점수: {sc}점<br>"
                           f"위반 규칙: {viol}/{total}개<extra></extra>"),
        ))
    fig.update_layout(
        barmode="overlay", height=height,
        margin=dict(l=10, r=15, t=10, b=10),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(tickfont=dict(size=13, color="#1e293b"), automargin=True,
                   ticklabelposition="outside left"),
        xaxis=dict(range=[0, 115], showgrid=True, gridcolor="#f1f5f9",
                   ticksuffix="점", tickfont=dict(size=10), zeroline=False),
        showlegend=False,
    )
    return fig

def trend_fig(trend_df, domains, height=240):
    rows = []
    for m in AVAILABLE_MONTHS:
        sub = trend_df[trend_df["month"] == m]
        if sub.empty: continue
        sc_map = calc_scores(sub, month=m)
        for d in domains:
            rows.append({"월": MONTH_LABELS[m], "도메인": d, "점수": sc_map.get(d, 100)})
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
    fig.add_hrect(y0=0,  y1=60, fillcolor="rgba(251,113,133,0.04)", line_width=0)
    fig.add_hrect(y0=60, y1=80, fillcolor="rgba(251,191,36,0.04)",  line_width=0)
    fig.add_hrect(y0=80, y1=105, fillcolor="rgba(96,165,250,0.03)", line_width=0)
    fig.add_hline(y=80, line_dash="dot", line_color="#60a5fa", line_width=1,
                  annotation_text="80", annotation_font_color="#60a5fa",
                  annotation_position="left")
    fig.add_hline(y=60, line_dash="dot", line_color="#fbbf24", line_width=1,
                  annotation_text="60", annotation_font_color="#fbbf24",
                  annotation_position="left")
    # y축 하한: 실제 최솟값에서 10점 아래 (최소 0)
    all_scores = [r["점수"] for r in rows]
    y_min = max(0, min(all_scores) - 10) if all_scores else 0
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=15, t=10, b=10),
        legend=dict(orientation="h", y=1.12, font=dict(size=11),
                    bgcolor="rgba(0,0,0,0)"),
        yaxis=dict(range=[y_min, 105], showgrid=True, gridcolor="#f1f5f9",
                   tickfont=dict(size=10)),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
    )
    return fig

def heatmap_fig(df, height=240):
    heat = (df[df["yn_violation"] == "Y"]
            .groupby(["audit_domain", "severity"]).size()
            .reset_index(name="건수"))
    pivot = (heat.pivot(index="severity", columns="audit_domain", values="건수")
             .reindex(["HIGH", "MEDIUM", "LOW"])
             .reindex(columns=DOMAIN_ORDER, fill_value=0).fillna(0))
    fig = px.imshow(pivot,
                    color_continuous_scale=[[0, "#f0f7ff"], [0.5, "#a5c8f5"],
                                            [1, "#60a5fa"]],
                    text_auto=True, aspect="auto", height=height)
    fig.update_traces(textfont_size=14, textfont_color="white")
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=False,
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(size=12), title=None),
        yaxis=dict(tickfont=dict(size=11), title=None),
    )
    return fig

def top_bar_fig(df, n=8, height=280):
    top = (df[df["yn_violation"] == "Y"]
           .nlargest(n, "violation_count")
           [["rule_nm", "severity", "violation_count"]]
           .sort_values("violation_count"))          # 오름차순 → 위에서 높은 값
    if top.empty:
        return go.Figure()

    MAX_LEN = 15
    labels = [nm[:MAX_LEN] + "…" if len(nm) > MAX_LEN else nm
              for nm in top["rule_nm"]]
    colors = [SEV_COLORS[s] for s in top["severity"]]
    SEV_KO = {"HIGH": "위험", "MEDIUM": "주의", "LOW": "낮음"}

    SEV_KO = {"HIGH": "위험", "MEDIUM": "주의", "LOW": "낮음"}

    # 메인 바 — 범례 제외
    fig = go.Figure(go.Bar(
        x=top["violation_count"], y=labels,
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        customdata=list(zip(top["severity"].map(SEV_KO), top["rule_nm"])),
        text=[f"{v}건" for v in top["violation_count"]],
        textposition="outside",
        textfont=dict(size=11, color="#334155"),
        showlegend=False,
        hovertemplate="<b>%{customdata[1]}</b><br>심각도: %{customdata[0]}<br>위반: %{x}건<extra></extra>",
    ))
    # 범례용 더미 트레이스 (실제 데이터 없음, 색상 안내만)
    for sev, ko in SEV_KO.items():
        if sev in top["severity"].values:
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers",
                marker=dict(color=SEV_COLORS[sev], size=9, symbol="square"),
                name=ko, showlegend=True,
            ))

    max_val = int(top["violation_count"].max())
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=55, t=10, b=35),   # 하단 여백으로 범례 공간 확보
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(tickfont=dict(size=11, color="#1e293b"), automargin=True),
        xaxis=dict(showgrid=True, gridcolor="#f1f5f9",
                   range=[0, max_val * 1.3], tickfont=dict(size=10)),
        legend=dict(
            orientation="h",       # 가로 배치
            x=0, y=-0.12,          # 차트 아래 바깥
            xanchor="left",
            yanchor="top",
            font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
            traceorder="normal",
        ),
        showlegend=True,
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
                marker_color="#f43f5e", text=ddf["위반"],
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

def violation_rate_fig(df, height=260):
    """도메인별 위반율 — 이중 링 도넛 + 중앙 수치"""
    fig = go.Figure()
    domain_stats = []
    for d in DOMAIN_ORDER:
        sub = df[df["audit_domain"] == d]
        total = len(sub)
        viol  = int((sub["yn_violation"] == "Y").sum())
        rate  = round(viol / total * 100) if total else 0
        domain_stats.append({"도메인": d, "위반": viol, "준수": total - viol,
                              "위반율": rate, "전체": total})
    ds = pd.DataFrame(domain_stats)

    fig.add_trace(go.Bar(
        name="위반", x=ds["도메인"], y=ds["위반율"],
        marker=dict(color=[DOMAIN_COLORS[d] for d in ds["도메인"]],
                    opacity=0.85, line=dict(width=0)),
        text=[f"{r}%" for r in ds["위반율"]],
        textposition="outside",
        textfont=dict(size=13, color="#1e293b"),
        hovertemplate="<b>%{x}</b><br>위반율: %{y}%<extra></extra>",
        showlegend=False,
    ))
    # 목표선 (위반율 0% 기준선)
    fig.add_hline(y=0, line_color="#e2e8f0", line_width=1)
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(showgrid=True, gridcolor="#f1f5f9",
                   ticksuffix="%", tickfont=dict(size=10),
                   title=None,
                   range=[0, max(ds["위반율"].max() * 1.35, 5)]),
        xaxis=dict(tickfont=dict(size=13, color="#1e293b")),
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
        prev_month = AVAILABLE_MONTHS[AVAILABLE_MONTHS.index(
            st.session_state.get("selected_month", AVAILABLE_MONTHS[-1])) - 1] \
            if AVAILABLE_MONTHS.index(st.session_state.get("selected_month", AVAILABLE_MONTHS[-1])) > 0 else None
        ps = calc_scores(prev_df, month=prev_month)
        prev_avg   = round(sum(ps.values()) / len(ps))
        prev_viol  = int((prev_df["yn_violation"] == "Y").sum())
        prev_high  = int(((prev_df["severity"] == "HIGH") & (prev_df["yn_violation"] == "Y")).sum())
        prev_clean = len(prev_df) - prev_viol

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, avg,   "종합 리스크 점수", g_col,    delta_html(avg,   prev_avg,   "점"), "점"),
        (c2, viol,  "위반 탐지 규칙",   "#f43f5e", delta_html(viol,  prev_viol,  "개"), "개"),
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
# 상단 메뉴바
# ════════════════════════════════════════════════════════════════
NAV_ITEMS = [
    ("scan",      "점검 실행",   ":material/play_circle:"),
    ("overview",  "전체 개요",   ":material/dashboard:"),
    ("access",    "접근통제",   ":material/lock:"),
    ("change",    "변경관리",   ":material/sync:"),
    ("ops",       "운영통제",   ":material/dns:"),
    ("analysis",  "심화 분석",   ":material/insights:"),
    ("ai",        "AI 분석",    ":material/smart_toy:"),
    ("sanctions", "제재 이력",   ":material/gavel:"),
    ("report",    "보고서 생성", ":material/description:"),
]


def render_topbar():
    """상단 가로 메뉴바 — 로고 + 분석월 + 가로 네비게이션. month 반환."""
    # 1행: 로고(좌) + 분석월(우)
    logo_col, month_col = st.columns([3, 1.1])
    with logo_col:
        st.markdown("""
        <div style='display:flex;align-items:baseline;gap:10px;padding-top:4px;'>
          <div style='font-size:1.3rem;font-weight:900;color:#0f172a;letter-spacing:-0.03em;'>
            <i class='fa-solid fa-shield-halved' style='color:#2563eb;margin-right:7px;'></i>IT<span style='color:#2563eb;'>감사</span> 시스템
          </div>
          <div style='font-size:0.68rem;color:#94a3b8;font-weight:500;
                      letter-spacing:0.06em;text-transform:uppercase;'>
              AI-Powered Audit Control</div>
        </div>
        """, unsafe_allow_html=True)
    with month_col:
        sel_month = st.selectbox(
            "month", AVAILABLE_MONTHS,
            index=AVAILABLE_MONTHS.index(st.session_state.selected_month),
            format_func=lambda m: f"📅  {MONTH_LABELS[m]}",
            label_visibility="collapsed")
        if sel_month != st.session_state.selected_month:
            st.session_state.selected_month = sel_month
            st.rerun()

    # 2행: 가로 메뉴 (책갈피 텍스트 탭)
    nav_box = st.container(key="topnav")
    nav_cols = nav_box.columns(len(NAV_ITEMS))
    for col, (key, label, icon) in zip(nav_cols, NAV_ITEMS):
        with col:
            is_active = st.session_state.view == key
            if st.button(label, key=f"nav_{key}", icon=icon,
                         use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.view = key
                st.rerun()

    st.markdown("<hr style='margin:-0.3rem 0 1rem; border:none; "
                "border-top:1px solid #e2e8f0;'>", unsafe_allow_html=True)
    return sel_month


def filter_bar(show_domain=True, show_sev=True):
    """화면 내부 인라인 필터 바 (라벨 + 구분선). (domains, sevs) 반환."""
    domains = st.session_state.filter_domains
    sevs    = st.session_state.filter_sevs
    if not (show_domain or show_sev):
        return domains, sevs

    # 태그가 한 줄에 다 보이도록 넓게 배치
    if show_domain and show_sev:
        cols = st.columns(2)          # 도메인 50% / 심각도 50%
    else:
        cols = st.columns([1, 1.4])   # 심각도만 — 넉넉히
    idx = 0
    if show_domain:
        with cols[idx]:
            domains = st.multiselect(
                "도메인", DOMAIN_ORDER,
                default=st.session_state.filter_domains,
                key="flt_domain", placeholder="전체 도메인")
            if not domains: domains = DOMAIN_ORDER
            st.session_state.filter_domains = domains
        idx += 1
    if show_sev:
        with cols[idx]:
            sevs = st.multiselect(
                "심각도", ["HIGH", "MEDIUM", "LOW"],
                default=st.session_state.filter_sevs,
                key="flt_sev", placeholder="전체 심각도")
            if not sevs: sevs = ["HIGH", "MEDIUM", "LOW"]
            st.session_state.filter_sevs = sevs

    st.markdown("<hr style='margin:0.3rem 0 1rem; border:none; "
                "border-top:1px solid var(--border);'>", unsafe_allow_html=True)
    return domains, sevs


# ════════════════════════════════════════════════════════════════
# VIEW: 전체 개요  (3구역)
# ════════════════════════════════════════════════════════════════
def view_overview(month):
    df = load_summary(month)
    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    domains, sevs = filter_bar(show_domain=True, show_sev=True)
    fdf     = apply_filters(df, domains, sevs)
    scores  = calc_scores(df, month=month)
    m_idx   = AVAILABLE_MONTHS.index(month)
    prev_df = load_summary(AVAILABLE_MONTHS[m_idx - 1]) if m_idx > 0 else None

    tagged_df, n_repeat, n_new, n_resolved = compare_violations(fdf, prev_df)

    # ────────────────────────────────────────────────────────────
    # ZONE 1 — 지금 상태가 어떤가?
    # ────────────────────────────────────────────────────────────
    active_scores = {d: scores[d] for d in domains if d in scores}
    avg_score     = round(sum(active_scores.values()) / len(active_scores)) if active_scores else 100
    g_lbl, g_col  = grade(avg_score)

    # 전월 비교
    prev_month = AVAILABLE_MONTHS[m_idx - 1] if m_idx > 0 else None
    prev_month_label = AVAILABLE_MONTHS[m_idx - 1] if m_idx > 0 else None
    prev_avg = None
    if prev_df is not None:
        ps = calc_scores(prev_df, month=prev_month)
        prev_avg = round(sum(ps[d] for d in domains if d in ps) / len(domains))
    score_delta = avg_score - prev_avg if prev_avg is not None else None
    delta_html = ""
    if score_delta is not None:
        sym = "▲" if score_delta >= 0 else "▼"
        delta_col = "#10b981" if score_delta >= 0 else "#f43f5e"
        delta_html = (f"<span style='font-size:0.85rem;font-weight:600;"
                      f"color:{delta_col};margin-left:10px;'>"
                      f"{sym} {abs(score_delta)}점 전월 대비</span>")

    # ── ZONE 1: 종합 점수 + 도메인 카드 (st.columns 분리)
    active_domains = [d for d in DOMAIN_ORDER if d in active_scores]
    col_weights = [1.1] + [1] * len(active_domains)
    cols_z1 = st.columns(col_weights)

    # 종합 점수 카드
    with cols_z1[0]:
        st.markdown(
            f"<div style='background:white;border-radius:14px;padding:1.1rem 1.2rem;"
            f"border:1px solid #e2e8f0;border-left:5px solid {g_col};"
            f"box-shadow:0 1px 4px rgba(0,0,0,0.05);height:100%;'>"
            f"<div style='font-size:0.7rem;font-weight:700;color:#94a3b8;"
            f"letter-spacing:0.08em;text-transform:uppercase;'>종합 점수</div>"
            f"<div style='font-size:3rem;font-weight:900;color:{g_col};"
            f"line-height:1.1;margin-top:0.25rem;'>{avg_score}</div>"
            f"<div style='font-size:0.9rem;font-weight:700;color:{g_col};'>{g_lbl}"
            f"{delta_html}</div>"
            f"<div style='font-size:0.68rem;color:#94a3b8;margin-top:0.3rem;'>"
            f"{MONTH_LABELS[month]}</div></div>",
            unsafe_allow_html=True)

    # 도메인별 카드
    for col, d in zip(cols_z1[1:], active_domains):
        sc = active_scores[d]
        g, gc = grade(sc)
        sub   = fdf[fdf["audit_domain"] == d]
        viol  = int((sub["yn_violation"] == "Y").sum())
        total = len(sub)
        high  = int(((sub["severity"] == "HIGH") & (sub["yn_violation"] == "Y")).sum())
        high_str = f" · HIGH <b style='color:#f43f5e;'>{high}건</b>" if high > 0 else ""
        with col:
            st.markdown(
                f"<div style='background:white;border-radius:14px;padding:1rem 1.1rem;"
                f"border:1px solid #e2e8f0;border-top:4px solid {gc};"
                f"box-shadow:0 1px 4px rgba(0,0,0,0.05);height:100%;'>"
                f"<div style='font-size:0.7rem;font-weight:700;color:#94a3b8;"
                f"letter-spacing:0.08em;text-transform:uppercase;"
                f"margin-bottom:0.4rem;'>{d}</div>"
                f"<div style='display:flex;align-items:baseline;gap:7px;'>"
                f"<span style='font-size:2rem;font-weight:900;color:{gc};"
                f"line-height:1;'>{sc}점</span>"
                f"<span style='font-size:0.82rem;font-weight:700;color:{gc};'>{g}</span>"
                f"</div>"
                f"<div style='font-size:0.7rem;color:#64748b;margin-top:0.4rem;'>"
                f"위반 <b>{viol}</b>개 / 전체 {total}개 규칙{high_str}</div>"
                f"</div>",
                unsafe_allow_html=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ────────────────────────────────────────────────────────────
    # ZONE 2 — 이번 달 무슨 변화가 있었나?
    # ────────────────────────────────────────────────────────────
    repeat_df   = tagged_df[tagged_df["위반상태"] == "반복위반"].sort_values(
        ["severity","violation_count"], ascending=[True,False])
    new_df      = tagged_df[tagged_df["위반상태"] == "신규위반"].sort_values(
        ["severity","violation_count"], ascending=[True,False])
    resolved_df = pd.DataFrame()
    if prev_df is not None and n_resolved > 0:
        resolved_df = prev_df[~prev_df["rule_id"].isin(
            tagged_df[tagged_df["yn_violation"]=="Y"]["rule_id"]
        )][["rule_id","rule_nm","audit_domain","severity","violation_count"]].copy()

    def _viol_table(tbl_df, empty_msg="해당 항목 없음"):
        if tbl_df is None or tbl_df.empty:
            st.caption(empty_msg); return
        cols = ["rule_id","rule_nm","audit_domain","severity","violation_count"]
        t = (tbl_df[[c for c in cols if c in tbl_df.columns]]
             .query("violation_count > 0")             # 0건 제외
             .sort_values("violation_count", ascending=False)   # 건수 많은 순
             .rename(columns={"rule_id":"ID","rule_nm":"규칙명","audit_domain":"도메인",
                               "severity":"등급","violation_count":"위반건수"}))
        if t.empty:
            st.caption(empty_msg); return
        st.dataframe(t, width="stretch", hide_index=True,
                     height=min(56 + len(t)*35, 280),
                     column_config={
                         "ID":       st.column_config.TextColumn(width=65),
                         "규칙명":   st.column_config.TextColumn(width=220),
                         "도메인":   st.column_config.TextColumn(width=90),
                         "등급":     st.column_config.TextColumn(width=75),
                         "위반건수": st.column_config.NumberColumn(width=75, format="%d건"),
                     })

    st.markdown("<div style='font-size:0.72rem;font-weight:700;color:#94a3b8;"
                "letter-spacing:0.08em;text-transform:uppercase;"
                "margin-bottom:0.4rem;'>전월 대비 위반 변화</div>",
                unsafe_allow_html=True)

    tab_r, tab_n, tab_h = st.tabs([
        f"반복 위반  {n_repeat}건",
        f"신규 위반  {n_new}건",
        f"해결 완료  {n_resolved}건",
    ])
    with tab_r:
        st.caption("전월과 이번 달 모두 동일 규칙 위반 — 즉시 조치 필요")
        _viol_table(repeat_df, "반복 위반 없음")
    with tab_n:
        st.caption("이번 달 처음 발생 — 원인 파악 후 시정조치 계획 수립")
        _viol_table(new_df, "신규 위반 없음")
    with tab_h:
        st.caption("전월 위반이 이번 달 정상화 — 조치 효과 확인")
        _viol_table(resolved_df, "해결된 위반 없음")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ────────────────────────────────────────────────────────────
    # ZONE 3 — 분석 차트
    # ────────────────────────────────────────────────────────────
    st.markdown("<div style='font-size:0.72rem;font-weight:700;color:#94a3b8;"
                "letter-spacing:0.08em;text-transform:uppercase;"
                "margin-bottom:0.4rem;'>상세 분석</div>",
                unsafe_allow_html=True)

    trend_df = load_all_monthly()
    ca, cb = st.columns([1.7, 1])
    with ca:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>"
                    "<i class='fa-solid fa-chart-line fa-sm'></i>  월별 리스크 점수 트렌드</div>",
                    unsafe_allow_html=True)
        if trend_df is not None:
            st.plotly_chart(trend_fig(trend_df, domains, height=230),
                            width="stretch", config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with cb:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'>"
                    "<i class='fa-solid fa-ranking-star fa-sm'></i>  위반 건수 TOP 8</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(top_bar_fig(fdf, n=8, height=230),
                        width="stretch", config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# VIEW: 도메인 상세 (접근통제 / 변경관리 / 운영통제)
# ════════════════════════════════════════════════════════════════
# VIEW: AI 분석
# ════════════════════════════════════════════════════════════════
def view_ai(month):
    df = load_summary(month)
    st.markdown("<div class='view-header'>"
                "<i class='fa-solid fa-robot' style='color:#2563eb;"
                "margin-right:8px;font-size:1.1rem;'></i>AI 분석</div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>{MONTH_LABELS[month]} 기준 · Claude 기반 점검 결과 인사이트</div>",
                unsafe_allow_html=True)

    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    scores  = calc_scores(df, month=month)
    m_idx   = AVAILABLE_MONTHS.index(month)
    prev_df = load_summary(AVAILABLE_MONTHS[m_idx-1]) if m_idx > 0 else None
    _, n_repeat, n_new, n_resolved = compare_violations(df, prev_df)

    # 안내 카드
    ca, cb, cc = st.columns(3)
    for col, icon, title, desc in [
        (ca, "fa-magnifying-glass-chart", "위반 패턴 분석", "어느 영역이 집중 위반인지, 반복 원인 해석"),
        (cb, "fa-list-ol",                "우선 조치 Top 5", "가장 먼저 처리할 항목과 구체적 조치 방법"),
        (cc, "fa-file-signature",         "점검 총평 초안",  "경영진 보고용 한 단락 요약 자동 작성"),
    ]:
        with col:
            st.markdown(
                f"<div style='background:white;border-radius:12px;padding:0.9rem 1rem;"
                f"border:1px solid #e2e8f0;box-shadow:0 1px 4px rgba(0,0,0,0.04);'>"
                f"<div style='color:#2563eb;font-size:1.2rem;margin-bottom:0.4rem;'>"
                f"<i class='fa-solid {icon}'></i></div>"
                f"<div style='font-size:0.85rem;font-weight:700;color:#1e293b;'>{title}</div>"
                f"<div style='font-size:0.72rem;color:#94a3b8;margin-top:0.2rem;'>{desc}</div>"
                f"</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    ai_key = f"ai_insights_{month}"
    c1, c2 = st.columns([1, 5])
    with c1:
        run_ai = st.button("분석 실행", type="primary",
                           key=f"ai_run_{month}", use_container_width=True)
    with c2:
        if st.session_state.get(ai_key):
            if st.button("다시 분석", key=f"ai_rerun_{month}"):
                st.session_state[ai_key] = None
                st.rerun()

    if run_ai:
        # 생성 과정은 숨기고 스피너만 → 완료 후 rerun → 요약 뷰
        context   = build_audit_context(df, month, scores, n_repeat, n_new, n_resolved)
        full_text = ""
        with st.spinner("⏳  AI가 점검 결과를 분석하고 있습니다…"):
            for chunk in stream_ai_insights(context):
                full_text += chunk
        st.session_state[ai_key] = full_text
        st.session_state[f"{ai_key}_warnings"] = \
            verify_ai_response(full_text, df, scores, n_repeat, n_new)
        st.rerun()

    elif st.session_state.get(ai_key):
        render_ai_result(st.session_state[ai_key],
                         st.session_state.get(f"{ai_key}_warnings", []))
    else:
        st.markdown(
            "<div class='dash-card'>"
            "<p style='color:#94a3b8;margin:0.5rem 0;'>"
            "위 <b>분석 실행</b> 버튼을 누르면 Claude가 이번 달 점검 결과를 "
            "분석하여 핵심 요약과 세 가지 섹션으로 정리해드립니다.</p></div>",
            unsafe_allow_html=True)


# 통제 영역 매핑 — 제재 사례 키워드 ↔ 우리 점검 규칙 키워드
SANCTION_TOPIC_MAP = {
    "변경관리·배포 통제": {
        "sanction_kw": ["프로그램", "변경", "배포", "테스트", "이관", "차세대",
                        "운영시스템", "검증", "반출", "소스"],
        "our_kw":      ["배포", "변경", "승인", "직무분리", "조작", "CR", "이관"],
    },
    "백업·복구 통제": {
        "sanction_kw": ["백업", "복구", "이중화", "재해", "장애"],
        "our_kw":      ["백업", "복구"],
    },
    "접근·권한 통제": {
        "sanction_kw": ["접근", "권한", "계정", "인증", "비밀번호", "출입", "패스워드"],
        "our_kw":      ["권한", "접근", "계정", "비밀번호", "출입", "인증", "퇴직"],
    },
    "정보보호·암호화 통제": {
        "sanction_kw": ["암호", "정보보호", "보안", "개인정보", "망분리", "유출"],
        "our_kw":      ["암호", "보안", "정보보호", "개인정보", "망분리"],
    },
}


# ════════════════════════════════════════════════════════════════
# VIEW: 금융감독원 제재 이력
# ════════════════════════════════════════════════════════════════
def view_sanctions(month):
    st.markdown("<div class='view-header'>"
                "<i class='fa-solid fa-landmark' style='color:#2563eb;"
                "margin-right:8px;font-size:1.1rem;'></i>금융감독원 IT 제재 이력</div>",
                unsafe_allow_html=True)
    st.markdown("<div class='view-sub'>IT검사국·전자금융검사국 실제 제재 사례 · "
                "출처: 금융감독원 제재관련공시 (공공누리 제1유형)</div>",
                unsafe_allow_html=True)

    sanctions_path = os.path.join(DATA_DIR, "fss_sanctions.json")
    if not os.path.exists(sanctions_path):
        st.info("제재 이력 데이터 없음 — 아래 버튼으로 수집하세요.")
        if st.button("금감원 제재 이력 수집", type="primary"):
            with st.spinner("금융감독원 공시 수집 중... (약 60초)"):
                res = subprocess.run(
                    [sys.executable, os.path.join(SRC_DIR, "fss_collector.py"),
                     "--max-pages", "50"],
                    capture_output=True, text=True, cwd=BASE_DIR)
            if res.returncode == 0:
                st.success("수집 완료! 새로고침 해주세요.")
            else:
                st.error("수집 실패"); st.code(res.stderr[:500])
        return

    with open(sanctions_path, encoding="utf-8") as f:
        sanctions_data = json.load(f)
    items     = sanctions_data.get("items", [])
    collected = sanctions_data.get("collected_at", "")[:10]

    # 현재 점검에서 탐지된 위반 규칙
    df = load_summary(month)
    if df is not None:
        viol_df = df[df["yn_violation"] == "Y"][
            ["rule_id","rule_nm","condition_desc","violation_count",
             "severity","audit_domain"]].copy()
    else:
        viol_df = pd.DataFrame()

    def _is_garbled(t):
        """한글 비율이 너무 낮으면 깨진 추출로 판단"""
        if not t:
            return True
        import re as _re
        han = len(_re.findall(r"[가-힣]", t))
        return han < 10 or han < len(t) * 0.25

    # 제재 사례 ↔ 우리 점검 위반 규칙 매칭 (통제 영역 단위)
    def _match_controls(item):
        # 제재 사례의 깨지지 않은 위반 텍스트
        vtext = " ".join(v for v in item.get("violations", [])
                         if not _is_garbled(v))
        snip = item.get("pdf_text_snippet", "")
        if not _is_garbled(snip):
            vtext += " " + snip
        results = []
        if viol_df.empty or not vtext.strip():
            return results
        for topic, kw in SANCTION_TOPIC_MAP.items():
            if not any(k in vtext for k in kw["sanction_kw"]):
                continue
            rules = []
            for _, row in viol_df.iterrows():
                rt = str(row["rule_nm"]) + " " + str(row.get("condition_desc",""))
                if any(k in rt for k in kw["our_kw"]):
                    rules.append(row)
            if rules:
                results.append((topic, rules))
        return results

    # ── 검색 / 필터 바 ──
    sc1, sc2 = st.columns([3, 1.3])
    with sc1:
        query = st.text_input(
            "검색", key="sanction_q", label_visibility="collapsed",
            placeholder="🔍  기관명·위반 키워드 검색  (예: 백업, 접근통제, 전자금융)")
    with sc2:
        only_related = st.toggle("관련 사례만", value=False,
                                 help="우리 점검 위반과 같은 통제 영역의 제재 사례만 표시")

    filtered = []
    for item in items:
        item_text = (item.get("institution","") + " " + item.get("department","") +
                     " " + " ".join(item.get("violations", [])) + " " +
                     item.get("pdf_text_snippet", ""))
        matches = _match_controls(item)
        is_related = bool(matches)
        if query and query.strip() and query.strip() not in item_text:
            continue
        if only_related and not is_related:
            continue
        filtered.append((item, is_related, matches))

    st.caption(f"전체 {len(items)}건 중 {len(filtered)}건 표시 | 기준일: {collected}")
    st.markdown(
        "<p style='font-size:0.82rem;color:#64748b;margin:0.2rem 0 0.9rem;'>"
        "<b style='color:#f43f5e;'>관련 가능성</b> 배지가 붙은 사례는, 그 회사가 제재받은 "
        "통제 영역(예: 변경관리·백업)에서 <b>우리 점검에서도 동일하게 위반이 탐지된</b> "
        "경우입니다. 사례를 펼치면 우리 점검의 어떤 규칙이 해당되는지 보여줍니다.</p>",
        unsafe_allow_html=True)

    if not filtered:
        st.info("검색 결과가 없습니다.")
    for item, is_related, matches in filtered:
        date_str = item.get("date", "")
        date_fmt = (f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
                    if len(date_str) == 8 else date_str)
        institution = item.get("institution", "")
        dept        = item.get("department", "")
        violations  = item.get("violations", [])
        pdf_snippet = item.get("pdf_text_snippet", "")

        border_color = "#f43f5e" if is_related else "#e0f2fe"
        badge = (f"<span style='background:#fef2f2;color:#f43f5e;"
                 f"font-size:0.7rem;font-weight:700;padding:2px 8px;"
                 f"border-radius:999px;margin-left:8px;'>관련 가능성</span>"
                 if is_related else "")

        with st.expander(
                f"{date_fmt}   |   {institution}   |   {dept}{'   ⚠ 관련' if is_related else ''}",
                expanded=is_related and bool(query)):
            st.markdown(
                f"<div style='padding:0.3rem 0;border-left:3px solid {border_color};"
                f"padding-left:0.8rem;'>"
                f"<div style='font-size:0.9rem;font-weight:700;color:#1e293b;'>"
                f"{institution}{badge}</div>"
                f"<div style='font-size:0.76rem;color:#64748b;margin-top:0.2rem;'>"
                f"{date_fmt} &nbsp;·&nbsp; {dept}</div></div>",
                unsafe_allow_html=True)

            # 제재 사례의 위반 내용
            clean_violations = [v for v in violations if not _is_garbled(v)]
            if clean_violations:
                st.markdown(
                    "<div style='font-size:0.82rem;font-weight:700;"
                    "color:#334155;margin:0.6rem 0 0.3rem;'>이 회사가 제재받은 내용</div>",
                    unsafe_allow_html=True)
                for v in clean_violations[:8]:
                    st.markdown(
                        f"<div style='font-size:0.82rem;color:#475569;"
                        f"padding:0.25rem 0;border-bottom:1px solid #f1f5f9;'>"
                        f"▸ {v}</div>", unsafe_allow_html=True)
            elif pdf_snippet and not _is_garbled(pdf_snippet):
                st.markdown(
                    f"<div style='font-size:0.8rem;color:#64748b;"
                    f"white-space:pre-line;'>{pdf_snippet[:400]}</div>",
                    unsafe_allow_html=True)
            else:
                st.caption("이 PDF는 자동 텍스트 추출이 어려워 위반 내용을 "
                           "표시할 수 없습니다. 아래 원본 PDF에서 확인해주세요.")

            # 우리 점검과의 연결 — 같은 통제 영역의 우리 위반 규칙
            if is_related and matches:
                blocks = ""
                for topic, rules in matches:
                    rule_items = "".join(
                        f"<div style='font-size:0.8rem;color:#334155;padding:0.18rem 0;'>"
                        f"• <b>{r['rule_id']}</b> {r['rule_nm']} &nbsp;"
                        f"<span style='color:#e11d48;font-weight:700;'>"
                        f"{int(r['violation_count'])}건</span></div>"
                        for r in rules[:3])
                    blocks += (
                        f"<div style='margin-bottom:0.45rem;'>"
                        f"<span style='font-size:0.73rem;font-weight:700;color:#2563eb;"
                        f"background:#eff6ff;padding:2px 9px;border-radius:6px;'>{topic}</span>"
                        f"<div style='margin-top:0.25rem;'>{rule_items}</div></div>")
                st.markdown(
                    f"<div style='margin-top:0.7rem;background:#fff7f8;"
                    f"border:1px solid #fecdd3;border-radius:10px;padding:0.75rem 0.95rem;'>"
                    f"<div style='font-size:0.82rem;font-weight:800;color:#e11d48;"
                    f"margin-bottom:0.5rem;'>"
                    f"<i class='fa-solid fa-triangle-exclamation'></i>&nbsp; "
                    f"우리 점검에서도 같은 영역이 미흡합니다</div>"
                    f"{blocks}"
                    f"<div style='font-size:0.73rem;color:#94a3b8;margin-top:0.4rem;'>"
                    f"이 회사가 제재받은 통제 영역에서 우리도 위반이 탐지되었습니다. "
                    f"방치 시 유사 제재 대상이 될 수 있어 우선 조치를 권고합니다.</div></div>",
                    unsafe_allow_html=True)

            if item.get("pdf_urls"):
                st.markdown(f"[원본 PDF 보기]({item['pdf_urls'][0]})")

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    if st.button("데이터 업데이트", key="update_sanctions"):
        with st.spinner("금융감독원 공시 재수집 중..."):
            subprocess.run(
                [sys.executable, os.path.join(SRC_DIR, "fss_collector.py"),
                 "--max-pages", "50"],
                capture_output=True, text=True, cwd=BASE_DIR)
        st.success("업데이트 완료!")
        st.rerun()


# ════════════════════════════════════════════════════════════════
def view_domain(month, domain):
    df = load_summary(month)
    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    _, sevs = filter_bar(show_domain=False, show_sev=True)
    sub = apply_filters(df, [domain], sevs)
    scores = calc_scores(df, month=month)
    score  = scores.get(domain, 100)
    g_lbl, g_col = grade(score)
    violated = int((sub["yn_violation"] == "Y").sum())
    total    = len(sub)
    trend_df = load_all_monthly()

    # 전월 비교
    m_idx   = AVAILABLE_MONTHS.index(month)
    prev_df = load_summary(AVAILABLE_MONTHS[m_idx - 1]) if m_idx > 0 else None
    tagged_sub, n_repeat, n_new, n_resolved = compare_violations(sub, prev_df)

    st.markdown(f"<div class='view-header'>"
                f"{domain} 상세</div>",
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
        st.markdown(f"<div class='kpi-box' style='--accent:#f43f5e;'>"
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
                    "<div class='card-title'><i class='fa-solid fa-chart-line fa-sm'></i>  월별 리스크 점수 트렌드</div>",
                    unsafe_allow_html=True)
        if trend_df is not None:
            st.plotly_chart(trend_fig(trend_df, [domain], height=230),
                            width="stretch",
                            config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'><i class='fa-solid fa-chart-pie fa-sm'></i>  심각도별 위반 비율</div>",
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

    # 위반 추이 미니 배너
    if prev_df is not None:
        st.markdown(f"""
        <div style='display:flex;gap:0.5rem;margin-bottom:0.5rem;'>
          <div style='flex:1;padding:0.55rem 0.8rem;border-radius:10px;
                      background:#fef2f2;border-left:3px solid #f43f5e;'>
            <span style='font-size:1.3rem;font-weight:900;color:#f43f5e;'>{n_repeat}</span>
            <span style='font-size:0.72rem;color:#f43f5e;font-weight:700;margin-left:4px;'>반복 위반</span>
            <div style='font-size:0.66rem;color:#94a3b8;'>전월 동일 규칙 위반 지속</div>
          </div>
          <div style='flex:1;padding:0.55rem 0.8rem;border-radius:10px;
                      background:#fff7ed;border-left:3px solid #f59e0b;'>
            <span style='font-size:1.3rem;font-weight:900;color:#f59e0b;'>{n_new}</span>
            <span style='font-size:0.72rem;color:#f59e0b;font-weight:700;margin-left:4px;'>신규 위반</span>
            <div style='font-size:0.66rem;color:#94a3b8;'>이번 달 처음 발생</div>
          </div>
          <div style='flex:1;padding:0.55rem 0.8rem;border-radius:10px;
                      background:#f0fdf4;border-left:3px solid #10b981;'>
            <span style='font-size:1.3rem;font-weight:900;color:#10b981;'>{n_resolved}</span>
            <span style='font-size:0.72rem;color:#10b981;font-weight:700;margin-left:4px;'>해결 완료</span>
            <div style='font-size:0.66rem;color:#94a3b8;'>전월 위반 이번 달 정상화</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ROW 3: TOP 위반 + 규칙 테이블 (위반상태 포함)
    c3, c4 = st.columns([1, 1.3])
    with c3:
        st.markdown("<div class='dash-card'>"
                    "<div class='card-title'><i class='fa-solid fa-ranking-star fa-sm'></i>  위반 건수 TOP 8</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(top_bar_fig(tagged_sub, n=8, height=260),
                        width="stretch",
                        config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with c4:
        viol_rows = tagged_sub[tagged_sub["yn_violation"] == "Y"].sort_values(
            ["위반상태", "violation_count"], ascending=[True, False])
        # 상태 배지 HTML 렌더링
        rows_html = ""
        for _, r in viol_rows.iterrows():
            css = STATUS_BADGE_CSS.get(r["위반상태"], "")
            badge = (f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;"
                     f"font-size:0.68rem;font-weight:700;{css}'>{r['위반상태']}</span>")
            sev_css = f"color:{SEV_COLORS.get(r['severity'], '#666')};font-weight:700;"
            rows_html += (
                f"<tr style='border-bottom:1px solid #f1f5f9;'>"
                f"<td style='padding:7px 6px;font-size:0.78rem;color:#334155;'>{r['rule_id']}</td>"
                f"<td style='padding:7px 6px;font-size:0.78rem;color:#1e293b;'>{r['rule_nm'][:18]}{'…' if len(r['rule_nm'])>18 else ''}</td>"
                f"<td style='padding:7px 6px;font-size:0.78rem;{sev_css}'>{r['severity']}</td>"
                f"<td style='padding:7px 6px;font-size:0.78rem;font-weight:700;color:#1e293b;text-align:right;'>{int(r['violation_count'])}건</td>"
                f"<td style='padding:7px 6px;'>{badge}</td>"
                f"</tr>"
            )
        # 카드 + 테이블을 하나의 흰 배경 div로 (분리 방지)
        st.markdown(
            f"<div class='dash-card'>"
            f"<div class='card-title'><i class='fa-solid fa-list-check fa-sm'></i>  위반 규칙 목록</div>"
            f"<div style='overflow-y:auto;max-height:270px;background:#ffffff;border-radius:10px;'>"
            f"<table style='width:100%;border-collapse:collapse;background:#ffffff;'>"
            f"<thead><tr style='border-bottom:2px solid #e2e8f0;background:#f8fafc;'>"
            f"<th style='padding:8px 6px;font-size:0.7rem;color:#94a3b8;font-weight:700;text-align:left;'>ID</th>"
            f"<th style='padding:8px 6px;font-size:0.7rem;color:#94a3b8;font-weight:700;text-align:left;'>규칙명</th>"
            f"<th style='padding:8px 6px;font-size:0.7rem;color:#94a3b8;font-weight:700;text-align:left;'>등급</th>"
            f"<th style='padding:8px 6px;font-size:0.7rem;color:#94a3b8;font-weight:700;text-align:right;'>건수</th>"
            f"<th style='padding:8px 6px;font-size:0.7rem;color:#94a3b8;font-weight:700;text-align:left;'>상태</th>"
            f"</tr></thead><tbody>{rows_html}</tbody></table></div>"
            f"</div>",
            unsafe_allow_html=True)


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

    st.markdown("<div class='view-header'><i class='fa-solid fa-chart-bar' style='color:#2563eb;margin-right:8px;font-size:1.1rem;'></i>심화 분석</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>{MONTH_LABELS[month]} 기준 · DB 데이터 자동 분석</div>",
                unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["부서별 위험도", "역할별 분석", "리스크 매트릭스", "법령 준수율", "복합 위험 사용자"])

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
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-table-cells fa-sm'></i>  부서별 위반 히트맵</div>",
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
                                plot_bgcolor="white",
                                font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-ranking-star fa-sm'></i>  부서별 종합 위험점수 TOP 10</div>",
                        unsafe_allow_html=True)
            top10 = dept_risk.head(10).reset_index()
            fig_b = go.Figure(go.Bar(
                x=top10["위험점수"], y=top10["dept_nm"],
                orientation="h",
                marker_color=["#f43f5e" if s>=10 else "#f59e0b" if s>=5 else "#3b82f6"
                              for s in top10["위험점수"]],
                text=top10["위험점수"], textposition="outside",
            ))
            fig_b.update_layout(height=350, margin=dict(l=10,r=50,t=10,b=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="white",
                                xaxis=dict(color="#64748b", showgrid=True, gridcolor="#f1f5f9"),
                                yaxis=dict(color="#1e293b", autorange="reversed",
                                           tickfont=dict(size=11)),
                                font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-table-list fa-sm'></i>  부서별 위험점수 상세</div>",
                    unsafe_allow_html=True)
        st.dataframe(dept_risk.reset_index().rename(columns={"dept_nm":"부서명"}),
                     use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 탭2: 역할별 분석 ─────────────────────────────────────────
    with tab2:
        roles  = ["developer","operator","security","business"]
        labels = ["개발","운영","보안","업무"]

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
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-users fa-sm'></i>  역할별 접근통제 위반 현황</div>",
                        unsafe_allow_html=True)
            fig_r = go.Figure()
            colors_r = ["#f43f5e","#f59e0b","#9b59b6"]
            for i, (col, color) in enumerate(zip(role_df.columns, colors_r)):
                fig_r.add_trace(go.Bar(name=col, x=labels, y=role_df[col], marker_color=color))
            fig_r.update_layout(barmode="group", height=300,
                                margin=dict(l=10,r=10,t=30,b=10),
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="white",
                                legend=dict(font=dict(color="#334155", size=12),
                                            bgcolor="rgba(0,0,0,0)",
                                            orientation="h", y=1.08),
                                xaxis=dict(color="#334155", tickfont=dict(size=12)),
                                yaxis=dict(color="#334155", showgrid=True,
                                           gridcolor="#f1f5f9"),
                                font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_r, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-chart-bar fa-sm'></i>  역할별 위반 관여 비율</div>",
                        unsafe_allow_html=True)
            fig_rate = go.Figure(go.Bar(
                x=labels, y=role_rate.values,
                marker_color=["#f43f5e" if v>20 else "#f59e0b" if v>10 else "#3b82f6"
                              for v in role_rate.values],
                text=[f"{v}%" for v in role_rate.values],
                textposition="outside",
            ))
            fig_rate.update_layout(height=300, margin=dict(l=10,r=10,t=10,b=10),
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="white",
                                   xaxis=dict(color="#334155", tickfont=dict(size=12)),
                                   yaxis=dict(color="#334155", showgrid=True,
                                              gridcolor="#f1f5f9",
                                              title=dict(text="비율 (%)", font=dict(size=12))),
                                   font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_rate, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-table fa-sm'></i>  역할별 요약</div>",
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

        grade_colors = {"Critical":"#8B0000","High":"#f43f5e",
                        "Medium":"#f59e0b","Low":"#3b82f6","이상없음":"#64748b"}

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-chart-pie fa-sm'></i>  위험 등급별 규칙 분포</div>",
                        unsafe_allow_html=True)
            grade_order = ["Critical","High","Medium","Low","이상없음"]
            gcnt = df_r.groupby("위험등급").size().reindex(grade_order, fill_value=0)
            gcnt_nz = gcnt[gcnt>0]
            fig_pie = go.Figure(go.Pie(
                labels=gcnt_nz.index, values=gcnt_nz.values, hole=0.55,
                marker_colors=[grade_colors[g] for g in gcnt_nz.index],
                textinfo="label+value", textfont=dict(size=11),
            ))
            fig_pie.update_layout(height=300, showlegend=True,
                                  margin=dict(l=10,r=10,t=10,b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  legend=dict(font=dict(color="#334155", size=12),
                                              bgcolor="rgba(0,0,0,0)"),
                                  font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-triangle-exclamation fa-sm'></i>  고위험 규칙 TOP 10</div>",
                        unsafe_allow_html=True)
            top10r = df_r[df_r["위험점수"]>0].nlargest(10,"위험점수")
            fig_top = go.Figure(go.Bar(
                x=top10r["위험점수"][::-1],
                y=[f"{r} {n[:10]}" for r,n in zip(top10r["rule_id"][::-1],top10r["rule_nm"][::-1])],
                orientation="h",
                marker_color=[grade_colors[g] for g in top10r["위험등급"][::-1]],
                text=top10r["위험점수"][::-1].round(1), textposition="outside",
            ))
            fig_top.update_layout(height=300, margin=dict(l=10,r=50,t=10,b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="white",
                                  xaxis=dict(color="#64748b", showgrid=True,
                                             gridcolor="#f1f5f9"),
                                  yaxis=dict(color="#1e293b", tickfont=dict(size=10)),
                                  font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_top, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-circle-dot fa-sm'></i>  위험도 산점도</div>",
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
            height=270, margin=dict(l=10,r=10,t=10,b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="white",
            xaxis=dict(type="log",
                       title=dict(text="위반 건수 (log)", font=dict(size=12)),
                       color="#64748b", gridcolor="#f1f5f9"),
            yaxis=dict(tickvals=[1,2,3], ticktext=["LOW","MEDIUM","HIGH"],
                       color="#334155", gridcolor="#f1f5f9",
                       tickfont=dict(size=12)),
            font=dict(color="#1e293b", size=12),
        )
        st.plotly_chart(fig_sc, use_container_width=True, config={"displayModeBar":False})
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 탭4: 법령 준수율 ─────────────────────────────────────────
    with tab4:
        law_viol = df_sum[df_sum["yn_violation"]=="Y"].copy()
        law_total_cnt = df_sum.groupby("source_law").size()
        # 위반 0건인 법령은 law_viol_cnt에 없으므로 reindex로 0 채움 → 준수율 100%
        law_viol_cnt = (law_viol.groupby("source_law").size()
                        .reindex(law_total_cnt.index, fill_value=0))
        law_comp = ((1 - law_viol_cnt / law_total_cnt) * 100).round(1).reset_index()
        law_comp.columns = ["법령명","준수율(%)"]
        law_comp = law_comp.sort_values("준수율(%)")

        law_sum = law_viol.groupby("source_law").agg(
            위반규칙수=("rule_id","count"),
            총위반건수=("violation_count","sum"),
            HIGH건수=("severity", lambda x: (x=="HIGH").sum())
        ).reset_index().sort_values("위반규칙수", ascending=False)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-scale-balanced fa-sm'></i>  법령별 준수율</div>",
                        unsafe_allow_html=True)
            fig_comp = go.Figure(go.Bar(
                x=law_comp["준수율(%)"], y=law_comp["법령명"],
                orientation="h",
                marker_color=["#f43f5e" if v<50 else "#f59e0b" if v<75 else "#10b981"
                              for v in law_comp["준수율(%)"]],
                text=[f"{v}%" for v in law_comp["준수율(%)"]],
                textposition="outside",
            ))
            fig_comp.update_layout(height=320, margin=dict(l=10,r=80,t=10,b=10),
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="white",
                                   xaxis=dict(range=[0,120], color="#64748b",
                                              showgrid=True, gridcolor="#f1f5f9"),
                                   yaxis=dict(color="#1e293b", tickfont=dict(size=11)),
                                   font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-gavel fa-sm'></i>  법령별 위반 규칙 수</div>",
                        unsafe_allow_html=True)
            fig_law = go.Figure(go.Bar(
                x=law_sum["위반규칙수"], y=law_sum["source_law"],
                orientation="h",
                marker_color=["#f43f5e" if h>0 else "#3b82f6" for h in law_sum["HIGH건수"]],
                text=[f"{v}개" + (f" (HIGH {h})" if h>0 else "")
                      for v,h in zip(law_sum["위반규칙수"],law_sum["HIGH건수"])],
                textposition="outside",
            ))
            fig_law.update_layout(height=320, margin=dict(l=10,r=130,t=10,b=10),
                                  paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="white",
                                  xaxis=dict(color="#64748b", showgrid=True,
                                             gridcolor="#f1f5f9"),
                                  yaxis=dict(color="#1e293b", tickfont=dict(size=11)),
                                  font=dict(color="#1e293b", size=12))
            st.plotly_chart(fig_law, use_container_width=True, config={"displayModeBar":False})
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='dash-card'><div class='card-title'><i class='fa-solid fa-table-list fa-sm'></i>  법령별 위반 현황 상세</div>",
                    unsafe_allow_html=True)
        st.dataframe(law_sum.rename(columns={"source_law":"법령명"}),
                     use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── 탭5: 복합 위험 사용자 ────────────────────────────────────
    with tab5:
        st.markdown("<div style='font-size:0.82rem;color:#64748b;margin-bottom:0.8rem;'>"
                    "여러 위반 유형이 동시에 탐지된 사용자를 식별합니다. "
                    "단일 위반보다 복합 위반자가 실질 위험이 높습니다.</div>",
                    unsafe_allow_html=True)

        # ── 위반 유형별 emp_id 집합 수집 ──────────────────────────
        viol_map = {}  # emp_id → set of violation types

        # 1) 업무시간 외 접속
        ah_ids = set(df_access[df_access["yn_after_hours"] == "Y"]["emp_id"].dropna())
        for eid in ah_ids:
            viol_map.setdefault(eid, set()).add("업무시간외 접속")

        # 2) 권한검토 초과 계정 보유
        od_ids = set(df_account[df_account["yn_overdue_review"] == "Y"]["emp_id"].dropna())
        for eid in od_ids:
            viol_map.setdefault(eid, set()).add("권한검토 초과")

        # 3) 직무분리 위반 배포 (deployer_id)
        if "yn_job_sep_violation" in df_deploy.columns:
            js_ids = set(df_deploy[df_deploy["yn_job_sep_violation"] == "Y"]["deployer_id"].dropna())
            for eid in js_ids:
                viol_map.setdefault(eid, set()).add("직무분리 위반")

        # 4) 사후승인 배포
        if "yn_post_approval" in df_deploy.columns:
            pa_ids = set(df_deploy[df_deploy["yn_post_approval"] == "Y"]["deployer_id"].dropna())
            for eid in pa_ids:
                viol_map.setdefault(eid, set()).add("사후승인 배포")

        # ── 복합 위험 사용자 (2개 이상 위반 유형) ────────────────
        multi_viol = {eid: vtypes for eid, vtypes in viol_map.items() if len(vtypes) >= 2}

        # emp_master 조인
        emp_info = df_emp[["emp_id","emp_nm","dept_nm","role_type"]].copy()
        emp_info.columns = ["emp_id","이름","부서","역할"]

        rows = []
        for eid, vtypes in multi_viol.items():
            info = emp_info[emp_info["emp_id"] == eid]
            nm   = info["이름"].values[0] if not info.empty else "-"
            dept = info["부서"].values[0] if not info.empty else "-"
            role = info["역할"].values[0] if not info.empty else "-"
            risk = len(vtypes) * 3 + sum(
                2 if v in ("직무분리 위반","사후승인 배포") else 1 for v in vtypes)
            rows.append({
                "emp_id": eid, "이름": nm, "부서": dept, "역할": role,
                "위반 유형 수": len(vtypes),
                "위반 유형": " · ".join(sorted(vtypes)),
                "복합위험점수": risk,
            })

        if not rows:
            st.info("복합 위반 사용자가 없습니다.")
        else:
            result = (pd.DataFrame(rows)
                      .sort_values(["위반 유형 수","복합위험점수"], ascending=False)
                      .reset_index(drop=True))

            # KPI
            n_multi  = len(result)
            n_3plus  = int((result["위반 유형 수"] >= 3).sum())
            top_dept = result["부서"].value_counts().idxmax() if n_multi else "-"
            ck, cv, cd = st.columns(3)
            for col, val, lbl, color in [
                (ck, f"{n_multi}명",  "복합 위반 사용자",    "#f43f5e"),
                (cv, f"{n_3plus}명",  "3개 이상 위반 유형",  "#f59e0b"),
                (cd, top_dept,         "최다 발생 부서",       "#2563eb"),
            ]:
                with col:
                    st.markdown(
                        f"<div class='kpi-box' style='--accent:{color};'>"
                        f"<div class='val' style='font-size:1.6rem;'>{val}</div>"
                        f"<div class='lbl'>{lbl}</div></div>",
                        unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # 복합 위반 사용자 목록 (풀 너비)
            st.markdown("<div class='card-title' style='margin-bottom:0.5rem;'>"
                        "<i class='fa-solid fa-users fa-sm'></i>  복합 위반 사용자 목록</div>",
                        unsafe_allow_html=True)
            st.dataframe(
                result[["이름","부서","역할","위반 유형 수","위반 유형","복합위험점수"]],
                width="stretch", hide_index=True,
                height=min(56 + len(result) * 35, 360),
                column_config={
                    "이름":       st.column_config.TextColumn(width="small"),
                    "부서":       st.column_config.TextColumn(width="small"),
                    "역할":       st.column_config.TextColumn(width="small"),
                    "위반 유형 수": st.column_config.NumberColumn(width="small", format="%d개"),
                    "위반 유형":  st.column_config.TextColumn(width="large"),
                    "복합위험점수": st.column_config.NumberColumn(width="small", format="%d점"),
                })

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

            # 위반 유형 조합 분포 차트 (풀 너비)
            st.markdown("<div class='card-title' style='margin-bottom:0.5rem;'>"
                        "<i class='fa-solid fa-chart-bar fa-sm'></i>  위반 유형 조합 분포</div>",
                        unsafe_allow_html=True)
            combo_cnt = result["위반 유형"].value_counts().head(8).reset_index()
            combo_cnt.columns = ["조합","인원"]
            combo_cnt = combo_cnt.sort_values("인원")
            fig_combo = go.Figure(go.Bar(
                x=combo_cnt["인원"], y=combo_cnt["조합"],
                orientation="h",
                marker=dict(color="#60a5fa", opacity=0.85, line=dict(width=0)),
                text=[f"{v}명" for v in combo_cnt["인원"]],
                textposition="outside",
                textfont=dict(size=11, color="#334155"),
                showlegend=False,
                hovertemplate="%{y}<br>%{x}명<extra></extra>",
            ))
            fig_combo.update_layout(
                height=280,
                margin=dict(l=10, r=50, t=10, b=10),
                plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="#f1f5f9",
                           tickfont=dict(size=10),
                           range=[0, combo_cnt["인원"].max() * 1.3]),
                yaxis=dict(tickfont=dict(size=11, color="#1e293b"), automargin=True),
            )
            st.plotly_chart(fig_combo, width="stretch", config={"displayModeBar": False})


# ════════════════════════════════════════════════════════════════
# VIEW: 점검 실행
# ════════════════════════════════════════════════════════════════
def view_scan(month):
    rules_count = get_rules_count()

    # 선택 월 기준 날짜 범위 계산
    year, mon = map(int, month.split("-"))
    import calendar
    last_day = calendar.monthrange(year, mon)[1]
    dt_from = f"{year}.{mon:02d}.01"
    dt_to   = f"{year}.{mon:02d}.{last_day:02d}"

    # 선택 월 로그 건수만 카운트
    def count_month(df, col):
        if df.empty or col not in df.columns: return 0
        df[col] = pd.to_datetime(df[col], errors="coerce")
        return int(((df[col].dt.year == year) & (df[col].dt.month == mon)).sum())

    df_acc  = load_db("access_log.csv")
    df_dep  = load_db("deploy_log.csv")
    df_bak  = load_db("backup_log.csv")
    df_itsm = load_db("itsm_req.csv")
    total_logs = (count_month(df_acc,  "access_dt") +
                  count_month(df_dep,  "deploy_dt") +
                  count_month(df_bak,  "backup_dt") +
                  count_month(df_itsm, "request_dt"))

    st.markdown("<div class='view-header'><i class='fa-solid fa-circle-play' style='color:#2563eb;margin-right:8px;font-size:1.1rem;'></i>점검 실행</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='view-sub'>분석 월: {MONTH_LABELS[month]}</div>",
                unsafe_allow_html=True)

    # 현황
    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl, color in [
        (c1, f"{total_logs:,}건", "분석 대상 로그", "#3b82f6"),
        (c2, f"{rules_count}개", "점검 규칙",    "#2563eb"),
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
    c1.info("**접근통제**\n\n계정·권한·퇴직자 관리")
    c2.info("**변경관리**\n\nCR·배포·직무분리")
    c3.info("**운영통제**\n\n로그·백업·권한검토")

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
        # 셀렉트박스 라벨 높이만큼 띄워 세로 정렬 맞춤
        st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
        already = os.path.exists(
            os.path.join(DATA_DIR, f"violations_summary_{selected}.csv"))
        if already:
            st.success(f"{MONTH_LABELS[selected]} 점검 결과 있음 — 재검사 가능")
        else:
            st.info(f"{MONTH_LABELS[selected]} 점검 결과 없음 — 검사를 실행해주세요")

    if st.session_state.scan_state == "idle":
        st.markdown(f"<p style='text-align:center;color:#64748b;margin:1rem 0;'>"
                    f"<b>{MONTH_LABELS[selected]}</b> 데이터를 점검합니다.</p>",
                    unsafe_allow_html=True)
        _, mid, _ = st.columns([2, 1, 2])
        with mid:
            if st.button("검사 시작", type="primary", use_container_width=True):
                st.session_state.scan_state = "running"
                st.rerun()

    elif st.session_state.scan_state == "running":
        st.markdown(f"<h4 style='text-align:center;color:#1a237e;'>"
                    f"{MONTH_LABELS[selected]} 점검 진행 중...</h4>",
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
            if st.button("재검사", use_container_width=True):
                st.session_state.scan_state = "idle"; st.rerun()
        with c2:
            if st.button("결과 보기", use_container_width=True, type="primary"):
                st.session_state.view = "overview"; st.rerun()


# ════════════════════════════════════════════════════════════════
# VIEW: 보고서
# ════════════════════════════════════════════════════════════════
def view_report(month):
    df = load_summary(month)
    st.markdown("<div class='view-header'><i class='fa-solid fa-file-lines' style='color:#2563eb;margin-right:8px;font-size:1.1rem;'></i>보고서 생성</div>", unsafe_allow_html=True)
    if df is None:
        st.warning("점검 결과 없음 — '점검 실행' 메뉴에서 먼저 점검을 실행해주세요.")
        return

    scores   = calc_scores(df, month=month)
    min_sc   = min(scores.values())
    _, mg_col = grade(min_sc)

    # KPI 카드 (흰 배경)
    kpis = [
        (f"{len(df)}개", "점검 규칙", "#60a5fa"),
        (f"{int((df['yn_violation']=='Y').sum())}개", "위반 탐지", "#fb7185"),
        (datetime.now().strftime("%Y.%m.%d"), "기준일", "#22d3ee"),
        (f"{min_sc}점", "최저 점수", mg_col),
    ]
    kc = st.columns(4)
    for col, (val, lbl, color) in zip(kc, kpis):
        with col:
            st.markdown(
                f"<div class='kpi-box' style='--accent:{color};'>"
                f"<div class='val'>{val}</div>"
                f"<div class='lbl'>{lbl}</div></div>",
                unsafe_allow_html=True)

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)

    # 보고서 종류 안내 (흰 카드)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "<div class='dash-card'>"
            "<div style='font-size:0.95rem;font-weight:800;color:#0f172a;"
            "margin-bottom:0.6rem;'>"
            "<i class='fa-solid fa-file-excel' style='color:#22c55e;"
            "margin-right:7px;'></i>Excel 보고서</div>"
            "<ul style='margin:0;padding-left:1.1rem;color:#475569;"
            "font-size:0.85rem;line-height:1.9;'>"
            "<li>규칙별 위반 현황표</li>"
            "<li>도메인별 요약 집계</li>"
            "<li>심각도별 분류</li></ul></div>",
            unsafe_allow_html=True)
    with col2:
        st.markdown(
            "<div class='dash-card'>"
            "<div style='font-size:0.95rem;font-weight:800;color:#0f172a;"
            "margin-bottom:0.6rem;'>"
            "<i class='fa-solid fa-file-word' style='color:#2563eb;"
            "margin-right:7px;'></i>Word 보고서</div>"
            "<ul style='margin:0;padding-left:1.1rem;color:#475569;"
            "font-size:0.85rem;line-height:1.9;'>"
            "<li>표지 + 점검 총평</li>"
            "<li>도메인별 상세 분석</li>"
            "<li>AI 기반 시정조치 권고</li></ul></div>",
            unsafe_allow_html=True)

    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    if st.button("보고서 생성", type="primary"):
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
        ("xlsx","Excel 다운로드","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("docx","Word 다운로드", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
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
    month = render_topbar()
    view = st.session_state.view

    if view == "overview":
        view_overview(month)
    elif view == "access":
        view_domain(month, "접근통제")
    elif view == "change":
        view_domain(month, "변경관리")
    elif view == "ops":
        view_domain(month, "운영통제")
    elif view == "analysis":
        view_analysis(month)
    elif view == "ai":
        view_ai(month)
    elif view == "sanctions":
        view_sanctions(month)
    elif view == "scan":
        view_scan(month)
    elif view == "report":
        view_report(month)

if __name__ == "__main__":
    main()
