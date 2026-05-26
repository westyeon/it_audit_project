# AI 기반 금융권 IT감사 사전 통제 점검 및 위반 자동 탐지 시스템

## 프로젝트 개요
- **목적**: 금융권 법령/가이드라인 기반으로 IT통제 위반을 자동 탐지하고 보고서를 생성하는 시스템
- **대상 기관**: 신용평가사 중견사 (직원 500명 규모 가상 데이터)
- **GitHub**: https://github.com/westyeon/it_audit_project

## 디렉토리 구조
```
it_audit_project/
├── src/
│   ├── crawlers/          # 법령/가이드라인 수집
│   ├── generate_virtual_db.py   # 가상 DB 생성
│   ├── preprocess.py            # 파생 컬럼 생성
│   ├── rule_converter.py        # 법령 → Rule JSON (Claude API)
│   └── rule_engine.py           # 위반 자동 탐지
├── data/
│   ├── raw/               # 수집 원본
│   └── processed/
│       ├── virtual_db/    # 가상 DB CSV (6개 테이블)
│       ├── rules.json     # 70개 점검 규칙
│       ├── violations_summary.csv  # 규칙별 위반 건수
│       └── violations_detail.csv   # 위반 상세 목록
├── notebooks/
│   └── analysis.ipynb     # 분석 노트북 (섹션 0~6 구현됨)
├── .env                   # API 키 (절대 커밋 금지)
├── .env.example
└── requirements.txt
```

## 환경 설정
- **Python 환경**: conda `it_audit` 환경 사용
- **경로**: BASE_DIR = `/Users/kwakseoyeon/Documents/it_audit_project`
- **.env 필수 항목**:
  ```
  ANTHROPIC_API_KEY=sk-ant-...
  LAW_API_KEY=kwakseoyeon97
  ```
- **한글 폰트**: matplotlib → `AppleGothic` (Mac 기준)

## 가상 DB 시스템 코드 (신용평가사 특화)
```
CRED   → 신용평가시스템
PORTAL → 고객포털
ERP    → 경영관리시스템
DW     → 데이터웨어하우스
DEVP   → 개발포털
```
- 이전에 CORE/IBANK/ADMIN/INFO 였던 것을 변경함
- rules.json pandas_logic에도 모두 반영 완료

## 가상 DB 테이블 구조 (주요 컬럼)

### emp_master (500행)
- emp_id, emp_no, emp_nm, dept_cd, dept_nm
- role_type: NORMAL/ADMIN/DEV/SECUR
- hire_dt, resign_dt, yn_employed (Y/N)

### sys_account (1,195행)
- account_seq, emp_id, system_cd, login_id
- account_type: NORMAL/ADMIN/SVC
- account_status: **active/inactive/locked** (소문자)
- permission_level: READ/WRITE/ADMIN
- last_pw_change_dt, last_review_dt
- 파생: review_elapsed_days, yn_overdue_review (Y/N)

### access_log (322,445행)
- log_seq, emp_id, system_cd, access_dt
- action_type: LOGIN/QUERY/UPDATE/DELETE/DOWNLOAD
- src_ip, result_cd: **S/F** (SUCCESS=S, FAIL=F)
- 파생: yn_after_hours (Y/N), yn_post_resign_access (Y/N)

### itsm_req (184행)
- doc_no, request_dt, approval_dt, req_status
- req_type: DEV/DML/DDL/AUTH/EMER
- requester_id, deployer_id

### deploy_log (184행)
- deploy_seq, doc_no, deployer_id, system_cd, deploy_dt
- env_type: DEV/STG/**prod** (소문자)
- yn_emergency: Y/N
- 파생: yn_post_approval, yn_job_sep_violation, yn_no_cr

### backup_log (905행)
- backup_seq, system_cd, backup_dt, backup_type: FULL/INCREMENTAL
- backup_status: **S/F/PARTIAL** (SUCCESS=S, FAIL=F)
- yn_restore_test: Y/N

## Rule 엔진 주의사항
- `df_emp`, `df_account`, `df_access`, `df_itsm`, `df_deploy`, `df_backup` 으로 참조
- 대소문자 주의: account_status는 소문자(`active`), env_type도 소문자(`prod`)
- rule_engine.py에서 자동 치환 로직 있음 ('PRD'→'prod', 'ACTIVE'→'active', 'SUCCESS'→'S', 'FAIL'→'F')
- eval() vs exec() 혼용: 대입문/다중구문은 exec(), 순수 표현식은 eval()

## Rule 엔진 결과 (현재 기준)
- 총 점검 규칙: **70개** (접근통제 42 / 변경관리 15 / 운영통제 13)
- 위반 탐지: **43개 규칙 (61.4%)**
- 도메인별: 변경관리 73.3% > 접근통제 59.5% > 운영통제 53.8%

## 주요 위반 탐지 내용
| 위반 유형 | 건수 | 심각도 |
|---|---|---|
| 퇴사자 활성 계정 미삭제 | 15건 | HIGH |
| 권한검토 180일 초과 | 30건 | HIGH |
| 업무시간 외 접속 (22~06시) | 82건 | MEDIUM |
| CR 없는 무단 배포 | 15건 | HIGH |
| 사후 승인 배포 | 20건 | HIGH |
| 직무분리 위반 (신청=배포) | 15건 | HIGH |
| 백업 실패 | 20건 | MEDIUM |
| FULL백업 복구테스트 미실시 | 40건 | MEDIUM |

## 완료된 작업
- [x] 법령 수집 (법제처 API, KOFIA, 금감원 해설서, 제재공시)
- [x] 가상 DB 생성 (500명 규모, 위반 데이터 주입 포함)
- [x] 전처리 (파생 컬럼 생성)
- [x] Rule JSON 변환 (Claude API → rules.json 70개)
- [x] Rule 엔진 실행 (violations_summary.csv, violations_detail.csv)
- [x] 분석 노트북 뼈대 (analysis.ipynb 섹션 0~6)

## 미완료 작업 (TODO)
- [ ] 분석 노트북 심화 (시각화 다양화, 인사이트 도출) - 서연님 직접
- [ ] report_generator.py (Excel + Word 보고서 자동 생성, Claude API로 자연어 분석 포함)
- [ ] main.py (전체 파이프라인 진입점)
- [ ] app.py (Streamlit 대시보드, 업무망 로컬 실행용)

## 실행 순서
```bash
# 1. 가상 DB 생성
python src/generate_virtual_db.py
python src/preprocess.py

# 2. Rule JSON 변환 (ANTHROPIC_API_KEY 필요)
python src/rule_converter.py

# 3. Rule 엔진 실행
python src/rule_engine.py

# 4. 보고서 생성 (미구현)
python src/report_generator.py

# 5. 대시보드 (미구현)
streamlit run app.py
```

## 중요 주의사항
- `.env` 파일은 절대 GitHub에 올리지 말 것 (.gitignore에 포함됨)
- access_log.csv는 20MB → GitHub에 포함됨 (2025-05-26부터)
- 노트북 실행 시 `notebooks/` 폴더 기준으로 경로 설정됨 (`BASE = '../data'`)
- 다른 PC에서 실행 시 matplotlib 한글 폰트 설정 확인 필요 (Mac: AppleGothic, Windows: Malgun Gothic)
