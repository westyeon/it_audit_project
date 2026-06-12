"""
금융감독원 IT 검사결과 제재 공시 수집기
출처: https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476
공공누리 제1유형 — 출처 표시 시 자유 이용

수집 대상: IT검사국, 전자금융검사국 검사 결과만 필터링
저장 위치: data/processed/fss_sanctions.json
"""

import os, re, time, json, logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL   = "https://www.fss.or.kr"
LIST_URL   = f"{BASE_URL}/fss/job/openInfo/list.do"
HEADERS    = {
    "User-Agent": "Mozilla/5.0 (compatible; IT-Audit-Research/1.0; "
                  "academic research purpose; source: fss.or.kr public disclosure)",
    "Referer": BASE_URL,
}
DELAY_SEC  = 1.0   # 서버 부하 방지 — 요청 간 1초 대기
IT_DEPTS   = ["IT검사국", "전자금융검사국", "정보기술검사국",
               "전자금융감독국", "IT감독국", "정보보호"]

OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                           "data", "processed")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "fss_sanctions.json")


# ── 헬퍼 ─────────────────────────────────────────────────────────
def _get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params,
                             timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r
        except Exception as e:
            log.warning(f"요청 실패({i+1}/{retries}): {e}")
            time.sleep(2 * (i + 1))
    return None


def _text(tag):
    return re.sub(r"\s+", " ", tag.get_text()).strip() if tag else ""


# ── 목록 페이지 파싱 ──────────────────────────────────────────────
def fetch_list_page(page: int, sdate="2012-01-01"):
    """한 페이지의 IT 관련 제재 행 반환"""
    edate = datetime.today().strftime("%Y-%m-%d")
    r = _get(LIST_URL, params={
        "menuNo": "200476",
        "pageIndex": page,
        "sdate": sdate,
        "edate": edate,
    })
    if not r:
        return [], False

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("table tbody tr")
    if not rows:
        return [], False

    items = []
    for row in rows:
        cells = row.find_all("td")
        if not cells or not cells[0].get_text(strip=True).isdigit():
            continue

        dept = _text(cells[4]) if len(cells) > 4 else ""
        if not any(k in dept for k in IT_DEPTS):
            continue

        href_tag = row.find("a", href=re.compile(r"openInfo/view"))
        detail_url = BASE_URL + href_tag["href"] if href_tag else ""
        exam_no = re.search(r"examMgmtNo=(\d+)", detail_url)
        seq     = re.search(r"emOpenSeq=(\d+)", detail_url)

        items.append({
            "seq":           _text(cells[0]),
            "institution":   _text(cells[1]),
            "date":          _text(cells[2]),
            "department":    dept,
            "detail_url":    detail_url,
            "exam_mgmt_no":  exam_no.group(1) if exam_no else "",
            "em_open_seq":   seq.group(1) if seq else "",
        })

    return items, True


