"""Step 7b: expand each dossier document to realistic length and depth.

Second pass over a dossier produced by 07_generate_dossier.py (the plan: steps,
document list, trap labels, absent document). One call per document, with a
template for its type and a word target that matches real Swiss practice.
Traps keep their type but the giveaway is buried in the text, never in the
header or in a label. Figures (dates, amounts, percentages, birth dates) must be
consistent with the other documents of the dossier unless the trap is precisely
an inconsistency.

Input: facts of the case + the dossier plan (all documents' headers and key facts).
Never the considerations or the dispositive.

Usage:
  python scripts/07b_expand_documents.py --cases 8C_229/2024 [--model sonnet] [--only D05 D09]
Output: the dossier JSON is updated in place (bodies replaced, old bodies kept in body_v1),
plus _expansion metadata.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from common import PARSED, TESTSET

sys.path.insert(0, str(TESTSET.parent / "scripts"))
from importlib import import_module  # noqa: E402

gen = import_module("07_generate_dossier")

DOSSIERS = TESTSET / "dossiers"
LANG_NAME = {"de": "German", "fr": "French", "it": "Italian"}

# word targets and structure per document type (Swiss practice)
TEMPLATES = {
    "decision": (700, 1300, "Insurer / IV-office decision (Verfügung / décision / decisione): letterhead, file reference, AVS number, subject; 'Sachverhalt / Faits' recalling the claim and the inquiry with dates; 'Erwägungen / Considérants' applying the statute paragraph by paragraph, with article numbers and the usual case-law references; a numbered 'Dispositiv / Dispositif'; costs; 'Rechtsmittelbelehrung / Voies de droit' with the exact remedy, court and 30-day deadline; signature block with two names and functions."),
    "pre_decision": (500, 900, "IV pre-decision (Vorbescheid / préavis): same structure as a decision but announcing the intended decision and inviting objections within 30 days (art. 57a LAI), listing the file documents it relies on."),
    "objection": (500, 900, "Objection (Einsprache / opposition) by the insured or a lawyer: addressee, reference, requests (Rechtsbegehren / conclusions), facts from the insured's side, legal arguments with articles, evidence offered, signature, enclosures list."),
    "appeal": (900, 1600, "Appeal brief to a cantonal insurance court or to the Federal Supreme Court: cover, parties and representation, requests, admissibility paragraph (deadline, standing, court), facts, legal grounds in numbered sections with article citations and a few case references, evidence list, request for legal aid or suspensive effect if relevant, signature, enclosures."),
    "judgment": (1500, 2600, "Cantonal court judgment: court, composition (president, judges, clerk), parties, subject; 'Sachverhalt / Faits' A to C with the procedural history; 'Erwägungen / Considérants' numbered 1 to 6+ covering admissibility, applicable law (with intertemporal remark when the law changed), the evidence (expert reports, their probative value), the subsumption, costs; 'Dispositiv'; remedy instruction (30 days, Federal Supreme Court, art. 82 ff. LTF)."),
    "medical_report": (900, 1800, "Medical report or treating physician's report to the insurer: patient data (name, birth date, AVS no.), questions asked by the insurer, anamnesis, current complaints, clinical findings, diagnoses with ICD-10 codes (with and without effect on work capacity), treatment, prognosis, work capacity in percent in the usual activity and in an adapted activity, limitations list, consistency remarks, date and signature."),
    "expert_report": (1800, 3000, "Independent medical expert report (Gutachten / expertise): mandate and questions, file review listing the documents read (with dates), anamnesis (social, professional, medical), complaints, examination findings per system, diagnoses ICD-10, discussion with the standard indicators (severity, consistency, resources, course), work capacity in percent with start dates, limitations, answers to each question of the insurer, date, signature, qualifications."),
    "inquiry_report": (700, 1200, "Home inquiry report (Abklärungsbericht / rapport d'enquête à domicile) for helplessness allowance: date and place of the visit, persons present, living situation, the six ordinary acts of life each assessed (dressing, getting up / sitting / lying down, eating, personal hygiene, toilet, moving / social contacts) with help needed yes/no and hours, need for supervision, need for life-management support with minutes per week, summary, degree proposed."),
    "claim": (400, 700, "Claim form to the insurer or IV office as filled in: personal data, insurance details, employer and income, description of the health impairment and its beginning, physicians, prior benefits, benefits requested, authorisation to obtain information, date, signature."),
    "letter": (300, 600, "Letter between the parties: letterhead, reference, subject, body stating the position and the next step, enclosures, signature."),
    "order": (300, 600, "Procedural order of a court (effet suspensif, assistance judiciaire, instruction): court, parties, considerations in a few numbered paragraphs, order, notification."),
    "statute_extract": (300, 700, "Extract from the federal statute or ordinance as filed by a party: heading with SR number, title, consolidation date, the article(s) in full with paragraphs and letters, and a note of the amendment history."),
}

PROMPT = """You are writing one document of an evaluation dossier for a Swiss social-insurance case. Write it in {lang_name}. It must read like the real thing a practitioner would find in the file: full length, proper structure, concrete dates, amounts, percentages, names anonymised exactly as in the facts (A.________, B.________, firms as C.________ SA).

