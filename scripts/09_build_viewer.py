"""Step 9: build a single-file viewer for the generated dossiers.

Embeds testset/dossiers/*.json and, per step, the visible document ids and the
gold answer from testset/questions/*.jsonl (prompts are not embedded: the viewer
rebuilds the view from the dossier). Outcome label comes from testset/cases_100.jsonl.

Output: testset/viewer.html (open it in a browser, no server needed).
With --cases 8C_229/2024: testset/viewer_8C_229_2024.html with that case only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from common import ROOT, TESTSET

template = (ROOT / "scripts" / "viewer_template.html").read_text(encoding="utf-8")
outcomes = {}
for line in (TESTSET / "cases_100.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    outcomes[r["case_id"]] = r["outcome"]["label"]

only = [c.replace("/", "_") for c in sys.argv[sys.argv.index("--cases") + 1:]] if "--cases" in sys.argv else []
data = {}
for p in sorted((TESTSET / "dossiers").glob("*.json")):
    if only and p.stem not in only:
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    qpath = TESTSET / "questions" / (p.stem + ".jsonl")
    questions = []
    if qpath.exists():
        for line in qpath.open(encoding="utf-8"):
            q = json.loads(line)
            questions.append({"step_index": q["step_index"], "after_step": q["after_step"], "visible_doc_ids": q["visible_doc_ids"], "gold": q["gold"]})
    data[d["case_id"]] = {
        "case_id": d["case_id"], "language": d["language"], "domain": d.get("domain") or "",
        "outcome": outcomes.get(d["case_id"], ""),
        "steps": d["steps"], "documents": d["documents"], "absent_document": d.get("absent_document"), "questions": questions,
    }
    if not data[d["case_id"]]["domain"]:
        for line in (TESTSET / "cases_100.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            if r["case_id"] == d["case_id"]:
                data[d["case_id"]]["domain"] = r["domain"]; break

payload = json.dumps(data, ensure_ascii=False).replace("</", r"<\/")
html = template.replace("/*__DATA__*/", payload)
out = TESTSET / ("viewer_" + "_".join(only) + ".html" if only else "viewer.html")
out.write_text(html, encoding="utf-8")
print("cases:", len(data), "| wrote", out, "|", round(out.stat().st_size / 1e6, 2), "MB")
