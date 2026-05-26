"""
IT감사 자동화 시스템 - 전체 파이프라인 실행
사용법: python main.py [--skip-db] [--skip-rules] [--skip-report]

단계:
  1. 가상 DB 생성 (generate_virtual_db.py)
  2. 전처리 - 파생 컬럼 생성 (preprocess.py)
  3. Rule 엔진 실행 - 위반 탐지 (rule_engine.py)
  4. 보고서 생성 - Excel + Word (report_generator.py)

※ rule_converter.py (Rule JSON 생성)는 Claude API 비용이 발생하므로
  rules.json이 이미 있으면 자동 스킵됩니다.
  재생성하려면: python src/rule_converter.py 직접 실행
"""

import os
import sys
import time
import argparse
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR  = os.path.join(BASE_DIR, "src")
DATA_DIR = os.path.join(BASE_DIR, "data")


def run_step(name: str, script: str, step_num: int, total: int) -> bool:
    """단계 실행 후 성공 여부 반환"""
    print(f"\n{'='*60}")
    print(f"[{step_num}/{total}] {name}")
    print(f"{'='*60}")

    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        cwd=BASE_DIR,
        capture_output=False,
    )
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"\n  ✅ 완료 ({elapsed:.1f}초)")
        return True
    else:
        print(f"\n  ❌ 오류 발생 (returncode={result.returncode})")
        return False


def check_file(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 0


def main():
    parser = argparse.ArgumentParser(description="IT감사 자동화 시스템 전체 파이프라인")
    parser.add_argument("--skip-db",     action="store_true", help="가상 DB 생성 스킵 (이미 있을 때)")
    parser.add_argument("--skip-rules",  action="store_true", help="Rule 엔진 스킵")
    parser.add_argument("--skip-report", action="store_true", help="보고서 생성 스킵")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI 기반 금융권 IT감사 자동화 시스템")
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    total_start = time.time()
    results = {}
    step = 0
    total_steps = 4 - sum([args.skip_db, args.skip_rules, args.skip_report])
    # rule_converter는 자동 스킵 가능하므로 별도 처리

    # ── 1. 가상 DB 생성 ────────────────────────────────────────
    if args.skip_db:
        print("\n[가상 DB 생성] 스킵 (--skip-db)")
    else:
        step += 1
        db_exists = check_file(f"{DATA_DIR}/processed/virtual_db/emp_master.csv")
        if db_exists:
            print(f"\n[{step}/{total_steps}] 가상 DB 생성")
            print("  기존 가상 DB 발견 → 재생성하려면 Enter, 스킵하려면 s 입력: ", end="")
            try:
                ans = input().strip().lower()
            except EOFError:
                ans = "s"
            if ans == "s":
                print("  스킵")
                results["가상DB생성"] = True
            else:
                ok = run_step("가상 DB 생성", f"{SRC_DIR}/generate_virtual_db.py", step, total_steps)
                results["가상DB생성"] = ok
                if ok:
                    run_step("전처리 (파생컬럼)", f"{SRC_DIR}/preprocess.py", step, total_steps)
        else:
            ok = run_step("가상 DB 생성", f"{SRC_DIR}/generate_virtual_db.py", step, total_steps)
            results["가상DB생성"] = ok
            if ok:
                run_step("전처리 (파생컬럼)", f"{SRC_DIR}/preprocess.py", step, total_steps)

    # ── 2. Rule JSON 확인 (rule_converter는 비용 발생 → 자동 스킵) ──
    rules_path = f"{DATA_DIR}/processed/rules.json"
    if check_file(rules_path):
        print(f"\n[Rule JSON] rules.json 확인 ✅ (이미 존재, 스킵)")
    else:
        print(f"\n[Rule JSON] rules.json 없음 → rule_converter.py 실행 필요")
        print("  ANTHROPIC_API_KEY가 .env에 설정되어 있어야 합니다.")
        print("  실행: python src/rule_converter.py")
        sys.exit(1)

    # ── 3. Rule 엔진 실행 ──────────────────────────────────────
    if args.skip_rules:
        print("\n[Rule 엔진] 스킵 (--skip-rules)")
    else:
        step += 1
        ok = run_step("Rule 엔진 실행 (위반 탐지)", f"{SRC_DIR}/rule_engine.py", step, total_steps)
        results["Rule엔진"] = ok

    # ── 4. 보고서 생성 ─────────────────────────────────────────
    if args.skip_report:
        print("\n[보고서 생성] 스킵 (--skip-report)")
    else:
        summary_exists = check_file(f"{DATA_DIR}/processed/violations_summary.csv")
        if not summary_exists:
            print("\n❌ violations_summary.csv 없음 → Rule 엔진을 먼저 실행하세요.")
        else:
            step += 1
            ok = run_step("보고서 생성 (Excel + Word)", f"{SRC_DIR}/report_generator.py", step, total_steps)
            results["보고서생성"] = ok

    # ── 최종 결과 ──────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  파이프라인 완료 (총 {total_elapsed:.1f}초)")
    print(f"{'='*60}")

    for name, ok in results.items():
        status = "✅ 성공" if ok else "❌ 실패"
        print(f"  {name}: {status}")

    # 생성된 파일 목록
    report_dir = f"{DATA_DIR}/processed/report"
    if os.path.exists(report_dir):
        files = [f for f in os.listdir(report_dir) if f.startswith("IT감사보고서")]
        if files:
            print(f"\n  📄 생성된 보고서:")
            for f in sorted(files)[-2:]:  # 최신 2개
                print(f"     {report_dir}/{f}")

    summary_path = f"{DATA_DIR}/processed/violations_summary.csv"
    if os.path.exists(summary_path):
        import pandas as pd
        df = pd.read_csv(summary_path, encoding="utf-8-sig")
        violated = (df["yn_violation"] == "Y").sum()
        print(f"\n  📊 점검 결과: {len(df)}개 규칙 중 {violated}개 위반 탐지")

    print()


if __name__ == "__main__":
    main()
