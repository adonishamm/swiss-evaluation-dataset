"""Step 6: extract the procedural history (dated acts) from the facts of each case.

Reads data/parsed/<case>.json for the cases in data/work/proposed_100.csv and writes
data/procedural/<case>.json plus data/work/procedural_steps_100.csv (one row per act).

Method: sentence split of the facts, then regex on dated acts and procedural
verbs per language. Each act gets a date (when found), an actor guess, an act
type (claim, inquiry, pre_decision, decision, objection, cantonal_appeal,
cantonal_judgment, federal_appeal, interim, other) and the source sentence.
This is the backbone for dossier generation; a human reviews it afterwards.
"""
from __future__ import annotations

import json
import re
from collections import Counter

import pandas as pd

from common import DATA, PARSED, WORK

PROC = DATA / "procedural"
PROC.mkdir(exist_ok=True)

MONTHS = {
    "de": "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember",
    "fr": "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre",
    "it": "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre",
}
MONTH_NUM = {}
for lang, names in MONTHS.items():
    for i, n in enumerate(names.split("|"), 1):
        MONTH_NUM[n.lower()] = i

DATE_RX = {
    lang: re.compile(rf"\b(\d{{1,2}})(?:\.|er|\s)?\s*({names})\s+(\d{{4}})\b|\b(\d{{1,2}})\.(\d{{1,2}})\.(\d{{4}})\b", re.I)
    for lang, names in MONTHS.items()
}

ACT_PATTERNS = {
    "claim": r"angemeldet|Anmeldung|meldete sich|Leistungsgesuch|ersuchte|beantragte|a déposé une demande|demande de prestations|s'est annoncé|a annoncé|ha presentato una domanda|ha chiesto|richiesta di prestazioni",
    "inquiry": r"Gutachten|Expertise|Abklärung|Bericht|rapport|expertise|enquête|perizia|rapporto|accertament|Begutachtung|Untersuchung",
    "pre_decision": r"Vorbescheid|préavis|progetto di decisione|preavviso",
    "decision": r"Verfügung|verfügte|décision|a décidé|decisione|ha deciso|Einspracheentscheid|décision sur opposition|decisione su opposizione",
    "objection": r"Einsprache|opposition|opposizione",
    "cantonal_appeal": r"Beschwerde (?:an|beim|ans) (?:das )?(?:Sozialversicherungsgericht|Versicherungsgericht|Verwaltungsgericht|Kantonsgericht|Obergericht)|erhob .{0,40}Beschwerde|recours (?:au|auprès du|devant le) (?:Tribunal cantonal|tribunal cantonal|Tribunal administratif)|a recouru|a formé recours|Saisi d'un recours|ha interposto ricorso|ricorso (?:al|dinanzi al) Tribunale (?:cantonale|delle assicurazioni)|a saisi",
    "cantonal_judgment": r"(?:Sozialversicherungsgericht|Versicherungsgericht|Verwaltungsgericht|Kantonsgericht|Obergericht|Tribunal cantonal|Cour des assurances sociales|Tribunale (?:cantonale|delle assicurazioni)).{0,120}(?:wies .{0,30}ab|hiess .{0,30}gut|a rejeté|a admis|a réformé|a annulé|ha respinto|ha accolto|ha riformato|Urteil vom|arrêt du|sentenza del|giudizio del)",
    "federal_appeal": r"Beschwerde in öffentlich-rechtlichen Angelegenheiten|Beschwerde in Zivilsachen|recours en matière de droit public|recours en matière civile|ricorso in materia di diritto pubblico|ricorso in materia civile|führt .{0,60}Beschwerde|interjette un recours|beantragt.{0,80}(?:aufzuheben|sei)",
    "interim": r"aufschiebende Wirkung|effet suspensif|effetto sospensivo|unentgeltliche Rechtspflege|assistance judiciaire|assistenza giudiziaria|Sistierung|suspension de la procédure",
}
ACT_ORDER = list(ACT_PATTERNS)