# ── 상세 페이지 → PDF URL ─────────────────────────────────────────
def fetch_detail(item: dict) -> dict:
    """상세 페이지에서 PDF 링크 및 메타 추출"""
    if not item.get("detail_url"):
        return item

    r = _get(BASE_URL + item["detail_url"].replace(BASE_URL, "")
             if not item["detail_url"].startswith("http")
             else item["detail_url"])
    if not r:
        return item

    soup = BeautifulSoup(r.text, "html.parser")

    # PDF 링크 수집
    pdf_links = []
    for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
        href = a["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        pdf_links.append(href)

    item["pdf_urls"] = pdf_links
    item["source"] = "금융감독원 제재관련공시 (https://www.fss.or.kr)"
    return item


# ── PDF 파싱 ─────────────────────────────────────────────────────
def parse_pdf(url: str) -> str:
    """PDF 다운로드 후 텍스트 추출 (pdfplumber)"""
    try:
        import pdfplumber, io
        r = _get(url)
        if not r:
            return ""
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            texts = []
            for page in pdf.pages[:8]:   # 최대 8페이지
                t = page.extract_text()
                if t:
                    texts.append(t)
        full = "\n".join(texts)
        # IT 관련 핵심 단락만 추출
        it_keywords = ["전자금융", "정보보호", "IT", "정보기술", "시스템",
                       "접근통제", "백업", "변경관리", "개인정보"]
        paragraphs = full.split("\n")
        relevant = [p for p in paragraphs
                    if any(k in p for k in it_keywords) and len(p) > 20]
        return "\n".join(relevant[:30])   # 최대 30줄
    except Exception as e:
        log.warning(f"PDF 파싱 실패 ({url}): {e}")
        return ""


# ── 위반 항목 추출 ────────────────────────────────────────────────
def extract_violations(pdf_text: str) -> list[str]:
    """PDF 텍스트에서 위반 항목 추출"""
    violations = []
    patterns = [
        r"[①②③④⑤⑥⑦⑧⑨⑩]\s*(.+)",    # 원문자 번호
        r"\d+[.]\s*(.{10,80}위반.{0,40})", # "~위반" 포함 문장
        r"\d+[.]\s*(.{10,80}미흡.{0,40})", # "~미흡" 포함 문장
        r"\d+[.]\s*(.{10,80}불이행.{0,40})", # "~불이행" 포함 문장
    ]
    for pat in patterns:
        matches = re.findall(pat, pdf_text)
        violations.extend([m.strip() for m in matches if len(m.strip()) > 10])
    return list(dict.fromkeys(violations))[:15]  # 중복 제거, 최대 15개


# ── 메인 수집 ─────────────────────────────────────────────────────
def collect_all(max_pages=50, parse_pdfs=True) -> list[dict]:
    """전체 수집 실행"""
    log.info("=" * 60)
    log.info("금융감독원 IT 제재공시 수집 시작")
    log.info(f"IT 검사 부서 필터: {IT_DEPTS}")
    log.info("=" * 60)

    all_items = []
    for page in range(1, max_pages + 1):
        log.info(f"페이지 {page} 수집 중...")
        items, has_data = fetch_list_page(page)
        if not has_data:
            log.info(f"페이지 {page}: 데이터 없음 → 수집 완료")
            break
        if items:
            log.info(f"  IT 관련 {len(items)}건 발견")
            all_items.extend(items)
        time.sleep(DELAY_SEC)

    log.info(f"\n총 {len(all_items)}건 수집. 상세 정보 수집 시작...")

    for i, item in enumerate(all_items):
        log.info(f"  [{i+1}/{len(all_items)}] {item['institution']} 상세 조회...")
        item = fetch_detail(item)

        if parse_pdfs and item.get("pdf_urls"):
            pdf_url = item["pdf_urls"][0]
            log.info(f"    PDF 파싱: {pdf_url[-50:]}")
            pdf_text = parse_pdf(pdf_url)
            item["pdf_text_snippet"] = pdf_text[:1000]
            item["violations"] = extract_violations(pdf_text)

        all_items[i] = item
        time.sleep(DELAY_SEC)

    # 날짜 기준 내림차순 정렬
    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 저장
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    meta = {
        "collected_at": datetime.now().isoformat(),
        "total":        len(all_items),
        "source":       "금융감독원 제재관련공시 (공공누리 제1유형)",
        "source_url":   f"{LIST_URL}?menuNo=200476",
        "items":        all_items,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    log.info(f"\n저장 완료: {OUTPUT_PATH} ({len(all_items)}건)")
    return all_items


# ── 룰 매칭 ──────────────────────────────────────────────────────
def match_sanctions(rule_id: str, rule_nm: str,
                    condition_desc: str) -> list[dict]:
    """
    현재 위반 규칙과 유사한 제재 사례 반환.
    앱에서 호출: match_sanctions("R002", "미승인 운영배포", "...")
    """
    if not os.path.exists(OUTPUT_PATH):
        return []

    with open(OUTPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    keywords = set()
    for text in [rule_nm, condition_desc]:
        keywords.update(re.findall(r"[가-힣]{2,}", text))

    it_terms = {"전자금융", "IT", "시스템", "접근통제", "백업", "변경관리",
                "정보보호", "개인정보", "인증", "암호화", "권한", "배포",
                "운영", "계정", "로그"}
    keywords = keywords & it_terms | {rule_id[:4]}   # R002 → R002 포함 검색

    results = []
    for item in data.get("items", []):
        text_pool = " ".join([
            item.get("institution", ""),
            item.get("department", ""),
            item.get("pdf_text_snippet", ""),
            " ".join(item.get("violations", [])),
        ])
        score = sum(1 for k in keywords if k in text_pool)
        if score >= 1:
            results.append({**item, "_match_score": score})

    results.sort(key=lambda x: (-x["_match_score"], x.get("date", "")),
                 reverse=False)
    # 날짜 내림차순 재정렬
    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    return results[:5]   # 상위 5건


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pdf", action="store_true",
                        help="PDF 파싱 없이 메타데이터만 수집")
    parser.add_argument("--max-pages", type=int, default=50)
    args = parser.parse_args()

    items = collect_all(max_pages=args.max_pages,
                        parse_pdfs=not args.no_pdf)
    print(f"\n완료: {len(items)}건 수집")
    for item in items[:5]:
        print(f"  {item['date']} | {item['institution']} | {item['department']}")
        if item.get("violations"):
            print(f"    위반: {item['violations'][0][:60]}...")
