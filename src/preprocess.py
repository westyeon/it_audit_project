"""
가상 DB 파생 컬럼 생성 (전처리)
- access_log  : yn_after_hours, yn_post_resign_access
- sys_account : review_elapsed_days, yn_overdue_review
- deploy_log  : yn_post_approval, yn_job_sep_violation, yn_no_cr

입력:  data/raw/virtual_db/*.csv
출력:  data/processed/virtual_db/*.csv  (파생 컬럼 추가된 버전)
"""

import os
import pandas as pd
from datetime import datetime

RAW_DIR  = "data/raw/virtual_db"
OUT_DIR  = "data/processed/virtual_db"
BASE_DT  = datetime(2026, 4, 30)   # 분석 기준일 (로그 수집 종료일)
REVIEW_THRESHOLD_DAYS = 180         # 권한검토 주기 기준 (6개월)
AFTER_HOURS_START     = 22          # 업무시간 외 시작 시각 (22시)
AFTER_HOURS_END       = 6           # 업무시간 외 종료 시각 (06시)


def load_tables() -> dict:
    """가상 DB CSV 전체 로드"""
    dfs = {}
    for fname in ["emp_master", "sys_account", "access_log",
                  "itsm_req", "deploy_log", "backup_log"]:
        path = f"{RAW_DIR}/{fname}.csv"
        dfs[fname] = pd.read_csv(path, encoding="utf-8-sig")
    return dfs


def preprocess_access_log(df_access: pd.DataFrame,
                           df_emp: pd.DataFrame,
                           df_account: pd.DataFrame) -> pd.DataFrame:
    """
    access_log 파생 컬럼:
    - yn_after_hours         : 22:00~06:00 접속 여부 (Y/N)
    - yn_post_resign_access  : 퇴직자 활성계정으로 퇴사일 이후 접속 여부 (Y/N)
    """
    df = df_access.copy()
    df["access_dt"] = pd.to_datetime(df["access_dt"])

    # 업무시간 외 여부
    hour = df["access_dt"].dt.hour
    df["yn_after_hours"] = (
        (hour >= AFTER_HOURS_START) | (hour < AFTER_HOURS_END)
    ).map({True: "Y", False: "N"})

    # 퇴사 후 접속 여부:
    # 퇴직자(yn_employed=N) 중 활성 계정(account_status=active)을 가진 emp_id만 대상
    resigned_ids = set(df_emp[df_emp["yn_employed"] == "N"]["emp_id"])
    active_resigned_ids = set(
        df_account[
            df_account["emp_id"].isin(resigned_ids) &
            (df_account["account_status"] == "active")
        ]["emp_id"]
    )

    resign_map = df_emp.set_index("emp_id")["resign_dt"]
    df["resign_dt_emp"] = df["emp_id"].map(resign_map)
    df["resign_dt_emp"] = pd.to_datetime(df["resign_dt_emp"], errors="coerce")

    df["yn_post_resign_access"] = (
        df["emp_id"].isin(active_resigned_ids) &
        df["resign_dt_emp"].notna() &
        (df["access_dt"] > df["resign_dt_emp"])
    ).map({True: "Y", False: "N"})

    df.drop(columns=["resign_dt_emp"], inplace=True)
    return df


def preprocess_sys_account(df_account: pd.DataFrame) -> pd.DataFrame:
    """
    sys_account 파생 컬럼:
    - review_elapsed_days : 마지막 권한검토일로부터 경과일수 (int)
    - yn_overdue_review   : 180일 초과 여부 (Y/N)
    """
    df = df_account.copy()
    df["last_review_dt"] = pd.to_datetime(df["last_review_dt"], errors="coerce")

    df["review_elapsed_days"] = (BASE_DT - df["last_review_dt"]).dt.days
    df["review_elapsed_days"] = df["review_elapsed_days"].fillna(999).astype(int)

    df["yn_overdue_review"] = (
        df["review_elapsed_days"] > REVIEW_THRESHOLD_DAYS
    ).map({True: "Y", False: "N"})

    return df


