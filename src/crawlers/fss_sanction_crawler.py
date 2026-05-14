"""
금융감독원 검사결과제재 공시 - IT 관련 제재 수집 크롤러
- data/raw/it_sanction_ids.json (수집된 203건 ID) 기반
- 각 제재건 상세 페이지에서 기관명/일자/부서/위반내용/PDF 파일명 수집
- data/raw/fss_sanctions_it.csv 저장
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import re

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
BASE = "https://www.fss.or.kr"
IDS_PATH  = "data/raw/it_sanction_ids.json"
OUT_PATH  = "data/raw/fss_sanctions_it.csv"


def parse_detail(exam_mgmt_no: str, em_open_seq: str) -> dict:
    url = (f"{BASE}/fss/job/openInfo/view.do"
           f"?menuNo=200476&examMgmtNo={exam_mgmt_no}&emOpenSeq={em_open_seq}")
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    content = soup.find("div", id="content")
    if not content:
        return {}

    # 기본 정보 추출 (dl/dt/dd 또는 테이블)
    result = {
        "examMgmtNo": exam_mgmt_no,
        "emOpenSeq":  em_open_seq,
        "금융기관명": "",
        "제재조치일": "",
        "관련부서":   "",
        "기관제재내용": "",
        "임원제재내용": "",
        "직원제재내용": "",
        "첨부파일명":  "",
        "첨부파일URL": "",
    }

    # 텍스트 기반 추출
    text = content.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for i, line in enumerate(lines):
        if line == "금융기관명" and i + 1 < len(lines):
            result["금융기관명"] = lines[i + 1]
        elif line == "제재조치일" and i + 1 < len(lines):
            result["제재조치일"] = lines[i + 1]
        elif line == "관련부서" and i + 1 < len(lines):
            result["관련부서"] = lines[i + 1]
        elif line == "기관 제재대상" and i + 1 < len(lines):
            result["기관제재내용"] = lines[i + 1]
        elif line == "임원 제재대상" and i + 1 < len(lines):
            result["임원제재내용"] = lines[i + 1]
        elif line == "직원 제재대상" and i + 1 < len(lines):
            result["직원제재내용"] = lines[i + 1]

    # 첨부파일 정보
    file_el = content.find("div", class_="file-list__set__item")
    if file_el:
        a = file_el.find("a", href=True)
        if a:
            result["첨부파일URL"] = BASE + a["href"]
            name_el = a.find("span", class_="name")
            result["첨부파일명"] = name_el.get_text(strip=True) if name_el else ""

    return result


if __name__ == "__main__":
    with open(IDS_PATH, "r", encoding="utf-8") as f:
        raw_ids = json.load(f)

    # key: "(기관명, 날짜)"  value: [examMgmtNo, emOpenSeq]
    id_list = list(raw_ids.values())
    print(f"총 {len(id_list)}건 수집 시작...")

    rows = []
    for i, (exam_no, seq) in enumerate(id_list, 1):
        try:
            row = parse_detail(exam_no, seq)
            if row:
                rows.append(row)
        except Exception as e:
            print(f"  [{i}] 오류 {exam_no}/{seq}: {e}")

        if i % 20 == 0:
            print(f"  {i}/{len(id_list)} 완료")
        time.sleep(0.3)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n총 {len(df)}건 저장 완료 → {OUT_PATH}")

    print("\n[관련부서별 현황]")
    print(df["관련부서"].value_counts().to_string())
    print("\n[연도별 현황]")
    df["연도"] = df["제재조치일"].astype(str).str[:4]
    print(df["연도"].value_counts().sort_index().to_string())
