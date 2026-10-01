"""Step 7: generate the dossier (real documents + labelled traps) for each case.

Input per case: facts section (data/parsed), procedural acts skeleton
(data/procedural), domain, language. NEVER the considerations or the dispositive,
so generated documents cannot leak the outcome.

Backend: the Claude Code CLI in headless mode (uses the user's login, no API key).
Set CLAUDE_BIN to the executable, or let the script find the VS Code bundled one.
One call per case; the model returns one JSON object with the whole dossier.

Usage:
  python scripts/07_generate_dossier.py --cases 8C_229/2024 8C_484/2025
  python scripts/07_generate_dossier.py --all            # every case in proposed_100.csv
  python scripts/07_generate_dossier.py --model opus     # default: sonnet

Output: testset/dossiers/<case>.json and data/work/dossier_index.csv
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from common import DATA, PARSED, TESTSET, WORK

DOSSIERS = TESTSET / "dossiers"
DOSSIERS.mkdir(exist_ok=True)
PROC = DATA / "procedural"

TRAP_TYPES = {
    "T1_future": "a document dated AFTER the step it is planted in (typically the cantonal judgment or a later expert report placed before it exists)",
    "T2_superseded": "an earlier version of a real document, later replaced (first inquiry report, first medical certificate, first decision later corrected)",
    "T3_unsent": "a draft objection, appeal or letter that was written but never filed or never notified",
    "T4_wrong_person": "a similar document about another person (sibling, colleague, another insured with a similar name)",
    "T5_wrong_law_version": "the text of the key article in a version NOT in force at the relevant date (e.g. current wording instead of the wording at the decision date)",
    "T6_lookalike": "a plausible but irrelevant document (unrelated diagnosis, unrelated letter from the same insurer)",
}

LANG_NAME = {"de": "German", "fr": "French", "it": "Italian"}

PROMPT = """You are building an evaluation dossier for a Swiss social-insurance case. You will write realistic documents, in {lang_name}, reconstructed ONLY from the facts below. Never invent an outcome of the final court decision; never state how the case ends; never add medical or legal conclusions that are not in the facts.

CASE: {case_id}  DOMAIN: {domain}  LANGUAGE: {lang}

FACTS (as written by the court, procedural history included):
\"\"\"
{facts}
\"\"\"

PROCEDURAL ACTS DETECTED (date | actor guess | type guess | sentence). The actor/type guesses are noisy; correct them from the facts:
{acts}

TASK
1. Write the clean procedural history as steps, in chronological order. Allowed step codes: S1_claim, S2_inquiry, S3_pre_decision, S4_decision, S5_objection, S6_cantonal_appeal, S6b_cantonal_judgment, S7_federal_appeal, S7b_interim. Do NOT include the final federal outcome (no S8).
2. Write the REAL documents: one per act that produced a document in the facts (claim form, medical or inquiry report, decision, objection, appeal brief, cantonal judgment, federal appeal brief, interim order). 6 to 11 documents. Each has a realistic header and a body of 120 to 350 words that says only what the facts say. Party names stay anonymised as in the facts (A.________, B.________). Use realistic Swiss formats (addresses as "____", reference numbers, "Rechtsmittelbelehrung" / "Voies de droit" paragraphs on decisions).
3. Write 4 to 5 TRAP documents using the same templates and the same tone, so they are not visually distinguishable. Use at least these trap types: T1_future, T3_unsent, T5_wrong_law_version, and two more from: T2_superseded, T4_wrong_person, T6_lookalike. Definitions:
{trap_defs}
   TRAPS MUST NOT ANNOUNCE THEMSELVES. Never write "draft", "not sent", "brouillon", "non spedita", "Entwurf", "for information only", "version provisoire", "v1" or any similar label in the title or body. The giveaway must be a detail a careful practitioner would notice: for T3 an unsigned signature block, no registered-mail number, no receipt stamp, no acknowledgement from the recipient, or a mention in a later document that no objection was received; for T1 the date itself and references to events the agent has not seen; for T2 a date earlier than the final version and figures that the later document corrects; for T4 a different date of birth, AVS number or first-name initial in the header; for T5 the consolidation date or an amended paragraph; for T6 a subject that has nothing to do with the claim. Put the giveaway in ground_truth.trap_note for the reviewer, not in the document.
4. Name the ABSENT document (T7): the single most decisive piece of evidence that the facts show was never produced or still had to be obtained. If the facts give no such gap, name the document whose absence would most weaken the insured's position. One sentence on why.
5. Shuffle real and trap documents together and number them D01, D02, ... in a random, non-chronological order.

