"""
가상 DB 생성 스크립트
- 금융권 중견사 기준 (직원 500명)
- 생성 테이블: emp_master, sys_account, access_log, itsm_req, deploy_log, backup_log
- 위반 데이터 의도적으로 삽입 (Rule 엔진 검증용)
"""

import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta, date
import os

fake = Faker('ko_KR')
random.seed(42)
np.random.seed(42)

OUTPUT_DIR = "data/raw/virtual_db"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ══════════════════════════════════════════════
# 공통 설정
# ══════════════════════════════════════════════
TOTAL_EMP      = 500
RESIGNED_COUNT = 80   # 퇴사자 수 (전체의 16%)

SYSTEMS = {
    'CORE':  '핵심뱅킹시스템',
    'IBANK': '인터넷뱅킹',
    'ADMIN': '내부관리시스템',
    'INFO':  '정보계시스템',
    'DEVP':  '개발포털',
}

# (부서코드, 부서명, role_type, 인원비중)
DEPARTMENTS = [
    ('D001', 'IT개발1팀',    'developer', 45),
    ('D002', 'IT개발2팀',    'developer', 40),
    ('D003', 'IT운영팀',     'operator',  30),
    ('D004', '정보보안팀',   'security',  20),
    ('D005', '영업1팀',      'business',  45),
    ('D006', '영업2팀',      'business',  45),
    ('D007', '리스크관리팀', 'business',  40),
    ('D008', '경영지원팀',   'business',  35),
    ('D009', '심사팀',       'business',  40),
    ('D010', '준법감시팀',   'business',  25),
    ('D011', '기획팀',       'business',  30),
    ('D012', '고객서비스팀', 'business',  40),
    ('D013', '자산운용팀',   'business',  35),
    ('D014', '트레이딩팀',   'business',  30),
]

JOB_GRADES      = ['사원', '대리', '과장', '차장', '부장']
GRADE_WEIGHTS   = [0.20,   0.25,   0.25,   0.20,   0.10]
POSITION_BY_GRADE = {
    '사원': '일반', '대리': '일반', '과장': '일반',
    '차장': '파트장', '부장': '팀장'
}

# 입사년도 분포 (2015~2024, 합계 500)
HIRE_YEARS         = list(range(2015, 2025))
HIRE_YEAR_COUNTS   = [30, 40, 50, 55, 60, 55, 60, 55, 55, 40]

# 로그 기간 (6개월)
LOG_START = datetime(2024, 11, 1)
LOG_END   = datetime(2025,  4, 30)

# ══════════════════════════════════════════════
# 위반 건수 설정 (Rule 엔진 검증 기준값)
# ══════════════════════════════════════════════
V = {
    'resigned_active_accounts': 15,   # 퇴직자인데 계정 active
    'overdue_review_accounts':  30,   # 권한검토 6개월 초과
    'excess_permission':        10,   # business 직무에 admin 권한
    'after_hours_accounts':     15,   # 업무시간 외 접속 계정 수
    'multi_ip_accounts':        10,   # 동시간대 다중 IP 계정 수
    'post_approval_deploy':     20,   # 사후 승인 (배포일 < 결재일)
    'no_cr_deploy':             15,   # CR 없는 무단 배포
    'job_sep_violation':        15,   # 신청자 = 배포자 (직무분리 위반)
    'backup_fail':              20,   # 백업 실패
    'no_restore_test':          40,   # full backup 중 복구 테스트 미실시
}

# ══════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════
def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def rand_dt(start: datetime, end: datetime) -> datetime:
    delta = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, delta))

def business_hours_dt(base_date: date) -> datetime:
    """업무시간(09:00~18:00) 내 랜덤 datetime"""
    h = random.randint(9, 17)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return datetime(base_date.year, base_date.month, base_date.day, h, m, s)

def after_hours_dt(base_date: date) -> datetime:
    """업무시간 외(22:00~06:00) 랜덤 datetime"""
    h = random.choice(list(range(22, 24)) + list(range(0, 7)))
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return datetime(base_date.year, base_date.month, base_date.day, h, m, s)

