"""
법령/가이드라인 텍스트 → Rule JSON 변환기
- 입력: data/raw/law_articles.csv, kofia_guidelines.csv, fss_guide_articles.csv
- 출력: data/processed/rules.json

Claude API를 사용해 IT감사 핵심 조항을 가상DB 기반 점검 규칙으로 변환
"""

import os
import json
import pandas as pd
from anthropic import Anthropic
from dotenv import dotenv_values

_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))
_api_key = _env.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

# .env에 ANTHROPIC_API_KEY 필요
client = Anthropic(api_key=_api_key)

# ─── 가상 DB 스키마 설명 (시스템 프롬프트용) ──────────────────────────────
DB_SCHEMA = """
가상 DB 테이블 구조 (Python pandas DataFrame으로 분석):

[emp_master] 직원 마스터
- emp_id: 직원ID (int)
- emp_no: 사번 (str, 예: A240032)
- emp_nm: 이름 (str)
- dept_cd / dept_nm: 부서코드/명 (str)
- role_type: 역할 (NORMAL/ADMIN/DEV/SECUR)
- hire_dt: 입사일 (datetime)
- resign_dt: 퇴사일 (datetime, 재직중이면 NaT)
- yn_employed: 재직여부 (Y/N)

[sys_account] 시스템 계정
- account_seq: PK
- emp_id: 직원ID (int)
- system_cd: 시스템코드 (CORE/IBANK/ADMIN/INFO/DEVP)
- login_id: 로그인ID (str)
- account_type: NORMAL/ADMIN/SVC
- account_status: ACTIVE/INACTIVE/LOCKED
- permission_level: READ/WRITE/ADMIN
- last_pw_change_dt: 마지막 비밀번호 변경일 (datetime)
- last_review_dt: 마지막 권한검토일 (datetime)

[access_log] 시스템 접근 로그
- log_seq: PK
- emp_id: 직원ID
- system_cd: 시스템코드
- access_dt: 접근일시 (datetime)
- action_type: LOGIN/QUERY/UPDATE/DELETE/DOWNLOAD
- src_ip: 접속IP (str)
- result_cd: SUCCESS/FAIL

[itsm_req] 변경요청서 (ITSM)
- doc_no: 문서번호 (str, 예: CR-2024-0001)
- request_dt: 신청일 (datetime)
- approval_dt: 최종결재일 (datetime, 미결재시 NaT)
- req_status: DRAFT/APPROVED/REJECTED/CLOSED
- system_cd: 대상시스템
- req_type: DEV/DML/DDL/AUTH/EMER
- requester_id: 신청자 emp_id
- deployer_id: 배포담당자 emp_id

[deploy_log] 배포 이력
- deploy_seq: PK
- doc_no: 연결 ITSM 문서번호 (str, 없으면 null)
- deployer_id: 배포자 emp_id
- system_cd: 배포시스템
- deploy_dt: 배포일시 (datetime)
- env_type: DEV/STG/PRD (운영=PRD)
- yn_emergency: 긴급배포여부 (Y/N)

[backup_log] 백업 이력
- backup_seq: PK
- system_cd: 시스템코드
- backup_dt: 백업일시 (datetime)
- backup_type: FULL/INCREMENTAL
- backup_status: SUCCESS/FAIL/PARTIAL
- yn_restore_test: 복구테스트 수행여부 (Y/N)
- file_size_gb: 파일크기(GB)

파생 컬럼 (preprocess.py로 추가됨):
- access_log.yn_after_hours: 업무시간외(22:00~06:00) 접속 (Y/N)
- access_log.yn_post_resign_access: 퇴사 후 접속 (Y/N)
- sys_account.review_elapsed_days: 권한검토 경과일수 (int)
- sys_account.yn_overdue_review: 권한검토 180일 초과 (Y/N)
- deploy_log.yn_post_approval: 사후승인 배포 (deploy_dt < approval_dt) (Y/N)
- deploy_log.yn_job_sep_violation: 직무분리 위반 (신청자=배포자) (Y/N)
- deploy_log.yn_no_cr: CR없는 무단배포 (doc_no IS NULL) (Y/N)
"""