OUTPUT: exactly one JSON object, no prose before or after, no markdown fences:
{{
 "case_id": "...",
 "language": "...",
 "steps": [{{"code": "S4_decision", "date": "YYYY-MM-DD or null", "actor": "insured|insurer|iv_office|cantonal_court|federal_office|employer|other", "act": "one sentence", "deadline_rule": "e.g. 30 days from notification, art. 60 LPGA, or null"}}],
 "documents": [{{
   "doc_id": "D01", "type": "claim|medical_report|inquiry_report|expert_report|pre_decision|decision|objection|appeal|judgment|letter|statute_extract|order",
   "title": "...", "author": "...", "recipient": "...", "date": "YYYY-MM-DD", "reference": "...",
   "body": "...",
   "ground_truth": {{"status": "real|trap", "step_created": "S4_decision", "use_at_steps": ["S6_cantonal_appeal","S7_federal_appeal"], "trap_type": "null or T1_future etc.", "trap_note": "one sentence for the reviewer, why this is a trap and what gives it away", "source_sentence": "the facts sentence it is built from, or null for traps"}}
 }}],
 "absent_document": {{"type": "...", "description": "...", "why_decisive": "...", "needed_at_step": "S6_cantonal_appeal"}}
}}
"""


def find_claude_bin() -> str:
    env = os.environ.get("CLAUDE_BIN")
    if env and Path(env).exists():
        return env
    home = Path.home()
    cands = sorted(glob.glob(str(home / ".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe")))
    if cands:
        return cands[-1]
    for name in ("claude.exe", "claude.cmd", "claude"):
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if (Path(p) / name).exists():
                return str(Path(p) / name)
    sys.exit("no Claude CLI found; set CLAUDE_BIN")


def call_claude(prompt: str, model: str, binary: str) -> tuple[str, dict]:
    cmd = [binary, "-p", prompt, "--output-format", "json", "--max-turns", "1", "--model", model]
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500, stdin=subprocess.DEVNULL)
    if res.returncode != 0:
        raise RuntimeError(f"claude exited {res.returncode}: {res.stderr[:500]}")
    meta = json.loads(res.stdout)
    meta["_seconds"] = round(time.time() - t0, 1)
    return meta.get("result", ""), meta


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def check(d: dict) -> list[str]:
    problems = []
    docs = d.get("documents", [])
    real = [x for x in docs if x["ground_truth"]["status"] == "real"]
    traps = [x for x in docs if x["ground_truth"]["status"] == "trap"]
    if not 6 <= len(real) <= 12:
        problems.append(f"{len(real)} real documents")
    if not 3 <= len(traps) <= 6:
        problems.append(f"{len(traps)} traps")
    types = {x["ground_truth"].get("trap_type") for x in traps}
    for must in ("T1_future", "T3_unsent", "T5_wrong_law_version"):
        if must not in types:
            problems.append(f"missing {must}")
    if not d.get("absent_document", {}).get("type"):
        problems.append("no absent document")
    ids = [x["doc_id"] for x in docs]
    if len(ids) != len(set(ids)):
        problems.append("duplicate doc ids")
    for x in docs:
        if len(x.get("body", "").split()) < 60:
            problems.append(f"{x['doc_id']} body too short")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    sel = pd.read_csv(WORK / "proposed_100.csv")
    cases = sel["case_id"].tolist() if args.all else args.cases
    if not cases:
        sys.exit("give --cases ... or --all")
    binary = find_claude_bin()
    print("claude binary:", binary, "| model:", args.model)

    rows = []
    for cid in cases:
        slug = cid.replace("/", "_")
        out = DOSSIERS / f"{slug}.json"
        if out.exists() and not args.force:
            print(cid, "exists, skip"); continue
        parsed = json.loads((PARSED / f"{slug}.json").read_text(encoding="utf-8"))
        proc = json.loads((PROC / f"{slug}.json").read_text(encoding="utf-8"))
        acts = "\n".join(f"{a['date'] or '----'} | {a['actor']} | {a['act']} | {a['sentence'][:220]}" for a in proc["acts"])
        prompt = PROMPT.format(case_id=cid, domain=parsed["domain"], lang=parsed["language"], lang_name=LANG_NAME[parsed["language"]],
                               facts=parsed["facts"], acts=acts, trap_defs="\n".join(f"- {k}: {v}" for k, v in TRAP_TYPES.items()))
        try:
            text, meta = call_claude(prompt, args.model, binary)
            d = parse_json(text)
        except Exception as e:  # noqa: BLE001
            print(cid, "FAILED:", str(e)[:300]); rows.append({"case_id": cid, "status": "failed"}); continue
        d["_generation"] = {"model": args.model, "seconds": meta["_seconds"], "cost_usd": meta.get("total_cost_usd"), "session_id": meta.get("session_id")}
        problems = check(d)
        d["_check"] = problems
        out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        n_real = sum(1 for x in d["documents"] if x["ground_truth"]["status"] == "real")
        n_trap = len(d["documents"]) - n_real
        print(f"{cid}: {len(d['steps'])} steps, {n_real} real, {n_trap} traps, {meta['_seconds']}s, ${meta.get('total_cost_usd', 0):.2f}", "| PROBLEMS: " + "; ".join(problems) if problems else "| ok")
        rows.append({"case_id": cid, "status": "ok", "steps": len(d["steps"]), "real_docs": n_real, "traps": n_trap, "problems": "; ".join(problems), "seconds": meta["_seconds"], "cost_usd": meta.get("total_cost_usd")})

    idx_path = WORK / "dossier_index.csv"
    old = pd.read_csv(idx_path) if idx_path.exists() else pd.DataFrame()
    new = pd.concat([old[~old["case_id"].isin([r["case_id"] for r in rows])] if len(old) else old, pd.DataFrame(rows)], ignore_index=True)
    new.to_csv(idx_path, index=False)
    print("wrote", idx_path)


if __name__ == "__main__":
    main()
