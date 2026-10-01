"""Step 3: fetch full text from entscheidsuche.ch and split it into sections.

Reads data/work/proposed_100.csv by default (or data/work/candidates_hard_pool.csv with --pool).
For each case:
  1. resolve the entscheidsuche file name from the CH_BGer listing (cached in data/),
  2. download the HTML and JSON into data/raw/,
  3. split into facts / considerations / dispositive,
  4. extract cited (law, article) pairs from the considerations,
  5. write data/parsed/<case_id>.json.

Prints a coverage table at the end. Never touches bger.ch directly (bot-protected).
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from common import DATA, PARSED, RAW, WORK, UA, extract_citations, extract_precedents, split_sections, strip_html

LISTING_URL = "https://entscheidsuche.ch/docs/CH_BGer/"
DOC_URL = "https://entscheidsuche.ch/docs/CH_BGer/{name}"
LISTING_CACHE = DATA / "entscheidsuche_CH_BGer_listing.html"
NAME_RX = re.compile(r'href="(CH_BGer_(\d{3})_([0-9][A-Z]-\d+-\d{4})_(\d{4}-\d{2}-\d{2})\.html)"')


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def load_listing() -> dict[str, list[tuple[str, str]]]:
    if not LISTING_CACHE.exists() or "--refresh-listing" in sys.argv:
        print("downloading entscheidsuche listing (about 120 MB) ...")
        LISTING_CACHE.write_bytes(get(LISTING_URL))
    text = LISTING_CACHE.read_text(encoding="utf-8", errors="ignore")
    table: dict[str, list[tuple[str, str]]] = {}
    for m in NAME_RX.finditer(text):
        name, _chamber, num, d = m.groups()
        case_id = num.replace("-", "_", 1).replace("-", "/")  # 8C-553-2025 -> 8C_553/2025
        table.setdefault(case_id, []).append((name, d))
    return table


def resolve(case_id: str, decision_date: str, table: dict) -> str | None:
    cands = table.get(case_id)
    if not cands:
        return None
    target = date.fromisoformat(str(decision_date))
    cands = sorted(cands, key=lambda c: abs((date.fromisoformat(c[1]) - target).days))
    return cands[0][0]


def process(row: pd.Series, table: dict) -> dict:
    case_id, lang = row["case_id"], row["language"]
    rec = {"case_id": case_id, "language": lang, "domain": row["domain"], "outcome": row["outcome"],
           "decision_date": str(row["decision_date"]), "status": "", "file": None}
    name = resolve(case_id, row["decision_date"], table)
    if not name:
        rec["status"] = "not_in_listing"
        return rec
    rec["file"] = name
    html_path = RAW / name
    if not html_path.exists():
        try:
            html_path.write_bytes(get(DOC_URL.format(name=name)))
            json_name = name[:-5] + ".json"
            (RAW / json_name).write_bytes(get(DOC_URL.format(name=json_name)))
        except Exception as e:  # noqa: BLE001
            rec["status"] = f"download_error: {e}"
            return rec
    text = strip_html(html_path.read_text(encoding="utf-8", errors="ignore"))
    sec = split_sections(text, lang)
    if not sec["ok"]:
        rec["status"] = "section_split_failed"
        return rec
    cites = extract_citations(sec["considerations"], lang)
    rec.update({
        "status": "ok",
        "source_url": DOC_URL.format(name=name),
        "facts": sec["facts"],
        "considerations": sec["considerations"],
        "dispositive": sec["dispositive"],
        "facts_words": len(sec["facts"].split()),
        "considerations_words": len(sec["considerations"].split()),
        "cited_articles": cites,
        "cited_articles_substantive": [c for c in cites if not c["procedural"]],
        "cited_precedents": extract_precedents(sec["considerations"], case_id),
    })
    (PARSED / (case_id.replace("/", "_") + ".json")).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def main() -> None:
    src = WORK / ("candidates_hard_pool.csv" if "--pool" in sys.argv else "proposed_100.csv")
    cases = pd.read_csv(src)
    table = load_listing()
    print("listing entries:", sum(len(v) for v in table.values()), "| cases to fetch:", len(cases))
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda r: process(r[1], table), cases.iterrows()))
    df = pd.DataFrame([{k: v for k, v in r.items() if k in ("case_id", "language", "domain", "outcome", "status", "facts_words", "considerations_words")} | {"n_subst_cites": len(r.get("cited_articles_substantive", []))} for r in results])
    df.to_csv(DATA / "fetch_report.csv", index=False)
    print("\nstatus:", df["status"].value_counts().to_dict())
    ok = df[df["status"] == "ok"]
    if len(ok):
        print("facts words: median %d, min %d, max %d" % (ok["facts_words"].median(), ok["facts_words"].min(), ok["facts_words"].max()))
        print("substantive citations per case: median %d, min %d, max %d" % (ok["n_subst_cites"].median(), ok["n_subst_cites"].min(), ok["n_subst_cites"].max()))
    bad = df[df["status"] != "ok"]
    if len(bad):
        print("\nproblems:"); print(bad.to_string(index=False))
    print("wrote", DATA / "fetch_report.csv", "and", PARSED)


if __name__ == "__main__":
    main()