CASE {case_id}, domain {domain}. FACTS OF THE CASE AS LATER SUMMARISED BY THE COURT (your only source of truth; never go beyond them on the merits, never state how the final court case ends):
\"\"\"
{facts}
\"\"\"

DOSSIER PLAN (all documents of the file, so that your document is consistent with them: same dates, same amounts, same birth dates, same references, unless YOUR document is a trap whose point is an inconsistency):
{plan}

DOCUMENT TO WRITE: {doc_id}
type: {dtype}
title: {title}
author: {author}
recipient: {recipient}
date: {date}
reference: {reference}
status: {status}{trap_block}

STRUCTURE AND LENGTH for this type: {template}
Target: {wmin} to {wmax} words. Do not pad; make it dense with the kind of detail the real document carries (file references, dates of every prior act, figures, article numbers, names of functions). Where the facts give no figure, invent a plausible one and keep it consistent with the plan.

OUTPUT: the document text only, no JSON, no markdown fences, no commentary."""

TRAP_BLOCK = """
THIS DOCUMENT IS A TRAP of type {trap_type}: {trap_def}
Reviewer note from the plan (what gives it away): {trap_note}
Bury the giveaway inside the text where only a careful reader notices it. NEVER write words like draft, Entwurf, brouillon, bozza, not sent, non envoyé, nicht versandt, for information, version provisoire, v1, or any label that announces the trap. Headers must look exactly like a real document's."""


def plan_text(d: dict) -> str:
    lines = [f"- {s['code']} {s.get('date') or '----'}: {s['act']}" for s in d["steps"]]
    lines.append("documents:")
    for x in d["documents"]:
        g = x["ground_truth"]
        lines.append(f"- {x['doc_id']} [{x['type']}] {x['date']} | {x['author']} -> {x['recipient']} | ref {x['reference']} | {x['title']} | key facts: {x['body'][:260].replace(chr(10), ' ')}")
    a = d.get("absent_document") or {}
    lines.append(f"absent document (must NOT appear anywhere, not even as a reference that it exists): {a.get('type')} - {a.get('description')}")
    return "\n".join(lines)


def expand_one(d: dict, x: dict, facts: str, model: str, binary: str) -> dict:
    dtype = x["type"] if x["type"] in TEMPLATES else "letter"
    wmin, wmax, template = TEMPLATES[dtype]
    g = x["ground_truth"]
    trap_block = ""
    if g["status"] == "trap":
        trap_block = TRAP_BLOCK.format(trap_type=g["trap_type"], trap_def=gen.TRAP_TYPES.get(g["trap_type"], ""), trap_note=g.get("trap_note", ""))
    prompt = PROMPT.format(lang_name=LANG_NAME[d["language"]], case_id=d["case_id"], domain=d.get("domain", ""), facts=facts, plan=plan_text(d),
                           doc_id=x["doc_id"], dtype=x["type"], title=x["title"], author=x["author"], recipient=x["recipient"], date=x["date"],
                           reference=x["reference"], status=g["status"], trap_block=trap_block, template=template, wmin=wmin, wmax=wmax)
    text, meta = gen.call_claude(prompt, model, binary)
    text = text.strip()
    return {"doc_id": x["doc_id"], "body": text, "words": len(text.split()), "seconds": meta["_seconds"], "cost_usd": meta.get("total_cost_usd")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    binary = gen.find_claude_bin()
    for cid in args.cases:
        slug = cid.replace("/", "_")
        path = DOSSIERS / f"{slug}.json"
        d = json.loads(path.read_text(encoding="utf-8"))
        facts = json.loads((PARSED / f"{slug}.json").read_text(encoding="utf-8"))["facts"]
        targets = [x for x in d["documents"] if not args.only or x["doc_id"] in args.only]
        print(f"{cid}: expanding {len(targets)} documents with {args.model} ...")
        t0 = time.time()
        with ThreadPoolExecutor(args.workers) as ex:
            results = list(ex.map(lambda x: expand_one(d, x, facts, args.model, binary), targets))
        by_id = {r["doc_id"]: r for r in results}
        total_cost = 0.0
        for x in d["documents"]:
            r = by_id.get(x["doc_id"])
            if not r or r["words"] < 100:
                continue
            x.setdefault("body_v1", x["body"])
            x["body"] = r["body"]
            x["words"] = r["words"]
            total_cost += r.get("cost_usd") or 0
        d["_expansion"] = {"model": args.model, "seconds": round(time.time() - t0, 1), "cost_usd": round(total_cost, 2),
                           "words": {r["doc_id"]: r["words"] for r in results}}
        path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  done in {d['_expansion']['seconds']}s, ${d['_expansion']['cost_usd']:.2f} | words per document:",
              ", ".join(f"{k}={v}" for k, v in sorted(d["_expansion"]["words"].items())))


if __name__ == "__main__":
    main()
