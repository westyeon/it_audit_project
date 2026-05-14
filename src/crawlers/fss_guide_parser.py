"""
금융감독원 전자금융감독규정 해설서(2025.8) PDF 파서
- data/raw/fss_efg_guide_2025.pdf → data/raw/fss_guide_articles.csv
"""

import pdfplumber
import pandas as pd
import re

PDF_PATH = "data/raw/fss_efg_guide_2025.pdf"
OUT_PATH = "data/raw/fss_guide_articles.csv"

# 장/절 헤더 패턴
RE_CHAPTER = re.compile(r'^제\d+장\s+.+')   # 제1장 총칙
RE_SECTION = re.compile(r'^제\d+절\s+.+')   # 제1절 접근통제
RE_ITEM    = re.compile(r'^\d+\.\s+.+')     # 1. 규정 목적


def is_header_line(line: str) -> str | None:
    """장/절/항목 헤더 여부 판별 → ('chapter'|'section'|'item'|None)"""
    s = line.strip()
    if RE_CHAPTER.match(s):
        return 'chapter'
    if RE_SECTION.match(s):
        return 'section'
    if RE_ITEM.match(s) and len(s) < 60:
        return 'item'
    return None


def is_skip_line(line: str) -> bool:
    """목차·페이지 번호·헤더 등 불필요한 행 제거"""
    s = line.strip()
    if not s:
        return True
    if re.match(r'^\d+$', s):          # 숫자만 (페이지 번호)
        return True
    if '···' in s or '...' in s:       # 목차 점선
        return True
    if s in ('목차', '머 리 말', '머리말'):
        return True
    return False


def extract_pages(pdf_path: str) -> list[str]:
    """pdfplumber로 전체 페이지 텍스트 추출"""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return pages


def parse_guide(pages: list[str]) -> list[dict]:
    rows = []
    current_chapter = ""
    current_section = ""
    current_item = ""
    buffer = []

    def flush():
        content = " ".join(buffer).strip()
        if content and current_item:
            rows.append({
                "출처": "금융감독원 전자금융감독규정 해설서(2025.8)",
                "장": current_chapter,
                "절": current_section,
                "항목": current_item,
                "내용": content,
            })
        buffer.clear()

    for page_text in pages:
        for raw_line in page_text.split("\n"):
            line = raw_line.strip()

            if is_skip_line(line):
                continue

            kind = is_header_line(line)

            if kind == 'chapter':
                flush()
                current_chapter = line
                current_section = ""
                current_item = ""

            elif kind == 'section':
                flush()
                current_section = line
                current_item = ""

            elif kind == 'item':
                flush()
                current_item = line

            else:
                # 본문 텍스트 누적
                if current_item:
                    buffer.append(line)
                # 항목 지정 전에도 장/절 헤더 바로 뒤 텍스트는 포함
                elif current_chapter and not current_item:
                    # 임시 항목명으로 처리
                    current_item = f"[{current_chapter} 본문]"
                    buffer.append(line)

    flush()  # 마지막 버퍼 저장
    return rows


if __name__ == "__main__":
    print(f"PDF 파싱 중: {PDF_PATH}")
    pages = extract_pages(PDF_PATH)
    print(f"  총 {len(pages)}페이지 추출 완료")

    rows = parse_guide(pages)
    print(f"  총 {len(rows)}개 항목 파싱 완료")

    df = pd.DataFrame(rows)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"저장 완료 → {OUT_PATH}")

    print("\n[장별 항목 수]")
    print(df.groupby("장")["항목"].count().reset_index()
            .rename(columns={"항목": "항목수"}).to_string(index=False))