def random_ip(internal=True) -> str:
    if internal:
        return f"192.168.{random.randint(1,10)}.{random.randint(1,254)}"
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

# ══════════════════════════════════════════════
# 1. emp_master
# ══════════════════════════════════════════════
def gen_emp_master() -> pd.DataFrame:
    print("  emp_master 생성 중...")

    # emp_id: 10000~30000 중 500개 랜덤 비복원추출
    emp_ids = sorted(random.sample(range(10000, 30001), TOTAL_EMP))

    # 부서 배정
    dept_pool = []
    for dept_cd, dept_nm, role, count in DEPARTMENTS:
        dept_pool.extend([(dept_cd, dept_nm, role)] * count)
    random.shuffle(dept_pool)
    dept_pool = dept_pool[:TOTAL_EMP]

    # 입사년도 배정
    hire_year_pool = []
    for yr, cnt in zip(HIRE_YEARS, HIRE_YEAR_COUNTS):
        hire_year_pool.extend([yr] * cnt)
    random.shuffle(hire_year_pool)

    # 연도별 emp_no 순번 관리
    year_seq = {yr: 1 for yr in HIRE_YEARS}

    rows = []
    for i, emp_id in enumerate(emp_ids):
        dept_cd, dept_nm, role_type = dept_pool[i]
        hire_year = hire_year_pool[i]

        # emp_no: A + 2자리연도 + 4자리순번
        seq = year_seq[hire_year]
        emp_no = f"A{str(hire_year)[2:]}{seq:04d}"
        year_seq[hire_year] += 1

        # 입사일: 해당 연도 내 랜덤
        hire_dt = rand_date(date(hire_year, 1, 1), date(hire_year, 12, 31))

        # 직급
        job_grade = random.choices(JOB_GRADES, weights=GRADE_WEIGHTS)[0]
        position_nm = POSITION_BY_GRADE[job_grade]

        rows.append({
            'emp_id':      emp_id,
            'emp_no':      emp_no,
            'emp_nm':      fake.name(),
            'dept_cd':     dept_cd,
            'dept_nm':     dept_nm,
            'job_grade':   job_grade,
            'position_nm': position_nm,
            'role_type':   role_type,
            'hire_dt':     hire_dt,
            'resign_dt':   '',
            'yn_employed': 'Y',
            'emp_email':   f"{emp_id}@company.com",
        })

    df = pd.DataFrame(rows)

    # 퇴사자 80명 설정 (입사 1년 이상 된 직원 중 랜덤)
    eligible = df[df['hire_dt'] <= date(2023, 12, 31)].index.tolist()
    resigned_idx = random.sample(eligible, RESIGNED_COUNT)
    for idx in resigned_idx:
        hire = df.at[idx, 'hire_dt']
        resign = rand_date(
            max(hire + timedelta(days=365), date(2022, 1, 1)),
            date(2025, 3, 31)
        )
        df.at[idx, 'resign_dt']   = resign
        df.at[idx, 'yn_employed'] = 'N'

    df = df.sort_values('emp_id').reset_index(drop=True)
    df.to_csv(f"{OUTPUT_DIR}/emp_master.csv", index=False, encoding='utf-8-sig')
    print(f"    → {len(df)}명 생성 (퇴사자 {RESIGNED_COUNT}명 포함)")
    return df


