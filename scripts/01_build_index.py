"""Step 1: build the case index with domain, outcome and hardness signals.

Source: jachermann/bger-update on Hugging Face (daily parquet of every decision
published on bger.ch since 2022). Downloads the latest snapshot if none is cached.

Output: data/index.parquet (all decisions) and data/index_scope.csv (in-scope only).
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request

import pandas as pd

from common import DATA, MERITS, OUTCOME_MAP, SUBJECT_FLAGS, UA, domain_of

HF_API = "https://huggingface.co/api/datasets/jachermann/bger-update"
HF_FILE = "https://huggingface.co/datasets/jachermann/bger-update/resolve/main/{path}"


def latest_snapshot() -> str:
    with urllib.request.urlopen(urllib.request.Request(HF_API, headers=UA), timeout=60) as r:
        meta = json.load(r)
    files = sorted(s["rfilename"] for s in meta["siblings"] if s["rfilename"].startswith("urteile/"))
    return files[-1]


def load_snapshot() -> tuple[pd.DataFrame, str]:
    cached = sorted(DATA.glob("bger_update_*.parquet"))
    if cached and "--refresh" not in sys.argv:
        path = cached[-1]
    else:
        remote = latest_snapshot()
        path = DATA / ("bger_update_" + remote.split("/")[-1])
        if not path.exists():
            print("downloading", remote)
            urllib.request.urlretrieve(HF_FILE.format(path=remote), path)
    return pd.read_parquet(path), path.name


def main() -> None:
    df, snap = load_snapshot()
    print("snapshot:", snap, "rows:", len(df))

    df = df.sort_values("zuletzt_geaendert").drop_duplicates("urteilsnummer", keep="last")
    out = pd.DataFrame({
        "case_id": df["urteilsnummer"],
        "decision_date": pd.to_datetime(df["urteilsdatum"], errors="coerce").dt.date,
        "publication_date": pd.to_datetime(df["veroeffentlichungsdatum"], errors="coerce").dt.date,
        "language": df["sprache"].str.lower(),
        "chamber": df["urteilsnummer"].str.extract(r"^(\d[A-Z])")[0],
        "area_raw": df["rechtsgebiet"].fillna("").str.replace("*", "", regex=False).str.strip(),
        "subject": df["gegenstand"].fillna(""),
        "lower_court": df["vorinstanz"].fillna(""),
        "outcome_raw": df["verfahrensergebnis"].fillna(""),
        "length": df["laenge"],
        "n_judges": df["richterin"].fillna("").apply(lambda s: len([x for x in s.split(",") if x.strip()])),
        "publication_flag": df["publikation_vorgesehen"].fillna(False).astype(bool),
        "published_as": df["publiziert_als"].fillna(""),
        "ai_summary_de_from_index": df["zusammenfassung_korrigiert"].where(df["zusammenfassung_korrigiert"].fillna("") != "", df["zusammenfassung"]).fillna(""),
    })
    out["year"] = pd.to_datetime(out["decision_date"]).dt.year
    out["outcome"] = out["outcome_raw"].map(OUTCOME_MAP).fillna("unknown")
    out["merits"] = out["outcome"].isin(MERITS)
    out["domain"] = [domain_of(a, c, s) for a, c, s in zip(out["area_raw"], out["chamber"], out["subject"])]
    out["in_scope"] = out["domain"].notna()

    # hardness signals -------------------------------------------------------
    out["sig_reversal"] = out["outcome"].isin({"approval", "partial_approval"})
    out["sig_panel5"] = out["n_judges"] >= 5
    out["sig_publication"] = out["publication_flag"] | (out["published_as"] != "")
    scope_merits = out[out["in_scope"] & out["merits"] & (out["year"] >= 2025)]
    long_cut = scope_merits["length"].quantile(0.90) if len(scope_merits) else float("inf")
    out["sig_long"] = out["length"] >= long_cut
    for name, rx in SUBJECT_FLAGS.items():
        out[f"flag_{name}"] = out["subject"].str.contains(rx, case=False, regex=True, na=False)
    out["sig_subject"] = out[[f"flag_{n}" for n in SUBJECT_FLAGS]].any(axis=1)
    out["hardness"] = (
        out["sig_reversal"].astype(int)
        + out["sig_panel5"].astype(int) * 2
        + out["sig_publication"].astype(int) * 2
        + out["sig_long"].astype(int)
        + out["sig_subject"].astype(int)
    )

    out.to_parquet(DATA / "index.parquet", index=False)
    scope = out[out["in_scope"]].sort_values(["decision_date", "case_id"])
    scope.to_csv(DATA / "index_scope.csv", index=False)

    print("all decisions:", len(out), "| in scope:", len(scope), "| in scope merits >= 2025:", len(scope_merits))
    print("length cut for sig_long:", long_cut)
    print(pd.crosstab(scope_merits["domain"], scope_merits["outcome"], margins=True).to_string())
    print("wrote", DATA / "index.parquet", "and", DATA / "index_scope.csv")


if __name__ == "__main__":
    main()
