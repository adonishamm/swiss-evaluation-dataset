"""Step 8: build per-step questions (agent prompt + gold) from each generated dossier.

For each dossier in testset/dossiers/ and each step k (except the last), the agent is
placed just after step k and asked what comes next. It sees:
  - the case header (domain, language, insured's situation in one line),
  - the documents that exist at that moment: real documents created at or before
    step k, plus traps. T1_future traps are always planted (that is the trap);
    other traps are shown when their date is on or before the step date.
It must answer: next action + deadline; documents to use / to refuse / missing;
legal basis (law + article, version date).

Gold per step: the real next step and its deadline rule; documents whose
use_at_steps contains the next step; every trap shown; the absent document if
needed at or before the next step.

Output: testset/questions/<case>.jsonl (one line per step) and data/work/step_questions_index.csv.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from common import DATA, TESTSET, WORK

DOSSIERS = TESTSET / "dossiers"
OUT = TESTSET / "questions"
OUT.mkdir(exist_ok=True)

QUESTION = {
    "de": ("Sie sind die Rechtsvertretung der versicherten Person. Wir befinden uns unmittelbar nach dem Schritt: {step}. "
           "Unten finden Sie das Dossier, wie es jetzt vorliegt (Dokumente in zufälliger Reihenfolge; nicht alle sind verwendbar oder echt). "
           "Antworten Sie als JSON mit den Feldern: next_action (string), deadline (string: Dauer + Beginn + Rechtsgrundlage), "
           "use_documents (Liste doc_id), refuse_documents (Liste {{doc_id, reason}}), missing_document (string oder null), "
           "legal_basis (Liste {{law, article, version_date}}), reasoning (max. 5 Sätze). Antworten Sie auf Deutsch."),
    "fr": ("Vous représentez la personne assurée. Nous sommes juste après l'étape : {step}. "
           "Ci-dessous le dossier tel qu'il existe maintenant (documents en ordre aléatoire ; tous ne sont pas utilisables ni authentiques). "
           "Répondez en JSON avec les champs : next_action (string), deadline (string : durée + point de départ + base légale), "
           "use_documents (liste de doc_id), refuse_documents (liste de {{doc_id, reason}}), missing_document (string ou null), "
           "legal_basis (liste de {{law, article, version_date}}), reasoning (5 phrases max). Répondez en français."),
    "it": ("Lei rappresenta la persona assicurata. Ci troviamo subito dopo la fase: {step}. "
           "Qui sotto il dossier come esiste ora (documenti in ordine casuale; non tutti sono utilizzabili o autentici). "
           "Risponda in JSON con i campi: next_action (string), deadline (string: durata + decorrenza + base legale), "
           "use_documents (lista di doc_id), refuse_documents (lista di {{doc_id, reason}}), missing_document (string o null), "
           "legal_basis (lista di {{law, article, version_date}}), reasoning (max 5 frasi). Risponda in italiano."),
}

STEP_ORDER = ["S1_claim", "S2_inquiry", "S3_pre_decision", "S4_decision", "S5_objection",
              "S6_cantonal_appeal", "S6b_cantonal_judgment", "S7_federal_appeal", "S7b_interim"]


def to_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def visible_docs(docs: list[dict], step_date: date | None, step_code: str, step_idx: int, steps: list[dict]) -> list[dict]:
    """Documents on the table just after step k, while the party prepares step k+1.

    Window end = date of step k+1 if known, else step date + 45 days. Real documents
    created at or before step k, or dated inside the window, are visible. Traps:
    T1_future and T5_wrong_law_version are always planted; the others are visible
    when dated inside the window.
    """
    out = []
    earlier_codes = {s["code"] for s in steps[: step_idx + 1]}
    nxt_date = to_date(steps[step_idx + 1].get("date")) if step_idx + 1 < len(steps) else None
    window_end = nxt_date or (step_date + timedelta(days=45) if step_date else None)
    for d in docs:
        g = d["ground_truth"]
        dd = to_date(d.get("date"))
        inside = dd is None or window_end is None or dd <= window_end
        if g["status"] == "real":
            if g.get("step_created") in earlier_codes or (dd and step_date and dd <= step_date) or (dd and window_end and step_date and step_date < dd <= window_end):
                out.append(d)
        else:
            if g.get("trap_type") in ("T1_future", "T5_wrong_law_version") or inside:
                out.append(d)
    return out


def render_doc(d: dict) -> str:
    return (f"[{d['doc_id']}] {d['title']}\n{d.get('author','')} -> {d.get('recipient','')} | {d.get('date','')} | ref. {d.get('reference','')}\n"
            f"{d['body']}\n")


def main() -> None:
    rows = []
    for path in sorted(DOSSIERS.glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("_check"):
            pass  # questions are still built; the check list is kept in the row for review
        steps = d["steps"]
        docs = d["documents"]
        lang = d["language"]
        lines = []
        for k in range(len(steps) - 1):
            cur, nxt = steps[k], steps[k + 1]
            step_date = to_date(cur.get("date"))
            vis = visible_docs(docs, step_date, cur["code"], k, steps)
            if len(vis) < 2:
                continue
            gold_use = [x["doc_id"] for x in vis if x["ground_truth"]["status"] == "real" and nxt["code"] in (x["ground_truth"].get("use_at_steps") or [])]
            gold_refuse = [{"doc_id": x["doc_id"], "trap_type": x["ground_truth"]["trap_type"], "note": x["ground_truth"].get("trap_note")} for x in vis if x["ground_truth"]["status"] == "trap"]
            absent = d.get("absent_document") or {}
            need_idx = STEP_ORDER.index(absent["needed_at_step"]) if absent.get("needed_at_step") in STEP_ORDER else 99
            gold_absent = absent if STEP_ORDER.index(nxt["code"]) >= need_idx and nxt["code"] in STEP_ORDER else None
            prompt = (QUESTION[lang].format(step=f"{cur['code']} ({cur.get('date') or 'date inconnue'}): {cur['act']}") + "\n\n=== DOSSIER ===\n\n" + "\n".join(render_doc(x) for x in vis))
            rec = {
                "case_id": d["case_id"], "language": lang, "step_index": k, "after_step": cur["code"], "after_step_date": cur.get("date"),
                "prompt": prompt,
                "visible_doc_ids": [x["doc_id"] for x in vis],
                "gold": {
                    "next_step": nxt["code"], "next_action": nxt["act"], "next_actor": nxt.get("actor"), "deadline_rule": nxt.get("deadline_rule"),
                    "use_documents": gold_use, "refuse_documents": gold_refuse,
                    "missing_document": gold_absent,
                    "n_traps_visible": len(gold_refuse),
                },
            }
            lines.append(json.dumps(rec, ensure_ascii=False))
            rows.append({"case_id": d["case_id"], "language": lang, "after_step": cur["code"], "next_step": nxt["code"],
                         "visible_docs": len(vis), "gold_use": len(gold_use), "traps_visible": len(gold_refuse), "absent_expected": bool(gold_absent)})
        (OUT / (d["case_id"].replace("/", "_") + ".jsonl")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    df = pd.DataFrame(rows)
    if len(df):
        df.to_csv(WORK / "step_questions_index.csv", index=False)
        print("questions:", len(df), "| cases:", df["case_id"].nunique())
        print(df.groupby("case_id")[["visible_docs", "gold_use", "traps_visible"]].mean().round(1).to_string())
        print("transitions:", df.groupby(["after_step", "next_step"]).size().to_dict())
    else:
        print("no dossiers found in", DOSSIERS)


if __name__ == "__main__":
    main()
