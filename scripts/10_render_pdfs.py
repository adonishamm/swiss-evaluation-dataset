"""Step 10: render the documents of a dossier as PDFs, the way they would sit in a file.

One PDF per document (letterhead, recipient block, place and date, reference,
subject, body, signature) and one merged PDF of the whole dossier with an index
page, in the dossier's own numbering (random order, as the agent receives it).
Trap labels never appear in the PDFs: that is the point.

Usage:
  python scripts/10_render_pdfs.py --cases 8C_229/2024
Output: testset/pdf/<case>/<doc_id>.pdf and testset/pdf/<case>/dossier_<case>.pdf,
plus a page-count table printed at the end.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from common import TESTSET

FONT_DIR = Path("C:/Windows/Fonts")
for name, file in [("Body", "times.ttf"), ("Body-Bold", "timesbd.ttf"), ("Body-Italic", "timesi.ttf"), ("Body-BoldItalic", "timesbi.ttf"), ("Head", "arial.ttf"), ("Head-Bold", "arialbd.ttf")]:
    f = FONT_DIR / file
    if not f.exists():
        f = FONT_DIR / {"times.ttf": "georgia.ttf", "timesbd.ttf": "georgiab.ttf", "timesi.ttf": "georgiai.ttf"}.get(file, file)
    pdfmetrics.registerFont(TTFont(name, str(f)))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")

S_HEAD = ParagraphStyle("head", fontName="Head-Bold", fontSize=10.5, leading=13)
S_HEAD_SM = ParagraphStyle("headsm", fontName="Head", fontSize=8.5, leading=11, textColor="#444444")
S_META = ParagraphStyle("meta", fontName="Body", fontSize=10.5, leading=14)
S_SUBJECT = ParagraphStyle("subject", fontName="Body-Bold", fontSize=11.5, leading=15, spaceBefore=6, spaceAfter=10)
S_BODY = ParagraphStyle("body", fontName="Body", fontSize=11, leading=15, alignment=TA_JUSTIFY, spaceAfter=6)
S_H2 = ParagraphStyle("h2", fontName="Body-Bold", fontSize=11, leading=15, spaceBefore=8, spaceAfter=3)
S_INDEX = ParagraphStyle("idx", fontName="Body", fontSize=10.5, leading=14)
S_TITLE = ParagraphStyle("title", fontName="Head-Bold", fontSize=16, leading=20, spaceAfter=14)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


HEADING_RX = re.compile(r"^(?:[A-Z][A-ZÀ-Ü' ]{3,}|[IVX]+\.\s.+|\d+(?:\.\d+)*\.?\s+[A-ZÀ-Ü].{0,70}|(?:Sachverhalt|Erwägungen|Dispositiv|Rechtsmittelbelehrung|Faits|Considérants|Dispositif|Voies de droit|Fatti|Diritto|Dispositivo|Rimedi giuridici|Objet|Betreff|Oggetto|Concerne)\b.*)$")


def body_flowables(body: str) -> list:
    out = []
    text = body.replace("\r", "")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)      # the generator sometimes bolds with markdown
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = text.replace("---", "")
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        lines = [l.strip() for l in para.split("\n") if l.strip()]
        if len(lines) == 1 and HEADING_RX.match(re.sub(r"<[^>]+>", "", lines[0])) and len(lines[0]) < 90:
            out.append(Paragraph(esc(lines[0]).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>"), S_H2))
        else:
            out.append(Paragraph("<br/>".join(esc(l) for l in lines).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>"), S_BODY))
    return out


def render_doc(x: dict, out: Path, case_id: str) -> int:
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=25 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title=x["title"], author=x["author"], subject=f"{case_id} {x['doc_id']}")
    story = [Paragraph(esc(x["author"]), S_HEAD), Paragraph(esc(x.get("reference") or ""), S_HEAD_SM), Spacer(1, 10 * mm)]
    story.append(Paragraph(esc(x["recipient"]).replace(", ", "<br/>", 2), S_META))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(esc(x["date"]), S_META))
    story.append(Paragraph(esc(x["title"]), S_SUBJECT))
    story.extend(body_flowables(x["body"]))
    doc.build(story)
    return len(PdfReader(str(out)).pages)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="+", required=True)
    args = ap.parse_args()
    for cid in args.cases:
        slug = cid.replace("/", "_")
        d = json.loads((TESTSET / "dossiers" / f"{slug}.json").read_text(encoding="utf-8"))
        outdir = TESTSET / "pdf" / slug
        outdir.mkdir(parents=True, exist_ok=True)
        rows, files = [], []
        for x in d["documents"]:
            p = outdir / f"{x['doc_id']}.pdf"
            n = render_doc(x, p, cid)
            rows.append((x["doc_id"], x["type"], x["date"], x["title"], len(x["body"].split()), n))
            files.append(p)
        # index page + merge
        idx = outdir / "_index.pdf"
        doc = SimpleDocTemplate(str(idx), pagesize=A4, leftMargin=25 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm, title=f"Dossier {cid}")
        story = [Paragraph(f"Dossier {esc(cid)}", S_TITLE), Paragraph("Bordereau des pièces", S_H2), Spacer(1, 4 * mm)]
        table = Table([["Pièce", "Date", "Intitulé", "Pages"]] + [[r[0], r[2], Paragraph(esc(r[3]), S_INDEX), str(r[5])] for r in rows],
                      colWidths=[16 * mm, 24 * mm, 110 * mm, 15 * mm])
        table.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Head-Bold", 9.5), ("FONT", (0, 1), (-1, -1), "Body", 10), ("LINEBELOW", (0, 0), (-1, 0), 0.6, "#000000"),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("ALIGN", (3, 0), (3, -1), "RIGHT")]))
        story.append(table)
        doc.build(story)
        writer = PdfWriter()
        for p in [idx] + files:
            for page in PdfReader(str(p)).pages:
                writer.add_page(page)
        merged = outdir / f"dossier_{slug}.pdf"
        with merged.open("wb") as f:
            writer.write(f)
        idx.unlink()
        total = sum(r[5] for r in rows)
        print(f"{cid}: {len(rows)} documents, {total} pages -> {merged}")
        print(f"  {'doc':5s} {'type':16s} {'words':>6s} {'pages':>5s}  title")
        for r in rows:
            print(f"  {r[0]:5s} {r[1]:16s} {r[4]:6d} {r[5]:5d}  {r[3][:70]}")


if __name__ == "__main__":
    main()
