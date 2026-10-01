"""Step 4: assemble the test set file from the proposed selection and the parsed texts.

Reads data/work/proposed_100.csv and data/parsed/<case>.json, writes
testset/cases_100.jsonl (one record per line) and a readable summary
data/work/cases_100_summary.csv.

Record = v2 schema from docs/case-format-timeline.md. Fields that need the
timeline builder and the decision-point drafter (timeline, actors,
decision_points, presentation) are present but empty, so the file already
supports the outcome task (T3) and the citation metrics.

The AI-generated German summary that the index carries is deliberately NOT copied
into the test set: it is third-party text, always German, and it states the result.
It stays in data/work/proposed_100.csv as ai_summary_de_from_index for human use only.

Label rule: the outcome is read from the dispositive; the index value is kept
in outcome_index. Disagreements are listed at the end.
"""
from __future__ import annotations

import csv
import json
import re

import pandas as pd

from common import PARSED, TESTSET, WORK

DISPOSITIVE_RULES = [
    ("partial_approval", r"wird teilweise gutgeheissen|werden teilweise gutgeheissen|partiellement admis|parzialmente accolt"),
    ("approval", r"wird gutgeheissen|werden gutgeheissen|est admis|sont admis|è accolto|sono accolti"),
    ("dismissal", r"wird abgewiesen|werden abgewiesen|est rejeté|sont rejetés|è respinto|sono respinti"),
]
WINNER = {"approval": "appellant", "partial_approval": "appellant (in part)", "dismissal": "respondent"}
ACTOR_HINT = {"IV": "IV office vs insured", "UV": "accident insurer vs insured", "KV": "health insurer vs insured",
              "BVG": "pension fund vs insured", "AHV_EL": "compensation office vs insured", "PRIV_VVG": "insurer vs policyholder"}


def outcome_from_dispositive(disp: str) -> str | None:
    head = disp[:1200]
    for label, rx in DISPOSITIVE_RULES:
        if re.search(rx, head, re.I):
            return label
    return None


def main() -> None:
    sel = pd.read_csv(WORK / "proposed_100.csv")
    records, mismatches, summary = [], [], []
    for _, r in sel.iterrows():
        p = PARSED / (r["case_id"].replace("/", "_") + ".json")
        if not p.exists():
            print("missing parsed file for", r["case_id"]); continue
        d = json.loads(p.read_text(encoding="utf-8"))
        disp_label = outcome_from_dispositive(d["dispositive"])
        label = disp_label or r["outcome"]
        if disp_label and disp_label != r["outcome"]:
            mismatches.append((r["case_id"], r["language"], r["outcome"], disp_label))
        signals = [s for s in ("sig_panel5", "sig_publication", "sig_long", "sig_reversal", "sig_subject") if bool(r[s])]
        flags = [c[5:] for c in sel.columns if c.startswith("flag_") and bool(r[c])]
        rec = {
            "case_id": r["case_id"],
            "court": f"CH_BGer_{r['chamber']}",
            "decision_date": str(r["decision_date"]),
            "language": r["language"],
            "domain": r["domain"],
            "area_raw": r["area_raw"],
            "subject": r["subject"],
            "lower_court": r["lower_court"],
            "hardness": {"score": int(r["hardness"]), "signals": signals, "subject_flags": flags, "n_judges": int(r["n_judges"])},
            "actors": {},
            "actor_hint": ACTOR_HINT.get(r["domain"], ""),
            "timeline": [],
            "presentation": {},
            "decision_points": [],
            "facts": d["facts"],
            "facts_words": d["facts_words"],
            "outcome": {
                "label": label,
                "label_binary": "approval" if label in ("approval", "partial_approval") else "dismissal",
                "outcome_index": r["outcome"],
                "winner": WINNER[label],
                "dispositive": d["dispositive"],
            },
            "cited_articles_substantive": [{k: c[k] for k in ("law", "article", "old_version", "count")} for c in d["cited_articles_substantive"]],
            "cited_articles_procedural": [{k: c[k] for k in ("law", "article", "count")} for c in d["cited_articles"] if c["procedural"]],
            "cited_precedents": d["cited_precedents"],
            "considerations": d["considerations"],
            "considerations_words": d["considerations_words"],
            "source_url": d["source_url"],
        }
        records.append(rec)
        summary.append({"case_id": r["case_id"], "date": rec["decision_date"], "lang": r["language"], "domain": r["domain"],
                        "outcome": label, "hardness": int(r["hardness"]), "signals": "|".join(signals), "facts_words": d["facts_words"],
                        "n_articles": len(rec["cited_articles_substantive"]), "n_precedents": len(d["cited_precedents"]["leading_cases"]),
                        "subject": r["subject"], "url": d["source_url"]})

    out = TESTSET / "cases_100.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with (WORK / "cases_100_summary.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)

    df = pd.DataFrame(summary)
    print("records:", len(records), "->", out)
    print(pd.crosstab(df["domain"], df["outcome"], margins=True).to_string())
    print("languages:", df["lang"].value_counts().to_dict())
    print("label corrected from dispositive:", len(mismatches))
    for m in mismatches:
        print("  ", m)


if __name__ == "__main__":
    main()
