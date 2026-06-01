"""
IT감사 Rule 엔진
- rules.json의 각 규칙을 읽어 가상 DB에 적용
- 위반 건수 요약 및 상세 목록 저장

입력:  data/processed/rules.json
       data/processed/virtual_db/*.csv
출력:  data/processed/violations_summary.csv  ← 규칙별 위반 건수 요약
       data/processed/violations_detail.csv   ← 위반 건별 상세 목록
"""

import os
import json
import argparse
import pandas as pd
from datetime import datetime

# ── 경로 설정 ────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR    = os.path.join(BASE_DIR, "data", "processed", "virtual_db")
RULES_PATH = os.path.join(BASE_DIR, "data", "processed", "rules.json")
OUT_DIR   = os.path.join(BASE_DIR, "data", "processed")

SEVERITY_SCORE = {"HIGH": 10, "MEDIUM": 5, "LOW": 2}


# ── 1. 데이터 로드 ───────────────────────────────────────────
def load_data() -> dict:
    """
    가상 DB 6개 테이블을 모두 불러옴
    - eval()에서 df_emp, df_account 등으로 참조됨
    """
    print("데이터 로드 중...")
    dfs = {
        "df_emp":     pd.read_csv(f"{DB_DIR}/emp_master.csv",   encoding="utf-8-sig"),
        "df_account": pd.read_csv(f"{DB_DIR}/sys_account.csv",  encoding="utf-8-sig"),
        "df_access":  pd.read_csv(f"{DB_DIR}/access_log.csv",   encoding="utf-8-sig"),
        "df_itsm":    pd.read_csv(f"{DB_DIR}/itsm_req.csv",     encoding="utf-8-sig"),
        "df_deploy":  pd.read_csv(f"{DB_DIR}/deploy_log.csv",   encoding="utf-8-sig"),
        "df_backup":  pd.read_csv(f"{DB_DIR}/backup_log.csv",   encoding="utf-8-sig"),
    }

    # datetime 변환 (날짜 비교에 필요)
    date_cols = {
        "df_emp":     ["hire_dt", "resign_dt"],
        "df_account": ["create_dt", "last_pw_change_dt", "last_review_dt"],
        "df_access":  ["access_dt"],
        "df_itsm":    ["request_dt", "approval_dt", "due_dt"],
        "df_deploy":  ["deploy_dt"],
        "df_backup":  ["backup_dt"],
    }
    for name, cols in date_cols.items():
        for col in cols:
            if col in dfs[name].columns:
                dfs[name][col] = pd.to_datetime(dfs[name][col], errors="coerce")

    for name, df in dfs.items():
        print(f"  {name}: {len(df):,}행")

    return dfs