# ══════════════════════════════════════════════
# 2. sys_account
# ══════════════════════════════════════════════
def gen_sys_account(emp_df: pd.DataFrame) -> pd.DataFrame:
    print("  sys_account 생성 중...")

    # role별 접근 가능 시스템
    ROLE_SYSTEMS = {
        'developer': ['CORE', 'DEVP', 'INFO'],
        'operator':  ['CORE', 'IBANK', 'ADMIN', 'INFO', 'DEVP'],
        'security':  ['CORE', 'ADMIN', 'INFO'],
        'business':  ['IBANK', 'ADMIN'],
    }

    rows = []
    seq = 1000

    for _, emp in emp_df.iterrows():
        systems = ROLE_SYSTEMS[emp['role_type']]
        for sys_cd in systems:
            # 계정 생성일 = 입사일 + 영업일 3~5일
            create_dt = emp['hire_dt'] + timedelta(days=random.randint(3, 7))

            # 권한 검토일: 최근 1~5개월 내 랜덤 (정상 케이스 → 180일 미초과)
            review_dt = rand_date(date(2024, 12, 1), date(2025, 4, 15))

            # 계정 상태: 퇴사자는 기본 inactive (위반 케이스는 나중에 덮어씀)
            if emp['yn_employed'] == 'N':
                status = 'inactive'
            else:
                status = 'active'

            # 일반 권한: developer/operator는 write, business는 read
            if emp['role_type'] in ('developer', 'operator', 'security'):
                perm = random.choice(['write', 'write', 'read'])
            else:
                perm = 'read'

            rows.append({
                'account_seq':      seq,
                'emp_id':           emp['emp_id'],
                'system_cd':        sys_cd,
                'system_nm':        SYSTEMS[sys_cd],
                'login_id':         str(emp['emp_id']),
                'account_type':     'general',
                'account_status':   status,
                'permission_level': perm,
                'create_dt':        create_dt,
                'last_pw_change_dt': rand_date(date(2024, 1, 1), date(2025, 4, 30)),
                'last_review_dt':   review_dt,
            })
            seq += 1

    df = pd.DataFrame(rows)

    # ── 위반 삽입 ──────────────────────────────
    # (1) 퇴직자 계정 미비활성화: 퇴사자 중 15개 계정을 active로
    resigned_ids = emp_df[emp_df['yn_employed'] == 'N']['emp_id'].tolist()
    v1_targets = df[df['emp_id'].isin(resigned_ids)].sample(
        n=V['resigned_active_accounts'], random_state=42).index
    df.loc[v1_targets, 'account_status'] = 'active'

    # (2) 권한검토 6개월 초과: last_review_dt를 2024-04-30 이전으로 설정
    active_idx = df[df['account_status'] == 'active'].sample(
        n=V['overdue_review_accounts'], random_state=42).index
    df.loc[active_idx, 'last_review_dt'] = [
        rand_date(date(2023, 1, 1), date(2024, 4, 30))
        for _ in range(V['overdue_review_accounts'])
    ]

    # (3) business 직무 임직원에게 admin 권한 부여
    biz_ids = emp_df[emp_df['role_type'] == 'business']['emp_id'].tolist()
    v3_idx = df[df['emp_id'].isin(biz_ids)].sample(
        n=V['excess_permission'], random_state=42).index
    df.loc[v3_idx, 'permission_level'] = 'admin'
    df.loc[v3_idx, 'account_type']     = 'admin'

    df.to_csv(f"{OUTPUT_DIR}/sys_account.csv", index=False, encoding='utf-8-sig')
    print(f"    → {len(df)}개 계정 생성")
    return df


