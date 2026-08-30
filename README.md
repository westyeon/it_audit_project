# AI 기반 금융권 IT감사 사전 통제 점검 및 보고서 자동 생성 시스템

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://it-audit.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude_API-Anthropic-D97757?logo=anthropic&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)

> **서강대학교 대학원 | 생성형 AI 활용 과목 프로젝트**  
> 법령 기반 IT통제 점검 규칙을 자동 생성하고, 36만 건 로그를 전수 분석해 위반을 탐지·시각화·보고서로 출력하는 시스템

---

## 문제 정의 (Problem)

금융권 IT감사 현장에서 반복되는 3가지 구조적 문제를 해결하고자 합니다.

| # | 문제 | 설명 |
|---|------|------|
| 01 | **사전 점검 체계 부재** | 전문 지식과 자체 점검 시스템이 없어 감사를 받아야만 문제를 인지 |
| 02 | **소통의 어려움** | 감사인·개발자 간 공통 언어 부재 → 추상적 질의와 반복적 소명 발생 |
| 03 | **취약 패턴 미파악** | 위반 원인에 대한 정량적 분석 불가, 일회성 대응에 그침 |

---

## 솔루션 (Solution)

```
법령 텍스트 → AI Rule 자동 생성 → 전수 탐지 → 점수화 → 대시보드 + 보고서 자동 출력
```

| # | 솔루션 | 효과 |
|---|--------|------|
| 01 | **Rule 엔진 기반 사전 통제 점검 자동화** | 법적 리스크 사전 차단, 감사 준비 시간 단축 |
| 02 | **통제 기준의 데이터화 + 근거 제시** | 정확한 수치로 객관적 증명, 감사인·개발자 공통 언어 제공 |
| 03 | **설계·운영 이중 평가 + AI 취약 패턴 분석** | 근본 원인 파악 후 구조적 개선 가이드 제공 |

---

## AI 활용 포인트

이 프로젝트에서 AI는 단순 부가 기능이 아니라 핵심 구현 수단입니다.

- **법령 → 규칙 자동 변환**: 약 1,900개 법령 조항을 Claude API가 분석해 실행 가능한 점검 규칙(pandas 코드 포함)으로 자동 생성
- **위반 해석 자동화**: 탐지된 로그 수치를 AI가 자연어로 해석하고 우선 조치 방향을 제시
- **제재 사례 자동 매칭**: 금감원 IT 제재공시 203건을 위반 항목과 자동 연결해 유사 사례 경고
- **보고서 자동 생성**: 점검 결과를 바탕으로 Word·Excel 감사보고서를 원클릭으로 출력

---

## 시스템 파이프라인

```mermaid
flowchart LR
    A["📚 데이터 수집\n법제처 API\n금투협·금감원\nPDF·HTML"] --> B["🔧 전처리\n조항 단위 분할\n노이즈 제거\n가상 DB 생성"]
    B --> C["🤖 AI Rule 변환\nClaude API\n법령 조항 →\npandas 점검 규칙"]
    C --> D["🔍 위반 탐지\n70개 규칙\n36만 건 전수 적용\n위반 건수 산출"]
    D --> E["📊 점수화\n설계 40%\n운영 60%\n100점 만점"]
    E --> F["🖥️ 대시보드\nStreamlit\nPlotly"]
    E --> G["📄 보고서\nWord·Excel\n자동 생성"]
```

---

## 점검 결과 요약

### 점검 규모

| 지표 | 수치 |
|------|------|
| 점검 규칙 수 | **70개** (접근통제 42 / 변경관리 15 / 운영통제 13) |
| 법령 출처 | 전자금융감독규정, 개인정보보호법, 정보보호관리체계 기준 등 7개 법령 |
| 적용 로그 | **약 36만 건** (6개월 접근 로그 기준) |
| 위반 탐지 규칙 | **43개** (전체 대비 **61.4%** 위반율) |

### 위험도 평가 기준

본 프로젝트에서는 IT감사 맥락에 맞게 **설계(규칙 준수)와 운영(실제 로그) 두 축**으로 위험도를 평가하는 기준을 자체 설계했습니다.

```
종합 점수 = 설계 점수(40%) × 규칙 준수율 + 운영 점수(60%) × 로그 준수율
```

- **설계 점수**: 위반이 없는 규칙 비율 — 통제 체계 자체가 잘 갖춰졌는지
- **운영 점수**: 전체 로그 중 위반 로그 비율 — 실제 현장에서 규칙이 지켜지는지

| 구간 | 등급 | 설명 |
|------|------|------|
| 80점 이상 | 🟢 정상 | 통제 체계 양호 |
| 60 ~ 79점 | 🟡 주의 | 개선 권고 |
| 60점 미만 | 🔴 고위험 | 즉각 조치 필요 |

### 규칙별 위험도 분류

규칙 단위에서는 심각도와 위반 빈도를 함께 반영한 점수를 산출해 우선순위를 부여합니다. 위반 건수가 많더라도 심각도가 낮으면 낮게 평가되고, 건수가 적더라도 HIGH 규칙이면 높게 평가되도록 설계했습니다.

| 등급 | 설명 |
|------|------|
| Critical | 즉각 감사 보고 필요 수준 |
| High | 우선 조치 권고 수준 |
| Medium | 모니터링 강화 수준 |
| Low | 주의 관찰 수준 |

---

## 주요 기능 (대시보드 8개 뷰)