# ── 2. 단일 규칙 실행 ─────────────────────────────────────────
def run_rule(rule: dict, dfs: dict) -> tuple[int, pd.DataFrame | None]:
    """
    규칙 하나를 실행해서 (위반건수, 위반상세 DataFrame) 반환

    pandas_logic은 rules.json에 저장된 파이썬 코드 문자열
    - 한 줄: eval()로 실행 (결과값 바로 반환)
    - 여러 줄: exec()로 실행 (마지막에 result 변수에 저장해야 함)
    """
    logic = rule.get("pandas_logic", "")
    if not logic:
        return 0, None

    # 대소문자 정규화: Claude가 생성한 코드의 대문자 값을 실제 데이터 소문자 값으로 보정
    logic = (logic
             .replace("'PRD'", "'prod'")
             .replace("'ACTIVE'", "'active'")
             .replace("'INACTIVE'", "'inactive'")
             .replace("'SUCCESS'", "'S'")
             .replace("'FAIL'", "'F'")
             .replace('"PRD"', '"prod"')
             .replace('"ACTIVE"', '"active"')
             .replace('"INACTIVE"', '"inactive"')
    )

    try:
        # eval/exec 실행 환경: 데이터프레임 + 표준 내장함수 모두 허용
        local_vars = {**dfs, "pd": pd, "datetime": datetime}
        global_vars = {"__builtins__": __builtins__}

        # 실행 방식 결정:
        # - 세미콜론(;) 또는 개행(\n) 또는 대입문(=)이 포함되면 exec()
        # - 순수 표현식이면 eval()
        stripped = logic.strip()

        # 세미콜론을 개행으로 변환 (한 줄 다중 구문 처리)
        if ";" in stripped:
            stripped = stripped.replace("; ", "\n").replace(";", "\n")

        # import 구문 제거 (pd, datetime 등 이미 주입됨)
        lines = [l for l in stripped.split("\n")
                 if not l.strip().startswith("import ")]
        stripped = "\n".join(lines)

        # 대입문 포함 여부: 괄호 밖의 '=' 존재 확인
        first_line = stripped.split("\n")[0].strip()
        has_assignment = (
            "\n" in stripped or
            ("=" in first_line and
             not first_line.startswith("df_") and
             "==" not in first_line.split("=")[0])
        )

        if has_assignment:
            # exec()로 실행: 마지막 줄을 result = ...로 감싸기
            exec_lines = stripped.split("\n")
            last = exec_lines[-1].strip()
            if last and not last.startswith("result") and "=" not in last.split("(")[0]:
                exec_lines[-1] = f"result = {last}"
            elif last and "=" in last and not last.startswith("result"):
                # 마지막 줄이 대입문이면 그 변수를 result로
                var_name = last.split("=")[0].strip()
                exec_lines.append(f"result = {var_name}")
            exec_code = "\n".join(exec_lines)
            exec(exec_code, global_vars, local_vars)
            result = local_vars.get("result", None)
        else:
            result = eval(stripped, global_vars, local_vars)

        # 결과 타입에 따라 처리
        if isinstance(result, pd.DataFrame):
            count = len(result)
            if count > 0:
                detail = result.copy().head(500)
                detail.insert(0, "rule_id",      rule.get("rule_id", ""))
                detail.insert(1, "rule_nm",      rule.get("rule_nm", ""))
                detail.insert(2, "audit_domain", rule.get("audit_domain", ""))
                detail.insert(3, "severity",     rule.get("severity", ""))
                return count, detail
            return 0, None

        elif isinstance(result, (int, float)):
            return int(result), None

        elif isinstance(result, pd.Series):
            count = int(result.sum()) if result.dtype == bool else len(result)
            return count, None

        else:
            return 0, None

    except Exception as e:
        return -1, None   # -1 = 실행 오류 (오류 규칙은 건수 0으로 처리)