# ══════════════════════════════════════════════
# 3. access_log
# ══════════════════════════════════════════════
def gen_access_log(emp_df: pd.DataFrame, acc_df: pd.DataFrame) -> pd.DataFrame:
    print("  access_log 생성 중 (약 10만 건)...")

    ACTION_TYPES = ['LOGIN', 'QUERY', 'UPDATE', 'EXPORT']
    ACTION_W     = [0.35,    0.40,    0.20,    0.05]

    active_accounts = acc_df[acc_df['account_status'] == 'active'].copy()
    rows = []
    log_seq = 1

    # ── 정상 로그: 업무일 기준 생성 ──────────────
    current = LOG_START
    while current <= LOG_END:
        # 주말 제외
        if current.weekday() < 5:
            # 당일 활성 계정 중 70% 랜덤 접속
            day_accounts = active_accounts.sample(frac=0.70, random_state=current.day)
            for _, acc in day_accounts.iterrows():
                n_actions = random.randint(2, 5)
                for _ in range(n_actions):
                    rows.append({
                        'log_seq':     log_seq,
                        'emp_id':      acc['emp_id'],
                        'system_cd':   acc['system_cd'],
                        'access_dt':   business_hours_dt(current.date()),
                        'action_type': random.choices(ACTION_TYPES, weights=ACTION_W)[0],
                        'src_ip':      random_ip(internal=True),
                        'result_cd':   random.choices(['S', 'F'], weights=[0.97, 0.03])[0],
                    })
                    log_seq += 1
        current += timedelta(days=1)

    df = pd.DataFrame(rows)

    # ── 위반 삽입 ──────────────────────────────
    # (1) 업무시간 외 접속: 특정 15개 계정에서 야간 접속 로그 삽입
    after_targets = active_accounts.sample(
        n=V['after_hours_accounts'], random_state=7)
    for _, acc in after_targets.iterrows():
        for _ in range(random.randint(3, 8)):
            rd = rand_date(LOG_START.date(), LOG_END.date())
            rows.append({
                'log_seq':     log_seq,
                'emp_id':      acc['emp_id'],
                'system_cd':   acc['system_cd'],
                'access_dt':   after_hours_dt(rd),
                'action_type': random.choice(['QUERY', 'UPDATE', 'EXPORT']),
                'src_ip':      random_ip(internal=True),
                'result_cd':   'S',
            })
            log_seq += 1

    # (2) 다중 IP 접속 (동일 계정, 동일 1시간 내, 다른 IP 2개 이상)
    multi_targets = active_accounts.sample(
        n=V['multi_ip_accounts'], random_state=13)
    for _, acc in multi_targets.iterrows():
        base_dt = rand_dt(LOG_START, LOG_END - timedelta(hours=1))
        for _ in range(random.randint(2, 4)):
            rows.append({
                'log_seq':     log_seq,
                'emp_id':      acc['emp_id'],
                'system_cd':   acc['system_cd'],
                'access_dt':   base_dt + timedelta(minutes=random.randint(1, 50)),
                'action_type': 'LOGIN',
                'src_ip':      random_ip(internal=True),
                'result_cd':   'S',
            })
            log_seq += 1

    # (3) 퇴직자 계정(active 상태 위반 계정)에서 퇴사 후 접속 이력
    resigned_active = acc_df[
        (acc_df['account_status'] == 'active') &
        (acc_df['emp_id'].isin(emp_df[emp_df['yn_employed'] == 'N']['emp_id']))
    ]
    for _, acc in resigned_active.iterrows():
        resign_dt = emp_df[emp_df['emp_id'] == acc['emp_id']]['resign_dt'].values[0]
        if resign_dt and resign_dt != '':
            try:
                resign_date = pd.to_datetime(resign_dt).date()
                if resign_date < LOG_END.date():
                    access_after = rand_date(
                        max(resign_date + timedelta(days=1), LOG_START.date()),
                        LOG_END.date()
                    )
                    rows.append({
                        'log_seq':     log_seq,
                        'emp_id':      acc['emp_id'],
                        'system_cd':   acc['system_cd'],
                        'access_dt':   business_hours_dt(access_after),
                        'action_type': 'LOGIN',
                        'src_ip':      random_ip(internal=True),
                        'result_cd':   'S',
                    })
                    log_seq += 1
            except:
                pass

    df = pd.DataFrame(rows).sort_values('access_dt').reset_index(drop=True)
    df['log_seq'] = range(1, len(df) + 1)
    df.to_csv(f"{OUTPUT_DIR}/access_log.csv", index=False, encoding='utf-8-sig')
    print(f"    → {len(df):,}건 생성")
    return df