ACTORS = {
    "insured": r"\bA\._|Versicherte|assuré|assicurat|Beschwerdeführer(?!in)|recourant(?!e)|ricorrente|Versicherter",
    "insurer": r"IV-Stelle|office AI|Ufficio AI|Suva|SUVA|CNA|INSAI|Unfallversicher|Krankenversicher|assureur|assicurat(?:ore|rice)|Pensionskasse|caisse de pension|Vorsorgeeinrichtung|institution de prévoyance|Ausgleichskasse|caisse de compensation|cassa di compensazione|Versicherung|Assurances?\b|Krankenkasse|caisse-maladie|cassa malati",
    "cantonal_court": r"Sozialversicherungsgericht|Versicherungsgericht|Verwaltungsgericht|Kantonsgericht|Obergericht|Tribunal cantonal|Cour des assurances|Tribunale cantonale|Tribunale delle assicurazioni",
    "federal_court": r"Bundesgericht|Tribunal fédéral|Tribunale federale",
    "federal_office": r"Bundesamt|BSV|OFAS|UFAS|SECO",
    "employer": r"Arbeitgeber|employeur|datore di lavoro",
}


def find_date(sent: str, lang: str) -> str | None:
    m = DATE_RX[lang].search(sent)
    if not m:
        return None
    if m.group(1):
        d, mo, y = int(m.group(1)), MONTH_NUM[m.group(2).lower()], int(m.group(3))
    else:
        d, mo, y = int(m.group(4)), int(m.group(5)), int(m.group(6))
    try:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except ValueError:
        return None


def classify(sent: str) -> str:
    hits = [k for k in ACT_ORDER if re.search(ACT_PATTERNS[k], sent, re.I)]
    if not hits:
        return "other"
    for pref in ("federal_appeal", "cantonal_judgment", "cantonal_appeal", "objection", "pre_decision", "decision", "claim", "interim", "inquiry"):
        if pref in hits:
            return pref
    return hits[0]


def actor_of(sent: str) -> str:
    head = sent[:160]
    for k, rx in ACTORS.items():
        if re.search(rx, head):
            return k
    return "unknown"


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\b([A-Z])\.\s*([a-z])\.\s", r"\1\2 ", text)  # A.a. markers
    parts = re.split(r"(?<=[.;])\s+(?=[A-ZÄÖÜÉÈÀ\d])", text)
    return [p.strip() for p in parts if len(p.strip()) > 15]


def main() -> None:
    sel = pd.read_csv(WORK / "proposed_100.csv")
    rows, per_case = [], Counter()
    for _, r in sel.iterrows():
        p = PARSED / (r["case_id"].replace("/", "_") + ".json")
        d = json.loads(p.read_text(encoding="utf-8"))
        lang = d["language"]
        acts = []
        for i, s in enumerate(split_sentences(d["facts"])):
            kind = classify(s)
            date = find_date(s, lang)
            if kind == "other" and not date:
                continue
            acts.append({"n": len(acts) + 1, "date": date, "actor": actor_of(s), "act": kind, "sentence": s[:400], "sentence_idx": i})
        (PROC / (r["case_id"].replace("/", "_") + ".json")).write_text(
            json.dumps({"case_id": r["case_id"], "language": lang, "domain": r["domain"], "acts": acts}, ensure_ascii=False, indent=1), encoding="utf-8")
        per_case[r["case_id"]] = len(acts)
        for a in acts:
            rows.append({"case_id": r["case_id"], "language": lang, "domain": r["domain"], **{k: a[k] for k in ("n", "date", "actor", "act")}, "sentence": a["sentence"][:200]})
    df = pd.DataFrame(rows)
    df.to_csv(WORK / "procedural_steps_100.csv", index=False)
    counts = pd.Series(per_case)
    print("cases:", len(counts), "| acts per case: median %d, min %d, max %d" % (counts.median(), counts.min(), counts.max()))
    print("\nact types:", df["act"].value_counts().to_dict())
    print("acts with a date:", int(df["date"].notna().sum()), "of", len(df))
    print("\ncases with fewer than 4 acts:", counts[counts < 4].to_dict())
    print("wrote", WORK / "procedural_steps_100.csv", "and", PROC)


if __name__ == "__main__":
    main()
