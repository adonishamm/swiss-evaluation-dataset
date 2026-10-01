"""Shared paths, domain mapping and text helpers for the Swiss ruling eval pipeline."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PARSED = DATA / "parsed"
TESTSET = ROOT / "testset"
for p in (DATA, RAW, PARSED, TESTSET):
    p.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (swiss-evaluation-dataset; research)"}

# ---------------------------------------------------------------------------
# Scope: personal-incident insurance. Regex on the index's fine legal area.
# ---------------------------------------------------------------------------
DOMAIN_PATTERNS = {
    "IV": r"Invalidenversicherung|Assurance-invalidit|per l'invalidit",
    "UV": r"Unfallversicherung|Assurance-accidents|contro gli infortuni",
    "KV": r"Krankenversicherung|Assurance-maladie|contro le malattie",
    "BVG": r"Berufliche Vorsorge|voyance professionnelle|Previdenza professionale|Previdenza professionnale",
    "AHV_EL": r"Alters- und Hinterlassenen|vieillesse et survivants|vecchiaia e per i superstiti|Erg.nzungsleist|prestations compl|prestazioni compl",
    "MV_EO": r"Milit.rvers|Erwerbsersatz|perte de gain en cas de service|Assicurazione militare",
}
# Private insurance (VVG/LCA) is not an area in the index; it is a civil-chamber
# case (4A/4D) whose subject line mentions an insurance contract or daily allowance.
PRIVATE_SUBJECT = re.compile(
    r"taggeld|indemnit.s? journali|versicherungsvertrag|contrat d.assurance|contratto d.assicurazione"
    r"|zusatzversicher|assurance compl|assicurazione compl|\bVVG\b|\bLCA\b|perte de gain",
    re.I,
)

OUTCOME_MAP = {
    "Abweisung": "dismissal",
    "Gutheissung": "approval",
    "teilweise Gutheissung": "partial_approval",
    "Teilweise Gutheissung": "partial_approval",
    "Nichteintreten": "inadmissible",
    "Gegenstandslosigkeit": "moot",
}
MERITS = {"dismissal", "approval", "partial_approval"}

# Subject-line flags that correlate with hard legal questions in this domain.
SUBJECT_FLAGS = {
    "causality": r"kausal|causalit|whiplash|schleudertrauma|nesso",
    "revision": r"rentenrevision|r.vision de la rente|revisione della rendita|\brevision\b|\br.vision\b",
    "restitution": r"r.ckerstattung|restitution|r.ckforderung|restituzione",
    "expert_report": r"gutachten|expertise|perizia",
    "coordination": r"koordination|.berentsch.dig|surindemnis|coordination|sovraindennizz",
    "psychiatric": r"psychi|d.press|somatoform|schmerz|douleur",
    "income_comparison": r"einkommensvergleich|comparaison des revenus|confronto dei redditi|invalidit.tsgrad|taux d.invalidit|grado d.invalidit",
    "deadline_formality": r"\bfrist|d.lai|termine|meldepflicht|obligation d.annoncer|obligo di notifica",
    "helplessness_assistance": r"hilflosen|impotent|grande invalidit|assistenzbeitrag|contribution d.assistance",
}


def domain_of(area: str, chamber: str, subject: str) -> str | None:
    area = area or ""
    if chamber in {"4A", "4D"} and PRIVATE_SUBJECT.search(subject or ""):
        return "PRIV_VVG"
    for key, rx in DOMAIN_PATTERNS.items():
        if re.search(rx, area, re.I):
            return key
    return None


# ---------------------------------------------------------------------------
# Section markers in Federal Supreme Court decisions, by language.
# ---------------------------------------------------------------------------
SECTION_MARKERS = {
    "de": (r"Sachverhalt\s*:", r"Erw.gungen\s*:", r"Demnach erkennt das Bundesgericht\s*:"),
    "fr": (r"Faits\s*:", r"Consid.rant en droit\s*:", r"Par ces motifs, le Tribunal f.d.ral prononce\s*:"),
    "it": (r"Fatti\s*:", r"Diritto\s*:", r"Per questi motivi, il Tribunale federale pronuncia\s*:"),
}

# Law abbreviations we accept as citation targets, per language, plus old-version prefix "a".
LAWS = {
    "de": "ATSG|IVG|UVG|KVG|BVG|AHVG|ELG|VVG|OR|ZGB|ZPO|BGG|BV|EMRK|IVV|UVV|KVV|BVV 2|AHVV|ELV|VwVG|MVG|EOG|FZG|AVIG|AVIV|KLV|OKP|StGB|ArG|FamZG",
    "fr": "LPGA|LAI|LAA|LAMal|LPP|LAVS|LPC|LCA|CO|CC|CPC|LTF|Cst\\.|CEDH|RAI|OLAA|OAMal|OPP 2|RAVS|OPC|LAM|LAPG|LFLP|LACI|OACI|OPAS|PA|CP|LTr|LAFam",
    "it": "LPGA|LAI|LAINF|LAMal|LPP|LAVS|LPC|LCA|CO|CC|CPC|LTF|Cost\\.|CEDU|OAI|OAINF|OAMal|OPP 2|OAVS|OPC|LAM|LIPG|LFLP|LADI|OADI|OPre|PA|CP|LL|LAFam",
}
PROCEDURAL_LAWS = {"BGG", "LTF"}  # admissibility boilerplate, excluded from the gold citation set


def citation_regex(lang: str) -> re.Pattern:
    laws = LAWS[lang]
    return re.compile(
        rf"\b[Aa]rt\.?\s*(\d+[a-z]{{0,6}})"          # article number, e.g. 16, 28a, 7b
        rf"(?:\s*(?:Abs\.|al\.|cpv\.)\s*\d+[a-z]?)?"  # optional paragraph
        rf"(?:\s*(?:lit\.|let\.|lett\.)\s*[a-z])?"    # optional letter
        rf"\s+(a?)({laws})\b"
    )


def strip_html(raw: str) -> str:
    import html as _html
    txt = re.sub(r"<script.*?</script>", " ", raw, flags=re.S)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return _html.unescape(re.sub(r"\s+", " ", txt)).strip()


def split_sections(text: str, lang: str) -> dict:
    """Return facts / considerations / dispositive slices and their character offsets."""
    f_rx, c_rx, d_rx = SECTION_MARKERS[lang]
    f = re.search(f_rx, text)
    c = re.search(c_rx, text[f.end():] if f else text)
    c_start = (f.end() + c.start()) if (f and c) else (c.start() if c else None)
    d = re.search(d_rx, text[c_start:] if c_start is not None else text)
    d_start = (c_start + d.start()) if (c_start is not None and d) else (d.start() if d else None)
    out = {"facts": "", "considerations": "", "dispositive": "", "ok": False}
    if f and c_start is not None and d_start is not None and f.end() < c_start < d_start:
        out["facts"] = text[f.end():c_start].strip()
        out["considerations"] = text[c_start:d_start].strip()
        out["dispositive"] = text[d_start:d_start + 3000].strip()
        out["ok"] = True
    return out


def extract_citations(considerations: str, lang: str) -> list[dict]:
    rx = citation_regex(lang)
    counts: dict[tuple, int] = {}
    for m in rx.finditer(considerations):
        art, old, law = m.group(1), m.group(2), m.group(3)
        law = law.replace("\\", "")
        key = (law, art, bool(old))
        counts[key] = counts.get(key, 0) + 1
    rows = [
        {"law": k[0], "article": k[1], "old_version": k[2], "count": v,
         "procedural": k[0] in PROCEDURAL_LAWS}
        for k, v in counts.items()
    ]
    rows.sort(key=lambda r: (-r["count"], r["law"], r["article"]))
    return rows


# Leading-case citations: BGE 148 V 174 / ATF 148 V 174 / DTF 148 V 174, and
# unpublished rulings cited by number: 8C_256/2025, arrêt 9C_65/2025.
PRECEDENT_RX = re.compile(r"\b(?:BGE|ATF|DTF)\s+(\d{2,3})\s+([IV]+[a-z]?)\s+(\d+)")
RULING_RX = re.compile(r"\b(\d[A-Z]_\d+/\d{4})\b")


def extract_precedents(considerations: str, own_id: str | None = None) -> dict:
    bge: dict[str, int] = {}
    for m in PRECEDENT_RX.finditer(considerations):
        key = f"BGE {m.group(1)} {m.group(2)} {m.group(3)}"
        bge[key] = bge.get(key, 0) + 1
    rulings: dict[str, int] = {}
    for m in RULING_RX.finditer(considerations):
        if m.group(1) != own_id:
            rulings[m.group(1)] = rulings.get(m.group(1), 0) + 1
    return {
        "leading_cases": sorted(({"ref": k, "count": v} for k, v in bge.items()), key=lambda r: -r["count"]),
        "other_rulings": sorted(({"ref": k, "count": v} for k, v in rulings.items()), key=lambda r: -r["count"]),
    }