# ══════════════════════════════════════════════
# 4. itsm_req
# ══════════════════════════════════════════════
def gen_itsm_req(emp_df: pd.DataFrame) -> pd.DataFrame:
    print("  itsm_req 생성 중...")

    dev_ids  = emp_df[emp_df['role_type'] == 'developer']['emp_id'].tolist()
    ops_ids  = emp_df[emp_df['role_type'] == 'operator']['emp_id'].tolist()
    lead_ids = emp_df[emp_df['job_grade'].isin(['차장', '부장'])]['emp_id'].tolist()

    REQ_TYPES   = ['DEV', 'DML', 'DDL', 'AUTH', 'EMER']
    REQ_WEIGHTS = [0.45,  0.25,  0.10,  0.10,   0.10]

    TITLES = {
        'DEV':  ['로그인 로직 개선', '이체 한도 조정', '수수료 계산 수정', 'UI 버그 수정',
                 '배치 스케줄 변경', 'API 연동 개발', '리포트 기능 추가', '세션 타임아웃 조정'],
        'DML':  ['계정 상태 일괄 업데이트', '잘못된 거래 데이터 수정', '테스트 데이터 삭제',
                 '마스터 코드 추가', '잔액 정합성 보정'],
        'DDL':  ['신규 테이블 생성', '컬럼 추가', '인덱스 추가', '테이블 파티셔닝'],
        'AUTH': ['운영 DB 읽기 권한 부여', '관리자 계정 생성', '배치 계정 권한 추가',
                 '임시 접근 권한 부여'],
        'EMER': ['긴급 핫픽스 배포', '장애 대응 패치', '긴급 데이터 보정'],
    }

    rows = []
    doc_seq = 1

    # 6개월간 주 5~8건 생성
    current = LOG_START
    while current <= LOG_END:
        if current.weekday() == 0:  # 월요일마다 해당 주 CR 생성
            n_cr = random.randint(5, 8)
            for _ in range(n_cr):
                req_type = random.choices(REQ_TYPES, weights=REQ_WEIGHTS)[0]
                requester_id = random.choice(dev_ids + ops_ids)
                approver_id  = random.choice(lead_ids)
                sys_cd       = random.choice(list(SYSTEMS.keys()))

                request_dt = rand_dt(
                    datetime.combine(current.date(), datetime.min.time()) + timedelta(hours=9),
                    datetime.combine(current.date(), datetime.min.time()) + timedelta(days=4, hours=17)
                )
                approval_dt = request_dt + timedelta(hours=random.randint(4, 48))
                due_dt      = (request_dt + timedelta(days=random.randint(3, 14))).date()

                rows.append({
                    'doc_no':       f"ITSM-{request_dt.year}-{doc_seq:05d}",
                    'request_dt':   request_dt,
                    'approval_dt':  approval_dt,
                    'req_status':   'APPROVED',
                    'service_nm':   SYSTEMS[sys_cd],
                    'system_cd':    sys_cd,
                    'req_type':     req_type,
                    'title':        random.choice(TITLES[req_type]),
                    'due_dt':       due_dt,
                    'requester_id': requester_id,
                    'dev_lead_id':  random.choice(lead_ids),
                    'uat_lead_id':  random.choice(lead_ids),
                    'deployer_id':  random.choice(ops_ids),
                    'dml_lead_id':  random.choice(lead_ids) if req_type in ('DML', 'DDL') else '',
                })
                doc_seq += 1
        current += timedelta(days=1)

    # 미결재/반려 건 추가
    for _ in range(15):
        req_type     = random.choices(REQ_TYPES, weights=REQ_WEIGHTS)[0]
        requester_id = random.choice(dev_ids)
        request_dt   = rand_dt(LOG_START, LOG_END)
        sys_cd       = random.choice(list(SYSTEMS.keys()))
        rows.append({
            'doc_no':       f"ITSM-{request_dt.year}-{doc_seq:05d}",
            'request_dt':   request_dt,
            'approval_dt':  '',
            'req_status':   random.choice(['REVIEW', 'REJECTED', 'DRAFT']),
            'service_nm':   SYSTEMS[sys_cd],
            'system_cd':    sys_cd,
            'req_type':     req_type,
            'title':        random.choice(TITLES[req_type]),
            'due_dt':       (request_dt + timedelta(days=7)).date(),
            'requester_id': requester_id,
            'dev_lead_id':  random.choice(lead_ids),
            'uat_lead_id':  random.choice(lead_ids),
            'deployer_id':  random.choice(ops_ids),
            'dml_lead_id':  '',
        })
        doc_seq += 1

    df = pd.DataFrame(rows).sort_values('request_dt').reset_index(drop=True)
    df.to_csv(f"{OUTPUT_DIR}/itsm_req.csv", index=False, encoding='utf-8-sig')
    print(f"    → {len(df)}건 생성")
    return df


