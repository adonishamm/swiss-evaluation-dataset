"""Step 5: split the test set into what the agent sees and what the scorer sees.

data/work/agent_input_100.jsonl  -> case_id, language, domain, decision_date, facts, question
data/work/gold_100.jsonl         -> case_id, outcome, articles, precedents, dispositive
The agent file must never contain the gold fields.
"""
import json
from common import TESTSET, WORK

QUESTION = {
    "de": "Sie sind Anwalt/Anwältin in der Schweiz. Lesen Sie den Sachverhalt. Antworten Sie: (1) Wird das Bundesgericht die Beschwerde gutheissen oder abweisen? (2) Auf welche Gesetzesartikel stützt sich die Entscheidung (Gesetz + Artikel, z.B. Art. 42 Abs. 3 IVG)? (3) Kurze Begründung.",
    "fr": "Vous êtes avocat(e) en Suisse. Lisez les faits. Répondez : (1) Le Tribunal fédéral va-t-il admettre ou rejeter le recours ? (2) Sur quels articles de loi repose la décision (loi + article, ex. art. 42 al. 3 LAI) ? (3) Brève justification.",
    "it": "Lei è avvocato/a in Svizzera. Legga i fatti. Risponda: (1) Il Tribunale federale accoglierà o respingerà il ricorso? (2) Su quali articoli di legge si fonda la decisione (legge + articolo, es. art. 42 cpv. 3 LAI)? (3) Breve motivazione.",
}
inp = (WORK / "agent_input_100.jsonl").open("w", encoding="utf-8")
gold = (WORK / "gold_100.jsonl").open("w", encoding="utf-8")
n = 0
for line in (TESTSET / "cases_100.jsonl").open(encoding="utf-8"):
    r = json.loads(line); n += 1
    inp.write(json.dumps({"case_id": r["case_id"], "language": r["language"], "domain": r["domain"],
                          "decision_date": r["decision_date"], "facts": r["facts"],
                          "question": QUESTION[r["language"]]}, ensure_ascii=False) + "\n")
    gold.write(json.dumps({"case_id": r["case_id"], "language": r["language"], "domain": r["domain"],
                           "outcome": r["outcome"]["label"], "outcome_binary": r["outcome"]["label_binary"],
                           "winner": r["outcome"]["winner"], "dispositive": r["outcome"]["dispositive"],
                           "articles": [{"law": a["law"], "article": a["article"]} for a in r["cited_articles_substantive"]],
                           "precedents": [p["ref"] for p in r["cited_precedents"]["leading_cases"]],
                           "hardness": r["hardness"]}, ensure_ascii=False) + "\n")
print(n, "cases ->", WORK / "agent_input_100.jsonl", "and", WORK / "gold_100.jsonl")