SYSTEM_PROMPT = f"""당신은 금융권 IT감사 전문가입니다.
아래 가상 DB 스키마를 기반으로, 제공된 법령/가이드라인 조문에서
자동화된 점검이 가능한 IT감사 규칙을 JSON 형식으로 추출하세요.

{DB_SCHEMA}

출력 형식 (JSON 배열):
[
  {{
    "rule_id": "R001",
    "rule_nm": "규칙명 (한글, 20자 이내)",
    "audit_domain": "접근통제 | 변경관리 | 운영통제 중 하나",
    "source_law": "출처 법령명",
    "source_article": "관련 조문 요약 (50자 이내)",
    "check_target": "점검 대상 테이블명 (예: sys_account, access_log)",
    "condition_desc": "점검 조건 설명 (한글, 100자 이내)",
    "pandas_logic": "pandas/python 코드로 위반 건수 산출하는 표현 (한 줄 또는 다중 줄 코드 블록)",
    "severity": "HIGH | MEDIUM | LOW",
    "remediation": "시정 조치 방향 (50자 이내)"
  }}
]

규칙 작성 시 유의사항:
1. 가상 DB 컬럼명을 정확히 사용할 것 (오타 금지)
2. pandas_logic은 실제 실행 가능한 파이썬 코드여야 함
3. 테이블은 df_emp, df_account, df_access, df_itsm, df_deploy, df_backup 으로 참조
4. 파생 컬럼도 사용 가능
5. 중복 규칙 배제, 실무적으로 점검 가능한 것만 추출
6. 반드시 JSON만 출력 (설명 텍스트 없이)
"""

# ─── IT감사 핵심 조항 필터링 ──────────────────────────────────────────────
IT_KEYWORDS = [
    "접근통제", "접근권한", "권한", "계정", "비밀번호", "패스워드",
    "변경관리", "배포", "승인", "직무분리", "변경요청",
    "백업", "복구", "운영", "보안", "로그", "감사",
    "정보보호", "보호조치", "이상징후", "침해", "인증",
    "내부통제", "IT통제", "전산", "시스템", "운영자",
]

def filter_articles(df: pd.DataFrame, text_col: str, max_rows: int = 15) -> pd.DataFrame:
    """IT감사 관련 핵심 조항만 필터링"""
    mask = df[text_col].str.contains("|".join(IT_KEYWORDS), na=False, regex=True)
    filtered = df[mask].copy()
    # 너무 짧거나 긴 텍스트 제외
    filtered = filtered[filtered[text_col].str.len().between(30, 800)]
    # 랜덤 샘플링 (균등 분포)
    if len(filtered) > max_rows:
        filtered = filtered.sample(n=max_rows, random_state=42)
    return filtered


def load_source_articles() -> list[dict]:
    """3개 소스에서 IT감사 관련 조항 로드"""
    base = "data/raw"
    articles = []

    # 1. 법령 (전자금융감독규정 위주)
    df_law = pd.read_csv(f"{base}/law_articles.csv", encoding="utf-8-sig")
    # 전자금융감독규정 집중 (IT감사에 가장 직접적)
    efg = df_law[df_law["법령명"] == "전자금융감독규정"].copy()
    efg_filtered = filter_articles(efg, "조문내용", max_rows=20)
    for _, row in efg_filtered.iterrows():
        articles.append({
            "source": row["법령명"],
            "text": row["조문내용"]
        })

    # 기타 법령 (접근통제/백업 관련만)
    other_law = df_law[df_law["법령명"] != "전자금융감독규정"]
    other_filtered = filter_articles(other_law, "조문내용", max_rows=10)
    for _, row in other_filtered.iterrows():
        articles.append({
            "source": row["법령명"],
            "text": row["조문내용"]
        })

    # 2. KOFIA 가이드라인
    df_kofia = pd.read_csv(f"{base}/kofia_guidelines.csv", encoding="utf-8-sig")
    kofia_filtered = filter_articles(df_kofia, "조문내용", max_rows=10)
    for _, row in kofia_filtered.iterrows():
        articles.append({
            "source": "금융투자협회 IT감사 가이드라인",
            "text": row["조문내용"]
        })

    # 3. FSS 해설서 (IT감사영역 태그 있는 것 우선)
    df_fss = pd.read_csv(f"{base}/fss_guide_articles.csv", encoding="utf-8-sig")
    if "IT감사영역" in df_fss.columns:
        tagged = df_fss[df_fss["IT감사영역"].notna() & (df_fss["IT감사영역"] != "")]
        fss_filtered = filter_articles(tagged, "내용", max_rows=10)
        text_col = "내용"
    else:
        fss_filtered = filter_articles(df_fss, "내용", max_rows=10)
        text_col = "내용"

    for _, row in fss_filtered.iterrows():
        articles.append({
            "source": "금융감독원 전자금융감독규정 해설서(2025.8)",
            "text": str(row[text_col])
        })

    print(f"총 {len(articles)}개 조항 선별 완료")
    return articles