# ══════════════════════════════════════════════
# 5. deploy_log
# ══════════════════════════════════════════════
def gen_deploy_log(emp_df: pd.DataFrame, itsm_df: pd.DataFrame) -> pd.DataFrame:
    print("  deploy_log 생성 중...")

    ops_ids = emp_df[emp_df['role_type'] == 'operator']['emp_id'].tolist()
    dev_ids = emp_df[emp_df['role_type'] == 'developer']['emp_id'].tolist()

    approved = itsm_df[itsm_df['req_status'] == 'APPROVED'].copy()

    COMMIT_PATHS = [
        '/src/banking/transfer.py', '/src/auth/login.py',
        '/src/batch/settle.py',     '/src/api/account.py',
        '/src/report/daily.py',     '/src/admin/user.py',
        '/sql/proc_transfer.sql',   '/sql/update_balance.sql',
        '/config/app.properties',   '/src/common/util.py',
    ]

    rows = []
    dep_seq = 1

    for _, cr in approved.iterrows():
        if not cr['approval_dt']:
            continue
        approval_dt = pd.to_datetime(cr['approval_dt'])
        # 정상: 승인 후 1~5일 내 배포
        deploy_dt = approval_dt + timedelta(hours=random.randint(2, 120))

        rows.append({
            'deploy_seq':  dep_seq,
            'doc_no':      cr['doc_no'],
            'deployer_id': cr['deployer_id'],
            'system_cd':   cr['system_cd'],
            'deploy_dt':   deploy_dt,
            'commit_path': random.choice(COMMIT_PATHS),
            'env_type':    'prod',
            'yn_emergency': 'Y' if cr['req_type'] == 'EMER' else 'N',
        })
        dep_seq += 1

    df = pd.DataFrame(rows)

    # ── 위반 삽입 ──────────────────────────────
    # (1) 사후 승인: 배포일이 결재일보다 이전
    v1_idx = random.sample(range(len(df)), V['post_approval_deploy'])
    for idx in v1_idx:
        approval_dt = pd.to_datetime(itsm_df.loc[
            itsm_df['doc_no'] == df.at[idx, 'doc_no'], 'approval_dt'
        ].values[0])
        df.at[idx, 'deploy_dt'] = approval_dt - timedelta(hours=random.randint(1, 24))

    # (3) 직무분리 위반: 신청자 = 배포자  (no_cr 추가 전에 처리)
    v3_idx = random.sample(range(len(df)), V['job_sep_violation'])
    for idx in v3_idx:
        doc_no = df.at[idx, 'doc_no']
        requester = itsm_df.loc[itsm_df['doc_no'] == doc_no, 'requester_id'].values
        if len(requester) > 0:
            df.at[idx, 'deployer_id'] = requester[0]

    # (2) CR 없는 무단 배포  (violations to df are done → now extend with no-CR rows)
    no_cr_rows = []
    for _ in range(V['no_cr_deploy']):
        deploy_dt = rand_dt(LOG_START, LOG_END)
        no_cr_rows.append({
            'deploy_seq':  dep_seq,
            'doc_no':      None,
            'deployer_id': random.choice(dev_ids),  # 개발자가 직접 배포
            'system_cd':   random.choice(list(SYSTEMS.keys())),
            'deploy_dt':   deploy_dt,
            'commit_path': random.choice(COMMIT_PATHS),
            'env_type':    'prod',
            'yn_emergency': 'N',
        })
        dep_seq += 1

    df = pd.concat([df, pd.DataFrame(no_cr_rows)], ignore_index=True)
    df = df.sort_values('deploy_dt').reset_index(drop=True)
    df['deploy_seq'] = range(1, len(df) + 1)
    df.to_csv(f"{OUTPUT_DIR}/deploy_log.csv", index=False, encoding='utf-8-sig')
    print(f"    → {len(df)}건 생성")
    return df


