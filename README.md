# AI 기반 금융권 IT감사 사전 통제 점검 및 위반 자동 탐지 시스템

## 프로젝트 개요

금융권 IT감사에 필요한 법령·가이드라인을 자동 수집하고, 가상 DB에 Rule 엔진을 적용하여 IT통제 위반을 자동으로 탐지하는 시스템입니다.

## 시스템 구성

```
데이터 수집 → 가상 DB 생성 → 전처리 → Rule JSON 변환 → Rule 엔진 → 분석·보고서
```

## 디렉토리 구조

```
it_audit_project/
├── src/
│   ├── crawlers/
│   │   ├── law_api.py              # 법제처 API 법령 수집
│   │   ├── kofia_crawler.py        # 금투협 IT감사 가이드라인 수집
│   │   ├── fss_guide_parser.py     # 금감원 전자금융감독규정 해설서 파싱
│   │   └── fss_sanction_crawler.py # 금감원 IT 제재공시 수집
│   ├── generate_virtual_db.py      # 가상 DB 생성 (500명 규모 금융사)
│   ├── preprocess.py               # 파생 컬럼 생성
│   ├── rule_converter.py           # 법령 → Rule JSON 변환 (Claude API)
│   └── rule_engine.py              # Rule 엔진 (위반 자동 탐지)
├── data/
│   ├── raw/                        # 수집 원본 데이터
│   └── processed/                  # 전처리 및 분석 결과
├── .env.example                    # 환경변수 설정 예시
├── requirements.txt                # 필요 라이브러리
└── README.md
```

## 수집 데이터

| 출처 | 내용 | 건수 |
|---|---|---|
| 법제처 Open API | 전자금융감독규정 등 7개 법령 | 800개 조문 |
| 금융투자협회 | IT감사 가이드라인 | 42개 항목 |
| 금융감독원 | 전자금융감독규정 해설서(2025.8) | 284개 항목 |
| 금융감독원 | IT관련 제재공시 | 203건 |

## 가상 DB 구성

금융권 중견사(직원 500명) 규모의 가상 HR·IT 데이터

| 테이블 | 설명 | 행 수 |
|---|---|---|
| emp_master | 직원 마스터 | 500행 |
| sys_account | 시스템 계정 | 1,195행 |
| access_log | 시스템 접근 로그 (6개월) | 322,445행 |
| itsm_req | IT 변경요청서 | 184행 |
| deploy_log | 배포 이력 | 184행 |
| backup_log | 백업 이력 | 905행 |

## Rule 엔진 결과

- 총 점검 규칙: **70개** (접근통제 42 / 변경관리 15 / 운영통제 13)
- 위반 탐지: **43개 규칙**

## 실행 방법

### 1. 환경 설정

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일에 API 키 입력
```

### 2. 데이터 수집

```bash
python src/crawlers/law_api.py
python src/crawlers/kofia_crawler.py
python src/crawlers/fss_guide_parser.py
python src/crawlers/fss_sanction_crawler.py
```

### 3. 가상 DB 생성 및 전처리

```bash
python src/generate_virtual_db.py
python src/preprocess.py
```

### 4. Rule JSON 변환 (Claude API 필요)

```bash
python src/rule_converter.py
```

### 5. Rule 엔진 실행

```bash
python src/rule_engine.py
```

## 기술 스택

- **언어**: Python 3.11+
- **주요 라이브러리**: pandas, requests, BeautifulSoup4, pdfplumber, Faker
- **AI**: Anthropic Claude API (Rule JSON 변환)