def preprocess_deploy_log(df_deploy: pd.DataFrame,
                           df_itsm: pd.DataFrame) -> pd.DataFrame:
    """
    deploy_log + itsm_req JOIN 파생 컬럼:
    - yn_no_cr             : CR 없는 무단배포 (doc_no IS NULL) (Y/N)
    - yn_post_approval     : 사후승인 (deploy_dt < approval_dt) (Y/N)
    - yn_job_sep_violation : 직무분리 위반 (신청자 == 배포자) (Y/N)
    """
    df = df_deploy.copy()
    df["deploy_dt"] = pd.to_datetime(df["deploy_dt"])

    # CR 없는 무단배포
    df["yn_no_cr"] = df["doc_no"].isna().map({True: "Y", False: "N"})

    # ITSM 정보 JOIN (doc_no 기준)
    itsm_sub = df_itsm[["doc_no", "approval_dt", "requester_id"]].copy()
    itsm_sub["approval_dt"] = pd.to_datetime(itsm_sub["approval_dt"], errors="coerce")

    df = df.merge(itsm_sub, on="doc_no", how="left")

    # 사후승인: 배포일이 결재일보다 이전 (결재 전에 먼저 배포)
    df["yn_post_approval"] = (
        df["approval_dt"].notna() &
        (df["deploy_dt"] < df["approval_dt"])
    ).map({True: "Y", False: "N"})

    # 직무분리 위반: 신청자 == 배포자
    df["yn_job_sep_violation"] = (
        df["requester_id"].notna() &
        (df["deployer_id"] == df["requester_id"])
    ).map({True: "Y", False: "N"})

    # 불필요 컬럼 제거
    df.drop(columns=["approval_dt", "requester_id"], inplace=True)

    return df


def print_violation_summary(dfs_out: dict):
    """파생 컬럼 기반 위반 현황 요약 출력"""
    print("\n" + "=" * 60)
    print("파생 컬럼 위반 현황 요약")
    print("=" * 60)

    access = dfs_out["access_log"]
    account = dfs_out["sys_account"]
    deploy = dfs_out["deploy_log"]

    print(f"\n[접근통제]")
    print(f"  업무시간 외 접속          : {(access['yn_after_hours']=='Y').sum():>6,}건")
    print(f"  퇴사 후 접속              : {(access['yn_post_resign_access']=='Y').sum():>6,}건")
    print(f"  권한검토 180일 초과 계정   : {(account['yn_overdue_review']=='Y').sum():>6,}건")

    print(f"\n[변경관리]")
    print(f"  CR 없는 무단배포          : {(deploy['yn_no_cr']=='Y').sum():>6,}건")
    print(f"  사후승인 배포             : {(deploy['yn_post_approval']=='Y').sum():>6,}건")
    print(f"  직무분리 위반             : {(deploy['yn_job_sep_violation']=='Y').sum():>6,}건")

    # 퇴직자 활성 계정 (account_status는 소문자 'active')
    emp = dfs_out["emp_master"]
    resigned_ids = emp[emp["yn_employed"] == "N"]["emp_id"].tolist()
    active_resigned = account[
        account["emp_id"].isin(resigned_ids) &
        (account["account_status"] == "active")
    ]
    print(f"\n[계정관리]")
    print(f"  퇴직자 활성 계정          : {len(active_resigned):>6,}건")

    # 백업 실패 / 복구테스트 미실시 (backup_status: 'S'=성공, 'F'=실패)
    backup = dfs_out["backup_log"]
    print(f"\n[운영통제]")
    print(f"  백업 실패                 : {(backup['backup_status']=='F').sum():>6,}건")
    print(f"  복구테스트 미실시         : {(backup['yn_restore_test']=='N').sum():>6,}건")


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(BASE_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("파생 컬럼 생성 시작")
    print("=" * 60)

    # 원본 로드
    dfs = load_tables()
    print(f"원본 테이블 로드 완료:")
    for nm, df in dfs.items():
        print(f"  {nm}: {len(df):,}행")

    # 파생 컬럼 추가
    print("\n파생 컬럼 생성 중...")
    dfs["access_log"]  = preprocess_access_log(dfs["access_log"], dfs["emp_master"], dfs["sys_account"])
    dfs["sys_account"] = preprocess_sys_account(dfs["sys_account"])
    dfs["deploy_log"]  = preprocess_deploy_log(dfs["deploy_log"], dfs["itsm_req"])
    print("완료!")

    # 위반 현황 요약
    print_violation_summary(dfs)

    # 저장 (모든 테이블 저장 - 파생 컬럼 없는 테이블도 포함)
    print(f"\n데이터 저장 중 → {OUT_DIR}/")
    for nm, df in dfs.items():
        out_path = f"{OUT_DIR}/{nm}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"  {nm}.csv 저장 완료 ({len(df):,}행)")

    print(f"\n전처리 완료!")
    print(f"출력 디렉토리: {OUT_DIR}")
