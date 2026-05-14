"""
금융투자협회(KOFIA) IT감사 가이드라인 수집 크롤러
- 제1절 IT내부통제 기반사항        (historySeq=1694)
- 제2절 IT감사업무 수행단계별 준수사항 (historySeq=1695)

출처: https://law.kofia.or.kr
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://law.kofia.or.kr"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# 수집 대상 섹션 정의
SECTIONS = [
    {"history_seq": 1694, "section_name": "제1절 IT내부통제 기반사항"},
    {"history_seq": 1695, "section_name": "제2절 IT감사업무 수행단계별 준수사항"},
]

SEQ = 374  # IT감사 가이드라인 문서 번호


def fetch_section_content(seq: int, history_seq: int) -> BeautifulSoup:
    url = f"{BASE_URL}/service/law/lawFullScreenContent.do?seq={seq}&historySeq={history_seq}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = "utf-8"
    return BeautifulSoup(r.text, "html.parser")


def parse_section(soup: BeautifulSoup, section_name: str) -> list[dict]:
    """조문 단위(JO div)별로 조문 번호 + 본문 텍스트 추출"""
    rows = []
    seq_num = 1

    # 절 제목 행 추가
    jo_divs = soup.find_all("div", class_="JO")

    if not jo_divs:
        # JO 구조가 없는 경우(2절처럼 체크리스트 형태) → 전체 텍스트를 단락 단위로 분리
        full_text = soup.get_text(separator="\n", strip=True)
        # 헤더(사이트명/날짜) 제거
        lines = full_text.split("\n")
        clean_lines = [l for l in lines if l and "금융투자협회 법규정보시스템" not in l and "제정 2025" not in l]
        content = "\n".join(clean_lines)
        rows.append({
            "출처": "금융투자협회 IT감사 가이드라인",
            "섹션": section_name,
            "순번": seq_num,
            "조문내용": content.strip()
        })
        return rows

    for div in jo_divs:
        # 조문 번호/제목
        article_header = div.find("div", class_="article")
        title_text = article_header.get_text(strip=True) if article_header else ""

        # 본문 텍스트 (항/호/목 포함 전체)
        body_parts = []
        for cls in ["none", "hang", "ho", "mok"]:
            for el in div.find_all("div", class_=cls):
                t = el.get_text(separator=" ", strip=True)
                if t:
                    body_parts.append(t)

        full_content = title_text
        if body_parts:
            full_content += " " + " ".join(body_parts)

        if full_content.strip():
            rows.append({
                "출처": "금융투자협회 IT감사 가이드라인",
                "섹션": section_name,
                "순번": seq_num,
                "조문내용": full_content.strip()
            })
            seq_num += 1

    return rows


def parse_section2_checklist(soup: BeautifulSoup, section_name: str) -> list[dict]:
    """
    제2절은 체크리스트(Ⅰ.계획단계, Ⅱ.수행단계, Ⅲ.종료단계) 형태 → 항목별로 분리
    """
    rows = []
    seq_num = 1

    # 본문 전체 텍스트 정리
    raw = soup.get_text(separator="\n", strip=True)
    lines = raw.split("\n")

    # 헤더 제거
    skip_keywords = ["금융투자협회 법규정보시스템", "제정 2025", "전체선택", "규정내용"]
    lines = [l for l in lines if l and not any(k in l for k in skip_keywords)]

    current_phase = ""
    current_item = ""
    current_content_lines = []

    def flush(phase, item, content_lines):
        content = " ".join(content_lines).strip()
        if content:
            rows.append({
                "출처": "금융투자협회 IT감사 가이드라인",
                "섹션": section_name,
                "단계": phase,
                "항목": item,
                "순번": len(rows) + 1,
                "조문내용": f"[{phase}] {item} {content}".strip()
            })

    for line in lines:
        # 단계 헤더 (Ⅰ. 계획단계 등)
        if line.startswith(("Ⅰ.", "Ⅱ.", "Ⅲ.", "I.", "II.", "III.")):
            if current_item:
                flush(current_phase, current_item, current_content_lines)
                current_content_lines = []
                current_item = ""
            current_phase = line.strip()
        # 항목 번호 (1.1, 1.2, 2.1, ...)
        elif len(line) > 3 and line[0].isdigit() and "." in line[:4]:
            if current_item:
                flush(current_phase, current_item, current_content_lines)
                current_content_lines = []
            current_item = line.strip()
        else:
            current_content_lines.append(line)

    if current_item:
        flush(current_phase, current_item, current_content_lines)

    # 순번 재정렬
    for i, row in enumerate(rows):
        row["순번"] = i + 1

    return rows


def collect_kofia_guidelines() -> pd.DataFrame:
    all_rows = []

    for section in SECTIONS:
        h_seq = section["history_seq"]
        sec_name = section["section_name"]
        print(f"수집 중: {sec_name} ...", end=" ", flush=True)

        soup = fetch_section_content(SEQ, h_seq)

        if h_seq == 1694:
            rows = parse_section(soup, sec_name)
        else:
            rows = parse_section2_checklist(soup, sec_name)

        print(f"{len(rows)}개 항목 수집")
        all_rows.extend(rows)
        time.sleep(0.5)

    df = pd.DataFrame(all_rows)
    return df


if __name__ == "__main__":
    df = collect_kofia_guidelines()

    # 컬럼 정리 (없는 컬럼 채우기)
    for col in ["출처", "섹션", "단계", "항목", "순번", "조문내용"]:
        if col not in df.columns:
            df[col] = ""

    df = df[["출처", "섹션", "단계", "항목", "순번", "조문내용"]]

    print(f"\n총 {len(df)}개 항목 수집 완료!")

    out_path = "data/raw/kofia_guidelines.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료! → {out_path}")

    print("\n[섹션별 수집 현황]")
    print(df.groupby("섹션")["순번"].max().reset_index().to_string(index=False))