# ══════════════════════════════════════════════
# 6. backup_log
# ══════════════════════════════════════════════
def gen_backup_log() -> pd.DataFrame:
    print("  backup_log 생성 중...")

    rows = []
    bk_seq = 1

    for sys_cd in SYSTEMS:
        current = LOG_START.date()
        while current <= LOG_END.date():
            # 매일 incremental, 매주 일요일 full
            if current.weekday() == 6:
                btype = 'full'
            else:
                btype = 'incremental'

            # 정상 성공 기본값
            status       = 'S'
            restore_test = 'N' if btype == 'full' else ''  # full만 복구테스트 대상

            rows.append({
                'backup_seq':       bk_seq,
                'system_cd':        sys_cd,
                'system_nm':        SYSTEMS[sys_cd],
                'backup_dt':        datetime.combine(current, datetime.min.time()).replace(hour=2, minute=random.randint(0, 59)),
                'backup_type':      btype,
                'backup_status':    status,
                'yn_restore_test':  restore_test,
                'file_size_gb':     round(random.uniform(5.0, 50.0) if btype == 'full' else random.uniform(0.5, 5.0), 2),
            })
            bk_seq += 1
            current += timedelta(days=1)

    df = pd.DataFrame(rows)

    # ── 위반 삽입 ──────────────────────────────
    # (1) 백업 실패
    v1_idx = random.sample(range(len(df)), V['backup_fail'])
    df.loc[v1_idx, 'backup_status'] = 'F'

    # (2) full backup 중 복구 테스트 미실시
    full_idx = df[df['backup_type'] == 'full'].index.tolist()
    v2_idx   = random.sample(full_idx, min(V['no_restore_test'], len(full_idx)))
    df.loc[v2_idx, 'yn_restore_test'] = 'N'
    # 나머지 full backup은 복구 테스트 완료
    remaining_full = [i for i in full_idx if i not in v2_idx]
    df.loc[remaining_full, 'yn_restore_test'] = 'Y'

    df.to_csv(f"{OUTPUT_DIR}/backup_log.csv", index=False, encoding='utf-8-sig')
    print(f"    → {len(df):,}건 생성")
    return df


# ══════════════════════════════════════════════
# 메인 실행
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  가상 DB 생성 시작")
    print("=" * 50)

    emp_df    = gen_emp_master()
    acc_df    = gen_sys_account(emp_df)
    log_df    = gen_access_log(emp_df, acc_df)
    itsm_df   = gen_itsm_req(emp_df)
    deploy_df = gen_deploy_log(emp_df, itsm_df)
    backup_df = gen_backup_log()

    print()
    print("=" * 50)
    print("  생성 완료 요약")
    print("=" * 50)
    print(f"  emp_master  : {len(emp_df):>7,}명")
    print(f"  sys_account : {len(acc_df):>7,}개")
    print(f"  access_log  : {len(log_df):>7,}건")
    print(f"  itsm_req    : {len(itsm_df):>7,}건")
    print(f"  deploy_log  : {len(deploy_df):>7,}건")
    print(f"  backup_log  : {len(backup_df):>7,}건")
    print()
    print("  ▶ 삽입된 위반 데이터 기준값")
    for k, v in V.items():
        print(f"    {k:<30}: {v}건")
    print(f"\n  저장 위치: {OUTPUT_DIR}/")