def convert_to_rules(articles: list[dict], batch_size: int = 8) -> list[dict]:
    """Claude API로 조항 배치 → Rule JSON 변환"""
    all_rules = []
    rule_counter = 1

    batches = [articles[i:i+batch_size] for i in range(0, len(articles), batch_size)]
    print(f"총 {len(batches)}배치 처리 시작...")

    for b_idx, batch in enumerate(batches):
        print(f"  배치 {b_idx+1}/{len(batches)} 처리 중...", end=" ", flush=True)

        # 배치 텍스트 구성
        user_text = f"다음 {len(batch)}개 조항에서 IT감사 점검 규칙을 추출하세요.\n\n"
        for i, art in enumerate(batch, 1):
            user_text += f"[조항 {i}] 출처: {art['source']}\n{art['text']}\n\n"
        user_text += f"\n이 조항들에서 추출 가능한 규칙을 JSON 배열로 출력하세요. rule_id는 R{rule_counter:03d}부터 순번으로 부여하세요."

        try:
            response = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_text}]
            )

            raw = response.content[0].text.strip()

            # JSON 추출 (코드블록 제거)
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            rules = json.loads(raw)
            if isinstance(rules, list):
                all_rules.extend(rules)
                rule_counter += len(rules)
                print(f"{len(rules)}개 규칙 추출")
            else:
                print("JSON 배열이 아님, 스킵")

        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"  원본 응답 일부: {raw[:200]}")
        except Exception as e:
            print(f"API 오류: {e}")

    return all_rules


def deduplicate_rules(rules: list[dict]) -> list[dict]:
    """중복 규칙 제거 및 rule_id 재정렬"""
    seen_nms = set()
    unique = []
    for rule in rules:
        nm = rule.get("rule_nm", "")
        if nm and nm not in seen_nms:
            seen_nms.add(nm)
            unique.append(rule)

    # rule_id 재정렬
    for i, rule in enumerate(unique, 1):
        rule["rule_id"] = f"R{i:03d}"

    return unique


if __name__ == "__main__":
    import os
    os.chdir("/Users/kwakseoyeon/Documents/it_audit_project")

    # ANTHROPIC_API_KEY 확인
    if not _api_key:
        print("❌ .env에 ANTHROPIC_API_KEY가 없습니다.")
        print("   .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요.")
        exit(1)

    print("=" * 60)
    print("Rule JSON 변환 시작")
    print("=" * 60)

    # 1. 조항 로드
    articles = load_source_articles()

    # 2. Claude API 변환
    rules = convert_to_rules(articles, batch_size=8)
    print(f"\n원본 추출 규칙: {len(rules)}개")

    # 3. 중복 제거
    rules = deduplicate_rules(rules)
    print(f"중복 제거 후: {len(rules)}개")

    # 4. 저장
    out_path = "data/processed/rules.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)
    print(f"\n저장 완료 → {out_path}")

    # 5. 요약 출력
    print("\n[도메인별 규칙 현황]")
    from collections import Counter
    domain_cnt = Counter(r.get("audit_domain", "기타") for r in rules)
    for domain, cnt in sorted(domain_cnt.items()):
        print(f"  {domain}: {cnt}개")

    print("\n[심각도별 규칙 현황]")
    sev_cnt = Counter(r.get("severity", "MEDIUM") for r in rules)
    for sev, cnt in sorted(sev_cnt.items()):
        print(f"  {sev}: {cnt}개")

    print("\n[생성된 규칙 목록]")
    for r in rules:
        print(f"  {r['rule_id']} [{r.get('audit_domain','?')}] {r.get('rule_nm','?')} ({r.get('severity','?')})")