# ── 3. 전체 규칙 실행 ─────────────────────────────────────────
def run_all_rules(rules: list[dict], dfs: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    모든 규칙을 순서대로 실행해서
    - summary_df : 규칙별 위반 건수 요약
    - detail_df  : 위반 건별 상세
    를 반환
    """
    summary_rows = []
    detail_dfs   = []

    print(f"\n총 {len(rules)}개 규칙 실행 시작...")
    print("-" * 60)

    for rule in rules:
        rule_id = rule.get("rule_id", "")
        rule_nm = rule.get("rule_nm", "")
        domain  = rule.get("audit_domain", "")
        severity = rule.get("severity", "")

        count, detail = run_rule(rule, dfs)

        # 실행 결과 표시
        if count == -1:
            status = "⚠ 오류"
            count_display = 0
        elif count == 0:
            status = "✓ 이상없음"
            count_display = 0
        else:
            status = f"❌ {count}건 위반"
            count_display = count

        print(f"  {rule_id} [{domain}] {rule_nm}")
        print(f"       → {status}")

        is_violated = count_display > 0
        sev_score   = SEVERITY_SCORE.get(severity, 0)
        summary_rows.append({
            "rule_id":        rule_id,
            "rule_nm":        rule_nm,
            "audit_domain":   domain,
            "severity":       severity,
            "severity_score": sev_score,
            "source_law":     rule.get("source_law", ""),
            "source_article": rule.get("source_article", ""),
            "check_target":   rule.get("check_target", ""),
            "condition_desc": rule.get("condition_desc", ""),
            "violation_count": count_display,
            "yn_violation":   "Y" if is_violated else "N",
            "risk_deduction": sev_score if is_violated else 0,
            "remediation":    rule.get("remediation", ""),
        })

        if detail is not None and len(detail) > 0:
            detail_dfs.append(detail)

    summary_df = pd.DataFrame(summary_rows)
    detail_df  = pd.concat(detail_dfs, ignore_index=True) if detail_dfs else pd.DataFrame()

    return summary_df, detail_df


# ── 4. 결과 출력 ──────────────────────────────────────────────
def print_report(summary_df: pd.DataFrame):
    """콘솔에 점검 결과 요약 출력"""
    print("\n" + "=" * 60)
    print("IT감사 Rule 엔진 점검 결과")
    print("=" * 60)

    total     = len(summary_df)
    violated  = (summary_df["yn_violation"] == "Y").sum()
    clean     = total - violated

    print(f"\n총 점검 규칙 : {total}개")
    print(f"위반 탐지   : {violated}개 규칙")
    print(f"이상 없음   : {clean}개 규칙")

    print(f"\n[도메인별 위반 현황]")
    domain_summary = summary_df.groupby("audit_domain").agg(
        전체=("rule_id", "count"),
        위반=("yn_violation", lambda x: (x == "Y").sum()),
        총위반건수=("violation_count", "sum")
    ).reset_index()
    print(domain_summary.to_string(index=False))

    print(f"\n[심각도별 HIGH 위반 규칙]")
    high_violated = summary_df[
        (summary_df["severity"] == "HIGH") &
        (summary_df["yn_violation"] == "Y")
    ][["rule_id", "rule_nm", "audit_domain", "violation_count"]]
    if len(high_violated) > 0:
        print(high_violated.to_string(index=False))
    else:
        print("  없음")

    print(f"\n[위반 건수 TOP 10]")
    top10 = summary_df[summary_df["violation_count"] > 0].nlargest(10, "violation_count")
    print(top10[["rule_id", "rule_nm", "audit_domain", "severity", "violation_count"]].to_string(index=False))


# ── 월별 필터링 ───────────────────────────────────────────────
def filter_by_month(dfs: dict, month: str) -> dict:
    """
    month: 'YYYY-MM' 형식
    날짜 컬럼이 있는 테이블을 해당 월 데이터만 남김
    emp_master / sys_account는 스냅샷이므로 필터 없이 전체 사용
    """
    year, mon = map(int, month.split("-"))
    date_col_map = {
        "df_access": "access_dt",
        "df_deploy": "deploy_dt",
        "df_backup": "backup_dt",
        "df_itsm":   "request_dt",
    }
    filtered = dict(dfs)
    for key, col in date_col_map.items():
        df = dfs[key]
        if col in df.columns:
            filtered[key] = df[
                (df[col].dt.year == year) & (df[col].dt.month == mon)
            ].copy()
            print(f"  {key} [{month}]: {len(filtered[key]):,}행 (전체 {len(df):,}행)")
    return filtered


# ── 메인 실행 ────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", type=str, default=None,
                        help="분석 대상 월 (YYYY-MM). 미입력 시 전체 기간")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    label = f"IT감사 Rule 엔진 시작 [{args.month or '전체 기간'}]"
    print(label)
    print("=" * 60)

    # 1. 데이터 로드
    dfs = load_data()

    # 2. 월 필터링
    if args.month:
        print(f"\n[월 필터링] {args.month}")
        dfs = filter_by_month(dfs, args.month)

    # 3. rules.json 로드
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)
    print(f"\nrules.json 로드 완료: {len(rules)}개 규칙")

    # 4. 전체 규칙 실행
    summary_df, detail_df = run_all_rules(rules, dfs)

    # 5. 결과 출력
    print_report(summary_df)

    # 6. 저장 (월 지정 시 별도 파일)
    if args.month:
        summary_path = os.path.join(OUT_DIR, f"violations_summary_{args.month}.csv")
    else:
        summary_path = os.path.join(OUT_DIR, "violations_summary.csv")
    detail_path = os.path.join(OUT_DIR, "violations_detail.csv")

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"\n요약 저장 완료 → {summary_path}")

    if len(detail_df) > 0:
        detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")
        print(f"상세 저장 완료 → {detail_path} ({len(detail_df):,}건)")
    else:
        print("상세 데이터 없음 (pandas_logic이 DataFrame을 반환하지 않는 규칙)")

    print("\nRule 엔진 실행 완료!")

    print("\nRule 엔진 실행 완료!")
