"""Step 2: draw the hard candidate pool and a proposed 100-case selection.

Reads data/index.parquet (from 01_build_index.py).

Hard pool = in-scope merits decisions dated 2025 or later that carry at least one
strong hardness signal: five-judge panel, flagged for official publication, or
top-decile length. Reversals and subject flags raise the score but do not by
themselves qualify a case, otherwise the pool would be dominated by routine
disability-pension reversals.

Proposed 100 = greedy stratified pick from the pool by domain quota, language
cap and outcome balance, highest hardness first. Deterministic.

Outputs: testset/candidates_hard_pool.csv, testset/proposed_100.csv
"""
from __future__ import annotations

import pandas as pd

from common import DATA, TESTSET

MIN_YEAR = 2025
DOMAIN_QUOTA = {"IV": 30, "UV": 25, "KV": 15, "BVG": 10, "AHV_EL": 10, "PRIV_VVG": 10}
LANG_CAP = {"de": 60, "fr": 40, "it": 8}
TARGET_REVERSAL_SHARE = 0.5

COLS = [
    "case_id", "decision_date", "language", "chamber", "domain", "area_raw", "subject",
    "lower_court", "outcome", "n_judges", "length", "hardness",
    "sig_reversal", "sig_panel5", "sig_publication", "sig_long", "sig_subject",
    "flag_causality", "flag_revision", "flag_restitution", "flag_expert_report",
    "flag_coordination", "flag_psychiatric", "flag_income_comparison",
    "flag_deadline_formality", "flag_helplessness_assistance", "ai_summary_de_from_index",
]


def pick_100(pool: pd.DataFrame) -> pd.DataFrame:
    pool = pool.sort_values(["hardness", "decision_date"], ascending=[False, False]).reset_index(drop=True)
    chosen: list[int] = []
    lang_used = {k: 0 for k in LANG_CAP}
    for dom, quota in DOMAIN_QUOTA.items():
        sub = pool[pool["domain"] == dom]
        want_rev = round(quota * TARGET_REVERSAL_SHARE)
        got = {"rev": 0, "dis": 0}
        for i, row in sub.iterrows():
            if got["rev"] + got["dis"] >= quota:
                break
            if lang_used.get(row["language"], 99) >= LANG_CAP.get(row["language"], 0):
                continue
            kind = "rev" if row["sig_reversal"] else "dis"
            limit = want_rev if kind == "rev" else quota - want_rev
            if got[kind] >= limit:
                continue
            chosen.append(i)
            got[kind] += 1
            lang_used[row["language"]] += 1
        # second pass: fill the domain quota regardless of outcome balance
        for i, row in sub.iterrows():
            if got["rev"] + got["dis"] >= quota:
                break
            if i in chosen or lang_used.get(row["language"], 99) >= LANG_CAP.get(row["language"], 0):
                continue
            chosen.append(i)
            got["rev" if row["sig_reversal"] else "dis"] += 1
            lang_used[row["language"]] += 1
    return pool.loc[chosen]


def main() -> None:
    idx = pd.read_parquet(DATA / "index.parquet")
    base = idx[idx["in_scope"] & idx["merits"] & (idx["year"] >= MIN_YEAR)]
    pool = base[base["sig_panel5"] | base["sig_publication"] | base["sig_long"]].copy()
    pool = pool.sort_values(["hardness", "decision_date"], ascending=[False, False])
    pool[COLS].to_csv(TESTSET / "candidates_hard_pool.csv", index=False)

    print("in-scope merits >= %d: %d | hard pool: %d" % (MIN_YEAR, len(base), len(pool)))
    print("\npool by domain x outcome"); print(pd.crosstab(pool["domain"], pool["outcome"], margins=True).to_string())
    print("\npool by language"); print(pool["language"].value_counts().to_dict())
    print("\npool hardness distribution"); print(pool["hardness"].value_counts().sort_index().to_dict())

    sel = pick_100(pool)
    sel[COLS].to_csv(TESTSET / "proposed_100.csv", index=False)
    print("\nproposed selection:", len(sel))
    print(pd.crosstab(sel["domain"], sel["outcome"], margins=True).to_string())
    print(pd.crosstab(sel["domain"], sel["language"], margins=True).to_string())
    print("signals in selection:", {c: int(sel[c].sum()) for c in ["sig_reversal", "sig_panel5", "sig_publication", "sig_long", "sig_subject"]})
    print("wrote", TESTSET / "candidates_hard_pool.csv", "and", TESTSET / "proposed_100.csv")


if __name__ == "__main__":
    main()