| 메뉴 | 내용 |
|------|------|
| 종합 현황 | 도메인별 종합 점수, 월별 위반 추이, 핵심 위험 지표 |
| 규칙별 점검 결과 | 70개 규칙 전체 위반 여부·건수·심각도 |
| 심화 분석 | 부서별·역할별 위험도, 규칙별 위험도 분포, 법령 준수율, 복합 위험 사용자 |
| AI 인사이트 | 위반 해석·우선 조치·종합 총평 (Claude API Streaming) |
| 제재 사례 | 금감원 IT 제재공시 203건 매칭 및 경고 |
| 비교 분석 | 전월 대비 위반 변동 추이 |
| 월별 트렌드 | 7개월(2025.11~2026.05) 위반 패턴 변화 |
| 보고서 생성 | Word·Excel 감사보고서 원클릭 다운로드 |

---

## 확장 가능성

현재는 학습 목적의 가상 DB 환경에서 구현했으나, 시스템 구조 자체는 실제 환경으로의 확장을 고려해 설계했습니다.

- 점검 데이터 소스를 교체하면 실제 HR·계정·로그 데이터에도 동일한 Rule 엔진을 적용할 수 있습니다.
- 법령이 개정되더라도 `rule_converter.py`를 재실행하면 점검 규칙이 자동으로 업데이트됩니다.
- 대시보드와 보고서 출력 구조는 데이터 소스와 독립적으로 동작합니다.

---

## 수집 데이터

| 출처 | 내용 | 수량 |
|------|------|------|
| 법제처 Open API | 전자금융감독규정 등 7개 법령 | 약 800개 조문 |
| 금융투자협회 | IT감사 가이드라인 | 42개 항목 |
| 금융감독원 | 전자금융감독규정 해설서(2025.8) | 284개 항목 |
| 금융감독원 | IT관련 제재공시 | 203건 |
| **합계** | | **약 1,900개 조항** |

---

## 가상 DB 구성

금융권 중견사(직원 500명) 규모로 생성. 의도적 위반 패턴 삽입으로 탐지 시나리오 구현.

| 테이블 | 설명 | 행 수 |
|--------|------|-------|
| emp_master | 직원 마스터 (재직·퇴직) | 500행 |
| sys_account | 시스템 계정 (권한·상태) | 1,195행 |
| access_log | 시스템 접근 로그 (6개월) | 322,445행 |
| itsm_req | IT 변경요청서 | 184행 |
| deploy_log | 배포 이력 | 184행 |
| backup_log | 백업 이력 | 905행 |

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Language | Python 3.11+ |
| Frontend | Streamlit, Plotly |
| AI | Anthropic Claude API (claude-opus-4-5) |
| Data | Pandas, NumPy |
| Crawling | requests, BeautifulSoup4, pdfplumber |
| Report | python-docx, openpyxl |
| Data Gen | Faker |
| Deploy | Streamlit Cloud |

---

## 프로젝트 구조

```
it_audit_project/
├── app.py                          # Streamlit 대시보드 메인 (8개 뷰)
├── main.py                         # 전체 파이프라인 실행 진입점
├── src/
│   ├── crawlers/
│   │   ├── law_api.py              # 법제처 API 법령 수집
│   │   ├── kofia_crawler.py        # 금투협 IT감사 가이드라인 수집
│   │   ├── fss_guide_parser.py     # 금감원 전자금융감독규정 해설서 파싱
│   │   └── fss_sanction_crawler.py # 금감원 IT 제재공시 수집
│   ├── generate_virtual_db.py      # 가상 DB 생성 (500명 규모 금융사)
│   ├── preprocess.py               # 파생 컬럼 생성 (위반 판정 플래그)
│   ├── rule_converter.py           # 법령 조항 → Rule JSON 변환 (Claude API)
│   ├── rule_engine.py              # Rule 엔진 (70개 규칙 전수 적용)
│   └── report_generator.py         # Word·Excel 보고서 자동 생성
├── data/
│   ├── raw/                        # 수집 원본 (법령·가이드라인·제재공시)
│   └── processed/                  # 전처리 결과 (rules.json, violations_summary.csv 등)
├── notebooks/
│   └── analysis.ipynb              # 탐색적 데이터 분석
├── .env.example                    # 환경변수 설정 예시
└── requirements.txt                # 의존성 패키지
```

---

## 실행 방법

### 환경 설정

```bash
git clone https://github.com/westyeon/it_audit_project.git
cd it_audit_project
pip install -r requirements.txt
cp .env.example .env
# .env에 ANTHROPIC_API_KEY 입력
```

### 대시보드 바로 실행 (분석 결과 포함)

```bash
streamlit run app.py
```

### 전체 파이프라인 순서 실행

```bash
# 1. 법령·가이드라인 수집
python src/crawlers/law_api.py
python src/crawlers/kofia_crawler.py
python src/crawlers/fss_guide_parser.py
python src/crawlers/fss_sanction_crawler.py

# 2. 가상 DB 생성 및 전처리
python src/generate_virtual_db.py
python src/preprocess.py

# 3. Rule JSON 변환 (Claude API 호출)
python src/rule_converter.py

# 4. Rule 엔진 실행 (위반 탐지)
python src/rule_engine.py

# 5. 대시보드 실행
streamlit run app.py
```

### 배포 버전 바로 보기

**[https://it-audit.streamlit.app/](https://it-audit.streamlit.app/)**

