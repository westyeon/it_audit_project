import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import os
import pandas as pd

load_dotenv()
API_KEY = os.getenv("LAW_API_KEY")

# IT감사 관련 법령 목록 (법령ID, 법령명, target)
# target: 'law' = 법률/시행령/시행규칙, 'admrul' = 행정규칙(고시/훈령/예규)
IT_AUDIT_LAWS = [
    ("2100000274812", "전자금융감독규정",                                           "admrul"),
    ("010199",        "전자금융거래법",                                              "law"),
    ("010366",        "전자금융거래법 시행령",                                        "law"),
    ("011357",        "개인정보 보호법",                                              "law"),
    ("011468",        "개인정보 보호법 시행령",                                        "law"),
    ("000030",        "정보통신망 이용촉진 및 정보보호 등에 관한 법률",                   "law"),
    ("001540",        "신용정보의 이용 및 보호에 관한 법률",                             "law"),
]


def _extract_text(element):
    """XML 요소에서 CDATA 포함 전체 텍스트 추출"""
    texts = []
    if element.text and element.text.strip():
        texts.append(element.text.strip())
    for child in element:
        t = _extract_text(child)
        if t:
            texts.append(t)
    if element.tail and element.tail.strip():
        texts.append(element.tail.strip())
    return " ".join(texts)


def get_law_detail_admrul(law_id, law_name):
    """행정규칙: 최상위 조문내용 리스트 파싱"""
    url = "http://www.law.go.kr/DRF/lawService.do"
    params = {"OC": API_KEY, "target": "admrul", "ID": law_id, "type": "XML"}
    response = requests.get(url, params=params)
    response.encoding = "utf-8"
    root = ET.fromstring(response.text)

    rows = []
    for i, article in enumerate(root.findall("조문내용")):
        text = article.text
        if text and text.strip():
            rows.append({"법령명": law_name, "순번": i + 1, "조문내용": text.strip()})
    return rows


def get_law_detail_law(law_id, law_name):
    """법률/시행령: 조문단위 기준 파싱 (항/호/목 포함 전체 텍스트 수집)"""
    url = "http://www.law.go.kr/DRF/lawService.do"
    params = {"OC": API_KEY, "target": "law", "ID": law_id, "type": "XML"}
    response = requests.get(url, params=params)
    response.encoding = "utf-8"
    root = ET.fromstring(response.text)

    rows = []
    seq = 1
    for unit in root.iter("조문단위"):
        content_el = unit.find("조문내용")
        if content_el is None:
            continue

        main_text = (content_el.text or "").strip()
        if not main_text:
            continue

        # 항/호/목 등 하위 조문 텍스트 수집
        sub_texts = []
        for child_tag in ["항", "호", "목"]:
            for el in unit.iter(child_tag):
                t = _extract_text(el).strip()
                if t:
                    sub_texts.append(t)

        full_text = main_text
        if sub_texts:
            full_text += " " + " ".join(sub_texts)

        rows.append({"법령명": law_name, "순번": seq, "조문내용": full_text.strip()})
        seq += 1

    return rows


def get_law_detail(law_id, law_name, target="law"):
    if target == "admrul":
        return get_law_detail_admrul(law_id, law_name)
    return get_law_detail_law(law_id, law_name)


if __name__ == "__main__":
    all_data = []

    for law_id, law_name, target in IT_AUDIT_LAWS:
        print(f"수집 중: {law_name} ...", end=" ", flush=True)
        rows = get_law_detail(law_id, law_name, target)
        all_data += rows
        print(f"{len(rows)}개 조문 수집")

    df = pd.DataFrame(all_data)
    print(f"\n총 {len(df)}개 조문 수집 완료!")

    out_path = "data/raw/law_articles.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료! → {out_path}")

    summary = df.groupby("법령명")["순번"].max().reset_index()
    summary.columns = ["법령명", "조문수"]
    print("\n[법령별 수집 현황]")
    print(summary.to_string(index=False))
